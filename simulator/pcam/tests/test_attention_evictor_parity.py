"""
End-to-end KVCachePolicy parity tests — PCAM vs CTM+ reference.

This suite validates that the PCAM simulator's attention-aware eviction
policy produces identical victim sets to the canonical implementation at

    CTM_plus/KVPolicy/kv_policy/attention_evictor.py

per ADR-0001 (docs/design/ADR-0001-CTM-KV-SCORING-SOURCE-OF-TRUTH.md).

Scope
-----
Full pipeline parity: admission → attention → phase → scoring → victim
selection. Sketch-level parity is tested separately in
test_sketch_conformance.py. A failure here means the scoring weights, the
sink-pinning logic, the filler fast path, the entity bonus, or the
sampled-path RNG contract has diverged.

PCAM side contract (API expected of the port)
----------------------------------------------
The PCAM alignment PR must expose an equivalent policy at
`simulator.pcam.kv_policy.KVCachePolicy` with the following duck-type
surface:

    KVCachePolicy(max_blocks, block_size, sink_tokens,
                  recent_window, entity_attention_threshold,
                  attention_ema_alpha)
    .register_sequence(seq_id: int) -> None
    .set_phase(seq_id: int, phase: InferencePhase) -> None
    .set_rng(rng: random.Random) -> None
    .ensure_block(block_id: int, sequence_id: int, positions: list[int]) -> None
    .on_block_attention(block_id, attention_sum, sequence_id, seq_len=0) -> None
    .select_victims(count: int) -> list[int]
    .gpu_blocks: set[int]
    .pinned_blocks: set[int]

If the PCAM implementation wraps an existing class (e.g. inside
CXLEdgePool) rather than providing a standalone KVCachePolicy, ship a
thin adapter at `simulator.pcam.kv_policy` that presents this API. The
tests don't care about internal structure — they care about observable
behavior.

RNG contract
------------
Both sides receive the SAME seed via fresh random.Random(seed) instances.
Non-determinism in victim selection must come ONLY from rng.sample() and
sorted() tie-breaks. Anything else is a parity violation.
"""

from __future__ import annotations

import random
from typing import Any, Dict, Iterable, List, Tuple

import pytest

# ---------------------------------------------------------------------------
# Reference import — vendored, not sys.path-hacked (see
# test_sketch_conformance.py for rationale). The vendored file at
# simulator/pcam/reference/attention_evictor_vendored.py is the
# Phase 0 in-tree oracle per ADR-0001.
# ---------------------------------------------------------------------------
from simulator.pcam.reference.attention_evictor_vendored import (
    InferencePhase,
    KVCachePolicy as RefKVCachePolicy,
)


# ---------------------------------------------------------------------------
# PCAM-side import with graceful skip.
# ---------------------------------------------------------------------------
_PCAM_SKIP_REASON = (
    "PCAM-side KVCachePolicy not found at simulator.pcam.kv_policy. "
    "This module is introduced by the PCAM alignment PR described in "
    "simulator/pcam/docs/PCAM_UPDATE_PR_SCOPE.md. The test suite will "
    "auto-activate once that module exposes a KVCachePolicy class (or an "
    "adapter matching the duck-type surface documented at the top of this file)."
)


def _load_pcam_policy_class():
    try:
        from simulator.pcam.kv_policy import KVCachePolicy as PCAMKVCachePolicy  # type: ignore
    except ImportError:
        pytest.skip(_PCAM_SKIP_REASON, allow_module_level=False)
    return PCAMKVCachePolicy


# ---------------------------------------------------------------------------
# Paired policy builder.
# ---------------------------------------------------------------------------


def _paired_policies(
    *,
    max_blocks: int = 128,
    block_size: int = 16,
    sink_tokens: int = 4,
    recent_window: int = 256,
    entity_attention_threshold: float = 0.02,
    attention_ema_alpha: float = 0.1,
    seed: int = 42,
) -> Tuple[RefKVCachePolicy, Any]:
    """Construct a reference and PCAM policy with identical parameters and seeds."""
    pcam_cls = _load_pcam_policy_class()
    kwargs = dict(
        max_blocks=max_blocks,
        block_size=block_size,
        sink_tokens=sink_tokens,
        recent_window=recent_window,
        entity_attention_threshold=entity_attention_threshold,
        attention_ema_alpha=attention_ema_alpha,
    )
    ref = RefKVCachePolicy(**kwargs)
    pcam = pcam_cls(**kwargs)
    # Both sides get independent RNGs seeded identically.
    ref.set_rng(random.Random(seed))
    pcam.set_rng(random.Random(seed))
    return ref, pcam


# ---------------------------------------------------------------------------
# Trace helpers.
# ---------------------------------------------------------------------------

Admission = Tuple[int, int, List[int]]          # (block_id, seq_id, positions)
Attention = Tuple[int, float, int]               # (block_id, attention_sum, seq_id)


