"""``python -m ugence_actiongate_provider`` entry point (delegates to :mod:`.cli`)."""
from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
