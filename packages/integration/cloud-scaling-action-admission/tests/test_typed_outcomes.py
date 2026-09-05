"""The gate speaks two words; the outcome never executes."""

from __future__ import annotations

import ast
import inspect

from risk_authority.domain.enums import ActionGateDecision

from ugence_cloud_scaling_action_admission import (
    REQUIRED_ENVELOPE_BINDINGS,
    CapacityAdmissionOutcome,
    gate as gate_module,
)


def test_the_gate_source_names_only_authorized_and_denied():
    names = {n.attr for n in ast.walk(ast.parse(inspect.getsource(gate_module)))
             if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)
             and n.value.id == "ActionGateDecision"}
    assert names == {"AUTHORIZED", "DENIED"}
    assert "RETRY_STATE_CHANGED" in {m.name for m in ActionGateDecision}  # exists, never spoken here


def test_the_outcome_is_never_executable_and_admitted_requires_a_verdict():
    from datetime import datetime, timezone
    out = CapacityAdmissionOutcome(admitted_at=datetime(2026, 1, 1, tzinfo=timezone.utc), action=None,
                                   authorization=None, refusal=None, detail="")
    assert out.executable is False and out.admitted is False and out.replayed is False
    assert "executable" not in {f.name for f in __import__("dataclasses").fields(out)}


def test_the_two_required_bindings_are_the_ratified_kinds():
    assert REQUIRED_ENVELOPE_BINDINGS == ("cloud-scaling.authorization-candidate",
                                          "cloud-scaling.execution-target-scope")
