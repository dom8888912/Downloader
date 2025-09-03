import asyncio
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional, Tuple

import requests
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
from playwright.async_api import async_playwright

# flag to avoid repeatedly trying Playwright when the bundled browsers are
# missing and sniffing is therefore impossible
PLAYWRIGHT_AVAILABLE = True
from rich.table import Table

STREAM_EXTS = (".m3u8", ".mpd", ".mp4")

# Known embed host patterns whose URLs we can hand off to yt-dlp
HOST_HINTS = [
    "supervideo.cc",
    "p2pplay",
    "kinoger.pw",
    "kinoger.ru",
]

# rudimentary ad host patterns that should be blocked during sniffing
AD_PATTERNS = [
    "doubleclick",
    "googlesyndication",
    "adservice",
    "popads",
    "ads.",
]

# HTTP headers used for all yt-dlp requests so that hosts protected by
# Cloudflare see us as a regular browser
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Sec-Fetch-Mode": "navigate",
}


def _fetch_html(url: str) -> str:
    """Retrieve ``url`` using yt-dlp's HTTP client with impersonation.

    Some hosts (e.g. Cloudflare protected sites) block plain ``requests``
    calls. By reusing yt-dlp's downloader with ``generic:impersonate`` we
    mimic a real browser and get the full HTML needed to locate embed
    players.
    """
    opts = {
        "quiet": True,
        "extractor_args": {"generic": ["impersonate"]},
        "http_headers": HEADERS,
    }
    try:
        with YoutubeDL(opts) as ydl:
            with ydl.urlopen(url) as resp:
                data = resp.read()
    except Exception:
        opts.pop("extractor_args", None)
        with YoutubeDL(opts) as ydl:
            with ydl.urlopen(url) as resp:
                data = resp.read()
    try:
        return data.decode()
    except Exception:
        return data.decode("utf-8", errors="ignore")


def _extract_embeds(html: str) -> list[str]:
    urls = set(re.findall(r"https?://[^\"'\s]+", html))
    return [u for u in urls if any(h in u for h in HOST_HINTS)]


async def _sniff(url: str, ui=None) -> list[str]:
    """Capture media requests by exploring the page with Playwright.

    If launching the browser fails (e.g. because ``playwright install`` wasn't
    run), the failure is propagated and ``PLAYWRIGHT_AVAILABLE`` is set to
    ``False`` so later calls can skip sniffing altogether.
    """
    global PLAYWRIGHT_AVAILABLE
    try:
        async with async_playwright() as pw:
            browser = await pw.firefox.launch(headless=True)
            context = await browser.new_context()

            async def block_ads(route):
                if any(pat in route.request.url for pat in AD_PATTERNS):
                    if ui:
                        ui.log(f"Blocked {route.request.url}")
                    await route.abort()
                else:
                    await route.continue_()

            await context.route("**", block_ads)

            page = await context.new_page()
            page.on("popup", lambda p: asyncio.create_task(p.close()))
            context.on("page", lambda p: asyncio.create_task(p.close()))

            found: set[str] = set()

            async def handle_response(response):
                u = response.url.split("?")[0]
                if u.endswith(STREAM_EXTS):
                    found.add(response.url)
                    if ui:
                        ui.log(f"Found {response.url}")

            context.on("response", handle_response)

            # Visiting some pages takes a while. We do not want navigation
            # timeouts to abort sniffing, so swallow any errors and keep waiting
            # for network responses instead.
            try:
                await page.goto(url, timeout=60_000)
            except Exception:
                pass

            visited: set[int] = set()

            async def trigger(frame):
                fid = id(frame)
                if fid in visited:
                    return
                visited.add(fid)

                selectors = [
                    "button[aria-label*=play i]",
                    "button",
                    "div[role=button]",
                    "div[id*=play]",
                    "div[class*=play]",
                    "span[class*=play]",
                    "video",
                ]
                for sel in selectors:
                    try:
                        await frame.locator(sel).first.click(timeout=1_000, force=True, no_wait_after=True)
                        break
                    except Exception:
                        continue
                try:
                    await frame.evaluate("document.querySelectorAll('video').forEach(v=>v.play())")
                except Exception:
                    pass
            page.on("frameattached", lambda f: asyncio.create_task(trigger(f)))

            end = asyncio.get_event_loop().time() + 30
            while asyncio.get_event_loop().time() < end:
                for f in page.frames:
                    await trigger(f)
                await asyncio.sleep(2)
            await browser.close()
            return list(found)
    except Exception as e:
        PLAYWRIGHT_AVAILABLE = False
        if "Executable doesn't exist" in str(e) and ui:
            # Offer a concise hint for the common case of missing browsers
            ui.log("Playwright-Browser fehlen – `playwright install` ausführen")
        raise


