#!/usr/bin/env python3
"""
Stage 9 — Post-Training Attention Mechanism Ablation Audit (F.14)
=================================================================

Standalone script to run the 8-configuration ablation matrix on a trained
checkpoint. Produces a report with PPL, attention entropy, token change rate,
and hidden state perturbation for each configuration.

Usage:
    python scripts/run_ablation_audit.py \
        --checkpoint checkpoints_mistral_cg/best.pt \
        --model_type mistral_cg \
        --dataset wikitext103 \
        --batch_size 4 \
        --max_seq_len 512 \
        --output ablation_report.json

Prerequisites (per F.14.1):
    - First convergence plateau reached
    - Stable validation perplexity established
    - Generation quality is reasonable
    - Typically at 10-20% of planned training steps, or after first LR decay
"""

import argparse
import os
import sys
import math
import json

import torch

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from symbolu.training.conscious_generation.ablation import (
    AttentionAblationConfig,
    AblationRunner,
    ABLATION_MATRIX,
)


def build_eval_fn(config, tokenizer, dataset):
    """Build an evaluation function compatible with AblationRunner."""

    def eval_fn(model, dataloader, device):
        model.eval()
        total_loss = 0.0
        total_tokens = 0
        with torch.no_grad():
            for batch in dataloader:
                if isinstance(batch, dict):
                    input_ids = batch["input_ids"].to(device)
                else:
                    input_ids = batch.to(device)

                targets = input_ids[:, 1:].contiguous()
                inputs = input_ids[:, :-1].contiguous()

                outputs = model(inputs)
                if isinstance(outputs, dict):
                    logits = outputs.get("logits", outputs.get("output"))
                else:
                    logits = outputs

                if logits is None:
                    continue

                loss = torch.nn.functional.cross_entropy(
                    logits.view(-1, logits.size(-1)),
                    targets.view(-1),
                    reduction="sum",
                )
                total_loss += loss.item()
                total_tokens += targets.numel()

        avg_loss = total_loss / max(total_tokens, 1)
        return avg_loss, None  # No attention weights captured for now

    return eval_fn


def main():
    parser = argparse.ArgumentParser(
        description="Stage 9: Post-Training Attention Mechanism Ablation Audit"
    )
    parser.add_argument("--checkpoint", type=str, required=True,
                       help="Path to trained checkpoint (e.g., checkpoints/best.pt)")
    parser.add_argument("--model_type", type=str, default="ontological_hybrid",
                       help="Model type (must match training config)")
    parser.add_argument("--dataset", type=str, default="wikitext103",
                       help="Evaluation dataset")
    parser.add_argument("--batch_size", type=int, default=4,
                       help="Evaluation batch size")
    parser.add_argument("--max_seq_len", type=int, default=512,
                       help="Max sequence length for evaluation")
    parser.add_argument("--max_eval_batches", type=int, default=50,
                       help="Max number of eval batches (0=all)")
    parser.add_argument("--output", type=str, default="ablation_report.json",
                       help="Output path for JSON report")
    parser.add_argument("--configs", type=str, nargs="*", default=None,
                       help="Subset of configs to run (by name). Default: all 8.")
    parser.add_argument("--device", type=str, default="auto",
                       help="Device (auto, cpu, cuda, cuda:0, etc.)")

    args = parser.parse_args()

    # Device selection
    if args.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(args.device)
    print(f"  Device: {device}")

    # Load model and checkpoint
    print(f"\n{'='*60}")
    print(f"  Stage 9 Ablation Audit")
    print(f"  Checkpoint: {args.checkpoint}")
    print(f"{'='*60}")

    # Import model creation from training module
    from symbolu.training.unified.train import create_model
    from symbolu.training.unified.config import UnifiedTrainingConfig
    from symbolu.training.unified.checkpointing import load_checkpoint

    config = UnifiedTrainingConfig(
        model_type=args.model_type,
        max_seq_len=args.max_seq_len,
        batch_size=args.batch_size,
    )

    model = create_model(config, device)

    # Load checkpoint weights
    from pathlib import Path
    load_result = load_checkpoint(
        path=Path(args.checkpoint),
        model=model,
        optimizer=None,
        scheduler=None,
        weights_only=True,
        device=device,
    )
    if load_result:
        step = load_result.get("step", "?")
        best_ppl = load_result.get("best_val_loss", "?")
        print(f"  Loaded checkpoint from step {step}")
    else:
        print("  WARNING: Could not load checkpoint. Running with random weights.")

    # Ensure all modules have ablation_config attribute
    from symbolu.training.conscious_generation.ablation.config import AttentionAblationConfig as AAC
    for module in model.modules():
        if hasattr(module, "ablation_config"):
            module.ablation_config = AAC.baseline()

    model.to(device)
    model.eval()

    # Build dataloader
    from symbolu.training.unified.train import load_dataset
    tokenizer = None
    if hasattr(model, "tokenizer") and model.tokenizer is not None:
        tokenizer = model.tokenizer
    train_ds, val_ds, tokenizer = load_dataset(config, tokenizer)

    val_loader = torch.utils.data.DataLoader(
        val_ds, batch_size=args.batch_size, shuffle=False, drop_last=True,
    )

    # Optionally limit eval batches
    if args.max_eval_batches > 0:
        limited_batches = []
        for i, batch in enumerate(val_loader):
            if i >= args.max_eval_batches:
                break
            limited_batches.append(batch)
        val_loader = limited_batches

    eval_fn = build_eval_fn(config, tokenizer, val_loader)

    # Filter configs if requested
    configs = ABLATION_MATRIX
    if args.configs:
        configs = [(n, c) for n, c in ABLATION_MATRIX if n in args.configs]
        if not configs:
            print(f"  ERROR: No matching configs found. Available: "
                  f"{[n for n, _ in ABLATION_MATRIX]}")
            sys.exit(1)

    # Run ablation matrix
    runner = AblationRunner(model=model, eval_fn=eval_fn, device=device)
    results = runner.run_matrix(val_loader, configs=configs)

    # Print and save report
    AblationRunner.print_report(results)
    AblationRunner.save_report(results, args.output)


if __name__ == "__main__":
    main()
