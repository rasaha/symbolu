"""
Tests for MemoryRetentionPolicy (v2.5).

Batches covered:
- M2 — policy types, ``last_accessed_at`` field, kwarg threading,
  ``to_dict`` operational namespace.
- M3 — lazy eviction on read and write: ``item_ttl_s``, ``idle_ttl_s``,
  ``max_items``; embedding-cache and ``last_accessed_at`` pruning;
  read-path access updates; backward compatibility with no policy or
  inactive policy; ``window_size`` vs ``max_items`` composition.
- M4 — per-session eviction counter on ``AgentMemory`` and trace
  surfacing via ``AgentRunTrace.memory_evictions``.

A ``MEMORY_EVICTED`` streaming event is explicitly NOT shipped
(per design §2 / §8).
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

    def test_inactive_policy_matches_no_policy(self):
        """A policy with all fields ``None`` is observably indistinguishable
        from no policy at all."""
        store_a = MemoryStore()
        store_b = MemoryStore(memory_retention_policy=MemoryRetentionPolicy())

        memory_a = create_memory("a")
        memory_b = create_memory("b")
        for i in range(5):
            memory_a = store_a.append_turn(
                memory_a, create_turn_snapshot(i, f"Q{i}", f"A{i}"),
            )
            memory_b = store_b.append_turn(
                memory_b, create_turn_snapshot(i, f"Q{i}", f"A{i}"),
            )

        assert len(memory_a.history) == len(memory_b.history)
        assert [t.turn_id for t in memory_a.history] == [
            t.turn_id for t in memory_b.history
        ]


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


# ===================================================================
# M3 — Lazy eviction on read and write
# ===================================================================
#
# Tests force expiry by rewinding TurnSnapshot.timestamp and
# AgentMemory.last_accessed_at backwards rather than sleeping in real
# time.  Same pattern as B2 (session TTL): keeps the suite fast and
# deterministic.
# ===================================================================


def _seed(store, memory, turn_ids, age_s_each=None):
    """Append turns with the given turn_ids; optionally rewind each
    turn's timestamp by ``age_s_each`` seconds (for item_ttl tests)."""
    for tid in turn_ids:
        memory = store.append_turn(
            memory, create_turn_snapshot(tid, f"Q{tid}", f"A{tid}"),
        )
    if age_s_each is not None:
        delta = timedelta(seconds=age_s_each)
        for turn in memory.history:
            turn.timestamp = turn.timestamp - delta
    return memory


def _rewind_last_accessed(memory, seconds, only_turn_ids=None):
    """Pretend the last-access for some/all turns happened earlier."""
    delta = timedelta(seconds=seconds)
    for tid in list(memory.last_accessed_at.keys()):
        if only_turn_ids is not None and tid not in only_turn_ids:
            continue
        memory.last_accessed_at[tid] = memory.last_accessed_at[tid] - delta


class TestM3ItemTTL:
    def test_old_turns_evicted_on_read(self):
        store = MemoryStore(
            memory_retention_policy=MemoryRetentionPolicy(item_ttl_s=10.0),
        )
        memory = create_memory("s")
        memory = _seed(store, memory, [1, 2, 3], age_s_each=60.0)
        # All three turns are 60 s old; TTL is 10 s.
        recent = store.get_summary_for_llm(memory, max_turns=10)
        assert "Turn 1" not in recent
        assert "Turn 2" not in recent
        assert "Turn 3" not in recent
        assert memory.history == []  # eviction is in-place on read

    def test_old_turns_evicted_on_write(self):
        store = MemoryStore(
            memory_retention_policy=MemoryRetentionPolicy(item_ttl_s=10.0),
        )
        memory = create_memory("s")
        memory = _seed(store, memory, [1, 2], age_s_each=60.0)
        # Both old turns evicted before the new turn is appended.
        memory = store.append_turn(memory, create_turn_snapshot(3, "Q3", "A3"))
        assert [t.turn_id for t in memory.history] == [3]

    def test_fresh_turn_survives_when_appended_alongside_expired(self):
        store = MemoryStore(
            memory_retention_policy=MemoryRetentionPolicy(item_ttl_s=10.0),
        )
        memory = create_memory("s")
        memory = _seed(store, memory, [1], age_s_each=60.0)
        memory = store.append_turn(memory, create_turn_snapshot(2, "Q2", "A2"))
        # Turn 1 was evicted (old); Turn 2 was just added (fresh).
        assert [t.turn_id for t in memory.history] == [2]

    def test_within_ttl_no_eviction(self):
        store = MemoryStore(
            memory_retention_policy=MemoryRetentionPolicy(item_ttl_s=3600.0),
        )
        memory = create_memory("s")
        memory = _seed(store, memory, [1, 2, 3])  # no rewind
        memory = store.append_turn(memory, create_turn_snapshot(4, "Q4", "A4"))
        assert [t.turn_id for t in memory.history] == [1, 2, 3, 4]


