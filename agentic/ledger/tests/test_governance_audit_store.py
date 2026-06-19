"""
Tests for GovernanceAuditStore — durable, append-only, tamper-evident audit.

Covers:
    - Appending records
    - Append-only sequencing
    - Hash chain correctness
    - Tamper detection
    - Deterministic serialization stability
    - Replay verification
    - Persistence across store re-open
    - Query methods (by event_type, decision, session)
    - JSONL export
    - Event factory helpers
    - Integration with GovernanceService audit flow
"""

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import time

import pytest

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
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def store():
    """In-memory audit store for fast tests."""
    s = GovernanceAuditStore(":memory:")
    yield s
    s.close()


@pytest.fixture
def file_store(tmp_path):
    """File-backed audit store for persistence tests."""
    db_path = str(tmp_path / "test_audit.db")
    s = GovernanceAuditStore(db_path)
    yield s, db_path
    s.close()


def _make_event(
    event_id: str = "",
    event_type: str = "governance_decision",
    decision: str = "ALLOW",
    actor_id: str = "test-actor",
    tool_name: str = "test-tool",
    confidence: float = 0.85,
    eligible: bool = True,
    **kwargs,
) -> GovernanceAuditEvent:
    """Helper to create a test event with sensible defaults."""
    return GovernanceAuditEvent(
        event_id=event_id or create_event_id(),
        timestamp=kwargs.get("timestamp", create_timestamp()),
        event_type=event_type,
        source_module=kwargs.get("source_module", "test"),
        actor_id=actor_id,
        session_id=kwargs.get("session_id", "sess-001"),
        action_type=kwargs.get("action_type", "authorize"),
        tool_name=tool_name,
        decision_outcome=decision,
        eligible=eligible,
        risk_level=kwargs.get("risk_level", "WRITE"),
        confidence=confidence,
        execution_mode=kwargs.get("execution_mode", "FULL"),
        escalation_level=kwargs.get("escalation_level", "NONE"),
        blocked_reasons=kwargs.get("blocked_reasons", ()),
        rationale=kwargs.get("rationale", "test rationale"),
        request_snapshot=kwargs.get("request_snapshot", {"key": "value"}),
        execution_result=kwargs.get("execution_result", {}),
        schema_version=SCHEMA_VERSION,
    )


# =============================================================================
# Test: Append and basic retrieval
# =============================================================================


class TestAppend:
    def test_append_single(self, store):
        event = _make_event()
        entry_hash = store.append(event)
        assert len(entry_hash) == 16
        assert store.count() == 1

    def test_append_multiple(self, store):
        for i in range(5):
            store.append(_make_event(event_id=f"evt-{i:04d}"))
        assert store.count() == 5

    def test_list_recent_returns_newest_first(self, store):
        for i in range(3):
            store.append(_make_event(event_id=f"evt-{i:04d}"))
        recent = store.list_recent(limit=10)
        assert len(recent) == 3
        assert recent[0]["event_id"] == "evt-0002"
        assert recent[2]["event_id"] == "evt-0000"

    def test_list_recent_respects_limit(self, store):
        for i in range(10):
            store.append(_make_event(event_id=f"evt-{i:04d}"))
        recent = store.list_recent(limit=3)
        assert len(recent) == 3

    def test_duplicate_event_id_raises(self, store):
        store.append(_make_event(event_id="dup-001"))
        with pytest.raises(GovernanceAuditError):
            store.append(_make_event(event_id="dup-001"))


# =============================================================================
# Test: Append-only sequencing
# =============================================================================


class TestAppendOnly:
    def test_seq_is_monotonic(self, store):
        for i in range(5):
            store.append(_make_event())
        records = store.list_recent(limit=100)
        seqs = [r["seq"] for r in records]
        # newest first, so reversed should be ascending
        assert sorted(seqs) == list(reversed(seqs))

    def test_no_update_or_delete(self, store):
        """Verify that the store has no update/delete methods."""
        assert not hasattr(store, "update")
        assert not hasattr(store, "delete")
        assert not hasattr(store, "remove")


