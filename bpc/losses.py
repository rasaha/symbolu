"""
BPC Loss Functions
==================

Loss 1: Rollout Predictability Consistency
  - Trajectory smoothness: sum_k || z_{t+k} - z_{t+k-1} ||^2
  - Anchor-to-start: sum_k || z_{t+k} - z_t ||^2
  - Variance floor to prevent collapse

Loss 2: Counterfactual Invariance (bounded)
  - L_cf = relu( ||z_t - z_t_cf|| - margin )^2

Stop-gradient policy:
  - Generated tokens treated as constants (no REINFORCE)
  - Backprop through forward pass that produced z (standard)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class BPCConfig:
    """Configuration for BPC training."""

    # Subspace
    target_layer: int = 6  # L* (default: middle layer of 12-layer model)
    subspace_rank: int = 32  # r

    # Rollout
    rollout_steps: int = 4  # K
    rollout_stride: int = 8  # sample position every N tokens
    rollout_mode: str = "greedy"  # "greedy" or "sample"
    rollout_temperature: float = 1.0  # for sampling mode

    # Loss weights (target values after warmup)
    lambda_rollout: float = 0.1  # lambda_1
    lambda_cf: float = 0.05  # lambda_2
    lambda_varfloor: float = 0.01  # lambda_3

    # Counterfactual
    cf_margin: float = 0.5  # m in relu(||z - z_cf|| - m)^2

    # Variance floor
    varfloor_eps: float = 0.1  # minimum per-dim std

    # Rollout loss mix
    use_trajectory_smoothness: bool = True  # term (i)
    use_anchor_to_start: bool = True  # term (ii)
    trajectory_weight: float = 1.0
    anchor_weight: float = 0.5

    # Schedule
    warmup_fraction: float = 0.1  # first 10% steps: lambda=0
    ramp_fraction: float = 0.3  # next 30%: ramp to target
    # After 40%: hold constant

    # Collapse detection
    collapse_std_threshold: float = 0.01
    auto_increase_varfloor: bool = True
    varfloor_increase_factor: float = 2.0

    # Gradient clipping for BPC components
    bpc_grad_clip: float = 1.0

    # Normalization for z coords
    normalize_z: bool = True  # normalize by running RMS


class LambdaScheduler:
    """Schedules BPC loss weights with warmup + ramp."""

    def __init__(self, config: BPCConfig, total_steps: int):
        self.config = config
        self.total_steps = total_steps
        self.warmup_end = int(total_steps * config.warmup_fraction)
        self.ramp_end = int(total_steps * (config.warmup_fraction + config.ramp_fraction))

    def get_lambdas(self, step: int) -> Dict[str, float]:
        if step < self.warmup_end:
            scale = 0.0
        elif step < self.ramp_end:
            progress = (step - self.warmup_end) / max(1, self.ramp_end - self.warmup_end)
            scale = progress
        else:
            scale = 1.0

        return {
            "lambda_rollout": self.config.lambda_rollout * scale,
            "lambda_cf": self.config.lambda_cf * scale,
            "lambda_varfloor": self.config.lambda_varfloor * scale,
        }


class RunningRMSNormalizer(nn.Module):
    """Running RMS statistics for z normalization (NOT layernorm on h)."""

    def __init__(self, dim: int, momentum: float = 0.01):
        super().__init__()
        self.dim = dim
        self.momentum = momentum
        self.register_buffer("running_sq_mean", torch.ones(dim))
        self.register_buffer("num_updates", torch.tensor(0, dtype=torch.long))

    @torch.no_grad()
    def update(self, z: torch.Tensor):
        """Update running statistics. z: [*, dim]"""
        flat = z.detach().reshape(-1, self.dim)
        batch_sq_mean = flat.pow(2).mean(dim=0)
        self.running_sq_mean.mul_(1 - self.momentum).add_(
            batch_sq_mean * self.momentum
        )
        self.num_updates += 1

    def normalize(self, z: torch.Tensor) -> torch.Tensor:
        """Normalize z by running RMS. Does NOT layernorm the hidden state."""
        rms = self.running_sq_mean.sqrt().clamp(min=1e-8)
        return z / rms


class RolloutPredictor(nn.Module):
    """
    Runs K-step rollouts from selected positions.

    Stop-gradient through sampled tokens: treats generated tokens as constants,
    backprop through forward pass that produces hidden states / belief coords.
    """

    def __init__(self, config: BPCConfig):
        super().__init__()
        self.K = config.rollout_steps
        self.stride = config.rollout_stride
        self.mode = config.rollout_mode
        self.temperature = config.rollout_temperature

    @torch.no_grad()
    def select_positions(
        self, seq_len: int, batch_size: int, device: torch.device
    ) -> torch.Tensor:
        """Select rollout anchor positions. Returns [num_positions]."""
        # Start from stride, leave room for K rollout steps
        positions = torch.arange(
            self.stride, seq_len - self.K, self.stride, device=device
        )
        return positions

    @torch.no_grad()
    def generate_rollout_tokens(
        self, model: nn.Module, input_ids: torch.Tensor, position: int
    ) -> torch.Tensor:
        """
        Generate K tokens from position using stop-gradient.

        Args:
            model: the causal LM
            input_ids: [B, T] original input
            position: starting position t

        Returns:
            rollout_ids: [B, K] generated token ids (detached)
        """
        B = input_ids.shape[0]
        device = input_ids.device

        # Start with context up to position
        context = input_ids[:, : position + 1].clone()
        generated = []

        for k in range(self.K):
            out = model(context)
            logits = out["logits"][:, -1, :]  # [B, V]

            if self.mode == "greedy":
                next_token = logits.argmax(dim=-1, keepdim=True)  # [B, 1]
            else:
                probs = F.softmax(logits / self.temperature, dim=-1)
                next_token = torch.multinomial(probs, num_samples=1)  # [B, 1]

            generated.append(next_token)
            context = torch.cat([context, next_token], dim=1)

        return torch.cat(generated, dim=1)  # [B, K]


class BeliefProjector(nn.Module):
    """Projects hidden states into belief subspace using pre-computed PCA basis."""

    def __init__(self, embed_dim: int, rank: int):
        super().__init__()
        self.embed_dim = embed_dim
        self.rank = rank
        # U_r: (embed_dim, rank) orthonormal basis
        self.register_buffer("U_r", torch.zeros(embed_dim, rank))
        # Mean of hidden states (for centering)
        self.register_buffer("h_mean", torch.zeros(embed_dim))
        self._loaded = False

    def load_basis(self, U_r: torch.Tensor, h_mean: Optional[torch.Tensor] = None):
        """Load pre-computed PCA basis."""
        assert U_r.shape == (self.embed_dim, self.rank), (
            f"Expected ({self.embed_dim}, {self.rank}), got {U_r.shape}"
        )
        self.U_r.copy_(U_r)
        if h_mean is not None:
            self.h_mean.copy_(h_mean)
        self._loaded = True

    def load_random_basis(self):
        """Load random orthonormal basis (control condition)."""
        Q, _ = torch.linalg.qr(torch.randn(self.embed_dim, self.rank))
        self.U_r.copy_(Q)
        self.h_mean.zero_()
        self._loaded = True

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def project(self, h: torch.Tensor) -> torch.Tensor:
        """
        Project hidden states to belief coordinates.
        h: [*, embed_dim] -> z: [*, rank]
        z = U_r^T (h - mean)
        """
        centered = h - self.h_mean
        return centered @ self.U_r  # [*, rank]

    def project_full(self, h: torch.Tensor) -> torch.Tensor:
        """
        Project hidden states onto belief subspace (full dim).
        h: [*, embed_dim] -> h_proj: [*, embed_dim]
        h_proj = U_r U_r^T (h - mean) + mean
        """
        centered = h - self.h_mean
        z = centered @ self.U_r  # [*, rank]
        h_proj = z @ self.U_r.T + self.h_mean  # [*, embed_dim]
        return h_proj

    def residual(self, h: torch.Tensor) -> torch.Tensor:
        """
        Compute residual: h - U_r U_r^T h
        h: [*, embed_dim] -> h_res: [*, embed_dim]
        """
        return h - self.project_full(h)


class BPCLoss(nn.Module):
    """
    Full BPC loss combining rollout consistency + counterfactual invariance.

    L_total = L_CE + lambda1 * L_rollout + lambda2 * L_cf + lambda3 * L_varfloor
    """

    def __init__(self, config: BPCConfig, embed_dim: int, total_steps: int):
        super().__init__()
        self.config = config
        self.embed_dim = embed_dim

        self.projector = BeliefProjector(embed_dim, config.subspace_rank)
        self.rollout_predictor = RolloutPredictor(config)
        self.scheduler = LambdaScheduler(config, total_steps)

        if config.normalize_z:
            self.z_normalizer = RunningRMSNormalizer(config.subspace_rank)
        else:
            self.z_normalizer = None

        # Diagnostics
        self._current_step = 0
        self._collapse_detected = False
        self._nan_first_step = -1
        self._current_varfloor_weight = config.lambda_varfloor

    def _get_z(self, h: torch.Tensor) -> torch.Tensor:
        """Get belief coordinates from hidden state, with optional normalization."""
        z = self.projector.project(h)
        if self.z_normalizer is not None:
            if self.training:
                self.z_normalizer.update(z)
            z = self.z_normalizer.normalize(z)
        return z

    def compute_rollout_loss(
        self,
        model: nn.Module,
        input_ids: torch.Tensor,
        teacher_hidden: torch.Tensor,
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Compute rollout predictability consistency loss.

        Args:
            model: the causal LM
            input_ids: [B, T] input token ids
            teacher_hidden: [B, T, D] hidden states from layer L* (teacher-forced)

        Returns:
            loss: scalar tensor
            metrics: dict of diagnostic values
        """
        B, T, D = teacher_hidden.shape
        device = teacher_hidden.device
        config = self.config

        positions = self.rollout_predictor.select_positions(T, B, device)
        if len(positions) == 0:
            return torch.tensor(0.0, device=device, requires_grad=True), {
                "rollout_smooth": 0.0,
                "rollout_anchor": 0.0,
            }

        total_smooth = torch.tensor(0.0, device=device)
        total_anchor = torch.tensor(0.0, device=device)
        count = 0

        for t in positions:
            t = t.item()

            # Teacher-forced z at anchor
            z_anchor = self._get_z(teacher_hidden[:, t, :])  # [B, r]

            # Generate rollout tokens (stop-gradient)
            rollout_ids = self.rollout_predictor.generate_rollout_tokens(
                model, input_ids, t
            )  # [B, K]

            # Build rollout input: original context + generated tokens
            rollout_input = torch.cat(
                [input_ids[:, : t + 1], rollout_ids], dim=1
            )  # [B, t+1+K]

            # Forward pass through model to get hidden states at rollout positions
            with torch.enable_grad():
                rollout_out = model(
                    rollout_input,
                    extract_layers=[config.target_layer],
                )
                rollout_hidden = rollout_out["hidden_states"][0]  # [B, t+1+K, D]

            # Extract z at rollout positions (t+1, t+2, ..., t+K)
            z_rollout = []
            for k in range(config.rollout_steps):
                pos = t + 1 + k
                if pos < rollout_hidden.shape[1]:
                    z_k = self._get_z(rollout_hidden[:, pos, :])  # [B, r]
                    z_rollout.append(z_k)

            if len(z_rollout) < 2:
                continue

            z_rollout = torch.stack(z_rollout, dim=1)  # [B, K', r]

            # (i) Trajectory smoothness: sum_k || z_{t+k} - z_{t+k-1} ||^2
            if config.use_trajectory_smoothness:
                diffs = z_rollout[:, 1:, :] - z_rollout[:, :-1, :]  # [B, K'-1, r]
                smooth = diffs.pow(2).sum(dim=-1).mean()
                total_smooth = total_smooth + smooth

            # (ii) Anchor-to-start: sum_k || z_{t+k} - z_t ||^2
            if config.use_anchor_to_start:
                anchor_expanded = z_anchor.unsqueeze(1).expand_as(
                    z_rollout
                )  # [B, K', r]
                anchor_diff = (z_rollout - anchor_expanded).pow(2).sum(dim=-1).mean()
                total_anchor = total_anchor + anchor_diff

            count += 1

        if count == 0:
            return torch.tensor(0.0, device=device, requires_grad=True), {
                "rollout_smooth": 0.0,
                "rollout_anchor": 0.0,
            }

        smooth_loss = total_smooth / count * config.trajectory_weight
        anchor_loss = total_anchor / count * config.anchor_weight
        loss = smooth_loss + anchor_loss

        return loss, {
            "rollout_smooth": smooth_loss.item(),
            "rollout_anchor": anchor_loss.item(),
        }

    def compute_cf_loss(
        self,
        teacher_hidden: torch.Tensor,
        cf_hidden: torch.Tensor,
        positions: torch.Tensor,
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Compute counterfactual invariance loss (bounded).

        L_cf = relu( ||z_t - z_t_cf|| - margin )^2

        Also computes residual sensitivity as a control metric (not a loss).

        Args:
            teacher_hidden: [B, T, D] original hidden states
            cf_hidden: [B, T, D] counterfactual hidden states
            positions: [N] positions to compare

        Returns:
            loss: scalar tensor
            metrics: dict
        """
        device = teacher_hidden.device
        config = self.config

        if len(positions) == 0:
            return torch.tensor(0.0, device=device, requires_grad=True), {
                "cf_loss": 0.0,
                "cf_z_dist_mean": 0.0,
                "cf_res_dist_mean": 0.0,
            }

        z_dists = []
        res_dists = []

        for t in positions:
            t = t.item() if isinstance(t, torch.Tensor) else t
            if t >= teacher_hidden.shape[1] or t >= cf_hidden.shape[1]:
                continue

            z_orig = self._get_z(teacher_hidden[:, t, :])  # [B, r]
            z_cf = self._get_z(cf_hidden[:, t, :])  # [B, r]

            z_dist = (z_orig - z_cf).pow(2).sum(dim=-1).sqrt()  # [B]
            z_dists.append(z_dist)

            # Residual distance (control metric, no gradient needed)
            with torch.no_grad():
                h_res = self.projector.residual(teacher_hidden[:, t, :])
                h_res_cf = self.projector.residual(cf_hidden[:, t, :])
                res_dist = (h_res - h_res_cf).pow(2).sum(dim=-1).sqrt()
                res_dists.append(res_dist)

        if len(z_dists) == 0:
            return torch.tensor(0.0, device=device, requires_grad=True), {
                "cf_loss": 0.0,
                "cf_z_dist_mean": 0.0,
                "cf_res_dist_mean": 0.0,
            }

        z_dists = torch.stack(z_dists, dim=0)  # [N, B]
        # Bounded objective: penalize only extreme jumps
        cf_loss = F.relu(z_dists - config.cf_margin).pow(2).mean()

        with torch.no_grad():
            res_dists = torch.stack(res_dists, dim=0)

        return cf_loss, {
            "cf_loss": cf_loss.item(),
            "cf_z_dist_mean": z_dists.mean().item(),
            "cf_res_dist_mean": res_dists.mean().item(),
        }

    def compute_varfloor_loss(
        self, teacher_hidden: torch.Tensor
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Variance floor penalty: penalize std(z_dim) < eps over batch.
        Prevents trivial collapse of belief coordinates to zero.

        Args:
            teacher_hidden: [B, T, D]

        Returns:
            loss: scalar tensor
            metrics: dict
        """
        device = teacher_hidden.device
        config = self.config

        # Sample positions to reduce compute
        B, T, D = teacher_hidden.shape
        sample_positions = torch.arange(0, T, max(1, T // 64), device=device)
        h_sample = teacher_hidden[:, sample_positions, :]  # [B, N_sample, D]

        z_sample = self._get_z(h_sample)  # [B, N_sample, r]
        # Flatten batch and time dims for std computation
        z_flat = z_sample.reshape(-1, config.subspace_rank)  # [B*N, r]

        per_dim_std = z_flat.std(dim=0)  # [r]

        # Penalize dimensions with std below eps
        violations = F.relu(config.varfloor_eps - per_dim_std)  # [r]
        varfloor_loss = violations.pow(2).mean()

        # Collapse detection
        min_std = per_dim_std.min().item()
        mean_std = per_dim_std.mean().item()
        collapsed_dims = (per_dim_std < config.collapse_std_threshold).sum().item()

        if collapsed_dims > config.subspace_rank // 2:
            self._collapse_detected = True
            if config.auto_increase_varfloor:
                self._current_varfloor_weight *= config.varfloor_increase_factor

        return varfloor_loss, {
            "varfloor_loss": varfloor_loss.item(),
            "z_std_min": min_std,
            "z_std_mean": mean_std,
            "z_collapsed_dims": collapsed_dims,
            "varfloor_weight": self._current_varfloor_weight,
        }

    def forward(
        self,
        model: nn.Module,
        input_ids: torch.Tensor,
        targets: torch.Tensor,
        ce_loss: torch.Tensor,
        teacher_hidden: torch.Tensor,
        cf_hidden: Optional[torch.Tensor] = None,
        cf_positions: Optional[torch.Tensor] = None,
        step: int = 0,
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Compute full BPC loss.

        L_total = L_CE + lambda1*L_rollout + lambda2*L_cf + lambda3*L_varfloor

        Args:
            model: causal LM
            input_ids: [B, T]
            targets: [B, T]
            ce_loss: scalar CE loss (already computed)
            teacher_hidden: [B, T, D] hidden states from layer L*
            cf_hidden: optional [B, T, D] counterfactual hidden states
            cf_positions: optional [N] positions for CF comparison
            step: current training step

        Returns:
            total_loss: scalar
            metrics: dict
        """
        self._current_step = step
        device = input_ids.device
        metrics = {"ce_loss": ce_loss.item()}

        lambdas = self.scheduler.get_lambdas(step)
        metrics.update({f"sched/{k}": v for k, v in lambdas.items()})

        total_loss = ce_loss

        # NaN guard
        def _check_nan(tensor, name):
            if torch.isnan(tensor).any():
                if self._nan_first_step < 0:
                    self._nan_first_step = step
                metrics[f"nan/{name}"] = True
                return torch.tensor(0.0, device=device, requires_grad=True)
            return tensor

        # 1. Rollout loss
        if lambdas["lambda_rollout"] > 0:
            rollout_loss, rollout_metrics = self.compute_rollout_loss(
                model, input_ids, teacher_hidden
            )
            rollout_loss = _check_nan(rollout_loss, "rollout")
            total_loss = total_loss + lambdas["lambda_rollout"] * rollout_loss
            metrics.update(rollout_metrics)
        else:
            metrics["rollout_smooth"] = 0.0
            metrics["rollout_anchor"] = 0.0

        # 2. Counterfactual loss
        if lambdas["lambda_cf"] > 0 and cf_hidden is not None and cf_positions is not None:
            cf_loss, cf_metrics = self.compute_cf_loss(
                teacher_hidden, cf_hidden, cf_positions
            )
            cf_loss = _check_nan(cf_loss, "cf")
            total_loss = total_loss + lambdas["lambda_cf"] * cf_loss
            metrics.update(cf_metrics)
        else:
            metrics["cf_loss"] = 0.0

        # 3. Variance floor
        vf_weight = max(
            lambdas["lambda_varfloor"], self._current_varfloor_weight
        )
        if vf_weight > 0:
            vf_loss, vf_metrics = self.compute_varfloor_loss(teacher_hidden)
            vf_loss = _check_nan(vf_loss, "varfloor")
            total_loss = total_loss + vf_weight * vf_loss
            metrics.update(vf_metrics)

        total_loss = _check_nan(total_loss, "total")
        metrics["total_loss"] = total_loss.item()
        metrics["nan_first_step"] = self._nan_first_step

        return total_loss, metrics
