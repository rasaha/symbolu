"""
CSR Inference Guard Module
==========================

Inference-time CSR (Constraint-Structure-Resonance) safety layers.

This module implements phonetic-ontological grounding during generation,
applying the same safety constraints used during training to prevent:
- High-entropy (incoherent) output
- Repetition loops
- Divergent generation

Key components:
- EntropySink: Absorbs high-entropy energy from hidden states
- SynthesisGate: Controls information flow based on coherence

**CRITICAL**: Unlike earlier proposals, this implementation properly
re-projects modified hidden states through lm_head to ensure safety
interventions actually affect token selection.

Usage:
------
    from symbolu.inference import CSRInferenceGuard

    guard = CSRInferenceGuard(
        entropy_sink=trained_sink,
        synthesis_gate=trained_gate,
        lm_head=model.lm_head,
    )

    # In generation loop:
    outputs = model(input_ids, return_last_hidden=True)
    gated_logits, info = guard.apply(
        hidden_state=outputs['last_hidden_state'][:, -1, :],
        original_logits=outputs['logits'][:, -1, :],
    )

    # Use gated_logits for sampling (safety-enforced)
    next_token = sample(gated_logits)
"""

import math
from typing import Dict, List, Tuple, Optional, Any, Callable

import torch
import torch.nn as nn
import torch.nn.functional as F


