"""Deprecation warnings for the compatibility layer."""
from __future__ import annotations
import warnings


class AgentRuntimeDeprecationWarning(DeprecationWarning):
    pass


def deprecated(what: str, replacement: str) -> None:
    warnings.warn(
        f"{what} is deprecated in the Agent Runtime migration; use {replacement}. "
        "Governance now lives in the AI Control Plane, not the runtime.",
        AgentRuntimeDeprecationWarning, stacklevel=3)
