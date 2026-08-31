"""Path bootstrap for the frozen ActionGate reference + ACP core (import-only).

Used ONLY by the original-side V0.3 modules (profiles, producers, control plane,
acp_db, conformance). The clean-room package (``cer_v0_3/cleanroom``) must NOT
import this — it reaches none of the frozen implementation and is checked by the
forbidden-import test.
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_HERE)
_ACTIONGATE_ROOT = os.path.join(_REPO_ROOT, "cyber_security", "action_gate_reference")
# The clean-room canonicalizer now lives in the ``ugence-jcs`` leaf distribution.
# Adding its source root keeps a bare source checkout working without an editable
# install. This is a path bootstrap only; it imports nothing.
_JCS_SRC = os.path.join(_REPO_ROOT, "packages", "jcs", "src")
for _p in (_ACTIONGATE_ROOT, _JCS_SRC, _REPO_ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)
