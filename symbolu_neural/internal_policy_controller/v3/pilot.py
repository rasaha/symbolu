"""v3 orchestrator. Self-contained harness (local llm/judge/data). Fixes vs v2:
draft-states everywhere, no silent judge fallback, and a built-in field-influence
self-check that must pass before any (paid) quality run.
"""
from __future__ import annotations

import argparse
from typing import Dict, List
import copy

import numpy as np

from .data import prompts
from .llm import get_llm
from .judge import judge, RUBRIC
from .symbolu_state import compute_state, POLICY_DRIVING
from .policy import ARMS, AXES, policy_for_arm, translate, policy_divergence


# --------------------------------------------------------------------------- #
# Field-influence self-check (the v2-defect guardrail)
# --------------------------------------------------------------------------- #
def _cv(s, **kw):
    """helper: copy classical_vritti dict with overrides."""
    s.classical_vritti = {**s.classical_vritti, **kw}


_MUTS = {
    "classical_primary": lambda s: _cv(s, primary=("vikalpa" if s.classical_vritti["primary"] != "vikalpa" else "viparyaya")),
    "nidra_flag": lambda s: _cv(s, nidra=not s.classical_vritti["nidra"]),
    "smrti_flag": lambda s: _cv(s, smrti=not s.classical_vritti["smrti"]),
    "dynamic_state": lambda s: setattr(s, "dynamic_state",
        {k: (1.0 if k == "INERTIA" else 0.0) for k in s.dynamic_state}),
    "guna": lambda s: setattr(s, "guna", {"sattva": 0.0, "rajas": 0.0, "tamas": 1.0}),
    "kosha": lambda s: setattr(s, "kosha", {k: (1.0 if k == "vijnanamaya" else 0.0) for k in s.kosha}),
    "aspect_balance": lambda s: setattr(s, "aspect_balance", -1.0),
    # threshold-crossing (the uncertainty branch flips at 0.85)
    "guna_resonance": lambda s: setattr(s, "guna_resonance", 0.99 if s.guna_resonance < 0.85 else 0.5),
    "valence": lambda s: setattr(s, "valence", "liberating" if s.valence != "liberating" else "binding"),
}


def field_influence_check() -> Dict[str, bool]:
    """Proves each POLICY-DRIVING signal independently changes the policy — incl. the
    three sentence-level cognitive signals (classical_primary, nidra_flag, smrti_flag)
    and dynamic_state SEPARATELY."""
    base = compute_state("It might possibly be a good year; perhaps prices could rise.")
    ref = translate(base).as_dict()
    out = {}
    for f in POLICY_DRIVING:
        s = copy.deepcopy(base)
        _MUTS[f](s)
        out[f] = translate(s).as_dict() != ref
    return out


def field_influence_by_family() -> Dict[str, Dict]:
    """Which AXIS each cognitive signal / dynamic_state changes — proves the intended
    separation: primary->epistemic, nidra->clarification, smrti->memory, dynamic->delivery."""
    from .policy import COGNITIVE_AXES, DELIVERY_AXES
    base = compute_state("It might possibly be a good year; perhaps prices could rise.")
    ref = translate(base).as_dict()
    expect = {"classical_primary": "epistemic_stance", "nidra_flag": "clarification_policy",
              "smrti_flag": "memory_policy", "dynamic_state": "delivery_pace"}
    res = {}
    for fld in expect:
        s = copy.deepcopy(base); _MUTS[fld](s)
        d = translate(s).as_dict()
        changed = [a for a in AXES if d[a] != ref[a]]
        res[fld] = {"changed_axes": changed, "expected_axis": expect[fld],
                    "hits_expected": expect[fld] in changed,
                    "family": "delivery" if fld == "dynamic_state" else "cognitive"}
    return res


