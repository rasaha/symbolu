"""Sample end-to-end shadow workflows for the console.

The prototype anchors on the platform's primary commercial wedge (First Look §3;
Productization Roadmap §4): an enterprise **Kubernetes / infrastructure agent**
proposing a high-consequence write. Three variants exercise the non-compensatory
gates — a clean allow, an operational HOLD, and an unsupported assertion.
"""

from __future__ import annotations

from .models import (
    ActionRequest,
    AssertionRequest,
    ContextUnit,
    DeploymentMode,
    GovernedLoopRequest,
    OperationalSignals,
)


def _base_context() -> list[ContextUnit]:
    return [
        ContextUnit(id="u1", text="Deployment payments-api runs in namespace prod.",
                    protected=True),
        ContextUnit(id="u2", text="Prometheus shows 3 healthy replicas for payments-api.",
                    redundancy_set="replicas"),
        ContextUnit(id="u3", text="prometheus reports three healthy payments-api replicas",
                    redundancy_set="replicas"),  # redundant duplicate of u2
        ContextUnit(id="u4", text="PagerDuty shows no active incidents for the prod cluster."),
    ]


SCENARIOS: dict[str, dict] = {
    "k8s_rollout_restart_clean": {
        "title": "K8s rollout restart — clean shadow allow",
        "description": "SRE-authorized rolling restart with supported evidence and a healthy cluster.",
        "request": GovernedLoopRequest(
            mode=DeploymentMode.SHADOW,
            context_units=_base_context(),
            assertion=AssertionRequest(
                assertion="payments-api has 3 healthy replicas and no active incidents.",
                assertion_type="operational_state",
                evidence_refs=["evidence:prometheus-snapshot", "evidence:pagerduty-clear"],
                source_identity="agent:infra-bot",
                policy_refs=["policy:k8s-prod-writes"],
            ),
            action=ActionRequest(
                action_type="k8s.rollout_restart",
                requested_parameters={"namespace": "prod", "name": "payments-api"},
                actor="agent:infra-bot", authority_context="sre-oncall",
                target_resource="prod/payments-api",
                policy_refs=["policy:k8s-prod-writes"],
                risk_context={"blast_radius": "medium", "environment": "production"},
                evidence_refs=["evidence:prometheus-snapshot"],
            ),
            operational_signals=OperationalSignals(
                error_budget_remaining=0.65, cluster_health="green",
                change_freeze_active=False),
        ),
    },
    "k8s_delete_during_freeze": {
        "title": "K8s delete during change freeze — operational HOLD",
        "description": "Authorized deletion, but a change-freeze window is active and the "
                       "error budget is nearly exhausted — ACP holds it.",
        "request": GovernedLoopRequest(
            mode=DeploymentMode.SHADOW,
            context_units=_base_context(),
            assertion=AssertionRequest(
                assertion="payments-api has 3 healthy replicas and no active incidents.",
                assertion_type="operational_state",
                evidence_refs=["evidence:prometheus-snapshot", "evidence:pagerduty-clear"],
                source_identity="agent:infra-bot",
                policy_refs=["policy:k8s-prod-writes"],
            ),
            action=ActionRequest(
                action_type="k8s.delete_deployment",
                requested_parameters={"namespace": "prod", "name": "payments-api"},
                actor="agent:infra-bot", authority_context="sre-oncall",
                target_resource="prod/payments-api",
                policy_refs=["policy:k8s-prod-writes"],
                risk_context={"blast_radius": "high", "environment": "production"},
                evidence_refs=["evidence:prometheus-snapshot"],
            ),
            operational_signals=OperationalSignals(
                error_budget_remaining=0.04, cluster_health="yellow",
                change_freeze_active=True),
        ),
    },
    "k8s_unsupported_claim": {
        "title": "K8s scale-up on an unsupported claim — Truth & Evidence gate",
        "description": "The agent asserts state it cannot back with evidence; TAP flags it "
                       "before the action is relied upon.",
        "request": GovernedLoopRequest(
            mode=DeploymentMode.SHADOW,
            context_units=_base_context(),
            assertion=AssertionRequest(
                assertion="Traffic will triple within the hour so 12 replicas are required.",
                assertion_type="forecast",
                evidence_refs=[],  # no evidence supplied
                source_identity="agent:infra-bot",
                policy_refs=["policy:k8s-prod-writes"],
            ),
            action=ActionRequest(
                action_type="k8s.scale_deployment",
                requested_parameters={"namespace": "prod", "name": "payments-api",
                                      "replicas": "12"},
                actor="agent:infra-bot", authority_context="sre-oncall",
                target_resource="prod/payments-api",
                policy_refs=["policy:k8s-prod-writes"],
                risk_context={"blast_radius": "medium", "environment": "production"},
            ),
            operational_signals=OperationalSignals(
                error_budget_remaining=0.65, cluster_health="green",
                change_freeze_active=False),
        ),
    },
}


def summaries() -> list[dict]:
    return [
        {"id": sid, "title": s["title"], "description": s["description"]}
        for sid, s in SCENARIOS.items()
    ]
