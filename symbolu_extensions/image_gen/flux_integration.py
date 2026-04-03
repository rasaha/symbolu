#!/usr/bin/env python3
"""
FLUX Integration: Symbol-U Integration with FLUX Diffusion Models
===================================================================

Wraps FLUX.1 models (dev/schnell/pro) with Symbol-U layer hooks for:
1. Capturing hidden states at each transformer block
2. Mapping FLUX blocks to Symbol-U 12-layer ontology
3. Applying coherence-guided modifications during denoising
4. Extracting attention maps for analysis

Architecture:
    FLUX.1 has 19 double transformer blocks + 38 single transformer blocks.
    These map to Symbol-U layers 2-11 (L1 is latent init, L12 is output).

Usage:
------
    from symbolu_extensions.image_gen.flux_integration import SymbolUFluxWrapper

    # Wrap a FLUX pipeline
    wrapper = SymbolUFluxWrapper.from_pretrained("black-forest-labs/FLUX.1-dev")

    # Generate with layer state capture
    result = wrapper.generate(
        prompt="A beautiful sunset over mountains",
        capture_states=True,
    )

    # Access layer states
    layer_states = result.layer_states
    attention_maps = result.attention_maps
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Callable, Union
from contextlib import contextmanager
import logging

try:
    import torch
    import torch.nn as nn
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False
    torch = None
    nn = None

import numpy as np

from symbolu_extensions.image_gen.config import FluxConfig, ImageGenConfig, FluxVariant
from symbolu_extensions.image_gen.layer_mapper import (
    LayerMapper,
    OntologicalLayer,
    LAYER_NAMES,
)

logger = logging.getLogger(__name__)


# =============================================================================
# RESULT DATACLASSES
# =============================================================================

@dataclass
class FluxLayerCapture:
    """Captured state from a FLUX transformer block."""
    block_type: str  # "double" or "single"
    block_index: int
    layer_index: int  # Mapped Symbol-U layer (1-12)
    layer_name: str
    hidden_state: Any  # Captured tensor
    attention_weights: Optional[Any] = None


@dataclass
class FluxGenerationState:
    """Complete state during FLUX generation."""
    timestep: int
    total_timesteps: int
    latents: Any
    prompt_embeds: Any
    pooled_prompt_embeds: Optional[Any]

    # Captured layer states per block
    double_block_states: Dict[int, FluxLayerCapture]
    single_block_states: Dict[int, FluxLayerCapture]

    def get_layer_states(self) -> Dict[int, Any]:
        """Get consolidated layer states keyed by layer index."""
        states = {}

        # Aggregate from double blocks (layers 2-7)
        for block_idx, capture in self.double_block_states.items():
            layer_idx = capture.layer_index
            if layer_idx not in states:
                states[layer_idx] = capture.hidden_state
            # If multiple blocks map to same layer, average them
            elif PYTORCH_AVAILABLE and isinstance(states[layer_idx], torch.Tensor):
                states[layer_idx] = (states[layer_idx] + capture.hidden_state) / 2

        # Aggregate from single blocks (layers 8-11)
        for block_idx, capture in self.single_block_states.items():
            layer_idx = capture.layer_index
            if layer_idx not in states:
                states[layer_idx] = capture.hidden_state
            elif PYTORCH_AVAILABLE and isinstance(states[layer_idx], torch.Tensor):
                states[layer_idx] = (states[layer_idx] + capture.hidden_state) / 2

        return states


@dataclass
class FluxGenerationResult:
    """Result from FLUX generation with Symbol-U integration."""
    images: List[Any]  # PIL images or tensors
    latents: Any
    seed: int

    # Symbol-U layer data
    layer_states: Dict[int, Any]
    attention_maps: Optional[Dict[str, Any]]

    # Timing
    inference_time_ms: float
    timesteps_captured: int


# =============================================================================
# BLOCK HOOKS
# =============================================================================

class BlockHook:
    """Hook for capturing FLUX transformer block outputs."""

    def __init__(
        self,
        block_type: str,
        block_index: int,
        layer_mapper: LayerMapper,
        capture_attention: bool = False,
    ):
        self.block_type = block_type
        self.block_index = block_index
        self.layer_mapper = layer_mapper
        self.capture_attention = capture_attention

        # Mapped layer
        if block_type == "double":
            self.layer_index = layer_mapper.get_layer_for_double_block(block_index)
        else:
            self.layer_index = layer_mapper.get_layer_for_single_block(block_index)

        self.layer_name = LAYER_NAMES.get(self.layer_index, f"Layer{self.layer_index}")

        # Captured state
        self.captured_state: Optional[Any] = None
        self.captured_attention: Optional[Any] = None

    def __call__(self, module: Any, input: Any, output: Any) -> None:
        """Hook callback - captures block output."""
        if isinstance(output, tuple):
            hidden_state = output[0]
            attention = output[1] if len(output) > 1 and self.capture_attention else None
        else:
            hidden_state = output
            attention = None

        # Detach to avoid memory issues
        if PYTORCH_AVAILABLE and isinstance(hidden_state, torch.Tensor):
            self.captured_state = hidden_state.detach().clone()
            if attention is not None and isinstance(attention, torch.Tensor):
                self.captured_attention = attention.detach().clone()
        else:
            self.captured_state = hidden_state

    def get_capture(self) -> FluxLayerCapture:
        """Get captured data as FluxLayerCapture."""
        return FluxLayerCapture(
            block_type=self.block_type,
            block_index=self.block_index,
            layer_index=self.layer_index,
            layer_name=self.layer_name,
            hidden_state=self.captured_state,
            attention_weights=self.captured_attention,
        )

    def reset(self) -> None:
        """Clear captured state."""
        self.captured_state = None
        self.captured_attention = None


class ModificationHook:
    """Hook for modifying FLUX block outputs based on coherence."""

    def __init__(
        self,
        block_type: str,
        block_index: int,
        modification_fn: Optional[Callable] = None,
    ):
        self.block_type = block_type
        self.block_index = block_index
        self.modification_fn = modification_fn
        self.enabled = True

    def __call__(self, module: Any, input: Any, output: Any) -> Any:
        """Hook callback - modifies block output."""
        if not self.enabled or self.modification_fn is None:
            return output

        if isinstance(output, tuple):
            hidden_state = output[0]
            modified = self.modification_fn(hidden_state, self.block_index)
            return (modified,) + output[1:]
        else:
            return self.modification_fn(output, self.block_index)


# =============================================================================
# FLUX WRAPPER
# =============================================================================

class SymbolUFluxWrapper:
    """
    Wrapper for FLUX pipelines with Symbol-U integration.

    Provides:
    1. Layer state capture during generation
    2. Block-to-layer mapping
    3. Coherence-guided modifications (optional)
    4. Attention map extraction
    """

    def __init__(
        self,
        pipeline: Any,
        config: Optional[FluxConfig] = None,
    ):
        """
        Initialize wrapper around a FLUX pipeline.

        Args:
            pipeline: A diffusers FluxPipeline instance
            config: FLUX configuration
        """
        self.pipeline = pipeline
        self.config = config or FluxConfig()
        self.layer_mapper = LayerMapper()

        # Hooks
        self._capture_hooks: List[Tuple[Any, BlockHook]] = []
        self._mod_hooks: List[Tuple[Any, ModificationHook]] = []
        self._hooks_registered = False

        # State during generation
        self._current_timestep = 0
        self._timestep_states: List[FluxGenerationState] = []

    @classmethod
    def from_pretrained(
        cls,
        model_id: str = "black-forest-labs/FLUX.1-dev",
        config: Optional[FluxConfig] = None,
        **kwargs,
    ) -> "SymbolUFluxWrapper":
        """
        Load FLUX pipeline and wrap it.

        Args:
            model_id: HuggingFace model ID
            config: Optional FLUX config
            **kwargs: Passed to FluxPipeline.from_pretrained

        Returns:
            SymbolUFluxWrapper instance
        """
        try:
            from diffusers import FluxPipeline
        except ImportError:
            raise ImportError(
                "diffusers is required for FLUX integration. "
                "Install with: pip install diffusers"
            )

        if config is None:
            config = FluxConfig(model_id=model_id)

        # Determine dtype
        dtype_map = {
            "float16": torch.float16 if PYTORCH_AVAILABLE else None,
            "bfloat16": torch.bfloat16 if PYTORCH_AVAILABLE else None,
            "float32": torch.float32 if PYTORCH_AVAILABLE else None,
        }
        torch_dtype = dtype_map.get(config.torch_dtype)

        # Load pipeline
        pipeline = FluxPipeline.from_pretrained(
            model_id,
            torch_dtype=torch_dtype,
            **kwargs,
        )

        # Apply offloading if configured
        if config.enable_model_cpu_offload:
            pipeline.enable_model_cpu_offload()
        elif config.enable_sequential_cpu_offload:
            pipeline.enable_sequential_cpu_offload()
        else:
            pipeline = pipeline.to(config.device)

        if config.enable_attention_slicing:
            pipeline.enable_attention_slicing()

        if config.vae_slicing:
            pipeline.enable_vae_slicing()

        return cls(pipeline, config)

    # =========================================================================
    # HOOK MANAGEMENT
    # =========================================================================

    def _register_capture_hooks(self, capture_attention: bool = False) -> None:
        """Register forward hooks to capture block outputs."""
        if self._hooks_registered:
            return

        transformer = self._get_transformer()
        if transformer is None:
            logger.warning("Could not find FLUX transformer for hook registration")
            return

        # Hook double blocks
        if hasattr(transformer, 'transformer_blocks'):
            for idx, block in enumerate(transformer.transformer_blocks):
                hook = BlockHook("double", idx, self.layer_mapper, capture_attention)
                handle = block.register_forward_hook(hook)
                self._capture_hooks.append((handle, hook))

        # Hook single blocks
        if hasattr(transformer, 'single_transformer_blocks'):
            for idx, block in enumerate(transformer.single_transformer_blocks):
                hook = BlockHook("single", idx, self.layer_mapper, capture_attention)
                handle = block.register_forward_hook(hook)
                self._capture_hooks.append((handle, hook))

        self._hooks_registered = True
        logger.debug(f"Registered {len(self._capture_hooks)} capture hooks")

    def _unregister_hooks(self) -> None:
        """Remove all registered hooks."""
        for handle, hook in self._capture_hooks:
            handle.remove()
        self._capture_hooks.clear()

        for handle, hook in self._mod_hooks:
            handle.remove()
        self._mod_hooks.clear()

        self._hooks_registered = False

    def _get_transformer(self) -> Optional[Any]:
        """Get the transformer module from the pipeline."""
        if hasattr(self.pipeline, 'transformer'):
            return self.pipeline.transformer
        return None

    def _collect_captures(self) -> Tuple[Dict[int, FluxLayerCapture], Dict[int, FluxLayerCapture]]:
        """Collect captured states from all hooks."""
        double_states = {}
        single_states = {}

        for handle, hook in self._capture_hooks:
            if hook.captured_state is not None:
                capture = hook.get_capture()
                if hook.block_type == "double":
                    double_states[hook.block_index] = capture
                else:
                    single_states[hook.block_index] = capture

        return double_states, single_states

    def _reset_captures(self) -> None:
        """Reset all hook captures."""
        for handle, hook in self._capture_hooks:
            hook.reset()

    @contextmanager
    def capture_context(self, capture_attention: bool = False):
        """Context manager for capture hooks."""
        try:
            self._register_capture_hooks(capture_attention)
            yield
        finally:
            self._unregister_hooks()

    # =========================================================================
    # GENERATION
    # =========================================================================

    def generate(
        self,
        prompt: str,
        prompt_2: Optional[str] = None,
        height: int = 1024,
        width: int = 1024,
        num_inference_steps: int = 28,
        guidance_scale: float = 3.5,
        num_images_per_prompt: int = 1,
        generator: Optional[Any] = None,
        seed: Optional[int] = None,
        capture_states: bool = True,
        capture_attention: bool = False,
        capture_every_n_steps: int = 1,
        output_type: str = "pil",
        **kwargs,
    ) -> FluxGenerationResult:
        """
        Generate images with optional layer state capture.

        Args:
            prompt: Text prompt
            prompt_2: Optional second prompt for T5
            height: Output height
            width: Output width
            num_inference_steps: Number of denoising steps
            guidance_scale: Classifier-free guidance scale
            num_images_per_prompt: Batch size
            generator: Optional torch generator
            seed: Random seed (creates generator if not provided)
            capture_states: Whether to capture layer states
            capture_attention: Whether to capture attention maps
            capture_every_n_steps: Capture frequency
            output_type: "pil", "latent", "pt"
            **kwargs: Passed to pipeline

        Returns:
            FluxGenerationResult with images and layer data
        """
        import time

        start_time = time.time()

        # Setup generator
        if generator is None and seed is not None:
            if PYTORCH_AVAILABLE:
                generator = torch.Generator(device=self.config.device).manual_seed(seed)

        if seed is None and generator is not None:
            seed = generator.initial_seed()
        elif seed is None:
            seed = np.random.randint(0, 2**32 - 1)

        # Reset state
        self._timestep_states.clear()
        self._current_timestep = 0

        # Setup callback for timestep capture
        captured_latents = []
        captured_layer_states = {}

        def timestep_callback(pipe, step_idx, timestep, callback_kwargs):
            nonlocal captured_layer_states

            if capture_states and step_idx % capture_every_n_steps == 0:
                # Collect captures from hooks
                double_states, single_states = self._collect_captures()

                # Create generation state
                state = FluxGenerationState(
                    timestep=step_idx,
                    total_timesteps=num_inference_steps,
                    latents=callback_kwargs.get("latents"),
                    prompt_embeds=callback_kwargs.get("prompt_embeds"),
                    pooled_prompt_embeds=callback_kwargs.get("pooled_prompt_embeds"),
                    double_block_states=double_states,
                    single_block_states=single_states,
                )

                self._timestep_states.append(state)

                # Update layer states with latest
                captured_layer_states = state.get_layer_states()

                self._reset_captures()

            self._current_timestep = step_idx
            return callback_kwargs

        # Run generation
        try:
            if capture_states:
                self._register_capture_hooks(capture_attention)

            output = self.pipeline(
                prompt=prompt,
                prompt_2=prompt_2,
                height=height,
                width=width,
                num_inference_steps=num_inference_steps,
                guidance_scale=guidance_scale,
                num_images_per_prompt=num_images_per_prompt,
                generator=generator,
                output_type=output_type,
                callback_on_step_end=timestep_callback if capture_states else None,
                **kwargs,
            )

        finally:
            self._unregister_hooks()

        # Process output
        if output_type == "pil":
            images = output.images
            latents = None
        elif output_type == "latent":
            images = []
            latents = output.images  # Actually latents
        else:
            images = output.images
            latents = None

        # Extract attention maps if captured
        attention_maps = None
        if capture_attention and self._timestep_states:
            attention_maps = {}
            for state in self._timestep_states:
                for block_idx, capture in state.double_block_states.items():
                    if capture.attention_weights is not None:
                        key = f"double_{block_idx}_t{state.timestep}"
                        attention_maps[key] = capture.attention_weights

        inference_time = (time.time() - start_time) * 1000

        return FluxGenerationResult(
            images=images,
            latents=latents,
            seed=seed,
            layer_states=captured_layer_states,
            attention_maps=attention_maps,
            inference_time_ms=inference_time,
            timesteps_captured=len(self._timestep_states),
        )

    def get_timestep_states(self) -> List[FluxGenerationState]:
        """Get all captured timestep states."""
        return self._timestep_states

    # =========================================================================
    # UTILITIES
    # =========================================================================

    def get_block_count(self) -> Tuple[int, int]:
        """Get number of double and single transformer blocks."""
        transformer = self._get_transformer()
        if transformer is None:
            return self.config.num_double_blocks, self.config.num_single_blocks

        num_double = len(transformer.transformer_blocks) if hasattr(transformer, 'transformer_blocks') else 0
        num_single = len(transformer.single_transformer_blocks) if hasattr(transformer, 'single_transformer_blocks') else 0

        return num_double, num_single

    def get_layer_mapping_info(self) -> Dict[str, Any]:
        """Get information about layer mappings."""
        num_double, num_single = self.get_block_count()

        info = {
            "num_double_blocks": num_double,
            "num_single_blocks": num_single,
            "total_blocks": num_double + num_single,
            "double_block_mapping": {},
            "single_block_mapping": {},
        }

        for idx in range(num_double):
            layer = self.layer_mapper.get_layer_for_double_block(idx)
            info["double_block_mapping"][idx] = {
                "layer": layer,
                "name": LAYER_NAMES.get(layer),
            }

        for idx in range(num_single):
            layer = self.layer_mapper.get_layer_for_single_block(idx)
            info["single_block_mapping"][idx] = {
                "layer": layer,
                "name": LAYER_NAMES.get(layer),
            }

        return info

    def encode_prompt(
        self,
        prompt: str,
        prompt_2: Optional[str] = None,
    ) -> Tuple[Any, Any]:
        """
        Encode prompt using FLUX text encoders.

        Returns:
            (prompt_embeds, pooled_prompt_embeds)
        """
        # Use pipeline's encode methods
        if hasattr(self.pipeline, 'encode_prompt'):
            result = self.pipeline.encode_prompt(
                prompt=prompt,
                prompt_2=prompt_2,
            )
            if isinstance(result, tuple) and len(result) >= 2:
                return result[0], result[1]
            return result, None

        return None, None


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_flux_wrapper(
    variant: FluxVariant = FluxVariant.DEV,
    device: str = "cuda",
    enable_cpu_offload: bool = True,
) -> SymbolUFluxWrapper:
    """
    Create a FLUX wrapper with common settings.

    Args:
        variant: FLUX variant (DEV, SCHNELL)
        device: Target device
        enable_cpu_offload: Enable memory-efficient offloading

    Returns:
        SymbolUFluxWrapper instance
    """
    config = FluxConfig(
        model_id=variant.value,
        variant=variant,
        device=device,
        enable_model_cpu_offload=enable_cpu_offload,
    )

    return SymbolUFluxWrapper.from_pretrained(config.model_id, config=config)


def get_layer_for_timestep(
    timestep: int,
    total_timesteps: int,
) -> int:
    """
    Estimate which Symbol-U layer is most active at a timestep.

    Early timesteps (high noise) -> early layers (structure)
    Late timesteps (low noise) -> later layers (detail)

    Args:
        timestep: Current timestep (0 = most noise)
        total_timesteps: Total number of timesteps

    Returns:
        Estimated active layer (1-12)
    """
    progress = timestep / max(total_timesteps - 1, 1)

    # Map progress to layer range
    # Early: L2-L4 (identity, execution, structure)
    # Middle: L5-L8 (cognition, agency, reasoning, purpose)
    # Late: L9-L12 (witnesses, unifying, integration, absolving)

    if progress < 0.3:
        layer = 2 + int(progress / 0.1)  # L2-L4
    elif progress < 0.7:
        layer = 5 + int((progress - 0.3) / 0.1)  # L5-L8
    else:
        layer = 9 + int((progress - 0.7) / 0.1)  # L9-L12

    return min(max(layer, 1), 12)
