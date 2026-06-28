"""v4 orchestrator. Reuses v3's gate-validated pairwise harness (independent judge,
position-debias, validity gate, bounded concurrency) but swaps in the v4 high-fidelity
translator. Adds a v4 bottleneck audit that measures TOKEN-level relabel divergence —
the headline number that must beat v3's 34%.
"""
from __future__ import annotations

import difflib
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List

import numpy as np

from ..v3.data import prompts
from ..v3.llm import get_llm
from ..v3.judge import judge_pairwise, judge_discriminates, pairwise_reason
from ..v3.symbolu_state import compute_state
from ..v3.pilot import _max_workers, _ci95
from .policy_v4 import ARMS, translate_v4, policy_for_arm_v4
from ..v3.policy import _relabel_state

CONTROLS = ["draft_only", "generic_refine", "nl_policy", "sentiment_critic",
            "random_policy", "shuffled_symbolu", "relabeled_symbolu"]


# --------------------------------------------------------------------------- #
# Bottleneck audit (offline) — does v4 actually preserve more than v3?
# --------------------------------------------------------------------------- #
def _token_divergence(a: str, b: str) -> float:
    """1 - difflib similarity ratio over whitespace tokens: fraction of the prompt
    that CHANGES. 0 = identical, 1 = totally different."""
    return 1.0 - difflib.SequenceMatcher(None, a.split(), b.split()).ratio()


def _field_divergence(a, b) -> float:
    """Fraction of structured policy fields that differ (the direct analog of v3's
    axis-change metric)."""
    da, db = a.as_dict(), b.as_dict()
    keys = [k for k in da if k != "source"]
    return float(np.mean([da[k] != db[k] for k in keys]))


def bottleneck_report_v4() -> dict:
    """Information-preservation audit, measured FAIRLY against v3 on BOTH metrics:
      * field-level relabel divergence (the direct analog of v3's 34% axis-change), and
      * token-level relabel divergence (how much of the actual PROMPT text changes).
    Both are computed for v3 and v4 so the comparison is apples-to-apples."""
    from ..v3.policy import translate as translate_v3, _FIXED_NL_POLICY
    ps = prompts()
    states = [compute_state(p) for p, _, _ in ps]

    def metrics(translate):
        pols = [translate(s) for s in states]
        rel = [translate(_relabel_state(s, 0)) for s in states]
        field = float(np.mean([_field_divergence(pols[i], rel[i]) for i in range(len(ps))]))
        tok = float(np.mean([_token_divergence(pols[i].render(), rel[i].render())
                             for i in range(len(ps))]))
        nl = float(np.mean([_token_divergence(p.render(), _FIXED_NL_POLICY.render()) for p in pols]))
        return {"field_div": round(field, 3), "token_div": round(tok, 3),
                "distinct_prompts": len(set(p.render() for p in pols)),
                "divergence_from_generic": round(nl, 3)}

    v3m, v4m = metrics(translate_v3), metrics(translate_v4)
    return {
        "n_prompts": len(ps),
        "v3": v3m, "v4": v4m,
        "relabel_field_divergence": v4m["field_div"],     # headline field-level (vs v3 0.34)
        "relabel_token_divergence": v4m["token_div"],      # headline token-level
        "distinct_prompts": v4m["distinct_prompts"],
        "field_gain_over_v3": round(v4m["field_div"] - v3m["field_div"], 3),
        "token_gain_over_v3": round(v4m["token_div"] - v3m["token_div"], 3),
    }


# --------------------------------------------------------------------------- #
# Pairwise A/B eval with the v4 translator (same gate-valid machinery as v3)
# --------------------------------------------------------------------------- #
def _arm_final_v4(llm, arm, prompt, draft, state, other_state, seed):
    pol, mode = policy_for_arm_v4(arm, state, other_state, seed)
    if mode == "none":
        return draft
    if mode == "self_refine":
        return llm.chat("Critique your previous draft for clarity, caution, and "
                        "directness, then output an improved version. Return only "
                        "the improved answer.",
                        f"PROMPT:\n{prompt}\n\nDRAFT:\n{draft}", seed)
    return llm.chat("You revise answers to follow a response policy.",
                    f"PROMPT:\n{prompt}\n\nDRAFT:\n{draft}\n\n{pol.render()}", seed)


