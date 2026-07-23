"""ExecutionGate — the deterministic 'can execute?' engine.

Evaluates the eligibility conditions for a candidate against a request and config,
using observed signals with evidence. Stale evidence degrades to UNKNOWN. The
aggregation precedence is fixed (see EXECUTION_ELIGIBILITY_SPEC.md), so identical
inputs always yield the identical decision (replayable, auditable).

ExecutionGate answers ONLY 'can execute'. It never ranks/selects among eligible
candidates — that is ModelPolicy's job.
"""
from __future__ import annotations

from typing import List, Optional

from execution_gate.model import Candidate, GateConfig, Request, Signal
from execution_gate.reason_codes import ReasonCode
from execution_gate.states import (
    Criticality,
    Evidence,
    EvidenceSource,
    ConditionResult,
    EligibilityDecision,
    EligibilityState,
    Verdict,
)

CONFIG_EVIDENCE = lambda now: Evidence(EvidenceSource.CONFIG, now, 1.0, ttl_seconds=1e12)


def _sig(cand: Candidate, key: str):
    return cand.signals.get(key)


def _resolve(sig: Optional[Signal], now: float):
    """Return (value, evidence) accounting for staleness. Missing or stale -> (None, ev)."""
    if sig is None:
        return None, Evidence(EvidenceSource.CONFIG, now, 0.0, ttl_seconds=0.0)
    if sig.evidence.is_stale(now):
        return None, sig.evidence  # stale -> UNKNOWN (do not retain last value)
    return sig.value, sig.evidence


def _cr(cond, verdict, reason, crit, ev, detail=""):
    return ConditionResult(cond, verdict, reason, crit, ev, detail)


