"""Governed runtime worker — the composition root of the governed review service
(ADR_UGENCE_REVIEW_SERVICE_COMPOSITION_ROOT_SCOPING.md, step 2; rulings CR-1, CR-3,
CR-4, CR-5).

    ONE PROCESS. IT WIRES; IT DECIDES NOTHING. Production mode is a fail-closed
    posture, never a certification, and enables no LIVE execution.

Since 0.2.0 the review service it composes exposes the sixth route of front-door seam
6 (FD-10): a relayed start of this deployment's own shadow workflow, under its own
definition digest, with nothing supplied by the caller but a correlation id.
"""

from __future__ import annotations

from .composition import (
    STORE_FILES,
    PostureRefused,
    WallClock,
    Worker,
    WorkerClock,
    build_identity_port,
    compose,
    preflight,
)
from .config import ENV_PREFIX, MODES, WorkerConfig, WorkerConfigError, is_private_bind
from .redaction import REDACTED, Scrubber, redact_dsn
from .starter import ShadowRunStarter, instance_id_for
from .version import DEPLOYMENT_NAME, ENFORCEMENT_ENABLED, MATURITY, __version__
from .workload import ShadowProvider, ShadowUpstreamSource, ShadowWorkload, Workload

__all__ = [
    "__version__", "DEPLOYMENT_NAME", "MATURITY", "ENFORCEMENT_ENABLED",
    "WorkerConfig", "WorkerConfigError", "MODES", "ENV_PREFIX", "is_private_bind",
    "compose", "preflight", "build_identity_port", "Worker", "WorkerClock", "WallClock",
    "PostureRefused", "STORE_FILES",
    "Workload", "ShadowWorkload", "ShadowProvider", "ShadowUpstreamSource",
    "ShadowRunStarter", "instance_id_for",
    "redact_dsn", "Scrubber", "REDACTED",
]
