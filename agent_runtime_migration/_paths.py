"""Path bootstrap so the migration runtime can import the FROZEN CER + control
plane (import-only). The runtime never modifies those packages."""
from __future__ import annotations
import os, sys
_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
_AG = os.path.join(_REPO_ROOT, "cyber_security", "action_gate_reference")
for _p in (_AG, _REPO_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)
