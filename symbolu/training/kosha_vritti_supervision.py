"""
Kosha-Vritti Structured Supervision (Static Compatibility Version)
==================================================================

Auxiliary supervision for causal language models using:
- Soft-label KL training for Kosha (4 classes) and Vritti (5 classes)
- Entropy floor (anti-collapse)
- Static joint compatibility matrix W_kv
- Staged Viparyaya/Nidra curriculum
- DDP-safe collapse detection
- AMP-safe numerics (FP32 auxiliaries)

This module does NOT modify transformer blocks or attention mechanisms.
It only adds auxiliary linear heads and additional loss terms.

Reference: Kosha = {Annamaya, Pranamaya, Manomaya, Vijnanamaya}
           Vritti = {Pramana, Viparyaya, Vikalpa, Smrti, Nidra}

Author: SymbolU Team
Date: February 2026
"""

import math
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class KoshaVrittiSupervisionConfig:
    """Configuration for Kosha-Vritti structured supervision."""

    # Master toggle
    enable: bool = False

    # Number of classes
    num_koshas: int = 4   # Annamaya, Pranamaya, Manomaya, Vijnanamaya
    num_vrittis: int = 5  # Pramana, Viparyaya, Vikalpa, Smrti, Nidra

    # Loss weights (Section 6)
    weight_kosha_kl: float = 0.1
    weight_vritti_kl: float = 0.1
    weight_entropy_floor: float = 0.01
    weight_compatibility: float = 0.05
    weight_prior: float = 0.001

    # Entropy floor thresholds (Section 5C)
    # Hmin = 0.4 * log(num_classes)
    entropy_floor_ratio: float = 0.4

    # Compatibility prior matrix path (optional W0)
    compatibility_prior_path: Optional[str] = None

    # Viparyaya/Nidra curriculum (Section 7)
    curriculum_exclude_epochs: int = 2    # Epochs to exclude Viparyaya/Nidra
    curriculum_ramp_epochs: int = 1       # Epochs to linearly ramp inclusion

    # Teacher label generation
    # Default soft distributions per token type heuristic
    default_kosha_dist: str = "uniform"   # "uniform" or "heuristic"
    default_vritti_dist: str = "uniform"  # "uniform" or "heuristic"
    teacher_clamp_min: float = 1e-6       # Clamp minimum for teacher distributions

    # DDP collapse detection
    collapse_entropy_threshold: float = 0.3   # Flag if mean entropy below this
    collapse_top1_threshold: float = 0.85     # Flag if top-1 frequency above this
    collapse_check_interval: int = 100        # Steps between collapse checks

    # KL clamping for stability
    kl_clamp_max: float = 100.0  # Clamp individual KL values


# =============================================================================
# KOSHA NAMES / VRITTI NAMES
# =============================================================================

KOSHA_LABELS = ["Annamaya", "Pranamaya", "Manomaya", "Vijnanamaya"]
VRITTI_LABELS = ["Pramana", "Viparyaya", "Vikalpa", "Smrti", "Nidra"]


# =============================================================================
# TEACHER LABEL GENERATOR
# =============================================================================


