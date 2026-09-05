"""Share the §11 matrix fixtures published by the contracts package's tests."""

import sys
from pathlib import Path

_CONTRACT_TESTS = Path(__file__).resolve().parents[2] / "reasoning-method-governance" / "tests"
if str(_CONTRACT_TESTS) not in sys.path:
    sys.path.insert(0, str(_CONTRACT_TESTS))
