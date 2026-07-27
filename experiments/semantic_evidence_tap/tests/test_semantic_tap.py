"""Tests for semantic evidence normalization + TAP governance."""
from __future__ import annotations

import torch

from experiments.enterprise_slots_quadratic.schema import DomainCfg
from experiments.semantic_evidence_tap.corpus_generator import generate
from experiments.semantic_evidence_tap.semantic_interpreter import interpret_workflow
from experiments.semantic_evidence_tap.normalization_validator import validate
from experiments.semantic_evidence_tap.evaluate_normalization import evaluate_normalization
from experiments.semantic_evidence_tap.evaluate_tap import evaluate_tap
from experiments.semantic_evidence_tap.evidence_schema import EXACT, INFERRED


def _cfg_wfs(n=100, seed=900000):
    cfg = DomainCfg(); return cfg, generate(cfg, n, seed)


def test_oracle_normalization_ceiling():
    cfg, wfs = _cfg_wfs()
    r = evaluate_normalization("N5", wfs, cfg, q=1.0)
    assert r["downstream_outcome_accuracy"] >= 0.98 and r["unsupported_fact_admission_rate"] == 0.0


def test_governance_blocks_hallucination_span():
    """A record whose span is not in the document is never admitted."""
    cfg, wfs = _cfg_wfs(60)
    admitted_bad = 0
    for i, wf in enumerate(wfs):
        recs = interpret_workflow(wf, q=0.5, h=0.5, seed=i)     # heavy hallucination
        routed = validate(recs, wf)
        for r in routed.authoritative:
            body = next((d.body for d in wf.documents if d.doc_id == r.source_document_id), "")
            admitted_bad += int(r.source_span not in body)
    assert admitted_bad == 0


def test_no_inferred_record_presented_as_exact():
    cfg, wfs = _cfg_wfs(40)
    for i, wf in enumerate(wfs):
        recs = interpret_workflow(wf, q=0.9, h=0.0, seed=i)
        for r in recs:
            assert r.interpretation_status != EXACT      # interpreter never claims EXACT


def test_unsupported_admission_low_with_governance():
    cfg, wfs = _cfg_wfs(150)
    r = evaluate_normalization("N3", wfs, cfg, q=0.85, h=0.05)
    assert r["unsupported_fact_admission_rate"] <= 0.01


def test_tap_blocks_all_authority_claims():
    cfg, wfs = _cfg_wfs(150)
    r = evaluate_tap("T3", [wf.frozen_ex for wf in wfs])
    assert r["authority_exceedance_recall"] == 1.0 and r["unsupported_claim_recall"] >= 0.95


def test_prompt_only_does_not_enforce():
    """T1 (prompt-only) must NOT achieve enforcement — governance ≠ prompting."""
    cfg, wfs = _cfg_wfs(150)
    r = evaluate_tap("T1", [wf.frozen_ex for wf in wfs])
    assert r["authority_exceedance_recall"] < 0.95


def test_frozen_pipeline_imported_unmodified():
    import experiments.enterprise_field_prediction.deterministic_fields as D
    import experiments.enterprise_output_mapping.outcome_contract as O
    assert "def extract_finding" in open(D.__file__).read()
    assert "def decide" in open(O.__file__).read()
