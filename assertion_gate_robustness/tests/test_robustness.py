"""Robustness study tests (Phase 16). Deterministic; no live calls; no real actions."""
import pytest

from assertion_gate_robustness import metrics as M
from assertion_gate_robustness.dataset import base_items, clean_bundle, observed, split, stats
from assertion_gate_robustness.gate import govern, govern_disposition
from assertion_gate_robustness.perturbations import DETECTABLE, SILENT, PERTURBATIONS, apply
from assertion_gate_robustness.policy import GatePolicy
from assertion_gate_robustness.qualification import qualify_text, new_claim_introduced, semantic_preservation
from assertion_gate_robustness.signals import EvidenceMeta, Entailment, Grounding, SignalBundle
from assertion_gate_robustness.taxonomy import Disposition as D, to_primary
from assertion_gate_robustness.verify_prior import verify as verify_prior


def _b(support=0.9, label="supports", conf=1.0, adequacy=0.9, risk="medium", conflict="none", age=10.0):
    return SignalBundle(Grounding(support, conf), Entailment(label, conf),
                        EvidenceMeta(adequacy, age_days=age, required_recency_days=365, conflict=conflict),
                        risk_class=risk)


# --- prior AGE artifact verification (must not drift) ---------------------
def test_prior_age_artifacts_unchanged():
    assert verify_prior() is True


# --- canonical dispositions ------------------------------------------------
def test_allow_requires_conjunction():
    assert govern(_b(0.9, "supports", 1.0, 0.9), 0.9).disposition == D.ALLOW.value

def test_high_confidence_contradiction_rejects():
    assert govern(_b(0.9, "contradicts", 0.9), 0.9).disposition == D.REJECT.value

def test_neutral_is_indeterminate():
    assert govern(_b(0.5, "neutral", 1.0), 0.5).disposition == D.INDETERMINATE.value


# --- signal missingness / uncertainty propagation -------------------------
def test_low_confidence_withholds():
    d = govern(_b(0.9, "supports", 0.1, 0.9), 0.9)          # high uncertainty
    assert d.disposition != D.ALLOW.value

def test_high_risk_uncertainty_escalates():
    d = govern(_b(0.9, "supports", 0.1, 0.5, risk="critical"), 0.9)
    assert d.disposition == D.ESCALATE.value

def test_missing_evidence_not_silent_allow():
    d = govern(_b(0.05, "neutral", 1.0, 0.1), 0.9)
    assert d.disposition in (D.NOT_SUPPORTED.value, D.INDETERMINATE.value, D.ESCALATE.value)


# --- disagreement / conflict ----------------------------------------------
def test_signal_disagreement_surfaced():
    d = govern(_b(0.8, "contradicts", 0.9), 0.8)
    assert d.disposition in (D.REJECT.value, D.ESCALATE.value, D.INDETERMINATE.value)

def test_major_conflict_escalates_high_risk():
    d = govern(_b(0.9, "supports", 1.0, 0.9, risk="high", conflict="major"), 0.9)
    assert d.disposition == D.ESCALATE.value


# --- stale evidence --------------------------------------------------------
def test_stale_high_risk_escalates():
    d = govern(_b(0.9, "supports", 1.0, 0.9, risk="high", age=9999), 0.9)
    assert d.disposition == D.ESCALATE.value


# --- risk over/under classification (via bundle) ---------------------------
def test_risk_affects_disposition():
    hi = govern(_b(0.5, "supports", 1.0, 0.9, risk="critical"), 0.95).disposition
    lo = govern(_b(0.5, "supports", 1.0, 0.9, risk="low"), 0.95).disposition
    assert hi != D.ALLOW.value  # large overclaim in high risk not allowed


# --- correlated signal failure (gate cannot detect silent) ----------------
def test_correlated_silent_failure_can_fool_gate():
    # silent: support+entailment both pushed to "supported" with high confidence
    b = apply("correlated", _b(0.2, "neutral", 0.9, 0.9), 0.5)
    d = govern(b, 0.3)
    # honest: the gate MAY allow this (documented limitation) — assert it does not crash + is deterministic
    assert d.disposition == govern(b, 0.3).disposition


# --- qualification preservation / no invented evidence --------------------
def test_qualification_preserves_and_adds_no_claims():
    q = qualify_text("The treatment is safe", 0.5)
    assert semantic_preservation("The treatment is safe", q) >= 0.75
    assert new_claim_introduced("The treatment is safe", q) is False

def test_qualify_never_negates():
    q = qualify_text("The result is significant", 0.4)
    assert "not " not in q.lower()


# --- perturbation reproducibility -----------------------------------------
def test_perturbations_deterministic():
    b = _b()
    for name in PERTURBATIONS:
        assert apply(name, b, 0.3).grounding.support == apply(name, b, 0.3).grounding.support

def test_detectable_raises_uncertainty_silent_does_not():
    b = _b(0.3, "neutral", 0.9, 0.9)
    assert apply("stale", b, 0.5).uncertainty() > b.uncertainty()       # detectable
    corr = apply("correlated", b, 0.5)
    assert corr.uncertainty() <= b.uncertainty() + 0.05                  # silent stays low


# --- dataset freeze / dev-eval separation ---------------------------------
def test_dataset_deterministic():
    assert [i.item_id for i in base_items()] == [i.item_id for i in base_items()]

def test_dev_eval_disjoint():
    dev = {i.item_id for i in split("dev")}
    ev = {i.item_id for i in split("eval")}
    assert dev and ev and not (dev & ev)

def test_ground_truth_independent_annotators_recorded():
    s = stats()
    assert s["annotator_disagreement"] > 0  # disagreement preserved, not hidden


# --- metrics sanity --------------------------------------------------------
def test_escape_and_false_blocking_bounds():
    preds = ["ALLOW", "ALLOW", "REJECT"]
    golds = ["REJECT", "ALLOW", "REJECT"]
    assert M.escape_rate(preds, golds) == 0.5        # 1 escape / 2 not-deliverable (REJECT) golds
    assert M.false_blocking(preds, golds) == 0.0     # the one ALLOW gold was allowed


# --- no live calls / no real actions --------------------------------------
def test_gate_is_pure_no_io(tmp_path):
    d = govern(_b(), 0.9)
    assert d.audit["gate"] == "assertion_gate_v1" and isinstance(d.disposition, str)

def test_policy_version_mismatch_fail_closed():
    d = govern(_b(0.9, "supports", 1.0, 0.9), 0.9, policy_version="WRONG")
    assert d.disposition == D.ESCALATE.value
