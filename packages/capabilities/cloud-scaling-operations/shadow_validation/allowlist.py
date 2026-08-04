"""Immutable target allowlist.

A resource may be observed only after it matches every configured dimension: cluster,
namespace, kind, and name (exact or a restricted ``prefix*`` pattern), within a bounded
target count. Discovery never implies authorization — a resource is rejected unless it is
explicitly allowlisted. Secret- and credential-bearing kinds are always rejected.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

# Kinds that must never be observed by the shadow harness.
_FORBIDDEN_KINDS = frozenset({
    "secret", "serviceaccount", "configmap",  # configmaps may carry credentials
})
_WILDCARDS = ("*", "all", "any", "")


@dataclass(frozen=True)
class TargetRef:
    cluster_identifier: str
    namespace: str
    resource_kind: str
    resource_name: str

    def key(self) -> str:
        return f"{self.cluster_identifier}/{self.namespace}/{self.resource_kind}/{self.resource_name}"


@dataclass(frozen=True)
class AllowlistDecision:
    target: TargetRef
    allowed: bool
    reason: str


@dataclass(frozen=True)
class TargetAllowlist:
    cluster_identifier: str
    namespaces: Tuple[str, ...]
    resource_kinds: Tuple[str, ...]
    resource_name_patterns: Tuple[str, ...]
    maximum_target_count: int

    def _name_matches(self, name: str) -> bool:
        for pat in self.resource_name_patterns:
            if pat.endswith("*"):
                if name.startswith(pat[:-1]) and pat[:-1] != "":
                    return True
            elif name == pat:
                return True
        return False

    def evaluate(self, target: TargetRef) -> AllowlistDecision:
        def deny(reason: str) -> AllowlistDecision:
            return AllowlistDecision(target, False, reason)

        if not self.cluster_identifier or self.cluster_identifier in _WILDCARDS:
            return deny("allowlist cluster is empty/wildcard")
        if target.cluster_identifier != self.cluster_identifier:
            return deny(f"cluster {target.cluster_identifier!r} not allowlisted")
        if not target.namespace or target.namespace in _WILDCARDS:
            return deny("empty/wildcard namespace")
        if target.namespace not in self.namespaces:
            return deny(f"namespace {target.namespace!r} not allowlisted")
        if target.resource_kind.lower() in _FORBIDDEN_KINDS:
            return deny(f"kind {target.resource_kind!r} is credential-bearing/forbidden")
        if target.resource_kind not in self.resource_kinds:
            return deny(f"kind {target.resource_kind!r} not allowlisted")
        if not target.resource_name or target.resource_name in _WILDCARDS:
            return deny("empty/wildcard/ambiguous resource name")
        if not self._name_matches(target.resource_name):
            return deny(f"resource {target.resource_name!r} not allowlisted")
        return AllowlistDecision(target, True, "allowlisted")

    def filter(self, targets: List[TargetRef]) -> Tuple[List[AllowlistDecision],
                                                        List[AllowlistDecision]]:
        """Return (approved, rejected). Enforces the target-count cap (fail closed)."""
        approved: List[AllowlistDecision] = []
        rejected: List[AllowlistDecision] = []
        for t in targets:
            d = self.evaluate(t)
            if d.allowed and len(approved) >= self.maximum_target_count:
                rejected.append(AllowlistDecision(t, False, "exceeds maximum_target_count"))
            elif d.allowed:
                approved.append(d)
            else:
                rejected.append(d)
        return approved, rejected

    @classmethod
    def from_config(cls, config) -> "TargetAllowlist":
        return cls(
            cluster_identifier=config.cluster_identifier,
            namespaces=tuple(config.namespace_allowlist),
            resource_kinds=tuple(config.resource_kind_allowlist),
            resource_name_patterns=tuple(config.resource_name_allowlist),
            maximum_target_count=config.maximum_target_count,
        )


__all__ = ["TargetRef", "AllowlistDecision", "TargetAllowlist"]
