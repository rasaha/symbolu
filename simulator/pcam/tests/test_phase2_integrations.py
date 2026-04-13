"""
Phase 2 tests for the vLLM integration adapter and the trace replay
utility.

Scope is intentionally narrow:

- ``simulator.pcam.integrations.vllm`` importability without vllm
  installed in the test environment
- ``PCAMEvictor`` lifecycle (construction, sequence/phase, admission,
  attention, eviction, tier hints, vLLM duck-type surface)
- ``simulator.pcam.trace`` event schema, replay correctness, and
  unknown-kind handling

These tests do NOT re-test parity — that lives in
``test_sketch_conformance.py`` and ``test_attention_evictor_parity.py``.
The Phase 2 tests assume the runtime policy is correct and only verify
the new adapter and replay layer on top of it.
"""

from __future__ import annotations

import pytest

from simulator.pcam import (
    InferencePhase,
    KVCachePolicy,
    PCAMConfig,
    TierHint,
)
from simulator.pcam.integrations.vllm import PCAMEvictor, make_pcam_evictor
from simulator.pcam.trace import EventKind, ReplayResult, TraceEvent, replay


# ===========================================================================
# vLLM adapter — importability and basic ergonomics
# ===========================================================================


class TestVLLMAdapterImportability:
    def test_import_does_not_require_vllm(self):
        """
        The integration module must import cleanly even when vllm is
        not installed in the environment. We verify this by re-importing
        and checking the public symbols are reachable.
        """
        from simulator.pcam.integrations import vllm as vllm_mod

        assert vllm_mod.PCAMEvictor is PCAMEvictor
        assert vllm_mod.make_pcam_evictor is make_pcam_evictor

    def test_no_root_level_export_added(self):
        """
        Phase 2 must not broaden the package-root API. PCAMEvictor is
        only reachable via simulator.pcam.integrations.vllm, never as
        simulator.pcam.PCAMEvictor.
        """
        import simulator.pcam as pcam

        assert not hasattr(pcam, "PCAMEvictor")


# ===========================================================================
# PCAMEvictor — construction
# ===========================================================================


class TestPCAMEvictorConstruction:
    def test_from_policy(self):
        policy = PCAMConfig(max_blocks=64).build_policy()
        evictor = PCAMEvictor(policy)
        assert evictor.policy is policy
        assert len(evictor) == 0
        assert evictor.num_blocks == 0

    def test_from_config(self):
        cfg = PCAMConfig(max_blocks=64, sink_tokens=2)
        evictor = PCAMEvictor.from_config(cfg)
        assert isinstance(evictor.policy, KVCachePolicy)
        assert evictor.policy.sink_tokens == 2

    def test_make_pcam_evictor_factory(self):
        cfg = PCAMConfig(max_blocks=64)
        evictor = make_pcam_evictor(cfg)
        assert isinstance(evictor, PCAMEvictor)


# ===========================================================================
# PCAMEvictor — sequence lifecycle
# ===========================================================================


class TestPCAMEvictorSequenceLifecycle:
    def _make(self) -> PCAMEvictor:
        return PCAMEvictor.from_config(PCAMConfig(max_blocks=64))

    def test_register_sequence_without_phase(self):
        evictor = self._make()
        evictor.register_sequence(seq_id=1)
        assert 1 in evictor.policy.sequences

    def test_register_sequence_with_phase_in_one_call(self):
        evictor = self._make()
        evictor.register_sequence(seq_id=1, phase=InferencePhase.PREFILL)
        assert evictor.policy.sequences[1].phase is InferencePhase.PREFILL

    def test_set_phase(self):
        evictor = self._make()
        evictor.register_sequence(1)
        evictor.set_phase(1, InferencePhase.DECODE)
        assert evictor.policy.sequences[1].phase is InferencePhase.DECODE

    def test_complete_sequence_drops_tracked_blocks(self):
        evictor = self._make()
        evictor.register_sequence(1)
        evictor.set_phase(1, InferencePhase.DECODE)
        evictor.admit_block(0, 1, [10], vllm_block="block-obj-0")
        evictor.admit_block(1, 1, [20], vllm_block="block-obj-1")

        freed = evictor.complete_sequence(1)
        assert set(freed) == {0, 1}
        # Tracked vLLM block objects must be dropped on completion.
        assert evictor.select_victims_as_blocks(2) == []


# ===========================================================================
# PCAMEvictor — admission, attention, eviction
# ===========================================================================