# =============================================================================
# Test: Hash chain correctness
# =============================================================================


class TestHashChain:
    def test_first_entry_uses_genesis_hash(self, store):
        store.append(_make_event())
        records = store.list_recent(limit=1)
        assert records[0]["prev_hash"] == "0" * 16

    def test_second_entry_chains_to_first(self, store):
        h1 = store.append(_make_event(event_id="first"))
        store.append(_make_event(event_id="second"))
        records = store.list_recent(limit=10)
        # newest first
        second = records[0]
        assert second["prev_hash"] == h1

    def test_chain_of_10(self, store):
        hashes = []
        for i in range(10):
            h = store.append(_make_event(event_id=f"chain-{i:04d}"))
            hashes.append(h)
        # Verify each hash chains to the previous
        records = store.list_recent(limit=100)
        records.reverse()  # oldest first
        assert records[0]["prev_hash"] == "0" * 16
        for i in range(1, len(records)):
            assert records[i]["prev_hash"] == records[i - 1]["entry_hash"]

    def test_hash_is_deterministic(self):
        """Same inputs → same hash."""
        h1 = compute_entry_hash("abcd1234abcd1234", '{"key":"value"}')
        h2 = compute_entry_hash("abcd1234abcd1234", '{"key":"value"}')
        assert h1 == h2
        assert len(h1) == 16

    def test_hash_changes_with_different_prev(self):
        h1 = compute_entry_hash("aaaa" * 4, '{"key":"value"}')
        h2 = compute_entry_hash("bbbb" * 4, '{"key":"value"}')
        assert h1 != h2

    def test_hash_changes_with_different_payload(self):
        prev = "aaaa" * 4
        h1 = compute_entry_hash(prev, '{"key":"value1"}')
        h2 = compute_entry_hash(prev, '{"key":"value2"}')
        assert h1 != h2


# =============================================================================
# Test: Tamper detection
# =============================================================================


class TestTamperDetection:
    def test_verify_chain_valid(self, store):
        for i in range(5):
            store.append(_make_event(event_id=f"valid-{i:04d}"))
        result = store.verify_chain()
        assert result.valid is True
        assert result.total_records == 5

    def test_verify_empty_store(self, store):
        result = store.verify_chain()
        assert result.valid is True
        assert result.total_records == 0

    def test_detect_tampered_payload(self, store):
        for i in range(3):
            store.append(_make_event(event_id=f"tamper-{i:04d}"))

        # Tamper: modify a canonical_payload directly in SQLite
        store._conn.execute(
            "UPDATE audit_events SET canonical_payload = '{\"tampered\":true}' WHERE seq = 2"
        )
        store._conn.commit()

        result = store.verify_chain()
        assert result.valid is False
        assert result.error_at_seq == 2
        assert "entry_hash mismatch" in result.error_detail

    def test_detect_tampered_prev_hash(self, store):
        for i in range(3):
            store.append(_make_event(event_id=f"prevtamper-{i:04d}"))

        # Tamper: modify prev_hash of second entry
        store._conn.execute(
            "UPDATE audit_events SET prev_hash = 'deadbeefdeadbeef' WHERE seq = 2"
        )
        store._conn.commit()

        result = store.verify_chain()
        assert result.valid is False
        assert result.error_at_seq == 2
        assert "prev_hash mismatch" in result.error_detail

    def test_detect_tampered_entry_hash(self, store):
        for i in range(3):
            store.append(_make_event(event_id=f"hashtamper-{i:04d}"))

        # Tamper: modify entry_hash of first entry
        store._conn.execute(
            "UPDATE audit_events SET entry_hash = 'badc0ffeebadc0ff' WHERE seq = 1"
        )
        store._conn.commit()

        result = store.verify_chain()
        assert result.valid is False
        # First entry's hash is wrong, so it will be detected
        assert result.error_at_seq == 1


