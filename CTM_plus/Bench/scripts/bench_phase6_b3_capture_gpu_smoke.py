"""Phase 6B.3 — GPU smoke for enforce_eager=False capture-enable.

Confirms vLLM 0.7.3 V0's CUDA Graphs capture works end-to-end with
the int4_protected backend + 6B.1 write-path preflight + 6B.2 pre-
capture hook, producing byte-identical generated tokens vs eager
mode on real Qwen-2.5-7B-Instruct + A100 + forked vllm-flash-attn.

Mirrors bench_phase6_b2_hook_gpu_smoke.py's self-spawning subprocess
pattern. Two cells:

  cell eager    : PHASE6B3_FORCE_EAGER=1; int4_protected runs eagerly
                  (matches the 6B.1 + 6B.2 smoke baseline). Reference.
  cell captured : PHASE6B3_FORCE_EAGER unset; Int4ProtectedLLM default
                  enforce_eager=False; vLLM captures decode forwards at
                  its internal default ~35-batch-size curve.

Each cell:
  * Loads Qwen-7B; records HBM stats pre/post init + per generate.
  * Warms up; resets call_stats + hook stats.
  * Runs B in {1, 2, 4, 8} sweeps with the same workload. Per B:
      run1: generates max_tokens=32 greedy
      run2: re-generates with the SAME prompts + sampling
      → asserts run1.token_ids == run2.token_ids (multi-batch determinism)
  * Dumps per-B per-run tokens + call_stats + hook stats + HBM stats.

Driver then compares the two cells: eager vs captured byte-equality
+ multi-batch determinism + zero fallbacks + HBM growth report.

Usage on the GPU pod:

  /workspace/venv-vllm/bin/python3 \\
      /workspace/symbolu/CTM_plus/Bench/scripts/bench_phase6_b3_capture_gpu_smoke.py \\
      --output-dir /workspace/symbolu/bench_out/phase6b3_gpu_smoke

  # Manual cell-at-a-time:
  python3 bench_phase6_b3_capture_gpu_smoke.py --worker --cell eager     --output cell_eager.json
  python3 bench_phase6_b3_capture_gpu_smoke.py --worker --cell captured  --output cell_captured.json
  python3 bench_phase6_b3_capture_gpu_smoke.py --compare cell_eager.json cell_captured.json

Acceptance gate (Phase 6B.3 G_CAPTURE):
  1. Capture succeeded (engine init didn't crash; load_seconds finite).
  2. Eager vs captured tokens byte-equal across all B in {1,2,4,8}.
  3. Multi-batch determinism: run1 == run2 byte-equal per cell per B.
  4. Both cells: write_path_fallback == 0, decode_calls_fallback == 0.
  5. HBM growth in captured cell reported (informational; budget 5 GB).
  6. Captured cell: stash_call_count > 0 (6B.2 hook still firing).

Exit codes:
  0 — GREEN; G_CAPTURE passes
  1 — RED; at least one check failed
  2 — environment error
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


PROMPTS = [
    (
        "Below is a paragraph about a small fictional town. After it, "
        "answer the question concisely.\n\n"
        "Greendell is nestled between two rivers and has a population "
        "of just over four thousand. Its main industries are pottery, "
        "honey production, and the seasonal wool trade. The annual "
        "harvest festival in early autumn draws visitors from across "
        "the region. The oldest building in town is a stone library "
        "founded in 1742.\n\n"
        "Question: What year was the oldest building in Greendell "
        "founded?\nAnswer:"
    ),
    (
        "Translate to French and explain briefly:\n"
        "English: The quick brown fox jumps over the lazy dog.\n"
        "French:"
    ),
]


CELL_EAGER    = "eager"
CELL_CAPTURED = "captured"

# Batch sizes for the sweep. Each B repeats PROMPTS to fill the batch.
BATCH_SIZES = [1, 2, 4, 8]


def _check_environment() -> tuple[bool, str]:
    try:
        import torch
    except ImportError as e:
        return False, f"torch import failed: {e}"
    if not torch.cuda.is_available():
        return False, "torch.cuda.is_available() == False; need GPU pod"
    try:
        from vllm import SamplingParams  # noqa: F401
    except ImportError as e:
        return False, f"vllm import failed: {e}"
    try:
        from kv_policy.int4_protected import Int4ProtectedLLM  # noqa: F401
        from kv_policy.phase6b2_precapture_hook import (  # noqa: F401
            install_int4_protected_precapture_hook,
        )
    except ImportError as e:
        return False, f"kv_policy import failed: {e}"
    return True, "ok"


def _find_inner_model(llm):
    candidates = [
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model,
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model_runner.model,
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
    ]
    for fn in candidates:
        try:
            mr = fn(llm)
            if mr is not None and hasattr(mr, "execute_model"):
                return mr
        except (AttributeError, IndexError):
            continue
    return None


def _reset_all_writers(inner_model) -> int:
    """Reset every Int4ProtectedAttentionImpl's writer back to fresh
    (slot pool fully free; SeqState dict cleared; counter pools at
    sentinel). Returns the number of writers reset.

    Required between generate() calls in the multi-run sweep because
    the writer's _slot_map accumulates seq_ids across requests — vLLM
    doesn't auto-emit a sequence-finish callback that would let the
    writer evict completed seqs. Without this reset, the slot pool
    fills up at moderate cumulative seq counts AND new requests get
    contaminated slots when their first block_id collides with a
    recycled block from a prior request.

    See PHASE_6B3_CAPTURE_FINDINGS.md (when landed) for the deferred-
    investigation item: production auto-eviction hook.
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


