"""Tradeoff plots for the real-LLM validation harness.

Kept separate from the library/tests (no matplotlib dependency in the core). When
no real LLM ran, every figure is stamped NON-SCIENTIFIC (deterministic-reader dry
run) so the images can never be mistaken for measured LLM results.
"""

from __future__ import annotations

import json
import pathlib


def _series(res, method):
    xs, cells = [], [c for c in res.cells if c.method == method]
    return sorted(cells, key=lambda c: c.token_reduction)


def plot_data(res) -> dict:
    d = {"is_real_llm": res.is_real, "methods": {}}
    for m in ("protected", "protection_unaware"):
        cells = _series(res, m)
        d["methods"][m] = {
            "token_reduction": [c.token_reduction for c in cells],
            "task_accuracy": [c.task_accuracy for c in cells],
            "decision_preservation": [c.decision_preservation for c in cells],
            "cost_estimate_usd": [c.cost_estimate_usd for c in cells],
            "latency_ms": [c.mean_latency_ms for c in cells],
        }
    return d


def render(res, out_dir) -> list:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    d = plot_data(res)
    (out_dir / "real_llm_plot_data.json").write_text(json.dumps(d, indent=2) + "\n")
    wm = None if res.is_real else "NON-SCIENTIFIC dry run (deterministic reader, no real LLM)"
    written = []

    def _fig(name, ykey, ylabel, title, ylim=None):
        fig, ax = plt.subplots(figsize=(6, 4))
        for m, style in (("protected", dict(marker="o", color="green")),
                         ("protection_unaware", dict(marker="s", color="crimson", linestyle="--"))):
            md = d["methods"][m]
            ax.plot([100 * x for x in md["token_reduction"]],
                    [100 * y for y in md[ykey]], label=m, **style)
        ax.set_xlabel("token reduction (%)")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        if ylim:
            ax.set_ylim(*ylim)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=8)
        if wm:
            ax.text(0.5, 0.5, wm, transform=ax.transAxes, fontsize=9, color="gray",
                    alpha=0.5, ha="center", va="center", rotation=20)
        fig.tight_layout()
        p = out_dir / name
        fig.savefig(p, dpi=110)
        plt.close(fig)
        written.append(str(p))

    _fig("rllm_accuracy_vs_compression.png", "task_accuracy", "task accuracy (%)",
         "Accuracy vs compression", ylim=(-5, 105))
    _fig("rllm_decision_vs_compression.png", "decision_preservation",
         "decision preserved (%)", "Decision preservation vs compression", ylim=(-5, 105))
    _fig("rllm_cost_vs_compression.png", "cost_estimate_usd", "cost estimate ($)",
         "Cost vs compression")
    _fig("rllm_latency_vs_compression.png", "latency_ms", "latency (ms)",
         "Latency vs compression")
    return written
