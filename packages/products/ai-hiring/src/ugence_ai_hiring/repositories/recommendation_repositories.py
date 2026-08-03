"""In-memory repositories for H2 recommendation/synthesis records.

Reference adapters for evidence-synthesis packages, recommendations (versioned),
structured claims, provider-evaluation bindings, and reviewer dispositions. Same
contract as the H1 stores: unique keys, immutability (no overwrite), append-only
history, deterministic ordering, tenant-agnostic storage (tenant isolation is
enforced in the services). No production database in this phase.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from ..errors import (
    RecommendationNotFoundError,
    SynthesisPackageNotFoundError,
    VersionConflictError,
)
from ..recommendations.claim import HiringClaim
from ..recommendations.recommendation import HiringRecommendation
from ..recommendations.review import ReviewerDisposition
from ..recommendations.status import RECOMMENDATION_TERMINAL_STATUSES
from ..recommendations.tap_integration import ClaimAssertionBinding
from ..synthesis.package import EvidencePackage
from .product_repositories import _VersionedStore


# --- Evidence-synthesis packages (versioned) --------------------------------
class InMemoryEvidencePackageRepository:
    def __init__(self) -> None:
        self._s: _VersionedStore[EvidencePackage] = _VersionedStore(
            id_of=lambda r: r.synthesis_package_id, version_of=lambda r: r.version,
            not_found=lambda k: SynthesisPackageNotFoundError(f"synthesis package '{k}' not found"),
            label="synthesis_package")

    def add(self, record): return self._s.add(record)
    def get(self, package_id): return self._s.get(package_id)
    def exists(self, package_id): return self._s.exists(package_id)
    def history(self, package_id): return self._s.history(package_id)

    def latest_for_application(self, application_id: str) -> Optional[EvidencePackage]:
        matches = [p for p in self._s.latest_records() if p.application_id == application_id]
        return max(matches, key=lambda p: p.created_at) if matches else None


# --- Recommendations (versioned) --------------------------------------------
class InMemoryRecommendationRepository:
    def __init__(self) -> None:
        self._s: _VersionedStore[HiringRecommendation] = _VersionedStore(
            id_of=lambda r: r.recommendation_id, version_of=lambda r: r.version,
            not_found=lambda k: RecommendationNotFoundError(f"recommendation '{k}' not found"),
            label="recommendation")

    def add(self, record): return self._s.add(record)
    def get(self, recommendation_id): return self._s.get(recommendation_id)
    def get_version(self, recommendation_id, version): return self._s.get_version(recommendation_id, version)
    def exists(self, recommendation_id): return self._s.exists(recommendation_id)
    def history(self, recommendation_id): return self._s.history(recommendation_id)

    def list_for_application(self, application_id: str) -> tuple[HiringRecommendation, ...]:
        return tuple(sorted(
            (r for r in self._s.latest_records() if r.application_id == application_id),
            key=lambda r: r.recommendation_id))

    def active_for_application(self, application_id: str) -> tuple[HiringRecommendation, ...]:
        return tuple(r for r in self.list_for_application(application_id)
                     if r.status not in RECOMMENDATION_TERMINAL_STATUSES)


# --- Structured claims (append-only, unique claim_id) -----------------------
class InMemoryClaimRepository:
    def __init__(self) -> None:
        self._by_id: dict[str, HiringClaim] = {}

    def add(self, claim: HiringClaim) -> HiringClaim:
        if claim.claim_id in self._by_id:
            raise VersionConflictError(f"claim '{claim.claim_id}' already exists")
        self._by_id[claim.claim_id] = claim
        return claim

    def get(self, claim_id: str) -> Optional[HiringClaim]:
        return self._by_id.get(claim_id)

    def claims_for(self, recommendation_id: str, recommendation_version: int) -> tuple[HiringClaim, ...]:
        return tuple(sorted(
            (c for c in self._by_id.values()
             if c.recommendation_id == recommendation_id
             and c.recommendation_version == recommendation_version),
            key=lambda c: c.claim_id))


# --- Provider-evaluation bindings (append-only) -----------------------------
class InMemoryClaimAssertionBindingRepository:
    def __init__(self) -> None:
        self._by_id: dict[str, ClaimAssertionBinding] = {}

    def add(self, binding: ClaimAssertionBinding) -> ClaimAssertionBinding:
        if binding.binding_id in self._by_id:
            raise VersionConflictError(f"binding '{binding.binding_id}' already exists")
        self._by_id[binding.binding_id] = binding
        return binding

    def bindings_for(self, recommendation_id: str, recommendation_version: int) -> tuple[ClaimAssertionBinding, ...]:
        return tuple(sorted(
            (b for b in self._by_id.values()
             if b.recommendation_id == recommendation_id
             and b.recommendation_version == recommendation_version),
            key=lambda b: b.claim_id))

    def for_claim(self, claim_id: str) -> tuple[ClaimAssertionBinding, ...]:
        return tuple(b for b in self._by_id.values() if b.claim_id == claim_id)


# --- Reviewer dispositions (append-only) ------------------------------------
class InMemoryReviewerDispositionRepository:
    def __init__(self) -> None:
        self._items: list[ReviewerDisposition] = []

    def add(self, disposition: ReviewerDisposition) -> ReviewerDisposition:
        self._items.append(disposition)
        return disposition

    def dispositions_for(self, recommendation_id: str) -> tuple[ReviewerDisposition, ...]:
        return tuple(d for d in self._items if d.recommendation_id == recommendation_id)


@runtime_checkable
class RecommendationRepository(Protocol):
    def add(self, record: HiringRecommendation) -> HiringRecommendation: ...
    def get(self, recommendation_id: str) -> HiringRecommendation: ...
    def history(self, recommendation_id: str) -> tuple[HiringRecommendation, ...]: ...
