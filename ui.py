from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn
from pathlib import Path


class UI:
    def __init__(self, log_path: str = "downloader.log"):
        self.console = Console()
        self.phase = ""
        self.progress = Progress(
            TextColumn("{task.description}"),
            BarColumn(),
            TextColumn("{task.percentage:>5.1f}%"),
            TextColumn("{task.fields[speed]}", justify="right"),
            TextColumn("ETA {task.fields[eta]}", justify="right"),
            console=self.console,
        )
        self.progress.start()
        self.tasks = {}
        self.log_path = Path(log_path).resolve()
        self.log_file = self.log_path.open("w", encoding="utf-8")
        self.console.log(f"Logging to {self.log_path}")

    def set_phase(self, phase):
        self.phase = phase
        self.log(f"[bold blue]Phase:[/bold blue] {phase}")

    def log(self, msg):
        self.console.log(msg)
        self.log_file.write(str(msg) + "\n")
        self.log_file.flush()

    def update_progress(self, name, percent, speed=None, eta=None):
        task = self.tasks.get(name)
        if task is None:
            task = self.progress.add_task(name, total=100, speed="", eta="")
            self.tasks[name] = task
        self.progress.update(task, completed=percent, speed=speed or "", eta=eta or "")

    def close(self):
        self.progress.stop()
        self.log_file.close()
