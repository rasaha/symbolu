"""Path bootstrap so the CER package can import the frozen ActionGate reference
and the frozen ACP cloud core WITHOUT copying or modifying them.

This is the only place sys.path is touched. It adds:
  * the ActionGate reference package root (for ``action_gate_ref``);
  * the repository root (for ``symbolu_robotics.autonomous_control_plane.cloud``).

No control-plane code is imported here — only made importable.
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
_ACTIONGATE_ROOT = os.path.join(_REPO_ROOT, "cyber_security", "action_gate_reference")

for _p in (_ACTIONGATE_ROOT, _REPO_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)
