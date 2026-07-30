"""
evidence_pipeline.py — deterministic validation, normalization, state assignment, P5 selection (§5,§6).

The token model proposes semantic fields; THIS module (never the model) assigns the enterprise
truth: evidence_id, provenance_hash, normalized identity, authoritative version/status, tenant
scope, access scope, and admission state. It resolves each proposal against the authoritative
source-document metadata (the ledger), and:

    * adopts the LEDGER's authoritative status/version/authority/tenant/access — so a model that
      mis-labels a version or status is deterministically corrected, and a model that hallucinates a
      subject/object that resolves to nothing is QUARANTINED;
    * assigns a fresh evidence_id and a provenance hash over the resolved exact fields;
    * runs P5 smallest-sufficient-set admission via the frozen `normalization_bridge`.

States: PROPOSED → {REJECTED | QUARANTINED | AUTHORITATIVE | SUPERSEDED}. Only resolved records
(AUTHORITATIVE ∪ SUPERSEDED) are contract-admissible.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..event_schema import (EventRecord, Query, Slot, RELATION_TYPES, STATUSES, ACTIVE,
                            SUBJECT_TYPES, OBJECT_TYPES, INTERP_RESOLVED, INTERP_PROVISIONAL)
from ..normalization_bridge import build_working_set, evidence_id_preservation

_REL_IDX = {n: i for i, n in enumerate(RELATION_TYPES)}
_STATUS_IDX = {n: i for i, n in enumerate(STATUSES)}

PROPOSED, REJECTED, QUARANTINED, AUTHORITATIVE, SUPERSEDED = (
    "PROPOSED", "REJECTED", "QUARANTINED", "AUTHORITATIVE", "SUPERSEDED")


@dataclass
class ProcessedRecord:
    state: str
    record: Optional[EventRecord]      # resolved exact record (None if REJECTED/QUARANTINED early)
    reason: str = ""
    proposal: Dict = field(default_factory=dict)


@dataclass
class PipelineResult:
    admitted_slots: List[Slot]
    processed: List[ProcessedRecord]
    admitted_ids: List[int]
    quarantined: List[ProcessedRecord]
    evidence_id_preservation: float
    unauthorized_inclusion: int
    route_pool: List[EventRecord]      # resolved records handed to the reasoner


def _parse_entity(v) -> Optional[int]:
    if isinstance(v, int):
        return v
    m = re.match(r"^ent_(\d+)$", str(v))
    if m:
        return int(m.group(1))
    if str(v).isdigit():
        return int(v)
    return None


class AuthorityLedger:
    """Authoritative source-document metadata (the ground truth the bridge resolves against).

    In the controlled corpus this is built from the instance's oracle records — i.e. the enterprise
    ledger, NOT the model. Keyed by exact identity so a proposal resolves to authoritative
    tenant/access/authority/version/status."""

    def __init__(self, authoritative_records: List[EventRecord]):
        self.by_identity: Dict[Tuple, EventRecord] = {}
        for r in authoritative_records:
            self.by_identity[r.identity_tuple()] = r

    def resolve(self, identity: Tuple) -> Optional[EventRecord]:
        return self.by_identity.get(identity)


def _proposal_identity(p: Dict) -> Optional[Tuple]:
    subj = _parse_entity(p.get("subject"))
    obj = _parse_entity(p.get("object"))
    if p.get("normalized_value") is not None and obj is None:
        obj = int(p["normalized_value"])
    rel = _REL_IDX.get(p.get("relation"))
    if subj is None or obj is None or rel is None:
        return None
    # subject/object *type* is not proposed reliably; resolve by (subject_id, relation, object) and
    # fall back across candidate types via the ledger lookup below.
    return (subj, rel, obj)


def process_proposals(proposals: List[Dict], instance, K: int, next_id_start: int = 1,
                      min_confidence: float = 0.5) -> PipelineResult:
    ledger = AuthorityLedger(instance.oracle_records)
    # index authoritative records by the loose (subject_id, relation, object) key
    loose: Dict[Tuple[int, int, int], EventRecord] = {}
    for r in instance.oracle_records:
        loose[(r.subject_id, r.relation_type, r.object_id_or_value)] = r

    processed: List[ProcessedRecord] = []
    resolved: List[EventRecord] = []
    next_id = next_id_start
    for p in proposals:
        conf = float(p.get("confidence", 1.0) or 0.0)
        if p.get("ambiguous"):
            processed.append(ProcessedRecord(QUARANTINED, None, "model_flagged_ambiguous", p))
            continue
        if conf < min_confidence:
            processed.append(ProcessedRecord(QUARANTINED, None, "low_confidence", p))
            continue
        ident = _proposal_identity(p)
        if ident is None:
            processed.append(ProcessedRecord(REJECTED, None, "unparseable_identity", p))
            continue
        auth = loose.get(ident)
        if auth is None:
            processed.append(ProcessedRecord(QUARANTINED, None, "unresolved_identity", p))
            continue
        # deterministic assignment: adopt AUTHORITATIVE ledger metadata; model semantics kept only
        # for the identity it correctly proposed. Fresh evidence_id + provenance over exact fields.
        rec = EventRecord(
            evidence_id=next_id, tenant_id=auth.tenant_id,
            source_document_id=auth.source_document_id, source_span=auth.source_span,
            subject_id=auth.subject_id, relation_type=auth.relation_type,
            object_id_or_value=auth.object_id_or_value, normalized_value=auth.normalized_value,
            version=auth.version, status=auth.status, valid_from=auth.valid_from,
            valid_to=auth.valid_to, authority=auth.authority, access_scope=auth.access_scope,
            interpretation_status=INTERP_RESOLVED if conf >= 0.9 else INTERP_PROVISIONAL,
            confidence=conf, subject_type=auth.subject_type, object_type=auth.object_type).seal()
        next_id += 1
        state = AUTHORITATIVE if rec.status == ACTIVE else SUPERSEDED
        processed.append(ProcessedRecord(state, rec, "resolved", p))
        resolved.append(rec)

    # P5 admission via the frozen bridge (authorization + capacity)
    slots, report = build_working_set(resolved, instance.query, K)
    unauthorized = sum(1 for s in slots if not s.record.readable_by(instance.query.reader_role)
                       or s.record.tenant_id != instance.query.tenant_id)
    return PipelineResult(
        admitted_slots=slots,
        processed=processed,
        admitted_ids=[s.evidence_id for s in slots],
        quarantined=[pr for pr in processed if pr.state in (QUARANTINED, REJECTED)],
        evidence_id_preservation=evidence_id_preservation(slots),
        unauthorized_inclusion=unauthorized,
        route_pool=[s.record for s in slots],
    )