def _format_size(size: Optional[int]) -> str:
    if not size:
        return "?"
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _probe_stream(url: str) -> Tuple[int, Optional[int], Optional[str]]:
    """Return ``(height, size, error)`` for ``url``.

    ``error`` contains a short message if probing failed.
    """
    opts = {
        "quiet": True,
        "extractor_args": {"generic": ["impersonate"]},
        "http_headers": HEADERS,
    }
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        try:
            opts.pop("extractor_args", None)
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            return 0, None, str(e)
    formats = info.get("formats") or [info]
    best = max(formats, key=lambda f: f.get("height") or 0)
    height = best.get("height") or 0
    size = best.get("filesize") or best.get("filesize_approx")
    return height, size, None


def _verify_resolution(path: str) -> int:
    """Return the height of the first video stream in ``path``.

    This uses ``ffprobe`` on the downloaded file as a fallback verification
    step since some hosts may not expose accurate metadata via yt-dlp.
    """
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=height",
            "-of",
            "csv=p=0",
            path,
        ]
        out = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return int(out.stdout.strip())
    except Exception:
        return 0


def resolve_url(url: str, ui, min_height: int) -> Tuple[list[str], int]:
    if url.split("?")[0].endswith(STREAM_EXTS):
        height, _, err = _probe_stream(url)
        if err:
            raise RuntimeError(f"Stream nicht nutzbar: {err}")
        if height < min_height:
            ui.log(f"Stream bietet nur {height}p – verwende niedrigere Qualität")
            min_height = height
        return [url], min_height

    embeds: list[str] = []
    try:
        html = _fetch_html(url)
        embeds = _extract_embeds(html)
    except Exception:
        pass
    candidates = list(dict.fromkeys(embeds))

    def probe(cands: list[str]):
        if not cands:
            return []
        with ThreadPoolExecutor() as ex:
            infos = list(ex.map(_probe_stream, cands))
        items = list(zip(cands, infos))
        return sorted(
            items,
            key=lambda x: ((x[1][0] or 0), x[1][1] or 0),
            reverse=True,
        )

    items = probe(candidates)

    candidates = list(dict.fromkeys(embeds))

    def probe(cands: list[str]):
        if not cands:
            return []
        with ThreadPoolExecutor() as ex:
            infos = list(ex.map(_probe_stream, cands))
        items = list(zip(cands, infos))
        return sorted(
            items,
            key=lambda x: ((x[1][0] or 0), x[1][1] or 0),
            reverse=True,
        )

    items = probe(candidates)

    for s, (h, _, err) in items:
        if err:
            ui.log(f"{s} nicht nutzbar: {err}")
        elif h < 1080:
            ui.log(f"{s} bietet nur {h}p")

    candidates = list(dict.fromkeys(embeds))

    def probe(cands: list[str]):
        if not cands:
            return []
        with ThreadPoolExecutor() as ex:
            infos = list(ex.map(_probe_stream, cands))
        items = list(zip(cands, infos))
        return sorted(
            items,
            key=lambda x: ((x[1][0] or 0), x[1][1] or 0),
            reverse=True,
        )

    items = probe(candidates)

    for s, (h, _, err) in items:
        if err:
            ui.log(f"{s} nicht nutzbar: {err}")
        elif h < min_height:
            ui.log(f"{s} bietet nur {h}p")

    hd_items = [(s, info) for s, info in items if info[0] >= min_height and not info[2]]

    if not hd_items and PLAYWRIGHT_AVAILABLE:
        ui.log(f"Keine Streams mit ≥{min_height}p gefunden – starte Playwright-Sniffing")
        sniffed: list[str] = []
        try:
            sniffed = asyncio.run(_sniff(url, ui))
        except Exception as e:
            ui.log(f"Sniff failed: {e}")
        candidates = list(dict.fromkeys(candidates + sniffed))
        items = probe(candidates)
        for s, (h, _, err) in items:
            if err:
                ui.log(f"{s} nicht nutzbar: {err}")
            elif h < min_height:
                ui.log(f"{s} bietet nur {h}p")
        hd_items = [(s, info) for s, info in items if info[0] >= min_height and not info[2]]

    if not hd_items:
        valid = [(s, info) for s, info in items if info[0] and not info[2]]
        if not valid:
            raise RuntimeError("Kein Stream in geforderter Qualität gefunden")
        fallback_height = valid[0][1][0]
        ui.log(
            f"Keine Streams mit ≥{min_height}p gefunden – wähle {fallback_height}p"
        )
        min_height = fallback_height
        hd_items = [(s, info) for s, info in valid if info[0] >= fallback_height]

    if not items:
        raise RuntimeError("Kein Stream in geforderter Qualität gefunden")

    table = Table(title="Gefundene Streams")
    table.add_column("Nr")
    table.add_column("URL")
    table.add_column("Qualität")
    table.add_column("Größe")
    for i, (s, (h, size, err)) in enumerate(items, start=1):
        qual = f"{h}p" if h else "?"
        if err:
            qual = "-"
        table.add_row(str(i), s, qual, _format_size(size))
    ui.console.print(table)

    choice = ui.console.input("Welche URL verwenden? [1]: ")
    try:
        idx = int(choice) - 1 if choice.strip() else 0
    except ValueError:
        idx = 0
    idx = max(0, min(idx, len(hd_items) - 1))

    ordered = [hd_items[idx][0]]
    ordered.extend(s for i, (s, _) in enumerate(hd_items) if i != idx)
    return ordered, min_height


