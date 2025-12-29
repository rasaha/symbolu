#!/usr/bin/env python3
"""
Unified SymbolU12 Training Script
==================================

Trains both layers of the SymbolU12 architecture together:

1. EXTERNAL (Phase Attention): Standard LLM token prediction
2. INTERNAL (State-Delta): Ontological/phoneme meaning dynamics

Architecture:
                        tokens
                           ↓
              ┌────────────────────────┐
              │   Phase Attention      │  ← O(n) attention
              │   Transformer          │
              └────────────────────────┘
                           ↓
                      hidden[d]
                           ↓
          ┌────────────────┼────────────────┐
          ↓                                  ↓
    ┌───────────┐                    ┌───────────────┐
    │  LM Head  │                    │ StateProjector│
    │  (50K)    │                    │   (124 dim)   │
    └───────────┘                    └───────────────┘
          ↓                                  ↓
    ┌───────────┐                    ┌───────────────┐
    │   CE Loss │                    │ Delta Predict │
    │   (token) │                    │  (ontology)   │
    └───────────┘                    └───────────────┘
          ↓                                  ↓
          └──────────┬───────────────────────┘
                     ↓
              Combined Loss:
              L = λ_token * L_token + λ_state * L_state + λ_coherence * L_coh

Benefits of unified training:
- Shared representations learn both token AND meaning
- Coherence loss ensures alignment between perception and cognition
- State-Delta provides denser training signal
- Better generalization through multi-task learning

Usage:
    # Default balanced training
    python scripts/train_symbolu12.py --max_seq_len 131072 --max_steps 20000

    # Focus on state-delta (for long context)
    python scripts/train_symbolu12.py --lambda_state 0.7 --lambda_token 0.3

    # Resume from standard LLM checkpoint
    python scripts/train_symbolu12.py --resume checkpoints/best.pt
"""