def _dump_writer_state(inner_model, impls, cell: str, B: int, tag: str) -> None:
    """Print writer + impl state for root-cause debugging of B>=2 divergence."""
    import torch
    from kv_policy.phase5b_backend_install import Int4ProtectedAttentionImpl

    # Only inspect writer 0 (same slot-map across all layers).
    first_impl = impls[0] if impls else None
    first_writer = None
    for _, sub in inner_model.named_modules():
        impl = getattr(sub, "impl", None)
        if isinstance(impl, Int4ProtectedAttentionImpl):
            w = getattr(impl, "_phase5b_paged_writer", None)
            if w is not None and getattr(w, "_allocated", False):
                first_writer = w
                first_impl = impl
                break

    print(f"\n[DEBUG cell={cell} B={B} {tag}]")
    if first_writer is None:
        print("  no allocated writer found")
        return

    slot_map = dict(first_writer._slot_map)
    free_slots = list(first_writer._free_slots)
    print(f"  slot_map={slot_map}  free_slots={free_slots}")

    if first_writer._seq_pos_pool is not None:
        n_slots = first_writer._max_active_slots
        pos = first_writer._seq_pos_pool[:n_slots].cpu().tolist()
        sentinel = first_writer._k_stage_block_id_pool[:n_slots].cpu().tolist()
        print(f"  seq_pos_pool[:n_slots]={pos}")
        print(f"  k_stage_block_id_pool[:n_slots]={sentinel}")
        # Check bf16 backing norms for ALL active slots.
        for seq_id, slot in sorted(slot_map.items()):
            pool = first_writer._bf16_k_backing_pool
            if pool is not None:
                seq_pos = int(first_writer._seq_pos_pool[slot].item())
                if seq_pos > 0:
                    norm = float(pool[slot, :seq_pos].norm().item())
                    # First token's key norm across heads (shape H, D -> scalar)
                    tok0_norm = float(pool[slot, 0].norm().item())
                else:
                    norm = 0.0
                    tok0_norm = 0.0
                print(f"  slot={slot} seq_id={seq_id} seq_pos={seq_pos} "
                      f"bf16k_norm={norm:.4f} tok0_norm={tok0_norm:.4f}")

    if first_impl is not None:
        buf = getattr(first_impl, "_phase5b_slot_idx_buf", None)
        if buf is not None:
            vals = buf[:min(B, buf.numel())].cpu().tolist()
            print(f"  impl0._phase5b_slot_idx_buf[:{B}]={vals}")


