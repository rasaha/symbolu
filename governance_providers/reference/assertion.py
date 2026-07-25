"""Deterministic reference Assertion Governance provider (framework validation only).

NOT TAP. Evaluates an assertion against evidence with configurable outcomes.
"""

from __future__ import annotations

from ..contracts import (
    AssertionCoverage,
    AssertionGovernanceRequest,
    AssertionGovernanceResult,
)
from ..contracts.base import BaseProvider
from ..errors import ProviderResultValidationError, ProviderTimeoutError
from ..fingerprint import fingerprint
from ..metadata import (
    ProviderCapabilities,
    ProviderCompatibility,
    ProviderDescriptor,
    ProviderKind,
)

_KIND = ProviderKind.ASSERTION_GOVERNANCE


class DeterministicAssertionProvider(BaseProvider):
    def __init__(self, *, provider_id: str = "deterministic-assertion",
                 coverage: AssertionCoverage = AssertionCoverage.SUPPORTED,
                 unsupported_elements: tuple[str, ...] = (),
                 constraints: tuple[str, ...] = (),
                 timeout: bool = False, malformed: bool = False,
                 default: bool = True) -> None:
        descriptor = ProviderDescriptor(
            provider_id=provider_id, kind=_KIND, implementation_version="0.1.0",
            compatibility=ProviderCompatibility(contract_version="1.0.0"),
            capabilities=ProviderCapabilities(
                kind=_KIND, features=frozenset({"evaluate", "evidence_coverage"}),
                deterministic=True),
            factory=lambda: DeterministicAssertionProvider(
                provider_id=provider_id, coverage=coverage,
                unsupported_elements=unsupported_elements, constraints=constraints,
                timeout=timeout, malformed=malformed, default=default),
            vendor="framework-reference", default=default)
        super().__init__(descriptor)
        self._coverage = coverage
        self._unsupported = unsupported_elements
        self._constraints = constraints
        self._timeout, self._malformed = timeout, malformed

    def evaluate(self, request: AssertionGovernanceRequest) -> AssertionGovernanceResult:
        if self._timeout:
            raise ProviderTimeoutError(
                f"assertion provider '{self.descriptor().provider_id}' timed out")
        if self._malformed:
            # A provider returning a malformed result surfaces as a validation error.
            raise ProviderResultValidationError("assertion provider returned malformed result")
        covered = request.evidence_refs if self._coverage is AssertionCoverage.SUPPORTED else ()
        ratio = 1.0 if self._coverage is AssertionCoverage.SUPPORTED else (
            0.0 if self._coverage is AssertionCoverage.UNSUPPORTED else 0.5)
        fp = fingerprint({"assertion": request.assertion,
                          "type": request.assertion_type,
                          "evidence": list(request.evidence_refs),
                          "coverage": self._coverage.value})
        return AssertionGovernanceResult(
            coverage=self._coverage, evidence_coverage=ratio,
            covered_evidence_refs=covered, unsupported_elements=self._unsupported,
            constraints=self._constraints,
            explanation_refs=(f"explanation-{fp[:8]}",),
            provider_trace_id=f"trace-{fp[:12]}", fingerprint=fp)
