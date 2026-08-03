"""ActionGate health checks — availability, configuration, compatibility, policy."""
from __future__ import annotations

from dataclasses import dataclass

from ugence_governance_provider_framework.api import ProviderHealth

from ..configuration import ActionGateSettings
from ..provider import ActionGateProvider
from ..version import TARGET_KERNEL_VERSION


@dataclass(frozen=True)
class ActionGateHealthReport:
    available: bool
    configuration_valid: bool
    protocol_compatible: bool
    policy_available: bool
    provider_health: ProviderHealth

    @property
    def healthy(self) -> bool:
        return (self.available and self.configuration_valid
                and self.protocol_compatible and self.policy_available)


def check(provider: ActionGateProvider, settings: ActionGateSettings) -> ActionGateHealthReport:
    ph = provider.health()
    try:
        settings.validate()
        config_ok = True
    except Exception:  # noqa: BLE001
        config_ok = False
    d = provider.descriptor()
    protocol_ok = (str(TARGET_KERNEL_VERSION.split(".")[0])
                   in d.compatibility.compatible_kernel_majors)
    return ActionGateHealthReport(
        available=ph.healthy, configuration_valid=config_ok,
        protocol_compatible=protocol_ok, policy_available=ph.healthy,
        provider_health=ph)


__all__ = ["ActionGateHealthReport", "check"]
