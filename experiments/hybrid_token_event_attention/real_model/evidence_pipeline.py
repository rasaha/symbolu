"""
evidence_pipeline.py — deterministic validation, resolution, state assignment and P5 admission (§5, §6).

This is the authority boundary. The real model only *proposed* semantic fields and exact source
spans; here — with zero learned state — we:

  * parse the proposed content deterministically,
  * check type compatibility (relation in the governed vocabulary),
  * resolve identity against the governed ledger (assigning the AUTHORITATIVE evidence_id — the model
    never assigns ids),
  * inherit governance attributes (tenant scope, access scope, validity window, authority) from the
    ledger, NOT from the model,
  * recompute the provenance hash (seal),
  * assign a lifecycle state
    (PROPOSED / VALIDATED / QUARANTINED / REJECTED / SUPERSEDED / AUTHORITATIVE), and
  * run the frozen P5 admission (`normalization_bridge.build_working_set`) over the admissible set.

Malformed, unresolved, unauthorized, corrupt or low-confidence proposals are quarantined or rejected
— never silently repaired. The two integrity invariants (evidence-ID preservation = 1.00,
unauthorized inclusion = 0.00) are enforced structurally by the frozen bridge.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Tuple

from ..event_schema import (EventRecord, Query, Slot, REL, STATUSES, ACTIVE, SUPERSEDED,
                            INTERP_RESOLVED, INTERP_PROVISIONAL, INTERP_AMBIGUOUS)
from ..normalization_bridge import build_working_set, ValidationReport
from .extraction import ProvisionalEvent

# lifecycle states (§6)
PROPOSED = "PROPOSED"
VALIDATED = "VALIDATED"
QUARANTINED = "QUARANTINED"
REJECTED = "REJECTED"
SUPERSEDED_STATE = "SUPERSEDED"
AUTHORITATIVE = "AUTHORITATIVE"

LOW_CONFIDENCE = 0.5


@dataclass
class EvidenceRecordEnvelope:
    """A provisional proposal after deterministic processing: the sealed exact record (if any), its
    lifecycle state, and the reason. Only VALIDATED/AUTHORITATIVE envelopes proceed to admission."""
    state: str
    reason: str
    provisional: ProvisionalEvent
    record: Optional[EventRecord] = None      # sealed exact record (None if not resolvable)
    resolved_evidence_id: Optional[int] = None


@dataclass
class PipelineOutput:
    envelopes: List[EvidenceRecordEnvelope]
    slots: List[Slot]                          # P5-admitted exact binding slots
    admission_report: ValidationReport
    counts: Dict[str, int]

    @property
    def admitted_records(self) -> List[EventRecord]:
        return [s.record for s in self.slots]


# --------------------------------------------------------------------------- #
# deterministic parsers                                                        #
# --------------------------------------------------------------------------- #
import re as _re
_ENT_RE = _re.compile(r"\bent_(\d+)\b")


def _parse_ent(s: str) -> Optional[int]:
    """Accept ONLY a bounded canonical `ent_<N>` token (RM1-v1.1). A bare number like "532" is NOT
    silently resolved — that preserves strict identity while tolerating normal model phrasing such as
    "the subject is ent_532". Existence in the instance ledger is checked separately by the resolver.
    """
    if s is None:
        return None
    m = _ENT_RE.search(str(s))
    return int(m.group(1)) if m else None


def _parse_prefixed_int(s: str, prefix: str) -> Optional[int]:
    s = s.strip()
    if prefix and s.startswith(prefix):
        s = s[len(prefix):]
    return int(s) if s.lstrip("-").isdigit() else None


def _parse_status(s: str) -> Optional[int]:
    s = s.strip().lower()
    return STATUSES.index(s) if s in STATUSES else None


def _parse_authority(s: str) -> Optional[float]:
    v = _parse_prefixed_int(s, "a")
    return None if v is None else max(0.0, min(1.0, v / 10.0))


# --------------------------------------------------------------------------- #
# resolution against the governed ledger                                       #
# --------------------------------------------------------------------------- #
def _index_ledger(ledger: List[EventRecord]) -> Dict[Tuple[int, int, int], List[EventRecord]]:
    idx: Dict[Tuple[int, int, int], List[EventRecord]] = {}
    for r in ledger:
        idx.setdefault((r.subject_id, r.relation_type, r.object_id_or_value), []).append(r)
    return idx


def _resolve(prov: ProvisionalEvent, ledger_idx, query: Query) -> Tuple[Optional[EventRecord], str]:
    """Deterministically resolve one provisional proposal into a sealed exact record.

    Returns (record, reason). record is None when the proposal cannot be resolved. Governance
    attributes (tenant, access, validity, doc/span markers) are inherited from the resolved ledger
    entry; content attributes (value/status/version/authority) come from the model-copied source
    span. The evidence_id is the ledger's — never the model's.
    """
    if prov.relation not in REL:
        return None, "type_incompatible_relation"
    subj = _parse_ent(prov.subject)
    obj = _parse_ent(prov.object)
    if subj is None:
        return None, "unresolved_subject"
    rel = REL[prov.relation]
    norm = _parse_prefixed_int(prov.value, "n")
    if obj is None:
        obj = norm if norm is not None else 0
    key = (subj, rel, obj)
    matches = ledger_idx.get(key)
    if not matches:
        # try (subject, relation) with object==normalized_value fallback already applied; else fail
        return None, "unresolved_identity"
    ledger_rec = matches[0]

    status = _parse_status(prov.status)
    version = _parse_prefixed_int(prov.version, "v")
    authority = _parse_authority(prov.authority)
    interp = INTERP_AMBIGUOUS if prov.ambiguous else INTERP_RESOLVED

    rec = replace(
        ledger_rec,
        object_id_or_value=obj,
        normalized_value=norm if norm is not None else ledger_rec.normalized_value,
        status=status if status is not None else ledger_rec.status,
        version=version if version is not None else ledger_rec.version,
        authority=authority if authority is not None else ledger_rec.authority,
        interpretation_status=interp,
        confidence=prov.confidence,
        provenance_hash="",
    ).seal()
    return rec, "resolved"


# --------------------------------------------------------------------------- #
# state assignment                                                             #
# --------------------------------------------------------------------------- #
def _classify(prov: ProvisionalEvent, rec: Optional[EventRecord], reason: str,
              query: Query) -> EvidenceRecordEnvelope:
    # provisional gates first
    if not prov.span_verified:
        from .extraction import RES_AMBIGUOUS
        reason_ = ("ambiguous_source_document"
                   if prov.document_resolution_method == RES_AMBIGUOUS else "span_not_verified")
        return EvidenceRecordEnvelope(QUARANTINED, reason_, prov)
    if rec is None:
        if reason == "type_incompatible_relation":
            return EvidenceRecordEnvelope(REJECTED, reason, prov)
        return EvidenceRecordEnvelope(QUARANTINED, reason, prov)
    if not rec.hash_valid():
        return EvidenceRecordEnvelope(REJECTED, "provenance_invalid", prov, rec)
    # authority/access/tenant boundary (never admit cross-tenant or out-of-scope)
    if rec.tenant_id != query.tenant_id:
        return EvidenceRecordEnvelope(REJECTED, "cross_tenant", prov, rec)
    if not rec.readable_by(query.reader_role):
        return EvidenceRecordEnvelope(REJECTED, "access_denied", prov, rec)
    if prov.confidence < LOW_CONFIDENCE:
        return EvidenceRecordEnvelope(QUARANTINED, "low_confidence", prov, rec)
    if prov.ambiguous:
        return EvidenceRecordEnvelope(QUARANTINED, "materially_ambiguous", prov, rec)
    if rec.status == SUPERSEDED:
        return EvidenceRecordEnvelope(SUPERSEDED_STATE, "stale_version", prov, rec,
                                      resolved_evidence_id=rec.evidence_id)
    return EvidenceRecordEnvelope(VALIDATED, "ok", prov, rec, resolved_evidence_id=rec.evidence_id)


def _promote_authoritative(envs: List[EvidenceRecordEnvelope]) -> None:
    """Mark the active, highest-authority VALIDATED record for each identity AUTHORITATIVE. If a
    newer active version dominates an identity, older active duplicates are marked SUPERSEDED."""
    by_ident: Dict[Tuple, List[EvidenceRecordEnvelope]] = {}
    for e in envs:
        if e.state == VALIDATED and e.record is not None:
            by_ident.setdefault((e.record.subject_id, e.record.relation_type), []).append(e)
    for group in by_ident.values():
        # winner: active, then highest version, then highest authority
        winner = max(group, key=lambda e: (e.record.status == ACTIVE, e.record.version,
                                            e.record.authority))
        for e in group:
            if e is winner:
                e.state = AUTHORITATIVE
            elif e.record.version < winner.record.version and e.record.status == ACTIVE:
                e.state = SUPERSEDED_STATE
                e.reason = "superseded_by_newer_version"


def run_pipeline(proposals: List[ProvisionalEvent], query: Query, ledger: List[EventRecord],
                 K: int = 8) -> PipelineOutput:
    ledger_idx = _index_ledger(ledger)
    envs: List[EvidenceRecordEnvelope] = []
    for prov in proposals:
        rec, reason = _resolve(prov, ledger_idx, query)
        envs.append(_classify(prov, rec, reason, query))
    _promote_authoritative(envs)

    admissible = [e.record for e in envs if e.state in (VALIDATED, AUTHORITATIVE)
                  and e.record is not None]
    slots, report = build_working_set(admissible, query, K)

    counts: Dict[str, int] = {s: 0 for s in
                              (PROPOSED, VALIDATED, QUARANTINED, REJECTED,
                               SUPERSEDED_STATE, AUTHORITATIVE)}
    for e in envs:
        counts[e.state] = counts.get(e.state, 0) + 1
    counts["ADMITTED"] = len(slots)
    return PipelineOutput(envelopes=envs, slots=slots, admission_report=report, counts=counts)


def quarantine_entries(output: PipelineOutput) -> List[Dict]:
    out: List[Dict] = []
    for e in output.envelopes:
        if e.state in (QUARANTINED, REJECTED):
            out.append({
                "state": e.state,
                "reason": e.reason,
                "relation": e.provisional.relation,
                "source_document_id": e.provisional.source_document_id,
                "source_span": e.provisional.source_span,
                "confidence": e.provisional.confidence,
                "ambiguous": e.provisional.ambiguous,
                "resolved_evidence_id": e.resolved_evidence_id,
            })
    return out
