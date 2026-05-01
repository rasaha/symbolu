"""
Tests for MemoryRetentionPolicy (v2.5).

Batch M2 — types only.  No cleanup logic exists yet; these tests cover:
- Policy object construction, defaults, ``is_active()``, ``to_dict()``,
  frozen invariant.
- ``AgentMemory`` carries the new ``last_accessed_at`` field, default
  empty, and survives ``append_turn`` round-trips unchanged.
- ``MemoryStore`` accepts the new kwarg without changing behaviour.
- ``AgenticLLMWrapper`` threads the kwarg into its ``MemoryStore``.
- ``AgentMemory.to_dict()`` exposes ``operational.last_accessed_at`` as
  a top-level operational namespace.

Cleanup, eviction, and trace surfacing land in M3 / M4 and have their
own tests.
"""

import json
from datetime import datetime, timedelta

import pytest

from agentic.agentic_framework import (
    AgenticLLMWrapper,
    MemoryRetentionPolicy,
)
from agentic.agentic_framework.llm_adapters import MockLLMAdapter
from agentic.agentic_framework.memory_store import (
    MemoryStore,
    create_memory,
    create_turn_snapshot,
)


# ===================================================================
# 1. Policy object — construction, defaults, helpers
# ===================================================================


class TestMemoryRetentionPolicyUnit:
    def test_default_all_none(self):
        p = MemoryRetentionPolicy()
        assert p.item_ttl_s is None
        assert p.idle_ttl_s is None
        assert p.max_items is None

    def test_is_active_default_false(self):
        assert MemoryRetentionPolicy().is_active() is False

    def test_is_active_each_field(self):
        assert MemoryRetentionPolicy(item_ttl_s=1.0).is_active() is True
        assert MemoryRetentionPolicy(idle_ttl_s=1.0).is_active() is True
        assert MemoryRetentionPolicy(max_items=1).is_active() is True

    def test_is_active_with_zero(self):
        # Zero is a valid (extremely aggressive) cap; the policy is
        # active because the field is set, not None.
        assert MemoryRetentionPolicy(item_ttl_s=0.0).is_active() is True
        assert MemoryRetentionPolicy(max_items=0).is_active() is True

    def test_to_dict_round_trip(self):
        p = MemoryRetentionPolicy(
            item_ttl_s=3600.0,
            idle_ttl_s=600.0,
            max_items=50,
        )
        d = p.to_dict()
        json.dumps(d)
        assert d["item_ttl_s"] == 3600.0
        assert d["idle_ttl_s"] == 600.0
        assert d["max_items"] == 50

    def test_to_dict_default(self):
        d = MemoryRetentionPolicy().to_dict()
        json.dumps(d)
        assert d == {
            "item_ttl_s": None,
            "idle_ttl_s": None,
            "max_items": None,
        }

    def test_policy_frozen(self):
        p = MemoryRetentionPolicy(item_ttl_s=10.0)
        with pytest.raises(AttributeError):
            p.item_ttl_s = 20.0  # type: ignore[misc]

    def test_independent_fields(self):
        # Setting one field does not implicitly set the others.
        p = MemoryRetentionPolicy(idle_ttl_s=30.0)
        assert p.item_ttl_s is None
        assert p.max_items is None
        assert p.is_active()


# ===================================================================
# 2. AgentMemory — last_accessed_at field
# ===================================================================


class TestAgentMemoryLastAccessedAt:
    def test_create_memory_initialises_empty(self):
        memory = create_memory("session-x")
        assert memory.last_accessed_at == {}
        assert isinstance(memory.last_accessed_at, dict)

    def test_append_turn_carries_dict_through(self):
        store = MemoryStore()
        memory = create_memory("session-x")
        # Manually populate to confirm round-trip; M3 will be the path
        # that actually populates it on read.
        memory.last_accessed_at[1] = datetime.utcnow()
        memory.last_accessed_at[2] = datetime.utcnow() - timedelta(minutes=5)

        memory = store.append_turn(
            memory, create_turn_snapshot(1, "Q", "A"),
        )
        assert 1 in memory.last_accessed_at
        assert 2 in memory.last_accessed_at

    def test_append_turn_does_not_alias(self):
        """append_turn must copy last_accessed_at, not reference-share."""
        store = MemoryStore()
        memory_a = create_memory("session-x")
        memory_a.last_accessed_at[1] = datetime.utcnow()

        memory_b = store.append_turn(
            memory_a, create_turn_snapshot(1, "Q", "A"),
        )

        # Mutating memory_b must not leak back into memory_a.
        memory_b.last_accessed_at[2] = datetime.utcnow()
        assert 2 not in memory_a.last_accessed_at


