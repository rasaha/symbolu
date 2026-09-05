"""ADR §4a rows 1 and 3 (CR-3, CR-4): what the production posture refuses before any
socket opens or any database is touched, and what test mode accepts and names.
"""

from __future__ import annotations

import pytest

from governed_runtime_worker import (
    PostureRefused,
    ShadowWorkload,
    WorkerConfigError,
    compose,
    preflight,
)
from ugence_approval_workflow import ApproverKind, ApproverRef, StaticApproverEligibility
from ugence_durable_execution.postgres.bundle import InMemoryReferenceBundle
from ugence_governed_review_service import StaticApproverIdentityAdapter

from conftest import ROLE, Clock, config_for

APPROVER = ApproverRef(approver_id="approver-1", approver_kind=ApproverKind.HUMAN, role=ROLE,
                       authority_reference="fixture")


class _NonProductionPort:
    NON_PRODUCTION = True

    def authenticate(self, proof):  # pragma: no cover - never reached
        raise AssertionError


class _FixtureEligibility:
    maturity = "FIXTURE_ONLY"


# --------------------------------------------------------------------------- #
# row 1: the static identity adapter or an in-memory store in production mode
# --------------------------------------------------------------------------- #
def test_the_static_identity_adapter_is_refused_in_production_before_anything_opens(tmp_path):
    cfg = config_for(tmp_path, "production")
    with pytest.raises(PostureRefused, match="fixture identity adapter.*CR-4"):
        preflight(cfg, identity_port=StaticApproverIdentityAdapter())
    with pytest.raises(PostureRefused, match="fixture identity adapter"):
        preflight(cfg, identity_port=_NonProductionPort())


def test_a_fixture_eligibility_adapter_is_refused_in_production(tmp_path):
    cfg = config_for(tmp_path, "production")
    with pytest.raises(PostureRefused, match="eligibility.*authority directory"):
        preflight(cfg, eligibility=StaticApproverEligibility((APPROVER,)))
    with pytest.raises(PostureRefused, match="fixture eligibility"):
        preflight(cfg, eligibility=_FixtureEligibility())


def test_an_in_memory_store_is_refused_in_production(tmp_path):
    with pytest.raises(WorkerConfigError, match="in-memory stores are refused"):
        preflight(config_for(tmp_path, "production", data_dir=":memory:"))


def test_a_non_authoritative_bundle_is_refused_in_production(tmp_path):
    cfg = config_for(tmp_path, "production")
    bundle = InMemoryReferenceBundle()
    assert bundle.is_production_authoritative is False
    with pytest.raises(PostureRefused, match="non-authoritative.*CR-4"):
        preflight(cfg, bundle=bundle)


def test_an_identity_port_is_mandatory_in_production(tmp_path):
    cfg = config_for(tmp_path, "production", identity_issuer="", identity_audience="",
                     identity_jwks_url="")
    with pytest.raises(WorkerConfigError, match="identity port is mandatory"):
        preflight(cfg)


def test_a_configured_issuer_or_a_caller_port_satisfies_production_preflight(tmp_path):
    cfg = config_for(tmp_path, "production")
    preflight(cfg)  # the adapter will be built from configuration

    class Port:
        NON_PRODUCTION = False

        def authenticate(self, proof):  # pragma: no cover
            raise AssertionError

    preflight(cfg, identity_port=Port())


# --------------------------------------------------------------------------- #
# row 3 at the root: the refusal precedes every connection
# --------------------------------------------------------------------------- #
def test_compose_refuses_before_any_store_or_database_is_touched(tmp_path, monkeypatch):
    import dbos
    import sqlalchemy

    import governed_runtime_worker.composition as composition

    def boom(*_a, **_k):
        raise AssertionError("a connection was attempted before the posture refused")

    monkeypatch.setattr(sqlalchemy, "create_engine", boom)
    monkeypatch.setattr(composition.sa, "create_engine", boom)
    monkeypatch.setattr(dbos.SQLAlchemyDatasource, "create", boom)
    monkeypatch.setattr(composition, "SqliteAuthorityDirectory", boom)
    monkeypatch.setattr(composition, "AuditLedger", boom)

    cfg = config_for(tmp_path, "production")
    workload = ShadowWorkload(required_role=ROLE)
    with pytest.raises(PostureRefused):
        compose(cfg, clock=Clock(), workload=workload,
                identity_port=StaticApproverIdentityAdapter())
    with pytest.raises(PostureRefused):
        compose(cfg, clock=Clock(), workload=workload, bundle=InMemoryReferenceBundle())
    with pytest.raises(WorkerConfigError):
        compose(config_for(tmp_path, "production", bind_host="0.0.0.0"), clock=Clock(),
                workload=workload)
    with pytest.raises(WorkerConfigError, match="clock"):
        compose(cfg, clock=object(), workload=workload)
    with pytest.raises(WorkerConfigError, match="workload"):
        compose(cfg, clock=Clock(), workload=object())
    assert not list(tmp_path.glob("*.sqlite3"))


# --------------------------------------------------------------------------- #
# test mode accepts the fixtures and names itself
# --------------------------------------------------------------------------- #
def test_test_mode_accepts_fixtures_and_is_named_as_test(tmp_path):
    cfg = config_for(tmp_path, "test")
    assert not cfg.is_production and cfg.redacted()["deployment_mode"] == "test"
    preflight(cfg, identity_port=StaticApproverIdentityAdapter(),
              eligibility=StaticApproverEligibility((APPROVER,)), bundle=InMemoryReferenceBundle())
    preflight(cfg)  # no identity at all is admissible only here
