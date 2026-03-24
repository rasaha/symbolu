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
        --max_seq_len 2048 \
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
    """Build an evaluation function compatible with AblationRunner.

    Returns (avg_loss, cg_diagnostics_dict) where cg_diagnostics contains:
      - hidden_states: list of [B, T, D] tensors from each batch
      - adapter_gate: mean gate value across batches
      - adapter_output_norm: mean adapter output norm
      - state_norm: mean sovereign state L2 norm
      - delta_S_norm: mean state delta norm
    """

    def eval_fn(model, dataloader, device):
        model.eval()
        total_loss = 0.0
        total_tokens = 0
        # CG diagnostics accumulators
        gate_sum = 0.0
        adapter_norm_sum = 0.0
        state_norm_sum = 0.0
        delta_s_norm_sum = 0.0
        n_batches = 0
        hidden_states_sample = []  # Keep a few for hidden state delta
        MAX_HIDDEN_SAMPLES = 5  # Don't OOM — keep only a few batches

        with torch.no_grad():
            for batch in dataloader:
                # TextDataset returns (inputs, targets) tuple
                if isinstance(batch, (list, tuple)) and len(batch) == 2:
                    inputs = batch[0].to(device)
                    targets = batch[1].to(device)
                elif isinstance(batch, dict):
                    input_ids = batch["input_ids"].to(device)
                    targets = input_ids[:, 1:].contiguous()
                    inputs = input_ids[:, :-1].contiguous()
                else:
                    input_ids = batch.to(device)
                    targets = input_ids[:, 1:].contiguous()
                    inputs = input_ids[:, :-1].contiguous()

                try:
                    outputs = model(inputs, return_last_hidden=True)
                except TypeError:
                    outputs = model(inputs)
                if isinstance(outputs, dict):
                    logits = outputs.get("logits", outputs.get("output"))
                    # Capture CG diagnostics from model output
                    if "adapter_gate" in outputs:
                        gate_val = outputs["adapter_gate"]
                        gate_sum += gate_val if isinstance(gate_val, (int, float)) else gate_val.item()
                    if "adapter_output_norm" in outputs:
                        norm_val = outputs["adapter_output_norm"]
                        adapter_norm_sum += norm_val if isinstance(norm_val, (int, float)) else norm_val.item()
                    if "state" in outputs and outputs["state"] is not None:
                        state_norm_sum += outputs["state"].detach().norm(dim=-1).mean().item()
                    if "delta_S" in outputs and outputs["delta_S"] is not None:
                        delta_s_norm_sum += outputs["delta_S"].detach().norm(dim=-1).mean().item()
                    # Capture hidden states for HiddenΔ comparison
                    if "last_hidden_state" in outputs and len(hidden_states_sample) < MAX_HIDDEN_SAMPLES:
                        hidden_states_sample.append(outputs["last_hidden_state"].detach().cpu())
                    elif len(hidden_states_sample) < MAX_HIDDEN_SAMPLES:
                        # If model doesn't return last_hidden_state, compute from logits shape
                        pass
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
                n_batches += 1

        avg_loss = total_loss / max(total_tokens, 1)

        # Build CG diagnostics dict
        cg_diag = None
        if n_batches > 0:
            cg_diag = {
                "adapter_gate": gate_sum / n_batches,
                "adapter_output_norm": adapter_norm_sum / n_batches,
                "state_norm": state_norm_sum / n_batches,
                "delta_S_norm": delta_s_norm_sum / n_batches,
            }
            if hidden_states_sample:
                cg_diag["hidden_states"] = torch.cat(hidden_states_sample, dim=0)

        return avg_loss, cg_diag

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
    parser.add_argument("--max_seq_len", type=int, default=None,
                       help="Max sequence length (auto-detected from checkpoint, or 2048 fallback)")
    parser.add_argument("--max_eval_batches", type=int, default=50,
                       help="Max number of eval batches (0=all)")
    parser.add_argument("--output", type=str, default="ablation_report.json",
                       help="Output path for JSON report")
    parser.add_argument("--configs", type=str, nargs="*", default=None,
                       help="Subset of configs to run (by name). Default: all 8.")
    parser.add_argument("--device", type=str, default="auto",
                       help="Device (auto, cpu, cuda, cuda:0, etc.)")
    # Mistral CG options (must match training config)
    parser.add_argument("--mistral_model_name", type=str, default="mistralai/Mistral-7B-v0.3",
                       help="HuggingFace model ID for Mistral backbone")
    parser.add_argument("--mistral_quantize", type=str, default="none",
                       choices=["none", "4bit", "8bit"],
                       help="Quantization for Mistral backbone (match training)")

    args = parser.parse_args()

    # Device selection
    if args.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(args.device)
    print(f"  Device: {device}")

    # Import model creation from training module
    from symbolu.training.unified.train import create_model
    from symbolu.training.unified.config import UnifiedTrainingConfig
    from symbolu.training.unified.checkpointing import load_checkpoint
    from pathlib import Path

    # ── Auto-detect training config from checkpoint ───────────────────
    # Peek at checkpoint metadata to extract seq_len, model_type, etc.
    # so the ablation audit uses the same settings as training.
    ckpt_path = Path(args.checkpoint)
    ckpt_stem = ckpt_path.parent / ckpt_path.stem
    meta_path = Path(f"{ckpt_stem}_meta.pt")
    ckpt_training_config = None
    ckpt_step = None
    if meta_path.exists():
        _meta = torch.load(meta_path, map_location="cpu", weights_only=False)
        ckpt_training_config = _meta.get("training_config", None)
        ckpt_step = _meta.get("step", None)
        del _meta

    # Resolve sequence length: CLI explicit > checkpoint > fallback 2048
    user_explicit = args.max_seq_len is not None
    if user_explicit:
        effective_seq_len = args.max_seq_len
        seq_source = "CLI"
    elif ckpt_training_config is not None and ckpt_training_config.get("max_seq_len"):
        effective_seq_len = ckpt_training_config["max_seq_len"]
        seq_source = "checkpoint"
        print(f"  Auto-detected max_seq_len={effective_seq_len} from checkpoint")
    else:
        effective_seq_len = 2048
        seq_source = "default"
        print(f"  No training_config in checkpoint — using fallback max_seq_len=2048")

    # Print header
    print(f"\n{'='*60}")
    print(f"  Stage 9 Ablation Audit")
    print(f"  Checkpoint: {args.checkpoint}")
    if ckpt_step is not None:
        print(f"  Checkpoint step: {ckpt_step}"
              f"{'  !! WARNING: step 0 — CG adapter may not be trained' if ckpt_step == 0 else ''}")
    print(f"  Sequence length: {effective_seq_len} (from {seq_source})")
    print(f"  Eval batches: {args.max_eval_batches} x {args.batch_size}")
    print(f"{'='*60}")

    config = UnifiedTrainingConfig(
        model_type=args.model_type,
        max_seq_len=effective_seq_len,
        batch_size=args.batch_size,
        mistral_model_name=args.mistral_model_name,
        mistral_quantize=args.mistral_quantize,
    )

    model = create_model(config, device)

    # Load checkpoint weights
    load_result = load_checkpoint(
        path=ckpt_path,
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

    # Match ALL non-backbone params to backbone dtype (bf16)
    # This covers nn.Parameters like adapter_gate that aren't inside child modules
    if hasattr(model, 'backbone'):
        backbone_dtype = next(model.backbone.parameters()).dtype
        for name, param in model.named_parameters():
            if not name.startswith('backbone.') and param.dtype != backbone_dtype:
                param.data = param.data.to(dtype=backbone_dtype)
        print(f"  Trainable parameters cast to {backbone_dtype}")

    # Ensure all modules have ablation_config attribute
    from symbolu.training.conscious_generation.ablation.config import AttentionAblationConfig as AAC
    for module in model.modules():
        if hasattr(module, "ablation_config"):
            module.ablation_config = AAC.baseline()

    model.to(device)
    model.eval()

    # Build dataloader — reuse the training pipeline's data loading
    from symbolu.training.unified.data import load_data
    tokenizer = None
    if hasattr(model, "tokenizer") and model.tokenizer is not None:
        tokenizer = model.tokenizer
        tokenizer.model_max_length = int(1e12)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        config.vocab_size = len(tokenizer)
    if tokenizer is None:
        # Fallback: use tiktoken GPT-2 tokenizer
        import tiktoken
        tokenizer = tiktoken.get_encoding("gpt2")

    config.dataset = args.dataset
    train_loader, val_loader = load_data(config, tokenizer)

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
