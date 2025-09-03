from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / '.venv'


def ensure_venv() -> None:
    """Ensure the script runs inside the local virtual environment.

    If the current interpreter is already the one from `.venv`, nothing
    happens. Otherwise, if the virtual environment exists and contains a
    Python executable, the current process is re-executed inside that
    interpreter. If the virtual environment is missing, execution
    continues but a warning is printed so features depending on the
    environment may fail.
    """
    if str(Path(sys.prefix).resolve()).startswith(str(VENV_DIR)):
        return

    python = VENV_DIR / ('Scripts' if os.name == 'nt' else 'bin') / (
        'python.exe' if os.name == 'nt' else 'python'
    )
    if python.exists():
        print('Re-running inside virtual environment...')
        os.execv(str(python), [str(python)] + sys.argv)
    else:
        print('Warning: virtual environment not found; proceeding with system Python')
