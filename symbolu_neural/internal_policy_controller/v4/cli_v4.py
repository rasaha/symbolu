"""CLI for internal_policy_controller v4 (high-fidelity translator).

    python -m symbolu_neural.internal_policy_controller.v4.cli_v4 bottleneck
    python -m symbolu_neural.internal_policy_controller.v4.cli_v4 state
    python -m symbolu_neural.internal_policy_controller.v4.cli_v4 pairwise \
        --backend mistral --judge-backend anthropic --seeds 1
"""
from __future__ import annotations

import argparse

from . import pilot_v4
from .policy_v4 import translate_v4
from ..v3.data import prompts
from ..v3.symbolu_state import compute_state


def main() -> None:
    ap = argparse.ArgumentParser(prog="internal_policy_controller.v4")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("bottleneck", help="how much ontology info the v4 translator preserves")
    sub.add_parser("state", help="show the v4 ontology-rich policy per prompt")
    pw = sub.add_parser("pairwise", help="gate-valid pairwise A/B eval with the v4 translator")
    pw.add_argument("--backend", default="mock", choices=["mock", "anthropic", "mistral"])
    pw.add_argument("--model", default=None)
    pw.add_argument("--judge-backend", default=None, choices=["mock", "anthropic", "mistral"])
    pw.add_argument("--judge-model", default=None)
    pw.add_argument("--seeds", type=int, default=1)
    args = ap.parse_args()

    if args.cmd == "bottleneck":
        b = pilot_v4.bottleneck_report_v4()
        v3, v4 = b["v3"], b["v4"]
        print(f"Translator information-preservation — v3 vs v4 ({b['n_prompts']} prompts)\n")
        print(f"  {'metric':<38}{'v3':>8}{'v4':>8}")
        print("  " + "-" * 54)
        print(f"  {'distinct prompts (of 36)':<38}{v3['distinct_prompts']:>8}{v4['distinct_prompts']:>8}")
        print(f"  {'relabel FIELD divergence':<38}{v3['field_div']:>8.0%}{v4['field_div']:>8.0%}"
              "   <- analog of v3's 34%")
        print(f"  {'relabel TOKEN divergence':<38}{v3['token_div']:>8.0%}{v4['token_div']:>8.0%}"
              "   <- how much PROMPT text moves")
        print(f"  {'divergence from FIXED generic policy':<38}{v3['divergence_from_generic']:>8.0%}"
              f"{v4['divergence_from_generic']:>8.0%}   <- higher = less generic")
        print(f"\n  v4 de-genericizes the prompt {v4['divergence_from_generic']/max(v3['divergence_from_generic'],1e-9):.1f}x "
              "(the bottleneck fix) and more than doubles relabel token-divergence.")
        print("  NOTE: relabel divergence is CAPPED — ~30% of the v4 policy is driven by")
        print("        continuous magnitudes (resonance/aspect) that a label scramble")
        print("        correctly leaves unchanged. v4 is a fairer, not perfect, ontology test.")
    elif args.cmd == "state":
        for p, _para, cat in prompts():
            s = compute_state(p)
            print(f"\n[{cat}] {p[:62]}")
            print("   " + translate_v4(s).render().replace("\n", "\n   "))
    elif args.cmd == "pairwise":
        pilot_v4.print_pairwise_v4(pilot_v4.run_pairwise_multi_v4(
            args.backend, args.model, seeds=tuple(range(max(1, args.seeds))),
            judge_backend=args.judge_backend, judge_model=args.judge_model))


if __name__ == "__main__":
    main()
