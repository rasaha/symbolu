"""Pytest configuration for the Governance Studio P3A fixtures.

Puts the app's ``scripts/`` directory (the scenario authoring + loader helpers)
on ``sys.path`` and the AWC package ``src/`` too, so the suite runs with or
without an editable install of ``ugence-agent-workforce-composer``.
"""
import os
import sys

_TESTS = os.path.dirname(os.path.abspath(__file__))
_APP = os.path.dirname(_TESTS)
_REPO = os.path.dirname(os.path.dirname(_APP))
_AWC_SRC = os.path.join(_REPO, "packages", "capabilities", "agent-workforce-composer", "src")

for p in (os.path.join(_APP, "scripts"), _TESTS, _AWC_SRC):
    if p not in sys.path:
        sys.path.insert(0, p)
