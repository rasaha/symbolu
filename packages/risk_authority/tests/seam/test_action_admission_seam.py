"""Phase 5C action admission seam (ADR 5C D-1, D-3, D-4, D-5): kernel verification first,
derived ids, replay, a port that may only say AUTHORIZED or DENIED, and no execution."""

from __future__ import annotations

import ast
import inspect
from dataclasses import replace
from datetime import timedelta

import pytest

from risk_authority.api import (
    AUTHORIZATION_ID_PREFIX,
    ActionAdmissionOutcome,
    ActionAdmissionRefusal as R,
    ActionAdmissionRequest,
    ActionAdmissionSeam,
    AuthorizeActionRequest,
    RiskAuthorityApplication,
    SeamConfigurationError,
    derive_authorization_id,
)
from risk_authority.api import action_admission_seam as seam_module
from risk_authority.crypto import SigningKey, SigningKeyRecord
from risk_authority.domain.actions import ActionAuthorization, CanonicalAction
from risk_authority.domain.enums import ActionGateDecision, AuthorizationDisposition, GovernanceEventType
from risk_authority.domain.errors import ProductionContainmentError, RiskAuthorityError
from risk_authority.integrations import InMemoryWorkflowIRSource
from risk_authority.integrations.actiongate import ReferenceActionGate
from risk_authority.persistence import PersistenceConflictError, SqliteRiskAuthorityStore

from tests import scenario as S
from tests.seam.test_facade_containment import _prod_kwargs

NOW = S.FIXED_NOW
KEY = SigningKeyRecord(S.KEY_ID, SigningKey.from_seed(bytes(range(32))))


class _Clock:
    def __init__(self, at=NOW):
        self.at, self.reads = at, 0

    def __call__(self):
        self.reads += 1
        return self.at


def _action(**over) -> CanonicalAction:
    base = dict(tenant_id=S.TENANT, actor_id=S.ACTOR, model_id=S.MODEL, action_type="crm.read",
                target_id="txn_123", purpose="CUSTOMER_REFUND_REVIEW", destination="internal://finance")
    base.update(over)
    return CanonicalAction(**base)


def _request(envelope, **over) -> ActionAdmissionRequest:
    base = dict(tenant_id=S.TENANT, envelope_id=envelope.envelope_id, action=_action(), session_id="sess_1")
    base.update(over)
    return ActionAdmissionRequest(**base)


@pytest.fixture
def world():
    clock = _Clock()
    app = S.build_application()
    app._clock = clock
    _, _, envelope = S.approved_envelope(app)
    clock.reads = 0
    return clock, app, envelope


# --------------------------------------------------------------------------- #
# The act
# --------------------------------------------------------------------------- #
def test_a_valid_action_is_admitted_with_a_derived_id_the_envelope_expiry_and_an_event(world):
    clock, app, envelope = world
    out = ActionAdmissionSeam.reference(app=app, clock=clock).issue(_request(envelope))
    assert type(out) is ActionAdmissionOutcome and out.admitted and out.refusal is None
    auth = out.authorization
    assert auth.authorization_id == derive_authorization_id(
        tenant_id=S.TENANT, envelope_id=envelope.envelope_id, action_digest=_action().digest)
    assert auth.authorization_id.startswith(AUTHORIZATION_ID_PREFIX)
    assert auth.disposition is AuthorizationDisposition.ADMITTED
    assert auth.expires_at == envelope.expires_at and auth.tenant_id == S.TENANT
    assert app.authorizations.get(S.TENANT, auth.authorization_id) == auth
    assert app.events.for_aggregate(S.TENANT, envelope.envelope_id)[-1].event_type is GovernanceEventType.ACTION_AUTHORIZED
    assert out.executable is False and auth.executable is False
    assert clock.reads == 1


def test_re_admission_of_the_same_action_replays_the_stored_verdict(world):
    clock, app, envelope = world
    seam = ActionAdmissionSeam.reference(app=app, clock=clock)
    first = seam.issue(_request(envelope)).authorization
    events_before = len(app.events.for_aggregate(S.TENANT, envelope.envelope_id))
    again = seam.issue(_request(envelope))
    assert again.replayed and again.admitted
    assert again.authorization == replace(first, disposition=AuthorizationDisposition.REPLAYED)
    assert len(app.events.for_aggregate(S.TENANT, envelope.envelope_id)) == events_before
    assert clock.reads == 2


