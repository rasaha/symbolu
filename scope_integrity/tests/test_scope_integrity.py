"""Test suite (M6). Locks the headline claims as assertions. Deterministic; no live calls. Consumes
the FROZEN ClaimIntegrity downstream adapter read-only; does not touch prior artifacts.
"""
from dataclasses import asdict

from claim_integrity import dataset as cdata, downstream, baselines as cbaselines
from scope_integrity import dataset, variants

SC = [asdict(e) for e in dataset.all_examples()]
GEN = [asdict(e) for e in cdata.all_examples()]


def test_corpus_shape():
    assert dataset.DATASET_VERSION == "sc_corpus_v1"
    assert len(SC) == 520
    assert sum(e["heldout"] for e in SC) == 168
    assert sum(e["ambiguity_flag"] for e in SC) == 120


def test_frozen_adapter_baselines():
    """Sanity: the frozen adapter scores preserve-whole high and oracle clean on this corpus."""
    whole = downstream.score_method(SC, lambda e: [e["original_text"]])
    oracle = downstream.score_method(SC, lambda e: [g["text"] for g in e["gold_claims"]])
    assert whole["unsafe_delivery_rate"] > 0.4
    assert oracle["unsafe_delivery_rate"] == 0.0


def test_gated_extension_eliminates_general_residual():
    """THE decisive claim: the gated extension reduces the general ClaimIntegrity residual (0.068) to
    0.000 with no rise in false-rejection or evidence-query."""
    base = downstream.score_method(GEN, cbaselines.BASELINES["P_claim_integrity"])
    h = downstream.score_method(GEN, variants.variant_h_integrated)
    assert base["unsafe_delivery_rate"] > 0.06
    assert h["unsafe_delivery_rate"] == 0.0
    assert h["false_rejection_rate"] <= base["false_rejection_rate"]
    assert h["evidence_query_altered_rate"] <= base["evidence_query_altered_rate"]


def test_ungated_variants_are_undeployable_on_general():
    """The honesty check: ungated scope-carry variants make the general corpus WORSE, not better."""
    for name in ["B_naive", "C_subject", "D_subject_qualifier", "E_full_scope", "F_preserve_flag",
                 "G_hybrid"]:
        s = downstream.score_method(GEN, variants.VARIANTS[name])
        assert s["unsafe_delivery_rate"] > 0.1, name   # all far above the 0.068 baseline


def test_gated_extension_reduces_scope_corpus():
    a = downstream.score_method(SC, variants.VARIANTS["A_current"])
    h = downstream.score_method(SC, variants.variant_h_integrated)
    assert h["unsafe_delivery_rate"] < a["unsafe_delivery_rate"]
    assert h["evidence_query_altered_rate"] == 0.0    # reference resolution preserved


def test_postposed_exception_is_load_bearing():
    """Ablation lock: removing postposed-exception carry reverts the general corpus to the residual."""
    from scope_integrity.variants import SCOPE_ELEMENTS
    without = downstream.score_method(
        GEN, lambda e: variants.variant_h_integrated(e, enabled=SCOPE_ELEMENTS - {"postfix_exception"}))
    assert without["unsafe_delivery_rate"] > 0.06     # residual returns


def test_improvement_not_from_abstention():
    """The gated extension SPLITS provable cases; it does not just preserve-whole everything."""
    split_more = 0
    for e in SC:
        a = variants.VARIANTS["A_current"](e)
        h = variants.variant_h_integrated(e)
        if len(h) > len(a):
            split_more += 1
    assert split_more > 100     # it actively splits, not abstains


def test_preserves_reference_resolution():
    """No produced claim begins with a dangling pronoun (reference resolution composed in)."""
    for e in SC:
        for c in variants.variant_h_integrated(e):
            assert not c.lower().lstrip().startswith(("it ", "they ", "this is")), (e["example_id"], c)


def test_deterministic():
    a = variants.variant_h_integrated(SC[0])
    b = variants.variant_h_integrated(SC[0])
    assert a == b


def test_complexity_is_small():
    """The winning mechanism is a small extension, not a heavyweight component: bounded regex rules."""
    import inspect
    src = inspect.getsource(variants)
    assert src.count("re.compile") < 15     # a handful of patterns, not a parser
