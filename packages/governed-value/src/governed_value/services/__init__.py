"""Scoring service for the realized (POST_DEPLOYMENT_VALUE) stage.

Decay projection, portfolio normalization, forecast modelling and readiness
scoring are separate, later, reviewed phases and are intentionally absent here.
"""

from __future__ import annotations

from .scorer import GovernedValueResult, score_case

__all__ = ["GovernedValueResult", "score_case"]