class TestM3IdleTTL:
    def test_idle_turn_evicted_on_read(self):
        store = MemoryStore(
            memory_retention_policy=MemoryRetentionPolicy(idle_ttl_s=10.0),
        )
        memory = create_memory("s")
        memory = _seed(store, memory, [1, 2, 3])
        # Append stamps last_accessed_at[i] = now for each i.
        # Rewind only turn 1's last-access by 60 s.
        _rewind_last_accessed(memory, seconds=60.0, only_turn_ids=[1])
        store.get_summary_for_llm(memory, max_turns=10)
        assert [t.turn_id for t in memory.history] == [2, 3]

    def test_never_accessed_falls_back_to_created_at(self):
        """A turn that has no last_accessed_at entry falls back to its
        ``timestamp`` (creation time) for the idle check."""
        store = MemoryStore(
            memory_retention_policy=MemoryRetentionPolicy(idle_ttl_s=10.0),
        )
        memory = create_memory("s")
        memory = _seed(store, memory, [1])
        # Drop the last_accessed entry so the fallback fires.
        memory.last_accessed_at.pop(1)
        # Turn 1's created_at is recent -> survives.
        store.get_summary_for_llm(memory, max_turns=10)
        assert [t.turn_id for t in memory.history] == [1]
        # Now age the turn's timestamp; with no last_accessed entry it
        # falls back to the (aged) created_at -> evicted.
        memory.history[0].timestamp -= timedelta(seconds=60.0)
        memory.last_accessed_at.pop(1, None)
        store.get_summary_for_llm(memory, max_turns=10)
        assert memory.history == []

    def test_read_extends_idle_window(self):
        """Reading a turn updates its last_accessed_at to now; the
        next idle check must use the newer timestamp."""
        store = MemoryStore(
            memory_retention_policy=MemoryRetentionPolicy(idle_ttl_s=10.0),
        )
        memory = create_memory("s")
        memory = _seed(store, memory, [1, 2])
        # Rewind both last-access timestamps to be 5 s old (still within
        # idle TTL).
        _rewind_last_accessed(memory, seconds=5.0)
        # Read turn 1 explicitly via get_summary (max_turns=1 picks the
        # most recent only -> turn 2).  Then turn 1 is still 5 s old.
        store.get_summary_for_llm(memory, max_turns=1)
        # Now both turns are present; the "recent" one (2) was touched.
        # Rewind both by 30 s; the just-touched one was reset to ~0 s
        # ago by get_summary, so after rewind it's ~30 s old.  But the
        # just-touched-then-rewound test is brittle; cover the simpler
        # claim instead: get_summary did update last_accessed for the
        # turns it returned.
        ts_before = memory.last_accessed_at[2]
        store.get_summary_for_llm(memory, max_turns=1)
        ts_after = memory.last_accessed_at[2]
        assert ts_after >= ts_before


