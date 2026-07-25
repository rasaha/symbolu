"""Provider registry — explicit registration, discovery, lifecycle, validation.

The registry never dynamically scans arbitrary modules: providers are registered
explicitly (by composition) or via configuration-driven factories. It validates
descriptors, kind support, contract- and kernel-version compatibility, and
default uniqueness.
"""

from __future__ import annotations

from typing import Optional

from ..contracts import Provider
from ..errors import (
    ProviderCompatibilityError,
    ProviderRegistrationError,
    ProviderResolutionError,
)
from ..metadata import ProviderDescriptor, ProviderHealth, ProviderKind
from ..version import is_contract_compatible, is_kernel_compatible, TARGET_KERNEL_MAJOR


class ProviderRegistry:
    """An in-memory registry of provider descriptors + their live instances."""

    def __init__(self) -> None:
        self._descriptors: dict[str, ProviderDescriptor] = {}
        self._instances: dict[str, Provider] = {}

    # --- registration ------------------------------------------------------

    def register(self, descriptor: ProviderDescriptor) -> ProviderDescriptor:
        self._validate_descriptor(descriptor)
        if descriptor.provider_id in self._descriptors:
            raise ProviderRegistrationError(
                f"duplicate provider id '{descriptor.provider_id}'")
        # ambiguous default guard
        if descriptor.default:
            existing_default = [d for d in self.list_by_kind(descriptor.kind) if d.default]
            if existing_default:
                raise ProviderRegistrationError(
                    f"kind {descriptor.kind.value} already has a default provider "
                    f"'{existing_default[0].provider_id}'")
        self._descriptors[descriptor.provider_id] = descriptor
        return descriptor

    def deregister(self, provider_id: str) -> None:
        if provider_id not in self._descriptors:
            raise ProviderResolutionError(f"no provider '{provider_id}'")
        inst = self._instances.pop(provider_id, None)
        if inst is not None:
            inst.shutdown()
        del self._descriptors[provider_id]

    def _validate_descriptor(self, d: ProviderDescriptor) -> None:
        if not d.provider_id.strip():
            raise ProviderRegistrationError("provider id is required")
        if not callable(d.factory):
            raise ProviderRegistrationError(f"provider '{d.provider_id}' factory not callable")
        if d.kind not in ProviderKind:
            raise ProviderRegistrationError(f"unsupported provider kind {d.kind!r}")
        if d.kind is not d.capabilities.kind:
            raise ProviderRegistrationError(
                f"provider '{d.provider_id}' descriptor kind != capabilities kind")
        if not is_contract_compatible(d.contract_version):
            raise ProviderCompatibilityError(
                f"provider '{d.provider_id}' contract {d.contract_version} incompatible")
        if str(TARGET_KERNEL_MAJOR) not in d.compatibility.compatible_kernel_majors:
            raise ProviderCompatibilityError(
                f"provider '{d.provider_id}' does not support kernel major "
                f"{TARGET_KERNEL_MAJOR}")

    # --- discovery ---------------------------------------------------------

    def get_descriptor(self, provider_id: str) -> ProviderDescriptor:
        try:
            return self._descriptors[provider_id]
        except KeyError:
            raise ProviderResolutionError(f"no provider '{provider_id}'") from None

    def list_by_kind(self, kind: Optional[ProviderKind] = None
                     ) -> tuple[ProviderDescriptor, ...]:
        items = self._descriptors.values()
        if kind is not None:
            items = [d for d in items if d.kind is kind]
        return tuple(items)

    def find_by_capability(self, kind: ProviderKind, feature: str
                           ) -> tuple[ProviderDescriptor, ...]:
        return tuple(d for d in self.list_by_kind(kind)
                     if d.capabilities.supports_feature(feature))

    def is_compatible(self, descriptor: ProviderDescriptor) -> bool:
        return (is_contract_compatible(descriptor.contract_version)
                and str(TARGET_KERNEL_MAJOR) in descriptor.compatibility.compatible_kernel_majors)

    # --- lifecycle ---------------------------------------------------------

    def get_provider(self, provider_id: str) -> Provider:
        if provider_id not in self._instances:
            descriptor = self.get_descriptor(provider_id)
            instance = descriptor.factory()
            instance.initialize()
            self._instances[provider_id] = instance
        return self._instances[provider_id]

    def health(self, provider_id: str) -> ProviderHealth:
        return self.get_provider(provider_id).health()

    def shutdown_all(self) -> None:
        for inst in self._instances.values():
            inst.shutdown()
        self._instances.clear()

    def validate(self) -> None:
        for d in self._descriptors.values():
            self._validate_descriptor(d)
        for kind in ProviderKind:
            if len([d for d in self.list_by_kind(kind) if d.default]) > 1:
                raise ProviderRegistrationError(
                    f"multiple default providers for kind {kind.value}")

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(self._descriptors)
