#!/usr/bin/env python3
"""bhava_probe_report.py — results.json -> report.md + summary.json (Deliverable 5).

Answers, per label_type and overall:
  1. Does Bhava beat chance?
  2. Does Bhava beat delta-Bhava?
  3. Does Bhava beat generic hidden features?
  4. Does Bhava add complementary signal over hidden features?
  5. Are results statistically meaningful?
  6. Continue, park, or redesign?

Pure Python. Usage: python scripts/cg_wrapper_ablation/bhava_probe_report.py runs/bhava_probe/<ts>
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cg_ablation.probe_decide import parks_bhava, continues_bhava  # noqa: E402


def data_warnings(blk: dict) -> list:
    """Surface data-quality problems that make a verdict unreliable (Task 5)."""
    w = []
    pos, neg = blk.get("pos", 0), blk.get("neg", 0)
    tot = pos + neg
    results = blk.get("results", {})
    if pos == 0 or neg == 0:
        w.append(f"SINGLE-CLASS labels (pos={pos}, neg={neg}) — degenerate; cannot probe "
                 "(possible template leakage or model always passes/fails).")
    elif pos < 8 or neg < 8:
        w.append(f"TOO FEW per class (pos={pos}, neg={neg}; need >=8 each) — INSUFFICIENT_DATA.")
    if tot and 0 < min(pos, neg) / tot < 0.2:
        w.append(f"CLASS IMBALANCE (minority fraction {min(pos,neg)/tot:.2f} < 0.20) — "
                 "AUROC is used (imbalance-robust), but power is low.")
    hid = results.get("hidden_only", {})
    au = hid.get("auroc", float("nan"))
    if au == au and au < 0.5:
        w.append(f"HIDDEN BASELINE AUROC={au:.3f} < 0.5 even after PCA — overfit/insufficient n; "
                 "'beats hidden' comparisons are UNRELIABLE.")
    aurocs = [r.get("auroc", float("nan")) for r in results.values()]
    if aurocs and all((a == a and a >= 0.999) for a in aurocs):
        w.append("ALL feature sets AUROC≈1.0 — label likely LEAKED by prompt template; uninformative.")
    return w


def _fmt_set(name, r):
    ci = r.get("auroc_ci", [float("nan"), float("nan")])
    return (f"  {name:<22} AUROC={r['auroc']:.3f} "
            f"CI[{ci[0]:.3f},{ci[1]:.3f}] "
            f"bal_acc={r.get('balanced_accuracy', float('nan')):.3f} "
            f"F1={r['f1']:.3f} selectivity={r['selectivity']:+.3f} "
            f"{'DECODABLE' if r['beats_chance'] else 'ns'}")


def build(run_dir: Path) -> dict:
    results = json.loads((run_dir / "results.json").read_text())
    cfg = {}
    if (run_dir / "config.json").exists():
        cfg = json.loads((run_dir / "config.json").read_text())

    lines = ["# Bhava / Ontology Probe — Report", ""]
    lines.append(f"model={cfg.get('model_id','?')} ckpt={cfg.get('checkpoint','?')} "
                 f"probe={results.get('model')} k={results.get('k')}")
    lines.append("")
    overall = []
    summary = {"config": cfg, "model": results.get("model"), "by_label_type": {}}

    for lt, blk in results["by_label_type"].items():
        v = blk["verdict"]
        ans = v.get("answers", {})
        warns = data_warnings(blk)
        lines += [f"## {lt}  (n={blk['n']}, pos={blk['pos']}, neg={blk['neg']})", ""]
        for w in warns:
            lines.append(f"  ⚠ {w}")
        if warns:
            lines.append("")
        for s, r in blk["results"].items():
            lines.append(_fmt_set(s, r))
        lines.append("")
        for key, label in [
            ("hidden_plus_bhava_vs_hidden", "hidden+bhava vs hidden_only"),
            ("hidden_plus_cg_state_vs_hidden", "hidden+cg_state vs hidden_only"),
            ("bhava_vs_delta_bhava", "bhava_only vs delta_bhava_only"),
        ]:
            p = blk["paired"].get(key)
            if p:
                lines.append(f"  paired {label:<34} Δacc={p['delta_acc']:+.3f} "
                             f"CI[{p['ci'][0]:+.3f},{p['ci'][1]:+.3f}] p={p['mcnemar_p']:.3g} "
                             f"{'SIG' if p['significant'] else 'ns'} ({p['direction']})")
        lines += ["",
                  "  Q1 Bhava beats chance?            " + str(ans.get("bhava_beats_chance")),
                  "  Q2 Bhava beats delta-Bhava?       " + str(ans.get("bhava_beats_delta_bhava")),
                  "  Q3 Bhava beats generic hidden?    " + str(ans.get("bhava_beats_hidden")),
                  "  Q4 Bhava complements hidden?      " + str(ans.get("bhava_complements_hidden")),
                  f"  Q6 DECISION: {v['decision']}",
                  "      " + "; ".join(v.get("reasons", [])),
                  ""]
        overall.append(v["decision"])
        summary["by_label_type"][lt] = {"decision": v["decision"], "answers": ans,
                                        "n": blk["n"], "pos": blk["pos"], "neg": blk["neg"],
                                        "warnings": warns}

    # overall recommendation: continue if ANY label_type shows complementary/strong; else park.
    if any(continues_bhava(d) for d in overall):
        overall_decision = "CONTINUE_CG"
    elif overall and all(d == "INSUFFICIENT_DATA" for d in overall):
        overall_decision = "INSUFFICIENT_DATA"
    elif any(parks_bhava(d) for d in overall):
        overall_decision = "PARK_CG"
    else:
        overall_decision = "REVIEW"
    summary["overall_decision"] = overall_decision
    lines += ["## Overall", "",
              f"**{overall_decision}**  (per-label: {overall})", "",
              "- CONTINUE_CG only if some label shows BHAVA_COMPLEMENTARY_SIGNAL or "
              "BHAVA_STRONG_SIGNAL (bhava beats chance AND hidden+bhava beats hidden_only).",
              "- PARK_CG if Bhava adds nothing over generic hidden features.",
              "- Probe = correlation only; a causal generation test is a separate later step.",
              ""]

    (run_dir / "report.md").write_text("\n".join(lines))
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: bhava_probe_report.py <run_dir>")
        return 2
    run_dir = Path(sys.argv[1])
    if not (run_dir / "results.json").exists():
        print(f"no results.json in {run_dir} — run train_bhava_probe.py first")
        return 2
    s = build(run_dir)
    print(Path(run_dir, "report.md").read_text())
    print(f"\noverall: {s['overall_decision']}")
    print(f"report: {run_dir/'report.md'}  summary: {run_dir/'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
