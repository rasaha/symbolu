"""Deterministic tests for the Model Selection Policy experiment.

Covers the eight mandated behaviors:
  1. hard-constraint enforcement
  2. policy precedence
  3. score calculation
  4. fallback ordering
  5. explanation completeness
  6. evidence-provenance handling
  7. self-assessment field restrictions
  8. zero-eligible-model behavior

Run: python3 -m pytest model_selection_experiment/tests -q
"""

from __future__ import annotations

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
if PKG not in sys.path:
    sys.path.insert(0, PKG)

import baselines as bl  # noqa: E402
import metrics as met  # noqa: E402
import policy as pol  # noqa: E402
import simulator as sim  # noqa: E402
from common import load_corpus, load_policy, load_registry  # noqa: E402

REGISTRY = load_registry()
POLICY = load_policy()
CORPUS = load_corpus()
ENT = CORPUS["enterprise_policy"]
TELEM_MATURE = sim.telemetry_feed("mature")


def _task(**over):
    base = {
        "task_id": "unit", "task_class": "reasoning",
        "required_caps": {"reasoning": 1.0}, "input_tokens_k": 6,
        "business_priority": "balanced",
        "utility_weights": {"quality": 1.0, "cost": 0.45, "latency": 0.35},
        "acceptable_quality_threshold": 0.7, "hard_constraints": {}, "note": "",
    }
    base.update(over)
    return base


# --- 1. hard-constraint enforcement -----------------------------------------
def test_hard_constraint_enforcement_onprem():
    task = _task(hard_constraints={"require_on_prem": True})
    rec = bl.arm_F_policy(task, REGISTRY, ENT, TELEM_MATURE, POLICY, "mature")
    # only the on-prem model may be eligible
    assert rec["eligible"] == ["m_small_local"]
    assert rec["selected"] == "m_small_local"


def test_hard_constraint_never_selects_ineligible_across_corpus():
    for task in CORPUS["tasks"]:
        rec = bl.arm_F_policy(task, REGISTRY, ENT, TELEM_MATURE, POLICY, "mature")
        if rec["selected"] is not None:
            ok, _, _, _ = pol.hard_filter(REGISTRY["models"][rec["selected"]], task,
                                          pol.resolve_constraints(task, ENT))
            assert ok, f"{task['task_id']} selected an ineligible model"


# --- 2. policy precedence ----------------------------------------------------
def test_precedence_enterprise_policy_vetoes_best_quality():
    # external frontier is highest quality but on a non-approved provider.
    task = _task()
    rec = bl.arm_F_policy(task, REGISTRY, ENT, TELEM_MATURE, POLICY, "mature")
    assert "m_external_frontier" not in rec["eligible"]
    elim = {e["model"]: e for e in rec["eliminated"]}
    assert elim["m_external_frontier"]["provenance"] == "enterprise-hard-policy"
    # a high utility score can never resurrect it
    assert rec["selected"] != "m_external_frontier"


def test_precedence_allowing_provider_admits_frontier():
    ent = {"approved_providers": ENT["approved_providers"] + ["vendor_omega"]}
    task = _task()
    rec = bl.arm_F_policy(task, REGISTRY, ent, TELEM_MATURE, POLICY, "mature")
    assert "m_external_frontier" in rec["eligible"]


# --- 3. score calculation ----------------------------------------------------
def test_score_monotonic_in_quality():
    task = _task()
    model = REGISTRY["models"]["m_strong_reason"]
    s_lo = pol.score(model, task, 0.5, cost_ref=10.0, lat_ref=2000.0)
    s_hi = pol.score(model, task, 0.9, cost_ref=10.0, lat_ref=2000.0)
    assert s_hi["utility"] > s_lo["utility"]


def test_score_penalizes_cost_and_latency():
    task = _task()
    model = REGISTRY["models"]["m_strong_reason"]
    s = pol.score(model, task, 0.8, cost_ref=10.0, lat_ref=2000.0)
    assert s["components"]["cost_penalty"] <= 0
    assert s["components"]["latency_penalty"] <= 0


# --- 4. fallback ordering ----------------------------------------------------
def test_fallback_ordering_is_descending_utility():
    task = _task()
    rec = bl.arm_F_policy(task, REGISTRY, ENT, TELEM_MATURE, POLICY, "mature")
    utils = [s["utility"] for s in rec["scored"]]
    assert utils == sorted(utils, reverse=True)
    # fallback chain = scored order minus the winner
    assert rec["fallback_chain"] == [s["model"] for s in rec["scored"][1:]]
    assert rec["selected"] not in rec["fallback_chain"]


