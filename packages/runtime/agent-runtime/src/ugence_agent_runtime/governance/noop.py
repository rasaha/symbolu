"""Backward-compatible shim.

The always-CLEAR hook formerly named ``NoopGovernanceHook`` lived here and was the
runtime default — that was fail-open and has been corrected. The hooks now live in
``ugence_agent_runtime.governance.hooks``; the default is the fail-closed
``UnconfiguredGovernanceHook``. This module re-exports the renamed hooks so existing
imports keep resolving.
"""
from __future__ import annotations

from .hooks import (  # noqa: F401
    GOVERNANCE_NOT_CONFIGURED,
    AllowAllGovernanceHook,
    NoopGovernanceHook,
    UnconfiguredGovernanceHook,
)

__all__ = [
    "UnconfiguredGovernanceHook",
    "AllowAllGovernanceHook",
    "NoopGovernanceHook",
    "GOVERNANCE_NOT_CONFIGURED",
]
