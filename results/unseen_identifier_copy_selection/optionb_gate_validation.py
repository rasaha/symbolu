"""Validate the PROPOSED sampling-aware shortcut gate (Option B) WITHOUT modifying frozen code.

Proposed rule (per (split, baseline) with pooled applicable n and pooled score p_hat):
  practical  = p_hat > chance + 0.05                         # unchanged practical-equivalence margin
  p0         = chance + 0.05
  se0        = sqrt(p0*(1-p0)/n)                              # SE under the boundary null
  z          = (p_hat - p0) / se0                             # one-sided: is it ABOVE the practical bound?
  m          = number of (split,baseline) comparisons in the cohort
  alpha_fw   = 0.05                                           # family-wise error rate
  alpha_per  = 1 - (1-alpha_fw)**(1/m)                        # Sidak multiple-comparison correction
  z_crit     = Phi^{-1}(1 - alpha_per)
  BLOCK      = practical AND (z > z_crit)                     # block only if practically AND statistically above
The split fails if any baseline blocks; all_pass = no split fails.
"""
from __future__ import annotations

import math
from statistics import NormalDist

from experiments.unseen_identifier_copy_selection.runner import build_cohort
from experiments.unseen_identifier_copy_selection.config import SPLIT_IDS
from experiments.unseen_identifier_copy_selection.shortcuts import shortcut_scores, aggregate_shortcuts

DEV = (9071, 9072, 9073)
ALPHA_FW = 0.05
PRACTICAL = 0.05


def proposed_gate(agg, inject=None):
    chance = agg["chance"]
    p0 = chance + PRACTICAL
    # count comparisons actually evaluated
    comps = [(s, b) for s, d in agg["per_split"].items() for b in d["baselines"]]
    m = len(comps)
    alpha_per = 1 - (1 - ALPHA_FW) ** (1 / m)
    z_crit = NormalDist().inv_cdf(1 - alpha_per)
    blocks = []
    for split, d in agg["per_split"].items():
        # pooled applicable n for this split (from summed counts; same across baselines)
        n = next(iter(d["counts"].values()))[1]
        for b, p_hat in d["baselines"].items():
            if inject and inject[0] == split and inject[1] == b:
                p_hat = inject[2]  # synthetic leak
            practical = p_hat > p0
            se0 = math.sqrt(p0 * (1 - p0) / n)
            z = (p_hat - p0) / se0 if se0 > 0 else 0.0
            if practical and z > z_crit:
                blocks.append((split, b, round(p_hat, 4), round(z, 2)))
    return {"m": m, "z_crit": round(z_crit, 3), "all_pass": len(blocks) == 0, "blocks": blocks}


def main():
    for cohort in ("seen", "unseen"):
        per_seed = [shortcut_scores([e for s in SPLIT_IDS for e in build_cohort(sd, cohort, token="development")[s]])
                    for sd in DEV]
        agg = aggregate_shortcuts(per_seed)
        frozen_pass = agg["all_pass"]
        prop = proposed_gate(agg)
        # inject a genuine leak on one split/baseline to prove the gate still blocks real leakage
        a_split = sorted(agg["per_split"])[0]
        a_base = sorted(agg["per_split"][a_split]["baselines"])[0]
        leaked = proposed_gate(agg, inject=(a_split, a_base, 0.60))
        print(f"\n=== cohort={cohort} ===")
        print(f"  FROZEN gate all_pass         : {frozen_pass}  (flat chance+0.05)")
        print(f"  PROPOSED gate all_pass       : {prop['all_pass']}  (m={prop['m']} comparisons, z_crit={prop['z_crit']})")
        print(f"    proposed blocks (real data): {prop['blocks'] if prop['blocks'] else 'NONE'}")
        print(f"  CONTROL — inject {a_split}/{a_base}=0.60 leak:")
        print(f"    proposed all_pass          : {leaked['all_pass']}  blocks: {leaked['blocks']}")


if __name__ == "__main__":
    main()
