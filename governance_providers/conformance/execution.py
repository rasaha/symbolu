"""External-execution provider conformance kit."""
from __future__ import annotations

from typing import Callable

from ..contracts import ExecutionDispatchRequest
from ..contracts.execution import ExecutionBusinessOutcome, ExternalExecutionProvider
from ..contracts.base import Provider
from ..metadata import ProviderKind
from .common import (
    ProviderConformanceReport, common_checks, deterministic_fingerprint, fail, ok)


def run_execution_provider_conformance(provider_factory: Callable[[], Provider]
                                       ) -> ProviderConformanceReport:
    rep = ProviderConformanceReport(kind="external_execution")
    rep.results += common_checks(provider_factory, expected_kind=ProviderKind.EXTERNAL_EXECUTION,
                                 protocol=ExternalExecutionProvider)
    req = ExecutionDispatchRequest(action_type="ACT", parameters={"k": "v"})

    p = provider_factory(); p.initialize()
    disp = p.dispatch(req)
    rep.results.append(ok("dispatch", "accepted") if disp.accepted and disp.external_request_id
                       else fail("dispatch", "accepted", "dispatch not accepted"))
    obs = p.observe(external_request_id=disp.external_request_id)
    rep.results.append(ok("observe", "outcome_valid")
                       if isinstance(obs.business_outcome, ExecutionBusinessOutcome)
                       else fail("observe", "outcome_valid", "bad outcome type"))
    rep.results.append(ok("transport_split", "ack_not_outcome")
                       if hasattr(disp, "accepted") and hasattr(obs, "business_outcome")
                       else fail("transport_split", "ack_not_outcome", "split violated"))

    def call(pf):
        pf.initialize()
        d = pf.dispatch(req)
        return pf.observe(external_request_id=d.external_request_id)
    rep.results.append(deterministic_fingerprint(call, provider_factory))

    # cancellation supported
    p2 = provider_factory(); p2.initialize()
    d2 = p2.dispatch(req)
    rep.results.append(ok("cancel", "cancellable") if p2.cancel(external_request_id=d2.external_request_id)
                       else fail("cancel", "cancellable", "cancel returned False"))
    return rep
