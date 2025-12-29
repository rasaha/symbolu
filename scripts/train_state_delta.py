#!/usr/bin/env python3
"""
State-Delta Training Script
============================

Trains using state-delta paradigm instead of token prediction.

Key differences from standard training:
- Predicts: ΔS = S_{t+1} - S_t (how understanding changes)
- NOT: P(token_{t+1}) (what word comes next)

Memory savings:
- Token prediction: O(B × T × V) = 200GB at 1M context
- State-delta: O(B × T × d) = 3GB at 1M context (65x reduction)

Usage:
    python scripts/train_state_delta.py --max_seq_len 131072 --max_steps 20000

    # Resume from checkpoint
    python scripts/train_state_delta.py --resume checkpoints/best.pt --max_steps 50000

    # Use Tier 3 (ontological) instead of Tier 2 (hidden)
    python scripts/train_state_delta.py --tier 3 --max_steps 20000
"""

import os
import sys
import argparse
import time
import logging
from pathlib import Path

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
    CognitiveState,
    StateDelta,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# =============================================================================
# MODEL CONFIGURATIONS
# =============================================================================

MODEL_CONFIGS = {
    'tiny': {'embed_dim': 256, 'num_heads': 4, 'num_layers': 4, 'ff_dim': 512},
    'small': {'embed_dim': 512, 'num_heads': 8, 'num_layers': 6, 'ff_dim': 1024},
    'medium': {'embed_dim': 768, 'num_heads': 12, 'num_layers': 12, 'ff_dim': 2048},
    'large': {'embed_dim': 1024, 'num_heads': 16, 'num_layers': 24, 'ff_dim': 4096},
}


# =============================================================================
# STATE-DELTA TRAINER
# =============================================================================

