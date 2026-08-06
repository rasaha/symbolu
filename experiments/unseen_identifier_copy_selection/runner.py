"""Command interface for the unseen-identifier diagnostic — phase-scoped, fail-closed.

This module wires the pipeline. Reserved seeds are generated only when their phase is declared for the
invocation (the phase is threaded as `token` to the primitive guards); the final phase additionally
requires a passing shortcut precheck. Non-reserved (fixture) seeds build cohorts for unit tests.

No `main()` is invoked during CI. Running the model / reserved cohorts is a separate, operator-directed
phase-named invocation.
"""
from __future__ import annotations

from dataclasses import dataclass

from .config import SPLIT_IDS
from .execution import ExecutionNotAuthorized, require_execution_authorization
from .serializer import serialize
from .shortcuts import shortcut_precheck
from .tasks import generate_split

# Orchestration order (protocol-lock Decision 10). Every reserved seed requires a SEPARATE explicit
# phase-named command; there is NO automatic smoke->development transition.
ORCHESTRATION_ORDER: tuple[str, ...] = (
    "validate_phase_seed",
    "verify_source_identity",
    "verify_recipe_hashes_and_parameter_count",
    "create_explicit_run_directory",
    "generate_one_phase_cohort",
    "serialize",
    "shortcut_precheck",
    "train",
    "checkpoint",
    "evaluate",
    "emit_traces_and_metrics",
    "assemble_manifest",
    "replay",
    "compare_digests",
    "emit_integrity_status",
    "stop",
)

# Fail-closed rejection conditions (protocol-lock Decision 11), recorded for review/tests.
FAIL_CLOSED_REJECTIONS: tuple[str, ...] = (
    "unknown phase",
    "wrong seed",
    "wrong cohort",
    "final seed under a non-final phase",
    "cross-role phase/seed combination",
    "reserved seed without its phase declared",
    "non-empty output directory",
    "overwrite attempt",
    "stale checkpoint",
    "incomplete prior run",
    "unsupported subcommand",
    "wildcard/range/list seed input",
    "unresolved shortcut state",
    "replay mismatch",
)


class ShortcutGateError(RuntimeError):
    """Raised when the final phase is attempted while the shortcut precheck is unresolved/failing."""


def build_cohort(seed: int, cohort: str, token: str | None = None):
    """Build all C1-C8 examples for a (seed, cohort). `token` carries the declared phase; reserved
    seeds fail closed unless their phase is named (the primitive generators are guarded too, so the
    phase is threaded through)."""
    require_execution_authorization(seed, token)  # raises for a reserved seed without its phase
    return {split: generate_split(split, cohort, seed, token=token) for split in SPLIT_IDS}


def serialize_cohort(cohort_examples) -> dict:
    return {split: [serialize(e) for e in exs] for split, exs in cohort_examples.items()}


@dataclass(frozen=True)
class FinalPhaseGuard:
    shortcut_passed: bool
    authorized: bool


def enter_final_phase(seed: int, token: str | None, shortcut_examples) -> FinalPhaseGuard:
    """Fail-closed entry to the final phase: needs the 'final' phase declared AND a passing shortcut precheck."""
    status = shortcut_precheck(shortcut_examples)
    if not status.passed:
        raise ShortcutGateError(
            "shortcut precheck failed or unresolved; final-phase execution is blocked"
        )
    require_execution_authorization(seed, token)  # raises for a reserved seed without its phase
    return FinalPhaseGuard(shortcut_passed=True, authorized=True)


def main(argv=None):  # pragma: no cover - use the CLI (cli.main) with an explicit --phase
    raise ExecutionNotAuthorized(
        "use the phase-scoped CLI (python -m experiments.unseen_identifier_copy_selection) with --phase"
    )