def structural_report(seed=0) -> dict:
    """Real, offline. NOTE: state computed from PROMPTS as a stand-in for drafts when
    no LLM is available; the quality path uses real draft-states."""
    ps = prompts()
    states = [compute_state(p) for p, _, _ in ps]
    other = states[1:] + states[:1]
    arms = ["nl_policy", "sentiment_critic", "random_policy", "shuffled_symbolu",
            "relabeled_symbolu", "symbolu"]
    div = {a: [] for a in arms}
    pols = set()
    for i in range(len(ps)):
        ref, _ = policy_for_arm("symbolu", states[i], other[i], seed)
        pols.add(tuple(ref.as_dict()[k] for k in AXES))
        for a in arms:
            p, _ = policy_for_arm(a, states[i], other[i], seed)
            div[a].append(policy_divergence(ref, p))
    return {"n_prompts": len(ps), "field_influence": field_influence_check(),
            "distinct_symbolu_policies": len(pols),
            "example_state": states[0].summary(),
            "example_policy": translate(states[0]).as_dict(),
            "policy_divergence_vs_symbolu": {a: float(np.mean(v)) for a, v in div.items()}}


def coverage_report() -> dict:
    """Offline census: which state-signal and policy-axis VALUES appear across the
    prompt set. Distinguishes 'wired & influences' (always true here) from 'every
    nominal value observed' (one value — RELEASE/anandamaya/'holistic' — is
    structurally near-unreachable on natural English text)."""
    from .cognitive_evaluator import evaluate_cognitive, PROBE_ANSWERS, PRIMARY_VRITTI
    ps = prompts()
    state_vals = {"primary_vritti": set(), "nidra_flag": set(), "smrti_flag": set(),
                  "dynamic_state_top": set(), "guna_top": set(), "kosha_top": set(), "valence": set()}
    cont = {"aspect_balance": [], "guna_resonance": []}
    axis_vals = {a: set() for a in AXES}
    for p, _, _ in ps:
        s = compute_state(p)
        sm = s.summary()
        state_vals["primary_vritti"].add(sm["classical_primary"])
        state_vals["nidra_flag"].add(sm["nidra"])
        state_vals["smrti_flag"].add(sm["smrti"])
        state_vals["dynamic_state_top"].add(sm["dynamic_state_top"])
        state_vals["guna_top"].add(sm["guna_top"])
        state_vals["kosha_top"].add(sm["kosha_top"])
        state_vals["valence"].add(sm["valence"])
        cont["aspect_balance"].append(s.aspect_balance)
        cont["guna_resonance"].append(s.guna_resonance)
        d = translate(s).as_dict()
        for a in AXES:
            axis_vals[a].add(d[a])
    nominal_state = {"primary_vritti": 3, "nidra_flag": 2, "smrti_flag": 2,
                     "dynamic_state_top": 5, "guna_top": 3, "kosha_top": 5, "valence": 3}
    nominal_axis = {"tone": 3, "delivery_pace": 5, "epistemic_stance": 3,
                    "clarification_policy": 2, "memory_policy": 2, "reasoning_style": 5,
                    "caution": 3, "uncertainty_handling": 2, "speculation_reduction": 3, "clarity": 1}
    # evaluator reachability: classical_vritti is about ANSWERS, so census crafted probes
    probe_primary = {evaluate_cognitive(a)["primary"] for a in PROBE_ANSWERS.values()}
    probe_nidra = {evaluate_cognitive(a)["nidra"] for a in PROBE_ANSWERS.values()}
    probe_smrti = {evaluate_cognitive(a)["smrti"] for a in PROBE_ANSWERS.values()}
    return {
        "n_prompts": len(ps),
        "state": {k: {"seen": sorted(map(str, v)), "n": len(v), "nominal": nominal_state[k]}
                  for k, v in state_vals.items()},
        "continuous": {k: {"min": round(min(v), 3), "max": round(max(v), 3)}
                       for k, v in cont.items()},
        "axes": {a: {"seen": sorted(v), "n": len(v), "nominal": nominal_axis[a]}
                 for a, v in axis_vals.items()},
        "evaluator_reachability": {"primary": sorted(probe_primary),
                                   "nidra": sorted(map(str, probe_nidra)),
                                   "smrti": sorted(map(str, probe_smrti))},
        "field_influence": field_influence_check(),
        "field_influence_by_family": field_influence_by_family(),
    }


