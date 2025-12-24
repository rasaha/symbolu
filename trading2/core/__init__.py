"""
Trading2 Core Module

Bayesian-based state evolution for trading with recursive self-improvement.
"""

from trading2.core.config import BayesianConfig, PriorConfig, LikelihoodConfig
from trading2.core.state_register import BayesianStateRegister, BayesianPosterior
from trading2.core.evolution_engine import BayesianEvolutionEngine
from trading2.core.hybrid_engine import HybridEvolutionEngine, ActiveModel, EMAState, create_hybrid_engine
from trading2.core.observables import BayesianObservables
from trading2.core.utility import BayesianUtility, UtilityResult
from trading2.core.recursive_self_improvement import (
    RecursiveSelfImprover,
    KnowledgeBase,
    SelfEvaluator,
    MetaReasoner,
    Belief,
    BeliefType,
    ImprovementAction,
    ImprovementType,
    create_self_improving_system,
)
from trading2.core.self_improving_engine import (
    SelfImprovingHybridEngine,
    create_self_improving_engine,
)

__all__ = [
    # Config
    "BayesianConfig",
    "PriorConfig",
    "LikelihoodConfig",
    # State
    "BayesianStateRegister",
    "BayesianPosterior",
    # Engines
    "BayesianEvolutionEngine",
    "HybridEvolutionEngine",
    "ActiveModel",
    "EMAState",
    "create_hybrid_engine",
    # Self-Improvement
    "RecursiveSelfImprover",
    "KnowledgeBase",
    "SelfEvaluator",
    "MetaReasoner",
    "Belief",
    "BeliefType",
    "ImprovementAction",
    "ImprovementType",
    "create_self_improving_system",
    # Self-Improving Engine
    "SelfImprovingHybridEngine",
    "create_self_improving_engine",
    # Observables & Utility
    "BayesianObservables",
    "BayesianUtility",
    "UtilityResult",
]
