"""Backwards-compatibility stub — module moved to symbolu_extensions/."""
import importlib
import sys

_new_name = __name__.replace("symbolu.", "symbolu_extensions.", 1)
try:
    _mod = importlib.import_module(_new_name)
    sys.modules[__name__] = _mod
    globals().update({k: v for k, v in _mod.__dict__.items() if not k.startswith("_")})
except ImportError:
    pass
