"""Immutable typed artifacts for the governed-value kernel (POST_DEPLOYMENT_VALUE).

The reported identity (GV-1):

    total benefit        = reported benefit + reported avoided loss
    ReportedNGV          = total benefit − actual losses − cost to serve
    RiskAdjustedNGV      = ReportedNGV − residual expected loss        (Σ p × magnitude)
    ReportedROI          = ReportedNGV / Total Investment
    RiskAdjustedROI      = RiskAdjustedNGV / Total Investment

Expected loss is additive absolute money and may exceed total benefit; reported
benefit is never re-discounted; Total Investment is distinct from cost-to-serve.
Every result carries an orthogonal classification
(:class:`AssessmentStage` / :class:`EvidenceStatus` / :class:`AuthorityStatus` /
:class:`Scorability`) and this kernel never rises above
``POST_DEPLOYMENT_VALUE / REPORTED / UNVERIFIED``.
"""

from __future__ import annotations

from .attribution import AttributionEvidence
from .case import AgentValueCase
from .cost import COST_COMPONENTS, CostToServe
from .enums import (
    OUTCOME_MEASUREMENT,
    AssessmentStage,
    AuthorityStatus,
    ConfidenceClass,
    DomainKind,
    EvidenceStatus,
    MeasurementMethod,
    OutcomeClass,
    Scorability,
    ValueSource,
)
from .errors import (
    CurrencyMismatchError,
    GovernedValueError,
    InvalidRatioError,
)
from .events import GovernedValueEvent
from .expected_loss import ExpectedLoss, ExpectedLossItem
from .investment import INVESTMENT_COMPONENTS, TotalInvestment
from .modifiers import DomainProfile, GeographyProfile
from .money import Money
from .rates import to_decimal, unit_ratio
from .value import ReportedValue

__all__ = [
    "AttributionEvidence",
    "AgentValueCase",
    "COST_COMPONENTS",
    "CostToServe",
    "OUTCOME_MEASUREMENT",
    "AssessmentStage",
    "AuthorityStatus",
    "ConfidenceClass",
    "DomainKind",
    "EvidenceStatus",
    "MeasurementMethod",
    "OutcomeClass",
    "Scorability",
    "ValueSource",
    "CurrencyMismatchError",
    "GovernedValueError",
    "InvalidRatioError",
    "GovernedValueEvent",
    "ExpectedLoss",
    "ExpectedLossItem",
    "INVESTMENT_COMPONENTS",
    "TotalInvestment",
    "DomainProfile",
    "GeographyProfile",
    "Money",
    "to_decimal",
    "unit_ratio",
    "ReportedValue",
]
