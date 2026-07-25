"""The provider conformance kit passes against a mock-populated registry."""
from __future__ import annotations

from decision_governance_provider.conformance import run_provider_conformance


def test_provider_conformance_passes(registry):
    report = run_provider_conformance(registry)
    assert report.passed, report.failures
    dims = {r.dimension for r in report.results}
    assert dims == {"registration", "resolution", "configuration", "capability",
                    "errors", "version", "lifecycle", "integration"}


def test_integration_runs_kernel_lifecycle_through_providers(registry):
    report = run_provider_conformance(registry)
    integ = [r for r in report.results if r.dimension == "integration"]
    assert integ and all(r.passed for r in integ)
