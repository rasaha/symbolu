"""The four governance strategies + a registry keyed by strategy id."""
from __future__ import annotations

from .protocol import COST_KEYS, GovernanceStrategy, zero_cost
from .no_governance import NoGovernanceStrategy
from .action_only import ActionOnlyStrategy
from .assertion_only import AssertionOnlyStrategy
from .full_governance import FullGovernanceStrategy

STRATEGIES = {
    "no_governance": NoGovernanceStrategy,
    "action_only": ActionOnlyStrategy,
    "assertion_only": AssertionOnlyStrategy,
    "full_governance": FullGovernanceStrategy,
}

STRATEGY_ORDER = ("no_governance", "action_only", "assertion_only", "full_governance")


def build_strategy(strategy_id: str) -> GovernanceStrategy:
    return STRATEGIES[strategy_id]()


__all__ = [
    "GovernanceStrategy", "COST_KEYS", "zero_cost", "STRATEGIES", "STRATEGY_ORDER",
    "build_strategy", "NoGovernanceStrategy", "ActionOnlyStrategy", "AssertionOnlyStrategy",
    "FullGovernanceStrategy",
]
