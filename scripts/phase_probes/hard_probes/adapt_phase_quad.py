#!/usr/bin/env python3
"""
Standalone CLI for Phase-Aware Adaptation (IA³ + Surgical LoRA).

This tool provides a dedicated interface for training, evaluating,
and managing adaptation layers on Phase Quad models.

Usage:
  # Train IA³ adaptation on a pretrained model
  python adapt_phase_quad.py train --base-checkpoint model.pt --output adapter.pt

  # Evaluate adapter quality
  python adapt_phase_quad.py eval --base-checkpoint model.pt --adapter adapter.pt

  # Merge LoRA into base weights for zero-overhead inference
  python adapt_phase_quad.py merge --base-checkpoint model.pt --adapter adapter.pt --output merged.pt

  # Show adapter summary (parameter counts, gate statistics)
  python adapt_phase_quad.py info --adapter adapter.pt

  # Run benchmark suite (no pretrained model needed)
  python adapt_phase_quad.py benchmark

  # Compare IA³-only vs LoRA-only vs Combined
  python adapt_phase_quad.py benchmark --ablation
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

from symbolu.vision.adaptation import (
    IA3Gate,
    IA3BlockGates,
    IA3Config,
    LoRALinear,
    LoRAConfig,
    AdaptationConfig,
    PhaseQuadAdaptationManager,
)
from symbolu.vision.phase_quad_dit_block import PhaseQuadDiTBlockStack
from symbolu.vision.controls import PatchMeta


# =============================================================================
# HELPERS
# =============================================================================

def make_test_meta(H_p: int = 8, W_p: int = 8, device: str = "cpu") -> PatchMeta:
    """Create PatchMeta for testing."""
    coords = torch.stack(
        torch.meshgrid(
            torch.arange(H_p), torch.arange(W_p), indexing="ij"
        ),
        dim=-1,
    ).reshape(-1, 2).to(device)
    return PatchMeta(H_p=H_p, W_p=W_p, coords=coords, patch_size=2)


def build_stack(args, device: str = "cpu") -> PhaseQuadDiTBlockStack:
    """Build a PhaseQuadDiTBlockStack from CLI args."""
    return PhaseQuadDiTBlockStack(
        num_blocks=args.num_blocks,
        embed_dim=args.embed_dim,
        num_heads=args.num_heads,
        topk=args.topk,
        window_size=args.window_size,
        ffn_ratio=args.ffn_ratio,
        use_cross_attn=False,
        use_bcvf=False,
    ).to(device)


def build_adaptation_config(args) -> AdaptationConfig:
    """Build AdaptationConfig from CLI args."""
    ia3_config = IA3Config(
        enable=args.ia3,
        gate_attention=True,
        gate_mlp=True,
        gate_quad=True,
        init_value=1.0,
        regularization_lambda=args.ia3_reg_lambda,
    )

    lora_config = LoRAConfig(
        enable=args.lora,
        rank=args.lora_rank,
        alpha=args.lora_alpha,
        dropout=args.lora_dropout,
        target_modules=args.lora_targets.split(","),
    )

    return AdaptationConfig(
        ia3=ia3_config,
        lora=lora_config,
        freeze_base=True,
    )


def format_params(n: int) -> str:
    """Format parameter count."""
    if n >= 1e6:
        return f"{n/1e6:.2f}M"
    elif n >= 1e3:
        return f"{n/1e3:.1f}K"
    return str(n)


# =============================================================================
# COMMANDS
# =============================================================================

def cmd_train(args):
    """Train adaptation layers on a pretrained Phase Quad model."""
    device = args.device
    print("=" * 70)
    print("PHASE-AWARE ADAPTATION: Training")
    print("=" * 70)

    # Build or load model
    if args.base_checkpoint and os.path.exists(args.base_checkpoint):
        print(f"\nLoading base model from: {args.base_checkpoint}")
        checkpoint = torch.load(args.base_checkpoint, map_location=device, weights_only=False)
        stack = build_stack(args, device)
        if "model_state_dict" in checkpoint:
            stack.load_state_dict(checkpoint["model_state_dict"], strict=False)
        else:
            stack.load_state_dict(checkpoint, strict=False)
        print("  Base model loaded.")
    else:
        print("\nNo base checkpoint provided. Using randomly initialized model.")
        print("  (For real adaptation, provide --base-checkpoint)")
        stack = build_stack(args, device)

    # Build adapter
    adapt_config = build_adaptation_config(args)
    adapter = PhaseQuadAdaptationManager(stack, adapt_config).to(device)

    summary = adapter.get_adaptation_summary()
    print(f"\nAdaptation Summary:")
    print(f"  Base params (frozen): {format_params(summary['base_params_frozen'])}")
    print(f"  IA3 params:           {format_params(summary['ia3_params'])}")
    print(f"  LoRA params:          {format_params(summary['lora_params'])}")
    print(f"  Total trainable:      {format_params(summary['total_trainable'])} "
          f"({summary['adaptation_ratio']:.4%})")

    # Setup training
    optimizer = torch.optim.AdamW(
        adapter.trainable_parameters(),
        lr=args.lr,
        weight_decay=args.weight_decay,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=args.train_steps, eta_min=args.lr / 100
    )

    # Training inputs (synthetic for demo)
    H_p, W_p = 8, 8
    N = H_p * W_p
    meta = make_test_meta(H_p, W_p, device)

    print(f"\nTraining for {args.train_steps} steps...")
    print(f"  Learning rate: {args.lr}")
    print(f"  Batch size:    {args.batch_size}")

    adapter.train()
    best_loss = float("inf")

    for step in range(args.train_steps):
        # Synthetic training data
        x = torch.randn(args.batch_size, N, args.embed_dim, device=device)
        t_emb = torch.randn(args.batch_size, args.embed_dim, device=device)
        timestep = torch.randint(0, 1000, (args.batch_size,), device=device)
        target = torch.randn_like(x) * 0.1

        optimizer.zero_grad()
        out = adapter(x, meta, t_emb, timestep=timestep)
        task_loss = F.mse_loss(out, target)
        reg_loss = adapter.regularization_loss()
        loss = task_loss + reg_loss
        loss.backward()

        torch.nn.utils.clip_grad_norm_(adapter.trainable_parameters(), 1.0)
        optimizer.step()
        scheduler.step()

        if loss.item() < best_loss:
            best_loss = loss.item()

        if step % max(args.train_steps // 10, 1) == 0 or step == args.train_steps - 1:
            lr_now = scheduler.get_last_lr()[0]
            print(f"  Step {step:5d} | loss={loss.item():.6f} "
                  f"(task={task_loss.item():.6f}, reg={reg_loss.item():.6f}) "
                  f"| lr={lr_now:.2e}")

    # Save adapter
    output_path = args.output or "adapter.pt"
    adapter.save_adapter(output_path)
    file_size = os.path.getsize(output_path)
    print(f"\nAdapter saved to: {output_path}")
    print(f"  File size: {file_size:,} bytes ({file_size/1024:.1f} KB)")
    print(f"  Best loss: {best_loss:.6f}")


def cmd_eval(args):
    """Evaluate an adapter on a pretrained Phase Quad model."""
    device = args.device
    print("=" * 70)
    print("PHASE-AWARE ADAPTATION: Evaluation")
    print("=" * 70)

    if not args.adapter or not os.path.exists(args.adapter):
        print(f"\nError: Adapter file not found: {args.adapter}")
        return 1

    # Build model
    stack = build_stack(args, device)

    if args.base_checkpoint and os.path.exists(args.base_checkpoint):
        print(f"\nLoading base model from: {args.base_checkpoint}")
        checkpoint = torch.load(args.base_checkpoint, map_location=device, weights_only=False)
        if "model_state_dict" in checkpoint:
            stack.load_state_dict(checkpoint["model_state_dict"], strict=False)
        else:
            stack.load_state_dict(checkpoint, strict=False)

    # Build adapter and load weights
    adapt_config = build_adaptation_config(args)
    adapter = PhaseQuadAdaptationManager(stack, adapt_config).to(device)
    adapter.load_adapter(args.adapter)
    print(f"Adapter loaded from: {args.adapter}")

    # Evaluate
    adapter.eval()
    H_p, W_p = 8, 8
    N = H_p * W_p
    meta = make_test_meta(H_p, W_p, device)

    total_loss = 0.0
    num_eval = args.eval_batches

    print(f"\nEvaluating on {num_eval} batches...")
    for i in range(num_eval):
        x = torch.randn(args.batch_size, N, args.embed_dim, device=device)
        t_emb = torch.randn(args.batch_size, args.embed_dim, device=device)
        timestep = torch.randint(0, 1000, (args.batch_size,), device=device)
        target = torch.randn_like(x) * 0.1

        with torch.no_grad():
            out = adapter(x, meta, t_emb, timestep=timestep)
            loss = F.mse_loss(out, target)
        total_loss += loss.item()

    avg_loss = total_loss / num_eval
    print(f"  Average loss: {avg_loss:.6f}")

    # Gate statistics
    print("\nGate Statistics:")
    for i, gates in enumerate(adapter.ia3_gates):
        if gates is None:
            continue
        stats = {}
        for name, module in [
            ("local_attn", gates.gate_local_attn),
            ("quad_attn", gates.gate_quad_attn),
            ("ffn", gates.gate_ffn),
        ]:
            if module is not None:
                g = module.gate.data
                stats[name] = {
                    "mean": g.mean().item(),
                    "std": g.std().item(),
                    "min": g.min().item(),
                    "max": g.max().item(),
                }
        print(f"\n  Block {i}:")
        for name, s in stats.items():
            print(f"    {name}: mean={s['mean']:.4f} std={s['std']:.4f} "
                  f"range=[{s['min']:.4f}, {s['max']:.4f}]")

    return 0


def cmd_merge(args):
    """Merge LoRA weights into base model for zero-overhead inference."""
    device = args.device
    print("=" * 70)
    print("PHASE-AWARE ADAPTATION: LoRA Merge")
    print("=" * 70)

    if not args.lora:
        print("\nError: --lora must be enabled for merge operation.")
        return 1

    if not args.base_checkpoint or not os.path.exists(args.base_checkpoint):
        print(f"\nError: Base checkpoint not found: {args.base_checkpoint}")
        return 1

    if not args.adapter or not os.path.exists(args.adapter):
        print(f"\nError: Adapter file not found: {args.adapter}")
        return 1

    # Load base model
    stack = build_stack(args, device)
    checkpoint = torch.load(args.base_checkpoint, map_location=device, weights_only=False)
    if "model_state_dict" in checkpoint:
        stack.load_state_dict(checkpoint["model_state_dict"], strict=False)
    else:
        stack.load_state_dict(checkpoint, strict=False)

    # Build adapter and load
    adapt_config = build_adaptation_config(args)
    adapter = PhaseQuadAdaptationManager(stack, adapt_config).to(device)
    adapter.load_adapter(args.adapter)

    print(f"\nBase model:  {args.base_checkpoint}")
    print(f"Adapter:     {args.adapter}")

    # Merge LoRA
    adapter.merge_lora()
    print("LoRA weights merged into base model.")

    # Save merged model
    output_path = args.output or "merged_model.pt"
    merged_state = {
        "model_state_dict": stack.state_dict(),
        "merged_from": {
            "base": args.base_checkpoint,
            "adapter": args.adapter,
        },
    }
    torch.save(merged_state, output_path)
    print(f"\nMerged model saved to: {output_path}")
    print(f"  File size: {os.path.getsize(output_path):,} bytes")
    print("\nThe merged model runs at full speed with no adaptation overhead.")

    return 0


def cmd_info(args):
    """Show adapter summary (parameter counts, gate statistics)."""
    print("=" * 70)
    print("PHASE-AWARE ADAPTATION: Adapter Info")
    print("=" * 70)

    if not args.adapter or not os.path.exists(args.adapter):
        print(f"\nError: Adapter file not found: {args.adapter}")
        return 1

    state = torch.load(args.adapter, map_location="cpu", weights_only=True)

    # Extract config
    config = state.get("config", {})
    print(f"\nAdapter file: {args.adapter}")
    print(f"  File size:  {os.path.getsize(args.adapter):,} bytes "
          f"({os.path.getsize(args.adapter)/1024:.1f} KB)")

    print(f"\nConfiguration:")
    for key, val in config.items():
        print(f"  {key}: {val}")

    # Count parameters
    ia3_keys = [k for k in state.keys() if k.startswith("ia3.")]
    lora_keys = [k for k in state.keys() if k.startswith("lora.")]

    ia3_params = sum(state[k].numel() for k in ia3_keys)
    lora_params = sum(state[k].numel() for k in lora_keys)

    print(f"\nParameters:")
    print(f"  IA3 keys:   {len(ia3_keys)}")
    print(f"  IA3 params: {format_params(ia3_params)}")
    print(f"  LoRA keys:  {len(lora_keys)}")
    print(f"  LoRA params: {format_params(lora_params)}")
    print(f"  Total:      {format_params(ia3_params + lora_params)}")

    # Gate values
    print(f"\nIA3 Gate Values:")
    for key in sorted(ia3_keys):
        tensor = state[key]
        print(f"  {key}: shape={list(tensor.shape)} "
              f"mean={tensor.mean():.4f} std={tensor.std():.4f} "
              f"range=[{tensor.min():.4f}, {tensor.max():.4f}]")

    return 0


def cmd_benchmark(args):
    """Run adaptation benchmark suite (no pretrained model needed)."""
    device = args.device
    print("=" * 70)
    print("PHASE-AWARE ADAPTATION: Benchmark Suite")
    print("=" * 70)

    # Import benchmark function from train_hard_probes
    # Or run standalone benchmarks here
    H_p, W_p = 8, 8
    N = H_p * W_p
    meta = make_test_meta(H_p, W_p, device)
    batch_size = 4

    configs_to_test = {}

    # IA³ only
    configs_to_test["ia3_only"] = AdaptationConfig(
        ia3=IA3Config(enable=True),
        lora=LoRAConfig(enable=False),
        freeze_base=True,
    )

    if args.lora or args.ablation:
        # LoRA only
        configs_to_test["lora_only"] = AdaptationConfig(
            ia3=IA3Config(enable=False),
            lora=LoRAConfig(enable=True, rank=args.lora_rank, alpha=args.lora_alpha),
            freeze_base=True,
        )
        # Combined
        configs_to_test["combined"] = AdaptationConfig(
            ia3=IA3Config(enable=True),
            lora=LoRAConfig(enable=True, rank=args.lora_rank, alpha=args.lora_alpha),
            freeze_base=True,
        )

    results = {}

    for config_name, adapt_config in configs_to_test.items():
        print(f"\n{'=' * 50}")
        print(f"  Config: {config_name}")
        print(f"{'=' * 50}")

        stack = build_stack(args, device)
        adapter = PhaseQuadAdaptationManager(stack, adapt_config).to(device)

        summary = adapter.get_adaptation_summary()
        print(f"  Trainable: {format_params(summary['total_trainable'])} "
              f"({summary['adaptation_ratio']:.4%})")

        # Train
        x = torch.randn(batch_size, N, args.embed_dim, device=device)
        t_emb = torch.randn(batch_size, args.embed_dim, device=device)
        timestep = torch.randint(0, 1000, (batch_size,), device=device)
        target = torch.randn_like(x) * 0.1

        optimizer = torch.optim.AdamW(adapter.trainable_parameters(), lr=5e-3)

        losses = []
        t_start = time.time()
        for step in range(args.train_steps):
            optimizer.zero_grad()
            out = adapter(x, meta, t_emb, timestep=timestep)
            loss = F.mse_loss(out, target) + adapter.regularization_loss()
            loss.backward()
            optimizer.step()
            losses.append(loss.item())

        train_time = time.time() - t_start

        # Throughput
        adapter.eval()
        if device == "cuda":
            torch.cuda.synchronize()

        t_start = time.time()
        for _ in range(20):
            with torch.no_grad():
                _ = adapter(x, meta, t_emb, timestep=timestep)
        if device == "cuda":
            torch.cuda.synchronize()
        infer_time = (time.time() - t_start) / 20

        results[config_name] = {
            "trainable_params": summary["total_trainable"],
            "adaptation_ratio": summary["adaptation_ratio"],
            "initial_loss": losses[0],
            "final_loss": losses[-1],
            "loss_decrease_pct": (1 - losses[-1] / losses[0]) * 100 if losses[0] > 0 else 0,
            "train_time_s": train_time,
            "inference_ms": infer_time * 1000,
        }

        print(f"  Initial loss:  {losses[0]:.6f}")
        print(f"  Final loss:    {losses[-1]:.6f} "
              f"({results[config_name]['loss_decrease_pct']:.1f}% decrease)")
        print(f"  Train time:    {train_time:.2f}s ({args.train_steps} steps)")
        print(f"  Inference:     {infer_time*1000:.2f} ms/forward")

    # Summary table
    print(f"\n{'=' * 70}")
    print("BENCHMARK SUMMARY")
    print(f"{'=' * 70}")
    print(f"\n  {'Config':<15} {'Params':>10} {'Ratio':>8} {'Loss':>10} "
          f"{'Decrease':>10} {'Train':>8} {'Infer':>10}")
    print("  " + "-" * 75)
    for name, r in results.items():
        print(f"  {name:<15} {format_params(r['trainable_params']):>10} "
              f"{r['adaptation_ratio']:>7.4%} "
              f"{r['final_loss']:>10.6f} "
              f"{r['loss_decrease_pct']:>9.1f}% "
              f"{r['train_time_s']:>7.2f}s "
              f"{r['inference_ms']:>9.2f}ms")

    # Save results
    if args.output:
        # Convert to JSON-serializable
        json_results = {}
        for k, v in results.items():
            json_results[k] = {kk: float(vv) for kk, vv in v.items()}
        with open(args.output, "w") as f:
            json.dump(json_results, f, indent=2)
        print(f"\nResults saved to: {args.output}")

    return 0


# =============================================================================
# ARGUMENT PARSER
# =============================================================================

def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        description="Phase-Aware Adaptation CLI for Phase Quad (IA3 + Surgical LoRA)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run benchmark suite
  python adapt_phase_quad.py benchmark

  # Benchmark with ablation (IA3 vs LoRA vs Combined)
  python adapt_phase_quad.py benchmark --ablation --lora

  # Train adapter on pretrained model
  python adapt_phase_quad.py train --base-checkpoint model.pt --output my_adapter.pt

  # Evaluate adapter
  python adapt_phase_quad.py eval --base-checkpoint model.pt --adapter my_adapter.pt

  # Merge LoRA into base for deployment
  python adapt_phase_quad.py merge --base-checkpoint model.pt --adapter my_adapter.pt --lora

  # Inspect adapter file
  python adapt_phase_quad.py info --adapter my_adapter.pt
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Shared arguments
    def add_common_args(sub):
        sub.add_argument("--device", type=str,
                         default="cuda" if torch.cuda.is_available() else "cpu")
        sub.add_argument("--embed-dim", type=int, default=256)
        sub.add_argument("--num-heads", type=int, default=8)
        sub.add_argument("--num-blocks", type=int, default=3)
        sub.add_argument("--topk", type=int, default=16)
        sub.add_argument("--window-size", type=int, default=4)
        sub.add_argument("--ffn-ratio", type=float, default=4.0)

    def add_adaptation_args(sub):
        sub.add_argument("--ia3", action="store_true", default=True,
                         help="Enable IA3 gates (default: True)")
        sub.add_argument("--no-ia3", dest="ia3", action="store_false")
        sub.add_argument("--ia3-reg-lambda", type=float, default=0.01)
        sub.add_argument("--lora", action="store_true",
                         help="Enable surgical LoRA on projections")
        sub.add_argument("--lora-rank", type=int, default=8)
        sub.add_argument("--lora-alpha", type=float, default=16.0)
        sub.add_argument("--lora-dropout", type=float, default=0.0)
        sub.add_argument("--lora-targets", type=str, default="W_q,W_k,W_v",
                         help="Comma-separated projection names for LoRA")

    # train
    p_train = subparsers.add_parser("train", help="Train adaptation layers")
    add_common_args(p_train)
    add_adaptation_args(p_train)
    p_train.add_argument("--base-checkpoint", type=str, default=None)
    p_train.add_argument("--output", "-o", type=str, default="adapter.pt")
    p_train.add_argument("--train-steps", type=int, default=1000)
    p_train.add_argument("--batch-size", type=int, default=4)
    p_train.add_argument("--lr", type=float, default=5e-4)
    p_train.add_argument("--weight-decay", type=float, default=0.01)

    # eval
    p_eval = subparsers.add_parser("eval", help="Evaluate an adapter")
    add_common_args(p_eval)
    add_adaptation_args(p_eval)
    p_eval.add_argument("--base-checkpoint", type=str, default=None)
    p_eval.add_argument("--adapter", type=str, required=True)
    p_eval.add_argument("--batch-size", type=int, default=4)
    p_eval.add_argument("--eval-batches", type=int, default=10)

    # merge
    p_merge = subparsers.add_parser("merge", help="Merge LoRA into base weights")
    add_common_args(p_merge)
    add_adaptation_args(p_merge)
    p_merge.add_argument("--base-checkpoint", type=str, required=True)
    p_merge.add_argument("--adapter", type=str, required=True)
    p_merge.add_argument("--output", "-o", type=str, default="merged_model.pt")

    # info
    p_info = subparsers.add_parser("info", help="Show adapter info")
    p_info.add_argument("--adapter", type=str, required=True)
    p_info.add_argument("--device", type=str, default="cpu")

    # benchmark
    p_bench = subparsers.add_parser("benchmark", help="Run benchmark suite")
    add_common_args(p_bench)
    add_adaptation_args(p_bench)
    p_bench.add_argument("--train-steps", type=int, default=100)
    p_bench.add_argument("--ablation", action="store_true",
                         help="Compare IA3-only vs LoRA-only vs Combined")
    p_bench.add_argument("--output", "-o", type=str, default=None,
                         help="Save results to JSON file")

    return parser


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        "train": cmd_train,
        "eval": cmd_eval,
        "merge": cmd_merge,
        "info": cmd_info,
        "benchmark": cmd_benchmark,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main() or 0)
