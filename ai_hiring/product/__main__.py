"""Enable ``python -m ai_hiring.product`` to invoke the product CLI."""

from __future__ import annotations

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
