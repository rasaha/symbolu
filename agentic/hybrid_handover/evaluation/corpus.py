#!/usr/bin/env python3
"""
Adversarial enterprise corpora — one synthetic dataset per retrieval failure
mode. These are DELIBERATELY hard: each embeds a specific way a sovereign
extractor can produce an incomplete or misleading evidence packet.

ALL DATA IS SYNTHETIC. No real contracts, parties, or figures.

Ground truth (`expected_*`) describes what a *correct, enterprise-safe* system
should do — it is NOT tuned to what the current deterministic extractor happens
to achieve. The gap between the two is exactly what the evaluation measures.
"""

from __future__ import annotations

from agentic.hybrid_handover.schema import Corpus, Document, ResolvedAnswer

from .cases import EvalCase, PrecedenceReq, RequiredSpan

_Q = "Can we terminate for convenience, and what notice and penalty apply?"


def _doc(doc_id, citation, order, text, approx_tokens=50_000) -> Document:
    return Document(
        doc_id=doc_id, citation=citation, order=order, text=text,
        approx_tokens=approx_tokens,
    )


# 1 -------------------------------------------------------------------------- #
def case_later_amendment_override() -> EvalCase:
    """CONTROL-ish: the baseline long-range supersession (extractor handles it)."""
    corpus = Corpus(documents=[
        _doc("msa", "MSA §7.1 p.12", 0,
             "This Master Services Agreement governs the parties. "
             "Neither party may terminate for convenience. "
             "Termination is permitted only for uncured material breach."),
        _doc("amd4", "Amendment 4 §3 p.204", 2,
             "Amendment 4 revises termination. Section 7.1 is deleted and "
             "replaced: either party may terminate for convenience upon ninety "
             "(90) days prior written notice."),
        _doc("amd6", "Amendment 6 §2 p.331", 3,
             "Amendment 6 introduces an early-termination fee. Any termination "
             "for convenience shall carry a termination fee equal to three (3) "
             "months of fees."),
    ])
    return EvalCase(
        case_id="later_amendment_override", failure_mode="later amendment overrides earlier clause",
        question=_Q, corpus=corpus,
        expected_answer=ResolvedAnswer(termination_for_convenience="allowed", notice_days=90, penalty="3 months' fees"),
        required_decisive=[
            RequiredSpan(doc_id="msa", needle="Neither party may terminate for convenience"),
            RequiredSpan(doc_id="amd4", needle="either party may terminate for convenience"),
            RequiredSpan(doc_id="amd6", needle="termination fee equal to three (3) months"),
        ],
        required_precedence=[PrecedenceReq(superseded="MSA §7.1 p.12", superseded_by="Amendment 4 §3 p.204")],
        expected_doc_ids=["msa", "amd4", "amd6"], expected_routing="ESCALATE",
    )


# 2 -------------------------------------------------------------------------- #
def case_buried_exception() -> EvalCase:
    """A decisive exception buried in later prose; no keyword flags it."""
    corpus = Corpus(documents=[
        _doc("msa", "MSA §7.1 p.12", 0,
             "Either party may terminate for convenience upon sixty (60) days notice."),
        _doc("sched", "Schedule D §4 p.88", 1,
             "The parties agree to various operational schedules. "
             "This provision applies generally, except that during the Initial "
             "Term the customer is locked in and may not exit early."),
    ])
    return EvalCase(
        case_id="buried_exception", failure_mode="buried exception",
        question=_Q, corpus=corpus,
        expected_answer=ResolvedAnswer(termination_for_convenience="allowed", notice_days=60, penalty=None),
        required_decisive=[RequiredSpan(doc_id="msa", needle="Either party may terminate for convenience")],
        required_defeaters=[RequiredSpan(doc_id="sched", needle="except that during the Initial Term", kind="defeater",
                                         note="carve-out that gates the answer")],
        expected_doc_ids=["msa", "sched"], expected_routing="ESCALATE",
    )


# 3 -------------------------------------------------------------------------- #
def case_conflicting_definitions() -> EvalCase:
    """Two governing definitions of a key term conflict."""
    corpus = Corpus(documents=[
        _doc("msa", "MSA §1 p.3", 0,
             "Definitions. Confidential Information means written material "
             "marked confidential."),
        _doc("dpa", "DPA §1 p.51", 1,
             "For purposes of data protection, Confidential Information means "
             "any personal data, whether or not marked."),
        _doc("msa7", "MSA §7.1 p.12", 0,
             "Either party may terminate for convenience upon thirty (30) days notice."),
    ])
    return EvalCase(
        case_id="conflicting_definitions", failure_mode="conflicting definitions",
        question="What is the notice period, and how is Confidential Information defined?",
        corpus=corpus,
        expected_answer=ResolvedAnswer(termination_for_convenience="allowed", notice_days=30, penalty=None),
        required_decisive=[RequiredSpan(doc_id="msa7", needle="terminate for convenience")],
        required_definitions=[
            RequiredSpan(doc_id="msa", needle="Confidential Information means written material", kind="definition"),
            RequiredSpan(doc_id="dpa", needle="Confidential Information means", kind="definition"),
        ],
        expected_doc_ids=["msa", "dpa", "msa7"], expected_routing="ESCALATE",
    )


