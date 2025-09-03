import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from threading import Thread
from queue import Queue
from types import SimpleNamespace
from downloader import process


def append_log(msg: str) -> None:
    """Add a message to the queue for display in the GUI."""
    log_queue.put(msg)


class TkConsole:
    def print(self, *args, **kwargs):
        append_log(" ".join(str(a) for a in args))

    def input(self, prompt: str = "") -> str:
        append_log(prompt)
        return ""  # use default selection


class TkUI:
    def __init__(self):
        self.console = TkConsole()

    def log(self, msg: str) -> None:
        append_log(str(msg))

    def update_progress(self, name: str, percent: float, speed: str = "", eta: str = "") -> None:
        append_log(f"{name}: {percent:5.1f}% {speed} ETA {eta}")


def worker(url: str) -> None:
    append_log(f"Starte Download: {url}")
    ui = TkUI()
    cfg = SimpleNamespace(
        out="downloads",
        koofr_user=None,
        koofr_password=None,
        koofr_base="",
        surfshark_server=None,
    )
    try:
        process(url, cfg, ui)
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
