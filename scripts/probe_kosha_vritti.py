#!/usr/bin/env python3
"""
Kosha-Vritti Probe Validation Script (Section 10)
===================================================

Standalone script to validate that the base model's hidden states
contain separable Kosha/Vritti information.

Steps:
1. Freeze the base model
2. Train a linear probe on hidden states
3. Predict Kosha (4-class) and Vritti (5-class) from frozen features
4. Report token-level KL divergence and accuracy
5. Abort if separability < 70%

Usage:
    python scripts/probe_kosha_vritti.py \\
        --checkpoint checkpoints_unified/best.pt \\
        --model_type ontological_hybrid \\
        --model_size small \\
        --dataset wikitext103 \\
        --max_samples 5000 \\
        --epochs 20 \\
        --min_accuracy 0.70

Author: SymbolU Team
Date: February 2026
"""

import argparse
import math
import sys
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def extract_hidden_states(
    model,
    dataloader,
    device,
    max_samples: int = 5000,
    tokenizer=None,
):
    """
    Extract hidden states and generate teacher labels from a frozen model.

    Returns:
        hidden_all: [N, hidden_dim] concatenated hidden states
        kosha_labels: [N, 4] soft Kosha teacher labels
        vritti_labels: [N, 5] soft Vritti teacher labels
    """
    from symbolu.training.kosha_vritti_supervision import (
        KoshaVrittiSupervisionConfig,
        KoshaVrittiTeacherLabeler,
    )

    config = KoshaVrittiSupervisionConfig(
        default_kosha_dist="heuristic",
        default_vritti_dist="heuristic",
    )
    labeler = KoshaVrittiTeacherLabeler(config, tokenizer=tokenizer)

    model.eval()
    all_hidden = []
    all_k_labels = []
    all_v_labels = []
    total_tokens = 0

    with torch.no_grad():
        for batch in dataloader:
            if total_tokens >= max_samples:
                break

            if isinstance(batch, dict):
                x = batch["input_ids"].to(device)
            elif isinstance(batch, (list, tuple)):
                x = batch[0].to(device)
            else:
                x = batch.to(device)

            if x.dim() == 1:
                x = x.unsqueeze(0)

            # Forward pass
            outputs = model(x)

            # Extract hidden states - try various output formats
            hidden = None
            if isinstance(outputs, dict):
                hidden = outputs.get('hidden_states', None)
                if hidden is None:
                    # Try to get from last layer
                    hidden = outputs.get('last_hidden_state', None)
                if hidden is None and 'logits' in outputs:
                    # Some models return logits but also store hidden states
                    for key in ['encoder_last_hidden_state', 'decoder_hidden_states']:
                        hidden = outputs.get(key, None)
                        if hidden is not None:
                            break
            elif isinstance(outputs, (list, tuple)):
                # (logits, hidden_states) format
                if len(outputs) >= 2 and isinstance(outputs[1], torch.Tensor):
                    hidden = outputs[1]
                elif len(outputs) >= 2 and isinstance(outputs[1], (list, tuple)):
                    hidden = outputs[1][-1]  # Last layer

            if hidden is None:
                print(f"  WARNING: Could not extract hidden states from model output.")
                print(f"  Output type: {type(outputs)}")
                if isinstance(outputs, dict):
                    print(f"  Output keys: {list(outputs.keys())}")
                print(f"  Trying hook-based extraction...")
                hidden = _extract_via_hooks(model, x)

            if hidden is None:
                print(f"  FATAL: Could not extract hidden states. Aborting.")
                return None, None, None

            # hidden shape should be [B, T, D]
            if hidden.dim() == 4:
                hidden = hidden[:, -1]  # Take last layer if [B, L, T, D]

            B, T, D = hidden.shape

            # Generate teacher labels
            p_k, p_v, _ = labeler.generate_labels(x)

            # Flatten [B, T, ...] -> [B*T, ...]
            all_hidden.append(hidden.reshape(-1, D).cpu())
            all_k_labels.append(p_k.reshape(-1, p_k.shape[-1]).cpu())
            all_v_labels.append(p_v.reshape(-1, p_v.shape[-1]).cpu())

            total_tokens += B * T

    print(f"  Extracted {total_tokens:,} token representations")

    hidden_all = torch.cat(all_hidden, dim=0)[:max_samples]
    kosha_all = torch.cat(all_k_labels, dim=0)[:max_samples]
    vritti_all = torch.cat(all_v_labels, dim=0)[:max_samples]

    return hidden_all, kosha_all, vritti_all


