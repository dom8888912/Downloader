import asyncio
import subprocess
from pathlib import Path
from typing import Optional

import requests
from yt_dlp import YoutubeDL
from playwright.async_api import async_playwright

STREAM_EXTS = (".m3u8", ".mpd", ".mp4")


async def _sniff(url: str) -> Optional[str]:
    async with async_playwright() as pw:
        browser = await pw.firefox.launch(headless=True)
        page = await browser.new_page()
        found: asyncio.Future[Optional[str]] = asyncio.Future()

        async def handle_response(response):
            if not found.done():
                u = response.url.split("?")[0]
                if u.endswith(STREAM_EXTS):
                    found.set_result(response.url)

        page.on("response", handle_response)
        await page.goto(url)

        # First wait a moment for direct stream requests during page load.
        try:
            return await asyncio.wait_for(found, timeout=5)
        except asyncio.TimeoutError:
            # Some sites only load the stream after playback starts. Trigger
            # a muted play attempt to satisfy autoplay restrictions.
            try:
                await page.evaluate(
                    """
() => {
    const v = document.querySelector('video');
    if (v) {
        v.muted = true;
        v.play().catch(() => {});
    }
    const btn = document.querySelector('button');
    if (btn) btn.click();
}
"""
                )
            except Exception:
                pass
            try:
                return await asyncio.wait_for(found, timeout=10)
            except asyncio.TimeoutError:
                return None
        finally:
            await browser.close()


def resolve_url(url: str, ui) -> str:
    if url.split("?")[0].endswith(STREAM_EXTS):
        return url
    ui.log("Sniffing stream URL via Playwright")
    try:
        sniffed = asyncio.run(_sniff(url))
        return sniffed or url
    except Exception as e:
        ui.log(f"Sniff failed: {e}")
        return url


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
