"""The production factory fails closed on every reference-grade dependency (D-1, D-5)."""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone

import pytest

from ugence_execution_reservation import InMemoryExecutionReservationStore, SqliteExecutionReservationStore

from _broker_fixtures import production_app

from ugence_cloud_scaling_credential_broker import (
    CREDENTIAL_PROFILE,
    CredentialBrokerConfigurationError,
    CredentialBrokerPort,
    CredentialBrokerSeam,
    CredentialGrantStore,
    InMemoryCredentialGrantStore,
    ReferenceCredentialBroker,
)

NOW = datetime(2026, 1, 1, 0, 6, tzinfo=timezone.utc)


class _ProdBroker:
    is_production_authoritative = True
    broker_authority_id = "kms.example"
    credential_profile = CREDENTIAL_PROFILE

    def materialize(self, request):  # pragma: no cover
        raise AssertionError("not reached")


class _ProdGrants(InMemoryCredentialGrantStore):
    is_production_authoritative = True


def _ledger():
    return SqliteExecutionReservationStore(os.path.join(tempfile.mkdtemp(), "ledger.sqlite3"), production_mode=True)


def _production(**over):
    kw = dict(app=production_app(), reservations=_ledger(), broker=_ProdBroker(), grants=_ProdGrants(), clock=lambda: NOW)
    kw.update(over)
    return CredentialBrokerSeam.production(**kw)


def test_the_production_seam_constructs_over_production_grade_parts():
    assert _production().is_production is True


def test_production_refuses_a_reference_mode_application(world):
    with pytest.raises(CredentialBrokerConfigurationError, match="production mode"):
        _production(app=world.app)


def test_production_refuses_the_reference_broker_and_a_silent_one():
    with pytest.raises(CredentialBrokerConfigurationError, match="reference broker"):
        _production(broker=ReferenceCredentialBroker())

    class Sub(ReferenceCredentialBroker):
        is_production_authoritative = True

    with pytest.raises(CredentialBrokerConfigurationError, match="reference broker"):
        _production(broker=Sub())

    class Silent(_ProdBroker):
        is_production_authoritative = False

    with pytest.raises(CredentialBrokerConfigurationError, match="production-authoritative"):
        _production(broker=Silent())


def test_production_refuses_the_in_memory_ledger_and_grant_store():
    with pytest.raises(CredentialBrokerConfigurationError, match="in-memory ledger"):
        _production(reservations=InMemoryExecutionReservationStore())
    with pytest.raises(CredentialBrokerConfigurationError, match="in-memory store"):
        _production(grants=InMemoryCredentialGrantStore())


def test_the_reference_seam_refuses_a_production_application():
    with pytest.raises(CredentialBrokerConfigurationError):
        CredentialBrokerSeam.reference(app=production_app(), reservations=InMemoryExecutionReservationStore(), clock=lambda: NOW)


def test_ports_are_runtime_checkable_and_the_reference_broker_declares_itself():
    assert isinstance(ReferenceCredentialBroker(), CredentialBrokerPort)
    assert isinstance(_ProdBroker(), CredentialBrokerPort)
    assert isinstance(InMemoryCredentialGrantStore(), CredentialGrantStore)
    assert ReferenceCredentialBroker().is_production_authoritative is False
    assert InMemoryCredentialGrantStore().is_production_authoritative is False
