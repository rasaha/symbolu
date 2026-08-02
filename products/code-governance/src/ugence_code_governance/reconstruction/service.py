"""Governance-chain reconstruction service.

Loads every referenced record and verifies the chain end-to-end. Any missing
mandatory record, tenant inconsistency, identity/fingerprint mismatch, or
base/head inconsistency fails closed with a structured result.

For a shadow-complete workflow whose current head matches the chain, the result
is ``COMPLETE``. An old-head chain remains fully reconstructable but is reported
``STALE``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from ..models.enums import ReconstructionState
from ..persistence.protocols import (
    ClaimManifestRepository,
    EvidenceRepository,
    GovernanceChainRepository,
    PreparedActionRepository,
    RecommendationRepository,
    WorkflowRepository,
)
from .records import GovernanceChainRecord


@dataclass(frozen=True)
class ReconstructionResult:
    """Structured outcome of a chain reconstruction."""

    state: ReconstructionState
    chain_id: str
    issues: Tuple[str, ...] = ()
    verified_links: Tuple[str, ...] = ()

    @property
    def is_complete(self) -> bool:
        return self.state is ReconstructionState.COMPLETE


class ChainReconstructionService:
    """Reconstructs and verifies a governance chain from durable references."""

    def __init__(
        self,
        *,
        evidence_repo: EvidenceRepository,
        claim_repo: ClaimManifestRepository,
        recommendation_repo: RecommendationRepository,
        prepared_action_repo: PreparedActionRepository,
        workflow_repo: WorkflowRepository,
        chain_repo: GovernanceChainRepository,
    ) -> None:
        self._evidence = evidence_repo
        self._claims = claim_repo
        self._recs = recommendation_repo
        self._actions = prepared_action_repo
        self._workflows = workflow_repo
        self._chains = chain_repo

    def reconstruct(
        self,
        tenant_id: str,
        chain_id: str,
        *,
        current_head_sha: Optional[str] = None,
    ) -> ReconstructionResult:
        """Reconstruct the chain ``chain_id`` for ``tenant_id`` and verify it.

        ``current_head_sha`` (when provided) is the lineage's current head; if the
        chain's head differs, the chain is historical and reported ``STALE``.
        """
        issues: List[str] = []
        verified: List[str] = []

        chain = self._chains.get(tenant_id, chain_id)
        if chain is None:
            return ReconstructionResult(
                ReconstructionState.INCOMPLETE, chain_id,
                issues=("chain record not found",))
        assert isinstance(chain, GovernanceChainRecord)

        # Tenant consistency across every referenced record.
        if chain.tenant_id != tenant_id:
            return ReconstructionResult(
                ReconstructionState.TENANT_MISMATCH, chain_id,
                issues=("chain tenant does not match requested tenant",))

        # Workflow revision link.
        revision = self._workflows.get(tenant_id, chain.revision_id)
        if revision is None:
            issues.append("workflow revision not found")
        else:
            if getattr(revision, "tenant_id", None) != tenant_id:
                return ReconstructionResult(
                    ReconstructionState.TENANT_MISMATCH, chain_id,
                    issues=("workflow revision tenant mismatch",))
            if revision.head_sha != chain.head_sha or revision.base_sha != chain.base_sha:
                issues.append("workflow revision base/head mismatch")
            else:
                verified.append("workflow_revision")

        # Evidence links + integrity + tenant + head binding.
        if not chain.evidence_refs:
            issues.append("no evidence references in chain")
        for eid in chain.evidence_refs:
            ev = self._evidence.get(tenant_id, eid)
            if ev is None:
                issues.append(f"missing evidence ref {eid}")
                continue
            if ev.tenant_id != tenant_id:
                return ReconstructionResult(
                    ReconstructionState.TENANT_MISMATCH, chain_id,
                    issues=(f"evidence {eid} tenant mismatch",))
            try:
                ev.verify_integrity()
            except Exception:
                return ReconstructionResult(
                    ReconstructionState.INTEGRITY_FAILURE, chain_id,
                    issues=(f"evidence {eid} content digest mismatch",))
            if ev.head_sha != chain.head_sha:
                issues.append(f"evidence {eid} bound to different head")
            else:
                verified.append(f"evidence:{eid}")

        # Claim manifest link + fingerprint + base/head.
        manifest = self._claims.get(tenant_id, chain.claim_manifest_ref)
        if manifest is None:
            issues.append("missing claim manifest")
        else:
            if manifest.tenant_id != tenant_id:
                return ReconstructionResult(
                    ReconstructionState.TENANT_MISMATCH, chain_id,
                    issues=("claim manifest tenant mismatch",))
            if manifest.fingerprint != chain.claim_manifest_fingerprint:
                return ReconstructionResult(
                    ReconstructionState.INTEGRITY_FAILURE, chain_id,
                    issues=("claim manifest fingerprint mismatch",))
            if manifest.head_sha != chain.head_sha or manifest.base_sha != chain.base_sha:
                issues.append("claim manifest base/head mismatch")
            else:
                verified.append("claim_manifest")

        # TAP results must be present for a complete chain.
        if not chain.tap_result_fingerprints:
            issues.append("no TAP result references")
        else:
            verified.append("tap_results")

        # Recommendation (optional link) — verify if referenced.
        if chain.recommendation_ref is not None:
            rec = self._recs.get(tenant_id, chain.recommendation_ref)
            if rec is None:
                issues.append("missing recommendation")
            elif rec.tenant_id != tenant_id:
                return ReconstructionResult(
                    ReconstructionState.TENANT_MISMATCH, chain_id,
                    issues=("recommendation tenant mismatch",))
            else:
                verified.append("recommendation")

        # Decision + CER linkage (mandatory).
        if not chain.decision_record_id:
            issues.append("missing DecisionRecord reference")
        else:
            verified.append("decision_record")
        if not chain.cer_id or not chain.cer_content_hash:
            issues.append("missing CER reference / content hash")
        else:
            verified.append("cer")

        # Prepared-action identity (mandatory).
        action = self._actions.get(tenant_id, chain.prepared_action_ref)
        if action is None:
            issues.append("missing prepared action")
        else:
            if action.fingerprint != chain.prepared_action_ref:
                return ReconstructionResult(
                    ReconstructionState.REFERENCE_MISMATCH, chain_id,
                    issues=("prepared action fingerprint mismatch",))
            if action.head_sha != chain.head_sha or action.base_sha != chain.base_sha:
                issues.append("prepared action base/head mismatch")
            else:
                verified.append("prepared_action")

        # ActionGate request/result linkage (mandatory).
        if not chain.action_request_fingerprint or not chain.action_result_fingerprint:
            issues.append("missing ActionGate request/result reference")
        else:
            verified.append("actiongate")

        if issues:
            # A base/head mismatch against a known current head is staleness,
            # not incompleteness.
            return ReconstructionResult(
                ReconstructionState.INCOMPLETE, chain_id,
                issues=tuple(issues), verified_links=tuple(verified))

        # Staleness: a fully-linked historical chain whose head is superseded.
        if current_head_sha is not None and chain.head_sha != current_head_sha:
            return ReconstructionResult(
                ReconstructionState.STALE, chain_id,
                issues=("chain head superseded by a newer revision",),
                verified_links=tuple(verified))

        return ReconstructionResult(
            ReconstructionState.COMPLETE, chain_id, verified_links=tuple(verified))


__all__ = ["ReconstructionResult", "ChainReconstructionService"]
