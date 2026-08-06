"""Package entry point: ``python -m experiments.unseen_identifier_copy_selection <subcommand> ...``.

Delegates entirely to ``cli.main``; it has no logic of its own.
"""
from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
