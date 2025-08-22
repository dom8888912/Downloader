import asyncio
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import requests
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
from playwright.async_api import async_playwright
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


def _fetch_html(url: str) -> str:
    """Retrieve ``url`` using yt-dlp's HTTP client with impersonation.

    Some hosts (e.g. Cloudflare protected sites) block plain ``requests``
    calls. By reusing yt-dlp's downloader with ``generic:impersonate`` we
    mimic a real browser and get the full HTML needed to locate embed
    players.
    """
    ydl_opts = {"quiet": True, "extractor_args": {"generic": ["impersonate"]}}
    with YoutubeDL(ydl_opts) as ydl:
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

    The function is declared as a coroutine so that ``await`` statements such
    as ``page.goto`` operate within an async context, preventing the
    "await outside async function" syntax error reported by some users.
    """
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


def _format_size(size: Optional[int]) -> str:
    if not size:
        return "?"
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _head_size(url: str) -> Optional[int]:
    try:
        resp = requests.head(
            url,
            allow_redirects=True,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        cl = resp.headers.get("Content-Length")
        return int(cl) if cl else None
    except Exception:
        return None


def resolve_url(url: str, ui) -> list[str]:
    if url.split("?")[0].endswith(STREAM_EXTS):
        return [url]

    embeds: list[str] = []
    try:
        html = _fetch_html(url)
        embeds = _extract_embeds(html)
    except Exception:
        pass

    sniffed: list[str] = []
    if not embeds:
        ui.log("Sniffing stream URL via Playwright")
        try:
            sniffed = asyncio.run(_sniff(url, ui))
        except Exception as e:
            ui.log(f"Sniff failed: {e}")

    candidates = list(dict.fromkeys(embeds + sniffed))
    if not candidates:
        return [url]

    with ThreadPoolExecutor() as ex:
        sizes = list(ex.map(_head_size, candidates))
    items = sorted(zip(candidates, sizes), key=lambda x: x[1] or 0, reverse=True)

    table = Table(title="Gefundene Streams")
    table.add_column("Nr")
    table.add_column("URL")
    table.add_column("Größe")
    for i, (s, size) in enumerate(items, start=1):
        table.add_row(str(i), s, _format_size(size))
    ui.console.print(table)

    # use Rich's input method so the prompt remains visible while the progress bar is active
    choice = ui.console.input("Welche URL verwenden? [1]: ")
    try:
        idx = int(choice) - 1 if choice.strip() else 0
    except ValueError:
        idx = 0
    idx = max(0, min(idx, len(items) - 1))

    # return selected URL first, followed by the remaining candidates so callers
    # can try alternatives if the first choice fails
    ordered = [items[idx][0]]
    ordered.extend(s for i, (s, _) in enumerate(items) if i != idx)
    return ordered


def download(url: str, out: str, ui) -> str:
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
    candidates = resolve_url(url, ui)
    seen: set[str] = set()

    while candidates:
        target = candidates.pop(0)
        if target in seen:
            continue
        seen.add(target)
        ui.log(f"Versuche {target}")
        try:
            path = download(target, cfg.out, ui)
        except Exception as e:
            ui.log(f"yt-dlp konnte {target} nicht verarbeiten: {e}; versuche nächste URL")
            try:
                extra = asyncio.run(_sniff(target, ui))
            except Exception as e2:
                ui.log(f"Sniff fehlgeschlagen: {e2}")
            else:
                candidates.extend(extra)
            continue
        if path:
            upload_to_koofr(path, cfg, ui)
            break
