"""
Tests for Ledger L0 Cleanup — validates the public API surface.

Ensures:
    - agentic.ledger exposes the governance audit store surface
    - Dead duplicate ontological replay/store modules are NOT in __all__
    - Dead audit_trace facade is removed
    - Live governance audit imports still work
"""

from __future__ import annotations

import importlib


class TestPublicAPISurface:
    """Validate that agentic.ledger.__all__ reflects the live governance audit API."""

    def test_all_contains_governance_audit_store(self):
        import agentic.ledger as ledger
        assert "GovernanceAuditStore" in ledger.__all__

    def test_all_contains_governance_audit_event(self):
        import agentic.ledger as ledger
        assert "GovernanceAuditEvent" in ledger.__all__

    def test_all_contains_chain_verification_result(self):
        import agentic.ledger as ledger
        assert "ChainVerificationResult" in ledger.__all__

    def test_all_contains_governance_audit_error(self):
        import agentic.ledger as ledger
        assert "GovernanceAuditError" in ledger.__all__

    def test_all_contains_event_factories(self):
        import agentic.ledger as ledger
        assert "event_from_governance_decision" in ledger.__all__
        assert "event_from_mcp_audit" in ledger.__all__

    def test_all_contains_singleton_helpers(self):
        import agentic.ledger as ledger
        assert "get_default_store" in ledger.__all__
        assert "set_default_store" in ledger.__all__

    def test_all_contains_serialization(self):
        import agentic.ledger as ledger
        assert "canonical_serialize" in ledger.__all__
        assert "compute_entry_hash" in ledger.__all__

    def test_all_contains_schema_version(self):
        import agentic.ledger as ledger
        assert "SCHEMA_VERSION" in ledger.__all__


class TestDeadModulesExcluded:
    """Validate that deprecated/dead modules are NOT in the public surface."""

    def test_no_ledger_projection_entry_in_all(self):
        import agentic.ledger as ledger
        assert "LedgerProjectionEntry" not in ledger.__all__

    def test_no_ledger_entry_in_all(self):
        import agentic.ledger as ledger
        assert "LedgerEntry" not in ledger.__all__

    def test_no_ledger_replay_verifier_in_all(self):
        import agentic.ledger as ledger
        assert "LedgerReplayVerifier" not in ledger.__all__

    def test_no_ledger_store_in_all(self):
        import agentic.ledger as ledger
        assert "LedgerStore" not in ledger.__all__

    def test_no_ledger_entry_store_in_all(self):
        import agentic.ledger as ledger
        assert "LedgerEntryStore" not in ledger.__all__

    def test_no_verify_ledger_replay_in_all(self):
        import agentic.ledger as ledger
        assert "verify_ledger_replay" not in ledger.__all__

    def test_no_record_projection_in_all(self):
        import agentic.ledger as ledger
        assert "record_projection" not in ledger.__all__

    def test_no_record_ledger_entry_in_all(self):
        import agentic.ledger as ledger
        assert "record_ledger_entry" not in ledger.__all__


class TestAuditTraceFacadeRemoved:
    """Validate that the dead audit_trace facade no longer exists."""

    def test_audit_trace_module_not_importable(self):
        try:
            importlib.import_module("agentic.ledger.audit_trace")
            assert False, "agentic.ledger.audit_trace should not be importable"
        except (ImportError, ModuleNotFoundError):
            pass


class TestLiveGovernanceAuditImports:
    """Validate that all live governance audit imports still work."""

    def test_governance_audit_store_importable(self):
        from agentic.ledger.governance_audit_store import GovernanceAuditStore
        assert GovernanceAuditStore is not None

    def test_governance_audit_event_importable(self):
        from agentic.ledger.governance_audit_store import GovernanceAuditEvent
        assert GovernanceAuditEvent is not None

    def test_event_from_governance_decision_importable(self):
        from agentic.ledger.governance_audit_store import event_from_governance_decision
        assert event_from_governance_decision is not None

    def test_event_from_mcp_audit_importable(self):
        from agentic.ledger.governance_audit_store import event_from_mcp_audit
        assert event_from_mcp_audit is not None

    def test_chain_verification_result_importable(self):
        from agentic.ledger.governance_audit_store import ChainVerificationResult
        assert ChainVerificationResult is not None

    def test_package_level_reexports_work(self):
        from agentic.ledger import (
            GovernanceAuditStore,
            GovernanceAuditEvent,
            GovernanceAuditError,
            ChainVerificationResult,
            event_from_governance_decision,
            event_from_mcp_audit,
            get_default_store,
            set_default_store,
            canonical_serialize,
            compute_entry_hash,
            create_event_id,
            create_timestamp,
            SCHEMA_VERSION,
        )
        assert GovernanceAuditStore is not None
        assert GovernanceAuditEvent is not None
        assert GovernanceAuditError is not None
        assert ChainVerificationResult is not None
        assert callable(event_from_governance_decision)
        assert callable(event_from_mcp_audit)
        assert callable(get_default_store)
        assert callable(set_default_store)
        assert callable(canonical_serialize)
        assert callable(compute_entry_hash)
        assert callable(create_event_id)
        assert callable(create_timestamp)
        assert isinstance(SCHEMA_VERSION, str)
