"""
Inference Manager Module
========================

Central orchestrator for the Symbolu inference pipeline with tiered modes.

The InferenceManager is the "central nervous system" that coordinates all
inference-time components (Karma, Gunas, CSR, Scorer, Metacognition) into
a unified, tiered generation pipeline.

Modes:
------
1. **Fast**: Raw transformer inference with minimal overhead.
   - No karma injection or storage
   - No quality monitoring
   - Ideal for: Rapid prototyping, benchmarking, latency-sensitive applications

2. **Standard**: Karma persistence with Guna-scaled dynamic alpha.
   - Cross-sequence state via karma buffer
   - Guna tracking for dynamic alpha
   - Basic quality metrics
   - Ideal for: Production inference, multi-turn conversations

3. **Sovereign**: Full safety and alignment pipeline.
   - All Standard features +
   - CSR Guard with lm_head re-projection
   - Metacognitive monitoring (ABORT/BRAKE/RECOVER)
   - Sovereign R-Matrix alignment scoring
   - Ideal for: High-stakes applications, alignment research

Usage:
------
    from symbolu.inference import InferenceManager, InferenceMode

    # Create manager
    manager = InferenceManager(model, mode=InferenceMode.SOVEREIGN)

    # Generate with full pipeline
    output, metrics = manager.generate(
        input_ids,
        max_new_tokens=100,
    )

    # Check alignment score
    print(f"Sovereign alignment: {metrics['sovereign_score']:.3f}")

    # Switch modes dynamically
    manager.set_mode(InferenceMode.FAST)
"""

from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Union

import torch
import torch.nn as nn
import torch.nn.functional as F

from .evolutionary_inference import EvolutionaryInferenceEngine
from .metacognitive_monitor import InferenceMetacognition, Recommendation
from .guna_inference import InferenceGunas
from .csr_inference import CSRInferenceGuard
from .sovereign_scorer import SovereignInferenceScorer
from .layer_config import LayerInferenceConfig


class InferenceMode(Enum):
    """Inference pipeline modes."""
    FAST = "fast"            # Raw transformer, minimal overhead
    STANDARD = "standard"    # Karma + Guna-Alpha scaling
    SOVEREIGN = "sovereign"  # Full CSR + Scorer + Metacognition


