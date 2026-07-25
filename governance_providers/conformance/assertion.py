"""Assertion-governance provider conformance kit."""
from __future__ import annotations

from typing import Callable

from ..contracts import AssertionGovernanceRequest
from ..contracts.assertion import AssertionCoverage, AssertionGovernanceProvider
from ..contracts.base import Provider
from ..metadata import ProviderKind
from .common import (
    ProviderConformanceReport, classified_error, common_checks,
    deterministic_fingerprint, fail, ok)


def run_assertion_provider_conformance(provider_factory: Callable[[], Provider]
                                       ) -> ProviderConformanceReport:
    rep = ProviderConformanceReport(kind="assertion_governance")
    rep.results += common_checks(provider_factory, expected_kind=ProviderKind.ASSERTION_GOVERNANCE,
                                 protocol=AssertionGovernanceProvider)
    req = AssertionGovernanceRequest(assertion="X supports Y", assertion_type="claim",
                                     evidence_refs=("e1", "e2"))

    def call(p):
        p.initialize()
        return p.evaluate(req)

    result = call(provider_factory())
    rep.results.append(ok("result", "coverage_valid")
                       if isinstance(result.coverage, AssertionCoverage)
                       else fail("result", "coverage_valid", "bad coverage type"))
    rep.results.append(ok("result", "coverage_ratio_bounded")
                       if 0.0 <= result.evidence_coverage <= 1.0
                       else fail("result", "coverage_ratio_bounded", "ratio out of [0,1]"))
    rep.results.append(deterministic_fingerprint(call, provider_factory))

    original = AssertionGovernanceRequest(assertion="X supports Y", assertion_type="claim",
                                          evidence_refs=("e1", "e2"))
    rep.results.append(ok("immutability", "request_unchanged") if req == original
                       else fail("immutability", "request_unchanged", "request mutated"))

    from ..reference.assertion import DeterministicAssertionProvider
    from ..errors import ProviderResultValidationError, ProviderTimeoutError
    if isinstance(provider_factory(), DeterministicAssertionProvider):
        def timeout():
            p = DeterministicAssertionProvider(timeout=True); p.initialize(); return p.evaluate(req)
        def malformed():
            p = DeterministicAssertionProvider(malformed=True); p.initialize(); return p.evaluate(req)
        rep.results.append(classified_error(timeout, expected=ProviderTimeoutError))
        rep.results.append(classified_error(malformed, expected=ProviderResultValidationError))
    return rep
