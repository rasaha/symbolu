"""
Symbolu Robotics Tiers
======================

Three-tier control architecture:

Tier R1 (Reflexive): <1ms, safety-critical, STL-only
Tier R2 (Reactive): <10ms, behavioral, STL + edge model
Tier R3 (Deliberative): <100ms, planning, full inference

Uses patent formulas B1-B3 (BCVF) for action selection.
"""

from symbolu_robotics.tiers.base import BaseTier, TierConfig
from symbolu_robotics.tiers.reflexive import ReflexiveTier
from symbolu_robotics.tiers.reactive import ReactiveTier
from symbolu_robotics.tiers.deliberative import DeliberativeTier
from symbolu_robotics.tiers.factory import create_tier, TierLevel

__all__ = [
    "BaseTier",
    "TierConfig",
    "ReflexiveTier",
    "ReactiveTier",
    "DeliberativeTier",
    "create_tier",
    "TierLevel",
]
