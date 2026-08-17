"""Phase 4B F-1: the subject-context **revalidation** boundary, pinned behaviorally.

Why this file exists (independent-audit finding F-1). Step 1 of
``validate_subject_binding`` re-parses the carried context through
``SubjectContext.from_dict(context.to_canonical_dict())`` rather than trusting the
instance it was handed. That step is load-bearing, but the pre-existing tests did not
prove it: they mutate a context and leave a **stale** digest behind, so they are caught by
the digest comparison in step 5 and would still pass if revalidation were deleted.

The attacks here close that gap. Each one mutates a frozen ``SubjectContext`` into a state
its constructor forbids and then **reseals every surrounding value** — the context digest,
the reconstructed ``SubjectBinding`` and the outer ``subject_digest`` are all recomputed
over the tampered context. Nothing is stale, so the digest comparison is satisfied and the
request reaches the revalidation boundary on its merits. Only re-parsing the context can
reject it. Delete that step and every test in this file fails.

Modelled threat: a tampered or hostile *deserialized* object — one whose invariants were
established once and then broken, exactly as a compromised upstream or a bypassed
constructor would produce. ``object.__setattr__`` is the test-only mechanism used to reach
that state, because the production constructors correctly refuse these values up front.

Nothing here asserts that a helper "was called". Every assertion is behavioral, through the
real production seam, with audit-owned counting collaborators.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from risk_authority.api import RiskEvaluationSeam
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
    InMemoryWorkflowIRSource,
    SubjectBinding,
    SubjectContext,
    SubjectRiskDisposition,
    SeamContractError,
    SubjectRiskEvaluationRequestV2,
    SubjectRiskNonDecisionReason,
)
from risk_authority.integrations.control_assurance import (
    ControlAssuranceRequest,
    ControlAssuranceResult,
    bind_control_result,
)
from risk_authority.services.decision_authority import ReferenceDecisionAuthority

from ..contract.test_subject_context_contracts import REC_DIGEST, T0, adr_context

TENANT = "tnt-acme"
SUBJECT_ID = "wl-checkout-api"
SUBJECT_TYPE = "cloud_scaling.capacity_action"
PURPOSE = "cloud_scaling.capacity_action"
DOMAIN = "cloud_scaling"
SCOPE = Scope(purposes=(PURPOSE,))
KEY = SigningKeyRecord("k1", SigningKey.from_seed(bytes(range(32))))
# Inside the fixture's validity window, so no rejection can be an accident of expiry.
TRUSTED_NOW = T0 + timedelta(minutes=5)


# ------------------------------------------------------- audit-owned collaborators
class AuditCounters:
    """Counts every trusted collaborator a request could possibly reach.

    Owned by this suite, not by production, and wired into a **real** production seam.
    A run in which all five counters are zero is proof that the request was refused
    before anything downstream could observe it."""

    def __init__(self):
        self.policy = 0
        self.evidence = 0
        self.decision_authority = 0
        self.envelope_issuer = 0
        self.actiongate = 0
        self.contexts_seen: list = []

    @property
    def downstream_total(self) -> int:
        return (self.policy + self.evidence + self.decision_authority
                + self.envelope_issuer + self.actiongate)

    def as_dict(self) -> dict:
        return {
            "policy_resolver": self.policy,
            "evidence_resolver": self.evidence,
            "decision_authority": self.decision_authority,
            "envelope_issuer": self.envelope_issuer,
            "actiongate": self.actiongate,
        }


class CountingSubjectAwareResolver:
    is_production_authoritative = True
    is_subject_context_aware = True

    def __init__(self, counters: AuditCounters, workflow):
        self._c = counters
        self._w = workflow

    def resolve_with_subject_context(self, *, tenant_id, purpose, domain, risk_class,
                                     requested_scope, subject_context, evidence_references,
                                     now):
        self._c.policy += 1
        self._c.contexts_seen.append(subject_context)
        return self._w

    def resolve(self, *, tenant_id, purpose, domain, risk_class, requested_scope, now):
        # Counted separately so a v1 fallback is visible rather than silent.
        self._c.policy += 1
        self._c.contexts_seen.append("V1_FALLBACK")
        return self._w


class CountingEvidenceResolver:
    is_production_authoritative = True

    def __init__(self, counters: AuditCounters):
        self._c = counters

    def resolve(self, **kwargs):
        self._c.evidence += 1
        return ()


class CountingDecisionAuthority:
    is_production_authoritative = True

    def __init__(self, counters: AuditCounters):
        self._c = counters
        self._inner = ReferenceDecisionAuthority()

    def issue_decision(self, **kw):
        self._c.decision_authority += 1
        return self._inner.issue_decision(**kw)


class _Ingress:
    def is_trusted(self, evidence, *, now):
        return True


class _Admission:
    def is_admissible(self, record, *, now):
        return True


class _ControlAssurance:
    is_production_authoritative = True

    def evaluate(self, request: ControlAssuranceRequest) -> ControlAssuranceResult:
        result = bind_control_result(
            request, status=ControlStatus.MISSING, engine_id="prod-assurance-double",
            engine_version="1", reason="no admitted evidence")
        return ControlAssuranceResult(control_result=result,
                                      engine_id="prod-assurance-double",
                                      engine_version="1", available=True)


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


def audited_production_seam():
    """A REAL production seam with every reachable collaborator counted."""

    counters = AuditCounters()
    src = InMemoryWorkflowIRSource()
    workflow = src.register(_workflow())
    seam = RiskEvaluationSeam.production(
        workflow_source=src,
        policy_resolver=CountingSubjectAwareResolver(counters, workflow),
        evidence_resolver=CountingEvidenceResolver(counters),
        evidence_admission=_Admission(),
        control_assurance=_ControlAssurance(),
        evidence_ingress=_Ingress(),
        decision_authority=CountingDecisionAuthority(counters),
        evaluator_grant=AuthorityGrant(
            principal_id="prod-evaluator", tenant_id=TENANT,
            authority_type=AuthorityType.RISK_APPROVAL, domains=(DOMAIN,),
            allowed_risk_classes=(RiskClass.LOW, RiskClass.MEDIUM, RiskClass.HIGH),
            max_autonomy=5, delegated_by="root", grantable_scope=SCOPE),
        key_record=KEY,
        clock=lambda: TRUSTED_NOW,
    )

    # The two authority-granting surfaces the seam must never reach. Counting them here
    # means "no authorization artifact" is an observation, not an assumption.
    def _count_envelope(*a, **k):
        counters.envelope_issuer += 1
        raise AssertionError("the seam issued an envelope")

    def _count_actiongate(*a, **k):
        counters.actiongate += 1
        raise AssertionError("the seam invoked ActionGate")

    seam._app.issue_envelope = _count_envelope       # type: ignore[assignment]
    seam._app.authorize_action = _count_actiongate   # type: ignore[assignment]
    return seam, counters


# ------------------------------------------------------------------- the attacks
def tampered_context(**bad_fields) -> SubjectContext:
    """A ``SubjectContext`` forced into a state its constructor forbids.

    Models a tampered or hostile deserialized object whose invariants were established
    once and then broken. The production constructor correctly refuses these values, so
    reaching the state at all requires this test-only bypass."""

    context = adr_context()
    for name, value in bad_fields.items():
        object.__setattr__(context, name, value)
    return context


def resealed_request(context: SubjectContext, **overrides) -> SubjectRiskEvaluationRequestV2:
    """Wrap ``context`` in a v2 request with **every** surrounding value recomputed.

    The context digest, the reconstructed binding and the outer ``subject_digest`` are all
    derived from the tampered context, so nothing is stale. The digest-equality gate is
    therefore satisfied and the request reaches the revalidation boundary on its merits —
    which is the entire point: rejection must come from re-parsing the context, not from a
    mismatched digest."""

    binding = SubjectBinding(
        tenant_id=TENANT, subject_id=SUBJECT_ID, subject_type=SUBJECT_TYPE,
        recommendation_digest=REC_DIGEST, context_digest=context.digest())
    base = dict(
        subject_type=SUBJECT_TYPE, subject_id=SUBJECT_ID,
        subject_digest=binding.digest(), tenant_id=TENANT,
        requested_purpose=PURPOSE, requested_domain=DOMAIN, requested_scope=SCOPE,
        evidence_references=("sha256:aaa", "sha256:bbb"),
        subject_context=context, recommendation_digest=REC_DIGEST)
    base.update(overrides)
    return SubjectRiskEvaluationRequestV2(**base)


# Non-NFC strings are written with explicit combining-mark escapes, never as source
# literals: a literal "\u00e9" may be stored precomposed (already NFC) by the editor or the
# file encoding, which would silently turn the attack into a *valid* value and make the
# test pass for the wrong reason.
NON_NFC_ENVIRONMENT = "prod" + "e\u0301"      # e + COMBINING ACUTE; NFC folds it to U+00E9
NON_NFC_REGION = "eu-west-" + "e\u0301"
NON_NFC_COMPUTE_GROUP = "clu" + "s\u0327" + "ter"   # s + COMBINING CEDILLA

# Each entry is a value the closed contract forbids, resealed so only revalidation
# can catch it. Named for the invariant it violates.
INVALID_CONTEXTS = [
    pytest.param({"magnitude_before": True}, id="bool-where-int-magnitude-required"),
    pytest.param({"magnitude_after": False}, id="bool-false-where-int-magnitude-required"),
    pytest.param({"environment": NON_NFC_ENVIRONMENT}, id="non-nfc-environment"),
    pytest.param({"region": NON_NFC_REGION}, id="non-nfc-region"),
    pytest.param({"compute_group": NON_NFC_COMPUTE_GROUP}, id="non-nfc-compute-group"),
    pytest.param({"action_type": ""}, id="empty-action-type"),
    pytest.param({"action_type": "   "}, id="whitespace-only-action-type"),
    pytest.param({"action_type": "\t\n"}, id="tab-newline-only-action-type"),
    pytest.param({"action_type": " scale_up "}, id="padded-action-type"),
]


def test_the_non_nfc_fixtures_are_genuinely_non_nfc():
    """Guards the guard.

    A non-NFC attack written as a source literal can be silently stored precomposed by
    the editor or file encoding, degrading it into a perfectly valid value — the attack
    would then be accepted and its test would pass while proving nothing. These are built
    from explicit combining marks; this asserts they really are decomposed."""

    import unicodedata

    for value in (NON_NFC_ENVIRONMENT, NON_NFC_REGION, NON_NFC_COMPUTE_GROUP):
        assert unicodedata.normalize("NFC", value) != value, repr(value)


@pytest.mark.parametrize("bad_fields", INVALID_CONTEXTS)
def test_a_resealed_invalid_context_is_refused_before_any_downstream_observation(bad_fields):
    """The F-1 regression. Fails if the revalidation step is removed."""

    seam, counters = audited_production_seam()
    request = resealed_request(tampered_context(**bad_fields))

    # Pre-condition: the attack really is self-consistent, so it is NOT being caught by
    # a stale digest. Without this the test could pass for the wrong reason.
    binding = SubjectBinding(
        tenant_id=TENANT, subject_id=SUBJECT_ID, subject_type=SUBJECT_TYPE,
        recommendation_digest=REC_DIGEST, context_digest=request.subject_context.digest())
    assert request.subject_digest == binding.digest(), "attack is not resealed"

    result = seam.evaluate(request)

    # Typed refusal. INVALID_SUBJECT is the ratified reason for a context/binding that
    # does not validate; no more precise ratified member exists for this case.
    assert result.disposition is SubjectRiskDisposition.NOT_EVALUATED
    assert result.non_decision_reason is SubjectRiskNonDecisionReason.INVALID_SUBJECT
    assert "binding:SeamContractError" in result.reason_codes

    # Nothing downstream observed it — the load-bearing half of the assertion.
    assert counters.as_dict() == {
        "policy_resolver": 0, "evidence_resolver": 0, "decision_authority": 0,
        "envelope_issuer": 0, "actiongate": 0,
    }
    # ...and specifically no v1 fallback occurred.
    assert counters.contexts_seen == []

    # No authorization artifact of any kind.
    assert result.risk_outcome is None
    assert result.decision_snapshot is None and result.decision_digest is None
    assert result.evaluation_snapshot is None and result.evaluation_digest is None
    assert result.expires_at is None

    # Execution flags remain structurally false, on the object and when serialized.
    assert (result.authorization_performed, result.envelope_issued,
            result.actiongate_invoked, result.actuation_performed,
            result.effect_verified, result.executable) == (False,) * 6
    serialized = result.to_canonical_dict()
    for flag in ("authorization_performed", "envelope_issued", "actiongate_invoked",
                 "actuation_performed", "effect_verified", "executable"):
        assert serialized[flag] is False, flag


@pytest.mark.parametrize("bad_fields", INVALID_CONTEXTS)
def test_the_invalid_value_is_rejected_and_never_normalized(bad_fields):
    """Refusal must not be a silent repair.

    A normalizing implementation would coerce ``True`` to ``1``, NFC-fold the string, or
    strip the padding and then proceed. Proving the *request* was refused outright, and
    that the tampered value survives unchanged on the caller's object, distinguishes
    rejection from repair."""

    seam, counters = audited_production_seam()
    context = tampered_context(**bad_fields)
    before = dict(context.to_canonical_dict())
    request = resealed_request(context)

    result = seam.evaluate(request)
    assert result.disposition is SubjectRiskDisposition.NOT_EVALUATED

    # The seam did not rewrite the caller's object into a valid one.
    assert context.to_canonical_dict() == before
    for name, value in bad_fields.items():
        assert getattr(context, name) == value
    # ...and the request's committed identity is untouched.
    assert request.subject_context is context
    assert counters.downstream_total == 0


def test_the_two_gates_are_distinguishable_by_the_error_type_they_raise():
    """Isolates *which* gate does the work, by contrasting two tampered requests.

    The distinction matters because it is exactly what the pre-existing coverage missed:

    * a **stale** request — a *valid* value changed after sealing — reconciles as a
      perfectly legal context but its recomputed ``subject_digest`` no longer matches, so
      the digest-equality gate (step 5) rejects it with ``SubjectBindingError``;
    * a **resealed** request — an *illegal* value with every digest recomputed — satisfies
      digest equality completely, so only context revalidation (step 1) can reject it, and
      it raises the plain ``SeamContractError`` that re-parsing produces.

    Different error types therefore prove different gates fired. If revalidation were
    removed, the second case would not raise at all."""

    from risk_authority.integrations import SubjectBindingError, validate_subject_binding

    # (a) stale, but the substituted value is itself perfectly VALID.
    stale = resealed_request(adr_context())
    object.__setattr__(stale.subject_context, "environment", "staging")  # not resealed
    with pytest.raises(SubjectBindingError):
        validate_subject_binding(stale)

    # (b) resealed, with an ILLEGAL value. Digest equality is satisfied.
    resealed = resealed_request(tampered_context(action_type=""))
    with pytest.raises(SeamContractError) as caught:
        validate_subject_binding(resealed)
    assert not isinstance(caught.value, SubjectBindingError), (
        "the resealed attack must be refused by context revalidation, not by the "
        "digest-equality gate")
    assert "action_type" in str(caught.value)


def test_a_valid_context_still_reaches_policy_resolution():
    """The control. Without it, a validator that rejected everything would pass above."""

    seam, counters = audited_production_seam()
    result = seam.evaluate(resealed_request(adr_context()))

    assert result.non_decision_reason is not SubjectRiskNonDecisionReason.INVALID_SUBJECT
    assert counters.policy == 1 and counters.evidence == 1
    assert counters.contexts_seen == [adr_context()]
    # Still no authority: reaching policy resolution is not authorization.
    assert counters.envelope_issuer == 0 and counters.actiongate == 0
    assert result.executable is False


@pytest.mark.parametrize("bad_fields", INVALID_CONTEXTS)
def test_the_temporal_ordering_invariant_is_also_revalidated(bad_fields):
    """Every closed-contract invariant is re-checked, not just the field the attack used.

    Re-parsing runs the whole ``__post_init__``, so a second, independent violation in the
    same object is caught too — a partial revalidation would not do this."""

    seam, counters = audited_production_seam()
    context = tampered_context(**bad_fields)
    # Break temporal ordering as well: asserted_at now precedes valid_from.
    object.__setattr__(context, "subject_asserted_at", T0 - timedelta(days=1))
    result = seam.evaluate(resealed_request(context))

    assert result.non_decision_reason is SubjectRiskNonDecisionReason.INVALID_SUBJECT
    assert counters.downstream_total == 0


def test_temporal_ordering_alone_is_enough_to_be_refused():
    seam, counters = audited_production_seam()
    context = tampered_context(subject_asserted_at=T0 - timedelta(days=1))
    result = seam.evaluate(resealed_request(context))

    assert result.non_decision_reason is SubjectRiskNonDecisionReason.INVALID_SUBJECT
    assert counters.downstream_total == 0


def test_a_foreign_schema_tag_smuggled_into_the_context_is_refused():
    """Cross-schema substitution at the context layer, resealed."""

    seam, counters = audited_production_seam()
    context = tampered_context(schema_version="risk-subject-binding-1")
    result = seam.evaluate(resealed_request(context))

    assert result.non_decision_reason is SubjectRiskNonDecisionReason.INVALID_SUBJECT
    assert counters.downstream_total == 0


@pytest.mark.parametrize("bad_value", [1.5, "6", None, [], {}])
def test_a_non_canonical_magnitude_type_is_refused(bad_value):
    seam, counters = audited_production_seam()
    context = tampered_context(magnitude_before=bad_value)
    try:
        request = resealed_request(context)
    except Exception:
        # Some types cannot even be canonicalized into a digest; refusal at that
        # boundary is equally fail-closed and never reaches the seam.
        assert counters.downstream_total == 0
        return
    result = seam.evaluate(request)
    if bad_value is None:
        # None is the legitimate "missing" sentinel, so this one is genuinely valid.
        assert result.non_decision_reason is not SubjectRiskNonDecisionReason.INVALID_SUBJECT
        return
    assert result.non_decision_reason is SubjectRiskNonDecisionReason.INVALID_SUBJECT
    assert counters.downstream_total == 0
