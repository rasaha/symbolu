#!/usr/bin/env python3
"""DEPRECATED alias — the module was renamed `asg_renderer` → `pse_renderer` (ASG → PSE; see NAMING.md).

Import `pse_renderer` instead. This shim re-exports everything (including private helpers) so existing
imports and `python asg_renderer.py ...` keep working during the deprecation window.
"""
import pse_renderer as _pse
from pse_renderer import *  # noqa: F401,F403

# carry over private/underscore names too (used by tests/tools), and main for CLI back-compat
globals().update({k: v for k, v in vars(_pse).items() if not k.startswith("__")})

if __name__ == "__main__":
    raise SystemExit(_pse.main())
