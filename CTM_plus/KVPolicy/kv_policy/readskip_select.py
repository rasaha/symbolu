"""Read-skip block selection + position mapping (PURE, CPU-testable).

The host-side logic for the read-skip / sparse-decode kernel (see
CTM_plus/Bench/scripts/PHASE9_READSKIP_KERNEL_BUILD_PLAN.md). Kept dependency-free
(no torch) so it is unit-testable on a CPU box and shared by BOTH:
  * the quality harness (phase9_decode_retention_harness.py), and
  * the cache's kernel_inputs(active_blocks=...) gather (the kernel build).

Validated by the Phase-9 retention experiment: keeping sink + recent +
decode-attention top blocks (+neighbors) preserves needle/MMLU quality (GREEN).

Block model: KV position p belongs to block p // block_size. "Retained" blocks
are the ones the decode reads; the rest stay STORED in int4 but are not read.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Set


def n_blocks(seq_len: int, block_size: int) -> int:
    return (max(0, int(seq_len)) + block_size - 1) // block_size


def sink_block_set(sink_tokens: int, block_size: int) -> Set[int]:
    """Blocks covering the first `sink_tokens` positions (attention sinks)."""
    return set(range((max(0, sink_tokens) + block_size - 1) // block_size))


def recent_block_set(seq_len: int, recent_tokens: int, block_size: int) -> Set[int]:
    """Blocks covering the last `recent_tokens` positions of a length-`seq_len`
    sequence (the recent window — always read)."""
    if seq_len <= 0:
        return set()
    start = max(0, seq_len - max(0, recent_tokens))
    return set(range(start // block_size, (seq_len - 1) // block_size + 1))


def select_retained_blocks(nb: int, block_score: Sequence[float],
                           sink_blocks: Set[int], recent_blocks: Set[int],
                           budget_blocks: int, neighbor: int = 0) -> Set[int]:
    """Choose the retained block set. pinned = sink ∪ recent; from the rest take
    the top `budget_blocks` by decode-attention score; expand by ±`neighbor`.

    This is the policy the Phase-9 harness validated GREEN.
    """
    pinned = set(sink_blocks) | set(recent_blocks)
    candidates = [b for b in range(nb) if b not in pinned]
    candidates.sort(key=lambda b: block_score[b], reverse=True)
    chosen = set(candidates[:max(0, budget_blocks)])
    retained = set(pinned) | chosen
    for b in list(chosen):
        for x in range(b - neighbor, b + neighbor + 1):
            if 0 <= x < nb:
                retained.add(x)
    return retained


def blocks_to_positions(retained_blocks: Set[int], block_size: int,
                        seq_len: int) -> List[int]:
    """Expand a retained-block set into the SORTED list of KV token positions to
    gather (0 <= p < seq_len). This is the index the cache uses to compact its
    per-position buffers before handing them to the fused kernel.

    INVARIANT (the P1 byte-eq foundation): if `retained_blocks` covers every
    block, the result is exactly range(seq_len) — i.e. read-skip with everything
    retained is identical to reading the full sequence.
    """
    positions: List[int] = []
    for b in sorted(retained_blocks):
        lo = b * block_size
        hi = min((b + 1) * block_size, seq_len)
        if lo < seq_len:
            positions.extend(range(lo, hi))
    return positions


def retained_positions_for_policy(
        policy: str, seq_len: int, block_size: int, sink_tokens: int,
        recent_tokens: int, budget_blocks: int, neighbor: int,
        block_score: Optional[Sequence[float]] = None) -> List[int]:
    """Convenience: full policy → sorted retained positions. `policy` in
    {full, recent_only, sink_recent, retention}. `block_score` required for
    'retention'."""
    nb = n_blocks(seq_len, block_size)
    sinks = sink_block_set(sink_tokens, block_size)
    recents = recent_block_set(seq_len, recent_tokens, block_size)
    if policy == "full":
        retained = set(range(nb))
    elif policy == "recent_only":
        retained = set(recents) | {0}
    elif policy == "sink_recent":
        retained = set(sinks) | set(recents)
    elif policy == "retention":
        if block_score is None:
            raise ValueError("retention policy requires block_score")
        retained = select_retained_blocks(nb, block_score, sinks, recents,
                                          budget_blocks, neighbor)
    else:
        raise ValueError(f"unknown policy {policy!r}")
    return blocks_to_positions(retained, block_size, seq_len)


def needle_retained(needle_block_ids: Sequence[int], retained: Set[int]) -> bool:
    return all(b in retained for b in needle_block_ids)


# --------------------------------------------------------------- self-test ----

def _selftest() -> int:
    bs = 32
    # 1. IDENTITY (the P1 byte-eq foundation): retain all blocks -> positions
    #    == range(seq_len), for seq lengths that are and aren't block-aligned.
    for S in (32, 100, 256, 257, 8192):
        nb = n_blocks(S, bs)
        allpos = blocks_to_positions(set(range(nb)), bs, S)
        assert allpos == list(range(S)), (S, allpos[:5], allpos[-5:])
    # 2. sink/recent block math.
    assert sink_block_set(256, 32) == set(range(8))
    rb = recent_block_set(8192, 2048, 32)
    assert min(rb) == (8192 - 2048) // 32 and max(rb) == 8191 // 32
    # 3. selection keeps the high-attention MIDDLE block + neighbors + pinned
    #    (the exact v1-failure-mode this whole line of work fixed).
    nb = 64
    score = [0.0] * nb
    score[30] = 9.0
    ret = select_retained_blocks(nb, score, {0, 1}, {62, 63}, budget_blocks=2,
                                 neighbor=1)
    assert 30 in ret and {29, 31} <= ret and {0, 1, 62, 63} <= ret, ret
    # 4. positions are sorted, unique, in-range, and a strict subset under skip.
    pos = blocks_to_positions(ret, bs, nb * bs)
    assert pos == sorted(set(pos)) and all(0 <= p < nb * bs for p in pos)
    assert len(pos) < nb * bs, "retention must drop something here"
    # 5. retention positions include the needle block's positions iff retained.
    assert needle_retained([30], ret) and not needle_retained([45], ret)
    # 6. policy router: recent_only at long ctx keeps BOS but drops an early-mid block.
    rp = set(retained_positions_for_policy("recent_only", 8192, bs, 256, 2048, 64, 1))
    assert 0 in rp, "recent_only keeps BOS (block 0)"
    assert 4000 not in rp, "early-middle position must be skipped by recent_only"
    # 7. retention router keeps a scored middle block's positions.
    sc = [0.0] * n_blocks(8192, bs)
    sc[125] = 5.0     # ~position 4000 region
    rp2 = set(retained_positions_for_policy("retention", 8192, bs, 256, 2048, 64, 1,
                                            block_score=sc))
    assert 125 * bs in rp2, "retention must keep the high-score middle block"
    print("readskip_select self-test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
