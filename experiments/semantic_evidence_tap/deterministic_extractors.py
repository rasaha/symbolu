"""
deterministic_extractors.py — exact parsing of explicitly-represented fields (§7 DETERMINISTIC).

Regex/rule extraction of amounts→tier, policy versions, explicit status, approval-record existence,
and subject ids directly from document text. Every record is EXACT with a verifiable source span; no
model inference. These fields are removed from LLM ownership.
"""
from __future__ import annotations

import re
from typing import List

from .document_schema import Document
from .evidence_schema import EvidenceRecord, EXACT, EXTRACT_DETERMINISTIC
from .corpus_generator import TIER_DOLLARS

DOLLARS_TIER = {v: k for k, v in TIER_DOLLARS.items()}
_AMOUNT = re.compile(r"\$([\d,]+)")
_VERSION = re.compile(r"Version (\d+)\.0")
_REQ = re.compile(r"request:(\d+)")


def _eid(doc, i):
    return f"{doc.doc_id}-E{i}"


def extract(doc: Document) -> List[EvidenceRecord]:
    recs: List[EvidenceRecord] = []
    body = doc.body

    if doc.doc_type == "purchase_request":
        m = _AMOUNT.search(body)
        if m:
            amt = int(m.group(1).replace(",", "")); tier = DOLLARS_TIER.get(amt)
            if tier is not None:
                recs.append(EvidenceRecord(_eid(doc, 0), doc.tenant_id, doc.doc_id, m.group(0),
                    doc.subject_id, "has_budget", tier, tier, 1, "active", 0, 10**9, None,
                    EXTRACT_DETERMINISTIC, 1.0, EXACT, field_name="budget_tier"))

    if doc.doc_type == "policy_document":
        mv = _VERSION.search(body)
        status = ("superseded" if "superseded" in body and "in effect" not in body and "in force" not in body
                  else "active")
        if mv:
            v = int(mv.group(1))
            recs.append(EvidenceRecord(_eid(doc, 0), doc.tenant_id, doc.doc_id, mv.group(0),
                doc.subject_id, "governed_by", v, v, v, status, 0, 10**9, None,
                EXTRACT_DETERMINISTIC, 1.0, EXACT, field_name="policy_version"))

    if doc.doc_type == "approval_email":
        mr = _REQ.search(body)
        recs.append(EvidenceRecord(_eid(doc, 0), doc.tenant_id, doc.doc_id,
            mr.group(0) if mr else "Re:", doc.subject_id, "authorized_by", -1, True, 1, "active",
            0, 10**9, None, EXTRACT_DETERMINISTIC, 1.0, EXACT, field_name="approval_record_exists"))

    return recs
