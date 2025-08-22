from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn

class UI:
    def __init__(self):
        self.console = Console()
        self.phase = ""
        self.progress = Progress(
            TextColumn("{task.description}"),
            BarColumn(),
            TextColumn("{task.percentage:>3.0f}%"),
            console=self.console,
        )
        self.progress.start()
        self.tasks = {}

    def set_phase(self, phase):
        self.phase = phase
        self.console.log(f"[bold blue]Phase:[/bold blue] {phase}")

    def log(self, msg):
        self.console.log(msg)

    def update_progress(self, name, percent, speed=None, eta=None):
        task = self.tasks.get(name)
        if task is None:
            task = self.progress.add_task(name, total=100)
            self.tasks[name] = task
        self.progress.update(task, completed=percent)
