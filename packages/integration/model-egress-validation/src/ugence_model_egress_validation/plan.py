"""The validation plan digest (ADR §0.6): what the owner's typed authorization binds
as ``validation_plan_digest``. It is the digest of this distribution's row table and the
three distribution versions, so an authorization issued for one plan cannot admit a
call under another.
"""

from __future__ import annotations

from ugence_model_egress_unit import canonical_digest
from ugence_model_egress_unit import __version__ as unit_version
from ugence_model_egress_provider_openai import __version__ as adapter_version

from .rows import ROWS
from .version import __version__ as harness_version

__all__ = ["VALIDATION_PLAN_DIGEST_DOMAIN", "validation_plan_digest"]

VALIDATION_PLAN_DIGEST_DOMAIN = "ugence.model-egress-validation/validation-plan/v1"


def validation_plan_digest() -> str:
    body = {
        "versions": {"ugence-model-egress-unit": unit_version, "ugence-model-egress-provider-openai": adapter_version,
                     "ugence-model-egress-validation": harness_version},
        "rows": [{"row": r.row, "scenario": r.scenario, "required": r.required, "offline": r.offline,
                  "infrastructure_dependent": r.infrastructure_dependent} for r in ROWS],
    }
    return canonical_digest(VALIDATION_PLAN_DIGEST_DOMAIN, "ValidationPlan", body)
