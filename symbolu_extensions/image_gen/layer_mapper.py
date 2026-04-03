#!/usr/bin/env python3
"""
Layer Mapper: FLUX Blocks to Symbol-U 12-Layer Ontological Mapping
===================================================================

Maps FLUX.1 transformer blocks to Symbol-U's 12 ontological layers.

FLUX Architecture:
- 19 Double Transformer Blocks (joint text-image attention)
- 38 Single Transformer Blocks (image-only attention)
- Total: 57 blocks + input/output layers

12-Layer Mapping:
- L1 (Potential):    Noise prior + T5 latent space
- L2 (Identity):     Double Blocks 0-2
- L3 (Execution):    Double Blocks 3-5
- L4 (Structure):    Double Blocks 6-8
- L5 (Cognition):    Double Blocks 9-11
- L6 (Agency):       Double Blocks 12-14
- L7 (Reasoning):    Double Blocks 15-18
- L8 (Purpose):      Single Blocks 0-9
- L9 (Witnesses):    Single Blocks 10-19
- L10 (Unifying):    Single Blocks 20-29
- L11 (Integration): Single Blocks 30-37
- L12 (Absolving):   Final Norm + VAE Decoder

Usage:
------
    from symbolu_extensions.image_gen.layer_mapper import LayerMapper, LAYER_CONFIG

    mapper = LayerMapper()

    # Get layer for a specific block
    layer = mapper.get_layer_for_double_block(5)  # Returns 3 (Execution)

    # Extract layer states from hidden states
    layer_states = mapper.extract_all_layer_states(
        double_hidden_states,
        single_hidden_states,
        initial_latents,
        final_latents,
    )
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any, Union
from enum import IntEnum

try:
    import torch
    import torch.nn as nn
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False
    torch = None

import numpy as np

from symbolu_extensions.image_gen.config import LayerMappingConfig


# =============================================================================
# LAYER DEFINITIONS
# =============================================================================

class OntologicalLayer(IntEnum):
    """Symbol-U's 12 ontological layers."""
    POTENTIAL = 1     # Dormant - latent capacity
    IDENTITY = 2      # Tagging - entity emergence
    EXECUTION = 3     # Action - active transformation
    STRUCTURE = 4     # Forming - spatial layout
    COGNITION = 5     # Perception - feature recognition
    AGENCY = 6        # Direction - guidance integration
    REASONING = 7     # Discrimination - semantic discrimination
    PURPOSE = 8       # Meaning - meaning refinement
    WITNESSES = 9     # Meta-Observation - quality self-check
    UNIFYING = 10     # Coherence - cross-layer binding
    INTEGRATION = 11  # Resolution - final synthesis
    ABSOLVING = 12    # Termination - completion release


# Layer names for display
LAYER_NAMES: Dict[int, str] = {
    1: "Potential",
    2: "Identity",
    3: "Execution",
    4: "Structure",
    5: "Cognition",
    6: "Agency",
    7: "Reasoning",
    8: "Purpose",
    9: "Witnesses",
    10: "Unifying",
    11: "Integration",
    12: "Absolving",
}

# Layer Bhava (character/function)
LAYER_BHAVA: Dict[int, str] = {
    1: "Dormant",
    2: "Tagging",
    3: "Action",
    4: "Forming",
    5: "Perception",
    6: "Direction",
    7: "Discrimination",
    8: "Meaning",
    9: "Meta-Observation",
    10: "Coherence",
    11: "Resolution",
    12: "Termination",
}


# =============================================================================
# LAYER CONFIGURATION
# =============================================================================

@dataclass
class LayerBlockMapping:
    """Mapping of a single layer to FLUX blocks."""
    layer_index: int
    layer_name: str
    bhava: str
    block_type: str  # "input", "double", "single", "output"
    block_range: Optional[Tuple[int, int]]  # (start, end) for ranges
    description: str


