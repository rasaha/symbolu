"""Phase 6B.4 — GPU throughput bench (eager vs captured).

Measures the actual decode throughput uplift from CUDA Graphs
capture. Two cells:

  cell eager    : PHASE6B3_FORCE_EAGER=1 -> int4_protected runs
                  eagerly (matches 6B.1 + 6B.2 + the original
                  Phase 6 v2 Option A 42.6 tok/s @ B=8 baseline).
  cell captured : PHASE6B3_FORCE_EAGER unset -> Int4ProtectedLLM
                  default enforce_eager=False; vLLM captures all
                  35 decode shapes at engine init; the 6B.2 hook
                  populates each impl's _phase5b_slot_idx_buf
                  before every graph replay.

Each cell:
  * Loads Qwen-7B; records HBM stats pre/post init + per generate.
  * Warms up; resets call_stats + hook stats.
  * Runs B in {1, 2, 4, 8} sweeps, n_runs=5 per B, median wall
    time. The bench reports:
      - wall_s (median)
      - n_output_tokens (median)
      - agg_tps = n_output_tokens / wall_s
      - per_seq_tps = agg_tps / B
  * Writes a per-cell JSON.

Driver:
  * Spawns both workers as subprocesses with the proper env.
  * Compares per-B agg_tps across cells; emits speedup factor.
  * G_THROUGHPUT acceptance gate: captured agg_tps @ B=8 >= 80 tok/s
    (>= 1.88x the eager 42.6 baseline). Per the Phase 6B plan.

Mirrors the bench_phase6_b3_capture_gpu_smoke.py self-spawning
subprocess pattern. Uses n_runs=5 median to reduce timer jitter,
matching the methodology of the original Phase 6 baseline.

Run:
  python CTM_plus/Bench/scripts/bench_phase6_b4_throughput_gpu.py

For a single cell:
  python CTM_plus/Bench/scripts/bench_phase6_b4_throughput_gpu.py \\
    --worker --cell captured --output /tmp/cell_captured.json
"""
from __future__ import annotations

import argparse
import gc
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

ROOT_CANDIDATES = [
    Path("/workspace/symbolu/CTM_plus"),
    Path("/home/user/symbolu/CTM_plus"),
    Path(__file__).resolve().parent.parent.parent,
]
for _root in ROOT_CANDIDATES:
    kvp = _root / "KVPolicy"
    if kvp.is_dir() and str(kvp) not in sys.path:
        sys.path.insert(0, str(kvp))
        break


# Same prompts as the original Phase 6 v2 Option A baseline bench
# (bench_phase6_batched_throughput.py PROMPT) — same prompt repeated B
# times, so per-seq decode work is identical and the across-B speedup
# is interpretable as decode-batching gain (+ vLLM prefill batching;
# both move together).
PROMPT = (
    "Below is a paragraph about a small fictional town. After it, "
    "answer the question concisely.\n\n"
    "Greendell is nestled between two rivers and has a population of "
    "just over four thousand. Its main industries are pottery, honey "
    "production, and the seasonal wool trade. The annual harvest "
    "festival in early autumn draws visitors from across the region. "
    "The oldest building in town is a stone library founded in 1742.\n\n"
    "Question: What year was the oldest building in Greendell founded?\n"
    "Answer:"
)


CELL_EAGER    = "eager"
CELL_CAPTURED = "captured"
CELL_BF16     = "bf16"      # stock vLLM (no int4_protected), graphs enabled by default

CELLS = [CELL_EAGER, CELL_CAPTURED, CELL_BF16]

BATCH_SIZES = [1, 2, 4, 8]
DEFAULT_N_RUNS = 5

# Acceptance gate (per Phase 6B plan): captured B=8 agg_tps >= 80 tok/s.
G_THROUGHPUT_B8_MIN_TPS = 80.0
# The eager baseline from the original Phase 6 v2 Option A bench.
PHASE6_V2_EAGER_B8_BASELINE_TPS = 42.6


def _check_environment(require_int4: bool = True) -> tuple[bool, str]:
    try:
        import torch
        if not torch.cuda.is_available():
            return False, "torch.cuda.is_available() is False"
    except ImportError as exc:
        return False, f"torch import failed: {exc}"
    try:
        import vllm  # noqa: F401
    except ImportError as exc:
        return False, f"vllm import failed: {exc}"
    if require_int4:
        try:
            from kv_policy import int4_protected  # noqa: F401
        except ImportError as exc:
            return False, f"kv_policy.int4_protected import failed: {exc}"
    return True, "OK"


