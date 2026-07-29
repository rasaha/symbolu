"""
event_schema.py — canonical, provenance-preserving EventRecord (§3).

Domain: procurement & approval governance (the same governed domain as the predecessor experiment
`enterprise_slots_quadratic`, which established that full slot-to-slot attention beats
query-to-slot; this experiment adds the Mistral token path around it).

An `EventRecord` is the *exact, resolvable* unit of evidence. Every categorical field is a small
int index into a bounded vocabulary, so held-out "unseen entity / template / wording" splits are
structural (new ids), not string matching. The record is authoritative: a slot holds a copy of it
plus a *learned* event embedding, but the exact fields are NEVER mutated by learning, and the
`evidence_id` rides with the embedding so every event-level output resolves back to the ledger.

Required fields (§3) are all present. `provenance_hash` is a deterministic digest of the exact
identity fields — corrupting any exact field changes the hash, which the normalization bridge and
the authoritative-output check both rely on.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional, Tuple

# ---------------- bounded vocabularies ----------------
SUBJECT_TYPES = ("PurchaseRequest", "Vendor", "Contract", "Budget", "Policy", "Approval",
                 "Employee", "Department", "Exception", "Invoice")
OBJECT_TYPES = ("Role", "Amount", "Vendor", "Contract", "Policy", "Boolean", "Employee", "Value")
RELATION_TYPES = ("requires_approval", "has_budget", "awarded_to", "governed_by", "supersedes",
                  "grants_exception", "authorized_by", "conflicts_with", "approval_requested",
                  "approval_granted", "threshold_at", "belongs_to")
STATUSES = ("active", "superseded", "expired", "pending", "revoked")
INTERP_STATUSES = ("resolved", "provisional", "ambiguous", "conflicted")
ROLES = ("role:requester", "role:finance", "role:finance_director", "role:auditor", "role:admin")

# index handles
ACTIVE, SUPERSEDED, EXPIRED, PENDING, REVOKED = range(5)
INTERP_RESOLVED, INTERP_PROVISIONAL, INTERP_AMBIGUOUS, INTERP_CONFLICTED = range(4)
REL = {name: i for i, name in enumerate(RELATION_TYPES)}

N_SUBJECT_TYPE = len(SUBJECT_TYPES)
N_OBJECT_TYPE = len(OBJECT_TYPES)
N_RELATION = len(RELATION_TYPES)
N_STATUS = len(STATUSES)
N_INTERP = len(INTERP_STATUSES)
N_ROLE = len(ROLES)


@dataclass
class EventRecord:
    # ---- §3 required exact fields ----
    evidence_id: int                 # unique, resolvable in the ledger
    tenant_id: int
    source_document_id: int
    source_span: int                 # page/offset marker
    subject_id: int
    relation_type: int               # index into RELATION_TYPES
    object_id_or_value: int
    normalized_value: int            # canonicalized value (e.g. amount tier / canonical version)
    version: int
    status: int                      # index into STATUSES
    valid_from: int
    valid_to: int
    authority: float                 # source authority weight in [0,1]
    access_scope: int                # bitmask over ROLES permitted to read the record
    interpretation_status: int       # index into INTERP_STATUSES
    confidence: float                # extraction/normalization confidence in [0,1]
    provenance_hash: str = ""        # digest of the exact identity fields (filled by seal())
    # ---- auxiliary typing (aids the encoder; still exact, never a label) ----
    subject_type: int = 0
    object_type: int = 0
    # ---- generator bookkeeping (NEVER fed to any model) ----
    template: int = 0
    tag: str = ""
    arrival_step: int = 0

    # ---------- identity / provenance ----------
    def identity_tuple(self) -> Tuple:
        """Exact (subject, relation, object) identity used for deterministic joins / dedup."""
        return (self.subject_type, self.subject_id, self.relation_type,
                self.object_type, self.object_id_or_value)

    def _provenance_payload(self) -> str:
        return "|".join(str(x) for x in (
            self.tenant_id, self.source_document_id, self.source_span, self.subject_type,
            self.subject_id, self.relation_type, self.object_type, self.object_id_or_value,
            self.normalized_value, self.version, self.status, self.valid_from, self.valid_to))

    def compute_hash(self) -> str:
        return hashlib.sha1(self._provenance_payload().encode()).hexdigest()[:16]

    def seal(self) -> "EventRecord":
        self.provenance_hash = self.compute_hash()
        return self

    def hash_valid(self) -> bool:
        return self.provenance_hash == self.compute_hash()

    def readable_by(self, role_idx: int) -> bool:
        return bool(self.access_scope & (1 << role_idx))

    def as_record(self) -> Dict:
        return asdict(self)


@dataclass
class Slot:
    """A bound working-memory slot: exact record + (runtime) learned embedding + audit event.

    `repr_row` is filled by the encoder at forward time; `evidence_id` mirrors the record so an
    attention weight over a slot resolves to an exact ledger record (attribution)."""
    slot_index: int
    record: EventRecord
    repr_row: Optional[List[float]] = None
    admit_event: str = "admitted"

    @property
    def evidence_id(self) -> int:
        return self.record.evidence_id


@dataclass
class Query:
    """The decision request over a workflow (what the arms must answer)."""
    task_family: str
    subject_id: int                  # the focal PurchaseRequest / entity
    reader_role: int                 # role issuing the query (drives access_scope filtering)
    tenant_id: int
    aux: Dict = field(default_factory=dict)


@dataclass
class Instance:
    """One end-to-end example."""
    query: Query
    oracle_records: List[EventRecord]      # ground-truth normalized events
    predicted_records: List[EventRecord]   # extraction-pipeline output (noisy)
    raw_text: str                          # enterprise document text for the token path
    retrieved_text: str                    # retrieved packet for H1 (text, no normalized events)
    gold_answer: int                       # answer class index
    required_ids: List[int]                # evidence_ids that must survive for a valid decision
    labels: Dict                           # per-family diagnostic labels (conflict, abstain, ...)


def seal_all(records: List[EventRecord]) -> List[EventRecord]:
    for r in records:
        r.seal()
    return records


def scope_mask(role_idxs: List[int]) -> int:
    m = 0
    for r in role_idxs:
        m |= (1 << r)
    return m