class InferenceManager:
    """
    Central orchestrator for tiered inference pipeline.

    Manages all inference-time components and provides a unified
    interface for generation across different quality/latency tradeoffs.

    The manager lazily initializes components based on the selected mode,
    minimizing overhead when not using full Sovereign mode.

    Args:
        model: The transformer model (HybridPhaseTransformer or compatible)
        mode: Initial inference mode (default: STANDARD)
        dim: Hidden dimension (inferred from model if not provided)
        enable_logging: Enable detailed logging of pipeline operations
        checkpoint_path: Optional path to load trained component weights

    Attributes:
        mode: Current inference mode
        engine: EvolutionaryInferenceEngine (karma and base generation)
        metacognition: InferenceMetacognition (quality monitoring)
        gunas: InferenceGunas (cognitive state tracking)
        csr_guard: CSRInferenceGuard (safety layer)
        scorer: SovereignInferenceScorer (alignment scoring)
    """

    # Mode-to-components mapping
    MODE_COMPONENTS = {
        InferenceMode.FAST: {
            'engine': False,
            'gunas': False,
            'metacognition': False,
            'csr_guard': False,
            'scorer': False,
        },
        InferenceMode.STANDARD: {
            'engine': True,
            'gunas': True,
            'metacognition': False,
            'csr_guard': False,
            'scorer': False,
        },
        InferenceMode.SOVEREIGN: {
            'engine': True,
            'gunas': True,
            'metacognition': True,
            'csr_guard': True,
            'scorer': True,
        },
    }

    def __init__(
        self,
        model: nn.Module,
        mode: InferenceMode = InferenceMode.STANDARD,
        dim: Optional[int] = None,
        enable_logging: bool = False,
        checkpoint_path: Optional[str] = None,
        # Component configuration
        resonance_alpha: float = 0.1,
        karma_decay: float = 0.99,
        coherence_window: int = 50,
        alarm_threshold: float = 0.3,
        abort_consecutive: int = 5,
        guna_window_size: int = 20,
        entropy_threshold: float = 2.0,
        csr_skip_threshold: float = 0.9,
    ):
        self.model = model
        self._mode = mode
        self.enable_logging = enable_logging

        # Infer dimension from model
        if dim is None:
            if hasattr(model, 'config'):
                dim = model.config.embed_dim
            elif hasattr(model, 'token_embed'):
                dim = model.token_embed.weight.shape[1]
            else:
                raise ValueError("Cannot infer dim from model, please provide explicitly")

        self.dim = dim
        self.device = next(model.parameters()).device

        # Store configuration for lazy initialization
        self._config = {
            'resonance_alpha': resonance_alpha,
            'karma_decay': karma_decay,
            'coherence_window': coherence_window,
            'alarm_threshold': alarm_threshold,
            'abort_consecutive': abort_consecutive,
            'guna_window_size': guna_window_size,
            'entropy_threshold': entropy_threshold,
            'csr_skip_threshold': csr_skip_threshold,
        }

        # Component storage (lazily initialized)
        self._engine: Optional[EvolutionaryInferenceEngine] = None
        self._metacognition: Optional[InferenceMetacognition] = None
        self._gunas: Optional[InferenceGunas] = None
        self._csr_guard: Optional[CSRInferenceGuard] = None
        self._scorer: Optional[SovereignInferenceScorer] = None

        # Statistics
        self.generation_count = 0
        self.mode_history: List[InferenceMode] = []

        # Load checkpoint if provided
        if checkpoint_path:
            self.load_checkpoint(checkpoint_path)

        # Initialize components for current mode
        self._initialize_mode_components()

    @property
    def mode(self) -> InferenceMode:
        """Current inference mode."""
        return self._mode

    @property
    def engine(self) -> Optional[EvolutionaryInferenceEngine]:
        """Evolutionary inference engine (karma, generation)."""
        return self._engine

    @property
    def metacognition(self) -> Optional[InferenceMetacognition]:
        """Metacognitive monitor (quality recommendations)."""
        return self._metacognition

    @property
    def gunas(self) -> Optional[InferenceGunas]:
        """Guna tracker (cognitive state)."""
        return self._gunas

    @property
    def csr_guard(self) -> Optional[CSRInferenceGuard]:
        """CSR safety guard."""
        return self._csr_guard

    @property
    def scorer(self) -> Optional[SovereignInferenceScorer]:
        """Sovereign alignment scorer."""
        return self._scorer

    @property
    def layer_config(self) -> type:
        """Layer configuration for 9:3 hierarchical split."""
        return LayerInferenceConfig

    def get_layer_temperature(self, layer_idx: int, base_temp: float) -> float:
        """
        Get temperature adjusted for layer type (9:3 split).

        Sensory layers (O10-O12) get sharper temperature for precise
        token selection.

        Args:
            layer_idx: Layer index (0-11)
            base_temp: Base temperature value

        Returns:
            Adjusted temperature for the layer
        """
        return LayerInferenceConfig.get_temperature_adjustment(layer_idx, base_temp)

    def get_cache_priority(self, layer_idx: int) -> str:
        """
        Get KV-cache priority for a layer.

        Authority layers (O1-O9) get HIGH priority, Sensory (O10-O12) MEDIUM.

        Args:
            layer_idx: Layer index (0-11)

        Returns:
            Priority string: "high" or "medium"
        """
        return LayerInferenceConfig.get_cache_priority(layer_idx)

    def set_mode(self, mode: InferenceMode):
        """
        Switch inference mode.

        Lazily initializes required components if not already present.

        Args:
            mode: New inference mode
        """
        if mode == self._mode:
            return

        self.mode_history.append(self._mode)
        self._mode = mode
        self._initialize_mode_components()

        if self.enable_logging:
            print(f"[InferenceManager] Mode switched to: {mode.value}")

    def _initialize_mode_components(self):
        """Initialize components required for current mode."""
        required = self.MODE_COMPONENTS[self._mode]

        # Engine (karma, base generation)
        if required['engine'] and self._engine is None:
            self._engine = EvolutionaryInferenceEngine(
                self.model,
                dim=self.dim,
                resonance_alpha=self._config['resonance_alpha'],
                karma_decay=self._config['karma_decay'],
            )
            if self.enable_logging:
                print("[InferenceManager] Initialized EvolutionaryInferenceEngine")

        # Gunas (cognitive state tracking)
        if required['gunas'] and self._gunas is None:
            self._gunas = InferenceGunas(
                window_size=self._config['guna_window_size'],
            )
            if self.enable_logging:
                print("[InferenceManager] Initialized InferenceGunas")

        # Metacognition (quality monitoring)
        if required['metacognition'] and self._metacognition is None:
            self._metacognition = InferenceMetacognition(
                coherence_window=self._config['coherence_window'],
                alarm_threshold=self._config['alarm_threshold'],
                abort_consecutive=self._config['abort_consecutive'],
            )
            if self.enable_logging:
                print("[InferenceManager] Initialized InferenceMetacognition")

        # CSR Guard (safety layer)
        if required['csr_guard'] and self._csr_guard is None:
            # Get lm_head from model
            lm_head = getattr(self.model, 'lm_head', None)
            self._csr_guard = CSRInferenceGuard(
                lm_head=lm_head,
                dim=self.dim,
                entropy_threshold=self._config['entropy_threshold'],
                skip_threshold=self._config['csr_skip_threshold'],
            )
            self._csr_guard.to(self.device)
            if self.enable_logging:
                print("[InferenceManager] Initialized CSRInferenceGuard")

        # Sovereign Scorer (alignment scoring)
        if required['scorer'] and self._scorer is None:
            self._scorer = SovereignInferenceScorer(dim=self.dim)
            self._scorer.to(self.device)
            if self.enable_logging:
                print("[InferenceManager] Initialized SovereignInferenceScorer")

    def _get_active_components(self) -> Dict[str, bool]:
        """Get which components are active for current mode."""
        return self.MODE_COMPONENTS[self._mode]

    def generate(
        self,
        input_ids: torch.Tensor,
        max_new_tokens: int = 128,
        temperature: float = 1.0,
        top_k: int = 50,
        top_p: float = 0.9,
        # Karma controls
        inject_karma: bool = True,
        store_karma: bool = True,
        # Scoring controls (Sovereign mode)
        compute_alignment: bool = True,
        alignment_layers: Optional[List[int]] = None,
        # Return options
        return_detailed_metrics: bool = False,
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Generate with the configured inference pipeline.

        This is the main entry point for generation. The behavior depends
        on the current mode:

        - **FAST**: Direct model generation, minimal processing
        - **STANDARD**: Karma injection/storage + Guna tracking
        - **SOVEREIGN**: Full pipeline with CSR, metacognition, scoring

        Args:
            input_ids: Input token IDs [B, N]
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_k: Top-k filtering (0 to disable)
            top_p: Nucleus sampling threshold
            inject_karma: Whether to inject stored karma (STANDARD/SOVEREIGN)
            store_karma: Whether to store new karma (STANDARD/SOVEREIGN)
            compute_alignment: Whether to compute Sovereign alignment (SOVEREIGN)
            alignment_layers: Layers to use for alignment scoring
            return_detailed_metrics: Include detailed component metrics

        Returns:
            output_ids: Generated token IDs including input
            metrics: Dict with generation info, mode-specific metrics
        """
        self.generation_count += 1
        active = self._get_active_components()

        # Base metrics
        metrics: Dict[str, Any] = {
            'generation_id': self.generation_count,
            'mode': self._mode.value,
        }

        # Move input to device
        input_ids = input_ids.to(self.device)

        # Route based on mode
        if self._mode == InferenceMode.FAST:
            output_ids, fast_metrics = self._generate_fast(
                input_ids,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
            )
            metrics.update(fast_metrics)

        elif self._mode == InferenceMode.STANDARD:
            output_ids, standard_metrics = self._generate_standard(
                input_ids,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                inject_karma=inject_karma,
                store_karma=store_karma,
            )
            metrics.update(standard_metrics)

        else:  # SOVEREIGN
            output_ids, sovereign_metrics = self._generate_sovereign(
                input_ids,
                max_new_tokens=max_new_tokens,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                inject_karma=inject_karma,
                store_karma=store_karma,
                compute_alignment=compute_alignment,
                alignment_layers=alignment_layers,
            )
            metrics.update(sovereign_metrics)

        # Add detailed component metrics if requested
        if return_detailed_metrics:
            metrics['component_status'] = self._get_component_status()

        return output_ids, metrics

    def _generate_fast(
        self,
        input_ids: torch.Tensor,
        max_new_tokens: int,
        temperature: float,
        top_k: int,
        top_p: float,
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Fast mode: Direct model generation with minimal overhead.

        Bypasses all components and uses simple autoregressive sampling.
        """
        metrics: Dict[str, Any] = {'overhead': 'minimal'}

        generated_ids = input_ids.clone()
        B = input_ids.shape[0]

        for step in range(max_new_tokens):
            # Forward pass
            outputs = self.model(generated_ids)
            logits = outputs['logits'][:, -1, :]  # [B, V]

            # Apply temperature
            logits = logits / temperature

            # Top-k filtering
            if top_k > 0:
                indices_to_remove = logits < torch.topk(logits, top_k)[0][..., -1, None]
                logits[indices_to_remove] = float('-inf')

            # Top-p (nucleus) filtering
            if top_p < 1.0:
                sorted_logits, sorted_indices = torch.sort(logits, descending=True)
                cumulative_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)
                sorted_indices_to_remove = cumulative_probs > top_p
                sorted_indices_to_remove[..., 1:] = sorted_indices_to_remove[..., :-1].clone()
                sorted_indices_to_remove[..., 0] = False
                indices_to_remove = sorted_indices_to_remove.scatter(
                    1, sorted_indices, sorted_indices_to_remove
                )
                logits[indices_to_remove] = float('-inf')

            # Sample
            probs = F.softmax(logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)
            generated_ids = torch.cat([generated_ids, next_token], dim=1)

            # Check for EOS
            if hasattr(self.model, 'config') and hasattr(self.model.config, 'eos_token_id'):
                eos_id = self.model.config.eos_token_id
                if eos_id is not None and (next_token == eos_id).all():
                    break

        metrics['tokens_generated'] = generated_ids.shape[1] - input_ids.shape[1]
        return generated_ids, metrics

    def _generate_standard(
        self,
        input_ids: torch.Tensor,
        max_new_tokens: int,
        temperature: float,
        top_k: int,
        top_p: float,
        inject_karma: bool,
        store_karma: bool,
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Standard mode: Karma persistence with Guna-scaled dynamic alpha.

        Uses EvolutionaryInferenceEngine with Guna tracker but without
        CSR/Metacognition overhead.
        """
        # Reset Gunas for new generation
        if self._gunas is not None:
            self._gunas.reset()

        # Generate with karma using engine
        output_ids, engine_metrics = self._engine.generate_with_karma(
            input_ids,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            inject_karma=inject_karma,
            store_karma=store_karma,
            return_coherence=True,
            guna_tracker=self._gunas,
            metacognition=None,
            csr_guard=None,
        )

        # Add Guna summary
        if self._gunas is not None:
            engine_metrics['final_gunas'] = self._gunas.current_gunas
            engine_metrics['guna_dominant'] = self._gunas.get_detailed_state()['dominant']

        return output_ids, engine_metrics

    def _generate_sovereign(
        self,
        input_ids: torch.Tensor,
        max_new_tokens: int,
        temperature: float,
        top_k: int,
        top_p: float,
        inject_karma: bool,
        store_karma: bool,
        compute_alignment: bool,
        alignment_layers: Optional[List[int]],
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Sovereign mode: Full pipeline with CSR, metacognition, scoring.

        Engages all safety and alignment components for maximum quality
        at the cost of additional latency.
        """
        # Reset components for new generation
        if self._gunas is not None:
            self._gunas.reset()
        if self._metacognition is not None:
            self._metacognition.reset()
        if self._csr_guard is not None:
            self._csr_guard.reset_statistics()

        # Generate with full pipeline
        output_ids, engine_metrics = self._engine.generate_with_karma(
            input_ids,
            max_new_tokens=max_new_tokens,
            temperature=temperature,
            top_k=top_k,
            top_p=top_p,
            inject_karma=inject_karma,
            store_karma=store_karma,
            return_coherence=True,
            metacognition=self._metacognition,
            guna_tracker=self._gunas,
            csr_guard=self._csr_guard,
        )

        # Add component summaries
        if self._gunas is not None:
            engine_metrics['final_gunas'] = self._gunas.current_gunas
            engine_metrics['guna_detailed'] = self._gunas.get_detailed_state()

        if self._metacognition is not None:
            engine_metrics['metacognition'] = self._metacognition.get_detailed_status()
            engine_metrics['final_recommendation'] = self._metacognition._get_recommendation().value

        if self._csr_guard is not None:
            engine_metrics['csr_statistics'] = self._csr_guard.get_statistics()

        # Compute Sovereign alignment score if requested
        if compute_alignment and self._scorer is not None:
            alignment_score, alignment_info = self._compute_alignment_score(
                output_ids,
                alignment_layers,
            )
            engine_metrics['sovereign_score'] = alignment_score
            engine_metrics['sovereign_info'] = alignment_info

        return output_ids, engine_metrics

    def _compute_alignment_score(
        self,
        output_ids: torch.Tensor,
        alignment_layers: Optional[List[int]] = None,
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Compute Sovereign R-Matrix alignment score.

        Args:
            output_ids: Generated sequence
            alignment_layers: Which layers to score (default: all 12)

        Returns:
            alignment_score: Overall alignment score (0-1)
            alignment_info: Detailed Vṛtti distribution info
        """
        if alignment_layers is None:
            alignment_layers = list(range(12))

        # Get hidden states for scoring
        with torch.no_grad():
            outputs = self.model(
                output_ids,
                extract_layers=alignment_layers,
            )

        hidden_states = outputs.get('hidden_states', [])

        if not hidden_states:
            return 0.5, {'error': 'No hidden states available'}

        # Build layer states dict
        layer_states = {}
        for i, layer_idx in enumerate(sorted(alignment_layers)):
            if i < len(hidden_states):
                layer_states[layer_idx] = hidden_states[i]

        # Compute alignment using scorer
        score, info = self._scorer.score_generation(layer_states)

        return score, info

    def load_checkpoint(self, checkpoint_path: str, apply_config: bool = True) -> bool:
        """
        Load trained weights and inference configuration.

        Loads:
        - Inference config (resonance_alpha, split, etc.) if present
        - Evolutionary bridge weights (if present)
        - CSR Guard weights (if present)
        - Sovereign Scorer weights (if present)

        Args:
            checkpoint_path: Path to training checkpoint
            apply_config: Whether to apply inference config from checkpoint

        Returns:
            True if any weights were loaded
        """
        success = False

        try:
            checkpoint = torch.load(checkpoint_path, map_location=self.device)
        except Exception as e:
            if self.enable_logging:
                print(f"[InferenceManager] Failed to load checkpoint: {e}")
            return False

        # Load and apply inference config if present
        if apply_config and 'inference_config' in checkpoint:
            self._apply_inference_config(checkpoint['inference_config'])
            success = True
            if self.enable_logging:
                print(f"[InferenceManager] Applied inference config from {checkpoint_path}")

        # Initialize engine if needed for loading
        if self._engine is None:
            self._initialize_mode_components()

        # Load bridge weights
        if self._engine is not None:
            if self._engine.load_bridge_checkpoint(checkpoint_path):
                success = True
                if self.enable_logging:
                    print(f"[InferenceManager] Loaded bridge weights from {checkpoint_path}")

        # Load CSR weights if guard exists
        if self._csr_guard is not None:
            try:
                self._csr_guard.load_from_training(checkpoint)
                success = True
                if self.enable_logging:
                    print(f"[InferenceManager] Loaded CSR weights from {checkpoint_path}")
            except Exception as e:
                if self.enable_logging:
                    print(f"[InferenceManager] CSR weight loading failed: {e}")

        # Load scorer weights if exists
        if self._scorer is not None:
            try:
                if 'sovereign_scorer' in checkpoint:
                    self._scorer.load_state_dict(checkpoint['sovereign_scorer'], strict=False)
                    success = True
                    if self.enable_logging:
                        print(f"[InferenceManager] Loaded Scorer weights from {checkpoint_path}")
            except Exception as e:
                if self.enable_logging:
                    print(f"[InferenceManager] Scorer weight loading failed: {e}")

        return success

    def _apply_inference_config(self, config: Dict[str, Any]):
        """
        Apply inference configuration from checkpoint.

        Updates internal config with checkpoint-specified values.

        Args:
            config: Inference config dict from checkpoint
        """
        # Apply recommended resonance alpha
        if 'recommended_alpha' in config:
            self._config['resonance_alpha'] = config['recommended_alpha']
            if self._engine is not None:
                self._engine.resonance_alpha = config['recommended_alpha']

        # Store split info for reference
        if 'authority_sensory_split' in config:
            self._inference_split = tuple(config['authority_sensory_split'])

        # Store training state for reference
        if 'training_state' in config:
            self._training_state = config['training_state']

        if self.enable_logging:
            print(f"[InferenceManager] Config: alpha={config.get('recommended_alpha', 0.1)}, "
                  f"split={config.get('authority_sensory_split', (9, 3))}, "
                  f"state={config.get('training_state', 'unknown')}")

    def clear_karma(self):
        """
        Clear karma buffer for fresh conversation start.

        Also resets component states.
        """
        if self._engine is not None:
            self._engine.clear_karma()
        if self._gunas is not None:
            self._gunas.reset()
        if self._metacognition is not None:
            self._metacognition.reset()
        if self._csr_guard is not None:
            self._csr_guard.reset_statistics()

    def get_karma_status(self) -> str:
        """Get karma coherence status string."""
        if self._engine is not None:
            return self._engine.get_coherence_status()
        return "Karma:disabled"

    def _get_component_status(self) -> Dict[str, Any]:
        """Get detailed status of all components."""
        status = {
            'mode': self._mode.value,
            'generation_count': self.generation_count,
        }

        if self._engine is not None:
            status['engine'] = {
                'bridge_enabled': self._engine.bridge_enabled,
                'karma_stored': self._engine.karma_buffer is not None,
                'gunas': self._engine.current_gunas,
            }

        if self._gunas is not None:
            status['gunas'] = self._gunas.get_detailed_state()

        if self._metacognition is not None:
            status['metacognition'] = self._metacognition.get_detailed_status()

        if self._csr_guard is not None:
            status['csr_guard'] = self._csr_guard.get_statistics()

        if self._scorer is not None:
            status['scorer'] = {'initialized': True}

        return status

    def get_status_line(self) -> str:
        """
        Get compact status line for logging.

        Format: [MODE] karma_status | guna_status | meta_status
        """
        parts = [f"[{self._mode.value.upper()}]"]

        if self._engine is not None:
            parts.append(self._engine.get_coherence_status())

        if self._gunas is not None:
            parts.append(self._gunas.get_status())

        if self._metacognition is not None:
            parts.append(self._metacognition.get_status())

        return " | ".join(parts)

    def __repr__(self) -> str:
        active = self._get_active_components()
        components = [k for k, v in active.items() if v]
        return (
            f"InferenceManager(mode={self._mode.value}, "
            f"dim={self.dim}, "
            f"components={components})"
        )
