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


class ReadSkipController:
    """Per-sequence (per-layer) read-skip decision state machine — the 'brain'
    of retention, kept PURE (scores are passed in, computed elsewhere) so it is
    CPU-unit-testable. Mirrors the observe→retain→refresh loop the Phase-9
    harness validated GREEN.

    Lifecycle per decode step:
      1. caller checks `needs_scores()`; if True it computes per-block
         decode-attention mass for the current step and passes it in.
      2. `active_positions(seq_len, block_scores)` returns the sorted KV
         positions to READ this step (or the full range during the observe
         window / before the first selection).

    Observe window (first `observe_steps`) and every `refresh_every` steps: read
    EVERYTHING and accumulate EMA scores; otherwise read only the retained set.
    """

    def __init__(self, block_size: int, sink_tokens: int, recent_tokens: int,
                 attention_budget_tokens: int, neighbor_blocks: int = 1,
                 observe_steps: int = 8, refresh_every: int = 16,
                 score_decay: float = 0.8) -> None:
        self.block_size = block_size
        self.sink_tokens = sink_tokens
        self.recent_tokens = recent_tokens
        self.budget_blocks = attention_budget_tokens // block_size
        self.neighbor_blocks = neighbor_blocks
        self.observe_steps = observe_steps
        self.refresh_every = refresh_every
        self.score_decay = score_decay
        self._step = 0
        self._ema: Dict[int, float] = {}
        self._retained: Optional[Set[int]] = None
        self._cached_blocks = None    # Step 4: GPU block-id tensor, rebuilt on observe

    def _is_observe_step(self) -> bool:
        return (self._step < self.observe_steps
                or (self.refresh_every > 0
                    and self._step % self.refresh_every == 0))

    def needs_scores(self) -> bool:
        """Whether the UPCOMING active_positions call should be given
        block_scores (observe / refresh step)."""
        return self._is_observe_step()

    def _update_ema(self, block_scores: Sequence[float]) -> None:
        d = self.score_decay
        for b, s in enumerate(block_scores):
            self._ema[b] = d * self._ema.get(b, 0.0) + (1 - d) * float(s)

    def active_positions(self, seq_len: int,
                         block_scores: Optional[Sequence[float]] = None) -> List[int]:
        read_all = self._step_and_select(seq_len, block_scores)
        # Read everything during the observe window or before any selection.
        if read_all:
            return list(range(seq_len))
        return blocks_to_positions(self._retained, self.block_size, seq_len)

    def _step_and_select(self, seq_len: int,
                         block_scores: Optional[Sequence[float]] = None) -> bool:
        """Advance the observe/steady cadence and (on observe) re-select the
        retained block set from the EMA scores. Returns True if this step must
        read ALL positions (observe window, or before any selection exists).
        Shared by active_positions (Python list) and active_index (GPU tensor)."""
        nb = n_blocks(seq_len, self.block_size)
        observe = self._is_observe_step()
        if observe and block_scores is not None:
            self._update_ema(block_scores)
            score_list = [self._ema.get(b, 0.0) for b in range(nb)]
            self._retained = select_retained_blocks(
                nb, score_list, sink_block_set(self.sink_tokens, self.block_size),
                recent_block_set(seq_len, self.recent_tokens, self.block_size),
                self.budget_blocks, self.neighbor_blocks)
        self._step += 1
        if observe:
            self._cached_blocks = None    # retained set may have changed -> rebuild
        return observe or self._retained is None

    def active_index(self, seq_len: int, device,
                     block_scores: Optional[Sequence[float]] = None):
        """READ-SKIP Step 3+4: the retained positions as a GPU int32 tensor, built
        on-device from the SMALL retained-block set — NOT a Python list. Avoids the
        per-layer-per-step ``torch.as_tensor(list_of_thousands)`` that the profile
        showed dominates ``kernel_inputs``.

        Step 4: cache the BLOCK-ID tensor (``torch.tensor(sorted(retained))`` — the
        expensive Python->GPU transfer), rebuilt only on observe steps since
        ``self._retained`` is constant across steady steps. The cheap expansion +
        ``< seq_len`` filter still runs every step, so the highest block correctly
        picks up new tokens as ``seq_len`` grows — i.e. EXACTLY ``active_positions``
        / ``blocks_to_positions``, no staleness. Same cadence/EMA effects."""
        import torch
        read_all = self._step_and_select(seq_len, block_scores)
        if read_all:
            return torch.arange(seq_len, device=device, dtype=torch.int32)
        if self._cached_blocks is None:
            self._cached_blocks = torch.tensor(
                sorted(self._retained), device=device, dtype=torch.int64)
        bs = self.block_size
        pos = (self._cached_blocks[:, None] * bs
               + torch.arange(bs, device=device, dtype=torch.int64)[None, :]).reshape(-1)
        return pos[pos < seq_len].to(torch.int32)

    @property
    def retained_blocks(self) -> Optional[Set[int]]:
        return set(self._retained) if self._retained is not None else None


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

    # 8. ReadSkipController: observe window reads ALL; after observing a
    #    high-attention middle block it RETAINS it (and drops a cold one).
    S = 40 * bs                       # 40 blocks
    ctrl = ReadSkipController(block_size=bs, sink_tokens=2 * bs,
                              recent_tokens=2 * bs, attention_budget_tokens=4 * bs,
                              neighbor_blocks=1, observe_steps=3, refresh_every=0,
                              score_decay=0.5)
    hot = 20                          # a cold-middle block that gets attention
    scores = [0.0] * n_blocks(S, bs)
    scores[hot] = 10.0
    # observe steps: needs_scores True, reads everything.
    for _ in range(3):
        assert ctrl.needs_scores()
        ap = ctrl.active_positions(S, block_scores=scores)
        assert ap == list(range(S)), "observe window must read all"
    # post-observe: no longer needs scores; retains the hot block, drops a far cold one.
    assert not ctrl.needs_scores()
    ap = ctrl.active_positions(S)
    assert len(ap) < S, "retention must skip something"
    assert hot * bs in ap, "the observed high-attention block must be retained"
    assert 10 * bs not in ap, "a cold un-attended middle block must be skipped"

    # 9. Step 3 index expansion: the on-GPU expansion (full block via broadcast,
    #    then filter < seq_len) must yield EXACTLY blocks_to_positions. Mimic it in
    #    pure Python (no torch) so the equivalence is CPU-proven; the kernel/cache
    #    GPU gate then only has to confirm the torch port.
    def _gpu_expand_mimic(blocks, block_size, seq_len):
        flat = []
        for b in sorted(blocks):
            flat.extend(range(b * block_size, b * block_size + block_size))  # full block
        return [p for p in flat if p < seq_len]                              # then filter
    for (blocks, S2) in [({0, 1, 30, 31, 62, 63}, 64 * bs), ({0, 5, 9}, 300),
                         (set(range(40)), 40 * bs), ({0, 9}, 257), ({3}, 100)]:
        assert _gpu_expand_mimic(blocks, bs, S2) == blocks_to_positions(blocks, bs, S2), \
            (sorted(blocks), S2)

    print("readskip_select self-test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(_selftest())
