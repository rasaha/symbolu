"""
Authority helpers. Authority is never inferred from the layer — only from the
per-record epistemic/verification/authority metadata.
"""

from __future__ import annotations

from typing import List

from agentic.enterprise_ontology.events import (
    EnterpriseEventEnvelope,
    VerticalDecision,
)
from agentic.enterprise_ontology.records import OntologyRecord


def supporting_records(decision: VerticalDecision,
                       envelope: EnterpriseEventEnvelope) -> List[OntologyRecord]:
    out = []
    for rid in decision.supporting_record_ids:
        r = envelope.record_by_id(rid)
        if r is not None:
            out.append(r)
    return out


def has_authority_basis(decision: VerticalDecision,
                        envelope: EnterpriseEventEnvelope) -> bool:
    """A decision has an authority basis iff at least one supporting record is
    effectively authority-bearing (explicit role + trustworthy epistemics +
    verified/inferred, never declared-only interpretive)."""
    return any(r.is_authority_bearing for r in supporting_records(decision, envelope))


def depends_solely_on_advisory(decision: VerticalDecision,
                               envelope: EnterpriseEventEnvelope) -> bool:
    """True when the decision has supporting records, none authority-bearing, and
    at least one is advisory / non-authoritative / declared-only / interpretive."""
    recs = supporting_records(decision, envelope)
    if not recs:
        return False
    if any(r.is_authority_bearing for r in recs):
        return False
    return any(
        r.is_advisory_only
        or r.verification.value in ("declared", "unknown", "disputed")
        or (r.epistemic_origin is not None
            and r.epistemic_origin.value == "derived_interpretive")
        for r in recs
    )
