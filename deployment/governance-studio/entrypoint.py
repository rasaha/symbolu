#!/usr/bin/env python
"""Container entrypoint (P3E §19, §20).

Runs the fail-closed startup integrity gate and then the HTTPS server. Never binds the
port when integrity fails; exits nonzero with a precise code and no secrets.
"""
from __future__ import annotations

import sys

from governance_studio_deployment.server import run


def main() -> int:
    return run()


if __name__ == "__main__":
    sys.exit(main())
