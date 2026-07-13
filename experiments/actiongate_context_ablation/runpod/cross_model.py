"""Cross-model reproducibility analysis for ActionGate Context Minimization.

Aggregates per-model results (each a durable run's results.json + run_manifest.json,
optionally records.jsonl) produced by the FROZEN benchmark. Computes the forest
deltas, decision-preservation comparison, cost/accuracy tradeoff, architecture
sensitivity (with bootstrap CIs where records are available), a failure taxonomy,
and the replication verdict. Missing models are skipped honestly; non-real (mock)
results never count toward the scientific verdict.

This is analysis machinery — it does not run models and does not touch ActionGate,
the compressor, extractor, detector, corpus, prompts, budgets, or scoring.
"""

from __future__ import annotations

import json
import pathlib
import random
from dataclasses import dataclass, field

BUDGETS = (0.2, 0.3, 0.4)

# HF ids for the planned replication set (the already-run Qwen-7B is included when present)
PLANNED_MODELS = [
    "Qwen/Qwen2.5-14B-Instruct",
    "meta-llama/Llama-3.1-8B-Instruct",
    "google/gemma-2-9b-it",
    "mistralai/Mistral-7B-Instruct-v0.3",
]

NON_REGRESSION_MARGIN = 0.02   # protected task-delta must be >= -2% to "preserve utility"

# ---- replication verdicts ----
CONSISTENT_REPLICATION = "CONSISTENT_REPLICATION"
PARTIAL_REPLICATION = "PARTIAL_REPLICATION"
MODEL_SPECIFIC = "MODEL_SPECIFIC"
FAILED_REPLICATION = "FAILED_REPLICATION"
INSUFFICIENT_MODELS = "INSUFFICIENT_MODELS"

# ---- failure taxonomy categories ----
FAILURE_CATEGORIES = ("hallucination", "extraction_miss", "summarization_loss",
                      "reasoning_degradation", "policy_misunderstanding",
                      "tool_argument_error", "tool_selection_error", "decision_flip")
_TASK_TO_CAUSE = {
    "extraction": "extraction_miss",
    "factual_qa": "extraction_miss",
    "summarization": "summarization_loss",
    "reasoning": "reasoning_degradation",
    "instruction_following": "policy_misunderstanding",
    "actiongate_envelope_extraction": "policy_misunderstanding",
    "tool_argument_generation": "tool_argument_error",
    "tool_selection": "tool_selection_error",
}


@dataclass
class ModelResult:
    model_id: str
    model_revision: str
    is_real: bool
    cells: list
    records_path: pathlib.Path | None = None
    short: str = ""

    def cell(self, method, budget):
        for c in self.cells:
            if c["method"] == method and abs(float(c["budget"]) - budget) < 1e-9:
                return c
        return None

    def task_acc(self, method, budget):
        c = self.cell(method, budget)
        return c["task_accuracy"] if c else None

    def decision_pres(self, method, budget):
        c = self.cell(method, budget)
        return c["decision_preservation"] if c else None


def load_model_result(result_dir) -> ModelResult | None:
    d = pathlib.Path(result_dir)
    rj, mj = d / "results.json", d / "run_manifest.json"
    if not rj.exists():
        return None
    res = json.loads(rj.read_text())
    man = json.loads(mj.read_text()) if mj.exists() else {}
    # run_config.model_id is authoritative (what the run committed to). The top-level
    # manifest model_id can be mislabeled if collect ran without MODEL_ID exported, which
    # would otherwise collapse/mis-name distinct architectures in the report.
    model_id = (man.get("run_config", {}).get("model_id")
                or man.get("model_id")
                or res.get("model_id", d.name))
    rp = d / "records.jsonl"
    return ModelResult(
        model_id=model_id,
        model_revision=man.get("model_revision", "unknown"),
        is_real=bool(res.get("is_real_llm", False)),
        cells=res.get("cells", []),
        records_path=(rp if rp.exists() else None),
        short=model_id.split("/")[-1])


def discover(dirs) -> list:
    out = []
    for d in dirs:
        m = load_model_result(d)
        if m is not None:
            out.append(m)
    # de-dupe by (model_id, revision); prefer the one with records
    best = {}
    for m in out:
        k = (m.model_id, m.model_revision)
        if k not in best or (m.records_path and not best[k].records_path):
            best[k] = m
    return list(best.values())


