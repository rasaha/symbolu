"""HTTPS server entrypoint (P3E §12, §19).

Runs the fail-closed startup integrity gate BEFORE binding the port. On failure it
writes the integrity report, prints one precise code, and exits nonzero without
listening. On success it serves the wrapped app over TLS 1.2+ on 8443.
"""
from __future__ import annotations

import os
import ssl
import sys
from typing import Optional

from .app import build_app, load_frontend_marker
from .config import DeploymentConfig, IDLE_TIMEOUT_SECONDS
from .startup_integrity import IntegrityInputs, run_startup_integrity, write_report


def _default_paths(config: DeploymentConfig) -> tuple[str, str, str]:
    """Resolve the packaged OpenAPI, approved-ops manifest, and frontend marker."""
    here = os.path.dirname(os.path.abspath(__file__))
    pkg_root = os.path.abspath(os.path.join(here, "..", "..", ".."))  # repo root when run from source
    openapi = os.environ.get("UGENCE_STUDIO_OPENAPI") or os.path.join(pkg_root, "apps", "ugence-governance-studio", "contracts", "openapi.json")
    approved = os.environ.get("UGENCE_STUDIO_APPROVED_OPS") or os.path.join(pkg_root, "apps", "ugence-governance-studio", "frontend", "security", "approved-api-operations.json")
    marker = os.path.join(os.path.dirname(os.path.abspath(config.frontend_dir)), "frontend-build.json")
    return openapi, approved, marker


def build_tls_context(config: DeploymentConfig) -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2  # TLS 1.0/1.1 disabled; 1.3 stays enabled
    ctx.load_cert_chain(config.tls_cert_file, config.tls_key_file)
    return ctx


def run(config: Optional[DeploymentConfig] = None) -> int:
    config = config or DeploymentConfig.from_env()
    openapi, approved, marker = _default_paths(config)
    result = run_startup_integrity(IntegrityInputs(config=config, openapi_path=openapi, approved_ops_path=approved, frontend_build_marker=marker))

    report_path = os.path.join(config.runtime_dir, "startup-integrity.json")
    try:
        write_report(result, report_path)
    except OSError:
        pass

    if not result.ok:
        sys.stderr.write(f"{result.code}: startup integrity failed: {'; '.join(result.failures)}\n")
        return 1

    import uvicorn

    app = build_app(config, readiness=lambda: True)
    if config.mode == "test":
        sys.stderr.write("WARNING: UGENCE_STUDIO_DEPLOYMENT_MODE=test (loopback development mode)\n")

    uvicorn.run(
        app,
        host=config.bind_host,
        port=config.port,
        ssl_certfile=config.tls_cert_file,
        ssl_keyfile=config.tls_key_file,
        ssl_version=ssl.PROTOCOL_TLS_SERVER,
        timeout_keep_alive=IDLE_TIMEOUT_SECONDS,
        log_level="info",
        access_log=config.enable_access_log,
        server_header=False,
        date_header=True,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run())
