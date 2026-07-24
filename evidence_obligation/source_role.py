"""Phase 4 - Source-role model.

Classifies WHAT KIND of source an artifact is, deterministically, from its path and content signals.
Source role is distinct from authority (authority.py): a role is a category; authority is what that
source can legitimately attest to. Fail-closed: an unclassifiable source is UNKNOWN (never authoritative).
"""
from __future__ import annotations

import re
from typing import Tuple

# canonical source roles
PRIMARY_IMPLEMENTATION = "primary_implementation"
TEST_ARTIFACT = "test_artifact"
GENERATED_DOCUMENTATION = "generated_documentation"
APPROVED_POLICY = "approved_policy"
DRAFT_POLICY = "draft_policy"
TECHNICAL_DESIGN_DOCUMENT = "technical_design_document"
OPERATIONAL_RUNBOOK = "operational_runbook"
TELEMETRY_OUTPUT = "telemetry_output"
AUDIT_LOG = "audit_log"
EXTERNAL_PRIMARY_AUTHORITY = "external_primary_authority"
EXTERNAL_SECONDARY_SOURCE = "external_secondary_source"
INTERNAL_OPINION = "internal_opinion"
USER_STATEMENT = "user_statement"
MODEL_GENERATED_TEXT = "model_generated_text"
UNKNOWN_SOURCE = "unknown_source"

SOURCE_ROLES = (
    PRIMARY_IMPLEMENTATION, TEST_ARTIFACT, GENERATED_DOCUMENTATION, APPROVED_POLICY, DRAFT_POLICY,
    TECHNICAL_DESIGN_DOCUMENT, OPERATIONAL_RUNBOOK, TELEMETRY_OUTPUT, AUDIT_LOG,
    EXTERNAL_PRIMARY_AUTHORITY, EXTERNAL_SECONDARY_SOURCE, INTERNAL_OPINION, USER_STATEMENT,
    MODEL_GENERATED_TEXT, UNKNOWN_SOURCE,
)

_TEST_PATH = re.compile(r"(^|/)(tests?|_test|test_)", re.I)
_DOC_EXT = re.compile(r"\.(md|rst|txt)$", re.I)
_CODE_EXT = re.compile(r"\.(py|js|ts|go|java|rs|c|cpp|h)$", re.I)
_DRAFT = re.compile(r"\b(draft|proposed|wip|tentative|rfc)\b", re.I)
_APPROVED = re.compile(r"\b(approved|ratified|signed|official policy|effective)\b", re.I)
_RUNBOOK = re.compile(r"\b(runbook|on-?call|incident response|escalation procedure)\b", re.I)
_DESIGN = re.compile(r"\b(design doc|architecture|rationale|trade-?off|we chose|decision record)\b", re.I)
_TELEMETRY = re.compile(r"\b(p50|p95|p99|throughput|latency_ms|rps|error rate|uptime)\b", re.I)
_AUDIT = re.compile(r"\b(audit log|audit trail|logged at|recorded event)\b", re.I)
_OPINION = re.compile(r"\b(i think|in my opinion|we believe|arguably|it seems)\b", re.I)


def classify_source_role(source_path: str, source_kind: str, text: str) -> Tuple[str, list]:
    """Deterministic source-role classification. Returns (role, reason_codes)."""
    codes = []
    p = source_path or ""
    t = text or ""

    # code files are primary implementation unless they are tests
    if _CODE_EXT.search(p):
        if _TEST_PATH.search(p):
            return TEST_ARTIFACT, ["ROLE.TEST_PATH"]
        if source_kind == "docstring":
            codes.append("ROLE.DOCSTRING_IN_CODE")
            return PRIMARY_IMPLEMENTATION, codes            # docstring documents the implementation
        if source_kind == "comment":
            return PRIMARY_IMPLEMENTATION, ["ROLE.CODE_COMMENT"]
        return PRIMARY_IMPLEMENTATION, ["ROLE.CODE_FILE"]

    # markdown / text: disambiguate by content signals
    if _DOC_EXT.search(p) or source_kind == "doc":
        if _APPROVED.search(t) and not _DRAFT.search(t):
            return APPROVED_POLICY, ["ROLE.APPROVED_MARKERS"]
        if _DRAFT.search(t):
            return DRAFT_POLICY, ["ROLE.DRAFT_MARKERS"]
        if _RUNBOOK.search(t):
            return OPERATIONAL_RUNBOOK, ["ROLE.RUNBOOK_MARKERS"]
        if _DESIGN.search(t):
            return TECHNICAL_DESIGN_DOCUMENT, ["ROLE.DESIGN_MARKERS"]
        if _TELEMETRY.search(t):
            return TELEMETRY_OUTPUT, ["ROLE.TELEMETRY_MARKERS"]
        if _AUDIT.search(t):
            return AUDIT_LOG, ["ROLE.AUDIT_MARKERS"]
        if _OPINION.search(t):
            return INTERNAL_OPINION, ["ROLE.OPINION_MARKERS"]
        return GENERATED_DOCUMENTATION, ["ROLE.GENERIC_DOC"]

    return UNKNOWN_SOURCE, ["ROLE.UNCLASSIFIED"]            # fail-closed
