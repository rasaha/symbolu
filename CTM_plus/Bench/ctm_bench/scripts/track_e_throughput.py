"""Track E throughput — HF route-B decode tokens/sec for FP16 baseline
vs KIVI-style INT4 KV cache.

The peer measurement to ``run_streaming.py``'s vLLM tokens/sec
(§13.3's harness). Together they answer "is the FP8-KV throughput gap
small enough that the route-A vLLM integration alone closes it, or is
a Marlin-style fused unpack-attend kernel the actual blocker?" — see
``Bench/scripts/FP8_INT4_THROUGHPUT_RUNBOOK.md`` for the four-cell
composition and the comparison frame.

Why a separate script from ``track_e_quality_eval.py``:

* The quality eval measures prefill perplexity and short-prompt MMLU
  accuracy — these are correctness numbers, not throughput numbers.
* The streaming runner measures vLLM tokens/sec — but route-B INT4
  doesn't live on the vLLM path; it lives in HF's ``DynamicCache``.
  Measuring HF-side throughput requires its own timing harness.
* Keeping the two concerns in separate scripts also means the
  quality artefacts (``int4_mmlu_1000.json`` etc.) and the throughput
  artefacts (``int4_throughput_hf.json``) stay separately auditable.

CLI
---

  # Real GPU run (Qwen2.5-7B, FP16 baseline + INT4 KIVI):
  python -m ctm_bench.scripts.track_e_throughput \\
      --model Qwen/Qwen2.5-7B-Instruct \\
      --device cuda --dtype float16 \\
      --prefill-lengths 512,2048,8192 \\
      --decode-tokens 128 \\
      --trials 5 --warmup 2 \\
      --output bench_out/track_e_audit_followups/int4_throughput_hf.json

  # CPU dry-run — exercises the timing loop with a fake tiny model.
  python -m ctm_bench.scripts.track_e_throughput \\
      --dry-run \\
      --output /tmp/dryrun_throughput.json

What it measures
----------------

For each (cache_type, prefill_length) cell:

* Prefill time (ms) — wall clock of the first forward pass with the
  full prompt.
* Decode time (ms) — wall clock of the subsequent N=decode-tokens
  greedy decode steps.
* Decode tokens/sec — N / decode_seconds.
* Total tokens/sec — (prefill_len + N) / (prefill + decode) seconds.

Reports both baseline and INT4 cells side-by-side, plus the ratio.
On GPU, ``torch.cuda.synchronize()`` is called before/after each
timed segment so the numbers reflect kernel execution, not async
queue depth. On CPU dry-run the syncs are no-ops.

The KIVI INT4 cache config matches the §18.3 ship default:
``--k-group-size 32 --v-group-size 32 --asymmetric-int4`` (overridable).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, List, Optional, Sequence

from ctm_bench.policies import _add_kv_policy_to_path
_add_kv_policy_to_path()


LOG = logging.getLogger("track_e_throughput")


# Re-use the version gate + cache factories + dry-run model from
# track_e_quality_eval so the two scripts agree on plumbing.
def _import_quality_eval_helpers():
    from ctm_bench.scripts import track_e_quality_eval as qe
    return qe


@dataclass
class ThroughputCell:
    """One (cache, prefill_length) measurement.

    All timings in milliseconds. Tokens/sec computed from those
    timings at output time so the raw numbers stay editable.
    """
    cache_type: str
    prefill_tokens: int
    decode_tokens: int
    trial: int
    prefill_ms: float
    decode_ms: float
    decode_tokens_per_sec: float
    total_tokens_per_sec: float


@dataclass
class ThroughputSummary:
    model_id: str
    dtype: str
    device: str
    config: dict
    cells: List[ThroughputCell] = field(default_factory=list)
    aggregates: dict = field(default_factory=dict)


def _cuda_sync(device_obj: Any) -> None:
    """torch.cuda.synchronize() if we're on CUDA; no-op otherwise.

    Keeps the timing harness device-agnostic so the dry-run path
    (CPU) and the real-run path (CUDA) share one code path.
    """
    try:
        import torch  # type: ignore
    except ImportError:
        return
    if hasattr(device_obj, "type") and device_obj.type == "cuda":
        torch.cuda.synchronize(device_obj)
    elif isinstance(device_obj, str) and device_obj.startswith("cuda"):
        torch.cuda.synchronize(device_obj)


def _build_prompt_ids(tokenizer, model, target_tokens: int):
    """Build a prompt of approximately ``target_tokens`` IDs.

    Repeats a neutral seed until the tokenizer's encoding hits the
    target, then truncates exactly. Returns a (1, target_tokens) tensor
    on the model's device. Repeated tokens are fine for a throughput
    measurement — we're timing forward passes, not measuring quality.
    """
    import torch
    # The chosen seed text doesn't matter for throughput; what matters
    # is reaching exactly ``target_tokens`` consistent length across
    # baseline and INT4 cells. Use a short word that tokenizes to ~1
    # token so the repeated multiplication lands near-target.
    seed = (
        "The quick brown fox jumps over the lazy dog. "
        "Pack my box with five dozen liquor jugs. "
        "How vexingly quick daft zebras jump. "
    )
    repeats = max(2, target_tokens // 32 + 4)
    text = seed * repeats
    ids = tokenizer(text, return_tensors="pt")["input_ids"]
    if ids.shape[1] < target_tokens:
        # Make sure we're long enough; repeat once more then truncate.
        ids = tokenizer(text * 2, return_tensors="pt")["input_ids"]
    if ids.shape[1] < target_tokens:
        raise RuntimeError(
            f"could not synthesize {target_tokens}-token prompt; "
            f"tokenizer produced {ids.shape[1]} tokens"
        )
    ids = ids[:, :target_tokens].contiguous()
    return ids.to(model.device)


def _time_prefill_decode(
    *,
    model,
    tokenizer,
    prefill_tokens: int,
    decode_tokens: int,
    cache_factory: Callable[[], Any],
    cache_type: str,
    trial: int,
) -> ThroughputCell:
    """One timed prefill + decode pass. Caller responsible for warmup.

    Greedy decoding only — we're measuring throughput, not quality.
    The cache is constructed fresh per call so each trial starts from
    a clean state (no carryover effects).
    """
    import torch
    cache = cache_factory()
    ids = _build_prompt_ids(tokenizer, model, prefill_tokens)

    # Prefill timing.
    _cuda_sync(model.device)
    t0 = time.perf_counter()
    with torch.no_grad():
        out = model(input_ids=ids, use_cache=True, past_key_values=cache)
    _cuda_sync(model.device)
    prefill_ms = (time.perf_counter() - t0) * 1000.0
    next_id = int(out.logits[0, -1, :].argmax().item())

    # Decode timing — N greedy steps.
    _cuda_sync(model.device)
    t1 = time.perf_counter()
    with torch.no_grad():
        for _ in range(decode_tokens):
            tok = torch.tensor([[next_id]], device=model.device)
            out = model(input_ids=tok, use_cache=True, past_key_values=cache)
            next_id = int(out.logits[0, -1, :].argmax().item())
    _cuda_sync(model.device)
    decode_ms = (time.perf_counter() - t1) * 1000.0

    decode_tps = (decode_tokens / decode_ms * 1000.0) if decode_ms > 0 else 0.0
    total_tps = (
        (prefill_tokens + decode_tokens) / ((prefill_ms + decode_ms) / 1000.0)
        if (prefill_ms + decode_ms) > 0
        else 0.0
    )
    return ThroughputCell(
        cache_type=cache_type,
        prefill_tokens=prefill_tokens,
        decode_tokens=decode_tokens,
        trial=trial,
        prefill_ms=prefill_ms,
        decode_ms=decode_ms,
        decode_tokens_per_sec=decode_tps,
        total_tokens_per_sec=total_tps,
    )


def _compute_aggregates(cells: List[ThroughputCell]) -> dict:
    """Best-of-trials per (cache_type, prefill_tokens). Best-of rather
    than mean because we want the steady-state number, not the
    JIT-warmup-perturbed mean.
    """
    import statistics
    keyed: dict = {}
    for c in cells:
        key = (c.cache_type, c.prefill_tokens)
        keyed.setdefault(key, []).append(c)

    out: dict = {}
    for (cache, plen), rows in keyed.items():
        decode_tps_vals = [r.decode_tokens_per_sec for r in rows]
        total_tps_vals = [r.total_tokens_per_sec for r in rows]
        decode_ms_vals = [r.decode_ms for r in rows]
        prefill_ms_vals = [r.prefill_ms for r in rows]
        out[f"{cache}@prefill={plen}"] = {
            "best_decode_tokens_per_sec": max(decode_tps_vals),
            "median_decode_tokens_per_sec": statistics.median(decode_tps_vals),
            "best_total_tokens_per_sec": max(total_tps_vals),
            "median_total_tokens_per_sec": statistics.median(total_tps_vals),
            "median_prefill_ms": statistics.median(prefill_ms_vals),
            "median_decode_ms": statistics.median(decode_ms_vals),
            "n_trials": len(rows),
        }
    return out


def _compute_ratios(aggregates: dict, prefill_lengths: List[int]) -> dict:
    """INT4 / baseline ratios per prefill length. ``<1.0`` means INT4
    is slower than baseline (the expected result with the current
    pure-PyTorch unpack path).
    """
    ratios: dict = {}
    for plen in prefill_lengths:
        b = aggregates.get(f"baseline@prefill={plen}")
        q = aggregates.get(f"int4-per-channel@prefill={plen}")
        if not b or not q:
            continue
        ratios[f"prefill={plen}"] = {
            "int4_vs_baseline_decode_tps_ratio": (
                q["best_decode_tokens_per_sec"]
                / max(b["best_decode_tokens_per_sec"], 1e-9)
            ),
            "int4_vs_baseline_total_tps_ratio": (
                q["best_total_tokens_per_sec"]
                / max(b["best_total_tokens_per_sec"], 1e-9)
            ),
            "int4_decode_overhead_pct": (
                (b["best_decode_tokens_per_sec"]
                 - q["best_decode_tokens_per_sec"])
                / max(b["best_decode_tokens_per_sec"], 1e-9) * 100.0
            ),
        }
    return ratios


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="track_e_throughput",
        description=(
            "Track E (route B) — decode tokens/sec for HF "
            "DynamicCache (FP16 baseline) vs KIVI INT4. The HF-side "
            "peer of run_streaming.py's vLLM tokens/sec (§13.3)."
        ),
    )
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument(
        "--dtype", default="float16",
        choices=["float16", "bfloat16", "float32"],
    )
    parser.add_argument("--device", default="auto")
    parser.add_argument(
        "--prefill-lengths", default="512,2048",
        help=(
            "Comma-separated prefill token counts. Each is one cell. "
            "Defaults cover short prompts (where decode dominates) and "
            "medium prompts (where prefill dominates). Add 8192 / 32768 "
            "for long-context cells (paired with the §20 long-context "
            "sweep)."
        ),
    )
    parser.add_argument(
        "--decode-tokens", type=int, default=128,
        help=(
            "Tokens to greedy-decode after each prefill. 128 is a "
            "reasonable steady-state sample on Qwen2.5-7B — long enough "
            "to amortize CUDA-launch jitter, short enough to keep the "
            "harness under ~10 min for a 3-prefill × 5-trial × 2-cache "
            "sweep."
        ),
    )
    parser.add_argument(
        "--trials", type=int, default=5,
        help=(
            "Timed trials per (cache, prefill_length). Best-of "
            "reported as the headline. >= 3 recommended for the "
            "harness to expose CUDA-launch jitter."
        ),
    )
    parser.add_argument(
        "--warmup", type=int, default=2,
        help=(
            "Untimed warmup runs per cache, run BEFORE the first "
            "timed trial. Loads CUDA kernels, triggers any lazy "
            "compilation, warms the SM scheduler. >= 1 required for "
            "the timed numbers to be steady-state. Default 2."
        ),
    )
    # KIVI-config knobs — defaults match the §18.3 ship config.
    parser.add_argument("--k-group-size", type=int, default=32)
    parser.add_argument("--v-group-size", type=int, default=32)
    parser.add_argument("--asymmetric-int4", action="store_true", default=True)
    parser.add_argument("--no-asymmetric-int4", action="store_false",
                        dest="asymmetric_int4")
    parser.add_argument("--bits", type=int, default=4)
    parser.add_argument(
        "--sink-size", type=int, default=0,
        help=(
            "StreamingLLM-style sink-FP16 + body-INT4 mixed precision. "
            "When > 0, positions [0, sink) are kept FP16 (identity "
            "passthrough); positions [sink:) are quantized. Use the "
            "§20.2 sweep recipe (sink ∈ {0, 4, 16, 64}) to test the "
            "quality recovery hypothesis. Throughput cost of sink-FP16 "
            "vs pure INT4 is negligible (4-64 positions out of ~thousands)."
        ),
    )
    parser.add_argument(
        "--output", type=Path, required=True,
        help="Output JSON path. Caller responsible for the parent dir.",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help=(
            "Use the fake tiny model from track_e_quality_eval (no HF "
            "model download, no GPU). Verifies the timing-loop shape "
            "before paying for GPU time."
        ),
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    qe = _import_quality_eval_helpers()
    prefill_lengths = [int(s.strip()) for s in args.prefill_lengths.split(",") if s.strip()]
    if not prefill_lengths:
        print("--prefill-lengths must list at least one length", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)

    # ---- Load model ----
    if args.dry_run:
        LOG.info("DRY RUN: building fake tiny model (no HF download)")
        qe._check_transformers_version()
        model, tokenizer = qe._build_fake_model()
        model_id_for_summary = "fake-tiny-model (DRY-RUN)"
        # Cap dry-run prefill/decode tiny so the fake model can handle it.
        prefill_lengths = [min(p, 64) for p in prefill_lengths]
        decode_tokens = min(args.decode_tokens, 8)
        n_trials = min(args.trials, 2)
        n_warmup = min(args.warmup, 1)
    else:
        qe._check_transformers_version()
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        LOG.info("Loading %s (dtype=%s, device=%s)",
                 args.model, args.dtype, args.device)
        torch_dtype = getattr(torch, args.dtype)
        device_map = args.device if args.device != "auto" else "auto"
        tokenizer = AutoTokenizer.from_pretrained(args.model)
        if tokenizer.pad_token_id is None:
            tokenizer.pad_token_id = tokenizer.eos_token_id
        model = AutoModelForCausalLM.from_pretrained(
            args.model, torch_dtype=torch_dtype, device_map=device_map,
        )
        model.eval()
        model_id_for_summary = args.model
        decode_tokens = args.decode_tokens
        n_trials = args.trials
        n_warmup = args.warmup

    baseline_factory = qe._baseline_cache_factory()
    int4_factory = qe._int4_per_channel_cache_factory(
        sink_size=args.sink_size,
        k_group_size=args.k_group_size,
        v_group_size=args.v_group_size,
        asymmetric=args.asymmetric_int4,
        bits=args.bits,
    )

    config_dict = {
        "quant": "int4-per-channel",
        "k_group_size": args.k_group_size,
        "v_group_size": args.v_group_size,
        "asymmetric": args.asymmetric_int4,
        "bits": args.bits,
        "sink_size": args.sink_size,
        "prefill_lengths": prefill_lengths,
        "decode_tokens": decode_tokens,
        "trials": n_trials,
        "warmup": n_warmup,
        "scheme": (
            f"K=per-channel INT{args.bits}, V=per-token INT{args.bits}, "
            f"{'asymmetric' if args.asymmetric_int4 else 'symmetric'}, "
            f"k_group={args.k_group_size}, v_group={args.v_group_size}"
            + (f", sink_size={args.sink_size}" if args.sink_size > 0 else "")
        ),
    }
    summary = ThroughputSummary(
        model_id=model_id_for_summary,
        dtype=args.dtype,
        device=str(getattr(model, "device", args.device)),
        config=config_dict,
    )

    cells: List[ThroughputCell] = []
    for cache_label, factory in (
        ("baseline", baseline_factory),
        ("int4-per-channel", int4_factory),
    ):
        for plen in prefill_lengths:
            LOG.info("[%s prefill=%d] warmup=%d trials=%d decode=%d",
                     cache_label, plen, n_warmup, n_trials, decode_tokens)
            # Warmup.
            for w in range(n_warmup):
                _time_prefill_decode(
                    model=model, tokenizer=tokenizer,
                    prefill_tokens=plen, decode_tokens=decode_tokens,
                    cache_factory=factory, cache_type=cache_label, trial=-1,
                )
            # Timed trials.
            for t in range(n_trials):
                cell = _time_prefill_decode(
                    model=model, tokenizer=tokenizer,
                    prefill_tokens=plen, decode_tokens=decode_tokens,
                    cache_factory=factory, cache_type=cache_label, trial=t,
                )
                cells.append(cell)
                LOG.info(
                    "  trial=%d prefill=%.1fms decode=%.1fms decode_tps=%.1f",
                    t, cell.prefill_ms, cell.decode_ms, cell.decode_tokens_per_sec,
                )

    summary.cells = cells
    summary.aggregates = _compute_aggregates(cells)
    summary.aggregates["int4_vs_baseline"] = _compute_ratios(
        summary.aggregates, prefill_lengths,
    )

    args.output.write_text(json.dumps(asdict(summary), indent=2))
    print(f"Wrote {args.output}")

    # Reader-friendly summary on stdout.
    print()
    print("=" * 72)
    print(f"Track E throughput — {model_id_for_summary}")
    print("=" * 72)
    for plen in prefill_lengths:
        b = summary.aggregates.get(f"baseline@prefill={plen}")
        q = summary.aggregates.get(f"int4-per-channel@prefill={plen}")
        r = summary.aggregates.get("int4_vs_baseline", {}).get(f"prefill={plen}")
        if not (b and q and r):
            continue
        print(
            f"  prefill={plen:>5}: baseline {b['best_decode_tokens_per_sec']:7.2f} tok/s "
            f"vs INT4 {q['best_decode_tokens_per_sec']:7.2f} tok/s   "
            f"(INT4 ratio={r['int4_vs_baseline_decode_tps_ratio']:.3f}, "
            f"overhead={r['int4_decode_overhead_pct']:+.1f}%)"
        )
    print()
    print(f"Full per-trial detail in {args.output}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
