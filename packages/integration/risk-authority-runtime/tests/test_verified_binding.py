"""The verified production path — envelope binding and posture (ADR §2, §8/D-A…D-E).

What these prove, stated precisely so the suite cannot be misread as proving more:

* the binding rejects evidence that does not cohere, and does so as a ``BindingViolation``
  rather than as a Risk Authority denial;
* a reference-produced result is structurally unable to enter the production composition
  path — the requirement ADR §8/D-E names;
* the production composition path refuses a raw ``RiskAuthorityMachineResult``, which is
  the deployment-supplied object ADR §2 rules non-authoritative.

They do **not** prove that ``VerifiedRiskAuthorityResult`` is unforgeable. It is not, and
ADR §8/D-B says so: the type prevents accidental mixing; the envelope and the binding
checks are what establish trust.
"""

from __future__ import annotations

import pytest
from risk_authority.domain import ActionGateDecision
from risk_authority.domain.actions import ActionAuthorization
from risk_authority.integrations import ReferenceActionGate

from ugence_risk_authority_runtime import (
    BindingViolation,
    EnforcerConfigurationError,
    ProductionCompositionError,
    RiskAuthorityCompositionEngine,
    RiskAuthorityEnforcer,
    VerifiedRiskAuthorityResult,
    verify_and_bind,
)
from ugence_risk_authority_runtime.contracts import (
    GovernanceVetoResult,
    RiskAuthorityDisposition,
    VetoDisposition,
)

DA_NO_VETO = GovernanceVetoResult(
    source="decision_authority", disposition=VetoDisposition.NO_VETO)
AG_NO_VETO = GovernanceVetoResult(source="actiongate", disposition=VetoDisposition.NO_VETO)


def _authorize(ra, action=None, identity=None):
    action = action if action is not None else ra.action()
    return ReferenceActionGate().authorize(
        authorization_id="auth_1",
        envelope=ra.envelope,
        action=action,
        identity=identity if identity is not None else ra.identity(),
        key_ring=ra.key_ring,
        revocation_state=ra.revocation,
        now=ra.now,
    ), action


def _bind(ra, *, authorization, action, production=False):
    return verify_and_bind(
        envelope=ra.envelope,
        authorization=authorization,
        action=action,
        identity=ra.identity(),
        key_ring=ra.key_ring,
        revocation_state=ra.revocation,
        now=ra.now,
        production=production,
    )


# --------------------------------------------------------------- D-A: the binding
def test_a_verified_allow_carries_the_envelope_binding(ra):
    auth, action = _authorize(ra)
    v = _bind(ra, authorization=auth, action=action)

    assert v.result.disposition is RiskAuthorityDisposition.ALLOW
    assert v.envelope_id == ra.envelope.envelope_id
    assert v.action_digest == action.digest == auth.action_digest
    assert v.decision_id == ra.envelope.decision_id
    assert v.workflow_ir_digest  # policy identity present
    assert v.verified_at == ra.now
    assert v.not_before == ra.envelope.not_before
    assert v.expires_at == ra.envelope.expires_at


def test_b_envelope_digest_is_over_the_canonical_signing_payload(ra):
    """D-C: the repository's established algorithm and identifier, nothing new."""

    from risk_authority.crypto.hashing import sha256_hex

    auth, action = _authorize(ra)
    v = _bind(ra, authorization=auth, action=action)

    assert v.envelope_digest == sha256_hex(ra.envelope.signing_payload())
    assert v.envelope_digest.startswith("sha256:")
    # envelope_id is caller-supplied, not content-addressed — so the digest is retained
    # rather than reusing the id (ADR §8/D-C).
    assert v.envelope_digest != v.envelope_id


@pytest.mark.parametrize("field,value", [
    ("envelope_id", "rae_other"),
    ("action_digest", "sha256:" + "0" * 64),
    ("tenant_id", "tenant_other"),
])
def test_c_incoherent_authorization_is_a_binding_violation_not_a_denial(ra, field, value):
    """A mismatch means Risk Authority was never coherently asked — never 'RA denied'."""

    auth, action = _authorize(ra)
    forged = ActionAuthorization(**{**{
        "authorization_id": auth.authorization_id,
        "envelope_id": auth.envelope_id,
        "action_digest": auth.action_digest,
        "decision": auth.decision,
        "tenant_id": auth.tenant_id or ra.envelope.tenant_id,
        "reason_codes": auth.reason_codes,
    }, field: value})

    with pytest.raises(BindingViolation):
        _bind(ra, authorization=forged, action=action)


def test_d_a_substituted_action_cannot_reuse_an_authorization(ra):
    """The action digest is the binding: another action does not inherit this verdict."""

    auth, _ = _authorize(ra)
    with pytest.raises(BindingViolation):
        _bind(ra, authorization=auth, action=ra.action(target_id="txn_substituted"))


def test_e_a_denied_verdict_binds_and_stays_denied(ra):
    auth, action = _authorize(ra)
    denied = ActionAuthorization(
        authorization_id=auth.authorization_id,
        envelope_id=auth.envelope_id,
        action_digest=auth.action_digest,
        decision=ActionGateDecision.DENIED,
        tenant_id=ra.envelope.tenant_id,
        reason_codes=("scope mismatch",),
    )
    v = _bind(ra, authorization=denied, action=action)

    assert v.result.disposition is RiskAuthorityDisposition.DENY
    assert v.authorized is False
    assert "scope mismatch" in v.result.raw_reason_codes