import os
import sys
import argparse
import time
import math
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from symbolu.phase_transformer import HybridPhaseTransformer, PhaseAttentionTransformer
from symbolu.experimental import (
    StateProjector,
    CognitiveStateProjectorLite,
    OntologicalDeltaPredictor,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================

MODEL_CONFIGS = {
    'tiny': {'embed_dim': 256, 'num_heads': 4, 'num_layers': 4, 'ff_dim': 512},
    'small': {'embed_dim': 512, 'num_heads': 8, 'num_layers': 6, 'ff_dim': 1024},
    'medium': {'embed_dim': 768, 'num_heads': 12, 'num_layers': 12, 'ff_dim': 2048},
    'large': {'embed_dim': 1024, 'num_heads': 16, 'num_layers': 24, 'ff_dim': 4096},
}


@dataclass
class UnifiedTrainingConfig:
    """Configuration for unified SymbolU12 training."""
    # Loss weights
    lambda_token: float = 0.5       # Weight for token prediction loss
    lambda_state: float = 0.3       # Weight for state-delta loss
    lambda_coherence: float = 0.1   # Weight for coherence loss
    lambda_entropy: float = 0.05    # Weight for entropy regularization
    lambda_ontology: float = 0.05   # Weight for ontology transition loss

    # State dimensions
    num_phonemes: int = 44
    topic_dim: int = 64
    num_ontology: int = 12

    # Training dynamics
    warmup_state_delta: int = 500   # Steps before state-delta loss kicks in
    state_delta_ramp: int = 1000    # Steps to ramp up state-delta weight


# =============================================================================
# UNIFIED SYMBOLU12 MODEL
# =============================================================================

class UnifiedSymbolU12(nn.Module):
    """
    Unified SymbolU12 Model: Combines LLM + Ontological State-Delta.

    This is the complete architecture that trains:
    1. Phase Attention for efficient long-range attention (external)
    2. State-Delta for meaning dynamics (internal)

    Together they form a system that:
    - Perceives efficiently (Phase Attention O(n))
    - Understands deeply (State-Delta in meaning space)
    - Acts precisely (constrained token generation)
    """

    def __init__(
        self,
        base_model: nn.Module,
        config: UnifiedTrainingConfig,
        hidden_dim: int = 768,
        vocab_size: int = 50257,
    ):
        super().__init__()
        self.base_model = base_model
        self.config = config
        self.hidden_dim = hidden_dim
        self.vocab_size = vocab_size

        # =====================================================================
        # HEAD 1: Standard LLM (Token Prediction)
        # =====================================================================
        # Already in base_model as lm_head

        # =====================================================================
        # HEAD 2: State-Delta (Ontological)
        # =====================================================================

        # Full state projector: hidden → CognitiveState
        self.state_projector = StateProjector(
            hidden_dim=hidden_dim,
            num_phonemes=config.num_phonemes,
            topic_dim=config.topic_dim,
            num_ontology=config.num_ontology,
        )

        # State delta predictor
        self.delta_predictor = OntologicalDeltaPredictor(
            state_dim=self.state_projector.state_dim,
            num_phonemes=config.num_phonemes,
            topic_dim=config.topic_dim,
            num_ontology=config.num_ontology,
        )

        # =====================================================================
        # COHERENCE BRIDGE: Aligns LM head and State-Delta
        # =====================================================================

        # Projects state back to vocabulary space for coherence
        self.state_to_vocab = nn.Sequential(
            nn.Linear(self.state_projector.state_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, vocab_size),
        )

        # Entropy predictor from state (should match actual next-token entropy)
        self.state_entropy_predictor = nn.Sequential(
            nn.Linear(self.state_projector.state_dim, hidden_dim // 4),
            nn.GELU(),
            nn.Linear(hidden_dim // 4, 1),
            nn.Softplus(),  # Entropy is always positive
        )

    def forward(
        self,
        input_ids: torch.Tensor,
        labels: Optional[torch.Tensor] = None,
        step: int = 0,
    ) -> Dict[str, torch.Tensor]:
        """
        Unified forward pass computing both token and state-delta losses.

        Args:
            input_ids: [B, T] token indices
            labels: [B, T] target tokens (if None, use shifted input_ids)
            step: Current training step (for loss ramping)

        Returns:
            Dict with losses and metrics
        """
        B, T = input_ids.shape
        device = input_ids.device

        if labels is None:
            labels = input_ids

        # =================================================================
        # FORWARD THROUGH BASE MODEL
        # =================================================================

        outputs = self.base_model(input_ids, return_hidden=True)

        if isinstance(outputs, dict):
            hidden = outputs.get('hidden_states', outputs.get('last_hidden_state'))
            logits = outputs.get('logits')
        else:
            hidden = outputs
            logits = self.base_model.lm_head(hidden)

        # =================================================================
        # LOSS 1: Token Prediction (Standard LLM)
        # =================================================================

        # Shift for next-token prediction
        shift_logits = logits[:, :-1, :].contiguous()
        shift_labels = labels[:, 1:].contiguous()

        token_loss = F.cross_entropy(
            shift_logits.view(-1, self.vocab_size),
            shift_labels.view(-1),
            ignore_index=-100,
        )

        # Compute token entropy for coherence loss
        with torch.no_grad():
            token_probs = F.softmax(shift_logits, dim=-1)
            token_entropy = -torch.sum(
                token_probs * torch.log(token_probs + 1e-9),
                dim=-1
            )  # [B, T-1]

        # =================================================================
        # LOSS 2: State-Delta (Ontological)
        # =================================================================

        # Project hidden to cognitive states
        cognitive_states = self.state_projector(hidden)  # [B, T, state_dim]

        # Compute state-delta loss
        state_loss, state_metrics = self.delta_predictor.compute_loss(
            cognitive_states,
            lambda_ontology=self.config.lambda_ontology,
            lambda_coherence=self.config.lambda_coherence,
            lambda_entropy=self.config.lambda_entropy,
        )

        # =================================================================
        # LOSS 3: Coherence (Bridges token and state)
        # =================================================================

        # State-predicted logits should align with actual logits
        state_logits = self.state_to_vocab(cognitive_states[:, :-1])  # [B, T-1, V]

        # KL divergence between token probs and state-predicted probs
        state_probs = F.softmax(state_logits, dim=-1)
        coherence_loss = F.kl_div(
            torch.log(state_probs + 1e-9),
            token_probs,
            reduction='batchmean',
        )

        # =================================================================
        # LOSS 4: Entropy Alignment
        # =================================================================

        # State-predicted entropy should match actual token entropy
        predicted_entropy = self.state_entropy_predictor(
            cognitive_states[:, :-1]
        ).squeeze(-1)  # [B, T-1]

        entropy_loss = F.mse_loss(predicted_entropy, token_entropy)

        # =================================================================
        # COMBINE LOSSES WITH RAMPING
        # =================================================================

        # Ramp up state-delta loss gradually
        if step < self.config.warmup_state_delta:
            state_weight = 0.0
        elif step < self.config.warmup_state_delta + self.config.state_delta_ramp:
            progress = (step - self.config.warmup_state_delta) / self.config.state_delta_ramp
            state_weight = self.config.lambda_state * progress
        else:
            state_weight = self.config.lambda_state

        total_loss = (
            self.config.lambda_token * token_loss +
            state_weight * state_loss +
            self.config.lambda_coherence * coherence_loss +
            self.config.lambda_entropy * entropy_loss
        )

        # =================================================================
        # METRICS
        # =================================================================

        # Token perplexity
        ppl = torch.exp(token_loss).item()

        # State entropy (from ontology distribution)
        onto_start = self.config.num_phonemes + self.config.topic_dim
        onto_end = onto_start + self.config.num_ontology
        ontology_probs = cognitive_states[:, :, onto_start:onto_end]
        state_entropy = -torch.sum(
            ontology_probs * torch.log(ontology_probs + 1e-9),
            dim=-1
        ).mean()

        # Coherence from dynamics
        dynamics_start = onto_end
        coherence = cognitive_states[:, :, dynamics_start].mean()

        metrics = {
            'total_loss': total_loss.detach(),
            'token_loss': token_loss.detach(),
            'state_loss': state_loss.detach(),
            'coherence_loss': coherence_loss.detach(),
            'entropy_loss': entropy_loss.detach(),
            'ppl': ppl,
            'state_entropy': state_entropy.detach(),
            'coherence': coherence.detach(),
            'token_entropy': token_entropy.mean().detach(),
            'state_weight': state_weight,
        }
        metrics.update({f'state_{k}': v for k, v in state_metrics.items()})

        return {
            'loss': total_loss,
            'metrics': metrics,
            'hidden': hidden,
            'cognitive_states': cognitive_states,
            'logits': logits,
        }

    def get_cognitive_state(self, hidden: torch.Tensor) -> torch.Tensor:
        """Get cognitive state from hidden representation."""
        return self.state_projector(hidden)

    def get_cognitive_state_dict(self, hidden: torch.Tensor) -> Dict[str, torch.Tensor]:
        """Get cognitive state as dictionary with named components."""
        return self.state_projector.forward_dict(hidden)


# =============================================================================
# DATASET
# =============================================================================

def load_dataset(name: str, tokenizer, max_seq_len: int):
    """Load and prepare dataset."""
    from datasets import load_dataset as hf_load_dataset

    logger.info(f"Loading dataset: {name}")

    if name == 'wikitext103':
        dataset = hf_load_dataset('wikitext', 'wikitext-103-v1')
    elif name == 'wikitext2':
        dataset = hf_load_dataset('wikitext', 'wikitext-2-v1')
    else:
        dataset = hf_load_dataset(name)

    def tokenize_and_chunk(examples):
        tokens = tokenizer(
            examples['text'],
            truncation=False,
            padding=False,
            return_attention_mask=False,
        )

        all_ids = []
        for ids in tokens['input_ids']:
            all_ids.extend(ids)

        chunks = []
        for i in range(0, len(all_ids) - max_seq_len, max_seq_len):
            chunks.append(all_ids[i:i + max_seq_len])

        return {'input_ids': chunks}

    train_data = dataset['train'].map(
        tokenize_and_chunk,
        batched=True,
        remove_columns=dataset['train'].column_names,
        desc="Tokenizing train",
    )

    val_data = dataset['validation'].map(
        tokenize_and_chunk,
        batched=True,
        remove_columns=dataset['validation'].column_names,
        desc="Tokenizing val",
    )

    train_data.set_format(type='torch', columns=['input_ids'])
    val_data.set_format(type='torch', columns=['input_ids'])

    return train_data, val_data


# =============================================================================
# TRAINING LOOP
# =============================================================================

def train(args):
    """Main training function."""
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    logger.info(f"Using device: {device}")

    # Load tokenizer
    from transformers import GPT2Tokenizer
    tokenizer = GPT2Tokenizer.from_pretrained('gpt2')
    tokenizer.pad_token = tokenizer.eos_token
    vocab_size = len(tokenizer)

    # Model config
    config = MODEL_CONFIGS[args.model_size]
    logger.info(f"Model config: {config}")

    # Training config
    train_config = UnifiedTrainingConfig(
        lambda_token=args.lambda_token,
        lambda_state=args.lambda_state,
        lambda_coherence=args.lambda_coherence,
        lambda_entropy=args.lambda_entropy,
        lambda_ontology=args.lambda_ontology,
        warmup_state_delta=args.warmup_state_delta,
        state_delta_ramp=args.state_delta_ramp,
    )

    # Create base model
    if args.model_type == 'hybrid':
        base_model = HybridPhaseTransformer(
            vocab_size=vocab_size,
            max_seq_len=args.max_seq_len,
            window_size=args.window_size,
            local_backend=args.local_backend,
            **config,
        )
    else:
        base_model = PhaseAttentionTransformer(
            vocab_size=vocab_size,
            max_seq_len=args.max_seq_len,
            **config,
        )

    # Wrap with unified training
    model = UnifiedSymbolU12(
        base_model=base_model,
        config=train_config,
        hidden_dim=config['embed_dim'],
        vocab_size=vocab_size,
    )

    # Gradient checkpointing
    if args.gradient_checkpointing and hasattr(base_model, 'enable_gradient_checkpointing'):
        base_model.enable_gradient_checkpointing()
        logger.info("Gradient checkpointing enabled")

    model = model.to(device)

    # Count parameters
    total_params = sum(p.numel() for p in model.parameters())
    base_params = sum(p.numel() for p in base_model.parameters())
    state_params = total_params - base_params
    logger.info(f"Total parameters: {total_params:,}")
    logger.info(f"  Base model (Phase Attention): {base_params:,}")
    logger.info(f"  State-Delta heads: {state_params:,}")

    # Resume
    start_step = 0
    if args.resume:
        logger.info(f"Loading checkpoint: {args.resume}")
        checkpoint = torch.load(args.resume, map_location=device)

        if 'model_state_dict' in checkpoint:
            try:
                model.load_state_dict(checkpoint['model_state_dict'], strict=False)
            except:
                base_model.load_state_dict(checkpoint['model_state_dict'], strict=False)
            start_step = checkpoint.get('step', 0)
        else:
            base_model.load_state_dict(checkpoint, strict=False)

        logger.info(f"Resumed from step {start_step}")

    # Load dataset
    train_data, val_data = load_dataset(args.dataset, tokenizer, args.max_seq_len)

    train_loader = DataLoader(
        train_data,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0,
        pin_memory=True,
    )

    val_loader = DataLoader(
        val_data,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,
    )

    # Optimizer
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=args.lr,
        weight_decay=args.weight_decay,
    )

    # LR scheduler
    def lr_lambda(step):
        if step < args.warmup_steps:
            return step / args.warmup_steps
        else:
            progress = (step - args.warmup_steps) / (args.max_steps - args.warmup_steps)
            return 0.5 * (1 + math.cos(math.pi * progress))

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)

    # Training
    model.train()
    step = start_step
    best_val_loss = float('inf')
    grad_accum_count = 0
    accum_loss = 0.0
    accum_metrics = {}

    os.makedirs(args.checkpoint_dir, exist_ok=True)

    logger.info("=" * 70)
    logger.info("UNIFIED SYMBOLU12 TRAINING")
    logger.info("External: Phase Attention (O(n) long-range attention)")
    logger.info("Internal: State-Delta (Ontological meaning dynamics)")
    logger.info("=" * 70)
    logger.info(f"Token loss weight (λ_token): {args.lambda_token}")
    logger.info(f"State loss weight (λ_state): {args.lambda_state}")
    logger.info(f"Coherence loss weight: {args.lambda_coherence}")
    logger.info(f"State-delta warmup: {args.warmup_state_delta} steps")
    logger.info(f"State-delta ramp: {args.state_delta_ramp} steps")
    logger.info("=" * 70)

    train_iter = iter(train_loader)
    start_time = time.time()

    while step < args.max_steps:
        try:
            batch = next(train_iter)
        except StopIteration:
            train_iter = iter(train_loader)
            batch = next(train_iter)

        input_ids = batch['input_ids'].to(device)

        # Forward
        outputs = model(input_ids, step=step)
        loss = outputs['loss'] / args.gradient_accumulation

        # Backward
        loss.backward()
        accum_loss += loss.item()

        # Accumulate metrics
        for k, v in outputs['metrics'].items():
            if k not in accum_metrics:
                accum_metrics[k] = 0.0
            if isinstance(v, torch.Tensor):
                accum_metrics[k] += v.item()
            else:
                accum_metrics[k] += v

        grad_accum_count += 1

        # Update
        if grad_accum_count >= args.gradient_accumulation:
            torch.nn.utils.clip_grad_norm_(model.parameters(), args.max_grad_norm)
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad()

            step += 1

            # Logging
            if step % args.log_every == 0:
                elapsed = time.time() - start_time
                tokens_per_sec = (
                    args.log_every * args.batch_size * args.max_seq_len *
                    args.gradient_accumulation
                ) / elapsed

                # Average metrics
                for k in accum_metrics:
                    accum_metrics[k] /= (args.log_every * args.gradient_accumulation)

                lr = scheduler.get_last_lr()[0]
                vram_gb = torch.cuda.max_memory_allocated() / 1e9 if torch.cuda.is_available() else 0

                # Build log message
                ppl = accum_metrics.get('ppl', 0)
                token_ent = accum_metrics.get('token_entropy', 0)
                state_ent = accum_metrics.get('state_entropy', 0)
                coh = accum_metrics.get('coherence', 0)
                state_w = accum_metrics.get('state_weight', 0)

                log_msg = (
                    f"Step {step:6d} | "
                    f"Loss: {accum_loss:.4f} | "
                    f"PPL: {ppl:.2f} | "
                    f"TokEnt: {token_ent:.2f} | "
                    f"StaEnt: {state_ent:.2f} | "
                    f"Coh: {coh:.3f} | "
                    f"StaW: {state_w:.2f} | "
                    f"LR: {lr:.2e} | "
                    f"Tok/s: {tokens_per_sec:.0f} | "
                    f"VRAM: {vram_gb:.1f}GB"
                )
                logger.info(log_msg)

                start_time = time.time()
                accum_metrics = {}

            # Evaluation
            if step % args.eval_every == 0:
                val_metrics = evaluate(model, val_loader, device, step)
                val_loss = val_metrics['total_loss']
                val_ppl = val_metrics['ppl']
                val_state_ent = val_metrics['state_entropy']

                logger.info(
                    f"  Val Loss: {val_loss:.4f} | "
                    f"Val PPL: {val_ppl:.2f} | "
                    f"Val StaEnt: {val_state_ent:.2f}"
                )

                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    save_path = os.path.join(args.checkpoint_dir, 'best_symbolu12.pt')
                    torch.save({
                        'step': step,
                        'model_state_dict': model.state_dict(),
                        'base_model_state_dict': base_model.state_dict(),
                        'optimizer_state_dict': optimizer.state_dict(),
                        'val_loss': val_loss,
                        'val_ppl': val_ppl,
                        'config': train_config,
                    }, save_path)
                    logger.info(f"  New best! Saved to {save_path}")

                model.train()

            accum_loss = 0.0
            grad_accum_count = 0

    logger.info("=" * 70)
    logger.info("Training complete!")
    logger.info(f"Best validation loss: {best_val_loss:.4f}")
    logger.info("=" * 70)


def evaluate(model, val_loader, device, step, max_batches=10):
    """Evaluate model."""
    model.eval()
    total_metrics = {}
    num_batches = 0

    with torch.no_grad():
        for batch in val_loader:
            if num_batches >= max_batches:
                break

            input_ids = batch['input_ids'].to(device)
            outputs = model(input_ids, step=step)

            for k, v in outputs['metrics'].items():
                if k not in total_metrics:
                    total_metrics[k] = 0.0
                if isinstance(v, torch.Tensor):
                    total_metrics[k] += v.item()
                else:
                    total_metrics[k] += v

            num_batches += 1

    for k in total_metrics:
        total_metrics[k] /= max(num_batches, 1)

    return total_metrics


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='Unified SymbolU12 Training')

    # Model
    parser.add_argument('--model_type', type=str, default='hybrid', choices=['hybrid', 'phase'])
    parser.add_argument('--model_size', type=str, default='tiny', choices=['tiny', 'small', 'medium', 'large'])

    # Data
    parser.add_argument('--dataset', type=str, default='wikitext103')
    parser.add_argument('--max_seq_len', type=int, default=131072)

    # Training
    parser.add_argument('--batch_size', type=int, default=1)
    parser.add_argument('--gradient_accumulation', type=int, default=2)
    parser.add_argument('--max_steps', type=int, default=20000)
    parser.add_argument('--lr', type=float, default=1e-4)
    parser.add_argument('--weight_decay', type=float, default=0.01)
    parser.add_argument('--warmup_steps', type=int, default=50)
    parser.add_argument('--max_grad_norm', type=float, default=1.0)

    # Loss weights
    parser.add_argument('--lambda_token', type=float, default=0.5, help='Token prediction loss weight')
    parser.add_argument('--lambda_state', type=float, default=0.3, help='State-delta loss weight')
    parser.add_argument('--lambda_coherence', type=float, default=0.1, help='Coherence loss weight')
    parser.add_argument('--lambda_entropy', type=float, default=0.05, help='Entropy alignment weight')
    parser.add_argument('--lambda_ontology', type=float, default=0.05, help='Ontology transition weight')

    # State-delta ramping
    parser.add_argument('--warmup_state_delta', type=int, default=500, help='Steps before state-delta kicks in')
    parser.add_argument('--state_delta_ramp', type=int, default=1000, help='Steps to ramp state-delta weight')

    # Architecture
    parser.add_argument('--window_size', type=int, default=128)
    parser.add_argument('--local_backend', type=str, default='unfold')
    parser.add_argument('--gradient_checkpointing', action='store_true')

    # Logging
    parser.add_argument('--log_every', type=int, default=10)
    parser.add_argument('--eval_every', type=int, default=50)
    parser.add_argument('--checkpoint_dir', type=str, default='checkpoints')

    # Resume
    parser.add_argument('--resume', type=str, default=None)

    args = parser.parse_args()

    train(args)


if __name__ == '__main__':
    main()