# --- 5. explanation completeness --------------------------------------------
def test_explanation_completeness_all_policy_records():
    for task in CORPUS["tasks"]:
        for arm in ("F", "G"):
            advisory = ({m: sim.advisory_feed(m, task) for m in sim.MODEL_IDS}
                        if arm == "G" else None)
            rec = bl.ARMS[arm](task, REGISTRY, ENT, TELEM_MATURE, POLICY, "mature", advisory)
            res = met.explanation_completeness(rec)
            assert res["complete"], f"{arm}/{task['task_id']}: {res['issues']}"


def test_explanation_detects_silent_drop():
    task = _task()
    rec = bl.arm_F_policy(task, REGISTRY, ENT, TELEM_MATURE, POLICY, "mature")
    # corrupt the record: drop an eliminated entry -> partition breaks
    rec["eliminated"] = rec["eliminated"][:-1] if rec["eliminated"] else rec["eliminated"]
    if rec["eliminated"] != []:
        assert not met.explanation_completeness(rec)["complete"]


# --- 6. evidence-provenance handling ----------------------------------------
def test_every_scored_model_records_evidence_provenance():
    task = _task()
    rec = bl.arm_F_policy(task, REGISTRY, ENT, TELEM_MATURE, POLICY, "mature")
    for s in rec["scored"]:
        assert s["evidence"], "no evidence recorded"
        provs = {e["provenance"] for e in s["evidence"]}
        assert provs <= {"provider-declared", "benchmark-measured", "runtime-observed",
                         "model-advisory"}
        # mature regime must include runtime-observed telemetry evidence
        assert "runtime-observed" in provs


def test_conflicting_evidence_resolved_by_confidence_weight():
    # Inject a controlled conflict: high-confidence telemetry that disagrees
    # sharply with declared/benchmark evidence must dominate the fused estimate.
    task = _task()
    model = REGISTRY["models"]["m_strong_reason"]
    no_tel = pol.fuse_quality(model, task, {}, POLICY, advisory=None)["predicted_quality"]
    conflicting = {"m_strong_reason": {"reasoning": {"estimate": 0.20, "n": 5000}}}
    with_tel = pol.fuse_quality(model, task, conflicting, POLICY, advisory=None)["predicted_quality"]
    # a strong low-quality signal from high-confidence telemetry pulls the estimate down
    assert with_tel < no_tel
    # and pulls it a substantial fraction of the way toward the telemetry value
    assert with_tel < (no_tel + 0.20) / 2


# --- 7. self-assessment field restrictions ----------------------------------
def test_self_assessment_rejects_forbidden_fields():
    task = _task()
    bad_advisory = {m: {"suitability_estimate": 0.9, "price": 0.01} for m in sim.MODEL_IDS}
    with pytest.raises(pol.SelfAssessmentViolation):
        bl.arm_G_policy_selfassess(task, REGISTRY, ENT, TELEM_MATURE, POLICY, "mature", bad_advisory)


def test_self_assessment_allowed_fields_pass():
    task = _task()
    ok_advisory = {m: sim.advisory_feed(m, task) for m in sim.MODEL_IDS}
    rec = bl.arm_G_policy_selfassess(task, REGISTRY, ENT, TELEM_MATURE, POLICY, "mature", ok_advisory)
    assert rec["selected"] is not None
    assert rec["advisory_used"]


# --- 8. zero-eligible-model behavior ----------------------------------------
def test_zero_eligible_abstains_not_crashes():
    # on-prem required AND image modality -> no model qualifies
    task = _task(task_class="extraction", required_caps={"extraction": 1.0},
                 hard_constraints={"require_on_prem": True, "require_modality": "image"})
    rec = bl.arm_F_policy(task, REGISTRY, ENT, TELEM_MATURE, POLICY, "mature")
    assert rec["eligible"] == []
    assert rec["abstained"] is True
    assert rec["selected"] is None
    assert rec["abstain_reason"]
    # abstaining on an empty set is scored as zero regret, not a violation
    rq = sim.regret_for_choice(task, None, ENT["approved_providers"], abstained=True)
    assert rq["regret"] == 0.0 and rq["violated"] is False


def test_determinism_repeat_route_identical():
    task = _task()
    a = bl.arm_F_policy(task, REGISTRY, ENT, TELEM_MATURE, POLICY, "mature")
    b = bl.arm_F_policy(task, REGISTRY, ENT, TELEM_MATURE, POLICY, "mature")
    assert a == b
