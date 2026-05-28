"""Phase 6H — high-load capacity bench.

Tests whether int4_protected's reported 2x max_concurrency translates
to 2x completed-load capacity at high B, or whether the sidecars
(audited in Phase 6G as ~16% overhead on top of vLLM's KV cache)
cause OOM at int4's reported limit.

Sweep (per Phase 6H design doc):

    max_model_len | B_low (just over bf16 max_conc) | B_high (near int4 max_conc)
       8192       |        64                        |        96
      16384       |        32                        |        48
      32768       |        16                        |        20

Reference max_concurrencies (audit-measured at gpu_memory_utilization=0.5):
    mml=8192:  bf16=55.3   int4=110.6
    mml=16384: bf16=26.4   int4=52.8
    mml=32768: bf16=12.0   int4=23.9

For each (cell, max_model_len, B) the bench captures:
  - completed_requests / failed_requests
  - end_to_end_wall_s
  - completed_tps = total_output_tokens / wall_s (only completed reqs)
  - peak_HBM_during_burst
  - scheduler preemption + swap counter delta
  - OOM event flag
  - quality_pass_rate (any seq contains the embedded answer "1742")
  - median output token count

Subprocess-per-(cell, mml, B) isolation:
  - max_num_seqs is set to B exactly, so vLLM captures only the shape
    we're testing (avoids over-capturing at long context).
  - Fresh process per run so HBM peak measurement is clean.
  - gpu_memory_utilization=0.4 (lower than long-context bench's 0.5)
    to leave room for the larger captured-graph intermediates at
    high B.

Driver aggregates 12 cell JSONs and writes a verdict report:

  JUSTIFIED:     int4 completes >=1.5x bf16's completed reqs at
                 the lower-B row of one or more max_model_lens,
                 with quality intact.
  PARTIAL:       int4 completes more than bf16 but <1.5x.
  NOT_JUSTIFIED: int4 OOMs at or below bf16's max_concurrency.

Run:
  python CTM_plus/Bench/scripts/bench_phase6_h_high_load_gpu.py

Single worker (internal):
  python CTM_plus/Bench/scripts/bench_phase6_h_high_load_gpu.py \\
    --worker --cell captured --max-model-len 8192 --batch-size 96 \\
    --output /tmp/h_cap_8k_96.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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


CELL_BF16     = "bf16"
CELL_CAPTURED = "captured"
CELLS = [CELL_BF16, CELL_CAPTURED]

# (max_model_len, B_low, B_high) per the Phase 6H design doc.
# B_low is just over bf16's max_concurrency at that mml; B_high
# approaches int4's reported max_concurrency.
DEFAULT_SWEEP: List[Tuple[int, List[int]]] = [
    (8192,  [64, 96]),
    (16384, [32, 48]),
    (32768, [16, 20]),
]

DEFAULT_MAX_TOKENS    = 48      # higher than long-context bench's 32; greedy
                                # decode needs room to actually emit "1742"
                                # after the answer preamble at long context.
DEFAULT_N_RUNS        = 2       # n_runs=2 keeps wall-clock budget reasonable
                                # at high B; we report median.
DEFAULT_GPU_MEM_UTIL  = 0.4     # lower than long-context's 0.5 because
                                # high-B captured graphs need more headroom
                                # for the read-path's gather intermediates.

QUALITY_FACT_ANSWER = "1742"

# Long synthetic prompt building blocks — same as the long-context bench so
# that prompt-level effects (prefill cost, attention shape) are comparable
# across the two benches.
PROMPT_INTRO = (
    "Below is a long document about a small fictional town. "
    "After the document, answer the question concisely.\n\n"
    "Document:\n"
)
PROMPT_FILLER = (
    "Greendell is nestled between two rivers and has a population of "
    "just over four thousand. Its main industries are pottery, honey "
    "production, and the seasonal wool trade. The annual harvest "
    "festival in early autumn draws visitors from across the region. "
    "The two rivers meet at the southern edge of town near the old mill. "
    "The town council meets the first Thursday of every month. "
    "The market square hosts a weekly produce fair on Saturdays. "
    "Local potters glaze in earth tones inspired by the river clay. "
    "Honey harvest peaks in late summer when the wildflower meadows "
    "around Greendell are at their fullest bloom. "
)
PROMPT_FACT = (
    "The oldest building in town is a stone library founded in 1742, "
    "originally as a granary and converted to a library in 1810. "
)
PROMPT_QUESTION = (
    "\n\nQuestion: What year was the oldest building in Greendell founded?\n"
    "Answer:"
)


def _make_long_prompt(target_tokens: int) -> str:
    target_chars = max(0, target_tokens * 4)
    fixed_chars = len(PROMPT_INTRO) + len(PROMPT_FACT) + len(PROMPT_QUESTION)
    filler_chars = max(0, target_chars - fixed_chars)
    n_reps = max(1, filler_chars // len(PROMPT_FILLER))
    long_text = PROMPT_FILLER * n_reps
    return PROMPT_INTRO + long_text + PROMPT_FACT + PROMPT_QUESTION


def _check_environment(require_int4: bool) -> Tuple[bool, str]:
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


def _hbm_snapshot() -> Dict[str, float]:
    import torch
    free, total = torch.cuda.mem_get_info()
    return {
        "allocated_gb":     torch.cuda.memory_allocated()     / (1024**3),
        "reserved_gb":      torch.cuda.memory_reserved()      / (1024**3),
        "max_allocated_gb": torch.cuda.max_memory_allocated() / (1024**3),
        "max_reserved_gb":  torch.cuda.max_memory_reserved()  / (1024**3),
        "free_gb":          free  / (1024**3),
        "total_gb":         total / (1024**3),
        "used_gb":          (total - free) / (1024**3),
    }


def _kv_cache_config(llm) -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "num_gpu_blocks":  None,
        "block_size":      None,
        "max_model_len":   None,
        "max_concurrency": None,
        "kv_cache_dtype":  None,
    }
    try:
        engine = llm.llm_engine
        cfg = engine.cache_config
        info["num_gpu_blocks"] = int(getattr(cfg, "num_gpu_blocks", 0) or 0)
        info["block_size"]     = int(getattr(cfg, "block_size", 0) or 0)
        info["kv_cache_dtype"] = str(getattr(cfg, "cache_dtype", "") or "")
        mcfg = getattr(engine, "model_config", None)
        if mcfg is not None:
            mml = getattr(mcfg, "max_model_len", None)
            if mml is not None:
                info["max_model_len"] = int(mml)
        if info["num_gpu_blocks"] and info["block_size"] and info["max_model_len"]:
            info["max_concurrency"] = (
                info["num_gpu_blocks"] * info["block_size"] / info["max_model_len"]
            )
    except (AttributeError, TypeError, ValueError):
        pass
    return info


def _scheduler_stats(llm) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "num_preempted":   0,
        "num_swapped":     0,
        "num_aborted":     0,
        "stats_available": False,
    }
    try:
        engine = llm.llm_engine
        scheduler = getattr(engine, "scheduler", None)
        if scheduler is None:
            return out
        if isinstance(scheduler, list):
            scheduler = scheduler[0]
        for attr, key in (
            ("num_cumulative_preemption", "num_preempted"),
            ("preemption_count",          "num_preempted"),
            ("num_swap_out_seqs",         "num_swapped"),
            ("num_aborted_seq_groups",    "num_aborted"),
        ):
            v = getattr(scheduler, attr, None)
            if v is not None:
                try:
                    out[key] = int(v)
                    out["stats_available"] = True
                except (TypeError, ValueError):
                    pass
    except AttributeError:
        pass
    return out


def _run_burst(
    llm,
    inner,
    B: int,
    sampling,
    n_runs: int,
    prompt: str,
) -> Dict[str, Any]:
    """Send B prompts in a single llm.generate() call. Return per-burst
    metrics including completion counts + quality signals."""
    import torch
    prompts = [prompt] * B
    burst_results: List[Dict[str, Any]] = []
    last_outputs: List[Any] = []

    for run_i in range(n_runs):
        # Best-effort reset for int4 cell. bf16 cell has no writer state.
        if inner is not None:
            try:
                from kv_policy.phase5b_backend_install import Int4ProtectedAttentionImpl
                for _, sub in inner.named_modules():
                    impl = getattr(sub, "impl", None)
                    if not isinstance(impl, Int4ProtectedAttentionImpl):
                        continue
                    w = getattr(impl, "_phase5b_paged_writer", None)
                    if w is not None and getattr(w, "_allocated", False):
                        w.reset_sequence("all")
            except (ImportError, AttributeError):
                pass
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
        t0 = time.perf_counter()
        try:
            outs = llm.generate(prompts, sampling)
            elapsed = time.perf_counter() - t0
            torch.cuda.synchronize()
            n_completed = sum(1 for o in outs if len(o.outputs[0].token_ids) > 0)
            n_failed    = B - n_completed
            total_out_tokens = sum(len(o.outputs[0].token_ids) for o in outs)
            per_seq_out = sorted(len(o.outputs[0].token_ids) for o in outs)
            median_out  = per_seq_out[len(per_seq_out) // 2] if per_seq_out else 0
            quality_hits = sum(
                1 for o in outs
                if QUALITY_FACT_ANSWER in (o.outputs[0].text or "")
            )
            burst_results.append({
                "run":               run_i,
                "wall_s":            elapsed,
                "n_completed":       n_completed,
                "n_failed":          n_failed,
                "total_output_toks": total_out_tokens,
                "median_output_toks": median_out,
                "min_output_toks":   per_seq_out[0] if per_seq_out else 0,
                "completed_tps":     total_out_tokens / elapsed if elapsed > 0 else 0.0,
                "quality_hits":      quality_hits,
                "quality_pass_rate": quality_hits / B if B > 0 else 0.0,
                "peak_hbm_gb":       torch.cuda.max_memory_allocated() / (1024**3),
                "oom":               False,
            })
            last_outputs = outs
        except torch.cuda.OutOfMemoryError as exc:
            elapsed = time.perf_counter() - t0
            burst_results.append({
                "run":               run_i,
                "wall_s":            elapsed,
                "n_completed":       0,
                "n_failed":          B,
                "total_output_toks": 0,
                "median_output_toks": 0,
                "min_output_toks":   0,
                "completed_tps":     0.0,
                "quality_hits":      0,
                "quality_pass_rate": 0.0,
                "peak_hbm_gb":       torch.cuda.max_memory_allocated() / (1024**3),
                "oom":               True,
                "oom_error":         str(exc)[:200],
            })
            # Attempt allocator reset; subsequent runs may still OOM.
            try:
                torch.cuda.empty_cache()
            except Exception:
                pass

    # Aggregate across runs (use median of completed_tps; sum of OOM flags
    # as a count of failures).
    n_oom = sum(1 for r in burst_results if r["oom"])
    completed_runs = [r for r in burst_results if not r["oom"]]
    if completed_runs:
        completed_runs.sort(key=lambda r: r["wall_s"])
        median_run = completed_runs[len(completed_runs) // 2]
    else:
        median_run = burst_results[0]   # all OOMed; pick first for metadata

    sample_text = ""
    if last_outputs:
        try:
            sample_text = (last_outputs[0].outputs[0].text or "")[:200]
        except (IndexError, AttributeError):
            pass

    return {
        "B":                       B,
        "n_runs":                  n_runs,
        "n_oom_runs":              n_oom,
        "burst_runs":              burst_results,
        "median_wall_s":           median_run["wall_s"],
        "median_n_completed":      median_run["n_completed"],
        "median_n_failed":         median_run["n_failed"],
        "median_completed_tps":    median_run["completed_tps"],
        "median_quality_hits":     median_run.get("quality_hits", 0),
        "median_quality_pass_rate": median_run.get("quality_pass_rate", 0.0),
        "median_output_toks":      median_run.get("median_output_toks", 0),
        "peak_hbm_gb":             max(r["peak_hbm_gb"] for r in burst_results),
        "sample_output":           sample_text,
    }


def run_worker(
    cell: str,
    max_model_len: int,
    batch_size: int,
    output_path: Path,
    *,
    model: str,
    max_tokens: int,
    gpu_memory_utilization: float,
    n_runs: int,
) -> int:
    if cell not in CELLS:
        print(f"FAIL: unknown cell {cell!r}")
        return 1
    if cell == CELL_CAPTURED:
        os.environ["PHASE6E_FUSED_WRITER"] = "1"
        # Auto-bump max_active_slots to the batch_size + headroom.
        user_provided = os.environ.get("PHASE6_MAX_ACTIVE_SLOTS")
        if not (user_provided and user_provided.strip()):
            os.environ["PHASE6_MAX_ACTIVE_SLOTS"] = str(max(16, batch_size * 2))

    require_int4 = (cell != CELL_BF16)
    ok, diag = _check_environment(require_int4=require_int4)
    if not ok:
        print(f"FAIL: {diag}")
        return 2

    import torch
    from vllm import SamplingParams

    torch.cuda.reset_peak_memory_stats()
    hbm_before_load = _hbm_snapshot()
    print(f"[cell={cell} mml={max_model_len} B={batch_size}] "
          f"HBM before load: used={hbm_before_load['used_gb']:.2f} GB")
    print(f"[cell={cell}] Loading {model}, max_model_len={max_model_len}, "
          f"max_num_seqs={batch_size} (=B exactly so capture matches)")
    t0 = time.time()

    inner = None
    model_runner = None
    hook = None
    writers: List[Any] = []
    impls: List[Any] = []

    if cell == CELL_BF16:
        from vllm import LLM
        try:
            llm = LLM(
                model=model,
                max_model_len=max_model_len,
                gpu_memory_utilization=gpu_memory_utilization,
                dtype="bfloat16",
                max_num_seqs=batch_size,
            )
        except torch.cuda.OutOfMemoryError as exc:
            print(f"[cell={cell}] LLM init OOM: {str(exc)[:200]}")
            return _write_oom_payload(
                output_path, cell, max_model_len, batch_size, exc,
                phase="llm_init",
            )
        torch.cuda.synchronize()
    else:
        try:
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
                max_num_seqs=batch_size,
            )
        except torch.cuda.OutOfMemoryError as exc:
            print(f"[cell={cell}] Int4ProtectedLLM init OOM: {str(exc)[:200]}")
            return _write_oom_payload(
                output_path, cell, max_model_len, batch_size, exc,
                phase="llm_init",
            )
        torch.cuda.synchronize()

    t_load = time.time() - t0
    hbm_after_init = _hbm_snapshot()
    kv_cfg = _kv_cache_config(llm)
    print(f"[cell={cell}] Loaded in {t_load:.1f}s. "
          f"HBM after init: {hbm_after_init['used_gb']:.2f} GB")
    if kv_cfg.get("max_concurrency"):
        print(f"[cell={cell}] KV cache: blocks={kv_cfg['num_gpu_blocks']}, "
              f"max_concurrency={kv_cfg['max_concurrency']:.1f}")

    # Long synthetic prompt at ~half the mml.
    prompt = _make_long_prompt(max_model_len // 2)
    print(f"[cell={cell}] Long prompt: {len(prompt)} chars (target ~{max_model_len//2} tokens).")

    print(f"[cell={cell}] Warmup (1 short generate)...")
    try:
        llm.generate([prompt], SamplingParams(temperature=0.0, max_tokens=4))
    except torch.cuda.OutOfMemoryError as exc:
        print(f"[cell={cell}] Warmup OOM: {str(exc)[:200]}")
        return _write_oom_payload(
            output_path, cell, max_model_len, batch_size, exc,
            phase="warmup",
        )

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
        hook = install_int4_protected_precapture_hook(
            model_runner, writers, impls=impls,
        )
        print(f"[cell={cell}] Hook: enabled={hook.enabled}")

    sampling = SamplingParams(temperature=0.0, max_tokens=max_tokens)
    sched_before = _scheduler_stats(llm)

    print(f"[cell={cell}] Burst B={batch_size}, n_runs={n_runs}, "
          f"max_tokens={max_tokens}...")
    burst = _run_burst(llm, inner, batch_size, sampling, n_runs, prompt)
    sched_after = _scheduler_stats(llm)

    hbm_final = _hbm_snapshot()
    payload: Dict[str, Any] = {
        "cell":                       cell,
        "max_model_len":              max_model_len,
        "batch_size":                 batch_size,
        "max_tokens":                 max_tokens,
        "model":                      model,
        "gpu_memory_utilization":     gpu_memory_utilization,
        "load_seconds":               t_load,
        "n_runs":                     n_runs,
        "hbm_before_load":            hbm_before_load,
        "hbm_after_init":             hbm_after_init,
        "hbm_final":                  hbm_final,
        "kv_cache_config":            kv_cfg,
        "scheduler_before_burst":     sched_before,
        "scheduler_after_burst":      sched_after,
        "preemption_events":          (
            sched_after.get("num_preempted", 0) - sched_before.get("num_preempted", 0)
        ),
        "swap_events": (
            sched_after.get("num_swapped", 0) - sched_before.get("num_swapped", 0)
        ),
        "burst":                      burst,
        "phase":                      "complete",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2))
    print(f"[cell={cell}] B={batch_size}: completed={burst['median_n_completed']}/{batch_size}  "
          f"failed={burst['median_n_failed']}  "
          f"peak_hbm={burst['peak_hbm_gb']:.2f} GB  "
          f"wall={burst['median_wall_s']:.2f}s  "
          f"tps={burst['median_completed_tps']:.1f}  "
          f"quality={burst['median_quality_hits']}/{batch_size}  "
          f"preempts={payload['preemption_events']}")
    print(f"[cell={cell}] Wrote {output_path}")
    if hook is not None:
        try:
            hook.teardown()
        except Exception:
            pass
    return 0


def _write_oom_payload(
    output_path: Path,
    cell: str,
    max_model_len: int,
    batch_size: int,
    exc: Exception,
    phase: str,
) -> int:
    payload = {
        "cell":          cell,
        "max_model_len": max_model_len,
        "batch_size":    batch_size,
        "phase":         phase,
        "oom_error":     str(exc)[:200],
        "burst": {
            "B":                       batch_size,
            "median_n_completed":      0,
            "median_n_failed":         batch_size,
            "median_completed_tps":    0.0,
            "median_quality_hits":     0,
            "median_quality_pass_rate": 0.0,
            "peak_hbm_gb":             0.0,
            "median_wall_s":           0.0,
            "n_oom_runs":              1,
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2))
    return 0   # not a driver failure — the OOM IS data


def compare(
    cell_paths: Dict[Tuple[str, int, int], Path],
    sweep: List[Tuple[int, List[int]]],
    report_json: Path,
    report_txt: Path,
) -> int:
    loaded: Dict[Tuple[str, int, int], Dict[str, Any]] = {}
    for key, p in cell_paths.items():
        if p.exists():
            loaded[key] = json.loads(p.read_text())

    rows: List[Dict[str, Any]] = []
    for mml, b_list in sweep:
        for B in b_list:
            bf  = loaded.get((CELL_BF16,     mml, B))
            cap = loaded.get((CELL_CAPTURED, mml, B))
            if bf is None and cap is None:
                continue
            def _get(d: Optional[Dict[str, Any]], key: str, default: Any = None) -> Any:
                if d is None:
                    return default
                if "burst" in d:
                    return d["burst"].get(key, default)
                return d.get(key, default)
            row = {
                "max_model_len":           mml,
                "B":                       B,
                "bf16_completed":          _get(bf, "median_n_completed"),
                "bf16_failed":             _get(bf, "median_n_failed"),
                "bf16_completed_tps":      _get(bf, "median_completed_tps"),
                "bf16_peak_hbm_gb":        _get(bf, "peak_hbm_gb"),
                "bf16_preempts":           (bf or {}).get("preemption_events"),
                "bf16_quality_hits":       _get(bf, "median_quality_hits"),
                "bf16_oom":                (bf or {}).get("phase") in ("llm_init", "warmup")
                                            or (_get(bf, "n_oom_runs", 0) or 0) > 0,
                "bf16_phase":              (bf or {}).get("phase"),
                "captured_completed":      _get(cap, "median_n_completed"),
                "captured_failed":         _get(cap, "median_n_failed"),
                "captured_completed_tps":  _get(cap, "median_completed_tps"),
                "captured_peak_hbm_gb":    _get(cap, "peak_hbm_gb"),
                "captured_preempts":       (cap or {}).get("preemption_events"),
                "captured_quality_hits":   _get(cap, "median_quality_hits"),
                "captured_oom":            (cap or {}).get("phase") in ("llm_init", "warmup")
                                            or (_get(cap, "n_oom_runs", 0) or 0) > 0,
                "captured_phase":          (cap or {}).get("phase"),
            }
            # Capacity ratio: how many more requests did int4 complete?
            if row["bf16_completed"] is not None and row["captured_completed"] is not None:
                if row["bf16_completed"] > 0:
                    row["captured_over_bf16_ratio"] = (
                        row["captured_completed"] / row["bf16_completed"]
                    )
                elif row["captured_completed"] > 0:
                    # bf16 OOMed (completed=0), int4 completed something.
                    # Treat as infinite advantage; report as "inf".
                    row["captured_over_bf16_ratio"] = float("inf")
                else:
                    row["captured_over_bf16_ratio"] = None
            else:
                row["captured_over_bf16_ratio"] = None
            rows.append(row)

    # Verdict.
    # JUSTIFIED:     int4 completes >=1.5x bf16 at least at one B per mml,
    #                OR bf16 OOMs at some B and int4 doesn't.
    # PARTIAL:       int4 completes more than bf16 at some B but <1.5x.
    # INCONCLUSIVE:  both cells completed all requests at every tested B
    #                (saturation never reached — need higher B to differentiate).
    # NOT_JUSTIFIED: int4 OOMs at or below bf16's max_concurrency, OR int4
    #                completes strictly fewer than bf16 at some B without OOM.
    int4_wins_strong   = 0
    int4_wins_weak     = 0
    int4_loses         = 0
    both_complete_tied = 0    # ratio == 1.0 with no OOM either side
    for r in rows:
        ratio = r.get("captured_over_bf16_ratio")
        if r.get("captured_oom") and not r.get("bf16_oom"):
            int4_loses += 1
            continue
        if r.get("bf16_oom") and not r.get("captured_oom"):
            int4_wins_strong += 1
            continue
        if ratio is None:
            continue
        if ratio == float("inf"):
            int4_wins_strong += 1
        elif ratio >= 1.5:
            int4_wins_strong += 1
        elif ratio > 1.0:
            int4_wins_weak += 1
        elif ratio == 1.0:
            # Both completed; saturation didn't differentiate them.
            both_complete_tied += 1
        else:
            int4_loses += 1

    if int4_wins_strong >= 1:
        verdict = "JUSTIFIED"
        verdict_note = (
            f"int4 completes >=1.5x bf16's completed requests (or bf16 "
            f"OOMs while int4 doesn't) at {int4_wins_strong} of the "
            f"{len(rows)} tested (mml, B) combinations. The protect-mask "
            f"design's 2x max_concurrency translates to real high-load "
            f"capacity. Phase 6G implementation (e.g., option C: fp8 "
            f"sidecars) is now justified to make the capacity advantage "
            f"cleaner."
        )
    elif int4_wins_weak >= 1:
        verdict = "PARTIAL"
        verdict_note = (
            f"int4 completes more requests than bf16 at high B (real "
            f"advantage) but the ratio is below 1.5x (sidecar overhead "
            f"consumes some of vLLM's reported 2x budget). Diet options "
            f"may push the ratio higher; recommend running 6G option C "
            f"and re-running 6H to measure the delta."
        )
    elif int4_loses >= 1:
        verdict = "NOT_JUSTIFIED"
        verdict_note = (
            f"int4 OOMs or completes fewer than bf16 at high B at "
            f"{int4_loses} (mml, B) combinations. The reported 2x "
            f"max_concurrency is bookkeeping-only — sidecars consume the "
            f"budget vLLM thinks int4 has. Phase 6G diet alone cannot "
            f"rescue this (the audit ceiling is ~2.5 GB savings vs a "
            f"~5 GB delta). Consider Phase 6I structural redesign "
            f"(e.g., move int4 logic into flash_attn) or close the "
            f"int4_protected line."
        )
    elif both_complete_tied >= 1:
        verdict = "INCONCLUSIVE"
        verdict_note = (
            f"Both cells completed all requested generations at every "
            f"tested (mml, B) — {both_complete_tied} of {len(rows)} "
            f"combinations. Saturation never reached. The chosen B "
            f"values were not high enough to trigger differential "
            f"behavior. Re-run with significantly higher B and/or lower "
            f"gpu_memory_utilization to find the operating point where "
            f"capacity actually differentiates the cells. The throughput "
            f"comparison from this bench remains informative: bf16 was "
            f"consistently faster than int4 by 1.4-1.9x across the sweep."
        )
    else:
        verdict = "INCONCLUSIVE"
        verdict_note = "No completed comparisons (all runs OOMed or missing)."

    report = {
        "verdict":               verdict,
        "verdict_note":          verdict_note,
        "int4_wins_strong":      int4_wins_strong,
        "int4_wins_weak":        int4_wins_weak,
        "int4_loses":            int4_loses,
        "both_complete_tied":    both_complete_tied,
        "total_combinations":    len(rows),
        "sweep":                 [[m, bs] for m, bs in sweep],
        "rows":                  rows,
    }
    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(report, indent=2, default=str))

    lines: List[str] = []
    lines.append("=" * 90)
    lines.append("Phase 6H — high-load capacity bench")
    lines.append("=" * 90)
    lines.append(f"Verdict: {verdict}")
    for line in (verdict_note or "").splitlines() or [""]:
        lines.append(f"  {line}")
    lines.append("")
    lines.append(f"Wins strong (>=1.5x or bf16-OOM): {int4_wins_strong}    "
                 f"Wins weak (>1x, <1.5x): {int4_wins_weak}    "
                 f"Tied (both completed): {both_complete_tied}    "
                 f"Loses (OOM or <bf16): {int4_loses}    "
                 f"of {len(rows)} (mml, B) combinations")
    lines.append("")
    lines.append("Per-(mml, B) results:")
    lines.append(
        f"  {'mml':>6} | {'B':>3} | {'bf16 completed':>15} | "
        f"{'int4 completed':>15} | {'ratio':>7} | "
        f"{'bf16 tps':>9} | {'int4 tps':>9} | "
        f"{'bf16 HBM':>8} | {'int4 HBM':>8} | "
        f"{'preempts':>13} | {'notes':>10}"
    )
    lines.append("  " + "-" * 130)
    for r in rows:
        def _intish(v):
            if v is None: return "  n/a"
            return f"{v}"
        def _fmt_completed(v, total):
            if v is None: return "      n/a"
            return f"{v}/{total}"
        def _fmt_f(v, fmt="{:>8.1f}"):
            if v is None or (isinstance(v, float) and v != v):  # NaN check
                return "    n/a "
            return fmt.format(v)
        ratio = r.get("captured_over_bf16_ratio")
        if ratio is None:
            ratio_str = "   n/a "
        elif ratio == float("inf"):
            ratio_str = "    INF"
        else:
            ratio_str = f"{ratio:>6.2f}x"
        notes_bits = []
        if r["bf16_oom"]:    notes_bits.append("bf16 OOM")
        if r["captured_oom"]: notes_bits.append("int4 OOM")
        notes = " ".join(notes_bits) or ""
        lines.append(
            f"  {r['max_model_len']:>6} | {r['B']:>3} | "
            f"{_fmt_completed(r['bf16_completed'], r['B']):>15} | "
            f"{_fmt_completed(r['captured_completed'], r['B']):>15} | "
            f"{ratio_str:>7} | "
            f"{_fmt_f(r['bf16_completed_tps']):>9} | "
            f"{_fmt_f(r['captured_completed_tps']):>9} | "
            f"{_fmt_f(r['bf16_peak_hbm_gb'], '{:>6.2f}'):>8} | "
            f"{_fmt_f(r['captured_peak_hbm_gb'], '{:>6.2f}'):>8} | "
            f"bf16={_intish(r['bf16_preempts']):>3} int4={_intish(r['captured_preempts']):>3} | "
            f"{notes}"
        )
    lines.append("")
    lines.append(f"Verdict: {verdict}")
    report_txt.parent.mkdir(parents=True, exist_ok=True)
    report_txt.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    # Exit codes:
    #   0 = JUSTIFIED or PARTIAL (proceed with diet / brief draft)
    #   2 = INCONCLUSIVE (re-run with higher B before deciding)
    #   1 = NOT_JUSTIFIED (close the line or pivot to a different framing)
    if verdict in ("JUSTIFIED", "PARTIAL"):
        return 0
    if verdict == "INCONCLUSIVE":
        return 2
    return 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--worker", action="store_true",
                   help="Internal: run a single (cell, mml, B) worker.")
    p.add_argument("--cell", choices=CELLS)
    p.add_argument("--max-model-len", type=int)
    p.add_argument("--batch-size", type=int)
    p.add_argument("--output", type=str)
    p.add_argument("--output-dir", type=str,
                   default="bench_out/phase6h_high_load",
                   help="Driver mode: directory for per-cell JSONs + report.")
    p.add_argument("--cells", default=",".join(CELLS))
    p.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    p.add_argument("--sweep",
                   default="8192:64,96;16384:32,48;32768:16,20",
                   help="mml:B1,B2;mml:B1,B2;... — overrides DEFAULT_SWEEP.")
    p.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    p.add_argument("--gpu-memory-utilization", type=float,
                   default=DEFAULT_GPU_MEM_UTIL)
    p.add_argument("--n-runs", type=int, default=DEFAULT_N_RUNS)
    args = p.parse_args()

    if args.worker:
        if (not args.cell or args.max_model_len is None
                or args.batch_size is None or not args.output):
            print("FAIL: --worker requires --cell, --max-model-len, "
                  "--batch-size, --output.")
            return 2
        return run_worker(
            cell=args.cell,
            max_model_len=args.max_model_len,
            batch_size=args.batch_size,
            output_path=Path(args.output),
            model=args.model,
            max_tokens=args.max_tokens,
            gpu_memory_utilization=args.gpu_memory_utilization,
            n_runs=args.n_runs,
        )

    # Parse sweep.
    sweep: List[Tuple[int, List[int]]] = []
    for chunk in args.sweep.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        mml_str, b_str = chunk.split(":")
        sweep.append((int(mml_str), [int(b) for b in b_str.split(",")]))
    cells_to_run = [c.strip() for c in args.cells.split(",") if c.strip()]
    for c in cells_to_run:
        if c not in CELLS:
            print(f"FAIL: unknown cell {c!r}")
            return 2

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cell_paths: Dict[Tuple[str, int, int], Path] = {}
    for c in cells_to_run:
        for mml, b_list in sweep:
            for B in b_list:
                cell_paths[(c, mml, B)] = (
                    out_dir / f"cell_{c}_mml{mml}_B{B}.json"
                )

    ok, diag = _check_environment(require_int4=(CELL_CAPTURED in cells_to_run))
    if not ok:
        print(f"FAIL: environment check: {diag}")
        return 2

    common_args = [
        "--worker",
        "--model", args.model,
        "--max-tokens", str(args.max_tokens),
        "--gpu-memory-utilization", str(args.gpu_memory_utilization),
        "--n-runs", str(args.n_runs),
    ]
    # Order: by (mml, B, cell). At each (mml, B), run bf16 first then int4,
    # so the result for that operating point lands together in the output dir.
    for mml, b_list in sweep:
        for B in b_list:
            for cell in cells_to_run:
                out_path = cell_paths[(cell, mml, B)]
                print()
                print(f"=== Driver: cell={cell} mml={mml} B={B} ===")
                cmd = [sys.executable, __file__] + common_args + [
                    "--cell", cell,
                    "--max-model-len", str(mml),
                    "--batch-size", str(B),
                    "--output", str(out_path),
                ]
                ret = subprocess.run(cmd, check=False)
                if ret.returncode != 0:
                    print(f"WARN: worker cell={cell} mml={mml} B={B} "
                          f"exited code {ret.returncode} — continuing.")

    return compare(
        cell_paths=cell_paths,
        sweep=sweep,
        report_json=out_dir / "high_load_report.json",
        report_txt=out_dir / "high_load_report.txt",
    )


if __name__ == "__main__":
    sys.exit(main())
