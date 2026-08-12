"""Optional FastAPI wiring for the RA-1..RA-4 endpoints.

FastAPI is an *optional* dependency: the package core (and its conformance
suite) is stdlib-only and drives :class:`RiskAuthorityApplication` directly.
When FastAPI is installed, :func:`build_app` mounts the eight MVP endpoints
(user brief §21) over the same application facade.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

__all__ = ["build_app", "FASTAPI_AVAILABLE"]

try:  # pragma: no cover - exercised only where FastAPI is installed
    import fastapi  # noqa: F401

    FASTAPI_AVAILABLE = True
except Exception:  # pragma: no cover
    FASTAPI_AVAILABLE = False

if TYPE_CHECKING:  # pragma: no cover
    from .dependencies import RiskAuthorityApplication


def build_app(application: "RiskAuthorityApplication"):
    """Return a FastAPI app exposing the MVP endpoints over ``application``.

    Raises ``RuntimeError`` if FastAPI is not installed so the requirement is
    explicit rather than a silent import failure.
    """

    if not FASTAPI_AVAILABLE:  # pragma: no cover
        raise RuntimeError(
            "FastAPI is not installed; install risk_authority[api] to serve HTTP "
            "routes. The application facade works without it."
        )

    from fastapi import FastAPI, HTTPException  # pragma: no cover

    from ..domain.errors import RiskAuthorityError  # pragma: no cover
    from ..version import __version__  # pragma: no cover
    from .schemas import (  # pragma: no cover
        AuthorizeActionRequest,
        CreateCaseRequest,
        DecisionRequest,
        EvaluateRequest,
        IssueEnvelopeRequest,
    )

    app = FastAPI(title="Ugence Risk Authority", version=__version__)  # pragma: no cover

    @app.post("/risk-cases")  # pragma: no cover
    def create_case(req: CreateCaseRequest):
        try:
            case = application.create_case(req)
        except RiskAuthorityError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        return {"case_id": case.case_id, "state": case.state.value}

    @app.post("/actions/authorize")  # pragma: no cover
    def authorize_action(req: AuthorizeActionRequest):
        authz = application.authorize_action(req)
        return {
            "authorization_id": authz.authorization_id,
            "decision": authz.decision.value,
            "action_digest": authz.action_digest,
            "reason_codes": list(authz.reason_codes),
        }

    return app
