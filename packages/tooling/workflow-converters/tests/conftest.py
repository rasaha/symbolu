"""Pytest configuration for the converters suite.

Puts this package's ``src`` and its first-party dependencies on ``sys.path`` so the
suite runs from the package directory with only pytest and pydantic installed, as
the package-suites CI matrix runs it. The composer is optional: the preview test that
adapts the preview IR skips when it is absent.
"""
from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(PACKAGE, "..", "..", ".."))
for rel in (
    os.path.join(PACKAGE, "src"),
    os.path.join(REPO, "packages", "tooling", "policy-workflow-compiler", "src"),
    os.path.join(REPO, "packages", "capabilities", "decision-authority", "src"),
    os.path.join(REPO, "packages", "capabilities", "agent-workforce-composer", "src"),
):
    if rel not in sys.path:
        sys.path.insert(0, rel)
sys.path.insert(0, HERE)

FIXTURES = os.path.join(HERE, "fixtures")