# 4 -------------------------------------------------------------------------- #
def case_order_of_precedence() -> EvalCase:
    """An explicit order-of-precedence clause decides a conflict."""
    corpus = Corpus(documents=[
        _doc("msa", "MSA §7.1 p.12", 0,
             "Either party may terminate for convenience upon ninety (90) days notice."),
        _doc("of", "Order Form §2 p.1", 1,
             "Termination for convenience requires thirty (30) days notice. "
             "In the event of any conflict, the Order Form governs over the MSA."),
    ])
    return EvalCase(
        case_id="order_of_precedence", failure_mode="order-of-precedence language",
        question=_Q, corpus=corpus,
        expected_answer=ResolvedAnswer(termination_for_convenience="allowed", notice_days=30, penalty=None),
        required_decisive=[RequiredSpan(doc_id="of", needle="thirty (30) days notice")],
        required_defeaters=[RequiredSpan(doc_id="of", needle="the Order Form governs over the MSA", kind="defeater")],
        required_precedence=[PrecedenceReq(superseded="MSA §7.1 p.12", superseded_by="Order Form §2 p.1")],
        expected_doc_ids=["msa", "of"], expected_routing="ESCALATE",
    )


# 5 -------------------------------------------------------------------------- #
def case_conflicting_versions() -> EvalCase:
    """Two documents both labelled 'Amendment 3' with different content."""
    corpus = Corpus(documents=[
        _doc("amd3a", "Amendment 3 (v1) p.150", 1,
             "Amendment 3. Either party may terminate for convenience upon sixty (60) days notice."),
        _doc("amd3b", "Amendment 3 (v2) p.150", 1,
             "Amendment 3. Neither party may terminate for convenience."),
    ])
    return EvalCase(
        case_id="conflicting_versions", failure_mode="conflicting document versions",
        question=_Q, corpus=corpus,
        expected_answer=ResolvedAnswer(termination_for_convenience="unknown", notice_days=None, penalty=None),
        required_decisive=[
            RequiredSpan(doc_id="amd3a", needle="terminate for convenience upon sixty (60)"),
            RequiredSpan(doc_id="amd3b", needle="Neither party may terminate for convenience"),
        ],
        expected_doc_ids=["amd3a", "amd3b"],
        expected_abstention=True, expected_routing="REFUSE",  # ambiguous version -> must refuse
    )


# 6 -------------------------------------------------------------------------- #
def case_duplicate_amendment() -> EvalCase:
    """Same amendment appears twice, one copy truncated mid-clause."""
    corpus = Corpus(documents=[
        _doc("amd4_full", "Amendment 4 p.204", 2,
             "Amendment 4. Either party may terminate for convenience upon ninety (90) days notice."),
        _doc("amd4_dup", "Amendment 4 (dup) p.204", 2,
             "Amendment 4. Either party may terminate for conv"),  # truncated
    ])
    return EvalCase(
        case_id="duplicate_amendment", failure_mode="duplicate amendments",
        question=_Q, corpus=corpus,
        expected_answer=ResolvedAnswer(termination_for_convenience="allowed", notice_days=90, penalty=None),
        required_decisive=[RequiredSpan(doc_id="amd4_full", needle="terminate for convenience upon ninety (90)")],
        expected_doc_ids=["amd4_full", "amd4_dup"], expected_routing="ESCALATE",
    )


# 7 -------------------------------------------------------------------------- #
def case_ocr_corruption() -> EvalCase:
    """The decisive clause is OCR-garbled in its source."""
    corpus = Corpus(documents=[
        _doc("msa", "MSA §7.1 p.12 (scanned)", 0,
             "Either party may terrninate for c0nvenience up0n ninety (90) days n0tice."),
    ])
    return EvalCase(
        case_id="ocr_corruption", failure_mode="OCR corruption",
        question=_Q, corpus=corpus,
        expected_answer=ResolvedAnswer(termination_for_convenience="allowed", notice_days=90, penalty=None),
        required_decisive=[RequiredSpan(doc_id="msa", needle="terrninate for c0nvenience")],
        expected_doc_ids=["msa"],
        expected_abstention=True, expected_routing="REFUSE",  # unreliable source -> should refuse
    )