def test_a_denied_verdict_is_persisted_emitted_and_replayed_as_denied(world):
    clock, app, envelope = world
    seam = ActionAdmissionSeam.reference(app=app, clock=clock)
    denied = seam.issue(_request(envelope, action=_action(action_type="refund.execute")))
    assert not denied.admitted and denied.refusal is None
    assert denied.authorization.decision is ActionGateDecision.DENIED
    assert app.events.for_aggregate(S.TENANT, envelope.envelope_id)[-1].event_type is GovernanceEventType.ACTION_DENIED
    again = seam.issue(_request(envelope, action=_action(action_type="refund.execute")))
    assert again.replayed and not again.admitted


def test_different_actions_under_one_envelope_get_different_ids(world):
    clock, app, envelope = world
    seam = ActionAdmissionSeam.reference(app=app, clock=clock)
    a = seam.issue(_request(envelope)).authorization
    b = seam.issue(_request(envelope, action=_action(target_id="txn_999"))).authorization
    assert a.authorization_id != b.authorization_id and a.action_digest != b.action_digest


# --------------------------------------------------------------------------- #
# Kernel verification runs before the port (D-4)
# --------------------------------------------------------------------------- #
class _SpyGate:
    is_production_authoritative = True

    def __init__(self):
        self.calls = []
        self._inner = ReferenceActionGate()

    def authorize(self, **kw):
        self.calls.append(kw["authorization_id"])
        return self._inner.authorize(**kw)


@pytest.mark.parametrize("mutate, expected", [
    (lambda env, clock, app: setattr(clock, "at", env.expires_at + timedelta(seconds=1)), R.ENVELOPE_INVALID),
    (lambda env, clock, app: app.revocation.advance_epoch(S.TENANT), R.ENVELOPE_INVALID),
    (lambda env, clock, app: app.revocation.revoke_envelope(env.envelope_id), R.ENVELOPE_INVALID),
])
def test_an_invalid_envelope_is_refused_before_the_port_runs(world, mutate, expected):
    clock, app, envelope = world
    gate = _SpyGate()
    mutate(envelope, clock, app)
    out = ActionAdmissionSeam.reference(app=app, clock=clock, gate=gate).issue(_request(envelope))
    assert out.refusal is expected and out.authorization is None and gate.calls == []


def test_a_session_or_tenant_mismatch_is_refused_in_the_kernel(world):
    clock, app, envelope = world
    gate = _SpyGate()
    seam = ActionAdmissionSeam.reference(app=app, clock=clock, gate=gate)
    assert seam.issue(_request(envelope, session_id="other")).refusal is R.ENVELOPE_INVALID
    assert seam.issue(_request(envelope, tenant_id="other", action=_action(tenant_id="other"))).refusal is R.ENVELOPE_NOT_FOUND
    assert gate.calls == []


def test_a_forged_signature_is_refused_in_the_kernel(world):
    clock, app, envelope = world
    forged = replace(envelope, signature=bytes(64))
    app.envelopes._envelopes[(S.TENANT, envelope.envelope_id)] = forged
    gate = _SpyGate()
    out = ActionAdmissionSeam.reference(app=app, clock=clock, gate=gate).issue(_request(envelope))
    assert out.refusal is R.ENVELOPE_INVALID and gate.calls == []


# --------------------------------------------------------------------------- #
# The port may say AUTHORIZED or DENIED and nothing else (D-4)
# --------------------------------------------------------------------------- #
class _Gate:
    is_production_authoritative = True

    def __init__(self, behaviour):
        self._b = behaviour

    def authorize(self, **kw):
        return self._b(kw)


