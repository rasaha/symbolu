"""RA-5 production adversarial matrix (spec §13, §15; task Phases 13–17, 23).

Deny-heavy by design: the production path must fail closed on every row except
the single fully-supported one. Row 2 (caller-forged PASS) and the RA-1→RA-4 /
RA-4.5 baselines are the acceptance anchors.

The disposition under test is the Risk Engine recommendation derived from the
*trusted*, RA-re-checked control results the production path persists:
``ALLOW``/``ALLOW_WITH_CONDITIONS`` = "RA may proceed"; anything else = no
authority (DENY/ESCALATE). No row may yield ALLOW without genuine full support.
"""

from __future__ import annotations

import dataclasses
from datetime import timedelta

import pytest

from risk_authority.api.schemas import ControlResultInput, EvaluateRequest
from risk_authority.domain.enums import ControlStatus, RiskRecommendation
from risk_authority.domain.errors import RiskAuthorityError
from ugence_tap_provider.api import TapOutcome, TapRule

import ra5_scenario as C

PROCEED = (RiskRecommendation.ALLOW, RiskRecommendation.ALLOW_WITH_CONDITIONS)


def _evaluate(runtime, records, mapping=None, conditions=()):
    C.create_case(runtime)
    return runtime.submit_evidence_and_evaluate(
        C.TENANT, "rdc_prod_1", records, control_evidence=mapping, conditions=conditions
    )


# --- Row 1: the one success row -------------------------------------------
def test_row1_full_support_all_controls_pass_may_proceed(runtime):
    records, mapping = C.full_evidence_and_map()
    ev = _evaluate(runtime, records, mapping)
    assert ev.recommendation in PROCEED
    assert ev.failed_controls == ()
    trusted = runtime.trusted_controls(C.TENANT, "rdc_prod_1")
    assert len(trusted) == len(C.REQUIRED_CONTROLS)
    assert all(t.status is ControlStatus.PASS for t in trusted)
    # Every trusted result is fully bound and RA-re-checked.
    assert all(t.has_production_bindings() for t in trusted)


# --- Row 2: caller-forged PASS (THE central acceptance test, F-A) ---------
def test_row2_caller_forged_pass_without_evidence_cannot_produce_authority(runtime):
    # No admitted evidence, no assurance — a forged "PASS" has nowhere to enter.
    ev = _evaluate(runtime, ())
    assert ev.recommendation is RiskRecommendation.DENY
    statuses = {cid: st for cid, st in ev.failed_controls}
    assert all(st is ControlStatus.MISSING for st in statuses.values())
    # The persisted trusted set contains NO passing result.
    trusted = runtime.trusted_controls(C.TENANT, "rdc_prod_1")
    assert not any(t.status is ControlStatus.PASS for t in trusted)


def test_row2b_reference_evaluate_is_disabled_in_production(runtime):
    C.create_case(runtime)
    # Even a direct call to the reference path with a forged PASS fails closed.
    with pytest.raises(RiskAuthorityError):
        runtime.application.evaluate(
            C.TENANT,
            "rdc_prod_1",
            EvaluateRequest(
                control_results=tuple(
                    ControlResultInput(c, "PASS") for c in C.REQUIRED_CONTROLS
                )
            ),
        )


def test_forged_pass_but_evidence_says_unsupported_denies():
    # Real admitted evidence exists, but the evaluator says UNSUPPORTED for one
    # mandatory control. No caller status can override trusted assurance.
    rule = {"HUMAN_OVERSIGHT_VALID": TapRule(outcome=TapOutcome.UNSUPPORTED, evidence_coverage=1.0)}
    runtime = C.build_runtime(tap_provider=C.make_tap_provider(rule))
    records, mapping = C.full_evidence_and_map()
    ev = _evaluate(runtime, records, mapping)
    assert ev.recommendation is RiskRecommendation.DENY
    assert ("HUMAN_OVERSIGHT_VALID", ControlStatus.FAIL) in ev.failed_controls