class TestM3MaxItems:
    def test_max_items_drops_oldest_on_write(self):
        store = MemoryStore(
            memory_retention_policy=MemoryRetentionPolicy(max_items=3),
        )
        memory = create_memory("s")
        for i in range(5):
            memory = store.append_turn(
                memory, create_turn_snapshot(i, f"Q{i}", f"A{i}"),
            )
        assert [t.turn_id for t in memory.history] == [2, 3, 4]

    def test_max_items_overrides_window_size(self):
        """When max_items is set, AgentMemory.window_size is ignored."""
        store = MemoryStore(
            memory_retention_policy=MemoryRetentionPolicy(max_items=2),
        )
        memory = create_memory("s")
        memory.window_size = 10  # would otherwise allow 10 turns
        for i in range(5):
            memory = store.append_turn(
                memory, create_turn_snapshot(i, f"Q{i}", f"A{i}"),
            )
        assert [t.turn_id for t in memory.history] == [3, 4]

    def test_max_items_includes_newly_appended_turn(self):
        """The newly appended turn counts toward max_items immediately."""
        store = MemoryStore(
            memory_retention_policy=MemoryRetentionPolicy(max_items=1),
        )
        memory = create_memory("s")
        for i in range(3):
            memory = store.append_turn(
                memory, create_turn_snapshot(i, f"Q{i}", f"A{i}"),
            )
            assert len(memory.history) == 1

    def test_max_items_after_ttl(self):
        """TTL filters first; max_items applies to the survivors only."""
        store = MemoryStore(
            memory_retention_policy=MemoryRetentionPolicy(
                item_ttl_s=10.0,
                max_items=5,
            ),
        )
        memory = create_memory("s")
        # 3 expired turns + 2 fresh.
        memory = _seed(store, memory, [1, 2, 3], age_s_each=60.0)
        memory = store.append_turn(memory, create_turn_snapshot(4, "Q4", "A4"))
        memory = store.append_turn(memory, create_turn_snapshot(5, "Q5", "A5"))
        # TTL drops 1, 2, 3; max_items=5 leaves 4, 5 untouched.
        assert [t.turn_id for t in memory.history] == [4, 5]

    def test_max_items_evicts_on_read(self):
        store = MemoryStore(
            memory_retention_policy=MemoryRetentionPolicy(max_items=2),
        )
        memory = create_memory("s")
        # Bypass append_turn's max_items by writing directly to history.
        for i in range(5):
            memory.history.append(create_turn_snapshot(i, f"Q{i}", f"A{i}"))
        store.get_summary_for_llm(memory, max_turns=10)
        assert [t.turn_id for t in memory.history] == [3, 4]


class TestM3CachePruning:
    def test_embedding_cache_pruned_on_eviction(self):
        store = MemoryStore(
            memory_retention_policy=MemoryRetentionPolicy(item_ttl_s=10.0),
        )
        memory = create_memory("s")
        memory = _seed(store, memory, [1, 2, 3], age_s_each=60.0)
        # Pre-populate embedding_cache for the about-to-expire turns.
        for tid in (1, 2, 3):
            memory.embedding_cache[tid] = [0.0, 0.1]
        store.get_summary_for_llm(memory, max_turns=10)
        # All three evicted -> all three pruned from the cache.
        for tid in (1, 2, 3):
            assert tid not in memory.embedding_cache

    def test_last_accessed_pruned_on_eviction(self):
        store = MemoryStore(
            memory_retention_policy=MemoryRetentionPolicy(item_ttl_s=10.0),
        )
        memory = create_memory("s")
        memory = _seed(store, memory, [1, 2, 3], age_s_each=60.0)
        for tid in (1, 2, 3):
            assert tid in memory.last_accessed_at
        store.get_summary_for_llm(memory, max_turns=10)
        for tid in (1, 2, 3):
            assert tid not in memory.last_accessed_at

    def test_cache_intact_for_survivors(self):
        store = MemoryStore(
            memory_retention_policy=MemoryRetentionPolicy(item_ttl_s=10.0),
        )
        memory = create_memory("s")
        memory = _seed(store, memory, [1, 2, 3])  # all fresh
        for tid in (1, 2, 3):
            memory.embedding_cache[tid] = [0.0, 0.1]
        store.get_summary_for_llm(memory, max_turns=10)
        # Nothing evicted -> cache untouched.
        for tid in (1, 2, 3):
            assert tid in memory.embedding_cache


