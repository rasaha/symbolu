import os
import sys
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_AG = os.path.join(_ROOT, "cyber_security", "action_gate_reference")
for _p in (_AG, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)
