"""Phase 4B: validated v2 seam admission and subject-aware policy resolution.

What this file proves, using the real production code and the real canonicalizers:

* a genuine v2 request is admitted by ``RiskEvaluationSeam`` and terminates at a
  **non-executable** ``SubjectRiskDecision``;
* every admission gate runs in the load-bearing order, proven with **counting spies**
  rather than by reading the source: on every rejection path the policy resolver, the
  evidence resolver and the Decision Authority observe **nothing at all**;
* a caller-supplied ``evaluation_time`` is rejected fail-closed on the trusted production
  path, before any resolution, and the caller's value never becomes the clock;
* a v2 request requires an **explicitly subject-aware** resolver and never falls back to
  a v1-only one;
* v1 behavior is unchanged.

The adversarial counterpart is ``tests/adversarial/test_phase4b_admission_adversarial.py``.

Naming note: nothing here is named "authentic". These tests prove **binding integrity**
and ordering. Phase 4B establishes no source authenticity whatsoever — see
``test_phase4b_admission_adversarial.py`` for the tests that pin that boundary explicitly.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from risk_authority.api import RiskEvaluationSeam, SeamConfigurationError
from risk_authority.crypto import SigningKeyRecord
from risk_authority.crypto.signing import SigningKey
from risk_authority.domain import (
    AuthorityGrant,
    AuthorityType,
    Predicate,
    PredicateOp,
    RiskClass,
    RuleEffect,
    Scope,
    WorkflowIR,
    WorkflowRule,
    WorkflowStatus,
)
from risk_authority.domain.enums import ControlStatus
from risk_authority.integrations import (
    EVALUATION_REQUEST_SCHEMA_VERSION,
    EVALUATION_REQUEST_SCHEMA_VERSION_V2,
    InMemoryWorkflowIRSource,
    ReferenceSubjectAwarePolicyResolver,
    SubjectContext,
    SubjectRiskDisposition,
    SubjectRiskEvaluationRequest,
    SubjectRiskNonDecisionReason,
    is_subject_aware_policy_resolver,
)
from risk_authority.integrations.control_assurance import (
    ControlAssuranceRequest,
    ControlAssuranceResult,
    bind_control_result,
)
from risk_authority.services.decision_authority import ReferenceDecisionAuthority
from tests.scenario import durable_store

from ..contract.test_subject_context_contracts import T0, adr_context, v2_request

# The trusted clock sits INSIDE the fixture's validity window [T0, T0 + 15min], so a
# rejection can never be an accident of an expired subject.
TRUSTED_NOW = T0 + timedelta(minutes=5)
# A time a caller might try to impose. Deliberately different from TRUSTED_NOW so an
# assertion can tell which one actually governed.
CALLER_TIME = T0 + timedelta(minutes=1)

TENANT = "tnt-acme"
PURPOSE = "cloud_scaling.capacity_action"
DOMAIN = "cloud_scaling"
V2_SCOPE = Scope(purposes=(PURPOSE,))
KEY = SigningKeyRecord("k1", SigningKey.from_seed(bytes(range(32))))


# --------------------------------------------------------------------------- spies
class CallLog:
    """A single ordered record of which trusted collaborator was reached, and when.

    One shared log across all spies is what makes ordering assertions meaningful: an
    empty log proves nothing downstream observed the request at all."""

    def __init__(self):
        self.events: list[str] = []

    def record(self, name: str) -> None:
        self.events.append(name)


class SpyClock:
    def __init__(self, log: CallLog, now: datetime = TRUSTED_NOW):
        self._log = log
        self._now = now
        self.reads = 0

    def __call__(self) -> datetime:
        self.reads += 1
        self._log.record("clock")
        return self._now


class SpySubjectAwareResolver:
    """A production-authoritative, explicitly subject-aware policy resolver."""

    is_production_authoritative = True
    is_subject_context_aware = True

    def __init__(self, log: CallLog, workflow, *, fail: bool = False):
        self._log = log
        self._workflow = workflow
        self._fail = fail
        self.calls: list[dict] = []
        self.v1_calls: list[dict] = []

    def resolve_with_subject_context(self, *, tenant_id, purpose, domain, risk_class,
                                     requested_scope, subject_context, evidence_references,
                                     now):
        self._log.record("policy")
        self.calls.append({
            "tenant_id": tenant_id, "purpose": purpose, "domain": domain,
            "subject_context": subject_context, "evidence_references": evidence_references,
            "now": now,
        })
        if self._fail:
            raise RuntimeError("resolver exploded")
        return self._workflow if domain == DOMAIN else None

    def resolve(self, *, tenant_id, purpose, domain, risk_class, requested_scope, now):
        # A subject-aware resolver still serves v1 the v1 way — the successor boundary is
        # additive, so composing one does not strand existing v1 traffic.
        self._log.record("policy")
        self.v1_calls.append({"tenant_id": tenant_id, "domain": domain, "now": now})
        return self._workflow if domain == DOMAIN else None


class SpyLegacyResolver:
    """A v1-only production resolver: no subject-aware method, no declaration."""

    is_production_authoritative = True

    def __init__(self, log: CallLog, workflow):
        self._log = log
        self._workflow = workflow

    def resolve(self, *, tenant_id, purpose, domain, risk_class, requested_scope, now):
        self._log.record("policy")
        return self._workflow


class SpyEvidenceResolver:
    is_production_authoritative = True

    def __init__(self, log: CallLog, *, fail: bool = False):
        self._log = log
        self._fail = fail

    def resolve(self, **kwargs):
        self._log.record("evidence")
        if self._fail:
            raise RuntimeError("trusted evidence unavailable")
        return ()


class SpyDecisionAuthority:
    is_production_authoritative = True

    def __init__(self, log: CallLog):
        self._log = log
        self._inner = ReferenceDecisionAuthority()

    def issue_decision(self, **kw):
        self._log.record("decision_authority")
        return self._inner.issue_decision(**kw)


class _ProdIngress:
    def is_trusted(self, evidence, *, now):
        return True


class _ProdAdmission:
    def is_admissible(self, record, *, now):
        return True


class _ProdControlAssurance:
    is_production_authoritative = True

    def evaluate(self, request: ControlAssuranceRequest) -> ControlAssuranceResult:
        result = bind_control_result(
            request, status=ControlStatus.MISSING, engine_id="prod-assurance-double",
            engine_version="1", reason="no admitted evidence")
        return ControlAssuranceResult(control_result=result,
                                      engine_id="prod-assurance-double",
                                      engine_version="1", available=True)


# ------------------------------------------------------------------------ fixtures
def _workflow(controls=()):
    rules = ()
    if controls:
        rules = (WorkflowRule(rule_id="R1",
                              conditions=(Predicate("domain", PredicateOp.EQ, DOMAIN),),
                              required_controls=tuple(controls),
                              effect=RuleEffect.DENY_UNLESS_ALL),)
    return WorkflowIR(workflow_ir_id="scaling-pol", version="1.0.0",
                      status=WorkflowStatus.ACTIVE, rules=rules, source_refs=(),
                      effective_at=T0).with_digest()


def _grant():
    return AuthorityGrant(
        principal_id="prod-evaluator",
        tenant_id=TENANT,
        authority_type=AuthorityType.RISK_APPROVAL,
        domains=(DOMAIN,),
        allowed_risk_classes=(RiskClass.LOW, RiskClass.MEDIUM, RiskClass.HIGH),
        max_autonomy=5,
        delegated_by="root",
        grantable_scope=V2_SCOPE,
    )


def production_seam(*, controls=(), log=None, resolver=None, evidence_resolver=None,
                    clock=None):
    """A production seam wired with counting spies for every trusted collaborator."""

    log = log or CallLog()
    src = InMemoryWorkflowIRSource()
    workflow = src.register(_workflow(controls))
    seam = RiskEvaluationSeam.production(
        workflow_source=src,
        policy_resolver=resolver if resolver is not None else SpySubjectAwareResolver(log, workflow),
        evidence_resolver=evidence_resolver if evidence_resolver is not None else SpyEvidenceResolver(log),
        evidence_admission=_ProdAdmission(),
        control_assurance=_ProdControlAssurance(),
        evidence_ingress=_ProdIngress(),
        decision_authority=SpyDecisionAuthority(log),
        evaluator_grant=_grant(),
        key_record=KEY,
        clock=clock if clock is not None else SpyClock(log),
        persistence=durable_store(),
    )
    return seam, log


def downstream(log: CallLog) -> list[str]:
    """Everything except the clock — i.e. every collaborator that must not observe an
    unvalidated request. The clock is excluded deliberately: it is read to stamp a
    rejection record, which is not an observation of the subject context."""

    return [e for e in log.events if e != "clock"]


# ============================================================ HAPPY PATH (3 only)
def test_a_genuine_v2_request_is_admitted_and_reaches_a_non_executable_decision():
    seam, log = production_seam()
    result = seam.evaluate(v2_request())

    assert result.disposition is SubjectRiskDisposition.RISK_PASSED
    assert result.non_decision_reason is None
    # Terminates at the risk decision: non-executable, no authority of any kind.
    assert (result.authorization_performed, result.envelope_issued,
            result.actiongate_invoked, result.actuation_performed,
            result.effect_verified, result.executable) == (False,) * 6
    # ...and the trusted collaborators were reached in the load-bearing order.
    assert downstream(log)[:2] == ["policy", "evidence"]


def test_the_subject_aware_resolver_receives_the_validated_neutral_context():
    log = CallLog()
    src = InMemoryWorkflowIRSource()
    workflow = src.register(_workflow())
    resolver = SpySubjectAwareResolver(log, workflow)
    seam, _ = production_seam(log=log, resolver=resolver)
    seam.evaluate(v2_request())

    (call,) = resolver.calls
    context = call["subject_context"]
    assert isinstance(context, SubjectContext)
    # The neutral facts the ADR requires a scaling policy to be able to route on.
    assert (context.environment, context.region, context.compute_group,
            context.resource_class) == ("prod", "eu-west-1", "cluster-7", "web")
    assert (context.action_type, context.magnitude_before, context.magnitude_after) == (
        "scale_up", 6, 9)
    assert (context.subject_valid_from, context.subject_valid_until) == (
        T0, T0 + timedelta(minutes=15))
    # It is the VALIDATED object, equal to the raw one but re-derived by the validator.
    assert context == adr_context()
    # Outer authoritative identity stays outside the neutral context: the context the
    # resolver receives carries no tenant or subject identity at all, and tenant is
    # passed as its own argument exactly as the v1 method passes it.
    assert call["tenant_id"] == TENANT
    assert "tenant_id" not in context.to_canonical_dict()
    assert "subject_id" not in context.to_canonical_dict()
    # Evidence references stay a separate concern, not folded into the context.
    assert call["evidence_references"] == ("sha256:aaa", "sha256:bbb")
    # ...and the trusted clock, never a caller value, governs resolution.
    assert call["now"] == TRUSTED_NOW


def test_a_reference_seam_can_conform_on_v2_without_being_production_authoritative():
    src = InMemoryWorkflowIRSource()
    workflow = src.register(_workflow())
    resolver = ReferenceSubjectAwarePolicyResolver(
        by_purpose_domain={(PURPOSE, DOMAIN): workflow})
    seam = RiskEvaluationSeam.reference(
        workflow_source=src, key_record=KEY, clock=lambda: TRUSTED_NOW,
        policy_resolver=resolver)

    result = seam.evaluate(v2_request())
    assert result.executable is False
    assert resolver.last_subject_context == [adr_context()]
    # The reference resolver stays visibly non-authoritative and is refused by production.
    assert resolver.is_production_authoritative is False


# ==================================================== EVALUATION-TIME REJECTION
def test_caller_supplied_evaluation_time_is_rejected_on_the_production_path():
    seam, log = production_seam()
    result = seam.evaluate(v2_request(evaluation_time=CALLER_TIME))

    assert result.disposition is SubjectRiskDisposition.NOT_EVALUATED
    assert result.non_decision_reason is SubjectRiskNonDecisionReason.CALLER_SUPPLIED_EVALUATION_TIME
    assert "evaluation_time:caller_supplied" in result.reason_codes


def test_the_evaluation_time_rejection_precedes_all_policy_and_evidence_resolution():
    seam, log = production_seam()
    seam.evaluate(v2_request(evaluation_time=CALLER_TIME))
    # Nothing downstream observed the request: not the policy resolver, not the evidence
    # resolver, not the Decision Authority.
    assert downstream(log) == []


def test_a_caller_supplied_time_never_becomes_the_clock_even_on_its_own_rejection():
    seam, log = production_seam()
    result = seam.evaluate(v2_request(evaluation_time=CALLER_TIME))
    # The rejection record is stamped with the TRUSTED clock, not the caller's value, so
    # a caller cannot influence even the timestamp of its own rejection.
    assert result.evaluated_at == TRUSTED_NOW
    assert result.evaluated_at != CALLER_TIME


def test_the_caller_supplied_time_is_never_silently_ignored():
    # The same request differing ONLY in evaluation_time must not produce the accepting
    # outcome: silently dropping the field would make these two results identical.
    seam_a, _ = production_seam()
    seam_b, _ = production_seam()
    accepted = seam_a.evaluate(v2_request())
    rejected = seam_b.evaluate(v2_request(evaluation_time=CALLER_TIME))
    assert accepted.disposition is SubjectRiskDisposition.RISK_PASSED
    assert rejected.disposition is SubjectRiskDisposition.NOT_EVALUATED


def test_reference_mode_remains_the_only_place_an_explicit_clock_may_be_supplied():
    # ADR §10: reference/test time injection is explicitly separated from production
    # authority. A reference seam still honors it; production refuses it (above).
    src = InMemoryWorkflowIRSource()
    workflow = src.register(_workflow())
    seam = RiskEvaluationSeam.reference(
        workflow_source=src, key_record=KEY, clock=lambda: TRUSTED_NOW,
        policy_resolver=ReferenceSubjectAwarePolicyResolver(
            by_purpose_domain={(PURPOSE, DOMAIN): workflow}))
    result = seam.evaluate(v2_request(evaluation_time=CALLER_TIME))
    assert result.non_decision_reason is not SubjectRiskNonDecisionReason.CALLER_SUPPLIED_EVALUATION_TIME
    assert result.evaluated_at == CALLER_TIME


# ==================================================== SUBJECT-AWARE RESOLVER BOUNDARY
def test_a_v2_request_against_a_legacy_resolver_fails_closed_before_resolution():
    log = CallLog()
    src = InMemoryWorkflowIRSource()
    workflow = src.register(_workflow())
    legacy = SpyLegacyResolver(log, workflow)
    seam, _ = production_seam(log=log, resolver=legacy)

    result = seam.evaluate(v2_request())
    assert result.disposition is SubjectRiskDisposition.NOT_EVALUATED
    assert result.non_decision_reason is SubjectRiskNonDecisionReason.NO_AUTHORITATIVE_POLICY
    assert "resolver:not_subject_context_aware" in result.reason_codes
    # No fallback: the legacy resolver was never called at all.
    assert downstream(log) == []


def test_a_kwargs_swallowing_resolver_cannot_infer_its_way_into_v2_capability():
    # The exact failure an added keyword would have caused: a resolver that accepts
    # anything and silently drops the subject context. Capability is declared, never
    # inferred from a permissive signature.
    log = CallLog()

    class Permissive:
        is_production_authoritative = True
        is_subject_context_aware = True  # declared, but the method does not exist

        def resolve(self, **kwargs):
            log.record("policy")
            raise AssertionError("must never be reached")

    assert is_subject_aware_policy_resolver(Permissive()) is False
    seam, _ = production_seam(log=log, resolver=Permissive())
    result = seam.evaluate(v2_request())
    assert result.non_decision_reason is SubjectRiskNonDecisionReason.NO_AUTHORITATIVE_POLICY
    assert downstream(log) == []


def test_a_resolver_with_the_method_but_no_declaration_is_also_refused():
    log = CallLog()

    class Undeclared:
        is_production_authoritative = True  # no is_subject_context_aware

        def resolve_with_subject_context(self, **kwargs):
            log.record("policy")
            raise AssertionError("must never be reached")

    assert is_subject_aware_policy_resolver(Undeclared()) is False
    seam, _ = production_seam(log=log, resolver=Undeclared())
    assert seam.evaluate(v2_request()).non_decision_reason is (
        SubjectRiskNonDecisionReason.NO_AUTHORITATIVE_POLICY)
    assert downstream(log) == []


def test_a_reference_subject_aware_resolver_cannot_enter_the_production_composition_root():
    with pytest.raises(SeamConfigurationError):
        production_seam(resolver=ReferenceSubjectAwarePolicyResolver(by_purpose_domain={}))


def test_a_subject_aware_resolver_failure_fails_closed_as_ambiguous_policy():
    log = CallLog()
    src = InMemoryWorkflowIRSource()
    workflow = src.register(_workflow())
    seam, _ = production_seam(
        log=log, resolver=SpySubjectAwareResolver(log, workflow, fail=True))
    result = seam.evaluate(v2_request())
    assert result.disposition is SubjectRiskDisposition.NOT_EVALUATED
    assert result.non_decision_reason is SubjectRiskNonDecisionReason.AMBIGUOUS_POLICY
    # It failed at policy resolution, so evidence was never resolved.
    assert "evidence" not in downstream(log)


def test_no_authoritative_policy_for_a_v2_request_fails_closed():
    log = CallLog()
    src = InMemoryWorkflowIRSource()
    workflow = src.register(_workflow())

    class NoPolicy(SpySubjectAwareResolver):
        def resolve_with_subject_context(self, **kwargs):
            self._log.record("policy")
            return None

    seam, _ = production_seam(log=log, resolver=NoPolicy(log, workflow))
    result = seam.evaluate(v2_request())
    assert result.non_decision_reason is SubjectRiskNonDecisionReason.NO_AUTHORITATIVE_POLICY
    assert "evidence" not in downstream(log)


def test_trusted_evidence_failure_on_the_v2_path_fails_closed():
    log = CallLog()
    seam, _ = production_seam(
        controls=("CTRL_A",), log=log,
        evidence_resolver=SpyEvidenceResolver(log, fail=True))
    result = seam.evaluate(v2_request())
    assert result.disposition is SubjectRiskDisposition.NOT_EVALUATED
    assert result.non_decision_reason is SubjectRiskNonDecisionReason.EVALUATOR_UNAVAILABLE
    # Policy resolution precedes evidence resolution — proven by the recorded order.
    assert downstream(log) == ["policy", "evidence"]


def test_a_required_control_without_trusted_evidence_never_passes_on_v2():
    seam, _ = production_seam(controls=("CTRL_A",))
    result = seam.evaluate(v2_request())
    assert result.disposition in (SubjectRiskDisposition.RISK_DENIED,
                                  SubjectRiskDisposition.RISK_ESCALATED)
    assert result.executable is False


# ==================================================== ORDERING (counting spies)
def test_policy_resolution_never_precedes_binding_validation():
    # A context-digest mismatch must be caught before ANY collaborator is reached.
    seam, log = production_seam()
    # The raw context is altered while the request keeps the ORIGINAL subject_digest, so
    # the recomputed context_digest no longer reconciles.
    tampered = v2_request(subject_context=SubjectContext.from_dict(
        {**adr_context().to_canonical_dict(), "environment": "staging"}))
    result = seam.evaluate(tampered)
    assert result.non_decision_reason is SubjectRiskNonDecisionReason.INVALID_SUBJECT
    assert downstream(log) == []


@pytest.mark.parametrize("mutation,expected_reason", [
    # One mutation per load-bearing gate; each must be caught by ITS gate, and in every
    # case nothing downstream may observe the request.
    ({"evaluation_time": CALLER_TIME},
     SubjectRiskNonDecisionReason.CALLER_SUPPLIED_EVALUATION_TIME),
    ({"tenant_id": "tnt-other"}, SubjectRiskNonDecisionReason.INVALID_SUBJECT),
    ({"subject_id": "wl-other"}, SubjectRiskNonDecisionReason.INVALID_SUBJECT),
    ({"subject_type": "other.type"}, SubjectRiskNonDecisionReason.INVALID_SUBJECT),
    ({"recommendation_digest": "sha256:" + "9" * 64},
     SubjectRiskNonDecisionReason.INVALID_SUBJECT),
    ({"subject_digest": "sha256:" + "0" * 64},
     SubjectRiskNonDecisionReason.INVALID_SUBJECT),
])
def test_every_load_bearing_gate_rejects_before_any_downstream_observation(mutation, expected_reason):
    seam, log = production_seam()
    result = seam.evaluate(v2_request(**mutation))
    assert result.disposition is SubjectRiskDisposition.NOT_EVALUATED
    assert result.non_decision_reason is expected_reason
    assert downstream(log) == []


def test_the_expired_subject_gate_runs_after_validation_and_before_resolution():
    # This layer holds the authoritative clock here, so it can and does enforce validity.
    log = CallLog()
    seam, _ = production_seam(log=log, clock=SpyClock(log, T0 + timedelta(hours=2)))
    result = seam.evaluate(v2_request())
    assert result.non_decision_reason is SubjectRiskNonDecisionReason.EXPIRED_SUBJECT
    assert "subject_validity:expired" in result.reason_codes
    assert downstream(log) == []


def test_a_subject_not_yet_valid_also_fails_closed():
    log = CallLog()
    seam, _ = production_seam(log=log, clock=SpyClock(log, T0 - timedelta(hours=1)))
    result = seam.evaluate(v2_request())
    assert result.non_decision_reason is SubjectRiskNonDecisionReason.EXPIRED_SUBJECT
    assert downstream(log) == []


# ==================================================== SCHEMA / TYPE ADMISSION
def test_a_v1_class_object_carrying_the_v2_tag_cannot_masquerade_as_v2():
    # The v2 tag is now a SUPPORTED value, so membership alone would admit this object.
    # Gating on the (class, tag) pair is what still refuses it.
    seam, log = production_seam()
    masquerade = SubjectRiskEvaluationRequest(
        subject_type="cloud_scaling.capacity_action", subject_id="wl-checkout-api",
        subject_digest="sha256:" + "e" * 64, tenant_id=TENANT,
        requested_purpose=PURPOSE, requested_domain=DOMAIN, requested_scope=V2_SCOPE,
        schema_version=EVALUATION_REQUEST_SCHEMA_VERSION_V2)
    result = seam.evaluate(masquerade)
    assert result.disposition is SubjectRiskDisposition.NOT_EVALUATED
    assert result.non_decision_reason is SubjectRiskNonDecisionReason.UNSUPPORTED_SCHEMA_VERSION
    assert downstream(log) == []


def test_a_v2_object_carrying_a_smuggled_unknown_tag_fails_closed():
    seam, log = production_seam()
    smuggled = v2_request()
    object.__setattr__(smuggled, "schema_version", "risk-subject-evaluation-request-99")
    result = seam.evaluate(smuggled)
    assert result.non_decision_reason is SubjectRiskNonDecisionReason.UNSUPPORTED_SCHEMA_VERSION
    assert downstream(log) == []


def test_a_v2_object_carrying_the_v1_tag_fails_closed():
    seam, log = production_seam()
    smuggled = v2_request()
    object.__setattr__(smuggled, "schema_version", EVALUATION_REQUEST_SCHEMA_VERSION)
    result = seam.evaluate(smuggled)
    assert result.non_decision_reason is SubjectRiskNonDecisionReason.UNSUPPORTED_SCHEMA_VERSION
    assert downstream(log) == []


# ==================================================== V1 PRESERVATION
def _v1_request(**kw):
    base = dict(
        subject_type="cloud_scaling.capacity_action", subject_id="wl-checkout-api",
        subject_digest="sha256:" + "e" * 64, tenant_id=TENANT,
        requested_purpose=PURPOSE, requested_domain=DOMAIN, requested_scope=V2_SCOPE,
        requested_risk_class=RiskClass.HIGH, evaluation_time=CALLER_TIME)
    base.update(kw)
    return SubjectRiskEvaluationRequest(**base)


def test_v1_still_uses_the_legacy_resolver_method_unchanged():
    log = CallLog()
    src = InMemoryWorkflowIRSource()
    workflow = src.register(_workflow())
    legacy = SpyLegacyResolver(log, workflow)
    seam, _ = production_seam(log=log, resolver=legacy)

    result = seam.evaluate(_v1_request())
    assert result.disposition is SubjectRiskDisposition.RISK_PASSED
    assert downstream(log)[:2] == ["policy", "evidence"]


def test_v1_still_honors_a_caller_supplied_evaluation_time_in_production():
    # The v2 rejection must NOT leak into v1: v1's evaluation_time semantics are frozen.
    seam, _ = production_seam()
    result = seam.evaluate(_v1_request(evaluation_time=CALLER_TIME))
    assert result.disposition is SubjectRiskDisposition.RISK_PASSED
    assert result.evaluated_at == CALLER_TIME


def test_v1_takes_the_v1_method_even_when_the_resolver_is_subject_aware():
    # The successor boundary is additive, not a replacement: composing a subject-aware
    # resolver must not reroute v1 traffic through the v2 method (which would hand v1 a
    # context it does not have), and must not strand it either.
    log = CallLog()
    src = InMemoryWorkflowIRSource()
    workflow = src.register(_workflow())
    resolver = SpySubjectAwareResolver(log, workflow)
    seam, _ = production_seam(log=log, resolver=resolver)

    result = seam.evaluate(_v1_request())
    assert result.disposition is SubjectRiskDisposition.RISK_PASSED
    assert len(resolver.v1_calls) == 1        # the v1 method served it...
    assert resolver.calls == []               # ...and the v2 method was never called.


def test_the_same_resolver_serves_v1_and_v2_through_their_own_methods():
    log = CallLog()
    src = InMemoryWorkflowIRSource()
    workflow = src.register(_workflow())
    resolver = SpySubjectAwareResolver(log, workflow)
    seam, _ = production_seam(log=log, resolver=resolver)

    seam.evaluate(_v1_request())
    seam.evaluate(v2_request())
    assert len(resolver.v1_calls) == 1
    assert len(resolver.calls) == 1
