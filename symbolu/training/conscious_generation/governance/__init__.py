"""Governance layer (Pranamaya plane) for Conscious Generation."""

from symbolu.training.conscious_generation.governance.kosha_router import (
    KoshaDomainRouter,
    KoshaPrimitiveRouter,  # backward compatibility alias
)
from symbolu.training.conscious_generation.governance.bliss_gate import (
    BlissTokenGate,
)

__all__ = ["KoshaDomainRouter", "KoshaPrimitiveRouter", "BlissTokenGate"]
