"""
A STRONG existing-controls baseline (not the stage-1 naive per-vertical model).

It models what a mature enterprise realistically already runs — an approval
matrix, an ERP reconciliation job, a business-rule engine, and an IAM access
review — and is deliberately GENEROUS: it assumes those controls are present and
effective. A finding only counts as net-new if even this strong baseline would
not catch it.
"""

from __future__ import annotations

from typing import Set

from agentic.enterprise_governance.invariants import run_invariants
from agentic.enterprise_governance.model import WorkflowEvidence

# Failure codes a strong, realistic existing-controls stack already catches.
#   approval matrix        → MISSING_AUTHORITY_BASIS
#   ERP reconciliation job → STATE_RECONCILIATION_FAILURE
#   business-rule engine   → PROTECTED_INVARIANT_BREACH
#   IAM access review      → PROHIBITED_CAPABILITY_EXPOSURE
BASELINE_DETECTABLE: Set[str] = {
    "MISSING_AUTHORITY_BASIS",
    "STATE_RECONCILIATION_FAILURE",
    "PROTECTED_INVARIANT_BREACH",
    "PROHIBITED_CAPABILITY_EXPOSURE",
}


class StrongControlsBaseline:
    """Conservative model of existing enterprise controls."""

    detectable = BASELINE_DETECTABLE

    def catches(self, wf: WorkflowEvidence) -> Set[str]:
        return {f.failure_code for f in run_invariants(wf)
                if f.failure_code in self.detectable}
