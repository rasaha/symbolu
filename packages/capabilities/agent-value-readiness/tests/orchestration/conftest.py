"""Make ``_orchestration_fixtures`` importable regardless of pytest's import mode.

The module is named ``_orchestration_fixtures`` rather than ``_fixtures`` so a
combined multi-package pytest run cannot shadow another package's fixtures.
"""

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
