"""
State-Conditional Logit Scale ("Confidence Knob") + Entropy Band Control
=========================================================================

Production-grade calibration module for causal LM training.

Modules:
  - ConfidenceScaler: Per-token learned logit scale s_t with optional
    Kosha/Vritti risk gating (Viparyaya + Nidra → increase uncertainty).
  - EntropyBandLoss: Soft band constraint on per-token output entropy
    plus a gentle scale regulariser.
  - CalibrationDiagnostics: DDP-safe metric collection for logit
    calibration monitoring.
  - ConfidenceInferenceHook: Inference-time scaling using trained
    ConfidenceScaler (with optional risk head).

Constraints:
  - Does NOT modify transformer blocks or attention.
  - Only modifies the emission path + loss + logging.
  - Works with linear / quadratic / local attention backbones (head-side only).
  - DDP-safe (no module-level mutable state across sequences).
  - AMP-safe (FP32 for scale internals, casts back to input dtype).

Reference: Gemini logit-scaling + entropy-band specification.
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
class ConfidenceScalerConfig:
    """Configuration for state-conditional logit scaling + entropy band."""

    # Master toggle
    enable: bool = False

    # ConfidenceScaler params
    s_min: float = 0.3          # Minimum scale (prevents over-sharpening)
    s_max: float = 10.0         # Maximum scale (prevents trivial uncertainty)
    epsilon: float = 1e-4       # Numerical floor for softplus output

    # Risk gating (Kosha/Vritti)
    enable_risk_gating: bool = False
    alpha_risk: float = 0.5     # Risk scaling coefficient: s' = s * (1 + alpha * r)

    # Entropy band
    entropy_band_ratio_min: float = 0.10  # H_min = ratio * log(V)
    entropy_band_ratio_max: float = 0.35  # H_max = ratio * log(V)
    lambda_entropy_band: float = 1e-3     # Weight for entropy band loss
    lambda_scale_penalty: float = 1e-4    # Weight for log(s) regulariser

    # Vritti head (optional auxiliary)
    enable_vritti_head: bool = False
    num_vrittis: int = 5        # Pramana, Viparyaya, Vikalpa, Smrti, Nidra
    vritti_kl_weight: float = 0.1
    vritti_teacher_clamp_min: float = 1e-6

    # Viparyaya index = 1, Nidra index = 4 (in standard Vritti enum)
    viparyaya_idx: int = 1
    nidra_idx: int = 4

    # Logging
    log_every: int = 10


# =============================================================================
# CONFIDENCE SCALER MODULE
# =============================================================================

class ConfidenceScaler(nn.Module):
    """
    Per-token state-conditional logit scale s_t ("confidence knob").

    Given hidden states h [B, T, D]:
        s = softplus(Linear(D→1)(h)) + epsilon
        if risk r provided: s = s * (1 + alpha_risk * r)
        s = clamp(s, s_min, s_max)

    Scaled logits: logits_scaled = logits_raw / s   (broadcast [B, T, 1])

    Args:
        hidden_dim: Dimension of input hidden states.
        config: ConfidenceScalerConfig instance.
    """

    def __init__(self, hidden_dim: int, config: Optional[ConfidenceScalerConfig] = None):
        super().__init__()
        self.config = config or ConfidenceScalerConfig()

        # Linear projection D → 1 for confidence scalar
        self.scale_proj = nn.Linear(hidden_dim, 1)

        # Initialise bias so initial s ≈ 1.0
        # softplus(x) ≈ x for x >> 0; we want softplus(b) + eps ≈ 1.0
        # softplus(0.54) ≈ 0.9996, so init bias ≈ 0.54
        nn.init.zeros_(self.scale_proj.weight)
        nn.init.constant_(self.scale_proj.bias, 0.54)

    def forward(
        self,
        hidden_states: torch.Tensor,
        risk_prob: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, Dict[str, torch.Tensor]]:
        """
        Compute per-token confidence scale.

        Args:
            hidden_states: [B, T, D] hidden states from backbone.
            risk_prob: [B, T, 1] optional risk scalar (e.g. P(Viparyaya) + P(Nidra)).

        Returns:
            s: [B, T, 1] per-token scale values (clamped).
            diagnostics: dict with 's_raw', 's_clamped' tensors for logging.
        """
        cfg = self.config

        # Compute in FP32 for numerical stability
        h = hidden_states.float()
        s_raw = F.softplus(self.scale_proj(h)) + cfg.epsilon  # [B, T, 1]

        # Risk gating: increase temperature when model detects risky states
        if risk_prob is not None and cfg.enable_risk_gating:
            r = risk_prob.float()
            s_raw = s_raw * (1.0 + cfg.alpha_risk * r)

        # Clamp to safe range
        s = torch.clamp(s_raw, min=cfg.s_min, max=cfg.s_max)

        diagnostics = {
            's_raw': s_raw.detach(),
            's_clamped': s.detach(),
        }

        return s, diagnostics

    def scale_logits(
        self,
        logits_raw: torch.Tensor,
        hidden_states: torch.Tensor,
        risk_prob: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor, Dict[str, torch.Tensor]]:
        """
        Convenience: compute s_t and apply scaling to logits in one call.

        Args:
            logits_raw: [B, T, V] raw logits from LM head.
            hidden_states: [B, T, D] backbone hidden states.
            risk_prob: [B, T, 1] optional risk scalar.

        Returns:
            logits_scaled: [B, T, V] scaled logits.
            s: [B, T, 1] scale values.
            diagnostics: dict of diagnostic tensors.
        """
        s, diagnostics = self.forward(hidden_states, risk_prob)

        # Cast s to match logits dtype and broadcast divide
        s_cast = s.to(logits_raw.dtype)
        logits_scaled = logits_raw / s_cast  # [B, T, V] / [B, T, 1]

        return logits_scaled, s, diagnostics


# =============================================================================
# ENTROPY BAND LOSS
# =============================================================================

class EntropyBandLoss(nn.Module):
    """
    Soft entropy band constraint + scale regulariser.

    L_band = lambda_H * E_t[ relu(H_min - H_t)^2 + relu(H_t - H_max)^2 ]
    L_scale = lambda_s * E_t[ log(s_t) ]

    Where H_t is per-token entropy of softmax(scaled_logits_t).

    Args:
        vocab_size: Vocabulary size (for computing H_min, H_max).
        config: ConfidenceScalerConfig instance.
    """

    def __init__(self, vocab_size: int, config: Optional[ConfidenceScalerConfig] = None):
        super().__init__()
        self.config = config or ConfidenceScalerConfig()
        self.vocab_size = vocab_size

        log_V = math.log(vocab_size)
        self.H_min = self.config.entropy_band_ratio_min * log_V
        self.H_max = self.config.entropy_band_ratio_max * log_V

    def forward(
        self,
        logits_scaled: torch.Tensor,
        s: torch.Tensor,
        ignore_index: int = -100,
        targets: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Compute entropy band loss and scale penalty.

        Args:
            logits_scaled: [B, T, V] logits after confidence scaling.
            s: [B, T, 1] per-token scale values.
            ignore_index: Padding index to mask out.
            targets: [B, T] optional targets (for masking padding tokens).

        Returns:
            loss: Scalar loss tensor.
            metrics: Dict of diagnostic values.
        """
        cfg = self.config
        B, T, V = logits_scaled.shape

        # Compute per-token entropy (in FP32)
        logits_f = logits_scaled.float()
        p = F.softmax(logits_f, dim=-1)  # [B, T, V]
        log_p = F.log_softmax(logits_f, dim=-1)  # [B, T, V]
        H = -(p * log_p).sum(dim=-1)  # [B, T]

        # Build mask for valid tokens
        if targets is not None:
            mask = (targets != ignore_index).float()  # [B, T]
        else:
            mask = torch.ones(B, T, device=logits_scaled.device, dtype=torch.float32)

        mask_sum = mask.sum().clamp(min=1.0)

        # Entropy band penalty: quadratic outside [H_min, H_max]
        below = F.relu(self.H_min - H) ** 2  # [B, T]
        above = F.relu(H - self.H_max) ** 2   # [B, T]
        band_penalty = (below + above) * mask
        L_band = cfg.lambda_entropy_band * band_penalty.sum() / mask_sum

        # Scale penalty: gentle pressure to keep s near 1 (prevent inflation)
        s_f = s.float().squeeze(-1)  # [B, T]
        log_s = torch.log(s_f)  # [B, T]
        L_scale = cfg.lambda_scale_penalty * (log_s * mask).sum() / mask_sum

        total_loss = L_band + L_scale

        # Diagnostics
        with torch.no_grad():
            H_masked = (H * mask).sum() / mask_sum
            H_vals = H[mask.bool()] if mask.any() else H.flatten()
            metrics = {
                'entropy_band_loss': L_band.item(),
                'scale_penalty_loss': L_scale.item(),
                'confidence_total_aux_loss': total_loss.item(),
                'entropy_mean': H_masked.item(),
                'entropy_H_min': self.H_min,
                'entropy_H_max': self.H_max,
            }
            if H_vals.numel() > 0:
                sorted_H = torch.sort(H_vals).values
                n = sorted_H.numel()
                metrics['entropy_p10'] = sorted_H[max(0, int(0.1 * n) - 1)].item()
                metrics['entropy_p90'] = sorted_H[min(n - 1, int(0.9 * n))].item()
            else:
                metrics['entropy_p10'] = 0.0
                metrics['entropy_p90'] = 0.0

        return total_loss, metrics


