#!/usr/bin/env python3
"""
Ontological Binding Cache Inference Engine
============================================

Inference-time engine for OntologicalBindingCacheTransformer (V10.0 AGI Architecture).

This engine implements the two-pass architecture:
- Pass 1: Get hidden states WITHOUT intent phase
- Pass 2: Compute state delta → intent phase → full forward WITH intent

Provides:
- Two-pass generation loop with Sovereign State tracking
- 32D Sovereign State monitoring via SovereignStateMonitor
- Intent phase projection access
- OntologicalBindingAnnotator control
- External delta_S injection
- State persistence across conversations

Training Reference: symbolu/phase_transformer.py:3740-4075 (OntologicalBindingCacheTransformer)

Author: Sovereign-1 Training Initiative
Date: January 2026
Phase: 5c - V10.0 Ontological Binding Cache Inference
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
import math
import warnings

from .binding_cache_inference import (
    BindingCacheInferenceEngine,
    BindingCacheInferenceConfig,
    IntentPhaseInferenceModule,
    BindingSalienceController,
)
from .sovereign_state_monitor import (
    SovereignStateMonitor,
    SovereignStateMetrics,
    SOVEREIGN_STATE_DIM,
    BHAVA_SLICE,
    KOSHA_SLICE,
    VRITTI_SLICE,
    GUNA_SLICE,
)


@dataclass
class OntologicalBindingCacheInferenceConfig(BindingCacheInferenceConfig):
    """Configuration for Ontological Binding Cache inference."""
    # Sovereign State settings
    state_dim: int = SOVEREIGN_STATE_DIM  # 32D
    track_state_trajectory: bool = True
    state_persistence: bool = True  # Persist state across generations

    # Two-pass settings
    enable_two_pass: bool = True
    use_external_delta: bool = False

    # Binding annotator settings
    use_csr_annotation: bool = True
    use_kosha_annotation: bool = True
    use_srk_annotation: bool = True

    # Warning thresholds
    error_risk_threshold: float = 0.5
    turbulence_threshold: float = 0.8


class OntologicalBindingCacheInferenceEngine:
    """
    Inference engine for OntologicalBindingCacheTransformer (V10.0 AGI Architecture).

    Implements the two-pass architecture where:
    - System 2 (slow, deliberate) computes Sovereign State delta
    - Delta is converted to intent phase via IntentPhaseProjector
    - System 1 (fast, binding cache) uses intent for guided completion

    This engine provides full inference capabilities including:
    - Two-pass generation with state tracking
    - 32D Sovereign State monitoring (Bhava, Kosha, Vritti, Guna)
    - Reliability assessment via Vritti analysis
    - Depth tracking via Kosha analysis
    - CSR/Kosha/SRK binding salience control

    Example:
        engine = OntologicalBindingCacheInferenceEngine(model)
        engine.to('cuda')

        # Generate with two-pass ontological reasoning
        output, meta = engine.generate_with_ontology(
            input_ids,
            max_new_tokens=100,
        )

        # Access state trajectory
        print(engine.get_state_trajectory_summary())

        # Check reliability
        if meta['final_metrics'].error_risk > 0.5:
            print("Warning: High hallucination risk detected!")

        # Get depth progression
        print(engine.state_monitor.get_depth_progression())
    """

    def __init__(
        self,
        model: nn.Module,
        config: Optional[OntologicalBindingCacheInferenceConfig] = None,
    ):
        """
        Initialize Ontological Binding Cache inference engine.

        Args:
            model: OntologicalBindingCacheTransformer model
            config: Engine configuration
        """
        self.model = model
        self.config = config or OntologicalBindingCacheInferenceConfig()

        # Infer model parameters
        if hasattr(model, 'embed_dim'):
            self.config.embed_dim = model.embed_dim
        if hasattr(model, 'num_heads'):
            self.config.num_heads = model.num_heads
        if hasattr(model, 'state_dim'):
            self.config.state_dim = model.state_dim
        if hasattr(model, 'binding_cache') and hasattr(model.binding_cache, 'top_k'):
            self.config.top_k = model.binding_cache.top_k

        # Initialize Sovereign State monitor
        self.state_monitor = SovereignStateMonitor(
            warn_thresholds={
                'error_risk': self.config.error_risk_threshold,
                'turbulence': self.config.turbulence_threshold,
                'low_lucidity': 0.2,
                'bhava_entropy': 2.0,
            }
        )

        # Initialize binding cache components
        self.intent_module = IntentPhaseInferenceModule(
            num_heads=self.config.num_heads,
            head_dim=self.config.embed_dim // self.config.num_heads,
        )
        self.salience_controller = BindingSalienceController(
            default_boost=self.config.default_salience_boost,
        )

        # State tracking
        self._state_history: List[torch.Tensor] = []
        self._delta_history: List[torch.Tensor] = []
        self._intent_phase_history: List[torch.Tensor] = []
        self._prev_state: Optional[torch.Tensor] = None

        # External delta injection
        self._external_delta: Optional[torch.Tensor] = None

        # Device tracking
        self._device = torch.device('cpu')

    def to(self, device: Union[str, torch.device]) -> 'OntologicalBindingCacheInferenceEngine':
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
        self.state_monitor.to(device)
        self.intent_module.to(device)
        self.salience_controller.to(device)

        if self._prev_state is not None:
            self._prev_state = self._prev_state.to(device)
        if self._external_delta is not None:
            self._external_delta = self._external_delta.to(device)

        return self

    @property
    def device(self) -> torch.device:
        """Get current device."""
        return self._device

    def set_external_delta(self, delta_S: torch.Tensor) -> None:
        """
        Set external state delta for injection.

        Useful for:
        - Multi-turn conversation context
        - User instruction encoding
        - Cross-document reasoning

        Args:
            delta_S: [B, 32] state delta to inject
        """
        self._external_delta = delta_S.to(self._device)

    def clear_external_delta(self) -> None:
        """Clear external delta."""
        self._external_delta = None

    def set_annotator_config(
        self,
        use_csr: Optional[bool] = None,
        use_kosha: Optional[bool] = None,
        use_srk: Optional[bool] = None,
    ) -> None:
        """
        Configure binding annotator components.

        Args:
            use_csr: Enable CSR phonological grounding
            use_kosha: Enable depth-based selection
            use_srk: Enable Sovereignty signals
        """
        if use_csr is not None:
            self.config.use_csr_annotation = use_csr
        if use_kosha is not None:
            self.config.use_kosha_annotation = use_kosha
        if use_srk is not None:
            self.config.use_srk_annotation = use_srk

        # Propagate to model if possible
        if hasattr(self.model, 'binding_annotator'):
            annotator = self.model.binding_annotator
            if use_csr is not None and hasattr(annotator, 'use_csr'):
                annotator.use_csr = use_csr
            if use_kosha is not None and hasattr(annotator, 'use_kosha'):
                annotator.use_kosha = use_kosha
            if use_srk is not None and hasattr(annotator, 'use_srk'):
                annotator.use_srk = use_srk

    def get_current_state(self) -> Optional[torch.Tensor]:
        """Get current Sovereign State."""
        return self._prev_state

    def get_state_metrics(self) -> Optional[SovereignStateMetrics]:
        """Get metrics for current state."""
        if self._prev_state is None:
            return None
        return self.state_monitor.analyze_state(self._prev_state)

    def get_state_trajectory_summary(self) -> Dict[str, Any]:
        """Get summary of state trajectory."""
        if not self._state_history:
            return {'empty': True}

        metrics_history = self.state_monitor.get_state_trajectory()

        return {
            'num_states': len(self._state_history),
            'depth_progression': self.state_monitor.get_depth_progression(),
            'bhava_sequence': self.state_monitor.get_bhava_sequence(),
            'reliability_trend': self.state_monitor.get_reliability_trend(),
            'average_metrics': self.state_monitor.get_average_metrics(),
            'warnings': len(self.state_monitor.get_warnings()),
        }

    @torch.no_grad()
    def generate_with_ontology(
        self,
        input_ids: torch.Tensor,
        max_new_tokens: int = 100,
        temperature: float = 1.0,
        top_p: float = 0.9,
        top_k: int = 50,
        reset_state: bool = False,
        csr_mask: Optional[torch.Tensor] = None,
        track_trajectory: bool = True,
        on_token_callback: Optional[callable] = None,
        **kwargs,
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Generate with two-pass ontological reasoning.

        The two-pass architecture:
        1. Pass 1: Forward without intent → get hidden states
        2. Compute state delta: hidden → SovereignState[32] → ΔS
        3. Convert ΔS → intent phase: ΔS[32] → θ[H]
        4. Compute binding salience from annotator
        5. Pass 2: Forward WITH intent phase AND binding salience

        Args:
            input_ids: [B, T] input token IDs
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling threshold
            top_k: Top-k sampling
            reset_state: Reset Sovereign State (start fresh)
            csr_mask: Optional [B, T] CSR content word mask
            track_trajectory: Track state evolution
            on_token_callback: Optional callback(token_id, step_meta)
            **kwargs: Additional model arguments

        Returns:
            generated_ids: [B, T+N] generated sequence
            meta: Generation metadata including state trajectory
        """
        input_ids = input_ids.to(self._device)
        generated = input_ids.clone()
        B = input_ids.size(0)

        # Reset state if requested
        if reset_state:
            self._prev_state = None
            self.state_monitor.clear()
            self._state_history = []
            self._delta_history = []
            self._intent_phase_history = []

        meta = {
            'tokens_generated': 0,
            'state_trajectory': [],
            'delta_trajectory': [],
            'intent_phase_trajectory': [],
            'metrics_trajectory': [],
            'warnings': [],
            'final_state': None,
            'final_metrics': None,
        }

        # Generation loop with two-pass per token
        for step in range(max_new_tokens):
            # Determine if we should reset state for this step
            step_reset = (step == 0 and reset_state)

            # Use model's two-pass forward
            if self.config.enable_two_pass and hasattr(self.model, 'forward'):
                # Prepare external delta if available
                external_delta = self._external_delta if self.config.use_external_delta else None

                # Full two-pass forward
                outputs = self.model(
                    generated,
                    reset_state=step_reset,
                    external_delta_S=external_delta,
                    csr_mask=csr_mask,
                    **kwargs,
                )

                # Extract outputs from dict
                if isinstance(outputs, dict):
                    logits = outputs.get('logits', outputs.get('output'))
                    current_state = outputs.get('state')
                    delta_S = outputs.get('delta_S')
                    intent_phase = outputs.get('intent_phase')
                    binding_salience = outputs.get('binding_salience')
                else:
                    logits = outputs
                    current_state = None
                    delta_S = None
                    intent_phase = None
                    binding_salience = None
            else:
                # Fallback: simple forward without two-pass
                outputs = self.model(generated, **kwargs)
                if isinstance(outputs, dict):
                    logits = outputs.get('logits', outputs.get('output'))
                else:
                    logits = outputs
                current_state = None
                delta_S = None
                intent_phase = None
                binding_salience = None

            next_logits = logits[:, -1, :] / max(temperature, 1e-8)

            # Track state if available
            if track_trajectory and current_state is not None:
                self._state_history.append(current_state.clone())
                meta['state_trajectory'].append(current_state.clone())

                # Analyze state
                metrics = self.state_monitor.analyze_state(current_state)
                meta['metrics_trajectory'].append(metrics)

                # Check for high error risk
                if metrics.error_risk > self.config.error_risk_threshold:
                    warning = {
                        'step': step,
                        'type': 'high_error_risk',
                        'value': metrics.error_risk,
                    }
                    meta['warnings'].append(warning)

            if track_trajectory and delta_S is not None:
                self._delta_history.append(delta_S.clone())
                meta['delta_trajectory'].append(delta_S.clone())

            if track_trajectory and intent_phase is not None:
                self._intent_phase_history.append(intent_phase.clone())
                meta['intent_phase_trajectory'].append(intent_phase.clone())

            # Update previous state for continuity
            if current_state is not None:
                self._prev_state = current_state

            # Top-k filtering
            if top_k > 0:
                top_k_vals = torch.topk(next_logits, min(top_k, next_logits.size(-1)))[0]
                threshold = top_k_vals[:, -1].unsqueeze(-1)
                next_logits = torch.where(
                    next_logits < threshold,
                    torch.full_like(next_logits, float('-inf')),
                    next_logits,
                )

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

            # Sample token
            probs = F.softmax(next_logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)
            next_token_prob = probs.gather(-1, next_token).item()

            # Append token
            generated = torch.cat([generated, next_token], dim=-1)
            meta['tokens_generated'] += 1

            # Update CSR mask if provided (extend for new token)
            if csr_mask is not None:
                # Assume new token is not a CSR content word by default
                new_mask = torch.zeros(B, 1, device=self._device)
                csr_mask = torch.cat([csr_mask, new_mask], dim=1)

            # Callback
            if on_token_callback is not None:
                step_meta = {
                    'step': step,
                    'token_id': next_token.item(),
                    'prob': next_token_prob,
                    'state': current_state,
                    'delta_S': delta_S,
                    'intent_phase': intent_phase,
                    'metrics': meta['metrics_trajectory'][-1] if meta['metrics_trajectory'] else None,
                }
                on_token_callback(next_token.item(), step_meta)

            # Check for EOS
            if next_token.item() == 2:  # Assuming EOS = 2
                break

        # Final state and metrics
        meta['final_state'] = self._prev_state
        if self._prev_state is not None:
            meta['final_metrics'] = self.state_monitor.analyze_state(self._prev_state)

        # Aggregate warnings
        meta['warnings'].extend(self.state_monitor.get_warnings())

        # Summary metrics
        if meta['metrics_trajectory']:
            meta['avg_reliability'] = sum(
                m.reliability_score for m in meta['metrics_trajectory']
            ) / len(meta['metrics_trajectory'])
            meta['avg_coherence'] = sum(
                m.coherence_estimate for m in meta['metrics_trajectory']
            ) / len(meta['metrics_trajectory'])

        return generated, meta

    def get_status_line(self) -> str:
        """Get status line for monitoring."""
        parts = ["OntologicalBC"]

        # State monitor status
        if self._prev_state is not None:
            metrics = self.state_monitor.analyze_state(self._prev_state)
            parts.append(f"Bhava:{metrics.dominant_bhava}")
            parts.append(f"Depth:{metrics.depth_level.name[:4]}")
            parts.append(f"Rel:{metrics.reliability_score:.2f}")
        else:
            parts.append("State:none")

        # Trajectory info
        if self._state_history:
            parts.append(f"Traj:{len(self._state_history)}")

        return " | ".join(parts)

    def clear_state(self) -> None:
        """Clear all accumulated state."""
        self._prev_state = None
        self._external_delta = None
        self._state_history = []
        self._delta_history = []
        self._intent_phase_history = []
        self.state_monitor.clear()
        self.intent_module.clear()
        self.salience_controller.clear_boosts()

    def get_state(self) -> Dict[str, Any]:
        """Get serializable state for persistence."""
        return {
            'config': self.config,
            'prev_state': self._prev_state.cpu() if self._prev_state is not None else None,
            'external_delta': self._external_delta.cpu() if self._external_delta is not None else None,
            'state_history_len': len(self._state_history),
            'monitor_state': self.state_monitor.get_state(),
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        """Load state from dict."""
        if state.get('prev_state') is not None:
            self._prev_state = state['prev_state'].to(self._device)
        if state.get('external_delta') is not None:
            self._external_delta = state['external_delta'].to(self._device)
        if state.get('monitor_state'):
            self.state_monitor.load_state(state['monitor_state'])

    def save_state_to_file(self, path: str) -> None:
        """Save state to file for session persistence."""
        state = self.get_state()
        torch.save(state, path)

    def load_state_from_file(self, path: str) -> None:
        """Load state from file."""
        state = torch.load(path, map_location=self._device)
        self.load_state(state)
