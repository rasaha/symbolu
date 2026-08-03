"""Pytest configuration for the Governance Studio API (P3B).

Puts the backend ``src/`` and the sibling AWC / compiler package sources on
``sys.path`` so the suite runs with or without editable installs. This mirrors the
P3A conftest pattern; it does not install or import any P3A test helper.
"""
import os
import sys

_BACKEND = os.path.dirname(os.path.abspath(__file__))
_APP = os.path.dirname(_BACKEND)
_REPO = os.path.dirname(os.path.dirname(_APP))
_SRC = os.path.join(_BACKEND, "src")
_AWC_SRC = os.path.join(_REPO, "packages", "capabilities", "agent-workforce-composer", "src")
_COMPILER_SRC = os.path.join(_REPO, "packages", "tooling", "policy-workflow-compiler", "src")

for p in (_SRC, _AWC_SRC, _COMPILER_SRC):
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)
