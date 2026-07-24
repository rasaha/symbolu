"""Phase 22 - Reviewer-readiness assessment.

Aggregates every dimension of the apparatus into one structured readiness verdict, mapped to the eight
allowed decisions. Each dimension is checked programmatically; the FIRST failing dimension (in the order
below) selects the decision, so the assessment names a concrete thing to fix rather than a vague "not
ready". If every dimension passes, the decision is REVIEWER-READY - WAITING FOR REAL REVIEWERS.

Crucially, "reviewer-ready" is a statement about the APPARATUS, not about human acceptance: human
validation stays NOT EVALUATED, the external pilot stays BLOCKED, production stays NOT READY. The
assessment never returns a decision implying real human validation. Deterministic, stdlib-only.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List

from reviewer_ready_pilot import (dataset, review_set_audit, simulated_workflow, verify_prior_artifacts,
                                  verify_evaluation_freeze)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DOCS = os.path.join(_ROOT, "docs", "reviewer_ready_pilot")

# the eight allowed decisions
D_READY = "REVIEWER-READY - WAITING FOR REAL REVIEWERS"
D_WORKFLOW = "REVIEW WORKFLOW NEEDS FIXES"
D_REVIEW_SET = "REVIEW SET NEEDS IMPROVEMENT"
D_GUIDE = "REVIEWER GUIDE NEEDS IMPROVEMENT"
D_METADATA = "SOURCE METADATA NEEDS IMPROVEMENT"
D_ARTIFACTS = "NOT ENOUGH ELIGIBLE ARTIFACTS"
D_PILOT = "INTERNAL PILOT NOT READY"
D_STOP = "DO NOT PROCEED"

_REQUIRED_GUIDE_DOCS = ["REVIEWER_GUIDE.md", "REVIEWER_QUICK_REFERENCE.md", "COMMON_REVIEW_ERRORS.md",
                        "REVIEW_DECISION_TREE.md", "REVIEWER_QUALIFICATION_PROTOCOL.md"]
_REQUIRED_PILOT_DOCS = ["REVIEWER_GOVERNANCE_PROTOCOL.md", "REVIEWER_ROLE_MODEL.md",
                        "REVIEWER_RECRUITMENT_PLAN.md", "REVIEWER_ONBOARDING_PLAN.md",
                        "ADJUDICATION_PROTOCOL.md", "REVIEW_AUDIT_SPEC.md",
                        "FUTURE_HUMAN_EVALUATION_PROTOCOL.md"]


@dataclass
class Dimension:
    key: str
    label: str
    passed: bool
    decision_if_failed: str
    detail: str = ""


@dataclass
class Readiness:
    decision: str
    dimensions: List[Dimension] = field(default_factory=list)
    human_validation: str = "NOT_EVALUATED"
    external_customer_pilot: str = "BLOCKED"
    production_readiness: str = "NOT_READY"

    def as_dict(self) -> Dict[str, Any]:
        return {"decision": self.decision, "human_validation": self.human_validation,
                "external_customer_pilot": self.external_customer_pilot,
                "production_readiness": self.production_readiness,
                "dimensions": [{"key": d.key, "label": d.label, "passed": d.passed,
                                "decision_if_failed": d.decision_if_failed, "detail": d.detail}
                               for d in self.dimensions]}


def _docs_present(names: List[str]) -> List[str]:
    return [n for n in names if not os.path.exists(os.path.join(_DOCS, n))]


def assess() -> Readiness:
    dims: List[Dimension] = []

    # D8 hard stop: any honesty invariant broken, or prior artifacts drifted
    prior_ok = verify_prior_artifacts.verify()
    cfg = verify_evaluation_freeze.FUTURE_EVAL_CONFIG
    honesty_ok = (prior_ok and cfg["human_validation"] == "NOT_EVALUATED"
                  and cfg["production_readiness"] == "NOT_READY"
                  and cfg["external_customer_pilot"].startswith("BLOCKED")
                  and cfg["policy_modified"] is False and cfg["enforcement"] == "DISABLED")
    dims.append(Dimension("honesty", "prior artifacts intact + honesty invariants hold", honesty_ok,
                          D_STOP, "" if honesty_ok else "an invariant or prior-artifact guard failed"))

    # eligible artifacts
    m = dataset.build()
    arts_ok = m["evidence_status"] == "SUFFICIENT" and m["counts"]["final_natural"] >= dataset.MIN_FINAL
    dims.append(Dimension("eligible_artifacts", ">= 75 natural eligible artifacts", arts_ok, D_ARTIFACTS,
                          f"{m['counts']['final_natural']} natural (min {dataset.MIN_FINAL})"))

    # source metadata: every natural item carries provenance + surface metadata
    missing_md = [i["artifact_id"] for i in m["final_review"]
                  if not i.get("synthetic") and not (i.get("source_path") and i.get("source_kind")
                                                     and i.get("risk_tier") and i.get("claim_family"))]
    dims.append(Dimension("source_metadata", "provenance + surface metadata on every natural item",
                          not missing_md, D_METADATA, f"{len(missing_md)} items missing metadata"))

    # reviewer guide + qualification docs
    missing_guide = _docs_present(_REQUIRED_GUIDE_DOCS)
    dims.append(Dimension("reviewer_guide", "reviewer guide + qualification materials present",
                          not missing_guide, D_GUIDE, f"missing: {missing_guide}"))

    # review set audit
    audit = review_set_audit.audit()
    dims.append(Dimension("review_set", "final review set audit passes", audit.status == "REVIEW_SET_OK",
                          D_REVIEW_SET, audit.status))

    # review workflow: simulated end-to-end run is well-formed (audit ok, no stop, mock excluded)
    sim = simulated_workflow.run(dataset.load_final(), limit=40)
    wf_ok = (sim["audit"]["workflow_ok"] and sim["audit"]["chain_ok"]
             and sim["all_records_mock"] and not sim["stop"]["should_stop"]
             and sim["metrics_on_real_records"]["status"] == "NOT_ENOUGH_HUMAN_EVIDENCE")
    dims.append(Dimension("review_workflow", "blinded workflow runs end-to-end and stays honest", wf_ok,
                          D_WORKFLOW, "audit/stop/mock-exclusion check"))

    # internal pilot docs (governance, roles, recruitment, onboarding, adjudication, audit, eval freeze)
    missing_pilot = _docs_present(_REQUIRED_PILOT_DOCS)
    freeze_ok = verify_evaluation_freeze.verify()
    pilot_ok = not missing_pilot and freeze_ok
    dims.append(Dimension("internal_pilot", "governance + plans + protocol freeze in place", pilot_ok,
                          D_PILOT, f"missing: {missing_pilot}; freeze_ok={freeze_ok}"))

    # first failing dimension (in listed order) selects the decision
    decision = D_READY
    for d in dims:
        if not d.passed:
            decision = d.decision_if_failed
            break

    return Readiness(decision=decision, dimensions=dims)


if __name__ == "__main__":
    r = assess()
    print(f"DECISION: {r.decision}")
    for d in r.dimensions:
        print(f"  [{'PASS' if d.passed else 'FAIL'}] {d.key}: {d.label} - {d.detail}")
    print(f"human_validation={r.human_validation} external_pilot={r.external_customer_pilot} "
          f"production={r.production_readiness}")