@pytest.mark.parametrize("behaviour, reason", [
    (lambda kw: (_ for _ in ()).throw(RuntimeError("down")), "gate raised RuntimeError"),
    (lambda kw: "AUTHORIZED", "foreign result type"),
    (lambda kw: ActionAuthorization(authorization_id=kw["authorization_id"], envelope_id=kw["envelope"].envelope_id,
                                    action_digest=kw["action"].digest, decision=ActionGateDecision.RETRY_STATE_CHANGED),
     "only AUTHORIZED or DENIED"),
    (lambda kw: ActionAuthorization(authorization_id="auth.v1:" + "0" * 64, envelope_id=kw["envelope"].envelope_id,
                                    action_digest=kw["action"].digest, decision=ActionGateDecision.AUTHORIZED),
     "does not name this authorization"),
    (lambda kw: ActionAuthorization(authorization_id=kw["authorization_id"], envelope_id="rae_other",
                                    action_digest=kw["action"].digest, decision=ActionGateDecision.AUTHORIZED),
     "does not name this authorization"),
])
def test_anything_but_authorized_or_denied_is_recorded_as_denied(world, behaviour, reason):
    clock, app, envelope = world
    out = ActionAdmissionSeam.reference(app=app, clock=clock, gate=_Gate(behaviour)).issue(_request(envelope))
    assert out.refusal is None and not out.admitted
    assert out.authorization.decision is ActionGateDecision.DENIED
    assert any(reason in r for r in out.authorization.reason_codes), out.authorization.reason_codes
    assert app.authorizations.get(S.TENANT, out.authorization.authorization_id) is not None


def test_a_port_that_authorizes_is_admitted_with_the_seams_identity_fields(world):
    clock, app, envelope = world
    gate = _Gate(lambda kw: ActionAuthorization(
        authorization_id=kw["authorization_id"], envelope_id=kw["envelope"].envelope_id,
        action_digest=kw["action"].digest, decision=ActionGateDecision.AUTHORIZED, expires_at=None))
    out = ActionAdmissionSeam.reference(app=app, clock=clock, gate=gate).issue(_request(envelope))
    assert out.admitted and out.authorization.expires_at == envelope.expires_at
    assert out.authorization.tenant_id == S.TENANT


# --------------------------------------------------------------------------- #
# Identity conflicts (D-3)
# --------------------------------------------------------------------------- #
def test_a_stored_authorization_naming_another_action_is_a_conflict(world):
    clock, app, envelope = world
    seam = ActionAdmissionSeam.reference(app=app, clock=clock)
    auth = seam.issue(_request(envelope)).authorization
    other = replace(auth, action_digest="sha256:" + "f" * 64)
    with pytest.raises(PersistenceConflictError):
        app.authorizations.save(other)
    app.authorizations._authorizations[(S.TENANT, auth.authorization_id)] = other
    out = seam.issue(_request(envelope))
    assert out.refusal is R.AUTHORIZATION_CONFLICT and out.authorization is None


def test_the_same_authorization_saved_twice_is_idempotent(world):
    clock, app, envelope = world
    auth = ActionAdmissionSeam.reference(app=app, clock=clock).issue(_request(envelope)).authorization
    app.authorizations.save(auth)
    assert app.authorizations.get(S.TENANT, auth.authorization_id) == auth


# --------------------------------------------------------------------------- #
# Durable: reopen and replay through SQLite
# --------------------------------------------------------------------------- #
def _durable_app(path, clock):
    store = SqliteRiskAuthorityStore(path)
    source = InMemoryWorkflowIRSource()
    source.register(S.build_workflow())
    app = RiskAuthorityApplication(workflow_source=source, key_record=KEY, clock=clock, persistence=store)
    app.authority.add_grant(S.build_grant())
    return store, app


def test_admission_is_replayed_by_a_fresh_application_over_a_reopened_store(tmp_path):
    path = str(tmp_path / "ra.sqlite")
    clock = _Clock()
    store, app = _durable_app(path, clock)
    _, _, envelope = S.approved_envelope(app)
    first = ActionAdmissionSeam.reference(app=app, clock=clock).issue(_request(envelope)).authorization
    assert store.verify_chain()
    store.close()

    store2, app2 = _durable_app(path, clock)
    again = ActionAdmissionSeam.reference(app=app2, clock=clock).issue(_request(envelope))
    assert again.replayed and again.authorization.authorization_id == first.authorization_id
    assert app2.authorizations.get(S.TENANT, first.authorization_id) == first
    with pytest.raises(PersistenceConflictError):
        store2.authorizations.save(replace(first, action_digest="sha256:" + "e" * 64))
    store2.revocation.advance_epoch(S.TENANT)
    store2.close()
    _, app3 = _durable_app(path, clock)
    fresh = ActionAdmissionSeam.reference(app=app3, clock=clock).issue(
        _request(envelope, action=_action(target_id="txn_new")))
    assert fresh.refusal is R.ENVELOPE_INVALID


