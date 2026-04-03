#!/usr/bin/env python3
"""
Ontological Trainer: Tier 3 Training Loop
==========================================

Training loop for ontological state-delta learning.

Key difference from standard training:
- NO token prediction loss (no LM head)
- Learns state transitions in meaning space
- Losses based on coherence, entropy, constraints

Memory at 10M context:
- Tier 1 (tokens): 2TB - impossible
- Tier 2 (hidden): 30GB - needs H200
- Tier 3 (ontological): 5GB - consumer GPU

This is EXPERIMENTAL - separate from production training.
"""

import os
import sys
import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import AdamW
from torch.optim.lr_scheduler import LambdaLR
from torch.cuda.amp import autocast, GradScaler
from torch.utils.data import DataLoader

# Local imports
from .cognitive_state import (
    CognitiveState,
    StateDelta,
    StateProjector,
    OntologicalDeltaPredictor,
)
from .ontology_mapper import (
    OntologicalPerception,
    OntologyMapper,
    NUM_BHAVA_STATES,
)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class OntologicalTrainingConfig:
    """Configuration for Tier 3 ontological training."""

    # Model
    model_type: str = "hybrid"  # phase or hybrid
    model_size: str = "small"
    vocab_size: int = 50257
    embed_dim: int = 768
    max_seq_len: int = 1_000_000  # 1M default, can go to 100M

    # Cognitive state dimensions
    num_phonemes: int = 44
    topic_dim: int = 64
    num_bhava: int = NUM_BHAVA_STATES  # 12
    state_dim: int = 124  # 44 + 64 + 12 + 4

    # Training
    batch_size: int = 1
    gradient_accumulation: int = 1
    max_steps: int = 10000
    warmup_steps: int = 500
    learning_rate: float = 1e-4
    weight_decay: float = 0.1
    max_grad_norm: float = 1.0

    # Loss weights
    lambda_delta: float = 1.0           # State delta prediction
    lambda_bhava: float = 0.5           # Bhava transition
    lambda_coherence: float = 0.1       # Coherence stability
    lambda_entropy: float = 0.1         # Entropy smoothness
    lambda_constraint: float = 0.1      # Constraint satisfaction
    lambda_phoneme: float = 0.1         # Phoneme consistency

    # Memory optimization
    gradient_checkpointing: bool = True
    mixed_precision: str = "bf16"

    # Logging
    log_every: int = 10
    eval_every: int = 100
    save_every: int = 1000
    checkpoint_dir: str = "checkpoints/ontological"

    # Dataset
    dataset: str = "wikitext103"
    tokenizer: str = "gpt2"

    # Device
    device: str = "auto"
    seed: int = 42


# =============================================================================
# ONTOLOGICAL LOSS FUNCTIONS
# =============================================================================

