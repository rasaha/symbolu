"""Action-governance provider conformance kit."""
from __future__ import annotations

from typing import Callable

from ..contracts import ActionGovernanceRequest
from ..contracts.action import ActionGovernanceOutcome, ActionGovernanceProvider
from ..contracts.base import Provider
from ..metadata import ProviderKind
from .common import (
    ProviderConformanceReport, classified_error, common_checks,
    deterministic_fingerprint, fail, ok)


def run_action_provider_conformance(provider_factory: Callable[[], Provider]
                                    ) -> ProviderConformanceReport:
    rep = ProviderConformanceReport(kind="action_governance")
    rep.results += common_checks(provider_factory, expected_kind=ProviderKind.ACTION_GOVERNANCE,
                                 protocol=ActionGovernanceProvider)
    req = ActionGovernanceRequest(action_type="ACT", requested_parameters={"k": "v"})

    def call(p):
        p.initialize()
        return p.authorize(req)

    result = call(provider_factory())
    rep.results.append(ok("result", "outcome_valid")
                       if isinstance(result.outcome, ActionGovernanceOutcome)
                       else fail("result", "outcome_valid", "bad outcome type"))
    rep.results.append(deterministic_fingerprint(call, provider_factory))

    # input immutability: the request must be unchanged after the call
    original = ActionGovernanceRequest(action_type="ACT", requested_parameters={"k": "v"})
    rep.results.append(ok("immutability", "request_unchanged") if req == original
                       else fail("immutability", "request_unchanged", "request mutated"))

    # error classification: an unavailable provider raises a classified error
    from ..reference.action import DeterministicActionGovernanceProvider
    from ..errors import ProviderUnavailableError
    if isinstance(provider_factory(), DeterministicActionGovernanceProvider):
        def unavailable():
            p = DeterministicActionGovernanceProvider(unavailable=True); p.initialize()
            return p.authorize(req)
        rep.results.append(classified_error(unavailable, expected=ProviderUnavailableError))
    return rep
