"""Top-level CLI: ``python -m ugence_procurement <command>``.

Thin, read-only, offline command surface over the public API. Delegates to
:mod:`ugence_procurement.product.cli`. Every subcommand runs deterministic
simulation with in-memory adapters and prints to stdout — no network, no model
SDK, no credentials, no production integration — and stops before any real
supplier effect.

Subcommands: ``version`` · ``verify`` · ``demo`` · ``report`` (``--json`` for JSON).
"""

from __future__ import annotations

from .product.cli import main

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