def _extract_via_hooks(model, x):
    """Fallback: extract hidden states via forward hooks."""
    captured = {}

    def hook_fn(module, input, output):
        if isinstance(output, torch.Tensor):
            captured['hidden'] = output
        elif isinstance(output, tuple) and len(output) > 0:
            captured['hidden'] = output[0]

    # Find last transformer layer
    target = None
    for name, module in model.named_modules():
        if any(keyword in name for keyword in ['layers', 'blocks', 'encoder']):
            if isinstance(module, nn.ModuleList):
                target = module[-1]  # Last layer
                break

    if target is None:
        # Try norm layer (usually right before lm_head)
        for name, module in model.named_modules():
            if 'norm' in name.lower() and 'ln' in name.lower() or 'final' in name.lower():
                target = module
                break

    if target is None:
        return None

    handle = target.register_forward_hook(hook_fn)
    try:
        with torch.no_grad():
            model(x)
    finally:
        handle.remove()

    return captured.get('hidden', None)


def train_probe(
    hidden: torch.Tensor,  # [N, D]
    labels: torch.Tensor,  # [N, C] soft labels
    num_classes: int,
    epochs: int = 20,
    lr: float = 1e-3,
    batch_size: int = 256,
    device: str = 'cpu',
    name: str = 'probe',
):
    """
    Train a linear probe and evaluate.

    Returns:
        accuracy: Hard accuracy (argmax match)
        kl_div: Mean KL divergence from probe predictions to teacher labels
        probe: Trained probe module
    """
    N, D = hidden.shape

    # Split train/val (80/20)
    split = int(0.8 * N)
    train_h, val_h = hidden[:split], hidden[split:]
    train_l, val_l = labels[:split], labels[split:]

    # Create datasets
    train_ds = TensorDataset(train_h, train_l)
    val_ds = TensorDataset(val_h, val_l)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

    # Linear probe
    probe = nn.Linear(D, num_classes).to(device)
    optimizer = torch.optim.Adam(probe.parameters(), lr=lr)

    best_acc = 0.0
    best_kl = float('inf')

    for epoch in range(epochs):
        # Train
        probe.train()
        for h_batch, l_batch in train_loader:
            h_batch = h_batch.to(device)
            l_batch = l_batch.to(device)

            logits = probe(h_batch)
            log_probs = F.log_softmax(logits, dim=-1)

            # KL(teacher || probe)
            loss = F.kl_div(log_probs, l_batch, reduction='batchmean')

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

        # Evaluate
        probe.eval()
        correct = 0
        total = 0
        total_kl = 0.0

        with torch.no_grad():
            for h_batch, l_batch in val_loader:
                h_batch = h_batch.to(device)
                l_batch = l_batch.to(device)

                logits = probe(h_batch)
                log_probs = F.log_softmax(logits, dim=-1)

                kl = F.kl_div(log_probs, l_batch, reduction='batchmean')
                total_kl += kl.item() * h_batch.shape[0]

                pred = logits.argmax(dim=-1)
                target = l_batch.argmax(dim=-1)
                correct += (pred == target).sum().item()
                total += h_batch.shape[0]

        acc = correct / total if total > 0 else 0.0
        avg_kl = total_kl / total if total > 0 else float('inf')

        if acc > best_acc:
            best_acc = acc
            best_kl = avg_kl

        if (epoch + 1) % 5 == 0 or epoch == 0:
            print(f"    [{name}] Epoch {epoch+1:3d}/{epochs}: "
                  f"Acc={acc:.4f} KL={avg_kl:.4f}")

    return best_acc, best_kl, probe