# Complete layer configuration matching design document
LAYER_CONFIG: Dict[int, LayerBlockMapping] = {
    1: LayerBlockMapping(
        layer_index=1,
        layer_name="Potential",
        bhava="Dormant",
        block_type="input",
        block_range=None,
        description="Noise prior z_T ~ N(0,I) + T5 latent space"
    ),
    2: LayerBlockMapping(
        layer_index=2,
        layer_name="Identity",
        bhava="Tagging",
        block_type="double",
        block_range=(0, 3),
        description="Entity emergence from noise (Double Blocks 0-2)"
    ),
    3: LayerBlockMapping(
        layer_index=3,
        layer_name="Execution",
        bhava="Action",
        block_type="double",
        block_range=(3, 6),
        description="Active denoising transformation (Double Blocks 3-5)"
    ),
    4: LayerBlockMapping(
        layer_index=4,
        layer_name="Structure",
        bhava="Forming",
        block_type="double",
        block_range=(6, 9),
        description="Spatial layout crystallization (Double Blocks 6-8)"
    ),
    5: LayerBlockMapping(
        layer_index=5,
        layer_name="Cognition",
        bhava="Perception",
        block_type="double",
        block_range=(9, 12),
        description="Object/scene recognition (Double Blocks 9-11)"
    ),
    6: LayerBlockMapping(
        layer_index=6,
        layer_name="Agency",
        bhava="Direction",
        block_type="double",
        block_range=(12, 15),
        description="Guidance integration (Double Blocks 12-14)"
    ),
    7: LayerBlockMapping(
        layer_index=7,
        layer_name="Reasoning",
        bhava="Discrimination",
        block_type="double",
        block_range=(15, 19),
        description="Style/content/attribute discrimination (Double Blocks 15-18)"
    ),
    8: LayerBlockMapping(
        layer_index=8,
        layer_name="Purpose",
        bhava="Meaning",
        block_type="single",
        block_range=(0, 10),
        description="Semantic grounding (Single Blocks 0-9)"
    ),
    9: LayerBlockMapping(
        layer_index=9,
        layer_name="Witnesses",
        bhava="Meta-Observation",
        block_type="single",
        block_range=(10, 20),
        description="Self-quality assessment (Single Blocks 10-19)"
    ),
    10: LayerBlockMapping(
        layer_index=10,
        layer_name="Unifying",
        bhava="Coherence",
        block_type="single",
        block_range=(20, 30),
        description="Cross-layer binding (Single Blocks 20-29)"
    ),
    11: LayerBlockMapping(
        layer_index=11,
        layer_name="Integration",
        bhava="Resolution",
        block_type="single",
        block_range=(30, 38),
        description="Conflict resolution, final synthesis (Single Blocks 30-37)"
    ),
    12: LayerBlockMapping(
        layer_index=12,
        layer_name="Absolving",
        bhava="Termination",
        block_type="output",
        block_range=None,
        description="Final Layer Norm + VAE Decode"
    ),
}


# =============================================================================
# LAYER MAPPER
# =============================================================================

