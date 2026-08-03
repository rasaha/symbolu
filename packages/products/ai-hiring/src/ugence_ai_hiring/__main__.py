"""Top-level CLI: ``python -m ugence_ai_hiring <command>``.

Thin, read-only, offline command surface over the public API. Every subcommand
runs deterministic simulation with in-memory adapters and prints to stdout — no
network, no model SDK, no credentials, no production integration, and it stops
before any downstream enterprise action is executed.

Subcommands:

* ``version`` — print **distribution + product** version metadata
                (:func:`ugence_ai_hiring.version_info`); ``--json`` for JSON.
* ``verify``  — assert the packaged product's safety/governance invariants and
                print PASS/FAIL.
* ``demo``    — run the canonical safe demo (evidence → assessment → advisory
                recommendation → authorized human decision) and print the cohort
                summary. Stops before enterprise action execution.
* ``report``  — print a sample accountability report from the demo cohort.

``verify`` / ``demo`` / ``report`` delegate to :mod:`ugence_ai_hiring.product.cli`.
"""

from __future__ import annotations

import json
import sys
from typing import Sequence

from .product import cli as _product_cli
from .version import version_info


def _cmd_version(as_json: bool) -> int:
    info = version_info()
    if as_json:
        print(json.dumps(info.to_dict(), indent=2))
    else:
        print(f"{info.distribution} {info.distribution_version} "
              f"(distribution) — AI Hiring product {info.product_version} "
              f"({info.stability})")
        print(f"release classification: {info.release_classification}")
        print(f"production certified: {info.production_certified}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in argv
    positional = [a for a in argv if a != "--json"]
    command = positional[0] if positional else None
    if command == "version":
        return _cmd_version(as_json)
    # Delegate every other subcommand (verify / demo / report) to the product CLI,
    # preserving its flags.
    return _product_cli.main(argv)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
