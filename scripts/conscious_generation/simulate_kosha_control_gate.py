#!/usr/bin/env python3
"""simulate_kosha_control_gate.py — CPU-SAFE simulation of a Kosha control-plane readiness/entropy gate.

Pre-reg: docs/KOSHA_CONTROL_PLANE_GATE_PREREG.md. NEW hypothesis, distinct from the failed K2 prompt
modifier (K2 = CG_KOSHA_K2_DEGRADES_FRAME tested Kosha-as-prompt-text; this tests Kosha-as-control-plane
emit/defer/hedge/depth-cap decisions over EXISTING traces). This file:
  * does NOT touch runtime, prompt construction, or any model generation path;
  * does NOT add Quad/Phase/recursion behavior;
  * uses a DETERMINISTIC query-derived p_k from the existing Kosha selector (NOT hidden-state, NOT trained);
  * blocks the hidden-state p_k path until real Kosha labels pass the surface-baseline gate;
  * compares gate decisions to NO_GATE / RANDOM_GATE baselines and (when outcome labels exist) reports
    whether the gate would have made BETTER or WORSE emit/withhold decisions — honestly, no tuning.

The frozen parameters are declared in the pre-reg and MUST NOT be tuned after seeing outcomes.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_HERE = Path(__file__).resolve().parent
_CSR = _HERE.parent / "cg_wrapper_ablation"
if str(_CSR) not in sys.path:
    sys.path.insert(0, str(_CSR))
# NOTE: we import ONLY the deterministic scoring selector — never the prompt-block or generation paths.
from csr_match_filter.kosha import select_kosha_depth, KoshaLevel   # noqa: E402

LOG5 = math.log(5.0)
LEVELS = ("annamaya", "pranamaya", "manomaya", "vijnanamaya", "anandamaya")
EMIT_DECISIONS = ("EMIT", "HEDGE", "DEFER")
DEPTH_DECISIONS = ("DEPTH_CAP_HIGH", "DEPTH_CAP_LOW")

# overall simulation verdicts (pre-registered label set)
SIM_LABELS = ("KOSHA_CONTROL_SIM_READY", "KOSHA_CONTROL_SIM_OUTCOMES_UNAVAILABLE",
              "KOSHA_CONTROL_SIM_NO_SIGNAL", "KOSHA_CONTROL_SIM_BEATS_BASELINES",
              "KOSHA_CONTROL_SIM_DEGRADES_GUARDRAILS", "KOSHA_CONTROL_SIM_PARAMETER_TUNING_RISK",
              "KOSHA_CONTROL_SIM_HIDDEN_PK_BLOCKED")

# findings (from the Phase-3 audit trace) that count as frame failure / rejected-domain leak
_FRAME_FAIL_FINDINGS = frozenset({"primary_frame_missing", "secondary_promoted_to_primary"})
_REJECTED_LEAK_FINDINGS = frozenset({"rejected_domain_promoted", "rejected_domain_mentioned_as_refutation"})


# ====================================================================================================
# Frozen parameters (declared in the pre-reg; do NOT tune after seeing outcomes)
# ====================================================================================================
@dataclass(frozen=True)
class GateParams:
    tau_K: float = 0.55           # Kosha-entropy soft-gate threshold (normalized)
    kappa: float = 8.0            # soft-gate sharpness
    alpha_K: float = 1.0          # Kosha recursion-modulation weight (reported, not wired)
    a: float = 0.0               # weight on (tau_D - H_D)  [H_D unavailable -> term drops out at a=0]
    b: float = 0.0               # weight on (tau_G - H_G)  [H_G unavailable -> term drops out at b=0]
    c: float = 1.0               # weight on (tau_K - H_K_norm)
    d: float = 1.0               # weight on R_K
    tau_emit: float = 0.55        # E_emit >= -> EMIT
    tau_hedge: float = 0.45       # E_emit in [tau_hedge, tau_emit) -> HEDGE ; below -> DEFER
    tau_defer: float = 0.35       # documentation of the DEFER band lower edge
    max_depth_default: int = 1    # depth cap when not high-readiness (reported, not wired)
    # auxiliary fixed defaults for unavailable trace fields (clearly labelled when used)
    H_D_default: float = 0.5      # used only if a != 0 and H_D absent
    H_G_default: float = 0.5      # used only if b != 0 and H_G absent
    tau_D: float = 0.55
    tau_G: float = 0.55
    R_res_default: float = 1.0    # residual readiness default when absent
    softmax_temp: float = 0.5     # selector-score -> p_k softmax temperature (frozen)
    # pre-registered pass thresholds for the overall verdict
    min_separation: float = 0.15        # P(withhold|bad) - P(withhold|good) to be "useful"
    max_withhold_good: float = 0.20     # max fraction of GOOD answers withheld
    min_beat_random: float = 0.10       # separation must beat random baseline by this
    degrade_separation: float = -0.10   # separation below this = actively harmful


DEFAULTS = GateParams()


# ====================================================================================================
# Core formulas (pure, CPU-only, deterministic)
# ====================================================================================================
def sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _normalize_pk(p_k: List[float]) -> List[float]:
    if len(p_k) != 5:
        raise ValueError(f"p_k must have 5 entries (got {len(p_k)})")
    if any(v < 0 for v in p_k):
        raise ValueError("p_k entries must be >= 0")
    s = float(sum(p_k))
    if s <= 0:
        return [0.2] * 5
    return [v / s for v in p_k]


def kosha_entropy(p_k: List[float]) -> float:
    """Shannon entropy H_K (nats) of a 5-state Kosha distribution. 0 for one-hot, log(5) for uniform."""
    p = _normalize_pk(p_k)
    h = 0.0
    for v in p:
        if v > 0:
            h -= v * math.log(v)
    return h


def normalized_entropy(p_k: List[float]) -> float:
    """H_K_norm = H_K / log(5) in [0, 1]. 0 for one-hot, 1 for uniform."""
    return kosha_entropy(p_k) / LOG5


def kosha_readiness(p_k: List[float], target_idx: int) -> float:
    """R_K = p_target * (1 - H_K_norm). High when the target Kosha state is probable AND peaked."""
    p = _normalize_pk(p_k)
    if not (0 <= target_idx < 5):
        raise ValueError("target_idx out of range")
    return p[target_idx] * (1.0 - normalized_entropy(p))


def kosha_emit_score(p_k: List[float], target_idx: int, params: GateParams = DEFAULTS,
                     *, H_D: Optional[float] = None, H_G: Optional[float] = None,
                     R_res: Optional[float] = None) -> Tuple[float, Dict]:
    """E_emit = R_res * sigmoid(a(tau_D-H_D) + b(tau_G-H_G) + c(tau_K-H_K_norm) + d*R_K).
    Returns (E_emit, provenance). Missing H_D/H_G/R_res fall back to declared defaults (flagged)."""
    p = _normalize_pk(p_k)
    h_k = normalized_entropy(p)
    r_k = kosha_readiness(p, target_idx)
    used = []
    if params.a != 0.0:
        hd = H_D if H_D is not None else (used.append("H_D_default"), params.H_D_default)[1]
    else:
        hd = 0.0
    if params.b != 0.0:
        hg = H_G if H_G is not None else (used.append("H_G_default"), params.H_G_default)[1]
    else:
        hg = 0.0
    rr = R_res if R_res is not None else (used.append("R_res_default"), params.R_res_default)[1]
    z = (params.a * (params.tau_D - hd) + params.b * (params.tau_G - hg)
         + params.c * (params.tau_K - h_k) + params.d * r_k)
    e = rr * sigmoid(z)
    return e, {"H_K_norm": round(h_k, 4), "R_K": round(r_k, 4), "z": round(z, 4),
               "used_defaults": used}


def decide_control(E_emit: float, R_K: float, H_K_norm: float,
                   params: GateParams = DEFAULTS) -> Tuple[str, str]:
    """Deterministic (emit_decision, depth_decision). Simulation only — NEVER affects runtime."""
    if E_emit >= params.tau_emit:
        emit = "EMIT"
    elif E_emit >= params.tau_hedge:
        emit = "HEDGE"
    else:
        emit = "DEFER"
    depth = "DEPTH_CAP_HIGH" if (R_K >= 0.65 and H_K_norm <= 0.45) else "DEPTH_CAP_LOW"
    return emit, depth


# ====================================================================================================
# Deterministic query-derived p_k (NOT hidden-state, NOT trained)
# ====================================================================================================
def selector_to_pk(query: str, *, primary_domain: Optional[str] = None,
                   params: GateParams = DEFAULTS) -> Tuple[List[float], int]:
    """Convert the existing deterministic Kosha selector's additive scores into a query-derived p_k via a
    frozen-temperature softmax. Returns (p_k over LEVELS order, target_idx = selected primary level).
    This is a HEURISTIC p_k: not hidden-state, not a trained estimator, cannot support a learned claim."""
    sel = select_kosha_depth(query or "", primary_domain=primary_domain)
    scores = sel.features.get("scores", {})                     # only >0 levels present
    vec = [float(scores.get(lvl, 0.0)) for lvl in LEVELS]
    if max(vec) <= 0.0:
        p_k = [0.2] * 5                                         # no depth cue -> uniform (max entropy)
    else:
        t = max(params.softmax_temp, 1e-6)
        m = max(vec)
        exps = [math.exp((v - m) / t) for v in vec]
        ssum = sum(exps)
        p_k = [e / ssum for e in exps]
    target_idx = LEVELS.index(sel.level.value)
    return p_k, target_idx


def blocked_hidden_pk_report(reason: str = "real Kosha labels have not passed the surface-baseline gate"):
    return {"decision": "KOSHA_CONTROL_SIM_HIDDEN_PK_BLOCKED",
            "note": f"hidden-state p_k is BLOCKED: {reason}. Use --pk-source selector (deterministic).",
            "blocker": ["real Kosha labels exist", "labels pass non-circular usability gate",
                        "hidden-state probe beats surface-feature baseline"]}


# ====================================================================================================
# Trace loading + outcome extraction (CPU-only; no GPU, no generation)
# ====================================================================================================
def normalize_row(row: dict) -> dict:
    """Normalize a trace row to {id, query, primary_domain, secondary_domains, rejected_domains, slice,
    outcomes}. outcomes is None when no trusted outcome label is present."""
    rid = row.get("id") or row.get("item_id") or ""
    query = row.get("query") or row.get("prompt") or ""
    fix = row.get("csr_trace_fixture") or {}
    pri = row.get("primary_domain")
    if pri is None:
        pds = fix.get("primary_domains") or row.get("primary_domains") or []
        pri = pds[0] if pds else None
    sec = row.get("secondary_domains") or fix.get("secondary_domains") or []
    rej = row.get("rejected_domains") or fix.get("rejected_domains") or []
    outcomes = None
    if "expected_needs_rewrite" in row or "expected_passed" in row or "expected_findings" in row:
        findings = set(row.get("expected_findings") or [])
        good = bool(row.get("expected_passed")) if "expected_passed" in row \
            else (not bool(row.get("expected_needs_rewrite")))
        audit_fail = bool(row.get("expected_needs_rewrite")) if "expected_needs_rewrite" in row \
            else (not good)
        outcomes = {
            "good_answer": good,
            "audit_failure": audit_fail,
            "frame_failure": bool(findings & _FRAME_FAIL_FINDINGS),
            "rejected_domain_leak": bool(findings & _REJECTED_LEAK_FINDINGS),
        }
    return {"id": rid, "query": query, "primary_domain": pri, "secondary_domains": list(sec),
            "rejected_domains": list(rej), "slice": row.get("slice"), "outcomes": outcomes}


def load_traces(path: Path) -> List[dict]:
    """Recognized formats: (a) JSONL of audit rows (expected_* fields -> outcomes);
    (b) JSON dict with 'queries' (e.g. kosha_k2_queries.json; NO outcomes);
    (c) JSON dict with 'per_example'; (d) JSON list of rows."""
    text = path.read_text()
    if path.suffix == ".jsonl":
        rows = [json.loads(l) for l in text.splitlines() if l.strip()]
    else:
        blob = json.loads(text)
        if isinstance(blob, list):
            rows = blob
        elif isinstance(blob, dict):
            rows = blob.get("queries") or blob.get("per_example") or blob.get("rows") or []
        else:
            rows = []
    return [normalize_row(r) for r in rows]


# ====================================================================================================
# Simulation over traces + baselines
# ====================================================================================================
def simulate(traces: List[dict], params: GateParams = DEFAULTS) -> List[dict]:
    """Run the deterministic gate over each trace. Pure: no runtime/prompt/model side effects."""
    out = []
    for t in traces:
        p_k, tgt = selector_to_pk(t["query"], primary_domain=t["primary_domain"], params=params)
        e, prov = kosha_emit_score(p_k, tgt, params)
        emit, depth = decide_control(e, prov["R_K"], prov["H_K_norm"], params)
        out.append({"id": t["id"], "slice": t.get("slice"), "p_k": [round(v, 4) for v in p_k],
                    "target_level": LEVELS[tgt], "E_emit": round(e, 4), "R_K": prov["R_K"],
                    "H_K_norm": prov["H_K_norm"], "emit_decision": emit, "depth_decision": depth,
                    "used_defaults": prov["used_defaults"], "outcomes": t["outcomes"]})
    return out


def no_gate_decisions(n: int) -> List[str]:
    return ["EMIT"] * n


def random_gate_decisions(gate_emit: List[str], seed: int = 1234) -> List[str]:
    """Random baseline with the SAME marginal decision distribution as the gate (seeded, reproducible)."""
    rng = random.Random(seed)
    pool = list(gate_emit)
    rng.shuffle(pool)                                           # permute -> identical marginals, broken link
    return pool


def query_length_decisions(traces: List[dict], params: GateParams = DEFAULTS) -> List[str]:
    """Simple length/complexity heuristic baseline: long/complex queries EMIT, very short ones DEFER."""
    dec = []
    for t in traces:
        wc = len((t["query"] or "").split())
        dec.append("EMIT" if wc >= 8 else ("HEDGE" if wc >= 4 else "DEFER"))
    return dec


# ---- metrics --------------------------------------------------------------------------------------
def _rate(flags) -> float:
    flags = list(flags)
    return round(sum(1 for f in flags if f) / len(flags), 4) if flags else 0.0


def _phi(x: List[int], y: List[int]) -> Optional[float]:
    """Pearson correlation of two 0/1 vectors (= phi). None if a vector is constant."""
    n = len(x)
    if n == 0:
        return None
    mx, my = sum(x) / n, sum(y) / n
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    dx = math.sqrt(sum((a - mx) ** 2 for a in x))
    dy = math.sqrt(sum((b - my) ** 2 for b in y))
    if dx == 0 or dy == 0:
        return None
    return round(num / (dx * dy), 4)


def _withhold(dec: str) -> int:
    return 1 if dec in ("HEDGE", "DEFER") else 0


def decision_metrics(sim_rows: List[dict], emit_decisions: Optional[List[str]] = None) -> dict:
    """Compute decision distribution + (if outcomes present) the guardrail-relevant separation metrics for
    a given decision vector (defaults to the gate's own emit_decision)."""
    n = len(sim_rows)
    decs = emit_decisions if emit_decisions is not None else [r["emit_decision"] for r in sim_rows]
    from collections import Counter
    dist = dict(Counter(decs))
    depth_hi = _rate(r["depth_decision"] == "DEPTH_CAP_HIGH" for r in sim_rows)
    m = {"total": n, "decision_distribution": dist,
         "emit_rate": _rate(d == "EMIT" for d in decs),
         "hedge_rate": _rate(d == "HEDGE" for d in decs),
         "defer_rate": _rate(d == "DEFER" for d in decs),
         "depth_cap_high_rate": depth_hi}

    have_outcomes = all(r["outcomes"] is not None for r in sim_rows) and n > 0
    if not have_outcomes:
        m["outcomes_available"] = False
        return m
    m["outcomes_available"] = True
    good = [r for r, d in zip(sim_rows, decs) if r["outcomes"]["good_answer"]]
    bad = [r for r, d in zip(sim_rows, decs) if r["outcomes"]["audit_failure"]]
    good_decs = [d for r, d in zip(sim_rows, decs) if r["outcomes"]["good_answer"]]
    bad_decs = [d for r, d in zip(sim_rows, decs) if r["outcomes"]["audit_failure"]]
    withhold = [_withhold(d) for d in decs]
    m["would_defer_good_answer_rate"] = _rate(d == "DEFER" for d in good_decs)
    m["would_emit_bad_answer_rate"] = _rate(d == "EMIT" for d in bad_decs)
    m["would_hedge_bad_answer_rate"] = _rate(d == "HEDGE" for d in bad_decs)
    m["withhold_good_rate"] = _rate(_withhold(d) for d in good_decs)       # guardrail violation rate
    m["withhold_bad_rate"] = _rate(_withhold(d) for d in bad_decs)
    m["guardrail_violation_rate"] = m["withhold_good_rate"]
    m["separation"] = round(m["withhold_bad_rate"] - m["withhold_good_rate"], 4)
    m["corr_withhold_audit_failure"] = _phi(withhold, [int(r["outcomes"]["audit_failure"]) for r in sim_rows])
    m["corr_withhold_frame_failure"] = _phi(withhold, [int(r["outcomes"]["frame_failure"]) for r in sim_rows])
    m["corr_withhold_rejected_leak"] = _phi(withhold, [int(r["outcomes"]["rejected_domain_leak"]) for r in sim_rows])
    if any(r["slice"] for r in sim_rows):
        by = {}
        for r, d in zip(sim_rows, decs):
            by.setdefault(r["slice"] or "none", Counter())[d] += 1
        m["decision_by_slice"] = {k: dict(v) for k, v in by.items()}
    return m


# ---- overall verdict (pre-registered gate; pre-registered labels only) ----------------------------
def verdict(gate_m: dict, random_m: dict, params: GateParams, *,
            params_are_default: bool) -> Tuple[str, dict]:
    notes = {"params_are_default": params_are_default}
    if not gate_m.get("outcomes_available"):
        return "KOSHA_CONTROL_SIM_OUTCOMES_UNAVAILABLE", notes
    sep = gate_m["separation"]
    rnd_sep = random_m.get("separation", 0.0)
    notes.update({"separation": sep, "random_separation": rnd_sep,
                  "withhold_good_rate": gate_m["withhold_good_rate"],
                  "beats_random_by": round(sep - rnd_sep, 4)})
    if sep <= params.degrade_separation or gate_m["withhold_good_rate"] > 0.5:
        return "KOSHA_CONTROL_SIM_DEGRADES_GUARDRAILS", notes
    if (sep >= params.min_separation and gate_m["withhold_good_rate"] <= params.max_withhold_good
            and (sep - rnd_sep) >= params.min_beat_random):
        label = "KOSHA_CONTROL_SIM_BEATS_BASELINES"
    else:
        label = "KOSHA_CONTROL_SIM_NO_SIGNAL"
    if not params_are_default:
        notes["parameter_tuning_risk"] = "KOSHA_CONTROL_SIM_PARAMETER_TUNING_RISK"
    return label, notes


def run(traces: List[dict], params: GateParams = DEFAULTS, *, params_are_default: bool = True,
        random_seed: int = 1234) -> dict:
    sim_rows = simulate(traces, params)
    gate_m = decision_metrics(sim_rows)
    rnd_decs = random_gate_decisions([r["emit_decision"] for r in sim_rows], seed=random_seed)
    nogate_m = decision_metrics(sim_rows, no_gate_decisions(len(sim_rows)))
    random_m = decision_metrics(sim_rows, rnd_decs)
    qlen_m = decision_metrics(sim_rows, query_length_decisions(traces, params))
    label, notes = verdict(gate_m, random_m, params, params_are_default=params_are_default)
    return {"n": len(traces), "pk_source": "selector_deterministic_heuristic",
            "params": asdict(params), "params_are_default": params_are_default,
            "gate": gate_m, "baselines": {"NO_GATE": nogate_m, "RANDOM_GATE": random_m,
                                          "QUERY_LENGTH": qlen_m},
            "decision": label, "decision_notes": notes,
            "decision_labels": list(SIM_LABELS), "per_example": sim_rows}


# ====================================================================================================
# Reports
# ====================================================================================================
def to_markdown(rep: dict) -> str:
    if rep.get("decision") == "KOSHA_CONTROL_SIM_HIDDEN_PK_BLOCKED":
        L = ["# Kosha control-plane gate sim — HIDDEN p_k BLOCKED", "",
             f"- **DECISION: `{rep['decision']}`**", f"- {rep.get('note', '')}", "",
             "Unblock requires:"] + [f"  - {b}" for b in rep.get("blocker", [])]
        return "\n".join(L) + "\n"
    g = rep["gate"]
    L = ["# Kosha control-plane readiness/entropy gate — CPU simulation", "",
         f"- n: **{rep['n']}**  ·  p_k source: `{rep['pk_source']}`  (deterministic, NOT hidden-state)",
         f"- **DECISION: `{rep['decision']}`**",
         f"- params default (no tuning): **{rep['params_are_default']}**", "",
         "## Gate decision distribution",
         f"- emit_rate **{g['emit_rate']}** · hedge_rate **{g['hedge_rate']}** · "
         f"defer_rate **{g['defer_rate']}** · depth_cap_high_rate **{g['depth_cap_high_rate']}**",
         f"- distribution: `{g['decision_distribution']}`", ""]
    if g.get("outcomes_available"):
        L += ["## Guardrail separation (outcome-labelled)",
              f"- separation (withhold|bad − withhold|good): **{g['separation']}**",
              f"- withhold_good_rate (guardrail violation): **{g['withhold_good_rate']}** · "
              f"withhold_bad_rate: **{g['withhold_bad_rate']}**",
              f"- would_defer_good_answer_rate: {g['would_defer_good_answer_rate']} · "
              f"would_emit_bad_answer_rate: {g['would_emit_bad_answer_rate']} · "
              f"would_hedge_bad_answer_rate: {g['would_hedge_bad_answer_rate']}",
              f"- corr(withhold, audit_failure): {g['corr_withhold_audit_failure']} · "
              f"frame_failure: {g['corr_withhold_frame_failure']} · "
              f"rejected_leak: {g['corr_withhold_rejected_leak']}", "",
              "## Baseline comparison (separation)",
              f"- GATE: **{g['separation']}** · RANDOM_GATE: "
              f"{rep['baselines']['RANDOM_GATE'].get('separation')} · QUERY_LENGTH: "
              f"{rep['baselines']['QUERY_LENGTH'].get('separation')} · NO_GATE: 0.0 (emits all)", ""]
        if "decision_by_slice" in g:
            L.append(f"- decision_by_slice: `{g['decision_by_slice']}`")
    else:
        L += ["## Outcomes",
              "- **KOSHA_CONTROL_SIM_OUTCOMES_UNAVAILABLE** — this trace set has no trusted outcome",
              "  labels; only the decision distribution is reported. No signal is claimed."]
    L += ["", f"- notes: `{rep['decision_notes']}`", "",
          "> Simulation only. Deterministic query-derived p_k (NOT hidden-state, NOT trained, NOT a",
          "> learned-state claim). No runtime, prompt, or generation path is touched. Distinct from the",
          "> failed K2 prompt modifier. Unvalidated until it beats baselines on trusted outcome-labelled",
          "> traces without post-hoc parameter tuning."]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="CPU simulation of a Kosha control-plane readiness/entropy gate.")
    ap.add_argument("--input", default=str(_CSR / "csr_match_filter" / "eval_data" / "answer_audit_eval.jsonl"),
                    help="trace file (JSONL audit rows / JSON {queries|per_example|rows} / JSON list)")
    ap.add_argument("--out", default="runs/kosha_control/sim.json")
    ap.add_argument("--report", default="runs/kosha_control/sim.md")
    ap.add_argument("--pk-source", choices=("selector", "hidden"), default="selector",
                    help="selector = deterministic query-derived (allowed); hidden = BLOCKED")
    ap.add_argument("--seed", type=int, default=1234)
    args = ap.parse_args(argv)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    if args.pk_source == "hidden":
        rep = blocked_hidden_pk_report()
        rep["decision_labels"] = list(SIM_LABELS)
        Path(args.out).write_text(json.dumps(rep, indent=2))
        Path(args.report).write_text(to_markdown(rep))
        print(f"DECISION: {rep['decision']} (hidden-state p_k is blocked; wrote {args.out})")
        return 0

    traces = load_traces(Path(args.input))
    rep = run(traces, DEFAULTS, params_are_default=True, random_seed=args.seed)
    Path(args.out).write_text(json.dumps(rep, indent=2))
    Path(args.report).write_text(to_markdown(rep))
    print(f"n={rep['n']} DECISION: {rep['decision']}  (p_k=selector, CPU sim, no runtime/prompt change)")
    print(f"wrote {args.out} + {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
