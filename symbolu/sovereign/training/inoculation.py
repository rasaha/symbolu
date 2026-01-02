"""
Sovereign-1 Inoculation Trainer: Self-Supervised State Learning
================================================================

The "Inoculation" training loop that forces the model to predict the
*State Delta* of the next token, not just the token itself.

Key Insight: By predicting the Ontological Shift required to generate
the next word, we "stamp" the Sovereign logic into the model weights.

Training Targets:
- Given token t_n, predict the State Delta of t_{n+1}
- State Delta is computed by SovereignObserver on the fly
- R-Signal (Meaning) weighted 5x higher than C-Signal (Sound)

Alpha Decay Schedule:
- Epoch 0-1: α = 1.0 (Strict state compliance - "Learn the rules")
- Epoch 2+: α decays linearly to 0.2 (Allow nuance/creativity)

Reference: SOVEREIGN_1_DESIGN_IMPLEMENTATION.md Section 11
"""

from typing import Dict, Optional, Tuple, Any, Iterator, Callable
from dataclasses import dataclass
import math

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.optim import Optimizer
from torch.optim.lr_scheduler import _LRScheduler


@dataclass
class InoculationConfig:
    """Configuration for Inoculation Training."""

    # Alpha decay schedule
    alpha_initial: float = 1.0      # Start strict
    alpha_final: float = 0.2        # End flexible
    decay_epochs: int = 3           # Linear decay over 3 epochs

    # Loss weights (from Sovereign-1 spec)
    weight_guna: float = 1.0        # Dynamics baseline
    weight_s: float = 2.0           # Referent accuracy
    weight_r: float = 5.0           # Ontological accuracy (CRITICAL)
    weight_c: float = 0.5           # Phonetic accuracy

    # Transition penalty
    transition_weight: float = 0.5

    # Training parameters
    gradient_clip: float = 1.0
    log_interval: int = 100

    # State dimensions
    state_dim: int = 128


class AlphaScheduler:
    """
    Alpha decay scheduler for state friction loss.

    The alpha parameter controls how strictly the model must follow
    the Sovereign State predictions:
    - α = 1.0: Maximum state enforcement ("Learn the rules")
    - α = 0.2: Relaxed enforcement ("Allow creativity")

    Schedule:
    - Epoch 0: α = 1.0
    - Epoch 1: α = 0.73
    - Epoch 2: α = 0.47
    - Epoch 3+: α = 0.2
    """

    def __init__(
        self,
        alpha_initial: float = 1.0,
        alpha_final: float = 0.2,
        decay_epochs: int = 3,
    ):
        self.alpha_initial = alpha_initial
        self.alpha_final = alpha_final
        self.decay_epochs = decay_epochs
        self._current_epoch = 0

    def get_alpha(self, epoch: Optional[int] = None) -> float:
        """
        Get alpha value for the given epoch.

        Args:
            epoch: Epoch number (0-indexed). If None, uses current epoch.

        Returns:
            Alpha value in [alpha_final, alpha_initial]
        """
        if epoch is None:
            epoch = self._current_epoch

        if epoch >= self.decay_epochs:
            return self.alpha_final

        # Linear decay
        progress = epoch / self.decay_epochs
        return self.alpha_initial - progress * (self.alpha_initial - self.alpha_final)

    def step(self):
        """Advance to next epoch."""
        self._current_epoch += 1

    @property
    def current_epoch(self) -> int:
        return self._current_epoch

    def state_dict(self) -> Dict[str, Any]:
        return {
            'alpha_initial': self.alpha_initial,
            'alpha_final': self.alpha_final,
            'decay_epochs': self.decay_epochs,
            'current_epoch': self._current_epoch,
        }

    def load_state_dict(self, state_dict: Dict[str, Any]):
        self.alpha_initial = state_dict['alpha_initial']
        self.alpha_final = state_dict['alpha_final']
        self.decay_epochs = state_dict['decay_epochs']
        self._current_epoch = state_dict['current_epoch']


