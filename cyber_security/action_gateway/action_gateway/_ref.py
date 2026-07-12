"""Locate and import the frozen Stage-1 reference harness.

The gateway is a *consumer* of the reference harness (``action_gate_ref``); it
never reimplements canonicalization, hashing, projection, evaluation, tokens, or
auditing. The harness lives in the sibling package directory
``cyber_security/action_gate_reference``; add it to sys.path once, here, so the
rest of the gateway can ``from ._ref import gate, token, ...``.
"""

from __future__ import annotations

import pathlib
import sys

_REF_DIR = pathlib.Path(__file__).resolve().parents[2] / "action_gate_reference"
if not (_REF_DIR / "action_gate_ref" / "__init__.py").exists():  # pragma: no cover
    raise RuntimeError(f"reference harness not found at {_REF_DIR}")
if str(_REF_DIR) not in sys.path:
    sys.path.insert(0, str(_REF_DIR))

import action_gate_ref  # noqa: E402
from action_gate_ref import (  # noqa: E402,F401
    approval,
    audit,
    canon_profile,
    errors,
    evidence,
    gate,
    hashing,
    jcs,
    policy,
    projection,
    schema,
    signing,
    token,
)

REF_VERSION = action_gate_ref.__version__

__all__ = [
    "approval", "audit", "canon_profile", "errors", "evidence", "gate",
    "hashing", "jcs", "policy", "projection", "schema", "signing", "token",
    "REF_VERSION",
]
