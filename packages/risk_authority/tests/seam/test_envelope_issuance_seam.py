"""Phase 5 envelope issuance seam — construction gates, the act, and every refusal.

Drives the finance vertical slice (``tests/scenario.py``) to a granting decision, then
issues through the seam with an injected verification port and a counting clock, so the
single-read invariant, the instant-equality rule and the digest bindings are measured
rather than argued.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone

import pytest

from risk_authority.api import (
    VERIFIED,
    ArtifactVerificationPort,
    AuthorizeActionRequest,
    EnvelopeIssuanceOutcome,
    EnvelopeIssuanceRefusal,
    EnvelopeIssuanceRequest,
    EnvelopeIssuanceSeam,
    IssueEnvelopeRequest,
    RiskAuthorityApplication,
    SeamConfigurationError,
    VerifiedArtifactBinding,
)
from risk_authority.crypto import SigningKey, SigningKeyRecord
from risk_authority.crypto.canonical import to_canonical_obj
from risk_authority.crypto.hashing import digest as _digest
from risk_authority.domain import ArtifactBinding, EnvelopeBindings, Scope
from risk_authority.domain.errors import ProductionContainmentError
from risk_authority.integrations import InMemoryWorkflowIRSource
from risk_authority.services import EnvelopeSignerPort, ReferenceEnvelopeSigner
from risk_authority.services.envelope_issuer import DEFAULT_ENVELOPE_TTL

from tests import scenario as S

NOW = S.FIXED_NOW
KINDS = ("authorization_candidate", "policy_authenticity", "producer_attestation")


def _hex(seed: str) -> str:
    return hashlib.sha256(seed.encode()).hexdigest()


class _Clock:
    """A counting clock: every read is observable."""

    def __init__(self, at: datetime = NOW) -> None:
        self.at, self.reads = at, 0

    def __call__(self) -> datetime:
        self.reads += 1
        return self.at


class _Verification:
    """A verification port reporting VERIFIED bindings at whatever instant it is asked."""

    is_production_authoritative = True

    def __init__(self, kinds=KINDS, *, outcome=VERIFIED, skew: timedelta = timedelta(0),
                 raise_exc: bool = False, digest_for=None):
        self.kinds, self.outcome, self.skew, self.raise_exc = kinds, outcome, skew, raise_exc
        self.calls: list[datetime] = []
        self.digest_for = digest_for or (lambda k: _hex(k))

    def verify(self, *, as_of: datetime):
        self.calls.append(as_of)
        if self.raise_exc:
            raise RuntimeError("verifier down")
        return tuple(VerifiedArtifactBinding(kind=k, digest=self.digest_for(k), outcome=self.outcome,
                                             resolved_as_of=as_of + self.skew) for k in self.kinds)


KEY_RECORD = SigningKeyRecord(S.KEY_ID, SigningKey.from_seed(bytes(range(32))))


def _granting_app(clock: _Clock):
    """Drive the finance scenario to a granting decision on a reference application."""

    from risk_authority.api import ControlResultInput, CreateCaseRequest, DecisionRequest, EvaluateRequest
    from risk_authority.domain import RiskClass

    source = InMemoryWorkflowIRSource()
    source.register(S.build_workflow())
    app = RiskAuthorityApplication(workflow_source=source, key_record=KEY_RECORD, clock=clock)
    app.authority.add_grant(S.build_grant())
    case_id = "rdc_seam"
    app.create_case(CreateCaseRequest(
        tenant_id=S.TENANT, case_id=case_id, subject_id=S.ACTOR, model_id=S.MODEL,
        purpose="CUSTOMER_REFUND_REVIEW", domain="FINANCE", jurisdictions=("US",),
        tools=("crm.read", "refund.prepare"), autonomy_level=2,
        data_classes=("CUSTOMER_PII", "TRANSACTION_DATA"), workflow_ir_id="finance-ai-risk",
        inherent_risk=RiskClass.HIGH, residual_risk=RiskClass.MEDIUM))
    evaluation = app.evaluate(S.TENANT, case_id, EvaluateRequest(
        control_results=(ControlResultInput("MODEL_PROVENANCE_VALID", "PASS"),
                         ControlResultInput("HUMAN_OVERSIGHT_VALID", "PASS"),
                         ControlResultInput("BIAS_EVALUATION_CURRENT", "PASS")),
        conditions=("context_minimization",)))
    decision = app.issue_decision(S.TENANT, case_id, evaluation,
                                  DecisionRequest(principal_id=S.PRINCIPAL, requested_scope=S.FINANCE_SCOPE))
    case = app.cases.get(S.TENANT, case_id)
    return app, case, decision


@pytest.fixture
def world():
    clock = _Clock()
    app, case, decision = _granting_app(clock)
    assert decision.grants_authority
    return clock, app, case, decision


def _request(decision, **kw) -> EnvelopeIssuanceRequest:
    base = dict(tenant_id=decision.tenant_id, decision_id=decision.decision_id,
                decision_digest=_digest(to_canonical_obj(decision)), audience="actiongate",
                session_id="sess-1", nonce="nonce-1")
    base.update(kw)
    return EnvelopeIssuanceRequest(**base)


def _reference_seam(app, clock, verification=None, kinds=KINDS):
    return EnvelopeIssuanceSeam.reference(app=app, key_record=KEY_RECORD, clock=clock,
                                          verification=verification or _Verification(),
                                          required_binding_kinds=kinds)


# --------------------------------------------------------------------------- #
# The act
# --------------------------------------------------------------------------- #
def test_issuance_reads_the_clock_once_and_binds_what_was_verified(world):
    clock, app, case, decision = world
    verification = _Verification()
    seam = _reference_seam(app, clock, verification)
    reads_before = clock.reads
    outcome = seam.issue(_request(decision))
    assert outcome.issued and outcome.refusal is None, outcome.detail
    assert clock.reads == reads_before + 1                       # one read per act
    assert verification.calls == [NOW]                           # the same instant went to the verifiers
    env = outcome.envelope
    assert env.issued_at == NOW and env.not_before == NOW        # no future dating
    assert outcome.issued_at == NOW and outcome.executable is False
    assert {b.kind for b in env.bindings.artifact_bindings} == set(KINDS)
    assert env.bindings.binding_for("policy_authenticity").digest == _hex("policy_authenticity")
    assert env.bindings.authority_epoch == app.revocation.current_epoch(decision.tenant_id)
    assert env.decision_id == decision.decision_id and env.tenant_id == decision.tenant_id
    assert app.envelopes.get(decision.tenant_id, env.envelope_id) == env
    assert app.verify_envelope(decision.tenant_id, env.envelope_id).valid


def test_expiry_is_capped_by_the_decision(world):
    clock, app, case, decision = world
    seam = _reference_seam(app, clock)
    out = seam.issue(_request(decision, ttl=timedelta(days=365)))
    assert out.issued
    expected = min(NOW + timedelta(days=365), decision.expires_at) if decision.expires_at else NOW + timedelta(days=365)
    assert out.envelope.expires_at == expected
    out2 = seam.issue(_request(decision, nonce="nonce-2"))
    assert out2.envelope.expires_at <= NOW + DEFAULT_ENVELOPE_TTL


def test_the_signature_verifies_and_covers_the_artifact_bindings(world):
    clock, app, case, decision = world
    env = _reference_seam(app, clock).issue(_request(decision)).envelope
    assert KEY_RECORD.verify_key.verify(env.signing_payload(), env.signature)
    first = env.bindings.artifact_bindings[0]
    forged = replace(env, bindings=replace(env.bindings, artifact_bindings=(
        ArtifactBinding(first.kind, _hex("other")),) + env.bindings.artifact_bindings[1:]))
    assert not KEY_RECORD.verify_key.verify(forged.signing_payload(), forged.signature)


# --------------------------------------------------------------------------- #
# Refusals
# --------------------------------------------------------------------------- #
def _refusal(seam, request) -> EnvelopeIssuanceRefusal:
    out = seam.issue(request)
    assert not out.issued and out.envelope is None, out
    return out.refusal


def test_unknown_decision_and_digest_drift_are_refused(world):
    clock, app, case, decision = world
    seam = _reference_seam(app, clock)
    assert _refusal(seam, _request(decision, decision_id="nope")) is EnvelopeIssuanceRefusal.DECISION_NOT_FOUND
    assert _refusal(seam, _request(decision, tenant_id="other")) is EnvelopeIssuanceRefusal.DECISION_NOT_FOUND
    assert _refusal(seam, _request(decision, decision_digest=_hex("drift"))) is EnvelopeIssuanceRefusal.DECISION_DIGEST_MISMATCH


def test_an_expired_decision_is_refused_at_the_instant(world):
    clock, app, case, decision = world
    assert decision.expires_at is not None
    clock.at = decision.expires_at + timedelta(seconds=1)
    assert _refusal(_reference_seam(app, clock), _request(decision)) is EnvelopeIssuanceRefusal.DECISION_EXPIRED


def test_verification_that_is_not_verified_incomplete_or_unavailable_refuses(world):
    clock, app, case, decision = world
    assert _refusal(_reference_seam(app, clock, _Verification(outcome="INDETERMINATE")),
                    _request(decision)) is EnvelopeIssuanceRefusal.VERIFICATION_NOT_VERIFIED
    assert _refusal(_reference_seam(app, clock, _Verification(kinds=KINDS[:2])),
                    _request(decision)) is EnvelopeIssuanceRefusal.VERIFICATION_INCOMPLETE
    assert _refusal(_reference_seam(app, clock, _Verification(raise_exc=True)),
                    _request(decision)) is EnvelopeIssuanceRefusal.VERIFICATION_UNAVAILABLE
    assert app.envelopes.get(decision.tenant_id, "rae-1") is None


def test_a_binding_verified_at_another_instant_is_refused(world):
    clock, app, case, decision = world
    for skew in (timedelta(microseconds=1), timedelta(microseconds=-1), timedelta(minutes=5)):
        seam = _reference_seam(app, clock, _Verification(skew=skew))
        assert _refusal(seam, _request(decision)) is EnvelopeIssuanceRefusal.INSTANT_MISMATCH


def test_malformed_and_duplicate_bindings_are_refused(world):
    clock, app, case, decision = world
    bad_digest = _Verification(digest_for=lambda k: "not-a-digest")
    assert _refusal(_reference_seam(app, clock, bad_digest), _request(decision)) is EnvelopeIssuanceRefusal.BINDING_MALFORMED
    dup = _Verification(kinds=KINDS + (KINDS[0],))
    assert _refusal(_reference_seam(app, clock, dup), _request(decision)) is EnvelopeIssuanceRefusal.BINDING_MALFORMED


def test_a_scope_wider_than_the_decision_is_refused(world):
    clock, app, case, decision = world
    wider = replace(decision.scope, tools_allow=decision.scope.tools_allow + ("refund.execute",))
    assert _refusal(_reference_seam(app, clock), _request(decision, envelope_scope=wider)) \
        is EnvelopeIssuanceRefusal.SCOPE_EXCEEDS_DECISION


def test_a_non_positive_ttl_is_refused(world):
    clock, app, case, decision = world
    assert _refusal(_reference_seam(app, clock), _request(decision, ttl=timedelta(0))) is EnvelopeIssuanceRefusal.TTL_INVALID


# --------------------------------------------------------------------------- #
# Construction gates and containment
# --------------------------------------------------------------------------- #
class _ProdSigner:
    is_production_authoritative = True
    key_id = S.KEY_ID
    signature_alg = "ed25519"

    def sign(self, payload: bytes) -> bytes:
        return KEY_RECORD.signing_key.sign(payload)


def test_production_seam_refuses_reference_grade_dependencies(world):
    clock, app, case, decision = world  # a reference application
    with pytest.raises(SeamConfigurationError, match="production mode"):
        EnvelopeIssuanceSeam.production(app=app, signer=_ProdSigner(), verification=_Verification(),
                                        required_binding_kinds=KINDS, clock=clock)

    class _NotProdVerification(_Verification):
        is_production_authoritative = False

    prod_like = type("App", (), {"_production_mode": True})()
    with pytest.raises(SeamConfigurationError, match="reference signer is refused"):
        EnvelopeIssuanceSeam.production(app=prod_like, signer=ReferenceEnvelopeSigner(KEY_RECORD),
                                        verification=_Verification(), required_binding_kinds=KINDS, clock=clock)
    with pytest.raises(SeamConfigurationError, match="ArtifactVerificationPort"):
        EnvelopeIssuanceSeam.production(app=prod_like, signer=_ProdSigner(),
                                        verification=_NotProdVerification(), required_binding_kinds=KINDS, clock=clock)
    with pytest.raises(SeamConfigurationError, match="required binding kind"):
        EnvelopeIssuanceSeam.production(app=prod_like, signer=_ProdSigner(),
                                        verification=_Verification(), required_binding_kinds=(), clock=clock)
    seam = EnvelopeIssuanceSeam.production(app=prod_like, signer=_ProdSigner(),
                                           verification=_Verification(), required_binding_kinds=KINDS, clock=clock)
    assert seam.is_production is True


def test_reference_seam_refuses_a_production_application(world):
    clock, app, case, decision = world
    prod_like = type("App", (), {"_production_mode": True})()
    with pytest.raises(SeamConfigurationError):
        EnvelopeIssuanceSeam.reference(app=prod_like, key_record=KEY_RECORD, clock=clock,
                                       verification=_Verification())


def test_signer_and_verification_ports_are_runtime_checkable():
    assert isinstance(ReferenceEnvelopeSigner(KEY_RECORD), EnvelopeSignerPort)
    assert isinstance(_ProdSigner(), EnvelopeSignerPort)
    assert isinstance(_Verification(), ArtifactVerificationPort)
    assert ReferenceEnvelopeSigner(KEY_RECORD).is_production_authoritative is False


def test_legacy_paths_stay_contained_in_production_mode():
    """D-4: the seam lifts nothing else. The case-based path and ActionGate stay contained."""

    from tests.seam.test_facade_containment import _prod_kwargs
    app = RiskAuthorityApplication(**_prod_kwargs())
    with pytest.raises(ProductionContainmentError):
        app.issue_envelope("t", "c", IssueEnvelopeRequest(decision_id="d", audience="a",
                                                          session_id="s", nonce="n"))
    with pytest.raises(ProductionContainmentError):
        app.authorize_action(AuthorizeActionRequest(envelope_id="e", tenant_id="t", actor_id="a",
                                                    model_id="m", session_id="s", action_type="x",
                                                    target_id="t", purpose="p"))


# --------------------------------------------------------------------------- #
# Domain additions
# --------------------------------------------------------------------------- #
def test_artifact_binding_and_bindings_validate():
    with pytest.raises(ValueError):
        ArtifactBinding(" kind", _hex("x"))
    with pytest.raises(ValueError):
        ArtifactBinding("kind", "abc")
    with pytest.raises(ValueError):
        EnvelopeBindings("w", "e", "m", 1, artifact_bindings=(ArtifactBinding("k", _hex("a")),
                                                              ArtifactBinding("k", _hex("b"))))
    legacy = EnvelopeBindings("w", "e", "m", 1)
    assert legacy.artifact_bindings == () and legacy.binding_for("k") is None


def test_issuer_requires_exactly_one_signing_path(world):
    clock, app, case, decision = world
    from risk_authority.domain.errors import RiskAuthorityError
    from risk_authority.services.envelope_issuer import EnvelopeIssuer
    issuer = EnvelopeIssuer(issuer="x")
    common = dict(envelope_id="e", decision=decision, audience="a", subject="s", model_id="m",
                  session_id="s", nonce="n", revocation_state=app.revocation, now=NOW)
    with pytest.raises(RiskAuthorityError, match="exactly one"):
        issuer.issue(**common)
    with pytest.raises(RiskAuthorityError, match="exactly one"):
        issuer.issue(**common, key_record=KEY_RECORD, signer=ReferenceEnvelopeSigner(KEY_RECORD))
    assert issuer.issue(**common, signer=ReferenceEnvelopeSigner(KEY_RECORD)).key_id == S.KEY_ID