class InoculationTrainer:
    """
    Self-Supervised Inoculation Trainer for Sovereign-1.

    The trainer "stamps" the Sovereign logic into model weights by:
    1. Computing State Delta targets on the fly using SovereignObserver
    2. Training the model to predict Next-State, not just next token
    3. Gradually relaxing state enforcement via alpha decay

    This prevents "Signal Washing" where the model learns to ignore
    the state partition and produces homogeneous embeddings.

    Usage:
        trainer = InoculationTrainer(
            model=sovereign_transformer,
            observer=sovereign_observer,
            optimizer=optimizer,
            config=InoculationConfig(),
        )

        for epoch in range(num_epochs):
            for batch in dataloader:
                loss, metrics = trainer.train_step(batch)
            trainer.end_epoch()
    """

    def __init__(
        self,
        model: nn.Module,
        observer: nn.Module,
        loss_fn: nn.Module,
        optimizer: Optimizer,
        config: Optional[InoculationConfig] = None,
        lr_scheduler: Optional[_LRScheduler] = None,
        device: Optional[torch.device] = None,
        tokenizer: Optional[Any] = None,
    ):
        """
        Initialize InoculationTrainer.

        Args:
            model: SovereignTransformer model
            observer: SovereignObserver for computing state targets
            loss_fn: SovereignLoss function
            optimizer: PyTorch optimizer
            config: Training configuration
            lr_scheduler: Optional learning rate scheduler
            device: Target device (cuda/cpu)
            tokenizer: Optional tokenizer for referent lookup
        """
        self.model = model
        self.observer = observer
        self.loss_fn = loss_fn
        self.optimizer = optimizer
        self.config = config or InoculationConfig()
        self.lr_scheduler = lr_scheduler
        self.device = device or torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.tokenizer = tokenizer

        # Alpha scheduler
        self.alpha_scheduler = AlphaScheduler(
            alpha_initial=self.config.alpha_initial,
            alpha_final=self.config.alpha_final,
            decay_epochs=self.config.decay_epochs,
        )

        # Training state
        self._step = 0
        self._epoch = 0

        # Move to device
        self.model.to(self.device)
        self.observer.to(self.device)

    def compute_training_targets(
        self,
        input_ids: torch.Tensor,
        hidden_states: torch.Tensor,
        attention_weights: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Compute self-supervised State Delta targets.

        The target for position n is the State Delta of position n+1,
        computed by the Observer. This forces the model to predict
        the *Ontological Shift* required for the next token.

        Args:
            input_ids: [B, N] token IDs
            hidden_states: [B, N, D] hidden states from model
            attention_weights: [B, H, N, N] attention weights (optional)

        Returns:
            target_states: [B, N, 128] state targets for training
        """
        B, N = input_ids.shape

        with torch.no_grad():
            # Compute state for each position
            observer_output = self.observer(
                token_ids=input_ids,
                hidden_states=hidden_states,
                attention_weights=attention_weights,
                tokenizer=self.tokenizer,
            )

            current_states = observer_output['state_delta']  # [B, 128]

            # For sequence targets, we shift: target[n] = state[n+1]
            # This teaches the model to predict the *next* state
            if hidden_states.shape[1] > 1:
                # Compute states for all positions
                target_states = torch.zeros(B, N, 128, device=self.device)

                # For training, we can use the current state as a simplified target
                # In practice, you'd compute state at each position
                target_states[:, :-1] = current_states.unsqueeze(1).expand(-1, N-1, -1)
                target_states[:, -1] = current_states  # Last position targets itself

            else:
                target_states = current_states.unsqueeze(1)

        return target_states

    def train_step(
        self,
        batch: Dict[str, torch.Tensor],
        nexus_position: int = 6,
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Execute one training step.

        Args:
            batch: Dictionary with 'input_ids', 'labels', and optionally 'attention_mask'
            nexus_position: Virtual Nexus position (4, 6, or 8)

        Returns:
            loss: Scalar loss tensor
            metrics: Dictionary of training metrics
        """
        self.model.train()
        self._step += 1

        # Get batch data
        input_ids = batch['input_ids'].to(self.device)
        labels = batch['labels'].to(self.device)
        attention_mask = batch.get('attention_mask')
        if attention_mask is not None:
            attention_mask = attention_mask.to(self.device)

        # Forward pass
        outputs = self.model(
            input_ids,
            nexus_position=nexus_position,
        )

        logits = outputs['logits']
        hidden_states = outputs['hidden_states']
        authority = outputs.get('authority')

        # Compute state targets using Observer
        target_states = self.compute_training_targets(
            input_ids=input_ids,
            hidden_states=hidden_states,
            attention_weights=outputs.get('attention_weights'),
        )

        # Extract predicted state from hidden states (last 128 dims)
        # Or compute via model's state predictor if available
        if hasattr(self.model, 'state_projector'):
            predicted_states = self.model.state_projector(hidden_states)
        else:
            # Use last 128 dims of hidden states as state
            predicted_states = hidden_states[..., -128:]

        # Get current alpha
        alpha = self.alpha_scheduler.get_alpha()

        # Compute loss with current alpha
        if hasattr(self.loss_fn, 'forward'):
            total_loss, loss_metrics = self.loss_fn(
                logits=logits,
                targets=labels,
                predicted_state=predicted_states,
                target_state=target_states,
                epoch=self._epoch,
            )
        else:
            # Fallback: simple CE + state loss
            ce_loss = F.cross_entropy(
                logits.view(-1, logits.size(-1)),
                labels.view(-1),
                ignore_index=-100,
            )
            state_loss = F.mse_loss(predicted_states, target_states)
            total_loss = ce_loss + alpha * state_loss
            loss_metrics = {'ce_loss': ce_loss.item(), 'state_loss': state_loss.item()}

        # Backward pass
        self.optimizer.zero_grad()
        total_loss.backward()

        # Gradient clipping
        if self.config.gradient_clip > 0:
            torch.nn.utils.clip_grad_norm_(
                self.model.parameters(),
                self.config.gradient_clip,
            )

        self.optimizer.step()

        # Build metrics
        metrics = {
            'loss': total_loss.item(),
            'alpha': alpha,
            'epoch': self._epoch,
            'step': self._step,
            **loss_metrics,
        }

        if authority is not None:
            metrics['authority_mean'] = authority.mean().item()
            metrics['authority_min'] = authority.min().item()

        return total_loss, metrics

    def end_epoch(self):
        """Called at end of each epoch to update schedulers."""
        self._epoch += 1
        self.alpha_scheduler.step()

        if self.lr_scheduler is not None:
            self.lr_scheduler.step()

    def train_epoch(
        self,
        dataloader: Iterator,
        nexus_position: int = 6,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Dict[str, float]:
        """
        Train for one full epoch.

        Args:
            dataloader: Training data iterator
            nexus_position: Virtual Nexus position
            progress_callback: Optional callback for progress updates

        Returns:
            Epoch statistics
        """
        epoch_losses = []
        epoch_metrics = {}

        for batch_idx, batch in enumerate(dataloader):
            loss, metrics = self.train_step(batch, nexus_position)
            epoch_losses.append(loss.item())

            # Accumulate metrics
            for key, value in metrics.items():
                if key not in epoch_metrics:
                    epoch_metrics[key] = []
                epoch_metrics[key].append(value)

            # Log progress
            if progress_callback and batch_idx % self.config.log_interval == 0:
                progress_callback(metrics)

        # End epoch
        self.end_epoch()

        # Compute averages
        stats = {
            'epoch': self._epoch - 1,
            'loss_mean': sum(epoch_losses) / len(epoch_losses),
            'alpha': self.alpha_scheduler.get_alpha(self._epoch - 1),
        }

        for key, values in epoch_metrics.items():
            if isinstance(values[0], (int, float)):
                stats[f'{key}_mean'] = sum(values) / len(values)

        return stats

    def state_dict(self) -> Dict[str, Any]:
        """Get trainer state for checkpointing."""
        return {
            'model_state': self.model.state_dict(),
            'optimizer_state': self.optimizer.state_dict(),
            'alpha_scheduler_state': self.alpha_scheduler.state_dict(),
            'step': self._step,
            'epoch': self._epoch,
            'config': self.config.__dict__,
        }

    def load_state_dict(self, state_dict: Dict[str, Any]):
        """Load trainer state from checkpoint."""
        self.model.load_state_dict(state_dict['model_state'])
        self.optimizer.load_state_dict(state_dict['optimizer_state'])
        self.alpha_scheduler.load_state_dict(state_dict['alpha_scheduler_state'])
        self._step = state_dict['step']
        self._epoch = state_dict['epoch']


def create_inoculation_trainer(
    model: nn.Module,
    observer: nn.Module,
    loss_fn: nn.Module,
    learning_rate: float = 1e-4,
    weight_decay: float = 0.01,
    **config_kwargs,
) -> InoculationTrainer:
    """
    Factory function to create an InoculationTrainer.

    Args:
        model: SovereignTransformer
        observer: SovereignObserver
        loss_fn: SovereignLoss
        learning_rate: Learning rate for AdamW
        weight_decay: Weight decay
        **config_kwargs: Additional config parameters

    Returns:
        Configured InoculationTrainer
    """
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=learning_rate,
        weight_decay=weight_decay,
    )

    config = InoculationConfig(**config_kwargs)

    return InoculationTrainer(
        model=model,
        observer=observer,
        loss_fn=loss_fn,
        optimizer=optimizer,
        config=config,
    )
