#!/usr/bin/env python3
"""
CSR Inference Guard
====================

Inference-time safety layer using CSR (Constraint-Structure-Resonance) components.

Monitors generation entropy and applies safety interventions:
1. Flag high-entropy tokens for review
2. Apply synthesis gating to hidden states
3. Optionally reject/resample tokens exceeding entropy threshold

Training Reference: csr_phoneme_provider.py (EntropySink, SynthesisGate)

Author: Sovereign-1 Training Initiative
Date: January 2026
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
import math
import warnings


@dataclass
class CSRGuardConfig:
    """Configuration for CSR inference guard."""
    entropy_threshold: float = 2.0  # Log-entropy threshold for intervention
    confidence_threshold: float = 0.1  # Min confidence to accept token
    temperature_dampening: float = 0.7  # Temperature multiplier when entropy high
    max_resample_attempts: int = 3  # Max resampling when entropy exceeded
    enable_entropy_sink: bool = True
    enable_synthesis_gate: bool = True


class EntropySinkInference(nn.Module):
    """
    Inference-time entropy sink.

    Absorbs high-entropy energy from hidden states to prevent divergence.
    Trained version learns projection; inference uses simplified dampening.
    """

    def __init__(self, embed_dim: int, sink_dim: Optional[int] = None):
        super().__init__()
        self.embed_dim = embed_dim
        self.sink_dim = sink_dim or embed_dim // 4

        # Projection to sink space
        self.sink_proj = nn.Linear(embed_dim, self.sink_dim)
        self.sink_gate = nn.Linear(self.sink_dim, 1)

        # Re-projection back
        self.out_proj = nn.Linear(self.sink_dim, embed_dim)

        # Initialize to identity-like behavior
        nn.init.zeros_(self.out_proj.weight)
        nn.init.zeros_(self.out_proj.bias)

    def forward(
        self,
        hidden_state: torch.Tensor,
        entropy_level: float = 0.0,
    ) -> torch.Tensor:
        """
        Apply entropy sink to absorb high-entropy energy.

        Args:
            hidden_state: [B, D] or [B, T, D] hidden state
            entropy_level: Current entropy level (0-inf)

        Returns:
            dampened: Hidden state with entropy absorbed
        """
        original_shape = hidden_state.shape
        if hidden_state.dim() == 3:
            B, T, D = hidden_state.shape
            hidden_state = hidden_state.view(B * T, D)

        # Project to sink space
        sink_state = self.sink_proj(hidden_state)
        sink_state = F.gelu(sink_state)

        # Compute absorption gate based on entropy
        absorption = torch.sigmoid(self.sink_gate(sink_state))

        # Scale absorption by entropy (more entropy = more absorption)
        entropy_scale = min(1.0, entropy_level / 3.0)  # Normalize
        absorption = absorption * entropy_scale

        # Absorb energy (subtract from hidden)
        absorbed = self.out_proj(sink_state * absorption)
        dampened = hidden_state - absorbed

        # Reshape if needed
        if len(original_shape) == 3:
            dampened = dampened.view(original_shape)

        return dampened

    def load_from_checkpoint(self, state_dict: Dict[str, torch.Tensor]) -> bool:
        """Load weights from checkpoint."""
        prefixes = ["csr_entropy_sink.", "entropy_sink.", ""]

        for prefix in prefixes:
            try:
                self.sink_proj.weight.data = state_dict[f"{prefix}sink_proj.weight"]
                self.sink_proj.bias.data = state_dict[f"{prefix}sink_proj.bias"]
                self.sink_gate.weight.data = state_dict[f"{prefix}sink_gate.weight"]
                self.sink_gate.bias.data = state_dict[f"{prefix}sink_gate.bias"]
                self.out_proj.weight.data = state_dict[f"{prefix}out_proj.weight"]
                self.out_proj.bias.data = state_dict[f"{prefix}out_proj.bias"]
                return True
            except KeyError:
                continue

        return False


class SynthesisGateInference(nn.Module):
    """
    Inference-time synthesis gate.

    Controls information flow based on coherence/confidence signals.
    """

    def __init__(self, embed_dim: int):
        super().__init__()
        self.embed_dim = embed_dim

        # Gate computation
        self.gate_proj = nn.Linear(embed_dim, embed_dim)
        self.gate_norm = nn.LayerNorm(embed_dim)

    def forward(
        self,
        hidden_state: torch.Tensor,
        confidence: Optional[torch.Tensor] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Apply synthesis gate to hidden state.

        Args:
            hidden_state: [B, D] or [B, T, D] hidden state
            confidence: Optional [B] or [B, T] confidence scores

        Returns:
            gated: Gated hidden state
            gate_values: Gate activations for monitoring
        """
        # Compute gate
        gate = torch.sigmoid(self.gate_proj(hidden_state))
        gate = self.gate_norm(gate)

        # Apply confidence scaling if provided
        if confidence is not None:
            if confidence.dim() < gate.dim():
                confidence = confidence.unsqueeze(-1)
            gate = gate * confidence

        # Apply gate
        gated = hidden_state * gate

        return gated, gate.mean(dim=-1)

    def compute_gate(self, hidden_state: torch.Tensor) -> torch.Tensor:
        """Compute gate value without applying."""
        gate = torch.sigmoid(self.gate_proj(hidden_state))
        return gate.mean(dim=-1)

    def load_from_checkpoint(self, state_dict: Dict[str, torch.Tensor]) -> bool:
        """Load weights from checkpoint."""
        prefixes = ["csr_synthesis_gate.", "synthesis_gate.", ""]

        for prefix in prefixes:
            try:
                self.gate_proj.weight.data = state_dict[f"{prefix}gate_proj.weight"]
                self.gate_proj.bias.data = state_dict[f"{prefix}gate_proj.bias"]
                self.gate_norm.weight.data = state_dict[f"{prefix}gate_norm.weight"]
                self.gate_norm.bias.data = state_dict[f"{prefix}gate_norm.bias"]
                return True
            except KeyError:
                continue

        return False


