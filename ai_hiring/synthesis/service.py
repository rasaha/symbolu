"""Evidence-synthesis service (H2).

Builds a bounded, minimized, provenance-preserving evidence package for
recommendation generation from tenant-authorized intake evidence. It binds
evidence to the correct application/candidate/requisition/rubric versions,
distinguishes direct from derived evidence, detects missing / quarantined / stale
/ duplicated / conflicting evidence, and **never silently omits adverse evidence**.
Deterministic for the same normalized inputs and policy.
"""

from __future__ import annotations

from typing import Callable, Optional

from decision_governance.api.common import new_id

from ..domain_audit.events import HiringDomainEventType
from ..domain_audit.service import HiringDomainAuditService
from ..errors import ProhibitedAttributeError, StaleRubricVersionError
from ..repositories.product_repositories import (
    ApplicationRepository,
    EvidenceIntakeRepository,
    JobDefinitionRepository,
)
from ..services._hiring_context import ActorContext, guard_tenant
from .minimization import MinimizationPolicy
from .package import EvidenceKind, EvidencePackage, EvidencePackageItem


class EvidenceSynthesisService:
    def __init__(
        self, *,
        applications: ApplicationRepository,
        job_definitions: JobDefinitionRepository,
        evidence_intake: EvidenceIntakeRepository,
        packages,  # InMemoryEvidencePackageRepository
        audit: HiringDomainAuditService,
        id_factory: Callable[[str], str] = new_id,
    ) -> None:
        self._apps = applications
        self._defs = job_definitions
        self._intake = evidence_intake
        self._packages = packages
        self._audit = audit
        self._new_id = id_factory

    def synthesize(
        self, ctx: ActorContext, *, application_id: str, rubric_version: int,
        policy: Optional[MinimizationPolicy] = None,
        supplied_attribute_keys: tuple[str, ...] = (),
        adverse_refs: tuple[str, ...] = (),
        derived_items: tuple[EvidencePackageItem, ...] = (),
        package_id: Optional[str] = None, correlation_id: str = "",
    ) -> EvidencePackage:
        policy = policy or MinimizationPolicy()
        app = self._apps.get(application_id)
        guard_tenant(ctx, record_tenant_id=app.tenant_id, entity_type="application",
                     entity_id=application_id, audit=self._audit)
        job_definition = self._defs.get(app.job_definition_id)

        self._audit.record(
            event_type=HiringDomainEventType.SYNTHESIS_REQUESTED, entity_type="synthesis_package",
            entity_id=application_id, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
            actor_type=ctx.actor_type, correlation_id=correlation_id,
            payload={"application_id": application_id, "rubric_version": str(rubric_version)})

        # Protected/prohibited attribute leakage prevention.
        prohibited_hits = policy.contains_prohibited(supplied_attribute_keys)
        if prohibited_hits:
            self._audit.record_denial(
                entity_type="synthesis_package", entity_id=application_id, tenant_id=ctx.tenant_id,
                actor_id=ctx.actor_id, actor_type=ctx.actor_type,
                reason="prohibited_attribute:" + ",".join(prohibited_hits))
            raise ProhibitedAttributeError(
                "prohibited attributes supplied to synthesis: " + ", ".join(prohibited_hits))

        # Rubric-version binding — stale rubric fails safe.
        if rubric_version != job_definition.rubric_version:
            self._audit.record_denial(
                entity_type="synthesis_package", entity_id=application_id, tenant_id=ctx.tenant_id,
                actor_id=ctx.actor_id, actor_type=ctx.actor_type,
                reason=f"stale_rubric:{rubric_version}!={job_definition.rubric_version}")
            raise StaleRubricVersionError(
                f"rubric_version {rubric_version} != job definition rubric_version "
                f"{job_definition.rubric_version}")

        # Tenant-authorized intake for this application only.
        intake_items = [
            i for i in self._intake.items_for_application(application_id)
            if i.tenant_id == ctx.tenant_id]
        adverse = set(adverse_refs)

        items: list[EvidencePackageItem] = []
        quarantined: list[str] = []
        duplicates: list[str] = []
        seen_hashes: set[str] = set()
        excluded_types: set[str] = set()

        for it in sorted(intake_items, key=lambda x: x.intake_id):
            if not policy.evidence_type_allowed(it.evidence_type):
                excluded_types.add(it.evidence_type)
                continue
            if policy.is_quarantined(it.content_hash):
                quarantined.append(it.intake_id)
                continue
            if it.content_hash in seen_hashes:
                duplicates.append(it.intake_id)
                continue
            seen_hashes.add(it.content_hash)
            items.append(EvidencePackageItem(
                evidence_ref=it.intake_id, evidence_type=it.evidence_type,
                content_hash=it.content_hash, kind=EvidenceKind.DIRECT,
                provenance_source=it.provenance.source.value, collected_by=it.provenance.collected_by,
                adverse=(it.intake_id in adverse)))

        items.extend(derived_items)

        # Bounded minimization — always keep adverse items; truncate non-adverse only.
        minimization_applied = False
        if policy.max_items and len(items) > policy.max_items:
            adverse_items = [i for i in items if i.adverse]
            non_adverse = [i for i in items if not i.adverse]
            budget = max(policy.max_items - len(adverse_items), 0)
            items = adverse_items + non_adverse[:budget]
            minimization_applied = True

        covered = {i.evidence_type for i in items if i.evidence_ref not in set(quarantined)}
        required = tuple(job_definition.required_evidence_types)
        missing = tuple(t for t in required if t not in covered)
        conflicting_types = tuple(sorted({i.evidence_type for i in items if i.adverse}))

        pkg = EvidencePackage(
            synthesis_package_id=package_id or self._new_id("syn"), tenant_id=ctx.tenant_id,
            application_id=application_id, candidate_subject_ref=app.candidate_id,
            requisition_id=app.requisition_id, job_definition_id=app.job_definition_id,
            job_definition_version=app.job_definition_version, rubric_id=job_definition.rubric_id,
            rubric_version=job_definition.rubric_version, items=tuple(items),
            missing_evidence_types=missing, quarantined_refs=tuple(quarantined),
            duplicate_refs=tuple(duplicates), conflicting_evidence_types=conflicting_types,
            item_limit=policy.max_items, minimization_applied=minimization_applied,
            excluded_fields=tuple(policy.excluded_fields),
            prohibited_attributes_checked=tuple(sorted(policy.prohibited_set())),
            policy_refs=(policy.policy_ref,), correlation_id=correlation_id)
        self._packages.add(pkg)

        if missing:
            self._audit.record(
                event_type=HiringDomainEventType.EVIDENCE_INSUFFICIENCY_DETECTED,
                entity_type="synthesis_package", entity_id=pkg.synthesis_package_id,
                tenant_id=ctx.tenant_id, actor_id=ctx.actor_id, actor_type=ctx.actor_type,
                correlation_id=correlation_id, payload={"missing": ",".join(missing)})
        self._audit.record(
            event_type=HiringDomainEventType.SYNTHESIS_COMPLETED, entity_type="synthesis_package",
            entity_id=pkg.synthesis_package_id, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
            actor_type=ctx.actor_type, entity_version=pkg.version, correlation_id=correlation_id,
            payload={"fingerprint": pkg.fingerprint, "included": str(pkg.included_count),
                     "missing": ",".join(missing)})
        return pkg
