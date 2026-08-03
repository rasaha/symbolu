"""Structural diff and change-impact analysis."""

from __future__ import annotations

from .change_impact import compute_impact
from .structural_diff import (
    ChangeType,
    ImpactSummary,
    ObjectChange,
    PolicyPackDiff,
    diff_policy_packs,
)

__all__ = [
    "ChangeType",
    "ObjectChange",
    "ImpactSummary",
    "PolicyPackDiff",
    "diff_policy_packs",
    "compute_impact",
]