def _hbm_snapshot() -> dict:
    """Capture GB-level HBM stats. Used for capture-overhead reporting."""
    import torch
    free, total = torch.cuda.mem_get_info()
    return {
        "allocated_gb": torch.cuda.memory_allocated() / (1024**3),
        "reserved_gb":  torch.cuda.memory_reserved()  / (1024**3),
        "free_gb":      free  / (1024**3),
        "total_gb":     total / (1024**3),
        "used_gb":      (total - free) / (1024**3),
    }


def run_worker(cell: str, output_path: Path, *, model: str,
               max_model_len: int, max_tokens: int,
               gpu_memory_utilization: float) -> int:
    if cell not in (CELL_EAGER, CELL_CAPTURED):
        print(f"FAIL: unknown cell {cell!r}")
        return 1
    if cell == CELL_EAGER:
        os.environ["PHASE6B3_FORCE_EAGER"] = "1"
    else:
        os.environ.pop("PHASE6B3_FORCE_EAGER", None)

    ok, diag = _check_environment()
    if not ok:
        print(f"FAIL: {diag}")
        return 2

    import torch
    from vllm import SamplingParams
    import kv_policy.int4_protected
    from kv_policy.int4_protected import Int4ProtectedLLM
    from kv_policy.phase5b_backend_install import Int4ProtectedAttentionImpl
    from kv_policy.phase6b2_precapture_hook import (
        install_int4_protected_precapture_hook,
    )

    hbm_before = _hbm_snapshot()
    print(f"[cell={cell}] HBM before load: used={hbm_before['used_gb']:.2f} GB / "
          f"{hbm_before['total_gb']:.2f} GB total")

    print(f"[cell={cell}] Loading {model}...")
    t0 = time.time()
    llm = Int4ProtectedLLM(
        model=model,
        max_model_len=max_model_len,
        gpu_memory_utilization=gpu_memory_utilization,
        # Don't pass enforce_eager — let the factory's PHASE6B3_FORCE_
        # EAGER env override decide. eager cell sets env=1; captured
        # cell leaves env unset -> factory default False.
    )
    torch.cuda.synchronize()
    t_load = time.time() - t0
    hbm_after_init = _hbm_snapshot()
    print(f"[cell={cell}] Loaded in {t_load:.1f}s.")
    print(f"[cell={cell}] HBM after init:  used={hbm_after_init['used_gb']:.2f} GB"
          f"  (delta={hbm_after_init['used_gb']-hbm_before['used_gb']:.2f} GB)")

    # Warmup B=1 to construct writers.
    print(f"[cell={cell}] Warmup...")
    llm.generate(["Hello."], SamplingParams(temperature=0.0, max_tokens=4))
    hbm_after_warmup = _hbm_snapshot()

    # Install hook post-warmup (same as 6B.2 smoke).
    inner = _find_inner_model(llm)
    model_runner = _find_model_runner(llm)
    if inner is None or model_runner is None:
        print(f"FAIL: cannot locate inner model or model_runner")
        return 2
    writers = []
    impls   = []
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

    # Per-B sweep: 2 runs each, assert token-equality.
    # We reset writer state BEFORE EACH generate() call so each run
    # starts with a fresh slot pool. Without this, the writer's
    # _slot_map accumulates seq_ids across the sweep (vLLM doesn't
    # auto-emit a request-finish callback that would evict completed
    # seqs), and (a) the slot pool exhausts at moderate cumulative
    # B counts, (b) new requests get contaminated slots when their
    # first block_id collides with a recycled block from a prior
    # request. The pre-existing bug is a Phase 6B.x deferred-
    # investigation item (production-grade fix: auto-eviction hook).
    Int4ProtectedAttentionImpl.reset_call_stats()
    per_b_results = {}
    for B in BATCH_SIZES:
        prompts_b = (PROMPTS * ((B + len(PROMPTS) - 1) // len(PROMPTS)))[:B]
        sampling = SamplingParams(temperature=0.0, max_tokens=max_tokens)

        # Run 1
        n_reset_pre_run1 = _reset_all_writers(inner)
        Int4ProtectedAttentionImpl.reset_call_stats()
        hook_stash_pre_run1 = hook.stash_call_count
        t0 = time.time()
        outs1 = llm.generate(prompts_b, sampling)
        torch.cuda.synchronize()
        t_gen1 = time.time() - t0
        stats_run1 = Int4ProtectedAttentionImpl.get_call_stats()
        run1_tokens = [list(o.outputs[0].token_ids) for o in outs1]
        run1_texts  = [o.outputs[0].text for o in outs1]
        hook_stash_run1 = hook.stash_call_count - hook_stash_pre_run1
        for i, txt in enumerate(run1_texts):
            print(f"[cell={cell} B={B} run1 seq{i}] {repr(txt[:80])}")
        _dump_writer_state(inner, impls, cell, B, "after_run1")

        # Run 2 (same prompts, same sampling, FRESH writer slot pool)
        n_reset_pre_run2 = _reset_all_writers(inner)
        Int4ProtectedAttentionImpl.reset_call_stats()
        hook_stash_pre_run2 = hook.stash_call_count
        t0 = time.time()
        outs2 = llm.generate(prompts_b, sampling)
        torch.cuda.synchronize()
        t_gen2 = time.time() - t0
        stats_run2 = Int4ProtectedAttentionImpl.get_call_stats()
        run2_tokens = [list(o.outputs[0].token_ids) for o in outs2]
        run2_texts  = [o.outputs[0].text for o in outs2]
        hook_stash_run2 = hook.stash_call_count - hook_stash_pre_run2

        deterministic = (run1_tokens == run2_tokens)
        per_b_results[B] = {
            "B":                  B,
            "deterministic":      deterministic,
            "run1_tokens":        run1_tokens,
            "run1_texts":         run1_texts,
            "run1_seconds":       t_gen1,
            "run1_call_stats":    stats_run1,
            "run1_hook_stash":    hook_stash_run1,
            "run1_writers_reset": n_reset_pre_run1,
            "run2_tokens":        run2_tokens,
            "run2_texts":         run2_texts,
            "run2_seconds":       t_gen2,
            "run2_call_stats":    stats_run2,
            "run2_hook_stash":    hook_stash_run2,
            "run2_writers_reset": n_reset_pre_run2,
        }
        print(f"[cell={cell}] B={B}: run1={t_gen1:.2f}s run2={t_gen2:.2f}s "
              f"deterministic={deterministic} stash_run1={hook_stash_run1} "
              f"stash_run2={hook_stash_run2} writers_reset={n_reset_pre_run1}/{n_reset_pre_run2}")

    hbm_final = _hbm_snapshot()
    payload = {
        "cell":                       cell,
        "model":                      model,
        "max_model_len":              max_model_len,
        "gpu_memory_utilization":     gpu_memory_utilization,
        "max_tokens":                 max_tokens,
        "load_seconds":               t_load,
        "batch_sizes":                BATCH_SIZES,
        "n_prompts_per_batch":        len(PROMPTS),
        "hook_enabled":               hook.enabled,
        "hook_target_name":           hook.hook_target_name,
        "hook_total_stash_calls":     hook.stash_call_count,
        "hook_total_skipped_steps":   hook.skipped_step_count,
        "hbm_before_load":            hbm_before,
        "hbm_after_init":             hbm_after_init,
        "hbm_after_warmup":           hbm_after_warmup,
        "hbm_final":                  hbm_final,
        "capture_overhead_gb":        hbm_after_init["used_gb"] - hbm_before["used_gb"],
        "per_b":                      per_b_results,
        "phase6b3_force_eager_env":   os.environ.get("PHASE6B3_FORCE_EAGER"),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2))
    print(f"[cell={cell}] Wrote {output_path}")
    hook.teardown()
    return 0


def compare(eager_path: Path, captured_path: Path,
            report_json: Path, report_txt: Path) -> int:
    eager    = json.loads(eager_path.read_text())
    captured = json.loads(captured_path.read_text())

    checks = []
    # Per-B token byte-equality.
    for B in BATCH_SIZES:
        eb = eager["per_b"].get(str(B)) or eager["per_b"].get(B)
        cb = captured["per_b"].get(str(B)) or captured["per_b"].get(B)
        if eb is None or cb is None:
            checks.append((f"B{B}_per_b_present", False, "missing per_b entry"))
            continue
        eq = (eb["run1_tokens"] == cb["run1_tokens"])
        checks.append((
            f"B{B}_eager_vs_captured_tokens_byte_equal",
            eq,
            "byte-equal" if eq else f"diverged at first prompt",
        ))
        # Multi-batch determinism per cell.
        checks.append((
            f"B{B}_eager_deterministic_run1_eq_run2",
            eb["deterministic"],
            f"run1 ?= run2",
        ))
        checks.append((
            f"B{B}_captured_deterministic_run1_eq_run2",
            cb["deterministic"],
            f"run1 ?= run2",
        ))

    # Zero fallbacks across all batches in both cells.
    for cell_name, payload in (("eager", eager), ("captured", captured)):
        any_fallback = False
        for B in BATCH_SIZES:
            b = payload["per_b"].get(str(B)) or payload["per_b"].get(B)
            if b is None:
                continue
            for s in (b["run1_call_stats"], b["run2_call_stats"]):
                if s.get("write_path_fallback", 0) > 0:
                    any_fallback = True
                if s.get("decode_calls_fallback", 0) > 0:
                    any_fallback = True
        checks.append((
            f"{cell_name}_zero_fallbacks_across_sweep",
            not any_fallback,
            "zero" if not any_fallback else "saw fallback",
        ))

    # 6B.2 hook fired in captured cell (informational; should fire in eager
    # too since the hook is installed in both, but eager mode doesn't gate
    # on it).
    cap_stash = captured.get("hook_total_stash_calls", 0)
    checks.append((
        "captured_cell_hook_stash_positive",
        cap_stash > 0,
        f"stash_call_count={cap_stash}",
    ))

    # Capture overhead (informational; 5 GB target).
    overhead = captured.get("capture_overhead_gb", 0)
    overhead_within_budget = overhead <= 5.0
    checks.append((
        "captured_cell_hbm_overhead_within_5gb",
        True,  # informational only — never fails
        f"overhead={overhead:.2f} GB (target ≤ 5.0 GB; within={overhead_within_budget})",
    ))

    overall_ok = all(ok for _, ok, _ in checks)
    report = {
        "verdict":         "GREEN" if overall_ok else "RED",
        "eager_cell":      str(eager_path),
        "captured_cell":   str(captured_path),
        "model":           eager.get("model"),
        "batch_sizes":     BATCH_SIZES,
        "checks":          [{"name": n, "passed": ok, "detail": d} for n, ok, d in checks],
        "eager_load_seconds":    eager.get("load_seconds"),
        "captured_load_seconds": captured.get("load_seconds"),
        "capture_overhead_gb":   overhead,
        "eager_hook_stash":      eager.get("hook_total_stash_calls"),
        "captured_hook_stash":   captured.get("hook_total_stash_calls"),
        "per_b_diffs":           [],
    }
    for B in BATCH_SIZES:
        eb = eager["per_b"].get(str(B)) or eager["per_b"].get(B)
        cb = captured["per_b"].get(str(B)) or captured["per_b"].get(B)
        if eb is None or cb is None: continue
        report["per_b_diffs"].append({
            "B": B,
            "eager_run1_text":    eb["run1_texts"][0] if eb["run1_texts"] else "",
            "captured_run1_text": cb["run1_texts"][0] if cb["run1_texts"] else "",
            "tokens_byte_equal":  eb["run1_tokens"] == cb["run1_tokens"],
            "eager_deterministic":    eb["deterministic"],
            "captured_deterministic": cb["deterministic"],
            "eager_run1_seconds":     eb["run1_seconds"],
            "captured_run1_seconds":  cb["run1_seconds"],
        })

    report_json.parent.mkdir(parents=True, exist_ok=True)
    report_json.write_text(json.dumps(report, indent=2))

    lines = []
    lines.append("=" * 78)
    lines.append("Phase 6B.3 GPU smoke — eager vs captured comparison")
    lines.append("=" * 78)
    lines.append(f"Model: {report['model']}    Batch sizes: {BATCH_SIZES}")
    lines.append(f"Verdict: {report['verdict']}")
    lines.append("")
    lines.append(f"Load times:    eager={report['eager_load_seconds']:.1f}s    "
                 f"captured={report['captured_load_seconds']:.1f}s "
                 f"(capture phase = +{report['captured_load_seconds']-report['eager_load_seconds']:.1f}s)")
    lines.append(f"HBM overhead:  captured cell = {report['capture_overhead_gb']:.2f} GB")
    lines.append(f"Hook stash:    eager={report['eager_hook_stash']}    captured={report['captured_hook_stash']}")
    lines.append("")
    lines.append("Checks:")
    for c in report["checks"]:
        mark = "PASS" if c["passed"] else "FAIL"
        lines.append(f"  [{mark}] {c['name']:<52s} {c['detail']}")
    lines.append("")
    lines.append("Per-B sweep (run1 timing):")
    for d in report["per_b_diffs"]:
        lines.append(f"  B={d['B']:<2d} byte_eq={d['tokens_byte_equal']} "
                     f"e_det={d['eager_deterministic']} c_det={d['captured_deterministic']} "
                     f"e_t={d['eager_run1_seconds']:.2f}s c_t={d['captured_run1_seconds']:.2f}s")
        if not d["tokens_byte_equal"]:
            lines.append(f"    eager:    {d['eager_run1_text']!r}")
            lines.append(f"    captured: {d['captured_run1_text']!r}")
    lines.append("")
    if overall_ok:
        lines.append("Phase 6B.3 GPU smoke: GREEN")
        lines.append("  CUDA Graphs capture is operational. Captured-mode decode")
        lines.append("  produces byte-identical generated tokens to eager mode at")
        lines.append(f"  all B in {BATCH_SIZES}; multi-batch determinism preserved")
        lines.append("  in both cells; zero fallbacks; hook integration intact.")
    else:
        lines.append("Phase 6B.3 GPU smoke: RED")
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
    grp.add_argument("--compare", nargs=2, metavar=("EAGER", "CAPTURED"),
                     help="Compare two existing cell JSONs and emit a report.")
    p.add_argument("--cell", choices=[CELL_EAGER, CELL_CAPTURED],
                   help="Worker mode: which cell to run.")
    p.add_argument("--output", type=str,
                   help="Worker mode: JSON output path for this cell's results.")
    p.add_argument("--output-dir", type=str,
                   default="bench_out/phase6b3_gpu_smoke",
                   help="Driver mode: directory for both cells + report.")
    p.add_argument("--model",          default="Qwen/Qwen2.5-7B-Instruct")
    p.add_argument("--max-model-len",  type=int,   default=4096)
    p.add_argument("--max-tokens",     type=int,   default=32)
    p.add_argument("--gpu-memory-utilization", type=float, default=0.5)
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
        )

    if args.compare:
        return compare(
            eager_path=Path(args.compare[0]),
            captured_path=Path(args.compare[1]),
            report_json=Path(args.compare[0]).parent / "smoke_report.json",
            report_txt=Path(args.compare[0]).parent / "smoke_report.txt",
        )

    # Driver: spawn both cells as subprocesses.
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    eager_json    = out_dir / "cell_eager.json"
    captured_json = out_dir / "cell_captured.json"
    report_json   = out_dir / "smoke_report.json"
    report_txt    = out_dir / "smoke_report.txt"

    ok, diag = _check_environment()
    if not ok:
        print(f"FAIL: environment check: {diag}")
        return 2

    common_args = [
        "--worker",
        "--model", args.model,
        "--max-model-len", str(args.max_model_len),
        "--max-tokens", str(args.max_tokens),
        "--gpu-memory-utilization", str(args.gpu_memory_utilization),
    ]
    for cell, out_path in (
        (CELL_EAGER, eager_json),
        (CELL_CAPTURED, captured_json),
    ):
        print()
        print(f"=== Driver: spawning worker for cell={cell} ===")
        cmd = [sys.executable, __file__] + common_args + [
            "--cell", cell, "--output", str(out_path),
        ]
        ret = subprocess.run(cmd, check=False)
        if ret.returncode != 0:
            print(f"FAIL: worker cell={cell} exited with code {ret.returncode}")
            return ret.returncode

    return compare(eager_json, captured_json, report_json, report_txt)


if __name__ == "__main__":
    sys.exit(main())
