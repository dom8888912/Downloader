from rich.console import Console
from rich.table import Table

class UI:
    def __init__(self):
        self.console = Console()
        self.phase = ""

    def set_phase(self, phase):
        self.phase = phase
        self.console.log(f"[bold blue]Phase:[/bold blue] {phase}")

    def log(self, msg):
        self.console.log(msg)

    def update_progress(self, name, percent, speed=None, eta=None):
        self.console.log(f"{name}: {percent}% | {speed} | ETA {eta}")
