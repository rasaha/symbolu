"""Locate and re-export the runtime gateway, MCP layer, and frozen harness.

This package reuses — never re-implements — canonicalization, hashing, policy,
tokens, approvals, audit (``action_gate_ref``), the runtime enforcement gateway
(``action_gateway``), and the MCP mapping/audit patterns (``action_gateway_mcp``).
"""

from __future__ import annotations

import pathlib
import sys

_CS = pathlib.Path(__file__).resolve().parents[2]
for _pkg_dir in (_CS / "action_gateway", _CS / "action_gateway_mcp"):
    if str(_pkg_dir) not in sys.path:
        sys.path.insert(0, str(_pkg_dir))

import action_gateway  # noqa: E402
import action_gateway_mcp  # noqa: E402
from action_gateway import Gateway, ToolRequest  # noqa: E402,F401
from action_gateway import state as gw_state  # noqa: E402,F401
from action_gateway._ref import approval as ref_approval  # noqa: E402,F401
from action_gateway._ref import audit as ref_audit  # noqa: E402,F401
from action_gateway._ref import errors as ref_errors  # noqa: E402,F401
from action_gateway._ref import evidence as ref_evidence  # noqa: E402,F401
from action_gateway._ref import hashing as ref_hashing  # noqa: E402,F401
from action_gateway._ref import jcs as ref_jcs  # noqa: E402,F401
from action_gateway._ref import policy as ref_policy  # noqa: E402,F401
from action_gateway._ref import projection as ref_projection  # noqa: E402,F401
from action_gateway.broker import CredentialBroker, ScopedCredential  # noqa: E402,F401
from action_gateway.clock import FixedClock, RealClock  # noqa: E402,F401
from action_gateway_mcp.audit import Metrics, ProtocolAudit  # noqa: E402,F401

AG_VERSION = action_gateway.__version__
MCP_VERSION = action_gateway_mcp.__version__