# --- Rows 3–7: outcome mapping fail-closed --------------------------------
@pytest.mark.parametrize(
    "outcome,coverage,expected_status",
    [
        (TapOutcome.UNSUPPORTED, 1.0, ControlStatus.FAIL),      # row 3/4-ish
        (TapOutcome.CONSTRAINED, 0.5, ControlStatus.UNKNOWN),   # row 5
        (TapOutcome.INDETERMINATE, 0.0, ControlStatus.UNKNOWN), # row 6
        (TapOutcome.SUPPORTED, 0.5, ControlStatus.UNKNOWN),     # row 7 partial
        (TapOutcome.UNKNOWN, None, ControlStatus.UNKNOWN),      # non-determination
    ],
)
def test_non_full_support_outcomes_never_pass(outcome, coverage, expected_status):
    rule = {"BIAS_EVALUATION_CURRENT": TapRule(outcome=outcome, evidence_coverage=coverage)}
    runtime = C.build_runtime(tap_provider=C.make_tap_provider(rule))
    records, mapping = C.full_evidence_and_map()
    ev = _evaluate(runtime, records, mapping)
    assert ev.recommendation is RiskRecommendation.DENY
    trusted = {t.control_id: t.status for t in runtime.trusted_controls(C.TENANT, "rdc_prod_1")}
    assert trusted["BIAS_EVALUATION_CURRENT"] is expected_status


# --- Row 6: stale evidence -------------------------------------------------
def test_stale_evidence_denies():
    # Evidence whose validity window has already elapsed at ``now`` is inadmissible.
    stale = C.make_evidence(
        "ev_model_provenance_valid",
        observed_at=C.FIXED_NOW - timedelta(hours=2),
        valid_until=C.FIXED_NOW - timedelta(hours=1),
    )
    others = (
        C.make_evidence("ev_human_oversight_valid"),
        C.make_evidence("ev_bias_evaluation_current"),
    )
    mapping = {
        "MODEL_PROVENANCE_VALID": ("ev_model_provenance_valid",),
        "HUMAN_OVERSIGHT_VALID": ("ev_human_oversight_valid",),
        "BIAS_EVALUATION_CURRENT": ("ev_bias_evaluation_current",),
    }
    runtime = C.build_runtime()
    ev = _evaluate(runtime, (stale,) + others, mapping)
    assert ev.recommendation is RiskRecommendation.DENY
    assert ("MODEL_PROVENANCE_VALID", ControlStatus.MISSING) in ev.failed_controls


# --- Rows 7–10: cross-context bindings ------------------------------------
@pytest.mark.parametrize(
    "field,value",
    [
        ("tenant_id", C.OTHER_TENANT),
        ("workflow_ir_digest", "sha256:" + "0" * 64),
        ("policy_digest", "sha256:" + "0" * 64),
    ],
)
def test_wrong_context_evidence_is_filtered_and_denies(field, value):
    # A record bound to another tenant/workflow/policy never enters the
    # admitted-in-context set, even though storage would return it (§16).
    bad = C.make_evidence("ev_model_provenance_valid", **{field: value})
    others = (
        C.make_evidence("ev_human_oversight_valid"),
        C.make_evidence("ev_bias_evaluation_current"),
    )
    mapping = {
        "MODEL_PROVENANCE_VALID": ("ev_model_provenance_valid",),
        "HUMAN_OVERSIGHT_VALID": ("ev_human_oversight_valid",),
        "BIAS_EVALUATION_CURRENT": ("ev_bias_evaluation_current",),
    }
    runtime = C.build_runtime()
    ev = _evaluate(runtime, (bad,) + others, mapping)
    assert ev.recommendation is RiskRecommendation.DENY
    assert ("MODEL_PROVENANCE_VALID", ControlStatus.MISSING) in ev.failed_controls