class KoshaVrittiTeacherLabeler:
    """
    Generates soft teacher labels for Kosha and Vritti per token.

    Uses heuristic rules based on token properties (punctuation, stopwords,
    rare tokens, etc.) to produce soft probability distributions.

    These are NOT ground-truth labels -- they provide a structured prior
    that the model can refine through learning.
    """

    def __init__(
        self,
        config: KoshaVrittiSupervisionConfig,
        tokenizer=None,
    ):
        self.config = config
        self.tokenizer = tokenizer
        self.num_k = config.num_koshas
        self.num_v = config.num_vrittis
        self.clamp_min = config.teacher_clamp_min

        # Build token-type lookup if tokenizer available
        self._punctuation_ids = set()
        self._stopword_ids = set()
        self._build_token_sets()

    def _build_token_sets(self):
        """Pre-compute token sets for heuristic labeling."""
        if self.tokenizer is None:
            return

        # Common punctuation tokens
        punct_chars = set('.,;:!?-()[]{}"\'/\\@#$%^&*_+=<>~`|')
        # Common English stopwords
        stopwords = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'shall', 'can',
            'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by', 'from',
            'as', 'into', 'through', 'during', 'before', 'after', 'and',
            'but', 'or', 'nor', 'not', 'so', 'yet', 'both', 'either',
            'neither', 'each', 'every', 'all', 'any', 'few', 'more',
            'most', 'other', 'some', 'such', 'no', 'only', 'own', 'same',
            'than', 'too', 'very', 'just', 'it', 'its', 'he', 'she',
            'they', 'we', 'you', 'i', 'me', 'him', 'her', 'us', 'them',
            'my', 'your', 'his', 'our', 'their', 'this', 'that', 'these',
            'those', 'what', 'which', 'who', 'whom', 'how', 'when',
            'where', 'why', 'if', 'then', 'else', 'while', 'until',
        }

        if hasattr(self.tokenizer, 'get_vocab'):
            try:
                vocab = self.tokenizer.get_vocab()
                for token_str, token_id in vocab.items():
                    clean = token_str.replace('Ġ', '').replace('▁', '').strip()
                    if clean and all(c in punct_chars for c in clean):
                        self._punctuation_ids.add(token_id)
                    if clean.lower() in stopwords:
                        self._stopword_ids.add(token_id)
            except Exception:
                pass

    def generate_labels(
        self,
        input_ids: torch.Tensor,
        epoch: int = 0,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Generate soft teacher labels for a batch of token sequences.

        Args:
            input_ids: [B, T] input token IDs
            epoch: Current training epoch (for curriculum)

        Returns:
            p_k_teacher: [B, T, 4] soft Kosha labels (clamped + renormalized)
            p_v_teacher: [B, T, 5] soft Vritti labels (clamped + renormalized)
            mask_aux:    [B, T] float mask (1.0 = supervised, 0.0 = skip)
        """
        B, T = input_ids.shape
        device = input_ids.device

        # Initialize with slightly-off-uniform distributions
        # This provides a gentle structural prior
        p_k = torch.ones(B, T, self.num_k, device=device) / self.num_k
        p_v = torch.ones(B, T, self.num_v, device=device) / self.num_v
        mask = torch.ones(B, T, device=device)

        if self.config.default_kosha_dist == "heuristic" and self.tokenizer is not None:
            self._apply_heuristic_labels(input_ids, p_k, p_v, mask)

        # Clamp and renormalize (Section 2)
        p_k = torch.clamp(p_k, min=self.clamp_min)
        p_k = p_k / p_k.sum(dim=-1, keepdim=True)

        p_v = torch.clamp(p_v, min=self.clamp_min)
        p_v = p_v / p_v.sum(dim=-1, keepdim=True)

        return p_k, p_v, mask

    def _apply_heuristic_labels(
        self,
        input_ids: torch.Tensor,
        p_k: torch.Tensor,
        p_v: torch.Tensor,
        mask: torch.Tensor,
    ):
        """Apply heuristic soft labels based on token properties."""
        B, T = input_ids.shape

        for b in range(B):
            for t in range(T):
                tid = input_ids[b, t].item()

                if tid in self._punctuation_ids:
                    # Punctuation -> Annamaya (physical), Nidra (dormancy)
                    p_k[b, t] = torch.tensor(
                        [0.6, 0.15, 0.15, 0.1], device=p_k.device
                    )
                    p_v[b, t] = torch.tensor(
                        [0.1, 0.05, 0.05, 0.1, 0.7], device=p_v.device
                    )
                elif tid in self._stopword_ids:
                    # Stopwords -> Pranamaya (vital/functional), Pramana (routine truth)
                    p_k[b, t] = torch.tensor(
                        [0.2, 0.5, 0.2, 0.1], device=p_k.device
                    )
                    p_v[b, t] = torch.tensor(
                        [0.5, 0.05, 0.1, 0.25, 0.1], device=p_v.device
                    )
                else:
                    # Content words -> Manomaya/Vijnanamaya, various vrittis
                    p_k[b, t] = torch.tensor(
                        [0.1, 0.15, 0.45, 0.3], device=p_k.device
                    )
                    p_v[b, t] = torch.tensor(
                        [0.35, 0.1, 0.2, 0.25, 0.1], device=p_v.device
                    )


# =============================================================================
# AUXILIARY HEADS MODULE
# =============================================================================


class KoshaVrittiHead(nn.Module):
    """
    Auxiliary heads for Kosha and Vritti prediction plus compatibility matrix.

    Adds to the model:
    - kosha_head: Linear(hidden_dim, 4)
    - vritti_head: Linear(hidden_dim, 5)
    - W_kv: Parameter(4, 5) - static joint compatibility matrix

    These do NOT modify the transformer's forward pass.
    They operate on the hidden states produced by the last transformer layer.
    """

    def __init__(
        self,
        hidden_dim: int,
        config: KoshaVrittiSupervisionConfig,
        W0: Optional[torch.Tensor] = None,
    ):
        super().__init__()
        self.config = config
        self.hidden_dim = hidden_dim

        # Auxiliary classification heads (Section 3)
        self.kosha_head = nn.Linear(hidden_dim, config.num_koshas)
        self.vritti_head = nn.Linear(hidden_dim, config.num_vrittis)

        # Static joint compatibility matrix (Section 5D)
        self.W_kv = nn.Parameter(torch.empty(config.num_koshas, config.num_vrittis))
        nn.init.xavier_normal_(self.W_kv)

        # Optional prior matrix for regularization (Section 5E)
        if W0 is not None:
            self.register_buffer('W0', W0.clone())
        else:
            self.register_buffer('W0', None)

    def forward(
        self,
        hidden_states: torch.Tensor,
    ) -> Dict[str, torch.Tensor]:
        """
        Compute auxiliary logits from hidden states.

        Args:
            hidden_states: [B, T, hidden_dim] from last transformer layer

        Returns:
            dict with:
                k_logits: [B, T, 4]
                v_logits: [B, T, 5]
                W_kv: [4, 5] compatibility matrix
        """
        # Cast to FP32 for numerical stability (Section 5)
        h = hidden_states.float()

        k_logits = self.kosha_head(h)
        v_logits = self.vritti_head(h)

        return {
            'k_logits': k_logits,
            'v_logits': v_logits,
            'W_kv': self.W_kv,
        }


# =============================================================================
# LOSS COMPUTATION
# =============================================================================


class KoshaVrittiLoss(nn.Module):
    """
    Computes all auxiliary loss terms for Kosha-Vritti supervision.

    Loss components:
    A) Soft-label KL loss (Kosha + Vritti)
    B) Entropy floor (anti-collapse)
    C) Static joint compatibility loss
    D) Compatibility prior regularization

    All computations in FP32 for numerical stability.
    """

    def __init__(self, config: KoshaVrittiSupervisionConfig):
        super().__init__()
        self.config = config
        self.num_k = config.num_koshas
        self.num_v = config.num_vrittis

        # Entropy floor thresholds (Section 5C)
        self.Hmin_k = config.entropy_floor_ratio * math.log(config.num_koshas)
        self.Hmin_v = config.entropy_floor_ratio * math.log(config.num_vrittis)

    def forward(
        self,
        k_logits: torch.Tensor,      # [B, T, 4]
        v_logits: torch.Tensor,      # [B, T, 5]
        W_kv: torch.Tensor,          # [4, 5]
        p_k_teacher: torch.Tensor,   # [B, T, 4]
        p_v_teacher: torch.Tensor,   # [B, T, 5]
        mask_aux: torch.Tensor,      # [B, T]
        W0: Optional[torch.Tensor] = None,  # [4, 5] prior
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Compute all auxiliary losses.

        Returns:
            loss_aux: Weighted sum of auxiliary losses (scalar)
            metrics: Dictionary of individual loss values and diagnostics
        """
        cfg = self.config

        # Ensure FP32 (Section 5)
        k_logits = k_logits.float()
        v_logits = v_logits.float()
        p_k_teacher = p_k_teacher.float()
        p_v_teacher = p_v_teacher.float()
        mask_aux = mask_aux.float()

        mask_sum = mask_aux.sum() + 1e-6

        # =====================================================================
        # A) Soft-Label KL Loss (Section 5B)
        # KL(teacher || model) - sum over class dim BEFORE masking
        # =====================================================================
        log_p_k = F.log_softmax(k_logits, dim=-1)
        log_p_v = F.log_softmax(v_logits, dim=-1)

        # F.kl_div expects log-probs as input, target as probs
        # reduction="none" gives per-element KL
        kl_k = F.kl_div(log_p_k, p_k_teacher, reduction="none").sum(dim=-1)  # [B, T]
        kl_v = F.kl_div(log_p_v, p_v_teacher, reduction="none").sum(dim=-1)  # [B, T]

        # Clamp for stability
        kl_k = torch.clamp(kl_k, max=cfg.kl_clamp_max)
        kl_v = torch.clamp(kl_v, max=cfg.kl_clamp_max)

        # Apply mask and normalize
        kl_k = kl_k * mask_aux
        kl_v = kl_v * mask_aux

        loss_k = kl_k.sum() / mask_sum
        loss_v = kl_v.sum() / mask_sum

        # =====================================================================
        # B) Entropy Floor - Anti-Collapse (Section 5C)
        # =====================================================================
        p_k = torch.exp(log_p_k)
        p_v = torch.exp(log_p_v)

        # Entropy: H = -sum(p * log_p)
        H_k = -(p_k * log_p_k).sum(dim=-1)  # [B, T]
        H_v = -(p_v * log_p_v).sum(dim=-1)  # [B, T]

        # Penalize when entropy drops below floor
        loss_H = (
            F.relu(self.Hmin_k - H_k) +
            F.relu(self.Hmin_v - H_v)
        )
        loss_H = (loss_H * mask_aux).sum() / mask_sum

        # =====================================================================
        # C) Static Joint Compatibility Loss (Section 5D)
        # =====================================================================
        # Teacher joint: outer product of marginals
        # p_kv_teacher: [B, T, 4, 5]
        p_kv_teacher = p_k_teacher.unsqueeze(-1) * p_v_teacher.unsqueeze(-2)

        # Compatibility distribution from W_kv
        q_kv_logits = W_kv.view(-1)  # [20]
        q_kv = F.softmax(q_kv_logits, dim=0).view(self.num_k, self.num_v)
        q_kv = torch.clamp(q_kv, min=1e-12)
        log_q_kv = torch.log(q_kv)

        # Cross-entropy of teacher joint with compatibility dist
        # compat: [B, T]
        compat = (p_kv_teacher * log_q_kv).sum(dim=(-1, -2))
        compat = compat * mask_aux

        loss_kv = -compat.sum() / mask_sum

        # =====================================================================
        # D) Prior Regularization (Section 5E)
        # =====================================================================
        if W0 is not None:
            loss_prior = ((W_kv - W0) ** 2).mean()
        else:
            loss_prior = torch.tensor(0.0, device=k_logits.device)

        # =====================================================================
        # Total Auxiliary Loss (Section 6)
        # =====================================================================
        loss_aux = (
            cfg.weight_kosha_kl * loss_k +
            cfg.weight_vritti_kl * loss_v +
            cfg.weight_entropy_floor * loss_H +
            cfg.weight_compatibility * loss_kv +
            cfg.weight_prior * loss_prior
        )

        # =====================================================================
        # Diagnostics
        # =====================================================================
        metrics = {
            'kv_loss_total': loss_aux.item(),
            'kv_loss_kosha_kl': loss_k.item(),
            'kv_loss_vritti_kl': loss_v.item(),
            'kv_loss_entropy_floor': loss_H.item(),
            'kv_loss_compatibility': loss_kv.item(),
            'kv_loss_prior': loss_prior.item() if isinstance(loss_prior, torch.Tensor) else loss_prior,
            'kv_entropy_kosha_mean': (H_k * mask_aux).sum().item() / mask_sum.item(),
            'kv_entropy_vritti_mean': (H_v * mask_aux).sum().item() / mask_sum.item(),
            'kv_mask_coverage': mask_aux.mean().item(),
            'kv_W_kv_norm': W_kv.norm().item(),
            'kv_W_kv_min': W_kv.min().item(),
            'kv_W_kv_max': W_kv.max().item(),
        }

        # Top-1 frequency distributions (for collapse detection)
        with torch.no_grad():
            k_pred = p_k.argmax(dim=-1)  # [B, T]
            v_pred = p_v.argmax(dim=-1)  # [B, T]

            # Compute top-1 frequency per class
            k_freqs = []
            for c in range(self.num_k):
                freq = (k_pred == c).float().mean().item()
                k_freqs.append(freq)
                metrics[f'kv_kosha_freq_{KOSHA_LABELS[c]}'] = freq

            v_freqs = []
            for c in range(self.num_v):
                freq = (v_pred == c).float().mean().item()
                v_freqs.append(freq)
                metrics[f'kv_vritti_freq_{VRITTI_LABELS[c]}'] = freq

            metrics['kv_kosha_top1_freq'] = max(k_freqs) if k_freqs else 0.0
            metrics['kv_vritti_top1_freq'] = max(v_freqs) if v_freqs else 0.0

        return loss_aux, metrics