def run_quality(backend="mock", model=None, seed=0) -> dict:
    llm = get_llm(backend, model)
    ps = prompts()
    drafts = [llm.chat("You are a helpful assistant. Answer the user.", p, seed)
              for p, _, _ in ps]
    states = [compute_state(d) for d in drafts]           # state FROM DRAFT (fix D6)
    other = states[1:] + states[:1]
    out = {"backend": backend, "is_real": llm.is_real, "arms": {}, "judge_failures": 0}
    for arm in ARMS:
        sc = {k: [] for k in RUBRIC}
        prefer = []
        per_prompt = []                                      # per-prompt rubric mean (for CIs)
        for i, (prompt, _para, _cat) in enumerate(ps):
            pol, mode = policy_for_arm(arm, states[i], other[i], seed)
            if mode == "none":
                final = drafts[i]
            elif mode == "self_refine":
                final = llm.chat("Critique your previous draft for clarity, caution, and "
                                 "directness, then output an improved version. Return only "
                                 "the improved answer.",
                                 f"PROMPT:\n{prompt}\n\nDRAFT:\n{drafts[i]}", seed)
            else:
                final = llm.chat("You revise answers to follow a response policy.",
                                 f"PROMPT:\n{prompt}\n\nDRAFT:\n{drafts[i]}\n\n{pol.render()}", seed)
            v = judge(llm, prompt, drafts[i], final)
            if all(v.get(k, 0) == 0 for k in RUBRIC):       # surface judge failures (fix D7)
                out["judge_failures"] += 1
            for k in RUBRIC:
                sc[k].append(float(v.get(k, 0)))
            per_prompt.append(float(np.mean([v.get(k, 0) for k in RUBRIC])))
            prefer.append(1.0 if v.get("prefer_final") else 0.0)
        out["arms"][arm] = {**{k: float(np.mean(s)) for k, s in sc.items()},
                            "prefer_final": float(np.mean(prefer)),
                            "per_prompt": per_prompt,         # length = n_prompts, aligned by i
                            "rubric_mean": float(np.mean([np.mean(s) for s in sc.values()]))}
    return out


# --------------------------------------------------------------------------- #
# Multi-seed aggregation with confidence intervals (statistical validity)
# --------------------------------------------------------------------------- #
def _ci95(x):
    """mean and 95% CI half-width (normal approx) for a 1-D sample."""
    x = np.asarray(x, float)
    n = len(x)
    if n < 2:
        return (float(x.mean()) if n else 0.0), float("nan")
    return float(x.mean()), float(1.96 * x.std(ddof=1) / np.sqrt(n))


def run_multi(backend="mock", model=None, seeds=(0, 1, 2)) -> dict:
    """Run run_quality for each seed; pool per-(prompt,seed) samples for CIs.
    Pairs symbolu vs each control by (seed,prompt) -> paired-difference CIs."""
    runs = [run_quality(backend, model, s) for s in seeds]
    is_real = runs[0]["is_real"]
    pooled = {arm: [v for r in runs for v in r["arms"][arm]["per_prompt"]] for arm in ARMS}
    n = len(pooled["symbolu"])
    arms_ci = {}
    for arm in ARMS:
        m, h = _ci95(pooled[arm])
        arms_ci[arm] = {"mean": m, "ci95": h}
    # paired diffs: symbolu - control, aligned index-by-index (same seed,prompt order)
    su = np.asarray(pooled["symbolu"], float)
    paired = {}
    for ref in ["draft_only", "generic_refine", "nl_policy", "sentiment_critic",
                "random_policy", "shuffled_symbolu", "relabeled_symbolu"]:
        d = su - np.asarray(pooled[ref], float)
        m, h = _ci95(d)
        paired[ref] = {"diff": m, "ci95": h,
                       "significant": bool(not np.isnan(h) and (m - h > 0 or m + h < 0))}
    return {"backend": backend, "is_real": is_real, "seeds": list(seeds),
            "n_per_arm": n, "judge_failures": sum(r["judge_failures"] for r in runs),
            "arms_ci": arms_ci, "paired_vs_symbolu": paired}


