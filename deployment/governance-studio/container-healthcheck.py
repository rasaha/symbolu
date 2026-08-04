#!/usr/bin/env python
"""Container HEALTHCHECK (P3E §20, §24).

Performs a minimal TLS liveness probe against the local /healthz endpoint. Exits 0 when
alive, 1 otherwise. Does not authenticate and reveals nothing sensitive.
"""
from __future__ import annotations

import os
import ssl
import sys
import urllib.request


def main() -> int:
    port = os.environ.get("UGENCE_STUDIO_PORT", "8443")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # self-signed private cert; liveness only
    try:
        with urllib.request.urlopen(f"https://127.0.0.1:{port}/healthz", timeout=4, context=ctx) as resp:
            return 0 if resp.status == 200 else 1
    except Exception:  # noqa: BLE001
        return 1


if __name__ == "__main__":
    sys.exit(main())
