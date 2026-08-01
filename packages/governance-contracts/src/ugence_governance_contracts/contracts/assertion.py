"""Assertion governance contract (future implementation: TAP).

An assertion-governance provider evaluates *whether an assertion is supported by
evidence*. This is **not** external execution and is never routed through the
execution port. Its result feeds the assessment / recommendation workflow.

The vocabulary here is deliberately provider-neutral — no TAP-specific terms.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Protocol, runtime_checkable

from .base import Provider


class AssertionCoverage(str, Enum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"
    INDETERMINATE = "INDETERMINATE"
    CONSTRAINED = "CONSTRAINED"


@dataclass(frozen=True)
class AssertionGovernanceRequest:
    """A neutral request to evaluate an assertion against evidence."""

    assertion: str
    assertion_type: str = ""
    evidence_refs: tuple[str, ...] = ()
    source_identity: str = ""
    policy_refs: tuple[str, ...] = ()
    context: Mapping[str, str] = field(default_factory=dict)
    correlation_id: str = ""


@dataclass(frozen=True)
class AssertionGovernanceResult:
    """A neutral assertion-evaluation outcome."""

    coverage: AssertionCoverage
    evidence_coverage: float = 0.0            # 0..1 fraction of the assertion covered
    covered_evidence_refs: tuple[str, ...] = ()
    unsupported_elements: tuple[str, ...] = ()
    omitted_qualifiers: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    obligations: tuple[str, ...] = ()
    explanation_refs: tuple[str, ...] = ()
    provider_trace_id: str = ""
    fingerprint: str = ""

    @property
    def is_supported(self) -> bool:
        return self.coverage is AssertionCoverage.SUPPORTED


@runtime_checkable
class AssertionGovernanceProvider(Provider, Protocol):
    """Evaluate whether an assertion is supported by evidence."""

    def evaluate(self, request: AssertionGovernanceRequest) -> AssertionGovernanceResult: ...
