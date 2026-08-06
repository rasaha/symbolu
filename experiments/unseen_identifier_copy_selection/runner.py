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

# Frozen orchestration order (protocol-lock Decision 10). Every scientific seed requires a SEPARATE
# explicit command + authorization check; there is NO automatic smoke->development transition.
ORCHESTRATION_ORDER: tuple[str, ...] = (
    "validate_authorization_record",
    "verify_source_identity",
    "verify_recipe_hashes_and_parameter_count",
    "create_explicit_run_directory",
    "generate_one_authorized_cohort",
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

# Frozen fail-closed rejection conditions (protocol-lock Decision 11), recorded for review/tests.
FAIL_CLOSED_REJECTIONS: tuple[str, ...] = (
    "missing/malformed/unknown-state authorization record",
    "wrong seed",
    "wrong cohort",
    "final seed under smoke/development authorization",
    "mismatched protocol commit",
    "mismatched implementation commit",
    "mismatched model hashes",
    "parameter-count mismatch",
    "source-hash mismatch",
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
    """Build all C1-C8 examples for a (seed, cohort). Reserved seeds fail closed (the primitive
    generators are independently guarded too, so the token is threaded through)."""
    require_execution_authorization(seed, token)  # raises for reserved seeds without a valid token
    return {split: generate_split(split, cohort, seed, token=token) for split in SPLIT_IDS}


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