class LayerMapper:
    """
    Maps FLUX transformer blocks to Symbol-U's 12 ontological layers.

    This is the core component that enables coherence monitoring during
    the diffusion process by identifying which ontological layer is
    active at each transformer block.
    """

    def __init__(self, config: Optional[LayerMappingConfig] = None):
        """
        Initialize the layer mapper.

        Args:
            config: Optional configuration override
        """
        self.config = config or LayerMappingConfig()
        self._build_block_to_layer_maps()

    def _build_block_to_layer_maps(self) -> None:
        """Build reverse mappings from block indices to layer numbers."""
        # Double block to layer mapping
        self._double_block_to_layer: Dict[int, int] = {}
        for block_idx in range(19):  # 19 double blocks
            if block_idx < 3:
                self._double_block_to_layer[block_idx] = 2  # Identity
            elif block_idx < 6:
                self._double_block_to_layer[block_idx] = 3  # Execution
            elif block_idx < 9:
                self._double_block_to_layer[block_idx] = 4  # Structure
            elif block_idx < 12:
                self._double_block_to_layer[block_idx] = 5  # Cognition
            elif block_idx < 15:
                self._double_block_to_layer[block_idx] = 6  # Agency
            else:
                self._double_block_to_layer[block_idx] = 7  # Reasoning

        # Single block to layer mapping
        self._single_block_to_layer: Dict[int, int] = {}
        for block_idx in range(38):  # 38 single blocks
            if block_idx < 10:
                self._single_block_to_layer[block_idx] = 8   # Purpose
            elif block_idx < 20:
                self._single_block_to_layer[block_idx] = 9   # Witnesses
            elif block_idx < 30:
                self._single_block_to_layer[block_idx] = 10  # Unifying
            else:
                self._single_block_to_layer[block_idx] = 11  # Integration

    def get_layer_for_double_block(self, block_idx: int) -> int:
        """
        Get the ontological layer for a double transformer block.

        Args:
            block_idx: Double block index (0-18)

        Returns:
            Layer number (2-7)
        """
        if block_idx < 0 or block_idx >= 19:
            raise ValueError(f"Double block index must be 0-18, got {block_idx}")
        return self._double_block_to_layer[block_idx]

    def get_layer_for_single_block(self, block_idx: int) -> int:
        """
        Get the ontological layer for a single transformer block.

        Args:
            block_idx: Single block index (0-37)

        Returns:
            Layer number (8-11)
        """
        if block_idx < 0 or block_idx >= 38:
            raise ValueError(f"Single block index must be 0-37, got {block_idx}")
        return self._single_block_to_layer[block_idx]

    def get_blocks_for_layer(self, layer_idx: int) -> Tuple[str, Optional[range]]:
        """
        Get the FLUX blocks for a given ontological layer.

        Args:
            layer_idx: Layer number (1-12)

        Returns:
            Tuple of (block_type, block_range)
        """
        if layer_idx < 1 or layer_idx > 12:
            raise ValueError(f"Layer index must be 1-12, got {layer_idx}")

        mapping = LAYER_CONFIG[layer_idx]
        if mapping.block_range is None:
            return mapping.block_type, None
        else:
            return mapping.block_type, range(*mapping.block_range)

    def get_layer_info(self, layer_idx: int) -> LayerBlockMapping:
        """Get full layer information."""
        if layer_idx < 1 or layer_idx > 12:
            raise ValueError(f"Layer index must be 1-12, got {layer_idx}")
        return LAYER_CONFIG[layer_idx]

    def timestep_to_layer(
        self,
        timestep: Union[int, float],
        num_timesteps: int = 28,
    ) -> int:
        """
        Map a diffusion timestep to the current ontological layer.

        Early timesteps (high noise) map to lower layers.
        Late timesteps (low noise) map to higher layers.

        Args:
            timestep: Current timestep (0 = end, num_timesteps = start)
            num_timesteps: Total number of inference steps

        Returns:
            Layer number (1-12)
        """
        # Normalize timestep to [0, 1] where 0 = start, 1 = end
        progress = 1.0 - (float(timestep) / num_timesteps)

        # Map progress to layers
        # Early (high noise): L1-L7 (potential through reasoning)
        # Late (low noise): L8-L12 (purpose through absolving)
        if progress < 0.1:
            return 1  # Potential
        elif progress < 0.2:
            return 2  # Identity
        elif progress < 0.3:
            return 3  # Execution
        elif progress < 0.4:
            return 4  # Structure
        elif progress < 0.5:
            return 5  # Cognition
        elif progress < 0.6:
            return 6  # Agency
        elif progress < 0.7:
            return 7  # Reasoning
        elif progress < 0.8:
            return 8  # Purpose
        elif progress < 0.85:
            return 9  # Witnesses
        elif progress < 0.9:
            return 10  # Unifying
        elif progress < 0.95:
            return 11  # Integration
        else:
            return 12  # Absolving

    def extract_layer_state(
        self,
        hidden_states: List[Any],
        layer_idx: int,
        block_type: str = "double",
    ) -> Any:
        """
        Extract hidden states for a specific Symbol-U layer.

        Args:
            hidden_states: List of hidden states from transformer blocks
            layer_idx: Layer number (1-12)
            block_type: "double" or "single"

        Returns:
            Aggregated hidden state for the layer
        """
        mapping = LAYER_CONFIG[layer_idx]

        if mapping.block_type == "input":
            # Return first hidden state
            return hidden_states[0] if hidden_states else None

        if mapping.block_type == "output":
            # Return last hidden state
            return hidden_states[-1] if hidden_states else None

        if mapping.block_range is None:
            return None

        # Get block indices for this layer
        start, end = mapping.block_range
        if mapping.block_type != block_type:
            return None

        # Extract and aggregate
        if PYTORCH_AVAILABLE and torch is not None:
            layer_states = [hidden_states[i] for i in range(start, min(end, len(hidden_states)))]
            if not layer_states:
                return None
            return torch.stack(layer_states).mean(dim=0)
        else:
            # NumPy fallback
            layer_states = [hidden_states[i] for i in range(start, min(end, len(hidden_states)))]
            if not layer_states:
                return None
            return np.stack(layer_states).mean(axis=0)

    def extract_all_layer_states(
        self,
        double_hidden_states: List[Any],
        single_hidden_states: List[Any],
        initial_latents: Optional[Any] = None,
        final_latents: Optional[Any] = None,
    ) -> Dict[int, Any]:
        """
        Extract states for all 12 ontological layers.

        Args:
            double_hidden_states: Hidden states from double blocks (19 items)
            single_hidden_states: Hidden states from single blocks (38 items)
            initial_latents: Initial noise latents for L1
            final_latents: Final latents for L12

        Returns:
            Dictionary mapping layer index to hidden state
        """
        layer_states: Dict[int, Any] = {}

        # L1: Potential (input)
        if initial_latents is not None:
            layer_states[1] = initial_latents

        # L2-L7: Double block layers
        for layer_idx in range(2, 8):
            state = self.extract_layer_state(
                double_hidden_states, layer_idx, "double"
            )
            if state is not None:
                layer_states[layer_idx] = state

        # L8-L11: Single block layers
        for layer_idx in range(8, 12):
            state = self.extract_layer_state(
                single_hidden_states, layer_idx, "single"
            )
            if state is not None:
                layer_states[layer_idx] = state

        # L12: Absolving (output)
        if final_latents is not None:
            layer_states[12] = final_latents

        return layer_states

    def get_layer_summary(self) -> str:
        """Get a summary of all layer mappings."""
        lines = ["Symbol-U 12-Layer to FLUX Block Mapping", "=" * 50]

        for layer_idx in range(1, 13):
            mapping = LAYER_CONFIG[layer_idx]
            if mapping.block_range:
                blocks = f"{mapping.block_type} blocks {mapping.block_range[0]}-{mapping.block_range[1]-1}"
            else:
                blocks = mapping.block_type
            lines.append(
                f"L{layer_idx:2d} ({mapping.layer_name:12s}): {blocks:25s} - {mapping.bhava}"
            )

        return "\n".join(lines)


