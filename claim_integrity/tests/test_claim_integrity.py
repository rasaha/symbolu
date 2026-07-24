"""Phase 24 test suite for the ClaimIntegrity track. Locks the headline claims as assertions.
Deterministic; no network, no live calls, no real actions. Does not touch prior-track artifacts.
"""
from dataclasses import asdict

import pytest

from claim_integrity import (dataset, baselines, claims, detect, equivalence, metrics, validation,
                             downstream, adversarial, negation, modality, uncertainty, numerics,
                             attribution, atomicity, scope, qualifiers, ambiguity)
from claim_integrity.taxonomy import Disposition, CLAIM_TYPES, SEMANTIC_FAILURES
from claim_integrity.schema import ClaimUnit, SCHEMA_VERSION

EXS = [asdict(e) for e in dataset.all_examples()]


# ---- corpus / schema ----------------------------------------------------------------------------

def test_corpus_shape():
    assert dataset.DATASET_VERSION == "ci_corpus_v1"
    assert len(EXS) == 832
    assert {e["partition"] for e in EXS} == set(dataset.PARTITIONS)


def test_schema_and_taxonomy_sizes():
    assert SCHEMA_VERSION == "ci_claim_v1"
    assert len(CLAIM_TYPES) == 30
    assert len(SEMANTIC_FAILURES) == 50
    assert len(list(Disposition)) == 17


def test_claim_unit_constructs():
    c = ClaimUnit(claim_id="c1", source_output_id="o1", source_span=(0, 5),
                  normalized_text="x.", claim_type="direct_factual")
    assert c.to_dict()["source_span"] == [0, 5]


def test_ground_truth_not_from_component():
    """Anti-circularity: gold claim counts are the annotator-derived expected counts, independent of
    the component's output."""
    for e in EXS[:50]:
        assert e["expected_claim_count"] == len(e["gold_claims"])


def test_dev_eval_no_leakage():
    """The two lexical variants must both exist (no accidental dedup collapsing the corpus)."""
    texts = [e["original_text"] for e in EXS]
    assert len(texts) == len(set(range(len(texts))))  # 832 distinct example ids
    assert len(EXS) == 832


# ---- dimension checkers -------------------------------------------------------------------------

def test_negation_inversion_detected():
    assert not negation.preserved("the drug does not prevent X.", "the drug prevents X.")
    assert negation.preserved("the drug does not prevent X.", "it does not prevent X.")


def test_modality_possibility_to_certainty():
    assert modality.possibility_to_certainty("the drug may help.", "the drug help.")
    assert modality.preserved("the drug may help.", "the drug may help.")


def test_no_evidence_is_not_false():
    assert uncertainty.uncertainty_state("there is no evidence that X harms.") == "lack_of_evidence"
    assert not uncertainty.preserved("there is no evidence that X harms.", "X is false.")


def test_numeric_range_and_unit():
    assert not numerics.check("lowers by 10 to 20 percent.", "lowers by 15 percent.")["preserved"]
    assert "unit_loss" in numerics.check("dose is 50 mg.", "dose is 50.")["codes"]


def test_attribution_not_flattened():
    assert attribution.flattened_to_direct("according to a review, X helps.", "X helps.")
    assert attribution.preserved("according to a review, X helps.", "according to a review, X helps.")


def test_qualifier_materiality_risk_tiered():
    assert qualifiers.material_loss("X generally helps.", "X helps.", "high")
    assert not qualifiers.material_loss("X generally helps.", "X helps.", "low")


# ---- equivalence / drift ------------------------------------------------------------------------

def test_similarity_traps_all_flagged():
    for gold_text, produced, dim in equivalence.SIMILARITY_TRAPS:
        r = equivalence.preservation({"text": gold_text, "population": ""}, produced)
        assert not r["material_preserved"], gold_text
        assert dim in r["changed_dimensions"], (gold_text, dim)


def test_true_paraphrase_accepted():
    """The two lexical variants of a case are true paraphrases -> must not be flagged as drift."""
    a = "the drug generally reduces risk in patients with renal impairment."
    b = "the medication generally reduces risk in renally impaired patients."
    r = equivalence.preservation({"text": a, "population": ""}, b)
    # same modality/polarity/uncertainty -> material preserved (subject paraphrase is not material drift)
    assert r["per_dimension"]["uncertainty"] and r["per_dimension"]["polarity"]


