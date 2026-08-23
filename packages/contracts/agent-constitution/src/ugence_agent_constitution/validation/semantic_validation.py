"""Semantic-layer validation: is a well-shaped artifact internally coherent?

Runs only on an artifact the schema layer successfully constructed. Every rule
here is decidable from the artifact alone — this package resolves no registry,
fetches no predecessor, and consults no authority, so a rule that would need any
of those is not implemented, and the fields it would have judged are reported
INDETERMINATE rather than assumed fine.

The division between INVALID and INDETERMINATE is the whole design:

* A **contradiction** is INVALID. The artifact says two incompatible things, and
  no amount of extra context reconciles them.
* An **ambiguity** is INDETERMINATE. The artifact says one thing two ways, or says
  something this build cannot resolve, and picking an interpretation would be
  this package quietly making a decision that belongs to a person.

Rules are evaluated in full — no short-circuiting — so a report lists every
problem rather than only the first, and re-validating a fixed artifact does not
surface a new problem each round.
"""

from __future__ import annotations

from typing import Any, List, Sequence

from ..compatibility import (
    SuccessionCompatibility,
    is_semantic_version,
    succession_compatibility,
)
from ..fingerprint import compute_content_digest, is_well_formed_digest
from ..models.capability import CapabilityRequirement
from ..models.common import ArtifactKind, RequirementObligation
from ..models.constitution import AgentConstitution
from ..models.contract import DeveloperImplementationContract
from ..models.manifest import AgentRoleManifest
from ..models.subject import ConformanceSubject
from . import codes
from .outcomes import ValidationFinding, indeterminate, invalid


def _check_mandatory_text(
    value: Any, path: str, findings: List[ValidationFinding]
) -> None:
    """A mandatory text field must be present, non-blank, and unambiguous.

    Blank (or whitespace-only) is INVALID: the field is simply not there.

    Surrounding whitespace is INDETERMINATE, not a cosmetic nit. These artifacts
    are content-addressed, so ``"payments"`` and ``" payments"`` are two different
    artifacts that a human reads as one. Stripping it silently would change what
    the digest attests to; keeping it silently lets two artifacts that look
    identical carry different identities. Neither is this package's call to make.
    """
    if not isinstance(value, str) or not value.strip():
        findings.append(
            invalid(
                codes.MANDATORY_FIELD_MISSING,
                path,
                "mandatory field is absent or blank",
            )
        )
        return
    if value != value.strip():
        findings.append(
            indeterminate(
                codes.MANDATORY_FIELD_AMBIGUOUS,
                path,
                "mandatory field carries leading or trailing whitespace; in a "
                "content-addressed artifact this reads as one value and digests "
                "as another, and this package will not choose between them",
            )
        )


def _check_declared_digest(
    artifact: Any, declared: str, path: str, findings: List[ValidationFinding]
) -> None:
    """A declared content digest is a claim; recompute it rather than trust it."""
    if not declared:
        findings.append(
            indeterminate(
                codes.DIGEST_ABSENT,
                path,
                "artifact declares no content digest, so its identity cannot be "
                "established; stamp it before the artifact is stored or referenced",
            )
        )
        return
    if not is_well_formed_digest(declared):
        findings.append(
            invalid(
                codes.DIGEST_MALFORMED,
                path,
                f"declared digest {declared!r} is not a sha256:<64 hex> fingerprint",
            )
        )
        return
    if declared != compute_content_digest(artifact):
        findings.append(
            invalid(
                codes.DIGEST_MISMATCH,
                path,
                "declared content digest does not match the artifact's content; "
                "the artifact was edited after it was stamped",
            )
        )


