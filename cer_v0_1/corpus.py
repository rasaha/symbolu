"""Cross-runtime conformance corpus (milestone §9). 15 cases.

Each case is produced independently by BOTH runtimes (native Ugence + real
LangGraph) from the SAME shared ActuationRequest, except the malformed-CER cases
(13, 14) which model an adapter fault on one runtime. Every case is labelled by
provenance and its expected identity relationship + expected control-plane class.

Deterministic: fixed timestamps/versions, no wall clock.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .actuation import ActuationRequest
from .producers.langgraph_adapter import LangGraphCERAdapter
from .producers.ugence import UgenceCERProducer

NOW = "2026-01-01T00:10:00.000Z"
FRESH_AS_OF = "2026-01-01T00:09:30.000Z"     # 30s old — within the 600s bound
STALE_AS_OF = "2026-01-01T00:00:00.000Z"     # 600s old — exceeds the freshness bound

_UG = UgenceCERProducer()
_LG = LangGraphCERAdapter()


def _op(**over) -> dict:
    base = {
        "generation": 1, "desired_replicas": 10, "current_replicas": 10,
        "available_replicas": 10, "readiness_plasticity": 0.95,
        "active_rollback_watches": 0, "seconds_since_last_action": 600.0,
        "dependency_healthy": True, "freeze_active": False, "observation_time_s": 600.0,
    }
    base.update(over)
    return base


def _req(**over) -> ActuationRequest:
    """A base VALID+SAFE scale (web 10 -> 12) with per-case overrides."""
    d = dict(
        cluster="fixture", namespace="protected", deployment="web",
        from_replicas=10, to_replicas=12,
        principal="agent:web-ops", permissions=("deploy",), delegator_id="sre",
        resource_version="1001", state_hash="sha-256:" + "ab" * 32, as_of=FRESH_AS_OF,
        operational=_op(), policy_version="1.0.0+abc", policy_digest="pd",
        correlation_id="protected/web", attach_evidence=True,
    )
    d.update(over)
    return ActuationRequest(**d)


@dataclass
class CorpusCase:
    case_id: str
    description: str
    provenance: str
    # identity expectations
    expect_ug_eq_lg: Optional[bool] = None       # both runtimes -> same digest?
    expect_digest_vs_base: Optional[str] = None  # "same" | "differs" | None
    # control-plane expectation (composed class), on the Ugence-derived CER
    expect_cp_class: Optional[str] = None         # e.g. PROCEED / BLOCKED_BY_AUTHORIZATION
    # producer outputs
    ug_cer: Optional[dict] = None
    lg_cer: Optional[dict] = None
    # special handling flags for the runner
    malformed: bool = False          # validate_cer must fail closed
    policy_variant: bool = False     # evaluate under a restrictive policy
    stale: bool = False
    missing_evidence: bool = False
    bypass: bool = False
    observation: bool = False
    notes: str = ""


def _both(req: ActuationRequest):
    return _UG.propose(req), _LG.propose(req)


def build_corpus() -> List[CorpusCase]:
    cases: List[CorpusCase] = []

    # base valid request (also the reference for "vs base")
    base_req = _req()
    base_ug, base_lg = _both(base_req)

    # 1 — identical VALID scale from both runtimes -> same digest, PROCEED
    cases.append(CorpusCase(
        "01_valid_scale", "Identical valid scale (web 10->12) from both runtimes",
        "ugence+langgraph", expect_ug_eq_lg=True, expect_digest_vs_base="same",
        expect_cp_class="PROCEED", ug_cer=base_ug, lg_cer=base_lg))

    # 2 — identical UNAUTHORIZED request -> same digest, BLOCKED_BY_AUTHORIZATION
    un = _req(delegation_grant="read:*")  # permissions=deploy NOT covered -> PRIV_MONO DENY
    un_ug, un_lg = _both(un)
    cases.append(CorpusCase(
        "02_unauthorized", "Identical unauthorized scale (deploy not covered by delegation)",
        "ugence+langgraph", expect_ug_eq_lg=True, expect_cp_class="BLOCKED_BY_AUTHORIZATION",
        ug_cer=un_ug, lg_cer=un_lg))

    # 3 — identical OPERATIONALLY UNSAFE request -> same digest, HELD_BY_ACP
    unsafe = _req(operational=_op(freeze_active=True))
    us_ug, us_lg = _both(unsafe)
    cases.append(CorpusCase(
        "03_operationally_unsafe", "Identical scale during an active freeze window",
        "ugence+langgraph", expect_ug_eq_lg=True, expect_cp_class="HELD_BY_ACP",
        ug_cer=us_ug, lg_cer=us_lg))

    # 4 — SAME INTENT, DIFFERENT ACTUATION SURFACE -> digest DIFFERS from base
    #     (physically distinct target: a different deployment for the same "more web
    #     capacity" intent). Guards against claiming same identity for diff surfaces.
    surfB = _req(deployment="web-canary")
    sb_ug, sb_lg = _both(surfB)
    cases.append(CorpusCase(
        "04_diff_actuation_surface",
        "Same intent (more web capacity) via a physically distinct target -> different identity",
        "ugence+langgraph", expect_ug_eq_lg=True, expect_digest_vs_base="differs",
        ug_cer=sb_ug, lg_cer=sb_lg,
        notes="V0.1 pins one interface; distinct target models 'different surface'."))

    # 5 — same action, DIFFERENT RUNTIME PROVENANCE -> same digest (the headline)
    cases.append(CorpusCase(
        "05_diff_runtime_provenance", "Same action; runtime=ugence vs runtime=langgraph",
        "ugence!=langgraph provenance", expect_ug_eq_lg=True, expect_digest_vs_base="same",
        expect_cp_class="PROCEED", ug_cer=base_ug, lg_cer=base_lg))

    # 6 — same action, DIFFERENT OBJECTIVE PROSE -> same digest
    #     (the two producers already stamp different objective prose)
    cases.append(CorpusCase(
        "06_diff_objective_prose", "Same action; different objective prose per runtime",
        "different objective prose", expect_ug_eq_lg=True, expect_digest_vs_base="same",
        ug_cer=base_ug, lg_cer=base_lg,
        notes=f"ug='{base_ug['provenance']['objective'][:24]}...' lg='{base_lg['provenance']['objective'][:24]}...'"))

    # 7 — MODIFIED replica argument -> digest DIFFERS from base
    rep = _req(to_replicas=13)
    r_ug, r_lg = _both(rep)
    cases.append(CorpusCase(
        "07_modified_replicas", "Same target, replicas 12 -> 13 -> different identity",
        "ugence+langgraph", expect_ug_eq_lg=True, expect_digest_vs_base="differs",
        ug_cer=r_ug, lg_cer=r_lg))

    # 8 — MODIFIED target -> digest DIFFERS from base
    tgt = _req(deployment="api")
    t_ug, t_lg = _both(tgt)
    cases.append(CorpusCase(
        "08_modified_target", "Target web -> api -> different identity",
        "ugence+langgraph", expect_ug_eq_lg=True, expect_digest_vs_base="differs",
        ug_cer=t_ug, lg_cer=t_lg))

    # 9 — STALE resourceVersion -> invalidates BOTH paths (AG freshness + ACP binding)
    stale = _req(as_of=STALE_AS_OF, live_resource_version="2000")
    s_ug, s_lg = _both(stale)
    cases.append(CorpusCase(
        "09_stale_state", "Stale observation: old as_of + live resourceVersion advanced",
        "ugence+langgraph", expect_ug_eq_lg=True, expect_cp_class=None, stale=True,
        ug_cer=s_ug, lg_cer=s_lg,
        notes="AG rejects on freshness; ACP rejects on STATE_BINDING_MISMATCH; not eligible."))

    # 10 — POLICY UPDATE -> same digest, authorization changes (ALLOW -> DENY)
    cases.append(CorpusCase(
        "10_policy_update", "Same action under a restrictive policy update -> different verdict",
        "ugence", expect_ug_eq_lg=None, policy_variant=True, ug_cer=base_ug, lg_cer=base_lg,
        expect_cp_class="BLOCKED_BY_AUTHORIZATION",
        notes="Same action_hash under both policies; restrictive policy denies DEPLOY."))

    # 11 — MISSING evidence -> PENDING_AUTHORIZATION (REQUEST_MORE_EVIDENCE)
    noev = _req(attach_evidence=False)
    n_ug, n_lg = _both(noev)
    cases.append(CorpusCase(
        "11_missing_evidence", "Valid scale but required evidence absent",
        "ugence+langgraph", expect_ug_eq_lg=True, expect_cp_class="PENDING_AUTHORIZATION",
        missing_evidence=True, ug_cer=n_ug, lg_cer=n_lg))

    # 12 — RUNTIME direct tool BYPASS -> blocked in governed mode
    cases.append(CorpusCase(
        "12_direct_bypass", "Runtime attempts to execute the tool without a CER/verdict",
        "langgraph", bypass=True, ug_cer=base_ug, lg_cer=base_lg,
        notes="Governed mode: no execution identity without an eligible composed result."))

    # 13 — ADAPTER DROPS an identity-bearing field -> fail closed
    dropped = copy.deepcopy(base_ug)
    del dropped["identity"]["target"]
    cases.append(CorpusCase(
        "13_adapter_drops_field", "Adapter omits identity.target -> CER validation fails closed",
        "ugence(faulty)", malformed=True, ug_cer=dropped))

    # 14 — ADAPTER INJECTS an unsupported extension -> fail closed
    injected = copy.deepcopy(base_ug)
    injected["extensions"] = {"x-unknown": {"exfiltrate": True}}
    cases.append(CorpusCase(
        "14_adapter_injects_extension", "Adapter injects an unsupported extension -> fail closed",
        "ugence(faulty)", malformed=True, ug_cer=injected))

    # 15 — OBSERVATION returns to BOTH runtimes after a governed result
    cases.append(CorpusCase(
        "15_observation_return", "After a governed PROCEED, both runtimes observe/reflect",
        "ugence+langgraph", observation=True, ug_cer=base_ug, lg_cer=base_lg,
        expect_cp_class="PROCEED"))

    return cases
