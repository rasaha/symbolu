"""MEU validation job — a Cloud Run **Job** for the commissioning validation.

    OFFLINE BY DEFAULT. LIVE FAILS CLOSED. NO GENUINE DISPATCH PATH EXISTS IN THIS
    SLICE. Running it offline reads no secret, opens no connection and writes one
    redacted report.

It is a job, not a service: it runs to completion and exits, binds no port and exposes
no HTTP endpoint, so nothing can call it and the operator starts it.

This package is the deployment composition root: :mod:`meu_validation_job.composition`
is the only place in the repository that constructs a real Google Secret Manager client,
and it refuses to construct one while the execution posture or the seventeen step-8
designations are outstanding.
"""

from __future__ import annotations

from .config import JobConfig, JobConfigRefused, load_config
from .gates import GATES, GATES_BEFORE_COMPOSITION, GateOutcome, GateReport, evaluate_gates
from .job import JobResult, ci_marker_variables, run
from .version import (
    CONFIG_SCHEMA,
    DEPLOYMENT_KIND,
    GENUINE_DISPATCH_IMPLEMENTED,
    MATURITY,
    REPORT_SCHEMA,
    __version__,
)

__all__ = [
    "__version__", "MATURITY", "DEPLOYMENT_KIND", "GENUINE_DISPATCH_IMPLEMENTED",
    "CONFIG_SCHEMA", "REPORT_SCHEMA",
    "JobConfig", "JobConfigRefused", "load_config",
    "GATES", "GATES_BEFORE_COMPOSITION", "GateOutcome", "GateReport", "evaluate_gates",
    "JobResult", "ci_marker_variables", "run",
]