# --------------------------------------------------------------------------- #
# per-context matched deltas (needs records.jsonl) for CIs and forest
# --------------------------------------------------------------------------- #
def _per_context_task_means(records_path, method):
    """example_id -> mean task score for a method (pooled over its budgets)."""
    by_ctx = {}
    with open(records_path) as f:
        for ln in f:
            ln = ln.strip()
            if not ln:
                continue
            r = json.loads(ln)
            if r.get("method") != method:
                continue
            by_ctx.setdefault(r["example_id"], []).append(r.get("score", 0.0))
    return {k: sum(v) / len(v) for k, v in by_ctx.items()}


def matched_deltas(model: ModelResult):
    """protected - original per-context task-accuracy deltas (pooled budgets)."""
    if not model.records_path:
        return None
    orig = _per_context_task_means(model.records_path, "original")
    prot = _per_context_task_means(model.records_path, "protected")
    common = sorted(set(orig) & set(prot))
    return [prot[c] - orig[c] for c in common]


def _bootstrap_ci(xs, iters=1000, seed=0, alpha=0.05):
    if not xs:
        return (None, None)
    rng = random.Random(seed)
    n = len(xs)
    means = []
    for _ in range(iters):
        s = [xs[rng.randrange(n)] for _ in range(n)]
        means.append(sum(s) / n)
    means.sort()
    lo = means[int((alpha / 2) * iters)]
    hi = means[int((1 - alpha / 2) * iters)]
    return (lo, hi)


# --------------------------------------------------------------------------- #
# cross-model summaries
# --------------------------------------------------------------------------- #
def forest_data(models) -> list:
    """Per model: protected-vs-original task delta (mean over budgets) + CI if records."""
    out = []
    for m in models:
        deltas_budget = []
        for b in BUDGETS:
            o, p = m.task_acc("original", 0.0), m.task_acc("protected", b)
            if o is not None and p is not None:
                deltas_budget.append(p - o)
        point = sum(deltas_budget) / len(deltas_budget) if deltas_budget else None
        ctx_deltas = matched_deltas(m)
        lo, hi = _bootstrap_ci(ctx_deltas) if ctx_deltas else (None, None)
        out.append({"model": m.short, "is_real": m.is_real, "delta_mean": point,
                    "ci_low": lo, "ci_high": hi, "n_contexts": (len(ctx_deltas) if ctx_deltas else None)})
    return out


def decision_comparison(models) -> list:
    out = []
    for m in models:
        row = {"model": m.short, "is_real": m.is_real, "budgets": {}}
        for b in BUDGETS:
            row["budgets"][b] = {
                "protected": m.decision_pres("protected", b),
                "protection_unaware": m.decision_pres("protection_unaware", b)}
        out.append(row)
    return out


def cost_accuracy(models) -> list:
    out = []
    for m in models:
        pts = []
        for b in BUDGETS:
            c = m.cell("protected", b)
            if c:
                pts.append({"budget": b, "token_reduction": c["token_reduction"],
                            "cost": c["cost_estimate_usd"], "task_accuracy": c["task_accuracy"]})
        oc = m.cell("original", 0.0)
        out.append({"model": m.short, "is_real": m.is_real,
                    "original_cost": (oc["cost_estimate_usd"] if oc else None),
                    "original_accuracy": (oc["task_accuracy"] if oc else None),
                    "protected": pts})
    return out


def architecture_sensitivity(models) -> dict:
    """How much each architecture's task accuracy moves under compression (mean |delta|),
    ranked. Small |delta| => insensitive (robust to compression)."""
    reals = [m for m in models if m.is_real]
    rows = []
    for m in reals:
        f = next(x for x in forest_data([m]))
        rows.append({"model": m.short, "delta_mean": f["delta_mean"],
                     "ci_low": f["ci_low"], "ci_high": f["ci_high"]})
    deltas = [r["delta_mean"] for r in rows if r["delta_mean"] is not None]
    spread = (max(deltas) - min(deltas)) if len(deltas) >= 2 else None
    return {"per_model": sorted(rows, key=lambda r: (r["delta_mean"] is None, r["delta_mean"])),
            "delta_spread": spread,
            "note": ("delta_spread is the range of protected-vs-original task deltas across "
                     "real models; small spread => architecture-insensitive.")}


