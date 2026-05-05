"""SOTIF (ISO 21448) + ISO 26262 part-6 traceability template.

A regulator-facing mapping from BCVF artifacts to standard clauses.
The point is to let a buyer's safety team start a clause-by-clause
walk-through on day one of a diligence call rather than waiting for
"after the safety case is ready" — the artifacts that ground each
clause already exist in the repo; this package is the index.

Public surface:

    from symbolu_robotics.bcvf_autonomous.safety_case import (
        Standard, Clause, EvidenceArtifact, TraceabilityEntry,
        TraceabilityMatrix, build_traceability_matrix,
        render_markdown,
    )

    matrix = build_traceability_matrix()
    print(render_markdown(matrix))

The matrix is the source of truth. ``SOTIF_TRACEABILITY.md`` in this
directory is a snapshot of ``render_markdown(build_traceability_matrix())``
that ships in the repo for human readers; ``test_safety_case`` pins
the snapshot to the matrix so the doc cannot drift silently.
"""

from __future__ import annotations

from .traceability import (
    Clause,
    EvidenceArtifact,
    Standard,
    TraceabilityEntry,
    TraceabilityMatrix,
    build_traceability_matrix,
    iso_21448_clauses,
    iso_26262_part6_clauses,
    render_markdown,
)

__all__ = [
    "Clause",
    "EvidenceArtifact",
    "Standard",
    "TraceabilityEntry",
    "TraceabilityMatrix",
    "build_traceability_matrix",
    "iso_21448_clauses",
    "iso_26262_part6_clauses",
    "render_markdown",
]
