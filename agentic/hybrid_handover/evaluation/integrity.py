#!/usr/bin/env python3
"""
Benchmark integrity checker (Phase C).

Verifies the benchmark's OWN ground truth is complete and self-consistent —
independent of any extractor. This does not measure an extractor; it audits the
cases. A clean integrity run is a precondition for trusting any baseline number.

Checks per case:
  * question and corpus are non-empty; at least one decisive span is declared
  * every required span's ``needle`` actually occurs in its source document
    (empty needle allowed only for a document that is intentionally unusable —
    scanned/parser-failed/marker text — i.e. a coverage-failure case)
  * every required span's ``doc_id`` exists in the corpus
  * every precedence relationship's citations resolve to real documents
  * every ``expected_doc_id`` exists in the corpus
  * abstention flag is consistent with the expected routing
  * routing value is a valid enum

Run:  python -m agentic.hybrid_handover.evaluation.integrity
"""

from __future__ import annotations

import re
import sys

from pydantic import BaseModel

from .cases import EvalCase
from .corpus import all_cases

_UNUSABLE_MARKERS = ("[scanned", "[parser failure", "[missing", "not ocr", "�")
_VALID_ROUTING = {"SERVE_IN_HOUSE", "ESCALATE", "REFUSE"}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


class Issue(BaseModel):
    case_id: str
    severity: str  # ERROR | WARN | INFO
    check: str
    detail: str


def _doc_is_unusable(text: str) -> bool:
    low = text.lower()
    return any(m in low for m in _UNUSABLE_MARKERS)


def check_case(case: EvalCase) -> list[Issue]:
    issues: list[Issue] = []
    cid = case.case_id

    def err(check, detail):
        issues.append(Issue(case_id=cid, severity="ERROR", check=check, detail=detail))

    def warn(check, detail):
        issues.append(Issue(case_id=cid, severity="WARN", check=check, detail=detail))

    if not case.question.strip():
        err("question", "empty question")
    if not case.corpus.documents:
        err("corpus", "empty corpus")
    if not case.required_decisive:
        err("ground_truth", "no decisive evidence declared")

    doc_ids = {d.doc_id for d in case.corpus.documents}
    citations = " || ".join(_norm(d.citation) for d in case.corpus.documents)

    # required spans exist
    for grp_name, grp in (
        ("decisive", case.required_decisive),
        ("defeater", case.required_defeaters),
        ("definition", case.required_definitions),
    ):
        for rs in grp:
            if rs.doc_id not in doc_ids:
                err("span_doc", f"{grp_name} span references unknown doc_id {rs.doc_id!r}")
                continue
            doc = case.corpus.by_id(rs.doc_id)
            if rs.needle == "":
                if not _doc_is_unusable(doc.text):
                    err("empty_needle",
                        f"{grp_name} span in {rs.doc_id!r} has empty needle but the doc is not "
                        f"marked unusable — accidental ambiguity")
                continue
            if _norm(rs.needle) not in _norm(doc.text):
                err("span_text",
                    f"{grp_name} needle not found in {rs.doc_id!r}: {rs.needle!r}")

    # precedence citations resolve
    for pr in case.required_precedence:
        if _norm(pr.superseded) not in citations:
            err("precedence", f"superseded citation not in corpus: {pr.superseded!r}")
        if _norm(pr.superseded_by) not in citations:
            err("precedence", f"governing citation not in corpus: {pr.superseded_by!r}")

    # expected docs exist
    for did in case.expected_doc_ids:
        if did not in doc_ids:
            err("coverage", f"expected_doc_id not in corpus: {did!r}")

    # abstention consistency
    if case.expected_abstention != (case.expected_routing == "REFUSE"):
        err("abstention",
            f"expected_abstention={case.expected_abstention} inconsistent with "
            f"expected_routing={case.expected_routing!r}")

    if case.expected_routing not in _VALID_ROUTING:
        err("routing", f"invalid routing {case.expected_routing!r}")

    # informational: intentionally-unresolved references (the point of some cases)
    for ref in case.referenced_docs:
        resolved = any(
            _norm(ref) in _norm(d.citation) or
            (_norm(ref) in _norm(d.text) and not _doc_is_unusable(d.text))
            for d in case.corpus.documents
        )
        if not resolved and case.expected_routing != "REFUSE":
            warn("reference", f"referenced doc {ref!r} does not resolve but case is not expected to refuse")

    return issues


class IntegrityReport(BaseModel):
    ok: bool
    n_cases: int
    errors: list[Issue]
    warnings: list[Issue]


def check_all() -> IntegrityReport:
    errors: list[Issue] = []
    warnings: list[Issue] = []
    cases = all_cases()
    for case in cases:
        for issue in check_case(case):
            (errors if issue.severity == "ERROR" else warnings).append(issue)
    return IntegrityReport(ok=not errors, n_cases=len(cases), errors=errors, warnings=warnings)


def main() -> int:
    rep = check_all()
    print(f"Benchmark integrity — {rep.n_cases} cases")
    print(f"  errors  : {len(rep.errors)}")
    print(f"  warnings: {len(rep.warnings)}")
    for i in rep.errors:
        print(f"  ERROR [{i.case_id}] {i.check}: {i.detail}")
    for i in rep.warnings:
        print(f"  WARN  [{i.case_id}] {i.check}: {i.detail}")
    print("OK" if rep.ok else "INTEGRITY FAILURES PRESENT")
    return 0 if rep.ok else 1


if __name__ == "__main__":
    sys.exit(main())