# =============================================================================
# Test: Deterministic serialization
# =============================================================================


class TestDeterministicSerialization:
    def test_canonical_serialize_is_stable(self):
        """Same event always produces the same canonical JSON."""
        event = _make_event(
            event_id="stable-001",
            timestamp="2025-01-01T00:00:00+00:00",
        )
        s1 = canonical_serialize(event)
        s2 = canonical_serialize(event)
        assert s1 == s2

    def test_canonical_serialize_sorted_keys(self):
        event = _make_event()
        s = canonical_serialize(event)
        d = json.loads(s)
        keys = list(d.keys())
        assert keys == sorted(keys)

    def test_canonical_serialize_compact(self):
        """No spaces in separators."""
        event = _make_event()
        s = canonical_serialize(event)
        assert ": " not in s
        assert ", " not in s

    def test_blocked_reasons_sorted(self):
        """Blocked reasons are sorted for determinism."""
        event = _make_event(blocked_reasons=("zebra", "alpha", "middle"))
        s = canonical_serialize(event)
        d = json.loads(s)
        assert d["blocked_reasons"] == ["alpha", "middle", "zebra"]

    def test_float_stability(self):
        """Floats are rounded to 6 decimal places."""
        event = _make_event(confidence=0.123456789)
        s = canonical_serialize(event)
        d = json.loads(s)
        assert d["confidence"] == 0.123457

    def test_nested_dict_sorted(self):
        """Request snapshot keys are recursively sorted."""
        event = _make_event(
            request_snapshot={"z_key": 1, "a_key": {"nested_z": 2, "nested_a": 3}}
        )
        s = canonical_serialize(event)
        d = json.loads(s)
        keys = list(d["request_snapshot"].keys())
        assert keys == sorted(keys)
        nested_keys = list(d["request_snapshot"]["a_key"].keys())
        assert nested_keys == sorted(nested_keys)


# =============================================================================
# Test: Replay verification
# =============================================================================


class TestReplayVerification:
    def test_replay_verify_valid(self, store):
        for i in range(10):
            store.append(_make_event(event_id=f"replay-{i:04d}"))
        result = store.replay_verify()
        assert result.valid is True
        assert result.total_records == 10

    def test_replay_verify_is_alias(self, store):
        """replay_verify() and verify_chain() return same result."""
        for i in range(3):
            store.append(_make_event(event_id=f"alias-{i:04d}"))
        r1 = store.verify_chain()
        r2 = store.replay_verify()
        assert r1 == r2


# =============================================================================
# Test: Persistence survives re-open
# =============================================================================


class TestPersistence:
    def test_survives_reopen(self, file_store):
        store, db_path = file_store
        for i in range(5):
            store.append(_make_event(event_id=f"persist-{i:04d}"))
        last_hash = store.get_last_hash()
        store.close()

        # Reopen
        store2 = GovernanceAuditStore(db_path)
        assert store2.count() == 5
        assert store2.get_last_hash() == last_hash

        # Chain still valid
        result = store2.verify_chain()
        assert result.valid is True

        # Can append more
        store2.append(_make_event(event_id="persist-0005"))
        assert store2.count() == 6
        assert store2.verify_chain().valid is True
        store2.close()

    def test_new_entries_chain_after_reopen(self, file_store):
        store, db_path = file_store
        h1 = store.append(_make_event(event_id="before-close"))
        store.close()

        store2 = GovernanceAuditStore(db_path)
        store2.append(_make_event(event_id="after-reopen"))
        records = store2.list_recent(limit=10)
        after = [r for r in records if r["event_id"] == "after-reopen"][0]
        assert after["prev_hash"] == h1
        assert store2.verify_chain().valid is True
        store2.close()


# =============================================================================
# Test: Query methods
# =============================================================================


