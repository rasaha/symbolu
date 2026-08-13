"""Public application surface for ugence-governed-value.

Re-exports the aggregate input, the scorer result, the portfolio types, and the
facade so callers can ``from governed_value.api import ...`` a stable set.
"""

from __future__ import annotations

from ..domain.action import AuthorizedActionRef
from ..domain.attribution import AttributionContext
from ..domain.case import AgentValueCase
from ..domain.cost import CostToServe
from ..domain.enums import (
    DomainKind,
    MeasurementMethod,
    OutcomeClass,
    Scorability,
    ValueSource,
)
from ..domain.error_profile import ErrorProfile
from ..domain.modifiers import DomainProfile, GeographyProfile
from ..domain.money import Money
from ..domain.value import RealizedValue
from ..services.portfolio import PortfolioEntry, PortfolioSummary
from ..services.scorer import GovernedValueResult
from .facade import GovernedValueApplication

__all__ = [
    "AuthorizedActionRef",
    "AttributionContext",
    "AgentValueCase",
    "CostToServe",
    "DomainKind",
    "MeasurementMethod",
    "OutcomeClass",
    "Scorability",
    "ValueSource",
    "ErrorProfile",
    "DomainProfile",
    "GeographyProfile",
    "Money",
    "RealizedValue",
    "PortfolioEntry",
    "PortfolioSummary",
    "GovernedValueResult",
    "GovernedValueApplication",
]
