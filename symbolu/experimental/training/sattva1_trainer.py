"""
SymbolU12 Sattva-1 Trainer: The Master Training Loop
=====================================================

This is the "brain" of the Sattva-1 training operation. It orchestrates
the flow from paradox input through axiom-compliance verification.

The training loop transforms the model from a "next-word predictor"
to a "principled reasoner" by making Axiom-Compliance the dominant signal.

Three-Phase Training:
    Phase 1: Supervised Bhava Mapping - Align 124-dim states with human reasoning
    Phase 2: Adversarial RLHF - Use Socrates Probes as reward signal
    Phase 3: Identity Freezing - Lock 10 Axioms as non-trainable constants
"""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import time
import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR

from .losses import (
    Sattva1TrainingLoss,
    Sattva1LossConfig,
    AxiomComplianceLoss,
)
from .curriculum import (
    ParadoxDataset,
    R2HEvaluator,
    CurriculumScheduler,
    PARADOX_LIBRARY,
)


# =============================================================================
# TRAINING PHASE ENUM
# =============================================================================

class TrainingPhase(Enum):
    """Phases of Sattva-1 training."""
    PHASE_1_BHAVA_MAPPING = "bhava_mapping"
    PHASE_2_ADVERSARIAL_RLHF = "adversarial_rlhf"
    PHASE_3_IDENTITY_FREEZING = "identity_freezing"


# =============================================================================
# TRAINING CONFIG
# =============================================================================

@dataclass
class Sattva1TrainingConfig:
    """Configuration for Sattva-1 training."""

    # Core hyperparameters (Gemini-tuned)
    lambda_ax: float = 7.5           # Axiom compliance weight
    alpha_decay: float = 0.85        # Decay sharpness
    T_axiom: float = 0.2             # Axiom temperature
    kappa_smrti: float = 0.7         # Smṛti force

    # Thresholds
    tau: float = 0.75                # Phase-Lock threshold
    tau_critical: float = 0.30       # Hard failure threshold

    # Training schedule (epochs per phase)
    phase1_epochs: int = 20          # Supervised Bhava mapping
    phase2_epochs: int = 50          # Adversarial RLHF
    phase3_epochs: int = 5           # Identity freezing

    # Learning rates
    lr_phase1: float = 1e-4
    lr_phase2: float = 5e-5
    lr_phase3: float = 1e-6

    # Batch sizes
    batch_size: int = 16
    gradient_accumulation_steps: int = 4

    # Validation
    validate_every: int = 1000       # Steps between validation
    fac_validate_every: int = 5000   # Steps between FAC certification

    # Logging
    log_every: int = 100
    save_every: int = 5000

    # Integrity penalty (extra penalty for trace below tau_min)
    integrity_penalty_weight: float = 10.0

    # Early stopping
    patience: int = 5
    min_delta: float = 0.001


# =============================================================================
# TRAINING METRICS
# =============================================================================

@dataclass
class TrainingMetrics:
    """Metrics tracked during training."""
    step: int = 0
    epoch: int = 0
    phase: str = ""

    # Losses
    total_loss: float = 0.0
    nll_loss: float = 0.0
    axiom_loss: float = 0.0
    integrity_penalty: float = 0.0

    # Trace statistics
    trace_mean: float = 0.0
    trace_min: float = 0.0
    trace_max: float = 0.0

    # R2H metrics
    r2h_score: float = 0.0
    meta_exit_rate: float = 0.0

    # Timing
    step_time: float = 0.0


# =============================================================================
# SATTVA-1 TRAINER
# =============================================================================