def _check_requirements(
    requirements: Sequence[CapabilityRequirement],
    base_path: str,
    findings: List[ValidationFinding],
) -> None:
    """Rules over a requirement collection, individually and as a set."""
    seen_ids: dict = {}
    obligations_by_token: dict = {}

    for index, requirement in enumerate(requirements):
        path = f"{base_path}[{index}]"
        _check_mandatory_text(requirement.requirement_id, f"{path}.requirement_id", findings)
        _check_mandatory_text(requirement.summary, f"{path}.summary", findings)

        if requirement.obligation is RequirementObligation.CONDITIONAL:
            if not (requirement.condition or "").strip():
                findings.append(
                    invalid(
                        codes.REQUIREMENT_CONDITION_MISSING,
                        f"{path}.condition",
                        "a CONDITIONAL obligation with no stated condition is not a "
                        "weaker rule, it is an unreadable one",
                    )
                )
        elif (requirement.condition or "").strip():
            findings.append(
                invalid(
                    codes.REQUIREMENT_CONDITION_UNEXPECTED,
                    f"{path}.condition",
                    f"a {requirement.obligation.value} obligation binds "
                    "unconditionally; a condition on it contradicts the obligation",
                )
            )

        if requirement.entry_ref is not None:
            _check_mandatory_text(
                requirement.entry_ref.entry_id, f"{path}.entry_ref.entry_id", findings
            )
            _check_mandatory_text(
                requirement.entry_ref.registry_namespace,
                f"{path}.entry_ref.registry_namespace",
                findings,
            )
            if not is_well_formed_digest(requirement.entry_ref.entry_digest):
                findings.append(
                    invalid(
                        codes.DIGEST_MALFORMED,
                        f"{path}.entry_ref.entry_digest",
                        "a pinned registry entry must carry a well-formed digest; "
                        "an identifier alone does not pin a version",
                    )
                )
            obligations_by_token.setdefault(requirement.entry_ref.token, set()).add(
                requirement.obligation
            )
        elif requirement.obligation is RequirementObligation.MANDATORY:
            findings.append(
                indeterminate(
                    codes.REQUIREMENT_UNRESOLVABLE,
                    f"{path}.entry_ref",
                    "a MANDATORY requirement that pins no registry entry names "
                    "nothing a consumer can resolve, so whether it is met cannot "
                    "be decided by anyone downstream",
                )
            )

        key = requirement.requirement_id.strip()
        if key:
            seen_ids.setdefault(key, []).append(index)

    for requirement_id, indices in sorted(seen_ids.items()):
        if len(indices) > 1:
            findings.append(
                indeterminate(
                    codes.REQUIREMENT_ID_AMBIGUOUS,
                    f"{base_path}[{indices[0]}].requirement_id",
                    f"requirement id {requirement_id!r} is declared "
                    f"{len(indices)} times (indices {indices}); which one binds is "
                    "not determinable from the artifact",
                )
            )

    for token, obligations in sorted(obligations_by_token.items()):
        if {
            RequirementObligation.MANDATORY,
            RequirementObligation.PROHIBITED,
        } <= obligations:
            findings.append(
                invalid(
                    codes.REQUIREMENT_CONTRADICTORY,
                    base_path,
                    f"capability {token!r} is both MANDATORY and PROHIBITED; no "
                    "implementation can satisfy both",
                )
            )


def _check_prohibited_actions(
    prohibited: Sequence[str],
    requirements: Sequence[CapabilityRequirement],
    base_path: str,
    findings: List[ValidationFinding],
) -> None:
    """A prohibited action may not also be a mandatory requirement's summary."""
    for index, action in enumerate(prohibited):
        _check_mandatory_text(action, f"{base_path}[{index}]", findings)
    mandatory_summaries = {
        r.summary.strip()
        for r in requirements
        if r.obligation is RequirementObligation.MANDATORY
    }
    for action in sorted({a.strip() for a in prohibited} & mandatory_summaries):
        if action:
            findings.append(
                invalid(
                    codes.OBLIGATION_CONTRADICTION,
                    base_path,
                    f"{action!r} is listed as a prohibited action and is also the "
                    "subject of a MANDATORY capability requirement",
                )
            )


def validate_manifest_semantics(manifest: AgentRoleManifest) -> List[ValidationFinding]:
    """Semantic rules for a drafting artifact.

    A draft is held to internal coherence, not to ratification rules: it has no
    issuer, no lineage and no successor obligations, because it is not the artifact
    that supersedes anything. Its digest is optional in the same spirit — an
    unstamped draft is a draft, so an absent ``draft_digest`` is not reported at
    all, while a *stamped* one must be correct.
    """
    findings: List[ValidationFinding] = []
    _check_mandatory_text(manifest.manifest_id, "manifest_id", findings)
    _check_mandatory_text(manifest.role_name, "role_name", findings)
    _check_mandatory_text(manifest.role_summary, "role_summary", findings)
    _check_mandatory_text(manifest.author_id, "author_id", findings)
    if manifest.draft_revision < 0:
        findings.append(
            invalid(codes.MANDATORY_FIELD_MISSING, "draft_revision", "revision is negative")
        )
    _check_requirements(manifest.capability_requirements, "capability_requirements", findings)
    _check_prohibited_actions(
        manifest.prohibited_actions,
        manifest.capability_requirements,
        "prohibited_actions",
        findings,
    )
    if manifest.draft_digest:
        _check_declared_digest(manifest, manifest.draft_digest, "draft_digest", findings)
    return findings