class StateDeltaTrainer(nn.Module):
    """
    Wraps a base transformer with state-delta training heads.

    Architecture:
        tokens → Transformer → hidden[d] → StateProjector → state[124]
                                                ↓
                                    OntologicalDeltaPredictor
                                                ↓
                                           delta[124]
                                                ↓
                                         state_delta_loss
    """

    def __init__(
        self,
        base_model: nn.Module,
        tier: int = 2,
        hidden_dim: int = 768,
        state_dim: int = 124,
        num_phonemes: int = 44,
        topic_dim: int = 64,
        num_ontology: int = 12,
    ):
        super().__init__()
        self.base_model = base_model
        self.tier = tier
        self.hidden_dim = hidden_dim

        if tier == 2:
            # Tier 2: Simple hidden state delta
            self.transition = nn.Linear(hidden_dim, hidden_dim, bias=False)
            self.norm = nn.LayerNorm(hidden_dim)
            self.state_dim = hidden_dim
        else:
            # Tier 3: Structured ontological state delta
            self.projector = StateProjector(
                hidden_dim=hidden_dim,
                num_phonemes=num_phonemes,
                topic_dim=topic_dim,
                num_ontology=num_ontology,
            )
            self.delta_predictor = OntologicalDeltaPredictor(
                state_dim=self.projector.state_dim,
                num_phonemes=num_phonemes,
                topic_dim=topic_dim,
                num_ontology=num_ontology,
            )
            self.state_dim = self.projector.state_dim

    def forward(self, input_ids, labels=None):
        """
        Forward pass with state-delta loss.

        Args:
            input_ids: [B, T] token indices
            labels: [B, T] target tokens (used for teacher forcing)

        Returns:
            dict with loss, metrics, and predicted states
        """
        # Get hidden states from base model
        outputs = self.base_model(input_ids, return_hidden=True)

        if isinstance(outputs, dict):
            hidden = outputs.get('hidden_states', outputs.get('last_hidden_state'))
            token_loss = outputs.get('loss', None)
        else:
            hidden = outputs
            token_loss = None

        # Compute state-delta loss based on tier
        if self.tier == 2:
            loss, metrics = self._tier2_loss(hidden)
        else:
            loss, metrics = self._tier3_loss(hidden)

        # Combine with token loss if available
        if token_loss is not None:
            metrics['token_loss'] = token_loss.detach()
            loss = loss + 0.1 * token_loss  # Small weight for token loss

        return {
            'loss': loss,
            'metrics': metrics,
            'hidden': hidden,
        }

    def _tier2_loss(self, hidden: torch.Tensor):
        """
        Tier 2: Hidden state delta prediction.

        S_{t+1} = S_t + Δ
        Loss = 1 - cosine_similarity(predicted, actual)
        """
        B, T, D = hidden.shape

        # Current states
        s_t = hidden[:, :-1]  # [B, T-1, D]

        # Actual next states
        s_next_actual = hidden[:, 1:]  # [B, T-1, D]

        # Predicted delta
        delta = self.transition(s_t)  # [B, T-1, D]

        # Predicted next state
        s_next_pred = self.norm(s_t + delta)  # [B, T-1, D]

        # Cosine similarity loss
        cos_sim = F.cosine_similarity(s_next_pred, s_next_actual, dim=-1)  # [B, T-1]
        loss = (1 - cos_sim).mean()

        # Also compute MSE for monitoring
        mse = F.mse_loss(s_next_pred, s_next_actual)

        metrics = {
            'delta_loss': loss.detach(),
            'mse': mse.detach(),
            'cos_sim': cos_sim.mean().detach(),
        }

        return loss, metrics

    def _tier3_loss(self, hidden: torch.Tensor):
        """
        Tier 3: Ontological state delta prediction.

        hidden → CognitiveState → delta prediction → structured loss
        """
        # Project to cognitive states
        states = self.projector(hidden)  # [B, T, state_dim]

        # Compute ontological loss
        loss, metrics = self.delta_predictor.compute_loss(states)

        return loss, metrics

    def get_cognitive_state(self, hidden: torch.Tensor):
        """Get structured cognitive state from hidden."""
        if self.tier == 2:
            return hidden
        else:
            return self.projector(hidden)


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
        # Tokenize
        tokens = tokenizer(
            examples['text'],
            truncation=False,
            padding=False,
            return_attention_mask=False,
        )

        # Concatenate all tokens
        all_ids = []
        for ids in tokens['input_ids']:
            all_ids.extend(ids)

        # Chunk into max_seq_len pieces
        chunks = []
        for i in range(0, len(all_ids) - max_seq_len, max_seq_len):
            chunks.append(all_ids[i:i + max_seq_len])

        return {'input_ids': chunks}

    # Process datasets
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

    # Get model config
    config = MODEL_CONFIGS[args.model_size]
    logger.info(f"Model config: {config}")

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

    # Wrap with state-delta trainer
    model = StateDeltaTrainer(
        base_model=base_model,
        tier=args.tier,
        hidden_dim=config['embed_dim'],
    )

    # Enable gradient checkpointing
    if args.gradient_checkpointing and hasattr(base_model, 'enable_gradient_checkpointing'):
        base_model.enable_gradient_checkpointing()
        logger.info("Gradient checkpointing enabled")

    model = model.to(device)

    # Count parameters
    num_params = sum(p.numel() for p in model.parameters())
    logger.info(f"Model parameters: {num_params:,}")

    # Resume from checkpoint
    start_step = 0
    if args.resume:
        logger.info(f"Loading checkpoint: {args.resume}")
        checkpoint = torch.load(args.resume, map_location=device)
        if 'model_state_dict' in checkpoint:
            # Load base model weights
            base_model.load_state_dict(checkpoint['model_state_dict'], strict=False)
            start_step = checkpoint.get('step', 0)
            logger.info(f"Resumed from step {start_step}")
        else:
            base_model.load_state_dict(checkpoint, strict=False)

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

    # Learning rate scheduler
    def lr_lambda(step):
        if step < args.warmup_steps:
            return step / args.warmup_steps
        else:
            progress = (step - args.warmup_steps) / (args.max_steps - args.warmup_steps)
            return 0.5 * (1 + torch.cos(torch.tensor(progress * 3.14159)).item())

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)

    # Training
    model.train()
    step = start_step
    best_val_loss = float('inf')
    grad_accum_count = 0
    accum_loss = 0.0

    os.makedirs(args.checkpoint_dir, exist_ok=True)

    logger.info(f"Starting training from step {step}")
    logger.info(f"Tier: {args.tier} ({'Hidden State Delta' if args.tier == 2 else 'Ontological State Delta'})")
    logger.info(f"Max steps: {args.max_steps}")
    logger.info(f"Gradient accumulation: {args.gradient_accumulation}")

    train_iter = iter(train_loader)
    start_time = time.time()

    while step < args.max_steps:
        try:
            batch = next(train_iter)
        except StopIteration:
            train_iter = iter(train_loader)
            batch = next(train_iter)

        input_ids = batch['input_ids'].to(device)

        # Forward pass
        outputs = model(input_ids)
        loss = outputs['loss'] / args.gradient_accumulation

        # Backward pass
        loss.backward()
        accum_loss += loss.item()
        grad_accum_count += 1

        # Update weights
        if grad_accum_count >= args.gradient_accumulation:
            torch.nn.utils.clip_grad_norm_(model.parameters(), args.max_grad_norm)
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad()

            step += 1

            # Logging
            if step % args.log_every == 0:
                elapsed = time.time() - start_time
                tokens_per_sec = (args.log_every * args.batch_size * args.max_seq_len *
                                  args.gradient_accumulation) / elapsed

                metrics = outputs['metrics']
                lr = scheduler.get_last_lr()[0]

                vram_gb = torch.cuda.max_memory_allocated() / 1e9 if torch.cuda.is_available() else 0

                log_msg = f"Step {step:6d} | Loss: {accum_loss:.4f}"

                if 'cos_sim' in metrics:
                    log_msg += f" | CosSim: {metrics['cos_sim']:.3f}"
                if 'delta_loss' in metrics:
                    log_msg += f" | DeltaL: {metrics['delta_loss']:.4f}"
                if 'ontology_loss' in metrics:
                    log_msg += f" | OntoL: {metrics['ontology_loss']:.4f}"

                log_msg += f" | LR: {lr:.2e} | Tok/s: {tokens_per_sec:.0f} | VRAM: {vram_gb:.1f}GB"

                logger.info(log_msg)

                start_time = time.time()

            # Evaluation
            if step % args.eval_every == 0:
                val_loss = evaluate(model, val_loader, device)
                logger.info(f"  Val Loss: {val_loss:.4f}")

                if val_loss < best_val_loss:
                    best_val_loss = val_loss
                    save_path = os.path.join(args.checkpoint_dir, 'best_state_delta.pt')
                    torch.save({
                        'step': step,
                        'model_state_dict': model.state_dict(),
                        'base_model_state_dict': base_model.state_dict(),
                        'optimizer_state_dict': optimizer.state_dict(),
                        'val_loss': val_loss,
                        'tier': args.tier,
                    }, save_path)
                    logger.info(f"  New best! Saved to {save_path}")

                model.train()

            accum_loss = 0.0
            grad_accum_count = 0

    logger.info("Training complete!")
    logger.info(f"Best validation loss: {best_val_loss:.4f}")


