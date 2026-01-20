#!/usr/bin/env python3
"""
Inference Manager
==================

Orchestrates all inference components for unified generation.

Provides a single interface that coordinates:
- EvolutionaryInferenceEngine (karma/resonance)
- CSRInferenceGuard (safety/entropy)
- InferenceMetacognition (quality monitoring)
- InferenceGunas (cognitive state)
- SovereignInferenceScorer (quality scoring)

Author: Sovereign-1 Training Initiative
Date: January 2026
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from pathlib import Path
from enum import Enum

from .evolutionary_inference import EvolutionaryInferenceEngine, EvolutionaryConfig
from .csr_inference import CSRInferenceGuard, CSRGuardConfig
from .metacognitive_monitor import InferenceMetacognition, MetacognitiveConfig, GenerationRecommendation
from .guna_inference import InferenceGunas, GunaConfig
from .sovereign_scorer import SovereignInferenceScorer, SovereignScorerConfig
from .layer_config import LayerInferenceConfig, ArchitectureMode
from .binding_cache_inference import BindingCacheInferenceEngine, BindingCacheInferenceConfig
from .ontological_binding_cache_inference import (
    OntologicalBindingCacheInferenceEngine,
    OntologicalBindingCacheInferenceConfig,
)
from .sovereign_state_monitor import SovereignStateMonitor


class InferenceMode(Enum):
    """Inference mode presets."""
    FAST = "fast"  # Minimal overhead, basic generation
    STANDARD = "standard"  # Karma + basic monitoring
    FULL = "full"  # All features enabled
    SAFE = "safe"  # Full + strict CSR enforcement
    SOVEREIGN = "sovereign"  # Full metabolic loop with 3-way coherence


@dataclass
class InferenceManagerConfig:
    """Configuration for inference manager."""
    mode: InferenceMode = InferenceMode.STANDARD
    enable_karma: bool = True
    enable_csr_guard: bool = True
    enable_metacognition: bool = True
    enable_gunas: bool = True
    enable_scoring: bool = True

    # Generation defaults
    default_temperature: float = 1.0
    default_top_p: float = 0.9
    default_top_k: int = 50
    max_new_tokens: int = 128

    # Safety
    abort_on_low_coherence: bool = False
    auto_adjust_params: bool = True

    # V10.0 Architecture settings (Phase 5)
    architecture_mode: Optional[ArchitectureMode] = None  # Auto-detected from model
    enable_binding_cache_engine: bool = True  # Use specialized engine for V10.0
    enable_sovereign_state_monitor: bool = True  # Track 32D state
    track_state_trajectory: bool = True  # Track state evolution


class InferenceManager:
    """
    Unified inference orchestrator for Sovereign-1 models.

    Coordinates all inference components and provides a simple interface
    for generation with full cognitive capabilities.

    Example:
        # Basic usage
        manager = InferenceManager.from_checkpoint(
            checkpoint_path,
            model_class=HybridPhaseTransformer,
            device='cuda',
        )

        output = manager.generate(
            "The meaning of life is",
            max_new_tokens=100,
        )
        print(output['text'])
        print(manager.get_status())

        # Advanced usage with callbacks
        def on_token(token, meta):
            print(f"Generated: {token}, Coherence: {meta['coherence']:.2f}")

        output = manager.generate(
            input_ids,
            on_token_callback=on_token,
        )
    """

    def __init__(
        self,
        model: nn.Module,
        tokenizer: Any,
        config: Optional[InferenceManagerConfig] = None,
        evolutionary_engine: Optional[EvolutionaryInferenceEngine] = None,
        csr_guard: Optional[CSRInferenceGuard] = None,
        layer_config: Optional[LayerInferenceConfig] = None,
        binding_cache_engine: Optional[BindingCacheInferenceEngine] = None,
        ontological_engine: Optional[OntologicalBindingCacheInferenceEngine] = None,
        device: Union[str, torch.device] = 'cpu',
    ):
        """
        Initialize inference manager.

        Args:
            model: The transformer model
            tokenizer: Tokenizer for text encoding/decoding
            config: Manager configuration
            evolutionary_engine: Pre-initialized evolutionary engine
            csr_guard: Pre-initialized CSR guard
            layer_config: Layer configuration
            binding_cache_engine: Pre-initialized BindingCache engine (V10.0)
            ontological_engine: Pre-initialized OntologicalBindingCache engine (V10.0)
            device: Target device
        """
        self.config = config or InferenceManagerConfig()
        self.model = model
        self.tokenizer = tokenizer
        self._device = torch.device(device) if isinstance(device, str) else device

        # Apply mode presets
        self._apply_mode_preset()

        # Auto-detect architecture mode from model type
        self._detect_architecture_mode()

        # Initialize components based on config
        self.evolutionary_engine = evolutionary_engine
        self.csr_guard = csr_guard
        self.layer_config = layer_config or LayerInferenceConfig()

        # V10.0 Binding Cache engines (Phase 5)
        self.binding_cache_engine = binding_cache_engine
        self.ontological_engine = ontological_engine
        self.state_monitor: Optional[SovereignStateMonitor] = None

        # Initialize V10.0 engines if appropriate architecture
        self._initialize_v10_engines()

        # Create remaining components
        self.metacognition = InferenceMetacognition() if self.config.enable_metacognition else None
        self.gunas = InferenceGunas() if self.config.enable_gunas else None
        self.scorer = SovereignInferenceScorer() if self.config.enable_scoring else None

        # Generation state
        self._generation_count: int = 0
        self._total_tokens_generated: int = 0

    def _detect_architecture_mode(self) -> None:
        """Auto-detect architecture mode from model class name."""
        if self.config.architecture_mode is not None:
            return

        model_class_name = self.model.__class__.__name__

        if 'OntologicalBindingCache' in model_class_name:
            self.config.architecture_mode = ArchitectureMode.ONTOLOGICAL_BINDING_CACHE
        elif 'BindingCache' in model_class_name:
            self.config.architecture_mode = ArchitectureMode.BINDING_CACHE
        elif 'Ontological' in model_class_name or 'Hybrid' in model_class_name:
            self.config.architecture_mode = ArchitectureMode.SPLIT_6_6
        else:
            self.config.architecture_mode = ArchitectureMode.SPLIT_12_0

    def _initialize_v10_engines(self) -> None:
        """Initialize V10.0 inference engines based on architecture mode."""
        if not self.config.enable_binding_cache_engine:
            return

        arch = self.config.architecture_mode

        if arch == ArchitectureMode.ONTOLOGICAL_BINDING_CACHE:
            if self.ontological_engine is None:
                self.ontological_engine = OntologicalBindingCacheInferenceEngine(
                    self.model,
                    config=OntologicalBindingCacheInferenceConfig(
                        track_state_trajectory=self.config.track_state_trajectory,
                    ),
                )
                self.ontological_engine.to(self._device)

            # Use the engine's state monitor
            self.state_monitor = self.ontological_engine.state_monitor

        elif arch == ArchitectureMode.BINDING_CACHE:
            if self.binding_cache_engine is None:
                self.binding_cache_engine = BindingCacheInferenceEngine(
                    self.model,
                    config=BindingCacheInferenceConfig(),
                )
                self.binding_cache_engine.to(self._device)

        # Create state monitor for tracking even without ontological engine
        if (self.config.enable_sovereign_state_monitor and
            self.state_monitor is None):
            self.state_monitor = SovereignStateMonitor()
            self.state_monitor.to(self._device)

    def _apply_mode_preset(self) -> None:
        """Apply mode-specific defaults."""
        if self.config.mode == InferenceMode.FAST:
            self.config.enable_karma = False
            self.config.enable_csr_guard = False
            self.config.enable_metacognition = False
            self.config.enable_gunas = False
            self.config.enable_scoring = False

        elif self.config.mode == InferenceMode.STANDARD:
            self.config.enable_karma = True
            self.config.enable_csr_guard = False
            self.config.enable_metacognition = True
            self.config.enable_gunas = False
            self.config.enable_scoring = False

        elif self.config.mode == InferenceMode.SAFE:
            self.config.enable_karma = True
            self.config.enable_csr_guard = True
            self.config.enable_metacognition = True
            self.config.enable_gunas = True
            self.config.enable_scoring = True
            self.config.abort_on_low_coherence = True

        elif self.config.mode == InferenceMode.SOVEREIGN:
            # Full metabolic loop with all cognitive components
            self.config.enable_karma = True
            self.config.enable_csr_guard = True
            self.config.enable_metacognition = True
            self.config.enable_gunas = True
            self.config.enable_scoring = True
            self.config.abort_on_low_coherence = True
            self.config.auto_adjust_params = True

    @classmethod
    def from_checkpoint(
        cls,
        checkpoint_path: Union[str, Path],
        model_class: type,
        tokenizer: Any,
        model_kwargs: Optional[Dict] = None,
        config: Optional[InferenceManagerConfig] = None,
        device: Union[str, torch.device] = 'cuda' if torch.cuda.is_available() else 'cpu',
    ) -> 'InferenceManager':
        """
        Create manager from checkpoint.

        Args:
            checkpoint_path: Path to checkpoint
            model_class: Model class to instantiate
            tokenizer: Tokenizer instance
            model_kwargs: Model constructor arguments
            config: Manager configuration
            device: Target device

        Returns:
            manager: Initialized inference manager
        """
        from .checkpoint_utils import InferenceCheckpointLoader

        loader = InferenceCheckpointLoader(checkpoint_path, device)

        # Load model
        model = loader.load_model(model_class, model_kwargs)

        # Get embed_dim
        embed_dim = getattr(model, 'embed_dim', 768)
        lm_head = getattr(model, 'lm_head', None)

        # Load components
        evolutionary_engine = loader.load_evolutionary_engine(model)
        csr_guard = loader.load_csr_guard(lm_head, embed_dim)
        layer_config = loader.load_layer_config()

        return cls(
            model=model,
            tokenizer=tokenizer,
            config=config,
            evolutionary_engine=evolutionary_engine,
            csr_guard=csr_guard,
            layer_config=layer_config,
            device=device,
        )

    def to(self, device: Union[str, torch.device]) -> 'InferenceManager':
        """
        Move manager to device.

        Args:
            device: Target device

        Returns:
            self for chaining
        """
        if isinstance(device, str):
            device = torch.device(device)

        self._device = device
        self.model = self.model.to(device)

        if self.evolutionary_engine is not None:
            self.evolutionary_engine.to(device)

        if self.csr_guard is not None:
            self.csr_guard.to(device)

        # V10.0 engines (Phase 5)
        if self.binding_cache_engine is not None:
            self.binding_cache_engine.to(device)

        if self.ontological_engine is not None:
            self.ontological_engine.to(device)

        if self.state_monitor is not None:
            self.state_monitor.to(device)

        return self

    @property
    def device(self) -> torch.device:
        """Get current device."""
        return self._device

    def generate(
        self,
        prompt: Union[str, torch.Tensor],
        max_new_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        inject_karma: bool = True,
        on_token_callback: Optional[callable] = None,
        return_hidden_states: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Generate text with full cognitive capabilities.

        Args:
            prompt: Text prompt or input_ids tensor
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling threshold
            top_k: Top-k sampling
            inject_karma: Whether to inject stored karma
            on_token_callback: Optional callback(token_id, meta) per token
            return_hidden_states: Whether to return hidden states
            **kwargs: Additional generation arguments

        Returns:
            result: Dict with:
                - text: Generated text
                - tokens: Generated token IDs
                - hidden_states: Optional hidden states
                - meta: Generation metadata
                - scores: Quality scores
        """
        # Apply defaults
        max_new_tokens = max_new_tokens or self.config.max_new_tokens
        temperature = temperature or self.config.default_temperature
        top_p = top_p or self.config.default_top_p
        top_k = top_k or self.config.default_top_k

        # Encode prompt if string
        if isinstance(prompt, str):
            input_ids = self.tokenizer.encode(prompt, return_tensors='pt')
        else:
            input_ids = prompt

        input_ids = input_ids.to(self._device)

        # Reset per-generation state
        if self.metacognition is not None:
            self.metacognition.reset()
        if self.gunas is not None:
            self.gunas.reset()

        # Generation loop
        generated_ids = input_ids.clone()
        hidden_states_list = []
        generation_meta = {
            'tokens_generated': 0,
            'aborted': False,
            'abort_reason': None,
        }

        # Inject karma at start if enabled
        karma_meta = {}
        if self.config.enable_karma and self.evolutionary_engine is not None and inject_karma:
            # Will be injected during forward pass
            karma_meta['karma_available'] = self.evolutionary_engine.karma_buffer is not None

        with torch.no_grad():
            for step in range(max_new_tokens):
                # Get current effective parameters
                effective_temp = temperature
                effective_top_p = top_p

                # Auto-adjust parameters based on monitoring
                if self.config.auto_adjust_params and self.metacognition is not None:
                    adjustments = self.metacognition.get_generation_adjustment()
                    effective_temp *= adjustments.get('temperature_multiplier', 1.0)
                    effective_top_p = max(
                        0.1,
                        min(1.0, effective_top_p + adjustments.get('top_p_adjustment', 0.0))
                    )

                # Guna-based adjustments
                if self.gunas is not None:
                    effective_temp = self.gunas.get_temperature_modifier(effective_temp)

                # Forward pass
                outputs = self.model(generated_ids, **kwargs)

                if isinstance(outputs, dict):
                    logits = outputs.get('logits', outputs.get('output'))
                    hidden = outputs.get('hidden_states')
                elif isinstance(outputs, tuple):
                    logits = outputs[0]
                    hidden = outputs[1] if len(outputs) > 1 else None
                else:
                    logits = outputs
                    hidden = None

                next_logits = logits[:, -1, :]

                # CSR safety check
                csr_info = {}
                if self.config.enable_csr_guard and self.csr_guard is not None:
                    if hidden is not None:
                        hidden_for_csr = hidden[-1] if isinstance(hidden, list) else hidden
                        if hidden_for_csr.dim() == 3:
                            hidden_for_csr = hidden_for_csr[:, -1, :]
                    else:
                        hidden_for_csr = torch.zeros(1, self.model.embed_dim, device=self._device)

                    next_logits, csr_info = self.csr_guard.check_and_gate(
                        hidden_for_csr,
                        next_logits,
                    )

                # Apply temperature
                next_logits = next_logits / max(effective_temp, 1e-8)

                # Top-k filtering
                if top_k > 0:
                    top_k_values = torch.topk(next_logits, top_k)[0]
                    threshold = top_k_values[:, -1].unsqueeze(-1)
                    next_logits = torch.where(
                        next_logits < threshold,
                        torch.full_like(next_logits, float('-inf')),
                        next_logits,
                    )

                # Top-p (nucleus) filtering
                if effective_top_p < 1.0:
                    sorted_logits, sorted_indices = torch.sort(next_logits, descending=True)
                    cumulative_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)
                    sorted_indices_to_remove = cumulative_probs > effective_top_p
                    sorted_indices_to_remove[:, 1:] = sorted_indices_to_remove[:, :-1].clone()
                    sorted_indices_to_remove[:, 0] = False
                    indices_to_remove = sorted_indices_to_remove.scatter(
                        -1, sorted_indices, sorted_indices_to_remove
                    )
                    next_logits[indices_to_remove] = float('-inf')

                # Sample
                probs = F.softmax(next_logits, dim=-1)
                next_token = torch.multinomial(probs, num_samples=1)
                next_token_prob = probs.gather(-1, next_token).item()

                # Append token
                generated_ids = torch.cat([generated_ids, next_token], dim=-1)
                generation_meta['tokens_generated'] += 1

                # Store hidden states if requested
                if return_hidden_states and hidden is not None:
                    hidden_states_list.append(hidden)

                # Update monitoring
                step_meta = {'step': step, 'token_id': next_token.item(), 'prob': next_token_prob}
                step_meta.update(csr_info)

                if self.metacognition is not None:
                    meta_result = self.metacognition.update(
                        next_logits,
                        hidden[-1] if hidden is not None and isinstance(hidden, list) else hidden,
                        next_token.item(),
                    )
                    step_meta.update(meta_result)

                    # Check for abort
                    if (self.config.abort_on_low_coherence and
                        meta_result['recommendation'] == GenerationRecommendation.ABORT):
                        generation_meta['aborted'] = True
                        generation_meta['abort_reason'] = 'low_coherence'
                        break

                if self.gunas is not None:
                    sattva, rajas, tamas = self.gunas.update(
                        next_token.item(),
                        next_token_prob,
                    )
                    step_meta['gunas'] = {'sattva': sattva, 'rajas': rajas, 'tamas': tamas}

                # Callback
                if on_token_callback is not None:
                    on_token_callback(next_token.item(), step_meta)

                # Check for EOS
                eos_token_id = getattr(self.tokenizer, 'eos_token_id', 2)
                if next_token.item() == eos_token_id:
                    break

        # Update karma after generation
        if self.config.enable_karma and self.evolutionary_engine is not None:
            # Extract final hidden for karma
            if hidden is not None:
                final_hidden = hidden[-1] if isinstance(hidden, list) else hidden
                if final_hidden.dim() == 3:
                    final_hidden = final_hidden.mean(dim=1)

                new_karma = self.evolutionary_engine.bridge.compute_seed(final_hidden)
                self.evolutionary_engine.karma_buffer = new_karma * self.evolutionary_engine.config.karma_decay
                self.evolutionary_engine.karma_age += 1

        # Compute quality scores
        scores = {}
        if self.scorer is not None:
            gunas_tuple = None
            if self.gunas is not None:
                gunas_tuple = (self.gunas.sattva, self.gunas.rajas, self.gunas.tamas)

            scores = self.scorer.score_sequence(
                hidden_states=hidden_states_list if hidden_states_list else None,
                generated_tokens=generated_ids[:, input_ids.size(1):],
                gunas=gunas_tuple,
            )

        # Decode output
        generated_token_ids = generated_ids[0, input_ids.size(1):].tolist()
        generated_text = self.tokenizer.decode(generated_token_ids, skip_special_tokens=True)

        # Update counters
        self._generation_count += 1
        self._total_tokens_generated += generation_meta['tokens_generated']

        result = {
            'text': generated_text,
            'tokens': generated_token_ids,
            'full_ids': generated_ids,
            'meta': generation_meta,
            'scores': scores,
        }

        if return_hidden_states:
            result['hidden_states'] = hidden_states_list

        return result

    @torch.no_grad()
    def generate_v10(
        self,
        prompt: Union[str, torch.Tensor],
        max_new_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        reset_state: bool = False,
        track_trajectory: bool = True,
        on_token_callback: Optional[callable] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Generate using V10.0 Binding Cache architecture (Phase 5).

        Automatically dispatches to the appropriate engine based on architecture:
        - ONTOLOGICAL_BINDING_CACHE: Uses two-pass generation with 32D state
        - BINDING_CACHE: Uses proposal mode with Top-K cache

        Args:
            prompt: Text prompt or input_ids tensor
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling threshold
            top_k: Top-k sampling
            reset_state: Reset Sovereign State (for ontological mode)
            track_trajectory: Track state evolution
            on_token_callback: Optional callback(token_id, step_meta)
            **kwargs: Additional generation arguments

        Returns:
            result: Dict with generation outputs and V10.0 specific metrics
        """
        # Apply defaults
        max_new_tokens = max_new_tokens or self.config.max_new_tokens
        temperature = temperature or self.config.default_temperature
        top_p = top_p or self.config.default_top_p
        top_k = top_k or self.config.default_top_k

        # Encode prompt if string
        if isinstance(prompt, str):
            input_ids = self.tokenizer.encode(prompt, return_tensors='pt')
        else:
            input_ids = prompt

        input_ids = input_ids.to(self._device)

        arch = self.config.architecture_mode

        # Dispatch to appropriate engine
        if arch == ArchitectureMode.ONTOLOGICAL_BINDING_CACHE and self.ontological_engine is not None:
            # Two-pass generation with Sovereign State tracking
            generated_ids, engine_meta = self.ontological_engine.generate_with_ontology(
                input_ids,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                reset_state=reset_state,
                track_trajectory=track_trajectory,
                on_token_callback=on_token_callback,
                **kwargs,
            )

            # Decode output
            generated_token_ids = generated_ids[0, input_ids.size(1):].tolist()
            generated_text = self.tokenizer.decode(generated_token_ids, skip_special_tokens=True)

            # Update counters
            self._generation_count += 1
            self._total_tokens_generated += engine_meta['tokens_generated']

            return {
                'text': generated_text,
                'tokens': generated_token_ids,
                'full_ids': generated_ids,
                'meta': engine_meta,
                'architecture': 'ontological_binding_cache',
                'state_trajectory': engine_meta.get('state_trajectory'),
                'final_state': engine_meta.get('final_state'),
                'final_metrics': engine_meta.get('final_metrics'),
                'reliability': engine_meta.get('avg_reliability'),
                'warnings': engine_meta.get('warnings', []),
            }

        elif arch == ArchitectureMode.BINDING_CACHE and self.binding_cache_engine is not None:
            # Proposal mode generation with Top-K cache
            generated_ids, engine_meta = self.binding_cache_engine.generate(
                input_ids,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                track_metrics=track_trajectory,
                on_token_callback=on_token_callback,
                **kwargs,
            )

            # Decode output
            generated_token_ids = generated_ids[0, input_ids.size(1):].tolist()
            generated_text = self.tokenizer.decode(generated_token_ids, skip_special_tokens=True)

            # Update counters
            self._generation_count += 1
            self._total_tokens_generated += engine_meta['tokens_generated']

            return {
                'text': generated_text,
                'tokens': generated_token_ids,
                'full_ids': generated_ids,
                'meta': engine_meta,
                'architecture': 'binding_cache',
                'proposal_metrics': engine_meta.get('proposal_metrics'),
                'avg_confidence': engine_meta.get('avg_confidence'),
                'avg_skip_rate': engine_meta.get('avg_skip_rate'),
                'phase_health': engine_meta.get('final_phase_health'),
                'cache_metrics': engine_meta.get('final_cache_metrics'),
            }

        else:
            # Fallback to standard generation
            return self.generate(
                prompt,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p,
                top_k=top_k,
                on_token_callback=on_token_callback,
                **kwargs,
            )

    def get_status(self) -> str:
        """
        Get comprehensive status string.

        Returns:
            status: Multi-line status string
        """
        lines = [f"InferenceManager [{self.config.mode.value}]"]
        lines.append(f"  Device: {self._device}")
        lines.append(f"  Architecture: {self.config.architecture_mode.value if self.config.architecture_mode else 'unknown'}")
        lines.append(f"  Generations: {self._generation_count}")
        lines.append(f"  Total tokens: {self._total_tokens_generated}")
        lines.append("")

        # Component statuses
        if self.evolutionary_engine is not None:
            lines.append(f"  {self.evolutionary_engine.get_status_line()}")

        if self.csr_guard is not None:
            lines.append(f"  {self.csr_guard.get_status_line()}")

        if self.metacognition is not None:
            lines.append(f"  {self.metacognition.get_status_line()}")

        if self.gunas is not None:
            lines.append(f"  {self.gunas.get_status_line()}")

        if self.scorer is not None:
            lines.append(f"  {self.scorer.get_status_line()}")

        # V10.0 engine statuses (Phase 5)
        if self.binding_cache_engine is not None:
            lines.append(f"  {self.binding_cache_engine.get_status_line()}")

        if self.ontological_engine is not None:
            lines.append(f"  {self.ontological_engine.get_status_line()}")

        if self.state_monitor is not None:
            lines.append(f"  {self.state_monitor.get_status_line()}")

        return "\n".join(lines)

    def get_status_line(self) -> str:
        """Get single-line status."""
        parts = [f"Mode: {self.config.mode.value}"]

        if self.evolutionary_engine is not None and self.evolutionary_engine.bridge_enabled:
            parts.append(f"Karma: age={self.evolutionary_engine.karma_age}")

        if self.metacognition is not None and self.metacognition.coherence_history:
            avg_coh = sum(self.metacognition.coherence_history[-10:]) / len(self.metacognition.coherence_history[-10:])
            parts.append(f"Coh: {avg_coh:.2f}")

        return " | ".join(parts)

    def clear_state(self) -> None:
        """Clear all accumulated state."""
        if self.evolutionary_engine is not None:
            self.evolutionary_engine.clear_karma()

        if self.csr_guard is not None:
            self.csr_guard.reset_history()

        if self.metacognition is not None:
            self.metacognition.reset()

        if self.gunas is not None:
            self.gunas.reset()

        if self.scorer is not None:
            self.scorer.reset()

        # V10.0 engines (Phase 5)
        if self.binding_cache_engine is not None:
            self.binding_cache_engine.clear_state()

        if self.ontological_engine is not None:
            self.ontological_engine.clear_state()

        if self.state_monitor is not None:
            self.state_monitor.clear()

    def save_state(self, path: Union[str, Path]) -> None:
        """
        Save manager state for later resumption.

        Args:
            path: Save path
        """
        state = {
            'generation_count': self._generation_count,
            'total_tokens': self._total_tokens_generated,
            'config': self.config,
        }

        if self.evolutionary_engine is not None:
            state['evolutionary'] = self.evolutionary_engine.get_state()

        torch.save(state, path)

    def load_state(self, path: Union[str, Path]) -> None:
        """
        Load manager state.

        Args:
            path: State file path
        """
        state = torch.load(path, map_location=self._device)

        self._generation_count = state.get('generation_count', 0)
        self._total_tokens_generated = state.get('total_tokens', 0)

        if 'evolutionary' in state and self.evolutionary_engine is not None:
            self.evolutionary_engine.load_state(state['evolutionary'])

    @torch.no_grad()
    def generate_full_sequence(
        self,
        prompt_ids: torch.Tensor,
        max_tokens: int = 128,
        base_temp: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 50,
        on_step_callback: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Execute a complete metabolic generation sequence.

        This is the SOVEREIGN-level orchestrator that connects discrete token
        generation to the Metabolic Loop, ensuring every step is governed by
        Guna state and Karma persistence.

        The metabolic loop:
        1. Initialize sequence with evolutionary seed (karma injection)
        2. Generate tokens with Guna tracking and metacognitive adjustments
        3. Apply CSR safety checks and temperature adaptation
        4. Handle recommendations: BRAKE, RECOVER, ABORT
        5. Harvest O12 state for next sequence karma
        6. Compute 3-way toroidal coherence

        Args:
            prompt_ids: [B, T] input token IDs
            max_tokens: Maximum tokens to generate
            base_temp: Base sampling temperature
            top_p: Nucleus sampling threshold
            top_k: Top-k sampling
            on_step_callback: Optional callback(step, step_result) per step

        Returns:
            result: Dict with:
                - generated_ids: Full sequence including prompt
                - text: Decoded text (if tokenizer available)
                - gunas: Final (sattva, rajas, tamas) tuple
                - recommendation: Final metacognitive recommendation
                - coherence: 3-way toroidal coherence score
                - coherence_details: Dict with birth, flow, evolution similarities
                - aborted: Whether generation was aborted
                - abort_reason: Reason for abort (if applicable)
                - interventions: Number of CSR interventions
                - karma_stored: Whether karma was stored for next sequence
                - tokens_generated: Number of tokens generated
                - temperature_history: List of effective temperatures used
        """
        # Ensure on correct device
        prompt_ids = prompt_ids.to(self._device)
        B = prompt_ids.size(0)

        # Reset per-generation state
        if self.metacognition is not None:
            self.metacognition.reset()
        if self.gunas is not None:
            self.gunas.reset()
        if self.csr_guard is not None:
            self.csr_guard.reset_history()

        # Track generation state
        generated = prompt_ids.clone()
        current_temp = base_temp
        all_gunas = []
        temperature_history = []
        csr_interventions = 0
        final_recommendation = "CONTINUE"
        aborted = False
        abort_reason = None

        # === STEP 1: Initialize with Evolutionary Seed ===
        # Inject karma from previous conversation into Layer 0
        karma_injected = False
        if (self.config.enable_karma and
            self.evolutionary_engine is not None and
            self.evolutionary_engine.karma_buffer is not None and
            self.evolutionary_engine.bridge_enabled):
            karma_injected = True

        # === STEP 2: The Metabolic Generation Loop ===
        for step in range(max_tokens):
            # --- A. Forward Pass ---
            # Request hidden states for O12 extraction
            outputs = self.model(
                generated,
                extract_layers=[0, 11] if hasattr(self.model, 'forward') else None,
            )

            # Extract outputs
            if isinstance(outputs, dict):
                logits = outputs.get('logits', outputs.get('output'))
                hidden_states = outputs.get('hidden_states')
                last_hidden = outputs.get('last_hidden_state')
            elif isinstance(outputs, tuple):
                logits = outputs[0]
                hidden_states = outputs[1] if len(outputs) > 1 else None
                last_hidden = None
            else:
                logits = outputs
                hidden_states = None
                last_hidden = None

            next_logits = logits[:, -1, :].clone()

            # --- B. CSR Safety Check ---
            if self.config.enable_csr_guard and self.csr_guard is not None:
                # Get hidden state for CSR
                if last_hidden is not None:
                    hidden_for_csr = last_hidden[:, -1, :]
                elif hidden_states is not None:
                    h = hidden_states[-1] if isinstance(hidden_states, list) else hidden_states
                    hidden_for_csr = h[:, -1, :] if h.dim() == 3 else h
                else:
                    hidden_for_csr = torch.zeros(B, self.model.embed_dim, device=self._device)

                next_logits, csr_info = self.csr_guard.check_and_gate(
                    hidden_for_csr,
                    next_logits,
                )
                if csr_info.get('intervention', False):
                    csr_interventions += 1

            # --- C. Metacognitive Monitoring ---
            recommendation = "CONTINUE"
            if self.metacognition is not None:
                meta_result = self.metacognition.update(
                    next_logits,
                    hidden_states[-1] if hidden_states and isinstance(hidden_states, list) else hidden_states,
                    token_id=None,  # Not yet sampled
                )
                recommendation = meta_result.get('recommendation', GenerationRecommendation.CONTINUE)
                if isinstance(recommendation, GenerationRecommendation):
                    recommendation = recommendation.name
                final_recommendation = recommendation

            # --- D. Metacognitive Adjustment ---
            if recommendation == "BRAKE":
                current_temp *= 0.8  # Sharpen focus to reduce entropy
            elif recommendation == "RECOVER":
                current_temp = min(base_temp, current_temp * 1.2)  # Allow creative flow
            elif recommendation == "ABORT":
                aborted = True
                abort_reason = "coherence_collapse"
                break

            # --- E. Guna-based Temperature Adjustment ---
            effective_temp = current_temp
            if self.gunas is not None:
                effective_temp = self.gunas.get_temperature_modifier(current_temp)
            temperature_history.append(effective_temp)

            # --- F. Layer-aware Temperature (9:3 Split) ---
            # Sensory layers get sharper temperature (0.9x)
            # This is applied implicitly through the model's attention mechanism
            # but we can apply an additional adjustment here
            if self.layer_config is not None:
                # Get layer-adjusted temperature for final layers
                layer_temp_mult = self.layer_config.get_temperature_multiplier(layer_idx=11)
                effective_temp *= layer_temp_mult

            # --- G. Sampling ---
            # Apply temperature
            next_logits = next_logits / max(effective_temp, 1e-8)

            # Top-k filtering
            if top_k > 0:
                top_k_values = torch.topk(next_logits, min(top_k, next_logits.size(-1)))[0]
                threshold = top_k_values[:, -1].unsqueeze(-1)
                next_logits = torch.where(
                    next_logits < threshold,
                    torch.full_like(next_logits, float('-inf')),
                    next_logits,
                )

            # Top-p (nucleus) filtering
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

            # --- H. Update Guna State ---
            if self.gunas is not None:
                s, r, t = self.gunas.update(next_token.item(), next_token_prob)
                all_gunas.append((s, r, t))

            # --- I. Sequence Update ---
            generated = torch.cat((generated, next_token), dim=1)

            # Step callback
            if on_step_callback is not None:
                step_result = {
                    'step': step,
                    'token_id': next_token.item(),
                    'prob': next_token_prob,
                    'temperature': effective_temp,
                    'recommendation': recommendation,
                    'gunas': all_gunas[-1] if all_gunas else None,
                }
                on_step_callback(step, step_result)

            # --- J. Stop Condition ---
            eos_token_id = getattr(self.tokenizer, 'eos_token_id', 2) if self.tokenizer else 2
            if next_token.item() == eos_token_id:
                break

        # === STEP 3: Final Harvest (Toroidal Bridge) ===
        # Extract O1 and O12 states for coherence and karma
        coherence = 0.0
        coherence_details = {}
        karma_stored = False

        if self.evolutionary_engine is not None and self.evolutionary_engine.bridge_enabled:
            # Get final hidden states
            final_outputs = self.model(generated, extract_layers=[0, 11])
            if isinstance(final_outputs, dict) and 'hidden_states' in final_outputs:
                final_hidden_states = final_outputs['hidden_states']

                # Extract O1 (layer 0) and O12 (layer 11)
                if len(final_hidden_states) >= 2:
                    o1_hidden = final_hidden_states[0]  # Layer 0
                    o12_hidden = final_hidden_states[-1]  # Layer 11

                    # Mean pool over sequence dimension
                    o1_pooled = o1_hidden.mean(dim=1) if o1_hidden.dim() == 3 else o1_hidden
                    o12_pooled = o12_hidden.mean(dim=1) if o12_hidden.dim() == 3 else o12_hidden

                    # Compute 3-way toroidal coherence
                    coherence, coherence_details = self._compute_3way_coherence(
                        o1_pooled, o12_pooled
                    )

                    # Store new karma (harvest O12 for next sequence)
                    new_karma = self.evolutionary_engine.bridge.compute_seed(o12_pooled)
                    self.evolutionary_engine.karma_buffer = (
                        new_karma * self.evolutionary_engine.config.karma_decay
                    )
                    self.evolutionary_engine.karma_age += 1
                    karma_stored = True

        # === STEP 4: Build Result ===
        tokens_generated = generated.size(1) - prompt_ids.size(1)
        self._generation_count += 1
        self._total_tokens_generated += tokens_generated

        # Final Guna state
        final_gunas = all_gunas[-1] if all_gunas else (0.33, 0.33, 0.34)

        # Decode text if tokenizer available
        generated_text = ""
        if self.tokenizer is not None:
            generated_token_ids = generated[0, prompt_ids.size(1):].tolist()
            generated_text = self.tokenizer.decode(generated_token_ids, skip_special_tokens=True)

        # Sovereign score if available
        sovereign_score = None
        sovereign_info = {}
        if self.scorer is not None:
            try:
                sovereign_score, sovereign_info = self.scorer.score_generation_simple(
                    gunas=final_gunas,
                    coherence=coherence,
                )
            except Exception:
                pass

        return {
            # Core outputs
            'generated_ids': generated,
            'text': generated_text,

            # Cognitive state
            'gunas': final_gunas,
            'recommendation': final_recommendation,

            # Toroidal coherence
            'coherence': coherence,
            'coherence_details': coherence_details,

            # Generation status
            'aborted': aborted,
            'abort_reason': abort_reason,
            'interventions': csr_interventions,
            'karma_stored': karma_stored,
            'karma_injected': karma_injected,
            'tokens_generated': tokens_generated,
            'temperature_history': temperature_history,

            # Sovereign alignment (if available)
            'sovereign_score': sovereign_score,
            'sovereign_info': sovereign_info,
        }

    def _compute_3way_coherence(
        self,
        o1_hidden: torch.Tensor,
        o12_hidden: torch.Tensor,
    ) -> Tuple[float, Dict[str, float]]:
        """
        Compute 3-way toroidal coherence between Seed, O1, and O12.

        The 3-way coherence measures:
        1. Birth Similarity: Seed <-> O1 (karma injection effectiveness)
        2. Flow Similarity: O1 <-> O12 (internal coherence)
        3. Evolution Similarity: Seed <-> O12 (loop closure)

        Args:
            o1_hidden: [B, D] mean-pooled O1 hidden state
            o12_hidden: [B, D] mean-pooled O12 hidden state

        Returns:
            coherence: Combined coherence score [0, 1]
            details: Dict with individual similarity scores
        """
        if self.evolutionary_engine is None or self.evolutionary_engine.karma_buffer is None:
            # No seed available, compute 2-way coherence
            flow_sim = F.cosine_similarity(
                o1_hidden.view(1, -1),
                o12_hidden.view(1, -1),
            ).item()
            flow_sim = (flow_sim + 1) / 2  # Map to [0, 1]

            return flow_sim, {
                'birth_similarity': 0.0,
                'flow_similarity': flow_sim,
                'evolution_similarity': 0.0,
                '3way': False,
            }

        seed = self.evolutionary_engine.karma_buffer

        # Flatten for cosine similarity
        seed_flat = seed.view(1, -1)
        o1_flat = o1_hidden.view(1, -1)
        o12_flat = o12_hidden.view(1, -1)

        # Compute 3 similarities
        birth_sim = F.cosine_similarity(seed_flat, o1_flat).item()
        flow_sim = F.cosine_similarity(o1_flat, o12_flat).item()
        evolution_sim = F.cosine_similarity(seed_flat, o12_flat).item()

        # Map from [-1, 1] to [0, 1]
        birth_sim = (birth_sim + 1) / 2
        flow_sim = (flow_sim + 1) / 2
        evolution_sim = (evolution_sim + 1) / 2

        # Combined coherence (geometric mean for balance)
        combined = (birth_sim * flow_sim * evolution_sim) ** (1/3)

        return combined, {
            'birth_similarity': birth_sim,
            'flow_similarity': flow_sim,
            'evolution_similarity': evolution_sim,
            '3way': True,
        }

    def get_cognitive_status_line(self) -> str:
        """
        Get comprehensive cognitive status line for Sovereign mode.

        Format: [SOVEREIGN] Karma:0.75(strong)|avg:0.72 | Guna:S|s=0.45|r=0.30|t=0.25 | Meta:CONT|c=0.68

        Returns:
            status: Formatted status line
        """
        parts = [f"[{self.config.mode.value.upper()}]"]

        # Karma status
        if self.evolutionary_engine is not None and self.evolutionary_engine.bridge_enabled:
            coh = self.evolutionary_engine.compute_generation_coherence()
            strength = "strong" if coh > 0.7 else "weak" if coh < 0.3 else "medium"
            avg_coh = (
                sum(self.evolutionary_engine.coherence_history[-5:]) /
                len(self.evolutionary_engine.coherence_history[-5:])
                if self.evolutionary_engine.coherence_history else 0.0
            )
            parts.append(f"Karma:{coh:.2f}({strength})|avg:{avg_coh:.2f}")

        # Guna status
        if self.gunas is not None:
            s, r, t = self.gunas.sattva, self.gunas.rajas, self.gunas.tamas
            dominant = "S" if s >= r and s >= t else "R" if r >= t else "T"
            parts.append(f"Guna:{dominant}|s={s:.2f}|r={r:.2f}|t={t:.2f}")

        # Metacognition status
        if self.metacognition is not None:
            rec = self.metacognition.get_current_recommendation()
            if isinstance(rec, GenerationRecommendation):
                rec = rec.name[:4]
            coh = self.metacognition.get_current_coherence()
            trend = self.metacognition.get_coherence_trend()
            trend_symbol = "📈" if trend > 0.02 else "📉" if trend < -0.02 else "➡️"
            parts.append(f"Meta:{rec}|c={coh:.2f}{trend_symbol}")

        return " | ".join(parts)
