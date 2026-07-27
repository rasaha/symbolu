"""
evidence_ledger.py — authoritative long-term evidence storage.

The ledger is the single source of truth. Slots and quadratic attention may reference evidence_ids;
they must always resolve here. Access control and exact joins are DETERMINISTIC (schema/index),
never learned. The ledger also exposes deterministic candidate generation (by subject/object index)
and provenance/authority lookups. Nothing here is trainable.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .schema import Evidence


class EvidenceLedger:
    def __init__(self, records: List[Evidence], tenant_id: int, role_idx: int):
        self.tenant_id = tenant_id
        self.role_idx = role_idx
        self._by_id: Dict[int, Evidence] = {}
        self._by_subject: Dict[tuple, List[int]] = {}
        self._by_object: Dict[tuple, List[int]] = {}
        for e in records:
            self._by_id[e.evidence_id] = e
            self._by_subject.setdefault((e.subject_type, e.subject_id), []).append(e.evidence_id)
            self._by_object.setdefault((e.object_type, e.object_id_or_value), []).append(e.evidence_id)

    # ---- exact resolution ----
    def resolve(self, evidence_id: int) -> Optional[Evidence]:
        return self._by_id.get(evidence_id)

    def exists(self, evidence_id: int) -> bool:
        return evidence_id in self._by_id

    # ---- deterministic access control (never learned) ----
    def authorized(self, evidence_id: int) -> bool:
        e = self._by_id.get(evidence_id)
        return e is not None and e.tenant_id == self.tenant_id and e.readable_by(self.role_idx)

    # ---- deterministic candidate generation by index ----
    def candidates_for_subject(self, subject_type: int, subject_id: int) -> List[int]:
        return [eid for eid in self._by_subject.get((subject_type, subject_id), [])
                if self.authorized(eid)]

    def candidates_for_object(self, object_type: int, object_id: int) -> List[int]:
        return [eid for eid in self._by_object.get((object_type, object_id), [])
                if self.authorized(eid)]

    def all_authorized_ids(self) -> List[int]:
        return [eid for eid in self._by_id if self.authorized(eid)]

    def provenance(self, evidence_id: int):
        e = self._by_id.get(evidence_id)
        return None if e is None else (e.document_id, e.section_id, e.source_span, e.source_authority)
