import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from threading import Thread
from queue import Queue
from downloader import process
from config import load_config


def append_log(msg: str) -> None:
    """Add a message to the queue for display in the GUI."""
    log_queue.put(msg)

def queue_progress(name: str, percent: float, speed: str, eta: str) -> None:
    """Forward progress updates to the main thread."""
    progress_queue.put((name, percent, speed, eta))

def queue_progress(name: str, percent: float, speed: str, eta: str) -> None:
    """Forward progress updates to the main thread."""
    progress_queue.put((name, percent, speed, eta))


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
        queue_progress(name, percent, speed, eta)


def worker(url: str) -> None:
    append_log(f"Starte Download: {url}")
    ui = TkUI()
    cfg = load_config([])
    try:
        process(url, cfg, ui)
        append_log("Fertig.")
    except Exception as e:
        append_log(f"Fehler: {e}")
    finally:
        done_queue.put(True)


def start_download() -> None:
    url = entry.get().strip()
    if not url:
        return
    entry.config(state=tk.DISABLED)
    btn.config(state=tk.DISABLED)
    progress_var.set(0)
    pb.config(mode="indeterminate")
    pb.start(10)
    status_var.set("Verbinde…")
    Thread(target=worker, args=(url,), daemon=True).start()


def poll_queues() -> None:
    while not log_queue.empty():
        text.insert(tk.END, log_queue.get() + "\n")
        text.see(tk.END)

    while not progress_queue.empty():
        name, percent, speed, eta = progress_queue.get()
        if str(pb.cget("mode")) == "indeterminate":
            pb.stop()
            pb.config(mode="determinate")
        progress_var.set(percent)
        status_var.set(f"{name}: {percent:5.1f}% {speed} ETA {eta}")

    while not done_queue.empty():
        done_queue.get()
        pb.stop()
        pb.config(mode="determinate")
        progress_var.set(0)
        status_var.set("Bereit")
        entry.config(state=tk.NORMAL)
        btn.config(state=tk.NORMAL)

    root.after(100, poll_queues)


root = tk.Tk()
root.title("Downloader")

style = ttk.Style(root)
try:
    style.theme_use("clam")
except tk.TclError:
    pass
style.configure("TProgressbar", thickness=12)
style.configure("TButton", padding=6)

frame = ttk.Frame(root, padding=10)
frame.pack(fill="both", expand=True)
frame.columnconfigure(0, weight=1)

entry = ttk.Entry(frame, width=50)
entry.grid(row=0, column=0, padx=5, pady=5, sticky="ew")

btn = ttk.Button(frame, text="Download", command=start_download)
btn.grid(row=0, column=1, padx=5, pady=5)

progress_var = tk.DoubleVar(value=0)
pb = ttk.Progressbar(frame, variable=progress_var, maximum=100)
pb.grid(row=1, column=0, columnspan=2, sticky="ew", padx=5, pady=5)

status_var = tk.StringVar(value="Bereit")
status = ttk.Label(frame, textvariable=status_var)
status.grid(row=2, column=0, columnspan=2, sticky="w", padx=5)

text = ScrolledText(frame, width=60, height=15)
text.grid(row=3, column=0, columnspan=2, sticky="nsew", padx=5, pady=5)
frame.rowconfigure(3, weight=1)

log_queue: Queue[str] = Queue()
progress_queue: Queue[tuple[str, float, str, str]] = Queue()
done_queue: Queue[bool] = Queue()
poll_queues()

root.mainloop()