class TestQueries:
    def test_list_by_event_type(self, store):
        store.append(_make_event(event_type="governance_decision"))
        store.append(_make_event(event_type="mcp_tool_call"))
        store.append(_make_event(event_type="governance_decision"))

        gov = store.list_by_event_type("governance_decision")
        assert len(gov) == 2
        mcp = store.list_by_event_type("mcp_tool_call")
        assert len(mcp) == 1

    def test_list_by_decision(self, store):
        store.append(_make_event(decision="ALLOW"))
        store.append(_make_event(decision="DENY"))
        store.append(_make_event(decision="DENY"))

        denies = store.list_by_decision("DENY")
        assert len(denies) == 2
        allows = store.list_by_decision("ALLOW")
        assert len(allows) == 1

    def test_list_by_session(self, store):
        store.append(_make_event(session_id="sess-A"))
        store.append(_make_event(session_id="sess-B"))
        store.append(_make_event(session_id="sess-A"))

        sess_a = store.list_by_session("sess-A")
        assert len(sess_a) == 2
        sess_b = store.list_by_session("sess-B")
        assert len(sess_b) == 1


# =============================================================================
# Test: JSONL export
# =============================================================================


class TestExport:
    def test_export_jsonl(self, store, tmp_path):
        for i in range(3):
            store.append(_make_event(event_id=f"export-{i:04d}"))

        path = str(tmp_path / "audit.jsonl")
        count = store.export_jsonl(path)
        assert count == 3

        with open(path) as f:
            lines = f.readlines()
        assert len(lines) == 3

        # Each line is valid JSON
        for line in lines:
            d = json.loads(line)
            assert "event_id" in d
            assert "entry_hash" in d
            assert "prev_hash" in d

    def test_export_order_is_chronological(self, store, tmp_path):
        for i in range(5):
            store.append(_make_event(event_id=f"order-{i:04d}"))

        path = str(tmp_path / "audit.jsonl")
        store.export_jsonl(path)

        with open(path) as f:
            lines = [json.loads(line) for line in f]
        seqs = [l["seq"] for l in lines]
        assert seqs == sorted(seqs)


# =============================================================================
# Test: Event factory helpers
# =============================================================================


