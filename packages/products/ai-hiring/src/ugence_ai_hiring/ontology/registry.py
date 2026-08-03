"""Capability hierarchy graph and validation.

Pure, deterministic hierarchy logic over a set of capabilities: parent-existence,
cycle detection, ancestors/descendants, roots. Used by the ontology service and
the rubric validator. No evaluation occurs here.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..errors import CapabilityCycleError, CapabilityNotFoundError
from .capability import Capability


@dataclass(frozen=True)
class CapabilityGraph:
    """A read-only hierarchy view over capabilities (keyed by capability_id)."""

    capabilities: tuple[Capability, ...]

    def _by_id(self) -> dict[str, Capability]:
        return {c.capability_id: c for c in self.capabilities}

    def get(self, capability_id: str) -> Capability:
        cap = self._by_id().get(capability_id)
        if cap is None:
            raise CapabilityNotFoundError(f"capability '{capability_id}' not found")
        return cap

    def roots(self) -> tuple[Capability, ...]:
        return tuple(c for c in self.capabilities if c.parent_id is None)

    def children_of(self, capability_id: str) -> tuple[Capability, ...]:
        return tuple(c for c in self.capabilities if c.parent_id == capability_id)

    def ancestors(self, capability_id: str) -> tuple[str, ...]:
        by_id = self._by_id()
        chain: list[str] = []
        seen: set[str] = set()
        current = by_id.get(capability_id)
        while current is not None and current.parent_id is not None:
            parent_id = current.parent_id
            if parent_id in seen:
                raise CapabilityCycleError(f"cycle detected at '{parent_id}'")
            seen.add(parent_id)
            chain.append(parent_id)
            current = by_id.get(parent_id)
        return tuple(chain)

    def descendants(self, capability_id: str) -> tuple[str, ...]:
        out: list[str] = []
        stack = [c.capability_id for c in self.children_of(capability_id)]
        seen: set[str] = set()
        while stack:
            cid = stack.pop()
            if cid in seen:
                continue
            seen.add(cid)
            out.append(cid)
            stack.extend(c.capability_id for c in self.children_of(cid))
        return tuple(out)

    def validate(self) -> None:
        """Raise if any parent is missing or the hierarchy contains a cycle."""
        by_id = self._by_id()
        for cap in self.capabilities:
            if cap.parent_id is not None and cap.parent_id not in by_id:
                raise CapabilityNotFoundError(
                    f"capability '{cap.capability_id}' references missing parent "
                    f"'{cap.parent_id}'")
        # cycle detection via ancestor walk (raises on cycle)
        for cap in self.capabilities:
            self.ancestors(cap.capability_id)


def build_graph(capabilities: tuple[Capability, ...]) -> CapabilityGraph:
    return CapabilityGraph(capabilities=capabilities)
