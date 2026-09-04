"""Refusals and denials: only the one admitted, reserved, granted action is ever dispatched."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from ugence_cloud_scaling_operations.contracts import ExecutionMode, ExecutionOutcome
from ugence_cloud_scaling_operations.rollback_coordinator import RollbackAuthorization, RollbackPolicy
from ugence_decision_authority.execution.status import BusinessOutcome
from ugence_execution_reservation import ReservationState

from _broker_fixtures import RESERVATION_INSTANT
from _execution_fixtures import DISPATCH_INSTANT, dispatch_request, simulation_config

from ugence_cloud_scaling_bounded_execution import (
    BarePolicyRollbackRefused,
    BoundedExecutionContractError,
    BoundedExecutionExactTypeError,
    BoundedExecutionSeam,
    DispatchRefusal as R,
    ops_action_for,
    ops_target_for,
)


def _refused(world, request=None, expected=None, **seam_kw):
    out = world.seam(**seam_kw).dispatch(request or dispatch_request(world))
    assert out.record is None and out.dispatched is False
    if expected is not None:
        assert out.refusal is expected, (out.refusal, out.detail)
    assert world.reservations.get_reservation(world.reservation.reservation_id).state is ReservationState.RESERVED
    return out


# --------------------------------------------------------------------------- #
# The four named refusals
# --------------------------------------------------------------------------- #
def test_a_lapsed_lease_is_refused_before_any_client_is_touched(world):
    world.clock.at = world.reservation.lease.expires_at + timedelta(seconds=1)
    out = _refused(world, expected=R.LEASE_EXPIRED)
    assert world.clock.reads == 1 and not world.idempotency.get(world.reservation.execution_key.serialized)


def test_an_expired_grant_is_refused(world):
    """A grant minted under a short ttl cap expires while the reservation lease still runs."""

    from _broker_fixtures import materialization_request
    grants = world.grants.__class__()
    short = world.broker_world.seam(grants=grants, ttl_cap=timedelta(seconds=30)).materialize(
        materialization_request(world.broker_world))
    assert short.materialized
    world.clock.at = short.grant.validity.expires_at + timedelta(seconds=1)
    assert not world.reservation.lease.is_expired_at(world.clock.at)
    out = world.seam(grants=grants).dispatch(dispatch_request(world, grant_id=short.grant.grant_id))
    assert out.refusal is R.GRANT_EXPIRED and out.record is None


def test_a_dispatched_reservation_is_refused(world):
    world.reservations.mark_dispatched(world.reservation.reservation_id, "elsewhere",
                                       dispatch_deadline=DISPATCH_INSTANT + timedelta(minutes=5),
                                       as_of=RESERVATION_INSTANT + timedelta(seconds=1))
    out = world.seam().dispatch(dispatch_request(world))
    assert out.refusal is R.RESERVATION_NOT_RESERVED and out.record is None


def test_a_mismatched_target_scope_is_refused(world):
    other = replace(world.target_scope, compute_group=(world.target_scope.compute_group or "") + "-other")
    out = _refused(world, dispatch_request(world, target_scope=other), R.TARGET_SCOPE_MISMATCH)
    assert "TARGET_SCOPE_MISMATCH" in out.detail


def test_a_wider_target_scope_is_refused(world):
    s = world.target_scope
    wider = replace(s, requested_magnitude=s.requested_magnitude + 5, max_permitted_magnitude=s.max_permitted_magnitude + 5,
                    max_permitted_delta=s.max_permitted_delta + 5)
    _refused(world, dispatch_request(world, target_scope=wider), R.TARGET_SCOPE_MISMATCH)


# --------------------------------------------------------------------------- #
# Every other artifact must be the bound one
# --------------------------------------------------------------------------- #
def test_an_unknown_grant_authorization_or_reservation_is_refused(world):
    _refused(world, dispatch_request(world, grant_id="cred.v1:" + "0" * 64), R.GRANT_NOT_FOUND)
    _refused(world, dispatch_request(world, authorization_id="auth.v1:" + "0" * 64), R.AUTHORIZATION_NOT_FOUND)
    _refused(world, dispatch_request(world, reservation_id="res_unknown"), R.RESERVATION_NOT_FOUND)


def test_a_grant_for_another_authorization_does_not_rederive(world):
    from risk_authority.domain.enums import ActionGateDecision
    other = replace(world.authorization, authorization_id="auth.v1:" + "e" * 64)
    world.app.authorizations.save(other)
    _refused(world, dispatch_request(world, authorization_id=other.authorization_id), R.GRANT_NOT_REDERIVED)
    denied = replace(world.authorization, authorization_id="auth.v1:" + "d" * 64, decision=ActionGateDecision.DENIED)
    world.app.authorizations.save(denied)
    _refused(world, dispatch_request(world, authorization_id=denied.authorization_id), R.AUTHORIZATION_NOT_AUTHORIZED)


def test_a_released_reservation_is_refused(world):
    world.reservations.release(world.reservation.reservation_id, as_of=RESERVATION_INSTANT + timedelta(seconds=1))
    out = world.seam().dispatch(dispatch_request(world))
    assert out.refusal is R.RESERVATION_NOT_RESERVED


# --------------------------------------------------------------------------- #
# The executor's own gates still stand, and a denial is a record, not a mutation
# --------------------------------------------------------------------------- #
def test_a_config_allowlist_that_excludes_the_target_denies_and_records(world):
    config = simulation_config(allowed_clusters=("another-cluster",))
    out = world.seam(config).dispatch(dispatch_request(world))
    assert out.dispatched and out.record.ops_outcome == ExecutionOutcome.DENIED.value
    assert out.record.business_outcome is BusinessOutcome.REJECTED and out.record.applied is False
    assert "cluster" in (out.record.denial_reason or "")
    assert world.reservations.get_reservation(world.reservation.reservation_id).state is ReservationState.OBSERVED_FAILURE


def test_a_backend_failure_is_recorded_as_failed_and_observed(world):
    from ugence_cloud_scaling_operations.executors import FakeScalingBackend
    target = ops_target_for(world.target_scope)
    failing = FakeScalingBackend({f"{target.cluster}/{target.namespace}/{target.resource}": world.target_scope.magnitude_before},
                                 fail_on=target.resource)
    out = world.seam(parts=world.parts(backend=failing)).dispatch(dispatch_request(world))
    assert out.record.ops_outcome == ExecutionOutcome.FAILED.value and out.record.business_outcome is BusinessOutcome.FAILED
    assert world.reservations.get_reservation(world.reservation.reservation_id).state is ReservationState.OBSERVED_FAILURE


def test_exactly_one_set_replicas_per_dispatch(world):
    calls = []
    backend = world.parts().backend
    original = backend.set_replicas

    def counting(*a, **k):
        calls.append(a)
        return original(*a, **k)

    backend.set_replicas = counting
    world.seam(parts=world.parts(backend=backend)).dispatch(dispatch_request(world))
    assert len(calls) == 1


# --------------------------------------------------------------------------- #
# Projections
# --------------------------------------------------------------------------- #
def test_non_dispatchable_action_types_are_refused(world):
    for action_type in ("no_change", "coordinated", "delete_everything"):
        with pytest.raises(BoundedExecutionContractError):
            ops_action_for(action_type)
    assert ops_action_for("scale_up") == "scale" and ops_action_for("scale_down") == "scale"


def test_an_unaddressable_target_scope_is_refused():
    from _admission_fixtures import build_admission_world
    scope = replace(build_admission_world().target_scope, resource_class=None)
    with pytest.raises(BoundedExecutionContractError):
        ops_target_for(scope)


def test_a_scope_without_a_namespace_is_addressed_by_account_partition(world):
    target = ops_target_for(world.target_scope)
    assert target.namespace == (world.target_scope.namespace or world.target_scope.account_id)
    assert target.cluster == world.target_scope.compute_group and target.resource == world.target_scope.resource_class


# --------------------------------------------------------------------------- #
# Rollback is a second bounded action (D-4)
# --------------------------------------------------------------------------- #
def test_a_bare_policy_rollback_is_refused(world):
    with pytest.raises(BarePolicyRollbackRefused, match="bare RollbackPolicy"):
        BoundedExecutionSeam.rollback(RollbackAuthorization(policy=RollbackPolicy(min_replicas=1, max_replicas=10, max_delta=2)))


def test_a_rollback_with_a_foreign_authorization_is_refused_too(world):
    from ugence_cloud_scaling_operations.contracts import ExecutionAuthorization
    foreign = ExecutionAuthorization(
        authorization_id="x", decision_id="d", recommendation_id="r", tenant_id=world.candidate.tenant_id,
        actor_id="a", authority_source="someone", issued_at=0.0, expires_at=1e12, permitted_action="scale",
        target_cluster="c", target_namespace="n", target_resource="r", current_replicas=1, minimum_replicas=0,
        maximum_replicas=5, maximum_delta=5, reason="", policy_version="", idempotency_key="k", nonce="n")
    with pytest.raises(BarePolicyRollbackRefused):
        BoundedExecutionSeam.rollback(RollbackAuthorization(authorization=foreign))
    with pytest.raises(BoundedExecutionExactTypeError):
        BoundedExecutionSeam.rollback(object())  # type: ignore[arg-type]


def test_the_rollback_target_is_the_prior_records_pre_state(world):
    record = world.seam().dispatch(dispatch_request(world)).record
    assert BoundedExecutionSeam.rollback_target_for(record) == world.target_scope.magnitude_before


# --------------------------------------------------------------------------- #
# Request hygiene
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("field, value", [
    ("tenant_id", ""), ("grant_id", " g"), ("reservation_id", None), ("dispatch_request_id", ""), ("target_scope", object()),
])
def test_malformed_requests_are_refused(world, field, value):
    with pytest.raises(BoundedExecutionExactTypeError):
        dispatch_request(world, **{field: value})


def test_a_target_scope_for_another_tenant_cannot_ride_this_request(world):
    with pytest.raises(BoundedExecutionExactTypeError):
        dispatch_request(world, target_scope=replace(world.target_scope, tenant_id="tenant-other"))


def test_a_foreign_request_type_is_refused(world):
    with pytest.raises(BoundedExecutionExactTypeError):
        world.seam().dispatch(object())  # type: ignore[arg-type]