def _find_inner_model(llm):
    candidates = [
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model,
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model_runner.model,
        lambda x: x.model_executor.driver_worker.model_runner.model,
    ]
    for fn in candidates:
        try:
            m = fn(llm)
            if m is not None and hasattr(m, "named_modules"):
                return m
        except (AttributeError, IndexError):
            continue
    return None


def _find_model_runner(llm):
    candidates = [
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner,
        lambda x: x.model_executor.driver_worker.model_runner,
    ]
    for fn in candidates:
        try:
            m = fn(llm)
            if m is not None:
                return m
        except (AttributeError, IndexError):
            continue
    return None


def _reset_all_writers(inner_model) -> int:
    """Reset every Int4ProtectedAttentionImpl's writer back to fresh
    (slot pool fully free; SeqState dict cleared; counter pools at
    sentinel). Returns the number of writers reset. Same as 6B.3 smoke.
    """
    from kv_policy.phase5b_backend_install import Int4ProtectedAttentionImpl
    n = 0
    for _, sub in inner_model.named_modules():
        impl = getattr(sub, "impl", None)
        if not isinstance(impl, Int4ProtectedAttentionImpl):
            continue
        w = getattr(impl, "_phase5b_paged_writer", None)
        if w is not None and getattr(w, "_allocated", False):
            w.reset_sequence("all")
            n += 1
    return n


def _hbm_snapshot() -> dict:
    import torch
    free, total = torch.cuda.mem_get_info()
    return {
        "allocated_gb": torch.cuda.memory_allocated() / (1024**3),
        "reserved_gb":  torch.cuda.memory_reserved()  / (1024**3),
        "free_gb":      free  / (1024**3),
        "total_gb":     total / (1024**3),
        "used_gb":      (total - free) / (1024**3),
    }