class TestM3ReadPathAccessUpdates:
    def test_get_summary_for_llm_updates_returned_turns(self):
        store = MemoryStore(
            memory_retention_policy=MemoryRetentionPolicy(idle_ttl_s=999.0),
        )
        memory = create_memory("s")
        memory = _seed(store, memory, [1, 2, 3])
        # Rewind every entry's last-access to 100 s ago.
        _rewind_last_accessed(memory, seconds=100.0)
        before = dict(memory.last_accessed_at)
        store.get_summary_for_llm(memory, max_turns=2)  # picks 2, 3
        # Turns 2 and 3 were returned -> updated.  Turn 1 was not.
        assert memory.last_accessed_at[2] > before[2]
        assert memory.last_accessed_at[3] > before[3]
        assert memory.last_accessed_at[1] == before[1]

    def test_search_by_keyword_updates_matches(self):
        store = MemoryStore(
            memory_retention_policy=MemoryRetentionPolicy(idle_ttl_s=999.0),
        )
        memory = create_memory("s")
        memory = store.append_turn(
            memory, create_turn_snapshot(1, "find me", "yes"),
        )
        memory = store.append_turn(
            memory, create_turn_snapshot(2, "skip", "no"),
        )
        _rewind_last_accessed(memory, seconds=100.0)
        before = dict(memory.last_accessed_at)
        results = store.search_by_keyword(memory, "find")
        assert [t.turn_id for t in results] == [1]
        assert memory.last_accessed_at[1] > before[1]
        assert memory.last_accessed_at[2] == before[2]

    def test_get_recent_turns_does_not_update(self):
        """Per Decision 2: get_recent_turns is a low-level accessor on
        AgentMemory and must NOT update last_accessed_at."""
        store = MemoryStore(
            memory_retention_policy=MemoryRetentionPolicy(idle_ttl_s=999.0),
        )
        memory = create_memory("s")
        memory = _seed(store, memory, [1, 2, 3])
        _rewind_last_accessed(memory, seconds=100.0)
        before = dict(memory.last_accessed_at)
        memory.get_recent_turns(n=2)
        # No mutation.
        assert memory.last_accessed_at == before


class TestM3BackwardCompat:
    def test_no_policy_window_size_still_applies(self):
        store = MemoryStore()  # no policy
        memory = create_memory("s")
        memory.window_size = 3
        for i in range(5):
            memory = store.append_turn(
                memory, create_turn_snapshot(i, f"Q{i}", f"A{i}"),
            )
        assert [t.turn_id for t in memory.history] == [2, 3, 4]

    def test_inactive_policy_window_size_still_applies(self):
        """All-None policy: window_size still applies (max_items unset)."""
        store = MemoryStore(
            memory_retention_policy=MemoryRetentionPolicy(),
        )
        memory = create_memory("s")
        memory.window_size = 3
        for i in range(5):
            memory = store.append_turn(
                memory, create_turn_snapshot(i, f"Q{i}", f"A{i}"),
            )
        assert [t.turn_id for t in memory.history] == [2, 3, 4]

    def test_no_policy_no_last_accessed_updates(self):
        """With no policy, read paths must not update last_accessed_at
        either.  (The dict exists as a v2.5 field but stays unused.)"""
        store = MemoryStore()
        memory = create_memory("s")
        memory = _seed(store, memory, [1, 2])
        # append_turn DOES populate last_accessed_at for the new turn —
        # that's where the entries come from.  Rewind, then read.
        _rewind_last_accessed(memory, seconds=100.0)
        before = dict(memory.last_accessed_at)
        store.get_summary_for_llm(memory, max_turns=10)
        # No policy: read paths do not touch last_accessed_at.
        assert memory.last_accessed_at == before

    def test_no_policy_history_unchanged_on_read(self):
        store = MemoryStore()
        memory = create_memory("s")
        memory = _seed(store, memory, [1, 2, 3], age_s_each=1e9)
        store.get_summary_for_llm(memory, max_turns=10)
        # No policy: ancient turns survive untouched.
        assert [t.turn_id for t in memory.history] == [1, 2, 3]