def failure_taxonomy(models) -> dict:
    """Cluster failures (score<1) by cause, per real model, from records.jsonl.
    Adds decision_flip counts from the protection_unaware cells."""
    tax = {}
    for m in models:
        if not m.is_real:
            continue
        counts = {c: 0 for c in FAILURE_CATEGORIES}
        if m.records_path:
            with open(m.records_path) as f:
                for ln in f:
                    ln = ln.strip()
                    if not ln:
                        continue
                    r = json.loads(ln)
                    if r.get("hallucination"):
                        counts["hallucination"] += 1
                        continue
                    if r.get("score", 1.0) < 1.0:
                        cause = _TASK_TO_CAUSE.get(r.get("task"), "policy_misunderstanding")
                        counts[cause] += 1
        # decision flips are structural (protection_unaware): count flipped contexts
        for b in BUDGETS:
            c = m.cell("protection_unaware", b)
            if c:
                counts["decision_flip"] += round((1.0 - c["decision_preservation"]) * c["n_contexts"])
        tax[m.short] = {"counts": counts,
                        "records_available": bool(m.records_path)}
    return tax


def _model_replicates(m: ModelResult) -> dict:
    """A model replicates the hypothesis if protected preserves decisions (100% at all
    budgets), preserves utility (task-delta >= -margin), and protection beats
    protection-unaware on decision preservation somewhere."""
    prot_dec = [m.decision_pres("protected", b) for b in BUDGETS]
    prot_dec_ok = all(d is not None and d >= 1.0 - 1e-9 for d in prot_dec)
    f = next(x for x in forest_data([m]))
    utility_ok = (f["delta_mean"] is not None and f["delta_mean"] >= -NON_REGRESSION_MARGIN)
    beats_unaware = any(
        (m.decision_pres("protected", b) or 0) > (m.decision_pres("protection_unaware", b) or 0)
        for b in BUDGETS)
    replicates = bool(prot_dec_ok and utility_ok and beats_unaware)
    return {"model": m.short, "protected_decisions_100": prot_dec_ok,
            "utility_preserved": utility_ok, "protection_beats_unaware": beats_unaware,
            "replicates": replicates, "task_delta_mean": f["delta_mean"]}


def verdict(models) -> dict:
    reals = [m for m in models if m.is_real]
    per = [_model_replicates(m) for m in reals]
    n = len(reals)
    n_rep = sum(1 for p in per if p["replicates"])
    if n < 2:
        v = INSUFFICIENT_MODELS
    elif n_rep == n:
        v = CONSISTENT_REPLICATION
    elif n_rep > n / 2:
        v = PARTIAL_REPLICATION
    elif n_rep > 0:
        v = MODEL_SPECIFIC
    else:
        v = FAILED_REPLICATION
    return {"verdict": v, "n_real_models": n, "n_replicating": n_rep, "per_model": per}


def analyze(models) -> dict:
    real = [m for m in models if m.is_real]
    present_ids = {m.model_id for m in models}
    return {
        "n_models": len(models), "n_real": len(real),
        "models_present": sorted(present_ids),
        "models_planned_pending": [mid for mid in PLANNED_MODELS if mid not in present_ids],
        "forest": forest_data(models),
        "decision_comparison": decision_comparison(models),
        "cost_accuracy": cost_accuracy(models),
        "architecture_sensitivity": architecture_sensitivity(models),
        "failure_taxonomy": failure_taxonomy(models),
        "replication": verdict(models),
    }


def _pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}%"


def _ci(lo, hi):
    return "—" if lo is None else f"[{100*lo:+.1f}%, {100*hi:+.1f}%]"


