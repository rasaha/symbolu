"""Neutral Agent Runtime event → observation adapter tests (spec §17, §22; matrix 30, 33).

The adapter accepts a duck-typed runtime event and never imports the Agent
Runtime. It binds observations to the caller-supplied authority domain — it never
invents tenant/envelope from event contents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict

from ugence_risk_authority_runtime_assurance import (
    RuntimeBindingContext,
    RuntimeEventAdapter,
    TrajectoryObservation,
    TrajectoryPolicyRef,
)

NOW = datetime(2026, 8, 11, 12, 0, 0)


@dataclass(frozen=True)
class FakeRuntimeEvent:
    """Structural stand-in for ugence_agent_runtime.models.events.RuntimeEvent."""

    seq: int
    type: str
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"seq": self.seq, "type": self.type, "detail": dict(self.detail)}


def _ctx():
    return RuntimeBindingContext(
        tenant_id="t1",
        workflow_instance_id="wf1",
        envelope_id="env1",
        source="agent-runtime",
        source_version="0.6.0",
        policy_ref=TrajectoryPolicyRef("p1", "1"),
    )


def test_adapter_does_not_import_agent_runtime():
    import sys
    import ugence_risk_authority_runtime_assurance.event_adapter as ea  # noqa: F401

    assert "ugence_agent_runtime" not in sys.modules, (
        "RA-7 must not import the Agent Runtime (invariant N8/I11)"
    )


def test_adapter_binds_event_to_authority_domain():
    adapter = RuntimeEventAdapter(_ctx())
    obs = adapter.to_observation(
        FakeRuntimeEvent(seq=5, type="PROVIDER_COMPLETED", detail={"task_id": "task-9"}),
        observed_at=NOW,
    )
    assert isinstance(obs, TrajectoryObservation)
    assert obs.tenant_id == "t1"
    assert obs.workflow_instance_id == "wf1"
    assert obs.envelope_id == "env1"
    assert obs.runtime_event_type == "PROVIDER_COMPLETED"
    assert obs.sequence_number == 5
    assert obs.event_id == "wf1:5"  # deterministic ⇒ replay dedupes
    assert obs.action_id == "task-9"  # picked up from event detail
    assert obs.policy_ref == TrajectoryPolicyRef("p1", "1")


def test_adapter_merges_extra_detail():
    adapter = RuntimeEventAdapter(_ctx())
    obs = adapter.to_observation(
        FakeRuntimeEvent(seq=1, type="PROVIDER_COMPLETED"),
        observed_at=NOW,
        extra_detail={"exposure": {"model_cost": 42.0}},
    )
    assert obs.detail["exposure"] == {"model_cost": 42.0}


def test_adapter_returns_none_for_unmappable_event():
    adapter = RuntimeEventAdapter(_ctx())
    assert adapter.to_observation(object(), observed_at=NOW) is None  # no seq/type


def test_adapter_uses_only_neutral_shape_via_attributes():
    # An object exposing seq/type/detail attributes (no to_dict) still adapts.
    class Bare:
        seq = 7
        type = "TASK_COMPLETED"
        detail = {"action_id": "a-7"}

    obs = RuntimeEventAdapter(_ctx()).to_observation(Bare(), observed_at=NOW)
    assert obs is not None and obs.action_id == "a-7" and obs.sequence_number == 7


def test_adapter_explicit_action_id_overrides_detail():
    obs = RuntimeEventAdapter(_ctx()).to_observation(
        FakeRuntimeEvent(seq=1, type="X", detail={"task_id": "from-detail"}),
        observed_at=NOW,
        action_id="explicit",
    )
    assert obs.action_id == "explicit"
