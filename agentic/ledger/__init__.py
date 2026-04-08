"""
Ledger Module
=============

Durable, append-only, tamper-evident audit persistence for governance
decisions and tool mediation events.

The canonical live surface of this package is the **Governance Audit Store**:
    - GovernanceAuditStore: SQLite-backed append-only store with hash chain
    - GovernanceAuditEvent: Canonical frozen event model
    - ChainVerificationResult: Hash chain verification result
    - GovernanceAuditError: Fail-closed persistence error
    - Event factories for GovernanceService and MCP gateway audit flows
    - Module-level singleton helpers

Consumers:
    - agentic.agentic_framework.governance_service (decision audit)
    - agentic.agentic_framework.mcp_gateway (tool mediation audit)
    - agentic.agentic_framework.policy_replay (replay/simulation source)

DEPRECATION NOTE (L0 cleanup, 2026-04):
    The ontological projection replay modules (ledger_replay_verifier,
    ledger_store) were previously re-exported here but are non-canonical
    duplicates. The live/canonical ontological replay surface is in
    ``symbolu.ledger``. These files remain in this directory for reference
    but are deprecated and excluded from the public API.
"""

from agentic.ledger.governance_audit_store import (
    SCHEMA_VERSION,
    ChainVerificationResult,
    GovernanceAuditError,
    GovernanceAuditEvent,
    GovernanceAuditStore,
    canonical_serialize,
    compute_entry_hash,
    create_event_id,
    create_timestamp,
    event_from_governance_decision,
    event_from_mcp_audit,
    get_default_store,
    set_default_store,
)


__all__ = [
    # Core
    "GovernanceAuditStore",
    "GovernanceAuditEvent",
    "GovernanceAuditError",
    "ChainVerificationResult",
    # Serialization / hashing
    "canonical_serialize",
    "compute_entry_hash",
    # Event factories
    "create_event_id",
    "create_timestamp",
    "event_from_governance_decision",
    "event_from_mcp_audit",
    # Module-level store
    "get_default_store",
    "set_default_store",
    # Constants
    "SCHEMA_VERSION",
]