class TestPCAMEvictorEvictionFlow:
    def _make_with_seq(self) -> PCAMEvictor:
        evictor = PCAMEvictor.from_config(
            PCAMConfig(max_blocks=128, sink_tokens=4)
        )
        evictor.register_sequence(1, phase=InferencePhase.DECODE)
        return evictor

    def test_admit_block_without_vllm_object(self):
        evictor = self._make_with_seq()
        evictor.admit_block(10, 1, [100])
        assert 10 in evictor                      # __contains__
        assert evictor.num_blocks == 1            # property
        assert len(evictor) == 1                  # __len__

    def test_admit_block_with_vllm_object(self):
        evictor = self._make_with_seq()
        sentinel = object()
        evictor.admit_block(10, 1, [100], vllm_block=sentinel)
        evictor.on_attention(10, 0.0001, 1)       # filler
        # select_victims returns the bare ID
        ids = evictor.select_victims(1)
        assert ids == [10]
        # select_victims_as_blocks returns the tracked sentinel
        blocks = evictor.select_victims_as_blocks(1)
        assert blocks == [sentinel]

    def test_select_victims_skips_sinks(self):
        evictor = self._make_with_seq()
        # Sink block (positions 0..3 trigger is_sink=True)
        evictor.admit_block(0, 1, [0, 1, 2, 3])
        # Filler blocks
        evictor.admit_block(1, 1, [100])
        evictor.admit_block(2, 1, [200])
        evictor.on_attention(1, 0.0001, 1)
        evictor.on_attention(2, 0.0001, 1)

        victims = evictor.select_victims(2)
        assert 0 not in victims
        assert set(victims) == {1, 2}

    def test_select_victims_as_blocks_skips_untracked(self):
        evictor = self._make_with_seq()
        evictor.admit_block(0, 1, [0, 1, 2, 3])           # sink, no obj
        evictor.admit_block(1, 1, [100])                  # filler, no obj
        evictor.admit_block(2, 1, [200], vllm_block="b2")  # filler, tracked
        evictor.on_attention(1, 0.0001, 1)
        evictor.on_attention(2, 0.0001, 1)

        blocks = evictor.select_victims_as_blocks(2)
        assert blocks == ["b2"]  # only the tracked one survives

    def test_evict_block_returns_tracked_object(self):
        evictor = self._make_with_seq()
        sentinel = object()
        evictor.admit_block(10, 1, [100], vllm_block=sentinel)
        returned = evictor.evict_block(10)
        assert returned is sentinel
        assert 10 not in evictor
        # Subsequent evict_block returns None for already-gone blocks
        assert evictor.evict_block(10) is None


# ===========================================================================
# PCAMEvictor — tier hints
# ===========================================================================


class TestPCAMEvictorTierHints:
    def test_classify_tier_delegates(self):
        evictor = PCAMEvictor.from_config(PCAMConfig(max_blocks=64))
        evictor.register_sequence(1, phase=InferencePhase.DECODE)
        evictor.admit_block(0, 1, [0, 1, 2, 3])  # sink → HOT clamp
        assert evictor.classify_tier(0) is TierHint.HOT
        assert evictor.classify_tier(9999) is TierHint.EVICT

    def test_tier_hints_batches(self):
        evictor = PCAMEvictor.from_config(PCAMConfig(max_blocks=64))
        evictor.register_sequence(1, phase=InferencePhase.DECODE)
        evictor.admit_block(0, 1, [0, 1, 2, 3])
        evictor.admit_block(1, 1, [100])
        evictor.on_attention(1, 0.001, 1)

        hints = evictor.tier_hints([0, 1, 9999])
        assert hints[0] is TierHint.HOT
        assert hints[9999] is TierHint.EVICT
        assert hints[1] in (TierHint.COLD, TierHint.WARM, TierHint.EVICT)


# ===========================================================================
# Trace replay — event schema and round-trips
# ===========================================================================


class TestTraceEventSchema:
    def test_event_kind_string_values(self):
        assert EventKind.REGISTER_SEQUENCE.value == "register_sequence"
        assert EventKind.SET_PHASE.value == "set_phase"
        assert EventKind.ENSURE_BLOCK.value == "ensure_block"
        assert EventKind.ON_BLOCK_ATTENTION.value == "on_block_attention"
        assert EventKind.SELECT_VICTIMS.value == "select_victims"
        assert EventKind.COMPLETE_SEQUENCE.value == "complete_sequence"
        assert EventKind.TIER_HINTS.value == "tier_hints"

    def test_from_dict_roundtrip(self):
        event = TraceEvent(
            kind=EventKind.ENSURE_BLOCK,
            args={"block_id": 10, "sequence_id": 1, "positions": [100]},
        )
        round = TraceEvent.from_dict(event.to_dict())
        assert round.kind is event.kind
        assert round.args == event.args

    def test_from_dict_missing_kind_raises(self):
        with pytest.raises(TypeError, match="kind"):
            TraceEvent.from_dict({"args": {}})

    def test_from_dict_unknown_kind_raises(self):
        with pytest.raises(ValueError):
            TraceEvent.from_dict({"kind": "not_a_real_kind"})


