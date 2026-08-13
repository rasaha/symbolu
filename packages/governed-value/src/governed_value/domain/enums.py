"""Closed enumerations for the governed-value spine.

The spine is deliberately small: value decomposes into exactly three sources,
and the *intended outcome* selects exactly one measurement method. Domain and
geography act as **modifiers** on the spine's terms, not as parallel
frameworks — see :mod:`governed_value.domain.modifiers`.
"""

from __future__ import annotations

from enum import Enum

__all__ = [
    "ValueSource",
    "DomainKind",
    "OutcomeClass",
    "MeasurementMethod",
    "Scorability",
]


class ValueSource(str, Enum):
    """The only three sources of *realized* value.

    Everything else (satisfaction, "productivity", adoption) is a leading
    indicator, not value, and is intentionally not representable here.
    """

    LABOR_DISPLACED = "labor_displaced"
    THROUGHPUT_GAINED = "throughput_gained"
    LOSS_AVOIDED = "loss_avoided"


class DomainKind(str, Enum):
    """Domain sets the natural value unit and the error asymmetry."""

    SUPPORT = "support"
    SOFTWARE = "software"
    FINANCE_OPS = "finance_ops"
    REGULATED = "regulated"  # health, legal, credit — loss-avoided dominates
    SALES_MARKETING = "sales_marketing"
    GENERIC = "generic"


class OutcomeClass(str, Enum):
    """Intended outcome sets the measurement method (see :class:`MeasurementMethod`)."""

    DETERMINISTIC_AUTOMATION = "deterministic_automation"
    JUDGMENT_SUPPORT = "judgment_support"
    DISCOVERY_INSIGHT = "discovery_insight"
    RISK_CONTAINMENT = "risk_containment"


class MeasurementMethod(str, Enum):
    """How value is attributed for a given outcome class."""

    BEFORE_AFTER_BASELINE = "before_after_baseline"
    HOLDOUT_OR_STAGED = "holdout_or_staged"
    OPTION_VALUE = "option_value"
    ACTUARIAL_BASELINE = "actuarial_baseline"


# Deterministic mapping — the intended outcome fully determines the method.
OUTCOME_MEASUREMENT: dict[OutcomeClass, MeasurementMethod] = {
    OutcomeClass.DETERMINISTIC_AUTOMATION: MeasurementMethod.BEFORE_AFTER_BASELINE,
    OutcomeClass.JUDGMENT_SUPPORT: MeasurementMethod.HOLDOUT_OR_STAGED,
    OutcomeClass.DISCOVERY_INSIGHT: MeasurementMethod.OPTION_VALUE,
    OutcomeClass.RISK_CONTAINMENT: MeasurementMethod.ACTUARIAL_BASELINE,
}


class Scorability(str, Enum):
    """The governance verdict on whether a hard ROI figure is defensible.

    ``NOT_SCORABLE`` suppresses the headline ``ngva``/``roi`` (fail closed):
    a number without a defensible basis is worse than no number.
    """

    SCORABLE = "scorable"
    DEGRADED = "degraded"  # a figure is returned, but with material caveats
    NOT_SCORABLE = "not_scorable"  # headline suppressed
