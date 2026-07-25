"""Conformance-kit runner — executes the reusable check battery on a domain."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import (
    audit as _audit,
    authorization as _authorization,
    contracts as _contracts,
    dependency_rules as _dependency_rules,
    execution as _execution,
    hashes as _hashes,
    lifecycle as _lifecycle,
    reconciliation as _reconciliation,
    repositories as _repositories,
    serialization as _serialization,
)
from .fixtures import DomainConformanceFixture, LifecycleOutcome
from .results import CheckResult


@dataclass
class ConformanceReport:
    domain: str
    results: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def failures(self) -> list[CheckResult]:
        return [r for r in self.results if not r.passed]

    def summary(self) -> str:
        ok = sum(1 for r in self.results if r.passed)
        return f"{self.domain}: {ok}/{len(self.results)} conformance checks passed"


# Dimensions run against the captured lifecycle outcome.
_OUTCOME_DIMENSIONS = (
    ("lifecycle", _lifecycle),
    ("contracts", _contracts),
    ("repositories", _repositories),
    ("audit", _audit),
    ("authorization", _authorization),
    ("execution", _execution),
    ("reconciliation", _reconciliation),
    ("serialization", _serialization),
    ("hashes", _hashes),
)


def run_domain_conformance(fixture: DomainConformanceFixture) -> ConformanceReport:
    """Build the domain platform, run one lifecycle, and validate kernel conformance.

    Reusable across every domain: the fixture supplies the domain specifics; the
    checks are entirely domain-agnostic.
    """
    report = ConformanceReport(domain=fixture.name)

    # Static dimension — independent of any domain run.
    for r in _dependency_rules.check(fixture, None, None):
        report.results.append(r)

    platform = fixture.build_platform()
    outcome: LifecycleOutcome = fixture.run_lifecycle(platform)

    for dimension, module in _OUTCOME_DIMENSIONS:
        try:
            results = module.check(fixture, platform, outcome)
        except Exception as exc:  # a check dimension that raises is itself a failure
            results = [CheckResult(dimension, f"{dimension}:error", False, repr(exc))]
        report.results.extend(results)

    return report
