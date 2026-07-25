"""Declarative provider configuration.

A neutral, in-memory configuration model (parseable from a mapping / YAML-like
structure). It carries provider identity, kind, enabled state, default
assignment, contract version, provider-specific config, and **secret references**
(never embedded secrets). Unknown or contradictory configuration is rejected.
This module implements no secret-management system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .errors import ProviderConfigurationError
from .metadata import ProviderKind

#: config-label → provider kind
_KIND_LABELS: dict[str, ProviderKind] = {
    "assertion": ProviderKind.ASSERTION_GOVERNANCE,
    "assertion_governance": ProviderKind.ASSERTION_GOVERNANCE,
    "action_governance": ProviderKind.ACTION_GOVERNANCE,
    "action": ProviderKind.ACTION_GOVERNANCE,
    "execution": ProviderKind.EXTERNAL_EXECUTION,
    "external_execution": ProviderKind.EXTERNAL_EXECUTION,
}


@dataclass(frozen=True)
class ProviderEntry:
    provider_id: str
    kind: ProviderKind
    implementation: str = "local"
    enabled: bool = True
    contract_version: str = "1.0.0"
    default: bool = False
    settings: Mapping[str, str] = field(default_factory=dict)
    secret_refs: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ProvidersConfiguration:
    entries: tuple[ProviderEntry, ...] = ()

    def by_kind(self, kind: ProviderKind) -> tuple[ProviderEntry, ...]:
        return tuple(e for e in self.entries if e.kind is kind and e.enabled)

    def default_for(self, kind: ProviderKind):
        defaults = [e for e in self.by_kind(kind) if e.default]
        return defaults[0].provider_id if defaults else None

    def validate(self) -> None:
        ids = [e.provider_id for e in self.entries]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ProviderConfigurationError(f"duplicate provider ids: {sorted(dupes)}")
        for kind in ProviderKind:
            enabled_defaults = [e for e in self.by_kind(kind) if e.default]
            if len(enabled_defaults) > 1:
                raise ProviderConfigurationError(
                    f"contradictory: {len(enabled_defaults)} enabled defaults for "
                    f"kind {kind.value}")
        # a default must itself be enabled
        for e in self.entries:
            if e.default and not e.enabled:
                raise ProviderConfigurationError(
                    f"provider '{e.provider_id}' is the default but disabled")

    @classmethod
    def from_mapping(cls, data: Mapping) -> "ProvidersConfiguration":
        providers = data.get("providers", {})
        if not isinstance(providers, Mapping):
            raise ProviderConfigurationError("'providers' must be a mapping")
        entries: list[ProviderEntry] = []
        for label, block in providers.items():
            kind = _KIND_LABELS.get(str(label).lower())
            if kind is None:
                raise ProviderConfigurationError(f"unknown provider kind label '{label}'")
            default_id = block.get("default") if isinstance(block, Mapping) else None
            for reg in (block.get("registered", []) if isinstance(block, Mapping) else []):
                pid = reg.get("id")
                if not pid:
                    raise ProviderConfigurationError(f"provider entry under '{label}' missing id")
                entries.append(ProviderEntry(
                    provider_id=pid, kind=kind,
                    implementation=reg.get("implementation", "local"),
                    enabled=bool(reg.get("enabled", True)),
                    contract_version=reg.get("contract_version", "1.0.0"),
                    default=(pid == default_id) or bool(reg.get("default", False)),
                    settings=dict(reg.get("settings", {})),
                    secret_refs=dict(reg.get("secret_refs", {}))))
        config = cls(tuple(entries))
        config.validate()
        return config