# ===========================================================================
# Trace replay — execution
# ===========================================================================


class TestTraceReplay:
    def _build_basic_trace(self):
        return [
            TraceEvent(EventKind.REGISTER_SEQUENCE, {"seq_id": 1}),
            TraceEvent(EventKind.SET_PHASE, {"seq_id": 1, "phase": "DECODE"}),
            TraceEvent(EventKind.ENSURE_BLOCK,
                       {"block_id": 0, "sequence_id": 1, "positions": [0, 1, 2, 3]}),
            TraceEvent(EventKind.ENSURE_BLOCK,
                       {"block_id": 1, "sequence_id": 1, "positions": [100]}),
            TraceEvent(EventKind.ENSURE_BLOCK,
                       {"block_id": 2, "sequence_id": 1, "positions": [200]}),
            TraceEvent(EventKind.ON_BLOCK_ATTENTION,
                       {"block_id": 1, "attention_sum": 0.001, "sequence_id": 1}),
            TraceEvent(EventKind.ON_BLOCK_ATTENTION,
                       {"block_id": 2, "attention_sum": 0.001, "sequence_id": 1}),
            TraceEvent(EventKind.SELECT_VICTIMS, {"count": 2}),
            TraceEvent(EventKind.TIER_HINTS, {"block_ids": [0, 1, 2, 9999]}),
            TraceEvent(EventKind.COMPLETE_SEQUENCE, {"seq_id": 1}),
        ]

    def test_replay_returns_structured_result(self):
        policy = PCAMConfig(max_blocks=64).build_policy()
        result = replay(policy, self._build_basic_trace())

        assert isinstance(result, ReplayResult)
        assert result.event_count == 10
        assert isinstance(result.final_stats, dict)

    def test_replay_captures_victim_lists(self):
        policy = PCAMConfig(max_blocks=64).build_policy()
        result = replay(policy, self._build_basic_trace())

        assert len(result.victim_lists) == 1
        # Sink block (0) is pinned and must not appear.
        assert 0 not in result.victim_lists[0]
        assert set(result.victim_lists[0]) == {1, 2}

    def test_replay_captures_tier_hints(self):
        policy = PCAMConfig(max_blocks=64).build_policy()
        result = replay(policy, self._build_basic_trace())

        assert len(result.tier_hint_results) == 1
        hints = result.tier_hint_results[0]
        assert hints[0] is TierHint.HOT             # sink clamp
        assert hints[9999] is TierHint.EVICT        # unknown
        assert hints[1] in (TierHint.COLD, TierHint.WARM, TierHint.EVICT)

    def test_replay_captures_completed_sequences(self):
        policy = PCAMConfig(max_blocks=64).build_policy()
        result = replay(policy, self._build_basic_trace())

        assert len(result.completed_sequences) == 1
        # The sequence had 3 admitted blocks, but the pre-replay
        # SELECT_VICTIMS event evicted 2 of them, so only the sink
        # remains by the time COMPLETE_SEQUENCE fires.
        freed = set(result.completed_sequences[0])
        assert 0 in freed

    def test_replay_accepts_inference_phase_instance(self):
        """The set_phase event must accept an InferencePhase value as
        well as the string form."""
        events = [
            TraceEvent(EventKind.REGISTER_SEQUENCE, {"seq_id": 1}),
            TraceEvent(
                EventKind.SET_PHASE,
                {"seq_id": 1, "phase": InferencePhase.PREFILL},
            ),
        ]
        policy = PCAMConfig(max_blocks=64).build_policy()
        replay(policy, events)
        assert policy.sequences[1].phase is InferencePhase.PREFILL

    def test_replay_unknown_phase_string_raises(self):
        events = [
            TraceEvent(EventKind.REGISTER_SEQUENCE, {"seq_id": 1}),
            TraceEvent(
                EventKind.SET_PHASE,
                {"seq_id": 1, "phase": "BOGUS_PHASE"},
            ),
        ]
        policy = PCAMConfig(max_blocks=64).build_policy()
        with pytest.raises(ValueError, match="InferencePhase"):
            replay(policy, events)