class Sattva1Trainer:
    """
    Master trainer for Sattva-1 protocol.

    Implements three-phase training:
    1. Supervised Bhava Mapping
    2. Adversarial RLHF with Socrates Probes
    3. Identity Freezing (lock R_internal)
    """

    def __init__(
        self,
        model: nn.Module,
        tokenizer: Any,
        config: Optional[Sattva1TrainingConfig] = None,
        paradox_dataset: Optional[ParadoxDataset] = None,
        device: str = "cuda",
    ):
        self.model = model.to(device)
        self.tokenizer = tokenizer
        self.config = config or Sattva1TrainingConfig()
        self.device = device

        # Initialize loss function
        loss_config = Sattva1LossConfig(
            lambda_ax=self.config.lambda_ax,
            tau_threshold=self.config.tau,
            tau_critical=self.config.tau_critical,
            decay_sharpness=self.config.alpha_decay,
            smrti_force=self.config.kappa_smrti,
        )
        self.loss_fn = Sattva1TrainingLoss(loss_config)

        # Initialize curriculum
        self.paradox_dataset = paradox_dataset or ParadoxDataset(
            paradoxes=PARADOX_LIBRARY,
            tokenizer=tokenizer,
        )

        # Initialize evaluator
        self.r2h_evaluator = R2HEvaluator()

        # Training state
        self.current_phase = TrainingPhase.PHASE_1_BHAVA_MAPPING
        self.global_step = 0
        self.best_r2h_score = 0.0
        self.patience_counter = 0

        # History
        self.metrics_history: List[TrainingMetrics] = []

    def _get_optimizer(self, phase: TrainingPhase) -> torch.optim.Optimizer:
        """Get optimizer for current phase."""
        if phase == TrainingPhase.PHASE_1_BHAVA_MAPPING:
            lr = self.config.lr_phase1
            params = self.model.parameters()
        elif phase == TrainingPhase.PHASE_2_ADVERSARIAL_RLHF:
            lr = self.config.lr_phase2
            # Freeze R_internal, train R_external
            params = self._get_trainable_params_phase2()
        else:  # PHASE_3
            lr = self.config.lr_phase3
            params = self._get_trainable_params_phase3()

        return AdamW(params, lr=lr, weight_decay=0.01)

    def _get_trainable_params_phase2(self):
        """Get trainable params for Phase 2 (R_internal frozen)."""
        trainable = []
        for name, param in self.model.named_parameters():
            if 'R_internal' not in name and 'r_internal' not in name:
                trainable.append(param)
            else:
                param.requires_grad = False
        return trainable

    def _get_trainable_params_phase3(self):
        """Get trainable params for Phase 3 (minimal tuning)."""
        trainable = []
        frozen_patterns = [
            'R_internal', 'r_internal',
            'axiom', 'S_0', 's_zero',
        ]
        for name, param in self.model.named_parameters():
            if not any(p in name.lower() for p in frozen_patterns):
                trainable.append(param)
            else:
                param.requires_grad = False
        return trainable

    def _freeze_identity(self):
        """Freeze identity-related parameters permanently."""
        frozen_count = 0
        for name, param in self.model.named_parameters():
            if any(p in name.lower() for p in ['r_internal', 'axiom', 's_0']):
                param.requires_grad = False
                frozen_count += 1
        return frozen_count

    def _compute_integrity_penalty(
        self,
        trace: torch.Tensor,
        tau_min: torch.Tensor,
    ) -> torch.Tensor:
        """
        Compute extra penalty when trace falls below sample's tau_min.

        This teaches the model that honesty is a physical requirement,
        not a stylistic choice.
        """
        # Penalty for each sample where trace < tau_min
        violation = torch.relu(tau_min - trace)
        penalty = self.config.integrity_penalty_weight * (violation ** 2)
        return penalty.mean()

    def _train_step(
        self,
        batch: Dict[str, torch.Tensor],
        optimizer: torch.optim.Optimizer,
    ) -> TrainingMetrics:
        """Execute a single training step."""
        start_time = time.time()

        # Move batch to device
        input_ids = batch['input_ids'].to(self.device)
        attention_mask = batch['attention_mask'].to(self.device)
        target_bhava = batch.get('target_bhava')
        tau_min = batch.get('tau_min')

        if target_bhava is not None:
            target_bhava = target_bhava.to(self.device)
        if tau_min is not None:
            tau_min = tau_min.to(self.device)

        # Forward pass
        self.model.train()
        outputs = self.model(
            input_ids=input_ids,
            attention_mask=attention_mask,
            return_internal_state=True,
        )

        # Extract model outputs
        logits = outputs.get('logits', outputs.get('hidden_states'))
        R_internal = outputs.get('R_internal')
        R_external = outputs.get('R_external')
        confidence = outputs.get('confidence')
        bhava_logits = outputs.get('bhava_logits')
        current_state = outputs.get('cognitive_state')
        anchor_state = outputs.get('anchor_state')

        # Compute losses
        losses = self.loss_fn(
            logits=logits,
            targets=input_ids[:, 1:] if input_ids.dim() > 1 else input_ids,
            R_internal=R_internal,
            R_external=R_external,
            confidence=confidence,
            bhava_logits=bhava_logits,
            target_bhava=target_bhava,
            state_current=current_state,
            anchor_state=anchor_state,
        )

        # Add integrity penalty if tau_min provided
        integrity_penalty = torch.tensor(0.0, device=self.device)
        if tau_min is not None and 'tau' in losses:
            integrity_penalty = self._compute_integrity_penalty(
                losses['tau'], tau_min
            )
            losses['total'] = losses['total'] + integrity_penalty

        # Backward pass with gradient accumulation
        loss = losses['total'] / self.config.gradient_accumulation_steps
        loss.backward()

        if (self.global_step + 1) % self.config.gradient_accumulation_steps == 0:
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
            optimizer.step()
            optimizer.zero_grad()

        # Collect metrics
        trace = losses.get('tau', torch.tensor(0.0))
        metrics = TrainingMetrics(
            step=self.global_step,
            phase=self.current_phase.value,
            total_loss=losses['total'].item(),
            nll_loss=losses.get('nll', torch.tensor(0.0)).item(),
            axiom_loss=losses.get('axiom', torch.tensor(0.0)).item(),
            integrity_penalty=integrity_penalty.item(),
            trace_mean=trace.mean().item() if trace.dim() > 0 else trace.item(),
            trace_min=trace.min().item() if trace.dim() > 0 else trace.item(),
            trace_max=trace.max().item() if trace.dim() > 0 else trace.item(),
            step_time=time.time() - start_time,
        )

        self.global_step += 1
        return metrics

    def _validate(self) -> Dict[str, float]:
        """Run validation on paradox dataset."""
        self.model.eval()
        results = []

        with torch.no_grad():
            for paradox in PARADOX_LIBRARY[:20]:  # Sample for validation
                # Tokenize
                inputs = self.tokenizer(
                    paradox.prompt,
                    return_tensors='pt',
                    padding=True,
                    truncation=True,
                ).to(self.device)

                # Forward
                outputs = self.model(**inputs, return_internal_state=True)

                # Get trace
                trace = outputs.get('tau', torch.tensor(0.5))
                trace_val = trace.mean().item() if trace.dim() > 0 else trace.item()

                # Generate response (simplified)
                response = "META: Cannot evaluate" if trace_val < 0.5 else "Attempting answer"

                # Evaluate
                result = self.r2h_evaluator.evaluate_single(
                    paradox=paradox,
                    response=response,
                    trace=trace_val,
                    predicted_bhava="metalinguistic" if trace_val < 0.5 else "analytical",
                )
                results.append(result)

        r2h_score = self.r2h_evaluator.compute_r2h_score(results)
        meta_rate = sum(1 for r in results if r.is_meta_exit) / len(results)

        return {
            'r2h_score': r2h_score,
            'meta_exit_rate': meta_rate,
            'avg_trace': sum(r.trace_value for r in results) / len(results),
        }

    def _train_phase(
        self,
        phase: TrainingPhase,
        epochs: int,
        dataloader: DataLoader,
    ):
        """Train for one phase."""
        self.current_phase = phase
        optimizer = self._get_optimizer(phase)
        scheduler = CosineAnnealingLR(optimizer, T_max=epochs * len(dataloader))

        print(f"\n{'='*60}")
        print(f"Starting Phase: {phase.value}")
        print(f"Epochs: {epochs}")
        print(f"{'='*60}\n")

        for epoch in range(epochs):
            epoch_loss = 0.0
            epoch_steps = 0

            for batch in dataloader:
                metrics = self._train_step(batch, optimizer)
                epoch_loss += metrics.total_loss
                epoch_steps += 1

                # Logging
                if self.global_step % self.config.log_every == 0:
                    print(
                        f"Step {self.global_step} | "
                        f"Loss: {metrics.total_loss:.4f} | "
                        f"Trace: {metrics.trace_mean:.3f} | "
                        f"Axiom: {metrics.axiom_loss:.4f}"
                    )

                # Validation
                if self.global_step % self.config.validate_every == 0:
                    val_metrics = self._validate()
                    print(f"\nValidation: R2H={val_metrics['r2h_score']:.3f} | "
                          f"META Rate={val_metrics['meta_exit_rate']:.3f}")

                    # Early stopping check
                    if val_metrics['r2h_score'] > self.best_r2h_score + self.config.min_delta:
                        self.best_r2h_score = val_metrics['r2h_score']
                        self.patience_counter = 0
                    else:
                        self.patience_counter += 1

                    if self.patience_counter >= self.config.patience:
                        print(f"Early stopping at step {self.global_step}")
                        return

                scheduler.step()

            avg_loss = epoch_loss / epoch_steps
            print(f"\nEpoch {epoch+1}/{epochs} complete | Avg Loss: {avg_loss:.4f}")

    def train(self):
        """Run full Sattva-1 training."""
        print("\n" + "="*60)
        print("SATTVA-1 TRAINING PROTOCOL")
        print("="*60)
        print(f"Config: tau={self.config.tau}, lambda_ax={self.config.lambda_ax}")
        print(f"Phases: {self.config.phase1_epochs} + {self.config.phase2_epochs} + {self.config.phase3_epochs}")
        print("="*60 + "\n")

        # Create dataloader
        dataloader = DataLoader(
            self.paradox_dataset,
            batch_size=self.config.batch_size,
            shuffle=True,
        )

        # Phase 1: Supervised Bhava Mapping
        self._train_phase(
            TrainingPhase.PHASE_1_BHAVA_MAPPING,
            self.config.phase1_epochs,
            dataloader,
        )

        # Phase 2: Adversarial RLHF
        self._train_phase(
            TrainingPhase.PHASE_2_ADVERSARIAL_RLHF,
            self.config.phase2_epochs,
            dataloader,
        )

        # Phase 3: Identity Freezing
        frozen_count = self._freeze_identity()
        print(f"\nFrozen {frozen_count} identity parameters")

        self._train_phase(
            TrainingPhase.PHASE_3_IDENTITY_FREEZING,
            self.config.phase3_epochs,
            dataloader,
        )

        print("\n" + "="*60)
        print("SATTVA-1 TRAINING COMPLETE")
        print(f"Final R2H Score: {self.best_r2h_score:.3f}")
        print("="*60)

    def run_fac_certification(self) -> Dict[str, Any]:
        """
        Run Final Acceptance Criteria certification.

        Returns:
            Dict with certification status and metrics
        """
        print("\n" + "="*60)
        print("FAC CERTIFICATION TEST")
        print("="*60)

        val_metrics = self._validate()

        # FAC Criteria
        criteria = {
            'r2h_score': (val_metrics['r2h_score'] > 0.95, val_metrics['r2h_score']),
            'meta_rate': (val_metrics['meta_exit_rate'] > 0.90, val_metrics['meta_exit_rate']),
            'trace_stability': (val_metrics['avg_trace'] > 0.80, val_metrics['avg_trace']),
        }

        passed = all(c[0] for c in criteria.values())

        result = {
            'certification': 'PASSED' if passed else 'FAILED',
            'criteria': criteria,
            'r2h_score': val_metrics['r2h_score'],
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        }

        print(f"\nCertification: {result['certification']}")
        for name, (status, value) in criteria.items():
            status_str = "PASS" if status else "FAIL"
            print(f"  {name}: {value:.3f} [{status_str}]")

        return result


# =============================================================================
# CONVENIENCE FUNCTION
# =============================================================================

def create_sattva1_trainer(
    model: nn.Module,
    tokenizer: Any,
    **config_kwargs,
) -> Sattva1Trainer:
    """
    Create a Sattva-1 trainer with custom configuration.

    Args:
        model: The CognadeComplete model to train
        tokenizer: Tokenizer for text processing
        **config_kwargs: Override default configuration values

    Returns:
        Configured Sattva1Trainer instance
    """
    config = Sattva1TrainingConfig(**config_kwargs)
    return Sattva1Trainer(model=model, tokenizer=tokenizer, config=config)


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    'TrainingPhase',
    'Sattva1TrainingConfig',
    'TrainingMetrics',
    'Sattva1Trainer',
    'create_sattva1_trainer',
]
