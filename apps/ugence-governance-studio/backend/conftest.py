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
# Source roots for every package on the SD-1 public-entry-point allowlist, so the
# suite runs with or without editable installs. Each is guarded by isdir(), so the
# backend still collects when a package is absent.
_PACKAGE_SRC = [
    os.path.join(_REPO, "packages", "capabilities", "agent-workforce-composer", "src"),
    os.path.join(_REPO, "packages", "tooling", "policy-workflow-compiler", "src"),
    os.path.join(_REPO, "packages", "integration", "agent-constitution-activation", "src"),
    os.path.join(_REPO, "packages", "integration", "agent-constitution-policy", "src"),
    os.path.join(_REPO, "packages", "integration", "agent-constitution-conformance", "src"),
    os.path.join(_REPO, "packages", "capabilities", "agentic-proposer", "src"),
    os.path.join(_REPO, "packages", "policy-authority", "src"),
    os.path.join(_REPO, "packages", "capabilities", "decision-authority", "src"),
    os.path.join(_REPO, "packages", "runtime", "agent-runtime", "src"),
    os.path.join(_REPO, "packages", "uvi-policy-contracts", "src"),
    os.path.join(_REPO, "packages", "governance-contracts", "src"),
    os.path.join(_REPO, "packages", "jcs", "src"),
]

for p in [_SRC, *_PACKAGE_SRC]:
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)
