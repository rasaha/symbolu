"""Deterministic pilot candidate selection.

Selection is bounded and explainable: it draws only from an explicitly supplied
candidate list (PR list, workflow-revision list, an approved read-only GitHub
listing constrained by repo+branch, or historical replay), never an organization-
wide scan. Every included/excluded candidate carries a reason code.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from ..fingerprints import domain_hash
from .manifest import PilotStudyManifest

DOMAIN_CANDIDATE_SELECTION = "cg.pilot_study.candidate_selection.v1"


@dataclass(frozen=True)
class PilotCandidate:
    """A candidate governed change offered for pilot evaluation."""

    repository: str
    target_branch: str
    pull_request_number: int
    workflow_id: str
    workflow_revision_id: str
    head_sha: str
    evidence_class: str  # PilotEvidenceClass value


@dataclass(frozen=True)
class PilotCandidateSelectionRecord:
    """Immutable record of a candidate selection with reason codes."""

    pilot_id: str
    tenant_id: str
    selection_method: str
    included: Tuple[Tuple[str, str], ...]  # (revision_id, evidence_class)
    excluded: Tuple[Tuple[str, str], ...]  # (revision_id, reason_code)

    @property
    def selection_fingerprint(self) -> str:
        return domain_hash(DOMAIN_CANDIDATE_SELECTION, {
            "pilot_id": self.pilot_id, "tenant_id": self.tenant_id,
            "selection_method": self.selection_method,
            "included": sorted([list(x) for x in self.included]),
            "excluded": sorted([list(x) for x in self.excluded])})

    @property
    def record_id(self) -> str:
        return f"candidate-selection:{self.pilot_id}:{self.selection_fingerprint[:16]}"


def select_pilot_candidates(
    manifest: PilotStudyManifest,
    candidates: List[PilotCandidate],
    *,
    already_evaluated: Tuple[str, ...] = (),
) -> Tuple[List[PilotCandidate], PilotCandidateSelectionRecord]:
    """Deterministically select candidates respecting the manifest scope + bounds."""
    included: List[PilotCandidate] = []
    included_pairs: List[Tuple[str, str]] = []
    excluded: List[Tuple[str, str]] = []
    seen = set(already_evaluated)
    cap = manifest.maximum_evaluations
    for c in candidates:
        rid = c.workflow_revision_id
        if c.repository not in manifest.allowed_repositories:
            excluded.append((rid, "repository_not_allowed")); continue
        if c.target_branch not in manifest.allowed_branches:
            excluded.append((rid, "branch_not_allowed")); continue
        if manifest.allowed_pull_request_numbers and \
                c.pull_request_number not in manifest.allowed_pull_request_numbers:
            excluded.append((rid, "pull_request_not_allowed")); continue
        if c.evidence_class not in manifest.evidence_classes_permitted:
            excluded.append((rid, "evidence_class_not_permitted")); continue
        if rid in seen:
            excluded.append((rid, "already_evaluated_or_duplicate")); continue
        if len(included) >= cap:
            excluded.append((rid, "maximum_count_reached")); continue
        seen.add(rid)
        included.append(c)
        included_pairs.append((rid, c.evidence_class))
    record = PilotCandidateSelectionRecord(
        pilot_id=manifest.pilot_id, tenant_id=manifest.tenant_id,
        selection_method=manifest.selection_method,
        included=tuple(included_pairs), excluded=tuple(excluded))
    return included, record


__all__ = ["PilotCandidate", "PilotCandidateSelectionRecord", "select_pilot_candidates"]
