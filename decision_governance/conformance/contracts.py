"""Contracts dimension — produced records are kernel DomainModel instances."""
from __future__ import annotations

from ..base import DomainModel
from ..decisions import DecisionRecord
from .results import fail, ok


def check(fixture, platform, outcome):
    results = []
    for i, record in enumerate(outcome.records):
        name = type(record).__name__
        results.append(
            ok("contracts", f"kernel_model:{name}")
            if isinstance(record, DomainModel)
            and type(record).__module__.startswith("decision_governance.")
            else fail("contracts", f"kernel_model:{name}",
                      f"record {i} is not a kernel DomainModel: {type(record)!r}"))
    has_decision = any(isinstance(r, DecisionRecord) for r in outcome.records)
    results.append(
        ok("contracts", "decision_record_present") if has_decision
        else fail("contracts", "decision_record_present",
                  "no kernel DecisionRecord among produced records"))
    return results