def run_pairwise_v4(backend="mock", model=None, seed=0,
                    judge_backend=None, judge_model=None) -> dict:
    llm = get_llm(backend, model)
    jllm = get_llm(judge_backend, judge_model) if judge_backend else llm
    ps = prompts()
    with ThreadPoolExecutor(max_workers=_max_workers()) as pool:
        drafts = list(pool.map(
            lambda p: llm.chat("You are a helpful assistant. Answer the user.", p, seed),
            [p for p, _, _ in ps]))
        states = [compute_state(d) for d in drafts]
        other = states[1:] + states[:1]
        finals = {}
        for arm in ARMS:
            finals[arm] = list(pool.map(
                lambda i: _arm_final_v4(llm, arm, ps[i][0], drafts[i], states[i], other[i], seed),
                range(len(ps))))
        margins = {}
        for ctrl in CONTROLS:
            margins[ctrl] = list(pool.map(
                lambda i: judge_pairwise(jllm, ps[i][0], finals["symbolu"][i], finals[ctrl][i]),
                range(len(ps))))
        disc = judge_discriminates(jllm)
    return {"backend": backend, "judge_backend": jllm.backend,
            "is_real": bool(llm.is_real and jllm.is_real), "seed": seed,
            "margins": margins, "discriminates": disc}


def run_pairwise_multi_v4(backend="mock", model=None, seeds=(0, 1, 2),
                          judge_backend=None, judge_model=None) -> dict:
    runs = [run_pairwise_v4(backend, model, s, judge_backend, judge_model) for s in seeds]
    pooled = {c: [v for r in runs for v in r["margins"][c]] for c in CONTROLS}
    out = {}
    for c in CONTROLS:
        xs = pooled[c]
        m, h = _ci95(xs)
        wins = sum(1 for v in xs if v > 0)
        losses = sum(1 for v in xs if v < 0)
        out[c] = {"margin": m, "ci95": h,
                  "significant": bool(not np.isnan(h) and (m - h > 0 or m + h < 0)),
                  "wins": wins, "losses": losses, "ties": len(xs) - wins - losses, "n": len(xs)}
    disc = [r["discriminates"] for r in runs]
    return {"backend": backend, "judge_backend": runs[0]["judge_backend"],
            "is_real": runs[0]["is_real"], "seeds": list(seeds),
            "n_per_control": len(pooled[CONTROLS[0]]),
            "discrimination": {"per_seed": disc, "mean": float(np.mean(disc)) if disc else 0.0},
            "vs_symbolu": out}


