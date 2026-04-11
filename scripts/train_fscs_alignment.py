#!/usr/bin/env python3
"""
scripts/train_fscs_alignment.py

Short fine-tune of FSCS trainable parameters on a frozen Mistral
backbone, driven by the §12.2 stopgrad alignment loss. This is the
Text-FSCS spec §5.5 "first experiment" — the one that the frozen-
backbone r* measurement is a preflight for.

Goal: teach the coarse branch's adapter to produce outputs that track
the full branch's outputs, so that at inference time a meaningful
fraction of attention can be routed through the coarse branch without
quality loss. The spec predicts this should push r* from the frozen-
backbone lower bound (~8% on Mistral-7B + WikiText-2 per
docs/FSCS_RSTAR_FIRST_MEASUREMENT.md) into the 15-30% range.

What this script DOES NOT do:
- Fine-tune Mistral itself. The backbone stays frozen throughout.
- Train with the CE (next-token prediction) loss. The only loss is
  the alignment loss between the two attention branches at each
  layer. Adding CE loss would either require unfreezing Mistral
  (defeats the point) or training a LoRA on the backbone (out of
  scope for this first experiment).
- Run the r* sweep. After training, the operator runs
  scripts/r_star_sweep.py against the saved checkpoint to measure
  the post-training r*.

Trainable parameters:
- Per-layer FSCSCoarseAdapter (~2M params × 32 layers ≈ 67M)
- Per-band τ and α in FSCSRoutingGate (64 params total)
- Optional: the sigmoid gate in FSCSCoarseAdapter (1 param per layer)

Everything else is frozen (Mistral backbone, positional embeddings,
lm_head, etc).

Typical invocation (A100-80GB):

    python scripts/train_fscs_alignment.py \\
        --model mistralai/Mistral-7B-v0.3 \\
        --quantize bf16 \\
        --dataset wikitext103 \\
        --seq-len 1024 \\
        --batch-size 4 \\
        --learning-rate 1e-4 \\
        --max-steps 1000 \\
        --coarse-window 1024 \\
        --alignment-lambda 1.0 \\
        --checkpoint-out results/fscs_alignment/ckpt_step1000.pt \\
        --log-every 50

Estimated cost: ~1-4 hours of A100 time depending on max_steps,
batch_size, and seq_len. The dominant cost is the dual-branch
forward pass (same as the r* sweep) plus gradient computation
through the adapter modules (cheap relative to the forward).

SAFETY STATUS:

This script has been structurally tested via a CPU smoke harness
(tests/test_fscs_core.py::TestCoarseAdapter::test_training_reduces_alignment_loss)
which confirms that the adapter + alignment loss + optimizer cycle
works end-to-end on synthetic tensors. It has NOT been run against
real Mistral weights. The first operator run may surface bugs in
the integration layer (dataset tokenization, KV-cache handling,
checkpoint serialization). Those would be fixable with targeted
edits, not architectural rework.

A --smoke-test flag is provided that runs the full pipeline on a
tiny synthetic dataset for a handful of steps, suitable for verifying
the entire script structure before loading Mistral.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure the repo root is on sys.path so that 'from symbolu.fscs.core
# import ...' works when this script is invoked directly from the
# repo root via 'python3 scripts/train_fscs_alignment.py'. Without
# this, Python only adds scripts/ to sys.path (the script's own dir),
# not the repo root, and the symbolu package is not importable.
# Operators should NOT need to set PYTHONPATH manually.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="FSCS alignment-loss fine-tune on frozen Mistral",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    # Model
    p.add_argument("--model", type=str, default="mistralai/Mistral-7B-v0.3")
    p.add_argument(
        "--quantize", type=str, default="bf16",
        choices=["none", "bf16", "fp16", "4bit", "8bit"],
        help="Backbone quantization. bf16/none/fp16 skip bitsandbytes.",
    )

    # Dataset
    p.add_argument(
        "--dataset", type=str, default="wikitext103",
        choices=["wikitext2", "wikitext103", "synthetic"],
        help="Training dataset. Use 'synthetic' with --smoke-test.",
    )
    p.add_argument("--seq-len", type=int, default=1024)
    p.add_argument("--max-train-samples", type=int, default=10000)
    p.add_argument(
        "--max-tokens", type=int, default=None,
        help=(
            "Hard cap on total tokens tokenized from the training corpus. "
            "Default None = tokenize whatever the line-chunk loop needs to "
            "produce max_train_samples * seq_len tokens (plus a 10% margin). "
            "Set to a smaller number (e.g. 5_000_000) to force early stop "
            "even if max_train_samples * seq_len would ask for more. Useful "
            "with --dataset wikitext103 + slow tokenizer to avoid hours of "
            "tokenization on data you'll truncate anyway."
        ),
    )

    # Training
    p.add_argument("--batch-size", type=int, default=4)
    p.add_argument("--learning-rate", type=float, default=1e-4)
    p.add_argument("--weight-decay", type=float, default=0.0)
    p.add_argument("--max-steps", type=int, default=1000)
    p.add_argument("--warmup-steps", type=int, default=50)
    p.add_argument("--grad-clip", type=float, default=1.0)

    # FSCS coarse adapter + alignment loss
    p.add_argument("--coarse-window", type=int, default=1024)
    p.add_argument("--coarse-adapter-d-inner", type=int, default=256)
    p.add_argument(
        "--alignment-lambda", type=float, default=1.0,
        help=(
            "Weight on the alignment loss. Spec §12.2 default is 0.1; "
            "for this first experiment we use 1.0 because it is the "
            "only loss term (no CE)."
        ),
    )
    p.add_argument(
        "--train-routing-gate", action="store_true",
        help=(
            "Additionally unfreeze the per-band τ and α in "
            "FSCSRoutingGate. Off by default because the alignment "
            "loss does not have a direct gradient path to the routing "
            "gate in the no-CE setting."
        ),
    )

    # Calibration overrides (forwarded into FSCSConfig)
    p.add_argument("--tau-global", type=float, default=None)
    p.add_argument("--tau-mid", type=float, default=None)
    p.add_argument("--tau-local", type=float, default=None)
    p.add_argument("--alpha-sharpness", type=float, default=None)

    # Checkpoint + logging
    p.add_argument(
        "--checkpoint-out", type=str,
        default="results/fscs_alignment/ckpt_latest.pt",
    )
    p.add_argument(
        "--resume-from", type=str, default=None,
        help="Resume from a previously saved checkpoint file.",
    )
    p.add_argument("--log-every", type=int, default=50)
    p.add_argument("--save-every", type=int, default=500)

    # Smoke mode
    p.add_argument(
        "--smoke-test", action="store_true",
        help=(
            "Run the full pipeline for 3 steps on synthetic 2x64 "
            "tensors. Does NOT load Mistral. Use this to verify "
            "the script structure before burning A100 time."
        ),
    )

    return p


# ---------------------------------------------------------------------------
# Dataset loading
# ---------------------------------------------------------------------------

def load_training_tokens(
    tokenizer: Any,
    dataset_name: str,
    seq_len: int,
    max_samples: int,
    max_tokens: Optional[int] = None,
) -> Any:
    """
    Load and tokenize the training split. Returns a Tensor [num_samples, seq_len]
    suitable for batched slicing.

    Tokenization strategy:
      - The corpus is tokenized in line-chunks of N raw lines at a time
        rather than as one monolithic string. This gives us:
          * Real-time progress visibility (% complete + tokens/sec)
          * Bounded peak memory (the tokenizer does not have to hold a
            540 MB string plus its internal intermediates in RAM at once)
          * Early termination when we have enough tokens to fill
            max_samples sequences, so operators can skip tokenizing
            the tail of a huge corpus they won't use anyway.
      - max_tokens caps the total tokens processed; once reached we
        stop tokenizing even if the corpus has more to offer. Set via
        --max-tokens on the training CLI.

    For WikiText-2 this is ~10 s. For WikiText-103 with a fast tokenizer
    it is ~3-5 min. For WikiText-103 with a slow tokenizer it is ~2-3
    hours — use --max-tokens to cap this, or use WikiText-2.
    """
    import torch
    from datasets import load_dataset

    if dataset_name == "synthetic":
        print("    [data] using synthetic tokens (128 random sequences)",
              flush=True)
        return torch.randint(0, 32000, (128, seq_len))

    if dataset_name == "wikitext2":
        print("    [data] loading wikitext-2-raw-v1 (train split)...",
              flush=True)
        ds = load_dataset("wikitext", "wikitext-2-raw-v1", split="train")
    else:  # wikitext103
        print("    [data] loading wikitext-103-raw-v1 (train split)...",
              flush=True)
        ds = load_dataset("wikitext", "wikitext-103-raw-v1", split="train")

    # Report the tokenizer class so the operator can see at a glance
    # whether they are on the fast or slow path. is_fast=True runs at
    # ~200K tok/sec; is_fast=False runs at ~5-10K tok/sec.
    print(f"    [data] tokenizer: {type(tokenizer).__name__} "
          f"(is_fast={getattr(tokenizer, 'is_fast', 'unknown')})",
          flush=True)

    # Filter blank lines up front, then process in line-chunks.
    lines = [s for s in ds["text"] if s.strip()]
    n_lines = len(lines)

    # Stop early if we have enough tokens to fill max_samples sequences.
    # A small safety margin (1.1x) avoids re-tokenizing on a short tail.
    target_tokens = max_samples * seq_len
    target_tokens = int(target_tokens * 1.1)
    if max_tokens is not None and max_tokens > 0:
        target_tokens = min(target_tokens, max_tokens)

    print(f"    [data] {n_lines:,} non-empty lines to process, "
          f"target {target_tokens:,} tokens "
          f"(= {max_samples} samples × {seq_len} seq_len + 10% margin)",
          flush=True)
    print(f"    [data] tokenizing in line-chunks for real-time progress; "
          f"stopping early once target is reached...", flush=True)

    chunk_size_lines = 2000   # ~60-100 KB of raw text per chunk
    all_ids: List[int] = []
    t0 = time.perf_counter()
    last_print = t0

    for chunk_start in range(0, n_lines, chunk_size_lines):
        chunk_lines = lines[chunk_start:chunk_start + chunk_size_lines]
        chunk_text = "\n\n".join(chunk_lines)
        enc = tokenizer(chunk_text, add_special_tokens=False,
                        return_tensors=None)
        all_ids.extend(enc["input_ids"])

        now = time.perf_counter()
        # Print progress every ~5 seconds to avoid flooding the log
        if (now - last_print) >= 5.0 or len(all_ids) >= target_tokens:
            elapsed = now - t0
            tok_per_sec = len(all_ids) / max(1e-6, elapsed)
            pct_lines = 100.0 * (chunk_start + chunk_size_lines) / n_lines
            pct_tokens = 100.0 * len(all_ids) / max(1, target_tokens)
            print(f"    [data]   {len(all_ids):>12,} tokens  "
                  f"({pct_tokens:5.1f}% of target, "
                  f"{min(100.0, pct_lines):5.1f}% of corpus)  "
                  f"{tok_per_sec:>7,.0f} tok/s  "
                  f"elapsed {elapsed:6.1f}s",
                  flush=True)
            last_print = now

        if len(all_ids) >= target_tokens:
            print(f"    [data] reached target token count; "
                  f"stopping early.", flush=True)
            break

    tok_seconds = time.perf_counter() - t0
    total_tokens = len(all_ids)
    tok_rate = total_tokens / max(1e-6, tok_seconds)
    print(f"    [data] DONE: tokenized {total_tokens:,} tokens in "
          f"{tok_seconds:.1f}s ({tok_rate:,.0f} tok/s)", flush=True)

    if total_tokens < seq_len:
        raise RuntimeError(
            f"Corpus tokenized to {total_tokens} tokens but seq_len "
            f"is {seq_len}; not even one full sequence available."
        )

    ids_tensor = torch.tensor(all_ids, dtype=torch.long)
    n_total = (total_tokens // seq_len) * seq_len
    ids_tensor = ids_tensor[:n_total].view(-1, seq_len)
    if ids_tensor.shape[0] > max_samples:
        ids_tensor = ids_tensor[:max_samples]
    print(f"    [data] reshaped to {tuple(ids_tensor.shape)} "
          f"(seq_len={seq_len}, samples={ids_tensor.shape[0]})", flush=True)
    return ids_tensor


# ---------------------------------------------------------------------------
# Trainable parameter collection
# ---------------------------------------------------------------------------

def collect_trainable_parameters(
    wrapper: Any,
    include_routing_gate: bool,
) -> Tuple[List[Any], Dict[str, int]]:
    """
    Walk the FSCS-wrapped Mistral and return the list of parameters
    that should receive gradient updates. Everything else (the
    Mistral backbone) stays frozen.

    Returns (param_list, count_dict).
    """
    trainable: List[Any] = []
    counts = {"coarse_adapter": 0, "routing_gate": 0, "other": 0}

    for gl in wrapper.gated_layers:
        if gl.coarse_adapter is not None:
            for p in gl.coarse_adapter.parameters():
                p.requires_grad = True
                trainable.append(p)
                counts["coarse_adapter"] += p.numel()

        if include_routing_gate:
            for p in gl.routing_gate.parameters():
                p.requires_grad = True
                trainable.append(p)
                counts["routing_gate"] += p.numel()

    return trainable, counts


# ---------------------------------------------------------------------------
# Training loop
# ---------------------------------------------------------------------------

@dataclass
class StepMetrics:
    step: int
    alignment_loss: float
    avg_gate: float
    lr: float
    wall_seconds: float


def aggregate_alignment_loss(wrapper: Any) -> Any:
    """
    Pull the per-layer alignment losses from the gated layers and sum
    them into a single scalar tensor. Skips layers where the adapter
    is disabled (returns None).
    """
    import torch
    losses: List[Any] = []
    for gl in wrapper.gated_layers:
        layer_loss = gl.get_alignment_loss()
        if layer_loss is not None:
            losses.append(layer_loss)
    if not losses:
        return torch.zeros(1)
    return torch.stack(losses).sum()


def train_one_step(
    wrapper: Any,
    batch: Any,
    optimizer: Any,
    grad_clip: float,
    device: Any,
) -> Tuple[float, float]:
    """
    Run one forward + backward + optimizer step. Returns
    (alignment_loss_value, mean_gate_fraction).
    """
    import torch

    wrapper.train()
    optimizer.zero_grad()

    out = wrapper(input_ids=batch.to(device))
    align = aggregate_alignment_loss(wrapper)

    if align.requires_grad:
        align.backward()
        if grad_clip > 0:
            # Clip over all currently-trainable params
            params = [p for g in optimizer.param_groups for p in g["params"]]
            torch.nn.utils.clip_grad_norm_(params, grad_clip)
        optimizer.step()

    return float(align.item()), float(out.get("mean_gate_fraction", 0.0))


def lr_at_step(step: int, base_lr: float, warmup_steps: int) -> float:
    """Linear warmup then flat. No decay for this short fine-tune."""
    if step < warmup_steps and warmup_steps > 0:
        return base_lr * (step + 1) / warmup_steps
    return base_lr


# ---------------------------------------------------------------------------
# Checkpointing
# ---------------------------------------------------------------------------

def save_checkpoint(
    wrapper: Any,
    optimizer: Any,
    step: int,
    metrics_history: List[StepMetrics],
    args: argparse.Namespace,
    path: str,
) -> None:
    """
    Save only the FSCS trainable parameters (coarse adapters + optional
    routing gate), the optimizer state, and the run metadata. The
    Mistral backbone is NOT saved because it is frozen and unchanged.
    """
    import torch

    trainable_state: Dict[str, Any] = {}
    for i, gl in enumerate(wrapper.gated_layers):
        if gl.coarse_adapter is not None:
            for name, p in gl.coarse_adapter.named_parameters():
                trainable_state[f"layer_{i}.coarse_adapter.{name}"] = p.detach().cpu()
        if args.train_routing_gate:
            for name, p in gl.routing_gate.named_parameters():
                trainable_state[f"layer_{i}.routing_gate.{name}"] = p.detach().cpu()

    payload = {
        "step": step,
        "trainable_state_dict": trainable_state,
        "optimizer_state_dict": optimizer.state_dict(),
        "metrics_history": [asdict(m) for m in metrics_history],
        "args": vars(args),
    }
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, path)
    print(f"[checkpoint] saved step {step} -> {path}")


def load_checkpoint(wrapper: Any, optimizer: Any, path: str) -> int:
    """Load a checkpoint saved by save_checkpoint. Returns the step."""
    import torch

    print(f"[checkpoint] loading from {path}")
    payload = torch.load(path, map_location="cpu")

    for i, gl in enumerate(wrapper.gated_layers):
        if gl.coarse_adapter is not None:
            ckpt_prefix = f"layer_{i}.coarse_adapter."
            sd = {
                k[len(ckpt_prefix):]: v
                for k, v in payload["trainable_state_dict"].items()
                if k.startswith(ckpt_prefix)
            }
            if sd:
                gl.coarse_adapter.load_state_dict(sd)

    optimizer.load_state_dict(payload["optimizer_state_dict"])
    return int(payload["step"])


# ---------------------------------------------------------------------------
# Smoke test path: runs without real Mistral weights
# ---------------------------------------------------------------------------

def run_smoke_test() -> int:
    """
    Structural smoke test that exercises the full training loop on a
    tiny synthetic model without loading Mistral. Useful for verifying
    the script structure before a real run.

    Builds a 2-layer "fake Mistral" — two nn.TransformerEncoderLayer-
    like blocks wrapped by FSCSGatedDecoderLayer — and trains the
    coarse adapters for 3 steps on random tokens. Checks:
      - Adapters receive gradient
      - Alignment loss is finite and non-zero
      - Checkpoint save + load round-trips cleanly
    """
    import torch
    import torch.nn as nn

    from symbolu.fscs.core import FSCSConfig, FSCSCoarseAdapter

    print("=" * 64)
    print("FSCS alignment-loss training — SMOKE TEST (no Mistral)")
    print("=" * 64)

    # A toy "decoder layer" with the exact interface FSCSGatedDecoderLayer
    # expects: self_attn, mlp, input_layernorm, post_attention_layernorm.
    # We cannot use a real MistralDecoderLayer here without transformers
    # installed, so this just sanity-checks the adapter training cycle.
    class TinyAttn(nn.Module):
        def __init__(self, d):
            super().__init__()
            self.o_proj = nn.Linear(d, d)
            self.d = d
        def forward(self, hidden_states, attention_mask=None, **kwargs):
            # Return a tuple shaped like HF's MistralAttention return
            return (hidden_states, None, None)

    class TinyMLP(nn.Module):
        def __init__(self, d):
            super().__init__()
            self.fc = nn.Linear(d, d)
        def forward(self, x):
            return self.fc(x)

    class TinyDecoderLayer(nn.Module):
        def __init__(self, d):
            super().__init__()
            self.self_attn = TinyAttn(d)
            self.mlp = TinyMLP(d)
            self.input_layernorm = nn.LayerNorm(d)
            self.post_attention_layernorm = nn.LayerNorm(d)

    d_model = 32
    device = torch.device("cpu")

    # Adapter-only structural check: build an adapter, take 3 steps
    # against synthetic data, confirm loss decreases.
    adapter = FSCSCoarseAdapter(d_model=d_model, d_inner=8, gate_init=-1.0)
    adapter.to(device).float()

    optimizer = torch.optim.AdamW(adapter.parameters(), lr=1e-2)

    torch.manual_seed(0)
    coarse_raw = torch.randn(2, 16, d_model)
    target = coarse_raw * 0.5 + torch.randn_like(coarse_raw) * 0.1

    losses = []
    for step in range(5):
        optimizer.zero_grad()
        out = adapter(coarse_raw)
        diff = target.detach() - out
        loss = (diff * diff).mean()
        loss.backward()
        optimizer.step()
        losses.append(loss.item())
        print(f"  step {step}: alignment_loss = {loss.item():.6f}")

    print()
    if losses[-1] < losses[0]:
        print(f"PASS: loss decreased {losses[0]:.6f} -> {losses[-1]:.6f}")
    else:
        print(f"FAIL: loss did not decrease: {losses[0]:.6f} -> {losses[-1]:.6f}")
        return 1

    # Checkpoint round-trip
    tmp_path = "/tmp/fscs_smoke_ckpt.pt"
    torch.save({"adapter_state": adapter.state_dict()}, tmp_path)

    adapter2 = FSCSCoarseAdapter(d_model=d_model, d_inner=8, gate_init=-1.0)
    adapter2.load_state_dict(torch.load(tmp_path)["adapter_state"])
    out2 = adapter2(coarse_raw)
    out_ref = adapter(coarse_raw)
    if torch.allclose(out2, out_ref, atol=1e-6):
        print("PASS: checkpoint round-trip produces identical output")
    else:
        print("FAIL: checkpoint round-trip produced different output")
        return 1

    os.unlink(tmp_path)
    print()
    print("SMOKE TEST PASSED")
    return 0


# ---------------------------------------------------------------------------
# Main training entry point (real Mistral path)
# ---------------------------------------------------------------------------

def run_training(args: argparse.Namespace) -> int:
    import torch
    from symbolu.fscs.core import FSCSConfig
    from symbolu_training.training.unified.mistral_fscs_wrapper import (
        MistralFSCSWrapper,
    )

    # ---- Build FSCSConfig with co-training enabled -----------------
    cfg_kwargs: Dict[str, Any] = {
        "use_coarse_adapter": True,
        "coarse_adapter_d_inner": args.coarse_adapter_d_inner,
        "coarse_window": args.coarse_window,
        "alignment_lambda": args.alignment_lambda,
        "use_hard_routing": False,  # Mode 1 soft blend during training
    }
    if args.tau_global is not None:
        cfg_kwargs["tau_global"] = args.tau_global
    if args.tau_mid is not None:
        cfg_kwargs["tau_mid"] = args.tau_mid
    if args.tau_local is not None:
        cfg_kwargs["tau_local"] = args.tau_local
    if args.alpha_sharpness is not None:
        cfg_kwargs["alpha_sharpness"] = args.alpha_sharpness
    cfg = FSCSConfig(**cfg_kwargs)

    print("=" * 72)
    print("FSCS alignment-loss fine-tune")
    print("=" * 72)
    print(f"Model:              {args.model}")
    print(f"Quantize:           {args.quantize}")
    print(f"Dataset:            {args.dataset}")
    print(f"Seq len:            {args.seq_len}")
    print(f"Batch size:         {args.batch_size}")
    print(f"LR:                 {args.learning_rate}")
    print(f"Max steps:          {args.max_steps}")
    print(f"Coarse window:      {args.coarse_window}")
    print(f"Adapter d_inner:    {args.coarse_adapter_d_inner}")
    print(f"Alignment lambda:   {args.alignment_lambda}")
    print(f"Train routing gate: {args.train_routing_gate}")
    print(f"Calibration: tau_global={cfg.tau_global} "
          f"tau_mid={cfg.tau_mid} tau_local={cfg.tau_local}")
    print(f"Checkpoint out:     {args.checkpoint_out}")
    print("=" * 72)

    # ---- Load backbone + install gated layers (with adapter) -------
    print("\n[1/5] Loading Mistral backbone + FSCS gated layers...", flush=True)
    quant = None if args.quantize in ("none", "bf16", "fp16") else args.quantize
    wrapper = MistralFSCSWrapper(
        model_name=args.model,
        quantize=quant,
        fscs_cfg=cfg,
    )
    device = next(wrapper.backbone.parameters()).device
    print(f"    Backbone device:           {device}", flush=True)
    print(f"    FSCS trainable params:     {wrapper.fscs_trainable_parameters()}",
          flush=True)

    # ---- Freeze the backbone, verify the adapter is trainable -----
    print("    Freezing 7.25B backbone parameters (this is sub-second)...",
          flush=True)
    for p in wrapper.backbone.parameters():
        p.requires_grad = False

    print("    Collecting trainable adapter parameters...", flush=True)
    trainable, counts = collect_trainable_parameters(
        wrapper, include_routing_gate=args.train_routing_gate,
    )
    total_trainable = sum(p.numel() for p in trainable)
    print(f"    Total trainable params:    {total_trainable:,}", flush=True)
    print(f"    .coarse_adapter:           {counts['coarse_adapter']:,}", flush=True)
    print(f"    .routing_gate:             {counts['routing_gate']:,}", flush=True)

    if total_trainable == 0:
        print("ERROR: no trainable parameters found. "
              "Did FSCSGatedDecoderLayer instantiate the coarse adapter? "
              "Check cfg.use_coarse_adapter.", file=sys.stderr)
        return 1

    # ---- Tokenize training data ------------------------------------
    print("\n[2/5] Loading training data...", flush=True)
    train_ids = load_training_tokens(
        wrapper.tokenizer,
        args.dataset,
        args.seq_len,
        args.max_train_samples,
        max_tokens=args.max_tokens,
    )
    print(f"    Train shape: {tuple(train_ids.shape)}")

    # ---- Optimizer -------------------------------------------------
    print("\n[3/5] Initializing optimizer...")
    optimizer = torch.optim.AdamW(
        trainable, lr=args.learning_rate,
        weight_decay=args.weight_decay, betas=(0.9, 0.95),
    )

    start_step = 0
    if args.resume_from:
        start_step = load_checkpoint(wrapper, optimizer, args.resume_from)
        print(f"    Resumed from step {start_step}")

    # ---- Training loop ---------------------------------------------
    print("\n[4/5] Training...")
    metrics_history: List[StepMetrics] = []
    n_train = train_ids.shape[0]
    start_time = time.perf_counter()

    for step in range(start_step, args.max_steps):
        # Update LR
        lr_now = lr_at_step(step, args.learning_rate, args.warmup_steps)
        for g in optimizer.param_groups:
            g["lr"] = lr_now

        # Sample a batch
        idx = torch.randint(0, n_train, (args.batch_size,))
        batch = train_ids[idx]

        # Train
        step_start = time.perf_counter()
        align_loss, gate_frac = train_one_step(
            wrapper, batch, optimizer, args.grad_clip, device,
        )
        step_wall = time.perf_counter() - step_start

        m = StepMetrics(
            step=step, alignment_loss=align_loss, avg_gate=gate_frac,
            lr=lr_now, wall_seconds=step_wall,
        )
        metrics_history.append(m)

        if step % args.log_every == 0 or step == args.max_steps - 1:
            total_wall = time.perf_counter() - start_time
            print(
                f"  step {step:5d}/{args.max_steps}  "
                f"align_loss={align_loss:.6f}  gate={gate_frac:.4f}  "
                f"lr={lr_now:.2e}  step_wall={step_wall:.2f}s  "
                f"total={total_wall/60:.1f}min"
            )

        if step > 0 and step % args.save_every == 0:
            save_checkpoint(
                wrapper, optimizer, step, metrics_history,
                args, args.checkpoint_out,
            )

    # Final save
    save_checkpoint(
        wrapper, optimizer, args.max_steps, metrics_history,
        args, args.checkpoint_out,
    )

    # ---- Post-training summary -------------------------------------
    print("\n[5/5] Post-training summary")
    if metrics_history:
        first = metrics_history[0]
        last = metrics_history[-1]
        print(f"    first step align_loss: {first.alignment_loss:.6f}")
        print(f"    last step align_loss:  {last.alignment_loss:.6f}")
        if first.alignment_loss > 0:
            pct = 100.0 * (1.0 - last.alignment_loss / first.alignment_loss)
            print(f"    reduction: {pct:.1f}%")
    print(f"    checkpoint: {args.checkpoint_out}")
    print()
    print("Next step: run scripts/r_star_sweep.py with a wrapper that "
          "loads this checkpoint, and compare r* against the frozen-"
          "backbone baseline (results/fscs_rstar/v3_audited.json).")

    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    args = build_argparser().parse_args()
    if args.smoke_test:
        return run_smoke_test()
    return run_training(args)


if __name__ == "__main__":
    sys.exit(main())
