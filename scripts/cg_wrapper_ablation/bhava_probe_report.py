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


def _fmt_set(name, r):
    return (f"  {name:<22} acc={r['accuracy']:.3f} "
            f"CI[{r['acc_ci'][0]:.3f},{r['acc_ci'][1]:.3f}] "
            f"AUROC={r['auroc']:.3f} F1={r['f1']:.3f} "
            f"chance={r['chance']:.3f} selectivity={r['selectivity']:+.3f} "
            f"{'>chance' if r['beats_chance'] else 'ns'}")


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
        lines += [f"## {lt}  (n={blk['n']}, pos={blk['pos']}, neg={blk['neg']})", ""]
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
                                        "n": blk["n"]}

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
