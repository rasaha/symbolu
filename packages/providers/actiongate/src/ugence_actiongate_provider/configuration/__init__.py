"""ActionGate provider configuration + factory (mode: in_process | remote)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional

from ugence_governance_provider_framework.api import ProviderConfigurationError

from ..client import InProcessActionGateClient, RemoteActionGateClient
from ..core import ActionGateEngine
from ..observability import ActionGateInvocationLog
from ..provider import ActionGateProvider

_SUPPORTED_MODES = frozenset({"in_process", "remote"})


@dataclass(frozen=True)
class ActionGateSettings:
    provider_id: str = "actiongate"
    mode: str = "in_process"
    default: bool = True
    contract_version: str = "1.0.0"
    endpoint: str = "actiongate://in-memory"
    # secret *references* only — never embedded secrets
    secret_refs: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if self.mode not in _SUPPORTED_MODES:
            raise ProviderConfigurationError(
                f"unsupported ActionGate mode '{self.mode}' (allowed: {sorted(_SUPPORTED_MODES)})")
        if self.contract_version.split(".")[0] != "1":
            raise ProviderConfigurationError(
                f"unsupported contract_version '{self.contract_version}'")

    @classmethod
    def from_settings(cls, settings: Mapping[str, str], *, provider_id: str = "actiongate",
                      default: bool = True) -> "ActionGateSettings":
        s = cls(provider_id=provider_id,
                mode=str(settings.get("mode", "in_process")),
                default=default,
                contract_version=str(settings.get("contract_version", "1.0.0")),
                endpoint=str(settings.get("endpoint", "actiongate://in-memory")),
                secret_refs=dict(settings.get("secret_refs", {})))
        s.validate()
        return s


def build_actiongate_provider(engine: Optional[ActionGateEngine] = None, *,
                              settings: Optional[ActionGateSettings] = None,
                              invocation_log: Optional[ActionGateInvocationLog] = None,
                              transport_fail: Optional[str] = None) -> ActionGateProvider:
    """Construct an ActionGateProvider from settings + an engine."""
    settings = settings or ActionGateSettings()
    settings.validate()
    engine = engine or ActionGateEngine()
    if settings.mode == "remote":
        client = RemoteActionGateClient(engine, transport_fail=transport_fail,
                                        endpoint=settings.endpoint)
    else:
        client = InProcessActionGateClient(engine)
    return ActionGateProvider(client, provider_id=settings.provider_id,
                              default=settings.default, invocation_log=invocation_log)


__all__ = ["ActionGateSettings", "build_actiongate_provider"]