# 8 -------------------------------------------------------------------------- #
def case_scanned_annex() -> EvalCase:
    """A decisive annex is present only as an un-OCR'd scanned image."""
    corpus = Corpus(documents=[
        _doc("msa", "MSA §7 p.12", 0,
             "Termination terms are set out in Annex A."),
        _doc("annexA", "Annex A p.400", 1, "[SCANNED IMAGE - NOT OCR'D]"),
    ])
    return EvalCase(
        case_id="scanned_annex", failure_mode="scanned annex (no OCR)",
        question=_Q, corpus=corpus,
        expected_answer=ResolvedAnswer(termination_for_convenience="unknown"),
        required_decisive=[RequiredSpan(doc_id="annexA", needle="")],
        expected_doc_ids=["msa", "annexA"],
        expected_abstention=True, expected_routing="REFUSE",
    )


# 9 -------------------------------------------------------------------------- #
def case_hidden_negation() -> EvalCase:
    """Negation flips the plain-reading meaning of a permissive-looking clause."""
    corpus = Corpus(documents=[
        _doc("msa", "MSA §7.1 p.12", 0,
             "In no event may either party terminate for convenience during the Term."),
    ])
    return EvalCase(
        case_id="hidden_negation", failure_mode="hidden negation",
        question=_Q, corpus=corpus,
        expected_answer=ResolvedAnswer(termination_for_convenience="prohibited"),
        required_decisive=[RequiredSpan(doc_id="msa", needle="In no event may either party terminate for convenience")],
        required_defeaters=[RequiredSpan(doc_id="msa", needle="In no event", kind="defeater")],
        expected_doc_ids=["msa"], expected_routing="ESCALATE",
    )


# 10 ------------------------------------------------------------------------- #
def case_conflicting_tables() -> EvalCase:
    """Prose and a table disagree on the penalty."""
    corpus = Corpus(documents=[
        _doc("msa", "MSA §7.3 p.12", 0,
             "Either party may terminate for convenience upon ninety (90) days notice. "
             "The early-termination fee shall equal three (3) months of fees."),
        _doc("tbl", "Fee Table Exhibit B p.60", 1,
             "Fee Schedule. Early-termination fee: six (6) months of fees."),
    ])
    return EvalCase(
        case_id="conflicting_tables", failure_mode="conflicting tables",
        question=_Q, corpus=corpus,
        expected_answer=ResolvedAnswer(termination_for_convenience="allowed", notice_days=90, penalty=None),
        required_decisive=[RequiredSpan(doc_id="msa", needle="three (3) months of fees")],
        required_defeaters=[RequiredSpan(doc_id="tbl", needle="six (6) months of fees", kind="defeater",
                                         note="table contradicts prose penalty")],
        expected_doc_ids=["msa", "tbl"], expected_routing="ESCALATE",
    )


# 11 ------------------------------------------------------------------------- #
def case_cross_document_reference() -> EvalCase:
    """The decisive figure lives behind a cross-document reference."""
    corpus = Corpus(documents=[
        _doc("msa", "MSA §7.3 p.12", 0,
             "Either party may terminate for convenience. The penalty is as set "
             "out in Schedule C."),
        _doc("schedC", "Schedule C p.70", 1,
             "Schedule C. The early-termination penalty is four (4) months of fees."),
    ])
    return EvalCase(
        case_id="cross_document_reference", failure_mode="cross-document reference",
        question=_Q, corpus=corpus,
        expected_answer=ResolvedAnswer(termination_for_convenience="allowed", penalty="4 months' fees"),
        required_decisive=[
            RequiredSpan(doc_id="msa", needle="penalty is as set out in Schedule C"),
            RequiredSpan(doc_id="schedC", needle="four (4) months of fees"),
        ],
        expected_doc_ids=["msa", "schedC"], referenced_docs=["Schedule C"],
        expected_routing="ESCALATE",
    )


# 12 ------------------------------------------------------------------------- #
def case_circular_reference() -> EvalCase:
    """A→B→A reference loop that never resolves the decisive term."""
    corpus = Corpus(documents=[
        _doc("a", "MSA §7 p.12", 0, "Termination fee is defined in Schedule C."),
        _doc("c", "Schedule C p.70", 1, "The termination fee is as defined in the MSA §7."),
    ])
    return EvalCase(
        case_id="circular_reference", failure_mode="circular references",
        question=_Q, corpus=corpus,
        expected_answer=ResolvedAnswer(termination_for_convenience="unknown"),
        required_decisive=[RequiredSpan(doc_id="a", needle="Termination fee is defined in Schedule C")],
        expected_doc_ids=["a", "c"], referenced_docs=["Schedule C"],
        expected_abstention=True, expected_routing="REFUSE",
    )


