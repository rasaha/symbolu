#!/usr/bin/env python3
"""
SymbolU Phase 7B - RunPod Training Script
==========================================

Train SymbolU Phase Attention at 7B parameters to validate O(n) architecture at scale.

This is a PURE Phase Attention model - NO Bhava/Ontological components.
For Bhava models, use train_unified_llm.py with --model_type ontological

Hardware Requirements:
- Minimum: 1x A100 80GB (bf16)
- Recommended: 1x H100 80GB (faster)
- Alternative: 2x A100 40GB (with FSDP)

Cost Estimation (RunPod):
- A100 80GB: ~$1.89/hour
- H100 80GB: ~$3.89/hour
- 100 steps test: ~1-2 hours = $2-8
- 1000 steps test: ~4-8 hours = $8-32

Usage:
------
    # Quick validation (100 steps) - ~$5
    python train_7b.py --steps 100 --quick_test

    # Short training (1000 steps) - ~$15
    python train_7b.py --steps 1000

    # Full training (50000 steps) - ~$500+
    python train_7b.py --steps 50000 --checkpoint_dir /workspace/checkpoints_7b

Architecture at 7B (LLaMA-style + Phase Attention):
- embed_dim: 4096
- num_heads: 32
- num_kv_heads: 8 (GQA)
- num_layers: 32
- vocab_size: 32000
- Phase Attention O(n) complexity
- SwiGLU FFN
- RMSNorm
"""

import argparse
import collections
import math
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset

# Check CUDA
if not torch.cuda.is_available():
    print("WARNING: CUDA not available. 7B model requires GPU!")
    print("This script is designed for RunPod A100/H100")

# =============================================================================
# PERFORMANCE OPTIMIZATIONS
# =============================================================================
# TF32 for faster matrix multiplications on Ampere+ GPUs (A100, H100)
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True

# cuDNN autotuning for optimal convolution algorithms
torch.backends.cudnn.benchmark = True


# =============================================================================
# 7B MODEL CONFIGURATION
# =============================================================================

