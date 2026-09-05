"""The production factory fails closed; the gate declares itself; the seam refuses the reference gate."""

from __future__ import annotations

import pytest

from risk_authority.api import ActionAdmissionSeam, SeamConfigurationError
from risk_authority.domain.errors import ProductionContainmentError
from risk_authority.integrations.actiongate import ActionGatePort, ReferenceActionGate

from _admission_fixtures import NOW, production_app

from ugence_cloud_scaling_action_admission import (
    ActionAdmissionConfigurationError,
    CapacityActionGate,
    CloudScalingActionAdmission,
)


def test_the_gate_is_a_production_authoritative_action_gate_port(world):
    gate = CapacityActionGate(target_scope=world.target_scope, candidate_digest=world.candidate.candidate_digest)
    assert gate.is_production_authoritative is True
    assert isinstance(gate, ActionGatePort)
    assert not isinstance(gate, ReferenceActionGate)


def test_the_production_composition_constructs_over_a_production_application():
    root = CloudScalingActionAdmission.production(app=production_app(), clock=lambda: NOW)
    assert root.is_production is True


def test_production_refuses_a_reference_mode_application(world):
    with pytest.raises(ActionAdmissionConfigurationError, match="production mode"):
        CloudScalingActionAdmission.production(app=world.app, clock=lambda: NOW)


def test_the_reference_composition_refuses_a_production_application():
    with pytest.raises(ActionAdmissionConfigurationError):
        CloudScalingActionAdmission.reference(app=production_app(), clock=lambda: NOW)


def test_the_seam_accepts_this_gate_in_production_and_refuses_the_reference_gate(world):
    prod = production_app()
    gate = CapacityActionGate(target_scope=world.target_scope, candidate_digest=world.candidate.candidate_digest)
    assert ActionAdmissionSeam.production(app=prod, gate=gate, clock=lambda: NOW).is_production
    with pytest.raises(SeamConfigurationError):
        ActionAdmissionSeam.production(app=prod, gate=ReferenceActionGate(), clock=lambda: NOW)


def test_the_legacy_authorize_action_stays_contained():
    from risk_authority.api import AuthorizeActionRequest
    with pytest.raises(ProductionContainmentError):
        production_app().authorize_action(AuthorizeActionRequest(
            envelope_id="e", tenant_id="t", actor_id="a", model_id="m", session_id="s",
            action_type="x", target_id="y", purpose="p"))


def test_a_non_callable_clock_is_refused(world):
    with pytest.raises(ActionAdmissionConfigurationError):
        CloudScalingActionAdmission.reference(app=world.app, clock="now")  # type: ignore[arg-type]
