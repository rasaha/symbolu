#!/usr/bin/env python
"""Print report-ready tables from RESULTS/consistency_results.json (read-only)."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(HERE, "RESULTS", "consistency_results.json")) as f:
    R = json.load(f)

ARMS = R["arms"]
summ = R["summary"]
cmp = R["comparisons"]
causal = R["causal_guardrail1"]
prog = R["progressive"]
V = R["verdict"]
HARD = ["longer_context", "higher_distractor", "two_systems"]


def g(a, key):
    return summ[a][key]


print(f"lambda={R['lambda']}  seeds={R['seeds']}  wall={R['wall_clock_s']:.0f}s\n")

print("## Generalization (mean ± sd)")
print("arm | in_dist | mean_hard | " + " | ".join(HARD))
for a in ARMS:
    s = summ[a]
    print(f"{a} | {s['in_distribution']['mean']:.3f}±{s['in_distribution']['std']:.3f} | "
          f"{s['mean_hard']['mean']:.3f}±{s['mean_hard']['std']:.3f} | " +
          " | ".join(f"{s['conditions'][c]['mean']:.3f}±{s['conditions'][c]['std']:.3f}" for c in HARD))

print("\n## Health / stability (mean)")
keys = ["attn_entropy_norm", "head_diversity_js", "head_specialization_sel_std",
        "headmean_select_acc", "best_head_select_acc", "perturb_stability", "retrieval_stability"]
print("arm | " + " | ".join(keys))
for a in ARMS:
    print(f"{a} | " + " | ".join(f"{summ[a][k]['mean']:.3f}" for k in keys))

print("\n## Paired vs BD-A (mean-hard)")
print("arm | delta | median | n+/- | wilcoxon_p_greater | p_two | t_p_greater | ci95 | dz | sig")
for a in ["BD-Sync", "BD-Sync-Early", "BD-Shuffled", "BD-D"]:
    c = cmp[a]
    w = c["wilcoxon"]; t = c["ttest"]; b = c["bootstrap_ci95"]
    print(f"{a} | {c['mean_delta']:+.3f} | {c['median_delta']:+.3f} | "
          f"{c['n_positive']}/{c['n_negative']} | "
          f"{w['p_greater']} | {w['p_two_sided']} | {t['p_greater']} | "
          f"[{b['lo']:+.3f},{b['hi']:+.3f}] | {c['cohens_dz']:.2f} | "
          f"{c['significant_improvement_over_baseline']}")

print("\n## Per-condition paired vs BD-A (BD-Sync)")
for c in HARD:
    pc = cmp["BD-Sync"]["per_condition"][c]
    print(f"  {c}: delta={pc['mean_delta']:+.3f} wilcoxon_p_greater={pc['wilcoxon']['p_greater']} "
          f"ci95=[{pc['bootstrap_ci95']['lo']:+.3f},{pc['bootstrap_ci95']['hi']:+.3f}]")

print("\n## Guardrail 1 (causal necessity) — chance ~ %.3f" % causal["chance"])
for a in ARMS:
    if a in causal and isinstance(causal[a], dict):
        print(f"  {a}: clean={causal[a]['clean']:.3f} zeroed={causal[a]['attn_zero_all']:.3f} "
              f"retained={causal[a]['retained']:.3f} all_collapse={causal[a]['all_collapse']}")

print("\n## Guardrail 2 (health) — per-seed healthy flags")
for a in ARMS:
    flags = [R["per_arm_seed"][a][str(s)]["guardrail2"]["healthy"] for s in R["seeds"]]
    print(f"  {a}: {sum(flags)}/{len(flags)} seeds healthy  {flags}")

print("\n## Progressive perturbation (perturb_stability by level)")
labels = [d["label"] for d in prog[ARMS[0]]]
print("arm | " + " | ".join(labels))
for a in ARMS:
    print(f"{a} | " + " | ".join(f"{d['perturb_stability']:.3f}" for d in prog[a]))
print("\n## Progressive perturbation (accuracy by level)")
for a in ARMS:
    print(f"{a} | " + " | ".join(f"{d['accuracy']:.3f}" for d in prog[a]))

print("\n## VERDICT:", V["verdict"])
for k, v in V.items():
    if k not in ("verdict", "null_hypothesis"):
        print(f"  {k}: {v}")