def evaluate(model, val_loader, device, max_batches=10):
    """Evaluate model on validation set."""
    model.eval()
    total_loss = 0.0
    num_batches = 0

    with torch.no_grad():
        for batch in val_loader:
            if num_batches >= max_batches:
                break

            input_ids = batch['input_ids'].to(device)
            outputs = model(input_ids)
            total_loss += outputs['loss'].item()
            num_batches += 1

    return total_loss / max(num_batches, 1)


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='State-Delta Training')

    # Model
    parser.add_argument('--model_type', type=str, default='hybrid', choices=['hybrid', 'phase'])
    parser.add_argument('--model_size', type=str, default='tiny', choices=['tiny', 'small', 'medium', 'large'])
    parser.add_argument('--tier', type=int, default=2, choices=[2, 3], help='2=Hidden delta, 3=Ontological delta')

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

    # Architecture
    parser.add_argument('--window_size', type=int, default=128)
    parser.add_argument('--local_backend', type=str, default='unfold')
    parser.add_argument('--gradient_checkpointing', action='store_true')

    # Logging
    parser.add_argument('--log_every', type=int, default=10)
    parser.add_argument('--eval_every', type=int, default=50)
    parser.add_argument('--checkpoint_dir', type=str, default='checkpoints')

    # Resume
    parser.add_argument('--resume', type=str, default=None, help='Path to checkpoint')

    args = parser.parse_args()

    train(args)


if __name__ == '__main__':
    main()