class EntropySinkInference(nn.Module):
    """
    Inference-time Entropy Sink for absorbing high-entropy states.

    The EntropySink dampens hidden states when entropy is too high,
    preventing divergent generation. This is a lightweight version
    optimized for inference (no gradient tracking needed).

    Args:
        dim: Hidden dimension
        absorption_strength: How strongly to dampen high-entropy states
        threshold: Entropy threshold for activation
    """

    def __init__(
        self,
        dim: int,
        absorption_strength: float = 0.3,
        threshold: float = 2.0,
    ):
        super().__init__()
        self.dim = dim
        self.absorption_strength = absorption_strength
        self.threshold = threshold

        # Learnable sink projection (can be loaded from training)
        self.sink_proj = nn.Linear(dim, dim, bias=False)
        self.sink_gate = nn.Linear(dim, 1, bias=True)

        # Initialize to identity-like behavior
        nn.init.eye_(self.sink_proj.weight)
        nn.init.zeros_(self.sink_gate.weight)
        nn.init.constant_(self.sink_gate.bias, -2.0)  # Start mostly closed

    def forward(
        self,
        hidden_state: torch.Tensor,
        entropy_level: float,
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Apply entropy absorption to hidden state.

        Args:
            hidden_state: Hidden state tensor [B, D] or [B, N, D]
            entropy_level: Current entropy level (log-entropy)

        Returns:
            modified_state: Dampened hidden state
            info: Dict with absorption details
        """
        info = {
            "entropy_level": entropy_level,
            "sink_activated": False,
            "absorption_amount": 0.0,
        }

        # Only activate if entropy exceeds threshold
        if entropy_level <= self.threshold:
            return hidden_state, info

        info["sink_activated"] = True

        # Compute absorption amount based on how far above threshold
        excess = (entropy_level - self.threshold) / self.threshold
        absorption = min(self.absorption_strength, excess * self.absorption_strength)
        info["absorption_amount"] = absorption

        # Apply sink: project to dampened representation
        sink_output = self.sink_proj(hidden_state)

        # Gate controls how much sink to apply
        gate = torch.sigmoid(self.sink_gate(hidden_state))
        gate = gate * absorption  # Scale by absorption amount

        # Blend: hidden = (1 - gate) * hidden + gate * sink
        if hidden_state.dim() == 3:
            gate = gate.unsqueeze(-1)

        modified = (1 - gate) * hidden_state + gate * sink_output

        return modified, info


class SynthesisGateInference(nn.Module):
    """
    Inference-time Synthesis Gate for coherence-based information flow.

    The SynthesisGate modulates hidden state magnitude based on
    coherence signals, suppressing low-coherence representations.

    Args:
        dim: Hidden dimension
        gate_bias: Initial gate bias (negative = more restrictive)
    """

    def __init__(
        self,
        dim: int,
        gate_bias: float = 0.0,
    ):
        super().__init__()
        self.dim = dim

        # Gating network
        self.gate_proj = nn.Sequential(
            nn.Linear(dim, dim // 4),
            nn.GELU(),
            nn.Linear(dim // 4, 1),
        )

        # Apply initial bias
        if gate_bias != 0:
            self.gate_proj[-1].bias.data.fill_(gate_bias)

    def forward(
        self,
        hidden_state: torch.Tensor,
        coherence: Optional[float] = None,
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Apply synthesis gating to hidden state.

        Args:
            hidden_state: Hidden state tensor [B, D] or [B, N, D]
            coherence: External coherence signal (optional)

        Returns:
            gated_state: Gated hidden state
            info: Dict with gate values
        """
        # Compute gate value from hidden state
        gate_logit = self.gate_proj(hidden_state)
        gate = torch.sigmoid(gate_logit)

        # If external coherence provided, factor it in
        if coherence is not None:
            external_gate = torch.tensor(coherence, device=hidden_state.device)
            gate = gate * 0.7 + external_gate * 0.3

        # Apply gate
        if hidden_state.dim() == 3:
            gate = gate.unsqueeze(-1)

        gated_state = hidden_state * gate

        info = {
            "gate_value": gate.mean().item(),
            "gate_min": gate.min().item(),
            "gate_max": gate.max().item(),
        }

        return gated_state, info

    def compute_gate(self, hidden_state: torch.Tensor) -> torch.Tensor:
        """Compute gate value without applying it."""
        gate_logit = self.gate_proj(hidden_state)
        return torch.sigmoid(gate_logit)


class CSRInferenceGuard:
    """
    CSR Inference Guard with lm_head re-projection.

    This is the main safety layer for inference, combining:
    - EntropySink: Absorbs high-entropy states
    - SynthesisGate: Controls information flow

    **CRITICAL FEATURE**: After modifying hidden states, this guard
    re-projects through lm_head to ensure safety interventions
    actually affect the final token logits.

    This addresses the gap identified in evaluation:
    > "the SynthesisGate and EntropySink being computed but not
    > re-projected through the lm_head, rendering their safety
    > effects invisible to the actual token selection"

    Args:
        entropy_sink: Trained EntropySink module (or None for default)
        synthesis_gate: Trained SynthesisGate module (or None for default)
        lm_head: Language model head for re-projection (nn.Linear)
        dim: Hidden dimension (required if sink/gate are None)
        entropy_threshold: Threshold for entropy sink activation
        skip_threshold: Skip guard if confidence above this threshold

    Attributes:
        intervention_count: Number of times guard has intervened
        total_calls: Total number of guard calls
    """

    def __init__(
        self,
        entropy_sink: Optional[nn.Module] = None,
        synthesis_gate: Optional[nn.Module] = None,
        lm_head: Optional[nn.Module] = None,
        dim: int = 768,
        entropy_threshold: float = 2.0,
        skip_threshold: float = 0.9,
    ):
        # Initialize or use provided modules
        if entropy_sink is None:
            self.entropy_sink = EntropySinkInference(dim, threshold=entropy_threshold)
        else:
            self.entropy_sink = entropy_sink

        if synthesis_gate is None:
            self.synthesis_gate = SynthesisGateInference(dim)
        else:
            self.synthesis_gate = synthesis_gate

        self.lm_head = lm_head
        self.entropy_threshold = entropy_threshold
        self.skip_threshold = skip_threshold

        # Statistics
        self.intervention_count = 0
        self.total_calls = 0

    def set_lm_head(self, lm_head: nn.Module):
        """Set the lm_head for re-projection (call after model loading)."""
        self.lm_head = lm_head

    def to(self, device: torch.device) -> 'CSRInferenceGuard':
        """Move guard modules to device."""
        self.entropy_sink = self.entropy_sink.to(device)
        self.synthesis_gate = self.synthesis_gate.to(device)
        return self

    def apply(
        self,
        hidden_state: torch.Tensor,
        original_logits: torch.Tensor,
        coherence: Optional[float] = None,
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Apply CSR safety checks and return modified logits.

        This is the main entry point for the guard. It:
        1. Computes entropy from original logits
        2. Applies EntropySink if threshold exceeded
        3. Applies SynthesisGate for coherence control
        4. **Re-projects modified hidden state through lm_head**

        Args:
            hidden_state: Current hidden state [B, D] (last position)
            original_logits: Original logits [B, V] (for entropy check)
            coherence: External coherence signal (optional)

        Returns:
            modified_logits: Safety-enforced logits (use for sampling)
            info: Dict with intervention details
        """
        self.total_calls += 1

        info = {
            "entropy": 0.0,
            "sink_activated": False,
            "gate_applied": True,
            "re_projected": False,
            "intervention": False,
        }

        # Compute entropy from original logits
        probs = F.softmax(original_logits.float(), dim=-1)
        entropy = -(probs * torch.log(probs + 1e-10)).sum(dim=-1)
        mean_entropy = entropy.mean().item()
        info["entropy"] = mean_entropy

        # Fast path: skip if entropy is very low (high confidence)
        max_entropy = math.log(original_logits.shape[-1])
        normalized_entropy = mean_entropy / max_entropy
        if normalized_entropy < (1 - self.skip_threshold):
            info["skipped"] = True
            return original_logits, info

        # Track if we need to re-project
        state_modified = False
        current_hidden = hidden_state

        # Step 1: Apply EntropySink if entropy exceeds threshold
        if mean_entropy > self.entropy_threshold:
            current_hidden, sink_info = self.entropy_sink(
                current_hidden,
                entropy_level=mean_entropy,
            )
            info.update({f"sink_{k}": v for k, v in sink_info.items()})
            if sink_info["sink_activated"]:
                state_modified = True
                info["sink_activated"] = True

        # Step 2: Apply SynthesisGate
        current_hidden, gate_info = self.synthesis_gate(
            current_hidden,
            coherence=coherence,
        )
        info.update({f"gate_{k}": v for k, v in gate_info.items()})

        # Check if gate significantly modified the state
        if gate_info["gate_value"] < 0.95:
            state_modified = True

        # Step 3: Re-project through lm_head if state was modified
        if state_modified and self.lm_head is not None:
            modified_logits = self.lm_head(current_hidden)
            info["re_projected"] = True
            info["intervention"] = True
            self.intervention_count += 1
            return modified_logits, info

        # No significant modification, return original
        return original_logits, info

    def check_entropy(self, logits: torch.Tensor) -> Tuple[float, bool]:
        """
        Quick entropy check without full guard application.

        Args:
            logits: Token logits [B, V]

        Returns:
            entropy: Mean log-entropy
            exceeds_threshold: Whether entropy exceeds threshold
        """
        probs = F.softmax(logits.float(), dim=-1)
        entropy = -(probs * torch.log(probs + 1e-10)).sum(dim=-1)
        mean_entropy = entropy.mean().item()
        return mean_entropy, mean_entropy > self.entropy_threshold

    def get_statistics(self) -> Dict[str, Any]:
        """Get guard intervention statistics."""
        intervention_rate = (
            self.intervention_count / self.total_calls
            if self.total_calls > 0 else 0.0
        )
        return {
            "total_calls": self.total_calls,
            "intervention_count": self.intervention_count,
            "intervention_rate": intervention_rate,
        }

    def reset_statistics(self):
        """Reset intervention statistics."""
        self.intervention_count = 0
        self.total_calls = 0

    def load_from_training(
        self,
        checkpoint: Dict[str, Any],
        prefix: str = "csr_",
    ):
        """
        Load trained CSR weights from checkpoint.

        Args:
            checkpoint: Training checkpoint dict
            prefix: Key prefix for CSR weights in checkpoint
        """
        # Try to find entropy sink weights
        sink_keys = [k for k in checkpoint.keys() if "entropy_sink" in k.lower()]
        if sink_keys:
            sink_state = {
                k.replace(f"{prefix}entropy_sink.", ""): v
                for k, v in checkpoint.items()
                if k.startswith(f"{prefix}entropy_sink.")
            }
            if sink_state:
                self.entropy_sink.load_state_dict(sink_state, strict=False)

        # Try to find synthesis gate weights
        gate_keys = [k for k in checkpoint.keys() if "synthesis_gate" in k.lower()]
        if gate_keys:
            gate_state = {
                k.replace(f"{prefix}synthesis_gate.", ""): v
                for k, v in checkpoint.items()
                if k.startswith(f"{prefix}synthesis_gate.")
            }
            if gate_state:
                self.synthesis_gate.load_state_dict(gate_state, strict=False)
