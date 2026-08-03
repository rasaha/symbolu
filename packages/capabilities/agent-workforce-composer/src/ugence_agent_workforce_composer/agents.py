"""Immutable planning-time agent objects and the frozen registry snapshot.

These objects are *planning inputs*, not a live registry. There is no ambient
lookup, no network, no provider call. Logical time is injected. A profile
distinguishes **identity**, **capability claims** (declared), and **measured /
observed evidence** — a declared claim is never treated as measured evidence.

Semantic differences vs the H16 runtime ``AgentProfile``
(``agentic/agentic_framework/coordination.py``) are documented in
``docs/H16_CANONICALIZATION_STATUS.md``: H16's profile is a flat runtime
*authority envelope* (string sets, no evidence, no provenance, no version, no
digest); this profile is an evidence-backed, content-addressed *selection
manifest*. They are deliberately distinct types in distinct namespaces.
"""
from __future__ import annotations

from typing import List, Optional, Tuple, Union

from pydantic import model_validator

from .canonical import AwcModel, digest, to_canonical_obj
from .contracts import EVIDENCE_PRECEDENCE, EvidenceClass
from .fingerprint import stamp_fingerprint
from .version import CONTRACT_VERSION
from .workflow import Provenance
from enum import Enum


class AgentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    REVOKED = "REVOKED"


class AgentCapability(AwcModel):
    """A capability a profile *claims*. Declared claims are audited, never trusted
    as measured evidence."""

    capability_id: str
    capability_version: str = ""
    category: str = ""
    description: str = ""
    declared: bool = True


class AgentCapabilityEvidence(AwcModel):
    """A single, immutable evidence item backing a capability claim.

    ``evidence_class`` is DECLARED / MEASURED / OBSERVED. Synthetic fixtures MUST
    set ``provenance.synthetic = True`` — evidence is never fabricated as real.
    """

    contract_version: str = CONTRACT_VERSION
    evidence_id: str
    agent_id: str
    agent_version: str
    capability_id: str
    evidence_class: EvidenceClass
    measurement_type: str = ""
    value: Union[float, int, str, bool, None] = None
    unit: str = ""
    threshold_context: str = ""
    benchmark_id: str = ""
    benchmark_version: str = ""
    dataset_ref: str = ""
    environment_ref: str = ""
    sample_size: int = 0
    measured_at: float = 0.0
    valid_until: Optional[float] = None
    issuer: str = ""
    signature_or_digest: str = ""
    provenance: Provenance
    evidence_fingerprint: str = ""

    def is_expired(self, now: float) -> bool:
        """True iff a validity horizon is set and ``now`` is past it."""
        return self.valid_until is not None and now > self.valid_until

    def precedence(self) -> int:
        return EVIDENCE_PRECEDENCE[self.evidence_class]


class CapabilityEvidenceSet(AwcModel):
    """An immutable set of evidence items with deterministic resolution."""

    items: Tuple[AgentCapabilityEvidence, ...] = ()

    def for_capability(
        self, agent_id: str, agent_version: str, capability_id: str
    ) -> Tuple[AgentCapabilityEvidence, ...]:
        return tuple(
            e for e in self.items
            if e.agent_id == agent_id
            and e.agent_version == agent_version
            and e.capability_id == capability_id
        )

    def best_class(
        self, agent_id: str, agent_version: str, capability_id: str, now: float
    ) -> Optional[EvidenceClass]:
        """Highest-precedence *non-expired* evidence class for a capability, or None."""
        best: Optional[EvidenceClass] = None
        best_rank = -1
        for e in self.for_capability(agent_id, agent_version, capability_id):
            if e.is_expired(now):
                continue
            if e.precedence() > best_rank:
                best_rank = e.precedence()
                best = e.evidence_class
        return best


class AgentProfile(AwcModel):
    """Immutable planning-time agent capability profile."""

    contract_version: str = CONTRACT_VERSION
    agent_id: str
    agent_version: str
    provider_id: str
    agent_type: str = ""
    status: AgentStatus = AgentStatus.ACTIVE
    declared_capabilities: Tuple[AgentCapability, ...] = ()
    measured_capabilities: Tuple[str, ...] = ()
    observed_capabilities: Tuple[str, ...] = ()
    supported_domains: Tuple[str, ...] = ()
    supported_tools: Tuple[str, ...] = ()
    input_contracts: Tuple[str, ...] = ()
    output_contracts: Tuple[str, ...] = ()
    model_requirement_refs: Tuple[str, ...] = ()
    requested_permissions: Tuple[str, ...] = ()
    maximum_authority_scope: int = 0
    data_access_requirements: Tuple[str, ...] = ()
    supported_data_classifications: Tuple[str, ...] = ()
    residency: str = ""
    deployment_environment: str = ""
    security_classification: int = 0
    latency_evidence: Optional[float] = None
    cost_evidence: Optional[float] = None
    quality_evidence: Optional[float] = None
    reliability_evidence: Optional[float] = None
    benchmark_refs: Tuple[str, ...] = ()
    failure_mode_refs: Tuple[str, ...] = ()
    audit_capabilities: Tuple[str, ...] = ()
    state_model: str = ""
    concurrency_constraints: int = 0
    valid_from: float = 0.0
    valid_until: Optional[float] = None
    evidence_refs: Tuple[str, ...] = ()
    policy_refs: Tuple[str, ...] = ()
    provenance: Provenance
    profile_fingerprint: str = ""

    @property
    def identity(self) -> Tuple[str, str]:
        return (self.agent_id, self.agent_version)

    def is_expired(self, now: float) -> bool:
        return self.valid_until is not None and now > self.valid_until

    def declared_capability_ids(self) -> Tuple[str, ...]:
        return tuple(c.capability_id for c in self.declared_capabilities)


