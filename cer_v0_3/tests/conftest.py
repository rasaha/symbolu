import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_AG = os.path.join(_ROOT, "cyber_security", "action_gate_reference")
# The clean-room canonicalizer was extracted to the ``ugence-jcs`` leaf
# distribution; a bare source checkout resolves it without an editable install.
_JCS = os.path.join(_ROOT, "packages", "jcs", "src")
for _p in (_AG, _JCS, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)
