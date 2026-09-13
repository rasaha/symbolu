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

    ``client`` is injected by tests and by the offline path. Left as ``None`` — which
    only the deployed job does — the real Google Secret Manager client is built here.
    """

    if not gates.may_materialize_a_credential:
        raise CompositionRefused(
            "no credential path is composed while "
            f"{', '.join(gates.blocked)} is outstanding; the execution posture, the seventeen "
            f"designations and the owner's canonical authorization all come before any credential "
            f"is materialized, because a run that may not call may not read "
            f"(LP-7 ruling 12, LP-8, commissioning ADR §0.6)")
    config = CustodyConfig.from_mapping(job_config.custody)
    if client is None:
        client = build_google_secret_manager_client()
    return ProductionFormSecretManagerCustodyAdapter(
        config=config, client=client, designation=designation_record["step8_required_values"])
