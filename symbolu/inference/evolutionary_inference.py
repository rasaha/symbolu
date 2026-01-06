#!/usr/bin/env python3
"""
Evolutionary Inference Engine
==============================

Inference-time implementation of the EvolutionaryBridge (O12->O1 karma transfer).

This enables:
- Cognitive continuity across context windows
- "Memory" of previous conversations/sequences
- Recursive intelligence pattern during generation

Training Reference: train_unified_llm.py:373-538 (EvolutionaryBridge class)

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
class EvolutionaryConfig:
    """Configuration for evolutionary inference."""
    embed_dim: int = 768
    resonance_alpha: float = 0.1
    karma_decay: float = 0.95
    coherence_threshold: float = 0.3
    max_karma_age: int = 10  # Max sequences before karma expires
    enable_guna_scaling: bool = False  # Scale alpha by Guna state


class EvolutionaryBridgeInference(nn.Module):
    """
    Inference-time evolutionary bridge for karma state management.

    Loads trained weights from checkpoint and provides:
    - seed_gate: Gates how much karma influences next sequence
    - seed_proj: Projects O12 harvest to seed space
    - seed_norm: Normalizes seed for stability
    """

    def __init__(self, embed_dim: int):
        super().__init__()
        self.embed_dim = embed_dim

        # Match training architecture
        self.seed_proj = nn.Linear(embed_dim, embed_dim)
        self.seed_gate = nn.Linear(embed_dim, embed_dim)
        self.seed_norm = nn.LayerNorm(embed_dim)

    def compute_seed(self, o12_hidden: torch.Tensor) -> torch.Tensor:
        """
        Compute karma seed from O12 hidden state.

        Args:
            o12_hidden: [B, D] mean-pooled O12 hidden state

        Returns:
            seed: [B, D] karma seed for next sequence
        """
        projected = self.seed_proj(o12_hidden)
        gate = torch.sigmoid(self.seed_gate(o12_hidden))
        seed = self.seed_norm(projected * gate)
        return seed

    def load_from_checkpoint(self, state_dict: Dict[str, torch.Tensor]) -> bool:
        """
        Load bridge weights from checkpoint.

        Args:
            state_dict: Checkpoint state dict (may contain evolutionary_bridge.*)

        Returns:
            success: Whether weights were loaded
        """
        # Try different key patterns
        prefixes = ["evolutionary_bridge.", "bridge.", ""]

        for prefix in prefixes:
            try:
                self.seed_proj.weight.data = state_dict[f"{prefix}seed_proj.weight"]
                self.seed_proj.bias.data = state_dict[f"{prefix}seed_proj.bias"]
                self.seed_gate.weight.data = state_dict[f"{prefix}seed_gate.weight"]
                self.seed_gate.bias.data = state_dict[f"{prefix}seed_gate.bias"]
                self.seed_norm.weight.data = state_dict[f"{prefix}seed_norm.weight"]
                self.seed_norm.bias.data = state_dict[f"{prefix}seed_norm.bias"]
                return True
            except KeyError:
                continue

        return False


class EvolutionaryInferenceEngine:
    """
    Inference-time evolutionary state management.

    Maintains karma buffer across generation sequences and injects
    previous cognitive state into new sequences.

    Key Methods:
        - generate_with_karma(): Generate with evolutionary state injection
        - apply_inference_resonance(): Inject karma into hidden states
        - get_status_line(): Return status for monitoring

    Example:
        engine = EvolutionaryInferenceEngine(model, checkpoint_path)
        engine.to(device)  # Move to correct device

        output, meta = engine.generate_with_karma(input_ids, max_new_tokens=128)
        print(engine.get_status_line())  # "Karma: active | Coherence: 0.85"
    """

    def __init__(
        self,
        model: nn.Module,
        config: Optional[EvolutionaryConfig] = None,
        bridge_checkpoint_path: Optional[str] = None,
    ):
        """
        Initialize evolutionary inference engine.

        Args:
            model: The transformer model (HybridPhaseTransformer or similar)
            config: Evolutionary configuration
            bridge_checkpoint_path: Path to checkpoint with bridge weights
        """
        self.model = model
        self.config = config or EvolutionaryConfig()

        # Infer embed_dim from model
        if hasattr(model, 'embed_dim'):
            embed_dim = model.embed_dim
        elif hasattr(model, 'config') and hasattr(model.config, 'hidden_size'):
            embed_dim = model.config.hidden_size
        else:
            embed_dim = self.config.embed_dim

        self.embed_dim = embed_dim

        # Initialize bridge
        self.bridge = EvolutionaryBridgeInference(embed_dim)
        self.bridge_enabled = False

        # State buffers
        self.karma_buffer: Optional[torch.Tensor] = None
        self.current_o12: Optional[torch.Tensor] = None
        self.karma_age: int = 0
        self.coherence_history: List[float] = []

        # Device tracking
        self._device: torch.device = torch.device('cpu')

        # Load bridge if checkpoint provided
        if bridge_checkpoint_path:
            self._load_bridge(bridge_checkpoint_path)

    def to(self, device: Union[str, torch.device]) -> 'EvolutionaryInferenceEngine':
        """
        Move engine to specified device.

        Args:
            device: Target device ('cuda', 'cpu', or torch.device)

        Returns:
            self for chaining
        """
        if isinstance(device, str):
            device = torch.device(device)

        self._device = device
        self.bridge = self.bridge.to(device)

        # Move karma buffer if exists
        if self.karma_buffer is not None:
            self.karma_buffer = self.karma_buffer.to(device)
        if self.current_o12 is not None:
            self.current_o12 = self.current_o12.to(device)

        return self

    @property
    def device(self) -> torch.device:
        """Get current device."""
        return self._device

    def _load_bridge(self, checkpoint_path: str) -> None:
        """Load bridge weights from checkpoint."""
        try:
            checkpoint = torch.load(checkpoint_path, map_location='cpu')

            # Handle different checkpoint formats
            if isinstance(checkpoint, dict):
                if 'evolutionary_bridge' in checkpoint:
                    state_dict = checkpoint['evolutionary_bridge']
                elif 'model' in checkpoint:
                    state_dict = checkpoint['model']
                else:
                    state_dict = checkpoint
            else:
                state_dict = checkpoint

            success = self.bridge.load_from_checkpoint(state_dict)

            if success:
                self.bridge_enabled = True
                print(f"[EvolutionaryInference] Bridge loaded from {checkpoint_path}")
            else:
                warnings.warn(
                    f"Checkpoint {checkpoint_path} does not contain evolutionary bridge weights. "
                    "Karma injection will be disabled."
                )

        except Exception as e:
            warnings.warn(f"Failed to load bridge from {checkpoint_path}: {e}")

    def generate_with_karma(
        self,
        input_ids: torch.Tensor,
        max_new_tokens: int = 128,
        inject_karma: bool = True,
        temperature: float = 1.0,
        top_p: float = 0.9,
        top_k: int = 50,
        **kwargs,
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Generate with evolutionary state injection.

        1. If karma_buffer exists, inject into initial hidden state
        2. Generate tokens
        3. Extract O12 hidden state and store as new karma

        Args:
            input_ids: [B, T] input token IDs
            max_new_tokens: Maximum tokens to generate
            inject_karma: Whether to inject stored karma
            temperature: Sampling temperature
            top_p: Nucleus sampling probability
            top_k: Top-k sampling
            **kwargs: Additional generation arguments

        Returns:
            generated_ids: [B, T+N] generated token IDs
            meta: Dict with karma_coherence, bridge_active, etc.
        """
        # Ensure on correct device
        input_ids = input_ids.to(self._device)

        meta = {
            "karma_injected": False,
            "karma_coherence": 0.0,
            "bridge_active": self.bridge_enabled,
            "karma_age": self.karma_age,
        }

        # Check karma expiration
        if self.karma_age >= self.config.max_karma_age:
            self.karma_buffer = None
            self.karma_age = 0

        # Prepare karma injection
        karma_to_inject = None
        if inject_karma and self.karma_buffer is not None and self.bridge_enabled:
            karma_to_inject = self.karma_buffer * self.config.resonance_alpha
            meta["karma_injected"] = True

        # Forward pass with hidden state extraction
        with torch.no_grad():
            # Check if model supports return_hidden
            if hasattr(self.model, 'forward'):
                try:
                    outputs = self.model(
                        input_ids,
                        return_hidden=True,
                        karma_injection=karma_to_inject,
                        **kwargs,
                    )
                except TypeError:
                    # Model doesn't support these args, use basic forward
                    outputs = self.model(input_ids, **kwargs)
            else:
                outputs = self.model(input_ids, **kwargs)

            # Extract hidden states
            if isinstance(outputs, dict) and 'hidden_states' in outputs:
                hidden_states = outputs['hidden_states']
                logits = outputs.get('logits', outputs.get('output'))
            elif isinstance(outputs, tuple) and len(outputs) >= 2:
                logits = outputs[0]
                hidden_states = outputs[1] if len(outputs) > 1 else None
            else:
                logits = outputs
                hidden_states = None

            # Generate tokens autoregressively
            generated = self._autoregressive_generate(
                input_ids=input_ids,
                logits=logits,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
            )

            # Extract and store new karma from O12
            if hidden_states is not None and self.bridge_enabled:
                o12_hidden = hidden_states[-1] if isinstance(hidden_states, list) else hidden_states

                # Mean pool over sequence dimension
                if o12_hidden.dim() == 3:
                    o12_pooled = o12_hidden.mean(dim=1)
                else:
                    o12_pooled = o12_hidden

                # Compute new karma seed
                new_karma = self.bridge.compute_seed(o12_pooled)

                # Compute coherence with previous karma
                if self.karma_buffer is not None:
                    coherence = self._compute_coherence(self.karma_buffer, new_karma)
                    meta["karma_coherence"] = coherence
                    self.coherence_history.append(coherence)

                # Apply decay and store
                self.karma_buffer = new_karma * self.config.karma_decay
                self.current_o12 = o12_pooled
                self.karma_age += 1

        return generated, meta

    def _autoregressive_generate(
        self,
        input_ids: torch.Tensor,
        logits: Optional[torch.Tensor],
        max_new_tokens: int,
        temperature: float,
        top_p: float,
        top_k: int,
    ) -> torch.Tensor:
        """Simple autoregressive generation loop."""
        generated = input_ids.clone()

        for _ in range(max_new_tokens):
            # Get logits for last position
            if logits is None:
                with torch.no_grad():
                    outputs = self.model(generated)
                    if isinstance(outputs, dict):
                        logits = outputs.get('logits', outputs.get('output'))
                    elif isinstance(outputs, tuple):
                        logits = outputs[0]
                    else:
                        logits = outputs

            next_logits = logits[:, -1, :] / max(temperature, 1e-8)

            # Apply top-k
            if top_k > 0:
                indices_to_remove = next_logits < torch.topk(next_logits, top_k)[0][..., -1, None]
                next_logits[indices_to_remove] = float('-inf')

            # Apply top-p (nucleus)
            if top_p < 1.0:
                sorted_logits, sorted_indices = torch.sort(next_logits, descending=True)
                cumulative_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)
                sorted_indices_to_remove = cumulative_probs > top_p
                sorted_indices_to_remove[..., 1:] = sorted_indices_to_remove[..., :-1].clone()
                sorted_indices_to_remove[..., 0] = 0
                indices_to_remove = sorted_indices_to_remove.scatter(
                    -1, sorted_indices, sorted_indices_to_remove
                )
                next_logits[indices_to_remove] = float('-inf')

            # Sample
            probs = F.softmax(next_logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)

            # Append
            generated = torch.cat([generated, next_token], dim=-1)

            # Reset logits for next iteration
            logits = None

            # Check for EOS (assuming token 2 is EOS)
            if next_token.item() == 2:
                break

        return generated

    def apply_inference_resonance(
        self,
        current_hidden: torch.Tensor,
        alpha: Optional[float] = None,
    ) -> torch.Tensor:
        """
        Apply resonance from stored karma to current hidden state.

        For inference, use fixed alpha (no Guna tracking available unless
        InferenceGunas is integrated).

        Args:
            current_hidden: [B, T, D] current hidden state
            alpha: Override resonance strength (default: config.resonance_alpha)

        Returns:
            resonated: [B, T, D] hidden state with karma injected
        """
        if self.karma_buffer is None:
            return current_hidden

        alpha = alpha if alpha is not None else self.config.resonance_alpha

        # Expand karma to match current hidden dimensions
        karma_expanded = self.karma_buffer.unsqueeze(1)  # [B, 1, D]

        if current_hidden.dim() == 3:
            karma_expanded = karma_expanded.expand(-1, current_hidden.size(1), -1)

        # Inject with alpha scaling
        resonated = current_hidden + (alpha * karma_expanded)

        return resonated

    def _compute_coherence(
        self,
        karma: torch.Tensor,
        current: torch.Tensor,
    ) -> float:
        """Compute cosine coherence between karma and current state."""
        # Flatten if needed
        karma_flat = karma.view(1, -1)
        current_flat = current.view(1, -1)

        sim = F.cosine_similarity(karma_flat, current_flat)

        # Map from [-1, 1] to [0, 1]
        return (sim.item() + 1) / 2

    def compute_generation_coherence(self) -> float:
        """
        Compute coherence between stored karma and current generation.

        Useful for:
        - Detecting topic drift in long conversations
        - Measuring "memory retention" quality

        Returns:
            coherence: [0, 1] coherence score
        """
        if self.karma_buffer is None or self.current_o12 is None:
            return 0.0

        return self._compute_coherence(self.karma_buffer, self.current_o12)

    def clear_karma(self) -> None:
        """Clear karma buffer and reset state."""
        self.karma_buffer = None
        self.current_o12 = None
        self.karma_age = 0
        self.coherence_history = []

    def get_status_line(self) -> str:
        """
        Get status line for monitoring display.

        Returns:
            status: Human-readable status string
        """
        if not self.bridge_enabled:
            return "Karma: disabled (no bridge)"

        if self.karma_buffer is None:
            return "Karma: inactive (no buffer)"

        coherence = self.compute_generation_coherence()
        avg_coherence = (
            sum(self.coherence_history[-10:]) / len(self.coherence_history[-10:])
            if self.coherence_history else 0.0
        )

        status_parts = [
            f"Karma: active",
            f"Age: {self.karma_age}",
            f"Coh: {coherence:.2f}",
            f"Avg: {avg_coherence:.2f}",
        ]

        return " | ".join(status_parts)

    def get_state(self) -> Dict[str, Any]:
        """
        Get full state for serialization.

        Returns:
            state: Dict containing all state info
        """
        return {
            "karma_buffer": self.karma_buffer.cpu() if self.karma_buffer is not None else None,
            "current_o12": self.current_o12.cpu() if self.current_o12 is not None else None,
            "karma_age": self.karma_age,
            "coherence_history": self.coherence_history,
            "bridge_enabled": self.bridge_enabled,
            "config": {
                "embed_dim": self.config.embed_dim,
                "resonance_alpha": self.config.resonance_alpha,
                "karma_decay": self.config.karma_decay,
            },
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        """
        Load state from serialized dict.

        Args:
            state: Dict from get_state()
        """
        if state.get("karma_buffer") is not None:
            self.karma_buffer = state["karma_buffer"].to(self._device)
        if state.get("current_o12") is not None:
            self.current_o12 = state["current_o12"].to(self._device)
        self.karma_age = state.get("karma_age", 0)
        self.coherence_history = state.get("coherence_history", [])
