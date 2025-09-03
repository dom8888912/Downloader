#!/usr/bin/env python3
"""One-shot environment setup for the video downloader.

This script creates a virtual environment in `.venv`, installs all
required dependencies (including the libraries needed for Cloudflare
impersonation), downloads Playwright's Firefox browser and generates a
small helper script for starting the GUI via double click.

Run with: `python setup.py`
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
BIN_DIR = VENV_DIR / ("Scripts" if os.name == "nt" else "bin")
# Use pythonw.exe on Windows so the GUI launches without a console window.
PYTHON = BIN_DIR / ("python.exe" if os.name == "nt" else "python")
PYTHONW = BIN_DIR / ("pythonw.exe" if os.name == "nt" else "python")


def run(cmd: list[str]) -> None:
    """Run a subprocess, printing the command for transparency."""
    print(" →", " ".join(cmd))
    subprocess.check_call(cmd)


def ensure_venv() -> None:
    if not VENV_DIR.exists():
        run([sys.executable, "-m", "venv", str(VENV_DIR)])


def install_deps() -> None:
    run([str(PYTHON), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(PYTHON), "-m", "pip", "install", "-r", "requirements.txt"])
    run([str(PYTHON), "-m", "playwright", "install", "firefox"])


def create_launcher() -> None:
    if os.name == "nt":
        exe = PYTHONW if PYTHONW.exists() else PYTHON
        launcher = ROOT / "run_gui.bat"
        content = f"@echo off\n\"{exe}\" \"{ROOT / 'simple_gui.py'}\"\n"
    else:
        launcher = ROOT / "run_gui.sh"
        content = f"#!/bin/sh\n\"{PYTHON}\" \"{ROOT / 'simple_gui.py'}\"\n"
    launcher.write_text(content)
    if os.name != "nt":
        launcher.chmod(0o755)
    print(f"Launcher created: {launcher}")

    desktop = Path(os.environ.get("USERPROFILE" if os.name == "nt" else "HOME", "")) / "Desktop"
    if desktop.exists():
        desktop_launcher = desktop / launcher.name
        desktop_launcher.write_text(content)
        if os.name != "nt":
            desktop_launcher.chmod(0o755)
        print(f"Desktop shortcut created: {desktop_launcher}")


def main() -> None:
    ensure_venv()
    install_deps()
    create_launcher()
    print("\nSetup complete. Use the generated launcher to start the GUI.")


if __name__ == "__main__":
    main()
