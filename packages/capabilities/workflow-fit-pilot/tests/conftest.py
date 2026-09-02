"""Share the Slice 1 matrix fixtures, the Slice 2 rule fixtures and this suite's pilot fixtures."""

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_CAP = _HERE.parents[1]
for p in (_HERE, _CAP / "reasoning-method-governance" / "tests", _CAP / "reasoning-method-advisor" / "tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
