"""
MLCR - Multi-Layer Consciousness RAG
=====================================

Main package for consciousness-aware query routing.

Version: v3.1
Status: Production
Layer: Mechanical (No Symbol-U Core dependency)
"""

from .mlcr_engine import MLCR, route_query
from .activation_plan import (
    ActivationPlan,
    TierType,
    IntentType,
    ExpertTarget
)
from .ontology_mass import OntologyMassComputer, get_ontology_computer
from .intent_classifier import IntentClassifier, get_intent_classifier
from .entropy_adapter import EntropyAdapter, get_entropy_adapter
from .tier_selector import TierSelector, get_tier_selector
from .expert_router import ExpertRouter, get_expert_router
from .renderer_context import RendererContextBuilder, get_renderer_context_builder
from .explainability import ExplainabilityLogger, get_explainability_logger

# Placeholder stubs - OLM (5+5 Ontological Layer Mapper) replaces deprecated HRM
from .olm import OLMStub, get_olm
from .olm import HRMStub, get_hrm  # Deprecated backward compatibility
from .lcm import LCMStub, get_lcm
from .lam import LAMStub, get_lam

__version__ = "3.1.0"
__all__ = [
    # Main engine
    "MLCR",
    "route_query",
    
    # Dataclasses and enums
    "ActivationPlan",
    "TierType",
    "IntentType",
    "ExpertTarget",
    
    # Component classes
    "OntologyMassComputer",
    "IntentClassifier",
    "EntropyAdapter",
    "TierSelector",
    "ExpertRouter",
    "RendererContextBuilder",
    "ExplainabilityLogger",
    
    # Singleton getters
    "get_ontology_computer",
    "get_intent_classifier",
    "get_entropy_adapter",
    "get_tier_selector",
    "get_expert_router",
    "get_renderer_context_builder",
    "get_explainability_logger",
    
    # Placeholder stubs - OLM (5+5 Ontological) replaces deprecated HRM
    "OLMStub",
    "get_olm",
    "HRMStub",  # Deprecated - use OLMStub
    "get_hrm",  # Deprecated - use get_olm
    "LCMStub",
    "LAMStub",
    "get_lcm",
    "get_lam"
]
