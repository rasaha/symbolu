"""assemble.py — build results/aggregate.json and results/tables.md from the saved
results/raw/*.json probe outputs and results/ckpt/*.json arm metrics (no re-run)."""
from __future__ import annotations
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "results" / "raw"
CKPT = HERE / "results" / "ckpt"
RES = HERE / "results"


def load_raw():
    return {p.stem: json.loads(p.read_text()) for p in sorted(RAW.glob("*.json"))}


def arm_metrics():
    out = {}
    for p in sorted(CKPT.glob("*.json")):
        d = json.loads(p.read_text())
        out[f"{d['arm']}_p{d['pressure']}"] = d.get("metrics", {})
    return out


def main():
    raw = load_raw()
    am = arm_metrics()
    agg = {"arm_metrics": am, "raw": raw}
    (RES / "aggregate.json").write_text(json.dumps(agg, indent=2, default=float))

    L = ["# Phase-guidance diagnostics — result tables", ""]

    L.append("## Headline: answer accuracy & write-F1 by arm/pressure (seed 0)")
    L.append("| arm/pressure | answer_acc | write_f1 |")
    L.append("|---|---:|---:|")
    for k in sorted(am):
        m = am[k]
        L.append(f"| {k} | {m.get('answer_acc'):.3f} | {m.get('write_f1'):.3f} |")

    tp = raw.get("topic_probe_D_p3x", {})
    L += ["", "## Q A/F — topic decodability (D, 3x; chance=0.05)",
          "| feature | top1 | top3 |", "|---|---:|---:|"]
    for k in ("local_only", "phase_only", "local_plus_phase",
              "random_state_control", "shuffled_phase_control"):
        v = tp.get(k, {})
        L.append(f"| {k} | {v.get('top1'):.3f} | {v.get('topk'):.3f} |")

    dp = raw.get("distance_probe_D_p3x", {}).get("long_filler", {})
    L += ["", "## Q B — controlled long-filler: Phase topic decode & SNR vs distance",
          "| K (filler) | phase_top1 | state_norm | cos_to_decl | topic_SNR |",
          "|---:|---:|---:|---:|---:|"]
    for K in ("64", "128", "256", "512", "1024", "2048", "4096", "8192", "16384", "32768"):
        v = dp.get(K)
        if v:
            L.append(f"| {K} | {v['phase_top1']:.3f} | {v['state_norm_mean']:.0f} | "
                     f"{v['cos_to_decl_mean']:.3f} | {v['topic_snr_mean']:.4f} |")

    di = raw.get("dilution_probe_D_p3x", {}).get("sweep", [])
    L += ["", "## Q C — numerator attribution vs distractor count (D, 3x)",
          "| n_cand | seq_len | topic_share | relfact_share | filler_share | rel/distr | Z |",
          "|---:|---:|---:|---:|---:|---:|---:|"]
    for r in di:
        L.append(f"| {r['n_candidates']} | {r['seq_len_mean']:.0f} | {r['topic_num_share']:.4f} | "
                 f"{r['relfact_num_share']:.4f} | {r['filler_num_share']:.4f} | "
                 f"{r['relevant_to_distractor_num']:.3f} | {r['Z_mean']:.0f} |")

    de = raw.get("decay_probe_D_p3x", {}).get("gammas", {})
    L += ["", "## Q D — imposed-decay intervention (D, 3x; config decay=none)",
          "| gamma | phase_top1 | horizon |", "|---:|---:|---:|"]
    for gm, v in de.items():
        L.append(f"| {gm} | {v['phase_top1']:.3f} | {v['horizon_tokens']} |")

    ha = raw.get("head_analysis_D_p3x", {})
    L += ["", f"## Q E — per-head (D, 3x); full_top1={ha.get('full_topic_top1'):.3f}, "
          f"eff_rank={ha.get('effective_rank'):.1f}/{ha.get('max_rank')}, "
          f"mean|corr|={ha.get('mean_abs_offdiag_corr'):.3f}",
          "| head | topic_top1 | out_norm | ablate_delta |", "|---:|---:|---:|---:|"]
    for hh in range(ha.get("num_heads", 0)):
        ph = ha["per_head"][f"head_{hh}"]; ab = ha["ablation"][f"drop_head_{hh}"]
        L.append(f"| {hh} | {ph['topic_top1']:.3f} | {ph['out_norm']:.3f} | {ab['delta_vs_full']:+.3f} |")

    sd = raw.get("score_decomposition_D_p3x", {})
    L += ["", "## Q H — content-vs-Phase read score & beta sweep (D, 3x)",
          f"R = |s_phase|/|s_content|: mean={sd.get('R_ratio_phase_over_content',{}).get('mean'):.3f}, "
          f"p90={sd.get('R_ratio_phase_over_content',{}).get('p90'):.3f}", "",
          "| beta | answer_acc | frac_read_changed |", "|---:|---:|---:|"]
    for b, v in sd.get("beta_sweep", {}).items():
        L.append(f"| {b} | {v['answer_acc']:.3f} | {v['frac_read_changed_vs_content']:.3f} |")

    L += ["", "## Q I/J — slot-chain trace (occupancy / eviction / pressure)",
          "| arm/pressure | occ/M | saturated_end | evictions | hard_writes | matches |",
          "|---|---:|---:|---:|---:|---:|"]
    for k in ("slot_chain_trace_C_p1x", "slot_chain_trace_C_p3x",
              "slot_chain_trace_D_p1x", "slot_chain_trace_D_p3x"):
        v = raw.get(k, {})
        if v:
            L.append(f"| {v['arm']}/{v['pressure']} | {v['final_occupancy_mean']:.1f}/{v['M']} | "
                     f"{v['frac_saturated_end']:.2f} | {v['evictions_mean']:.1f} | "
                     f"{v['hard_writes_mean']:.1f} | {v['matches_mean']:.1f} |")

    L += ["", "## Q K — shortcut checks (answer acc under corruption)",
          "| mode | C | D |", "|---|---:|---:|"]
    cmodes = raw.get("shortcut_checks_C_p3x", {}).get("modes", {})
    dmodes = raw.get("shortcut_checks_D_p3x", {}).get("modes", {})
    for m in ("intact", "shuffle_slot_values", "shuffle_slot_keys", "random_slot_values",
              "zero_readout_memory", "mask_query_entity", "remove_phase_at_query"):
        c = cmodes.get(m); d = dmodes.get(m)
        L.append(f"| {m} | {'' if c is None else f'{c:.3f}'} | {'' if d is None else f'{d:.3f}'} |")

    mk = raw.get("masking_probe_D_p3x", {}).get("phase_topic_top1", {})
    L += ["", "## Q M — filler masking → Phase topic decode (D, 3x; chance=0.05)",
          "| input | phase_topic_top1 |", "|---|---:|"]
    for k, v in mk.items():
        L.append(f"| {k} | {v:.3f} |")

    mi = raw.get("multitask_interference_D_p3x", {}).get("groups", {})
    L += ["", "## Q L — per-loss gradients into shared params (D, 3x)",
          "| group | |g_answer| | |g_write| | grad_cosine | write/answer |",
          "|---|---:|---:|---:|---:|"]
    for gname, d in mi.items():
        L.append(f"| {gname} | {d['answer_grad_norm']:.3e} | {d['write_grad_norm']:.3e} | "
                 f"{d['grad_cosine']:+.3f} | {d['write_to_answer_norm_ratio']:.3e} |")

    la = raw.get("label_alignment_p3x", {})
    if la:
        c = la["counts"]
        L += ["", "## Q G — write-label alignment (3x)",
              f"label==1 precision for needed-later: {la['label1_precision_for_needed']:.3f}; "
              f"topic facts/ex={la['mean_topic_facts_per_ex']:.1f}, distractors/ex={la['mean_distractors_per_ex']:.1f}",
              f"(topic&needed label1={c['topic_related_needed_label1']}, "
              f"topic&not-needed label1={c['topic_related_notneeded_label1']})"]

    (RES / "tables.md").write_text("\n".join(L) + "\n")
    print("wrote aggregate.json and tables.md")


if __name__ == "__main__":
    main()
