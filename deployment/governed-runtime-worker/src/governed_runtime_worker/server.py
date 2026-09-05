"""The listener (CR-3): TLS on a private interface, or a plain loopback listener in
test mode only. Startup prints one redacted configuration line and never a DSN."""

from __future__ import annotations

import ssl
import sys
from typing import Optional

from .composition import PostureRefused, WallClock, compose
from .config import WorkerConfig, WorkerConfigError
from .redaction import Scrubber
from .version import DEPLOYMENT_NAME, ENFORCEMENT_ENABLED, MATURITY, __version__
from .workload import ShadowWorkload

__all__ = ["run"]

IDLE_TIMEOUT_SECONDS = 60


def run(config: Optional[WorkerConfig] = None) -> int:
    config = config or WorkerConfig.from_env()
    scrub = Scrubber(config.secrets).scrub
    try:
        worker = compose(config, clock=WallClock(),
                         workload=ShadowWorkload(required_role=config.required_role or "unset"))
    except (WorkerConfigError, PostureRefused) as exc:
        sys.stderr.write(scrub(f"{exc.code}: {exc}\n"))
        return 1

    sys.stderr.write(scrub(
        f"{DEPLOYMENT_NAME} {__version__} {MATURITY} enforcement_enabled={ENFORCEMENT_ENABLED} "
        f"mode={config.deployment_mode} listener={'https' if config.terminates_tls else 'http'}://"
        f"{config.bind_host}:{config.port} config={config.redacted()}\n"))
    if config.deployment_mode == "test":
        sys.stderr.write("WARNING: UGENCE_REVIEW_DEPLOYMENT_MODE=test (loopback development mode)\n")

    import uvicorn

    try:
        uvicorn.run(
            worker.app, host=config.bind_host, port=config.port,
            ssl_certfile=config.tls_cert_file or None, ssl_keyfile=config.tls_key_file or None,
            ssl_version=ssl.PROTOCOL_TLS_SERVER, timeout_keep_alive=IDLE_TIMEOUT_SECONDS,
            log_level="warning", access_log=False, server_header=False, date_header=True,
        )
    finally:
        worker.close()
    return 0
