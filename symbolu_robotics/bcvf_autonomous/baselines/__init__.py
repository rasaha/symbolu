"""Apples-to-apples baseline shootout.

Public API:

    from symbolu_robotics.bcvf_autonomous.baselines import (
        Arbitrator, ArbitrationResult,
        BCVFArbitrator, EKFArbitrator, EKFConfig,
        MajorityVoteArbitrator, AnchorArbitrator,
        run_shootout, ShootoutResult, ShootoutSummary,
    )

See ``DESIGN.md`` in this directory for methodology + scope caveats.
"""

from __future__ import annotations

from .anchor import AnchorArbitrator
from .base import ArbitrationResult, Arbitrator, validate_trajectories
from .bcvf_arbitrator import BCVFArbitrator
from .ekf_arbitrator import EKFArbitrator, EKFConfig
from .majority_vote import MajorityVoteArbitrator
from .shootout import (
    CellResult,
    ShootoutResult,
    ShootoutSummary,
    run_shootout,
)

__all__ = [
    "AnchorArbitrator",
    "ArbitrationResult",
    "Arbitrator",
    "BCVFArbitrator",
    "CellResult",
    "EKFArbitrator",
    "EKFConfig",
    "MajorityVoteArbitrator",
    "ShootoutResult",
    "ShootoutSummary",
    "run_shootout",
    "validate_trajectories",
]
