"""``python -m meu_validation_job`` — the container's entrypoint command.

Two subcommands. ``validate`` runs one job. ``dry-run`` validates the configuration and
the records, prints every gate, and exits without running the harness or writing a
report, which is what an operator wants before a first Cloud Run execution.
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys
from datetime import datetime, timezone
from typing import List, Optional

from .config import JobConfigRefused, load_config
from .gates import evaluate_gates
from .job import ci_marker_variables, load_records, run
from .version import EXIT_NONCONFORMANT, EXIT_OK, EXIT_REFUSED, __version__

__all__ = ["main"]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="meu_validation_job",
        description="The MEU commissioning validation job. Offline by default; live fails closed.")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (("validate", "run one validation job and write a redacted report"),
                            ("dry-run", "validate configuration and records, print every gate, write nothing")):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("--config", required=True, type=pathlib.Path)
        command.add_argument("--now", default=None, help="ISO-8601 instant with offset; defaults to now")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = _parser().parse_args(argv)
    now = datetime.fromisoformat(args.now) if args.now else datetime.now(timezone.utc)
    try:
        config = load_config(args.config)
        designation, validation, authorization = load_records(config)
    except JobConfigRefused as refused:
        print(f"configuration refused: {refused}")
        return EXIT_REFUSED

    if args.command == "dry-run":
        gates = evaluate_gates(config, designation_record=designation, validation_record=validation,
                               authorization_record=authorization,
                               variables=ci_marker_variables(os.environ), now=now)
        print(f"meu-validation-job {__version__} dry run — mode {config.mode}, "
              f"environment {config.environment}")
        for outcome in gates.outcomes:
            print(f"  [{outcome.status:<7}] {outcome.gate}: {outcome.reason}")
        print(f"may materialize a credential: {gates.may_materialize_a_credential}")
        print(f"may dispatch a genuine call:  {gates.may_dispatch_a_genuine_call}")
        print("nothing was run and no report was written (dry run)")
        return EXIT_OK if gates.may_materialize_a_credential else EXIT_NONCONFORMANT

    result = run(config, now=now, environ=os.environ)
    for message in result.messages:
        print(message)
    print(f"outcome {result.outcome}; report -> {result.report_path}")
    return result.exit_code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