# =============================================================================
# OPTIONAL: VRITTI HEAD FOR RISK GATING
# =============================================================================

class VrittiRiskHead(nn.Module):
    """
    Auxiliary Vritti classification head for risk gating.

    Predicts 5 Vritti classes: {Pramana, Viparyaya, Vikalpa, Smrti, Nidra}
    Derives risk scalar r = P(Viparyaya) + P(Nidra) for ConfidenceScaler.

    Trained with KL divergence against teacher soft labels (if provided).
    Does NOT backprop through the backbone (operates on detached hidden states
    unless explicitly wired otherwise).

    Args:
        hidden_dim: Dimension of hidden states.
        config: ConfidenceScalerConfig instance.
    """

    def __init__(self, hidden_dim: int, config: Optional[ConfidenceScalerConfig] = None):
        super().__init__()
        self.config = config or ConfidenceScalerConfig()
        self.vritti_head = nn.Linear(hidden_dim, self.config.num_vrittis)

    def forward(self, hidden_states: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        Compute Vritti logits and risk probability.

        Args:
            hidden_states: [B, T, D] (typically detached from backbone).

        Returns:
            dict with:
                v_logits: [B, T, 5]
                v_probs: [B, T, 5]
                risk_prob: [B, T, 1]   (P(Viparyaya) + P(Nidra))
        """
        cfg = self.config
        h = hidden_states.float()
        v_logits = self.vritti_head(h)  # [B, T, 5]
        v_probs = F.softmax(v_logits, dim=-1)  # [B, T, 5]

        # Risk = P(Viparyaya) + P(Nidra)
        risk = (
            v_probs[:, :, cfg.viparyaya_idx] +
            v_probs[:, :, cfg.nidra_idx]
        ).unsqueeze(-1)  # [B, T, 1]

        return {
            'v_logits': v_logits,
            'v_probs': v_probs,
            'risk_prob': risk,
        }

    def compute_kl_loss(
        self,
        v_logits: torch.Tensor,
        teacher_probs: torch.Tensor,
        mask: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Compute KL divergence loss against teacher soft labels.

        Args:
            v_logits: [B, T, 5] predicted logits.
            teacher_probs: [B, T, 5] teacher probability distribution.
            mask: [B, T] optional mask (1=supervised).

        Returns:
            loss: Scalar KL loss.
            metrics: Dict of diagnostics.
        """
        cfg = self.config

        # Clamp and renormalise teacher
        t_probs = torch.clamp(teacher_probs.float(), min=cfg.vritti_teacher_clamp_min)
        t_probs = t_probs / t_probs.sum(dim=-1, keepdim=True)

        log_pred = F.log_softmax(v_logits.float(), dim=-1)

        # KL(teacher || model) per token
        kl = F.kl_div(log_pred, t_probs, reduction='none').sum(dim=-1)  # [B, T]
        kl = torch.clamp(kl, max=100.0)

        if mask is not None:
            mask_f = mask.float()
            mask_sum = mask_f.sum().clamp(min=1.0)
            loss = cfg.vritti_kl_weight * (kl * mask_f).sum() / mask_sum
        else:
            loss = cfg.vritti_kl_weight * kl.mean()

        with torch.no_grad():
            pred_probs = torch.exp(log_pred)
            metrics = {
                'vritti_kl_loss': loss.item(),
                'vritti_risk_mean': (
                    pred_probs[:, :, cfg.viparyaya_idx] +
                    pred_probs[:, :, cfg.nidra_idx]
                ).mean().item(),
            }

        return loss, metrics


# =============================================================================
# CALIBRATION DIAGNOSTICS (DDP-safe)
# =============================================================================

class CalibrationDiagnostics:
    """
    DDP-safe diagnostic collection for logit calibration monitoring.

    Computes:
        - logit_std_before: std(W @ h_t) (raw logits)
        - logit_std_after: std(logits / s_t) (scaled logits)
        - s_mean, s_p95, s_max
        - entropy_mean, entropy_p10, entropy_p90
        - maxprob_when_wrong (mean of max prob on incorrect tokens)
    """

    @staticmethod
    @torch.no_grad()
    def compute(
        logits_raw: torch.Tensor,
        logits_scaled: torch.Tensor,
        s: torch.Tensor,
        targets: Optional[torch.Tensor] = None,
        ignore_index: int = -100,
    ) -> Dict[str, float]:
        """
        Compute all calibration diagnostics for a batch.

        Args:
            logits_raw: [B, T, V] raw logits before scaling.
            logits_scaled: [B, T, V] logits after confidence scaling.
            s: [B, T, 1] per-token scale values.
            targets: [B, T] target token IDs (for maxprob_when_wrong).
            ignore_index: Padding index.

        Returns:
            Dict of metric name → scalar value.
        """
        metrics = {}

        # Logit statistics
        metrics['logit_std_before'] = logits_raw.float().std().item()
        metrics['logit_std_after'] = logits_scaled.float().std().item()
        metrics['logit_mean_abs_before'] = logits_raw.float().abs().mean().item()
        metrics['logit_mean_abs_after'] = logits_scaled.float().abs().mean().item()

        # Scale statistics
        s_flat = s.float().squeeze(-1)  # [B, T]
        metrics['s_mean'] = s_flat.mean().item()
        metrics['s_max'] = s_flat.max().item()

        sorted_s = torch.sort(s_flat.flatten()).values
        n = sorted_s.numel()
        if n > 0:
            metrics['s_p95'] = sorted_s[min(n - 1, int(0.95 * n))].item()
        else:
            metrics['s_p95'] = 0.0

        # Entropy statistics
        p = F.softmax(logits_scaled.float(), dim=-1)
        log_p = F.log_softmax(logits_scaled.float(), dim=-1)
        H = -(p * log_p).sum(dim=-1)  # [B, T]

        if targets is not None:
            mask = (targets != ignore_index)
            H_valid = H[mask] if mask.any() else H.flatten()
        else:
            H_valid = H.flatten()

        if H_valid.numel() > 0:
            metrics['entropy_mean'] = H_valid.mean().item()
            sorted_H = torch.sort(H_valid).values
            nh = sorted_H.numel()
            metrics['entropy_p10'] = sorted_H[max(0, int(0.1 * nh) - 1)].item()
            metrics['entropy_p90'] = sorted_H[min(nh - 1, int(0.9 * nh))].item()
        else:
            metrics['entropy_mean'] = 0.0
            metrics['entropy_p10'] = 0.0
            metrics['entropy_p90'] = 0.0

        # Max-prob when wrong
        if targets is not None:
            mask = (targets != ignore_index)
            if mask.any():
                max_probs, preds = p.max(dim=-1)  # [B, T], [B, T]
                wrong = (preds != targets) & mask
                if wrong.any():
                    metrics['maxprob_when_wrong'] = max_probs[wrong].mean().item()
                else:
                    metrics['maxprob_when_wrong'] = 0.0
            else:
                metrics['maxprob_when_wrong'] = 0.0

        return metrics

    @staticmethod
    def ddp_reduce(metrics: Dict[str, float], world_size: int = 1) -> Dict[str, float]:
        """
        All-reduce scalar metrics across DDP ranks.

        Args:
            metrics: Dict of metric name → scalar value (local rank).
            world_size: Number of DDP workers.

        Returns:
            Averaged metrics across all ranks.
        """
        if world_size <= 1 or not torch.distributed.is_initialized():
            return metrics

        keys = sorted(metrics.keys())
        values = torch.tensor(
            [metrics[k] for k in keys],
            device='cuda' if torch.cuda.is_available() else 'cpu',
        )
        torch.distributed.all_reduce(values, op=torch.distributed.ReduceOp.SUM)
        values /= world_size

        return {k: values[i].item() for i, k in enumerate(keys)}


# =============================================================================
# INFERENCE HOOK
# =============================================================================

class ConfidenceInferenceHook:
    """
    Inference-time hook that applies ConfidenceScaler at each decode step.

    Computes s_t for the last token, scales logits before sampling/greedy.
    If risk gating is enabled, the risk head influences s_t at inference too.

    Usage:
        hook = ConfidenceInferenceHook(confidence_scaler, vritti_head=vritti_head)
        # In generation loop:
        logits_raw = lm_head(h_t)
        logits_scaled = hook.scale_step(logits_raw, h_t)
        # sample from logits_scaled
    """

    def __init__(
        self,
        confidence_scaler: ConfidenceScaler,
        vritti_head: Optional[VrittiRiskHead] = None,
    ):
        self.scaler = confidence_scaler
        self.vritti_head = vritti_head
        self._step = 0

    @torch.no_grad()
    def scale_step(
        self,
        logits_raw: torch.Tensor,
        hidden_states: torch.Tensor,
    ) -> torch.Tensor:
        """
        Scale logits for one decode step.

        Args:
            logits_raw: [B, 1, V] or [B, V] raw logits for current step.
            hidden_states: [B, 1, D] or [B, D] hidden states for current step.

        Returns:
            logits_scaled: Same shape as logits_raw, after confidence scaling.
        """
        # Ensure 3D
        unsqueezed = False
        if logits_raw.dim() == 2:
            logits_raw = logits_raw.unsqueeze(1)
            hidden_states = hidden_states.unsqueeze(1)
            unsqueezed = True

        risk_prob = None
        if self.vritti_head is not None and self.scaler.config.enable_risk_gating:
            vritti_out = self.vritti_head(hidden_states)
            risk_prob = vritti_out['risk_prob']

        s, _ = self.scaler(hidden_states, risk_prob)
        logits_scaled = logits_raw / s.to(logits_raw.dtype)

        self._step += 1

        if unsqueezed:
            logits_scaled = logits_scaled.squeeze(1)

        return logits_scaled

    def reset(self):
        """Reset step counter (call at start of new generation)."""
        self._step = 0


# =============================================================================
# SCALE-MATCHED BASELINE HELPER
# =============================================================================

@torch.no_grad()
def fit_constant_temperature(
    logits_raw: torch.Tensor,
    targets: torch.Tensor,
    ignore_index: int = -100,
    num_candidates: int = 50,
) -> Tuple[float, float]:
    """
    Fit a constant temperature T that minimises CE loss on the given logits.

    This is the "scale-matched baseline" comparison: if your per-token s_t
    improvement disappears after fitting a single scalar T, you did not
    improve modelling — you only improved calibration.

    Args:
        logits_raw: [B, T, V] raw logits.
        targets: [B, T] target tokens.
        ignore_index: Padding index.
        num_candidates: Number of temperature candidates to try.

    Returns:
        best_T: Best constant temperature.
        best_ppl: PPL at best temperature.
    """
    B, T, V = logits_raw.shape
    logits_flat = logits_raw.reshape(-1, V).float()
    targets_flat = targets.reshape(-1)

    # Filter out ignored tokens
    mask = targets_flat != ignore_index
    logits_valid = logits_flat[mask]
    targets_valid = targets_flat[mask]

    if logits_valid.numel() == 0:
        return 1.0, float('inf')

    # Search over temperature grid
    temps = torch.logspace(-1, 1, num_candidates)  # 0.1 to 10.0
    best_T = 1.0
    best_loss = float('inf')

    for T_candidate in temps:
        T_val = T_candidate.item()
        ce = F.cross_entropy(logits_valid / T_val, targets_valid)
        if ce.item() < best_loss:
            best_loss = ce.item()
            best_T = T_val

    best_ppl = math.exp(min(best_loss, 20.0))
    return best_T, best_ppl


# =============================================================================
# LOGGING UTILITY
# =============================================================================

def log_confidence_metrics(
    metrics: Dict[str, float],
    global_step: int,
    writer=None,
    print_every: int = 100,
    rank: int = 0,
    prefix: str = "confidence",
) -> Optional[str]:
    """
    Log confidence scaler metrics to console and TensorBoard.

    Args:
        metrics: Dictionary from CalibrationDiagnostics or EntropyBandLoss.
        global_step: Current training step.
        writer: Optional TensorBoard SummaryWriter.
        print_every: Console print interval.
        rank: DDP rank (only log on rank 0).
        prefix: Metric prefix for TensorBoard.

    Returns:
        Formatted log string (or None if not rank 0).
    """
    if rank != 0:
        return None

    # TensorBoard logging
    if writer is not None:
        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                writer.add_scalar(f"{prefix}/{key}", value, global_step)

    # Console logging
    if global_step % print_every == 0 and global_step > 0:
        parts = []
        for key in ['s_mean', 's_p95', 's_max', 'entropy_mean',
                     'logit_std_before', 'logit_std_after',
                     'maxprob_when_wrong', 'entropy_band_loss',
                     'vritti_risk_mean']:
            if key in metrics:
                parts.append(f"{key}={metrics[key]:.4f}")

        log_str = f"  [CONF] Step {global_step} | " + " | ".join(parts)
        print(log_str)
        return log_str

    return None
