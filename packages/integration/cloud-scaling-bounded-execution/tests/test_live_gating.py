"""LIVE only under a proven posture; any absence resolves to DRY_RUN, never SIMULATION (D-3).
Blast radius from the grant's role, never wider than config (D-4)."""

from __future__ import annotations

import os
import tempfile
from dataclasses import fields, replace
from datetime import datetime, timezone

import pytest

from ugence_cloud_scaling_operations.config import OperationsConfig, TargetPolicy
from ugence_cloud_scaling_operations.contracts import ExecutionMode
from ugence_cloud_scaling_operations.executors import FakeScalingBackend
from ugence_execution_reservation import InMemoryExecutionReservationStore, SqliteExecutionReservationStore

from _execution_fixtures import dispatch_request, production_app, simulation_config

from ugence_cloud_scaling_bounded_execution import (
    BoundedExecutionConfigurationError,
    BoundedExecutionSeam,
    ExecutorParts,
    InMemoryBoundedExecutionRecordStore,
    LivePosture,
    OpsTarget,
    narrow_target_policy,
    ops_target_for,
    resolve_effective_mode,
)
from ugence_cloud_scaling_credential_broker import CREDENTIAL_PROFILE, InMemoryCredentialGrantStore, ReferenceCredentialBroker

NOW = datetime(2026, 1, 1, 0, 6, tzinfo=timezone.utc)
ALL_HELD = LivePosture(True, True, True, True, True, True, True)


def test_live_resolves_only_when_every_precondition_holds():
    assert resolve_effective_mode(ExecutionMode.LIVE, ALL_HELD) == (ExecutionMode.LIVE, ())


@pytest.mark.parametrize("missing", [f.name for f in fields(LivePosture)])
def test_each_missing_precondition_resolves_live_to_dry_run_never_simulation(missing):
    posture = replace(ALL_HELD, **{missing: False})
    mode, reasons = resolve_effective_mode(ExecutionMode.LIVE, posture)
    assert mode is ExecutionMode.DRY_RUN and mode is not ExecutionMode.SIMULATION
    assert len(reasons) == 1 and "LIVE precondition absent" in reasons[0]


def test_non_live_requests_keep_their_mode():
    for mode in (ExecutionMode.DRY_RUN, ExecutionMode.SIMULATION, ExecutionMode.SHADOW):
        assert resolve_effective_mode(mode, replace(ALL_HELD, backend_injected=False)) == (mode, ())


def test_the_reference_seam_reports_its_posture_and_resolves_live_to_dry_run(world):
    seam = world.seam(simulation_config(ExecutionMode.LIVE))
    posture = seam.posture_for(world.grant)
    assert posture.production_application is False and posture.production_ledger is False
    assert posture.non_reference_grant_handle is False  # the reference broker's inert handle
    assert posture.backend_injected is True and posture.readiness_required is True
    out = seam.dispatch(dispatch_request(world))
    assert out.effective_mode is ExecutionMode.DRY_RUN and out.dispatched and out.applied is False
    assert len(out.mode_reasons) == len(posture.missing()) >= 4
    assert out.record.mode_reasons == out.mode_reasons


def test_a_live_config_without_a_backend_resolves_to_dry_run_with_the_reason(world):
    seam = world.seam(simulation_config(ExecutionMode.LIVE), parts=world.parts(simulation_config(ExecutionMode.LIVE), backend=None))
    out = seam.dispatch(dispatch_request(world))
    assert out.effective_mode is ExecutionMode.DRY_RUN
    assert any("injected backend" in r for r in out.mode_reasons)


# --------------------------------------------------------------------------- #
# Blast radius (D-4)
# --------------------------------------------------------------------------- #
def test_a_wider_config_is_narrowed_to_the_role(world):
    config = simulation_config()
    target = ops_target_for(world.target_scope)
    role = world.grant.role
    policy = narrow_target_policy(config, target, max_magnitude=role.max_magnitude, max_delta=role.max_delta)
    assert policy.max_replicas == role.max_magnitude < config.target_policy.max_replicas
    assert policy.max_replica_delta == role.max_delta < config.target_policy.max_replica_delta
    assert policy.allowed_clusters == (target.cluster,) and policy.allowed_resources == (target.resource,)
    assert policy.allowed_namespaces == (target.namespace,) and policy.allow_wildcard is False


def test_a_tighter_config_is_never_widened_by_the_role():
    config = OperationsConfig(mode=ExecutionMode.SIMULATION, target_policy=TargetPolicy(
        allowed_clusters=("c",), allowed_namespaces=("n",), allowed_resources=("r",), max_replica_delta=1, max_replicas=3))
    policy = narrow_target_policy(config, OpsTarget("c", "n", "r"), max_magnitude=100, max_delta=50)
    assert policy.max_replicas == 3 and policy.max_replica_delta == 1
    excluded = narrow_target_policy(config, OpsTarget("other", "n", "r"), max_magnitude=100, max_delta=50)
    assert excluded.allowed_clusters == ()  # config did not admit it; nothing is admitted


# --------------------------------------------------------------------------- #
# Production factory
# --------------------------------------------------------------------------- #
class _ProdBroker:
    is_production_authoritative = True
    broker_authority_id = "kms.example"
    credential_profile = CREDENTIAL_PROFILE

    def materialize(self, request):  # pragma: no cover
        raise AssertionError("not reached")


class _ProdGrants(InMemoryCredentialGrantStore):
    is_production_authoritative = True


class _ProdRecords(InMemoryBoundedExecutionRecordStore):
    is_production_authoritative = True


def _ledger():
    return SqliteExecutionReservationStore(os.path.join(tempfile.mkdtemp(), "ledger.sqlite3"), production_mode=True)


def _production(**over):
    kw = dict(app=production_app(), reservations=_ledger(), grants=_ProdGrants(), broker=_ProdBroker(),
              records=_ProdRecords(), parts=ExecutorParts(config=simulation_config(ExecutionMode.LIVE),
                                                          backend=FakeScalingBackend()), clock=lambda: NOW)
    kw.update(over)
    return BoundedExecutionSeam.production(**kw)


def test_the_production_seam_constructs_over_production_grade_parts():
    assert _production().is_production is True


def test_production_refuses_every_reference_grade_part(world):
    with pytest.raises(BoundedExecutionConfigurationError, match="production mode"):
        _production(app=world.app)
    with pytest.raises(BoundedExecutionConfigurationError, match="reference"):
        _production(broker=ReferenceCredentialBroker())
    with pytest.raises(BoundedExecutionConfigurationError, match="in-memory execution ledger"):
        _production(reservations=InMemoryExecutionReservationStore())
    with pytest.raises(BoundedExecutionConfigurationError, match="grant store"):
        _production(grants=InMemoryCredentialGrantStore())
    with pytest.raises(BoundedExecutionConfigurationError, match="record store"):
        _production(records=InMemoryBoundedExecutionRecordStore())


def test_the_reference_seam_refuses_a_production_application(world):
    with pytest.raises(BoundedExecutionConfigurationError):
        BoundedExecutionSeam.reference(app=production_app(), reservations=world.reservations, grants=world.grants,
                                       parts=world.parts(), clock=lambda: NOW)