def main():
    parser = argparse.ArgumentParser(
        description='Kosha-Vritti Probe Validation'
    )
    parser.add_argument('--checkpoint', type=str, required=True,
                        help='Path to model checkpoint')
    parser.add_argument('--model_type', type=str, default='ontological_hybrid',
                        help='Model architecture type')
    parser.add_argument('--model_size', type=str, default='small',
                        help='Model size preset')
    parser.add_argument('--dataset', type=str, default='wikitext103',
                        help='Dataset for evaluation')
    parser.add_argument('--max_samples', type=int, default=5000,
                        help='Max token samples to extract')
    parser.add_argument('--epochs', type=int, default=20,
                        help='Probe training epochs')
    parser.add_argument('--min_accuracy', type=float, default=0.70,
                        help='Minimum separability threshold (abort below)')
    parser.add_argument('--device', type=str, default='auto',
                        help='Device (auto/cpu/cuda)')
    parser.add_argument('--batch_size', type=int, default=8,
                        help='Batch size for data loading')
    parser.add_argument('--max_seq_len', type=int, default=512,
                        help='Max sequence length')
    args = parser.parse_args()

    print("=" * 70)
    print("  KOSHA-VRITTI PROBE VALIDATION")
    print("=" * 70)

    # Device
    if args.device == 'auto':
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    else:
        device = torch.device(args.device)
    print(f"  Device: {device}")

    # Load model
    print(f"\n  Loading checkpoint: {args.checkpoint}")
    from train_unified_llm import UnifiedTrainingConfig, create_model

    config = UnifiedTrainingConfig()
    config.model_type = args.model_type
    config.model_size = args.model_size
    config.max_seq_len = args.max_seq_len
    config.batch_size = args.batch_size
    config.dataset = args.dataset

    model = create_model(config, device)

    # Load weights
    ckpt = torch.load(args.checkpoint, map_location=device, weights_only=False)
    if 'model_state_dict' in ckpt:
        model.load_state_dict(ckpt['model_state_dict'], strict=False)
    elif 'model' in ckpt:
        model.load_state_dict(ckpt['model'], strict=False)
    else:
        model.load_state_dict(ckpt, strict=False)

    model.eval()
    model.to(device)

    num_params = sum(p.numel() for p in model.parameters())
    print(f"  Model: {args.model_type} ({args.model_size}), {num_params/1e6:.1f}M params")

    # Load tokenizer
    try:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained("gpt2")
    except ImportError:
        tokenizer = None
        print("  WARNING: transformers not available, using no tokenizer")

    # Load data
    print(f"\n  Loading dataset: {args.dataset}")
    from train_unified_llm import load_data
    _, val_loader = load_data(config, tokenizer)

    # Extract hidden states
    print(f"\n  Extracting hidden states (max {args.max_samples:,} tokens)...")
    hidden, kosha_labels, vritti_labels = extract_hidden_states(
        model, val_loader, device,
        max_samples=args.max_samples,
        tokenizer=tokenizer,
    )

    if hidden is None:
        print("\n  FATAL: Failed to extract hidden states. Cannot run probes.")
        sys.exit(1)

    print(f"  Hidden shape: {hidden.shape}")
    print(f"  Kosha labels shape: {kosha_labels.shape}")
    print(f"  Vritti labels shape: {vritti_labels.shape}")

    # Probe device (cpu for small probes is fine)
    probe_device = 'cpu'

    # Train Kosha probe
    print(f"\n  Training Kosha probe (4-class)...")
    kosha_acc, kosha_kl, _ = train_probe(
        hidden, kosha_labels,
        num_classes=4,
        epochs=args.epochs,
        device=probe_device,
        name='Kosha',
    )

    # Train Vritti probe
    print(f"\n  Training Vritti probe (5-class)...")
    vritti_acc, vritti_kl, _ = train_probe(
        hidden, vritti_labels,
        num_classes=5,
        epochs=args.epochs,
        device=probe_device,
        name='Vritti',
    )

    # Results
    print(f"\n{'=' * 70}")
    print(f"  PROBE RESULTS")
    print(f"{'=' * 70}")
    print(f"  Kosha  (4-class): Accuracy={kosha_acc:.4f}  KL={kosha_kl:.4f}")
    print(f"  Vritti (5-class): Accuracy={vritti_acc:.4f}  KL={vritti_kl:.4f}")
    print(f"  Min threshold:    {args.min_accuracy:.2f}")

    # Check separability
    mean_acc = (kosha_acc + vritti_acc) / 2
    print(f"  Mean accuracy:    {mean_acc:.4f}")

    if mean_acc < args.min_accuracy:
        print(f"\n  FAIL: Separability {mean_acc:.4f} < {args.min_accuracy:.2f}")
        print(f"  The model's hidden states do not contain sufficient")
        print(f"  Kosha/Vritti structure for auxiliary supervision.")
        print(f"  Consider training longer before enabling KV supervision.")
        sys.exit(1)
    else:
        print(f"\n  PASS: Separability {mean_acc:.4f} >= {args.min_accuracy:.2f}")
        print(f"  Hidden states contain adequate Kosha/Vritti structure.")

    print(f"{'=' * 70}")


if __name__ == '__main__':
    main()