# --------------------------------------------------------------- D-B: the type
def test_f_a_consumer_cannot_construct_a_verified_result(ra):
    auth, action = _authorize(ra)
    genuine = _bind(ra, authorization=auth, action=action)

    with pytest.raises(BindingViolation):
        VerifiedRiskAuthorityResult(
            result=genuine.result,
            envelope_id=genuine.envelope_id,
            envelope_digest=genuine.envelope_digest,
            action_digest=genuine.action_digest,
            authorization_id=genuine.authorization_id,
            workflow_ir_digest=genuine.workflow_ir_digest,
            decision_id=genuine.decision_id,
            authority_epoch=genuine.authority_epoch,
            not_before=genuine.not_before,
            expires_at=genuine.expires_at,
            verified_at=genuine.verified_at,
            production=True,
        )


def test_g_production_composition_refuses_a_raw_machine_result(ra):
    """ADR §2: the deployment-supplied object is not a trust boundary."""

    raw = ra.enforce()  # the pre-0.2.0 shape a GovernanceInputSource used to supply
    with pytest.raises(ProductionCompositionError):
        RiskAuthorityCompositionEngine().compose_verified(
            risk_authority=raw, decision_authority=DA_NO_VETO, actiongate=AG_NO_VETO)


def test_h_production_composition_refuses_a_look_alike(ra):
    class _LooksVerified:
        production = True

        def __init__(self, result):
            self.result = result

    with pytest.raises(ProductionCompositionError):
        RiskAuthorityCompositionEngine().compose_verified(
            risk_authority=_LooksVerified(ra.enforce()),
            decision_authority=DA_NO_VETO, actiongate=AG_NO_VETO)


# --------------------------------------------------------------- D-E: posture
def test_i_reference_results_cannot_enter_the_production_path(ra):
    """The requirement ADR §8/D-E names, proven rather than asserted."""

    enforcer = RiskAuthorityEnforcer.reference()
    assert enforcer.is_production is False

    verified = enforcer.derive(
        authorization_id="auth_ref",
        envelope=ra.envelope,
        action=ra.action(),
        identity=ra.identity(),
        key_ring=ra.key_ring,
        revocation_state=ra.revocation,
        now=ra.now,
    )
    assert verified.result.disposition is RiskAuthorityDisposition.ALLOW
    assert verified.production is False

    with pytest.raises(ProductionCompositionError):
        RiskAuthorityCompositionEngine().compose_verified(
            risk_authority=verified, decision_authority=DA_NO_VETO, actiongate=AG_NO_VETO)


def test_j_implicit_reference_construction_is_refused(ra):
    """The 0.2.0 typed refusal — no warning-only transition (ADR §8/D-E)."""

    with pytest.raises(TypeError):
        RiskAuthorityEnforcer()  # noqa: PLE1120 - the point of the test
    with pytest.raises(EnforcerConfigurationError):
        RiskAuthorityEnforcer(None)


def test_k_production_factory_refuses_the_reference_gate(ra):
    with pytest.raises(EnforcerConfigurationError):
        RiskAuthorityEnforcer.production(gate=ReferenceActionGate())

    class _Subclass(ReferenceActionGate):
        is_production_authoritative = True

    with pytest.raises(EnforcerConfigurationError):
        RiskAuthorityEnforcer.production(gate=_Subclass())


def test_l_production_factory_requires_a_declared_posture(ra):
    class _Silent:
        def authorize(self, **kw):  # pragma: no cover - never reached
            raise AssertionError

    with pytest.raises(EnforcerConfigurationError):
        RiskAuthorityEnforcer.production(gate=_Silent())


def test_m_a_production_gate_yields_a_composable_verified_result(ra):
    """The whole chain: production gate → binding → production composition → GRANT."""

    class _ProductionGate:
        is_production_authoritative = True

        def authorize(self, **kw):
            return ReferenceActionGate().authorize(**kw)

    enforcer = RiskAuthorityEnforcer.production(gate=_ProductionGate())
    assert enforcer.is_production is True

    verified = enforcer.derive(
        authorization_id="auth_prod",
        envelope=ra.envelope,
        action=ra.action(),
        identity=ra.identity(),
        key_ring=ra.key_ring,
        revocation_state=ra.revocation,
        now=ra.now,
    )
    assert verified.production is True

    decision = RiskAuthorityCompositionEngine().compose_verified(
        risk_authority=verified, decision_authority=DA_NO_VETO, actiongate=AG_NO_VETO)
    assert decision.final_disposition.executable is True


def test_n_a_revoked_envelope_denies_through_the_verified_path(ra):
    """Verification is genuinely performed here, not inherited from the caller."""

    auth, action = _authorize(ra)
    ra.revocation.revoke_envelope(ra.envelope.envelope_id)

    v = _bind(ra, authorization=auth, action=action)
    assert v.result.disposition is RiskAuthorityDisposition.DENY
    assert v.authorized is False
