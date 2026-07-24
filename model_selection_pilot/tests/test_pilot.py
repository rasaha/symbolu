"""Deterministic tests for the shadow-pilot harness.

Covers the ten mandated behaviors:
  routing-time information boundary, hard-policy enforcement, minimum-quality
  eligibility, cost guard, provider-metadata provenance, telemetry versioning,
  fallback ordering, self-assessment field restrictions, decision-record
  consistency, zero-eligible-model behavior.

Run: python3 -m pytest model_selection_pilot/tests -q
"""
from __future__ import annotations

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)
if PKG not in sys.path:
    sys.path.insert(0, PKG)

from model_selection_pilot import advisory as adv  # noqa: E402
from model_selection_pilot import arms as arms  # noqa: E402
from model_selection_pilot import costguard as cg  # noqa: E402
from model_selection_pilot import execute as execute  # noqa: E402
from model_selection_pilot import metrics as met  # noqa: E402
from model_selection_pilot import policy as pol  # noqa: E402
from model_selection_pilot import registry as reg  # noqa: E402
from model_selection_pilot.build_corpus import build as build_corpus  # noqa: E402

REGISTRY = reg.build()
CORPUS = build_corpus()
SHADOW = CORPUS["shadow"]
MODELS = set(REGISTRY["models"])


def _hi_conf_snapshot(quality: float):
    snap = {"_version": "test:hi"}
    from model_selection_pilot.common import TASK_CLASSES
    for mid in REGISTRY["models"]:
        snap[mid] = {tc: {"quality_mean": quality, "schema_valid_rate": 1.0, "n": 50}
                     for tc in TASK_CLASSES}
    return snap


def _empty_snapshot():
    snap = {"_version": "test:cold"}
    from model_selection_pilot.common import TASK_CLASSES
    for mid in REGISTRY["models"]:
        snap[mid] = {tc: {"quality_mean": None, "schema_valid_rate": None, "n": 0} for tc in TASK_CLASSES}
    return snap


def _task(**over):
    base = {"task_id": "u1", "task_class": "classification", "input_tokens_k": 0.1,
            "business_priority": "balanced", "hard_constraints": {}, "min_acceptable_quality": 0.7,
            "required_schema": {"fields": ["label"]}, "label_set": ["a", "b"],
            "_oracle": {"label": "a"}}
    base.update(over)
    return base


# --- 1. routing-time information boundary -----------------------------------
def test_routing_view_strips_oracle():
    v = pol.routing_view(_task())
    assert "_oracle" not in v and "output" not in v and "score" not in v


def test_boundary_assert_raises_on_leak():
    v = pol.routing_view(_task())
    v["_oracle"] = {"x": 1}
    with pytest.raises(pol.InformationBoundaryError):
        pol._assert_boundary(v)


def test_route_ignores_oracle_presence():
    snap = _hi_conf_snapshot(0.9)
    a = pol.route(_task(), REGISTRY, snap, "mature", "F2")
    b = pol.route(_task(_oracle={"label": "z"}), REGISTRY, snap, "mature", "F2")
    assert a["selected"] == b["selected"] and a["eligible"] == b["eligible"]


# --- 2. hard-policy enforcement ---------------------------------------------
def test_onprem_eliminates_all_cloud_with_provenance():
    task = _task(hard_constraints={"require_on_prem": True})
    rec = pol.route(task, REGISTRY, _hi_conf_snapshot(0.9), "mature", "F2")
    assert rec["eligible"] == []
    provs = {e["provenance"] for e in rec["eliminated"]}
    assert provs == {"enterprise-hard-policy"}


def test_selected_never_violates_hard_constraints():
    snap = _hi_conf_snapshot(0.9)
    for task in SHADOW:
        rec = pol.route(task, REGISTRY, snap, "mature", "F2")
        if rec["selected"]:
            ok, *_ = pol.hard_and_technical_filter(rec["selected"], REGISTRY["models"][rec["selected"]],
                                                   pol.routing_view(task), REGISTRY["enterprise_policy"])
            assert ok


# --- 3. minimum-quality eligibility -----------------------------------------
def test_min_quality_gate_eliminates_low_predicted():
    snap = _hi_conf_snapshot(0.20)  # all models predicted 0.20 < min 0.7
    rec = pol.route(_task(min_acceptable_quality=0.7), REGISTRY, snap, "mature", "F2")
    assert rec["abstained"] is True
    gate_reasons = {e["constraint"] for e in rec["eliminated"] if e.get("stage") == "quality-gate"}
    assert "min_quality" in gate_reasons


