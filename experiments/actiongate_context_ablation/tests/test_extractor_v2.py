"""Tests for the multi-stage extractor (v2) and its instability improvement."""

from __future__ import annotations

import pytest

from actiongate_context_ablation import (
    adapter, ablation, extractor_v2, metrics, milestone_bench as MB,
    semantic_extractor, structured_extractor, validator_extractor,
)
from actiongate_context_ablation.corpus import registry
from actiongate_context_ablation.corpus.schema import HELDOUT


@pytest.fixture(scope="module")
def items():
    return registry.load_all()


@pytest.fixture(scope="module")
def sp():
    return adapter.default_signed_policy()


def test_stage1_structured_is_paraphrase_invariant():
    # JSON and table facts parse regardless of surrounding prose
    frag, keys = structured_extractor.extract('{"sink_approved": true}')
    assert frag["args"]["sink_approved"] is True and "sink_approved" in keys
    frag2, keys2 = structured_extractor.extract("| affected | 8000 records |")
    assert frag2["args"]["affected_count"] == "8000"


def test_stage2_and_stage3_are_different_methods():
    # Stage 2 = token frames; Stage 3 = char-trigram similarity. A paraphrase Stage 2
    # frame catches should also register in Stage 3 sims, but via a different path.
    text = "two leads put their names on the change"     # dual approval paraphrase
    assert "appr_dual" in semantic_extractor.detect(text)
    sims = validator_extractor.sims(text)
    assert sims["appr_dual"] > sims["appr_single"]        # fuzzy agrees, independently


def test_no_cross_concept_bleed_on_clean_phrasing():
    # "Approved by the security lead (single approver)" must NOT yield dual/sink.
    ex = extractor_v2.extract_unit("Approved by the security lead (single approver).")
    assert "appr_single" in ex.concepts
    assert "appr_dual" not in ex.concepts
    assert "sink_approved" not in ex.concepts


def test_mutex_single_xor_dual():
    ex = extractor_v2.extract_unit("dual control approval from security and sre leads")
    assert ("appr_dual" in ex.concepts) and ("appr_single" not in ex.concepts)


def test_fail_closed_keeps_uncertain_fact():
    # a fact Stage 2 finds but Stage 3 does not strongly confirm is still kept
    ex = extractor_v2.extract_unit("CI produced a provenance-stamped image for this rollout.")
    assert "artifact" in ex.concepts


def test_v2_reduces_heldout_instability(items, sp):
    ho = [it for it in items if it.split == HELDOUT]
    v1 = metrics.aggregate([ablation.run_ablations(it.context, sp) for it in ho])
    v2 = metrics.aggregate([ablation.run_ablations(
        it.context, sp, realistic_spec_fn=extractor_v2.realistic_spec_v2) for it in ho])
    assert v2.extractor_instability_rate < 0.10
    assert v2.extractor_instability_rate < v1.extractor_instability_rate


def test_targets_met():
    b = MB.run_bench()
    t = MB.evaluate_targets(b)
    assert t["heldout_instability_below_10pct"]
    assert t["all_domains_instability_below_10pct"]
    assert t["heldout_recall_is_1"]
    assert t["heldout_precision_gain_substantial"]


def test_adversarial_distractor_injection(items, sp):
    # Inject a non-critical distractor sentence into each held-out context; instability
    # must stay < 10% and the fact detection must not break.
    from actiongate_context_ablation.units import Context, SemanticUnit
    ho = [it for it in items if it.split == HELDOUT]
    perturbed = []
    for it in ho:
        extra = SemanticUnit(id="adv_noise", source_type="sentence",
                             text="Unrelated: the office coffee machine was serviced on Tuesday.")
        perturbed.append(Context(id=it.item_id + "_adv", base=it.context.base,
                                 units=it.context.units + (extra,),
                                 data_origin=it.context.data_origin,
                                 linked_pairs=it.context.linked_pairs))
    agg = metrics.aggregate([ablation.run_ablations(
        c, sp, realistic_spec_fn=extractor_v2.realistic_spec_v2) for c in perturbed])
    assert agg.extractor_instability_rate < 0.10


def test_extractor_v2_deterministic():
    a = extractor_v2.extract_unit("A high-fidelity deployment simulation passed.")
    b = extractor_v2.extract_unit("A high-fidelity deployment simulation passed.")
    assert a == b
