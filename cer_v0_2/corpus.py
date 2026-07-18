"""CER V0.2 factorial corpus: {ugence, langgraph, openai-agents} x {scale, rollout}
plus the required cross-cutting cases. Deterministic.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional

from .actuation import EnvelopeContext, RolloutActuation, ScaleActuation
from .producers.langgraph_adapter import LangGraphCERAdapter
from .producers.openai_agents_adapter import OpenAIAgentsCERAdapter
from .producers.ugence import UgenceCERProducer

NOW = "2026-01-01T00:10:00.000Z"
FRESH = "2026-01-01T00:09:30.000Z"
STALE = "2026-01-01T00:00:00.000Z"

_UG = UgenceCERProducer()
_LG = LangGraphCERAdapter()
_OA = OpenAIAgentsCERAdapter()
RUNTIMES = {"ugence": _UG, "langgraph": _LG, "openai-agents": _OA}


def _op(**over):
    d = {"generation": 1, "desired_replicas": 10, "current_replicas": 10,
         "available_replicas": 10, "readiness_plasticity": 0.95,
         "active_rollback_watches": 0, "seconds_since_last_action": 600.0,
         "dependency_healthy": True, "freeze_active": False, "observation_time_s": 600.0}
    d.update(over)
    return d


def _ctx(**over) -> EnvelopeContext:
    base = EnvelopeContext(
        principal="agent:web-ops", permissions=("deploy",), delegator_id="sre",
        resource_version="1001", state_hash="sha-256:" + "ab" * 32, as_of=FRESH,
        operational=_op(), policy_version="1.0.0+abc", policy_digest="pd",
        correlation_id="protected/web")
    return replace(base, **over)


def _scale(**over):
    d = dict(cluster="fixture", namespace="protected", deployment="web",
             from_replicas=10, to_replicas=12)
    d.update(over)
    return ScaleActuation(**d)


def _rollout(**over):
    d = dict(cluster="fixture", namespace="protected", deployment="web",
             image_digest="sha256:" + "cd" * 32,
             current_manifest_digest="sha256:" + "ef" * 32, rollback_ref="web-rev-41")
    d.update(over)
    return RolloutActuation(**d)


def _all_three(ctx, act) -> Dict[str, dict]:
    return {name: p.propose(ctx, act) for name, p in RUNTIMES.items()}


@dataclass
class Case:
    case_id: str
    profile: Optional[str]
    description: str
    expect: str                       # "equal" | "different" | "invalid"
    cers: Dict[str, dict] = field(default_factory=dict)   # runtime -> CER
    base_ref: Optional[str] = None    # case_id whose digest to compare against
    expect_cp_class: Optional[str] = None
    malformed_cer: Optional[dict] = None
    stale: bool = False
    missing_evidence: bool = False
    policy_variant: bool = False
    bypass: bool = False
    observation: bool = False
    unsupported: bool = False
    notes: str = ""


def build_corpus() -> List[Case]:
    cases: List[Case] = []
    ctx = _ctx()

    # --- factorial valid base: 3 runtimes x 2 profiles (all-equal per profile) ---
    scale_base = _all_three(ctx, _scale())
    roll_base = _all_three(ctx, _rollout())
    cases.append(Case("01_scale_valid_all_runtimes", "kubernetes.scale.v1",
                      "Identical valid scale across ugence/langgraph/openai-agents",
                      "equal", cers=scale_base, expect_cp_class="PROCEED"))
    cases.append(Case("02_rollout_valid_all_runtimes", "kubernetes.rollout.v1",
                      "Identical valid rollout across all three runtimes",
                      "equal", cers=roll_base, expect_cp_class="PROCEED"))

    # --- different provenance / objective, same actuation -> equal ---
    cases.append(Case("03_scale_diff_provenance", "kubernetes.scale.v1",
                      "Same scale actuation; provenance differs across runtimes",
                      "equal", cers=scale_base))
    cases.append(Case("04_rollout_diff_objective", "kubernetes.rollout.v1",
                      "Same rollout; objective prose differs per runtime", "equal",
                      cers=roll_base))

    # --- changed target / argument / digest / strategy -> different from base ---
    cases.append(Case("05_scale_changed_target", "kubernetes.scale.v1",
                      "Scale target web->api", "different",
                      cers=_all_three(ctx, _scale(deployment="api")),
                      base_ref="01_scale_valid_all_runtimes"))
    cases.append(Case("06_scale_changed_replicas", "kubernetes.scale.v1",
                      "Scale replicas 12->13", "different",
                      cers=_all_three(ctx, _scale(to_replicas=13)),
                      base_ref="01_scale_valid_all_runtimes"))
    cases.append(Case("07_rollout_changed_image", "kubernetes.rollout.v1",
                      "Rollout image digest changed", "different",
                      cers=_all_three(ctx, _rollout(image_digest="sha256:" + "11" * 32)),
                      base_ref="02_rollout_valid_all_runtimes"))
    cases.append(Case("08_rollout_changed_strategy", "kubernetes.rollout.v1",
                      "Rollout strategy RollingUpdate->Recreate", "different",
                      cers=_all_three(ctx, _rollout(rollout_strategy="Recreate")),
                      base_ref="02_rollout_valid_all_runtimes"))

    # --- same intent, different actuation surface -> different (scale vs rollout) ---
    cases.append(Case("09_same_intent_diff_surface", None,
                      "Same intent (update web) via scale vs rollout -> different identity",
                      "different", cers={"scale": scale_base["ugence"],
                                         "rollout": roll_base["ugence"]},
                      notes="cross-profile: never equal identity for different surfaces"))

    # --- stale / policy / missing-evidence / auth-deny / acp-hold ---
    stale_ctx = _ctx(as_of=STALE, live_resource_version="2000")
    cases.append(Case("10_rollout_stale", "kubernetes.rollout.v1",
                      "Stale observation invalidates both layers", "equal", stale=True,
                      cers=_all_three(stale_ctx, _rollout())))
    cases.append(Case("11_scale_policy_update", "kubernetes.scale.v1",
                      "Restrictive policy update -> verdict flips (same identity)",
                      "equal", policy_variant=True, cers=scale_base,
                      expect_cp_class="BLOCKED_BY_AUTHORIZATION"))
    cases.append(Case("12_rollout_missing_evidence", "kubernetes.rollout.v1",
                      "Rollout without required evidence -> pending", "equal",
                      missing_evidence=True, cers=roll_base,
                      expect_cp_class="PENDING_AUTHORIZATION"))
    unauth = _ctx(delegation_grant="read:*")
    cases.append(Case("13_scale_auth_deny_acp_pass", "kubernetes.scale.v1",
                      "Unauthorized (deploy not delegated) but operationally fine",
                      "equal", cers=_all_three(unauth, _scale()),
                      expect_cp_class="BLOCKED_BY_AUTHORIZATION"))
    freeze_ctx = _ctx(operational=_op(freeze_active=True))
    cases.append(Case("14_rollout_auth_pass_acp_hold", "kubernetes.rollout.v1",
                      "Authorized rollout during a freeze window -> ACP hold", "equal",
                      cers=_all_three(freeze_ctx, _rollout()),
                      expect_cp_class="HELD_BY_ACP"))

    # --- fail-closed cases ---
    cases.append(Case("15_unsupported_profile", None,
                      "Unknown profile fails closed", "invalid", unsupported=True,
                      malformed_cer={**scale_base["ugence"], "profile": "kubernetes.delete.v9"}))
    inj = copy.deepcopy(roll_base["ugence"]); inj["extensions"] = {"x-evil": {"a": 1}}
    cases.append(Case("16_unsupported_extension", "kubernetes.rollout.v1",
                      "Non-empty unrecognized extension fails closed", "invalid",
                      malformed_cer=inj))
    bad = copy.deepcopy(roll_base["ugence"]); del bad["actuation"]["image_digest"]
    cases.append(Case("17_malformed_payload", "kubernetes.rollout.v1",
                      "Rollout missing image_digest fails closed", "invalid",
                      malformed_cer=bad))
    downgrade = copy.deepcopy(scale_base["ugence"])
    downgrade["actuation"]["image_digest"] = "sha256:" + "00" * 32  # rollout-only field
    cases.append(Case("18_profile_downgrade", "kubernetes.scale.v1",
                      "Rollout-only field under scale profile fails closed (downgrade)",
                      "invalid", malformed_cer=downgrade))

    # --- bypass + observation ---
    cases.append(Case("19_direct_bypass", "kubernetes.scale.v1",
                      "Direct governed-tool bypass yields no execution identity",
                      "equal", bypass=True, cers=scale_base))
    cases.append(Case("20_observation_return", "kubernetes.rollout.v1",
                      "Governed rollout result returns to each runtime", "equal",
                      observation=True, cers=roll_base, expect_cp_class="PROCEED"))

    return cases