def download(url: str, out: str, ui, min_height: int) -> str:
    Path(out).mkdir(parents=True, exist_ok=True)
    result = {"path": None}

    def hook(d):
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
            percent = round(d.get("downloaded_bytes", 0) / total * 100, 1)
            speed = d.get("_speed_str", "")
            eta = d.get("_eta_str", "")
            ui.update_progress(Path(d.get("filename", "")).name, percent, speed, eta)
        elif d.get("status") == "finished":
            result["path"] = d.get("filename")
            ui.log(f"Finished {d.get('filename')}")

    class YTLogger:
        def __init__(self, ui):
            self.ui = ui

        def debug(self, msg):
            self.ui.log(msg)

        info = debug

        def warning(self, msg):
            self.ui.log(f"[yellow]{msg}[/yellow]")

        def error(self, msg):
            self.ui.log(f"[red]{msg}[/red]")

    ydl_opts = {
        "outtmpl": str(Path(out) / "%(title)s.%(ext)s"),
        "progress_hooks": [hook],
        "concurrent_fragment_downloads": 5,
        # Use HTTP client impersonation to bypass Cloudflare checks on generic sites
        "extractor_args": {"generic": ["impersonate"]},
        # ensure at least Full HD quality
        "format": f"bestvideo[height>={min_height}]+bestaudio/best[height>={min_height}]",
        "http_headers": HEADERS,
        # disable yt-dlp's own progress output so only the rich progress bar is shown
        "noprogress": True,
        "quiet": False,
        "verbose": True,
        "logger": YTLogger(ui),
    }
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    return result["path"] or ""


def upload_to_koofr(local_path: str, cfg, ui) -> None:
    user, password = cfg.koofr_user, cfg.koofr_password
    if not (user and password):
        ui.log("Keine Koofr-Credentials, Upload übersprungen")
        return
    base = cfg.koofr_base.strip("/")
    filename = Path(local_path).name
    url = f"https://app.koofr.net/dav/{base}/{filename}" if base else f"https://app.koofr.net/dav/{filename}"
    with open(local_path, "rb") as f:
        resp = requests.put(url, data=f, auth=(user, password))
    resp.raise_for_status()
    ui.log(f"Upload nach Koofr abgeschlossen: {filename}")


def connect_vpn(server: Optional[str], ui) -> None:
    if not server:
        return
    ui.log(f"Verbinde VPN: {server}")
    subprocess.run(["surfshark-vpn", "connect", server], check=False)


def disconnect_vpn(ui) -> None:
    ui.log("Trenne VPN")
    subprocess.run(["surfshark-vpn", "disconnect"], check=False)


def process(url: str, cfg, ui) -> None:
    candidates, min_height = resolve_url(url, ui, cfg.min_height)
    seen: set[str] = set()

    while candidates:
        target = candidates.pop(0)
        if target in seen:
            continue
        seen.add(target)
        ui.log(f"Versuche {target}")
        height, _, err = _probe_stream(target)
        if err:
            ui.log(f"Stream {target} nicht nutzbar: {err}")
            continue
        if height < min_height:
            ui.log(f"Stream {target} bietet nur {height}p – überspringe")
            continue
        try:
            path = download(target, cfg.out, ui, min_height)
        except Exception as e:
            ui.log(f"yt-dlp konnte {target} nicht verarbeiten: {e}; versuche nächste URL")
            if PLAYWRIGHT_AVAILABLE:
                try:
                    extra = asyncio.run(_sniff(target, ui))
                except Exception as e2:
                    ui.log(f"Sniff fehlgeschlagen: {e2}")
                else:
                    hd_extra = []
                    for s in extra:
                        h, _, err = _probe_stream(s)
                        if err:
                            ui.log(f"{s} nicht nutzbar: {err}")
                        elif h < min_height:
                            ui.log(f"{s} bietet nur {h}p")
                        else:
                            hd_extra.append(s)
                    candidates[0:0] = hd_extra
            continue
        if path:
            final_height = _verify_resolution(path)
            if final_height < min_height:
                ui.log(f"Download bietet nur {final_height}p – versuche nächste URL")
                try:
                    Path(path).unlink()
                except Exception:
                    pass
                continue
            upload_to_koofr(path, cfg, ui)
            break
