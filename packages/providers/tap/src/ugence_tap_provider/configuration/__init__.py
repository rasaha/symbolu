"""TAP provider configuration + factory (mode: in_process | remote).

Rejects duplicate/contradictory/unsupported configuration. Carries **secret
references only** — never embedded secrets — and implements no secret-management
system.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional

from ugence_governance_provider_framework.api import ProviderConfigurationError

from ..client import InProcessTapClient, RemoteTapClient
from ..core import TapEngine
from ..observability import TapInvocationLog
from ..provider import TAPProvider

_SUPPORTED_MODES = frozenset({"in_process", "remote"})
_SUPPORTED_EVIDENCE_RESOLUTION = frozenset({
    "caller_supplied", "provider_client", "external_resolver"})


@dataclass(frozen=True)
class TapSettings:
    provider_id: str = "tap"
    mode: str = "in_process"
    default: bool = True
    contract_version: str = "1.0.0"
    endpoint: str = "tap://in-memory"
    policy_bundle: str = "default"
    evidence_resolution: str = "caller_supplied"
    fail_safe: bool = True
    # secret *references* only — never embedded secrets
    secret_refs: Mapping[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if self.mode not in _SUPPORTED_MODES:
            raise ProviderConfigurationError(
                f"unsupported TAP mode '{self.mode}' (allowed: {sorted(_SUPPORTED_MODES)})")
        if self.contract_version.split(".")[0] != "1":
            raise ProviderConfigurationError(
                f"unsupported contract_version '{self.contract_version}'")
        if self.evidence_resolution not in _SUPPORTED_EVIDENCE_RESOLUTION:
            raise ProviderConfigurationError(
                f"unsupported evidence_resolution '{self.evidence_resolution}' "
                f"(allowed: {sorted(_SUPPORTED_EVIDENCE_RESOLUTION)})")
        for k, v in self.secret_refs.items():
            if not isinstance(v, str) or not v.startswith("ref:"):
                raise ProviderConfigurationError(
                    f"secret '{k}' must be a reference (got a non-'ref:' value)")

    @classmethod
    def from_settings(cls, settings: Mapping[str, object], *, provider_id: str = "tap",
                      default: bool = True) -> "TapSettings":
        s = cls(provider_id=provider_id,
                mode=str(settings.get("mode", "in_process")),
                default=default,
                contract_version=str(settings.get("contract_version", "1.0.0")),
                endpoint=str(settings.get("endpoint", "tap://in-memory")),
                policy_bundle=str(settings.get("policy_bundle", "default")),
                evidence_resolution=str(settings.get("evidence_resolution", "caller_supplied")),
                fail_safe=bool(settings.get("fail_safe", True)),
                secret_refs=dict(settings.get("secret_refs", {})))
        s.validate()
        return s


def build_tap_provider(engine: Optional[TapEngine] = None, *,
                       settings: Optional[TapSettings] = None,
                       invocation_log: Optional[TapInvocationLog] = None,
                       transport_fail: Optional[str] = None) -> TAPProvider:
    """Construct a TAPProvider from settings + an engine."""
    settings = settings or TapSettings()
    settings.validate()
    engine = engine or TapEngine()
    if settings.mode == "remote":
        client = RemoteTapClient(engine, transport_fail=transport_fail,
                                 endpoint=settings.endpoint)
    else:
        client = InProcessTapClient(engine)
    return TAPProvider(client, provider_id=settings.provider_id, default=settings.default,
                       fail_safe=settings.fail_safe,
                       evidence_resolution=settings.evidence_resolution,
                       invocation_log=invocation_log)


__all__ = ["TapSettings", "build_tap_provider"]
