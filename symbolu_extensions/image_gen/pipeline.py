#!/usr/bin/env python3
"""
Symbol-U FLUX Pipeline: Coherent Image Generation
==================================================

Main pipeline for Symbol-U image generation integrating:
1. FLUX diffusion model (via flux_integration)
2. BCVF bidirectional verification
3. USE phase synchronization
4. SCC semantic coherence
5. Real-time coherence monitoring

Features:
- Automatic coherence verification at each timestep
- Targeted regeneration for weak layers
- Completion weight gating (w_final)
- Detailed generation metrics

Usage:
------
    from symbolu.image_gen.pipeline import SymbolUFluxPipeline

    # Create pipeline
    pipeline = SymbolUFluxPipeline.from_pretrained()

    # Generate with full Symbol-U integration
    result = pipeline.generate(
        prompt="A majestic eagle soaring over mountains at sunset",
        mode="balanced",
    )

    # Check result
    if result.success:
        result.image.save("eagle.png")
        print(f"Confidence: {result.metrics.confidence}")
    else:
        print(f"Generation failed: {result.error_message}")
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Union
import logging
import time

try:
    import torch
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False
    torch = None

import numpy as np

from symbolu.image_gen.config import (
    ImageGenConfig,
    FluxConfig,
    CoherenceConfig,
    GenerationMode,
    OutputFormat,
    ImageGenMetrics,
    ImageGenResult,
)
from symbolu.image_gen.layer_mapper import LayerMapper, LAYER_NAMES
from symbolu.image_gen.bcvf_image import BCVFImageEngine
from symbolu.image_gen.use_image import USEImageEngine
from symbolu.image_gen.scc_image import SCCImageEngine
from symbolu.image_gen.coherence_monitor import (
    CoherenceMonitor,
    GenerationDecision,
)
from symbolu.image_gen.flux_integration import (
    SymbolUFluxWrapper,
    FluxGenerationResult,
)

logger = logging.getLogger(__name__)


# =============================================================================
# GENERATION RESULT
# =============================================================================

@dataclass
class PipelineResult:
    """Complete result from Symbol-U pipeline generation."""
    # Output
    image: Any  # PIL.Image or tensor
    images: List[Any]  # All generated images (if batch > 1)
    latents: Optional[Any]

    # Metrics
    metrics: ImageGenMetrics

    # Status
    success: bool
    error_message: Optional[str]

    # Generation info
    prompt: str
    seed: int
    config: ImageGenConfig

    # Coherence details
    decision: Optional[GenerationDecision]
    layer_coherences: Dict[str, float]

    # Debug info
    num_retries: int
    generation_time_ms: float
    layer_states: Optional[Dict[int, Any]]
    attention_maps: Optional[Dict[str, Any]]

    @property
    def confidence(self) -> str:
        """Get confidence category."""
        return self.metrics.confidence

    @property
    def should_retry(self) -> bool:
        """Whether this result suggests retrying with different seed."""
        return not self.success and self.num_retries < self.config.max_retries


# =============================================================================
# SYMBOL-U FLUX PIPELINE
# =============================================================================

class SymbolUFluxPipeline:
    """
    Main Symbol-U image generation pipeline.

    Integrates FLUX diffusion with Symbol-U coherence verification.
    """

    def __init__(
        self,
        flux_wrapper: SymbolUFluxWrapper,
        config: Optional[ImageGenConfig] = None,
    ):
        """
        Initialize pipeline.

        Args:
            flux_wrapper: Initialized SymbolUFluxWrapper
            config: Pipeline configuration
        """
        self.flux = flux_wrapper
        self.config = config or ImageGenConfig()

        # Initialize engines
        self.bcvf_engine = BCVFImageEngine(self.config.bcvf)
        self.use_engine = USEImageEngine(self.config.use)
        self.scc_engine = SCCImageEngine(self.config.scc)
        self.layer_mapper = LayerMapper()

        # Monitor
        self.monitor = CoherenceMonitor(
            coherence_config=self.config.coherence,
            bcvf_config=self.config.bcvf,
            use_config=self.config.use,
            scc_config=self.config.scc,
            mode=self.config.mode,
        )

    @classmethod
    def from_pretrained(
        cls,
        model_id: Optional[str] = None,
        config: Optional[ImageGenConfig] = None,
        **kwargs,
    ) -> "SymbolUFluxPipeline":
        """
        Create pipeline from pretrained FLUX model.

        Args:
            model_id: HuggingFace model ID (default from config)
            config: Pipeline configuration
            **kwargs: Passed to FLUX loading

        Returns:
            SymbolUFluxPipeline instance
        """
        config = config or ImageGenConfig()
        model_id = model_id or config.flux.model_id

        flux_wrapper = SymbolUFluxWrapper.from_pretrained(
            model_id=model_id,
            config=config.flux,
            **kwargs,
        )

        return cls(flux_wrapper, config)

    @classmethod
    def fast(cls, **kwargs) -> "SymbolUFluxPipeline":
        """Create pipeline with fast preset."""
        config = ImageGenConfig.fast()
        return cls.from_pretrained(config=config, **kwargs)

    @classmethod
    def quality(cls, **kwargs) -> "SymbolUFluxPipeline":
        """Create pipeline with quality preset."""
        config = ImageGenConfig.quality()
        return cls.from_pretrained(config=config, **kwargs)

    @classmethod
    def strict(cls, **kwargs) -> "SymbolUFluxPipeline":
        """Create pipeline with strict preset."""
        config = ImageGenConfig.strict()
        return cls.from_pretrained(config=config, **kwargs)

    # =========================================================================
    # MAIN GENERATION
    # =========================================================================

    def generate(
        self,
        prompt: str,
        prompt_2: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        num_inference_steps: Optional[int] = None,
        guidance_scale: Optional[float] = None,
        seed: Optional[int] = None,
        mode: Optional[Union[str, GenerationMode]] = None,
        **kwargs,
    ) -> PipelineResult:
        """
        Generate an image with Symbol-U coherence verification.

        Args:
            prompt: Text prompt
            prompt_2: Optional second prompt
            width: Output width (default from config)
            height: Output height (default from config)
            num_inference_steps: Inference steps (default from config)
            guidance_scale: CFG scale (default from config)
            seed: Random seed
            mode: Generation mode ("fast", "balanced", "quality", "strict")
            **kwargs: Additional FLUX arguments

        Returns:
            PipelineResult with image and metrics
        """
        start_time = time.time()

        # Apply config defaults
        width = width or self.config.width
        height = height or self.config.height
        num_inference_steps = num_inference_steps or self.config.num_inference_steps
        guidance_scale = guidance_scale or self.config.guidance_scale

        if mode is not None:
            if isinstance(mode, str):
                mode = GenerationMode(mode)
            self.monitor.mode = mode

        # Generate seed if needed
        if seed is None:
            seed = np.random.randint(0, 2**32 - 1)

        # Reset monitor for new generation
        self.monitor.reset()
        self.monitor.set_prompt(prompt)

        # Attempt generation with retries
        result = None
        num_retries = 0
        last_error = None

        for attempt in range(self.config.max_retries):
            try:
                # Generate with FLUX
                flux_result = self._generate_with_monitoring(
                    prompt=prompt,
                    prompt_2=prompt_2,
                    width=width,
                    height=height,
                    num_inference_steps=num_inference_steps,
                    guidance_scale=guidance_scale,
                    seed=seed + attempt,  # Vary seed on retry
                    **kwargs,
                )

                # Get generation decision
                decision = self.monitor.get_generation_result(
                    final_latents=flux_result.latents,
                    final_image=flux_result.images[0] if flux_result.images else None,
                    final_layer_states=flux_result.layer_states,
                )

                # Build metrics
                metrics = self._build_metrics(flux_result, decision)

                # Check if acceptable
                if decision.should_accept or self.config.mode == GenerationMode.FAST:
                    # Success
                    generation_time = (time.time() - start_time) * 1000

                    return PipelineResult(
                        image=flux_result.images[0] if flux_result.images else None,
                        images=flux_result.images,
                        latents=flux_result.latents,
                        metrics=metrics,
                        success=True,
                        error_message=None,
                        prompt=prompt,
                        seed=flux_result.seed,
                        config=self.config,
                        decision=decision,
                        layer_coherences={
                            LAYER_NAMES.get(idx, f"L{idx}"): r.coherence
                            for idx, r in decision.final_scc.layer_results.items()
                        },
                        num_retries=num_retries,
                        generation_time_ms=generation_time,
                        layer_states=flux_result.layer_states if self.config.return_intermediate_states else None,
                        attention_maps=flux_result.attention_maps if self.config.return_intermediate_states else None,
                    )

                # Not acceptable - retry
                num_retries += 1
                logger.info(f"Generation attempt {attempt + 1} rejected, retrying...")

                if self.config.verbose:
                    logger.info(f"Issues: {decision.issues}")
                    logger.info(f"Recommendations: {decision.recommendations}")

            except Exception as e:
                last_error = str(e)
                logger.warning(f"Generation attempt {attempt + 1} failed: {e}")
                num_retries += 1

        # All attempts failed
        generation_time = (time.time() - start_time) * 1000

        return PipelineResult(
            image=None,
            images=[],
            latents=None,
            metrics=ImageGenMetrics(
                global_coherence=0.0,
                prompt_alignment=0.0,
                quality_score=0.0,
                lagrangian=float('inf'),
                completion_weight=0.0,
                layer_coherences={},
                generation_time_ms=generation_time,
                num_retries=num_retries,
                potential_issues=["Generation failed after max retries"],
            ),
            success=False,
            error_message=last_error or "Generation rejected after max retries",
            prompt=prompt,
            seed=seed,
            config=self.config,
            decision=None,
            layer_coherences={},
            num_retries=num_retries,
            generation_time_ms=generation_time,
            layer_states=None,
            attention_maps=None,
        )

    def _generate_with_monitoring(
        self,
        prompt: str,
        prompt_2: Optional[str],
        width: int,
        height: int,
        num_inference_steps: int,
        guidance_scale: float,
        seed: int,
        **kwargs,
    ) -> FluxGenerationResult:
        """Generate with coherence monitoring at each timestep."""
        # Encode prompt for backward scoring
        prompt_embeds, pooled_embeds = self.flux.encode_prompt(prompt, prompt_2)
        self.monitor.set_prompt(prompt, prompt_embeds)

        # Generate with state capture
        capture_every = 1 if self.config.mode in [GenerationMode.QUALITY, GenerationMode.STRICT] else 4

        result = self.flux.generate(
            prompt=prompt,
            prompt_2=prompt_2,
            width=width,
            height=height,
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale,
            seed=seed,
            capture_states=True,
            capture_attention=self.config.return_intermediate_states,
            capture_every_n_steps=capture_every,
            **kwargs,
        )

        # Record states to monitor
        for state in self.flux.get_timestep_states():
            layer_states = state.get_layer_states()
            self.monitor.record_timestep(
                timestep=state.timestep,
                latents=state.latents,
                layer_states=layer_states,
            )

        return result

    def _build_metrics(
        self,
        flux_result: FluxGenerationResult,
        decision: GenerationDecision,
    ) -> ImageGenMetrics:
        """Build metrics from generation results."""
        return ImageGenMetrics(
            global_coherence=decision.final_scc.global_coherence,
            prompt_alignment=decision.final_bcvf.backward_score,
            quality_score=decision.final_bcvf.forward_score,
            lagrangian=decision.final_bcvf.lagrangian,
            completion_weight=decision.completion_weight,
            layer_coherences={
                LAYER_NAMES.get(idx, f"L{idx}"): r.coherence
                for idx, r in decision.final_scc.layer_results.items()
            },
            generation_time_ms=flux_result.inference_time_ms,
            num_retries=0,  # Will be updated by caller
            potential_issues=decision.issues,
        )

    # =========================================================================
    # TARGETED REGENERATION
    # =========================================================================

    def regenerate_weak_layers(
        self,
        previous_result: PipelineResult,
        target_layers: Optional[List[int]] = None,
        strength: float = 0.5,
    ) -> PipelineResult:
        """
        Regenerate targeting specific weak layers.

        Uses the previous result as a guide and focuses diffusion
        on improving weak layers.

        Args:
            previous_result: Previous generation result
            target_layers: Layers to target (auto-detected if None)
            strength: How much to modify (0 = keep original, 1 = full regen)

        Returns:
            New PipelineResult
        """
        if not self.config.enable_targeted_regeneration:
            return previous_result

        # Detect weak layers if not specified
        if target_layers is None:
            if previous_result.decision:
                target_layers = previous_result.decision.final_scc.weakest_layers
            else:
                target_layers = []

        if not target_layers:
            logger.info("No weak layers to target")
            return previous_result

        logger.info(f"Targeting weak layers: {target_layers}")

        # For now, just regenerate with different seed
        # Full implementation would use layer-targeted guidance
        new_seed = previous_result.seed + 1000

        return self.generate(
            prompt=previous_result.prompt,
            seed=new_seed,
        )

    # =========================================================================
    # BATCH GENERATION
    # =========================================================================

    def generate_batch(
        self,
        prompts: List[str],
        seeds: Optional[List[int]] = None,
        **kwargs,
    ) -> List[PipelineResult]:
        """
        Generate multiple images.

        Args:
            prompts: List of prompts
            seeds: Optional list of seeds
            **kwargs: Passed to generate()

        Returns:
            List of PipelineResults
        """
        if seeds is None:
            seeds = [None] * len(prompts)

        results = []
        for prompt, seed in zip(prompts, seeds):
            result = self.generate(prompt=prompt, seed=seed, **kwargs)
            results.append(result)

        return results

    def generate_variations(
        self,
        prompt: str,
        num_variations: int = 4,
        **kwargs,
    ) -> List[PipelineResult]:
        """
        Generate multiple variations of the same prompt.

        Args:
            prompt: Text prompt
            num_variations: Number of variations
            **kwargs: Passed to generate()

        Returns:
            List of PipelineResults sorted by quality
        """
        results = []
        for i in range(num_variations):
            result = self.generate(prompt=prompt, seed=None, **kwargs)
            results.append(result)

        # Sort by completion weight (best first)
        results.sort(
            key=lambda r: r.metrics.completion_weight,
            reverse=True,
        )

        return results

    # =========================================================================
    # ANALYSIS
    # =========================================================================

    def analyze_coherence(
        self,
        image: Any,
        prompt: str,
        latents: Optional[Any] = None,
        layer_states: Optional[Dict[int, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze coherence of an existing image.

        Args:
            image: PIL image or tensor
            prompt: Original prompt
            latents: Optional latents
            layer_states: Optional layer states

        Returns:
            Dict with analysis results
        """
        # BCVF analysis
        bcvf_score = self.bcvf_engine.score(
            image=image,
            latents=latents,
            prompt=prompt,
        )

        analysis = {
            "bcvf": {
                "forward_score": bcvf_score.forward_score,
                "backward_score": bcvf_score.backward_score,
                "lagrangian": bcvf_score.lagrangian,
                "consistency_weight": bcvf_score.consistency_weight,
                "is_consistent": bcvf_score.is_consistent,
                "quality_category": bcvf_score.quality_category,
            },
            "issues": self.bcvf_engine.diagnose_issues(bcvf_score),
        }

        # Layer analysis if states available
        if layer_states:
            # USE analysis
            phases = self.use_engine.extract_phases(layer_states)
            use_coherence = self.use_engine.compute_total_coherence(phases=phases)

            # SCC analysis
            scc_result = self.scc_engine.compute_global_coherence(layer_states)

            analysis["use"] = {
                "phase_coherence": use_coherence,
            }

            analysis["scc"] = {
                "global_coherence": scc_result.global_coherence,
                "mean_layer_coherence": scc_result.mean_coherence,
                "weakest_layers": scc_result.weakest_layers,
                "strongest_layers": scc_result.strongest_layers,
                "layer_details": {
                    idx: {
                        "name": r.layer_name,
                        "coherence": r.coherence,
                        "entropy": r.entropy,
                        "resonance": r.resonance,
                    }
                    for idx, r in scc_result.layer_results.items()
                },
            }

            # Diagnose issues
            scc_issues = self.scc_engine.diagnose_issues(layer_states)
            analysis["issues"].extend([
                f"[{i.layer_name}] {i.issue_type}: {i.message}"
                for i in scc_issues
            ])

        return analysis

    def get_layer_info(self) -> Dict[str, Any]:
        """Get information about layer mappings."""
        return self.flux.get_layer_mapping_info()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def generate(
    prompt: str,
    mode: str = "balanced",
    seed: Optional[int] = None,
    **kwargs,
) -> PipelineResult:
    """
    Quick generation with default settings.

    Args:
        prompt: Text prompt
        mode: "fast", "balanced", "quality", "strict"
        seed: Random seed
        **kwargs: Additional arguments

    Returns:
        PipelineResult
    """
    if mode == "fast":
        pipeline = SymbolUFluxPipeline.fast()
    elif mode == "quality":
        pipeline = SymbolUFluxPipeline.quality()
    elif mode == "strict":
        pipeline = SymbolUFluxPipeline.strict()
    else:
        pipeline = SymbolUFluxPipeline.from_pretrained()

    return pipeline.generate(prompt=prompt, seed=seed, **kwargs)


def create_pipeline(
    model_id: str = "black-forest-labs/FLUX.1-dev",
    mode: str = "balanced",
    device: str = "cuda",
    **kwargs,
) -> SymbolUFluxPipeline:
    """
    Create a pipeline with specified settings.

    Args:
        model_id: HuggingFace model ID
        mode: Generation mode
        device: Target device
        **kwargs: Additional config

    Returns:
        SymbolUFluxPipeline
    """
    config = ImageGenConfig(
        mode=GenerationMode(mode),
        flux=FluxConfig(
            model_id=model_id,
            device=device,
        ),
    )

    return SymbolUFluxPipeline.from_pretrained(config=config)
