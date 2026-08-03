"""Planning-time failure-domain representation.

Derived ONLY from P1 profile fields (or an explicit composition overlay). Model
values are preserved as **references** already present in the profile — never by
invoking Model Selection. Used for team failure-domain diversity and fallback
diversity; never for runtime behaviour.
"""
from __future__ import annotations

from typing import Tuple

from .agents import AgentProfile
from .canonical import AwcModel
from .composition_contracts import FailureDomainKind


class FailureDomain(AwcModel):
    kind: FailureDomainKind
    value: str


class FailureDomainSet(AwcModel):
    agent_id: str
    agent_version: str
    domains: Tuple[FailureDomain, ...] = ()

    def values_by_kind(self, kind: FailureDomainKind) -> Tuple[str, ...]:
        return tuple(d.value for d in self.domains if d.kind is kind)

    def values_by_kind_provider(self) -> Tuple[str, ...]:
        return self.values_by_kind(FailureDomainKind.PROVIDER)

    def keys(self) -> frozenset:
        return frozenset((d.kind.value, d.value) for d in self.domains)


def build_failure_domain_set(profile: AgentProfile) -> FailureDomainSet:
    domains = []
    if profile.provider_id:
        domains.append(FailureDomain(kind=FailureDomainKind.PROVIDER, value=profile.provider_id))
    if profile.deployment_environment:
        domains.append(FailureDomain(kind=FailureDomainKind.CLOUD_ENVIRONMENT,
                                     value=profile.deployment_environment))
    if profile.residency:
        domains.append(FailureDomain(kind=FailureDomainKind.DEPLOYMENT_REGION,
                                     value=profile.residency))
    if profile.agent_type:
        domains.append(FailureDomain(kind=FailureDomainKind.RUNTIME_IMPLEMENTATION,
                                     value=profile.agent_type))
    for ref in profile.model_requirement_refs:  # reference-only, no Model Selection call
        domains.append(FailureDomain(kind=FailureDomainKind.MODEL_FAMILY_REF, value=ref))
    domains.sort(key=lambda d: (d.kind.value, d.value))
    return FailureDomainSet(agent_id=profile.agent_id, agent_version=profile.agent_version,
                            domains=tuple(domains))


__all__ = ["FailureDomain", "FailureDomainSet", "build_failure_domain_set"]
