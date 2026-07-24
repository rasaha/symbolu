"""AGE tests: determinism, taxonomy, engine sanity, dataset integrity, and the key evaluation
invariants (AGE beats existing baselines; G_risk composition matches/beats AGE)."""
from assertion_governance.dataset import all_items, split, stats
from assertion_governance.engine import govern_item, govern, AssertionInput
from assertion_governance.evaluation import run, metrics
from assertion_governance.baselines import tune
from assertion_governance.taxonomy import Disposition, fail_closed, to_primary


def test_dataset_deterministic_and_balanced():
    a = [i.item_id for i in all_items()]
    b = [i.item_id for i in all_items()]
    assert a == b and len(a) == 343
    s = stats()
    assert set(s["by_relation"]) == {"supports", "contradicts", "neutral", "missing", "conflicting"}


def test_engine_deterministic():
    it = split("eval")[0]
    assert govern_item(it).disposition == govern_item(it).disposition


def test_engine_never_silent_allow_on_contradiction():
    d = govern(AssertionInput("X", claim_strength=0.9, evidence_support=0.9,
                              risk_class="critical", relation="contradicts"))
    assert d.disposition == "REJECT" and d.delivered_text == ""


def test_qualify_produces_rewrite():
    d = govern(AssertionInput("The treatment is safe", claim_strength=0.95,
                              evidence_support=0.5, risk_class="low", relation="supports"))
    assert d.disposition == "QUALIFY" and d.delivered_text and d.delivered_text != "The treatment is safe"


def test_fail_closed_default():
    assert fail_closed("critical").value == "ESCALATE"
    assert fail_closed("low").value == "INDETERMINATE"


def test_age_beats_existing_technique_baselines():
    r = run("eval")
    m = r["metrics"]
    age = m["AGE"]["agreement"]
    for b in ("A_none", "B_confidence", "C_grounding", "D_entailment", "E_rule_qualify",
              "F_authority", "G_ground_entail"):
        assert age > m[b]["agreement"] + 0.05, (b, m[b]["agreement"], age)


def test_age_does_not_beat_trivial_g_risk_composition():
    # the anti-circularity finding: a grounding+entailment+risk rule matches/beats the engine
    r = run("eval")
    assert r["metrics"]["G_risk"]["agreement"] >= r["metrics"]["AGE"]["agreement"]
    assert r["comparisons"]["AGE_vs_G_risk"]["a_only"] == 0  # AGE beats G_risk on ZERO items


def test_age_zero_unsupported_escape():
    r = run("eval")
    assert r["metrics"]["AGE"]["unsupported_escape_rate"] == 0.0


def test_age_not_over_escalating_on_adversarial():
    r = run("eval")
    assert r["adversarial_to_age"]["age_error_rate"] == 0.0


def test_value_over_G_is_risk_concentrated():
    # G (risk-blind) already perfect on low-risk; AGE's gain is on high-risk
    r = run("eval")
    assert r["metrics"]["G_ground_entail"]["agreement_low_risk"] == 1.0
    assert r["metrics"]["AGE"]["agreement_high_risk"] > r["metrics"]["G_ground_entail"]["agreement_high_risk"] + 0.05