# --------------------------------------------------------------------------- #
# Posture and containment (D-1, D-4, D-5)
# --------------------------------------------------------------------------- #
def test_production_refuses_reference_grade_dependencies(world, tmp_path):
    clock, app, envelope = world
    prod = RiskAuthorityApplication(**_prod_kwargs(persistence=SqliteRiskAuthorityStore(str(tmp_path / "p.sqlite"))))
    with pytest.raises(SeamConfigurationError, match="production mode"):
        ActionAdmissionSeam.production(app=app, gate=_SpyGate(), clock=clock)
    with pytest.raises(SeamConfigurationError, match="ReferenceActionGate"):
        ActionAdmissionSeam.production(app=prod, gate=ReferenceActionGate(), clock=clock)

    class Sub(ReferenceActionGate):
        is_production_authoritative = True

    with pytest.raises(SeamConfigurationError, match="ReferenceActionGate"):
        ActionAdmissionSeam.production(app=prod, gate=Sub(), clock=clock)

    class Silent:
        def authorize(self, **kw):  # pragma: no cover
            raise AssertionError

    with pytest.raises(SeamConfigurationError, match="is_production_authoritative"):
        ActionAdmissionSeam.production(app=prod, gate=Silent(), clock=clock)
    seam = ActionAdmissionSeam.production(app=prod, gate=_SpyGate(), clock=clock)
    assert seam.is_production is True
    with pytest.raises(SeamConfigurationError):
        ActionAdmissionSeam.reference(app=prod, clock=clock)


def test_the_legacy_authorize_action_stays_contained_in_production(tmp_path):
    prod = RiskAuthorityApplication(**_prod_kwargs(persistence=SqliteRiskAuthorityStore(str(tmp_path / "p.sqlite"))))
    with pytest.raises(ProductionContainmentError):
        prod.authorize_action(AuthorizeActionRequest(envelope_id="e", tenant_id="t", actor_id="a", model_id="m",
                                                     session_id="s", action_type="x", target_id="y", purpose="p"))


def test_production_mode_refuses_an_in_memory_authorization_store(tmp_path):
    from risk_authority.persistence import InMemoryAuthorizationRepository, PersistenceProductionModeError
    store = SqliteRiskAuthorityStore(str(tmp_path / "p.sqlite"))
    kw = _prod_kwargs()
    kw.pop("persistence")
    kw.update(cases=store.cases, decisions=store.decisions, envelopes=store.envelopes, authority=store.authority,
              controls=store.controls, events=store.events, revocation=store.revocation, ids=store.ids,
              authorizations=InMemoryAuthorizationRepository())
    with pytest.raises(PersistenceProductionModeError, match="authorizations"):
        RiskAuthorityApplication(**kw)


def test_the_seam_reads_the_clock_once_and_takes_no_caller_instant():
    src = inspect.getsource(seam_module.ActionAdmissionSeam.issue)
    calls = [n for n in ast.walk(ast.parse(inspect.getsource(seam_module)))
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "_clock"]
    assert len(calls) == 1
    assert "self._clock()" in src
    params = set(inspect.signature(ActionAdmissionRequest).parameters)
    assert not params & {"now", "as_of", "evaluation_time", "admitted_at"}


@pytest.mark.parametrize("field, value", [
    ("tenant_id", ""), ("session_id", " s"), ("envelope_id", None), ("satisfied_conditions", ["x"]),
])
def test_malformed_requests_are_refused(world, field, value):
    clock, app, envelope = world
    with pytest.raises(RiskAuthorityError):
        _request(envelope, **{field: value})


def test_an_action_for_another_tenant_cannot_ride_this_request(world):
    clock, app, envelope = world
    with pytest.raises(RiskAuthorityError):
        _request(envelope, action=_action(tenant_id="other"))


def test_action_authorization_is_typed_and_never_executable():
    with pytest.raises(TypeError):
        ActionAuthorization(authorization_id="a", envelope_id="e", action_digest="d",
                            decision=ActionGateDecision.DENIED, expires_at="2026-01-01")
    auth = ActionAuthorization(authorization_id="a", envelope_id="e", action_digest="d",
                               decision=ActionGateDecision.AUTHORIZED, expires_at=NOW)
    assert auth.executable is False and auth.disposition is AuthorizationDisposition.ADMITTED
