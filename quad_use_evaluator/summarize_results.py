#!/usr/bin/env python
"""Print report-ready tables from RESULTS/use_results.json (read-only)."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
R = json.load(open(os.path.join(HERE, "RESULTS", "use_results.json")))
res = R["results"]; V = res["verdict"]
print("config:", R["config"]); print("model_acc:", R["model_acc"])
print("wall_clock_s:", R["wall_clock_s"])

print("\n## Per-condition predictors (AUROC | AUPRC)")
for c, r in res["per_condition"].items():
    if "predictors" not in r:
        print(f"  {c}: skipped ({r.get('skipped')}) n={r['n']} fail%={r['failure_rate']:.3f}"); continue
    p = r["predictors"]
    print(f"  {c} (n={r['n']}, fail%={r['failure_rate']:.3f}):")
    for name in ["token_prob_only","baseline_combo","use_best","use_all","use_quad",
                 "combined_base_use","combined_base_usebest","random"]:
        if name in p:
            d=p[name]; print(f"    {name:22s} AUROC={d['auroc']:.3f} CI=[{d['auroc_ci'][0]:.3f},{d['auroc_ci'][1]:.3f}] AUPRC={d['auprc']:.3f}")
    t=r["tests"]
    for tn in ["use_best_vs_baseline_combo","combined_vs_baseline_combo","combined_best_vs_baseline","combined_quad_vs_baseline"]:
        x=t[tn]; print(f"    DeLong {tn}: dAUC={x['auc1']-x['auc2']:+.4f} p1={x['p_one_sided_1_gt_2']:.4g}")

print("\n## Pooled omnibus")
po=res["pooled_all"]; p=po["predictors"]
for name in ["token_prob_only","baseline_combo","use_best","use_all","use_quad","combined_base_use","combined_base_usebest","random"]:
    if name in p:
        d=p[name]
        cal=f" Brier={d.get('brier','-'):.3f} ECE={d.get('ece','-'):.3f}" if 'brier' in d else ""
        print(f"  {name:22s} AUROC={d['auroc']:.3f} CI=[{d['auroc_ci'][0]:.3f},{d['auroc_ci'][1]:.3f}] AUPRC={d['auprc']:.3f}{cal}")
print("  best USE config:", po["use_best_config"])
for tn,x in po["tests"].items():
    print(f"  DeLong {tn}: dAUC={x['auc1']-x['auc2']:+.4f} z={x['z']:.2f} p1={x['p_one_sided_1_gt_2']:.4g}")

print("\n## Per-seed reproducibility (pooled within seed)")
for s,r in res["per_seed_condition"].items():
    if "predictors" not in r: continue
    p=r["predictors"]; t=r["tests"]["combined_best_vs_baseline"]
    print(f"  seed {s}: baseline={p['baseline_combo']['auroc']:.3f} use_all={p['use_all']['auroc']:.3f} "
          f"combined={p['combined_base_use']['auroc']:.3f} parsimonious_incr_dAUC={t['auc1']-t['auc2']:+.4f} p1={t['p_one_sided_1_gt_2']:.4g}")

print("\n## Univariate top features (pooled)")
uni=po["univariate"]
items=sorted(((k,v['auroc']) for k,v in uni.items() if v['auroc']==v['auroc']), key=lambda kv:-kv[1])
for k,a in items[:12]: print(f"  {k:52s} {a:.3f}")
print("  ... USE-only best:")
useitems=[(k,v['auroc']) for k,v in uni.items() if k.startswith('USE::') and v['auroc']==v['auroc']]
for k,a in sorted(useitems,key=lambda kv:-kv[1])[:6]: print(f"  {k:52s} {a:.3f}")

print("\n## Ablation: channel set")
for cs,v in sorted(R["ablation"]["channel_set"].items(), key=lambda kv:-kv[1]): print(f"  {cs:16s} {v:.3f}")
print("## Ablation: mapping")
for mp,v in R["ablation"]["mapping"].items(): print(f"  {mp:22s} {v:.3f}")
print("## Ablation: per-signal (quad_heads, complex_pair) single-signal oriented AUROC")
sa=R["ablation"]["signal_quad_ref"] if False else R["ablation"]["signal_full_ref"]
print("  (full/reference_projection group) full_group_auroc=%.3f"%sa["full_group_auroc"])
for s,d in sa["single_signal"].items(): print(f"    {s:14s} {d['auroc_oriented']:.3f}")

print("\n## Failure analysis")
fa=R["failure_analysis"]
print("  use_auroc=%.3f confidence_auroc=%.3f n=%d n_failure=%d"%(fa["use_auroc"],fa["confidence_auroc"],fa["n"],fa["n_failure"]))
for k,v in fa["categories"].items(): print(f"    {k:26s} count={v['count']:6d} frac={v['frac']:.3f}")
print("  detection:", {k:round(v,3) for k,v in fa["detection"].items()})

print("\n## VERDICT:", V["verdict"])
for k in ["reject_null","n_conditions_incremental","n_conditions_usable","pooled_incremental_significant","reproducible_across_seeds","use_beats_baseline_per_condition","incremental_significant_per_condition"]:
    print(f"  {k}: {V[k]}")
