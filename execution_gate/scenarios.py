"""Deterministic scenario suite (Phase 8).

Each scenario carries (a) the gate-visible SIGNALS (evidence, possibly stale/wrong) and
(b) GROUND TRUTH — what actually happens on a real call. The gap between them is where
false-eligible / false-ineligible arise, so the evaluation is not rigged for the gate.

Includes replay records distilled from the real V1/V2 investigation (credentials and
project identifiers removed): proxy 403 denials, Gemini free-tier 429, Anthropic
model_not_found, invalid AWS/Google creds, Claude/Gemma executable.

Base time T0 is fixed (no system clock) so everything is replayable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from execution_gate.model import Candidate, Request, Signal
from execution_gate.reason_codes import ReasonCode
from execution_gate.states import Evidence, EvidenceSource

T0 = 1_000_000.0  # fixed evaluation instant


def ev(source=EvidenceSource.LIVE_PROBE, age=0.0, ttl=900.0, conf=0.95, raw=None):
    return Evidence(source, T0 - age, conf, ttl, raw)


def sig(value, source=EvidenceSource.LIVE_PROBE, age=0.0, ttl=900.0, reason=None, raw=None):
    return Signal(value, ev(source, age, ttl, raw=raw), reason_hint=reason)


@dataclass
class GroundTruth:
    executable: bool          # would a real call return valid text?
    permitted: bool           # is it actually governance/compliance-permitted?
    latency_ms: float
    quality: float            # capability if it runs
    cost_per_call: float      # billed cost if it runs (0 if it errors)
    fail_reason: Optional[ReasonCode] = None
    error_latency_ms: float = 120.0   # wasted round-trip on failure


@dataclass
class Scenario:
    id: str
    category: str
    description: str
    request: Request
    candidates: List[Candidate]
    ground_truth: Dict[str, GroundTruth]      # model_id -> GT
    quality: Dict[str, float] = field(default_factory=dict)  # model_id -> capability prior


def _c(provider, model_id, family, developer="", region="global", ctx=200000,
       so=True, tools=True, pin=1.0, pout=4.0, **signals):
    return Candidate(provider, model_id, family, developer or provider, region, ctx, so, tools, pin, pout, dict(signals))


# reusable healthy-signal set (fresh live-probe evidence)
def healthy(model_available=True, quota="ok", billing=True, latency=800.0, reliability=0.99,
            reachable=True, network=True, authed=True):
    return dict(
        reachable=sig(reachable), network_allowed=sig(network), authenticated=sig(authed),
        credential_expiry_ts=sig(T0 + 1e9),   # probe confirms a valid, non-expiring credential
        billing_active=sig(billing), quota_state=sig(quota), model_available=sig(model_available),
        observed_latency_ms=sig(latency), reliability=sig(reliability), degraded=sig(False),
    )


def build() -> List[Scenario]:
    S: List[Scenario] = []
    R = lambda rid, **kw: Request(rid, **kw)

    # ---- REPLAY: real V1/V2 facts (credentials removed) ----
    # Claude + Gemma executable; Gemini free-tier 429; Anthropic old snapshot 404; others proxy-blocked.
    claude_h = _c("anthropic", "claude-haiku-4-5", "claude", pin=1.0, pout=5.0, **healthy(latency=760))
    claude_s = _c("anthropic", "claude-sonnet-4-5", "claude", pin=3.0, pout=15.0, **healthy(latency=1520))
    gemma = _c("google", "gemma-4-31b-it", "gemma", developer="google", pin=0.3, pout=0.3, **healthy(latency=1120))
    gemini = _c("google", "gemini-2.0-flash", "gemini", developer="google", pin=0.1, pout=0.4,
                **healthy(billing=False, quota="exhausted", latency=650))
    gemini.signals["billing_active"] = sig(False, reason="FREE_TIER_ONLY", raw="429 free_tier")
    old_claude = _c("anthropic", "claude-3-5-haiku-20241022", "claude",
                    **healthy(model_available=False, latency=500))
    old_claude.signals["model_available"] = sig(False, reason="MODEL_NOT_FOUND", raw="404 not_found")
    mistral = _c("mistral", "mistral-large", "mistral", **healthy(reachable=False, network=False))
    mistral.signals["network_allowed"] = sig(False, reason="NETWORK_BLOCKED", raw="403 CONNECT")
    S.append(Scenario("replay_multiprovider", "replay",
        "Real V1/V2 state: Claude+Gemma executable, Gemini free-tier 429, old Claude 404, Mistral proxy-blocked.",
        R("req_replay", context_tokens=4000, cost_cap_usd=1.0),
        [claude_h, claude_s, gemma, gemini, old_claude, mistral],
        {"claude-haiku-4-5": GroundTruth(True, True, 760, 0.80, 0.02),
         "claude-sonnet-4-5": GroundTruth(True, True, 1520, 0.90, 0.10),
         "gemma-4-31b-it": GroundTruth(True, True, 1120, 0.74, 0.003),
         "gemini-2.0-flash": GroundTruth(False, True, 0, 0.82, 0.0, ReasonCode.FREE_TIER_ONLY),
         "claude-3-5-haiku-20241022": GroundTruth(False, True, 0, 0.7, 0.0, ReasonCode.MODEL_NOT_FOUND),
         "mistral-large": GroundTruth(False, True, 0, 0.85, 0.0, ReasonCode.NETWORK_BLOCKED)},
        {"claude-haiku-4-5": 0.80, "claude-sonnet-4-5": 0.90, "gemma-4-31b-it": 0.74,
         "gemini-2.0-flash": 0.82, "claude-3-5-haiku-20241022": 0.70, "mistral-large": 0.85}))

    # ---- GOVERNANCE: prohibited-but-working provider (gate's decisive win over retry) ----
    good = _c("anthropic", "claude-haiku-4-5", "claude", pin=1.0, pout=5.0, **healthy(latency=760))
    prohibited = _c("unapproved_vendor", "vendorx-large", "vendorx", pin=0.2, pout=0.2, **healthy(latency=400))
    S.append(Scenario("gov_prohibited_but_working", "governance",
        "A cheaper, faster, working provider that is NOT enterprise-approved. Retry logic would use it (violation); the gate excludes it.",
        R("req_gov", context_tokens=3000, approved_providers={"anthropic", "google"}),
        [prohibited, good],
        {"vendorx-large": GroundTruth(True, False, 400, 0.88, 0.001),   # executable but NOT permitted
         "claude-haiku-4-5": GroundTruth(True, True, 760, 0.80, 0.02)},
        {"vendorx-large": 0.88, "claude-haiku-4-5": 0.80}))

    # ---- RESIDENCY: working model in wrong region ----
    eu_ok = _c("anthropic", "claude-haiku-4-5", "claude", region="eu", pin=1.0, pout=5.0, **healthy())
    us_model = _c("anthropic", "claude-sonnet-4-5", "claude", region="us", pin=3.0, pout=15.0, **healthy(latency=1200))
    S.append(Scenario("gov_residency", "governance",
        "Higher-quality model served from a non-residency region; must be excluded despite working.",
        R("req_res", context_tokens=3000, residency_required="eu"),
        [us_model, eu_ok],
        {"claude-sonnet-4-5": GroundTruth(True, False, 1200, 0.90, 0.10),
         "claude-haiku-4-5": GroundTruth(True, True, 760, 0.80, 0.02)},
        {"claude-sonnet-4-5": 0.90, "claude-haiku-4-5": 0.80}))

    # ---- EXECUTION failures recoverable by retry (gate saves the failed first attempt) ----
    top_broken = _c("google", "gemini-2.0-flash", "gemini", pin=0.1, pout=0.4,
                    **healthy(billing=False, quota="exhausted", latency=650))
    top_broken.signals["billing_active"] = sig(False, reason="FREE_TIER_ONLY")
    backup = _c("google", "gemma-4-31b-it", "gemma", pin=0.3, pout=0.3, **healthy(latency=1120))
    S.append(Scenario("exec_top_quota_backup_ok", "execution",
        "Best-quality model quota-blocked; a working backup exists. Retry succeeds on 2nd try; gate succeeds on 1st.",
        R("req_quota", context_tokens=3000),
        [top_broken, backup],
        {"gemini-2.0-flash": GroundTruth(False, True, 0, 0.82, 0.0, ReasonCode.QUOTA_EXHAUSTED),
         "gemma-4-31b-it": GroundTruth(True, True, 1120, 0.74, 0.003)},
        {"gemini-2.0-flash": 0.82, "gemma-4-31b-it": 0.74}))

    # ---- NO eligible model (fail-fast vs retry storm) ----
    b1 = _c("mistral", "mistral-large", "mistral", **healthy(network=False)); b1.signals["network_allowed"]=sig(False,reason="NETWORK_BLOCKED")
    b2 = _c("google", "gemini-2.0-flash", "gemini", **healthy(billing=False)); b2.signals["billing_active"]=sig(False,reason="FREE_TIER_ONLY")
    b3 = _c("anthropic", "claude-3-5-haiku-20241022", "claude", **healthy(model_available=False)); b3.signals["model_available"]=sig(False,reason="MODEL_NOT_FOUND")
    S.append(Scenario("exec_none_eligible", "execution",
        "No provider is executable. Gate abstains immediately; retry logic burns N failed calls before giving up.",
        R("req_none", context_tokens=3000),
        [b1, b2, b3],
        {"mistral-large": GroundTruth(False, True, 0, 0.85, 0.0, ReasonCode.NETWORK_BLOCKED),
         "gemini-2.0-flash": GroundTruth(False, True, 0, 0.82, 0.0, ReasonCode.FREE_TIER_ONLY),
         "claude-3-5-haiku-20241022": GroundTruth(False, True, 0, 0.70, 0.0, ReasonCode.MODEL_NOT_FOUND)},
        {"mistral-large": 0.85, "gemini-2.0-flash": 0.82, "claude-3-5-haiku-20241022": 0.70}))

    # ---- STALE evidence -> FALSE-ELIGIBLE (gate errs like retry; honest downside) ----
    stale_ok = _c("google", "gemini-2.0-flash", "gemini", pin=0.1, pout=0.4,
                  reachable=sig(True), network_allowed=sig(True), authenticated=sig(True), credential_expiry_ts=sig(T0+1e9),
                  billing_active=sig(True, source=EvidenceSource.CACHE, age=7200, ttl=900),  # STALE cache says billing ok
                  quota_state=sig("ok", source=EvidenceSource.CACHE, age=7200, ttl=900),
                  model_available=sig(True), observed_latency_ms=sig(650), reliability=sig(0.99), degraded=sig(False))
    fresh_backup = _c("google", "gemma-4-31b-it", "gemma", pin=0.3, pout=0.3, **healthy(latency=1120))
    S.append(Scenario("stale_false_eligible", "staleness",
        "Cached billing/quota evidence is stale; model looks eligible but actually 429s. Gate degrades stale->UNKNOWN (INDETERMINATE), avoiding a confident false-eligible.",
        R("req_stale", context_tokens=3000),
        [stale_ok, fresh_backup],
        {"gemini-2.0-flash": GroundTruth(False, True, 0, 0.82, 0.0, ReasonCode.QUOTA_EXHAUSTED),
         "gemma-4-31b-it": GroundTruth(True, True, 1120, 0.74, 0.003)},
        {"gemini-2.0-flash": 0.82, "gemma-4-31b-it": 0.74}))

    # ---- STALE ineligible -> FALSE-INELIGIBLE (gate discards usable capacity; honest downside) ----
    recovered = _c("google", "gemini-2.0-flash", "gemini", pin=0.1, pout=0.4,
                   reachable=sig(True), network_allowed=sig(True), authenticated=sig(True), credential_expiry_ts=sig(T0+1e9),
                   billing_active=sig(False, source=EvidenceSource.CACHE, age=7200, ttl=900),  # STALE: says down, actually recovered
                   quota_state=sig("exhausted", source=EvidenceSource.CACHE, age=7200, ttl=900),
                   model_available=sig(True), observed_latency_ms=sig(650), reliability=sig(0.99), degraded=sig(False))
    S.append(Scenario("stale_false_ineligible", "staleness",
        "Provider recovered but cache still says quota-exhausted (stale). Gate -> INDETERMINATE (won't select), so it misses now-usable, cheaper capacity — the cost of caution.",
        R("req_recover", context_tokens=3000),
        [recovered, fresh_backup],
        {"gemini-2.0-flash": GroundTruth(True, True, 650, 0.82, 0.0004),   # actually works now
         "gemma-4-31b-it": GroundTruth(True, True, 1120, 0.74, 0.003)},
        {"gemini-2.0-flash": 0.82, "gemma-4-31b-it": 0.74}))

    # ---- STABLE all-eligible (gate adds only overhead; expected null/negative for gate) ----
    a = _c("anthropic", "claude-haiku-4-5", "claude", pin=1.0, pout=5.0, **healthy(latency=760))
    b = _c("google", "gemma-4-31b-it", "gemma", pin=0.3, pout=0.3, **healthy(latency=1120))
    S.append(Scenario("stable_all_ok", "stable",
        "Everything healthy and permitted. Retry never needs to retry; the gate adds check overhead for no avoided failure.",
        R("req_stable", context_tokens=3000, approved_providers={"anthropic", "google"}),
        [a, b],
        {"claude-haiku-4-5": GroundTruth(True, True, 760, 0.80, 0.02),
         "gemma-4-31b-it": GroundTruth(True, True, 1120, 0.74, 0.003)},
        {"claude-haiku-4-5": 0.80, "gemma-4-31b-it": 0.74}))

    # ---- FEATURE / CONTEXT mismatch (gate avoids a guaranteed failure) ----
    no_tools = _c("google", "gemma-4-31b-it", "gemma", tools=False, pin=0.3, pout=0.3, **healthy(latency=1120))
    with_tools = _c("anthropic", "claude-haiku-4-5", "claude", tools=True, pin=1.0, pout=5.0, **healthy(latency=760))
    S.append(Scenario("feature_tools_required", "capability",
        "Task requires tool use; cheaper model lacks it. Gate excludes on FEATURE_UNSUPPORTED; retry would fail the call first.",
        R("req_feat", context_tokens=3000, features_required={"tool_use"}),
        [no_tools, with_tools],
        {"gemma-4-31b-it": GroundTruth(False, True, 0, 0.74, 0.0, ReasonCode.FEATURE_UNSUPPORTED),
         "claude-haiku-4-5": GroundTruth(True, True, 760, 0.80, 0.02)},
        {"gemma-4-31b-it": 0.74, "claude-haiku-4-5": 0.80}))
    small_ctx = _c("google", "gemma-4-31b-it", "gemma", ctx=8000, pin=0.3, pout=0.3, **healthy(latency=1120))
    big_ctx = _c("anthropic", "claude-sonnet-4-5", "claude", ctx=200000, pin=3.0, pout=15.0, **healthy(latency=1500))
    S.append(Scenario("context_overflow", "capability",
        "Large document exceeds the cheaper model's context. Gate excludes on CONTEXT_TOO_SMALL.",
        R("req_ctx", context_tokens=40000),
        [small_ctx, big_ctx],
        {"gemma-4-31b-it": GroundTruth(False, True, 0, 0.74, 0.0, ReasonCode.CONTEXT_TOO_SMALL),
         "claude-sonnet-4-5": GroundTruth(True, True, 1500, 0.90, 0.9)},
        {"gemma-4-31b-it": 0.74, "claude-sonnet-4-5": 0.90}))

    # ---- PROVIDER DEGRADED (operational; conditional) ----
    degraded = _c("anthropic", "claude-sonnet-4-5", "claude", pin=3.0, pout=15.0,
                  **healthy(latency=1500, reliability=0.6))
    degraded.signals["degraded"] = sig(True)
    steady = _c("google", "gemma-4-31b-it", "gemma", pin=0.3, pout=0.3, **healthy(latency=1120))
    S.append(Scenario("provider_degraded", "operational",
        "Best model is in partial outage (reliability 0.6). Gate marks it INELIGIBLE (operational fail) / conditional; policy prefers the steady one.",
        R("req_deg", context_tokens=3000),
        [degraded, steady],
        {"claude-sonnet-4-5": GroundTruth(True, True, 1500, 0.90, 0.10),  # sometimes works, but degraded
         "gemma-4-31b-it": GroundTruth(True, True, 1120, 0.74, 0.003)},
        {"claude-sonnet-4-5": 0.90, "gemma-4-31b-it": 0.74}))

    return S


SCENARIOS = build()