# --- Row 11: tampered integrity digest ------------------------------------
def test_tampered_evidence_digest_denies():
    good = C.make_evidence("ev_model_provenance_valid")
    # Flip a bound field but keep the (now-stale) digest ⇒ integrity mismatch.
    tampered = dataclasses.replace(good, subject_id="attacker")
    others = (
        C.make_evidence("ev_human_oversight_valid"),
        C.make_evidence("ev_bias_evaluation_current"),
    )
    mapping = {
        "MODEL_PROVENANCE_VALID": ("ev_model_provenance_valid",),
        "HUMAN_OVERSIGHT_VALID": ("ev_human_oversight_valid",),
        "BIAS_EVALUATION_CURRENT": ("ev_bias_evaluation_current",),
    }
    runtime = C.build_runtime()
    ev = _evaluate(runtime, (tampered,) + others, mapping)
    assert ev.recommendation is RiskRecommendation.DENY
    assert ("MODEL_PROVENANCE_VALID", ControlStatus.MISSING) in ev.failed_controls


def test_flipped_digest_denies():
    good = C.make_evidence("ev_model_provenance_valid")
    flipped = dataclasses.replace(good, digest="sha256:" + "d" * 64)
    others = (
        C.make_evidence("ev_human_oversight_valid"),
        C.make_evidence("ev_bias_evaluation_current"),
    )
    mapping = {
        "MODEL_PROVENANCE_VALID": ("ev_model_provenance_valid",),
        "HUMAN_OVERSIGHT_VALID": ("ev_human_oversight_valid",),
        "BIAS_EVALUATION_CURRENT": ("ev_bias_evaluation_current",),
    }
    runtime = C.build_runtime()
    ev = _evaluate(runtime, (flipped,) + others, mapping)
    assert ev.recommendation is RiskRecommendation.DENY


# --- Row 12: unadmitted evidence ------------------------------------------
def test_unadmitted_evidence_reference_denies():
    # A control_evidence map points at an id that was never admitted.
    records = (C.make_evidence("ev_human_oversight_valid"), C.make_evidence("ev_bias_evaluation_current"))
    mapping = {
        "MODEL_PROVENANCE_VALID": ("ev_never_admitted",),
        "HUMAN_OVERSIGHT_VALID": ("ev_human_oversight_valid",),
        "BIAS_EVALUATION_CURRENT": ("ev_bias_evaluation_current",),
    }
    runtime = C.build_runtime()
    ev = _evaluate(runtime, records, mapping)
    assert ev.recommendation is RiskRecommendation.DENY
    assert ("MODEL_PROVENANCE_VALID", ControlStatus.MISSING) in ev.failed_controls


def test_rejected_admission_status_denies():
    from risk_authority.domain.enums import EvidenceState
    from risk_authority.domain.evidence import EvidenceAdmission

    good = C.make_evidence("ev_model_provenance_valid")
    rejected = dataclasses.replace(
        good, admission=EvidenceAdmission(status=EvidenceState.REJECTED, reason="bad provenance")
    )
    others = (
        C.make_evidence("ev_human_oversight_valid"),
        C.make_evidence("ev_bias_evaluation_current"),
    )
    mapping = {
        "MODEL_PROVENANCE_VALID": ("ev_model_provenance_valid",),
        "HUMAN_OVERSIGHT_VALID": ("ev_human_oversight_valid",),
        "BIAS_EVALUATION_CURRENT": ("ev_bias_evaluation_current",),
    }
    runtime = C.build_runtime()
    ev = _evaluate(runtime, (rejected,) + others, mapping)
    assert ev.recommendation is RiskRecommendation.DENY


# --- Rows 14–15: admission / assurance unavailable ------------------------
def test_admission_unavailable_fails_closed():
    class RaisingAdmission:
        def is_admissible(self, evidence, *, now):
            raise RuntimeError("admission backend down")

    runtime = C.build_runtime(evidence_admission=RaisingAdmission())
    records, mapping = C.full_evidence_and_map()
    ev = _evaluate(runtime, records, mapping)
    assert ev.recommendation is RiskRecommendation.DENY


