"""Shared, fully deterministic artifact builders for this package's tests.

Every builder returns a *valid* artifact by default and takes overrides, so an
invariant test can express itself as "the valid artifact, with exactly one thing
wrong". Nothing here reads a clock or a random source: the same call produces the
same artifact, with the same digest, in every run.
"""

from __future__ import annotations

from typing import Any

from ugence_agent_constitution import (
    AgentConstitution,
    AgentRoleManifest,
    CapabilityRegistryEntryRef,
    CapabilityRequirement,
    ConformanceSubject,
    ConstitutionRef,
    ContentRef,
    DeveloperImplementationContract,
    IssuerIdentity,
    IssuerKind,
    RequirementObligation,
    SubjectKind,
    fingerprint,
)

RATIFIED_AT = "2026-01-15T09:30:00Z"
AUTHOR_ID = "drafter.alex"
ISSUER_ID = "owner.board"


def entry_ref(entry_id: str = "refund.issue", version: str = "1.0.0") -> CapabilityRegistryEntryRef:
    return CapabilityRegistryEntryRef(
        registry_namespace="ugence.capabilities",
        entry_id=entry_id,
        entry_version=version,
        entry_digest=fingerprint({"entry_id": entry_id, "entry_version": version}),
    )


def requirement(**overrides: Any) -> CapabilityRequirement:
    payload = {
        "requirement_id": "req.refund.ceiling",
        "summary": "Issue a refund only up to the ratified ceiling",
        "obligation": RequirementObligation.MANDATORY,
        "entry_ref": entry_ref(),
        "rationale": "The ceiling is the owner-ratified limit of delegated spend.",
    }
    payload.update(overrides)
    return CapabilityRequirement(**payload)


def manifest(**overrides: Any) -> AgentRoleManifest:
    """A valid, digest-stamped draft."""
    payload = {
        "manifest_id": "manifest.refund-agent",
        "role_name": "Refund agent",
        "role_summary": "Handles customer refund requests within a ratified ceiling.",
        "author_id": AUTHOR_ID,
        "capability_requirements": (requirement(),),
        "prohibited_actions": ("Approve a refund it originated",),
        "notes": "Draft for review.",
    }
    payload.update(overrides)
    stamp = payload.pop("_stamp", True)
    draft = AgentRoleManifest(**payload)
    return draft.with_draft_digest() if stamp else draft


def constitution(**overrides: Any) -> AgentConstitution:
    """A valid, digest-stamped lineage-root constitution."""
    source = manifest()
    payload = {
        "constitution_id": "constitution.refund-agent",
        "artifact_version": "1.0.0",
        "issuer": IssuerIdentity(
            issuer_id=ISSUER_ID,
            issuer_display_name="Ugence Owner Board",
            issuer_kind=IssuerKind.OWNER_BODY,
        ),
        "source_manifest_id": source.manifest_id,
        "source_manifest_digest": source.draft_digest,
        "source_manifest_author_id": source.author_id,
        "role_name": source.role_name,
        "role_summary": source.role_summary,
        "capability_requirements": source.capability_requirements,
        "prohibited_actions": source.prohibited_actions,
        "ratified_at": RATIFIED_AT,
    }
    payload.update(overrides)
    stamp = payload.pop("_stamp", True)
    artifact = AgentConstitution(**payload)
    return artifact.with_content_digest() if stamp else artifact


def successor(base: AgentConstitution, **overrides: Any) -> AgentConstitution:
    """A valid successor to ``base``: same lineage, bumped version, changed content."""
    payload = base.model_dump(mode="python")
    payload.update(
        {
            "artifact_version": "1.1.0",
            "predecessor": base.as_ref().model_dump(mode="python"),
            "role_summary": base.role_summary + " Escalates anything above the ceiling.",
            "content_digest": "",
        }
    )
    payload.update(overrides)
    stamp = payload.pop("_stamp", True)
    artifact = AgentConstitution.model_validate(payload)
    return artifact.with_content_digest() if stamp else artifact


def contract(governed_by: AgentConstitution | None = None, **overrides: Any) -> DeveloperImplementationContract:
    """A valid developer implementation contract."""
    source = governed_by or constitution()
    payload = {
        "contract_id": "contract.refund-agent.api",
        "artifact_version": "1.0.0",
        "constitution_ref": ConstitutionRef(
            constitution_id=source.constitution_id,
            artifact_version=source.artifact_version,
            content_digest=source.content_digest,
        ),
        "implementation_target": "services/refund-agent",
        "required_behaviours": ("Reject a refund above the ceiling",),
        "forbidden_behaviours": ("Retry a rejected refund automatically",),
        "acceptance_criteria": ("A refund above the ceiling returns a refusal",),
    }
    payload.update(overrides)
    stamp = payload.pop("_stamp", True)
    artifact = DeveloperImplementationContract(**payload)
    return artifact.with_content_digest() if stamp else artifact


def subject(governed_by: AgentConstitution | None = None, **overrides: Any) -> ConformanceSubject:
    """A valid conformance subject. AC-0 evaluates none of these."""
    source = governed_by or constitution()
    built = contract(source)
    payload = {
        "subject_id": "subject.refund-agent.build-417",
        "subject_kind": SubjectKind.AGENT_IMPLEMENTATION,
        "constitution_ref": ConstitutionRef(
            constitution_id=source.constitution_id,
            artifact_version=source.artifact_version,
            content_digest=source.content_digest,
        ),
        "contract_ref": ContentRef(
            ref_id=built.contract_id, content_digest=built.content_digest
        ),
        "declared_capability_entries": (entry_ref(),),
        "description": "Build 417 of the refund agent.",
    }
    payload.update(overrides)
    stamp = payload.pop("_stamp", True)
    artifact = ConformanceSubject(**payload)
    return artifact.with_content_digest() if stamp else artifact
