"""Shared v2 request helpers.

Mirrors ``api/deps.py``: routers resolve inputs, call one service, and wrap the result
in the same ``ApiResponse`` envelope v1 uses — including its ``maturity`` /
``SYNTHETIC_NOTICE`` block, unchanged. No policy logic lives here.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import ugence_agent_workforce_composer.api as awc
from starlette.requests import Request

from ...contracts.envelope import ApiResponse, Diagnostic
from ...version import API_V2_CONTRACT_VERSION

__all__ = ["v2_response", "studio", "V2Context"]


def _absent_review() -> Any:
    from ...services.studio_v2 import ReviewRelayService

    return ReviewRelayService(review=None)


def _absent_registry() -> Any:
    from ...services.studio_v2 import RegistryService

    return RegistryService(registry=None)


def _absent_start_run() -> Any:
    from ...services.studio_v2 import StartRunService

    return StartRunService(review=None)


def _absent_data_use() -> Any:
    from ...services.studio_v2 import DeclarationService

    return DeclarationService(declarations=None)


def _absent_vendor() -> Any:
    from ...services.studio_v2 import VendorDeclarationService

    return VendorDeclarationService(declarations=None)


def _absent_clearance_export() -> Any:
    from ...services.studio_v2 import ClearanceExportService

    return ClearanceExportService(source=None)


def _absent_ledger_observe() -> Any:
    from ...services.studio_v2 import LedgerObserveService

    return LedgerObserveService(review=None)


def _absent_deployment_status() -> Any:
    from ...services.studio_v2 import DeploymentStatusService

    return DeploymentStatusService(report=None)


class V2Context:
    """The six services, plus whatever optional dependencies were configured.

    Every service is constructed with what the deployment supplied and nothing else.
    An absent dependency stays absent: the service reports itself unavailable rather
    than being handed a stub that would make a missing capability look present.
    """

    def __init__(
        self,
        *,
        constitution: Any,
        policy: Any,
        authority: Any,
        simulate: Any,
        publish: Any,
        observe: Any,
        review: Any = None,
        registry: Any = None,
        start_run: Any = None,
        data_use: Any = None,
        vendor: Any = None,
        clearance_export: Any = None,
        ledger_observe: Any = None,
        deployment_status: Any = None,
    ) -> None:
        self.constitution = constitution
        self.policy = policy
        self.authority = authority
        self.simulate = simulate
        self.publish = publish
        self.observe = observe
        # GAS-7 HR-D: the review relay. Optional so a context built before it existed
        # keeps working; absent, the review routes report the gap.
        self.review = review if review is not None else _absent_review()
        # Front-door seam 5 (FD-9): the registration intake. Optional for the same reason;
        # absent, the registry routes report the gap.
        self.registry = registry if registry is not None else _absent_registry()
        # Front-door seam 6 (FD-10): the worker shadow-run relay. Absent, the start route
        # reports the same review_service gap as the review screens.
        self.start_run = start_run if start_run is not None else _absent_start_run()
        # Front-door seam 8 (FD-12): the data-use declaration intake. Absent, the
        # data-use routes report the gap.
        self.data_use = data_use if data_use is not None else _absent_data_use()
        # Front-door seam 9 (FD-13): the vendor-dependency intake. Absent, the vendor
        # routes report the gap.
        self.vendor = vendor if vendor is not None else _absent_vendor()
        # Clearance export (CE-5 EXPORT_IS_A_READ): the one read that returns the
        # portable form of a clearance the deployment already holds. Absent, the
        # route reports the gap rather than answering as though the tenant simply
        # held none.
        self.clearance_export = (
            clearance_export if clearance_export is not None
            else _absent_clearance_export())
        # Front-door seam 7 (FD-11): Observe over the worker's ledger. Absent, the ledger
        # route reports the same review_service gap.
        self.ledger_observe = ledger_observe if ledger_observe is not None else _absent_ledger_observe()
        # MA-2 as amended (MS-1 to MS-5): the deployment's own startup attestation,
        # handed once at composition. Absent, the status route reports the gap.
        self.deployment_status = (
            deployment_status if deployment_status is not None
            else _absent_deployment_status())


def studio(request: Request) -> V2Context:
    return request.app.state.studio


def v2_response(
    request: Request,
    *,
    operation: str,
    result: Any,
    diagnostics: Optional[List[Diagnostic]] = None,
    warnings: Optional[List[str]] = None,
) -> ApiResponse:
    """The v1 envelope, carrying the v2 contract identity.

    Reusing the envelope is deliberate: the synthetic / planning-only notice, the
    strict request models and the request-id discipline are exactly the properties v2
    must not lose, and re-declaring them would let the two drift apart.
    """
    response = ApiResponse(
        request_id=getattr(request.state, "request_id", "unknown"),
        operation=operation,
        awc_version=awc.__version__,
        result=result,
        diagnostics=diagnostics or [],
        warnings=warnings or [],
    )
    response.api_version = API_V2_CONTRACT_VERSION
    return response
