"""The refusal vocabulary is closed and the outcome never executes."""

from __future__ import annotations

from datetime import datetime, timezone

from ugence_cloud_scaling_credential_broker import (
    CredentialMaterializationOutcome,
    CredentialRefusal,
    GrantDisposition,
    NO_CREDENTIAL_ACTION_TYPES,
)


def test_the_refusal_vocabulary_names_every_gate():
    values = {r.value for r in CredentialRefusal}
    for needed in ("AUTHORIZATION_NOT_FOUND", "AUTHORIZATION_NOT_AUTHORIZED", "AUTHORIZATION_EXPIRED",
                   "ENVELOPE_EXPIRED", "RESERVATION_NOT_RESERVED", "RESERVATION_MISMATCH", "LEASE_EXPIRED",
                   "TARGET_SCOPE_MISMATCH", "NO_CREDENTIAL_REQUIRED", "BROKER_UNAVAILABLE", "GRANT_INVALID"):
        assert needed in values


def test_an_outcome_without_a_grant_is_never_materialized_or_executable():
    out = CredentialMaterializationOutcome(materialized_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    assert not out.materialized and not out.replayed and out.executable is False
    assert "executable" not in {f.name for f in __import__("dataclasses").fields(out)}


def test_no_change_is_the_only_credential_free_action_type():
    assert NO_CREDENTIAL_ACTION_TYPES == frozenset({"no_change"})
    assert {d.value for d in GrantDisposition} == {"MATERIALIZED", "REPLAYED"}
