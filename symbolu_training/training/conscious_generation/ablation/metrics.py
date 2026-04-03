"""
Ablation metrics for Stage 9 — measures mechanism contribution.

Four metrics per F.14.4:
  1. Validation Perplexity (PPL)
  2. Attention Entropy
  3. Token Change Rate
  4. Hidden State Perturbation

Plus runtime mechanism-strength logging per F.14.5.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import torch
import math


@dataclass
class AblationMetrics:
    """Collected metrics for one ablation configuration."""
    config_label: str = ""
    ppl: float = 0.0
    delta_ppl_pct: float = 0.0          # vs baseline
    attention_entropy: float = 0.0
    token_change_rate: float = 0.0      # vs baseline generation
    hidden_state_perturbation: float = 0.0  # vs baseline hidden states
    gradient_norms: Dict[str, float] = field(default_factory=dict)

    def summary(self) -> str:
        lines = [
            f"  Config: {self.config_label}",
            f"  PPL: {self.ppl:.4f}  (ΔPPL: {self.delta_ppl_pct:+.2f}%)",
            f"  Attn entropy: {self.attention_entropy:.4f}",
            f"  Token change rate: {self.token_change_rate:.2%}",
            f"  Hidden Δ_h: {self.hidden_state_perturbation:.4f}",
        ]
        if self.gradient_norms:
            lines.append("  Gradient norms:")
            for k, v in self.gradient_norms.items():
                lines.append(f"    {k}: {v:.6f}")
        return "\n".join(lines)


def compute_attention_entropy(attention_weights: torch.Tensor) -> float:
    """
    Compute mean attention entropy across all heads and layers.

    Args:
        attention_weights: [B, H, T, T] softmax attention weights
            (or list of such tensors, one per layer).

    Returns:
        Mean entropy H = -sum(p * log(p)).
    """
    if isinstance(attention_weights, list):
        return float(torch.tensor([
            compute_attention_entropy(aw) for aw in attention_weights
        ]).mean().item())

    # Clamp for numerical stability
    p = attention_weights.clamp(min=1e-9)
    entropy = -(p * p.log()).sum(dim=-1)  # [B, H, T]
    return float(entropy.mean().item())


def compute_token_change_rate(
    tokens_baseline: torch.Tensor,
    tokens_ablated: torch.Tensor,
) -> float:
    """
    Fraction of tokens that differ between baseline and ablated generation.

    Args:
        tokens_baseline: [B, T] token IDs from baseline
        tokens_ablated: [B, T] token IDs from ablated config

    Returns:
        change_rate in [0, 1]
    """
    min_len = min(tokens_baseline.shape[-1], tokens_ablated.shape[-1])
    baseline = tokens_baseline[..., :min_len]
    ablated = tokens_ablated[..., :min_len]
    different = (baseline != ablated).float().mean()
    return float(different.item())


def compute_hidden_state_perturbation(
    h_baseline: torch.Tensor,
    h_ablated: torch.Tensor,
) -> float:
    """
    Relative L2 perturbation:  ||h_mod - h_base||_2 / ||h_base||_2

    Args:
        h_baseline: [B, T, D] hidden states from baseline
        h_ablated: [B, T, D] hidden states from ablated config

    Returns:
        Mean relative perturbation across batch.
    """
    diff_norm = torch.norm(h_ablated - h_baseline, p=2, dim=-1)  # [B, T]
    base_norm = torch.norm(h_baseline, p=2, dim=-1).clamp(min=1e-8)  # [B, T]
    relative = diff_norm / base_norm  # [B, T]
    return float(relative.mean().item())


def compute_ablation_metrics(
    val_loss: float,
    baseline_ppl: Optional[float] = None,
    attention_weights: Optional[torch.Tensor] = None,
    tokens_baseline: Optional[torch.Tensor] = None,
    tokens_ablated: Optional[torch.Tensor] = None,
    h_baseline: Optional[torch.Tensor] = None,
    h_ablated: Optional[torch.Tensor] = None,
    config_label: str = "",
) -> AblationMetrics:
    """
    Convenience function: compute all available ablation metrics.
    """
    ppl = math.exp(val_loss)
    delta_ppl_pct = 0.0
    if baseline_ppl is not None and baseline_ppl > 0:
        delta_ppl_pct = ((ppl - baseline_ppl) / baseline_ppl) * 100.0

    attn_entropy = 0.0
    if attention_weights is not None:
        attn_entropy = compute_attention_entropy(attention_weights)

    tcr = 0.0
    if tokens_baseline is not None and tokens_ablated is not None:
        tcr = compute_token_change_rate(tokens_baseline, tokens_ablated)

    hsp = 0.0
    if h_baseline is not None and h_ablated is not None:
        hsp = compute_hidden_state_perturbation(h_baseline, h_ablated)

    return AblationMetrics(
        config_label=config_label,
        ppl=ppl,
        delta_ppl_pct=delta_ppl_pct,
        attention_entropy=attn_entropy,
        token_change_rate=tcr,
        hidden_state_perturbation=hsp,
    )


def collect_mechanism_strength_log(model: torch.nn.Module) -> Dict[str, float]:
    """
    Collect mechanism-strength signals from model parameters for runtime logging.

    Per F.14.5, these signals detect dead mechanisms early during training.

    Returns:
        Dict of metric_name -> value, e.g.:
            phase/sync_lr, guna/bias_norm, vritti/temperature_mean, etc.
    """
    log_dict: Dict[str, float] = {}

    for name, param in model.named_parameters():
        # Phase sync learning rate
        if "sync_lr" in name and param.numel() == 1:
            log_dict["phase/sync_lr"] = param.item()

        # Phase frequency parameters
        if name.endswith(".freq") and param.numel() > 1:
            log_dict["phase/freq_std"] = param.std().item()

        # Vritti temperature modulation weight norm
        if "temperature_mod" in name and "weight" in name:
            log_dict["vritti/temperature_weight_norm"] = param.norm().item()

        # Vritti position bias weight norm
        if "position_bias" in name and "vritti" in name.lower().replace("_", ""):
            log_dict["vritti/position_bias_norm"] = param.norm().item()

        # Guna bias network weight norm
        if "guna_to_bias" in name and "weight" in name:
            key = f"guna/bias_weight_norm_{name.split('.')[-2]}"
            log_dict.setdefault("guna/bias_total_norm", 0.0)
            log_dict["guna/bias_total_norm"] += param.norm().item()

        # Guna refinement weight
        if "guna_refine" in name and "weight" in name:
            log_dict["guna/refine_weight_norm"] = param.norm().item()

        # Vritti stiffness embeddings (SovereignPhaseAttention)
        if "v_to_stiffness" in name and "weight" in name:
            log_dict["vritti/stiffness_mean"] = param.mean().item()
            log_dict["vritti/stiffness_std"] = param.std().item()

    return log_dict


def collect_gradient_norms(model: torch.nn.Module) -> Dict[str, float]:
    """
    Collect gradient norms per mechanism family (F.14.7).

    Call after backward() but before optimizer.step().
    """
    norms: Dict[str, float] = {
        "phase_params": 0.0,
        "vritti_params": 0.0,
        "guna_params": 0.0,
    }
    counts: Dict[str, int] = {k: 0 for k in norms}

    for name, param in model.named_parameters():
        if param.grad is None:
            continue
        grad_norm = param.grad.norm().item()

        if any(k in name for k in ("phase_proj", "sync_lr", "freq", "r_to_phi",
                                     "s_to_amplitude", "phase_noise")):
            norms["phase_params"] += grad_norm ** 2
            counts["phase_params"] += 1
        elif any(k in name for k in ("vritti", "temperature_mod", "magnitude_mod",
                                       "v_to_stiffness")):
            norms["vritti_params"] += grad_norm ** 2
            counts["vritti_params"] += 1
        elif any(k in name for k in ("guna", "bhava_to_guna")):
            norms["guna_params"] += grad_norm ** 2
            counts["guna_params"] += 1

    # RMS norm
    for k in norms:
        if counts[k] > 0:
            norms[k] = (norms[k] / counts[k]) ** 0.5

    return norms