# =============================================================================
# LAYER STATE CONTAINER
# =============================================================================

@dataclass
class LayerState:
    """Container for a layer's state during generation."""
    layer_index: int
    layer_name: str
    hidden_state: Optional[Any]  # torch.Tensor or np.ndarray
    timestep: int
    block_indices: Optional[List[int]]  # Which blocks contributed

    # Computed metrics
    mean_activation: Optional[float] = None
    std_activation: Optional[float] = None
    entropy: Optional[float] = None


@dataclass
class GenerationLayerStates:
    """Container for all layer states during a generation."""
    states: Dict[int, LayerState]
    num_timesteps: int
    current_timestep: int

    def get_state(self, layer_idx: int) -> Optional[LayerState]:
        """Get state for a specific layer."""
        return self.states.get(layer_idx)

    def get_active_layers(self) -> List[int]:
        """Get list of layers with active states."""
        return [idx for idx, state in self.states.items() if state.hidden_state is not None]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "num_timesteps": self.num_timesteps,
            "current_timestep": self.current_timestep,
            "active_layers": self.get_active_layers(),
            "layer_activations": {
                idx: state.mean_activation
                for idx, state in self.states.items()
                if state.mean_activation is not None
            },
        }


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_layer_name(layer_idx: int) -> str:
    """Get the name of a layer by index."""
    return LAYER_NAMES.get(layer_idx, f"Unknown({layer_idx})")


def get_layer_bhava(layer_idx: int) -> str:
    """Get the Bhava (character) of a layer by index."""
    return LAYER_BHAVA.get(layer_idx, f"Unknown({layer_idx})")


def create_default_layer_mapper() -> LayerMapper:
    """Create a layer mapper with default configuration."""
    return LayerMapper()


# Module-level convenience instance
_default_mapper: Optional[LayerMapper] = None


def get_default_mapper() -> LayerMapper:
    """Get or create the default layer mapper instance."""
    global _default_mapper
    if _default_mapper is None:
        _default_mapper = LayerMapper()
    return _default_mapper