def _apply_trace(
    policies: Iterable[Any],
    *,
    sequences: List[int],
    phase: InferencePhase,
    admissions: List[Admission],
    attention_events: List[Attention],
) -> None:
    """Replay an identical trace against every policy in `policies`."""
    for p in policies:
        for sid in sequences:
            p.register_sequence(sid)
            p.set_phase(sid, phase)
        for block_id, seq_id, positions in admissions:
            p.ensure_block(block_id, seq_id, positions)
        for block_id, attn, seq_id in attention_events:
            p.on_block_attention(block_id, attn, seq_id)


def _assert_victim_parity(
    ref: RefKVCachePolicy,
    pcam: Any,
    count: int,
    *,
    ordered: bool = True,
    context: str = "",
) -> List[int]:
    """
    Call select_victims on both sides and assert equality.

    `ordered=True` requires the returned list to match element-by-element.
    `ordered=False` compares as sets (useful when tie-breaks are expected).
    Returns the reference victim list for downstream assertions.
    """
    ref_victims = ref.select_victims(count)
    pcam_victims = pcam.select_victims(count)

    if ordered:
        assert ref_victims == pcam_victims, (
            f"[{context}] ordered victim divergence\n"
            f"  reference: {ref_victims}\n"
            f"  pcam:      {pcam_victims}"
        )
    else:
        assert set(ref_victims) == set(pcam_victims), (
            f"[{context}] unordered victim divergence\n"
            f"  reference: {sorted(ref_victims)}\n"
            f"  pcam:      {sorted(pcam_victims)}"
        )
    return ref_victims


# ===========================================================================
# Sink pinning — the hardest safety invariant.
# ===========================================================================


class TestSinkPinning:
    def test_sink_blocks_never_evicted(self):
        """
        Blocks admitted at positions < sink_tokens are pinned. They must
        never appear in any victim set, even under heavy pressure.
        """
        ref, pcam = _paired_policies(max_blocks=64)
        _apply_trace(
            [ref, pcam],
            sequences=[1],
            phase=InferencePhase.DECODE,
            admissions=[
                (0, 1, [0, 1, 2, 3]),     # sink block
                (1, 1, [4, 5, 6, 7]),
                (2, 1, [8, 9, 10, 11]),
                (3, 1, [12, 13, 14, 15]),
            ],
            attention_events=[
                (0, 0.45, 1),
                (1, 0.01, 1),
                (2, 0.01, 1),
                (3, 0.01, 1),
            ],
        )
        # Confirm the sink was actually pinned on both sides (sanity).
        assert 0 in ref.pinned_blocks
        assert 0 in pcam.pinned_blocks

        victims = _assert_victim_parity(
            ref, pcam, count=2, context="sink-pinning",
        )
        assert 0 not in victims, "sink block 0 must never be a victim"


# ===========================================================================
# Filler fast path — deterministic by construction.
# ===========================================================================


class TestFillerFastPath:
    def test_all_filler_fast_path_order(self):
        """
        When enough all-filler blocks exist to satisfy the request, the fast
        path runs: fillers sorted by freq_sketch.estimate() ascending.

        This path is NOT sampled — it's deterministic — so the ordered
        comparison must pass.
        """
        ref, pcam = _paired_policies(max_blocks=128, sink_tokens=0)

        # 16 admissions, all non-sink, all receiving very low attention.
        admissions: List[Admission] = [
            (bid, 1, [100 + bid]) for bid in range(10, 26)
        ]
        attention_events: List[Attention] = [
            (bid, 0.005, 1) for bid in range(10, 26)
        ]
        _apply_trace(
            [ref, pcam],
            sequences=[1],
            phase=InferencePhase.DECODE,
            admissions=admissions,
            attention_events=attention_events,
        )

        _assert_victim_parity(
            ref, pcam, count=4, context="filler-fast-path", ordered=True,
        )


# ===========================================================================
# Entity bonus — high-attention blocks survive.
# ===========================================================================


class TestEntityBonus:
    def test_entity_blocks_survive_under_pressure(self):
        """
        Three strong-attention blocks must NOT appear in a victim set that's
        smaller than the pool of filler blocks.
        """
        ref, pcam = _paired_policies(max_blocks=64, sink_tokens=0)

        # 32 non-sink blocks.
        admissions: List[Admission] = [
            (bid, 1, [200 + bid]) for bid in range(32)
        ]
        # Blocks 0-2 get massive attention (20 high-attention events).
        attention_events: List[Attention] = []
        for _ in range(20):
            for bid in (0, 1, 2):
                attention_events.append((bid, 0.50, 1))
        # Blocks 3-10 each get one small attention event (filler).
        for bid in range(3, 11):
            attention_events.append((bid, 0.002, 1))

        _apply_trace(
            [ref, pcam],
            sequences=[1],
            phase=InferencePhase.DECODE,
            admissions=admissions,
            attention_events=attention_events,
        )

        victims = _assert_victim_parity(
            ref, pcam, count=3, context="entity-bonus", ordered=True,
        )
        for entity_id in (0, 1, 2):
            assert entity_id not in victims, (
                f"entity block {entity_id} was evicted — entity bonus not applied"
            )


