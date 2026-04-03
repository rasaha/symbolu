#!/usr/bin/env python3
"""
Binding Cache Inference Engine
===============================

Inference-time engine for BindingCacheTransformer (V10.0).

This engine provides:
- Proposal mode metrics access and control
- Intent phase injection support
- Binding salience control
- Phase health monitoring
- Cache instrumentation access

Training Reference: symbolu/phase_transformer.py:3375-3724 (BindingCacheTransformer)

Author: Sovereign-1 Training Initiative
Date: January 2026
Phase: 5b - V10.0 Binding Cache Inference
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
import math
import warnings


@dataclass
class BindingCacheInferenceConfig:
    """Configuration for Binding Cache inference."""
    embed_dim: int = 768
    num_heads: int = 12
    top_k: int = 64

    # Proposal mode settings
    confidence_threshold: float = 0.7
    adaptive_confidence: bool = True
    confidence_adaptation_rate: float = 0.1

    # Intent phase settings
    enable_intent_injection: bool = True
    intent_decay: float = 0.9

    # Binding salience settings
    enable_salience_control: bool = True
    default_salience_boost: float = 1.0

    # Monitoring
    track_phase_health: bool = True
    track_cache_metrics: bool = True


class IntentPhaseInferenceModule:
    """
    Compute and manage intent phase during inference.

    Intent phase rotates key phases in the binding cache to change
    how bindings are stored/retrieved based on intent.

    This module supports:
    - Computing intent from conversation history
    - Injecting external intent signals
    - Tracking intent evolution across tokens
    """

    def __init__(self, num_heads: int = 12, head_dim: int = 64):
        """
        Initialize intent phase module.

        Args:
            num_heads: Number of attention heads
            head_dim: Dimension per head
        """
        self.num_heads = num_heads
        self.head_dim = head_dim
        self._current_intent: Optional[torch.Tensor] = None
        self._intent_history: List[torch.Tensor] = []
        self._device = torch.device('cpu')

    def to(self, device: Union[str, torch.device]) -> 'IntentPhaseInferenceModule':
        """Move to device."""
        if isinstance(device, str):
            device = torch.device(device)
        self._device = device
        if self._current_intent is not None:
            self._current_intent = self._current_intent.to(device)
        return self

    def compute_intent_from_hidden(
        self,
        hidden_states: torch.Tensor,
        pooling: str = 'mean',
    ) -> torch.Tensor:
        """
        Compute intent phase from hidden states.

        Args:
            hidden_states: [B, T, D] hidden states
            pooling: 'mean', 'last', or 'first'

        Returns:
            intent_phase: [B, H] intent phase per head
        """
        # Pool over sequence dimension
        if pooling == 'mean':
            pooled = hidden_states.mean(dim=1)  # [B, D]
        elif pooling == 'last':
            pooled = hidden_states[:, -1, :]
        else:  # first
            pooled = hidden_states[:, 0, :]

        # Simple linear projection to num_heads dimensions
        # In practice, this would use the trained IntentPhaseProjector
        B, D = pooled.shape

        # Use a simple averaging scheme over embed_dim to get H values
        # Each head gets a phase angle based on its portion of the embedding
        chunk_size = D // self.num_heads
        intent_phases = []
        for h in range(self.num_heads):
            start = h * chunk_size
            end = start + chunk_size if h < self.num_heads - 1 else D
            chunk_mean = pooled[:, start:end].mean(dim=-1)  # [B]
            # Map to phase angle [-π, π]
            phase = torch.tanh(chunk_mean) * math.pi
            intent_phases.append(phase)

        intent_phase = torch.stack(intent_phases, dim=-1)  # [B, H]

        self._current_intent = intent_phase
        self._intent_history.append(intent_phase.clone())

        return intent_phase

    def inject_external_intent(
        self,
        intent_phase: torch.Tensor,
        blend_alpha: float = 1.0,
    ) -> torch.Tensor:
        """
        Inject external intent phase, optionally blending with current.

        Args:
            intent_phase: [B, H] or [B, H, D_h] external intent
            blend_alpha: Blend factor (1.0 = full external, 0.0 = full current)

        Returns:
            blended_intent: Resulting intent phase
        """
        if self._current_intent is None:
            self._current_intent = intent_phase.to(self._device)
        else:
            self._current_intent = (
                blend_alpha * intent_phase.to(self._device) +
                (1 - blend_alpha) * self._current_intent
            )

        self._intent_history.append(self._current_intent.clone())
        return self._current_intent

    def get_current_intent(self) -> Optional[torch.Tensor]:
        """Get current intent phase."""
        return self._current_intent

    def get_intent_evolution(self) -> List[torch.Tensor]:
        """Get history of intent phases."""
        return self._intent_history

    def clear(self) -> None:
        """Clear intent state."""
        self._current_intent = None
        self._intent_history = []


class BindingSalienceController:
    """
    Control binding salience during inference.

    Binding salience biases Top-K selection without modifying attention math.
    Higher salience for a position means it's more likely to be selected
    in the Top-K cache.
    """

    def __init__(self, default_boost: float = 1.0):
        """
        Initialize salience controller.

        Args:
            default_boost: Default salience boost factor
        """
        self.default_boost = default_boost
        self._position_boosts: Dict[int, float] = {}
        self._token_boosts: Dict[int, float] = {}
        self._device = torch.device('cpu')

    def to(self, device: Union[str, torch.device]) -> 'BindingSalienceController':
        """Move to device."""
        if isinstance(device, str):
            device = torch.device(device)
        self._device = device
        return self

    def boost_position(self, position: int, boost: float) -> None:
        """
        Boost salience for a specific position.

        Args:
            position: Token position to boost
            boost: Boost factor (>1 increases salience)
        """
        self._position_boosts[position] = boost

    def boost_token_positions(
        self,
        input_ids: torch.Tensor,
        token_id: int,
        boost: float,
    ) -> None:
        """
        Boost salience for all positions of a specific token.

        Args:
            input_ids: [B, T] input token IDs
            token_id: Token ID to boost
            boost: Boost factor
        """
        self._token_boosts[token_id] = boost

    def compute_salience(
        self,
        input_ids: torch.Tensor,
        hidden_states: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        """
        Compute binding salience for the sequence.

        Args:
            input_ids: [B, T] input token IDs
            hidden_states: Optional [B, T, D] hidden states

        Returns:
            salience: [B, T] salience scores
        """
        B, T = input_ids.shape

        # Start with default salience
        salience = torch.ones(B, T, device=self._device) * self.default_boost

        # Apply position boosts
        for pos, boost in self._position_boosts.items():
            if pos < T:
                salience[:, pos] *= boost

        # Apply token-based boosts
        for token_id, boost in self._token_boosts.items():
            mask = (input_ids == token_id)
            salience = torch.where(mask, salience * boost, salience)

        return salience

    def clear_boosts(self) -> None:
        """Clear all boost settings."""
        self._position_boosts = {}
        self._token_boosts = {}


class BindingCacheInferenceEngine:
    """
    Inference engine for BindingCacheTransformer (V10.0).

    Provides full inference capabilities for the protected phase + Top-K
    query architecture, including:
    - Proposal mode metrics and control
    - Intent phase injection
    - Binding salience control
    - Phase health monitoring
    - Cache instrumentation

    Example:
        engine = BindingCacheInferenceEngine(model)
        engine.to('cuda')

        # Generate with default settings
        output, meta = engine.generate(input_ids, max_new_tokens=100)

        # Access proposal mode metrics
        print(engine.get_proposal_metrics())

        # Adjust confidence threshold
        engine.set_confidence_threshold(0.8)

        # Generate with custom intent
        output, meta = engine.generate(
            input_ids,
            intent_phase=custom_intent,
        )
    """

    def __init__(
        self,
        model: nn.Module,
        config: Optional[BindingCacheInferenceConfig] = None,
    ):
        """
        Initialize Binding Cache inference engine.

        Args:
            model: BindingCacheTransformer model
            config: Engine configuration
        """
        self.model = model
        self.config = config or BindingCacheInferenceConfig()

        # Infer model parameters
        if hasattr(model, 'embed_dim'):
            self.config.embed_dim = model.embed_dim
        if hasattr(model, 'num_heads'):
            self.config.num_heads = model.num_heads
        if hasattr(model, 'top_k'):
            self.config.top_k = model.top_k

        # Initialize sub-modules
        self.intent_module = IntentPhaseInferenceModule(
            num_heads=self.config.num_heads,
            head_dim=self.config.embed_dim // self.config.num_heads,
        )
        self.salience_controller = BindingSalienceController(
            default_boost=self.config.default_salience_boost,
        )

        # Metrics tracking
        self._proposal_metrics_history: List[Dict[str, float]] = []
        self._phase_health_history: List[Dict[str, float]] = []
        self._cache_metrics_history: List[Dict[str, float]] = []

        # Device tracking
        self._device = torch.device('cpu')

    def to(self, device: Union[str, torch.device]) -> 'BindingCacheInferenceEngine':
        """
        Move engine to device.

        Args:
            device: Target device

        Returns:
            self for chaining
        """
        if isinstance(device, str):
            device = torch.device(device)

        self._device = device
        self.intent_module.to(device)
        self.salience_controller.to(device)

        return self

    @property
    def device(self) -> torch.device:
        """Get current device."""
        return self._device

    def set_confidence_threshold(self, threshold: float) -> None:
        """
        Set confidence threshold for proposal mode.

        When confidence exceeds threshold, Quad query is skipped.

        Args:
            threshold: Confidence threshold [0, 1]
        """
        self.config.confidence_threshold = threshold

        # Propagate to model if it supports it
        if hasattr(self.model, 'confidence_threshold'):
            self.model.confidence_threshold = threshold

        # Or propagate to blocks
        if hasattr(self.model, 'blocks'):
            for block in self.model.blocks:
                if hasattr(block, 'confidence_threshold'):
                    block.confidence_threshold = threshold

    def set_enable_slots_read(self, enabled: bool) -> None:
        """
        Enable/disable Quad retrieval (slots read).

        When disabled, only local attention and phase accumulation are used.
        This separates the read path from the write path (D.2).

        Args:
            enabled: Whether to enable slots read
        """
        if hasattr(self.model, 'blocks'):
            for block in self.model.blocks:
                if hasattr(block, 'enable_slots_read'):
                    block.enable_slots_read = enabled

    def get_proposal_metrics(self) -> Dict[str, float]:
        """
        Get proposal mode metrics from last forward pass.

        Returns:
            metrics: Dict with confidence_mean, skip_rate, per_layer metrics
        """
        if hasattr(self.model, 'get_proposal_metrics'):
            return self.model.get_proposal_metrics()
        return {
            'confidence_mean': 0.0,
            'skip_rate': 0.0,
            'per_layer_confidence': [],
            'per_layer_skip_rate': [],
        }

    def get_phase_health(self) -> Dict[str, Any]:
        """
        Get Phase health metrics.

        Returns:
            health: Dict with r_k_mean, r_k_per_layer
        """
        if hasattr(self.model, 'get_phase_health'):
            return self.model.get_phase_health()
        return {'r_k_mean': 0.0, 'r_k_per_layer': []}

    def get_cache_instrumentation(self) -> Dict[str, float]:
        """
        Get cache instrumentation metrics.

        Returns:
            metrics: Dict with cache_hit_rate, mean_alpha, cosine metrics
        """
        if hasattr(self.model, 'get_instrumentation'):
            return self.model.get_instrumentation()
        return {
            'cache_hit_rate': 0.0,
            'mean_alpha': 0.0,
            'cache_key_cosine_mean': 0.0,
            'cache_key_cosine_max': 0.0,
        }

    def set_ablation(self, mode: str, seed: Optional[int] = None) -> None:
        """
        Set ablation mode for diagnostic testing.

        Args:
            mode: 'none', 'shuffle', 'zero', or 'random'
            seed: Random seed for reproducibility
        """
        if hasattr(self.model, 'set_ablation'):
            self.model.set_ablation(mode, seed)

    def set_rotation(self, angle_radians: float) -> None:
        """
        Set phase rotation for testing.

        Args:
            angle_radians: Rotation angle in radians
        """
        if hasattr(self.model, 'set_rotation'):
            self.model.set_rotation(angle_radians)

    def clear_rotation(self) -> None:
        """Clear phase rotation."""
        if hasattr(self.model, 'clear_rotation'):
            self.model.clear_rotation()

    def set_enforce_control_contract(self, enabled: bool) -> None:
        """
        Enable/disable control contract enforcement (V10.6.6).

        When enabled, violations of control signal shapes raise exceptions.

        Args:
            enabled: Whether to enforce contracts
        """
        if hasattr(self.model, 'set_enforce_control_contract'):
            self.model.set_enforce_control_contract(enabled)

    @torch.no_grad()
    def generate(
        self,
        input_ids: torch.Tensor,
        max_new_tokens: int = 100,
        temperature: float = 1.0,
        top_p: float = 0.9,
        top_k: int = 50,
        intent_phase: Optional[torch.Tensor] = None,
        binding_salience: Optional[torch.Tensor] = None,
        compute_intent_from_context: bool = False,
        enable_slots_read: bool = True,
        track_metrics: bool = True,
        on_token_callback: Optional[callable] = None,
        **kwargs,
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Generate with Binding Cache model.

        Args:
            input_ids: [B, T] input token IDs
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling threshold
            top_k: Top-k sampling
            intent_phase: Optional [B, H] intent phase to inject
            binding_salience: Optional [B, T] salience to use
            compute_intent_from_context: Compute intent from hidden states
            enable_slots_read: Enable Quad retrieval
            track_metrics: Whether to track proposal/cache metrics
            on_token_callback: Optional callback(token_id, step_meta)
            **kwargs: Additional model arguments

        Returns:
            generated_ids: [B, T+N] generated sequence
            meta: Generation metadata including metrics
        """
        input_ids = input_ids.to(self._device)
        generated = input_ids.clone()
        B = input_ids.size(0)

        meta = {
            'tokens_generated': 0,
            'proposal_metrics': [],
            'phase_health': [],
            'cache_metrics': [],
            'intent_phases': [],
        }

        # Handle intent phase
        current_intent = intent_phase
        if current_intent is not None:
            current_intent = current_intent.to(self._device)

        # Handle binding salience
        current_salience = binding_salience
        if current_salience is None and self.config.enable_salience_control:
            current_salience = self.salience_controller.compute_salience(
                generated, None
            )

        # Generation loop
        for step in range(max_new_tokens):
            # Forward pass
            outputs = self.model(
                generated,
                intent_phase=current_intent,
                binding_salience=current_salience,
                enable_slots_read=enable_slots_read,
                **kwargs,
            )

            # Extract logits
            if isinstance(outputs, dict):
                logits = outputs.get('logits', outputs.get('output'))
                hidden_states = outputs.get('hidden_states')
            elif isinstance(outputs, tuple):
                logits = outputs[0]
                hidden_states = outputs[1] if len(outputs) > 1 else None
            else:
                logits = outputs
                hidden_states = None

            next_logits = logits[:, -1, :] / max(temperature, 1e-8)

            # Top-k filtering
            if top_k > 0:
                indices_to_remove = next_logits < torch.topk(next_logits, top_k)[0][..., -1, None]
                next_logits[indices_to_remove] = float('-inf')

            # Top-p filtering
            if top_p < 1.0:
                sorted_logits, sorted_indices = torch.sort(next_logits, descending=True)
                cumulative_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)
                sorted_indices_to_remove = cumulative_probs > top_p
                sorted_indices_to_remove[:, 1:] = sorted_indices_to_remove[:, :-1].clone()
                sorted_indices_to_remove[:, 0] = False
                indices_to_remove = sorted_indices_to_remove.scatter(
                    -1, sorted_indices, sorted_indices_to_remove
                )
                next_logits[indices_to_remove] = float('-inf')

            # Sample
            probs = F.softmax(next_logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)

            # Append token
            generated = torch.cat([generated, next_token], dim=-1)
            meta['tokens_generated'] += 1

            # Track metrics
            if track_metrics:
                proposal_metrics = self.get_proposal_metrics()
                phase_health = self.get_phase_health()
                cache_metrics = self.get_cache_instrumentation()

                meta['proposal_metrics'].append(proposal_metrics)
                meta['phase_health'].append(phase_health)
                meta['cache_metrics'].append(cache_metrics)

            # Compute intent from context if enabled
            if compute_intent_from_context and hidden_states is not None:
                h = hidden_states[-1] if isinstance(hidden_states, list) else hidden_states
                current_intent = self.intent_module.compute_intent_from_hidden(h)
                meta['intent_phases'].append(current_intent.clone())

            # Update salience for new sequence length
            if self.config.enable_salience_control:
                current_salience = self.salience_controller.compute_salience(
                    generated, hidden_states
                )

            # Callback
            if on_token_callback is not None:
                step_meta = {
                    'step': step,
                    'token_id': next_token.item(),
                    'prob': probs.gather(-1, next_token).item(),
                }
                if track_metrics:
                    step_meta['proposal_metrics'] = proposal_metrics
                    step_meta['phase_health'] = phase_health
                on_token_callback(next_token.item(), step_meta)

            # Check for EOS (assuming 2)
            if next_token.item() == 2:
                break

        # Aggregate final metrics
        if track_metrics and meta['proposal_metrics']:
            meta['avg_confidence'] = sum(
                m.get('confidence_mean', 0) for m in meta['proposal_metrics']
            ) / len(meta['proposal_metrics'])
            meta['avg_skip_rate'] = sum(
                m.get('skip_rate', 0) for m in meta['proposal_metrics']
            ) / len(meta['proposal_metrics'])
            meta['final_phase_health'] = meta['phase_health'][-1] if meta['phase_health'] else {}
            meta['final_cache_metrics'] = meta['cache_metrics'][-1] if meta['cache_metrics'] else {}

        return generated, meta

    def get_status_line(self) -> str:
        """Get status line for monitoring."""
        parts = ["BindingCache"]

        # Proposal mode status
        metrics = self.get_proposal_metrics()
        if metrics:
            parts.append(f"Conf:{metrics.get('confidence_mean', 0):.2f}")
            parts.append(f"Skip:{metrics.get('skip_rate', 0):.1%}")

        # Phase health
        health = self.get_phase_health()
        if health:
            parts.append(f"Phase:{health.get('r_k_mean', 0):.2f}")

        # Cache metrics
        cache = self.get_cache_instrumentation()
        if cache:
            parts.append(f"Hit:{cache.get('cache_hit_rate', 0):.1%}")

        return " | ".join(parts)

    def clear_state(self) -> None:
        """Clear all accumulated state."""
        self.intent_module.clear()
        self.salience_controller.clear_boosts()
        self._proposal_metrics_history = []
        self._phase_health_history = []
        self._cache_metrics_history = []

    def get_state(self) -> Dict[str, Any]:
        """Get serializable state."""
        return {
            'config': self.config,
            'current_intent': (
                self.intent_module.get_current_intent().cpu()
                if self.intent_module.get_current_intent() is not None else None
            ),
            'proposal_metrics_history': self._proposal_metrics_history,
            'phase_health_history': self._phase_health_history,
            'cache_metrics_history': self._cache_metrics_history,
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        """Load state from dict."""
        if state.get('current_intent') is not None:
            self.intent_module.inject_external_intent(
                state['current_intent'].to(self._device)
            )
        self._proposal_metrics_history = state.get('proposal_metrics_history', [])
        self._phase_health_history = state.get('phase_health_history', [])
        self._cache_metrics_history = state.get('cache_metrics_history', [])
