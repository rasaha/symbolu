#!/usr/bin/env python
"""Container HEALTHCHECK for the governed runtime worker.

A minimal liveness probe of the worker's own ``/healthz`` on the configured bind host
and port, over TLS when the listener terminates it. Exits 0 when alive, 1 otherwise.
Does not authenticate, sends no proof and reveals nothing.
"""
from __future__ import annotations

import os
import ssl
import sys
import urllib.request


def main() -> int:
    host = os.environ.get("UGENCE_REVIEW_BIND_HOST", "127.0.0.1")
    port = os.environ.get("UGENCE_REVIEW_PORT", "8444")
    tls = bool(os.environ.get("UGENCE_REVIEW_TLS_CERT_FILE"))
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    url = f"{'https' if tls else 'http'}://{host}:{port}/healthz"
    ctx = None
    if tls:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE  # private self-signed listener; liveness only
    try:
        with urllib.request.urlopen(url, timeout=4, context=ctx) as resp:
            return 0 if resp.status == 200 else 1
    except Exception:  # noqa: BLE001
        return 1


if __name__ == "__main__":
    sys.exit(main())
