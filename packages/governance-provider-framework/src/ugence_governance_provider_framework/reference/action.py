"""Deterministic reference Action Governance provider (framework validation only).

NOT ActionGate. Configurable authorize outcomes for tests.
"""

from __future__ import annotations

from ..contracts import (
    ActionGovernanceOutcome,
    ActionGovernanceRequest,
    ActionGovernanceResult,
)
from ..contracts.base import BaseProvider
from ..errors import ProviderUnavailableError
from ..fingerprint import fingerprint
from ..metadata import (
    ProviderCapabilities,
    ProviderCompatibility,
    ProviderDescriptor,
    ProviderKind,
)

_KIND = ProviderKind.ACTION_GOVERNANCE


class DeterministicActionGovernanceProvider(BaseProvider):
    def __init__(self, *, provider_id: str = "deterministic-action",
                 denied: frozenset[str] = frozenset(),
                 constrained: frozenset[str] = frozenset(),
                 indeterminate: frozenset[str] = frozenset(),
                 unavailable: bool = False, default: bool = True,
                 constraints: tuple[str, ...] = ("rate_limited",),
                 obligations: tuple[str, ...] = ("log_to_audit",)) -> None:
        descriptor = ProviderDescriptor(
            provider_id=provider_id, kind=_KIND, implementation_version="0.1.0",
            compatibility=ProviderCompatibility(contract_version="1.0.0"),
            capabilities=ProviderCapabilities(
                kind=_KIND, features=frozenset({"authorize", "constraints", "obligations"}),
                deterministic=True),
            factory=lambda: DeterministicActionGovernanceProvider(
                provider_id=provider_id, denied=denied, constrained=constrained,
                indeterminate=indeterminate, unavailable=unavailable, default=default,
                constraints=constraints, obligations=obligations),
            vendor="framework-reference", default=default)
        super().__init__(descriptor)
        self._denied, self._constrained, self._indeterminate = denied, constrained, indeterminate
        self._unavailable = unavailable
        self._constraints, self._obligations = constraints, obligations

    def authorize(self, request: ActionGovernanceRequest) -> ActionGovernanceResult:
        if self._unavailable:
            raise ProviderUnavailableError(f"provider '{self.descriptor().provider_id}' unavailable")
        outcome, constraints, obligations = self._classify(request)
        fp = fingerprint({"action_type": request.action_type,
                          "parameters": dict(request.requested_parameters),
                          "outcome": outcome.value})
        return ActionGovernanceResult(
            outcome=outcome, constraints=constraints, obligations=obligations,
            authority_basis=request.authority_context,
            reason_codes=(outcome.value,),
            provider_trace_id=f"trace-{fp[:12]}", fingerprint=fp)

    def _classify(self, request: ActionGovernanceRequest):
        if request.authorization_expired:
            return ActionGovernanceOutcome.EXPIRED, (), ()
        at = request.action_type
        if at in self._denied:
            return ActionGovernanceOutcome.DENIED, (), ()
        if at in self._indeterminate:
            return ActionGovernanceOutcome.INDETERMINATE, (), ()
        if at in self._constrained:
            return (ActionGovernanceOutcome.AUTHORIZED_WITH_CONSTRAINTS,
                    self._constraints, self._obligations)
        return ActionGovernanceOutcome.AUTHORIZED, (), self._obligations