def print_multi(res: dict) -> None:
    print("=" * 80)
    print(f"INTERNAL POLICY CONTROLLER v3 — MULTI-SEED  "
          f"backend={res['backend']} real_LLM={res['is_real']} "
          f"seeds={res['seeds']} n/arm={res['n_per_arm']}")
    print("=" * 80)
    if not res["is_real"]:
        print("*** MOCK: no real rewrite/judge — NO QUALITY VERDICT (plumbing only).")
        print("*** Run --backend anthropic|mistral --seeds 3 with a key for the real test.")
        return
    print(f"judge_failures={res['judge_failures']}\n")
    print(f"{'arm':<18}{'rubric_mean':>13}{'95% CI':>14}")
    print("-" * 45)
    for arm in ARMS:
        c = res["arms_ci"][arm]
        print(f"{arm:<18}{c['mean']:>13.3f}{('±%.3f' % c['ci95']):>14}")
    print("\nPaired difference  (symbolu − control), 95% CI; SIG = CI excludes 0:")
    print("-" * 60)
    for ref, p in res["paired_vs_symbolu"].items():
        verdict = ("BEATS" if p["significant"] and p["diff"] > 0 else
                   "WORSE" if p["significant"] and p["diff"] < 0 else "ns")
        print(f"  vs {ref:<18} Δ={p['diff']:+.3f} ±{p['ci95']:.3f}   [{verdict}]")
    rel = res["paired_vs_symbolu"]["relabeled_symbolu"]
    print("\nOntology check: symbolu vs relabeled_symbolu "
          f"Δ={rel['diff']:+.3f} ±{rel['ci95']:.3f} -> "
          f"{'specific ontology matters' if rel['significant'] and rel['diff']>0 else 'ontology NOT shown to matter'}")


def print_report(seed=0, backend="mock", model=None) -> None:
    s = structural_report(seed)
    print("=" * 80)
    print("INTERNAL POLICY CONTROLLER v3")
    print("=" * 80)
    fi = s["field_influence"]
    print("\n[SELF-CHECK] every policy-driving Symbol-U variable influences the policy:")
    for f, ok in fi.items():
        print(f"   {f:16} {'OK' if ok else '*** DEFECT: ZERO INFLUENCE ***'}")
    print(f"   ALL PASS: {all(fi.values())}   distinct symbolu policies: "
          f"{s['distinct_symbolu_policies']}/{s['n_prompts']} (v2 had 4)")
    print(f"\n[STRUCTURAL — real, offline] example state: {s['example_state']}")
    print(f"   example policy: {s['example_policy']}")
    print("   policy divergence vs symbolu (relabel>0 => ontology labels matter):")
    for a, d in s["policy_divergence_vs_symbolu"].items():
        print(f"     {a:<18} {d:.3f}")

    q = run_quality(backend, model, seed)
    print(f"\n[QUALITY — backend={backend} real_LLM={q['is_real']}]")
    if not q["is_real"]:
        print("   *** MOCK: no real rewrite/judge. NO QUALITY VERDICT. Plumbing only.")
        print("   *** Run --backend anthropic|mistral with an API key for the real test.")
        return
    print(f"   judge_failures={q['judge_failures']}")
    print(f"   {'arm':<18}{'rubric_mean':>12}{'prefer_final':>14}")
    for arm in ARMS:
        m = q["arms"][arm]
        print(f"   {arm:<18}{m['rubric_mean']:>12.3f}{m['prefer_final']:>14.3f}")
    su = q["arms"]["symbolu"]["rubric_mean"]
    print("\n   --- VERDICT (real LLM) ---")
    for ref in ["generic_refine", "nl_policy", "sentiment_critic", "random_policy",
                "shuffled_symbolu", "relabeled_symbolu"]:
        d = su - q["arms"][ref]["rubric_mean"]
        print(f"   symbolu vs {ref:<18}: {su:.3f} vs {q['arms'][ref]['rubric_mean']:.3f} "
              f"({'BEATS' if d > 0.1 else 'does NOT beat'})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="mock", choices=["mock", "anthropic", "mistral"])
    ap.add_argument("--model", default=None)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    print_report(args.seed, args.backend, args.model)


if __name__ == "__main__":
    main()
