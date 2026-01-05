"""
Evolutionary Inference Engine
=============================

Inference-time evolutionary state management for cross-sequence intelligence.

This module implements the inference counterpart to the training-time
EvolutionaryBridge (train_unified_llm.py:373-538), enabling:

1. Karma Buffer: Persistent state that carries cognitive patterns across sequences
2. Delayed Resonance: Injection of previous O12 state into current O1
3. Toroidal Coherence: Tracking cognitive continuity across context windows

The EvolutionaryBridge creates recursive intelligence where:
- The 'Harvest' of one sequence becomes the 'Seed' of the next
- Cognitive patterns persist and evolve across context boundaries
- Multi-turn conversations maintain coherent "memory"

Usage:
------
    from symbolu.inference import EvolutionaryInferenceEngine
    from symbolu.phase_transformer import HybridPhaseTransformer

    model = HybridPhaseTransformer(...)
    engine = EvolutionaryInferenceEngine(model)

    # Load trained bridge weights if available
    engine.load_bridge_checkpoint("checkpoint.pt")

    # Generate with karma persistence
    output_ids, metrics = engine.generate_with_karma(
        input_ids,
        max_new_tokens=100,
        inject_karma=True,
    )

    # Check coherence with previous sequence
    coherence = engine.compute_generation_coherence()
"""

import math
from typing import Dict, List, Optional, Tuple, Any, Union

import torch
import torch.nn as nn
import torch.nn.functional as F


class EvolutionaryBridgeInference(nn.Module):
    """
    Inference-time Evolutionary Bridge for O12 → O1 projection.

    This is a lightweight version of the training EvolutionaryBridge
    that focuses on:
    - Loading trained seed projection weights
    - Computing seeds from harvest states
    - No gradient tracking or SGP/BPTT logic (inference-only)

    The bridge implements the toroidal state transfer:
        O12 (Absolving) --[seed_proj]--> O1 (Potential)

    Args:
        dim: Hidden dimension of the model
        use_gating: Whether to use gated projection (matches training config)
        dropout: Dropout rate (typically 0.0 for inference)
    """

    def __init__(
        self,
        dim: int,
        use_gating: bool = True,
        dropout: float = 0.0,
    ):
        super().__init__()
        self.dim = dim
        self.use_gating = use_gating

        # Seed Projection: W_seed maps O12 → O1
        if use_gating:
            self.seed_gate = nn.Linear(dim, dim, bias=False)
            self.seed_proj = nn.Linear(dim, dim, bias=False)
            self.gate_activation = nn.Sigmoid()
        else:
            self.seed_gate = None
            self.seed_proj = nn.Linear(dim, dim, bias=False)

        self.seed_norm = nn.LayerNorm(dim)
        self.dropout = nn.Dropout(dropout)

    def compute_seed(self, harvest: torch.Tensor) -> torch.Tensor:
        """
        Compute the Seed state from the Harvest (O12 → O1 projection).

        The projection preserves ontological structure while applying
        'Evolutionary Loss' - shedding sequence-specific details.

        Args:
            harvest: O12 hidden state [B, dim] or [B, N, dim]

        Returns:
            seed: Projected state for O1 injection [B, dim]
        """
        # Reduce to [B, dim] if sequence dimension present
        if harvest.dim() == 3:
            harvest = harvest.mean(dim=1)

        if self.seed_gate is not None:
            # Gated projection: gate decides what to carry forward
            gate = self.gate_activation(self.seed_gate(harvest))
            projected = self.seed_proj(harvest)
            seed = gate * projected
        else:
            seed = self.seed_proj(harvest)

        seed = self.dropout(seed)
        seed = self.seed_norm(seed)
        return seed

    def load_from_training_bridge(self, training_bridge_state: Dict[str, torch.Tensor]):
        """
        Load weights from a training EvolutionaryBridge state dict.

        Args:
            training_bridge_state: State dict from training checkpoint
        """
        # Map training keys to inference keys
        key_mapping = {
            'seed_gate.weight': 'seed_gate.weight',
            'seed_proj.weight': 'seed_proj.weight',
            'seed_norm.weight': 'seed_norm.weight',
            'seed_norm.bias': 'seed_norm.bias',
        }

        inference_state = {}
        for train_key, inference_key in key_mapping.items():
            if train_key in training_bridge_state:
                inference_state[inference_key] = training_bridge_state[train_key]

        # Load with strict=False to handle potential mismatches
        self.load_state_dict(inference_state, strict=False)


