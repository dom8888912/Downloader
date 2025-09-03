#!/usr/bin/env python3
"""One-shot environment setup for the video downloader.

This script creates a virtual environment in `.venv`, installs all
required dependencies (including the Cloudflare impersonation extras for
yt-dlp), downloads Playwright's Firefox browser and generates a small
helper script for starting the GUI via double click.

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
PYTHON = BIN_DIR / ("python.exe" if os.name == "nt" else "python")


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
    # Install yt-dlp with Cloudflare extras so impersonation works out of the box
    run([str(PYTHON), "-m", "pip", "install", "yt-dlp[cloudflare]"])
    run([str(PYTHON), "-m", "playwright", "install", "firefox"])


def create_launcher() -> None:
    if os.name == "nt":
        launcher = ROOT / "run_gui.bat"
        content = f"@echo off\n\"{PYTHON}\" \"{ROOT / 'simple_gui.py'}\"\n"
    else:
        launcher = ROOT / "run_gui.sh"
        content = f"#!/bin/sh\n\"{PYTHON}\" \"{ROOT / 'simple_gui.py'}\"\n"
    launcher.write_text(content)
    if os.name != "nt":
        launcher.chmod(0o755)
    print(f"Launcher created: {launcher}")


def main() -> None:
    ensure_venv()
    install_deps()
    create_launcher()
    print("\nSetup complete. Use the generated launcher to start the GUI.")


if __name__ == "__main__":
    main()
