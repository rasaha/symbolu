"""Scenario execution, verification, workflow projection and export (§8, §16, §20).

The built-in scenario endpoints ALWAYS execute the real AWC pipeline through
:class:`AwcOrchestrationService` and then verify the observed fingerprints against
the frozen expected oracles. Frozen expected outputs are verification oracles,
never runtime replacements.
"""
from __future__ import annotations

from typing import Any, Dict

from ..scenarios.catalog import LOGICAL_TIME, ScenarioCatalog
from ..serialization.canonical import to_jsonable
from .orchestration import AwcOrchestrationService


class ScenarioService:
    def __init__(self, catalog: ScenarioCatalog, orchestration: AwcOrchestrationService):
        self._catalog = catalog
        self._orchestration = orchestration

    # -- execution + verification ---------------------------------------- #
    def run(self, scenario_id: str, logical_time: float | None = None):
        lt = LOGICAL_TIME if logical_time is None else logical_time
        inputs = self._catalog.inputs(scenario_id)
        return self._orchestration.run_pipeline(inputs, lt), lt

    def verify(self, scenario_id: str, pipeline) -> Dict[str, Any]:
        observed = pipeline.fingerprints()
        expected = self._catalog.expected_fingerprints(scenario_id)
        keys = [
            "adaptation_fingerprint", "workflow_eligibility_fingerprint",
            "composition_fingerprint", "plan_fingerprint", "replay_fingerprint",
        ]
        per_artifact = {k: {"expected": expected.get(k), "observed": observed.get(k),
                            "match": expected.get(k) == observed.get(k)} for k in keys}
        return {
            "expected_fingerprint": expected.get("plan_fingerprint"),
            "observed_fingerprint": observed.get("plan_fingerprint"),
            "match": all(v["match"] for v in per_artifact.values()),
            "per_artifact": per_artifact,
        }

    # -- workflow projection --------------------------------------------- #
    def workflow_projection(self, scenario_id: str) -> Dict[str, Any]:
        raw = self._catalog.raw_workflow(scenario_id)
        ir = raw.get("workflow_ir", raw)
        pipeline, _ = self.run(scenario_id)
        adaptation = pipeline.adaptation
        return {
            "scenario_id": scenario_id,
            "workflow_identity": adaptation.workflow_identity,
            "workflow_version": adaptation.workflow_version,
            "contract_version": adaptation.source_contract_version,
            "source_package_digest": adaptation.source_package_digest,
            "ir_version": ir.get("ir_version"),
            "nodes": ir.get("nodes", []),
            "edges": ir.get("edges", []),
            "structural_digest": raw.get("structural_digest"),
            "node_dispositions": to_jsonable(adaptation.node_dispositions),
            "role_requirements": to_jsonable(adaptation.role_requirements),
            "non_agent_dispositions": to_jsonable(adaptation.non_agent_dispositions),
            "adaptation_fingerprint": adaptation.adaptation_fingerprint,
        }

    # -- export bundle (§16) --------------------------------------------- #
    def export_bundle(self, scenario_id: str) -> Dict[str, Any]:
        inputs = self._catalog.inputs(scenario_id)
        pipeline, lt = self.run(scenario_id)
        rankings = [r for r in pipeline.rankings]
        return {
            "schema": "governance_studio.export_bundle.v1",
            "scenario_id": scenario_id,
            "synthetic_data_notice": {
                "synthetic": True, "planning_only": True,
                "no_agent_execution": True, "no_permission_grant": True,
            },
            "logical_time": lt,
            "scenario_manifest": self._catalog.scenario_manifest(scenario_id),
            "workflow": inputs["workflow"],
            "overlay": inputs["overlay"],
            "registry_snapshot": to_jsonable(inputs["registry"]),
            "policies": {
                "enterprise_policy": to_jsonable(inputs["enterprise_policy"]),
                "eligibility_policy": to_jsonable(inputs["eligibility_policy"]),
                "ranking_policy": to_jsonable(inputs["ranking_policy"]),
                "composition_policy": to_jsonable(inputs["composition_policy"]),
                "permission_policy": to_jsonable(inputs["permission_policy"]),
                "fallback_policy": to_jsonable(inputs["fallback_policy"]),
            },
            "adaptation": to_jsonable(pipeline.adaptation),
            "eligibility_reports": to_jsonable(list(pipeline.role_reports.values())),
            "workflow_eligibility": to_jsonable(pipeline.eligibility),
            "rankings": to_jsonable(rankings),
            "composition": to_jsonable(pipeline.composition),
            "permission_bound_proposals": to_jsonable(pipeline.plan.permission_bound_proposals),
            "fallback_plans": to_jsonable(pipeline.plan.role_fallback_plans),
            "agent_team_plan": to_jsonable(pipeline.plan),
            "replay_record": to_jsonable(pipeline.replay),
            "fingerprint_manifest": pipeline.fingerprints(),
        }
