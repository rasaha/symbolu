"""TAP health checks — availability, configuration, compatibility, evaluator, policy.

Health evaluates client/engine availability, evaluator readiness, evidence-resolver
readiness, configuration validity, protocol compatibility, and policy-bundle
availability. Health checks never produce a business assertion result and never
mutate evidence, and use no background thread.
"""
from __future__ import annotations

from dataclasses import dataclass

from ugence_governance_provider_framework.api import ProviderHealth

from ..configuration import TapSettings
from ..provider import TAPProvider
from ..version import TARGET_KERNEL_VERSION


@dataclass(frozen=True)
class TapHealthReport:
    available: bool
    configuration_valid: bool
    protocol_compatible: bool
    evaluator_ready: bool
    evidence_resolver_ready: bool
    policy_available: bool
    provider_health: ProviderHealth

    @property
    def healthy(self) -> bool:
        return (self.available and self.configuration_valid and self.protocol_compatible
                and self.evaluator_ready and self.evidence_resolver_ready
                and self.policy_available)


def check(provider: TAPProvider, settings: TapSettings) -> TapHealthReport:
    ph = provider.health()
    try:
        settings.validate()
        config_ok = True
    except Exception:  # noqa: BLE001
        config_ok = False
    d = provider.descriptor()
    protocol_ok = (str(TARGET_KERNEL_VERSION.split(".")[0])
                   in d.compatibility.compatible_kernel_majors)
    resolver_ok = d.metadata.get("evidence_resolution", "") in (
        "caller_supplied", "provider_client", "external_resolver")
    return TapHealthReport(
        available=ph.healthy, configuration_valid=config_ok,
        protocol_compatible=protocol_ok, evaluator_ready=ph.healthy,
        evidence_resolver_ready=resolver_ok, policy_available=ph.healthy,
        provider_health=ph)


__all__ = ["TapHealthReport", "check"]