def validate_constitution_semantics(
    constitution: AgentConstitution,
) -> List[ValidationFinding]:
    """Semantic rules for a ratified constitution, including succession."""
    findings: List[ValidationFinding] = []
    _check_mandatory_text(constitution.constitution_id, "constitution_id", findings)
    _check_mandatory_text(constitution.role_name, "role_name", findings)
    _check_mandatory_text(constitution.role_summary, "role_summary", findings)
    _check_mandatory_text(constitution.ratified_at, "ratified_at", findings)
    _check_mandatory_text(constitution.source_manifest_id, "source_manifest_id", findings)
    _check_mandatory_text(
        constitution.source_manifest_author_id, "source_manifest_author_id", findings
    )
    _check_mandatory_text(constitution.issuer.issuer_id, "issuer.issuer_id", findings)
    _check_mandatory_text(
        constitution.issuer.issuer_display_name, "issuer.issuer_display_name", findings
    )

    if not is_well_formed_digest(constitution.source_manifest_digest):
        findings.append(
            invalid(
                codes.DIGEST_MALFORMED,
                "source_manifest_digest",
                "the ratified draft must be pinned by a well-formed digest; without "
                "it the constitution does not record what was actually ratified",
            )
        )

    # Self-ratification. The issuer of a constitution may not be the author of the
    # draft it ratifies. This is a structural refusal, not an authority decision:
    # the package is not deciding who *may* ratify, only that an artifact claiming
    # one identity in both roles has recorded no independent act at all.
    if (
        constitution.issuer.issuer_id.strip()
        and constitution.issuer.issuer_id.strip()
        == constitution.source_manifest_author_id.strip()
    ):
        findings.append(
            invalid(
                codes.SELF_RATIFICATION,
                "issuer.issuer_id",
                f"issuer {constitution.issuer.issuer_id!r} is also the author of the "
                "manifest being ratified; a draft's author ratifying their own draft "
                "records no independent act",
            )
        )

    if not is_semantic_version(constitution.artifact_version):
        findings.append(
            invalid(
                codes.ARTIFACT_VERSION_MALFORMED,
                "artifact_version",
                f"{constitution.artifact_version!r} is not a MAJOR.MINOR.PATCH "
                "release version; pre-release and build-metadata versions are "
                "refused rather than ordered",
            )
        )

    _check_requirements(
        constitution.capability_requirements, "capability_requirements", findings
    )
    _check_prohibited_actions(
        constitution.prohibited_actions,
        constitution.capability_requirements,
        "prohibited_actions",
        findings,
    )
    _check_declared_digest(
        constitution, constitution.content_digest, "content_digest", findings
    )

    predecessor = constitution.predecessor
    if predecessor is not None:
        if (
            constitution.content_digest
            and predecessor.content_digest == constitution.content_digest
        ):
            findings.append(
                invalid(
                    codes.PREDECESSOR_SELF_REFERENCE,
                    "predecessor.content_digest",
                    "the artifact names itself as its own predecessor",
                )
            )
        else:
            findings.extend(
                _succession_findings(
                    succession_compatibility(
                        lineage_id=constitution.constitution_id,
                        artifact_version=constitution.artifact_version,
                        content_digest=constitution.content_digest,
                        predecessor_lineage_id=predecessor.constitution_id,
                        predecessor_version=predecessor.artifact_version,
                        predecessor_digest=predecessor.content_digest,
                    )
                )
            )
    return findings


def _succession_findings(
    result: SuccessionCompatibility,
) -> List[ValidationFinding]:
    """Translate a succession classification into findings."""
    if result in (
        SuccessionCompatibility.VALID_SUCCESSION,
        SuccessionCompatibility.LINEAGE_ROOT,
    ):
        return []
    if result is SuccessionCompatibility.LINEAGE_MISMATCH:
        return [
            invalid(
                codes.SUCCESSION_LINEAGE_MISMATCH,
                "predecessor.constitution_id",
                "the predecessor belongs to a different lineage; a constitution "
                "keeps its lineage identity across every version",
            )
        ]
    if result is SuccessionCompatibility.VERSION_NOT_BUMPED:
        return [
            invalid(
                codes.SUCCESSION_VERSION_NOT_BUMPED,
                "artifact_version",
                "a successor must bump its artifact version strictly above its "
                "predecessor's; reusing or lowering it makes the two versions "
                "indistinguishable to anyone holding a reference",
            )
        ]
    if result is SuccessionCompatibility.NO_MATERIAL_CHANGE:
        return [
            invalid(
                codes.SUCCESSION_NO_MATERIAL_CHANGE,
                "content_digest",
                "content is identical to the predecessor's; this supersedes nothing",
            )
        ]
    return [
        indeterminate(
            codes.SUCCESSION_VERSION_UNORDERABLE,
            "artifact_version",
            "one of the two versions could not be ordered, so whether this is a "
            "successor cannot be decided",
        )
    ]