def _bench_one_B(llm, inner, B: int, sampling, n_runs: int) -> Dict[str, Any]:
    """Run [PROMPT]*B through llm.generate, n_runs times, median.

    `inner` may be None (bf16 stock vLLM cell — no writer state to
    reset; vLLM manages its own KV cache between requests).
    """
    import torch
    prompts = [PROMPT] * B
    times: List[float] = []
    out_lens: List[int] = []
    last_text = None
    for _ in range(n_runs):
        if inner is not None:
            _reset_all_writers(inner)
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        outs = llm.generate(prompts, sampling)
        torch.cuda.synchronize()
        elapsed = time.perf_counter() - t0
        times.append(elapsed)
        n_out = sum(len(o.outputs[0].token_ids) for o in outs)
        out_lens.append(n_out)
        last_text = outs[0].outputs[0].text
    times.sort()
    out_lens.sort()
    median_t = times[len(times) // 2]
    median_out = out_lens[len(out_lens) // 2]
    return {
        "B":               B,
        "n_runs":          n_runs,
        "all_wall_s":      times,
        "wall_s":          median_t,
        "all_output_tok":  out_lens,
        "n_output_tokens": median_out,
        "wall_s_per_seq":  median_t / B,
        "agg_tps":         median_out / median_t if median_t > 0 else 0.0,
        "per_seq_tps":     (median_out / median_t / B) if median_t > 0 else 0.0,
        "sample_output":   (last_text or "")[:120],
    }


def run_worker(cell: str, output_path: Path, *, model: str,
               max_model_len: int, max_tokens: int,
               gpu_memory_utilization: float, n_runs: int) -> int:
    if cell not in CELLS:
        print(f"FAIL: unknown cell {cell!r}")
        return 1
    if cell == CELL_EAGER:
        os.environ["PHASE6B3_FORCE_EAGER"] = "1"
    else:
        os.environ.pop("PHASE6B3_FORCE_EAGER", None)

    require_int4 = (cell != CELL_BF16)
    ok, diag = _check_environment(require_int4=require_int4)
    if not ok:
        print(f"FAIL: {diag}")
        return 2

    import torch
    from vllm import SamplingParams

    hbm_before = _hbm_snapshot()
    print(f"[cell={cell}] HBM before load: used={hbm_before['used_gb']:.2f} GB / "
          f"{hbm_before['total_gb']:.2f} GB total")

    print(f"[cell={cell}] Loading {model}...")
    t0 = time.time()

    inner = None
    model_runner = None
    hook = None
    writers, impls = [], []

    if cell == CELL_BF16:
        # Stock vLLM, no int4_protected, no hook. Graphs are enabled by
        # default in vLLM (enforce_eager=False is the default). bf16 KV
        # cache is the model's native dtype for Qwen2.5-7B-Instruct.
        from vllm import LLM
        llm = LLM(
            model=model,
            max_model_len=max_model_len,
            gpu_memory_utilization=gpu_memory_utilization,
            dtype="bfloat16",
            # NOTE: vLLM's default kv_cache_dtype="auto" -> bf16 here.
            # No int4 quantization; no protect mask; no 6B.2 hook.
        )
        torch.cuda.synchronize()
    else:
        # int4_protected cells (eager + captured) — full Phase 6B stack.
        import kv_policy.int4_protected   # noqa: F401
        from kv_policy.int4_protected import Int4ProtectedLLM
        from kv_policy.phase5b_backend_install import Int4ProtectedAttentionImpl
        from kv_policy.phase6b2_precapture_hook import (
            install_int4_protected_precapture_hook,
        )
        llm = Int4ProtectedLLM(
            model=model,
            max_model_len=max_model_len,
            gpu_memory_utilization=gpu_memory_utilization,
        )
        torch.cuda.synchronize()

    t_load = time.time() - t0
    hbm_after_init = _hbm_snapshot()
    print(f"[cell={cell}] Loaded in {t_load:.1f}s. "
          f"HBM after init: {hbm_after_init['used_gb']:.2f} GB")

    print(f"[cell={cell}] Warmup...")
    llm.generate([PROMPT], SamplingParams(temperature=0.0, max_tokens=4))

    if cell != CELL_BF16:
        inner = _find_inner_model(llm)
        model_runner = _find_model_runner(llm)
        if inner is None or model_runner is None:
            print(f"FAIL: cannot locate inner model or model_runner")
            return 2
        for _, sub in inner.named_modules():
            impl = getattr(sub, "impl", None)
            if isinstance(impl, Int4ProtectedAttentionImpl):
                impls.append(impl)
                w = getattr(impl, "_phase5b_paged_writer", None)
                if w is not None:
                    writers.append(w)
        print(f"[cell={cell}] Collected {len(writers)} writers + {len(impls)} impls.")
        hook = install_int4_protected_precapture_hook(
            model_runner, writers, impls=impls,
        )
        print(f"[cell={cell}] Hook: enabled={hook.enabled}, target={hook.hook_target_name}")
    else:
        print(f"[cell={cell}] No int4 backend, no hook (stock vLLM bf16).")

    sampling = SamplingParams(temperature=0.0, max_tokens=max_tokens)

    per_b_results = {}
    for B in BATCH_SIZES:
        print(f"[cell={cell}] Running B={B} x {n_runs} runs...")
        r = _bench_one_B(llm, inner, B, sampling, n_runs=n_runs)
        per_b_results[B] = r
        print(f"[cell={cell}] B={B}: median wall {r['wall_s']:.3f}s  "
              f"out_tok={r['n_output_tokens']}  "
              f"agg_tps={r['agg_tps']:.1f}  per_seq_tps={r['per_seq_tps']:.1f}")

    hbm_final = _hbm_snapshot()
    payload = {
        "cell":                       cell,
        "model":                      model,
        "max_model_len":              max_model_len,
        "max_tokens":                 max_tokens,
        "gpu_memory_utilization":     gpu_memory_utilization,
        "load_seconds":               t_load,
        "batch_sizes":                BATCH_SIZES,
        "n_runs_per_B":               n_runs,
        "hook_enabled":               hook.enabled if hook else False,
        "hook_target_name":           hook.hook_target_name if hook else "n/a (bf16)",
        "hook_total_stash_calls":     hook.stash_call_count if hook else 0,
        "hbm_before_load":            hbm_before,
        "hbm_after_init":             hbm_after_init,
        "hbm_final":                  hbm_final,
        "capture_overhead_gb":        hbm_after_init["used_gb"] - hbm_before["used_gb"],
        "per_b":                      per_b_results,
        "phase6b3_force_eager_env":   os.environ.get("PHASE6B3_FORCE_EAGER"),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2))
    print(f"[cell={cell}] Wrote {output_path}")
    if hook is not None:
        hook.teardown()
    return 0


def compare(eager_path: Path, captured_path: Path,
            report_json: Path, report_txt: Path,
            bf16_path: Path | None = None) -> int:
    eager    = json.loads(eager_path.read_text())
    captured = json.loads(captured_path.read_text())
    bf16     = json.loads(bf16_path.read_text()) if (bf16_path and bf16_path.exists()) else None

    checks = []
    per_b_diffs = []
    for B in BATCH_SIZES:
        eb = eager["per_b"].get(str(B)) or eager["per_b"].get(B)
        cb = captured["per_b"].get(str(B)) or captured["per_b"].get(B)
        bb = (bf16["per_b"].get(str(B)) or bf16["per_b"].get(B)) if bf16 else None
        if eb is None or cb is None:
            checks.append((f"B{B}_per_b_present", False, "missing per_b entry"))
            continue
        e_tps = eb["agg_tps"]
        c_tps = cb["agg_tps"]
        b_tps = bb["agg_tps"] if bb else None
        speedup = (c_tps / e_tps) if e_tps > 0 else 0.0
        diff = {
            "B": B,
            "eager_agg_tps":    e_tps,
            "captured_agg_tps": c_tps,
            "speedup_x":        speedup,
            "eager_wall_s":     eb["wall_s"],
            "captured_wall_s":  cb["wall_s"],
            "eager_output_tokens":    eb["n_output_tokens"],
            "captured_output_tokens": cb["n_output_tokens"],
            "eager_sample":     eb["sample_output"],
            "captured_sample":  cb["sample_output"],
        }
        if bb:
            diff["bf16_agg_tps"]      = b_tps
            diff["bf16_wall_s"]       = bb["wall_s"]
            diff["bf16_output_tokens"] = bb["n_output_tokens"]
            diff["bf16_sample"]       = bb["sample_output"]
            diff["captured_vs_bf16_x"] = (c_tps / b_tps) if (b_tps and b_tps > 0) else 0.0
        per_b_diffs.append(diff)

    # G_THROUGHPUT primary gate: captured B=8 agg_tps >= 80 tok/s.
    cb8 = captured["per_b"].get("8") or captured["per_b"].get(8)
    eb8 = eager["per_b"].get("8")    or eager["per_b"].get(8)
    bb8 = (bf16["per_b"].get("8")    or bf16["per_b"].get(8)) if bf16 else None
    if cb8 is not None and eb8 is not None:
        b8_tps = cb8["agg_tps"]
        b8_speedup_vs_42p6 = b8_tps / PHASE6_V2_EAGER_B8_BASELINE_TPS
        checks.append((
            "captured_agg_tps_B8_ge_80",
            b8_tps >= G_THROUGHPUT_B8_MIN_TPS,
            f"captured B=8 agg_tps={b8_tps:.1f} tok/s "
            f"(gate >= {G_THROUGHPUT_B8_MIN_TPS:.1f}; "
            f"{b8_speedup_vs_42p6:.2f}x the 42.6 eager baseline)",
        ))
        checks.append((
            "captured_speedup_B8_ge_1p88x",
            b8_speedup_vs_42p6 >= 1.88,
            f"captured B=8 speedup vs 42.6 baseline = {b8_speedup_vs_42p6:.2f}x "
            f"(gate >= 1.88x)",
        ))
        in_run_speedup = (cb8["agg_tps"] / eb8["agg_tps"]) if eb8["agg_tps"] > 0 else 0.0
        checks.append((
            "in_run_speedup_B8_captured_vs_eager_positive",
            in_run_speedup > 1.0,
            f"in-run speedup B=8 = {in_run_speedup:.2f}x "
            f"(eager {eb8['agg_tps']:.1f} -> captured {cb8['agg_tps']:.1f} tok/s)",
        ))
        if bb8 is not None:
            # Industry comparison: int4_protected+graphs vs stock vLLM bf16+graphs.
            # Informational (not load-bearing on the gate verdict).
            ratio = (cb8["agg_tps"] / bb8["agg_tps"]) if bb8["agg_tps"] > 0 else 0.0
            checks.append((
                "info_captured_vs_bf16_B8_ratio",
                True,  # informational
                f"captured/bf16 B=8 ratio = {ratio:.2f}x "
                f"(bf16 stock {bb8['agg_tps']:.1f} -> int4 captured {cb8['agg_tps']:.1f} tok/s)",
            ))

    overall_ok = all(ok for _, ok, _ in checks)
    report = {
        "verdict":                "GREEN" if overall_ok else "RED",
        "eager_cell":             str(eager_path),
        "captured_cell":          str(captured_path),
        "bf16_cell":              str(bf16_path) if bf16_path else None,
        "model":                  eager.get("model"),
        "batch_sizes":            BATCH_SIZES,
        "n_runs_per_B":           eager.get("n_runs_per_B"),
        "checks":                 [{"name": n, "passed": ok, "detail": d} for n, ok, d in checks],
        "eager_load_seconds":     eager.get("load_seconds"),
        "captured_load_seconds":  captured.get("load_seconds"),
        "bf16_load_seconds":      bf16.get("load_seconds") if bf16 else None,
        "capture_overhead_gb":    captured.get("capture_overhead_gb"),
        "bf16_hbm_overhead_gb":   bf16.get("capture_overhead_gb") if bf16 else None,
        "per_b_diffs":            per_b_diffs,
    }
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(report, indent=2))

    lines = []
    lines.append("=" * 78)
    cells_in_run = "eager + captured" + (" + bf16" if bf16 else "")
    lines.append(f"Phase 6B.4 — throughput bench: {cells_in_run}")
    lines.append("=" * 78)
    lines.append(f"Model: {report['model']}    Batch sizes: {BATCH_SIZES}    "
                 f"n_runs/B: {report['n_runs_per_B']}")
    lines.append(f"Verdict: {report['verdict']}")
    lines.append("")
    lines.append(f"Load times:   eager={report['eager_load_seconds']:.1f}s    "
                 f"captured={report['captured_load_seconds']:.1f}s "
                 + (f"   bf16={report['bf16_load_seconds']:.1f}s" if bf16 else ""))
    lines.append(f"HBM:          captured cell={report['capture_overhead_gb']:.2f} GB "
                 + (f"   bf16 cell={report['bf16_hbm_overhead_gb']:.2f} GB" if bf16 else ""))
    lines.append("")
    lines.append("Checks (G_THROUGHPUT):")
    for c in report["checks"]:
        mark = "PASS" if c["passed"] else ("INFO" if c["name"].startswith("info_") else "FAIL")
        lines.append(f"  [{mark}] {c['name']:<52s} {c['detail']}")
    lines.append("")
    lines.append("Per-B throughput (tok/s):")
    if bf16:
        lines.append(f"  {'B':>3} | {'eager':>8} | {'captured':>9} | {'bf16':>8} | "
                     f"{'cap/eager':>10} | {'cap/bf16':>9}")
        lines.append("  " + "-" * 70)
        for d in report["per_b_diffs"]:
            lines.append(
                f"  {d['B']:>3} | {d['eager_agg_tps']:>8.1f} | "
                f"{d['captured_agg_tps']:>9.1f} | "
                f"{d.get('bf16_agg_tps', float('nan')):>8.1f} | "
                f"{d['speedup_x']:>9.2f}x | "
                f"{d.get('captured_vs_bf16_x', float('nan')):>8.2f}x"
            )
    else:
        lines.append(f"  {'B':>3} | {'eager_tps':>10} | {'cap_tps':>10} | "
                     f"{'speedup':>8} | {'eager_s':>8} | {'cap_s':>8}")
        lines.append("  " + "-" * 70)
        for d in report["per_b_diffs"]:
            lines.append(
                f"  {d['B']:>3} | {d['eager_agg_tps']:>10.1f} | "
                f"{d['captured_agg_tps']:>10.1f} | {d['speedup_x']:>7.2f}x | "
                f"{d['eager_wall_s']:>8.3f} | {d['captured_wall_s']:>8.3f}"
            )
    lines.append("")
    if overall_ok:
        lines.append("Phase 6B.4 GPU throughput: GREEN")
        lines.append("  CUDA Graphs capture delivers the projected throughput uplift.")
    else:
        lines.append("Phase 6B.4 GPU throughput: RED")
        lines.append("  At least one check failed. Inspect per-check 'detail' above.")
    report_txt.parent.mkdir(parents=True, exist_ok=True)
    report_txt.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0 if overall_ok else 1


