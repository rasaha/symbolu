"""
Motivation Flow Engine v1.0 — Deterministic Motivation Driver Classification

This module provides deterministic classification of motivational drivers
behind multi-turn sessions in Symbol-U.

Public API:
    - MotivationProfile: Classification result dataclass
    - compute_motivation_flow: Main classification function
"""

from .motivation_engine import MotivationProfile, compute_motivation_flow

__all__ = [
    "MotivationProfile",
    "compute_motivation_flow",
]
