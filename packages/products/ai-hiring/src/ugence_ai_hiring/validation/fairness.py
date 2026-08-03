"""Fairness analysis (H5) — read-only, analysis-only, no enforcement.

Computes descriptive rate metrics grouped by an **analysis-only** group label that is
joined separately and never enters the operational pipeline. Produces small-sample
warnings and disciplined interpretation wording. This module never alters outcomes,
never enforces quotas, never infers protected attributes, and never labels the system
"fair"/"unfair"/"compliant".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .lifecycle import CaseRun

MIN_GROUP_SIZE = 10  # below this, findings are descriptive only


@dataclass
class GroupMetrics:
    group: str
    n: int
    advancement_rate: float
    hold_rate: float
    reject_rate: float
    review_ready_rate: float
    override_rate: float
    authorization_denial_rate: float
    execution_failure_rate: float
    reconciliation_mismatch_rate: float
    small_sample: bool


@dataclass
class FairnessReport:
    groups: tuple[GroupMetrics, ...] = ()
    warnings: tuple[str, ...] = ()
    interpretation: str = ""


def _rate(items, pred) -> float:
    items = list(items)
    return round(sum(1 for x in items if pred(x)) / len(items), 4) if items else 0.0


def analyze(runs: list[CaseRun]) -> FairnessReport:
    by_group: dict[str, list[CaseRun]] = {}
    for r in runs:
        by_group.setdefault(r.spec.group_label or "UNLABELED", []).append(r)

    groups = []
    warnings = []
    for g, rs in sorted(by_group.items()):
        n = len(rs)
        small = n < MIN_GROUP_SIZE
        if small:
            warnings.append(f"group '{g}' n={n} < {MIN_GROUP_SIZE}: descriptive only, not a conclusion")
        groups.append(GroupMetrics(
            group=g, n=n,
            advancement_rate=_rate(rs, lambda r: r.decision_outcome == "ADVANCE"),
            hold_rate=_rate(rs, lambda r: r.decision_outcome == "HOLD"),
            reject_rate=_rate(rs, lambda r: r.decision_outcome == "REJECT"),
            review_ready_rate=_rate(rs, lambda r: r.recommendation_status == "READY_FOR_HUMAN_REVIEW"),
            override_rate=_rate(rs, lambda r: r.override),
            authorization_denial_rate=_rate(rs, lambda r: r.authorization_outcome == "DENIED"),
            execution_failure_rate=_rate(rs, lambda r: r.proposal_status == "EXECUTION_FAILED"),
            reconciliation_mismatch_rate=_rate(rs, lambda r: r.reconciliation_outcome in ("MISMATCHED", "DUPLICATE_EXECUTION")),
            small_sample=small))

    # Disciplined interpretation: never conclude "fair"/"unfair" from a bounded cohort.
    labeled = [g for g in groups if g.group != "UNLABELED"]
    if len(labeled) >= 2 and all(not g.small_sample for g in labeled):
        spread = max(g.advancement_rate for g in labeled) - min(g.advancement_rate for g in labeled)
        interpretation = (
            "No material disparity was detected in this bounded validation cohort."
            if spread < 0.2 else
            "A disparity was observed and requires further investigation; causality was not established.")
    else:
        interpretation = ("Cohort too small for a statistically supported fairness conclusion; "
                          "findings are descriptive only.")
    return FairnessReport(groups=tuple(groups), warnings=tuple(warnings), interpretation=interpretation)


def counterfactual_invariance(env_factory, base_spec, group_labels: tuple[str, ...]) -> bool:
    """The operational recommendation inputs must be identical when only the
    analysis-only group label / protected attributes change. Returns True iff the
    evidence-package fingerprint (the governed input) is identical across variants."""
    from .lifecycle import CaseSpec, run_lifecycle
    fingerprints = set()
    # Hold the case (and thus its evidence) fixed; vary ONLY the analysis-only label,
    # using a fresh env per variant so the identical case id does not collide.
    for g in group_labels:
        env = env_factory()
        spec = CaseSpec(**{**base_spec.__dict__, "group_label": g, "protected_attributes": {"group": g}})
        run = run_lifecycle(env, spec)
        fingerprints.add(run.package_fingerprint)
    return len(fingerprints) == 1
