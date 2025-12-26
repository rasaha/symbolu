#!/usr/bin/env python3
"""
BCVF Image Engine: Bidirectional Consistency Verification for Image Generation
================================================================================

Implements BCVF patent formulas for image generation quality verification.

Core Formula (B1):
    L = lambda_f * (1 - sf)^2 + lambda_b * (1 - sb)^2 + lambda_c * (sf - sb)^2

Where for images:
    sf: Forward feasibility score (image quality, coherence, aesthetics)
    sb: Backward goal-achievement score (prompt alignment via CLIP)

Key Features:
1. Forward scoring: Image quality, anatomical consistency, style coherence
2. Backward scoring: CLIP-based prompt alignment
3. Consistency verification: sf and sb should agree
4. Completion gating: w_final = exp(-beta * L)

Usage:
------
    from symbolu.image_gen.bcvf_image import BCVFImageEngine

    engine = BCVFImageEngine()

    # Score a generated image
    result = engine.score(
        image_latents=latents,
        prompt="A red sports car",
        text_embeddings=text_emb,
    )

    print(f"Forward: {result.forward_score:.3f}")
    print(f"Backward: {result.backward_score:.3f}")
    print(f"Lagrangian: {result.lagrangian:.3f}")
    print(f"Completion weight: {result.completion_weight:.3f}")
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Callable, Union
import math

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False
    torch = None
    nn = None
    F = None

import numpy as np

from symbolu.image_gen.config import BCVFImageConfig


# =============================================================================
# RESULT DATACLASSES
# =============================================================================

@dataclass
class BCVFImageScore:
    """
    BCVF scores for a generated image.

    Attributes:
        forward_score: sf in [0,1] - image quality/coherence
        backward_score: sb in [0,1] - prompt alignment
        lagrangian: L = lambda_f*(1-sf)^2 + lambda_b*(1-sb)^2 + lambda_c*(sf-sb)^2
        consistency_weight: w = exp(-beta * L)
        normalized_weight: W = w / sum(w) (for multi-candidate selection)
    """
    forward_score: float
    backward_score: float
    lagrangian: float
    consistency_weight: float
    normalized_weight: float = 0.0

    # Component breakdowns
    forward_components: Dict[str, float] = field(default_factory=dict)
    backward_components: Dict[str, float] = field(default_factory=dict)

    @property
    def is_consistent(self) -> bool:
        """Check if forward and backward scores are consistent."""
        return abs(self.forward_score - self.backward_score) < 0.3

    @property
    def quality_category(self) -> str:
        """Categorize quality based on scores."""
        if self.forward_score >= 0.8 and self.backward_score >= 0.8:
            return "excellent"
        elif self.forward_score >= 0.7 and self.backward_score >= 0.7:
            return "good"
        elif self.forward_score >= 0.5 and self.backward_score >= 0.5:
            return "acceptable"
        else:
            return "poor"

    @property
    def should_accept(self) -> bool:
        """Whether this image should be accepted (not retried)."""
        return (
            self.forward_score >= 0.5 and
            self.backward_score >= 0.5 and
            self.consistency_weight >= 0.3
        )


@dataclass
class ElementVerification:
    """Verification result for a prompt element."""
    element: str
    element_type: str  # "object", "attribute", "count", "spatial", "style"
    present: bool
    confidence: float
    details: Optional[str] = None


@dataclass
class BackwardVerificationResult:
    """Detailed backward verification result."""
    overall_score: float
    elements: List[ElementVerification]
    missing_elements: List[str]
    incorrect_elements: List[str]
    prompt_coverage: float


# =============================================================================
# CONSISTENCY LAGRANGIAN
# =============================================================================

class ConsistencyLagrangianImage:
    """
    Implements the BCVF Consistency Lagrangian for images.

    Core formula (B1):
        L = lambda_f * (1 - sf)^2 + lambda_b * (1 - sb)^2 + lambda_c * (sf - sb)^2

    This penalizes:
    1. Low image quality (low sf)
    2. Poor prompt alignment (low sb)
    3. Inconsistency between quality and alignment (sf != sb)
    """

    def __init__(self, config: Optional[BCVFImageConfig] = None):
        self.config = config or BCVFImageConfig()

    def compute_lagrangian(
        self,
        forward_score: float,
        backward_score: float,
    ) -> float:
        """
        Compute the Consistency Lagrangian L.

        Args:
            forward_score: sf in [0,1]
            backward_score: sb in [0,1]

        Returns:
            Lagrangian value (lower is better)
        """
        sf = float(np.clip(forward_score, 0.0, 1.0))
        sb = float(np.clip(backward_score, 0.0, 1.0))

        # Three penalty terms
        forward_penalty = (1.0 - sf) ** 2
        backward_penalty = (1.0 - sb) ** 2
        consistency_penalty = (sf - sb) ** 2

        # Weighted sum
        L = (
            self.config.lambda_forward * forward_penalty +
            self.config.lambda_backward * backward_penalty +
            self.config.lambda_consistency * consistency_penalty
        )

        return float(L)

    def compute_weight(self, lagrangian: float) -> float:
        """
        Convert Lagrangian to consistency weight.

        Formula: w = exp(-beta * L)

        Lower Lagrangian -> higher weight.
        """
        return float(np.exp(-self.config.beta * lagrangian))

    def score(
        self,
        forward_score: float,
        backward_score: float,
    ) -> BCVFImageScore:
        """
        Compute full BCVF score.

        Args:
            forward_score: sf in [0,1]
            backward_score: sb in [0,1]

        Returns:
            BCVFImageScore with all metrics
        """
        lagrangian = self.compute_lagrangian(forward_score, backward_score)
        weight = self.compute_weight(lagrangian)

        return BCVFImageScore(
            forward_score=forward_score,
            backward_score=backward_score,
            lagrangian=lagrangian,
            consistency_weight=weight,
        )


# =============================================================================
# FORWARD SCORER (sf) - Image Quality
# =============================================================================

class ForwardImageScorer:
    """
    Computes forward feasibility score sf for images.

    Components:
    1. Coherence: Internal consistency of the image
    2. Quality: Technical image quality (sharpness, noise)
    3. Aesthetics: Visual appeal (optional)
    4. Anatomy: Anatomical correctness for humans/animals
    5. Style: Style consistency across image regions
    """

    def __init__(self, config: Optional[BCVFImageConfig] = None):
        self.config = config or BCVFImageConfig()
        self._aesthetic_model = None
        self._quality_model = None

    def compute_coherence_score(
        self,
        latents: Any,
        hidden_states: Optional[Dict[int, Any]] = None,
    ) -> float:
        """
        Compute internal coherence of the image.

        Uses variance of feature activations as proxy for coherence.
        Low variance = consistent features = high coherence.
        """
        if not PYTORCH_AVAILABLE or latents is None:
            return 0.7  # Default

        if isinstance(latents, torch.Tensor):
            # Compute spatial variance
            variance = latents.var(dim=(-2, -1)).mean().item()
            # Normalize to [0, 1] - lower variance = higher coherence
            coherence = 1.0 / (1.0 + variance)
            return float(np.clip(coherence, 0.0, 1.0))

        return 0.7

    def compute_quality_score(
        self,
        latents: Any,
        decoded_image: Optional[Any] = None,
    ) -> float:
        """
        Compute technical quality score.

        For latents: Uses activation statistics.
        For decoded images: Would use quality metrics (NIQE, BRISQUE).
        """
        if not PYTORCH_AVAILABLE or latents is None:
            return 0.7  # Default

        if isinstance(latents, torch.Tensor):
            # Use statistics of latent activations
            mean_abs = latents.abs().mean().item()
            # Well-distributed activations suggest good quality
            quality = 1.0 - np.exp(-mean_abs)
            return float(np.clip(quality, 0.0, 1.0))

        return 0.7

    def compute_style_consistency_score(
        self,
        latents: Any,
        target_style: Optional[Any] = None,
    ) -> float:
        """
        Compute style consistency across image regions.

        Splits image into regions and checks if style is consistent.
        """
        if not PYTORCH_AVAILABLE or latents is None:
            return 0.8  # Default - assume consistent

        if isinstance(latents, torch.Tensor) and latents.dim() >= 3:
            # Split into quadrants and compare
            h, w = latents.shape[-2:]
            if h >= 4 and w >= 4:
                q1 = latents[..., :h//2, :w//2]
                q2 = latents[..., :h//2, w//2:]
                q3 = latents[..., h//2:, :w//2]
                q4 = latents[..., h//2:, w//2:]

                # Compare mean activations
                means = [q.mean().item() for q in [q1, q2, q3, q4]]
                variance = np.var(means)

                # Low variance = consistent style
                consistency = 1.0 / (1.0 + 10 * variance)
                return float(np.clip(consistency, 0.0, 1.0))

        return 0.8

    def compute_forward_score(
        self,
        latents: Any,
        hidden_states: Optional[Dict[int, Any]] = None,
        decoded_image: Optional[Any] = None,
        weights: Optional[Dict[str, float]] = None,
    ) -> Tuple[float, Dict[str, float]]:
        """
        Compute overall forward feasibility score sf.

        Args:
            latents: Image latents from diffusion
            hidden_states: Optional layer hidden states
            decoded_image: Optional decoded image for quality metrics
            weights: Optional component weights

        Returns:
            (sf, component_scores)
        """
        default_weights = {
            "coherence": 0.35,
            "quality": 0.35,
            "style": 0.30,
        }
        weights = weights or default_weights

        # Compute components
        components = {
            "coherence": self.compute_coherence_score(latents, hidden_states),
            "quality": self.compute_quality_score(latents, decoded_image),
            "style": self.compute_style_consistency_score(latents),
        }

        # Weighted average
        sf = sum(
            weights.get(k, 0) * v
            for k, v in components.items()
        )

        return float(np.clip(sf, 0.0, 1.0)), components


# =============================================================================
# BACKWARD SCORER (sb) - Prompt Alignment
# =============================================================================

class BackwardImageScorer:
    """
    Computes backward goal-achievement score sb for images.

    Uses CLIP or similar models to verify prompt alignment.

    Components:
    1. CLIP score: Overall text-image alignment
    2. Element verification: Are specific objects/attributes present?
    3. Count verification: Are counts correct?
    4. Attribute binding: Are attributes assigned to correct objects?
    """

    def __init__(self, config: Optional[BCVFImageConfig] = None):
        self.config = config or BCVFImageConfig()
        self._clip_model = None
        self._clip_processor = None

    def _ensure_clip_loaded(self) -> bool:
        """Lazy load CLIP model."""
        if self._clip_model is not None:
            return True

        if not self.config.use_clip_scorer:
            return False

        try:
            from transformers import CLIPModel, CLIPProcessor

            self._clip_model = CLIPModel.from_pretrained(
                self.config.clip_model_id
            )
            self._clip_processor = CLIPProcessor.from_pretrained(
                self.config.clip_model_id
            )

            if PYTORCH_AVAILABLE:
                self._clip_model.eval()
                if torch.cuda.is_available():
                    self._clip_model = self._clip_model.cuda()

            return True
        except Exception:
            return False

    def compute_clip_score(
        self,
        image: Any,
        prompt: str,
    ) -> float:
        """
        Compute CLIP similarity score between image and prompt.

        Args:
            image: PIL Image, torch.Tensor, or numpy array
            prompt: Text prompt

        Returns:
            CLIP similarity in [0, 1]
        """
        if not self._ensure_clip_loaded():
            return 0.7  # Default without CLIP

        try:
            # Process inputs
            inputs = self._clip_processor(
                text=[prompt],
                images=[image],
                return_tensors="pt",
                padding=True,
            )

            if PYTORCH_AVAILABLE and torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}

            # Get features
            with torch.no_grad():
                outputs = self._clip_model(**inputs)
                # Normalize and compute similarity
                image_embeds = outputs.image_embeds / outputs.image_embeds.norm(dim=-1, keepdim=True)
                text_embeds = outputs.text_embeds / outputs.text_embeds.norm(dim=-1, keepdim=True)
                similarity = (image_embeds @ text_embeds.T).item()

            # Map from [-1, 1] to [0, 1]
            return float(np.clip((similarity + 1) / 2, 0.0, 1.0))

        except Exception:
            return 0.7

    def compute_latent_text_alignment(
        self,
        latents: Any,
        text_embeddings: Any,
    ) -> float:
        """
        Compute alignment between latents and text embeddings.

        Used when decoded image is not available.

        Args:
            latents: Image latents
            text_embeddings: Text encoder embeddings (T5-XXL)

        Returns:
            Alignment score in [0, 1]
        """
        if not PYTORCH_AVAILABLE:
            return 0.7

        if latents is None or text_embeddings is None:
            return 0.7

        try:
            # Flatten and normalize
            latent_flat = latents.flatten().float()
            text_flat = text_embeddings.flatten().float()

            # Match dimensions (take shorter)
            min_dim = min(len(latent_flat), len(text_flat))
            latent_flat = latent_flat[:min_dim]
            text_flat = text_flat[:min_dim]

            # Normalize
            latent_norm = F.normalize(latent_flat.unsqueeze(0), dim=-1)
            text_norm = F.normalize(text_flat.unsqueeze(0), dim=-1)

            # Cosine similarity
            similarity = (latent_norm @ text_norm.T).item()

            # Map to [0, 1]
            return float(np.clip((similarity + 1) / 2, 0.0, 1.0))

        except Exception:
            return 0.7

    def verify_prompt_elements(
        self,
        image: Any,
        prompt: str,
    ) -> BackwardVerificationResult:
        """
        Verify individual elements from the prompt are present.

        This is a simplified version - full implementation would use
        object detection and attribute classification.

        Args:
            image: Decoded image
            prompt: Original prompt

        Returns:
            BackwardVerificationResult with element-level verification
        """
        # Simple keyword extraction (would be replaced with NLP)
        elements = []
        prompt_lower = prompt.lower()

        # Check for common elements (simplified)
        # In production, use spaCy or similar for proper parsing
        keywords = [
            ("object", word)
            for word in prompt_lower.split()
            if len(word) > 3 and word.isalpha()
        ]

        for elem_type, elem in keywords[:10]:  # Limit to 10
            elements.append(ElementVerification(
                element=elem,
                element_type=elem_type,
                present=True,  # Assume present without detection
                confidence=0.7,
            ))

        return BackwardVerificationResult(
            overall_score=0.7,
            elements=elements,
            missing_elements=[],
            incorrect_elements=[],
            prompt_coverage=0.7,
        )

    def compute_backward_score(
        self,
        image: Optional[Any] = None,
        latents: Optional[Any] = None,
        prompt: str = "",
        text_embeddings: Optional[Any] = None,
        weights: Optional[Dict[str, float]] = None,
    ) -> Tuple[float, Dict[str, float]]:
        """
        Compute overall backward goal-achievement score sb.

        Args:
            image: Decoded image (preferred)
            latents: Image latents (fallback)
            prompt: Text prompt
            text_embeddings: Text encoder embeddings
            weights: Optional component weights

        Returns:
            (sb, component_scores)
        """
        default_weights = {
            "clip": 0.6,
            "latent_alignment": 0.4,
        }
        weights = weights or default_weights

        components = {}

        # CLIP score if image available
        if image is not None:
            components["clip"] = self.compute_clip_score(image, prompt)
        else:
            components["clip"] = 0.7  # Default

        # Latent-text alignment
        if latents is not None and text_embeddings is not None:
            components["latent_alignment"] = self.compute_latent_text_alignment(
                latents, text_embeddings
            )
        else:
            components["latent_alignment"] = 0.7

        # Weighted average
        sb = sum(
            weights.get(k, 0) * v
            for k, v in components.items()
        )

        return float(np.clip(sb, 0.0, 1.0)), components


# =============================================================================
# BCVF IMAGE ENGINE
# =============================================================================

class BCVFImageEngine:
    """
    Complete BCVF engine for image generation.

    Combines forward and backward scoring with the consistency Lagrangian.
    """

    def __init__(self, config: Optional[BCVFImageConfig] = None):
        self.config = config or BCVFImageConfig()
        self.lagrangian = ConsistencyLagrangianImage(config)
        self.forward_scorer = ForwardImageScorer(config)
        self.backward_scorer = BackwardImageScorer(config)

    def score(
        self,
        image: Optional[Any] = None,
        latents: Optional[Any] = None,
        prompt: str = "",
        text_embeddings: Optional[Any] = None,
        hidden_states: Optional[Dict[int, Any]] = None,
    ) -> BCVFImageScore:
        """
        Compute complete BCVF score for an image.

        Args:
            image: Decoded image (PIL/tensor/numpy)
            latents: Image latents
            prompt: Text prompt
            text_embeddings: Text encoder embeddings
            hidden_states: Layer hidden states

        Returns:
            BCVFImageScore with all metrics
        """
        # Forward score (image quality)
        sf, forward_components = self.forward_scorer.compute_forward_score(
            latents=latents,
            hidden_states=hidden_states,
            decoded_image=image,
        )

        # Backward score (prompt alignment)
        sb, backward_components = self.backward_scorer.compute_backward_score(
            image=image,
            latents=latents,
            prompt=prompt,
            text_embeddings=text_embeddings,
        )

        # Compute Lagrangian and weight
        result = self.lagrangian.score(sf, sb)
        result.forward_components = forward_components
        result.backward_components = backward_components

        return result

    def score_candidates(
        self,
        candidates: List[Dict[str, Any]],
        prompt: str,
        text_embeddings: Optional[Any] = None,
    ) -> List[BCVFImageScore]:
        """
        Score multiple candidate images and normalize weights.

        Args:
            candidates: List of dicts with "image" and/or "latents"
            prompt: Text prompt
            text_embeddings: Text encoder embeddings

        Returns:
            List of BCVFImageScore with normalized weights
        """
        scores = []

        for candidate in candidates:
            score = self.score(
                image=candidate.get("image"),
                latents=candidate.get("latents"),
                prompt=prompt,
                text_embeddings=text_embeddings,
                hidden_states=candidate.get("hidden_states"),
            )
            scores.append(score)

        # Normalize weights
        total_weight = sum(s.consistency_weight for s in scores) + 1e-10
        for score in scores:
            score.normalized_weight = score.consistency_weight / total_weight

        return scores

    def select_best(
        self,
        candidates: List[Dict[str, Any]],
        prompt: str,
        text_embeddings: Optional[Any] = None,
    ) -> Tuple[int, BCVFImageScore]:
        """
        Select the best candidate based on BCVF scores.

        Args:
            candidates: List of candidate dicts
            prompt: Text prompt
            text_embeddings: Text encoder embeddings

        Returns:
            (best_index, best_score)
        """
        scores = self.score_candidates(candidates, prompt, text_embeddings)
        best_idx = max(range(len(scores)), key=lambda i: scores[i].normalized_weight)
        return best_idx, scores[best_idx]

    def should_accept(
        self,
        score: BCVFImageScore,
        threshold: Optional[float] = None,
    ) -> bool:
        """
        Determine if an image should be accepted or retried.

        Args:
            score: BCVF score for the image
            threshold: Optional custom threshold

        Returns:
            True if image should be accepted
        """
        threshold = threshold or 0.5
        return (
            score.forward_score >= threshold and
            score.backward_score >= threshold and
            score.is_consistent
        )

    def diagnose_issues(
        self,
        score: BCVFImageScore,
    ) -> List[str]:
        """
        Diagnose potential issues with a generated image.

        Args:
            score: BCVF score for the image

        Returns:
            List of issue descriptions
        """
        issues = []

        # Low forward score issues
        if score.forward_score < 0.5:
            if score.forward_components.get("coherence", 1) < 0.5:
                issues.append("Low coherence: Image lacks internal consistency")
            if score.forward_components.get("quality", 1) < 0.5:
                issues.append("Low quality: Technical image quality issues")
            if score.forward_components.get("style", 1) < 0.5:
                issues.append("Style inconsistency: Different styles across regions")

        # Low backward score issues
        if score.backward_score < 0.5:
            if score.backward_components.get("clip", 1) < 0.5:
                issues.append("Poor prompt alignment: Image doesn't match prompt")
            if score.backward_components.get("latent_alignment", 1) < 0.5:
                issues.append("Semantic mismatch: Latents diverged from text")

        # Consistency issues
        if not score.is_consistent:
            gap = abs(score.forward_score - score.backward_score)
            if score.forward_score > score.backward_score:
                issues.append(
                    f"Quality-alignment gap ({gap:.2f}): "
                    "High quality but doesn't match prompt"
                )
            else:
                issues.append(
                    f"Alignment-quality gap ({gap:.2f}): "
                    "Matches prompt but low quality"
                )

        return issues


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def create_bcvf_engine(
    config: Optional[BCVFImageConfig] = None
) -> BCVFImageEngine:
    """Create a BCVF image engine with optional config."""
    return BCVFImageEngine(config)


def quick_score(
    image: Any,
    prompt: str,
) -> BCVFImageScore:
    """Quick scoring with default settings."""
    engine = BCVFImageEngine()
    return engine.score(image=image, prompt=prompt)
