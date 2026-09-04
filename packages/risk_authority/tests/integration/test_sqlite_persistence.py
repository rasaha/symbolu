"""The durable store: D-1 backend, D-3 identity, D-4 revocation, D-5 posture, and the
acceptance test — a Phase 5 envelope issued from a reopened store, by a fresh application."""

from __future__ import annotations

import os
import sqlite3
import tempfile

import pytest

from risk_authority.api import (
    VERIFIED,
    ControlResultInput,
    CreateCaseRequest,
    DecisionRequest,
    EnvelopeIssuanceRequest,
    EnvelopeIssuanceSeam,
    EvaluateRequest,
    RiskAuthorityApplication,
    RiskEvaluationSeam,
    VerifiedArtifactBinding,
)
from risk_authority.crypto import SigningKey, SigningKeyRecord
from risk_authority.crypto.canonical import to_canonical_obj
from risk_authority.crypto.hashing import digest
from risk_authority.domain import RiskClass
from risk_authority.domain.enums import RiskCaseState
from risk_authority.integrations import InMemoryWorkflowIRSource
from risk_authority.persistence import (
    PersistenceConflictError,
    PersistenceProductionModeError,
    PersistenceStorageError,
    SqliteRevocationState,
    SqliteRiskAuthorityStore,
)

from tests import scenario as S
from tests.seam.test_facade_containment import _prod_kwargs

KEY = SigningKeyRecord(S.KEY_ID, SigningKey.from_seed(bytes(range(32))))
NOW = S.FIXED_NOW


@pytest.fixture
def path(tmp_path):
    return str(tmp_path / "risk-authority.sqlite")


def _app(store, clock=lambda: NOW) -> RiskAuthorityApplication:
    source = InMemoryWorkflowIRSource()
    source.register(S.build_workflow())
    return RiskAuthorityApplication(workflow_source=source, key_record=KEY, clock=clock, persistence=store)


def _decide(app, case_id="rdc_d"):
    app.authority.add_grant(S.build_grant())
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
    return app.issue_decision(S.TENANT, case_id, evaluation,
                              DecisionRequest(principal_id=S.PRINCIPAL, requested_scope=S.FINANCE_SCOPE))


class _Verification:
    is_production_authoritative = True

    def verify(self, *, as_of):
        return (VerifiedArtifactBinding("k", "a" * 64, VERIFIED, as_of),)


# --------------------------------------------------------------------------- #
# Acceptance: evaluate, close, reopen elsewhere, issue through the seam, verify
# --------------------------------------------------------------------------- #
def test_an_envelope_is_issued_from_a_reopened_store_by_a_fresh_application(path):
    store = SqliteRiskAuthorityStore(path)
    decision = _decide(_app(store))
    store.close()

    reopened = SqliteRiskAuthorityStore(path)
    app = _app(reopened)
    assert app.decisions.get(S.TENANT, decision.decision_id) == decision
    seam = EnvelopeIssuanceSeam.reference(app=app, key_record=KEY, verification=_Verification(),
                                          clock=lambda: NOW, required_binding_kinds=("k",))
    out = seam.issue(EnvelopeIssuanceRequest(
        tenant_id=S.TENANT, decision_id=decision.decision_id,
        decision_digest=digest(to_canonical_obj(decision)), audience="a", session_id="s", nonce="n"))
    assert out.issued, (out.refusal, out.detail)
    assert app.verify_envelope(S.TENANT, out.envelope.envelope_id).valid
    assert app.cases.get(S.TENANT, decision.case_id).state is RiskCaseState.ACTIVE
    assert reopened.verify_chain()
    reopened.close()

    third = SqliteRiskAuthorityStore(path)
    again = _app(third)
    assert again.envelopes.get(S.TENANT, out.envelope.envelope_id) == out.envelope
    assert again.verify_envelope(S.TENANT, out.envelope.envelope_id).valid


def test_the_evaluation_seam_persists_through_the_same_bundle(path):
    store = SqliteRiskAuthorityStore(path)
    source = InMemoryWorkflowIRSource()
    source.register(S.build_workflow())
    seam = RiskEvaluationSeam.reference(workflow_source=source, key_record=KEY, clock=lambda: NOW,
                                        persistence=store)
    assert seam._app.decisions is store.decisions and seam._app.revocation is store.revocation


# --------------------------------------------------------------------------- #
# D-3: identity
# --------------------------------------------------------------------------- #
def test_ids_never_restart_after_a_reopen(path):
    store = SqliteRiskAuthorityStore(path)
    first = [store.ids.next("rae") for _ in range(3)]
    store.close()
    assert SqliteRiskAuthorityStore(path).ids.next("rae") == "rae_000004"
    assert first == ["rae_000001", "rae_000002", "rae_000003"]


