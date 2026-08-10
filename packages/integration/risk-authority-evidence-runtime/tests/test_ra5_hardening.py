"""RA-5 audit remediation — adversarial coverage (H-1, H-2, L-3).

These lock in the structural hardening from the independent RA-5 audit:

* H-1 — support presumed from mere evidence presence (a rule-less/permissive
  evaluator) is NEVER a PASS in production; production refuses a non-authoritative
  Control-Assurance port.
* H-2 — evidence must arrive over an authenticated producer channel; a valid
  self-computed integrity digest buys nothing; production fails closed without a
  trusted-ingress seam.
* L-3 — post-hoc mutation of admission-time attribution (producer / version /
  admitted_at) fails admission.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from risk_authority.api.dependencies import RiskAuthorityApplication
from risk_authority.crypto import SigningKey, SigningKeyRecord
from risk_authority.domain.enums import ControlStatus, RiskRecommendation
from risk_authority.domain.errors import RiskAuthorityError
from risk_authority.integrations import (
    InMemoryWorkflowIRSource,
    ReferenceControlAssurance,
)

from ugence_risk_authority_evidence_runtime import (
    ProductionEvidenceAdmission,
    StaticTrustedIngress,
    TapControlAssurance,
)

import ra5_scenario as C


def _evaluate(runtime, records, mapping=None):
    C.create_case(runtime)
    return runtime.submit_evidence_and_evaluate(
        C.TENANT, "rdc_prod_1", records, control_evidence=mapping
    )


# --- H-1: presumptive support is never PASS -------------------------------
def test_presumptive_support_without_determination_denies():
    # Arbitrary admitted evidence + a rule-less evaluator ⇒ support presumed from
    # presence ⇒ every control UNKNOWN ⇒ DENY, no PASS (over a TRUSTED channel, so
    # this isolates H-1 from H-2).
    runtime = C.build_runtime(tap_provider=C.make_tap_provider(explicit_support=False))
    records, mapping = C.full_evidence_and_map()
    ev = _evaluate(runtime, records, mapping)
    assert ev.recommendation is RiskRecommendation.DENY
    statuses = {t.control_id: t.status for t in runtime.trusted_controls(C.TENANT, "rdc_prod_1")}
    assert statuses  # results were produced and persisted
    assert all(st is ControlStatus.UNKNOWN for st in statuses.values())
    assert not any(st is ControlStatus.PASS for st in statuses.values())


def test_presumptive_case_yields_no_authority():
    runtime = C.build_runtime(tap_provider=C.make_tap_provider(explicit_support=False))
    records, mapping = C.full_evidence_and_map()
    ev = _evaluate(runtime, records, mapping)
    from risk_authority.api.schemas import DecisionRequest, IssueEnvelopeRequest

    # UNKNOWN controls are evaluated (they reach AUTHORITY_REVIEW) but non-
    # satisfying: the decision grants NO authority and no envelope can be minted.
    decision = runtime.issue_decision(
        C.TENANT, "rdc_prod_1", ev,
        DecisionRequest(principal_id=C.PRINCIPAL, requested_scope=C.FINANCE_SCOPE),
    )
    assert not decision.grants_authority
    with pytest.raises(RiskAuthorityError):
        runtime.issue_envelope(
            C.TENANT, "rdc_prod_1",
            IssueEnvelopeRequest(decision_id=decision.decision_id, audience="x",
                                 session_id="s", nonce="n"),
        )


def test_explicit_determination_still_passes():
    # The legitimate path — an explicit SUPPORTED rule — still GRANTs.
    runtime = C.build_runtime()  # make_tap_provider() installs explicit SUPPORTED rules
    records, mapping = C.full_evidence_and_map()
    ev = _evaluate(runtime, records, mapping)
    assert ev.recommendation in (
        RiskRecommendation.ALLOW,
        RiskRecommendation.ALLOW_WITH_CONDITIONS,
    )
    assert all(
        t.status is ControlStatus.PASS
        for t in runtime.trusted_controls(C.TENANT, "rdc_prod_1")
    )


# --- H-1: production guardrail rejects permissive/reference evaluators -----
def test_production_rejects_permissive_control_assurance():
    permissive = TapControlAssurance(
        C.make_tap_provider(explicit_support=False), require_explicit_determination=False
    )
    assert permissive.is_production_authoritative is False
    with pytest.raises(RiskAuthorityError):
        C.build_runtime(control_assurance=permissive)


def test_production_rejects_reference_control_assurance():
    with pytest.raises(RiskAuthorityError):
        C.build_runtime(control_assurance=ReferenceControlAssurance())


# --- H-2: authenticated producer channel required -------------------------
def _bare_app(**kw):
    source = InMemoryWorkflowIRSource()
    source.register(C.build_workflow())
    key = SigningKeyRecord(C.KEY_ID, SigningKey.from_seed(bytes(range(32))))
    return RiskAuthorityApplication(
        workflow_source=source, key_record=key, clock=lambda: C.FIXED_NOW, **kw
    )


def test_production_requires_trusted_ingress():
    with pytest.raises(RiskAuthorityError):
        _bare_app(
            evidence_admission=ProductionEvidenceAdmission(),
            control_assurance=TapControlAssurance(C.make_tap_provider()),
            production_mode=True,  # no evidence_ingress ⇒ fail closed
        )


def test_production_rejects_reference_ingress():
    # F-1: the conformance stand-in (is_reference_ingress=True) is not a real
    # authenticated-channel verifier; production must refuse it at construction,
    # symmetric with test_production_rejects_reference_control_assurance. Wiring it
    # in would silently reopen the H-2 evidence-authenticity gap.
    assert StaticTrustedIngress(trusted=True).is_reference_ingress is True
    with pytest.raises(RiskAuthorityError):
        _bare_app(
            evidence_admission=ProductionEvidenceAdmission(),
            control_assurance=TapControlAssurance(C.make_tap_provider()),
            evidence_ingress=StaticTrustedIngress(trusted=True),
            production_mode=True,
        )
    # Rejection is on the reference marker, not the posture: trusted=False too.
    with pytest.raises(RiskAuthorityError):
        _bare_app(
            evidence_admission=ProductionEvidenceAdmission(),
            control_assurance=TapControlAssurance(C.make_tap_provider()),
            evidence_ingress=StaticTrustedIngress(trusted=False),
            production_mode=True,
        )


def test_untrusted_channel_evidence_is_dropped_and_denies():
    # Explicit full-support determination, but evidence arrives over an UNTRUSTED
    # channel ⇒ never admitted ⇒ every required control MISSING ⇒ DENY. A valid
    # self-computed digest is irrelevant. Uses a real (non-reference) deployment
    # channel verifier set to distrust — the conformance stand-in is refused in
    # production (F-1), so it can no longer stand in for this check.
    runtime = C.build_runtime(
        evidence_ingress=C.DeploymentChannelIngress(trusted=False)
    )
    records, mapping = C.full_evidence_and_map()
    ev = _evaluate(runtime, records, mapping)
    assert ev.recommendation is RiskRecommendation.DENY
    failed = {cid: st for cid, st in ev.failed_controls}
    assert set(failed) == set(C.REQUIRED_CONTROLS)
    assert all(st is ControlStatus.MISSING for st in failed.values())


def test_fabricated_evidence_over_trusted_channel_still_needs_real_determination():
    # The original audit exploit shape: fabricated evidence + self-computed digest.
    # Even if the channel is (wrongly) trusted, a rule-less evaluator yields only
    # presumptive support ⇒ DENY. Digest + presence are not authority.
    runtime = C.build_runtime(
        tap_provider=C.make_tap_provider(explicit_support=False),
        evidence_ingress=C.DeploymentChannelIngress(trusted=True),
    )
    records, mapping = C.full_evidence_and_map()
    ev = _evaluate(runtime, records, mapping)
    assert ev.recommendation is RiskRecommendation.DENY


# --- L-3: admission-record attribution binding ----------------------------
@pytest.mark.parametrize(
    "field,value",
    [
        ("producer", "attacker"),
        ("producer_version", "99"),
        ("admitted_at", C.FIXED_NOW + timedelta(minutes=5)),
    ],
)
def test_mutated_attribution_fails_admission(field, value):
    admitter = ProductionEvidenceAdmission()
    good = C.make_evidence("ev1")
    assert admitter.is_admissible(good, now=C.FIXED_NOW)
    mutated = C.tamper(good, **{field: value})
    assert not admitter.is_admissible(mutated, now=C.FIXED_NOW), field


def test_mutated_attribution_denies_in_pipeline():
    runtime = C.build_runtime()
    good = C.make_evidence("ev_model_provenance_valid")
    forged_attr = C.tamper(good, producer="attacker")  # breaks admission_digest
    others = (
        C.make_evidence("ev_human_oversight_valid"),
        C.make_evidence("ev_bias_evaluation_current"),
    )
    mapping = {
        "MODEL_PROVENANCE_VALID": ("ev_model_provenance_valid",),
        "HUMAN_OVERSIGHT_VALID": ("ev_human_oversight_valid",),
        "BIAS_EVALUATION_CURRENT": ("ev_bias_evaluation_current",),
    }
    ev = _evaluate(runtime, (forged_attr,) + others, mapping)
    assert ev.recommendation is RiskRecommendation.DENY
    assert ("MODEL_PROVENANCE_VALID", ControlStatus.MISSING) in ev.failed_controls
