"""Share the slice 1 matrix fixtures and this suite's rule fixtures."""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SLICE1_TESTS = _HERE.parents[1] / "reasoning-method-governance" / "tests"
for p in (_HERE, _SLICE1_TESTS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
