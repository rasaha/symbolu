#!/usr/bin/env python3
"""Tests for the Hybrid Handover enterprise-readiness evaluation framework.

These tests validate the *framework* (that it measures and falsifies correctly),
not the extractor. They assert the framework exposes the known baseline gaps
rather than hiding them.
"""

from __future__ import annotations

import pytest

from agentic.hybrid_handover.inhouse import InHouseExtractor
from agentic.hybrid_handover.evaluation import (
    DEFAULT_VALIDATORS,
    ContradictionSearchValidator,
    CoverageValidator,
    SpanIntegrityValidator,
    all_cases,
    aggregate,
    evaluate_case,
    recall,
    run,
)
from agentic.hybrid_handover.evaluation.corpus import (
    case_conflicting_definitions,
    case_later_amendment_override,
    case_missing_appendix,
    case_ocr_corruption,
)
from agentic.hybrid_handover.evaluation.injectors import (
    ALL_INJECTORS,
    DropCriticalSpan,
    DuplicateWrongVersion,
    OCRNoise,
)

EX = InHouseExtractor()


# --- corpus / cases -------------------------------------------------------- #
def test_all_cases_build_and_are_synthetic():
    cases = all_cases()
    assert len(cases) == 16
    assert all(c.is_synthetic for c in cases)
    # every case declares ground-truth decisive evidence
    assert all(c.required_decisive for c in cases)


def test_case_ids_unique():
    ids = [c.case_id for c in all_cases()]
    assert len(ids) == len(set(ids))


# --- injectors are deterministic ------------------------------------------- #
def test_injectors_are_deterministic():
    case = case_later_amendment_override()
    for inj in ALL_INJECTORS:
        if inj.kind == "corpus":
            a = inj.apply_corpus(case.corpus).model_dump()
            b = inj.apply_corpus(case.corpus).model_dump()
        else:
            pkt = EX.extract(case.question, case.corpus)
            a = inj.apply_packet(pkt).model_dump()
            b = inj.apply_packet(pkt).model_dump()
        assert a == b, f"{inj.name} not deterministic"


def test_drop_critical_span_removes_verdict_span():
    case = case_later_amendment_override()
    pkt = EX.extract(case.question, case.corpus)
    dropped = DropCriticalSpan().apply_packet(pkt)
    assert not any("terminate for convenience" in s.quote.lower() for s in dropped.evidence)


# --- validators catch what they should ------------------------------------- #
def test_span_integrity_flags_bad_offset():
    case = case_later_amendment_override()
    pkt = EX.extract(case.question, case.corpus)
    pkt.evidence[0].char_span = (pkt.evidence[0].char_span[0] + 5, pkt.evidence[0].char_span[1])
    out = SpanIntegrityValidator().validate(case, pkt, case.corpus)
    assert not out.passed and out.blocks_handover


def test_coverage_blocks_ocr_and_missing():
    for builder in (case_ocr_corruption, case_missing_appendix):
        case = builder()
        pkt = EX.extract(case.question, case.corpus)
        out = CoverageValidator().validate(case, pkt, case.corpus)
        assert not out.passed and out.blocks_handover


def test_contradiction_search_flags_uncovered_defeater():
    # buried exception uses 'except' with no extractor keyword -> extractor misses it
    from agentic.hybrid_handover.evaluation.corpus import case_buried_exception
    case = case_buried_exception()
    pkt = EX.extract(case.question, case.corpus)
    out = ContradictionSearchValidator().validate(case, pkt, case.corpus)
    assert not out.passed  # the 'except...' clause is not in the packet


# --- harness classification ------------------------------------------------ #
def test_control_case_passes_clean():
    case = case_later_amendment_override()
    r = evaluate_case(case, EX, DEFAULT_VALIDATORS, "augmented")
    assert r.system_decision == "ESCALATE"
    assert not r.unsafe_handover
    assert r.decisive == (3, 3)
    assert r.precedence == (1, 1)


def test_conflicting_definitions_is_exposed_as_unsafe():
    # No validator enforces definition completeness -> this is a known gap and
    # the framework MUST surface it, not hide it.
    case = case_conflicting_definitions()
    r = evaluate_case(case, EX, DEFAULT_VALIDATORS, "augmented")
    assert r.definition == (0, 2)
    assert r.decisive_missing
    assert r.unsafe_handover  # accepted despite missing decisive definitions


def test_injected_dropcritical_fails_closed():
    case = case_later_amendment_override()
    r = evaluate_case(case, EX, DEFAULT_VALIDATORS, "augmented",
                      injector=DropCriticalSpan(), injected=True)
    assert r.decisive_missing
    assert r.system_decision == "REFUSE"  # grounding/faithfulness catch it
    assert not r.unsafe_handover


# --- independent validation reduces unsafe handovers ----------------------- #
def test_augmented_reduces_unsafe_vs_gates_only():
    cases = all_cases()
    gates = [evaluate_case(c, EX, DEFAULT_VALIDATORS, "gates_only") for c in cases]
    aug = [evaluate_case(c, EX, DEFAULT_VALIDATORS, "augmented") for c in cases]
    g_unsafe = sum(r.unsafe_handover for r in gates)
    a_unsafe = sum(r.unsafe_handover for r in aug)
    assert a_unsafe < g_unsafe  # validators demonstrably help
    assert a_unsafe > 0  # ...but do NOT close the gap — honest falsification


# --- end to end ------------------------------------------------------------ #
def test_run_produces_verdict_and_metrics():
    report = run()
    assert report["verdict"] in ("VALIDATED", "PARTIALLY VALIDATED", "FALSIFIED")
    # the baseline is not enterprise-ready: unsafe handover must be reported nonzero
    assert "augmented" in report["metrics"]
    assert report["meta"]["synthetic"] is True
    # definition recall gap is surfaced
    assert report["metrics"]["augmented"]["definition_recall"].startswith("0.0%")


def test_baseline_is_not_validated():
    report = run()
    # With the deterministic extractor, the design must NOT come back VALIDATED.
    assert report["verdict"] != "VALIDATED"
    assert report["verdict_reasons"]
