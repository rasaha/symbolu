"""Symbol-U neural modules — one nn.Module per EQ group."""
from .segmentation import SoftSyllableSegmenter
from .typed_heads import (
    VrittiHead, AspectHead, AspectAggregator, GunaHead, KoshaHead,
    ContextVrittiCoupling,
)
from .entropy import EntropyEngine, shannon_entropy
from .refinement import EntropyGatedRefinementCore
from .stitching import SoftStitchingSelector
from .memory import DeferredInsightMemory
from .anchors import ExperienceAnchorRouter
from .delivery import DeliveryHarmonizationHead
from .safety import HardSafetyBoundary

__all__ = [
    "SoftSyllableSegmenter",
    "VrittiHead", "AspectHead", "AspectAggregator", "GunaHead", "KoshaHead",
    "ContextVrittiCoupling",
    "EntropyEngine", "shannon_entropy",
    "EntropyGatedRefinementCore",
    "SoftStitchingSelector",
    "DeferredInsightMemory",
    "ExperienceAnchorRouter",
    "DeliveryHarmonizationHead",
    "HardSafetyBoundary",
]