def test_immutable_artifacts_refuse_an_existing_id(path):
    store = SqliteRiskAuthorityStore(path)
    decision = _decide(_app(store))
    other = _app(SqliteRiskAuthorityStore(str(path) + ".b"))
    other.authority.add_grant(S.build_grant())
    envelope = S.approved_envelope(other, case_id="rdc_x")[2]
    with pytest.raises(PersistenceConflictError):
        store.decisions.save(decision)
    store.envelopes.save(envelope)
    with pytest.raises(PersistenceConflictError):
        store.envelopes.save(envelope)
    event = store.events.for_aggregate(S.TENANT, decision.case_id)[0]
    with pytest.raises(PersistenceConflictError):
        store.events.append(event)


def test_a_case_is_updated_as_the_same_aggregate_and_refused_as_another(path):
    store = SqliteRiskAuthorityStore(path)
    app = _app(store)
    decision = _decide(app)
    case = app.cases.get(S.TENANT, decision.case_id)
    case.transition(target=RiskCaseState.ENVELOPE_ISSUED, actor="t", reason="r", now=NOW)
    store.cases.save(case)  # same aggregate, one more event: an update
    assert store.cases.get(S.TENANT, case.case_id).state is RiskCaseState.ENVELOPE_ISSUED
    snap = case.snapshot()
    from dataclasses import replace
    from risk_authority.domain import RiskDecisionCase
    impostor = RiskDecisionCase.from_snapshot(replace(snap, subject_id="someone-else"))
    with pytest.raises(PersistenceConflictError):
        store.cases.save(impostor)
    shorter = RiskDecisionCase.from_snapshot(replace(snap, events=snap.events[:-1], seq=snap.seq - 1))
    with pytest.raises(PersistenceConflictError):
        store.cases.save(shorter)


def test_grants_and_control_results_replace_and_evidence_is_write_once(path):
    store = SqliteRiskAuthorityStore(path)
    grant = S.build_grant()
    store.authority.add_grant(grant)
    from dataclasses import replace
    store.authority.add_grant(replace(grant, max_autonomy=1))
    assert store.authority.get_grant(S.TENANT, S.PRINCIPAL).max_autonomy == 1
    from risk_authority.domain import ControlResult
    from risk_authority.domain.enums import ControlStatus
    r = ControlResult(control_id="C", status=ControlStatus.PASS, evaluated_at=NOW)
    store.controls.put(S.TENANT, "c1", (r,))
    store.controls.put(S.TENANT, "c1", ())
    assert store.controls.get(S.TENANT, "c1") == () and store.controls.get(S.TENANT, "nope") == ()
    from risk_authority.domain import ControlEvidenceRecord
    from risk_authority.domain.enums import EvidenceState
    from risk_authority.domain.evidence import EvidenceAdmission
    ev = ControlEvidenceRecord(evidence_id="e1", tenant_id=S.TENANT, type="t", subject_id=S.ACTOR, issuer="i",
                               created_at=NOW, valid_until=None, digest="sha256:" + "a" * 64,
                               admission=EvidenceAdmission(status=EvidenceState.ADMITTED))
    store.evidence.save(ev)
    assert store.evidence.get(S.TENANT, "e1") == ev
    with pytest.raises(PersistenceConflictError):
        store.evidence.save(ev)
    assert store.verify_chain()


def test_tenant_isolation_holds_in_the_durable_store(path):
    store = SqliteRiskAuthorityStore(path)
    decision = _decide(_app(store))
    assert store.decisions.get("other-tenant", decision.decision_id) is None
    assert store.cases.get("other-tenant", decision.case_id) is None


# --------------------------------------------------------------------------- #
# D-1: the ledger is append-only and tamper-evident
# --------------------------------------------------------------------------- #
def test_tampering_with_a_stored_record_or_the_ledger_is_detected(path):
    store = SqliteRiskAuthorityStore(path)
    decision = _decide(_app(store))
    assert store.verify_chain()
    raw = sqlite3.connect(path)
    raw.execute("UPDATE risk_decisions SET record_json = replace(record_json, 'ALLOW', 'ALLOX') "
                "WHERE decision_id=?", (decision.decision_id,))
    raw.commit()
    assert not store.verify_chain()
    with pytest.raises(sqlite3.DatabaseError):
        raw.execute("DELETE FROM ledger_events")
    with pytest.raises(sqlite3.DatabaseError):
        raw.execute("UPDATE ledger_events SET chain_digest='x'")
    with pytest.raises(sqlite3.DatabaseError):
        raw.execute("DELETE FROM governance_events")


def test_a_schema_from_another_version_is_refused(path):
    SqliteRiskAuthorityStore(path).close()
    raw = sqlite3.connect(path)
    raw.execute("UPDATE meta SET value='risk-authority-sqlite-0' WHERE key='schema_version'")
    raw.commit()
    with pytest.raises(PersistenceStorageError):
        SqliteRiskAuthorityStore(path)


def test_a_closed_store_refuses_every_operation(path):
    store = SqliteRiskAuthorityStore(path)
    store.close()
    with pytest.raises(PersistenceStorageError):
        store.decisions.get(S.TENANT, "x")
    with pytest.raises(PersistenceStorageError):
        store.ids.next("rae")