def trace_v4(n=6, backend="mock", model=None, judge_backend=None, judge_model=None,
             seed=0, out_path=None) -> str:
    """FORENSIC capture: for the first `n` prompts, persist EVERYTHING the aggregate
    run discards — draft, draft-state, every arm's final answer, the exact v4 revision
    prompt, and the judge's winner+reason for symbolu vs each control. Writes a markdown
    file and returns its path. Cheap: ~n*(1 + 8 + 7) calls."""
    llm = get_llm(backend, model)
    jllm = get_llm(judge_backend, judge_model) if judge_backend else llm
    ps = prompts()[:n]
    drafts = [llm.chat("You are a helpful assistant. Answer the user.", p, seed) for p, _, _ in ps]
    states = [compute_state(d) for d in drafts]
    other = states[1:] + states[:1]

    def md_state(s):
        cv = s.classical_vritti
        dist = lambda d: ", ".join(f"{k} {v:.0%}" for k, v in sorted(d.items(), key=lambda x: -x[1]) if v > 0.01)
        return (f"- classical_vritti: primary={cv['primary']} nidra={cv['nidra']} smrti={cv['smrti']}\n"
                f"- dynamic_state: {dist(s.dynamic_state)}\n"
                f"- guna: {dist(s.guna)}\n- kosha: {dist(s.kosha)}\n"
                f"- aspect_balance={s.aspect_balance:.3f} guna_resonance={s.guna_resonance:.3f} "
                f"kosha_resonance={s.kosha_resonance:.3f} valence={s.valence} (sign {s.valence_sign:+.2f})")

    out = [f"# v4 FORENSIC TRACE  gen={llm.backend} judge={jllm.backend} "
           f"real={bool(llm.is_real and jllm.is_real)} n={n} seed={seed}\n",
           "_Judge uses single-order pairwise+reason for readability; the experiment's "
           "verdict uses the position-debiased judge. Reasons are the judge's own words._\n"]
    for i, (p, _para, cat) in enumerate(ps):
        s = states[i]
        finals = {arm: _arm_final_v4(llm, arm, p, drafts[i], s, other[i], seed) for arm in ARMS}
        out.append(f"\n---\n## [{cat}] {p}\n")
        out.append(f"**DRAFT:**\n\n> {drafts[i]}\n")
        out.append(f"**Symbol-U state (from the draft):**\n{md_state(s)}\n")
        out.append(f"**Exact v4 revision prompt sent to the LLM:**\n```\n{translate_v4(s).render()}\n```")
        out.append(f"**SYMBOLU final:**\n\n> {finals['symbolu']}\n")
        out.append("**Comparison arms (judge: symbolu=A vs control=B):**\n")
        for c in CONTROLS:
            v = pairwise_reason(jllm, p, finals["symbolu"], finals[c])
            win = {"a": "SYMBOLU wins", "b": f"{c} wins", "tie": "tie"}.get(v["winner"], v["winner"])
            out.append(f"- **vs {c}** -> {win} — _{v['reason']}_")
            out.append(f"  - {c} final: {finals[c][:400]}")
        out.append("")
    path = out_path or "v4_forensic_trace.md"
    with open(path, "w") as f:
        f.write("\n".join(out))
    return path


def print_pairwise_v4(res: dict) -> None:
    print("=" * 80)
    print(f"v4 PAIRWISE A/B EVAL  gen={res['backend']} judge={res['judge_backend']} "
          f"real_LLM={res['is_real']} seeds={res['seeds']} n/control={res['n_per_control']}")
    print("=" * 80)
    if not res["is_real"]:
        print("*** MOCK: judge cannot compare answers — NO VERDICT (plumbing only).")
        return
    dm = res["discrimination"]["mean"]
    gate = dm > 0.5
    print(f"JUDGE VALIDITY GATE: margin {dm:+.2f} -> "
          f"{'PASS — judge discriminates' if gate else 'FAIL — verdict INVALID'}")
    print("\nSymbolu(v4) vs each control — preference margin in [-1,+1] "
          "(+ = symbolu; SIG = CI excludes 0):")
    print("-" * 74)
    for c, r in res["vs_symbolu"].items():
        verdict = ("BEATS" if r["significant"] and r["margin"] > 0 else
                   "WORSE" if r["significant"] and r["margin"] < 0 else "tie (ns)")
        print(f"  vs {c:<18} margin={r['margin']:+.3f} ±{r['ci95']:.3f}  "
              f"W/L/T={r['wins']}/{r['losses']}/{r['ties']:>3}  [{verdict}]")
    rel = res["vs_symbolu"]["relabeled_symbolu"]
    print(f"\nOntology check (v4 symbolu vs relabeled): margin={rel['margin']:+.3f} "
          f"±{rel['ci95']:.3f} -> "
          f"{'specific ontology matters' if rel['significant'] and rel['margin'] > 0 else 'ontology NOT shown to matter'}")
    if not gate:
        print("\n*** Judge failed the validity gate: verdicts above are unreliable.")
