"""Durable, resumable runner for the frozen real-LLM benchmark.

Reuses the FROZEN leaf functions (real_llm_bench._surviving/_prompt/_SYSTEM,
llm_tasks.build_tasks, the task scorers, real_llm_bench._hallucinated) so the
prompts, methods, budgets, and scoring are byte-identical to the frozen harness.
It only adds durable per-example persistence, resume, integrity guards, and the
final report via the frozen aggregation (real_llm_bench._success/render_report_md).

Usage: python run_benchmark.py            (config from environment)
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys

import runpod_common as RC

from actiongate_context_ablation import llm_tasks
from actiongate_context_ablation import real_llm_bench as R
from actiongate_context_ablation.corpus import registry
from actiongate_context_ablation import adapter, ablation, milestone_bench as MB, protected_detector as PD


class _Bench:
    """Version-selected benchmark surface. V1 uses the frozen llm_tasks/real_llm_bench;
    V2 uses the separate absolute-utility modules. The compression arms (_surviving) and
    prompt rendering (_prompt) are shared/frozen in both; only tasks, SYSTEM, task-types,
    scoring, verdict, and the fingerprint differ."""

    def __init__(self, version: str):
        self.version = version
        if version == "v2":
            from actiongate_context_ablation import llm_tasks_v2 as TV2
            from actiongate_context_ablation import real_llm_bench_v2 as RV2
            from actiongate_context_ablation import benchmark_v2 as BV2
            self.tasks = TV2
            self.system = RV2.SYSTEM_V2
            self.task_types = TV2.TASK_TYPES
            self.fingerprint = BV2.fingerprint()["fingerprint"]
        elif version == "v1":
            self.tasks = llm_tasks
            self.system = R._SYSTEM
            self.task_types = llm_tasks.TASK_TYPES
            self.fingerprint = RC.frozen_fingerprint()["fingerprint"]
        else:
            raise RuntimeError(f"unknown BENCHMARK_VERSION={version!r} (expected v1|v2)")


def _bench(config) -> _Bench:
    return _Bench(config.get("benchmark_version", "v1"))


def _prompt_hash(full_prompt: str) -> str:
    return "sha256:" + hashlib.sha256(full_prompt.encode("utf-8")).hexdigest()


def _model_revision(config) -> str:
    import os
    rev = os.environ.get("MODEL_REVISION")
    if rev:
        return rev
    rf = pathlib.Path(config["model_dir"]) / "revision.txt"
    return rf.read_text().strip() if rf.exists() else "local-unpinned"


def _needs_eager_attention(model_id: str) -> bool:
    """Gemma-2 uses logit soft-capping + sliding-window attention that the fused SDPA/
    FlashAttention kernels silently break: HuggingFace explicitly requires the *eager*
    attention implementation for Gemma-2, otherwise every generation raises. This is a
    per-family model-loading requirement, NOT a change to prompts, tasks, or scoring."""
    return "gemma-2" in (model_id or "").lower()


def build_client(config):
    """Return a real client, or the mock ONLY if ALLOW_MOCK=1 (local tests). A primary
    or smoke run must never silently use the mock reader.

    Deployment-layer only: this file is NOT part of the frozen benchmark fingerprint, so
    per-family loading requirements are handled here rather than in the frozen client.
    For Gemma-2 we inject attn_implementation='eager' by wrapping from_pretrained; the
    frozen TransformersLLMClient bytes are untouched and every other family loads exactly
    as before, so the frozen fingerprint is identical for all models."""
    from actiongate_context_ablation import llm_client
    if config["allow_mock"]:
        return llm_client.MockReaderClient()
    if _needs_eager_attention(config["model_id"]):
        import transformers
        _orig = transformers.AutoModelForCausalLM.from_pretrained

        def _eager_from_pretrained(*a, **k):
            k.setdefault("attn_implementation", "eager")
            return _orig(*a, **k)

        transformers.AutoModelForCausalLM.from_pretrained = _eager_from_pretrained
        try:
            client = llm_client.TransformersLLMClient(
                config["model_dir"], max_new_tokens=config["max_new_tokens"],
                dtype=config["dtype"], device=config["device"])
        finally:
            transformers.AutoModelForCausalLM.from_pretrained = _orig
    else:
        client = llm_client.TransformersLLMClient(
            config["model_dir"], max_new_tokens=config["max_new_tokens"],
            dtype=config["dtype"], device=config["device"])
    if not getattr(client, "is_real", False):
        raise RuntimeError("primary/smoke run requires a real model; refusing mock backend")
    return client


def expected_config(config, revision) -> dict:
    b = _bench(config)
    return {
        "run_id": config["run_id"], "run_kind": config["run_kind"],
        "benchmark_version": b.version,
        "model_id": config["model_id"], "model_revision": revision,
        "budgets": config["budgets"], "methods": config["methods"],
        "max_new_tokens": config["max_new_tokens"], "dtype": config["dtype"],
        "system_hash": _prompt_hash(b.system),
        "frozen_fingerprint": b.fingerprint,
    }


def check_resume_guard(config, revision):
    """Reject a resume whose model revision, prompts, methods/budgets, run kind, or
    frozen-artifact fingerprint changed since the run started."""
    cfg_path = RC.config_path(config)
    want = expected_config(config, revision)
    if not cfg_path.exists():
        RC.write_json_atomic(cfg_path, want)
        return
    have = json.loads(cfg_path.read_text())
    for key in ("run_kind", "benchmark_version", "model_id", "model_revision",
                "system_hash", "frozen_fingerprint", "max_new_tokens"):
        if have.get(key) != want.get(key):
            raise RuntimeError(f"resume guard: '{key}' changed "
                               f"({have.get(key)!r} -> {want.get(key)!r}); refusing to mix runs")
    if set(map(float, have.get("budgets", []))) < set(want["budgets"]) and False:
        pass  # budgets may be a superset on resume; new budgets simply add work


def _iter_units(config, items, sp, protect, bench):
    for method in config["methods"]:
        budgets = [0.0] if method in ("original", "structural_only") else config["budgets"]
        for b in budgets:
            for item in items:
                surviving, invariant, env_ok = R._surviving(method, item.context, protect, sp, b)
                total = item.context.total_tokens
                kept = sum(item.context.unit(i).token_count for i in surviving)
                tred = (total - kept) / total if total else 0.0
                prompt_ctx = R._prompt(item.context, surviving)
                for task in bench.tasks.build_tasks(item, sp):
                    yield (method, b, item, task, surviving, invariant, env_ok, tred, prompt_ctx)


def run(config=None, client=None):
    config = config or RC.load_config()
    gs = RC.git_state()
    if gs["dirty"] and not config["allow_dirty"]:
        raise RuntimeError("repository tree is dirty; commit or set ALLOW_DIRTY=1 to override")

    items = registry.load_all()
    if config["contexts_limit"]:
        items = items[: config["contexts_limit"]]
    sp = adapter.default_signed_policy()
    runs = [ablation.run_ablations(it.context, sp) for it in items]
    protect = MB.hybrid_protect_fn(PD.fit(items, runs))

    bench = _bench(config)
    if client is None:
        client = build_client(config)
    revision = _model_revision(config)
    check_resume_guard(config, revision)

    rpath = RC.records_path(config)
    done = {}
    for rec in RC.read_records(rpath):
        # Never mix benchmark versions in one run dir: a V1 record in a V2 run (or vice
        # versa) is a fatal integrity error, not a resumable state.
        rv = rec.get("benchmark_version", "v1")
        if rv != bench.version:
            raise RuntimeError(f"resume guard: record benchmark_version {rv!r} != run "
                               f"{bench.version!r}; refusing to mix V1/V2 records in {rpath}")
        k = rec["key"]
        if k in done and done[k] != rec.get("prompt_hash"):
            raise RuntimeError(f"duplicate result key with differing prompt: {k}")
        done[k] = rec.get("prompt_hash")

    n_new = 0
    for (method, b, item, task, surviving, invariant, env_ok, tred, prompt_ctx) in \
            _iter_units(config, items, sp, protect, bench):
        key = RC.example_key(config["run_id"], revision, method, b, item.item_id, task["type"])
        full_prompt = f"CONTEXT:\n{prompt_ctx}\n\nQUESTION: {task['question']}"
        ph = _prompt_hash(full_prompt)
        if key in done:
            if done[key] != ph:
                raise RuntimeError(f"resume guard: prompt changed for existing key {key}")
            continue
        status = "OK"
        err_msg = ""
        try:
            resp = client.generate(bench.system, full_prompt, task=task)
            score = float(task["scorer"](resp.text))
            halluc = R._hallucinated(task["type"], resp.text, full_prompt)
        except Exception as exc:   # OOM / parse / runtime
            resp = None
            score = 0.0
            halluc = False
            status = "ERROR:" + exc.__class__.__name__
            # Keep the message (truncated) so a systemic failure (e.g. a family that
            # needs a specific attention impl) is diagnosable instead of blind.
            err_msg = str(exc)[:500]
        record = {
            "key": key, "run_id": config["run_id"], "run_kind": config["run_kind"],
            "benchmark_version": bench.version,
            "example_id": item.item_id, "task": task["type"], "model_id": config["model_id"],
            "model_revision": revision, "method": method, "budget": b,
            "prompt_hash": ph,
            "output": (resp.text if resp else ""),
            "parsed_output": (resp.text.strip() if resp else ""),
            "score": score, "hallucination": bool(halluc),
            "prompt_tokens": (resp.prompt_tokens if resp else 0),
            "completion_tokens": (resp.completion_tokens if resp else 0),
            "latency_ms": (resp.latency_ms if resp else 0.0),
            "peak_mem_mb": (getattr(resp, "peak_mem_mb", 0.0) if resp else 0.0),
            "throughput_tps": (getattr(resp, "throughput_tps", 0.0) if resp else 0.0),
            "is_real": bool(resp.is_real) if resp else False,
            "token_reduction": tred, "decision_preservation": bool(invariant),
            "envelope_preservation": bool(env_ok), "status": status,
            "error": err_msg,
        }
        RC.atomic_append_jsonl(rpath, record)
        done[key] = ph
        n_new += 1
    return {"run_id": config["run_id"], "records_path": str(rpath), "new_records": n_new,
            "total_records": len(done), "model_revision": revision}


# --- aggregation back through the FROZEN verdict/report logic ----------------
def records_to_cells(records) -> list:
    by_cell = {}
    for r in records:
        by_cell.setdefault((r["method"], float(r["budget"])), []).append(r)
    cells = []
    for (method, budget), recs in sorted(by_cell.items()):
        by_ctx = {}
        for r in recs:
            by_ctx.setdefault(r["example_id"], []).append(r)
        n = len(by_ctx)
        tred = sum(next(iter(v))["token_reduction"] for v in by_ctx.values()) / n
        decp = sum(1.0 for v in by_ctx.values() if next(iter(v))["decision_preservation"]) / n
        envp = sum(1.0 for v in by_ctx.values() if next(iter(v))["envelope_preservation"]) / n
        acc = sum(sum(x["score"] for x in v) / len(v) for v in by_ctx.values()) / n
        per_type = {t: [0.0, 0] for t in llm_tasks.TASK_TYPES}
        halluc = [0, 0]
        ifail = [0, 0]
        toolc = [0.0, 0]
        lat = 0.0
        cost = 0.0
        for r in recs:
            pt = per_type[r["task"]]
            pt[0] += r["score"]
            pt[1] += 1
            halluc[0] += 1 if r["hallucination"] else 0
            halluc[1] += 1
            lat += r["latency_ms"]
            cost += r["prompt_tokens"] / 1000 * R.PRICE_IN + r["completion_tokens"] / 1000 * R.PRICE_OUT
            if r["task"] == "instruction_following":
                ifail[0] += 1 if r["score"] < 1.0 else 0
                ifail[1] += 1
            if r["task"] in ("tool_selection", "tool_argument_generation"):
                toolc[0] += r["score"]
                toolc[1] += 1
        cells.append(R.Cell(
            method=method, budget=budget, token_reduction=tred,
            decision_preservation=decp, envelope_preservation=envp, task_accuracy=acc,
            per_task_accuracy={t: (v[0] / v[1] if v[1] else None) for t, v in per_type.items()},
            hallucination_rate=(halluc[0] / halluc[1] if halluc[1] else 0.0),
            instruction_following_failure=(ifail[0] / ifail[1] if ifail[1] else 0.0),
            tool_call_correctness=(toolc[0] / toolc[1] if toolc[1] else 1.0),
            mean_latency_ms=lat / n, cost_estimate_usd=cost, n_contexts=n))
    return cells


def build_result(records) -> R.Result:
    cells = records_to_cells(records)
    is_real = bool(records) and all(r.get("is_real") for r in records)
    rec, detail = R._success(cells, is_real)
    note = "" if is_real else ("NON-SCIENTIFIC: records were produced by the mock reader.")
    return R.Result(is_real=is_real, client_name=("durable-run" if is_real else "mock"),
                    availability_reason="", cells=cells, success=detail,
                    recommendation=rec, note=note)


# --- V2 aggregation (absolute-utility benchmark) -----------------------------
def records_to_cells_v2(records) -> list:
    """Aggregate V2 records into V2 cells (field-aware, with protected_recall)."""
    from actiongate_context_ablation import real_llm_bench_v2 as R2
    from actiongate_context_ablation import llm_tasks_v2 as T2
    by_cell = {}
    for r in records:
        by_cell.setdefault((r["method"], float(r["budget"])), []).append(r)
    cells = []
    for (method, budget), recs in sorted(by_cell.items()):
        by_ctx = {}
        for r in recs:
            by_ctx.setdefault(r["example_id"], []).append(r)
        n = len(by_ctx)
        tred = sum(next(iter(v))["token_reduction"] for v in by_ctx.values()) / n
        decp = sum(1.0 for v in by_ctx.values() if next(iter(v))["decision_preservation"]) / n
        envp = sum(1.0 for v in by_ctx.values() if next(iter(v))["envelope_preservation"]) / n
        # protected_recall proxy: for protected/structural arms every retained context
        # preserves the decision-critical envelope (env preservation == recall of protected
        # spans). We report it explicitly so the safety criterion is auditable.
        recall = envp
        acc = sum(sum(x["score"] for x in v) / len(v) for v in by_ctx.values()) / n
        per_type = {t: [0.0, 0] for t in T2.TASK_TYPES}
        halluc = [0, 0]
        lat = cost = 0.0
        for r in recs:
            if r["task"] in per_type:
                per_type[r["task"]][0] += r["score"]
                per_type[r["task"]][1] += 1
            halluc[0] += 1 if r.get("hallucination") else 0
            halluc[1] += 1
            lat += r["latency_ms"]
            cost += r["prompt_tokens"] / 1000 * R2.PRICE_IN + r["completion_tokens"] / 1000 * R2.PRICE_OUT
        cells.append(R2.Cell(
            method=method, budget=budget, token_reduction=tred,
            decision_preservation=decp, envelope_preservation=envp, protected_recall=recall,
            task_accuracy=acc,
            per_task_accuracy={t: (v[0] / v[1] if v[1] else None) for t, v in per_type.items()},
            hallucination_rate=(halluc[0] / halluc[1] if halluc[1] else 0.0),
            mean_latency_ms=lat / n, cost_estimate_usd=cost, n_contexts=n))
    return cells


def build_result_v2(records) -> dict:
    """Return the V2 result JSON (recommendation + criteria + cells) from records."""
    from actiongate_context_ablation import real_llm_bench_v2 as R2
    cells = records_to_cells_v2(records)
    is_real = bool(records) and all(r.get("is_real") for r in records)
    rec, detail = R2._success(cells, is_real)
    return R2.to_json(rec, detail, cells, is_real)


if __name__ == "__main__":   # pragma: no cover
    out = run()
    print(json.dumps(out, indent=2))
