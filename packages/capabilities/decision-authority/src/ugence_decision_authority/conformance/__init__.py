"""Decision Governance — reusable domain conformance kit.

A domain-agnostic battery of checks proving a consuming domain runs the kernel
governance lifecycle correctly: lifecycle completion, kernel-typed contracts and
repositories, audit-namespace discipline, authorization, execution,
reconciliation, serialization, hashing, and the kernel dependency rule.

Adapt a domain with a :class:`DomainConformanceFixture` and run:

    from decision_governance.conformance import run_domain_conformance
    report = run_domain_conformance(my_fixture)
    assert report.passed, report.failures

The same kit validates every consuming domain unchanged.
"""
from __future__ import annotations

from .fixtures import DomainConformanceFixture, LifecycleOutcome, SimpleFixture
from .results import CheckResult
from .runner import ConformanceReport, run_domain_conformance

__all__ = [
    "run_domain_conformance",
    "ConformanceReport",
    "CheckResult",
    "DomainConformanceFixture",
    "LifecycleOutcome",
    "SimpleFixture",
]
