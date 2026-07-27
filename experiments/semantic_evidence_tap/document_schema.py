"""
document_schema.py — unstructured document representation + the §4 semantic-challenge taxonomy.

A Document carries free-text `body` plus a hidden `truth` list: the ground-truth (field, value,
interpretation_status, challenge, span) tuples the body encodes. Extractors/interpreters only see
`body`; `truth` is used solely to score them. Challenge tags force the corpus beyond keyword matching.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Dict, Optional

DOC_TYPES = ("purchase_request", "policy_document", "approval_email", "vendor_record", "invoice",
             "exception_request", "meeting_note", "contract_clause", "audit_event")

# §4 semantic challenges
CHALLENGES = ("explicit", "paraphrase", "implicit_approval", "requested_vs_granted",
              "active_vs_superseded", "ambiguous_date", "exception_modifies", "conflicting_authority",
              "incomplete", "cross_reference", "similar_not_equivalent", "distractor", "negation",
              "conditional", "quoted_claim", "retrospective_correction")

# fields that are always deterministically parseable vs those needing interpretation
DETERMINISTIC_FIELDS = ("amount", "date", "document_id", "policy_version", "explicit_status",
                        "named_authority", "approval_record_exists")
INTERPRETED_FIELDS = ("creates_obligation", "exception_applies", "clauses_conflict",
                      "approval_is_conditional", "wording_authorizes", "approval_granted")


@dataclass
class Fact:
    field: str
    value: object
    interpretation_status: str          # EXACT / INFERRED / AMBIGUOUS / CONFLICTED / INSUFFICIENT_EVIDENCE
    challenge: str
    span: str                           # the exact substring in the body supporting the fact


@dataclass
class Document:
    doc_id: str
    tenant_id: int
    doc_type: str
    body: str
    truth: List[Fact] = field(default_factory=list)
    subject_id: int = -1
    access_roles: int = 0xffff


@dataclass
class Workflow:
    workflow_id: str
    documents: List[Document]
    # linkage back to the frozen outcome example (for downstream scoring)
    frozen_ex: Dict = field(default_factory=dict)
