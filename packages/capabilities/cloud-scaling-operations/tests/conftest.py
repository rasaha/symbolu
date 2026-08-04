"""Make the operations + advisory src and the tests dir importable for standalone runs."""
from __future__ import annotations
import os, sys

_HERE = os.path.dirname(__file__)
_OPS_SRC = os.path.abspath(os.path.join(_HERE, "..", "src"))
_ADV_SRC = os.path.abspath(os.path.join(_HERE, "..", "..", "cloud-scaling-controller", "src"))
for p in (_OPS_SRC, _ADV_SRC):
    try:
        import ugence_cloud_scaling_operations  # noqa: F401
        break
    except ImportError:
        if p not in sys.path:
            sys.path.insert(0, p)
sys.path.insert(0, _HERE)
