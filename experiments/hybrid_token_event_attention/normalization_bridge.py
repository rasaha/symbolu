"""
normalization_bridge.py — deterministic normalization + provenance/access validation gate (§5 Level A).

Position in the pipeline:

    Mistral token processing → *proposed* EvidenceRecords → [THIS MODULE] → P5 binding slots →
    event attention.

This is a purely deterministic, non-learned boundary. It NEVER lets learned state alter an exact
field. It enforces, by construction, the two integrity invariants the acceptance criteria demand:

    * unauthorized-event inclusion = 0.00
        A record is admitted only if its `access_scope` grants the query's reader role AND its
        `tenant_id` matches the query tenant. Cross-tenant / out-of-scope records are dropped.

    * evidence-ID preservation = 1.00
        Admitted records are copied verbatim (exact fields untouched) and their `evidence_id`
        rides into the slot. The provenance hash is re-verified; a record whose exact fields do not
        match its sealed hash is rejected as tampered.

The P5 binding-slot admission policy itself is FROZEN (see `enterprise_slots_quadratic`); we only
*consume* it here as a deterministic, structural-signal-only priority when candidates exceed K.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Tuple

from .event_schema import (EventRecord, Slot, Query, ACTIVE, PENDING, REL, N_RELATION,
                           INTERP_AMBIGUOUS)

# chain relations (procurement approval chain): request→budget/policy/contract/approval
CHAIN_RELATIONS = {REL["requires_approval"], REL["has_budget"], REL["awarded_to"],
                   REL["governed_by"], REL["supersedes"], REL["grants_exception"],
                   REL["authorized_by"], REL["approval_requested"], REL["approval_granted"],
                   REL["threshold_at"]}


class ValidationReport:
    def __init__(self):
        self.n_proposed = 0
        self.n_schema_ok = 0
        self.n_provenance_ok = 0
        self.n_authorized = 0
        self.admitted_ids: List[int] = []
        self.rejected: List[Tuple[int, str]] = []          # (evidence_id, reason)
        self.unauthorized_seen: List[int] = []             # dropped for access/tenant
        self.evicted_ids: List[int] = []                   # dropped only for capacity

    def summary(self) -> Dict:
        return {
            "n_proposed": self.n_proposed,
            "n_schema_ok": self.n_schema_ok,
            "n_provenance_ok": self.n_provenance_ok,
            "n_authorized": self.n_authorized,
            "n_admitted": len(self.admitted_ids),
            "n_unauthorized_dropped": len(self.unauthorized_seen),
            "n_capacity_evicted": len(self.evicted_ids),
        }


# ---------------- schema validity ----------------
def schema_valid(rec: EventRecord) -> Tuple[bool, str]:
    if not (0 <= rec.relation_type < N_RELATION):
        return False, "bad_relation"
    if rec.confidence < 0.0 or rec.confidence > 1.0:
        return False, "bad_confidence"
    if rec.authority < 0.0 or rec.authority > 1.0:
        return False, "bad_authority"
    if rec.valid_to < rec.valid_from:
        return False, "bad_validity_window"
    if rec.evidence_id < 0:
        return False, "bad_evidence_id"
    return True, ""


def provenance_valid(rec: EventRecord) -> bool:
    return bool(rec.provenance_hash) and rec.hash_valid()


def authorized(rec: EventRecord, query: Query) -> bool:
    return rec.tenant_id == query.tenant_id and rec.readable_by(query.reader_role)


# ---------------- P5-consistent deterministic admission priority ----------------
def _priority(rec: EventRecord, query: Query) -> Tuple:
    """Structural-signal-only retention priority (higher = keep). Never reads task labels.

    Ordering: chain-relevant > active > higher authority > higher confidence > provisional-last.
    """
    chain = 1 if rec.relation_type in CHAIN_RELATIONS else 0
    subject_relevant = 1 if rec.subject_id == query.subject_id else 0
    active = 1 if rec.status == ACTIVE else 0
    interp = 0 if rec.interpretation_status == INTERP_AMBIGUOUS else 1
    return (chain, subject_relevant, active, interp, round(rec.authority, 4),
            round(rec.confidence, 4), -rec.evidence_id)


def normalize_value(rec: EventRecord) -> EventRecord:
    """Deterministic canonicalization: clamp confidence, keep exact identity fields intact.

    Returns a copy; the exact identity fields (subject/relation/object/version/status/validity)
    are unchanged so the provenance hash is preserved."""
    conf = min(1.0, max(0.0, rec.confidence))
    out = replace(rec, confidence=conf)
    out.provenance_hash = rec.provenance_hash  # identity fields unchanged → hash preserved
    return out


def build_working_set(proposed: List[EventRecord], query: Query, K: int,
                      report: ValidationReport = None) -> Tuple[List[Slot], ValidationReport]:
    """Validate → authorize → normalize → P5-admit ≤K records into exact binding slots."""
    if report is None:
        report = ValidationReport()
    report.n_proposed += len(proposed)

    candidates: List[EventRecord] = []
    for rec in proposed:
        ok, reason = schema_valid(rec)
        if not ok:
            report.rejected.append((rec.evidence_id, reason))
            continue
        report.n_schema_ok += 1
        if not provenance_valid(rec):
            report.rejected.append((rec.evidence_id, "provenance_mismatch"))
            continue
        report.n_provenance_ok += 1
        if not authorized(rec, query):
            report.unauthorized_seen.append(rec.evidence_id)
            report.rejected.append((rec.evidence_id, "unauthorized"))
            continue
        report.n_authorized += 1
        candidates.append(normalize_value(rec))

    # P5 deterministic admission when the authorized set exceeds capacity K
    candidates.sort(key=lambda r: _priority(r, query), reverse=True)
    admitted = candidates[:K]
    for r in candidates[K:]:
        report.evicted_ids.append(r.evidence_id)

    slots = [Slot(slot_index=i, record=r) for i, r in enumerate(admitted)]
    report.admitted_ids.extend(s.evidence_id for s in slots)
    return slots, report


def evidence_id_preservation(slots: List[Slot]) -> float:
    """Fraction of slots whose exact record still resolves (hash valid) — must be 1.0."""
    if not slots:
        return 1.0
    good = sum(1 for s in slots if s.record.hash_valid())
    return good / len(slots)
