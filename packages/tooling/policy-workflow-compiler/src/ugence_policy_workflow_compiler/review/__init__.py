"""Governed diff-driven review (PWC-P3A).

Standalone review artifacts and a fail-closed gate. Nothing here is stored inside a
policy pack, an approval record, or a compiled release's logical payload.
"""

from __future__ import annotations

from .gate import check_review
from .models import (
    REVIEW_ENFORCEMENT,
    REVIEWER_IDENTITY,
    ReviewCheck,
    ReviewCode,
    ReviewDisposition,
    ReviewLedger,
    ReviewRequirement,
    ReviewStepRequirement,
)
from .router import derive_review_requirement

__all__ = [
    "REVIEW_ENFORCEMENT",
    "REVIEWER_IDENTITY",
    "ReviewCode",
    "ReviewStepRequirement",
    "ReviewRequirement",
    "ReviewDisposition",
    "ReviewLedger",
    "ReviewCheck",
    "derive_review_requirement",
    "check_review",
]