def compute_ontological_loss(
    cognitive_states: torch.Tensor,
    delta_predictor: OntologicalDeltaPredictor,
    ontology_mapper: OntologyMapper,
    config: OntologicalTrainingConfig,
) -> Tuple[torch.Tensor, Dict[str, float]]:
    """
    Compute comprehensive ontological training loss.

    Loss components:
    1. State delta prediction (main signal)
    2. Bhava transition validity
    3. Coherence stability
    4. Entropy smoothness
    5. Constraint satisfaction
    6. Phoneme consistency

    Args:
        cognitive_states: [B, T, state_dim] sequence of cognitive states
        delta_predictor: OntologicalDeltaPredictor module
        ontology_mapper: OntologyMapper module
        config: Training configuration

    Returns:
        total_loss: Combined loss
        metrics: Dict of component losses
    """
    B, T, D = cognitive_states.shape

    # Parse state components
    num_phonemes = config.num_phonemes
    topic_dim = config.topic_dim
    num_bhava = config.num_bhava

    phoneme_energy = cognitive_states[:, :, :num_phonemes]
    topic_embed = cognitive_states[:, :, num_phonemes:num_phonemes + topic_dim]
    bhava_probs = cognitive_states[:, :, num_phonemes + topic_dim:num_phonemes + topic_dim + num_bhava]
    dynamics = cognitive_states[:, :, -4:]  # coherence, entropy, confidence, momentum

    # 1. State delta prediction loss
    delta_loss, delta_metrics = delta_predictor.compute_loss(cognitive_states)

    # 2. Bhava transition loss
    bhava_loss = ontology_mapper.compute_transition_loss(bhava_probs)

    # 3. Coherence stability loss (coherence shouldn't change too fast)
    coherence = dynamics[:, :, 0]  # [B, T]
    coherence_delta = coherence[:, 1:] - coherence[:, :-1]
    coherence_loss = (coherence_delta ** 2).mean()

    # 4. Entropy smoothness loss (entropy changes should be gradual)
    entropy = dynamics[:, :, 1]  # [B, T]
    entropy_delta = entropy[:, 1:] - entropy[:, :-1]
    entropy_loss = (entropy_delta ** 2).mean()

    # 5. Constraint satisfaction loss
    # Bhava should stay within valid ranges
    bhava_constraint_loss = F.relu(-bhava_probs).mean()  # No negative probs
    bhava_constraint_loss += F.relu(bhava_probs - 1).mean()  # No probs > 1

    # 6. Phoneme consistency loss (phoneme energy should be smooth)
    phoneme_delta = phoneme_energy[:, 1:] - phoneme_energy[:, :-1]
    phoneme_loss = (phoneme_delta ** 2).mean()

    # Combined loss
    total_loss = (
        config.lambda_delta * delta_loss +
        config.lambda_bhava * bhava_loss +
        config.lambda_coherence * coherence_loss +
        config.lambda_entropy * entropy_loss +
        config.lambda_constraint * bhava_constraint_loss +
        config.lambda_phoneme * phoneme_loss
    )

    # Metrics
    metrics = {
        'loss': total_loss.item(),
        'delta_loss': delta_loss.item(),
        'bhava_loss': bhava_loss.item(),
        'coherence_loss': coherence_loss.item(),
        'entropy_loss': entropy_loss.item(),
        'constraint_loss': bhava_constraint_loss.item(),
        'phoneme_loss': phoneme_loss.item(),
        'mean_coherence': coherence.mean().item(),
        'mean_entropy': entropy.mean().item(),
        **{k: v.item() if torch.is_tensor(v) else v for k, v in delta_metrics.items()},
    }

    return total_loss, metrics


# =============================================================================
# ONTOLOGICAL MODEL WRAPPER
# =============================================================================

