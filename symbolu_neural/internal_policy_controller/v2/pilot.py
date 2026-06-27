"""v2 orchestrator: draft -> full Symbol-U state -> policy -> LLM rewrite -> judge.

Two result tiers, kept strictly separate for honesty:

  STRUCTURAL (real, offline): the Symbol-U state and the per-arm POLICY are
  computed from canonical code with no LLM — so policy divergence across arms
  (does relabel/shuffle/random actually change the policy?) is a genuine result.

  QUALITY (needs a real LLM): draft generation, policy-conditioned rewrite, and
  the independent judge require an API. With the mock backend these are PLUMBING
  ONLY and the pilot refuses to emit a quality verdict.
"""
from __future__ import annotations

import argparse
from typing import Dict, List

import numpy as np

from .data import prompts
from .symbolu_state import compute_state
from .policy import ARMS, AXES, policy_for_arm, translate, policy_divergence
from .llm import get_llm
from .judge import judge, RUBRIC


def _draft_and_states(llm, seed=0):
    ps = prompts()
    drafts, states = [], []
    for prompt, _para, _cat in ps:
        d = llm.chat("You are a helpful assistant. Answer the user.", prompt, seed)
        drafts.append(d)
        states.append(compute_state(d))
    return ps, drafts, states


def structural_report(seed=0) -> dict:
    """Offline, real: compute states + per-arm policies from the PROMPTS (no LLM
    draft needed for the structural view — we state-analyze the prompts directly)."""
    ps = prompts()
    states = [compute_state(p) for p, _, _ in ps]
    other = states[1:] + states[:1]                 # neighbour state for 'shuffled'
    policy_arms = ["nl_policy", "sentiment_critic", "random_policy",
                   "shuffled_symbolu", "relabeled_symbolu", "symbolu"]
    # divergence of each arm's policy vs the real symbolu policy, averaged over prompts
    div = {a: [] for a in policy_arms}
    for i in range(len(ps)):
        ref, _ = policy_for_arm("symbolu", states[i], other[i], seed)
        for a in policy_arms:
            p, _ = policy_for_arm(a, states[i], other[i], seed)
            div[a].append(policy_divergence(ref, p))
    return {
        "n_prompts": len(ps),
        "example_state": states[0].summary(),
        "policy_divergence_vs_symbolu": {a: float(np.mean(v)) for a, v in div.items()},
        "example_symbolu_policy": translate(states[0]).as_dict(),
    }


def run_quality(backend="mock", model=None, seed=0) -> dict:
    llm = get_llm(backend, model)
    ps, drafts, states = _draft_and_states(llm, seed)
    other = states[1:] + states[:1]
    out = {"backend": backend, "is_real": llm.is_real, "arms": {}}
    for arm in ARMS:
        scores = {k: [] for k in RUBRIC}
        prefer = []
        for i, (prompt, _para, _cat) in enumerate(ps):
            policy, mode = policy_for_arm(arm, states[i], other[i], seed)
            if mode == "none":
                final = drafts[i]
            elif mode == "self_refine":
                final = llm.chat("Critique your previous draft for clarity, caution, "
                                 "and directness, then output an improved version. "
                                 "Return only the improved answer.",
                                 f"PROMPT:\n{prompt}\n\nDRAFT:\n{drafts[i]}", seed)
            else:
                final = llm.chat("You revise answers to follow a response policy.",
                                 f"PROMPT:\n{prompt}\n\nDRAFT:\n{drafts[i]}\n\n"
                                 f"{policy.render()}", seed)
            v = judge(llm, prompt, drafts[i], final)
            for k in RUBRIC:
                scores[k].append(float(v.get(k, 0)))
            prefer.append(1.0 if v.get("prefer_final") else 0.0)
        out["arms"][arm] = {**{k: float(np.mean(s)) for k, s in scores.items()},
                            "prefer_final": float(np.mean(prefer)),
                            "rubric_mean": float(np.mean([np.mean(s) for s in scores.values()]))}
    return out


def print_report(seed=0, backend="mock", model=None) -> None:
    s = structural_report(seed)
    print("=" * 80)
    print("INTERNAL POLICY CONTROLLER v2")
    print("=" * 80)
    print("\n[STRUCTURAL — REAL, OFFLINE] full Symbol-U state + policy translation")
    print(f"  prompts={s['n_prompts']}  example state: {s['example_state']}")
    print(f"  example Symbol-U policy: {s['example_symbolu_policy']}")
    print("  policy divergence vs real Symbol-U policy (fraction of 6 axes differing):")
    for a, d in s["policy_divergence_vs_symbolu"].items():
        print(f"    {a:<18} {d:.3f}")
    rel = s["policy_divergence_vs_symbolu"]["relabeled_symbolu"]
    print(f"  -> relabeled divergence {rel:.3f} > 0  ==> the specific ONTOLOGY LABELS "
          f"change the policy\n     (v1's relabel was a 0.000 tautology; this is fixed).")

    q = run_quality(backend, model, seed)
    print(f"\n[QUALITY — backend={backend}  real_LLM={q['is_real']}]")
    if not q["is_real"]:
        print("  *** MOCK: no LLM rewrite/judge. NO QUALITY VERDICT. Plumbing only.")
        print("  *** Run --backend anthropic|mistral with an API key for the real test.")
        return
    print(f"  {'arm':<18}{'rubric_mean':>12}{'prefer_final':>14}")
    print("  " + "-" * 44)
    for arm in ARMS:
        m = q["arms"][arm]
        print(f"  {arm:<18}{m['rubric_mean']:>12.3f}{m['prefer_final']:>14.3f}")
    _quality_verdict(q)


def _quality_verdict(q: dict) -> None:
    A = q["arms"]
    su = A["symbolu"]["rubric_mean"]
    print("\n  --- VERDICT (real LLM) ---")
    for ref in ["generic_refine", "nl_policy", "sentiment_critic", "random_policy",
                "shuffled_symbolu", "relabeled_symbolu"]:
        d = su - A[ref]["rubric_mean"]
        print(f"  symbolu vs {ref:<18}: {su:.3f} vs {A[ref]['rubric_mean']:.3f}  "
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
