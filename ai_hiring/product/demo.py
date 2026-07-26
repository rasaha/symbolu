"""Safe, canonical demo (H6 §9–§10).

Runs a small, curated, fully-deterministic hiring cohort end to end and returns a
structured result plus a ready-to-print accountability report for one advanced
case. "Safe" means, and is asserted to mean:

- Deterministic simulation only — every external effect goes through an in-memory
  adapter. There are **no** production HRIS writes, emails, calendar invites,
  payroll changes, or identity provisioning.
- No network, no filesystem writes, no vendor SDKs.
- Reproducible — the same inputs produce the same outputs and the same report.

The demo demonstrates the governed lifecycle and the accountability record; it is
not a benchmark and makes no scale, quality, or fairness claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from governance_providers.contracts import AssertionCoverage

from ..actions.action_types import HiringActionType
from ..governance.outcomes import HiringDecisionIntent
from ..validation.lifecycle import CaseRun, CaseSpec
from .accountability import AccountabilityReport, build_accountability_report
from .composition import HiringProduct, build_demo_platform


def canonical_cohort() -> list[CaseSpec]:
    """A minimal, branch-illustrating cohort for the demo (synthetic only).

    Covers: a normal advance, a hold, a reject→close, an unsupported-claim case
    that stays in review, and an authorization denial — enough to show the
    governed branches without the full validation pilot.
    """
    return [
        CaseSpec(case_id="demo-advance"),
        CaseSpec(
            case_id="demo-hold",
            decision_intent=HiringDecisionIntent.HOLD,
            action_type=HiringActionType.PLACE_ON_HOLD,
        ),
        CaseSpec(
            case_id="demo-reject",
            decision_intent=HiringDecisionIntent.REJECT,
            action_type=HiringActionType.CLOSE_WITHOUT_SELECTION,
        ),
        CaseSpec(
            case_id="demo-review",
            assertion_coverage=AssertionCoverage.UNSUPPORTED,
            decision_intent=None,
            action_type=None,
        ),
        CaseSpec(
            case_id="demo-denied",
            action_denied=frozenset({"ADVANCE_STAGE"}),
        ),
    ]


@dataclass
class DemoResult:
    product_version: str
    runs: list[CaseRun] = field(default_factory=list)
    sample_report: AccountabilityReport | None = None

    def summary(self) -> list[dict]:
        return [
            {
                "case_id": r.spec.case_id,
                "reached_stage": r.reached_stage,
                "recommendation_status": r.recommendation_status,
                "decision_outcome": r.decision_outcome,
                "authorization_outcome": r.authorization_outcome,
                "proposal_status": r.proposal_status,
                "reconciliation_outcome": r.reconciliation_outcome,
            }
            for r in self.runs
        ]


def run_demo(product: HiringProduct | None = None) -> DemoResult:
    """Run the canonical cohort and build a sample accountability report.

    Constructs the fixed demo product when none is supplied. Entirely in-memory
    and deterministic.
    """
    product = product or build_demo_platform()
    runs = [product.run_case(spec) for spec in canonical_cohort()]

    sample_report = None
    for r in runs:
        if r.action_proposal_id and r.reconciliation_outcome == "MATCHED":
            sample_report = build_accountability_report(product, r.action_proposal_id)
            break

    from .version import PRODUCT_VERSION

    return DemoResult(product_version=PRODUCT_VERSION, runs=runs, sample_report=sample_report)
