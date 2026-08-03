"""
slot_reference.py — dependency-free reference model of the bounded binding-slot mechanics.

Extraction status: SEMANTIC_EXTRACTION (pure-stdlib reimplementation of the discrete
mechanics of two incubated torch modules; NOT a copy of either).
Mirrors:
  * symbolu/lightweight_phase/binding_slots.py::BoundedBindingSlots  (source blob 6ee03c13…)
      -> content addressing, collision->supersede+version-bump, source attribution,
         LRU eviction, bounded O(M) state, streaming read-then-write.
  * experiments/phase_lc/models.py::BindingSlots                     (source blob 76b5af69…)
      -> content-routed top-k soft read over M fixed slots, no N x N score matrix.
Packaging status: NOT_PACKAGED.

WHY A STDLIB REFERENCE EXISTS
-----------------------------
The two production slot modules are written in PyTorch, which is not installed in this
environment, so their *learned* behaviour (whether SGD finds good projections) is
RESOURCE_BLOCKED. But the *mechanism* those modules implement — how a token is addressed
to a slot, how a repeated key supersedes an old value and bumps a version, how a source id
is retained, how capacity is managed by eviction, and the structural guarantee that state
is O(M) and no [N, N] tensor is ever built — is discrete and deterministic. This reference
implements exactly that mechanism, operating directly on already-projected key/value
vectors (the "address space"). It lets the behavioural and complexity claims be tested here,
today, with the projection-learning step cleanly separated out as the blocked part.

This is the "deterministic algorithmic probe before model training" substrate. It is also the
parity oracle the torch modules must match on discrete metadata once torch is available.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

# Vendored declarative no-N x N / bounded-state audit (stdlib, byte-identical to the source core).
from ..instrumentation.invariants import register_shape

Vector = Sequence[float]


def _dot(a: Vector, b: Vector) -> float:
    return sum(x * y for x, y in zip(a, b))


def _norm(a: Vector) -> float:
    return math.sqrt(sum(x * x for x in a))


def _cosine(a: Vector, b: Vector) -> float:
    na, nb = _norm(a), _norm(b)
    if na == 0.0 or nb == 0.0:
        return 0.0
    return _dot(a, b) / (na * nb)


def _softmax(xs: Sequence[float]) -> List[float]:
    if not xs:
        return []
    m = max(xs)
    exps = [math.exp(x - m) for x in xs]
    s = sum(exps)
    if s == 0.0:
        return [1.0 / len(xs)] * len(xs)
    return [e / s for e in exps]


@dataclass
class SlotState:
    """Bounded state: M slots, each carrying content + discrete metadata. Size is O(M),
    independent of the number of tokens processed (proven by state_numel())."""
    keys: List[List[float]]      # M x Ds  (content-addressable key)
    values: List[List[float]]    # M x Dv  (bound value)
    source: List[int]            # M       (source id, -1 = unset)
    version: List[int]           # M       (version counter; bumps on supersede)
    usage: List[float]           # M       (recency/usage for LRU eviction)
    active: List[bool]           # M       (True = occupied)
    position: int = 0
    # audit counters (metadata only; never affect readouts)
    collisions: int = 0
    evictions: int = 0

    def numel(self) -> int:
        M = len(self.active)
        Ds = len(self.keys[0]) if self.keys else 0
        Dv = len(self.values[0]) if self.values else 0
        return M * Ds + M * Dv + 4 * M  # keys + values + {source,version,usage,active}

    def n_active(self) -> int:
        return sum(1 for a in self.active if a)


class SlotReference:
    """Deterministic bounded binding-slot memory over a fixed address space.

    Operates on already-projected key/value vectors, so tests control addressing directly.
    No randomness: identical inputs -> identical state and readouts. No [N, N] tensor is ever
    built — writes/reads touch only the M slots, one token at a time.
    """

    def __init__(self, key_dim: int, value_dim: int, num_slots: int,
                 top_k: int = 4, match_threshold: float = 0.5, write_gate: float = 1.0):
        assert num_slots >= 1 and key_dim >= 1 and value_dim >= 1
        self.Ds = key_dim
        self.Dv = value_dim
        self.M = num_slots
        self.top_k = min(top_k, num_slots)
        self.match_threshold = match_threshold
        self.write_gate = write_gate

    # ------------------------------------------------------------------
    def init_state(self) -> SlotState:
        return SlotState(
            keys=[[0.0] * self.Ds for _ in range(self.M)],
            values=[[0.0] * self.Dv for _ in range(self.M)],
            source=[-1] * self.M,
            version=[0] * self.M,
            usage=[0.0] * self.M,
            active=[False] * self.M,
            position=0,
        )

    # ------------------------------------------------------------------
    def _address_write(self, key: Vector, state: SlotState) -> Tuple[int, bool]:
        """Pick a slot: matched active slot (collision->supersede) or a free/LRU slot.

        Returns (slot_index, matched). Discrete, deterministic; ties broken by lowest index.
        """
        best_idx, best_sim = -1, -2.0
        for m in range(self.M):
            if not state.active[m]:
                continue
            sim = _cosine(key, state.keys[m])
            if sim > best_sim:
                best_sim, best_idx = sim, m
        if best_idx >= 0 and best_sim >= self.match_threshold:
            return best_idx, True
        # allocate: first free slot, else LRU (lowest usage) among active
        for m in range(self.M):
            if not state.active[m]:
                return m, False
        lru_idx, lru_usage = 0, float("inf")
        for m in range(self.M):
            if state.usage[m] < lru_usage:
                lru_usage, lru_idx = state.usage[m], m
        return lru_idx, False

    # ------------------------------------------------------------------
    def write(self, key: Vector, value: Vector, state: SlotState,
              source_id: int = 0, gate: Optional[float] = None) -> SlotState:
        """Write (key -> value) into the addressed slot. Bounded O(M*D). Mutates a copy."""
        assert len(key) == self.Ds and len(value) == self.Dv
        g = self.write_gate if gate is None else gate
        idx, matched = self._address_write(key, state)
        was_active = state.active[idx]
        if matched:
            state.collisions += 1
        elif was_active:
            state.evictions += 1  # occupied slot reused for a new key = eviction

        # convex-combine content (cosine addressing is scale-invariant, so retrieval is robust
        # to g < 1); a fresh slot starts at zero so it becomes g*key / g*value in direction.
        for i in range(self.Ds):
            state.keys[idx][i] = (1.0 - g) * state.keys[idx][i] + g * key[i]
        for i in range(self.Dv):
            state.values[idx][i] = (1.0 - g) * state.values[idx][i] + g * value[i]

        # discrete metadata (auditable): version bump, source, recency, activation.
        if matched:
            state.version[idx] += 1          # supersession of the same key
        else:
            state.version[idx] = 1           # fresh binding
        state.source[idx] = source_id
        state.active[idx] = True
        for m in range(self.M):
            state.usage[m] *= 0.999
        state.usage[idx] += 1.0
        state.position += 1
        return state

    # ------------------------------------------------------------------
    def read(self, query: Vector, state: SlotState) -> Tuple[List[float], int]:
        """Top-k soft read over active slots. Returns (readout_value, argmax_slot_index).

        O(M*D). Registers the score shape as (M,) with ONE non-sequence axis so the
        declarative audit proves no [N, N] work occurs.
        """
        assert len(query) == self.Ds
        register_shape("slot_scores", (self.M,), n_seq_axes=0)  # M fixed, not N
        scored: List[Tuple[float, int]] = []
        for m in range(self.M):
            if not state.active[m]:
                continue
            score = _dot(query, state.keys[m]) / math.sqrt(self.Ds)
            scored.append((score, m))
        if not scored:
            return [0.0] * self.Dv, -1
        scored.sort(key=lambda t: (-t[0], t[1]))
        top = scored[: self.top_k]
        weights = _softmax([s for s, _ in top])
        readout = [0.0] * self.Dv
        for w, (_, m) in zip(weights, top):
            for i in range(self.Dv):
                readout[i] += w * state.values[m][i]
        argmax_slot = top[0][1]
        return readout, argmax_slot

    # ------------------------------------------------------------------
    def stream(self, keys: Sequence[Vector], values: Sequence[Vector],
               queries: Optional[Sequence[Vector]] = None,
               source_ids: Optional[Sequence[int]] = None
               ) -> Tuple[List[List[float]], SlotState]:
        """Streaming read-then-write over a sequence of tokens (mirrors the torch forward).

        Peak memory is O(M*D) for the carried state plus O(N*D) for the stacked outputs —
        never O(N*M*D) and never O(N*N). Returns (readouts, final_state).
        """
        state = self.init_state()
        readouts: List[List[float]] = []
        qs = queries if queries is not None else keys
        for t in range(len(keys)):
            ro, _ = self.read(qs[t], state)      # causal read BEFORE writing this token
            readouts.append(ro)
            src = source_ids[t] if source_ids is not None else state.position
            state = self.write(keys[t], values[t], state, source_id=src)
        return readouts, state
