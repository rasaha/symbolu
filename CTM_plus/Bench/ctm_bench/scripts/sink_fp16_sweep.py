"""§20.2 single-load sweep — sink-FP16 + body-INT4 quality across
sink ∈ {0, 4, 16, 64} on the §18.3 ship KIVI config.

**Why this script exists instead of a bash loop:** the runbook §5i
recipe loops the eval script across four sink values, which reloads
Qwen2.5-7B from disk four times (~4 × 30s on A100 = 2 min of pure
load overhead, ~$0.05 spot). This script loads the model ONCE and
iterates the cache configurations against it, so the same sweep
costs ~$0.50 total instead of ~$0.55 — about 10% savings per sweep,
material when you re-run with different group_size or bits.

CLI
---

  # Default sweep (sink ∈ {0, 4, 16, 64}, full KIVI ship config):
  python -m ctm_bench.scripts.sink_fp16_sweep \\
      --model Qwen/Qwen2.5-7B-Instruct \\
      --device cuda --dtype float16 \\
      --eval perplexity,mmlu \\
      --mmlu-num-questions 1000 \\
      --output bench_out/track_e_audit_followups/sink_fp16_sweep.json

  # CPU dry-run (exercises the loop shape, no HF download):
  python -m ctm_bench.scripts.sink_fp16_sweep \\
      --dry-run \\
      --output /tmp/dry_sink_sweep.json

What it measures
----------------

Per sink_size, runs both perplexity (single forward pass on the
inline 282-token text) and MMLU subset accuracy. The §18.3 ship
config (group=32 + asymmetric INT4) is held fixed across all sink
values so the sweep isolates the sink-FP16 axis.

Output schema (`§20.2.v1`)
-------------------------

Top-level: `model_id`, `dtype`, `int4_config` (group/asymmetric/bits),
`sink_sweep` (list of per-sink results, one per sink_size), `deltas`
(MMLU deltas vs sink=0 baseline). The composer
(`compose_sink_fp16_summary.py`) ingests this to produce the §20.2
markdown table + merged JSON.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, List, Optional, Sequence

from ctm_bench.policies import _add_kv_policy_to_path
_add_kv_policy_to_path()


LOG = logging.getLogger("sink_fp16_sweep")


def _import_quality_eval_helpers():
    from ctm_bench.scripts import track_e_quality_eval as qe
    return qe


@dataclass
class SinkResult:
    """One (sink_size, baseline_or_quant) measurement row.

    Mirrors `track_e_quality_eval`'s row schemas closely so the
    composer can read either output type uniformly.
    """
    sink_size: int
    cache_type: str       # "baseline" or "int4-per-channel"
    perplexity: Optional[float] = None
    nll_per_token: Optional[float] = None
    mmlu_correct: Optional[int] = None
    mmlu_total: Optional[int] = None
    mmlu_accuracy: Optional[float] = None
    notes: Optional[str] = None


@dataclass
class SinkSweepSummary:
    schema_version: str = "§20.2.v1"
    model_id: str = ""
    dtype: str = ""
    int4_config: dict = field(default_factory=dict)
    sink_values: List[int] = field(default_factory=list)
    rows: List[SinkResult] = field(default_factory=list)
    deltas: dict = field(default_factory=dict)


def _compute_deltas_vs_sink_zero(rows: List[SinkResult]) -> dict:
    """Compute MMLU and perplexity deltas at each sink_size vs the
    sink=0 INT4 measurement (the §19.4 measured baseline that this
    sweep tries to improve on).
    """
    # Find the sink=0 INT4 row to anchor the deltas.
    sink0 = next(
        (r for r in rows
         if r.sink_size == 0 and r.cache_type == "int4-per-channel"),
        None,
    )
    out: dict = {"anchor": "sink=0 int4-per-channel (§19.4 ship config)"}
    if sink0 is None:
        out["error"] = "no sink=0 INT4 row in sweep; can't compute deltas"
        return out
    out["sink0_mmlu_accuracy"] = sink0.mmlu_accuracy
    out["sink0_perplexity"] = sink0.perplexity
    out["per_sink"] = {}
    for r in rows:
        if r.cache_type != "int4-per-channel":
            continue
        delta: dict = {}
        if r.mmlu_accuracy is not None and sink0.mmlu_accuracy is not None:
            delta["mmlu_delta_pt"] = (
                (r.mmlu_accuracy - sink0.mmlu_accuracy) * 100.0
            )
        if r.perplexity is not None and sink0.perplexity is not None:
            delta["perplexity_ratio"] = r.perplexity / sink0.perplexity
        out["per_sink"][f"sink={r.sink_size}"] = delta
    # Also compute vs the FP16 baseline (the absolute gap that the
    # §20.2 hypothesis tries to recover).
    baseline = next(
        (r for r in rows
         if r.sink_size == 0 and r.cache_type == "baseline"),
        None,
    )
    if baseline is not None:
        out["baseline_fp16_mmlu_accuracy"] = baseline.mmlu_accuracy
        out["baseline_fp16_perplexity"] = baseline.perplexity
        out["per_sink_vs_fp16"] = {}
        for r in rows:
            if r.cache_type != "int4-per-channel":
                continue
            delta_fp16: dict = {}
            if r.mmlu_accuracy is not None and baseline.mmlu_accuracy is not None:
                delta_fp16["mmlu_delta_pt"] = (
                    (r.mmlu_accuracy - baseline.mmlu_accuracy) * 100.0
                )
            if r.perplexity is not None and baseline.perplexity is not None:
                delta_fp16["perplexity_ratio"] = r.perplexity / baseline.perplexity
            out["per_sink_vs_fp16"][f"sink={r.sink_size}"] = delta_fp16
    return out


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="sink_fp16_sweep",
        description=(
            "§20.2 single-load sweep across sink ∈ {0, 4, 16, 64} on the "
            "§18.3 ship config. Tests whether sink-FP16 + body-INT4-with-"
            "KIVI-rescue recovers the -0.9pt MMLU gap above FP8."
        ),
    )
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument(
        "--dtype", default="float16",
        choices=["float16", "bfloat16", "float32"],
    )
    parser.add_argument("--device", default="auto")
    parser.add_argument(
        "--eval", default="perplexity,mmlu",
        help="Comma-separated: perplexity, mmlu (no generation in sweep).",
    )
    parser.add_argument(
        "--sink-values", default="0,4,16,64",
        help=(
            "Comma-separated list of sink sizes to sweep. 0 is the "
            "control (reproduces §19.4 ship config); 4 tests "
            "StreamingLLM's published optimum; 16 tests for plateau; "
            "64 tests the 'first-chunk' alternative hypothesis."
        ),
    )
    parser.add_argument("--mmlu-num-questions", type=int, default=1000)
    parser.add_argument("--mmlu-seed", type=int, default=2026)
    # §18.3 ship config knobs. Sweep changes only sink_size; these are
    # held fixed so the sweep isolates the sink-FP16 axis.
    parser.add_argument("--k-group-size", type=int, default=32)
    parser.add_argument("--v-group-size", type=int, default=32)
    parser.add_argument("--asymmetric-int4", action="store_true", default=True)
    parser.add_argument("--no-asymmetric-int4", action="store_false",
                        dest="asymmetric_int4")
    parser.add_argument("--bits", type=int, default=4)
    parser.add_argument(
        "--output", type=Path, required=True,
        help="Output JSON path (composer reads this).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help=(
            "Use the fake tiny model from track_e_quality_eval. "
            "Verifies the sweep loop without HF/GPU."
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

    sink_values = [int(s.strip()) for s in args.sink_values.split(",") if s.strip()]
    if not sink_values:
        print("--sink-values must list at least one value", file=sys.stderr)
        return 2
    if 0 not in sink_values:
        print(
            "WARNING: sink=0 is the control measurement and is normally "
            "included in the sweep so deltas anchor against the §19.4 "
            "ship config. Proceeding anyway since you explicitly asked.",
            file=sys.stderr,
        )

    eval_kinds = [s.strip() for s in args.eval.split(",") if s.strip()]
    args.output.parent.mkdir(parents=True, exist_ok=True)

    qe = _import_quality_eval_helpers()

    # ---- Model load (ONCE, shared across all sink values) ----
    if args.dry_run:
        LOG.info("DRY RUN: building fake tiny model")
        qe._check_transformers_version()
        model, tokenizer = qe._build_fake_model()
        model_id_for_summary = "fake-tiny-model (DRY-RUN)"
        # On the fake model, MMLU uses the inline 5-question sample.
        mmlu_questions = qe.MMLU_SAMPLE
        # Cap dry-run sweep to keep wall < 1 min.
        n_mmlu = min(args.mmlu_num_questions, 5)
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
        if "mmlu" in eval_kinds:
            try:
                from datasets import load_dataset
                ds = load_dataset("cais/mmlu", "all", split="test")
                ds = ds.shuffle(seed=args.mmlu_seed)
                mmlu_questions = []
                for row in ds.select(range(min(args.mmlu_num_questions, len(ds)))):
                    mmlu_questions.append({
                        "subject": row["subject"],
                        "question": row["question"],
                        "choices": row["choices"],
                        "answer": "ABCD"[int(row["answer"])],
                    })
                LOG.info("Loaded %d MMLU questions", len(mmlu_questions))
            except Exception as exc:
                LOG.warning(
                    "MMLU load failed (%s); falling back to inline 5", exc,
                )
                mmlu_questions = qe.MMLU_SAMPLE
        else:
            mmlu_questions = qe.MMLU_SAMPLE
        n_mmlu = args.mmlu_num_questions

    int4_config = {
        "quant": "int4-per-channel",
        "k_group_size": args.k_group_size,
        "v_group_size": args.v_group_size,
        "asymmetric": args.asymmetric_int4,
        "bits": args.bits,
        "scheme": (
            f"K=per-channel INT{args.bits}, V=per-token INT{args.bits}, "
            f"{'asymmetric' if args.asymmetric_int4 else 'symmetric'}, "
            f"k_group={args.k_group_size}, v_group={args.v_group_size}"
        ),
    }
    summary = SinkSweepSummary(
        model_id=model_id_for_summary,
        dtype=args.dtype,
        int4_config=int4_config,
        sink_values=sink_values,
    )

    baseline_factory = qe._baseline_cache_factory()

    # --- Baseline (FP16) row at sink_size=0 — measured once, applies
    # to all sink values for the "vs FP16" delta block. We DON'T
    # re-run baseline per sink_size; FP16 has no sink_size axis. ---
    if "perplexity" in eval_kinds:
        LOG.info("Baseline FP16: perplexity")
        base_p = qe.compute_perplexity(
            model=model, tokenizer=tokenizer, text=qe.PERPLEXITY_TEXT,
            cache_factory=baseline_factory, cache_type="baseline",
        )
        summary.rows.append(SinkResult(
            sink_size=0, cache_type="baseline",
            perplexity=base_p.perplexity,
            nll_per_token=base_p.nll_per_token,
        ))
    if "mmlu" in eval_kinds:
        LOG.info("Baseline FP16: MMLU (%d questions)", len(mmlu_questions))
        base_m = qe.compute_mmlu_accuracy(
            model=model, tokenizer=tokenizer, questions=mmlu_questions,
            cache_factory=baseline_factory, cache_type="baseline",
        )
        # Update the same row (or append a separate one for sink=0
        # baseline with MMLU populated).
        existing = next(
            (r for r in summary.rows
             if r.sink_size == 0 and r.cache_type == "baseline"),
            None,
        )
        if existing is None:
            summary.rows.append(SinkResult(
                sink_size=0, cache_type="baseline",
                mmlu_correct=base_m.correct,
                mmlu_total=base_m.num_questions,
                mmlu_accuracy=base_m.accuracy,
            ))
        else:
            existing.mmlu_correct = base_m.correct
            existing.mmlu_total = base_m.num_questions
            existing.mmlu_accuracy = base_m.accuracy

    # --- Per-sink INT4 cells ---
    for sink in sink_values:
        LOG.info(
            "Sink=%d: INT4 + group=%d + asym=%s (eval=%s)",
            sink, args.k_group_size, args.asymmetric_int4, ",".join(eval_kinds),
        )
        int4_factory = qe._int4_per_channel_cache_factory(
            sink_size=sink,
            k_group_size=args.k_group_size,
            v_group_size=args.v_group_size,
            asymmetric=args.asymmetric_int4,
            bits=args.bits,
        )
        row = SinkResult(sink_size=sink, cache_type="int4-per-channel")
        if "perplexity" in eval_kinds:
            p = qe.compute_perplexity(
                model=model, tokenizer=tokenizer, text=qe.PERPLEXITY_TEXT,
                cache_factory=int4_factory, cache_type="int4-per-channel",
            )
            row.perplexity = p.perplexity
            row.nll_per_token = p.nll_per_token
        if "mmlu" in eval_kinds:
            m = qe.compute_mmlu_accuracy(
                model=model, tokenizer=tokenizer, questions=mmlu_questions,
                cache_factory=int4_factory, cache_type="int4-per-channel",
            )
            row.mmlu_correct = m.correct
            row.mmlu_total = m.num_questions
            row.mmlu_accuracy = m.accuracy
        summary.rows.append(row)
        LOG.info(
            "  sink=%d: ppl=%s mmlu=%s",
            sink,
            f"{row.perplexity:.4f}" if row.perplexity is not None else "n/a",
            f"{row.mmlu_accuracy:.4f}" if row.mmlu_accuracy is not None else "n/a",
        )

    summary.deltas = _compute_deltas_vs_sink_zero(summary.rows)

    args.output.write_text(json.dumps(asdict(summary), indent=2))
    print(f"Wrote {args.output}")

    # Reader-friendly stdout summary.
    print()
    print("=" * 72)
    print(f"§20.2 sink-FP16 sweep — {model_id_for_summary}")
    print("=" * 72)
    for sink in sink_values:
        row = next(
            (r for r in summary.rows
             if r.sink_size == sink and r.cache_type == "int4-per-channel"),
            None,
        )
        if row is None:
            continue
        ppl_str = f"ppl={row.perplexity:.4f}" if row.perplexity else "ppl=n/a"
        mmlu_str = (
            f"mmlu={row.mmlu_accuracy*100:.2f}%" if row.mmlu_accuracy is not None
            else "mmlu=n/a"
        )
        delta_block = summary.deltas.get("per_sink_vs_fp16", {}).get(f"sink={sink}", {})
        mmlu_delta = delta_block.get("mmlu_delta_pt")
        delta_str = (
            f"  Δ_MMLU vs FP16 = {mmlu_delta:+.2f}pt"
            if mmlu_delta is not None else ""
        )
        print(f"  sink={sink:>2}: {ppl_str}  {mmlu_str}{delta_str}")
    print()
    print(f"Full per-sink detail in {args.output}.")
    print(
        "Run `python -m ctm_bench.scripts.compose_sink_fp16_summary "
        f"--input {args.output}` to compose the §20.2 markdown table."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
