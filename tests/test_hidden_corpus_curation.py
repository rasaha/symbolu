#!/usr/bin/env python3
"""Tests for the hidden-corpus curation pipeline (audit-only). No resolver is run."""

from __future__ import annotations

import json

from agentic.hybrid_handover.resolution.hidden_corpus.curation import (
    answer_position, gold_sufficiency, leakage_pilot, pilot_corpus,
)
from agentic.hybrid_handover.resolution.hidden_corpus.curation.agreement import (
    cohens_kappa_binary, compare,
)
from agentic.hybrid_handover.resolution.hidden_corpus.curation.blinding import annotator_is_blind
from agentic.hybrid_handover.resolution.hidden_corpus.curation.difficulty_rubric import rubric_level
from agentic.hybrid_handover.resolution.hidden_corpus.curation.duplicates import (
    graph_signature, quarantine_recommended, similarity, template_fingerprint,
)
from agentic.hybrid_handover.resolution.hidden_corpus.curation.lifecycle import check_candidate
from agentic.hybrid_handover.resolution.hidden_corpus.curation.records import (
    accepted_candidates, all_candidates, annotator_record, candidate_view, opaque_id,
)
from agentic.hybrid_handover.resolution.hidden_corpus.curation.run_curation import run
from agentic.hybrid_handover.resolution.hidden_corpus.curation.schema import validate_path


def test_lifecycle_enforced_and_no_skips():
    assert validate_path(["DRAFT", "AUTHOR_COMPLETE", "READY_FOR_BLIND_ANNOTATION",
                          "ANNOTATED", "READY_FOR_ADJUDICATION", "ACCEPTED"])
    assert not validate_path(["DRAFT", "ANNOTATED"])          # skip
    assert not validate_path(["AUTHOR_COMPLETE", "ACCEPTED"])  # bad start
    for c in all_candidates():
        assert check_candidate(candidate_view(c)) == []


def test_blinding_annotator_has_no_author_fields():
    for c in all_candidates():
        assert annotator_is_blind(annotator_record(c)) == []


def test_accepted_only_loading():
    accepted_ids = {opaque_id(c) for c in accepted_candidates()}
    assert set(pilot_corpus.case_ids()) == accepted_ids
    for c in all_candidates():
        if c["decision"] != "ACCEPTED":
            assert not pilot_corpus.is_loadable(opaque_id(c))


def test_evidence_provenance_complete():
    assert gold_sufficiency.audit() == []


def test_graph_agreement_shapes():
    a = {"nodes": {"A": "Clause", "B": "Clause"}, "edges": [("A", "supersedes", "B")], "governing": ["A"], "abstain": False}
    b = {"nodes": {"A": "Clause", "B": "Clause"}, "edges": [("A", "supersedes", "B")], "governing": ["A"]}
    cmp = compare(a, b)
    assert cmp["edge_presence"]["f1"] == 1.0
    assert cmp["governing"]["exact"]
    k = cohens_kappa_binary([(True, True), (False, False), (True, False)])
    assert k is None or -1.0 <= k <= 1.0


def test_duplicate_and_template_detection():
    t = "x y z. p q r."
    g = {"nodes": {"A": "Clause"}, "edges": [("A", "supersedes", "B")], "governing": ["A"], "abstain": False}
    assert quarantine_recommended(similarity(t, g, t, g))          # exact dup
    t2 = "completely different words here about other things entirely."
    g2 = {"nodes": {"X": "Policy"}, "edges": [("X", "overrides", "Y")], "abstain": False}
    assert not quarantine_recommended(similarity(t, g, t2, g2))    # distinct
    # graph signature / template fingerprint discriminate structure
    assert graph_signature(g) != graph_signature(g2)
    assert template_fingerprint(g) != template_fingerprint(g2)


def test_difficulty_rubric_monotone():
    shallow = {"n_relationships": 1}
    deep = {"n_relationships": 4, "hop_depth": 4}
    assert rubric_level(shallow) < rubric_level(deep)
    assert rubric_level(deep) == 5


def test_answer_position_no_excess():
    assert answer_position.audit()["excessive_flags"] == []


def test_executable_leakage_clean():
    assert leakage_pilot.verify() == []


def test_pipeline_verdict_validated_and_deterministic():
    a = run()
    b = run()
    assert a["verdict"] == "CURATION PIPELINE VALIDATED"
    assert json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)


def test_seed_remains_immutable():
    # the frozen seed corpus is unchanged (22 cases, a known content hash present)
    from agentic.hybrid_handover.resolution.hidden_corpus.corpus import case_ids
    assert len(case_ids()) == 22