class OntologicalTransformer(nn.Module):
    """
    Wrapper that adds ontological perception to a base transformer.

    Architecture:
        tokens → base_transformer → hidden → perception → cognitive_state
                                                              ↓
                                                    delta_predictor → loss
    """

    def __init__(
        self,
        base_model: nn.Module,
        config: OntologicalTrainingConfig,
    ):
        super().__init__()
        self.base_model = base_model
        self.config = config

        # Ontological perception (hidden → cognitive state)
        self.perception = OntologicalPerception(
            vocab_size=config.vocab_size,
            embed_dim=config.embed_dim,
            num_phonemes=config.num_phonemes,
            topic_dim=config.topic_dim,
            num_bhava=config.num_bhava,
        )

        # State projector (alternative path)
        self.state_projector = StateProjector(
            hidden_dim=config.embed_dim,
            num_phonemes=config.num_phonemes,
            topic_dim=config.topic_dim,
            num_ontology=config.num_bhava,
        )

        # Delta predictor
        self.delta_predictor = OntologicalDeltaPredictor(
            state_dim=config.state_dim,
            num_phonemes=config.num_phonemes,
            topic_dim=config.topic_dim,
            num_ontology=config.num_bhava,
        )

        # Ontology mapper (for transition loss)
        self.ontology_mapper = OntologyMapper(
            num_phonemes=config.num_phonemes,
            topic_dim=config.topic_dim,
            num_bhava=config.num_bhava,
        )

    def forward(
        self,
        input_ids: torch.Tensor,
        use_perception: bool = True,
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass returning cognitive states.

        Args:
            input_ids: [B, T] token indices
            use_perception: Use full perception or simple projection

        Returns:
            Dict with hidden_states, cognitive_states, perception_output
        """
        # Get hidden states from base model (NO LM HEAD!)
        hidden_states = self.base_model.forward_hidden(input_ids)

        if use_perception:
            # Full perception pipeline
            perception_output = self.perception(hidden_states, input_ids)
            cognitive_states = perception_output['full_state']
        else:
            # Simple projection
            cognitive_states = self.state_projector(hidden_states)
            perception_output = None

        return {
            'hidden_states': hidden_states,
            'cognitive_states': cognitive_states,
            'perception_output': perception_output,
        }

    def compute_loss(
        self,
        input_ids: torch.Tensor,
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Compute ontological training loss.

        Args:
            input_ids: [B, T] token indices

        Returns:
            loss: Total loss
            metrics: Dict of component metrics
        """
        # Forward pass
        output = self.forward(input_ids)
        cognitive_states = output['cognitive_states']

        # Compute loss
        loss, metrics = compute_ontological_loss(
            cognitive_states,
            self.delta_predictor,
            self.ontology_mapper,
            self.config,
        )

        return loss, metrics


# =============================================================================
# TRAINING STEP
# =============================================================================

def ontological_train_step(
    model: OntologicalTransformer,
    batch: Tuple[torch.Tensor, torch.Tensor],
    optimizer: AdamW,
    scheduler: LambdaLR,
    scaler: Optional[GradScaler],
    config: OntologicalTrainingConfig,
    device: torch.device,
    accumulation_step: int,
) -> Dict[str, float]:
    """
    Single ontological training step.

    Key difference from standard training:
    - No token loss
    - Loss computed in cognitive state space
    - Much lower memory usage
    """
    x, _ = batch  # y (targets) not used in ontological training
    x = x.to(device)

    # Mixed precision
    use_amp = config.mixed_precision != "none" and device.type == "cuda"
    dtype = torch.bfloat16 if config.mixed_precision == "bf16" else torch.float16

    with autocast(device_type='cuda', enabled=use_amp, dtype=dtype):
        # Forward and loss
        loss, metrics = model.compute_loss(x)
        loss = loss / config.gradient_accumulation

    # Backward
    if scaler is not None:
        scaler.scale(loss).backward()
    else:
        loss.backward()

    # Gradient step
    if (accumulation_step + 1) % config.gradient_accumulation == 0:
        if scaler is not None:
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(model.parameters(), config.max_grad_norm)
            scaler.step(optimizer)
            scaler.update()
        else:
            torch.nn.utils.clip_grad_norm_(model.parameters(), config.max_grad_norm)
            optimizer.step()

        scheduler.step()
        optimizer.zero_grad()

    return metrics


# =============================================================================
# MAIN TRAINING LOOP
# =============================================================================

def train_ontological(
    base_model: nn.Module,
    train_loader: DataLoader,
    val_loader: Optional[DataLoader],
    config: OntologicalTrainingConfig,
):
    """
    Main training loop for Tier 3 ontological training.

    Args:
        base_model: Base transformer (PhaseTransformer or HybridPhaseTransformer)
        train_loader: Training data loader
        val_loader: Validation data loader (optional)
        config: Training configuration
    """
    # Device
    if config.device == "auto":
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(config.device)

    print(f"\n{'='*60}")
    print("TIER 3: Ontological State-Delta Training")
    print(f"{'='*60}")
    print(f"Device: {device}")
    print(f"Max sequence length: {config.max_seq_len:,}")
    print(f"State dimension: {config.state_dim} (vs 50K tokens)")
    print(f"Memory reduction: ~{50257 / config.state_dim:.0f}x")

    # Wrap base model
    model = OntologicalTransformer(base_model, config).to(device)

    # Enable gradient checkpointing
    if config.gradient_checkpointing:
        if hasattr(base_model, 'gradient_checkpointing_enable'):
            base_model.gradient_checkpointing_enable()
        print("Gradient checkpointing: ENABLED")

    # Count parameters
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Total parameters: {total_params:,}")
    print(f"Trainable parameters: {trainable_params:,}")

    # Optimizer
    optimizer = AdamW(
        model.parameters(),
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
    )

    # Scheduler
    def lr_lambda(step):
        if step < config.warmup_steps:
            return step / config.warmup_steps
        progress = (step - config.warmup_steps) / (config.max_steps - config.warmup_steps)
        return 0.5 * (1 + math.cos(math.pi * progress))

    scheduler = LambdaLR(optimizer, lr_lambda)

    # Mixed precision scaler
    scaler = GradScaler() if config.mixed_precision != "none" and device.type == "cuda" else None

    # Training loop
    print(f"\nStarting training for {config.max_steps} steps...")
    print(f"{'='*60}\n")

    model.train()
    global_step = 0
    accumulation_step = 0
    total_loss = 0.0

    start_time = time.time()

    for epoch in range(1000):  # Effectively infinite epochs
        for batch in train_loader:
            if global_step >= config.max_steps:
                break

            # Training step
            metrics = ontological_train_step(
                model, batch, optimizer, scheduler, scaler,
                config, device, accumulation_step
            )

            total_loss += metrics['loss']
            accumulation_step += 1

            if (accumulation_step) % config.gradient_accumulation == 0:
                global_step += 1

                # Logging
                if global_step % config.log_every == 0:
                    avg_loss = total_loss / config.log_every
                    elapsed = time.time() - start_time
                    steps_per_sec = global_step / elapsed

                    print(f"Step {global_step:6d} | "
                          f"Loss: {avg_loss:.4f} | "
                          f"Delta: {metrics.get('delta_loss', 0):.4f} | "
                          f"Bhava: {metrics.get('bhava_loss', 0):.4f} | "
                          f"Coherence: {metrics.get('mean_coherence', 0):.3f} | "
                          f"Entropy: {metrics.get('mean_entropy', 0):.3f} | "
                          f"LR: {scheduler.get_last_lr()[0]:.2e} | "
                          f"Steps/s: {steps_per_sec:.2f}")

                    total_loss = 0.0

                # Save checkpoint
                if global_step % config.save_every == 0:
                    os.makedirs(config.checkpoint_dir, exist_ok=True)
                    checkpoint_path = os.path.join(
                        config.checkpoint_dir,
                        f"ontological_step_{global_step}.pt"
                    )
                    torch.save({
                        'step': global_step,
                        'model_state_dict': model.state_dict(),
                        'optimizer_state_dict': optimizer.state_dict(),
                        'scheduler_state_dict': scheduler.state_dict(),
                        'config': config,
                    }, checkpoint_path)
                    print(f"Saved checkpoint to {checkpoint_path}")

        if global_step >= config.max_steps:
            break

    print(f"\n{'='*60}")
    print("Training complete!")
    print(f"{'='*60}")

    return model


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    """Command-line interface for ontological training."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Tier 3: Ontological State-Delta Training"
    )

    parser.add_argument("--max_seq_len", type=int, default=1_000_000)
    parser.add_argument("--batch_size", type=int, default=1)
    parser.add_argument("--max_steps", type=int, default=10000)
    parser.add_argument("--learning_rate", type=float, default=1e-4)
    parser.add_argument("--checkpoint_dir", type=str, default="checkpoints/ontological")
    parser.add_argument("--dataset", type=str, default="wikitext103")

    args = parser.parse_args()

    config = OntologicalTrainingConfig(
        max_seq_len=args.max_seq_len,
        batch_size=args.batch_size,
        max_steps=args.max_steps,
        learning_rate=args.learning_rate,
        checkpoint_dir=args.checkpoint_dir,
        dataset=args.dataset,
    )

    print("Ontological Training Configuration:")
    for k, v in vars(config).items():
        print(f"  {k}: {v}")

    # Note: In practice, you'd load the base model and data loader here
    print("\nTo run training, use:")
    print("  from symbolu.experimental.ontological_trainer import train_ontological")
    print("  train_ontological(base_model, train_loader, val_loader, config)")


if __name__ == "__main__":
    main()
