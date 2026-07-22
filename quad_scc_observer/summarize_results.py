#!/usr/bin/env python
"""Print report-ready tables from RESULTS/scc_results.json (read-only)."""
import json, os
R = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "RESULTS", "scc_results.json")))
res = R["results"]; V = res["verdict"]
print("config:", R["config"]); print("model_acc:", R["model_acc"], "wall:", R["wall_clock_s"])
usable = res["usable_conditions"]; print("usable:", usable)

print("\n## Arm AUROC per condition + pooled")
arms_order = ["1_confidence","2_conf_entail","3_conf_ground","7_cg_T","8_intrinsic_SRT","8b_conf_SRT","9_full_scc","9b_cg_full_scc"]
for c in list(res["per_condition"])+["POOLED"]:
    r = res["pooled"] if c=="POOLED" else res["per_condition"][c]
    if "arms" not in r: print(f"  {c}: skipped"); continue
    a=r["arms"]; print(f"  {c:16s} fail%={r['failure_rate']:.3f} " + " ".join(f"{k.split('_',1)[1][:10]}={a[k]['auroc']:.3f}" for k in arms_order if k in a))

print("\n## Incremental ΔAUROC per term, per base — PER CONDITION (does it survive where difficulty is constant?)")
for t in ["S","R","E","T"]:
    print(f"  Term {t}:")
    for c in usable:
        inc = res["per_condition"][c].get("increments",{}).get(t,{})
        s=" ".join(f"{b.replace('over_',''):>16s}:dAUC={inc[b]['delta_auroc']:+.4f}(sig={inc[b]['significant_and_meaningful']})" for b in ["over_confidence","over_conf_entail","over_conf_entail_ground"] if b in inc)
        print(f"    {c:16s} {s}")

print("\n## Per-seed pooled increment (reproducibility) over conf+entail")
for t in ["S","R","T"]:
    row=[]
    for s in res["per_seed"]:
        inc=res["per_seed"][s].get("increments",{}).get(t,{}).get("over_conf_entail",{})
        row.append(f"seed{s}:dAUC={inc.get('delta_auroc',float('nan')):+.4f}(sig={inc.get('significant_and_meaningful')})")
    print(f"  {t}: "+" ".join(row))

print("\n## Term-alone AUROC (pooled):", {k:round(v,3) for k,v in res["pooled"].get("term_alone",{}).items()})

print("\n## Redundancy (all features)")
for t,feats in R["redundancy"].items():
    print(f"  {t}:")
    for name,d in sorted(feats.items(), key=lambda kv:-(kv[1]['oriented_auroc'] if kv[1]['oriented_auroc']==kv[1]['oriented_auroc'] else 0)):
        print(f"    {name:28s} auroc={d['oriented_auroc']:.3f} corr[conf]={d['max_corr_confidence']:.2f} corr[entail]={d['max_corr_entailment']:.2f} corr[ground]={d['max_corr_grounding']:.2f}")

print("\n## Calibration (pooled)")
for k in ["1_confidence","7_cg_T","8b_conf_SRT","9b_cg_full_scc"]:
    d=res["pooled"]["arms"].get(k,{})
    if d: print(f"  {k:18s} AUROC={d['auroc']:.3f} Brier={d.get('brier',float('nan')):.3f} ECE={d.get('ece',float('nan')):.3f}")

print("\n## VERDICT:", V["verdict"])
for k in ["intrinsic_survivors_over_conf_entail","survivors_over_confidence","grounding_is_closed_world_oracle","grounding_auroc","confidence_auroc","E_redundant_with_grounding_by_construction"]:
    print(f"  {k}: {V[k]}")
print("  term_survival_over_conf_entail:")
for t,d in V["term_survival_over_conf_entail"].items():
    print(f"    {t}: {d}")
