"""Cache-aware admission scheduler — v2 cache-reuse layer (Phase 0 CPU prototype).

This module implements the prefix-tree + admission-ordering layer
described in `Bench/scripts/V2_CACHE_REUSE_DESIGN.md`. It is the
v2 production-hardening complement to `int4_protected`:

* int4_protected (v1, shipped) optimizes bytes-per-block.
* this module (v2, design + CPU prototype) optimizes block reuse
  across requests by admitting requests with high predicted
  prefix-cache hit rate first.

Phase 0 scope (this file):

* ``PrefixRadixTree`` — token-sequence to block-id index, LRU
  pruning with pin support.
* ``CacheHitPredictor`` — block-aligned hit-length prediction.
* ``CacheAwareScheduler`` — admission ordering with fairness guard.
* Pure-Python, no torch / no vllm — runs in any environment.

Not in scope here:

* vLLM ``AsyncLLMEngine`` integration (Phase 1)
* Streaming-runner telemetry plumbing (Phase 2)
* GPU validation (Phase 3)
* System-prompt pinning CLI (Phase 4)

Each of those is gated on this module passing the
``Bench/tests/test_cache_aware_scheduler.py`` CPU regression suite.

Honest scope discipline (per ``PHASE8_RETIREMENT.md``): this
module does NOT introduce a new eviction-scoring algorithm. It
reorders the admission queue using vLLM's existing block-level
LRU + prefix caching as the substrate. The pattern is SGLang's
RadixAttention scheduling, adapted to vLLM 0.7.3 + INT4 protected's
``block_size=32``.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple


# ----------------------------------------------------------------------
# PrefixRadixTree
# ----------------------------------------------------------------------


@dataclass
class _RadixNode:
    """One node in the radix tree.

    Each node represents a contiguous run of tokens (``segment``) that
    extends its parent. The root has an empty segment. A node holds
    the set of ``block_id``s that store this prefix's tokens in vLLM's
    KV cache, plus the LRU + pin bookkeeping.
    """
    segment: Tuple[int, ...]
    children: Dict[int, "_RadixNode"] = field(default_factory=dict)
    block_ids: Set[int] = field(default_factory=set)
    last_access: float = field(default_factory=time.monotonic)
    pinned: bool = False
    total_tokens: int = 0  # cached cumulative tokens from root to this node


class PrefixRadixTree:
    """Token-sequence prefix index.

    Maps cached prefixes to ``block_id`` sets. Insertions and queries
    are O(L) in token-sequence length. The tree supports LRU pruning
    (bounded by ``max_tokens``) and pinning (system prompts that
    must never be evicted from the index).

    Thread-safety: not thread-safe. Callers must serialize externally
    or wrap in a lock. Phase 1 will run this on the scheduler thread
    and call from vLLM's event callbacks; that thread is single per
    engine instance so no internal lock is needed.
    """

    def __init__(self, max_tokens: int = 1_000_000):
        if max_tokens <= 0:
            raise ValueError(
                f"max_tokens must be > 0, got {max_tokens}"
            )
        self._root = _RadixNode(segment=())
        self._max_tokens = max_tokens
        self._tracked_tokens = 0
        self._inserts = 0
        self._evictions = 0
        self._prunes = 0

    # ---- mutators ----

    def insert(
        self,
        tokens: Sequence[int],
        block_ids: Iterable[int],
        *,
        pinned: bool = False,
    ) -> None:
        """Register that ``tokens`` are cached at ``block_ids``.

        Idempotent: re-inserting the same tokens (e.g., from a
        re-observed cache state) merges block_ids and refreshes the
        LRU timestamp. If ``pinned=True``, marks every node along the
        path as pinned (LRU prune will skip them).
        """
        if not tokens:
            return
        self._inserts += 1
        block_set = set(block_ids)
        node = self._root
        i = 0
        n = len(tokens)
        while i < n:
            tok = tokens[i]
            child = node.children.get(tok)
            if child is None:
                # Add a fresh node carrying the rest of the suffix.
                new_seg = tuple(tokens[i:])
                fresh = _RadixNode(
                    segment=new_seg,
                    block_ids=set(block_set),
                    pinned=pinned,
                    total_tokens=node.total_tokens + len(new_seg),
                )
                node.children[tok] = fresh
                self._tracked_tokens += len(new_seg)
                node = fresh
                i = n
                break
            # Walk into the child; child.segment[0] == tok by construction.
            seg = child.segment
            j = 0
            while (
                j < len(seg)
                and i + j < n
                and seg[j] == tokens[i + j]
            ):
                j += 1
            if j == len(seg):
                # Entire child segment matched; descend.
                node = child
                i += j
                continue
            # Partial match: split the child at position j.
            split = _RadixNode(
                segment=seg[j:],
                children=child.children,
                block_ids=child.block_ids,
                last_access=child.last_access,
                pinned=child.pinned,
                total_tokens=child.total_tokens,
            )
            child.children = {seg[j]: split}
            child.segment = seg[:j]
            # Parent retains the block_ids: the original node represented
            # "this full path is cached at these blocks". After the split,
            # the prefix (parent) AND the suffix (split node) are both
            # still cached — same physical blocks back them. Empty
            # parent would make partial-prefix queries return 0 even
            # when the prefix is materially cached (the multi-request
            # prefix-sharing case the v2 layer exists to optimize).
            child.block_ids = set(split.block_ids)
            child.pinned = child.pinned  # parent of split inherits pin
            child.total_tokens = node.total_tokens + j
            node = child
            i += j
        node.block_ids |= block_set
        node.last_access = time.monotonic()
        if pinned:
            self._propagate_pin(tokens)
        # Bounded growth: prune if we exceed the budget.
        if self._tracked_tokens > self._max_tokens:
            self._prune_lru(target=int(self._max_tokens * 0.8))

    def evict(self, block_ids: Iterable[int]) -> None:
        """Drop the given block_ids from any node holding them.

        Nodes whose block_ids become empty are pruned from the tree
        (the prefix is no longer cached anywhere). Pinned nodes are
        kept even if their block_ids become empty — the pin records
        intent to re-cache rather than a current cache state.
        """
        block_set = set(block_ids)
        if not block_set:
            return
        self._evictions += len(block_set)
        # Walk the tree depth-first and drop empty nodes.
        self._evict_recursive(self._root, block_set)

    def pin(self, tokens: Sequence[int]) -> None:
        """Mark the prefix ``tokens`` as pinned (LRU-immune).

        Pin walks the existing path and sets ``pinned=True`` on every
        node from root to the deepest reachable node along the
        sequence. If the prefix isn't currently in the tree, this
        records the pin intent for any future insert along that path.
        """
        if not tokens:
            return
        self._propagate_pin(tokens)

    # ---- queries ----

    def query(self, tokens: Sequence[int]) -> int:
        """Return the longest cached-prefix length matching ``tokens``.

        Returns the maximum L such that ``tokens[:L]`` is fully
        represented by a path of cached (non-empty-block-id, or
        pinned) nodes from the root.
        """
        if not tokens:
            return 0
        node = self._root
        matched = 0
        i = 0
        n = len(tokens)
        while i < n:
            tok = tokens[i]
            child = node.children.get(tok)
            if child is None:
                break
            seg = child.segment
            j = 0
            while (
                j < len(seg)
                and i + j < n
                and seg[j] == tokens[i + j]
            ):
                j += 1
            if j < len(seg):
                # Partial segment match: only the matched prefix is
                # cached if the child has block_ids OR is pinned.
                if child.block_ids or child.pinned:
                    matched = i + j
                break
            # Full segment matched.
            i += j
            if child.block_ids or child.pinned:
                matched = i
                node = child
                child.last_access = time.monotonic()
            else:
                # This node has no blocks (was a split point); descend
                # but don't bump matched.
                node = child
        return matched

    def contains_pinned(self, tokens: Sequence[int]) -> bool:
        """True if any prefix along ``tokens`` is pinned."""
        node = self._root
        i = 0
        n = len(tokens)
        while i < n:
            tok = tokens[i]
            child = node.children.get(tok)
            if child is None:
                return False
            seg = child.segment
            j = 0
            while (
                j < len(seg)
                and i + j < n
                and seg[j] == tokens[i + j]
            ):
                j += 1
            if child.pinned and j > 0:
                return True
            if j < len(seg):
                return False
            i += j
            node = child
        return node.pinned

    def stats(self) -> Dict[str, int]:
        return {
            "tracked_tokens": self._tracked_tokens,
            "inserts": self._inserts,
            "evictions": self._evictions,
            "prunes": self._prunes,
            "max_tokens": self._max_tokens,
        }

    # ---- internal ----

    def _propagate_pin(self, tokens: Sequence[int]) -> None:
        node = self._root
        node.pinned = True
        i = 0
        n = len(tokens)
        while i < n:
            tok = tokens[i]
            child = node.children.get(tok)
            if child is None:
                return
            seg = child.segment
            j = 0
            while (
                j < len(seg)
                and i + j < n
                and seg[j] == tokens[i + j]
            ):
                j += 1
            child.pinned = True
            if j < len(seg):
                return
            i += j
            node = child

    def _evict_recursive(
        self, node: _RadixNode, blocks_to_drop: Set[int],
    ) -> bool:
        """Return True if the subtree rooted at ``node`` is now empty
        (and should be detached from its parent)."""
        node.block_ids -= blocks_to_drop
        dead_children = []
        for tok, child in node.children.items():
            if self._evict_recursive(child, blocks_to_drop):
                dead_children.append(tok)
        for tok in dead_children:
            child = node.children.pop(tok)
            self._tracked_tokens -= len(child.segment)
        # Detach iff: no block_ids, no children, and not pinned.
        if not node.block_ids and not node.children and not node.pinned:
            if node is not self._root:
                return True
        return False

    def _prune_lru(self, target: int) -> None:
        """Drop oldest unpinned leaves until ``tracked_tokens <= target``."""
        # Collect (last_access, path-from-root, node) for every leaf
        # that is non-pinned and has block_ids. Sort by last_access
        # ascending; pop oldest until target met.
        self._prunes += 1
        leaves: List[Tuple[float, List[int], _RadixNode, _RadixNode]] = []

        def walk(node: _RadixNode, parent: Optional[_RadixNode]) -> None:
            if not node.children and node is not self._root:
                if not node.pinned and node.block_ids:
                    leaves.append((node.last_access, [], node, parent))
            for child in node.children.values():
                walk(child, node)

        walk(self._root, None)
        leaves.sort(key=lambda t: t[0])
        for _, _, leaf, parent in leaves:
            if self._tracked_tokens <= target:
                break
            self._tracked_tokens -= len(leaf.segment)
            # Remove leaf from its parent.
            if parent is not None:
                # Find the key whose child is leaf.
                for tok, child in list(parent.children.items()):
                    if child is leaf:
                        del parent.children[tok]
                        break


# ----------------------------------------------------------------------
# CacheHitPredictor
# ----------------------------------------------------------------------


class CacheHitPredictor:
    """Block-aligned cache-hit predictor for a vLLM-style block cache.

    vLLM's `PrefixCachingBlockAllocator` caches at block granularity.
    A request whose first 1000 tokens match a cached prefix only hits
    the cache for ``(1000 // block_size) * block_size`` tokens; the
    tail of the partial block is recomputed.

    Predictions are conservative: if the tree shows a 1000-token
    match at block_size=32, the predictor returns 992 (= 31 blocks
    × 32 tokens).
    """

    def __init__(
        self,
        tree: PrefixRadixTree,
        *,
        block_size: int = 32,
    ):
        if block_size <= 0:
            raise ValueError(f"block_size must be > 0, got {block_size}")
        self.tree = tree
        self.block_size = block_size

    def predict_cache_hit(self, request_tokens: Sequence[int]) -> int:
        """Return predicted block-aligned cache-hit length in tokens."""
        matched = self.tree.query(request_tokens)
        return (matched // self.block_size) * self.block_size

    def predict_hit_rate(self, request_tokens: Sequence[int]) -> float:
        """Hit length divided by total prompt length."""
        n = len(request_tokens)
        if n == 0:
            return 0.0
        return self.predict_cache_hit(request_tokens) / n


# ----------------------------------------------------------------------
# CacheAwareScheduler
# ----------------------------------------------------------------------


@dataclass
class PendingRequest:
    """One waiting request from vLLM's admission queue."""
    request_id: str
    tokens: Sequence[int]
    arrival_time: float


@dataclass
class _AdmissionDecision:
    """Per-request scheduling annotation returned by the scheduler."""
    request: PendingRequest
    predicted_hit_tokens: int
    matched_pinned: bool


class CacheAwareScheduler:
    """Reorder a pending request queue by predicted cache-hit rate.

    Phase 0 scope: pure-Python policy. Inputs are an opaque list of
    ``PendingRequest`` values; output is the same set reordered. The
    Phase 1 integration will wrap a vLLM ``AsyncLLMEngine`` so the
    inputs come from vLLM's actual scheduler hooks.
    """

    def __init__(
        self,
        tree: PrefixRadixTree,
        *,
        block_size: int = 32,
        max_starvation_seconds: float = 30.0,
        pinned_priority_bonus: int = 10_000_000,
    ):
        self.tree = tree
        self.predictor = CacheHitPredictor(tree, block_size=block_size)
        self.max_starvation_seconds = max_starvation_seconds
        self.pinned_priority_bonus = pinned_priority_bonus
        self._admissions = 0
        self._reordered = 0
        self._starvation_overrides = 0
        self._predicted_hit_tokens_total = 0

    def order_admissions(
        self,
        pending: Sequence[PendingRequest],
        *,
        now: Optional[float] = None,
    ) -> List[PendingRequest]:
        """Return ``pending`` reordered by admission priority."""
        if not pending:
            return []
        now = now if now is not None else time.monotonic()

        # Score every request once.
        decisions: List[_AdmissionDecision] = []
        for req in pending:
            hit = self.predictor.predict_cache_hit(req.tokens)
            pinned = self.tree.contains_pinned(req.tokens)
            decisions.append(_AdmissionDecision(
                request=req,
                predicted_hit_tokens=hit,
                matched_pinned=pinned,
            ))

        # Starvation guard: any request older than the threshold
        # jumps to the front of the queue. FCFS within the starved
        # set for fairness.
        starved = [
            d for d in decisions
            if (now - d.request.arrival_time) > self.max_starvation_seconds
        ]
        fresh = [d for d in decisions if d not in starved]
        starved.sort(key=lambda d: d.request.arrival_time)
        self._starvation_overrides += len(starved)

        # Within ``fresh``: sort by priority. Pinned-prefix matchers
        # outrank everyone non-pinned; within each group, sort by
        # predicted hit length desc, then by arrival time asc.
        def sort_key(d: _AdmissionDecision):
            priority = d.predicted_hit_tokens + (
                self.pinned_priority_bonus if d.matched_pinned else 0
            )
            return (-priority, d.request.arrival_time)
        fresh.sort(key=sort_key)

        ordered_decisions = starved + fresh

        # Bookkeeping: was the FCFS-first request still the chosen
        # first? If not, this admission step was reordered.
        if pending:
            fcfs_first = min(
                pending, key=lambda r: r.arrival_time,
            )
            if ordered_decisions[0].request is not fcfs_first:
                self._reordered += 1
            self._admissions += 1
            self._predicted_hit_tokens_total += (
                ordered_decisions[0].predicted_hit_tokens
            )

        return [d.request for d in ordered_decisions]

    def stats(self) -> Dict[str, int]:
        return {
            "admissions": self._admissions,
            "reordered_count": self._reordered,
            "starvation_overrides": self._starvation_overrides,
            "predicted_hit_tokens_total": self._predicted_hit_tokens_total,
            **{f"tree_{k}": v for k, v in self.tree.stats().items()},
        }