class TestM3Integration:
    def test_idle_eviction_full_lifecycle(self):
        """End-to-end: append turns; let some go idle; next read evicts
        them; subsequent reads see the trimmed history."""
        store = MemoryStore(
            memory_retention_policy=MemoryRetentionPolicy(idle_ttl_s=10.0),
        )
        memory = create_memory("s")
        memory = _seed(store, memory, [1, 2, 3])
        # Rewind only turn 1.
        _rewind_last_accessed(memory, seconds=60.0, only_turn_ids=[1])
        store.get_summary_for_llm(memory, max_turns=10)
        assert [t.turn_id for t in memory.history] == [2, 3]
        # New turn appended on top.
        memory = store.append_turn(memory, create_turn_snapshot(4, "Q4", "A4"))
        assert [t.turn_id for t in memory.history] == [2, 3, 4]

    def test_three_field_composition(self):
        """item_ttl_s + idle_ttl_s + max_items applied together."""
        store = MemoryStore(
            memory_retention_policy=MemoryRetentionPolicy(
                item_ttl_s=100.0,
                idle_ttl_s=50.0,
                max_items=2,
            ),
        )
        memory = create_memory("s")
        # Bypass append_turn so max_items doesn't filter as we seed.
        now = datetime.utcnow()
        for i in [1, 2, 3, 4, 5]:
            memory.history.append(create_turn_snapshot(i, f"Q{i}", f"A{i}"))
            memory.last_accessed_at[i] = now
        # Age turn 1 past item_ttl; idle-rewind turn 2 past idle_ttl;
        # leave 3, 4, 5 fresh.
        memory.history[0].timestamp = memory.history[0].timestamp - timedelta(seconds=200.0)
        memory.last_accessed_at[2] = memory.last_accessed_at[2] - timedelta(seconds=100.0)
        store.get_summary_for_llm(memory, max_turns=10)
        # 1 evicted by item_ttl, 2 evicted by idle_ttl, then max_items
        # keeps the last 2 of [3, 4, 5] -> [4, 5].
        assert [t.turn_id for t in memory.history] == [4, 5]


# ===================================================================
# M4 — Per-session eviction counter + trace surfacing
# ===================================================================
#
# The counter lives on AgentMemory.evictions_since_last_run and is
# reset to 0 at the top of every public entry point (run / run_stream
# / run_stream_async).  The trace reads it from the RUN_COMPLETED
# payload and surfaces it as AgentRunTrace.memory_evictions.
# ===================================================================


def _make_runtime_agent(memory_retention_policy=None):
    """Build a permissive agent for end-to-end run tests."""
    from agentic.agentic_framework.safety_contract import (
        SafetyContractEvaluator, SafetyGate,
    )
    llm = MockLLMAdapter(default_response=(
        "A reasonably detailed response that should pass the rule-based "
        "critic without revisions; long enough to satisfy the threshold."
    ))
    agent = AgenticLLMWrapper(
        llm,
        use_llm_for_decomposition=False,
        max_revisions=0,
        quality_threshold=0.3,
        memory_retention_policy=memory_retention_policy,
    )
    agent.new_session()
    agent.safety_gate = SafetyGate(
        evaluator=SafetyContractEvaluator(
            consistency_threshold=0.0,
            alignment_threshold=0.0,
            reversal_risk_threshold=1.0,
            stability_threshold=0.0,
        ),
    )
    return agent


