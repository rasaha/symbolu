"""
Minimal Experiential Controller: 12-parameter resistance-driven plasticity.

Post-ablation minimal spec. This replaces the 58-parameter framework with
the load-bearing core identified through systematic ablation.

Core equation:
    g_eff = d_t · G_t · P_t · ∇L_exp

Where:
    P_t = sigmoid(k_r · R_t - k_m · M_t + b_p)     # plasticity gate
    G_t = clip(G_base · f_phase(t) · f_coh(C_t), G_min, G_max)  # adaptive gain
    d_t = exp(-k_dv · V_t - k_dc · U_t)             # damping
    L_exp = L_token + λ_temp·L_temporal + λ_coh·L_coherence + λ_lat·L_latent

12 parameters total:
    Loss:       λ_temp, λ_coh, λ_lat         (3)
    Plasticity: k_r, k_m, b_p                (3)
    Gain:       G_base, G_min, G_max          (3)
    Damping:    k_dv, k_dc                    (2)
    Identity:   α_base                        (1)

Pipeline insertion (Phase-Quad):
    [Phase-Quad Forward] → logits, hidden, memory
    [CSR / Coherence Observer] → Z_t, C_t, M_t
    [This Controller] → L_exp, P_t, G_t, d_t → scaled gradient
    [Optimizer Step]

Does NOT modify: Local attention, Phase accumulation, Quad retrieval.

Reference: CONSCIOUS_GENERATION_DESIGN.md, Experiential Learning Extension
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass
class ExperientialControllerConfig:
    """12-parameter minimal controller configuration.

    Every parameter here is ablation-validated as load-bearing or
    necessary for the minimal viable controller.
    """
    # --- Structural (not counted in the 12) ---
    d_model: int = 128
    num_regions: int = 12

    # --- Loss weights (3) ---
    lambda_temporal: float = 0.5    # Temporal/trajectory consistency
    lambda_coherence: float = 0.3   # Cross-signal coherence mismatch
    lambda_latent: float = 0.1      # Latent alignment

    # --- Plasticity gate (3) ---
    k_r: float = 2.0    # Resistance openness scaling
    k_m: float = 2.0    # Misalignment suppression scaling
    b_p: float = -1.0   # Bias floor (ensures plasticity > sigmoid(b_p) > 0)

    # --- Adaptive gain (3) ---
    G_base: float = 3.0
    G_min: float = 0.1
    G_max: float = 5.0

    # --- Damping (2) ---
    k_dv: float = 1.0   # Gradient variance sensitivity
    k_dc: float = 0.5   # Coherence instability sensitivity

    # --- Identity (1) ---
    alpha_base: float = 0.01

    # --- Replay (auxiliary, not counted in core 12) ---
    replay_buffer_size: int = 256
    replay_ttl: int = 200


class ExperientialLoss(nn.Module):
    """4-term experiential loss.

    L_exp = L_token + λ_temp·L_temporal + λ_coh·L_coherence + λ_lat·L_latent

    Maps to Phase-Quad:
        L_token:     standard CE from logits (passed in)
        L_temporal:  trajectory consistency from hidden state sequence
        L_coherence: mismatch across coherence signals (C_tok, C_lat, C_conv)
        L_latent:    alignment between latent state and hidden representation
    """

    def __init__(self, config: ExperientialControllerConfig):
        super().__init__()
        self.config = config

        # Temporal smoothing: 1D conv for trajectory consistency
        self.temporal_proj = nn.Conv1d(
            config.d_model, config.d_model, kernel_size=5, padding=2,
            groups=min(config.d_model, 16),
        )

        # Latent alignment projection
        self.latent_proj = nn.Linear(config.d_model, config.d_model)

    def forward(
        self,
        hidden: torch.Tensor,
        target_hidden: torch.Tensor,
        base_loss: Optional[torch.Tensor] = None,
        coherence_signals: Optional[Dict[str, float]] = None,
        latent_state: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """Compute 4-term experiential loss.

        Args:
            hidden: [B, T, D] predicted hidden states
            target_hidden: [B, T, D] target hidden states
            base_loss: Optional scalar L_token (CE loss from logits)
            coherence_signals: Optional dict with 'c_tok', 'c_lat', 'c_conv'
                from UnifiedCoherenceController
            latent_state: Optional [B, T, D] or [B, D] latent state from CSR

        Returns:
            Dict with 'loss', 'L_token', 'L_temporal', 'L_coherence', 'L_latent'
        """
        device = hidden.device

        # L_token: passed in or computed as MSE between hidden states
        L_token = base_loss if base_loss is not None else F.mse_loss(hidden, target_hidden)

        # L_temporal: trajectory consistency
        # Smooth hidden sequence and measure deviation from target
        h_t = hidden.transpose(1, 2)  # [B, D, T]
        h_smooth = self.temporal_proj(h_t).transpose(1, 2)  # [B, T, D]
        L_temporal = F.mse_loss(h_smooth, target_hidden)

        # L_coherence: mismatch across coherence signals
        L_coherence = torch.tensor(0.0, device=device)
        if coherence_signals is not None:
            c_tok = coherence_signals.get("c_tok", 0.5)
            c_lat = coherence_signals.get("c_lat", 0.5)
            c_conv = coherence_signals.get("c_conv", 0.5)
            c_vec = torch.tensor([c_tok, c_lat, c_conv], device=device)
            # Two-term coherence loss:
            #   1. Low overall coherence → high loss (penalize incoherence)
            #   2. Disagreement across signals → high loss (penalize inconsistency)
            L_coherence = (1.0 - c_vec.mean()).pow(2) + c_vec.var()

        # L_latent: alignment between latent state and hidden
        L_latent = torch.tensor(0.0, device=device)
        if latent_state is not None:
            if latent_state.dim() == 2:
                latent_state = latent_state.unsqueeze(1).expand_as(hidden)
            latent_proj = self.latent_proj(latent_state)
            L_latent = (1.0 - F.cosine_similarity(
                latent_proj, hidden, dim=-1
            )).mean()

        # Total
        L_exp = (
            L_token
            + self.config.lambda_temporal * L_temporal
            + self.config.lambda_coherence * L_coherence
            + self.config.lambda_latent * L_latent
        )

        return {
            "loss": L_exp,
            "L_token": L_token.detach() if isinstance(L_token, torch.Tensor) else L_token,
            "L_temporal": L_temporal.detach(),
            "L_coherence": L_coherence.detach(),
            "L_latent": L_latent.detach(),
        }


class PlasticityGate(nn.Module):
    """Minimal plasticity gate: P_t = sigmoid(k_r · R_t - k_m · M_t + b_p).

    Resistance-primary, misalignment as real suppressor.
    Bias floor ensures P_t > sigmoid(b_p) > 0 always (no dead zones).
    """

    def __init__(self, config: ExperientialControllerConfig):
        super().__init__()
        self.config = config

        # Resistance estimator: maps region state → openness in [0, 1]
        self.resistance_proj = nn.Sequential(
            nn.Linear(config.d_model, config.d_model // 4),
            nn.GELU(),
            nn.Linear(config.d_model // 4, 1),
            nn.Sigmoid(),
        )

        # Persistent resistance (EMA)
        self.register_buffer(
            "persistent_resistance",
            torch.full((config.num_regions,), 0.5),
        )

    def forward(
        self,
        region_states: torch.Tensor,
        misalignment: Optional[torch.Tensor] = None,
    ) -> Dict[str, torch.Tensor]:
        """Compute plasticity gate.

        Args:
            region_states: [B, num_regions, D]
            misalignment: Optional [B, num_regions] or scalar, from coherence

        Returns:
            Dict with 'plasticity' [B, num_regions], 'resistance' [B, num_regions]
        """
        B = region_states.shape[0]

        # Compute instantaneous resistance openness
        R_t = self.resistance_proj(region_states).squeeze(-1)  # [B, num_regions]

        # EMA smooth
        R_t = 0.9 * self.persistent_resistance.unsqueeze(0) + 0.1 * R_t

        # Misalignment signal
        M_t = torch.zeros(B, self.config.num_regions, device=region_states.device)
        if misalignment is not None:
            if misalignment.dim() == 0:
                M_t = misalignment.expand(B, self.config.num_regions)
            elif misalignment.dim() == 1:
                M_t = misalignment.unsqueeze(0).expand(B, -1)
            else:
                M_t = misalignment

        # P_t = sigmoid(k_r · R_t - k_m · M_t + b_p)
        logit = (
            self.config.k_r * R_t
            - self.config.k_m * M_t
            + self.config.b_p
        )
        plasticity = torch.sigmoid(logit)

        # Update persistent state
        with torch.no_grad():
            self.persistent_resistance.mul_(0.95).add_(
                R_t.mean(dim=0).detach() * 0.05
            )

        return {
            "plasticity": plasticity,
            "resistance_openness": R_t,
            "misalignment": M_t,
        }


class AdaptiveGain:
    """Minimal adaptive gain: G_t = clip(G_base · f_phase(t) · f_coh(C_t), G_min, G_max).

    Rate-limited to prevent oscillation.
    """

    def __init__(self, config: ExperientialControllerConfig):
        self.config = config
        self._prev_gain: Optional[float] = None

    def compute(
        self,
        coherence: Optional[float] = None,
        step: int = 0,
        warmup_steps: int = 1000,
    ) -> float:
        """Compute rate-limited adaptive gain."""
        # f_phase: ramp from 0.5 to 1.0 over warmup
        f_phase = min(1.0, 0.5 + 0.5 * step / max(warmup_steps, 1))

        # f_coh: monotonic coherence factor
        if coherence is not None:
            f_coh = 0.5 + 0.5 / (1.0 + math.exp(-(coherence - 0.5) * 4))
        else:
            f_coh = 0.75

        target = max(self.config.G_min, min(
            self.config.G_max,
            self.config.G_base * f_phase * f_coh,
        ))

        # Rate limiting: max 10% of G_base per step
        if self._prev_gain is not None:
            max_delta = self.config.G_base * 0.1
            target = max(self._prev_gain - max_delta,
                         min(self._prev_gain + max_delta, target))
        self._prev_gain = target

        return target


class Damping:
    """Minimal damping: d_t = exp(-k_dv · V_t - k_dc · U_t).

    Smooth, bounded, interpretable.
    V_t = gradient variance estimate (EMA)
    U_t = coherence instability estimate (EMA)
    """

    def __init__(self, config: ExperientialControllerConfig):
        self.config = config
        self._V_ema = 0.0
        self._U_ema = 0.0
        self._prev_d_t: Optional[float] = None

    def compute(
        self,
        grad_variance: float,
        coherence_instability: float = 0.0,
    ) -> float:
        """Compute damping factor in (0, 1]."""
        # EMA smooth inputs
        self._V_ema = 0.95 * self._V_ema + 0.05 * grad_variance
        self._U_ema = 0.95 * self._U_ema + 0.05 * coherence_instability

        # d_t = exp(-k_dv · V - k_dc · U)
        exponent = -(self.config.k_dv * self._V_ema + self.config.k_dc * self._U_ema)
        d_t = math.exp(max(exponent, -10.0))  # Floor at exp(-10) ≈ 4.5e-5
        d_t = max(d_t, 0.01)  # Hard floor

        # Rate limit
        if self._prev_d_t is not None:
            d_t = max(self._prev_d_t - 0.1, min(self._prev_d_t + 0.1, d_t))
        self._prev_d_t = d_t

        return d_t


class IdentityEMA:
    """Minimal identity: I_t = (1 - α_t)·I_{t-1} + α_t·summary(Z_stable).

    Lives on the slow loop only. α_t = α_base · stability · agreement.
    """

    def __init__(self, d_identity: int, alpha_base: float = 0.01):
        self.d_identity = d_identity
        self.alpha_base = alpha_base
        self.identity = torch.randn(d_identity) * 0.01
        self.accumulator = torch.zeros(d_identity)
        self.count = 0
        self.consolidation_count = 0

    def to(self, device: torch.device) -> 'IdentityEMA':
        """Move identity tensors to device."""
        self.identity = self.identity.to(device)
        self.accumulator = self.accumulator.to(device)
        return self

    def accumulate(self, signal: torch.Tensor, salience: float = 0.5) -> None:
        """Fast loop: accumulate identity-relevant signals."""
        if salience > 0.3:
            with torch.no_grad():
                _signal = signal.detach().to(self.accumulator.device)
                self.accumulator.mul_(0.99).add_(
                    _signal * (1 - 0.99) * salience
                )
                self.count += 1

    def consolidate(self) -> bool:
        """Slow loop: apply accumulated EMA to revise identity."""
        if self.count == 0 or self.accumulator.norm() < 1e-6:
            return False

        A_t = F.normalize(self.accumulator, dim=0) * (self.d_identity ** 0.5)

        # Adaptive alpha
        agreement = F.cosine_similarity(
            A_t.unsqueeze(0), self.identity.unsqueeze(0), dim=-1
        ).item()
        agreement = max(0.0, (agreement + 1.0) / 2.0)
        stability = 1.0 / (1.0 + self.accumulator.var().item())
        alpha_eff = max(self.alpha_base * stability * agreement, self.alpha_base * 0.1)

        self.identity = (1.0 - alpha_eff) * self.identity + alpha_eff * A_t
        self.identity = F.normalize(self.identity, dim=0) * (self.d_identity ** 0.5)

        self.accumulator.zero_()
        self.count = 0
        self.consolidation_count += 1
        return True

    def get_state(self) -> Dict[str, object]:
        return {
            "identity_norm": self.identity.norm().item(),
            "accumulator_count": self.count,
            "consolidation_count": self.consolidation_count,
        }


class ReplayBuffer:
    """Strictly auxiliary replay: bounded, TTL, no gradients."""

    def __init__(self, capacity: int = 256, ttl: int = 200):
        self.capacity = capacity
        self.ttl = ttl
        self.buffer: list = []

    def store(self, item: Dict, step: int) -> None:
        """Store if high misalignment + low openness."""
        item["step"] = step
        self.buffer.append(item)
        if len(self.buffer) > self.capacity:
            self.buffer.sort(key=lambda x: x.get("priority", 0))
            self.buffer.pop(0)

    def sample(self, k: int) -> list:
        """Probability-proportional sampling without replacement."""
        if not self.buffer:
            return []
        import random
        k = min(k, len(self.buffer))
        priorities = [item.get("priority", 0.01) for item in self.buffer]
        # Use weighted sampling without replacement
        indices = list(range(len(self.buffer)))
        result = []
        for _ in range(k):
            if not indices:
                break
            selected = random.choices(indices, weights=[priorities[i] for i in indices], k=1)[0]
            result.append(self.buffer[selected])
            indices.remove(selected)
        return result

    def prune(self, current_step: int) -> int:
        """Remove stale entries."""
        before = len(self.buffer)
        self.buffer = [
            item for item in self.buffer
            if current_step - item.get("step", 0) < self.ttl
        ]
        return before - len(self.buffer)

    def __len__(self):
        return len(self.buffer)


class ExperientialController(nn.Module):
    """12-parameter minimal experiential training controller.

    Complete controller for resistance-modulated adaptive plasticity.
    Sits between Phase-Quad forward pass and optimizer step.

    Architecture:
        [Phase-Quad Forward] → hidden, logits
        [CSR/Coherence] → C_t, M_t, Z_t
        [This] → L_exp, P_t, G_t, d_t → g_eff = d_t·G_t·P_t·∇L_exp
        [Optimizer]

    Args:
        config: ExperientialControllerConfig (12 tunable parameters)
    """

    def __init__(self, config: ExperientialControllerConfig):
        super().__init__()
        self.config = config

        # Core components
        self.loss_fn = ExperientialLoss(config)
        self.plasticity_gate = PlasticityGate(config)
        self.gain = AdaptiveGain(config)
        self.damping = Damping(config)

        # Auxiliary (not in gradient path)
        self.identity = IdentityEMA(d_identity=64, alpha_base=config.alpha_base)
        self.replay = ReplayBuffer(config.replay_buffer_size, config.replay_ttl)

        # Step counter
        self.register_buffer("step", torch.tensor(0, dtype=torch.long))

    def to(self, *args, **kwargs):
        """Override to propagate device to non-Module components."""
        result = super().to(*args, **kwargs)
        # IdentityEMA is not an nn.Module, so move it explicitly
        device = next(self.parameters()).device
        self.identity.to(device)
        return result

    def forward(
        self,
        hidden: torch.Tensor,
        target_hidden: torch.Tensor,
        base_loss: Optional[torch.Tensor] = None,
        coherence_signals: Optional[Dict[str, float]] = None,
        latent_state: Optional[torch.Tensor] = None,
        region_states: Optional[torch.Tensor] = None,
    ) -> Dict[str, object]:
        """One controller step.

        Args:
            hidden: [B, T, D] predicted hidden states from Phase-Quad
            target_hidden: [B, T, D] target hidden states
            base_loss: Optional L_token (CE loss from logits)
            coherence_signals: Optional {'c_tok', 'c_lat', 'c_conv'} from
                UnifiedCoherenceController
            latent_state: Optional [B, T, D] or [B, D] from CSR
            region_states: Optional [B, R, D] per-region states

        Returns:
            Dict with:
                'total_loss': Scalar loss for backward()
                'loss_components': {L_token, L_temporal, L_coherence, L_latent}
                'plasticity': [B, R] plasticity gate values
                'gain': scalar adaptive gain
                'damping': scalar damping factor
                'g_eff': [B, R] effective gain = d_t · G_t · P_t
        """
        B, T, D = hidden.shape
        device = hidden.device
        current_step = self.step.item()

        # Derive region states if not provided
        if region_states is None:
            region_states = self._derive_regions(hidden)

        # === Stage 3: Experiential loss ===
        loss_output = self.loss_fn(
            hidden, target_hidden, base_loss,
            coherence_signals=coherence_signals,
            latent_state=latent_state,
        )

        # === Stage 4: Plasticity controller ===
        # Compute misalignment from coherence signals
        misalignment = None
        if coherence_signals is not None:
            c_tok = coherence_signals.get("c_tok", 0.5)
            c_conv = coherence_signals.get("c_conv", 0.5)
            # M_t = 1 - mean(coherence) — normalized mismatch
            m_val = 1.0 - (c_tok + c_conv) / 2.0
            misalignment = torch.full(
                (B, self.config.num_regions), m_val, device=device
            )

        plasticity_output = self.plasticity_gate(region_states, misalignment)
        P_t = plasticity_output["plasticity"]

        # Coherence for gain
        coherence_val = None
        if coherence_signals is not None:
            coherence_val = sum(coherence_signals.values()) / len(coherence_signals)

        G_t = self.gain.compute(coherence=coherence_val, step=current_step)

        # Gradient variance for damping
        grad_var = hidden.var().item()
        coherence_instab = 0.0
        if coherence_signals is not None:
            c_vec = list(coherence_signals.values())
            if len(c_vec) > 1:
                coherence_instab = torch.tensor(c_vec).var().item()

        d_t = self.damping.compute(grad_var, coherence_instab)

        # === Effective gain ===
        # g_eff = d_t · G_t · P_t
        g_eff = d_t * G_t * P_t  # [B, num_regions]

        # Clamp effective gain
        g_eff = g_eff.clamp(self.config.G_min, self.config.G_max)

        # === Scale loss by g_eff ===
        # This is the core integration: g_eff modulates gradient magnitude.
        # Detach g_eff to avoid second-order gradients through the gate —
        # the gate learns from its own inputs, not from loss backprop.
        loss_scale = g_eff.detach().mean()
        total_loss = loss_scale * loss_output["loss"]

        # === Identity accumulation (fast loop) ===
        with torch.no_grad():
            identity_signal = hidden.mean(dim=(0, 1))[:64] if D >= 64 else hidden.mean(dim=(0, 1))
            mean_salience = P_t.mean().item()
            self.identity.accumulate(identity_signal, mean_salience)

        # === Replay (auxiliary) ===
        self.replay.prune(current_step)
        if misalignment is not None:
            high_m = misalignment.mean().item() > 0.3
            low_p = P_t.mean().item() < 0.3
            if high_m and low_p:
                self.replay.store({
                    "priority": misalignment.mean().item(),
                    "plasticity": P_t.mean().item(),
                }, current_step)

        self.step += 1

        return {
            "total_loss": total_loss,
            "loss_components": {
                "L_token": loss_output["L_token"],
                "L_temporal": loss_output["L_temporal"],
                "L_coherence": loss_output["L_coherence"],
                "L_latent": loss_output["L_latent"],
            },
            "plasticity": P_t,
            "gain": torch.tensor(G_t),
            "damping": torch.tensor(d_t),
            "g_eff": g_eff,
            "resistance_openness": plasticity_output["resistance_openness"],
        }

    def consolidate_identity(self) -> bool:
        """Slow loop: call every M >> N steps."""
        return self.identity.consolidate()

    def get_replay_items(self, k: int = 8) -> list:
        """Medium loop: get items for replay."""
        return self.replay.sample(k)

    def summary(self) -> str:
        """One-call system health report."""
        step = self.step.item()
        ids = self.identity.get_state()
        lines = [
            f"=== Experiential Controller (step {step}) ===",
            f"Identity: norm={ids['identity_norm']:.3f}, accumulator={ids['accumulator_count']}",
            f"Replay: buffer={len(self.replay)}",
            f"Resistance: mean={self.plasticity_gate.persistent_resistance.mean().item():.3f}",
        ]
        return "\n".join(lines)

    def _derive_regions(self, hidden: torch.Tensor) -> torch.Tensor:
        """Derive per-region states from hidden states."""
        B, T, D = hidden.shape
        R = self.config.num_regions
        if T >= R:
            chunk_size = T // R
            chunks = []
            for i in range(R):
                start = i * chunk_size
                end = start + chunk_size if i < R - 1 else T
                chunks.append(hidden[:, start:end, :].mean(dim=1))
            return torch.stack(chunks, dim=1)
        else:
            return hidden.mean(dim=1, keepdim=True).expand(B, R, D).clone()
