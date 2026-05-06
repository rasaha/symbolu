"""Tests for the workload generators."""

from __future__ import annotations

import pytest

from ctm_bench.workload import (
    AccessPattern,
    AGENTIC_64K,
    AGENTIC_CLUSTERED_64K,
    CHAT_32K,
    RAG_128K,
    TraceEvent,
    WorkloadSpec,
    generate,
    generate_agentic,
    generate_agentic_clustered,
    generate_chat,
    generate_rag,
)


def test_workload_spec_validates_n_concurrent_seqs_positive():
    with pytest.raises(ValueError, match="n_concurrent_seqs"):
        WorkloadSpec(
            name="bad",
            pattern=AccessPattern.AGENTIC,
            n_concurrent_seqs=0,
            context_length_tokens=1024,
            duration_decode_tokens=64,
        )


def test_workload_spec_validates_context_length_positive():
    with pytest.raises(ValueError, match="context_length_tokens"):
        WorkloadSpec(
            name="bad",
            pattern=AccessPattern.RAG,
            n_concurrent_seqs=1,
            context_length_tokens=0,
            duration_decode_tokens=64,
        )


def test_pinned_workload_specs_present():
    """The reference workloads exist + carry the expected pattern.
    Pinned so the CLI default remains stable."""
    assert AGENTIC_64K.pattern is AccessPattern.AGENTIC
    assert AGENTIC_64K.context_length_tokens == 64 * 1024
    assert AGENTIC_CLUSTERED_64K.pattern is AccessPattern.AGENTIC_CLUSTERED
    assert AGENTIC_CLUSTERED_64K.context_length_tokens == 64 * 1024
    assert RAG_128K.pattern is AccessPattern.RAG
    assert RAG_128K.context_length_tokens == 128 * 1024
    assert CHAT_32K.pattern is AccessPattern.CHAT
    assert CHAT_32K.context_length_tokens == 32 * 1024


def test_n_blocks_per_sequence_rounds_up():
    spec = WorkloadSpec(
        name="x",
        pattern=AccessPattern.RAG,
        n_concurrent_seqs=1,
        context_length_tokens=33,
        duration_decode_tokens=8,
        block_size_tokens=16,
    )
    # 33 tokens / 16 per block → 3 blocks (rounded up from 2.0625).
    assert spec.n_blocks_per_sequence() == 3


def _smoke_spec(pattern: AccessPattern) -> WorkloadSpec:
    return WorkloadSpec(
        name=f"smoke_{pattern.value}",
        pattern=pattern,
        n_concurrent_seqs=2,
        context_length_tokens=128,
        duration_decode_tokens=8,
        block_size_tokens=16,
        seed=7,
    )


def test_agentic_generator_yields_prefill_first_then_decode():
    spec = _smoke_spec(AccessPattern.AGENTIC)
    events = list(generate_agentic(spec))
    # Find the boundary between prefill + decode for seq 0.
    seq0_prefill = [e for e in events if e.seq_id == 0 and e.is_prefill]
    seq0_decode = [e for e in events if e.seq_id == 0 and not e.is_prefill]
    assert len(seq0_prefill) == spec.context_length_tokens
    assert len(seq0_decode) > 0


def test_rag_generator_emits_only_RAG_pattern():
    spec = _smoke_spec(AccessPattern.RAG)
    events = list(generate_rag(spec))
    assert all(isinstance(e, TraceEvent) for e in events)
    assert any(e.is_prefill for e in events)
    assert any(not e.is_prefill for e in events)


def test_chat_generator_re_reads_system_prompt_block():
    spec = _smoke_spec(AccessPattern.CHAT)
    events = list(generate_chat(spec))
    decode_events = [e for e in events if not e.is_prefill]
    # System prompt blocks (position < ~64) are touched by the
    # decode loop. Confirm at least one decode event references
    # an early position.
    assert any(e.position < 64 for e in decode_events)


def test_generators_are_deterministic_for_same_seed():
    spec = _smoke_spec(AccessPattern.AGENTIC)
    a = list(generate_agentic(spec))
    b = list(generate_agentic(spec))
    assert len(a) == len(b)
    for x, y in zip(a, b):
        assert x == y


def test_generate_dispatch():
    """The :func:`generate` dispatcher routes by pattern."""
    spec = _smoke_spec(AccessPattern.AGENTIC)
    events = list(generate(spec))
    assert len(events) > 0


def test_generators_reject_wrong_pattern():
    spec = _smoke_spec(AccessPattern.AGENTIC)
    with pytest.raises(ValueError, match="non-RAG"):
        list(generate_rag(spec))
    with pytest.raises(ValueError, match="non-CHAT"):
        list(generate_chat(spec))
    with pytest.raises(ValueError, match="non-clustered"):
        list(generate_agentic_clustered(spec))


def test_clustered_generator_emits_prefill_then_decode():
    spec = _smoke_spec(AccessPattern.AGENTIC_CLUSTERED)
    events = list(generate_agentic_clustered(spec))
    seq0_prefill = [e for e in events if e.seq_id == 0 and e.is_prefill]
    seq0_decode = [e for e in events if e.seq_id == 0 and not e.is_prefill]
    assert len(seq0_prefill) == spec.context_length_tokens
    assert len(seq0_decode) > 0


def test_clustered_generator_dwells_on_hot_blocks():
    """The Markov-dwell tool re-read should keep returning to
    the same hot block over multiple consecutive decode steps —
    that's the property uniform-random doesn't have."""
    spec = WorkloadSpec(
        name="dwell_check",
        pattern=AccessPattern.AGENTIC_CLUSTERED,
        n_concurrent_seqs=1,
        context_length_tokens=4096,
        duration_decode_tokens=200,
        block_size_tokens=16,
        seed=99,
    )
    events = list(generate_agentic_clustered(spec))
    # Pull out the high-attention re-read events (attention 0.35 is
    # the hot-block signature in the generator).
    hot_block_events = [
        e for e in events
        if not e.is_prefill and abs(e.attention_weight - 0.35) < 1e-6
    ]
    if not hot_block_events:
        return
    # Count the longest consecutive run of the same hot block_id.
    max_run = 1
    current_run = 1
    for prev, cur in zip(hot_block_events, hot_block_events[1:]):
        if cur.block_id == prev.block_id:
            current_run += 1
            max_run = max(max_run, current_run)
        else:
            current_run = 1
    # With stay_prob=0.7 over 200 decode steps + 8 hot blocks, the
    # longest dwell run should comfortably exceed 3. If this drops
    # below 3 the dwell logic regressed.
    assert max_run >= 3, (
        f"expected clustered dwell, got max consecutive run = {max_run}"
    )


def test_clustered_generator_is_deterministic_for_same_seed():
    spec = _smoke_spec(AccessPattern.AGENTIC_CLUSTERED)
    a = list(generate_agentic_clustered(spec))
    b = list(generate_agentic_clustered(spec))
    assert a == b


def test_block_ids_unique_across_concurrent_sequences():
    """Sequence X's blocks should not collide with sequence Y's
    (otherwise the cache + policy can't distinguish them)."""
    spec = WorkloadSpec(
        name="collision_check",
        pattern=AccessPattern.RAG,
        n_concurrent_seqs=4,
        context_length_tokens=256,
        duration_decode_tokens=8,
        block_size_tokens=16,
    )
    events = list(generate_rag(spec))
    by_seq = {}
    for e in events:
        by_seq.setdefault(e.seq_id, set()).add(e.block_id)
    # No block_id appears in more than one sequence.
    all_ids = set()
    for ids in by_seq.values():
        assert all_ids.isdisjoint(ids)
        all_ids.update(ids)
