"""Package-local pytest bootstrap.

These tests run WITHOUT the monorepo application layer. When run from a source
checkout, the package's ``src`` directory and this ``tests`` directory are placed on
the path here; when run from an installed wheel, the package import already resolves
and only the tests directory is added (for ``art_fakes``). No fixture is imported
from any monorepo application directory.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SRC = _HERE.parents[0] / "src"

# The tests directory is always needed (for ``art_fakes``).
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

# Only fall back to the source tree when the package is NOT already importable.
# When running from an installed wheel, the package resolves from site-packages and
# ``src`` must NOT be added (otherwise the source would shadow the installed wheel and
# check 53 — "tests run from the installed wheel" — would be meaningless).
if importlib.util.find_spec("ugence_agent_runtime") is None and _SRC.is_dir():
    sys.path.insert(0, str(_SRC))
