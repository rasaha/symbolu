"""API layer: callable facade and optional FastAPI adapter."""

from __future__ import annotations

from .routes import HiringAPI, build_fastapi_router
from .schemas import (
    CreateDecisionRequest,
    CreateEvaluationRequest,
    CreateRecommendationRequest,
    TransitionRequest,
)

__all__ = [
    "HiringAPI",
    "build_fastapi_router",
    "CreateEvaluationRequest",
    "CreateRecommendationRequest",
    "CreateDecisionRequest",
    "TransitionRequest",
]
