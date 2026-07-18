"""Generate the milestone plots from a compressor BenchResult.

Kept separate from the library/tests so the core has no matplotlib dependency.
Produces the five required curves as PNGs plus the underlying data as JSON, so the
results are reproducible without matplotlib.
"""

from __future__ import annotations

import json
import pathlib


def plot_data(bench) -> dict:
    xs = [r.actual_reduction for r in bench.budgets]
    return {
        "compression_ratio": xs,
        "task_quality_decision_proxy": [r.task_decision_acc for r in bench.budgets],
        "task_quality_incidental_proxy": [r.task_incidental_acc for r in bench.budgets],
        "actiongate_invariance": [r.decision_preservation for r in bench.budgets],
        "cost_reduction_cache_adjusted": [r.cost_reduction_cache_adj for r in bench.budgets],
        "latency_ms": [r.mean_latency_ms for r in bench.budgets],
        "fallback_rate": [r.fallback_rate for r in bench.budgets],
        "generic_unaware": {
            "ratios": [bench.baselines[f"generic_unaware_{p}"]["reduction"] for p in (30, 50, 70)],
            "invariance": [bench.baselines[f"generic_unaware_{p}"]["decision_preservation"]
                           for p in (30, 50, 70)]},
    }


def render(bench, out_dir) -> list:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    d = plot_data(bench)
    (out_dir / "plot_data.json").write_text(json.dumps(d, indent=2) + "\n")
    x = [100 * v for v in d["compression_ratio"]]
    written = []

    def _save(name, ys_list, labels, ylabel, title, ylim=None, extra=None):
        fig, ax = plt.subplots(figsize=(6, 4))
        for ys, lab in zip(ys_list, labels):
            ax.plot(x, [100 * v for v in ys], marker="o", label=lab)
        if extra:
            ax.plot([100 * v for v in extra[0]], [100 * v for v in extra[1]],
                    marker="s", linestyle="--", color="crimson", label=extra[2])
        ax.set_xlabel("actual token reduction (%)")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        if ylim:
            ax.set_ylim(*ylim)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
        fig.tight_layout()
        p = out_dir / name
        fig.savefig(p, dpi=110)
        plt.close(fig)
        written.append(str(p))

    _save("cr_vs_task_quality.png",
          [d["task_quality_decision_proxy"], d["task_quality_incidental_proxy"]],
          ["decision-relevant (proxy)", "incidental (proxy)"],
          "task accuracy (proxy, %)", "Compression vs task quality", ylim=(-5, 105))
    _save("cr_vs_actiongate_invariance.png",
          [d["actiongate_invariance"]], ["protected prototype"],
          "ActionGate decision preserved (%)", "Compression vs ActionGate invariance",
          ylim=(-5, 105),
          extra=(d["generic_unaware"]["ratios"], d["generic_unaware"]["invariance"],
                 "protection-unaware (LLMLingua-2-style proxy)"))
    _save("cr_vs_cost.png", [d["cost_reduction_cache_adjusted"]], ["cache-adjusted"],
          "cost reduction (%)", "Compression vs cost reduction")
    _save("cr_vs_latency.png", [[v / 100 for v in d["latency_ms"]]], ["compress latency"],
          "latency (ms, /100 scale)", "Compression vs latency (wall-clock)")
    _save("cr_vs_fallback.png", [d["fallback_rate"]], ["fallback rate"],
          "fallback rate (%)", "Compression vs fallback rate", ylim=(-5, 105))
    return written