# --------------------------------------------------------------------------- #
# D-4: revocation survives a restart
# --------------------------------------------------------------------------- #
def test_epochs_and_revocations_are_rebuilt_on_open(path):
    store = SqliteRiskAuthorityStore(path)
    assert isinstance(store.revocation, SqliteRevocationState)
    assert store.revocation.advance_epoch(S.TENANT) == 2
    store.revocation.revoke_envelope("rae_000009")
    store.revocation.revoke_subject(S.TENANT, "agent-x")
    store.revocation.revoke_model(S.TENANT, "model-x")
    store.close()
    again = SqliteRiskAuthorityStore(path).revocation
    assert again.current_epoch(S.TENANT) == 2 and again.current_epoch("other") == 1
    assert again.is_revoked(tenant_id=S.TENANT, envelope_id="rae_000009", subject_id="s", model_id="m",
                            envelope_epoch=2) == "envelope explicitly revoked"
    assert again.is_revoked(tenant_id=S.TENANT, envelope_id="e", subject_id="agent-x", model_id="m",
                            envelope_epoch=2) == "subject revoked"
    assert again.is_revoked(tenant_id=S.TENANT, envelope_id="e", subject_id="s", model_id="model-x",
                            envelope_epoch=2) == "model revoked"
    assert "stale authority epoch" in again.is_revoked(tenant_id=S.TENANT, envelope_id="e", subject_id="s",
                                                       model_id="m", envelope_epoch=1)


def test_an_epoch_advance_persisted_elsewhere_invalidates_the_envelope_here(path):
    store = SqliteRiskAuthorityStore(path)
    app = _app(store)
    app.authority.add_grant(S.build_grant())
    _, _, envelope = S.approved_envelope(app, case_id="rdc_e")
    assert app.verify_envelope(S.TENANT, envelope.envelope_id).valid
    store.close()
    SqliteRiskAuthorityStore(path).revocation.advance_epoch(S.TENANT)
    fresh = _app(SqliteRiskAuthorityStore(path))
    assert not fresh.verify_envelope(S.TENANT, envelope.envelope_id).valid


# --------------------------------------------------------------------------- #
# D-5: production posture
# --------------------------------------------------------------------------- #
def test_production_mode_refuses_the_in_memory_reference_stores():
    kw = _prod_kwargs()
    kw.pop("persistence")
    with pytest.raises(PersistenceProductionModeError, match="cases"):
        RiskAuthorityApplication(**kw)


def test_production_mode_refuses_an_in_memory_sqlite_database():
    store = SqliteRiskAuthorityStore(":memory:")
    assert store.is_production_authoritative is False
    with pytest.raises(PersistenceProductionModeError):
        RiskAuthorityApplication(**_prod_kwargs(persistence=store))


def test_production_mode_refuses_a_bundle_mixed_with_individual_stores(path):
    from risk_authority.persistence import InMemoryDecisionRepository
    with pytest.raises(PersistenceProductionModeError, match="beside"):
        RiskAuthorityApplication(**_prod_kwargs(persistence=SqliteRiskAuthorityStore(path),
                                                decisions=InMemoryDecisionRepository()))


def test_production_mode_refuses_one_reference_store_among_durable_ones(path):
    from risk_authority.services.revocation import RevocationState
    store = SqliteRiskAuthorityStore(path)
    kw = _prod_kwargs()
    kw.pop("persistence")
    kw.update(cases=store.cases, decisions=store.decisions, envelopes=store.envelopes,
              authority=store.authority, controls=store.controls, events=store.events,
              ids=store.ids, revocation=RevocationState())
    with pytest.raises(PersistenceProductionModeError, match="revocation"):
        RiskAuthorityApplication(**kw)


def test_production_mode_constructs_over_a_file_backed_store_and_stays_contained(path):
    app = RiskAuthorityApplication(**_prod_kwargs(persistence=SqliteRiskAuthorityStore(path)))
    assert app._production_mode is True and app.decisions.is_production_authoritative
    from risk_authority.api import IssueEnvelopeRequest
    from risk_authority.domain.errors import ProductionContainmentError
    with pytest.raises(ProductionContainmentError):
        app.issue_envelope("t", "c", IssueEnvelopeRequest(decision_id="d", audience="a", session_id="s", nonce="n"))


def test_reference_mode_still_defaults_to_the_in_memory_stores():
    app = S.build_application()
    assert getattr(app.decisions, "is_production_authoritative", False) is False


def test_the_store_reads_no_clock():
    import ast
    import pathlib
    import risk_authority.persistence as pkg
    for path_ in pathlib.Path(pkg.__file__).parent.glob("*.py"):
        for node in ast.walk(ast.parse(path_.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                assert name not in {"now", "utcnow", "today", "time", "monotonic"}, (path_.name, name)
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mod = getattr(node, "module", None) or ""
                names = [a.name for a in node.names]
                assert "time" not in names and not mod.startswith("time"), path_.name
