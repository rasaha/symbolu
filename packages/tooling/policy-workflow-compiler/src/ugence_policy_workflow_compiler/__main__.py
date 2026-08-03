"""``python -m ugence_policy_workflow_compiler`` entry point."""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
