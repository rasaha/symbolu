"""AWC orchestration service (§1, §4, §20).

This is the ONLY place the API touches the domain, and it is a THIN orchestration
layer: every step delegates to a public ``ugence_agent_workforce_composer.api``
function. It contains no eligibility, ranking, composition, permission, fallback,
replay or comparison logic of its own — it merely sequences the public calls in
the exact order the frozen P3A generator uses, so scenario execution reproduces
the committed fingerprints byte-for-byte.

The what-if operations (§15) build typed, bounded modifications of *copies* of the
frozen inputs and re-run the same public pipeline; they never mutate committed
fixtures and never evaluate arbitrary expressions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import ugence_agent_workforce_composer.api as awc
from ugence_agent_workforce_composer.fingerprint import stamp_fingerprint

WORKFLOW_IR_V1 = "workflow_ir.v1"
WORKFLOW_IR_V2 = "workflow_ir.v2"

# Contract pair used when building replay records (matches the P3A generator).
_CONTRACTS: Tuple[str, str] = (awc.CONTRACT_VERSION, awc.COMPOSITION_CONTRACT_VERSION)


# --------------------------------------------------------------------------- #
# result container
# --------------------------------------------------------------------------- #
@dataclass
class PipelineResult:
    adaptation: Any
    eligibility: Any
    role_reports: Dict[str, Any]
    rankings: Tuple[Any, ...]
    dependency_graph: Any
    composition: Any
    plan: Any
    replay: Any

    def fingerprints(self) -> dict:
        plan = self.plan
        return {
            "adaptation_fingerprint": self.adaptation.adaptation_fingerprint,
            "workflow_eligibility_fingerprint": self.eligibility.workflow_fingerprint,
            "composition_fingerprint": self.composition.composition_fingerprint,
            "plan_fingerprint": plan.plan_fingerprint,
            "plan_id": plan.plan_id,
            "plan_state": plan.plan_state.value,
            "replay_fingerprint": self.replay.replay_fingerprint,
            "expected_plan_fingerprint": self.replay.expected_plan_fingerprint,
        }


class AwcOrchestrationService:
    """Sequences public AWC calls. Stateless: safe to share across requests."""

    # -- adaptation ------------------------------------------------------- #
    def declared_contract_version(self, document: Dict[str, Any]) -> str:
        return awc.declared_contract_version(document)

    def adapt(
        self,
        document: Dict[str, Any],
        *,
        contract_version: Optional[str] = None,
        role_overlay: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Dispatch adaptation EXPLICITLY by declared contract version (§9).

        Returns the uniform :class:`AdaptationResultV2` envelope. Unknown versions
        fail closed inside AWC (``ok=False`` with a typed diagnostic).
        """
        return awc.adapt_workflow(
            document, contract_version=contract_version, role_overlay=role_overlay
        )

    def adapt_v1_frozen(self, workflow: Dict[str, Any], overlay: Dict[str, Any]) -> Any:
        """The frozen v1 adaptation used by the built-in scenario pipeline —
        byte-identical to the P3A generator's ``adapt_compiled_workflow``."""
        return awc.adapt_compiled_workflow(workflow, role_overlay=overlay)

    # -- eligibility / ranking / composition ------------------------------ #
    def evaluate_eligibility(
        self, adaptation, registry, enterprise, eligibility, logical_time: float
    ):
        workflow_result = awc.evaluate_workflow_eligibility(
            adaptation, registry, enterprise, eligibility, logical_time
        )
        roles = self._sorted_roles(adaptation)
        reports = {
            r.role_id: awc.evaluate_registry_for_role(
                r, registry, enterprise, eligibility, logical_time
            )
            for r in roles
        }
        return workflow_result, reports

    def rank(self, adaptation, reports, registry, ranking_policy, logical_time: float):
        roles = self._sorted_roles(adaptation)
        return tuple(
            awc.rank_eligible_candidates(
                r, reports[r.role_id], registry, ranking_policy, logical_time
            )
            for r in roles
        )

    def compose(
        self,
        adaptation,
        rankings,
        registry,
        enterprise,
        composition_policy,
        permission_policy,
        *,
        eligibility_policy,
        ranking_policy,
    ):
        roles = self._sorted_roles(adaptation)
        dep_graph = awc.build_role_dependency_graph(roles)
        composition = awc.compose_agent_team(
            roles,
            rankings,
            registry,
            enterprise,
            composition_policy,
            permission_policy,
            dep_graph,
            eligibility_policy_digest=eligibility_policy.policy_digest,
            ranking_policy_digest=ranking_policy.policy_digest,
            workflow_fingerprint=adaptation.adaptation_fingerprint,
        )
        return composition, dep_graph

    @staticmethod
    def _sorted_roles(adaptation) -> Tuple[Any, ...]:
        return tuple(sorted(adaptation.role_requirements, key=lambda r: r.role_id))

    # -- full pipeline (mirrors generate_fixtures._run_pipeline) ---------- #
    def run_pipeline(self, s: Dict[str, Any], logical_time: float) -> PipelineResult:
        workflow, overlay = s["workflow"], s["overlay"]
        reg, ent, elig = s["registry"], s["enterprise_policy"], s["eligibility_policy"]
        rank_p, comp_p = s["ranking_policy"], s["composition_policy"]
        perm_p, fb_p = s["permission_policy"], s["fallback_policy"]

        adaptation = awc.adapt_compiled_workflow(workflow, role_overlay=overlay)
        eligibility, reports = self.evaluate_eligibility(adaptation, reg, ent, elig, logical_time)
        rankings = self.rank(adaptation, reports, reg, rank_p, logical_time)
        composition, dep_graph = self.compose(
            adaptation, rankings, reg, ent, comp_p, perm_p,
            eligibility_policy=elig, ranking_policy=rank_p,
        )

        plan = awc.build_agent_team_plan(
            adaptation, reg, ent, elig, rank_p, comp_p, perm_p, fb_p, logical_time
        )
        replay = awc.build_replay_record(plan, adaptation, logical_time, _CONTRACTS)
        # Prove the plan replays to an identical fingerprint before returning it.
        awc.replay_agent_team_plan(
            adaptation, reg, ent, elig, rank_p, comp_p, perm_p, fb_p, logical_time, expected=plan
        )

        return PipelineResult(
            adaptation=adaptation,
            eligibility=eligibility,
            role_reports=reports,
            rankings=rankings,
            dependency_graph=dep_graph,
            composition=composition,
            plan=plan,
            replay=replay,
        )

    # -- replay / comparison --------------------------------------------- #
    def replay_from_scenario(self, s: Dict[str, Any], logical_time: float, expected_plan):
        adaptation = awc.adapt_compiled_workflow(s["workflow"], role_overlay=s["overlay"])
        return awc.replay_agent_team_plan(
            adaptation, s["registry"], s["enterprise_policy"], s["eligibility_policy"],
            s["ranking_policy"], s["composition_policy"], s["permission_policy"],
            s["fallback_policy"], logical_time, expected=expected_plan,
        )

    def compare_plans(self, plan_a, plan_b):
        return awc.compare_agent_team_plans(plan_a, plan_b)

    def compare_adaptations(self, v1_env, v2_env):
        return awc.compare_adaptations(v1_env, v2_env)

    # -- v1/v2 conformance ------------------------------------------------ #
    def run_v1v2_comparison(self, v2s: Dict[str, Any], logical_time: float) -> Dict[str, Any]:
        """Adapt the same logical workflow via v1 (full overlay) and v2 (reduced
        overlay) and classify equivalence — delegated entirely to AWC."""
        v1_env = awc.adapt_workflow(
            v2s["v1_workflow"], contract_version=WORKFLOW_IR_V1, role_overlay=v2s["v1_overlay"]
        )
        v2_env = awc.adapt_workflow(
            v2s["v2_workflow"], contract_version=WORKFLOW_IR_V2, role_overlay=v2s["v2_overlay"]
        )
        report = awc.compare_adaptations(v1_env, v2_env)
        return {"v1_env": v1_env, "v2_env": v2_env, "report": report}

    # -- what-if perturbations (§15) ------------------------------------- #
    SUPPORTED_PERTURBATIONS: Tuple[str, ...] = (
        "FORBID_PROVIDER",
        "REQUIRE_RESIDENCY",
        "TIGHTEN_COST_CEILING",
        "TIGHTEN_LATENCY_CEILING",
        "REVOKE_AGENT_VERSION",
        "EXPIRE_EVIDENCE",
        "TIGHTEN_PERMISSION_POLICY",
        "TIGHTEN_PROVIDER_CONCENTRATION",
        "REMOVE_CANDIDATE",
    )

    def apply_perturbation(
        self, s: Dict[str, Any], operation: str, params: Dict[str, Any], logical_time: float
    ) -> Tuple[Dict[str, Any], float, Dict[str, Any]]:
        """Return (modified_inputs_copy, effective_logical_time, applied_detail).

        Operates on a shallow copy of the loaded input dict; each mutated policy /
        registry is rebuilt as a NEW object, so the caller's committed fixtures are
        untouched. Unsupported operations raise ``ValueError``.
        """
        if operation not in self.SUPPORTED_PERTURBATIONS:
            raise ValueError(f"unsupported perturbation {operation!r}")
        m = dict(s)  # shallow copy; individual keys replaced with new objects
        effective_time = logical_time
        applied: Dict[str, Any] = {"operation": operation, "params": dict(params)}

        if operation == "FORBID_PROVIDER":
            provider = str(params["provider"])
            ent = s["enterprise_policy"]
            m["enterprise_policy"] = awc.finalize_enterprise_policy(
                ent.model_copy(update={
                    "forbidden_providers": tuple(ent.forbidden_providers) + (provider,),
                    "policy_digest": "",
                })
            )
        elif operation == "REQUIRE_RESIDENCY":
            residency = str(params["residency"])
            ent = s["enterprise_policy"]
            m["enterprise_policy"] = awc.finalize_enterprise_policy(
                ent.model_copy(update={
                    "required_residencies": tuple(ent.required_residencies) + (residency,),
                    "allowed_residencies": (residency,),
                    "policy_digest": "",
                })
            )
        elif operation == "TIGHTEN_COST_CEILING":
            ceiling = float(params["ceiling"])
            m["composition_policy"] = self._restamp(
                s["composition_policy"], {"team_cost_hard_ceiling": ceiling}
            )
        elif operation == "TIGHTEN_LATENCY_CEILING":
            ceiling = float(params["ceiling"])
            m["composition_policy"] = self._restamp(
                s["composition_policy"], {"team_latency_hard_ceiling": ceiling}
            )
        elif operation == "REVOKE_AGENT_VERSION":
            agent_ref = str(params["agent_version"])
            ent = s["enterprise_policy"]
            m["enterprise_policy"] = awc.finalize_enterprise_policy(
                ent.model_copy(update={
                    "forbidden_agent_versions": tuple(ent.forbidden_agent_versions) + (agent_ref,),
                    "policy_digest": "",
                })
            )
        elif operation == "EXPIRE_EVIDENCE":
            effective_time = float(params.get("at", 3_000_000.0))
            applied["effective_logical_time"] = effective_time
        elif operation == "TIGHTEN_PERMISSION_POLICY":
            permission = str(params["permission"])
            perm = s["permission_policy"]
            owned = tuple(getattr(perm, "governance_owned_permissions", ())) + (permission,)
            m["permission_policy"] = self._restamp(perm, {"governance_owned_permissions": owned})
        elif operation == "TIGHTEN_PROVIDER_CONCENTRATION":
            pct = int(params["limit_pct"])
            m["composition_policy"] = self._restamp(
                s["composition_policy"], {"provider_concentration_limit_pct": pct}
            )
        elif operation == "REMOVE_CANDIDATE":
            agent_id = str(params["agent_id"])
            agent_version = str(params.get("agent_version", ""))
            m["registry"] = self._remove_candidate(s["registry"], agent_id, agent_version, logical_time)
        return m, effective_time, applied

    @staticmethod
    def _restamp(policy, update: Dict[str, Any]):
        payload = dict(update)
        payload["policy_digest"] = ""
        return stamp_fingerprint(policy.model_copy(update=payload), "policy_digest")

    @staticmethod
    def _remove_candidate(snapshot, agent_id: str, agent_version: str, logical_time: float):
        removed = (agent_id, agent_version)

        def _match(item) -> bool:
            if agent_version:
                return (item.agent_id, item.agent_version) == removed
            return item.agent_id == agent_id

        profiles = [p for p in snapshot.agent_profiles if not _match(p)]
        evidence = [e for e in snapshot.capability_evidence if not _match(e)]
        return awc.build_registry_snapshot(
            snapshot_id=f"{snapshot.snapshot_id}_whatif",
            registry_version=snapshot.registry_version,
            logical_time=logical_time,
            agent_profiles=profiles,
            capability_evidence=evidence,
            provenance=awc.Provenance(source_kind="what_if_perturbation", synthetic=True),
        )
