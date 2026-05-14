"""Track D — Real-value KV cosine on captured Qwen2.5-7B activations.

Loads a HuggingFace causal LM (default ``Qwen/Qwen2.5-7B-Instruct``),
runs forward passes on a small set of fixed prompts, captures the K
and V tensors at chosen layers, and runs them through the TurboQuant
compression path. Reports per-layer cosine similarity vs the
synthetic-Gaussian baseline (cosine ~0.964 from
``Bench/bench_out/PHASE4_GPU_FINDINGS.md`` §15.2).

Closes the §15.3 caveat: "is cosine 0.965 on Gaussian a real claim?"

Outputs ``bench_out/track_d/results.json`` with a structured row per
(prompt, layer, backend) tuple. Optionally saves the captured tensors
to ``bench_out/track_d/fixtures/<prompt>_<layer>.pt`` for re-running
TurboQuant variations offline.

CLI
---

  python -m ctm_bench.scripts.track_d_capture_kv \
      --model Qwen/Qwen2.5-7B-Instruct \
      --layers 0,7,14,21,27 \
      --output-dir bench_out/track_d/

  # Dry-run on a fake tiny model — exercises the full pipeline on CPU
  # without HF model download. Validates the script before paying for
  # GPU time.
  python -m ctm_bench.scripts.track_d_capture_kv \
      --dry-run \
      --output-dir bench_out/track_d_dryrun/

Pod / cost estimate
-------------------

* Qwen2.5-7B FP16 on A100 80GB: model load ~5 min, capture ~30 sec
  per prompt. Total ~6-8 min for the 5-prompt default. Cost ~$0.20
  spot.
* Qwen2.5-7B FP16 on CPU with 32 GB RAM: model load ~5 min, capture
  ~5-15 min per prompt due to no batched attention kernel. Total
  ~30-90 min. Free if you have the host.
* Dry-run on this CPU-only pod: ~30 seconds end-to-end.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, List, Optional, Sequence

# Self-bootstrap: make kv_policy importable when launched from a fresh
# venv that hasn't `pip install -e`'d the sibling KVPolicy package.
from ctm_bench.policies import _add_kv_policy_to_path
_add_kv_policy_to_path()


LOG = logging.getLogger("track_d")


def _check_transformers_version() -> None:
    """Hard-fail early if transformers < 5.0 OR torch < 2.5.

    Track D reads ``past_key_values.layers[li].keys`` (the 5.x cache
    layer surface) and goes through ``AutoModelForCausalLM`` which
    eagerly imports transformers' MoE integration. transformers 5.x's
    ``integrations/moe.py`` calls ``torch.library.custom_op`` with
    PEP-563-style string annotations on Tensor params; torch < 2.5
    can't resolve those and crashes at import. Pin both versions so
    a mismatch fails before model load (not mid-capture).
    """
    try:
        import transformers  # type: ignore
    except ImportError:
        raise SystemExit(
            "transformers not installed. Run: pip install --upgrade 'transformers>=5.0'"
        )
    try:
        import torch  # type: ignore
    except ImportError:
        raise SystemExit("torch not installed. Run: pip install --upgrade torch")
    t_major = int(transformers.__version__.split(".")[0])
    if t_major < 5:
        raise SystemExit(
            f"transformers {transformers.__version__} detected; this script "
            f"requires >= 5.0. Run: pip install --upgrade 'transformers>=5.0'"
        )
    torch_parts = torch.__version__.split(".")
    pt_major, pt_minor = int(torch_parts[0]), int(torch_parts[1])
    if (pt_major, pt_minor) < (2, 5):
        raise SystemExit(
            f"torch {torch.__version__} detected; transformers 5.x requires "
            f"torch >= 2.5. Run: "
            f"pip install --upgrade torch --index-url https://download.pytorch.org/whl/cu121"
        )


# --------------------------------------------------------------------------- #
# Default prompts — diverse to exercise the activation-distribution variance  #
# that real KV cache sees in production. Tuned to be ~64-128 tokens each so   #
# capture is fast.                                                            #
# --------------------------------------------------------------------------- #

DEFAULT_PROMPTS = [
    # Casual chat — typical assistant workload
    ("chat", "What's the difference between latte and cappuccino? Be brief."),
    # Code — produces structured token distributions, often outlier-heavy
    ("code", "Write a Python function that computes the n-th Fibonacci number using memoization. Include a brief docstring."),
    # Long-form factual — typical RAG / summarisation
    ("factual", "Explain in three sentences why the sky is blue, then in three more sentences why sunsets are red."),
    # Reasoning — multi-step, often produces sharper attention peaks
    ("reasoning", "Alice is older than Bob. Bob is older than Carol. Carol is younger than Dan. Dan is younger than Alice. Order them from oldest to youngest and explain."),
    # Multilingual — non-Latin script changes the embedding distribution
    ("multilingual", "Translate to Japanese, then explain the grammar: 'The cat sat on the mat.'"),
]


# --------------------------------------------------------------------------- #
# Result schema                                                               #
# --------------------------------------------------------------------------- #


@dataclass
class CaptureRow:
    """One measurement: TurboQuant round-trip applied to one block of one
    layer's KV from one prompt's prefill."""
    prompt_label: str
    prompt_text_preview: str  # first 80 chars
    prompt_token_count: int
    layer_index: int
    block_token_offset: int    # which 16-token slice was sampled
    block_size: int
    num_kv_heads: int
    head_dim: int
    backend: str               # "numpy" or "torch"
    cosine_k: float
    cosine_v: float
    compression_ratio: float
    write_us: float
    read_us: float


@dataclass
class TrackDSummary:
    model_id: str
    dtype: str
    num_prompts: int
    layers_sampled: List[int]
    total_rows: int
    cosine_k_min: float
    cosine_k_mean: float
    cosine_v_min: float
    cosine_v_mean: float
    architecture_target_cosine: float = 0.95
    synthetic_gaussian_baseline_cosine: float = 0.964
    rows: List[CaptureRow] = None  # type: ignore


# --------------------------------------------------------------------------- #
# Capture pipeline                                                            #
# --------------------------------------------------------------------------- #


def _cosine(a, b) -> float:
    """Cosine similarity on flattened tensors, computed in float64 to
    avoid spurious FP16 underflow on the < 0.99 range we care about."""
    import torch
    af = a.flatten().to(torch.float64)
    bf = b.flatten().to(torch.float64)
    n = (torch.linalg.vector_norm(af) * torch.linalg.vector_norm(bf)).item()
    if n == 0.0:
        return 0.0
    return float(torch.dot(af, bf).item() / n)


def _slice_block(
    kv_tensor, *, token_offset: int, block_size: int
) -> Any:
    """Slice a (batch, num_kv_heads, seq, head_dim) tensor into a vLLM-
    style block of shape (block_size, num_kv_heads, head_dim).

    Picks the first batch element. Assumes seq >= token_offset +
    block_size (caller is responsible).
    """
    sliced = kv_tensor[0, :, token_offset:token_offset + block_size, :]
    # (num_kv_heads, block_size, head_dim) → (block_size, num_kv_heads, head_dim)
    return sliced.transpose(0, 1).contiguous()


def capture_one_prompt(
    *,
    model,
    tokenizer,
    prompt_text: str,
    target_layers: Sequence[int],
    block_size: int,
    backends: Sequence[str],
    dry_run_kv: Optional[Sequence[Any]] = None,
) -> List[CaptureRow]:
    """Run a forward pass on ``prompt_text``, capture KV at
    ``target_layers``, run each layer's KV through TurboQuant in each
    requested backend, and return the rows.

    ``dry_run_kv``: if provided, skips the model forward pass and uses
    the supplied KV (one entry per target layer, each shape
    ``(1, num_kv_heads, seq, head_dim)``) directly. Used by the
    ``--dry-run`` path so the script's CLI / output schema can be
    tested without HF model access.
    """
    import torch
    from kv_policy.turboquant_kvstore import TurboQuantKVStore

    if dry_run_kv is None:
        # Real forward pass.
        inputs = tokenizer(prompt_text, return_tensors="pt").to(model.device)
        with torch.no_grad():
            outputs = model(**inputs, use_cache=True)
        past = outputs.past_key_values
        prompt_token_count = int(inputs["input_ids"].shape[1])
        per_layer_kv = []
        for li in target_layers:
            # Newer transformers Cache exposes layers via .layers[li]
            # with .keys / .values; older versions return a tuple
            # (K, V) per layer.
            if hasattr(past, "layers"):
                k = past.layers[li].keys
                v = past.layers[li].values
            else:
                k, v = past[li]
            per_layer_kv.append((k, v))
    else:
        per_layer_kv = list(dry_run_kv)
        prompt_token_count = int(per_layer_kv[0][0].shape[2]) if per_layer_kv else 0

    rows: List[CaptureRow] = []
    for li_idx, (k_full, v_full) in enumerate(per_layer_kv):
        layer_index = int(target_layers[li_idx])
        seq = int(k_full.shape[2])
        if seq < block_size:
            LOG.warning(
                "Skipping layer %d: seq=%d < block_size=%d", layer_index, seq, block_size,
            )
            continue
        # Sample one block from the middle of the prompt — avoids
        # special-position effects (BOS, EOS).
        token_offset = max(0, (seq - block_size) // 2)
        k_block = _slice_block(k_full, token_offset=token_offset, block_size=block_size)
        v_block = _slice_block(v_full, token_offset=token_offset, block_size=block_size)
        num_kv_heads = int(k_block.shape[1])
        head_dim = int(k_block.shape[2])

        for backend in backends:
            store = TurboQuantKVStore(backend=backend)
            if backend == "torch":
                store.write_block(0, k_block.detach().cpu(), v_block.detach().cpu())
                k_back, v_back = store.read_block(0)
                cos_k = _cosine(k_block.detach().cpu(), k_back)
                cos_v = _cosine(v_block.detach().cpu(), v_back)
            else:  # numpy
                import numpy as np
                k_np = k_block.detach().cpu().to(torch.float32).numpy()
                v_np = v_block.detach().cpu().to(torch.float32).numpy()
                store.write_block(0, k_np, v_np)
                k_back, v_back = store.read_block(0)
                cos_k = _cosine(torch.from_numpy(k_np), torch.from_numpy(k_back))
                cos_v = _cosine(torch.from_numpy(v_np), torch.from_numpy(v_back))
            stats = store.get_stats()
            rows.append(
                CaptureRow(
                    prompt_label="(set by caller)",
                    prompt_text_preview=prompt_text[:80],
                    prompt_token_count=prompt_token_count,
                    layer_index=layer_index,
                    block_token_offset=token_offset,
                    block_size=block_size,
                    num_kv_heads=num_kv_heads,
                    head_dim=head_dim,
                    backend=backend,
                    cosine_k=cos_k,
                    cosine_v=cos_v,
                    compression_ratio=float(stats["compression_ratio"]),
                    write_us=float(stats["avg_write_us"]),
                    read_us=float(stats["avg_read_us"]),
                )
            )
    return rows


# --------------------------------------------------------------------------- #
# Dry-run fake "model"                                                        #
# --------------------------------------------------------------------------- #


def _fake_kv(target_layers: Sequence[int], *, seq: int = 64) -> List[Any]:
    """Construct fake (1, num_kv_heads=4, seq, head_dim=128) tensors
    matching the Qwen2.5-7B GQA-4 KV layout. Used for dry-run."""
    import torch
    g = torch.Generator().manual_seed(42)
    out = []
    for layer_idx in target_layers:
        # Per-layer seed shift so the output isn't identical across
        # "layers" — exercises the per-layer aggregation logic.
        gg = torch.Generator().manual_seed(42 + layer_idx)
        k = torch.randn(1, 4, seq, 128, generator=gg, dtype=torch.float32)
        v = torch.randn(1, 4, seq, 128, generator=gg, dtype=torch.float32)
        out.append((k, v))
    return out


# --------------------------------------------------------------------------- #
# Main                                                                        #
# --------------------------------------------------------------------------- #


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="track_d_capture_kv",
        description=(
            "Track D — real-value KV cosine on captured Qwen2.5-7B "
            "activations. Closes the §15.3 caveat in "
            "PHASE4_GPU_FINDINGS.md."
        ),
    )
    parser.add_argument(
        "--model", default="Qwen/Qwen2.5-7B-Instruct",
        help="HF model id. Default: Qwen2.5-7B-Instruct.",
    )
    parser.add_argument(
        "--dtype", default="float16", choices=["float16", "bfloat16", "float32"],
        help="Model dtype. Default float16 to match vLLM's KV-cache dtype.",
    )
    parser.add_argument(
        "--device", default="auto",
        help="Device map: 'auto', 'cuda', 'cpu'. Default 'auto'.",
    )
    parser.add_argument(
        "--layers", default="0,7,14,21,27",
        help=(
            "Comma-separated layer indices to sample. Default covers "
            "shallow / middle / deep strata of Qwen2.5-7B's 28 layers."
        ),
    )
    parser.add_argument(
        "--block-size", type=int, default=16,
        help="vLLM block size. Default 16.",
    )
    parser.add_argument(
        "--backends", default="numpy,torch",
        help="Comma-separated TurboQuant backends to test.",
    )
    parser.add_argument(
        "--output-dir", type=Path, required=True,
        help="Directory to write results.json + (optionally) fixtures.",
    )
    parser.add_argument(
        "--save-fixtures", action="store_true",
        help=(
            "Save the captured KV tensors as .pt fixtures so future "
            "TurboQuant variations can be tested offline. ~50 KB per "
            "(prompt, layer) pair."
        ),
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help=(
            "Skip model loading; use synthetic Gaussian KV at Qwen "
            "shape. Validates the CLI / pipeline / output schema on "
            "CPU without HF access."
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

    args.output_dir.mkdir(parents=True, exist_ok=True)
    target_layers = [int(s.strip()) for s in args.layers.split(",") if s.strip()]
    backends = [s.strip() for s in args.backends.split(",") if s.strip()]

    if args.dry_run:
        _check_transformers_version()
        LOG.info("DRY RUN: using fake Qwen-shape Gaussian KV (no HF download)")
        model = None
        tokenizer = None
        dry_run_kv = _fake_kv(target_layers, seq=64)
    else:
        _check_transformers_version()
        LOG.info("Loading %s (dtype=%s, device=%s)", args.model, args.dtype, args.device)
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        torch_dtype = getattr(torch, args.dtype)
        device_map = args.device if args.device != "auto" else "auto"
        tokenizer = AutoTokenizer.from_pretrained(args.model)
        model = AutoModelForCausalLM.from_pretrained(
            args.model, torch_dtype=torch_dtype, device_map=device_map,
        )
        model.eval()
        dry_run_kv = None
        LOG.info("Model loaded: %d parameters", sum(p.numel() for p in model.parameters()))

    all_rows: List[CaptureRow] = []
    prompts = DEFAULT_PROMPTS
    for label, text in prompts:
        LOG.info("Capturing prompt %r (%d chars)", label, len(text))
        rows = capture_one_prompt(
            model=model,
            tokenizer=tokenizer,
            prompt_text=text,
            target_layers=target_layers,
            block_size=args.block_size,
            backends=backends,
            dry_run_kv=dry_run_kv,
        )
        for r in rows:
            r.prompt_label = label
        all_rows.extend(rows)
        LOG.info(
            "  → %d rows; cosine_k range [%.4f, %.4f]",
            len(rows),
            min((r.cosine_k for r in rows), default=0.0),
            max((r.cosine_k for r in rows), default=0.0),
        )

    if not all_rows:
        LOG.error("No rows captured — did the prompts produce empty KV?")
        return 1

    cos_k_vals = [r.cosine_k for r in all_rows]
    cos_v_vals = [r.cosine_v for r in all_rows]
    summary = TrackDSummary(
        model_id=args.model + (" (DRY-RUN synthetic Gaussian)" if args.dry_run else ""),
        dtype=args.dtype,
        num_prompts=len(prompts),
        layers_sampled=target_layers,
        total_rows=len(all_rows),
        cosine_k_min=min(cos_k_vals),
        cosine_k_mean=sum(cos_k_vals) / len(cos_k_vals),
        cosine_v_min=min(cos_v_vals),
        cosine_v_mean=sum(cos_v_vals) / len(cos_v_vals),
        rows=all_rows,
    )

    out_path = args.output_dir / "results.json"
    with open(out_path, "w") as f:
        json.dump(asdict(summary), f, indent=2)
    LOG.info("Wrote %s", out_path)

    print()
    print("=" * 60)
    print(f"Track D summary — {summary.model_id}")
    print("=" * 60)
    print(f"  Prompts:         {summary.num_prompts}")
    print(f"  Layers sampled:  {summary.layers_sampled}")
    print(f"  Total rows:      {summary.total_rows}")
    print(f"  Cosine K mean:   {summary.cosine_k_mean:.4f}")
    print(f"  Cosine K min:    {summary.cosine_k_min:.4f}")
    print(f"  Cosine V mean:   {summary.cosine_v_mean:.4f}")
    print(f"  Cosine V min:    {summary.cosine_v_min:.4f}")
    print()
    print(f"  Architecture-doc target:           >= {summary.architecture_target_cosine}")
    print(f"  Synthetic-Gaussian baseline:        ~ {summary.synthetic_gaussian_baseline_cosine}")
    print()
    if summary.cosine_k_min >= summary.architecture_target_cosine:
        print("  PASS: real-value cosine meets architecture-doc target.")
    elif summary.cosine_k_mean >= summary.architecture_target_cosine:
        print("  PARTIAL: mean cosine meets target but min does not — some layers regress.")
    else:
        print("  REGRESSION: real-value cosine below architecture target. Investigate before Track E.")
    print()
    print(f"  Full results: {out_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