def test_control_assurance_unavailable_fails_closed():
    from ugence_risk_authority_evidence_runtime import TapControlAssurance

    provider = C.make_failing_provider("unavailable")
    runtime = C.build_runtime(control_assurance=TapControlAssurance(provider))
    records, mapping = C.full_evidence_and_map()
    ev = _evaluate(runtime, records, mapping)
    assert ev.recommendation is RiskRecommendation.DENY
    trusted = {t.control_id: t.status for t in runtime.trusted_controls(C.TENANT, "rdc_prod_1")}
    # Every control is UNKNOWN (evaluator did not really run) — never PASS.
    assert all(st is not ControlStatus.PASS for st in trusted.values())


# --- Row 19 / Phase 24: production incomplete config fails closed ---------
def test_incomplete_production_config_fails_closed():
    from risk_authority.api.dependencies import RiskAuthorityApplication
    from risk_authority.crypto import SigningKey, SigningKeyRecord
    from risk_authority.integrations import InMemoryWorkflowIRSource

    source = InMemoryWorkflowIRSource()
    source.register(C.build_workflow())
    key = SigningKeyRecord(C.KEY_ID, SigningKey.from_seed(bytes(range(32))))
    with pytest.raises(RiskAuthorityError):
        RiskAuthorityApplication(
            workflow_source=source,
            key_record=key,
            clock=lambda: C.FIXED_NOW,
            production_mode=True,  # no ports ⇒ fail closed
        )


# --- Phase 22: one mandatory FAIL / MISSING among PASS controls -----------
def test_one_mandatory_fail_among_pass_denies():
    rule = {"BIAS_EVALUATION_CURRENT": TapRule(outcome=TapOutcome.UNSUPPORTED, evidence_coverage=1.0)}
    runtime = C.build_runtime(tap_provider=C.make_tap_provider(rule))
    records, mapping = C.full_evidence_and_map()
    ev = _evaluate(runtime, records, mapping)
    assert ev.recommendation is RiskRecommendation.DENY
    assert ("BIAS_EVALUATION_CURRENT", ControlStatus.FAIL) in ev.failed_controls


def test_one_mandatory_missing_among_pass_denies():
    # Only two of the three required controls receive evidence.
    records = (
        C.make_evidence("ev_model_provenance_valid"),
        C.make_evidence("ev_human_oversight_valid"),
    )
    mapping = {
        "MODEL_PROVENANCE_VALID": ("ev_model_provenance_valid",),
        "HUMAN_OVERSIGHT_VALID": ("ev_human_oversight_valid",),
        # BIAS_EVALUATION_CURRENT deliberately omitted.
    }
    runtime = C.build_runtime()
    ev = _evaluate(runtime, records, mapping)
    assert ev.recommendation is RiskRecommendation.DENY
    assert ("BIAS_EVALUATION_CURRENT", ControlStatus.MISSING) in ev.failed_controls


# --- Row 17 / Phase 17: replay -------------------------------------------
def test_same_context_reuse_across_two_cases_is_valid():
    # One admitted evidence set backs two distinct cases in the SAME
    # tenant/workflow/policy context, still fresh ⇒ both may proceed (§8.3).
    runtime = C.build_runtime()
    records, mapping = C.full_evidence_and_map()
    from risk_authority.api.schemas import CreateCaseRequest

    for case_id in ("rdc_a", "rdc_b"):
        runtime.create_case(
            CreateCaseRequest(
                tenant_id=C.TENANT, case_id=case_id, subject_id=C.ACTOR, model_id=C.MODEL,
                purpose="CUSTOMER_REFUND_REVIEW", domain="FINANCE", jurisdictions=("US",),
                tools=("crm.read",), autonomy_level=2, data_classes=("CUSTOMER_PII",),
                workflow_ir_id="finance-ai-risk", inherent_risk=C.RiskClass.HIGH,
                residual_risk=C.RiskClass.MEDIUM,
            )
        )
        ev = runtime.submit_evidence_and_evaluate(
            C.TENANT, case_id, records, control_evidence=mapping
        )
        assert ev.recommendation in PROCEED