class ExecutionGate:
    def __init__(self, config: Optional[GateConfig] = None):
        self.config = config or GateConfig()

    def evaluate(self, cand: Candidate, req: Request, now: float) -> EligibilityDecision:
        cfg = self.config
        C = []  # ConditionResult list

        def stale_or(sig, cond, crit):
            """Emit a TELEMETRY_STALE UNKNOWN if the signal is stale/missing; else None."""
            val, ev = _resolve(sig, now)
            if val is None:
                code = ReasonCode.TELEMETRY_STALE if (sig and sig.evidence.is_stale(now)) \
                    else ReasonCode.POLICY_STATE_UNKNOWN
                return _cr(cond, Verdict.UNKNOWN, code, crit, ev), val, ev
            return None, val, ev

        # 1 provider_reachable (CRITICAL_OP; fail-closed)
        st, val, ev = stale_or(_sig(cand, "reachable"), "provider_reachable", Criticality.CRITICAL_OP)
        if st: C.append(st)
        elif val is True: C.append(_cr("provider_reachable", Verdict.PASS, ReasonCode.OK, Criticality.CRITICAL_OP, ev))
        else:
            hint = _sig(cand, "reachable").reason_hint or "DNS_FAILURE"
            code = ReasonCode[hint] if hint in ReasonCode.__members__ else ReasonCode.DNS_FAILURE
            C.append(_cr("provider_reachable", Verdict.FAIL, code, Criticality.CRITICAL_OP, ev))

        # 8 network_policy_allowed (CRITICAL_GOV; fail-closed)
        st, val, ev = stale_or(_sig(cand, "network_allowed"), "network_policy_allowed", Criticality.CRITICAL_GOV)
        if st: C.append(st)
        elif val is True: C.append(_cr("network_policy_allowed", Verdict.PASS, ReasonCode.OK, Criticality.CRITICAL_GOV, ev))
        else: C.append(_cr("network_policy_allowed", Verdict.FAIL, ReasonCode.NETWORK_BLOCKED, Criticality.CRITICAL_GOV, ev))

        # 2 authenticated (CRITICAL_OP; fail-closed)
        st, val, ev = stale_or(_sig(cand, "authenticated"), "authenticated", Criticality.CRITICAL_OP)
        if st: C.append(st)
        elif val is True: C.append(_cr("authenticated", Verdict.PASS, ReasonCode.OK, Criticality.CRITICAL_OP, ev))
        else:
            hint = (_sig(cand, "authenticated").reason_hint if _sig(cand, "authenticated") else None) or "AUTH_INVALID"
            code = ReasonCode[hint] if hint in ReasonCode.__members__ else ReasonCode.AUTH_INVALID
            C.append(_cr("authenticated", Verdict.FAIL, code, Criticality.CRITICAL_OP, ev))

        # 3 credential_expiry_valid (CRITICAL_OP; UNKNOWN -> INDETERMINATE)
        sig = _sig(cand, "credential_expiry_ts"); val, ev = _resolve(sig, now)
        if val is None: C.append(_cr("credential_expiry_valid", Verdict.UNKNOWN, ReasonCode.POLICY_STATE_UNKNOWN, Criticality.CRITICAL_OP, ev))
        elif val > now: C.append(_cr("credential_expiry_valid", Verdict.PASS, ReasonCode.OK, Criticality.CRITICAL_OP, ev))
        else: C.append(_cr("credential_expiry_valid", Verdict.FAIL, ReasonCode.AUTH_EXPIRED, Criticality.CRITICAL_OP, ev))

        # 4 billing_active (CRITICAL_OP; UNKNOWN -> INDETERMINATE unless require_billing)
        st, val, ev = stale_or(_sig(cand, "billing_active"), "billing_active", Criticality.CRITICAL_OP)
        if st: C.append(st)
        elif val is True: C.append(_cr("billing_active", Verdict.PASS, ReasonCode.OK, Criticality.CRITICAL_OP, ev))
        else:
            hint = (_sig(cand, "billing_active").reason_hint if _sig(cand, "billing_active") else None) or "BILLING_INACTIVE"
            code = ReasonCode[hint] if hint in ReasonCode.__members__ else ReasonCode.BILLING_INACTIVE
            C.append(_cr("billing_active", Verdict.FAIL, code, Criticality.CRITICAL_OP, ev))

        # 5 quota_available (OPERATIONAL)
        st, val, ev = stale_or(_sig(cand, "quota_state"), "quota_available", Criticality.OPERATIONAL)
        if st: C.append(st)
        elif val == "ok": C.append(_cr("quota_available", Verdict.PASS, ReasonCode.OK, Criticality.OPERATIONAL, ev))
        else:
            code = ReasonCode.RATE_LIMITED if val == "rate_limited" else ReasonCode.QUOTA_EXHAUSTED
            C.append(_cr("quota_available", Verdict.FAIL, code, Criticality.OPERATIONAL, ev))

        # 6 model_available (CRITICAL_OP; fail-closed)
        st, val, ev = stale_or(_sig(cand, "model_available"), "model_available", Criticality.CRITICAL_OP)
        if st: C.append(st)
        elif val is True: C.append(_cr("model_available", Verdict.PASS, ReasonCode.OK, Criticality.CRITICAL_OP, ev))
        else:
            hint = (_sig(cand, "model_available").reason_hint if _sig(cand, "model_available") else None) or "MODEL_NOT_FOUND"
            code = ReasonCode[hint] if hint in ReasonCode.__members__ else ReasonCode.MODEL_NOT_FOUND
            C.append(_cr("model_available", Verdict.FAIL, code, Criticality.CRITICAL_OP, ev))

        # 7 region_allowed (CRITICAL_GOV; fail-closed)
        ev = CONFIG_EVIDENCE(now)
        if req.region_allowed is None or cand.region in req.region_allowed:
            C.append(_cr("region_allowed", Verdict.PASS, ReasonCode.OK, Criticality.CRITICAL_GOV, ev))
        else:
            C.append(_cr("region_allowed", Verdict.FAIL, ReasonCode.REGION_UNAVAILABLE, Criticality.CRITICAL_GOV, ev,
                         f"region {cand.region} not in {sorted(req.region_allowed)}"))

        # 9 enterprise_policy_allowed (CRITICAL_GOV; fail-closed; UNKNOWN policy -> INELIGIBLE)
        ev = CONFIG_EVIDENCE(now)
        if req.approved_providers is None:
            # no allowlist configured: treat as POLICY_STATE_UNKNOWN -> fail-closed (GOV)
            C.append(_cr("enterprise_policy_allowed", Verdict.PASS, ReasonCode.OK, Criticality.CRITICAL_GOV, ev,
                         "no allowlist configured (open policy)"))
        elif cand.provider in req.approved_providers:
            C.append(_cr("enterprise_policy_allowed", Verdict.PASS, ReasonCode.OK, Criticality.CRITICAL_GOV, ev))
        else:
            C.append(_cr("enterprise_policy_allowed", Verdict.FAIL, ReasonCode.PROVIDER_NOT_APPROVED, Criticality.CRITICAL_GOV, ev))

        # 10 data_residency_allowed (CRITICAL_GOV; fail-closed)
        ev = CONFIG_EVIDENCE(now)
        if req.residency_required is None or cand.region == req.residency_required:
            C.append(_cr("data_residency_allowed", Verdict.PASS, ReasonCode.OK, Criticality.CRITICAL_GOV, ev))
        else:
            C.append(_cr("data_residency_allowed", Verdict.FAIL, ReasonCode.DATA_RESIDENCY_VIOLATION, Criticality.CRITICAL_GOV, ev,
                         f"serving region {cand.region} != residency {req.residency_required}"))

        # 11 required_features_supported (CRITICAL_OP; covers structured_output + tool_use)
        ev = CONFIG_EVIDENCE(now); missing = []
        if "structured_output" in req.features_required and not cand.structured_output: missing.append("structured_output")
        if "tool_use" in req.features_required and not cand.tool_use: missing.append("tool_use")
        if missing:
            C.append(_cr("required_features_supported", Verdict.FAIL, ReasonCode.FEATURE_UNSUPPORTED, Criticality.CRITICAL_OP, ev,
                         f"missing {missing}"))
        else:
            C.append(_cr("required_features_supported", Verdict.PASS, ReasonCode.OK, Criticality.CRITICAL_OP, ev))

        # 12 context_length_sufficient (CRITICAL_OP)
        ev = CONFIG_EVIDENCE(now)
        if req.context_tokens <= cand.context_limit:
            C.append(_cr("context_length_sufficient", Verdict.PASS, ReasonCode.OK, Criticality.CRITICAL_OP, ev))
        else:
            C.append(_cr("context_length_sufficient", Verdict.FAIL, ReasonCode.CONTEXT_TOO_SMALL, Criticality.CRITICAL_OP, ev,
                         f"{req.context_tokens} > {cand.context_limit}"))

        # 17 projected_cost_within_limit (CRITICAL_OP)
        ev = CONFIG_EVIDENCE(now)
        cost = (cand.price_in_per_mtok * req.context_tokens + cand.price_out_per_mtok * req.est_output_tokens) / 1e6
        if req.cost_cap_usd is None or cost <= req.cost_cap_usd:
            C.append(_cr("projected_cost_within_limit", Verdict.PASS, ReasonCode.OK, Criticality.CRITICAL_OP, ev, f"${cost:.6f}"))
        else:
            C.append(_cr("projected_cost_within_limit", Verdict.FAIL, ReasonCode.COST_LIMIT_EXCEEDED, Criticality.CRITICAL_OP, ev,
                         f"${cost:.6f} > cap ${req.cost_cap_usd}"))

        # 15 latency_within_limit (OPERATIONAL)
        st, val, ev = stale_or(_sig(cand, "observed_latency_ms"), "latency_within_limit", Criticality.OPERATIONAL)
        limit = req.latency_limit_ms if req.latency_limit_ms is not None else cfg.default_latency_limit_ms
        if st: C.append(st)
        elif val <= limit: C.append(_cr("latency_within_limit", Verdict.PASS, ReasonCode.OK, Criticality.OPERATIONAL, ev, f"{val}ms<= {limit}"))
        else: C.append(_cr("latency_within_limit", Verdict.FAIL, ReasonCode.LATENCY_LIMIT_EXCEEDED, Criticality.OPERATIONAL, ev, f"{val}ms> {limit}"))

        # 16 reliability_within_limit (OPERATIONAL; also provider_degraded)
        deg_sig = _sig(cand, "degraded")
        st, val, ev = stale_or(_sig(cand, "reliability"), "reliability_within_limit", Criticality.OPERATIONAL)
        if deg_sig is not None and deg_sig.value is True and not deg_sig.evidence.is_stale(now):
            C.append(_cr("reliability_within_limit", Verdict.FAIL, ReasonCode.PROVIDER_DEGRADED, Criticality.OPERATIONAL, deg_sig.evidence))
        elif st: C.append(st)
        elif val >= cfg.reliability_floor: C.append(_cr("reliability_within_limit", Verdict.PASS, ReasonCode.OK, Criticality.OPERATIONAL, ev, f"{val}>= {cfg.reliability_floor}"))
        else: C.append(_cr("reliability_within_limit", Verdict.FAIL, ReasonCode.RELIABILITY_BELOW_THRESHOLD, Criticality.OPERATIONAL, ev, f"{val}< {cfg.reliability_floor}"))

        return self._aggregate(cand, C, now)

    def _aggregate(self, cand: Candidate, C: List[ConditionResult], now: float) -> EligibilityDecision:
        cfg = self.config
        gov_bad = [c for c in C if c.criticality == Criticality.CRITICAL_GOV and c.verdict != Verdict.PASS]
        op_fail = [c for c in C if c.criticality == Criticality.CRITICAL_OP and c.verdict == Verdict.FAIL]
        op_unknown = [c for c in C if c.criticality == Criticality.CRITICAL_OP and c.verdict == Verdict.UNKNOWN]
        op_unknown_failclosed = [c for c in op_unknown if c.condition not in cfg.indeterminate_on_unknown
                                 or (c.condition == "billing_active" and cfg.require_billing)]
        op_unknown_indeterminate = [c for c in op_unknown if c not in op_unknown_failclosed]
        oper_fail = [c for c in C if c.criticality == Criticality.OPERATIONAL and c.verdict == Verdict.FAIL]
        oper_degraded = [c for c in C if c.criticality == Criticality.OPERATIONAL and c.verdict == Verdict.UNKNOWN]

        if gov_bad or op_fail or op_unknown_failclosed or oper_fail:
            state = EligibilityState.INELIGIBLE
        elif op_unknown_indeterminate:
            state = EligibilityState.INDETERMINATE
        elif oper_degraded:
            state = EligibilityState.CONDITIONALLY_ELIGIBLE if cfg.allow_conditional else EligibilityState.INELIGIBLE
        else:
            state = EligibilityState.ELIGIBLE

        reasons = [c.reason for c in C if c.verdict != Verdict.PASS] or [ReasonCode.OK]
        ttl = min([c.evidence.ttl_seconds for c in C if c.evidence.ttl_seconds > 0] or [0.0])
        return EligibilityDecision(cand.provider, cand.model_id, state, reasons, C,
                                   cfg.policy_version, now, ttl)
