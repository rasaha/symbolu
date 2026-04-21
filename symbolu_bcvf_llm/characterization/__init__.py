"""Phase 1.5 characterization harness (§3 scaffold).

**Status**: Strategic scaffold for §3 Phase 1.5. §3.1 (purpose) is the
authorized portion of the design; §3.2–§3.9 are design-draft and may
be refined before final sign-off. This package realizes the draft
spec as runnable code so the empirical sweep can inform revisions.

Sub-modules:
    traces.py        §3.3 generator — seven trace families
    alignment.py     §3.6 alignment diagnostic — hit / margin / rank
    sweep.py         §3.4 four-grid sweep + §3.9 tiebreaker
    __main__.py      `python -m symbolu_bcvf_llm.characterization` CLI

No ML-framework imports; pure NumPy, matches §2.8.1 discipline.
"""

from __future__ import annotations

from .alignment import (
    AlignmentAggregate,
    AlignmentMetrics,
    aggregate_alignment,
    compute_alignment_metrics,
)
from .traces import TraceBundle, generate_trace

__all__ = [
    "AlignmentAggregate",
    "AlignmentMetrics",
    "TraceBundle",
    "aggregate_alignment",
    "compute_alignment_metrics",
    "generate_trace",
]
