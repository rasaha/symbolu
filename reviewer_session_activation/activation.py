"""Real reviewer calibration-round activation driver.

Operational activation of the ALREADY-FROZEN reviewer workflow. Consumes reviewer_ready_pilot,
reviewer_calibration_pilot, and minimal_evidence_policy READ-ONLY. Builds no new review infrastructure and
modifies no frozen component.

Flow:
  Phase 1  verify_frozen_state()   - guards, freeze manifests, ActionGate vocabulary, threshold drift.
  Phase 2  eligibility.evaluate_roster() - real-reviewer eligibility gate.
  Gate     decide()                - only proceeds to training/qualification/calibration if BOTH phases
                                     pass. Otherwise returns a blocked activation and one decision-gate
                                     outcome. This driver NEVER fabricates reviewers, reviews, or metrics.

Because a real calibration round requires real qualified reviewers, an activation with no eligible real
reviewers stops at the gate: no training, no qualification, no calibration, no human metrics are produced -
those remain NOT EVALUATED / NOT ENOUGH COMPLETED HUMAN REVIEWS. Deterministic, stdlib-only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from reviewer_ready_pilot import (verify_prior_artifacts as rrp_guard,
                                  verify_evaluation_freeze as rrp_freeze,
                                  policy_runner, stop_conditions)
from reviewer_calibration_pilot import verify_prior_artifacts as rcp_guard
from reviewer_session_activation import eligibility

# decision-gate outcomes (exactly one is returned)
D_OPEN_FINAL = "OPEN FROZEN FINAL HUMAN REVIEW SET"
D_REPEAT_GUIDE = "REPEAT CALIBRATION AFTER GUIDE CLARIFICATION"
D_REPEAT_RETRAIN = "REPEAT CALIBRATION AFTER REVIEWER RETRAINING"
D_FIX_METADATA = "FIX SOURCE METADATA BEFORE CONTINUING"
D_FIX_INTERFACE = "FIX REVIEW INTERFACE BEFORE CONTINUING"
D_POLICY_TRACK = "POLICY REVISION REQUIRES A SEPARATE TRACK"
D_NOT_ENOUGH = "NOT ENOUGH COMPLETED HUMAN REVIEWS"
D_STOP_SAFETY = "STOP FOR SAFETY OR GOVERNANCE FAILURE"
D_DO_NOT_PROCEED = "DO NOT PROCEED"


@dataclass
class FrozenStateReport:
    ok: bool
    checks: List[Dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {"ok": self.ok, "checks": self.checks}


def _check(name: str, ok: bool, detail: str = "") -> Dict[str, Any]:
    return {"check": name, "ok": bool(ok), "detail": detail}


def verify_frozen_state() -> FrozenStateReport:
    checks: List[Dict[str, Any]] = []

    # 1 prior-artifact guards
    rrp_ok = rrp_guard.verify()
    rcp_ok = rcp_guard.verify()
    checks.append(_check("prior_artifact_guard_reviewer_ready", rrp_ok, f"{len(rrp_guard.FROZEN)} guarded"))
    checks.append(_check("prior_artifact_guard_reviewer_calibration", rcp_ok, f"{len(rcp_guard.FROZEN)} guarded"))

    # 2 frozen minimal-policy version
    from minimal_evidence_policy import classifier as mep
    d = mep.classify({"artifact_id": "probe", "text": "t", "risk_tier": "high",
                      "claim_family": "measured_performance"})
    pol_ok = d.policy_version == "minimal_evidence_policy_v1"
    checks.append(_check("frozen_minimal_policy_version", pol_ok, d.policy_version))

    # 3 reviewer-guide version (freeze config pins it)
    guide_ok = rrp_freeze.FUTURE_EVAL_CONFIG.get("label_schema_version") == "reviewer_label_v1" \
        and rrp_freeze.FUTURE_EVAL_CONFIG.get("interface_version") == "review_interface_v1"
    checks.append(_check("reviewer_guide_and_interface_version", guide_ok, "review_interface_v1"))

    # 4-6 training / calibration / final set hashes + 7 evaluation freeze
    freeze_ok = rrp_freeze.verify()
    checks.append(_check("evaluation_protocol_freeze", freeze_ok, "reviewer_ready future-eval freeze"))

    # 8 native ActionGate vocabulary preserved (6 outcomes, not collapsed)
    ag = policy_runner.NATIVE_ACTIONGATE_OUTCOMES
    ag_ok = len(ag) == 6 and set(ag) == {"ALLOW", "ALLOW_WITH_CONSTRAINTS", "DENY", "ESCALATE_TO_HUMAN",
                                         "REQUEST_MORE_EVIDENCE", "SIMULATE_AND_RETRY"}
    checks.append(_check("native_actiongate_vocabulary", ag_ok, f"{len(ag)} outcomes"))

    # 9 threshold drift
    frozen_cfg = rrp_freeze.FUTURE_EVAL_CONFIG.get("frozen_thresholds")
    drift_ok = frozen_cfg == stop_conditions.FROZEN_THRESHOLDS
    checks.append(_check("no_threshold_drift", drift_ok, "stop-condition thresholds == freeze"))

    return FrozenStateReport(ok=all(c["ok"] for c in checks), checks=checks)


@dataclass
class ActivationResult:
    activated: bool
    decision: str
    frozen_state: FrozenStateReport
    eligibility: eligibility.EligibilityReport
    stages_run: List[str]
    human_validation: str = "NOT_EVALUATED"
    external_pilot: str = "BLOCKED"
    production_readiness: str = "NOT_READY"
    final_set_may_open: bool = False
    note: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {"activated": self.activated, "decision": self.decision,
                "final_set_may_open": self.final_set_may_open,
                "frozen_state": self.frozen_state.as_dict(),
                "eligibility": self.eligibility.as_dict(),
                "stages_run": self.stages_run,
                "human_validation": self.human_validation, "external_pilot": self.external_pilot,
                "production_readiness": self.production_readiness, "note": self.note}


def activate(roster: Dict[str, Any], *, prohibited_artifacts: Optional[set] = None) -> ActivationResult:
    fs = verify_frozen_state()
    if not fs.ok:
        # Phase 1 drift is a mandatory stop.
        return ActivationResult(
            activated=False, decision=D_STOP_SAFETY, frozen_state=fs,
            eligibility=eligibility.EligibilityReport(False, [], 0, None, "not evaluated: frozen-state drift"),
            stages_run=["phase1_frozen_state"], final_set_may_open=False,
            note="Frozen-state verification failed; activation halted before touching reviewers.")

    elig = eligibility.evaluate_roster(roster, prohibited_artifacts=prohibited_artifacts)
    if not elig.activatable:
        # No real eligible reviewers -> cannot run training/qualification/calibration. Zero human reviews.
        return ActivationResult(
            activated=False, decision=D_NOT_ENOUGH, frozen_state=fs, eligibility=elig,
            stages_run=["phase1_frozen_state", "phase2_eligibility"], final_set_may_open=False,
            note="Activation blocked at the eligibility gate: no real, eligible reviewer roster was "
                 "supplied (fields are unfilled template placeholders). Per the frozen rules, reviewers "
                 "are never inferred or fabricated. No training, qualification, calibration, or human "
                 "metric was produced; all remain NOT EVALUATED.")

    # Both reviewers real + eligible: the session WOULD proceed to training -> qualification -> calibration.
    # Those stages require the reviewers' actual submitted responses, which are not present in this call;
    # the driver returns an activated session awaiting those real submissions. It never invents them.
    return ActivationResult(
        activated=True, decision=D_NOT_ENOUGH, frozen_state=fs, eligibility=elig,
        stages_run=["phase1_frozen_state", "phase2_eligibility", "phase3_training_ready",
                    "phase4_qualification_ready"],
        final_set_may_open=False,
        note="Roster is real and eligible; session activated and awaiting real reviewer training + "
             "qualification submissions. Until those real responses exist and qualification passes, "
             "completed human reviews = 0, so the final set may not open.")
