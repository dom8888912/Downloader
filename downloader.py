import asyncio
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import requests
from yt_dlp import YoutubeDL
from playwright.async_api import async_playwright
from rich.table import Table

STREAM_EXTS = (".m3u8", ".mpd", ".mp4")


async def _sniff(url: str) -> list[str]:
    async with async_playwright() as pw:
        browser = await pw.firefox.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        found: set[str] = set()

        async def handle_response(response):
            u = response.url.split("?")[0]
            if u.endswith(STREAM_EXTS):
                found.add(response.url)

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
        resp = requests.head(url, allow_redirects=True, timeout=10)
        cl = resp.headers.get("Content-Length")
        return int(cl) if cl else None
    except Exception:
        return None


def resolve_url(url: str, ui) -> str:
    if url.split("?")[0].endswith(STREAM_EXTS):
        return url
    ui.log("Sniffing stream URL via Playwright")
    try:
        sniffed = asyncio.run(_sniff(url))
    except Exception as e:
        ui.log(f"Sniff failed: {e}")
        return url
    if not sniffed:
        return url

    with ThreadPoolExecutor() as ex:
        sizes = list(ex.map(_head_size, sniffed))
    items = sorted(zip(sniffed, sizes), key=lambda x: x[1] or 0, reverse=True)

    table = Table(title="Gefundene Streams")
    table.add_column("Nr")
    table.add_column("URL")
    table.add_column("Größe")
    for i, (s, size) in enumerate(items, start=1):
        table.add_row(str(i), s, _format_size(size))
    ui.console.print(table)

    choice = input("Welche URL verwenden? [1]: ")
    try:
        idx = int(choice) - 1 if choice.strip() else 0
    except ValueError:
        idx = 0
    idx = max(0, min(idx, len(items) - 1))
    return items[idx][0]


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

    ydl_opts = {
        "outtmpl": str(Path(out) / "%(title)s.%(ext)s"),
        "progress_hooks": [hook],
        "concurrent_fragment_downloads": 5,
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
    target = resolve_url(url, ui)
    path = download(target, cfg.out, ui)
    if path:
        upload_to_koofr(path, cfg, ui)