# 13 ------------------------------------------------------------------------- #
def case_missing_appendix() -> EvalCase:
    """A referenced appendix that carries the decisive term is absent."""
    corpus = Corpus(documents=[
        _doc("msa", "MSA §7.3 p.12", 0,
             "Either party may terminate for convenience. Fees are set out in Appendix 1."),
    ])
    return EvalCase(
        case_id="missing_appendix", failure_mode="missing appendix",
        question=_Q, corpus=corpus,
        expected_answer=ResolvedAnswer(termination_for_convenience="allowed", penalty=None),
        required_decisive=[RequiredSpan(doc_id="msa", needle="terminate for convenience")],
        expected_doc_ids=["msa"], referenced_docs=["Appendix 1"],
        expected_abstention=True, expected_routing="REFUSE",  # decisive doc missing
    )


# 14 ------------------------------------------------------------------------- #
def case_irrelevant_distractors() -> EvalCase:
    """CONTROL: decisive clause present, surrounded by unrelated documents."""
    corpus = Corpus(documents=[
        _doc("nda", "NDA p.1", 0, "The parties will keep information confidential for five years."),
        _doc("msa", "MSA §7.1 p.12", 1,
             "Either party may terminate for convenience upon ninety (90) days notice."),
        _doc("inv", "Invoice 2043 p.1", 2, "Amount due for services rendered in Q3."),
    ])
    return EvalCase(
        case_id="irrelevant_distractors", failure_mode="irrelevant distractor documents",
        question=_Q, corpus=corpus,
        expected_answer=ResolvedAnswer(termination_for_convenience="allowed", notice_days=90, penalty=None),
        required_decisive=[RequiredSpan(doc_id="msa", needle="terminate for convenience upon ninety (90)")],
        expected_doc_ids=["nda", "msa", "inv"], expected_routing="ESCALATE",
    )


# 15 ------------------------------------------------------------------------- #
def case_inconsistent_numbering() -> EvalCase:
    """Inconsistent section numbering obscures which clause governs."""
    corpus = Corpus(documents=[
        _doc("msa", "MSA §7.1 p.12", 0,
             "Section 7.1. Either party may terminate for convenience upon ninety (90) days notice."),
        _doc("amd", "Amendment 5 §7.01 p.250", 3,
             "Section 7.01 is amended: termination for convenience requires forty-five (45) days notice."),
    ])
    return EvalCase(
        case_id="inconsistent_numbering", failure_mode="inconsistent numbering",
        question=_Q, corpus=corpus,
        expected_answer=ResolvedAnswer(termination_for_convenience="allowed", notice_days=45, penalty=None),
        required_decisive=[RequiredSpan(doc_id="amd", needle="forty-five (45) days notice")],
        required_precedence=[PrecedenceReq(superseded="MSA §7.1 p.12", superseded_by="Amendment 5 §7.01 p.250")],
        expected_doc_ids=["msa", "amd"], expected_routing="ESCALATE",
    )


# 16 ------------------------------------------------------------------------- #
def case_policy_override() -> EvalCase:
    """A corporate policy overrides the contract clause."""
    corpus = Corpus(documents=[
        _doc("msa", "MSA §7.1 p.12", 0,
             "Either party may terminate for convenience upon ninety (90) days notice."),
        _doc("pol", "Corporate Policy GOV-12 p.2", 5,
             "Company policy prohibits termination for convenience of regulated-"
             "services contracts, notwithstanding any contract term to the contrary."),
    ])
    return EvalCase(
        case_id="policy_override", failure_mode="policy override",
        question=_Q, corpus=corpus,
        expected_answer=ResolvedAnswer(termination_for_convenience="prohibited"),
        required_decisive=[RequiredSpan(doc_id="msa", needle="terminate for convenience upon ninety (90)")],
        required_defeaters=[RequiredSpan(doc_id="pol", needle="notwithstanding any contract term", kind="defeater")],
        required_precedence=[PrecedenceReq(superseded="MSA §7.1 p.12", superseded_by="Corporate Policy GOV-12 p.2")],
        expected_doc_ids=["msa", "pol"], expected_routing="ESCALATE",
    )


ALL_CASE_BUILDERS = [
    case_later_amendment_override,
    case_buried_exception,
    case_conflicting_definitions,
    case_order_of_precedence,
    case_conflicting_versions,
    case_duplicate_amendment,
    case_ocr_corruption,
    case_scanned_annex,
    case_hidden_negation,
    case_conflicting_tables,
    case_cross_document_reference,
    case_circular_reference,
    case_missing_appendix,
    case_irrelevant_distractors,
    case_inconsistent_numbering,
    case_policy_override,
]


def all_cases() -> list[EvalCase]:
    return [b() for b in ALL_CASE_BUILDERS]


# Cases the current extractor is expected to handle cleanly — used as the base
# for deliberate fault injection (fail-closed testing).
CONTROL_CASE_IDS = ["later_amendment_override", "irrelevant_distractors"]
