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


class InferenceMode(Enum):
    """Inference mode presets."""
    FAST = "fast"  # Minimal overhead, basic generation
    STANDARD = "standard"  # Karma + basic monitoring
    FULL = "full"  # All features enabled
    SAFE = "safe"  # Full + strict CSR enforcement


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
            device: Target device
        """
        self.config = config or InferenceManagerConfig()
        self.model = model
        self.tokenizer = tokenizer
        self._device = torch.device(device) if isinstance(device, str) else device

        # Apply mode presets
        self._apply_mode_preset()

        # Initialize components based on config
        self.evolutionary_engine = evolutionary_engine
        self.csr_guard = csr_guard
        self.layer_config = layer_config or LayerInferenceConfig()

        # Create remaining components
        self.metacognition = InferenceMetacognition() if self.config.enable_metacognition else None
        self.gunas = InferenceGunas() if self.config.enable_gunas else None
        self.scorer = SovereignInferenceScorer() if self.config.enable_scoring else None

        # Generation state
        self._generation_count: int = 0
        self._total_tokens_generated: int = 0

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

    def get_status(self) -> str:
        """
        Get comprehensive status string.

        Returns:
            status: Multi-line status string
        """
        lines = [f"InferenceManager [{self.config.mode.value}]"]
        lines.append(f"  Device: {self._device}")
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
