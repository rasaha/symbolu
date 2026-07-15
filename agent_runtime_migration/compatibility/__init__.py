"""Compatibility layer (public). Additive; no duplicate governance authority."""
from .legacy_adapter import to_goal, to_action, DEFAULT_RISK_MAP
from .warnings import deprecated, AgentRuntimeDeprecationWarning
from .legacy_imports import get_legacy
__all__ = ["to_goal", "to_action", "DEFAULT_RISK_MAP", "deprecated",
           "AgentRuntimeDeprecationWarning", "get_legacy"]
