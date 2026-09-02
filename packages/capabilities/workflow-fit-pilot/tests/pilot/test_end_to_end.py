"""§8 row A26: the real pilot runner over the research harness's workflows, behind the
separate boundary process, with a stub provider. Emits only the outcomes its evidence
warrants. Skipped when the runtime tree cannot import (numpy)."""

from __future__ import annotations

import pathlib
import sys

import pytest

import pilot_fixtures as pf

REPO = pathlib.Path(__file__).resolve().parents[5]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
pytest.importorskip("agentic.agentic_framework.reasoning_workflows")
from experiments.workflow_fit_study.pilot_executor import HarnessWorkflowExecutor  # noqa: E402
from ugence_reasoning_method_governance.api import FitOutcome  # noqa: E402
from ugence_workflow_fit_pilot.api import render, run_pilot, validate_lineage  # noqa: E402


def test_a26_real_workflows_behind_the_boundary():
    m = pf.manifest()
    adv = pf.advisory(m.plan.task_class)
    res = run_pilot(m, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=adv, cases=pf.cases(), executor=HarnessWorkflowExecutor(max_llm_calls=12), scorer=pf.KeywordScorer(),
                    identity=pf.IDENTITY, provider_factory="stub_provider:make_provider", now=pf.clock(), boundary_env=pf.boundary_env())
    assert all(r.complete for r in res.runs), [(r.method.method_id, r.reasons) for r in res.runs]
    assert len(res.runs) == 7 and len({r.record.record_digest for r in res.runs}) == 7 and len({r.observation.observation_digest for r in res.runs}) == 7
    assert res.result.authority_resolution_basis == "REQUESTER_ASSERTED"
    warranted = set(res.outcomes.values())
    assert warranted <= set(FitOutcome) and FitOutcome.COMPARISON_EVIDENCE_ABSENT not in warranted
    assert all(r.record.telemetry.llm_calls == r.diagnostics.harness_observed_calls for r in res.runs)
    validate_lineage(res.states, [m])
    text = render(res)
    assert "authority_resolution_basis=REQUESTER_ASSERTED" in text and "SUMMARY:" in text
    # A second run reproduces the same captured telemetry, quality and outcomes. Capture
    # fingerprints carry the boundary's own instants, so record digests legitimately differ.
    res2 = run_pilot(m, catalog=pf.catalog(), rule_set=pf.rule_set(), advisory=adv, cases=pf.cases(), executor=HarnessWorkflowExecutor(max_llm_calls=12), scorer=pf.KeywordScorer(),
                     identity=pf.IDENTITY, provider_factory="stub_provider:make_provider", now=pf.clock(), boundary_env=pf.boundary_env())
    key = lambda res_: {r.method.method_id: (r.record.telemetry.llm_calls, r.record.telemetry.token_usage.total_tokens, r.quality_result.value) for r in res_.runs}
    assert key(res) == key(res2) and res.outcomes == res2.outcomes