def main() -> int:
    p = argparse.ArgumentParser()
    grp = p.add_mutually_exclusive_group()
    grp.add_argument("--worker", action="store_true",
                     help="Run as a single-cell worker (internal).")
    grp.add_argument("--compare", nargs="+", metavar="CELL_JSON",
                     help="Compare cell JSONs. Args: EAGER CAPTURED [BF16].")
    p.add_argument("--cell", choices=CELLS,
                   help="Worker mode: which cell to run.")
    p.add_argument("--output", type=str,
                   help="Worker mode: JSON output path for this cell's results.")
    p.add_argument("--output-dir", type=str,
                   default="bench_out/phase6b4_throughput",
                   help="Driver mode: directory for both cells + report.")
    p.add_argument("--cells", default="eager,captured,bf16",
                   help="Driver mode: comma-separated cells to run. "
                   "Default 'eager,captured,bf16' runs all three. Use "
                   "'eager,captured' to skip the bf16 industry baseline.")
    p.add_argument("--model",          default="Qwen/Qwen2.5-7B-Instruct")
    p.add_argument("--max-model-len",  type=int,   default=4096)
    p.add_argument("--max-tokens",     type=int,   default=32)
    p.add_argument("--gpu-memory-utilization", type=float, default=0.5)
    p.add_argument("--n-runs",         type=int,   default=DEFAULT_N_RUNS,
                   help="Number of timed runs per B (median reported).")
    args = p.parse_args()

    if args.worker:
        if not args.cell or not args.output:
            print("FAIL: --worker requires --cell and --output.")
            return 2
        return run_worker(
            cell=args.cell, output_path=Path(args.output),
            model=args.model, max_model_len=args.max_model_len,
            max_tokens=args.max_tokens,
            gpu_memory_utilization=args.gpu_memory_utilization,
            n_runs=args.n_runs,
        )

    if args.compare:
        if len(args.compare) < 2 or len(args.compare) > 3:
            print("FAIL: --compare requires EAGER CAPTURED [BF16].")
            return 2
        eager_path    = Path(args.compare[0])
        captured_path = Path(args.compare[1])
        bf16_path     = Path(args.compare[2]) if len(args.compare) == 3 else None
        return compare(
            eager_path=eager_path,
            captured_path=captured_path,
            report_json=eager_path.parent / "throughput_report.json",
            report_txt=eager_path.parent / "throughput_report.txt",
            bf16_path=bf16_path,
        )

    cells_to_run = [c.strip() for c in args.cells.split(",") if c.strip()]
    for c in cells_to_run:
        if c not in CELLS:
            print(f"FAIL: unknown cell {c!r} in --cells (valid: {CELLS})")
            return 2

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cell_paths = {c: out_dir / f"cell_{c}.json" for c in cells_to_run}
    report_json = out_dir / "throughput_report.json"
    report_txt  = out_dir / "throughput_report.txt"

    # Always require int4 for the driver's own env check (the int4 cells
    # need it; the bf16 worker re-checks with require_int4=False itself).
    ok, diag = _check_environment(require_int4=True)
    if not ok:
        print(f"FAIL: environment check: {diag}")
        return 2

    common_args = [
        "--worker",
        "--model", args.model,
        "--max-model-len", str(args.max_model_len),
        "--max-tokens", str(args.max_tokens),
        "--gpu-memory-utilization", str(args.gpu_memory_utilization),
        "--n-runs", str(args.n_runs),
    ]
    for cell in cells_to_run:
        out_path = cell_paths[cell]
        print()
        print(f"=== Driver: spawning worker for cell={cell} ===")
        cmd = [sys.executable, __file__] + common_args + [
            "--cell", cell, "--output", str(out_path),
        ]
        ret = subprocess.run(cmd, check=False)
        if ret.returncode != 0:
            print(f"FAIL: worker cell={cell} exited with code {ret.returncode}")
            return ret.returncode

    # Compare requires eager + captured at minimum; bf16 is optional.
    if CELL_EAGER not in cell_paths or CELL_CAPTURED not in cell_paths:
        print("Skipping compare(): need both eager and captured cells.")
        return 0
    return compare(
        eager_path=cell_paths[CELL_EAGER],
        captured_path=cell_paths[CELL_CAPTURED],
        report_json=report_json,
        report_txt=report_txt,
        bf16_path=cell_paths.get(CELL_BF16),
    )


if __name__ == "__main__":
    sys.exit(main())