# ===========================================================================
# Phase-aware scoring — same trace, different phase, different result.
# ===========================================================================


class TestPhaseAwareScoring:
    def test_prefill_and_decode_both_match_reference(self):
        """
        For both PREFILL and DECODE, PCAM must match the reference exactly.
        We don't assert that PREFILL != DECODE (that's reference behavior,
        not our contract). We assert parity inside each phase.
        """
        for phase in (InferencePhase.PREFILL, InferencePhase.DECODE):
            ref, pcam = _paired_policies(max_blocks=64, sink_tokens=0, seed=7)

            admissions: List[Admission] = [
                (bid, 1, [300 + bid]) for bid in range(16)
            ]
            # Graded attention: block 0 highest, block 15 lowest.
            attention_events: List[Attention] = [
                (bid, max(0.0, 0.30 - 0.02 * bid), 1) for bid in range(16)
            ]

            _apply_trace(
                [ref, pcam],
                sequences=[1],
                phase=phase,
                admissions=admissions,
                attention_events=attention_events,
            )

            _assert_victim_parity(
                ref, pcam, count=4,
                context=f"phase={phase.name}", ordered=True,
            )


# ===========================================================================
# Sampled-path RNG contract — the parity test with the highest drift risk.
# ===========================================================================


class TestSampledPathDeterminism:
    def test_sampled_path_parity_across_many_rounds(self):
        """
        When the filler set is smaller than the request, select_victims()
        falls through to the sampled path: random.sample of up to 48
        candidates, score them, return the lowest-scoring.

        This is the codepath most likely to drift. Both sides must consume
        the RNG in the same order to produce the same sample.

        We run 10 eviction rounds on a mixed trace and require bit-identical
        victim lists across all of them.
        """
        ref, pcam = _paired_policies(
            max_blocks=256, sink_tokens=4, seed=0xC0FFEE,
        )

        # 200 admissions: mix of sinks, fillers, and entities.
        admissions: List[Admission] = []
        attention_events: List[Attention] = []
        for bid in range(200):
            if bid < 4:
                positions = [bid]  # sink
                attn = 0.1
            elif bid % 7 == 0:
                positions = [400 + bid]  # entity
                attn = 0.4
            else:
                positions = [400 + bid]  # filler
                attn = 0.003
            admissions.append((bid, 1, positions))
            attention_events.append((bid, attn, 1))

        _apply_trace(
            [ref, pcam],
            sequences=[1],
            phase=InferencePhase.DECODE,
            admissions=admissions,
            attention_events=attention_events,
        )

        # 10 rounds of eviction, 8 blocks each. Every round must match.
        for round_idx in range(10):
            _assert_victim_parity(
                ref, pcam, count=8,
                context=f"sampled-round-{round_idx}", ordered=True,
            )


# ===========================================================================
# Long randomized differential — the safety net.
# ===========================================================================


class TestRandomizedEndToEnd:
    def test_randomized_500_ops_parity(self):
        """
        Drive a pseudo-random stream of admissions, attention events, and
        eviction calls through both sides. Assert victim parity on every
        eviction.

        This catches subtle divergence (off-by-one in threshold, wrong sort
        stability, different handling of empty gpu_blocks, etc.) that the
        targeted tests above might miss.
        """
        ref, pcam = _paired_policies(max_blocks=512, seed=0xBEEFCAFE)
        _apply_trace([ref, pcam], sequences=[1], phase=InferencePhase.DECODE,
                     admissions=[], attention_events=[])

        rng = random.Random(0xDECADE)  # trace RNG, separate from policy RNG
        next_block_id = 100
        eviction_round = 0

        for step in range(500):
            op = rng.choices(
                ["admit", "attention", "evict"],
                weights=[3, 5, 1],
            )[0]
            if op == "admit":
                bid = next_block_id
                next_block_id += 1
                positions = [bid * 16]
                for p in (ref, pcam):
                    p.ensure_block(bid, 1, positions)
            elif op == "attention":
                if next_block_id == 100:
                    continue  # nothing admitted yet
                bid = rng.randint(100, next_block_id - 1)
                attn = rng.uniform(0.0, 0.5)
                for p in (ref, pcam):
                    p.on_block_attention(bid, attn, 1)
            else:  # evict
                if len(ref.gpu_blocks) < 8:
                    continue
                count = rng.randint(1, 4)
                _assert_victim_parity(
                    ref, pcam, count=count,
                    context=f"randomized-step={step}-round={eviction_round}",
                    ordered=True,
                )
                eviction_round += 1

        assert eviction_round > 0, "test must exercise at least one eviction"
