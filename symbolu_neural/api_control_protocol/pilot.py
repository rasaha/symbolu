"""API control-protocol pilot orchestrator.

For each arm × target axis × prompt: build the control message, call the LLM
(mock offline / anthropic real), and evaluate. Aggregates adherence, token cost,
consistency, and paraphrase stability.

NOTE: with the `mock` backend the adherence numbers are PLUMBING-ONLY (the mock
encodes the null by assumption). Token cost and the redundancy/structure findings
are real regardless of backend. The decisive adherence result requires the
`anthropic` backend (API key needed).
"""
from __future__ import annotations

import argparse
from typing import Dict, List

import numpy as np

from .ontology import AXES
from .packets import ARMS, build, approx_tokens
from .data import prompts
from .llm import get_llm
from .evaluator import tone_adherence, hit


def run(backend: str = "mock", model: str = None, seed: int = 0) -> dict:
    llm = get_llm(backend, model)
    ps = prompts()
    results = {"backend": backend, "is_real": llm.is_real, "arms": {}}

    for arm in ARMS:
        adher, hits, ptokens, para_stable = [], [], [], []
        for axis in AXES:
            ctrl = build(arm, axis, seed)
            ptokens.append(approx_tokens(ctrl))
            for prompt, para in ps:
                o1 = llm.generate(ctrl, prompt, seed)
                o2 = llm.generate(ctrl, para, seed)
                adher.append(tone_adherence(o1, axis))
                hits.append(hit(o1, axis))
                para_stable.append(int(hit(o1, axis) == hit(o2, axis)))
        results["arms"][arm] = {
            "adherence": float(np.mean(adher)),
            "hit_rate": float(np.mean(hits)),
            "ctrl_tokens": float(np.mean(ptokens)),
            "consistency": 1.0 - float(np.std(hits)),
            "paraphrase_stability": float(np.mean(para_stable)),
        }
    results["chance_hit"] = 1.0 / len(AXES)
    return results


def print_report(r: dict) -> None:
    real = r["is_real"]
    print("=" * 78)
    print(f"API CONTROL-PROTOCOL PILOT   backend={r['backend']}  real_LLM={real}")
    if not real:
        print("*** MOCK BACKEND: adherence is PLUMBING-ONLY (encodes the null by")
        print("*** assumption). Only token-cost + structure are meaningful here.")
    print("=" * 78)
    h = f"{'arm':<18}{'hit_rate':>9}{'adher':>8}{'consist':>9}{'para_stab':>10}{'ctrl_tok':>9}"
    print(h); print("-" * len(h))
    for arm in ARMS:
        m = r["arms"][arm]
        print(f"{arm:<18}{m['hit_rate']:>9.3f}{m['adherence']:>8.3f}"
              f"{m['consistency']:>9.3f}{m['paraphrase_stability']:>10.3f}"
              f"{m['ctrl_tokens']:>9.0f}")
    print(f"\nchance hit_rate = {r['chance_hit']:.3f}")
    _verdict(r)


def _verdict(r: dict) -> None:
    A = r["arms"]
    print("\n" + "-" * 28 + " READING " + "-" * 28)
    print("Token cost (REAL, backend-independent):")
    print(f"  nl_instruction = {A['nl_instruction']['ctrl_tokens']:.0f} tok   "
          f"sentiment_json = {A['sentiment_json']['ctrl_tokens']:.0f} tok   "
          f"hybrid = {A['hybrid']['ctrl_tokens']:.0f} tok   "
          f"symbolu_json = {A['symbolu_json']['ctrl_tokens']:.0f} tok")
    print(f"  -> JSON packets cost ~{A['hybrid']['ctrl_tokens']/max(A['nl_instruction']['ctrl_tokens'],1):.1f}x "
          f"the tokens of plain NL instruction for the same actionable content.")
    if not r["is_real"]:
        print("\nAdherence verdict: NOT AVAILABLE offline. Run --backend anthropic")
        print("with an API key for the decisive comparison (see report §commands).")
    else:
        nl, hy, sj = A['nl_instruction']['hit_rate'], A['hybrid']['hit_rate'], A['symbolu_json']['hit_rate']
        sent, shuf, rnd = A['sentiment_json']['hit_rate'], A['shuffled_symbolu']['hit_rate'], A['random_json']['hit_rate']
        print(f"\nReal-LLM adherence (hit_rate):")
        print(f"  symbolu_json vs nl_instruction:  {sj:.3f} vs {nl:.3f}  "
              f"-> {'ontology JSON beats prompting' if sj > nl + 0.05 else 'NO gain over plain prompting'}")
        print(f"  hybrid vs sentiment_json:        {hy:.3f} vs {sent:.3f}  "
              f"-> {'ontology adds value' if hy > sent + 0.05 else 'ontology adds nothing over policy-only'}")
        print(f"  hybrid vs shuffled_symbolu:      {hy:.3f} vs {shuf:.3f}  "
              f"-> {'ontology content matters' if hy > shuf + 0.05 else 'content does NOT matter (shuffle ties)'}")
        print(f"  any-JSON check (random_json):    {rnd:.3f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="mock", choices=["mock", "anthropic"])
    ap.add_argument("--model", default=None)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    print_report(run(args.backend, args.model, args.seed))


if __name__ == "__main__":
    main()
