"""Locate and re-export the runtime gateway + frozen harness.

The MCP layer is a *transport adapter* over the runtime gateway
(``action_gateway``), which itself consumes the frozen reference gate
(``action_gate_ref``). Nothing here reimplements canonicalization, hashing,
policy, tokens, approvals, or audit primitives — they are imported and reused.
"""

from __future__ import annotations

import pathlib
import sys

_AG_DIR = pathlib.Path(__file__).resolve().parents[2] / "action_gateway"
if not (_AG_DIR / "action_gateway" / "__init__.py").exists():  # pragma: no cover
    raise RuntimeError(f"runtime gateway not found at {_AG_DIR}")
if str(_AG_DIR) not in sys.path:
    sys.path.insert(0, str(_AG_DIR))

import action_gateway  # noqa: E402
from action_gateway import Gateway, ToolRequest  # noqa: E402,F401
from action_gateway import state as gw_state  # noqa: E402,F401
from action_gateway._ref import approval as ref_approval  # noqa: E402,F401
from action_gateway._ref import audit as ref_audit  # noqa: E402,F401
from action_gateway._ref import errors as ref_errors  # noqa: E402,F401
from action_gateway._ref import evidence as ref_evidence  # noqa: E402,F401
from action_gateway._ref import hashing as ref_hashing  # noqa: E402,F401
from action_gateway._ref import jcs as ref_jcs  # noqa: E402,F401
from action_gateway._ref import projection as ref_projection  # noqa: E402,F401
from action_gateway.broker import MockCredentialBroker, ScopedCredential  # noqa: E402,F401
from action_gateway.clock import FixedClock, RealClock  # noqa: E402,F401

AG_VERSION = action_gateway.__version__
