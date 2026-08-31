"""Make the forecasting test helpers importable under ``--import-mode=importlib``.

The repo runs pytest with importlib mode, which does not add each test file's directory
to ``sys.path``. Insert this directory so ``import fc_helpers`` resolves for the Phase-2
forecasting suite (mirrors how the package ``tests/conftest.py`` exposes ``support``).
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(__file__)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
