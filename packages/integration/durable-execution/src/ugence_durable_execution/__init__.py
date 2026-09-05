"""Ugence Durable Execution — the neutral boundary between a durable-execution engine
and the Agent Runtime.

    THE ENGINE OWNS SCHEDULING AND RECOVERY. IT OWNS NOTHING ELSE.

Workflow IR and governance state are always Ugence's. Agent Runtime owns proposal
binding, the governance hook, budgets, checkpoints and receipts. The engine never holds
governance state, never decides whether a step may run, and never re-drives a step past
the hook — every retry re-enters the same Agent Runtime transition and therefore
re-crosses the same governance boundary.

Scoped by ``docs/architecture/ADR_DBOS_DURABLE_EXECUTION_INTEGRATION.md``.

**Maturity.** DBOS is **ratified as the initial engine** (owner ruling OD-3, ADR §9)
because every row of the ADR §8 durability and failure matrix has passing evidence in
CI. Ratified establishes the matrix properties and nothing more: nothing here is
pilot-validated, production-certified or production-ready. :func:`engine_status`
reports the state and the test suite asserts it against the ADR record, so the claim
cannot drift from the evidence.
"""
from __future__ import annotations

from .clock import assert_durable_clock, is_monotonic_clock, wall_clock
from .errors import (
    BudgetExhausted,
    CheckpointIntegrityError,
    ClockDisciplineError,
    DefinitionVersionMismatch,
    DurableExecutionError,
    InstanceIdentityError,
    PostureError,
    UnrecoverableInstanceError,
)
from .interfaces import (
    DurableExecutionAdapter,
    DurableStepOutcome,
    DurableStoreBundle,
)
from .version import DBOS_ENGINE_STATUS, __version__

__all__ = [
    "__version__",
    "DBOS_ENGINE_STATUS",
    "engine_status",
    "DurableExecutionAdapter",
    "DurableStepOutcome",
    "DurableStoreBundle",
    "wall_clock",
    "assert_durable_clock",
    "is_monotonic_clock",
    "DurableExecutionError",
    "ClockDisciplineError",
    "PostureError",
    "CheckpointIntegrityError",
    "UnrecoverableInstanceError",
    "DefinitionVersionMismatch",
    "BudgetExhausted",
    "InstanceIdentityError",
]


def engine_status() -> dict:
    """The engine's ratification state, in the form a caller can assert on.

    ``RATIFIED`` by owner ruling OD-3 on CI evidence that every ADR §8 matrix row
    passes. Nothing in this package flips it as a side effect; it is changed only by a
    commit that also carries the evidence. Ratified is a narrower claim than
    pilot-validated or production-certified, which stay False.
    """
    return {
        "engine": "dbos",
        "status": DBOS_ENGINE_STATUS,
        "ratified": DBOS_ENGINE_STATUS == "RATIFIED",
        "gate": "docs/architecture/ADR_DBOS_DURABLE_EXECUTION_INTEGRATION.md §8",
        "pilot_validated": False,
        "production_certified": False,
    }
