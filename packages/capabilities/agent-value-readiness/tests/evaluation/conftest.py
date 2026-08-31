"""Make ``_fixtures`` importable regardless of pytest's import mode."""

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