class TestEventFactories:
    def test_event_from_governance_decision(self):
        event = event_from_governance_decision(
            decision_id="dec-001",
            timestamp="2025-01-01T00:00:00+00:00",
            actor_id="actor-1",
            action_type="authorize",
            tool_name="my_tool",
            decision="ALLOW",
            risk_level="WRITE",
            eligible=True,
            confidence=0.9,
            execution_mode="FULL",
            escalation_level="NONE",
            blocked_reasons=["reason1"],
            request_snapshot={"key": "val"},
        )
        assert event.event_type == "governance_decision"
        assert event.source_module == "governance_service"
        assert event.decision_outcome == "ALLOW"
        assert event.blocked_reasons == ("reason1",)

    def test_event_from_mcp_audit(self):
        event = event_from_mcp_audit(
            timestamp="2025-01-01T00:00:00",
            request_id="req-001",
            tool_name="search_files",
            parameters={"path": "/tmp"},
            decision="ALLOWED",
            confidence=0.75,
            risk_level="read_only",
            session_id="sess-X",
            execution_time_ms=42.5,
            success=True,
        )
        assert event.event_type == "mcp_tool_call"
        assert event.source_module == "mcp_gateway"
        assert event.eligible is True
        assert event.execution_result["execution_time_ms"] == 42.5

    def test_event_from_mcp_audit_blocked(self):
        event = event_from_mcp_audit(
            timestamp="2025-01-01T00:00:00",
            request_id="req-002",
            tool_name="rm_rf",
            parameters={},
            decision="BLOCKED",
            confidence=0.1,
            risk_level="destructive",
            error="forbidden capability",
        )
        assert event.eligible is False
        assert "forbidden capability" in event.blocked_reasons

    def test_event_from_mcp_audit_embeds_trust_shadow(self):
        # Phase 1.5: the parallel trust-core decision + legacy mismatch must be
        # embedded in request_snapshot so the migration differential is durable.
        event = event_from_mcp_audit(
            timestamp="2025-01-01T00:00:00",
            request_id="req-003",
            tool_name="file_read",
            parameters={"path": "/tmp"},
            decision="ALLOWED",
            confidence=0.9,
            risk_level="read_only",
            trust_decision="block",
            trust_legacy_decision="allow",
            trust_mismatch=True,
            trust_mismatch_class="unintended",
            trust_drivers=["jepa"],
            trust_reason="BLOCK driven by jepa(...)",
        )
        ts = event.request_snapshot["trust_shadow"]
        assert ts["decision"] == "block"
        assert ts["legacy_decision"] == "allow"
        assert ts["mismatch"] is True
        assert ts["mismatch_class"] == "unintended"
        assert ts["drivers"] == ["jepa"]
        assert ts["reason"].startswith("BLOCK driven by")

    def test_event_from_mcp_audit_without_trust_has_no_trust_shadow(self):
        # Legacy mode passes no trust args → events are unchanged (no trust_shadow key).
        event = event_from_mcp_audit(
            timestamp="2025-01-01T00:00:00",
            request_id="req-004",
            tool_name="file_read",
            parameters={"path": "/tmp"},
            decision="ALLOWED",
            confidence=0.9,
            risk_level="read_only",
        )
        assert "trust_shadow" not in event.request_snapshot

    def test_event_from_mcp_audit_embeds_entropy_gap(self):
        # Phase 1.5: raw-entropy + confidence-risk-gap provenance is embedded for slicing.
        event = event_from_mcp_audit(
            timestamp="2025-01-01T00:00:00",
            request_id="req-005",
            tool_name="file_write",
            parameters={"path": "/tmp"},
            decision="ESCALATE",
            confidence=0.7,
            risk_level="write",
            raw_entropy_available=True,
            raw_entropy=0.83,
            raw_entropy_source="producer",
            confidence_risk_gap_escalate=True,
            confidence_risk_gap_value=0.42,
            confidence_risk_gap_reason="verbalized-safe but high raw entropy",
            confidence_risk_gap_verbalized_safety=0.9,
        )
        eg = event.request_snapshot["entropy_gap"]
        assert eg["raw_entropy_available"] is True
        assert eg["raw_entropy"] == 0.83
        assert eg["raw_entropy_source"] == "producer"
        assert eg["confidence_risk_gap_escalate"] is True
        assert eg["confidence_risk_gap_value"] == 0.42
        assert eg["confidence_risk_gap_reason"].startswith("verbalized-safe")
        assert eg["confidence_risk_gap_verbalized_safety"] == 0.9

    def test_event_from_mcp_audit_without_entropy_gap_is_compatible(self):
        # Callers that pass no entropy/gap args → legacy-compatible (no entropy_gap key).
        event = event_from_mcp_audit(
            timestamp="2025-01-01T00:00:00",
            request_id="req-006",
            tool_name="file_read",
            parameters={"path": "/tmp"},
            decision="ALLOWED",
            confidence=0.9,
            risk_level="read_only",
        )
        assert "entropy_gap" not in event.request_snapshot

    def test_entropy_gap_persists_durably_and_chain_stays_valid(self, store):
        # Mixed events (with and without entropy_gap) persist and the hash chain verifies.
        store.append(event_from_mcp_audit(
            timestamp="2025-01-01T00:00:00", request_id="e1", tool_name="t1",
            parameters={}, decision="ALLOWED", confidence=0.9, risk_level="read_only"))
        store.append(event_from_mcp_audit(
            timestamp="2025-01-01T00:00:01", request_id="e2", tool_name="t2",
            parameters={}, decision="ESCALATE", confidence=0.6, risk_level="write",
            raw_entropy_available=True, raw_entropy=0.9, raw_entropy_source="producer",
            confidence_risk_gap_escalate=True, confidence_risk_gap_reason="gap"))
        assert store.verify_chain().valid
        recs = store.list_recent(limit=10)
        with_eg = [r for r in recs if "entropy_gap" in r["request_snapshot"]]
        assert len(with_eg) == 1
        assert with_eg[0]["request_snapshot"]["entropy_gap"]["raw_entropy"] == 0.9


