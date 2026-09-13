"""The deployment composition root: the one place a real Google client is constructed.

Nothing else in this repository calls :func:`build_google_secret_manager_client`. A test
passes ``client=`` and gets a fake; the deployed job passes nothing and gets the real
one, built from the Cloud Run Job's attached service account. That asymmetry is the
whole point of the seam, so it lives in a module named for what it is rather than being
spread through the runner.

The composition root is also where the job refuses to build anything at all until the
gates that protect a credential have passed. Construction order is the enforcement:
:func:`build_custody_adapter` will not construct a real client for a run whose posture
or designation is outstanding, so an incomplete run cannot reach Secret Manager even by
programming error.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional

from ugence_model_egress_custody_gcp import (
    CustodyConfig, ProductionFormSecretManagerCustodyAdapter, SecretManagerClient,
    build_google_secret_manager_client)

from .gates import GateReport

__all__ = ["CompositionRefused", "build_custody_adapter"]


class CompositionRefused(RuntimeError):
    """The job would not compose a credential path for this run, and why."""


def build_custody_adapter(
    job_config,
    *,
    designation_record: Mapping[str, Any],
    gates: GateReport,
    client: Optional[SecretManagerClient] = None,
) -> ProductionFormSecretManagerCustodyAdapter:
    """The production-form custody adapter for this run.

    ``client`` is injected by tests. Left as ``None`` — which only the deployed job does
    — the real Google Secret Manager client is built here, and that call is reached only
    after the guard below.
    """

    if not gates.may_compose_components:
        raise CompositionRefused(
            f"nothing is composed while {gates.first_blocked} is outstanding "
            f"(all outstanding: {', '.join(gates.blocked)}). No Google client is built, no custody "
            f"adapter exists, no transport exists and no Secret Manager materialization is attempted "
            f"until the configuration, the execution posture, the seventeen designations, their "
            f"independent verification, the owner's separate explicit authorization and the "
            f"live-vendor-egress flag have all passed, in that order "
            f"(LP-7 ruling 12, LP-8, commissioning ADR §0.6)")
    config = CustodyConfig.from_mapping(job_config.custody)
    if client is None:
        client = build_google_secret_manager_client()
    return ProductionFormSecretManagerCustodyAdapter(
        config=config, client=client, designation=designation_record["step8_required_values"])
