"""The Protocol surface must still match ADR §4.

A second engine (Temporal, ADR §7) has to satisfy these Protocols with no added method,
no added parameter and no widened return type — "a Protocol that had to grow for
Temporal was the wrong Protocol for DBOS". A widened Protocol would quietly make that
exit criterion unmeetable, so the surface is pinned here.
"""
from __future__ import annotations

import inspect

from ugence_durable_execution.interfaces import (
    DurableExecutionAdapter,
    DurableStepOutcome,
    DurableStoreBundle,
)

EXPECTED_ADAPTER_METHODS = {"start", "advance", "signal", "status", "recover"}
EXPECTED_ADAPTER_PROPERTIES = {"engine_id"}
EXPECTED_OUTCOME_PROPERTIES = {
    "instance_id", "progressed", "terminal", "awaiting_external", "checkpoint_digest",
}
EXPECTED_BUNDLE_PROPERTIES = {
    "checkpoint_store", "event_store", "state_store", "is_production_authoritative",
}


def _members(proto) -> set:
    return {
        n for n in vars(proto)
        if not n.startswith("_") and n not in {"mro"}
    }


def test_adapter_surface_matches_the_adr():
    assert _members(DurableExecutionAdapter) == (
        EXPECTED_ADAPTER_METHODS | EXPECTED_ADAPTER_PROPERTIES
    )


def test_step_outcome_surface_matches_the_adr():
    assert _members(DurableStepOutcome) == EXPECTED_OUTCOME_PROPERTIES


def test_store_bundle_surface_matches_the_adr():
    assert _members(DurableStoreBundle) == EXPECTED_BUNDLE_PROPERTIES


def test_adapter_signatures_match_the_adr():
    """Every adapter method is keyword-only, as the ADR writes it."""
    expected = {
        "start": ["workflow_id", "definition_digest", "instance_id", "correlation_id", "inputs"],
        "advance": ["instance_id", "attempt_token"],
        "signal": ["instance_id", "signal_name", "payload"],
        "status": ["instance_id"],
        "recover": ["worker_id"],
    }
    for name, params in expected.items():
        sig = inspect.signature(getattr(DurableExecutionAdapter, name))
        actual = [p for p in sig.parameters if p != "self"]
        assert actual == params, f"{name}: expected {params}, got {actual}"
        for p in params:
            assert sig.parameters[p].kind is inspect.Parameter.KEYWORD_ONLY, (
                f"{name}.{p} must be keyword-only"
            )


def test_concrete_dbos_adapter_satisfies_the_protocol():
    from ugence_durable_execution.engine.dbos_engine import DbosExecutionAdapter, StepOutcome

    for name in EXPECTED_ADAPTER_METHODS | EXPECTED_ADAPTER_PROPERTIES:
        assert hasattr(DbosExecutionAdapter, name), f"adapter is missing {name}"

    outcome = StepOutcome(
        instance_id="i", progressed=True, terminal=False, awaiting_external=False
    )
    assert isinstance(outcome, DurableStepOutcome)


def test_step_outcome_hides_the_governance_reason():
    """The engine must not be able to schedule differently for HOLD versus ESCALATE."""
    from ugence_durable_execution.engine.dbos_engine import StepOutcome

    fields = set(StepOutcome.__dataclass_fields__)
    for leak in ("disposition", "reason_codes", "governance", "hold", "escalate"):
        assert leak not in fields, (
            f"StepOutcome exposes {leak!r}; the engine must not learn the governance reason"
        )
