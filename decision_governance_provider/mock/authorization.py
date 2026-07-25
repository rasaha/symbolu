"""Deterministic mock AuthorizationProvider — validates the framework."""
from __future__ import annotations

from ..contracts import (
    AuthorizationContext,
    AuthorizationOutcome,
    AuthorizationVerdict,
    BaseProvider,
)
from ..metadata import ProviderCapabilities, ProviderKind, ProviderMetadata


class MockAuthorizationProvider(BaseProvider):
    """AUTHORIZED by default; configurable denied/constrained action types.

    Rules (in order): expired CER → EXPIRED; denied set → DENIED; constrained
    set → AUTHORIZED_WITH_CONSTRAINTS; otherwise AUTHORIZED.
    """

    def __init__(self, *, name: str = "mock-authorization",
                 denied: frozenset[str] = frozenset(),
                 constrained: frozenset[str] = frozenset(),
                 constraints: tuple[str, ...] = ("rate_limited",),
                 obligations: tuple[str, ...] = ("log_to_audit",)) -> None:
        super().__init__(
            ProviderMetadata(name=name, version="0.1.0", kind=ProviderKind.AUTHORIZATION,
                             kernel_port_version="1.0.0", description="deterministic mock",
                             vendor="framework-tests"),
            ProviderCapabilities(kind=ProviderKind.AUTHORIZATION,
                                 features=frozenset({"constraints", "obligations"}),
                                 deterministic=True))
        self._denied, self._constrained = denied, constrained
        self._constraints, self._obligations = constraints, obligations

    def authorize(self, context: AuthorizationContext) -> AuthorizationVerdict:
        if context.cer_expired:
            return AuthorizationVerdict(AuthorizationOutcome.EXPIRED)
        if context.action_type in self._denied:
            return AuthorizationVerdict(AuthorizationOutcome.DENIED, reason="denied action type")
        if context.action_type in self._constrained:
            return AuthorizationVerdict(
                AuthorizationOutcome.AUTHORIZED_WITH_CONSTRAINTS,
                constraints=self._constraints, obligations=self._obligations)
        return AuthorizationVerdict(AuthorizationOutcome.AUTHORIZED, obligations=self._obligations)