class AgentRegistrySnapshot(AwcModel):
    """A frozen, content-addressed registry snapshot — a pure planning input.

    Integrity is enforced at construction: no duplicate agent identity, no
    duplicate evidence id, and every evidence item resolves to a profile in the
    snapshot. Profiles and evidence are stored in canonical (id-sorted) order, so
    the digest is independent of input container ordering (invariant I6).
    """

    contract_version: str = CONTRACT_VERSION
    snapshot_id: str
    registry_version: str
    logical_time: float = 0.0
    agent_profiles: Tuple[AgentProfile, ...] = ()
    capability_evidence: Tuple[AgentCapabilityEvidence, ...] = ()
    source_refs: Tuple[str, ...] = ()
    policy_refs: Tuple[str, ...] = ()
    provenance: Provenance
    snapshot_digest: str = ""

    @model_validator(mode="after")
    def _check_integrity(self) -> "AgentRegistrySnapshot":
        ids = [p.identity for p in self.agent_profiles]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate agent identity (agent_id, agent_version) in snapshot")
        ev_ids = [e.evidence_id for e in self.capability_evidence]
        if len(ev_ids) != len(set(ev_ids)):
            raise ValueError("duplicate evidence_id in snapshot")
        known = set(ids)
        for e in self.capability_evidence:
            if (e.agent_id, e.agent_version) not in known:
                raise ValueError(
                    f"evidence {e.evidence_id!r} references unknown agent "
                    f"{(e.agent_id, e.agent_version)!r}")
        return self

    def evidence_set(self) -> CapabilityEvidenceSet:
        return CapabilityEvidenceSet(items=self.capability_evidence)

    def profile(self, agent_id: str, agent_version: str) -> Optional[AgentProfile]:
        for p in self.agent_profiles:
            if p.identity == (agent_id, agent_version):
                return p
        return None

    def logical_digest(self) -> str:
        """Order-independent content digest (excludes the stored digest field)."""
        payload = {
            "snapshot_id": self.snapshot_id,
            "registry_version": self.registry_version,
            "logical_time": self.logical_time,
            "profiles": sorted(
                (to_canonical_obj(p) for p in self.agent_profiles),
                key=lambda d: (d["agent_id"], d["agent_version"])),
            "evidence": sorted(
                (to_canonical_obj(e) for e in self.capability_evidence),
                key=lambda d: d["evidence_id"]),
            "source_refs": sorted(self.source_refs),
            "policy_refs": sorted(self.policy_refs),
        }
        return digest(payload)


def build_registry_snapshot(
    *,
    snapshot_id: str,
    registry_version: str,
    logical_time: float,
    agent_profiles: List[AgentProfile],
    capability_evidence: List[AgentCapabilityEvidence],
    provenance: Provenance,
    source_refs: Tuple[str, ...] = (),
    policy_refs: Tuple[str, ...] = (),
) -> AgentRegistrySnapshot:
    """Assemble a snapshot in canonical order with a deterministic digest.

    Input container ordering does not affect the stored order or the digest.
    """
    profiles = tuple(sorted(agent_profiles, key=lambda p: p.identity))
    evidence = tuple(sorted(capability_evidence, key=lambda e: e.evidence_id))
    snap = AgentRegistrySnapshot(
        snapshot_id=snapshot_id, registry_version=registry_version,
        logical_time=logical_time, agent_profiles=profiles,
        capability_evidence=evidence, source_refs=tuple(sorted(source_refs)),
        policy_refs=tuple(sorted(policy_refs)), provenance=provenance)
    return snap.model_copy(update={"snapshot_digest": snap.logical_digest()})


__all__ = [
    "AgentStatus",
    "AgentCapability",
    "AgentCapabilityEvidence",
    "CapabilityEvidenceSet",
    "AgentProfile",
    "AgentRegistrySnapshot",
    "build_registry_snapshot",
]
