"""Future command interface for the unseen-identifier diagnostic — FAIL-CLOSED, UNEXECUTED.

This module wires the pipeline but performs no reserved-seed cohort generation or training in the
implementation/authorization phase. Reserved seeds require an execution-authorization token (none
exists → they fail closed), and the final phase additionally requires a passing shortcut precheck.
Non-reserved (fixture) seeds may build cohorts for unit tests only.

No `main()` is invoked during implementation or CI. Running the model / reserved cohorts is a
separate, later execution authorization.
"""
from __future__ import annotations

from dataclasses import dataclass

from .config import SPLIT_IDS
from .execution import ExecutionNotAuthorized, require_execution_authorization
from .serializer import serialize
from .shortcuts import shortcut_precheck
from .tasks import generate_split


class ShortcutGateError(RuntimeError):
    """Raised when the final phase is attempted while the shortcut precheck is unresolved/failing."""


def build_cohort(seed: int, cohort: str, token: str | None = None):
    """Build all C1-C8 examples for a (seed, cohort). Reserved seeds fail closed."""
    require_execution_authorization(seed, token)  # raises for reserved seeds without a valid token
    return {split: generate_split(split, cohort, seed) for split in SPLIT_IDS}


def serialize_cohort(cohort_examples) -> dict:
    return {split: [serialize(e) for e in exs] for split, exs in cohort_examples.items()}


@dataclass(frozen=True)
class FinalPhaseGuard:
    shortcut_passed: bool
    authorized: bool


def enter_final_phase(seed: int, token: str | None, shortcut_examples) -> FinalPhaseGuard:
    """Fail-closed entry to the reserved-final phase: needs authorization AND a passing shortcut precheck."""
    status = shortcut_precheck(shortcut_examples)
    if not status.passed:
        raise ShortcutGateError(
            "shortcut precheck failed or unresolved; reserved-final execution is blocked"
        )
    require_execution_authorization(seed, token)  # raises for reserved seeds without a valid token
    return FinalPhaseGuard(shortcut_passed=True, authorized=True)


def main(argv=None):  # pragma: no cover - never invoked during implementation/CI
    raise ExecutionNotAuthorized(
        "the unseen-identifier runner is not authorized to execute; implementation phase only"
    )
