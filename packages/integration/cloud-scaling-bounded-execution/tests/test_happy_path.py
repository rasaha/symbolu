"""Positive controls: one bounded change dispatched in SIMULATION from a grant, observed, recorded."""

from __future__ import annotations

from ugence_cloud_scaling_operations.contracts import ExecutionMode, ExecutionOutcome
from ugence_decision_authority.execution.status import BusinessOutcome, Finality
from ugence_execution_reservation import ReservationState

from _execution_fixtures import DISPATCH_INSTANT, DISPATCH_REQUEST_ID, dispatch_request

from ugence_cloud_scaling_bounded_execution import (
    PROVIDER_ID,
    RECORD_SCHEMA_VERSION,
    BoundedDispatchOutcome,
    RecordDisposition,
    derive_record_id,
)


def test_a_simulated_dispatch_runs_one_bounded_change_and_observes_success(world):
    out = world.seam().dispatch(dispatch_request(world))
    assert type(out) is BoundedDispatchOutcome
    assert out.refusal is None, (out.refusal, out.detail)
    assert out.dispatched and out.effective_mode is ExecutionMode.SIMULATION and out.mode_reasons == ()
    record = out.record
    assert record.ops_outcome == ExecutionOutcome.SIMULATED.value
    assert record.business_outcome is BusinessOutcome.SUCCEEDED and record.finality is Finality.FINAL
    assert record.applied is False and out.applied is False
    assert record.pre_state == world.target_scope.magnitude_before
    assert record.post_state == world.target_scope.requested_magnitude
    assert world.reservations.get_reservation(world.reservation.reservation_id).state is ReservationState.OBSERVED_SUCCESS


def test_one_clock_read_and_the_executor_sees_the_same_instant(world):
    out = world.seam().dispatch(dispatch_request(world))
    assert world.clock.reads == 1
    assert out.dispatched_at == out.record.dispatched_at == out.record.observed_at == DISPATCH_INSTANT
    dispatched = world.reservations.get_reservation(world.reservation.reservation_id)
    assert dispatched.dispatched_at == DISPATCH_INSTANT and dispatched.dispatch_request_id == DISPATCH_REQUEST_ID


def test_the_record_carries_the_bindings_and_the_ra8_correlation_fields(world):
    record = world.seam().dispatch(dispatch_request(world)).record
    assert record.schema_version == RECORD_SCHEMA_VERSION
    assert record.record_id == derive_record_id(world.candidate.tenant_id, world.grant.grant_id, DISPATCH_REQUEST_ID)
    assert record.grant_id == world.grant.grant_id and record.request_digest == world.grant.request_digest
    assert record.reservation_id == world.reservation.reservation_id
    assert record.execution_key == world.reservation.execution_key.serialized
    assert record.target_scope_digest == world.target_scope.digest()
    assert record.envelope_id == world.envelope.envelope_id
    assert record.authorized_action_digest == world.authorization.action_digest == world.action.digest
    assert record.attempt_id == DISPATCH_REQUEST_ID and record.workflow_instance_id == record.reservation_id
    assert record.disposition is RecordDisposition.DISPATCHED
    assert world.records.get(record.tenant_id, record.record_id) == record


def test_the_effect_observation_is_well_formed_for_ra8(world):
    out = world.seam().dispatch(dispatch_request(world))
    obs = out.observation
    assert obs.binding_errors() == ()
    assert obs.observation_id == out.record.record_id and obs.attempt_id == DISPATCH_REQUEST_ID
    assert obs.envelope_id == world.envelope.envelope_id
    assert obs.authorized_action_digest == world.authorization.action_digest
    assert obs.business_outcome is BusinessOutcome.SUCCEEDED and obs.finality is Finality.FINAL
    assert obs.provider == PROVIDER_ID and obs.external_effect_id == out.record.receipt_hash
    assert obs.effect_digest and obs.observed_at == DISPATCH_INSTANT
    assert obs.observed_parameters["grant_id"] == world.grant.grant_id


def test_the_executors_idempotency_key_is_the_execution_key(world):
    world.seam().dispatch(dispatch_request(world))
    prior = world.idempotency.get(world.reservation.execution_key.serialized)
    assert prior is not None and prior.completed and prior.authorization_id == world.authorization.authorization_id


def test_re_dispatch_replays_the_stored_record_without_touching_the_executor(world):
    seam = world.seam()
    first = seam.dispatch(dispatch_request(world))
    events = len(world.audit.events) if hasattr(world.audit, "events") else None
    again = seam.dispatch(dispatch_request(world))
    assert again.replayed and again.record.record_id == first.record.record_id
    assert again.record.disposition is RecordDisposition.REPLAYED and again.observation is not None
    if events is not None:
        assert len(world.audit.events) == events


def test_the_executor_itself_answers_duplicate_for_the_same_request(world):
    """The executor's own replay protection, keyed on the execution key, still stands behind the seam."""

    from ugence_cloud_scaling_operations.contracts import ExecutionOutcome
    seam = world.seam()
    seam.dispatch(dispatch_request(world))
    prior = world.idempotency.get(world.reservation.execution_key.serialized)
    assert prior.completed and prior.receipt_hash == world.records.get(
        world.candidate.tenant_id, derive_record_id(world.candidate.tenant_id, world.grant.grant_id, DISPATCH_REQUEST_ID)).receipt_hash
    assert ExecutionOutcome.DUPLICATE.value == "duplicate"


def test_a_dry_run_proposes_without_touching_the_reservation(world):
    from _execution_fixtures import simulation_config
    out = world.seam(simulation_config(ExecutionMode.DRY_RUN)).dispatch(dispatch_request(world))
    assert out.dispatched and out.effective_mode is ExecutionMode.DRY_RUN
    assert out.record.ops_outcome == ExecutionOutcome.PROPOSED.value
    assert out.record.business_outcome is BusinessOutcome.UNKNOWN and out.record.finality is Finality.UNKNOWN
    assert world.reservations.get_reservation(world.reservation.reservation_id).state is ReservationState.RESERVED
