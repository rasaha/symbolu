"""Immutable typed artifacts for the governed-value spine.

    ROI = (realized value - TCO) / TCO

with realized value decomposed into only three sources (labor displaced,
throughput/revenue gained, loss avoided), reduced by the wrong-action term, and
normalized to **net governed value per authorized action** — the one figure that
makes a support agent in Manila and an underwriting agent in Frankfurt
commensurable, measured at the control-plane chokepoint where authorization
already happens.
"""

from __future__ import annotations

from .action import AuthorizedActionRef
from .attribution import AttributionContext
from .case import AgentValueCase
from .cost import COST_COMPONENTS, CostToServe
from .enums import (
    OUTCOME_MEASUREMENT,
    DomainKind,
    MeasurementMethod,
    OutcomeClass,
    Scorability,
    ValueSource,
)
from .error_profile import ErrorProfile
from .errors import (
    CurrencyMismatchError,
    GovernedValueError,
    InvalidMultiplierError,
    InvalidRatioError,
)
from .events import GovernedValueEvent
from .modifiers import DomainProfile, GeographyProfile
from .money import Money
from .rates import nonneg_multiplier, to_decimal, unit_ratio
from .value import RealizedValue

__all__ = [
    "AuthorizedActionRef",
    "AttributionContext",
    "AgentValueCase",
    "COST_COMPONENTS",
    "CostToServe",
    "OUTCOME_MEASUREMENT",
    "DomainKind",
    "MeasurementMethod",
    "OutcomeClass",
    "Scorability",
    "ValueSource",
    "ErrorProfile",
    "CurrencyMismatchError",
    "GovernedValueError",
    "InvalidMultiplierError",
    "InvalidRatioError",
    "GovernedValueEvent",
    "DomainProfile",
    "GeographyProfile",
    "Money",
    "nonneg_multiplier",
    "to_decimal",
    "unit_ratio",
    "RealizedValue",
]