# ===================================================================
# 3. MemoryStore — accepts the kwarg
# ===================================================================


class TestMemoryStoreKwarg:
    def test_default_no_policy(self):
        store = MemoryStore()
        assert store.memory_retention_policy is None

    def test_explicit_policy_stored(self):
        policy = MemoryRetentionPolicy(item_ttl_s=60.0)
        store = MemoryStore(memory_retention_policy=policy)
        assert store.memory_retention_policy is policy

    def test_kwarg_does_not_change_behaviour(self):
        """M2 wires the kwarg without applying any cleanup. A store
        configured with an aggressive policy must still behave exactly
        like one with no policy."""
        aggressive = MemoryRetentionPolicy(
            item_ttl_s=0.0,
            idle_ttl_s=0.0,
            max_items=1,
        )
        store_a = MemoryStore()
        store_b = MemoryStore(memory_retention_policy=aggressive)

        memory_a = create_memory("a")
        memory_b = create_memory("b")
        for i in range(5):
            memory_a = store_a.append_turn(
                memory_a, create_turn_snapshot(i, f"Q{i}", f"A{i}"),
            )
            memory_b = store_b.append_turn(
                memory_b, create_turn_snapshot(i, f"Q{i}", f"A{i}"),
            )

        # Same length; same window-driven eviction.  M3 will introduce
        # the divergence.
        assert len(memory_a.history) == len(memory_b.history)


# ===================================================================
# 4. AgenticLLMWrapper — kwarg threaded into MemoryStore
# ===================================================================


class TestAgenticLLMWrapperKwarg:
    def test_default_no_policy(self):
        agent = AgenticLLMWrapper(MockLLMAdapter(default_response="x"))
        assert agent.memory_store.memory_retention_policy is None

    def test_explicit_policy_threaded(self):
        policy = MemoryRetentionPolicy(idle_ttl_s=120.0)
        agent = AgenticLLMWrapper(
            MockLLMAdapter(default_response="x"),
            memory_retention_policy=policy,
        )
        assert agent.memory_store.memory_retention_policy is policy

    def test_existing_callers_unaffected(self):
        """Pre-v2.5 construction signature still works — the new kwarg
        is keyword-only by default-value position and has a None
        default."""
        agent = AgenticLLMWrapper(
            MockLLMAdapter(default_response="x"),
            memory_window=10,
            quality_threshold=0.3,
        )
        assert agent.memory_store.memory_retention_policy is None


# ===================================================================
# 5. AgentMemory.to_dict() — operational namespace exposed
# ===================================================================


class TestAgentMemoryToDictOperational:
    def test_operational_key_present(self):
        memory = create_memory("session-x")
        d = memory.to_dict()
        assert "operational" in d
        assert "last_accessed_at" in d["operational"]
        assert d["operational"]["last_accessed_at"] == {}

    def test_history_unchanged(self):
        """Existing top-level keys remain — only an additive
        `operational` key is introduced."""
        memory = create_memory("session-x")
        d = memory.to_dict()
        for k in ("session_id", "created_at", "turn_count", "window_size",
                  "history"):
            assert k in d

    def test_last_accessed_at_serialises_isoformat(self):
        memory = create_memory("session-x")
        ts = datetime(2026, 5, 1, 12, 0, 0)
        memory.last_accessed_at[7] = ts
        d = memory.to_dict()
        json.dumps(d)
        # Keys are stringified ints (JSON-safe), values are ISO strings.
        assert d["operational"]["last_accessed_at"]["7"] == ts.isoformat()

    def test_to_dict_json_safe(self):
        memory = create_memory("session-x")
        memory.last_accessed_at[1] = datetime.utcnow()
        # Build some history too.
        store = MemoryStore()
        memory = store.append_turn(
            memory, create_turn_snapshot(1, "Q", "A"),
        )
        json.dumps(memory.to_dict())  # must not raise
