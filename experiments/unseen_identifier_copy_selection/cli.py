"""Real executable CLI for the unseen-identifier diagnostic (protocol-lock Decision 2).

Invocation: ``python -m experiments.unseen_identifier_copy_selection <subcommand> ...``.

Every scientific-facing subcommand requires EXACTLY ONE explicit ``--seed`` (a single integer — no
wildcard, range, comma-list, glob, or implicit "all development seeds"), an explicit ``--cohort``,
an explicit ``--authorization-record``, and an explicit ``--output-dir``. The authorization record is
validated BEFORE any pool/cohort generation; reserved diagnostic seeds fail closed (no valid
execution token exists), so no scientific seed can be run through this interface. ``--help`` imports
no model, generates no data, writes nothing, and mutates no RNG state (torch-bearing orchestration is
imported lazily inside command handlers).
"""
from __future__ import annotations

import argparse
from typing import Sequence

# Deterministic exit codes.
EXIT_OK = 0
EXIT_AUTH_REFUSED = 2
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
        description="Unseen-identifier copy/selection diagnostic — fail-closed executable interface.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)
    for name in _SUBCOMMANDS:
        sub = subparsers.add_parser(name, help=f"{name} for one explicit authorized seed")
        sub.add_argument("--seed", type=_one_explicit_seed, required=True,
                         help="exactly one integer seed (no wildcard/range/list)")
        sub.add_argument("--cohort", choices=("seen", "unseen"), required=True)
        sub.add_argument("--authorization-record", required=True,
                         help="path to the JSON execution authorization record (validated before generation)")
        sub.add_argument("--authority-ref", default=None,
                         help="operator-controlled authoritative-default Git reference used to prove a "
                              "scientific authorization document is merged (defaults to the frozen "
                              "reference or the UNSEEN_ID_AUTHORITATIVE_REF environment value)")
        sub.add_argument("--repo-dir", default=None,
                         help="repository directory whose local Git provides the authority root "
                              "(defaults to the current working directory)")
        sub.add_argument("--output-dir", required=True,
                         help="explicit output directory; artifacts are written ONLY under it")
    return parser


def _authorize(args):
    """Validate the record into a MINTED, non-forgeable AuthorizationContext.

    Scientific states are proven against LOCAL Git (the authoritative-default reference and repo come
    from frozen config / operator-controlled flags, NEVER from the record). A caller-supplied
    authorization artifact is no longer trusted: the authorization document is read from the committed
    tree by the record's bound commit + allow-listed path."""
    from .execution import authorize, load_authorization_record

    record = load_authorization_record(args.authorization_record)
    return authorize(
        record,
        seed=args.seed,
        cohort=args.cohort,
        repo_dir=args.repo_dir,
        authoritative_ref=args.authority_ref,
    )


def _handle(args) -> int:
    from .execution import AuthorizationRecordError, ExecutionNotAuthorized, active_authorization
    from .evidence import EvidenceError

    try:
        context = _authorize(args)
    except (AuthorizationRecordError, ExecutionNotAuthorized) as exc:
        print(f"authorization refused: {exc}")
        return EXIT_AUTH_REFUSED

    try:
        # Torch-bearing orchestration is imported lazily, only after authorization passes. Every
        # generation runs inside `active_authorization`, so the primitive guards see the validated
        # capability (and only for the duration of this one command).
        from .runner import build_cohort

        if args.subcommand == "build-cohort":
            from .evidence import write_run_evidence
            from .manifest import dataset_digest
            from .serializer import serialize

            with active_authorization(context):
                cohort = build_cohort(args.seed, args.cohort, token=context.capability)
            serialized = [serialize(e) for split in sorted(cohort) for e in cohort[split]]
            summary = {"seed": args.seed, "cohort": args.cohort,
                       "dataset_digest": dataset_digest(serialized),
                       "n_examples": len(serialized)}
            write_run_evidence(args.output_dir, seed=args.seed, cohort=args.cohort,
                               traces=[], manifest=summary)
            print(f"build-cohort complete: {summary['n_examples']} examples")
            return EXIT_OK

        if args.subcommand == "shortcut-precheck":
            from .evidence import write_run_evidence
            from .shortcuts import shortcut_scores

            with active_authorization(context):
                cohort = build_cohort(args.seed, args.cohort, token=context.capability)
            examples = [e for split in sorted(cohort) for e in cohort[split]]
            result = shortcut_scores(examples)
            write_run_evidence(args.output_dir, seed=args.seed, cohort=args.cohort,
                               traces=[], manifest=result)
            print(f"shortcut-precheck complete: all_pass={result['all_pass']}")
            return EXIT_OK if result["all_pass"] else EXIT_CONTRACT

        # train / evaluate / replay / assemble-manifest run the frozen model for one authorized seed.
        # No scientific seed can reach here (scientific states fail closed at _authorize without an
        # approved artifact); a fixture seed would run locally. These handlers are thin wrappers over
        # the orchestration modules and are exercised only through mocks in fixture tests.
        if args.subcommand == "train":
            from .training import train_cohort

            with active_authorization(context):
                cohort = build_cohort(args.seed, args.cohort, token=context.capability)
            examples = [e for split in sorted(cohort) for e in cohort[split]]
            artifacts = train_cohort(args.seed, args.cohort, examples, args.output_dir)
            print(f"train complete: checkpoint at {artifacts.checkpoint_path}")
            return EXIT_OK

        if args.subcommand == "evaluate":
            from .evaluation import evaluate_cohort
            import os

            with active_authorization(context):
                cohort = build_cohort(args.seed, args.cohort, token=context.capability)
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