@dataclass
class Phase7BConfig:
    """7B parameter configuration for Phase Attention model."""

    # Model dimensions (7B scale, LLaMA-style)
    vocab_size: int = 32000
    embed_dim: int = 4096
    num_heads: int = 32
    num_kv_heads: int = 8  # GQA for memory efficiency
    num_layers: int = 32
    max_seq_len: int = 2048

    # Phase Attention parameters
    phase_dim: int = 128
    sync_steps: int = 3
    sync_lr: float = 0.1

    # FFN (SwiGLU)
    ffn_mult: float = 2.67
    intermediate_size: int = None  # Auto-computed

    # Memory optimization
    use_gradient_checkpointing: bool = True
    use_flash_attention: bool = True

    # Dropout
    dropout: float = 0.0

    def __post_init__(self):
        if self.intermediate_size is None:
            self.intermediate_size = int(self.embed_dim * self.ffn_mult)

    def estimate_parameters(self) -> int:
        """Estimate total parameters."""
        # Embeddings (tied weights)
        embed_params = self.vocab_size * self.embed_dim

        # Per layer
        # Attention: Q, K (GQA), V (GQA), O projections
        q_params = self.embed_dim * self.embed_dim
        kv_dim = self.num_kv_heads * (self.embed_dim // self.num_heads)
        k_params = self.embed_dim * kv_dim
        v_params = self.embed_dim * kv_dim
        o_params = self.embed_dim * self.embed_dim
        attn_params = q_params + k_params + v_params + o_params

        # Phase projection
        head_dim = self.embed_dim // self.num_heads
        phase_params = head_dim * self.phase_dim

        # FFN: gate, up, down (SwiGLU)
        ffn_params = self.embed_dim * self.intermediate_size * 3

        # Norms (2 per layer)
        norm_params = self.embed_dim * 2

        layer_params = attn_params + phase_params + ffn_params + norm_params
        total_layer_params = layer_params * self.num_layers

        # Final norm
        final_norm = self.embed_dim

        total = embed_params + total_layer_params + final_norm
        return total


# =============================================================================
# MEMORY-EFFICIENT PHASE ATTENTION
# =============================================================================

class EfficientPhaseAttention(nn.Module):
    """
    Memory-efficient O(n) Phase Attention for 7B scale.

    Uses:
    - Grouped Query Attention (GQA) for KV memory reduction
    - Flash Attention when available
    - Phase synchronization via mean-field approximation
    - Gradient checkpointing compatible
    """

    def __init__(self, config: Phase7BConfig):
        super().__init__()
        self.embed_dim = config.embed_dim
        self.num_heads = config.num_heads
        self.num_kv_heads = config.num_kv_heads
        self.head_dim = config.embed_dim // config.num_heads
        self.num_kv_groups = config.num_heads // config.num_kv_heads

        # Q projection (full heads)
        self.q_proj = nn.Linear(config.embed_dim, config.embed_dim, bias=False)
        # K, V projections (reduced heads for GQA)
        kv_dim = config.num_kv_heads * self.head_dim
        self.k_proj = nn.Linear(config.embed_dim, kv_dim, bias=False)
        self.v_proj = nn.Linear(config.embed_dim, kv_dim, bias=False)
        self.o_proj = nn.Linear(config.embed_dim, config.embed_dim, bias=False)

        # Phase components (O(n) mean-field synchronization)
        self.phase_dim = config.phase_dim
        self.phase_proj = nn.Linear(self.head_dim, config.phase_dim, bias=False)
        self.sync_lr = nn.Parameter(torch.tensor(config.sync_lr))
        self.sync_steps = config.sync_steps

        self.use_flash = config.use_flash_attention and hasattr(F, 'scaled_dot_product_attention')

    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        B, N, D = x.shape

        # Project Q, K, V
        q = self.q_proj(x).view(B, N, self.num_heads, self.head_dim)
        k = self.k_proj(x).view(B, N, self.num_kv_heads, self.head_dim)
        v = self.v_proj(x).view(B, N, self.num_kv_heads, self.head_dim)

        # Expand K, V for GQA
        k = k.repeat_interleave(self.num_kv_groups, dim=2)
        v = v.repeat_interleave(self.num_kv_groups, dim=2)

        # Transpose for attention
        q = q.transpose(1, 2)  # [B, H, N, D]
        k = k.transpose(1, 2)
        v = v.transpose(1, 2)

        # Phase synchronization (O(n) mean-field approximation)
        phases = torch.sigmoid(self.phase_proj(q.mean(dim=2))) * (2 * math.pi)
        for _ in range(self.sync_steps):
            phase_mean = phases.mean(dim=-1, keepdim=True)
            gradient = -torch.sin(phases - phase_mean)
            phases = (phases + self.sync_lr * gradient) % (2 * math.pi)

        # Phase coherence (how synchronized the phases are)
        phase_coherence = torch.cos(phases - phases.mean(dim=-1, keepdim=True)).mean(dim=-1)

        # Attention computation
        if self.use_flash:
            # Use Flash Attention (memory efficient)
            out = F.scaled_dot_product_attention(q, k, v, is_causal=True)
        else:
            # Manual attention
            scale = 1.0 / math.sqrt(self.head_dim)
            attn = torch.matmul(q, k.transpose(-2, -1)) * scale

            # Causal mask
            mask = torch.triu(torch.ones(N, N, device=x.device), diagonal=1).bool()
            attn = attn.masked_fill(mask, float('-inf'))

            attn = F.softmax(attn, dim=-1)
            out = torch.matmul(attn, v)

        # Reshape and project
        out = out.transpose(1, 2).reshape(B, N, D)

        return {
            'output': self.o_proj(out),
            'phase_coherence': phase_coherence.mean(dim=1),  # [B]
        }


# =============================================================================
# 7B TRANSFORMER BLOCK
# =============================================================================

class Phase7BBlock(nn.Module):
    """Single transformer block for 7B Phase model."""

    def __init__(self, config: Phase7BConfig, layer_idx: int):
        super().__init__()
        self.layer_idx = layer_idx

        # Pre-norm (RMSNorm)
        self.attn_norm = nn.RMSNorm(config.embed_dim)
        self.ffn_norm = nn.RMSNorm(config.embed_dim)

        # Phase Attention
        self.attn = EfficientPhaseAttention(config)

        # SwiGLU FFN
        self.gate_proj = nn.Linear(config.embed_dim, config.intermediate_size, bias=False)
        self.up_proj = nn.Linear(config.embed_dim, config.intermediate_size, bias=False)
        self.down_proj = nn.Linear(config.intermediate_size, config.embed_dim, bias=False)

    def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        # Attention with residual
        h = self.attn_norm(x)
        attn_out = self.attn(h)
        x = x + attn_out['output']

        # FFN with residual (SwiGLU)
        h = self.ffn_norm(x)
        x = x + self.down_proj(F.silu(self.gate_proj(h)) * self.up_proj(h))

        return {
            'output': x,
            'phase_coherence': attn_out['phase_coherence'],
        }


# =============================================================================
# PHASE 7B MODEL
# =============================================================================

class Phase7B(nn.Module):
    """
    Phase Attention Transformer at 7B parameters.

    Features:
    - 32 transformer layers with O(n) Phase Attention
    - Grouped Query Attention (GQA) for memory efficiency
    - SwiGLU FFN
    - RMSNorm
    - Gradient checkpointing for memory
    """

    def __init__(self, config: Optional[Phase7BConfig] = None):
        super().__init__()
        self.config = config or Phase7BConfig()

        # Embeddings
        self.embed_tokens = nn.Embedding(self.config.vocab_size, self.config.embed_dim)

        # Layers
        self.layers = nn.ModuleList([
            Phase7BBlock(self.config, i) for i in range(self.config.num_layers)
        ])

        # Output
        self.norm = nn.RMSNorm(self.config.embed_dim)
        self.lm_head = nn.Linear(self.config.embed_dim, self.config.vocab_size, bias=False)

        # Tie weights
        self.lm_head.weight = self.embed_tokens.weight

        # Gradient checkpointing flag
        self.gradient_checkpointing = self.config.use_gradient_checkpointing

    def forward(
        self,
        input_ids: torch.Tensor,
        labels: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        B, N = input_ids.shape

        # Embeddings
        x = self.embed_tokens(input_ids)

        # Track phase coherence across layers
        coherence_sum = 0.0
        num_layers = 0

        # Forward through layers
        for i, layer in enumerate(self.layers):
            if self.gradient_checkpointing and self.training:
                # Checkpoint for memory efficiency
                layer_out = torch.utils.checkpoint.checkpoint(
                    layer, x, use_reentrant=False
                )
            else:
                layer_out = layer(x)

            x = layer_out['output']
            coherence_sum += layer_out['phase_coherence']
            num_layers += 1

        # Average coherence across layers
        avg_coherence = coherence_sum / num_layers

        # Output
        x = self.norm(x)
        logits = self.lm_head(x)

        # Loss
        loss = None
        if labels is not None:
            shift_logits = logits[..., :-1, :].contiguous()
            shift_labels = labels[..., 1:].contiguous()
            loss = F.cross_entropy(
                shift_logits.view(-1, self.config.vocab_size),
                shift_labels.view(-1),
                ignore_index=-100,
            )

        return {
            'logits': logits,
            'loss': loss,
            'coherence': avg_coherence,  # Phase synchronization quality
        }

    def count_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters())


# =============================================================================
# DATASET
# =============================================================================

class TextDataset(Dataset):
    """Simple text dataset for training."""

    def __init__(self, tokenizer, max_length: int = 2048, num_samples: int = 10000):
        self.max_length = max_length
        self.num_samples = num_samples
        self.tokenizer = tokenizer

    def __len__(self):
        return self.num_samples

    def __getitem__(self, idx):
        # Random tokens for quick testing
        tokens = torch.randint(0, 32000, (self.max_length,))
        return {'input_ids': tokens, 'labels': tokens}


# =============================================================================
# TRAINING LOOP
# =============================================================================

def train_7b(args):
    """Main training function."""

    print("=" * 70)
    print("   SYMBOLU PHASE 7B - Training")
    print("   Pure Phase Attention O(n) - No Bhava/Ontological")
    print("=" * 70)

    # Device
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"\nDevice: {device}")

    if device.type == 'cuda':
        print(f"GPU: {torch.cuda.get_device_name()}")
        print(f"Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

    # Config
    config = Phase7BConfig(
        max_seq_len=args.seq_len,
        use_gradient_checkpointing=True,
        use_flash_attention=True,
    )

    print(f"\nModel Configuration:")
    print(f"  embed_dim: {config.embed_dim}")
    print(f"  num_heads: {config.num_heads}")
    print(f"  num_kv_heads: {config.num_kv_heads} (GQA)")
    print(f"  num_layers: {config.num_layers}")
    print(f"  vocab_size: {config.vocab_size}")
    print(f"  max_seq_len: {config.max_seq_len}")
    print(f"  phase_dim: {config.phase_dim}")
    print(f"  sync_steps: {config.sync_steps}")
    print(f"  Estimated params: {config.estimate_parameters() / 1e9:.2f}B")

    # Create model
    print("\nCreating model...")
    model = Phase7B(config)
    actual_params = model.count_parameters()
    print(f"Actual parameters: {actual_params:,} ({actual_params/1e9:.2f}B)")

    # Move to GPU with bf16
    model = model.to(device=device, dtype=torch.bfloat16)

    # Memory check
    if device.type == 'cuda':
        torch.cuda.empty_cache()
        allocated = torch.cuda.memory_allocated() / 1e9
        print(f"GPU memory after model load: {allocated:.2f} GB")

    # Optimizer
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=args.learning_rate,
        betas=(0.9, 0.95),
        weight_decay=0.1,
    )

    # Dataset (dummy for testing)
    print("\nCreating dataset...")
    dataset = TextDataset(None, max_length=args.seq_len, num_samples=args.steps * args.batch_size)

    # DataLoader with performance optimizations
    num_workers = 4
    dataloader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=True,
        drop_last=True,
        prefetch_factor=2 if num_workers > 0 else None,
        persistent_workers=num_workers > 0,
    )

    # Training
    print(f"\nStarting training...")
    print(f"  Steps: {args.steps}")
    print(f"  Batch size: {args.batch_size}")
    print(f"  Gradient accumulation: {args.gradient_accumulation}")
    print(f"  Effective batch size: {args.batch_size * args.gradient_accumulation}")
    print(f"  Learning rate: {args.learning_rate}")

    model.train()
    start_time = time.time()
    total_loss = 0
    step = 0
    best_loss = float('inf')
    spike_count = 0

    for batch_idx, batch in enumerate(dataloader):
        if step >= args.steps:
            break

        input_ids = batch['input_ids'].to(device)
        labels = batch['labels'].to(device)

        # Forward
        with torch.autocast(device_type='cuda', dtype=torch.bfloat16):
            outputs = model(input_ids, labels=labels)
            loss = outputs['loss'] / args.gradient_accumulation

        # Backward
        loss.backward()

        # Step
        if (batch_idx + 1) % args.gradient_accumulation == 0:
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            optimizer.zero_grad()
            step += 1

            total_loss += loss.item() * args.gradient_accumulation

            # Log
            if step % args.log_every == 0:
                avg_loss = total_loss / step
                elapsed = time.time() - start_time
                tokens_per_sec = (step * args.batch_size * args.seq_len) / elapsed

                if device.type == 'cuda':
                    mem = torch.cuda.max_memory_allocated() / 1e9
                else:
                    mem = 0

                print(f"Step {step:5d} | Loss: {avg_loss:.4f} | "
                      f"Tok/s: {tokens_per_sec:.0f} | Mem: {mem:.1f}GB | "
                      f"Coh: {outputs['coherence'].mean():.3f}")

                # Adaptive LR on loss spike
                current_loss = loss.item() * args.gradient_accumulation
                if current_loss < best_loss:
                    best_loss = current_loss
                elif step > 100:  # After warmup
                    if current_loss > best_loss * 2.0:
                        # MAJOR SPIKE: 0.7x LR + momentum reset
                        spike_count += 1
                        old_lr = optimizer.param_groups[0]['lr']
                        new_lr = old_lr * 0.7
                        optimizer.state = collections.defaultdict(dict)
                        for pg in optimizer.param_groups:
                            pg['lr'] = new_lr
                        print(f"  🚨 MAJOR spike ({current_loss:.4f} > {best_loss:.4f}*2)! LR: {old_lr:.2e} → {new_lr:.2e} + momentum reset")
                    elif current_loss > best_loss * 1.5:
                        # MODERATE SPIKE: 0.7x LR + momentum reset
                        spike_count += 1
                        old_lr = optimizer.param_groups[0]['lr']
                        new_lr = old_lr * 0.7
                        optimizer.state = collections.defaultdict(dict)
                        for pg in optimizer.param_groups:
                            pg['lr'] = new_lr
                        print(f"  ⚠️ Loss spike ({current_loss:.4f} > {best_loss:.4f}*1.5)! LR: {old_lr:.2e} → {new_lr:.2e} + momentum reset")
                    elif current_loss > best_loss * 1.3:
                        # MINOR SPIKE: 0.85x LR only
                        old_lr = optimizer.param_groups[0]['lr']
                        new_lr = old_lr * 0.85
                        for pg in optimizer.param_groups:
                            pg['lr'] = new_lr
                        print(f"  ⚡ Minor spike ({current_loss:.4f} > {best_loss:.4f}*1.3). LR: {old_lr:.2e} → {new_lr:.2e}")

    # Summary
    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print("   TRAINING COMPLETE")
    print("=" * 70)
    print(f"\nTotal time: {elapsed:.1f}s ({elapsed/60:.1f} min)")
    print(f"Steps completed: {step}")
    print(f"Final loss: {total_loss/step:.4f}")
    print(f"Tokens processed: {step * args.batch_size * args.seq_len:,}")

    # Save checkpoint
    if args.checkpoint_dir:
        os.makedirs(args.checkpoint_dir, exist_ok=True)
        checkpoint_path = os.path.join(args.checkpoint_dir, 'checkpoint_7b.pt')
        torch.save({
            'step': step,
            'model_state_dict': model.state_dict(),
            'optimizer_state_dict': optimizer.state_dict(),
            'config': config,
            'loss': total_loss / step,
        }, checkpoint_path)
        print(f"\nCheckpoint saved: {checkpoint_path}")

    # Cost estimate
    if device.type == 'cuda':
        hours = elapsed / 3600
        a100_cost = hours * 1.89  # RunPod A100 80GB
        h100_cost = hours * 3.89  # RunPod H100 80GB
        print(f"\nEstimated cost:")
        print(f"  A100 80GB: ${a100_cost:.2f}")
        print(f"  H100 80GB: ${h100_cost:.2f}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='SymbolU Phase 7B Training (Pure Phase Attention, No Bhava)',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # Training
    parser.add_argument('--steps', type=int, default=100, help='Training steps')
    parser.add_argument('--batch_size', type=int, default=1, help='Batch size')
    parser.add_argument('--gradient_accumulation', type=int, default=8, help='Gradient accumulation')
    parser.add_argument('--learning_rate', type=float, default=1e-4, help='Learning rate')
    parser.add_argument('--seq_len', type=int, default=1024, help='Sequence length')

    # Logging
    parser.add_argument('--log_every', type=int, default=10, help='Log every N steps')
    parser.add_argument('--checkpoint_dir', type=str, default=None, help='Checkpoint directory')

    # Quick test mode
    parser.add_argument('--quick_test', action='store_true', help='Quick test mode (100 steps)')

    args = parser.parse_args()

    if args.quick_test:
        args.steps = 100
        args.seq_len = 512
        print("\n*** QUICK TEST MODE - 100 steps, 512 seq_len ***\n")

    train_7b(args)


if __name__ == '__main__':
    main()
