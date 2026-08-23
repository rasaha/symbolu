"""Ugence Agentic Proposer — S0 capability skeleton.

The Agentic Proposer is an ADVISORY capability. It proposes; it decides nothing.
It mints no agent identity, authors no organizational role, admits no evidence,
authorizes no action, grants no clearance and executes nothing. Owner decisions
D1-D5 and the authority-ownership boundary are recorded in
``docs/architecture/ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md``.

S0 is a skeleton. It carries exactly the ratified D4 vocabulary and the boundary
proofs that keep the capability a leaf. It implements none of the canonical
contracts, none of the eligibility or readiness equations, no proposal identity,
no reason codes, no adapters, no semantic auditor and no HTTP surface. No public
contract is frozen at this version.

Proposal identity, when S1 introduces it, may only be a call into ``ugence_jcs``.
This package contains no canonicalization code of any kind — not in ``src``, not in
``tests``, not behind a flag, not as a fallback, not as a temporary helper — and
``tests/test_no_local_canonicalization.py`` enforces that.
"""
from __future__ import annotations

from .version import __version__
from .vocabulary import (
    RESERVED_AUTHORITY_VOCABULARY,
    CandidateDisposition,
    SemanticAuditorFindingStatus,
    TerminalOutcome,
)

__all__ = [
    "TerminalOutcome",
    "CandidateDisposition",
    "SemanticAuditorFindingStatus",
    "RESERVED_AUTHORITY_VOCABULARY",
    "__version__",
]
