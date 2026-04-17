"""Add ``sdk/cohera/python`` to sys.path so ``import cohera`` works under pytest."""

import sys
from pathlib import Path

SDK_PYTHON = Path(__file__).resolve().parent.parent / "python"
if str(SDK_PYTHON) not in sys.path:
    sys.path.insert(0, str(SDK_PYTHON))