# =============================================================================
# VIPARYAYA/NIDRA CURRICULUM
# =============================================================================


class ViparyayaCurriculum:
    """
    Staged curriculum for Viparyaya and Nidra samples (Section 7).

    Epoch 1-2: Exclude Viparyaya/Nidra samples (mask_aux = 0 for those tokens)
    Epoch 3+:  Linearly ramp inclusion probability over 1 epoch

    This prevents the model from being confused by error/dormancy patterns
    before it has learned basic language structure.
    """

    def __init__(self, config: KoshaVrittiSupervisionConfig):
        self.exclude_epochs = config.curriculum_exclude_epochs
        self.ramp_epochs = config.curriculum_ramp_epochs
        # Viparyaya=1, Nidra=4 in the Vritti enum
        self.excluded_vrittis = {1, 4}

    def get_inclusion_probability(self, epoch: int) -> float:
        """
        Get the inclusion probability for Viparyaya/Nidra at current epoch.

        Returns:
            float in [0, 1]: probability of including these samples
        """
        if epoch < self.exclude_epochs:
            return 0.0
        elif epoch < self.exclude_epochs + self.ramp_epochs:
            # Linear ramp from 0 to 1 over ramp_epochs
            progress = (epoch - self.exclude_epochs) / max(self.ramp_epochs, 1)
            return min(1.0, progress)
        else:
            return 1.0

    def apply_curriculum_mask(
        self,
        mask_aux: torch.Tensor,
        p_v_teacher: torch.Tensor,
        epoch: int,
    ) -> torch.Tensor:
        """
        Apply curriculum masking to the auxiliary mask.

        Tokens where the dominant vritti is Viparyaya or Nidra get masked
        out according to the current inclusion probability.

        Args:
            mask_aux: [B, T] current mask
            p_v_teacher: [B, T, 5] vritti teacher labels
            epoch: Current epoch

        Returns:
            Updated mask_aux [B, T]
        """
        inclusion_prob = self.get_inclusion_probability(epoch)

        if inclusion_prob >= 1.0:
            return mask_aux

        # Find tokens where dominant vritti is Viparyaya(1) or Nidra(4)
        dominant_vritti = p_v_teacher.argmax(dim=-1)  # [B, T]
        is_excluded = (dominant_vritti == 1) | (dominant_vritti == 4)

        if inclusion_prob <= 0.0:
            # Fully exclude
            mask_aux = mask_aux * (~is_excluded).float()
        else:
            # Probabilistic inclusion
            include_mask = torch.rand_like(mask_aux) < inclusion_prob
            # Only exclude tokens that are both "excluded vritti" AND not included by probability
            exclude = is_excluded & ~include_mask
            mask_aux = mask_aux * (~exclude).float()

        return mask_aux


