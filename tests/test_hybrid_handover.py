#!/usr/bin/env python3
"""Tests for the two-tier hybrid-LLM enterprise handover scaffold."""

from __future__ import annotations

import json

import pytest

from agentic.hybrid_handover import (
    HandoverRefused,
    InHouseExtractor,
    LeakError,
    MockFrontierModel,
    assert_no_leak,
    decide_escalation,
    ground_spans,
    packet_only_reresolve,
    redact,
    rehydrate,
    run_handover,
)
from agentic.hybrid_handover.fixtures import QUESTION, SECRETS, build_corpus


# --------------------------------------------------------------------------- #
# Part 1 — in-house distillation + long-range supersession                    #
# --------------------------------------------------------------------------- #
def test_inhouse_resolves_long_range_supersession():
    corpus = build_corpus()
    packet = InHouseExtractor().extract(QUESTION, corpus)
    ra = packet.resolved_answer
    # MSA prohibits; Amendment 4 (much later) overrides; Amendment 6 sets penalty.
    assert ra.termination_for_convenience == "allowed"
    assert ra.notice_days == 90
    assert ra.penalty == "3 months' fees"
    assert any(c.clause == "termination_for_convenience" for c in packet.conflicts_resolved)


def test_coverage_reports_full_corpus_size():
    corpus = build_corpus()
    packet = InHouseExtractor().extract(QUESTION, corpus)
    # ~250K tokens ingested in-house; only a handful of spans distilled out.
    assert packet.coverage.tokens_ingested > 200_000
    assert packet.coverage.spans_returned < 12


# --------------------------------------------------------------------------- #
# Gate A — grounding                                                          #
# --------------------------------------------------------------------------- #
def test_grounding_passes_for_honest_extractor():
    corpus = build_corpus()
    packet = InHouseExtractor().extract(QUESTION, corpus)
    assert ground_spans(packet, corpus).ok


def test_grounding_catches_tampered_span():
    corpus = build_corpus()
    packet = InHouseExtractor().extract(QUESTION, corpus)
    # Corrupt one quote so it no longer matches its char_span.
    packet.evidence[0].quote = packet.evidence[0].quote + " [fabricated]"
    report = ground_spans(packet, corpus)
    assert not report.ok
    assert report.ungrounded


# --------------------------------------------------------------------------- #
# Gate B — packet-only faithfulness ("did we drop the needle?")               #
# --------------------------------------------------------------------------- #
def test_faithfulness_passes_when_packet_is_complete():
    corpus = build_corpus()
    extractor = InHouseExtractor()
    packet = extractor.extract(QUESTION, corpus)
    assert packet_only_reresolve(packet, extractor).ok


def test_faithfulness_catches_dropped_needle():
    corpus = build_corpus()
    extractor = InHouseExtractor()
    packet = extractor.extract(QUESTION, corpus)
    # Simulate a distillation that keeps the verdict "allowed" but drops the
    # Amendment 4 override span it depended on. Packet-only re-resolution should
    # then disagree with the stated (full-corpus) verdict.
    packet.evidence = [s for s in packet.evidence if s.doc_id != "amd4"]
    report = packet_only_reresolve(packet, extractor)
    assert not report.ok
    assert report.full.key() != report.packet_only.key()


def test_pipeline_refuses_on_dropped_needle():
    corpus = build_corpus()
    extractor = InHouseExtractor()
    frontier = MockFrontierModel()

    class DropNeedleExtractor(InHouseExtractor):
        def extract(self, question, corpus):
            packet = super().extract(question, corpus)
            packet.evidence = [s for s in packet.evidence if s.doc_id != "amd4"]
            return packet

    with pytest.raises(HandoverRefused) as exc:
        run_handover(QUESTION, corpus, SECRETS, DropNeedleExtractor(), frontier)
    assert exc.value.gate == "faithfulness"


# --------------------------------------------------------------------------- #
# Gate C — redaction / sovereignty                                            #
# --------------------------------------------------------------------------- #
def test_redaction_removes_all_secrets_from_egress():
    corpus = build_corpus()
    packet = InHouseExtractor().extract(QUESTION, corpus)
    redacted, rmap = redact(packet, SECRETS)
    blob = redacted.model_dump_json()
    for real in SECRETS:
        assert real not in blob  # no real value crosses the boundary
    # map is inverse and stays in-house
    assert rmap.mapping == {ph: real for real, ph in SECRETS.items()}


def test_assert_no_leak_blocks_surviving_secret():
    with pytest.raises(LeakError):
        assert_no_leak("... signed by Globex Corporation ...", SECRETS.keys())


def test_rehydrate_round_trips():
    corpus = build_corpus()
    packet = InHouseExtractor().extract(QUESTION, corpus)
    redacted, rmap = redact(packet, SECRETS)
    text = "Counterparty ‹VENDOR› owes ‹PENALTY_AMT› to ‹CUSTOMER›."
    hydrated = rehydrate(text, rmap)
    assert "Globex Corporation" in hydrated
    assert "$450,000" in hydrated
    assert "‹VENDOR›" not in hydrated


# --------------------------------------------------------------------------- #
# Escalation decision                                                         #
# --------------------------------------------------------------------------- #
def test_lookup_with_confident_spans_serves_in_house():
    corpus = build_corpus()
    packet = InHouseExtractor().extract(QUESTION, corpus)
    assert decide_escalation(packet, task_type="lookup", min_confidence=0.9) == "SERVE_IN_HOUSE"


def test_interpretation_escalates():
    corpus = build_corpus()
    packet = InHouseExtractor().extract(QUESTION, corpus)
    assert decide_escalation(packet, task_type="interpretation") == "ESCALATE"


# --------------------------------------------------------------------------- #
# End-to-end                                                                  #
# --------------------------------------------------------------------------- #
def test_end_to_end_handover_produces_hydrated_answer():
    corpus = build_corpus()
    result = run_handover(
        QUESTION, corpus, SECRETS, InHouseExtractor(), MockFrontierModel(),
        task_type="interpretation",
    )
    assert result.audit.escalated
    assert result.audit.leak_check == "pass"
    # big context in-house, tiny context egressed
    assert result.audit.corpus_tokens > 200_000
    assert result.audit.egress_tokens_est < 2_000
    assert result.audit.reduction_ratio > 100
    # final answer is re-hydrated (real values restored in-house)
    assert "Globex Corporation" in result.final_answer or "$450,000" in result.final_answer


def test_serve_in_house_never_egresses():
    corpus = build_corpus()
    result = run_handover(
        QUESTION, corpus, SECRETS, InHouseExtractor(), MockFrontierModel(),
        task_type="lookup",
    )
    assert not result.audit.escalated
    assert result.audit.egress_tokens_est == 0
