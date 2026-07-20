#!/usr/bin/env python3
"""Tests for the hidden relationship corpus (audit-only).

Verify integrity, leakage-freedom, data separation, and coverage. No resolver is
run and no resolver performance is asserted.
"""

from __future__ import annotations

import re

from agentic.hybrid_handover.schema import EvidenceSpan
from agentic.hybrid_handover.resolution.hidden_corpus.corpus import (
    case_ids, evidence_for, executable_cases,
)
from agentic.hybrid_handover.resolution.hidden_corpus.leakage import verify
from agentic.hybrid_handover.resolution.hidden_corpus.stats import statistics
from agentic.hybrid_handover.resolution.hidden_corpus.validate import validate


def test_corpus_integrity_clean():
    assert validate() == []


def test_leakage_clean():
    assert verify() == []


def test_executable_view_exposes_no_metadata():
    for c in executable_cases():
        assert set(c) == {"id", "question", "documents"}
        for d in c["documents"]:
            assert set(d) == {"doc_id", "citation", "order", "text"}


def test_ids_are_opaque():
    for cid in case_ids():
        assert re.match(r"^HX[0-9a-f]{10}$", cid)


def test_evidence_is_spans_only():
    for cid in case_ids():
        ev = evidence_for(cid)
        assert ev and all(isinstance(s, EvidenceSpan) for s in ev)


def test_order_does_not_encode_difficulty():
    from agentic.hybrid_handover.resolution.hidden_corpus.annotations import annotation
    diffs = [annotation(c["id"])["difficulty"] for c in executable_cases()]
    assert diffs != sorted(diffs) and diffs != sorted(diffs, reverse=True)


def test_all_capabilities_covered():
    s = statistics()
    assert s["blind_spots"]["capabilities_zero"] == []
    # negative controls and abstention present
    assert s["coverage_by_abstention"]["abstain"] >= 5
    assert len(s["negative_controls"]) >= 5
    assert s["coverage_by_ambiguity"]["ambiguous"] >= 5


def test_difficulty_levels_all_present():
    s = statistics()
    for lvl in range(1, 6):
        assert s["coverage_by_difficulty"][lvl] >= 1


def test_deterministic_ids():
    a = case_ids()
    b = case_ids()
    assert a == b