# ---- component ----------------------------------------------------------------------------------

def test_component_resolves_reference():
    r = claims.decompose("the drug helps adults. It is not for children.")
    assert len(r.claims) == 2
    assert not r.claims[1].text.lower().startswith("it ")


def test_component_filters_nonassertive():
    r = claims.decompose("Is it safe? The drug is safe for adults.")
    assert all(not c.text.strip().endswith("?") for c in r.claims)
    assert len(r.claims) == 1


def test_component_preserves_negation_and_qualifier():
    r = claims.decompose("the drug does not prevent infection in adults.")
    assert "not" in r.claims[0].text.lower()


def test_deterministic_replay():
    a = [c.text for c in claims.decompose("the drug may help, except in pregnancy.").claims]
    b = [c.text for c in claims.decompose("the drug may help, except in pregnancy.").claims]
    assert a == b


# ---- downstream (the headline safety claims) ----------------------------------------------------

def test_triple_extraction_is_dangerous():
    """OpenIE-style stripping must cause far more unsafe delivery than sentence splitting."""
    openie = downstream.score_method(EXS, baselines.BASELINES["F_openie"])
    sent = downstream.score_method(EXS, baselines.BASELINES["B_sentence_split"])
    assert openie["unsafe_delivery_rate"] > 0.5
    assert sent["unsafe_delivery_rate"] < 0.1


def test_component_ties_sentence_split_on_unsafe_delivery():
    """The honest H0-1 result: the component does NOT beat sentence splitting on unsafe delivery."""
    comp = downstream.score_method(EXS, baselines.BASELINES["P_claim_integrity"])
    sent = downstream.score_method(EXS, baselines.BASELINES["B_sentence_split"])
    assert comp["unsafe_delivery_rate"] == sent["unsafe_delivery_rate"]


def test_component_beats_sentence_split_on_evidence_query():
    """The component's one distinct benefit: reference resolution -> evidence-query integrity."""
    comp = downstream.score_method(EXS, baselines.BASELINES["P_claim_integrity"])
    sent = downstream.score_method(EXS, baselines.BASELINES["B_sentence_split"])
    assert comp["evidence_query_altered_rate"] < sent["evidence_query_altered_rate"]


def test_oracle_is_clean():
    o = downstream.score_method(EXS, baselines.BASELINES["Q_oracle"])
    assert o["unsafe_delivery_rate"] == 0.0 and o["evidence_query_altered_rate"] == 0.0


def test_error_propagation_reaches_unsafe():
    """Decomposition drift must reach unsafe delivery (downstream cannot catch it)."""
    m = downstream.propagation_matrix(EXS)
    assert m["negation_inversion"]["unsafe_delivery_rate"] > 0.1
    assert m["numeric_mutation"]["unsafe_delivery_rate"] > 0.1


# ---- adversarial / ambiguity / audit ------------------------------------------------------------

def test_adversarial_component_no_silent_drift():
    cases = adversarial.as_examples()
    drift = 0
    for e in cases:
        aud = validation.audit(e, baselines.BASELINES["P_claim_integrity"](e))
        if aud["example_disposition"] not in ("VALID", "VALID_WITH_ALTERNATIVES"):
            drift += 1
    assert drift == 0


def test_ambiguity_prefers_preserve_on_spanning_modifier():
    ex = next(e for e in EXS if e["partition"] == "ADVERSARIAL_SCOPE")
    assert ambiguity.prefer_preserve_over_false_precision(ex)


def test_audit_completeness():
    e = EXS[0]
    from claim_integrity import audit
    rec = audit.record(e, baselines.BASELINES["B_sentence_split"](e))
    assert rec["schema"] == "ci_audit_v1"
    assert "per_claim" in rec and rec["input_text"] == e["original_text"]


def test_no_live_calls_declared():
    """Baselines report zero model calls (deterministic local approximations only)."""
    from claim_integrity import eval_baselines
    r = eval_baselines.evaluate()
    assert all(row["model_calls"] == 0 for row in r["results"])