# =============================================================================
# DDP-SAFE COLLAPSE DETECTION
# =============================================================================


class CollapseDetector:
    """
    DDP-safe collapse detection for Kosha and Vritti predictions (Section 8).

    Computes per-rank metrics, then all_reduces across workers.
    Logs warnings only on rank 0.
    """

    def __init__(self, config: KoshaVrittiSupervisionConfig):
        self.config = config
        self.step_counter = 0

    def check(
        self,
        metrics: Dict[str, float],
        global_step: int,
        rank: int = 0,
        world_size: int = 1,
    ) -> Dict[str, bool]:
        """
        Check for collapse conditions.

        Args:
            metrics: Dictionary from KoshaVrittiLoss forward
            global_step: Current training step
            rank: DDP rank
            world_size: DDP world size

        Returns:
            Dictionary of collapse flags
        """
        self.step_counter += 1
        if self.step_counter % self.config.collapse_check_interval != 0:
            return {}

        alerts = {}

        # Check entropy collapse
        kosha_entropy = metrics.get('kv_entropy_kosha_mean', 1.0)
        vritti_entropy = metrics.get('kv_entropy_vritti_mean', 1.0)

        if world_size > 1 and torch.distributed.is_initialized():
            # DDP sync: all_reduce to get mean across ranks
            metric_tensor = torch.tensor(
                [kosha_entropy, vritti_entropy],
                device='cuda' if torch.cuda.is_available() else 'cpu',
            )
            torch.distributed.all_reduce(
                metric_tensor, op=torch.distributed.ReduceOp.SUM
            )
            metric_tensor /= world_size
            kosha_entropy = metric_tensor[0].item()
            vritti_entropy = metric_tensor[1].item()

        # Entropy collapse check
        if kosha_entropy < self.config.collapse_entropy_threshold:
            alerts['kosha_entropy_collapse'] = True
            if rank == 0:
                logger.warning(
                    f"[KV-COLLAPSE] Step {global_step}: Kosha entropy "
                    f"{kosha_entropy:.4f} < {self.config.collapse_entropy_threshold}"
                )

        if vritti_entropy < self.config.collapse_entropy_threshold:
            alerts['vritti_entropy_collapse'] = True
            if rank == 0:
                logger.warning(
                    f"[KV-COLLAPSE] Step {global_step}: Vritti entropy "
                    f"{vritti_entropy:.4f} < {self.config.collapse_entropy_threshold}"
                )

        # Top-1 dominance check
        kosha_top1 = metrics.get('kv_kosha_top1_freq', 0.0)
        vritti_top1 = metrics.get('kv_vritti_top1_freq', 0.0)

        if kosha_top1 > self.config.collapse_top1_threshold:
            alerts['kosha_top1_collapse'] = True
            if rank == 0:
                logger.warning(
                    f"[KV-COLLAPSE] Step {global_step}: Kosha top-1 freq "
                    f"{kosha_top1:.4f} > {self.config.collapse_top1_threshold}"
                )

        if vritti_top1 > self.config.collapse_top1_threshold:
            alerts['vritti_top1_collapse'] = True
            if rank == 0:
                logger.warning(
                    f"[KV-COLLAPSE] Step {global_step}: Vritti top-1 freq "
                    f"{vritti_top1:.4f} > {self.config.collapse_top1_threshold}"
                )

        return alerts


