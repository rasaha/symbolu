"""Make the shared fixtures module importable under ``--import-mode=importlib``."""

import pathlib
import sys

HERE = str(pathlib.Path(__file__).resolve().parent)
if HERE not in sys.path:
    sys.path.insert(0, HERE)
