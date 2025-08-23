import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from threading import Thread
from queue import Queue
from pathlib import Path
import os
from yt_dlp import YoutubeDL


def append_log(msg: str) -> None:
    """Add a message to the queue for display in the GUI."""
    log_queue.put(msg)


def download_url(url: str, log) -> None:
    """Download ``url`` using yt-dlp, logging progress via ``log``."""
    base = url.rstrip('/').split('/')[-1].split('?')[0]
    name = os.path.splitext(base)[0]
    outdir = Path("downloads")
    outdir.mkdir(exist_ok=True)
    outtmpl = str(outdir / f"{name}.%(ext)s")

    def hook(d):
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
            percent = d.get("downloaded_bytes", 0) / total * 100
            speed = d.get("_speed_str", "")
            eta = d.get("_eta_str", "")
            log(f"{percent:5.1f}% {speed} ETA {eta}")
        elif d.get("status") == "finished":
            log(f"Abgeschlossen: {d.get('filename')}")

    ydl_opts = {
        "outtmpl": outtmpl,
        "progress_hooks": [hook],
        "noprogress": True,
        "quiet": True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def worker(url: str) -> None:
    append_log(f"Starte Download: {url}")
    try:
        download_url(url, append_log)
        append_log("Fertig.")
    except Exception as e:
        append_log(f"Fehler: {e}")


def start_download() -> None:
    url = entry.get().strip()
    if not url:
        return
    Thread(target=worker, args=(url,), daemon=True).start()


def update_log() -> None:
    while not log_queue.empty():
        text.insert(tk.END, log_queue.get() + "\n")
        text.see(tk.END)
    root.after(100, update_log)


root = tk.Tk()
root.title("Downloader")

entry = tk.Entry(root, width=50)
entry.pack(padx=5, pady=5)

btn = tk.Button(root, text="Download", command=start_download)
btn.pack(padx=5, pady=5)

text = ScrolledText(root, width=60, height=20)
text.pack(padx=5, pady=5)

log_queue = Queue()
update_log()

root.mainloop()
