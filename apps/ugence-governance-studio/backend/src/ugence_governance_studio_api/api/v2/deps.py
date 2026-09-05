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
