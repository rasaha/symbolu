"""Real executable CLI for the unseen-identifier diagnostic.

Invocation: ``python -m experiments.unseen_identifier_copy_selection <subcommand> ...``.

Every subcommand requires an explicit ``--phase`` (fixture / smoke / development / final), EXACTLY ONE
explicit ``--seed`` (a single integer — no wildcard, range, comma-list, glob, or alias), an explicit
``--cohort``, and an explicit ``--output-dir``. The seed must belong to the named phase's exact role;
reserved-phase seeds are refused unless their phase is named, so they are never run implicitly. This
is experimental-protocol control, not a security-authorization system. ``--help`` imports no model,
generates no data, writes nothing, and mutates no RNG state (torch-bearing orchestration is imported
lazily inside command handlers).
"""
from __future__ import annotations

import argparse
from typing import Sequence

from .execution import PHASES

# Deterministic exit codes.
EXIT_OK = 0
EXIT_PROTOCOL_REFUSED = 2
EXIT_CONTRACT = 3
EXIT_OUTPUT = 4
EXIT_REPLAY_MISMATCH = 5
EXIT_ERROR = 6

_SUBCOMMANDS = (
    "build-cohort",
    "shortcut-precheck",
    "train",
    "evaluate",
    "replay",
    "assemble-manifest",
)


class SeedContractError(argparse.ArgumentTypeError):
    """Raised when --seed is anything other than exactly one plain integer."""


def _one_explicit_seed(value: str) -> int:
    """Accept exactly one integer seed; reject wildcard / range / list / glob / alias forms."""
    text = value.strip()
    forbidden = (",", ":", "-", "*", "?", "..", "/", " ")
    lowered = text.lower()
    if lowered in ("all", "all-dev", "all_development", "dev", "development", "final", "smoke"):
        raise SeedContractError(f"seed alias {value!r} is not allowed; give exactly one integer seed")
    for marker in forbidden:
        if marker in text:
            raise SeedContractError(
                f"seed {value!r} must be exactly one integer (no wildcard/range/list/glob)"
            )
    try:
        return int(text)
    except ValueError as exc:
        raise SeedContractError(f"seed {value!r} is not a plain integer") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m experiments.unseen_identifier_copy_selection",
        description="Unseen-identifier copy/selection diagnostic — phase-scoped executable interface.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)
    for name in _SUBCOMMANDS:
        sub = subparsers.add_parser(name, help=f"{name} for one explicit seed in the named phase")
        sub.add_argument("--phase", choices=PHASES, required=True,
                         help="experimental phase; the seed must belong to this phase's exact role")
        sub.add_argument("--seed", type=_one_explicit_seed, required=True,
                         help="exactly one integer seed (no wildcard/range/list)")
        sub.add_argument("--cohort", choices=("seen", "unseen"), required=True)
        sub.add_argument("--output-dir", required=True,
                         help="explicit output directory; artifacts are written ONLY under it")
    return parser


def _handle(args) -> int:
    from .execution import ExecutionNotAuthorized, validate_phase_seed
    from .evidence import EvidenceError

    try:
        # Exact phase/seed-role validation before any side effect. Reserved seeds are refused unless
        # their phase is explicitly named; one seed per invocation (parser-enforced).
        validate_phase_seed(args.phase, args.seed)
    except ExecutionNotAuthorized as exc:
        print(f"protocol refused: {exc}")
        return EXIT_PROTOCOL_REFUSED

    try:
        # Torch-bearing orchestration is imported lazily, only after the protocol check passes. The
        # declared phase is threaded to the primitive guards so reserved seeds run only under their
        # own phase.
        from .runner import build_cohort

        if args.subcommand == "build-cohort":
            from .evidence import write_run_evidence
            from .manifest import dataset_digest
            from .serializer import serialize

            cohort = build_cohort(args.seed, args.cohort, token=args.phase)
            serialized = [serialize(e) for split in sorted(cohort) for e in cohort[split]]
            summary = {"phase": args.phase, "seed": args.seed, "cohort": args.cohort,
                       "dataset_digest": dataset_digest(serialized),
                       "n_examples": len(serialized)}
            write_run_evidence(args.output_dir, seed=args.seed, cohort=args.cohort,
                               traces=[], manifest=summary)
            print(f"build-cohort complete: {summary['n_examples']} examples")
            return EXIT_OK

        if args.subcommand == "shortcut-precheck":
            from .evidence import write_run_evidence
            from .shortcuts import shortcut_scores

            cohort = build_cohort(args.seed, args.cohort, token=args.phase)
            examples = [e for split in sorted(cohort) for e in cohort[split]]
            result = shortcut_scores(examples)
            write_run_evidence(args.output_dir, seed=args.seed, cohort=args.cohort,
                               traces=[], manifest=result)
            print(f"shortcut-precheck complete: all_pass={result['all_pass']}")
            return EXIT_OK if result["all_pass"] else EXIT_CONTRACT

        # train / evaluate / replay / assemble-manifest run the frozen model for one seed in the named
        # phase. Reserved seeds run only when their phase is declared; fixture phase runs locally.
        if args.subcommand == "train":
            from .training import train_cohort

            cohort = build_cohort(args.seed, args.cohort, token=args.phase)
            examples = [e for split in sorted(cohort) for e in cohort[split]]
            artifacts = train_cohort(args.seed, args.cohort, examples, args.output_dir)
            print(f"train complete: checkpoint at {artifacts.checkpoint_path}")
            return EXIT_OK

        if args.subcommand == "evaluate":
            from .evaluation import evaluate_cohort
            import os

            cohort = build_cohort(args.seed, args.cohort, token=args.phase)
            checkpoint_path = os.path.join(args.output_dir, "checkpoint.pt")
            ev = evaluate_cohort(checkpoint_path, cohort)
            print(f"evaluate complete: {len(ev.traces)} traces")
            return EXIT_OK

        if args.subcommand == "replay":
            print("replay requires an original run manifest; not run in this phase")
            return EXIT_CONTRACT

        if args.subcommand == "assemble-manifest":
            print("assemble-manifest requires a completed run; not run in this phase")
            return EXIT_CONTRACT

    except EvidenceError as exc:
        print(f"output refused: {exc}")
        return EXIT_OUTPUT
    except Exception as exc:  # pragma: no cover - defensive; deterministic error code
        print(f"error: {exc}")
        return EXIT_ERROR

    return EXIT_ERROR


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return _handle(args)