def test_f1_does_not_gate_quality():
    snap = _hi_conf_snapshot(0.20)
    rec = pol.route(_task(min_acceptable_quality=0.7), REGISTRY, snap, "mature", "F1")
    # F1 keeps low-quality models eligible (no gate) and selects one
    assert rec["abstained"] is False and rec["selected"] is not None


# --- 4. cost guard ----------------------------------------------------------
def test_cost_guard_blocks_over_cap():
    g = cg.CostGuard(max_spend_usd=0.01)
    g.charge(0.009)
    with pytest.raises(cg.CostCapExceeded):
        g.check(0.005)


def test_dry_run_positive_and_bounded():
    dr = cg.dry_run(REGISTRY, SHADOW, execute.technically_eligible)
    assert dr["estimated_total_usd"] > 0
    assert dr["worst_case_usd"] >= dr["estimated_total_usd"]


# --- 5. provider-metadata provenance ----------------------------------------
def test_every_provider_fact_has_provenance():
    for mid, m in REGISTRY["models"].items():
        for field, meta in m["provider_facts"].items():
            for key in ("provenance", "source", "date_verified", "verification_status"):
                assert key in meta, f"{mid}.{field} missing {key}"


# --- 6. telemetry versioning ------------------------------------------------
def test_snapshots_versioned_and_regime_gated():
    from model_selection_pilot import telemetry as tele
    dev = CORPUS["dev"]
    fake = {t["task_id"]: {mid: {"quality": 0.7, "schema_valid": True}
                           for mid in REGISTRY["models"]} for t in dev}
    snaps = tele.build_snapshots(fake, dev, "vX")
    assert snaps["cold"]["_version"].endswith(":cold")
    any_cell = next(iter([c for mid in snaps["cold"] if mid != "_version"
                          for c in snaps["cold"][mid].values()]))
    assert any_cell["n"] == 0
    rec = pol.route(_task(), REGISTRY, snaps["mature"], "mature", "F2")
    assert rec["telemetry_version"] == snaps["mature"]["_version"]


# --- 7. fallback ordering ----------------------------------------------------
def test_fallback_descending_utility():
    rec = pol.route(_task(), REGISTRY, _hi_conf_snapshot(0.9), "mature", "F2")
    utils = [s["utility"] for s in rec["scored"]]
    assert utils == sorted(utils, reverse=True)
    assert rec["fallback_chain"] == [s["model"] for s in rec["scored"][1:]]
    assert rec["selected"] not in rec["fallback_chain"]


# --- 8. self-assessment field restrictions ----------------------------------
def test_advisory_validate_rejects_forbidden():
    with pytest.raises(adv.SelfAssessmentViolation):
        adv.validate({"anticipated_reasoning_difficulty": "low", "price": 0.01})


def test_route_g_rejects_forbidden_advisory():
    amap = {mid: {"anticipated_reasoning_difficulty": "low", "latency": 10} for mid in REGISTRY["models"]}
    with pytest.raises(adv.SelfAssessmentViolation):
        pol.route(_task(), REGISTRY, _hi_conf_snapshot(0.9), "mature", "G", amap)


# --- 9. decision-record consistency -----------------------------------------
def test_decision_records_complete_across_shadow():
    snap = _hi_conf_snapshot(0.85)
    for task in SHADOW:
        for mode in ("F2", "G"):
            amap = ({mid: {"anticipated_reasoning_difficulty": "medium"} for mid in REGISTRY["models"]}
                    if mode == "G" else None)
            rec = pol.route(task, REGISTRY, snap, "mature", mode, amap)
            assert met._explanation_complete(rec, MODELS), f"{mode}/{task['task_id']}"


# --- 10. zero-eligible-model behavior ---------------------------------------
def test_zero_eligible_abstains():
    # on-prem required -> no cloud model qualifies -> abstain, not crash
    task = _task(hard_constraints={"require_on_prem": True})
    rec = pol.route(task, REGISTRY, _hi_conf_snapshot(0.9), "mature", "F2")
    assert rec["eligible"] == [] and rec["abstained"] is True
    assert rec["selected"] is None and rec["abstain_reason"]


def test_determinism_repeat_identical():
    snap = _hi_conf_snapshot(0.8)
    a = pol.route(_task(), REGISTRY, snap, "mature", "F2")
    b = pol.route(_task(), REGISTRY, snap, "mature", "F2")
    assert a == b