# =============================================================================
# SUPERVISOR (UNIFIED INTERFACE)
# =============================================================================


class KoshaVrittiSupervisor:
    """
    Unified interface for Kosha-Vritti structured supervision.

    Orchestrates:
    - Teacher label generation
    - Auxiliary head forward pass
    - Loss computation
    - Curriculum management
    - Collapse detection

    Usage in training loop:
        supervisor = KoshaVrittiSupervisor(config, hidden_dim, device)
        # Add supervisor params to optimizer
        optimizer.add_param_group({
            'params': supervisor.parameters(),
            'lr': lr, 'weight_decay': 0.01,
        })

        # In training step:
        kv_loss, kv_metrics = supervisor.step(
            hidden_states, input_ids, epoch, global_step
        )
        loss = loss + kv_loss
    """

    def __init__(
        self,
        config: KoshaVrittiSupervisionConfig,
        hidden_dim: int,
        device: torch.device,
        tokenizer=None,
    ):
        self.config = config
        self.device = device

        # Load optional prior matrix
        W0 = None
        if config.compatibility_prior_path:
            try:
                W0 = torch.load(config.compatibility_prior_path, weights_only=True)
                logger.info(f"[KV] Loaded compatibility prior from {config.compatibility_prior_path}")
            except Exception as e:
                logger.warning(f"[KV] Failed to load prior: {e}")

        # Create components
        self.head = KoshaVrittiHead(hidden_dim, config, W0=W0).to(device)
        self.loss_fn = KoshaVrittiLoss(config).to(device)
        self.labeler = KoshaVrittiTeacherLabeler(config, tokenizer=tokenizer)
        self.curriculum = ViparyayaCurriculum(config)
        self.collapse_detector = CollapseDetector(config)

    def parameters(self):
        """Return trainable parameters (for optimizer)."""
        return self.head.parameters()

    def state_dict(self):
        """Return state dict for checkpointing."""
        return {
            'head': self.head.state_dict(),
        }

    def load_state_dict(self, state_dict):
        """Load state dict from checkpoint."""
        if 'head' in state_dict:
            self.head.load_state_dict(state_dict['head'])

    def step(
        self,
        hidden_states: torch.Tensor,  # [B, T, hidden_dim]
        input_ids: torch.Tensor,      # [B, T]
        epoch: int = 0,
        global_step: int = 0,
        rank: int = 0,
        world_size: int = 1,
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Perform one supervision step.

        Args:
            hidden_states: Last-layer hidden states [B, T, hidden_dim]
            input_ids: Input token IDs [B, T] (NOT shifted targets)
            epoch: Current epoch
            global_step: Current global step
            rank: DDP rank
            world_size: DDP world size

        Returns:
            loss: Auxiliary loss (scalar tensor)
            metrics: Dictionary of diagnostic metrics
        """
        # Generate teacher labels (aligned with input_ids, not targets)
        p_k_teacher, p_v_teacher, mask_aux = self.labeler.generate_labels(
            input_ids, epoch=epoch,
        )

        # Apply Viparyaya/Nidra curriculum
        mask_aux = self.curriculum.apply_curriculum_mask(
            mask_aux, p_v_teacher, epoch,
        )

        # Forward through auxiliary heads
        head_out = self.head(hidden_states)

        # Compute losses (all FP32)
        loss, metrics = self.loss_fn(
            k_logits=head_out['k_logits'],
            v_logits=head_out['v_logits'],
            W_kv=head_out['W_kv'],
            p_k_teacher=p_k_teacher,
            p_v_teacher=p_v_teacher,
            mask_aux=mask_aux,
            W0=self.head.W0,
        )

        # Collapse detection
        alerts = self.collapse_detector.check(
            metrics, global_step, rank=rank, world_size=world_size,
        )
        if alerts:
            metrics['kv_collapse_alerts'] = len(alerts)

        # Curriculum info
        metrics['kv_curriculum_inclusion'] = self.curriculum.get_inclusion_probability(epoch)

        return loss, metrics


# =============================================================================
# LOGGING UTILITY
# =============================================================================


def log_kv_metrics(
    metrics: Dict[str, float],
    global_step: int,
    writer=None,
    print_every: int = 100,
    rank: int = 0,
):
    """
    Log Kosha-Vritti metrics to console and TensorBoard.

    Only logs on rank 0 for DDP.

    Args:
        metrics: Dictionary from KoshaVrittiSupervisor.step()
        global_step: Current step
        writer: Optional TensorBoard SummaryWriter
        print_every: Console print interval
        rank: DDP rank (only log on rank 0)
    """
    if rank != 0:
        return

    # TensorBoard logging
    if writer is not None:
        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                writer.add_scalar(f"kv/{key}", value, global_step)

    # Console logging
    if global_step % print_every == 0 and global_step > 0:
        total = metrics.get('kv_loss_total', 0.0)
        kl_k = metrics.get('kv_loss_kosha_kl', 0.0)
        kl_v = metrics.get('kv_loss_vritti_kl', 0.0)
        h_k = metrics.get('kv_entropy_kosha_mean', 0.0)
        h_v = metrics.get('kv_entropy_vritti_mean', 0.0)
        mask_cov = metrics.get('kv_mask_coverage', 0.0)
        curriculum = metrics.get('kv_curriculum_inclusion', 1.0)

        print(
            f"  [KV] Step {global_step} | "
            f"Loss={total:.4f} | "
            f"KL(K)={kl_k:.4f} KL(V)={kl_v:.4f} | "
            f"H(K)={h_k:.3f} H(V)={h_v:.3f} | "
            f"Mask={mask_cov:.2f} Curr={curriculum:.2f}"
        )
