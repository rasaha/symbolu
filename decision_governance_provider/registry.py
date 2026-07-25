"""Provider registry — registration, discovery, capability lookup, lifecycle.

The registry is the single owner of the set of available governance providers.
Applications register descriptors (by configuration/composition), then discover
and resolve providers by kind or capability. The **kernel never imports this
registry** — provider infrastructure lives strictly above the kernel.
"""

from __future__ import annotations

from typing import Optional

from .contracts import Provider
from .descriptor import ProviderDescriptor
from .errors import (
    IncompatibleProviderVersionError,
    ProviderConflictError,
    ProviderError,
    ProviderNotFoundError,
)
from .metadata import ProviderKind
from .version import is_kernel_compatible


class ProviderRegistry:
    """An in-memory registry of provider descriptors + their live instances."""

    def __init__(self) -> None:
        self._descriptors: dict[str, ProviderDescriptor] = {}
        self._instances: dict[str, Provider] = {}

    # --- registration ------------------------------------------------------

    def register(self, descriptor: ProviderDescriptor) -> ProviderDescriptor:
        """Register a provider descriptor after validating it."""
        self._validate(descriptor)
        if descriptor.name in self._descriptors:
            raise ProviderConflictError(
                f"a provider named '{descriptor.name}' is already registered")
        self._descriptors[descriptor.name] = descriptor
        return descriptor

    def unregister(self, name: str) -> None:
        if name not in self._descriptors:
            raise ProviderNotFoundError(f"no provider named '{name}'")
        # stop a live instance first
        inst = self._instances.pop(name, None)
        if inst is not None:
            inst.stop()
        del self._descriptors[name]

    def _validate(self, descriptor: ProviderDescriptor) -> None:
        if descriptor.metadata.kind is not descriptor.capabilities.kind:
            raise ProviderError(
                f"provider '{descriptor.name}' metadata kind "
                f"{descriptor.metadata.kind.value} != capabilities kind "
                f"{descriptor.capabilities.kind.value}")
        if not is_kernel_compatible(descriptor.metadata.kernel_port_version):
            raise IncompatibleProviderVersionError(
                f"provider '{descriptor.name}' targets kernel "
                f"{descriptor.metadata.kernel_port_version}, incompatible with this "
                "framework's supported kernel major")

    # --- discovery ---------------------------------------------------------

    def get_descriptor(self, name: str) -> ProviderDescriptor:
        try:
            return self._descriptors[name]
        except KeyError:
            raise ProviderNotFoundError(f"no provider named '{name}'") from None

    def list_descriptors(self, kind: Optional[ProviderKind] = None
                         ) -> tuple[ProviderDescriptor, ...]:
        items = self._descriptors.values()
        if kind is not None:
            items = [d for d in items if d.kind is kind]
        return tuple(items)

    def find_by_capability(self, kind: ProviderKind, feature: str
                           ) -> tuple[ProviderDescriptor, ...]:
        return tuple(
            d for d in self._descriptors.values()
            if d.kind is kind and d.capabilities.supports_feature(feature))

    def default_for(self, kind: ProviderKind) -> ProviderDescriptor:
        """The default provider for a kind: the one marked default, else the sole one."""
        candidates = self.list_descriptors(kind)
        if not candidates:
            raise ProviderNotFoundError(f"no provider registered for kind {kind.value}")
        marked = [d for d in candidates if d.default]
        if len(marked) > 1:
            raise ProviderError(
                f"multiple default providers for kind {kind.value}: "
                f"{[d.name for d in marked]}")
        if marked:
            return marked[0]
        if len(candidates) == 1:
            return candidates[0]
        raise ProviderNotFoundError(
            f"no default provider for kind {kind.value}; specify one by name")

    # --- lifecycle ---------------------------------------------------------

    def get_provider(self, name: str) -> Provider:
        """Instantiate (once), start, and return the provider for a name."""
        if name not in self._instances:
            descriptor = self.get_descriptor(name)
            instance = descriptor.factory()
            instance.start()
            self._instances[name] = instance
        return self._instances[name]

    def start_all(self) -> None:
        for name in self._descriptors:
            self.get_provider(name)

    def stop_all(self) -> None:
        for inst in self._instances.values():
            inst.stop()
        self._instances.clear()

    def validate(self) -> None:
        """Re-validate every registered descriptor and default uniqueness."""
        for descriptor in self._descriptors.values():
            self._validate(descriptor)
        for kind in ProviderKind:
            marked = [d for d in self.list_descriptors(kind) if d.default]
            if len(marked) > 1:
                raise ProviderError(
                    f"multiple default providers for kind {kind.value}")

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._descriptors)