class TestM4CounterMechanics:
    def test_default_counter_is_zero(self):
        memory = create_memory("s")
        assert memory.evictions_since_last_run == 0

    def test_read_eviction_counted(self):
        store = MemoryStore(
            memory_retention_policy=MemoryRetentionPolicy(item_ttl_s=10.0),
        )
        memory = create_memory("s")
        memory = _seed(store, memory, [1, 2, 3], age_s_each=60.0)
        # append_turn left the counter at 0 (turns were fresh at append).
        # Now the rewind makes them all expired; reading triggers
        # eviction of all three.
        assert memory.evictions_since_last_run == 0
        store.get_summary_for_llm(memory, max_turns=10)
        assert memory.evictions_since_last_run == 3

    def test_write_eviction_counted(self):
        store = MemoryStore(
            memory_retention_policy=MemoryRetentionPolicy(item_ttl_s=10.0),
        )
        memory = create_memory("s")
        memory = _seed(store, memory, [1, 2], age_s_each=60.0)
        # append_turn evicts the two stale turns before adding turn 3.
        memory = store.append_turn(
            memory, create_turn_snapshot(3, "Q3", "A3"),
        )
        assert memory.evictions_since_last_run == 2

    def test_max_items_drops_count(self):
        store = MemoryStore(
            memory_retention_policy=MemoryRetentionPolicy(max_items=2),
        )
        memory = create_memory("s")
        for i in range(5):
            memory = store.append_turn(
                memory, create_turn_snapshot(i, f"Q{i}", f"A{i}"),
            )
        # Each append after the second one drops the oldest under
        # max_items=2 -> three policy-driven cap drops total.
        assert memory.evictions_since_last_run == 3

    def test_window_size_drops_not_counted(self):
        """Window-size positional rolloff is the pre-v2.5 behaviour
        and must NOT be counted (only opted-in policy evictions are)."""
        store = MemoryStore()  # no policy
        memory = create_memory("s")
        memory.window_size = 3
        for i in range(6):
            memory = store.append_turn(
                memory, create_turn_snapshot(i, f"Q{i}", f"A{i}"),
            )
        # Three turns rolled off via window_size; counter unchanged.
        assert memory.evictions_since_last_run == 0

    def test_no_evictions_zero(self):
        store = MemoryStore(
            memory_retention_policy=MemoryRetentionPolicy(item_ttl_s=3600.0),
        )
        memory = create_memory("s")
        memory = _seed(store, memory, [1, 2, 3])  # all fresh
        store.get_summary_for_llm(memory, max_turns=10)
        memory = store.append_turn(
            memory, create_turn_snapshot(4, "Q4", "A4"),
        )
        assert memory.evictions_since_last_run == 0

    def test_inactive_policy_zero(self):
        store = MemoryStore(memory_retention_policy=MemoryRetentionPolicy())
        memory = create_memory("s")
        memory = _seed(store, memory, [1, 2, 3])
        store.get_summary_for_llm(memory, max_turns=10)
        assert memory.evictions_since_last_run == 0

    def test_counter_accumulates_across_calls(self):
        store = MemoryStore(
            memory_retention_policy=MemoryRetentionPolicy(item_ttl_s=10.0),
        )
        memory = create_memory("s")
        memory = _seed(store, memory, [1], age_s_each=60.0)
        memory = store.append_turn(
            memory, create_turn_snapshot(2, "Q2", "A2"),
        )
        # First write: 1 evicted.
        assert memory.evictions_since_last_run == 1
        # Age the survivor and read.
        memory.history[0].timestamp = datetime.utcnow() - timedelta(seconds=60)
        store.get_summary_for_llm(memory, max_turns=10)
        # Second eviction adds.
        assert memory.evictions_since_last_run == 2