class CSRInferenceGuard:
    """
    Apply CSR safety layers during inference.

    Monitors generation entropy and can:
    1. Flag high-entropy tokens for review
    2. Apply synthesis gating to hidden states
    3. Optionally reject/resample tokens exceeding entropy threshold

    IMPORTANT: The lm_head parameter may be None. All methods that use
    lm_head must check for None before accessing it.

    Example:
        guard = CSRInferenceGuard(config, lm_head=model.lm_head)
        guard.to(device)

        # During generation
        gated_logits, info = guard.check_and_gate(hidden_state, logits)
        if info['warning']:
            print(f"Warning: {info['warning']}")
    """

    def __init__(
        self,
        config: Optional[CSRGuardConfig] = None,
        entropy_sink: Optional[EntropySinkInference] = None,
        synthesis_gate: Optional[SynthesisGateInference] = None,
        embed_dim: int = 768,
        lm_head: Optional[nn.Module] = None,
    ):
        """
        Initialize CSR inference guard.

        Args:
            config: Guard configuration
            entropy_sink: Pre-initialized entropy sink (or None to create)
            synthesis_gate: Pre-initialized synthesis gate (or None to create)
            embed_dim: Embedding dimension for creating components
            lm_head: Language model head for re-projection (MAY BE NONE)
        """
        self.config = config or CSRGuardConfig()
        self.embed_dim = embed_dim

        # Initialize components
        self.entropy_sink = entropy_sink or EntropySinkInference(embed_dim)
        self.synthesis_gate = synthesis_gate or SynthesisGateInference(embed_dim)

        # CRITICAL: lm_head may be None - always check before use
        self._lm_head = lm_head
        self._lm_head_available = lm_head is not None

        # Tracking
        self.entropy_history: List[float] = []
        self.intervention_count: int = 0
        self._device: torch.device = torch.device('cpu')

    @property
    def lm_head(self) -> Optional[nn.Module]:
        """Get lm_head with explicit None check warning."""
        if self._lm_head is None:
            warnings.warn(
                "CSRInferenceGuard.lm_head is None. "
                "Re-projection after entropy sink is disabled."
            )
        return self._lm_head

    def set_lm_head(self, lm_head: nn.Module) -> None:
        """
        Set lm_head after initialization.

        Args:
            lm_head: Language model head module
        """
        self._lm_head = lm_head
        self._lm_head_available = lm_head is not None

    def to(self, device: Union[str, torch.device]) -> 'CSRInferenceGuard':
        """
        Move guard to specified device.

        Args:
            device: Target device

        Returns:
            self for chaining
        """
        if isinstance(device, str):
            device = torch.device(device)

        self._device = device
        self.entropy_sink = self.entropy_sink.to(device)
        self.synthesis_gate = self.synthesis_gate.to(device)

        return self

    @property
    def device(self) -> torch.device:
        """Get current device."""
        return self._device

    def compute_entropy(self, logits: torch.Tensor) -> torch.Tensor:
        """
        Compute token distribution entropy.

        Args:
            logits: [B, V] or [B, T, V] logits

        Returns:
            entropy: [B] or [B, T] entropy values
        """
        probs = F.softmax(logits, dim=-1)
        log_probs = torch.log(probs + 1e-10)
        entropy = -(probs * log_probs).sum(dim=-1)

        return entropy

    def check_and_gate(
        self,
        hidden_state: torch.Tensor,
        token_logits: torch.Tensor,
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Apply CSR safety checks to generation step.

        Args:
            hidden_state: Current hidden state [B, D] or [B, T, D]
            token_logits: Logits for next token [B, V] or [B, T, V]

        Returns:
            gated_logits: Possibly modified logits
            safety_info: Dict with entropy, gate values, warnings
        """
        # Compute entropy
        entropy = self.compute_entropy(token_logits)
        mean_entropy = entropy.mean().item()
        self.entropy_history.append(mean_entropy)

        safety_info = {
            "entropy": mean_entropy,
            "sink_activated": False,
            "gate_applied": False,
            "gate_value": 1.0,
            "warning": None,
            "intervention": False,
        }

        # Check if entropy exceeds threshold
        if mean_entropy > self.config.entropy_threshold:
            self.intervention_count += 1
            safety_info["intervention"] = True

            # Apply entropy sink if enabled
            if self.config.enable_entropy_sink:
                hidden_state = self.entropy_sink(hidden_state, entropy_level=mean_entropy)
                safety_info["sink_activated"] = True

                # CRITICAL: Check if lm_head is available before re-projection
                if self._lm_head_available and self._lm_head is not None:
                    # Re-project to logits with dampened hidden state
                    if hidden_state.dim() == 2:
                        token_logits = self._lm_head(hidden_state)
                    else:
                        # For sequence hidden states, take last position
                        token_logits = self._lm_head(hidden_state[:, -1, :])

                    safety_info["warning"] = (
                        f"High entropy ({mean_entropy:.2f}) - sink applied, logits recomputed"
                    )
                else:
                    # Cannot recompute logits without lm_head
                    # Apply temperature dampening instead
                    token_logits = token_logits / self.config.temperature_dampening
                    safety_info["warning"] = (
                        f"High entropy ({mean_entropy:.2f}) - sink applied, "
                        f"lm_head unavailable so temperature dampened"
                    )

        # Apply synthesis gate if enabled
        if self.config.enable_synthesis_gate:
            _, gate_value = self.synthesis_gate(hidden_state)
            safety_info["gate_value"] = gate_value.mean().item()
            safety_info["gate_applied"] = True

        return token_logits, safety_info

    def should_resample(
        self,
        token_logits: torch.Tensor,
        attempt: int = 0,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if token should be resampled due to high entropy.

        Args:
            token_logits: [B, V] logits for next token
            attempt: Current resampling attempt number

        Returns:
            should_resample: Whether to resample
            info: Dict with reason and suggestions
        """
        if attempt >= self.config.max_resample_attempts:
            return False, {"reason": "max_attempts_reached", "attempts": attempt}

        entropy = self.compute_entropy(token_logits)
        mean_entropy = entropy.mean().item()

        if mean_entropy > self.config.entropy_threshold * 1.5:  # Higher threshold for resampling
            return True, {
                "reason": "entropy_exceeded",
                "entropy": mean_entropy,
                "suggestion": "lower_temperature",
            }

        # Check if top probability is too low (low confidence)
        probs = F.softmax(token_logits, dim=-1)
        top_prob = probs.max(dim=-1)[0].mean().item()

        if top_prob < self.config.confidence_threshold:
            return True, {
                "reason": "low_confidence",
                "top_prob": top_prob,
                "suggestion": "increase_top_k",
            }

        return False, {"reason": "acceptable"}

    def get_adjusted_sampling_params(
        self,
        base_temperature: float,
        base_top_p: float,
        current_entropy: Optional[float] = None,
    ) -> Dict[str, float]:
        """
        Get adjusted sampling parameters based on entropy history.

        Args:
            base_temperature: Base temperature
            base_top_p: Base top-p value
            current_entropy: Current step entropy (or use recent average)

        Returns:
            params: Dict with adjusted temperature, top_p
        """
        # Use recent average if current not provided
        if current_entropy is None and self.entropy_history:
            current_entropy = sum(self.entropy_history[-5:]) / len(self.entropy_history[-5:])
        elif current_entropy is None:
            return {"temperature": base_temperature, "top_p": base_top_p}

        # Adjust based on entropy level
        if current_entropy > self.config.entropy_threshold:
            # High entropy: reduce temperature, reduce top_p
            temp_mult = max(0.5, 1.0 - (current_entropy - self.config.entropy_threshold) / 5.0)
            top_p_adj = max(-0.2, -(current_entropy - self.config.entropy_threshold) / 10.0)
        elif current_entropy < self.config.entropy_threshold * 0.5:
            # Low entropy: slight increase for variety
            temp_mult = min(1.2, 1.0 + (self.config.entropy_threshold * 0.5 - current_entropy) / 5.0)
            top_p_adj = min(0.05, (self.config.entropy_threshold * 0.5 - current_entropy) / 20.0)
        else:
            # Normal range
            temp_mult = 1.0
            top_p_adj = 0.0

        return {
            "temperature": base_temperature * temp_mult,
            "top_p": max(0.1, min(1.0, base_top_p + top_p_adj)),
        }

    def get_status_line(self) -> str:
        """
        Get status line for monitoring display.

        Returns:
            status: Human-readable status string
        """
        if not self.entropy_history:
            return "CSR Guard: no data"

        avg_entropy = sum(self.entropy_history[-20:]) / len(self.entropy_history[-20:])
        max_entropy = max(self.entropy_history[-20:]) if self.entropy_history else 0

        parts = [
            f"CSR Guard",
            f"Entropy: {avg_entropy:.2f}",
            f"Max: {max_entropy:.2f}",
            f"Interventions: {self.intervention_count}",
        ]

        if not self._lm_head_available:
            parts.append("(no lm_head)")

        return " | ".join(parts)

    def reset_history(self) -> None:
        """Reset tracking history."""
        self.entropy_history = []
        self.intervention_count = 0

    def load_from_checkpoint(self, checkpoint: Dict[str, Any]) -> bool:
        """
        Load CSR components from checkpoint.

        Args:
            checkpoint: Checkpoint dict

        Returns:
            success: Whether any components were loaded
        """
        success = False

        # Try to load entropy sink
        if 'csr_entropy_sink' in checkpoint:
            if self.entropy_sink.load_from_checkpoint(checkpoint['csr_entropy_sink']):
                success = True

        # Try to load synthesis gate
        if 'csr_synthesis_gate' in checkpoint:
            if self.synthesis_gate.load_from_checkpoint(checkpoint['csr_synthesis_gate']):
                success = True

        # Try loading from flat state dict
        if not success and isinstance(checkpoint, dict):
            sink_loaded = self.entropy_sink.load_from_checkpoint(checkpoint)
            gate_loaded = self.synthesis_gate.load_from_checkpoint(checkpoint)
            success = sink_loaded or gate_loaded

        return success
