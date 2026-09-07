"""Governed runtime worker — the composition root of the governed review service
(ADR_UGENCE_REVIEW_SERVICE_COMPOSITION_ROOT_SCOPING.md, step 2; rulings CR-1, CR-3,
CR-4, CR-5).

    ONE PROCESS. IT WIRES; IT DECIDES NOTHING. Production mode is a fail-closed
    posture, never a certification, and enables no LIVE execution.

Since 0.2.0 the review service it composes exposes the sixth route of front-door seam
6 (FD-10): a relayed start of this deployment's own shadow workflow, under its own
definition digest, with nothing supplied by the caller but a correlation id. Since
0.3.0 it exposes the seventh (FD-11): a raw read of this deployment's own tenant's
audit-ledger rows by correlation id, with the chain verification as a typed field.
Since 0.4.0 it also mounts the authority plane's four reads under ``/authority/``
(ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md AP-5 READS_FIRST), over the directory it already
opens. Since 0.5.0 it mounts the plane's two directory writes, load and revoke a role
grant (section 16, AW-1, AW-2), each behind the identity port the decision route uses
and refused outright without one (AW-5); activate and issue stay unserved.
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
