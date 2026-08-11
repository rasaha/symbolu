"""Neutral-contract invariants (spec §12–§13, §21 I9).

The RA-7 types are evidence/observation, NOT authority. These tests assert that
structurally — there is no ALLOW/scope/signature/grant field on any RA-7 type, and
the assessment cannot be used as standalone authority.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime

import pytest

from ugence_risk_authority_runtime_assurance import (
    AssessmentOutcome,
    ReasonCode,
    RuntimeRiskLevel,
    TrajectoryAssessment,
    TrajectoryObservation,
    TrajectoryPolicyRef,
)

_FORBIDDEN_FIELD_SUBSTRINGS = (
    "allow",
    "scope",
    "signature",
    "signed",
    "grant",
    "token",
    "authoriz",  # authorization / authorize
    "credential",
    "capability",
    "epoch",
    "revoke",
)

_RA7_DATA_TYPES = (
    TrajectoryObservation,
    TrajectoryAssessment,
    TrajectoryPolicyRef,
)


@pytest.mark.parametrize("cls", _RA7_DATA_TYPES)
def test_no_authority_granting_field_on_any_ra7_type(cls):
    for f in dataclasses.fields(cls):
        low = f.name.lower()
        for bad in _FORBIDDEN_FIELD_SUBSTRINGS:
            assert bad not in low, f"{cls.__name__}.{f.name} looks like an authority field ({bad})"


@pytest.mark.parametrize("cls", _RA7_DATA_TYPES)
def test_no_signing_method_on_any_ra7_type(cls):
    for name in ("sign", "signing_payload", "to_authority", "as_grant", "authorize"):
        assert not hasattr(cls, name), f"{cls.__name__} exposes {name}"


def test_risk_level_is_three_valued_only():
    assert {m.value for m in RuntimeRiskLevel} == {"NORMAL", "ESCALATED", "UNKNOWN"}
    # No ALLOW/DENY vocabulary (spec §12).
    assert "ALLOW" not in {m.value for m in RuntimeRiskLevel}
    assert "DENY" not in {m.value for m in RuntimeRiskLevel}


def test_assessment_material_iff_escalated():
    base = dict(
        assessment_id="a1",
        tenant_id="t",
        workflow_instance_id="w",
        envelope_id="e",
        outcome=AssessmentOutcome.NO_SIGNAL,
        produced_at=datetime(2026, 1, 1),
        evaluator_identity="id",
        evaluator_version="0",
    )
    assert not TrajectoryAssessment(risk_level=RuntimeRiskLevel.NORMAL, **base).is_material
    assert not TrajectoryAssessment(risk_level=RuntimeRiskLevel.UNKNOWN, **base).is_material
    assert TrajectoryAssessment(risk_level=RuntimeRiskLevel.ESCALATED, **base).is_material


def test_observation_binding_errors_reject_missing_bindings():
    obs = TrajectoryObservation(
        schema_version="1",
        event_id="",
        tenant_id="",
        workflow_instance_id="",
        envelope_id="",
        runtime_event_type="",
        observed_at=datetime(2026, 1, 1),
        source="",
        source_version="",
    )
    errors = obs.binding_errors()
    for expected in ("event_id", "tenant_id", "workflow_instance_id", "envelope_id", "source"):
        assert any(expected in e for e in errors), (expected, errors)


def test_observation_unsupported_schema_version_rejected():
    obs = TrajectoryObservation(
        schema_version="999",
        event_id="e",
        tenant_id="t",
        workflow_instance_id="w",
        envelope_id="env",
        runtime_event_type="X",
        observed_at=datetime(2026, 1, 1),
        source="s",
        source_version="1",
    )
    assert any("schema_version" in e for e in obs.binding_errors())


def test_observation_detail_is_frozen_copy():
    src = {"exposure": {"model_cost": 1.0}}
    obs = TrajectoryObservation(
        schema_version="1",
        event_id="e",
        tenant_id="t",
        workflow_instance_id="w",
        envelope_id="env",
        runtime_event_type="X",
        observed_at=datetime(2026, 1, 1),
        source="s",
        source_version="1",
        detail=src,
    )
    src["exposure"] = {"model_cost": 999.0}  # mutate original
    assert obs.detail["exposure"] == {"model_cost": 1.0}


def test_reason_codes_exclude_ra8_effect_mismatch():
    values = {m.value for m in ReasonCode}
    assert "EXECUTION_EFFECT_MISMATCH" not in values
    assert "EFFECT_MISMATCH" not in values


def test_trajectory_key_is_tenant_workflow():
    obs = TrajectoryObservation(
        schema_version="1",
        event_id="e",
        tenant_id="t1",
        workflow_instance_id="w1",
        envelope_id="env",
        runtime_event_type="X",
        observed_at=datetime(2026, 1, 1),
        source="s",
        source_version="1",
    )
    assert obs.trajectory_key == ("t1", "w1")
