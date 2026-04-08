"""Presentation Layer Types.

Implements: PRESENTATION_LAYER_v1.0.md Part 3

Defines the output types for presentation directives:
- DeliveryMode: How to present content
- ConfidenceIndicator: Visual confidence signal
- SuggestedBehaviors: Additional UX behaviors
- DiagnosticInfo: Debug/advanced UX info
- PresentationDirective: Complete output structure
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class DeliveryMode(Enum):
    """Primary instruction for how to present content.

    Part 3.1: Determines the linguistic style of delivery.
    """

    CONFIDENT = "confident"  # Direct, assertive delivery
    HEDGED = "hedged"  # Qualified, tentative language
    CLARIFYING = "clarifying"  # Request user clarification
    ACKNOWLEDGING = "acknowledging"  # Acknowledge uncertainty
    SILENT = "silent"  # Suppress output entirely


class ConfidenceIndicator(Enum):
    """Visual/textual confidence signal for UX.

    Part 3.2: Maps to visual indicators (colors, icons, etc.).
    """

    HIGH = "high"  # Green / Full indicator
    MEDIUM = "medium"  # Yellow / Partial indicator
    LOW = "low"  # Red / Minimal indicator
    UNKNOWN = "unknown"  # Gray / No indicator


@dataclass
class SuggestedBehaviors:
    """Additional UX behaviors to trigger.

    Part 3.3: Boolean flags for optional UX actions.
    """

    show_alternatives: bool = False  # Display multiple options
    request_repeat: bool = False  # Ask user to repeat
    offer_clarification: bool = False  # Offer to explain
    show_reasoning: bool = False  # Display confidence factors
    delay_response: bool = False  # Add processing pause
    escalate_to_human: bool = False  # Flag for human review


@dataclass
class DiagnosticInfo:
    """Diagnostic information for debugging/advanced UX.

    Part 3.4: Optional detailed breakdown of decision factors.
    """

    dominant_vritti: str
    primary_fracture: Optional[tuple[str, str]]
    active_penalties: list[str] = field(default_factory=list)
    signal_summary: str = ""


@dataclass(frozen=True)
class PresentationDirective:
    """Complete UX directive from Presentation Layer.

    Part 3.5: The unified output structure consumed by UX layers.

    Attributes:
        delivery_mode: Primary instruction for presentation style.
        confidence: Visual confidence indicator.
        behaviors: Additional UX behaviors to trigger.
        diagnostic: Optional debug/advanced info.
        explanation: User-facing explanation text.
        triggered_rule: Name of rule that produced this directive.
    """

    # Primary instructions
    delivery_mode: DeliveryMode
    confidence: ConfidenceIndicator

    # Behavioral suggestions (frozen dataclass requires immutable default)
    behaviors: SuggestedBehaviors = field(default_factory=SuggestedBehaviors)

    # Optional diagnostic (for debug/advanced UX)
    diagnostic: Optional[DiagnosticInfo] = None

    # Explanatory text (for user-facing explanation)
    explanation: str = ""

    # Rule that produced this directive (for audit)
    triggered_rule: str = ""

    def with_behaviors(self, **kwargs) -> "PresentationDirective":
        """Create new directive with modified behaviors.

        Since PresentationDirective is frozen, this returns a new instance.
        """
        import dataclasses

        new_behaviors = dataclasses.replace(self.behaviors, **kwargs)
        return dataclasses.replace(self, behaviors=new_behaviors)

    def with_diagnostic(self, diagnostic: DiagnosticInfo) -> "PresentationDirective":
        """Create new directive with diagnostic info attached."""
        import dataclasses

        return dataclasses.replace(self, diagnostic=diagnostic)
