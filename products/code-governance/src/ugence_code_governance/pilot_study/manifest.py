"""Immutable pilot study manifest + pre-pilot freeze + amendment records.

The manifest binds the bounded study design and fails closed on an unbounded or
underspecified study. The pre-pilot freeze binds all version inputs before data
collection; after collection begins, changing a frozen input requires a new pilot
revision or a formally recorded amendment — never a silent policy change. An
amendment may never rewrite prior results.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple

from ..fingerprints import domain_hash
from .errors import StudyManifestError
from .vocab import AmendmentReason, PilotEvidenceClass

MANIFEST_SCHEMA_VERSION = "code_governance.pilot_study_manifest.v1"
DOMAIN_STUDY_MANIFEST = "cg.pilot_study.manifest.v1"
DOMAIN_PREPILOT_FREEZE = "cg.pilot_study.prepilot_freeze.v1"
DOMAIN_AMENDMENT = "cg.pilot_study.amendment.v1"


@dataclass(frozen=True)
class PilotStudyManifest:
    """An immutable, versioned bounded-pilot study design."""

    manifest_id: str
    manifest_version: str
    pilot_id: str
    tenant_id: str
    allowed_repositories: Tuple[str, ...]
    allowed_branches: Tuple[str, ...]
    pilot_start_date: str
    pilot_end_date: str
    maximum_evaluations: int
    target_sample_count: int
    selection_method: str
    evaluation_profile_ref: str
    policy_version: str
    adapter_registry_version: str
    intervention_routing_version: str
    reviewer_role_allowlist: Tuple[str, ...]
    reviewer_refs: Tuple[str, ...]
    evidence_classes_permitted: Tuple[str, ...]
    minimum_reviewer_feedback_target: int
    reviewer_protocol_ref: str
    success_indicators: Tuple[str, ...] = ()
    pause_conditions: Tuple[str, ...] = ()
    stop_conditions: Tuple[str, ...] = ()
    exclusion_criteria: Tuple[str, ...] = ()
    allowed_pull_request_numbers: Tuple[int, ...] = ()
    known_limitations: Tuple[str, ...] = ()
    schema_version: str = MANIFEST_SCHEMA_VERSION
    execution_status: str = "DISABLED"

    @property
    def manifest_fingerprint(self) -> str:
        return domain_hash(DOMAIN_STUDY_MANIFEST, {
            "manifest_id": self.manifest_id, "manifest_version": self.manifest_version,
            "pilot_id": self.pilot_id, "tenant_id": self.tenant_id,
            "allowed_repositories": sorted(self.allowed_repositories),
            "allowed_branches": sorted(self.allowed_branches),
            "allowed_pull_request_numbers": sorted(self.allowed_pull_request_numbers),
            "pilot_start_date": self.pilot_start_date, "pilot_end_date": self.pilot_end_date,
            "maximum_evaluations": self.maximum_evaluations,
            "target_sample_count": self.target_sample_count,
            "selection_method": self.selection_method,
            "evaluation_profile_ref": self.evaluation_profile_ref,
            "policy_version": self.policy_version,
            "adapter_registry_version": self.adapter_registry_version,
            "intervention_routing_version": self.intervention_routing_version,
            "reviewer_role_allowlist": sorted(self.reviewer_role_allowlist),
            "reviewer_refs": sorted(self.reviewer_refs),
            "evidence_classes_permitted": sorted(self.evidence_classes_permitted),
            "minimum_reviewer_feedback_target": self.minimum_reviewer_feedback_target,
            "reviewer_protocol_ref": self.reviewer_protocol_ref,
            "schema_version": self.schema_version, "execution_status": self.execution_status})


def validate_study_manifest(m: PilotStudyManifest) -> PilotStudyManifest:
    """Validate a study manifest; raise StudyManifestError (fail closed)."""
    if m.schema_version != MANIFEST_SCHEMA_VERSION:
        raise StudyManifestError(f"unsupported manifest schema {m.schema_version!r}")
    if not m.tenant_id or m.tenant_id in ("*", "all", "any"):
        raise StudyManifestError("tenant scope must be explicit (no wildcard)")
    if not m.allowed_repositories:
        raise StudyManifestError("repository scope must be non-empty")
    if any(r in ("*", "") or r.endswith("/*") for r in m.allowed_repositories):
        raise StudyManifestError("repositories must be explicit (no wildcard)")
    if not m.allowed_branches or any(b in ("*", "") for b in m.allowed_branches):
        raise StudyManifestError("branches must be explicit and non-empty")
    if not m.pilot_end_date:
        raise StudyManifestError("a pilot end date is required")
    if m.maximum_evaluations <= 0 or m.target_sample_count <= 0:
        raise StudyManifestError("evaluation/sample bounds must be positive")
    if not m.policy_version:
        raise StudyManifestError("a policy version is required")
    if not m.reviewer_protocol_ref:
        raise StudyManifestError("a reviewer protocol reference is required")
    if not m.evidence_classes_permitted:
        raise StudyManifestError("at least one permitted evidence class is required")
    for ec in m.evidence_classes_permitted:
        if ec not in {e.value for e in PilotEvidenceClass}:
            raise StudyManifestError(f"unknown evidence class {ec!r}")
    if m.execution_status != "DISABLED":
        raise StudyManifestError("execution must be DISABLED")
    return m


@dataclass(frozen=True)
class PilotPrePilotFreezeRecord:
    """An immutable freeze of all version inputs, bound before data collection."""

    pilot_id: str
    tenant_id: str
    manifest_fingerprint: str
    code_governance_version: str
    action_clearance_version: str
    policy_version: str
    adapter_registry_version: str
    intervention_routing_version: str
    durable_store_schema_version: str
    config_fingerprint: str
    repository_scope: Tuple[str, ...]
    branch_scope: Tuple[str, ...]
    test_baseline_ref: str
    frozen_at: str
    execution_status: str = "DISABLED"

    @property
    def freeze_fingerprint(self) -> str:
        return domain_hash(DOMAIN_PREPILOT_FREEZE, {
            "pilot_id": self.pilot_id, "tenant_id": self.tenant_id,
            "manifest_fingerprint": self.manifest_fingerprint,
            "code_governance_version": self.code_governance_version,
            "action_clearance_version": self.action_clearance_version,
            "policy_version": self.policy_version,
            "adapter_registry_version": self.adapter_registry_version,
            "intervention_routing_version": self.intervention_routing_version,
            "durable_store_schema_version": self.durable_store_schema_version,
            "config_fingerprint": self.config_fingerprint,
            "repository_scope": sorted(self.repository_scope),
            "branch_scope": sorted(self.branch_scope),
            "test_baseline_ref": self.test_baseline_ref, "frozen_at": self.frozen_at,
            "execution_status": self.execution_status})

    @property
    def record_id(self) -> str:
        return f"prepilot-freeze:{self.pilot_id}:{self.freeze_fingerprint[:16]}"


@dataclass(frozen=True)
class PilotAmendmentRecord:
    """An immutable amendment. Never rewrites prior results."""

    amendment_id: str
    pilot_id: str
    previous_manifest_fingerprint: str
    new_manifest_fingerprint: str
    reason_category: AmendmentReason
    author_ref: str
    approved_at: str
    effective_evaluation_boundary: int
    affected_metrics: Tuple[str, ...] = ()
    report_prior_and_later_separately: bool = True

    @property
    def amendment_fingerprint(self) -> str:
        return domain_hash(DOMAIN_AMENDMENT, {
            "amendment_id": self.amendment_id, "pilot_id": self.pilot_id,
            "previous_manifest_fingerprint": self.previous_manifest_fingerprint,
            "new_manifest_fingerprint": self.new_manifest_fingerprint,
            "reason_category": self.reason_category.value, "author_ref": self.author_ref,
            "approved_at": self.approved_at,
            "effective_evaluation_boundary": self.effective_evaluation_boundary,
            "affected_metrics": sorted(self.affected_metrics),
            "report_prior_and_later_separately": self.report_prior_and_later_separately})

    @property
    def record_id(self) -> str:
        return f"pilot-amendment:{self.amendment_id}:{self.amendment_fingerprint[:12]}"


def freeze_pilot_study(
    manifest: PilotStudyManifest,
    *,
    code_governance_version: str,
    action_clearance_version: str,
    durable_store_schema_version: str,
    config_fingerprint: str,
    test_baseline_ref: str,
    frozen_at: str,
) -> PilotPrePilotFreezeRecord:
    """Build the pre-pilot freeze record from a validated manifest."""
    validate_study_manifest(manifest)
    return PilotPrePilotFreezeRecord(
        pilot_id=manifest.pilot_id, tenant_id=manifest.tenant_id,
        manifest_fingerprint=manifest.manifest_fingerprint,
        code_governance_version=code_governance_version,
        action_clearance_version=action_clearance_version,
        policy_version=manifest.policy_version,
        adapter_registry_version=manifest.adapter_registry_version,
        intervention_routing_version=manifest.intervention_routing_version,
        durable_store_schema_version=durable_store_schema_version,
        config_fingerprint=config_fingerprint,
        repository_scope=manifest.allowed_repositories, branch_scope=manifest.allowed_branches,
        test_baseline_ref=test_baseline_ref, frozen_at=frozen_at)


__all__ = [
    "MANIFEST_SCHEMA_VERSION", "PilotStudyManifest", "validate_study_manifest",
    "PilotPrePilotFreezeRecord", "PilotAmendmentRecord", "freeze_pilot_study",
]
