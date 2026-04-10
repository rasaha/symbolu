"""
PCAM-side KV-cache policy — INTENTIONAL TDD STUB.

Status
------
Stub. This module exists so that `simulator/pcam/tests/test_sketch_conformance.py`
and `simulator/pcam/tests/test_attention_evictor_parity.py` can import
`simulator.pcam.kv_policy` successfully. Before this file existed, the
conformance tests skipped with a module-not-found message; now they fail
loudly with NotImplementedError, turning the test suite from a waiting
room into a hard implementation gate.

Contract and plan
-----------------
Do not fill this in with partial or simplified logic.

- **Contract:** docs/design/ADR-0001-CTM-KV-SCORING-SOURCE-OF-TRUTH.md
  (declares `CTM_plus/KVPolicy/kv_policy/attention_evictor.py` the
  canonical reference for KV-cache scoring and locks the four-signal
  phase-aware formula)

- **Plan:** simulator/pcam/docs/PCAM_UPDATE_PR_SCOPE.md
  (files and line ranges to change, commit ordering, non-goals,
  acceptance criteria)

- **Oracle:** `CTM_plus/KVPolicy/kv_policy/attention_evictor.py`
  (the Python reference the PCAM implementation must be observationally
  equivalent to)

What "done" looks like
----------------------
Both of these commands report all green, with a fixed RNG seed and zero
mismatches across every parity test:

    pytest simulator/pcam/tests/test_sketch_conformance.py
    pytest simulator/pcam/tests/test_attention_evictor_parity.py

Structural surface (deliberately constructible)
-----------------------------------------------
- `FrequencySketch.__init__`  — computes width (floor 64, power of two),
  depth (4), and reset_threshold (capacity * 10). These are invariants,
  not algorithm; the conformance suite asserts them and they must be
  correct. The sketch table itself is NOT allocated here.
- `KVCachePolicy.__init__`    — stores constructor parameters and
  initializes `gpu_blocks` and `pinned_blocks` as empty sets. Exposing
  these attributes as empty sets (rather than leaving them undefined)
  ensures parity tests fail on missing BEHAVIOR, not missing attributes
  — a clearer failure mode for anyone picking up the PR.

Behavioral surface (must raise NotImplementedError)
---------------------------------------------------
Everything else. Every call into the scoring path, the sketch path, the
eviction path, or the policy state machine must raise loudly. No no-ops.
No silent stores. No partial logic. The reference is the oracle; the
stub stays a stub until a real port lands.

Re-exports
----------
`InferencePhase` and `PositionClass` are re-exported from the reference
so tests and implementations can import the whole contract from
`simulator.pcam.kv_policy` once the stub is replaced. This means the
parity test's `from kv_policy.attention_evictor import InferencePhase`
can, in the finished state, become
`from simulator.pcam.kv_policy import InferencePhase` — but that
migration is explicitly not part of this stub.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, List, Set

# ---------------------------------------------------------------------------
# Reference package wiring. CTM_plus/KVPolicy/kv_policy is a setup.py
# package imported as `kv_policy` (not `CTM_plus.KVPolicy.kv_policy`); we
# add its parent to sys.path so enum re-exports resolve without requiring
# a pip install.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_KV_POLICY_PARENT = _REPO_ROOT / "CTM_plus" / "KVPolicy"
if str(_KV_POLICY_PARENT) not in sys.path:
    sys.path.insert(0, str(_KV_POLICY_PARENT))

from kv_policy.attention_evictor import (  # noqa: E402
    InferencePhase,
    PositionClass,
)

__all__ = [
    "FrequencySketch",
    "KVCachePolicy",
    "InferencePhase",
    "PositionClass",
]


# ---------------------------------------------------------------------------
# Error helper — every NotImplementedError points at the contract and the
# plan so the failure message is actionable on its own.
# ---------------------------------------------------------------------------

_STUB_POINTER = (
    "simulator.pcam.kv_policy is a stub. "
    "Contract: docs/design/ADR-0001-CTM-KV-SCORING-SOURCE-OF-TRUTH.md. "
    "Plan: simulator/pcam/docs/PCAM_UPDATE_PR_SCOPE.md. "
    "Oracle: CTM_plus/KVPolicy/kv_policy/attention_evictor.py. "
    "Do not fill in with partial logic — replace with a real port."
)


def _unimplemented(method: str) -> NotImplementedError:
    return NotImplementedError(f"{method}: {_STUB_POINTER}")


# ===========================================================================
# FrequencySketch stub.
# ===========================================================================


class FrequencySketch:
    """
    Stub for the 4-bit Count-Min Sketch.

    Constructible with correct structural invariants so the `width >= 64`
    / power-of-two / `depth == 4` / `reset_threshold == capacity * 10`
    assertions in `TestStructuralInvariants.test_pcam_matches_structural_invariants`
    can run. Every mutating or querying method raises.
    """

    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.width = self._next_pow2(max(64, capacity))
        self.depth = 4
        self.size = 0
        self.reset_threshold = capacity * 10
        # Table deliberately NOT allocated. Allocating the 2D counter
        # array would invite accidental partial-implementation drift.
        # A real port will add the table AND the hash seeds AND the
        # increment/estimate/halve paths in one atomic change, per the
        # PR scope doc.

    @staticmethod
    def _next_pow2(n: int) -> int:
        """
        Structural helper for the width invariant. This is deliberately
        the same bit-twiddling used in the reference (attention_evictor.py
        lines 83-87) because width is a function of capacity, not an
        algorithm choice. Copying it here is not "partial implementation"
        — the sketch's behavior lives in increment/estimate/halve, which
        remain unimplemented below.
        """
        if n <= 1:
            return 1
        n -= 1
        n |= n >> 1
        n |= n >> 2
        n |= n >> 4
        n |= n >> 8
        n |= n >> 16
        return n + 1

    def increment(self, key: int) -> int:
        raise _unimplemented("FrequencySketch.increment")

    def estimate(self, key: int) -> int:
        raise _unimplemented("FrequencySketch.estimate")


# ===========================================================================
# KVCachePolicy stub.
# ===========================================================================


class KVCachePolicy:
    """
    Stub for the attention-aware KV-cache eviction policy.

    Constructor matches the reference signature so the `_paired_policies`
    helper in the parity harness can instantiate it. `gpu_blocks` and
    `pinned_blocks` are initialized as empty sets so the parity tests
    fail on missing BEHAVIOR rather than missing ATTRIBUTES — a clearer
    signal for whoever picks up the implementation.

    All other state and every behavioral method is unimplemented. The
    real logic lives in the reference at
    `CTM_plus/KVPolicy/kv_policy/attention_evictor.py` per ADR-0001, and
    the PCAM port must be observationally equivalent to it (not
    approximately, not structurally — observationally, as verified by
    the parity harness).
    """

    def __init__(
        self,
        max_blocks: int,
        block_size: int = 16,
        sink_tokens: int = 4,
        recent_window: int = 256,
        entity_attention_threshold: float = 0.02,
        attention_ema_alpha: float = 0.1,
    ) -> None:
        # Store constructor parameters so a real port can consume them
        # without rewriting this shell. Nothing here is behavior.
        self.max_blocks = max_blocks
        self.block_size = block_size
        self.sink_tokens = sink_tokens
        self.recent_window = recent_window
        self.entity_attention_threshold = entity_attention_threshold
        self.attention_ema_alpha = attention_ema_alpha

        # Attribute surface expected by the parity harness. Empty sets
        # so parity tests produce "NotImplementedError in select_victims"
        # rather than "AttributeError: pinned_blocks" when the harness
        # sanity-checks pinning after admission.
        self.gpu_blocks: Set[int] = set()
        self.pinned_blocks: Set[int] = set()

    # ---- Sequence lifecycle -------------------------------------------------

    def register_sequence(self, seq_id: int) -> None:
        raise _unimplemented("KVCachePolicy.register_sequence")

    def set_phase(self, seq_id: int, phase: InferencePhase) -> None:
        raise _unimplemented("KVCachePolicy.set_phase")

    def complete_sequence(self, seq_id: int) -> List[int]:
        raise _unimplemented("KVCachePolicy.complete_sequence")

    # ---- RNG contract -------------------------------------------------------

    def set_rng(self, rng: Any) -> None:
        raise _unimplemented("KVCachePolicy.set_rng")

    # ---- Block admission and attention events -----------------------------

    def ensure_block(
        self,
        block_id: int,
        sequence_id: int,
        positions: List[int],
    ) -> None:
        raise _unimplemented("KVCachePolicy.ensure_block")

    def on_block_attention(
        self,
        block_id: int,
        attention_sum: float,
        sequence_id: int,
        seq_len: int = 0,
    ) -> None:
        raise _unimplemented("KVCachePolicy.on_block_attention")

    def on_token_access(
        self,
        token_id: int,
        position: int,
        sequence_id: int,
        block_id: int,
        attention_weight: float = 0.0,
        seq_len: int = 0,
    ) -> None:
        raise _unimplemented("KVCachePolicy.on_token_access")

    # ---- Scoring and eviction ----------------------------------------------

    def score_block(self, block_id: int) -> float:
        raise _unimplemented("KVCachePolicy.score_block")

    def select_victims(self, count: int) -> List[int]:
        raise _unimplemented("KVCachePolicy.select_victims")

    def evict_block(self, block_id: int) -> None:
        raise _unimplemented("KVCachePolicy.evict_block")

    def pin_block(self, block_id: int) -> None:
        raise _unimplemented("KVCachePolicy.pin_block")

    def unpin_block(self, block_id: int) -> None:
        raise _unimplemented("KVCachePolicy.unpin_block")

    def get_stats(self) -> dict:
        raise _unimplemented("KVCachePolicy.get_stats")
