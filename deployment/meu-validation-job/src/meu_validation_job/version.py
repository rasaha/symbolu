"""Single source of truth for this deployment unit's version and posture."""

from __future__ import annotations

__version__ = "0.1.0"

#: A Cloud Run **Job**: it runs to completion and exits. It is not a service, it binds
#: no port and it exposes no HTTP endpoint. Nothing can call it; the operator starts it.
DEPLOYMENT_KIND = "GCP_CLOUD_RUN_JOB"

MATURITY = "REFERENCE_GRADE_SHADOW_ONLY"

#: No genuine dispatch path exists in this slice. The live transport is the next slice
#: and is not implemented here, so ``live`` mode has nothing to dispatch with and says
#: so rather than pretending to be blocked only by authorization.
GENUINE_DISPATCH_IMPLEMENTED = False

REPORT_SCHEMA = "meu-validation-job.report.v1"
CONFIG_SCHEMA = "meu-validation-job.config.v1"

#: Exit codes the operator and CI read.
EXIT_OK = 0
EXIT_NONCONFORMANT = 1
EXIT_REFUSED = 2
