"""Tests for the workload generators."""

from __future__ import annotations

import pytest

from ctm_bench.workload import (
    AccessPattern,
    AGENTIC_64K,
    CHAT_32K,
    RAG_128K,
    TraceEvent,
    WorkloadSpec,
    generate,
    generate_agentic,
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
    """The three reference workloads exist + carry the expected
    pattern. Pinned so the CLI default remains stable."""
    assert AGENTIC_64K.pattern is AccessPattern.AGENTIC
    assert AGENTIC_64K.context_length_tokens == 64 * 1024
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
