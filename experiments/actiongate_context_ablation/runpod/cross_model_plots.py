"""Cross-model plots: forest, decision-preservation, cost/accuracy, architecture
sensitivity. Kept out of the core (no matplotlib dependency in the library/tests).
Generates only from real model data; single-model runs still render (degenerate).
"""

from __future__ import annotations

import json
import pathlib

import cross_model as CM


def render(models, out_dir) -> list:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    a = CM.analyze(models)
    (out_dir / "cross_model_data.json").write_text(json.dumps(a, indent=2) + "\n")
    written = []

    # 1) forest: protected-original delta per model with CI
    forest = [f for f in a["forest"] if f["delta_mean"] is not None]
    if forest:
        fig, ax = plt.subplots(figsize=(6, max(2.5, 0.6 * len(forest) + 1)))
        ys = range(len(forest))
        for i, f in enumerate(forest):
            x = 100 * f["delta_mean"]
            if f["ci_low"] is not None:
                ax.plot([100 * f["ci_low"], 100 * f["ci_high"]], [i, i], color="gray")
            ax.plot(x, i, "o", color="green" if x >= -2 else "crimson")
        ax.axvline(0, color="black", lw=0.8)
        ax.axvline(-2, color="orange", ls="--", lw=0.8, label="-2% non-regression bound")
        ax.set_yticks(list(ys))
        ax.set_yticklabels([f["model"] for f in forest], fontsize=8)
        ax.set_xlabel("protected − original task delta (%)")
        ax.set_title("Forest: protected compression task delta by model")
        ax.legend(fontsize=8)
        fig.tight_layout()
        p = out_dir / "cross_forest.png"
        fig.savefig(p, dpi=110)
        plt.close(fig)
        written.append(str(p))

    # 2) decision preservation protected vs unaware (at 40%)
    dc = a["decision_comparison"]
    if dc:
        fig, ax = plt.subplots(figsize=(6, 4))
        labels = [r["model"] for r in dc]
        prot = [100 * (r["budgets"][0.4]["protected"] or 0) for r in dc]
        una = [100 * (r["budgets"][0.4]["protection_unaware"] or 0) for r in dc]
        x = range(len(labels))
        ax.bar([i - 0.2 for i in x], prot, width=0.4, label="protected", color="green")
        ax.bar([i + 0.2 for i in x], una, width=0.4, label="protection-unaware", color="crimson")
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, fontsize=8, rotation=15)
        ax.set_ylabel("ActionGate decision preservation @40% (%)")
        ax.set_ylim(90, 101)
        ax.set_title("Decision preservation: protected vs protection-unaware")
        ax.legend(fontsize=8)
        fig.tight_layout()
        p = out_dir / "cross_decision.png"
        fig.savefig(p, dpi=110)
        plt.close(fig)
        written.append(str(p))

    # 3) cost vs accuracy
    ca = a["cost_accuracy"]
    if ca:
        fig, ax = plt.subplots(figsize=(6, 4))
        for r in ca:
            xs = [p["cost"] for p in r["protected"]]
            ys = [100 * p["task_accuracy"] for p in r["protected"]]
            if xs:
                ax.plot(xs, ys, "o-", label=r["model"])
        ax.set_xlabel("estimated cost ($)")
        ax.set_ylabel("task accuracy (%)")
        ax.set_title("Cost vs accuracy (protected, across budgets)")
        ax.legend(fontsize=8)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()
        p = out_dir / "cross_cost_accuracy.png"
        fig.savefig(p, dpi=110)
        plt.close(fig)
        written.append(str(p))
    return written