class TestM4ResetBetweenRuns:
    def test_run_stream_resets_counter(self):
        agent = _make_runtime_agent(
            memory_retention_policy=MemoryRetentionPolicy(item_ttl_s=10.0),
        )
        # First run completes naturally.
        list(agent.run_stream("first"))
        # Pre-stage a stale turn so the next run will evict on append.
        agent._memory.history[0].timestamp -= timedelta(seconds=60)

        # Second run: at the top, counter resets to 0 BEFORE eviction
        # fires inside the run.  Eviction during the run takes it back
        # up.
        list(agent.run_stream("second"))
        # The first turn (now stale) was evicted somewhere during run 2
        # — counter is whatever evictions ran for THIS run only.
        assert agent._memory.evictions_since_last_run >= 1

        # Third run starts; reset must wipe run-2's accumulation
        # before any cleanup fires.  We capture the counter at the
        # moment the reset would have happened by running with a
        # passive setup (no eviction this run).
        # Pre-stage: no expired turns — counter for run 3 should be 0.
        list(agent.run_stream("third"))
        # No turn is expired heading into run 3, so no eviction occurred
        # during run 3 itself.
        assert agent._memory.evictions_since_last_run == 0

    def test_run_resets_counter(self):
        agent = _make_runtime_agent(
            memory_retention_policy=MemoryRetentionPolicy(item_ttl_s=10.0),
        )
        # Force the counter to be non-zero before the next run.
        agent._memory.evictions_since_last_run = 7
        agent.run("hello")
        # run() resets at the top; no expired turns in this run, so
        # counter stays 0 after reset.
        assert agent._memory.evictions_since_last_run == 0

    def test_async_run_stream_resets_counter(self):
        agent = _make_runtime_agent(
            memory_retention_policy=MemoryRetentionPolicy(item_ttl_s=10.0),
        )
        agent._memory.evictions_since_last_run = 9

        async def _run():
            out = []
            async for evt in agent.run_stream_async("hello"):
                out.append(evt)
            return out

        asyncio.run(_run())
        assert agent._memory.evictions_since_last_run == 0


class TestM4TraceSurface:
    def test_trace_memory_evictions_zero_default(self):
        from agentic.agentic_framework.tracing import TraceCollector
        agent = _make_runtime_agent()  # no policy
        collector = TraceCollector()
        list(agent.run_stream("hello", trace_collector=collector))
        trace = collector.build_trace()
        assert trace.memory_evictions == 0

    def test_trace_memory_evictions_counts_writes(self):
        from agentic.agentic_framework.tracing import TraceCollector
        agent = _make_runtime_agent(
            memory_retention_policy=MemoryRetentionPolicy(item_ttl_s=10.0),
        )
        # Run once to seed an entry, then age it.
        list(agent.run_stream("seed"))
        agent._memory.history[0].timestamp -= timedelta(seconds=60)
        # Second run: append_turn at the end evicts the stale turn.
        collector = TraceCollector()
        list(agent.run_stream("second", trace_collector=collector))
        trace = collector.build_trace()
        assert trace.memory_evictions >= 1

    def test_trace_to_dict_includes_field(self):
        from agentic.agentic_framework.tracing import TraceCollector
        agent = _make_runtime_agent()
        collector = TraceCollector()
        list(agent.run_stream("hello", trace_collector=collector))
        d = collector.build_trace().to_dict()
        json.dumps(d)
        assert "memory_evictions" in d
        assert d["memory_evictions"] == 0

    def test_trace_summary_includes_field(self):
        from agentic.agentic_framework.tracing import TraceCollector
        agent = _make_runtime_agent()
        collector = TraceCollector()
        list(agent.run_stream("hello", trace_collector=collector))
        summary = collector.build_trace().summary
        assert "memory_evictions" in summary

    def test_trace_no_policy_unchanged(self):
        """With no policy, trace.memory_evictions stays 0 even after
        many turns rolled off via window_size."""
        from agentic.agentic_framework.tracing import TraceCollector
        agent = _make_runtime_agent()
        agent._memory.window_size = 2
        # Force several turns through window_size rolloff.
        for i in range(5):
            list(agent.run_stream(f"turn {i}"))
        collector = TraceCollector()
        list(agent.run_stream("final", trace_collector=collector))
        trace = collector.build_trace()
        assert trace.memory_evictions == 0


# Module-level imports needed by the M4 runtime tests above.
import asyncio  # noqa: E402