def validate_contract_semantics(
    contract: DeveloperImplementationContract,
) -> List[ValidationFinding]:
    """Semantic rules for a developer implementation contract."""
    findings: List[ValidationFinding] = []
    _check_mandatory_text(contract.contract_id, "contract_id", findings)
    _check_mandatory_text(contract.implementation_target, "implementation_target", findings)
    _check_mandatory_text(
        contract.constitution_ref.constitution_id, "constitution_ref.constitution_id", findings
    )
    if not is_semantic_version(contract.artifact_version):
        findings.append(
            invalid(
                codes.ARTIFACT_VERSION_MALFORMED,
                "artifact_version",
                f"{contract.artifact_version!r} is not a MAJOR.MINOR.PATCH release version",
            )
        )
    if not is_well_formed_digest(contract.constitution_ref.content_digest):
        findings.append(
            invalid(
                codes.DIGEST_MALFORMED,
                "constitution_ref.content_digest",
                "a contract must pin the exact constitution version it derives from; "
                "an unpinned reference silently follows the lineage wherever it goes",
            )
        )
    for behaviour in contract.contradictory_behaviours:
        findings.append(
            invalid(
                codes.CONTRACT_CONTRADICTORY_BEHAVIOUR,
                "required_behaviours",
                f"{behaviour!r} is listed as both required and forbidden",
            )
        )
    if not contract.required_behaviours and not contract.forbidden_behaviours:
        findings.append(
            indeterminate(
                codes.CONTRACT_NO_OBLIGATIONS,
                "required_behaviours",
                "the contract states no required and no forbidden behaviour, so what "
                "it obliges a developer to do is not determinable from it",
            )
        )
    _check_declared_digest(contract, contract.content_digest, "content_digest", findings)
    return findings


def validate_subject_semantics(subject: ConformanceSubject) -> List[ValidationFinding]:
    """Semantic rules for a conformance subject.

    Note what is absent: nothing here evaluates the subject. AC-0 emits no
    conformance finding, so these rules only decide whether the subject is a
    coherent *description* of something a later build could assess.
    """
    findings: List[ValidationFinding] = []
    _check_mandatory_text(subject.subject_id, "subject_id", findings)
    _check_mandatory_text(
        subject.constitution_ref.constitution_id, "constitution_ref.constitution_id", findings
    )
    if not is_well_formed_digest(subject.constitution_ref.content_digest):
        findings.append(
            invalid(
                codes.DIGEST_MALFORMED,
                "constitution_ref.content_digest",
                "a subject must pin the exact constitution version it claims to be "
                "governed by",
            )
        )
    if subject.contract_ref is not None and not is_well_formed_digest(
        subject.contract_ref.content_digest
    ):
        findings.append(
            invalid(
                codes.DIGEST_MALFORMED,
                "contract_ref.content_digest",
                "a contract reference must be pinned by a well-formed digest",
            )
        )

    by_entry: dict = {}
    for index, entry in enumerate(subject.declared_capability_entries):
        if not is_well_formed_digest(entry.entry_digest):
            findings.append(
                invalid(
                    codes.DIGEST_MALFORMED,
                    f"declared_capability_entries[{index}].entry_digest",
                    "a declared capability entry must be pinned by a well-formed digest",
                )
            )
        by_entry.setdefault(
            (entry.registry_namespace, entry.entry_id), set()
        ).add((entry.entry_version, entry.entry_digest))
    for (namespace, entry_id), variants in sorted(by_entry.items()):
        if len(variants) > 1:
            findings.append(
                indeterminate(
                    codes.SUBJECT_ENTRY_AMBIGUOUS,
                    "declared_capability_entries",
                    f"capability entry {namespace}/{entry_id} is declared at "
                    f"{len(variants)} different version/digest pairs; which one the "
                    "subject actually uses is not determinable",
                )
            )
    _check_declared_digest(subject, subject.content_digest, "content_digest", findings)
    return findings


#: Dispatch from artifact kind to its semantic rule set.
SEMANTIC_RULES = {
    ArtifactKind.AGENT_ROLE_MANIFEST: validate_manifest_semantics,
    ArtifactKind.AGENT_CONSTITUTION: validate_constitution_semantics,
    ArtifactKind.DEVELOPER_IMPLEMENTATION_CONTRACT: validate_contract_semantics,
    ArtifactKind.CONFORMANCE_SUBJECT: validate_subject_semantics,
}


__all__ = [
    "SEMANTIC_RULES",
    "validate_manifest_semantics",
    "validate_constitution_semantics",
    "validate_contract_semantics",
    "validate_subject_semantics",
]
