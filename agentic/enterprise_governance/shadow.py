"""
Shadow-mode evaluator: observe → evaluate → emit findings → compare to the strong
existing-controls baseline. No automated denial. Reports operational-value
metrics including shared-invariant reuse across workflows.
"""

from __future__ import annotations

from typing import Dict, List

from agentic.enterprise_governance.baseline import StrongControlsBaseline
from agentic.enterprise_governance.invariants import INVARIANTS, run_invariants
from agentic.enterprise_governance.model import EvidenceStatus, WorkflowEvidence


class ShadowEvaluator:
    def __init__(self, baseline: StrongControlsBaseline | None = None):
        self.baseline = baseline or StrongControlsBaseline()

    def evaluate_workflow(self, wf: WorkflowEvidence) -> Dict:
        findings = run_invariants(wf)
        baseline_codes = self.baseline.catches(wf)
        net_new = [f for f in findings if f.failure_code not in baseline_codes]
        duplicate = [f for f in findings if f.failure_code in baseline_codes]
        total_ev = len(wf.evidence) or 1
        missing_ev = sum(1 for e in wf.evidence if e.status == EvidenceStatus.MISSING)
        disposition = {}
        promotion = {}
        for f in net_new:
            disposition[f.disposition.value] = disposition.get(f.disposition.value, 0) + 1
            promotion[f.default_promotion.value] = promotion.get(
                f.default_promotion.value, 0) + 1
        return {
            "workflow": wf.workflow_id,
            "workflow_type": wf.workflow_type,
            "total_findings": len(findings),
            "net_new_findings": len(net_new),
            "net_new_codes": sorted({f.failure_code for f in net_new}),
            "duplicate_of_existing_controls": sorted({f.failure_code for f in duplicate}),
            "baseline_catches": sorted(baseline_codes),
            "missing_data_rate": round(missing_ev / total_ev, 3),
            "net_new_disposition": disposition,
            "net_new_default_promotion": promotion,
            "invariants_fired": sorted({f.invariant for f in findings}),
        }

    def evaluate(self, workflows: List[WorkflowEvidence],
                 clean_workflows: List[WorkflowEvidence] | None = None) -> Dict:
        per_wf = [self.evaluate_workflow(wf) for wf in workflows]

        # Shared-invariant reuse: invariants that fired (unchanged) in >= 2 workflows.
        fired_in: Dict[str, set] = {}
        for wf in workflows:
            for f in run_invariants(wf):
                fired_in.setdefault(f.invariant, set()).add(wf.workflow_id)
        reused = {inv: sorted(wfs) for inv, wfs in fired_in.items() if len(wfs) >= 2}

        # False positives from clean workflows.
        clean_workflows = clean_workflows or []
        clean_findings = sum(len(run_invariants(wf)) for wf in clean_workflows)

        total_findings = sum(w["total_findings"] for w in per_wf)
        total_net_new = sum(w["net_new_findings"] for w in per_wf)
        return {
            "per_workflow": per_wf,
            "workflows_governed_by_same_invariants": len(workflows),
            "invariants_total": len(INVARIANTS),
            "invariants_reused_across_workflows": reused,
            "shared_invariant_reuse_count": len(reused),
            "total_findings": total_findings,
            "total_net_new_findings": total_net_new,
            "net_new_ratio": round(total_net_new / total_findings, 3) if total_findings else 0.0,
            "clean_workflow_false_positives": clean_findings,
            "false_positive_rate": round(
                clean_findings / (clean_findings + total_findings), 4)
            if (clean_findings + total_findings) else 0.0,
        }


def shadow_report() -> Dict:
    from agentic.enterprise_governance.workflows import all_workflows
    ev = ShadowEvaluator()
    return ev.evaluate(all_workflows(clean=False), all_workflows(clean=True))
