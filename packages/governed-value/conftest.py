"""Make the ``src`` layout and the shared contract layer importable in-place.

Mirrors the other governance capabilities: the package is tested from source
without an editable install, so its own ``src`` directory and that of
``governance-contracts`` — the one Ugence dependency this kernel declares, for
``MetricObservation`` (GV-DEP) — are prepended to ``sys.path``.
"""

from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
PACKAGES = HERE.parent
for _path in (HERE / "src", PACKAGES / "governance-contracts" / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