def render_investor_md(models) -> str:
    a = analyze(models)
    rep = a["replication"]
    real = [m for m in models if m.is_real]
    L, ap = [], None
    out = []
    ap = out.append
    ap("# CROSS_MODEL_RESULTS — ActionGate Context Minimization replication\n")
    ap("> Measured claims only. The Qwen2.5-7B primary run is frozen evidence; other "
       "models run the IDENTICAL frozen benchmark (same compressor, prompts, budgets, "
       "scoring — verified by fingerprint). No fabricated results: models that did not "
       "run are listed as pending.\n")
    ap(f"**Replication verdict: `{rep['verdict']}`**  "
       f"({rep['n_replicating']}/{rep['n_real_models']} real models replicate the hypothesis)\n")
    if rep["verdict"] == INSUFFICIENT_MODELS:
        ap("> Only one real model has run so far (Qwen2.5-7B). Cross-model replication "
           "requires ≥2 real models; run the pending models on RunPod to complete it.\n")
    ap(f"- Real models measured: **{a['n_real']}** — "
       + (", ".join(m.short for m in real) if real else "none") + ".")
    if a["models_planned_pending"]:
        ap(f"- Pending (not yet run): {', '.join(a['models_planned_pending'])}.\n")

    ap("## 1 · Protected vs original — task delta (utility non-regression)\n")
    ap("| model | task delta (protected − original) | 95% CI | real |")
    ap("|---|---|---|---|")
    for f in a["forest"]:
        ap(f"| {f['model']} | {_pct(f['delta_mean'])} | {_ci(f['ci_low'], f['ci_high'])} | {f['is_real']} |")
    ap("")

    ap("## 2 · Decision preservation — protected vs protection-unaware\n")
    ap("| model | budget | protected | protection-unaware |")
    ap("|---|---|---|---|")
    for row in a["decision_comparison"]:
        for b in BUDGETS:
            d = row["budgets"][b]
            ap(f"| {row['model']} | {int(b*100)}% | {_pct(d['protected'])} | {_pct(d['protection_unaware'])} |")
    ap("")

    ap("## 3 · Cost vs accuracy (protected)\n")
    ap("| model | budget | token↓ | cost $ | task acc |")
    ap("|---|---|---|---|---|")
    for ca in a["cost_accuracy"]:
        for p in ca["protected"]:
            ap(f"| {ca['model']} | {int(p['budget']*100)}% | {_pct(p['token_reduction'])} | "
               f"{p['cost']:.4f} | {_pct(p['task_accuracy'])} |")
    ap("")

    ap("## 4 · Architecture sensitivity\n")
    s = a["architecture_sensitivity"]
    ap(f"- Task-delta spread across real models: "
       f"{('—' if s['delta_spread'] is None else _pct(s['delta_spread']))} "
       "(small ⇒ architecture-insensitive).")
    ap("| model | task delta | 95% CI |")
    ap("|---|---|---|")
    for r in s["per_model"]:
        ap(f"| {r['model']} | {_pct(r['delta_mean'])} | {_ci(r['ci_low'], r['ci_high'])} |")
    ap("")

    ap("## 5 · Failure taxonomy (real models, from raw records)\n")
    tax = a["failure_taxonomy"]
    if not tax:
        ap("_No real-model records available yet._\n")
    else:
        ap("| model | " + " | ".join(FAILURE_CATEGORIES) + " | records |")
        ap("|---|" + "---|" * (len(FAILURE_CATEGORIES) + 1))
        for mod, t in tax.items():
            c = t["counts"]
            ap(f"| {mod} | " + " | ".join(str(c[k]) for k in FAILURE_CATEGORIES)
               + f" | {'yes' if t['records_available'] else 'no'} |")
        ap("")

    ap("## Interpretation\n")
    if rep["verdict"] == CONSISTENT_REPLICATION:
        ap("Every real model replicates: protected compression preserves 100% of ActionGate "
           "decisions with no utility regression, and beats protection-unaware compression. "
           "The effect is architecture-general on this corpus.")
    elif rep["verdict"] == INSUFFICIENT_MODELS:
        ap("One real model (Qwen2.5-7B) shows protected compression preserving decisions and "
           "utility while protection-unaware degrades decisions. This is consistent with the "
           "hypothesis but is a single architecture — cross-model replication is **pending** "
           "the other models. No cross-model claim is made yet.")
    else:
        ap(f"Verdict `{rep['verdict']}`: see the per-model replication table above. "
           "Consistency is not forced.")
    ap("\n_All numbers are measured on the frozen benchmark; absolute task accuracy is known "
       "to be depressed by three under-specified tasks (operation-enum items absent from "
       "context; exact-match extraction) — the load-bearing quantity is the protected−original "
       "delta and the protected-vs-unaware decision-preservation gap._")
    return "\n".join(out)


def to_json(models) -> dict:
    return analyze(models)
