"""The scoring aggregate — everything needed to score one agent for one window.

An ``AgentValueCase`` bundles the spine inputs (realized value, error profile,
cost-to-serve) with the three modifier lenses (domain, geography, outcome) and
the attribution context, anchored to a control-plane chokepoint reference. It is
immutable and self-consistent on currency: the numerator, the TCO, and the
geographic regulatory load must all speak one currency.
"""

from __future__ import annotations

from dataclasses import dataclass

from .action import AuthorizedActionRef
from .attribution import AttributionContext
from .cost import CostToServe
from .enums import OutcomeClass
from .error_profile import ErrorProfile
from .errors import CurrencyMismatchError
from .modifiers import DomainProfile, GeographyProfile
from .value import RealizedValue

__all__ = ["AgentValueCase"]


@dataclass(frozen=True)
class AgentValueCase:
    agent_id: str
    domain: DomainProfile
    geography: GeographyProfile
    outcome: OutcomeClass
    realized: RealizedValue
    error_profile: ErrorProfile
    cost: CostToServe
    attribution: AttributionContext
    action: AuthorizedActionRef

    def __post_init__(self) -> None:
        currency = self.realized.currency
        if self.cost.currency != currency:
            raise CurrencyMismatchError(
                f"cost currency {self.cost.currency} != value currency {currency}"
            )
        if self.geography.currency != currency:
            raise CurrencyMismatchError(
                f"geography currency {self.geography.currency} != value currency {currency}"
            )

    @property
    def currency(self) -> str:
        return self.realized.currency
