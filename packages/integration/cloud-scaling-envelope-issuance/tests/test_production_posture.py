"""The production factory fails closed on every reference-grade dependency (ADR D-5)."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone

import pytest

from risk_authority.api import RiskAuthorityApplication
from risk_authority.crypto import SigningKey, SigningKeyRecord
from risk_authority.domain import WorkflowIR, WorkflowStatus
from risk_authority.domain.errors import ProductionContainmentError
from risk_authority.integrations import InMemoryWorkflowIRSource
from risk_authority.persistence import SqliteRiskAuthorityStore
from risk_authority.services import ReferenceEnvelopeSigner
from risk_authority.services.decision_authority import ReferenceDecisionAuthority
from ugence_cloud_scaling_policy_authenticity import PolicyAuthenticityVerifier
from ugence_cloud_scaling_producer_attestation import (
    Ed25519ProducerSignatureVerifier,
    ProducerAttestationVerifier,
)

from _issuance_fixtures import KEY_RECORD, build_directory
from _policy_fixtures import issued_bounds, port_for

from ugence_cloud_scaling_envelope_issuance import (
    CloudScalingEnvelopeIssuance,
    EnvelopeIssuanceConfigurationError,
)

NOW = datetime(2026, 1, 1, 0, 6, tzinfo=timezone.utc)


# --- a production Risk Authority application, as Risk Authority's own containment suite builds it
class _Ingress:
    def is_trusted(self, evidence, *, now): return True


class _Admission:
    def is_admissible(self, record, *, now): return True


class _ControlAssurance:
    is_production_authoritative = True

    def evaluate(self, request):  # pragma: no cover
        raise AssertionError("not reached")


class _DecisionAuthority:
    is_production_authoritative = True

    def __init__(self): self._inner = ReferenceDecisionAuthority()

    def issue_decision(self, **kw): return self._inner.issue_decision(**kw)


def production_app() -> RiskAuthorityApplication:
    source = InMemoryWorkflowIRSource()
    source.register(WorkflowIR(workflow_ir_id="w", version="1", status=WorkflowStatus.ACTIVE,
                               rules=(), source_refs=(), effective_at=NOW).with_digest())
    return RiskAuthorityApplication(
        workflow_source=source, key_record=KEY_RECORD, clock=lambda: NOW,
        evidence_admission=_Admission(), control_assurance=_ControlAssurance(),
        evidence_ingress=_Ingress(), decision_authority=_DecisionAuthority(),
        persistence=SqliteRiskAuthorityStore(os.path.join(tempfile.mkdtemp(), "ra.sqlite")),
        production_mode=True,
    )


# --- production-grade upstream verifiers: delegating wrappers that opt in, never subclasses
class _ProductionDirectory:
    is_production_authoritative = True

    def __init__(self, inner): self._inner = inner

    def __getattr__(self, name): return getattr(self._inner, name)


class _ProductionPolicyPort:
    is_production_authoritative = True

    def __init__(self, inner): self._inner = inner

    @property
    def trust_configuration_digest(self): return self._inner.trust_configuration_digest

    def resolve_policy_version(self, *a, **kw): return self._inner.resolve_policy_version(*a, **kw)

    def __getattr__(self, name): return getattr(self._inner, name)


class _ProductionSigner:
    is_production_authoritative = True
    key_id = KEY_RECORD.key_id
    signature_alg = "ed25519"

    def sign(self, payload: bytes) -> bytes: return KEY_RECORD.signing_key.sign(payload)


def production_verifiers():
    authority, _ = issued_bounds()
    producer = ProducerAttestationVerifier(
        trust_anchor_resolver=_ProductionDirectory(build_directory()),
        signature_verifier=Ed25519ProducerSignatureVerifier(), production_mode=True)
    policy = PolicyAuthenticityVerifier(
        resolution_port=_ProductionPolicyPort(port_for(authority)), production_mode=True)
    return producer, policy


def reference_verifiers():
    authority, _ = issued_bounds()
    return (ProducerAttestationVerifier(trust_anchor_resolver=build_directory(),
                                        signature_verifier=Ed25519ProducerSignatureVerifier()),
            PolicyAuthenticityVerifier(resolution_port=port_for(authority)))


def _production(**over):
    producer, policy = production_verifiers()
    kw = dict(app=production_app(), signer=_ProductionSigner(), producer_verifier=producer,
              policy_verifier=policy, clock=lambda: NOW)
    kw.update(over)
    return CloudScalingEnvelopeIssuance.production(**kw)


def test_the_production_composition_constructs_over_production_grade_parts():
    root = _production()
    assert root.is_production is True


def test_production_refuses_a_reference_mode_application(world):
    with pytest.raises(EnvelopeIssuanceConfigurationError, match="production mode"):
        _production(app=world.app)


def test_production_refuses_the_reference_signer_and_a_silent_one():
    with pytest.raises(EnvelopeIssuanceConfigurationError, match="reference signer"):
        _production(signer=ReferenceEnvelopeSigner(KEY_RECORD))

    class Silent(_ProductionSigner):
        is_production_authoritative = False

    with pytest.raises(EnvelopeIssuanceConfigurationError, match="production-authoritative"):
        _production(signer=Silent())


def test_production_refuses_either_verifier_built_outside_production_mode():
    producer, policy = reference_verifiers()
    with pytest.raises(EnvelopeIssuanceConfigurationError, match="ProducerAttestationVerifier"):
        _production(producer_verifier=producer)
    with pytest.raises(EnvelopeIssuanceConfigurationError, match="PolicyAuthenticityVerifier"):
        _production(policy_verifier=policy)


def test_the_reference_composition_refuses_a_production_application():
    producer, policy = reference_verifiers()
    with pytest.raises(EnvelopeIssuanceConfigurationError):
        CloudScalingEnvelopeIssuance.reference(app=production_app(), key_record=KEY_RECORD,
                                               producer_verifier=producer, policy_verifier=policy,
                                               clock=lambda: NOW)


def test_the_legacy_issuance_and_actiongate_paths_stay_contained_in_production():
    """ADR D-4: the composition lifts nothing but the seam."""

    from risk_authority.api import AuthorizeActionRequest, IssueEnvelopeRequest
    app = production_app()
    with pytest.raises(ProductionContainmentError):
        app.issue_envelope("t", "c", IssueEnvelopeRequest(decision_id="d", audience="a",
                                                          session_id="s", nonce="n"))
    with pytest.raises(ProductionContainmentError):
        app.authorize_action(AuthorizeActionRequest(envelope_id="e", tenant_id="t", actor_id="a",
                                                    model_id="m", session_id="s", action_type="x",
                                                    target_id="y", purpose="p"))


def test_the_composition_holds_no_key_when_built_for_production():
    root = _production()
    assert root._key_record is None
    assert not any(isinstance(v, (SigningKey, SigningKeyRecord)) for v in vars(root).values())