# =============================================================================
# Test: Integration with GovernanceService
# =============================================================================


class TestGovernanceServiceIntegration:
    def test_governance_service_persists_to_store(self):
        """GovernanceService with audit_store persists decisions."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import AuthorizationRequest

        store = GovernanceAuditStore(":memory:")
        service = GovernanceService(audit_store=store)

        request = AuthorizationRequest(
            actor_id="test-agent",
            action_type="test_action",
            tool_name="test_tool",
            agency_level="FULL",
        )
        response = service.authorize(request)

        # In-memory log has the event
        assert len(service.get_audit_log()) == 1

        # Persistent store has the event
        assert store.count() == 1

        # Hash chain is valid
        assert store.verify_chain().valid is True

        # Event data matches
        records = store.list_recent(limit=1)
        assert records[0]["event_type"] == "governance_decision"
        assert records[0]["actor_id"] == "test-agent"
        store.close()

    def test_governance_service_works_without_store(self):
        """GovernanceService without audit_store still works (in-memory only)."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import AuthorizationRequest

        service = GovernanceService()
        request = AuthorizationRequest(
            actor_id="test-agent",
            action_type="test_action",
        )
        response = service.authorize(request)
        assert len(service.get_audit_log()) == 1

    def test_error_response_also_persisted(self):
        """Fail-closed DENY responses are also persisted."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import AuthorizationRequest

        store = GovernanceAuditStore(":memory:")
        service = GovernanceService(audit_store=store)

        # Create a request that will trigger the error path by giving
        # a deliberately malformed confidence_gate
        from unittest.mock import MagicMock
        service.gate = MagicMock(side_effect=RuntimeError("deliberate test error"))

        request = AuthorizationRequest(
            actor_id="test-agent",
            action_type="test_action",
        )
        response = service.authorize(request)
        assert response.governance_decision.value == "DENY"

        # Error event is persisted
        assert store.count() == 1
        records = store.list_recent()
        assert records[0]["decision_outcome"] == "DENY"
        store.close()


# =============================================================================
# Test: get_last_hash
# =============================================================================


class TestGetLastHash:
    def test_empty_store_returns_genesis(self, store):
        assert store.get_last_hash() == "0" * 16

    def test_after_append_returns_latest(self, store):
        h = store.append(_make_event())
        assert store.get_last_hash() == h


# =============================================================================
# Test: Failure handling
# =============================================================================


class TestFailureHandling:
    @pytest.mark.skipif(
        os.getuid() == 0, reason="root bypasses file permission checks"
    )
    def test_readonly_db_raises_on_append(self, tmp_path):
        """If the DB becomes read-only, append raises GovernanceAuditError."""
        db_path = str(tmp_path / "readonly_test.db")
        store = GovernanceAuditStore(db_path)
        store.append(_make_event(event_id="before-readonly"))
        store.close()

        # Make file read-only
        os.chmod(db_path, 0o444)
        try:
            store2 = GovernanceAuditStore(db_path)
            with pytest.raises(GovernanceAuditError):
                store2.append(_make_event(event_id="after-readonly"))
            store2.close()
        finally:
            os.chmod(db_path, 0o644)

    def test_invalid_db_path_raises(self):
        """Non-existent directory raises GovernanceAuditError."""
        with pytest.raises(GovernanceAuditError):
            GovernanceAuditStore("/nonexistent/path/to/audit.db")