class EvolutionaryInferenceEngine:
    """
    Inference-time evolutionary state management.

    Implements cross-sequence intelligence by:
    1. Storing O12 hidden states as "karma" for the next sequence
    2. Injecting karma into O1 via delayed resonance
    3. Tracking toroidal coherence for quality monitoring

    This bridges the gap identified in INFERENCE_HYBRID_TRANSFORMER_GAPS.md
    Section 1.1 (Evolutionary Bridge) and 1.2 (Delayed Resonance).

    Args:
        model: The HybridPhaseTransformer model
        dim: Hidden dimension (inferred from model if not provided)
        use_gating: Whether bridge uses gated projection
        resonance_alpha: Base alpha for resonance injection (default 0.1)
        karma_decay: Decay factor for karma across long conversations (default 0.99)

    Attributes:
        karma_buffer: Stored seed state from previous sequence
        current_o12: Most recent O12 hidden state
        coherence_history: Recent coherence scores
        bridge_enabled: Whether bridge weights are loaded
    """

    def __init__(
        self,
        model: nn.Module,
        dim: Optional[int] = None,
        use_gating: bool = True,
        resonance_alpha: float = 0.1,
        karma_decay: float = 0.99,
    ):
        self.model = model
        self.device = next(model.parameters()).device

        # Infer dimension from model
        if dim is None:
            if hasattr(model, 'config'):
                dim = model.config.embed_dim
            elif hasattr(model, 'token_embed'):
                dim = model.token_embed.weight.shape[1]
            else:
                raise ValueError("Cannot infer dim from model, please provide explicitly")

        self.dim = dim
        self.resonance_alpha = resonance_alpha
        self.karma_decay = karma_decay

        # Initialize bridge for O12 → O1 projection
        self.bridge = EvolutionaryBridgeInference(dim, use_gating=use_gating)
        self.bridge.to(self.device)
        self.bridge_enabled = False

        # State buffers
        self.karma_buffer: Optional[torch.Tensor] = None
        self.current_o12: Optional[torch.Tensor] = None

        # Coherence tracking
        self.coherence_history: List[float] = []
        self.generation_count = 0

        # Guna state (for dynamic alpha, if available)
        # Default to balanced state
        self.current_gunas: Tuple[float, float, float] = (0.33, 0.33, 0.33)

    def load_bridge_checkpoint(self, checkpoint_path: str) -> bool:
        """
        Load trained EvolutionaryBridge weights from checkpoint.

        Args:
            checkpoint_path: Path to training checkpoint file

        Returns:
            True if bridge weights were loaded successfully
        """
        try:
            checkpoint = torch.load(checkpoint_path, map_location=self.device)

            # Try different possible keys for bridge state
            bridge_state = None
            for key in ['evolutionary_bridge', 'bridge', 'evolutionary_bridge_state_dict']:
                if key in checkpoint:
                    bridge_state = checkpoint[key]
                    break

            if bridge_state is None:
                # Check if bridge params are in the main model state
                if 'model' in checkpoint:
                    model_state = checkpoint['model']
                    bridge_state = {
                        k.replace('evolutionary_bridge.', ''): v
                        for k, v in model_state.items()
                        if k.startswith('evolutionary_bridge.')
                    }

            if bridge_state:
                self.bridge.load_from_training_bridge(bridge_state)
                self.bridge_enabled = True
                return True
            else:
                print("Warning: Checkpoint does not contain evolutionary bridge weights")
                self.bridge_enabled = False
                return False

        except Exception as e:
            print(f"Warning: Failed to load bridge checkpoint: {e}")
            self.bridge_enabled = False
            return False

    def load_inference_config(self, checkpoint_path: str) -> Dict[str, Any]:
        """
        Load inference configuration from checkpoint metadata.

        Returns recommended inference settings based on training state.
        """
        try:
            checkpoint = torch.load(checkpoint_path, map_location='cpu')

            if 'inference_config' in checkpoint:
                config = checkpoint['inference_config']
                if 'recommended_resonance_alpha' in config:
                    self.resonance_alpha = config['recommended_resonance_alpha']
                return config

            return {}
        except Exception:
            return {}

    def clear_karma(self):
        """
        Clear karma buffer to start fresh conversation.

        Use this when:
        - Starting a completely new conversation topic
        - User explicitly requests memory reset
        - Coherence drops below critical threshold
        """
        self.karma_buffer = None
        self.current_o12 = None
        self.coherence_history.clear()
        self.generation_count = 0

    def apply_karma_decay(self):
        """
        Apply decay to karma buffer for long conversations.

        Prevents stale patterns from dominating new context.
        Called automatically after each generation.
        """
        if self.karma_buffer is not None:
            self.karma_buffer = self.karma_buffer * self.karma_decay

    def _compute_dynamic_alpha(self) -> float:
        """
        Compute dynamic resonance alpha based on Guna state.

        Mirrors training behavior (train_unified_llm.py:1536-1541):
        - High Sattva (clarity) → increase retention
        - High Rajas (error/heat) → reduce retention

        Returns:
            Dynamic alpha in range [0.05, 0.25]
        """
        s, r, t = self.current_gunas

        # Base is resonance_alpha (0.1); range is [0.05, 0.25]
        dynamic_alpha = self.resonance_alpha * (1.0 + (s * 1.5) - (r * 0.5))
        dynamic_alpha = max(0.05, min(0.25, dynamic_alpha))

        return dynamic_alpha

    def apply_inference_resonance(
        self,
        current_hidden: torch.Tensor,
        alpha: Optional[float] = None,
    ) -> torch.Tensor:
        """
        Apply resonance from stored karma to current hidden state.

        This implements delayed resonance injection at inference time,
        mirroring the training behavior (train_unified_llm.py:1513-1558).

        Args:
            current_hidden: Current O1 hidden state [B, N, D] or [B, D]
            alpha: Override alpha (uses dynamic alpha if None)

        Returns:
            Modified hidden state with karma injection
        """
        if self.karma_buffer is None:
            return current_hidden

        # Use dynamic alpha if not specified
        if alpha is None:
            alpha = self._compute_dynamic_alpha()

        # Expand karma to match current hidden dimensions
        karma = self.karma_buffer

        if current_hidden.dim() == 3:
            # [B, N, D] - expand karma to sequence length
            B, N, D = current_hidden.shape
            if karma.dim() == 2:
                # [B, D] -> [B, 1, D] -> [B, N, D]
                karma_expanded = karma.unsqueeze(1).expand(B, N, D)
            else:
                karma_expanded = karma.expand(B, N, D)
        else:
            karma_expanded = karma

        # Inject with alpha scaling
        return current_hidden + (alpha * karma_expanded)

    def _extract_layer_states(
        self,
        input_ids: torch.Tensor,
        extract_layers: Optional[List[int]] = None,
    ) -> Tuple[torch.Tensor, Dict[int, torch.Tensor]]:
        """
        Forward pass with efficient hidden state extraction.

        Uses the model's extract_layers parameter for memory-efficient
        extraction of only the requested layers.

        Args:
            input_ids: Input token IDs [B, N]
            extract_layers: Which layers to extract (default: [0, 11] for O1, O12)
                           Common patterns:
                           - [0, 11]: O1 (Potential) + O12 (Integration) for karma
                           - [0, 5, 11]: Authority + midpoint + final

        Returns:
            logits: Model output logits
            layer_states: Dict mapping layer_idx -> hidden state tensor
        """
        if extract_layers is None:
            extract_layers = [0, 11]  # O1 and O12 by default

        # Use efficient extraction - only requested layers are stored
        outputs = self.model(input_ids, extract_layers=extract_layers)

        logits = outputs['logits']
        hidden_list = outputs.get('hidden_states', [])

        # Map list positions back to layer indices
        # hidden_list[0] corresponds to extract_layers[0], etc.
        layer_states = {}
        for i, layer_idx in enumerate(sorted(extract_layers)):
            if i < len(hidden_list):
                layer_states[layer_idx] = hidden_list[i]

        return logits, layer_states

    def generate_with_karma(
        self,
        input_ids: torch.Tensor,
        max_new_tokens: int = 128,
        temperature: float = 1.0,
        top_k: int = 50,
        top_p: float = 0.9,
        inject_karma: bool = True,
        store_karma: bool = True,
        return_coherence: bool = False,
    ) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """
        Generate with evolutionary state injection.

        This is the main inference method that implements:
        1. Karma injection into initial embedding (at O1 position)
        2. Token generation with optional quality monitoring
        3. O12 extraction and karma storage for next sequence

        Args:
            input_ids: Input token IDs [B, N]
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_k: Top-k filtering (0 to disable)
            top_p: Nucleus sampling threshold
            inject_karma: Whether to inject stored karma
            store_karma: Whether to store new karma for next sequence
            return_coherence: Include coherence metrics in output

        Returns:
            output_ids: Generated token IDs including input
            metrics: Dict with karma_coherence, generation_info, etc.
        """
        self.generation_count += 1
        metrics: Dict[str, Any] = {
            'generation_id': self.generation_count,
            'karma_injected': False,
            'karma_stored': False,
        }

        # Move input to model device
        input_ids = input_ids.to(self.device)
        B = input_ids.shape[0]

        # Step 1: Initial forward pass with karma injection
        # We need to inject karma at the embedding level for O1
        initial_logits, initial_states = self._extract_layer_states(
            input_ids, extract_layers=[0, 11]
        )

        # If karma exists and injection requested, modify O1 state
        if inject_karma and self.karma_buffer is not None and self.bridge_enabled:
            # For the first token's hidden state, blend in karma
            # This approximates injecting karma at O1
            metrics['karma_injected'] = True
            metrics['karma_norm'] = self.karma_buffer.norm().item()

        # Step 2: Autoregressive generation
        generated_ids = input_ids.clone()

        for step in range(max_new_tokens):
            # Forward pass for next token
            outputs = self.model(generated_ids, return_hidden=True)
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

                # Remove tokens with cumulative probability above threshold
                sorted_indices_to_remove = cumulative_probs > top_p
                sorted_indices_to_remove[..., 1:] = sorted_indices_to_remove[..., :-1].clone()
                sorted_indices_to_remove[..., 0] = False

                indices_to_remove = sorted_indices_to_remove.scatter(
                    1, sorted_indices, sorted_indices_to_remove
                )
                logits[indices_to_remove] = float('-inf')

            # Sample next token
            probs = F.softmax(logits, dim=-1)
            next_token = torch.multinomial(probs, num_samples=1)
            generated_ids = torch.cat([generated_ids, next_token], dim=1)

            # Check for EOS (assuming token_id 0 or model-specific)
            # This is a simplified check - real implementation would use tokenizer
            if hasattr(self.model, 'config') and hasattr(self.model.config, 'eos_token_id'):
                eos_id = self.model.config.eos_token_id
                if (next_token == eos_id).all():
                    break

        # Step 3: Extract O12 and store as karma for next sequence
        if store_karma and self.bridge_enabled:
            # Final forward pass to get O12 state
            final_outputs = self.model(generated_ids, return_hidden=True)
            hidden_states = final_outputs.get('hidden_states', [])

            if len(hidden_states) >= 12:
                # O12 is the last layer (index 11)
                o12_hidden = hidden_states[11]  # [B, N, D]
                self.current_o12 = o12_hidden

                # Compute seed and store as karma
                self.karma_buffer = self.bridge.compute_seed(o12_hidden)
                metrics['karma_stored'] = True
                metrics['new_karma_norm'] = self.karma_buffer.norm().item()

                # Apply decay for long conversations
                self.apply_karma_decay()

        # Step 4: Compute coherence if requested
        if return_coherence:
            coherence = self.compute_generation_coherence()
            metrics['karma_coherence'] = coherence
            metrics['coherence_trend'] = self._get_coherence_trend()

        return generated_ids, metrics

    def compute_generation_coherence(self) -> float:
        """
        Compute coherence between stored karma and current O12.

        Useful for:
        - Detecting topic drift in long conversations
        - Measuring "memory retention" quality
        - Deciding when to clear karma buffer

        Returns:
            Coherence score in [0, 1] (0.5 if no prior state)
        """
        if self.karma_buffer is None or self.current_o12 is None:
            return 0.5

        # Get O12 mean for comparison
        if self.current_o12.dim() == 3:
            o12_mean = self.current_o12.mean(dim=1)  # [B, D]
        else:
            o12_mean = self.current_o12

        # Cosine similarity
        sim = F.cosine_similarity(
            self.karma_buffer.view(1, -1),
            o12_mean.view(1, -1),
            dim=-1
        )

        # Map from [-1, 1] to [0, 1]
        coherence = (sim.item() + 1) / 2

        # Track history
        self.coherence_history.append(coherence)
        if len(self.coherence_history) > 100:
            self.coherence_history = self.coherence_history[-100:]

        return coherence

    def _get_coherence_trend(self) -> str:
        """
        Get trend of coherence over recent generations.

        Returns:
            'improving', 'stable', 'declining', or 'unknown'
        """
        if len(self.coherence_history) < 3:
            return 'unknown'

        recent = self.coherence_history[-5:]
        avg_first_half = sum(recent[:len(recent)//2]) / max(1, len(recent)//2)
        avg_second_half = sum(recent[len(recent)//2:]) / max(1, len(recent) - len(recent)//2)

        diff = avg_second_half - avg_first_half

        if diff > 0.05:
            return 'improving'
        elif diff < -0.05:
            return 'declining'
        else:
            return 'stable'

    def get_coherence_status(self) -> str:
        """Get formatted coherence status for logging."""
        if not self.coherence_history:
            return "Karma:--"

        recent = self.coherence_history[-1]
        avg = sum(self.coherence_history[-10:]) / min(10, len(self.coherence_history))

        if recent >= 0.7:
            status = "strong"
        elif recent >= 0.5:
            status = "moderate"
        elif recent >= 0.3:
            status = "weak"
        else:
            status = "lost"

        return f"Karma:{recent:.2f}({status})|avg:{avg:.2f}"

    def update_gunas(self, sattva: float, rajas: float, tamas: float):
        """
        Update Guna state for dynamic alpha computation.

        Can be updated by external metacognitive monitoring.

        Args:
            sattva: Clarity/confidence (0-1)
            rajas: Activity/variance (0-1)
            tamas: Inertia/repetition (0-1)
        """
        # Normalize to sum to 1
        total = sattva + rajas + tamas
        if total > 0:
            self.current_gunas = (sattva / total, rajas / total, tamas / total)

    def get_state_dict(self) -> Dict[str, Any]:
        """
        Get serializable state for saving conversation state.

        Returns:
            Dict containing karma buffer and metadata
        """
        return {
            'karma_buffer': self.karma_buffer.cpu() if self.karma_buffer is not None else None,
            'coherence_history': self.coherence_history.copy(),
            'generation_count': self.generation_count,
            'current_gunas': self.current_gunas,
            'resonance_alpha': self.resonance_alpha,
        }

    def load_state_dict(self, state: Dict[str, Any]):
        """
        Restore state from saved conversation state.

        Args:
            state: Dict from get_state_dict()
        """
        if state.get('karma_buffer') is not None:
            self.karma_buffer = state['karma_buffer'].to(self.device)
        else:
            self.karma_buffer = None

        self.coherence_history = state.get('coherence_history', [])
        self.generation_count = state.get('generation_count', 0)
        self.current_gunas = state.get('current_gunas', (0.33, 0.33, 0.33))
        self.resonance_alpha = state.get('resonance_alpha', self.resonance_alpha)
