"""Make the shadow harness, operations, and advisory packages importable."""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(__file__)
_PKG_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))          # cloud-scaling-operations
_OPS_SRC = os.path.join(_PKG_ROOT, "src")
_ADV_SRC = os.path.abspath(os.path.join(_PKG_ROOT, "..", "cloud-scaling-controller", "src"))

for p in (_PKG_ROOT, _OPS_SRC, _ADV_SRC):
    if p not in sys.path:
        sys.path.insert(0, p)
