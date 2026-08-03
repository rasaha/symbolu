# Incubated from: symbolu/lightweight_phase/invariants.py
# Source commit: 8b4ec6e71666282384a4e23f78c724f8df4ba767
# Source blob: d064b252de162cfe4886c6e301e088a26d0a72d9
# Extraction status: BYTE_IDENTICAL (only this provenance header prepended)
# Packaging status: NOT_PACKAGED
"""
invariants.py — Runtime, executable invariants for the Lightweight Phase core.

These are *contracts*, not docstrings. Stage-1 completion criteria #4 and #5 are
enforced here and exercised by ``tests/test_complexity.py``:

  * INV-NO-NN   : no intermediate tensor may be indexed by two sequence positions
                  (i.e. no [.., N, N] score/affinity matrix — the signature of
                  quadratic sequence-to-sequence work).
  * INV-STATE-O : the recurrent Phase state size is independent of N.

Detection is DECLARATIVE, not value-based. The core marks every tensor it
materializes with the number of axes that are the *sequence* axis via
``register_shape(name, shape, n_seq_axes=...)``. A value-based heuristic
("two axes equal to N") is unreliable because N can coincide with the batch
size or head count (e.g. [B=2, N=2, H=4, Dh]); the number of sequence axes is a
semantic property the code knows exactly. The core never registers a tensor with
more than one sequence axis, which is the structural O(N) guarantee. The
companion measurement test (peak-intermediate scaling) is the empirical guard
against accidental quadratic work.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator, List, Optional, Tuple

# Thread-local so concurrent forward passes don't interfere.
_audit_state = threading.local()


class InvariantViolation(AssertionError):
    """Raised when a frozen invariant is violated at runtime."""


@dataclass
class _Record:
    name: str
    shape: Tuple[int, ...]
    n_seq_axes: int

    @property
    def numel(self) -> int:
        out = 1
        for s in self.shape:
            out *= int(s)
        return out


@dataclass
class ShapeAudit:
    """Collects registered tensor shapes and checks the no-two-sequence-axes rule."""

    seq_len: int
    records: List[_Record] = field(default_factory=list)

    def register(self, name: str, shape: Tuple[int, ...], n_seq_axes: int = 1) -> None:
        rec = _Record(name=name, shape=tuple(int(s) for s in shape), n_seq_axes=n_seq_axes)
        self.records.append(rec)
        if n_seq_axes >= 2:
            raise InvariantViolation(
                f"[INV-NO-NN] tensor {name!r} (shape={rec.shape}) is indexed by "
                f"{n_seq_axes} sequence positions. A tensor with two sequence axes is "
                f"a quadratic sequence-to-sequence tensor and is prohibited in the Phase core."
            )

    def peak_numel(self) -> int:
        return max((r.numel for r in self.records), default=0)


def get_active_audit() -> Optional[ShapeAudit]:
    return getattr(_audit_state, "audit", None)


def register_shape(name: str, shape, n_seq_axes: int = 1) -> None:
    """No-op unless a ShapeAudit context is active. ``n_seq_axes`` declares how many
    of this tensor's axes are indexed by sequence position (the core always uses 1)."""
    audit = get_active_audit()
    if audit is not None:
        audit.register(name, tuple(shape), n_seq_axes=n_seq_axes)


@contextmanager
def shape_audit(seq_len: int) -> Iterator[ShapeAudit]:
    """Activate no-two-sequence-axes auditing for the duration of a forward pass."""
    prev = getattr(_audit_state, "audit", None)
    audit = ShapeAudit(seq_len=seq_len)
    _audit_state.audit = audit
    try:
        yield audit
    finally:
        _audit_state.audit = prev


def assert_state_size_independent_of_n(state_numel_by_n: dict[int, int]) -> None:
    """INV-STATE-O: verify the recurrent state numel does not grow with N."""
    if len(state_numel_by_n) < 2:
        raise InvariantViolation(
            "need at least two sequence lengths to check state-size independence"
        )
    values = set(state_numel_by_n.values())
    if len(values) != 1:
        raise InvariantViolation(
            f"[INV-STATE-O] Phase state size varies with sequence length: {state_numel_by_n}. "
            "The recurrent state must be O(D), independent of N."
        )
