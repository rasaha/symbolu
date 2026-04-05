"""
Agentic — Governance and integration layer for Symbolu.

This package contains the agentic AI governance framework and the
integration modules that bridge governance decisions with the reasoning
substrate (symbolu_core).

CORE modules:
  - agentic_framework: Safety contracts, MCP gateway, confidence gate
  - safety: GCC runtime guard, static scanner
  - policy: Policy engine, session policy, domain profiles
  - posture: Posture classification and management
  - ledger: Immutable audit ledger, replay verifier

INTEGRATE modules:
  - entropy, core, identity, motivation, sovereign, inference,
    chitta_vritti, temporal, guna_modulation, dha, llm, api
"""

from agentic.agentic_framework.agent import AgenticLLMWrapper
from agentic.agentic_framework.cg_tool_dispatcher import CGToolDispatcher

__all__ = [
    "AgenticLLMWrapper",
    "CGToolDispatcher",
]
