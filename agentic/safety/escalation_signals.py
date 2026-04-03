"""
Escalation Signals — Governance facade for presentation-layer escalation.

Re-exports escalation-relevant types and de-escalation logic from
symbolu_core.presentation. These provide the governance layer with:

  - PresentationDirective.escalate_to_human flag
  - P6Lite regime selection (HOLD/DE_ESCALATE/CLARIFY)
  - P7Lite discourse deferral logic

Usage:
    from agentic.safety.escalation_signals import PresentationDirective
    if directive.escalate_to_human:
        # Trigger human-in-the-loop
"""

from symbolu_core.presentation.types import PresentationDirective
from symbolu_core.presentation.p6_lite import P6LiteResolver
from symbolu_core.presentation.p7_lite import P7LiteResolver

__all__ = [
    "PresentationDirective",
    "P6LiteResolver",
    "P7LiteResolver",
]
