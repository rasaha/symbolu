"""
normalization_validator.py — the governance gate before the authoritative ledger (§9).

Validates every candidate EvidenceRecord: schema conformity, SOURCE-SPAN EXISTENCE (the span must
occur verbatim in its document — blocks hallucinations), access authorization, confidence threshold,
interpretation status, and contradiction with prior records. Only EXACT records with a valid span
are admitted as authoritative; INFERRED/AMBIGUOUS or low-confidence records are routed to provisional
/ human-review / conflict-set. Unresolved interpretation NEVER enters the exact ledger as fact.
"""
from __future__ import annotations

from typing import Dict, List

from .document_schema import Workflow
from .evidence_schema import EvidenceRecord, EXACT, INFERRED, AMBIGUOUS, CONFLICTED, provenance_hash
from .provisional_evidence import RoutedEvidence

CONF_ADMIT = 0.95            # confidence needed to admit an interpreted record as authoritative-provisional
CONF_MIN = 0.5


def _doc_bodies(wf: Workflow) -> Dict[str, str]:
    return {d.doc_id: d.body for d in wf.documents}


def _authorized(rec, wf):
    for d in wf.documents:
        if d.doc_id == rec.source_document_id:
            return rec.tenant_id == d.tenant_id
    return False


def validate(records: List[EvidenceRecord], wf: Workflow) -> RoutedEvidence:
    bodies = _doc_bodies(wf)
    routed = RoutedEvidence()
    by_field: Dict[tuple, List[EvidenceRecord]] = {}
    for r in records:
        # 1 schema conformity
        if r.source_document_id not in bodies or r.field_name == "":
            routed.blocked.append({"record": r.evidence_id, "reason": "schema"}); continue
        # 2 source-span existence (blocks hallucination)
        if r.source_span not in bodies[r.source_document_id]:
            routed.blocked.append({"record": r.evidence_id, "reason": "span_not_found"}); continue
        # 3 provenance integrity
        if r.provenance_hash != provenance_hash(r.source_document_id, r.source_span, r.normalized_value):
            routed.blocked.append({"record": r.evidence_id, "reason": "provenance"}); continue
        # 4 access authorization
        if not _authorized(r, wf):
            routed.blocked.append({"record": r.evidence_id, "reason": "unauthorized"}); continue
        # 5 confidence floor
        if r.extraction_confidence < CONF_MIN:
            routed.provisional.append(r); continue
        by_field.setdefault((r.subject_id, r.field_name), []).append(r)

    for key, recs in by_field.items():
        # 6 contradiction detection among same-field records
        values = {r.normalized_value for r in recs}
        if len(values) > 1 and any(r.interpretation_status == EXACT for r in recs) is False:
            for r in recs:
                r.interpretation_status = CONFLICTED
            routed.conflict_set.extend(recs); continue
        for r in recs:
            # 7 interpretation-status routing: EXACT admitted; INFERRED admitted only if high-confidence,
            #    else provisional/human review. Unresolved interpretation never becomes authoritative fact.
            if r.interpretation_status == EXACT:
                routed.authoritative.append(r)
            elif r.interpretation_status == INFERRED and r.extraction_confidence >= CONF_ADMIT:
                routed.authoritative.append(r)          # admitted but flagged INFERRED (still provenance-linked)
            elif r.interpretation_status in (INFERRED, AMBIGUOUS):
                routed.human_review.append(r)
            else:
                routed.provisional.append(r)
    return routed
