"""Closed enumerations for the governed-value kernel.

Classification is **three orthogonal dimensions**, never one enum:

- :class:`AssessmentStage` — *where in the ROI lifecycle* a figure sits
  (readiness / forecast / post-deployment). This kernel only ever produces
  ``POST_DEPLOYMENT_VALUE``.
- :class:`EvidenceStatus` — *how well substantiated* the inputs are. This kernel
  only ever produces ``REPORTED`` (caller-supplied, un-evidenced). ``OBSERVED``,
  ``ATTRIBUTED`` and ``VERIFIED`` require the evidence/attribution/authority
  layers (GV-2/GV-4), which do not exist yet.
- :class:`AuthorityStatus` — *whether an authority attested* the figure. This
  kernel only ever produces ``UNVERIFIED``.

:class:`Scorability` is a fourth, independent axis: whether a defensible number
can be produced at all. Do not conflate evidence status with lifecycle stage.
"""

from __future__ import annotations

from enum import Enum

__all__ = [
    "ValueSource",
    "DomainKind",
    "OutcomeClass",
    "MeasurementMethod",
    "OUTCOME_MEASUREMENT",
    "AssessmentStage",
    "EvidenceStatus",
    "AuthorityStatus",
    "ConfidenceClass",
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
    REGULATED = "regulated"  # health, legal, credit — loss dominates
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


class AssessmentStage(str, Enum):
    """Where in the ROI lifecycle a figure sits. Orthogonal to evidence."""

    PRE_ROI_READINESS = "pre_roi_readiness"
    FORECAST = "forecast"
    POST_DEPLOYMENT_VALUE = "post_deployment_value"


class EvidenceStatus(str, Enum):
    """How well substantiated an input/result is. Orthogonal to lifecycle stage.

    Ordered from weakest to strongest. This kernel never rises above
    ``REPORTED`` — naming an input "realized" does not make it ``OBSERVED``.
    """

    REPORTED = "reported"
    MODELED = "modeled"
    OBSERVED = "observed"
    ATTRIBUTED = "attributed"
    VERIFIED = "verified"


class AuthorityStatus(str, Enum):
    """Whether a governance/finance authority attested the figure."""

    UNVERIFIED = "unverified"
    ATTESTED = "attested"
    VERIFIED = "verified"


class ConfidenceClass(str, Enum):
    """A qualitative, **caller-reported and unverified** confidence label.

    It is carried on the case (``reported_confidence``) and echoed to the result,
    but it is:

    * caller-reported — the caller asserts it; the kernel does not derive it;
    * unverified — it is *not* an evidence determination and is entirely separate
      from :class:`EvidenceStatus` (which this kernel fixes at ``REPORTED``);
    * never used in any monetary calculation — it does not scale, gate, or enter
      NGV / ROI / payback in any way.
    """

    UNCLASSIFIED = "unclassified"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Scorability(str, Enum):
    """Whether a defensible figure can be produced at all.

    ``NOT_SCORABLE`` suppresses the headline ROI / payback (fail closed): a
    number without a defensible basis is worse than no number. Independent of
    stage, evidence status and authority status.
    """

    SCORABLE = "scorable"
    DEGRADED = "degraded"  # a figure is returned, with material caveats
    NOT_SCORABLE = "not_scorable"  # headline suppressed
