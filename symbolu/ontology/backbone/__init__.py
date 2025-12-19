"""
10D Ontological Backbone
========================

Universal 10-dimensional encoding system for cross-domain reasoning.

Each dimension maps cognitive/philosophical concepts to mathematical structures,
enabling structural similarity detection across any domain (history, science,
literature, finance, etc.).

Dimensions:
    1D Action      → Linear algebra (addition/subtraction, progression)
    2D Identification → Ratios/polarities (multiplication/division)
    3D Body        → Geometry (form, shape, space)
    4D Mind        → Recursion/flow (time, process, memory)
    5D Ego         → Logic/computation (choices, branching, Boolean)
    6D Intellect   → Set theory (laws, universals, categories)
    7D Soul        → Topology (continuity across domains)
    8D Witness     → Probability (superposition, all possible paths)
    9D Singularity → Unification (unity of concepts)
    10D Absolute   → Symbolic infinity (transcendence, pure potential)

Usage:
    from symbolu.ontology.backbone import encode_10d, compute_similarity

    vec1 = encode_10d("The Civil War divided the nation")
    vec2 = encode_10d("Grapes of Wrath depicts family division")

    similarity = compute_similarity(vec1, vec2)
    # Returns structural similarity based on 10D encoding
"""

from .encoder import (
    Dimension,
    DimensionalVector,
    encode_10d,
    encode_batch,
)
from .similarity import (
    compute_similarity,
    find_similar,
    SimilarityResult,
)
from .extractors import (
    DimensionExtractor,
    get_extractor,
    ProjectionDirection,
)
from .experiential import (
    ExperientialObject,
    ExperientialStore,
    PatternType,
    create_experiential,
    get_experiential_store,
)
from .reasoning_extractor import (
    extract_reasoning,
    extract_and_create_experiential,
)
from .user_inclination import (
    UserInclinationProfile,
    UserInclinationStore,
    ReasoningStyle,
    get_user_store,
)
from .reasoning_synthesizer import (
    ReasoningSynthesizer,
    SynthesisResult,
    synthesize_for_problem,
)

__all__ = [
    # Core types
    "Dimension",
    "DimensionalVector",
    # Encoding
    "encode_10d",
    "encode_batch",
    # Similarity
    "compute_similarity",
    "find_similar",
    "SimilarityResult",
    # Extractors
    "DimensionExtractor",
    "get_extractor",
    "ProjectionDirection",
    # Experiential Objects
    "ExperientialObject",
    "ExperientialStore",
    "PatternType",
    "create_experiential",
    "get_experiential_store",
    # Reasoning Extraction
    "extract_reasoning",
    "extract_and_create_experiential",
    # User Inclination
    "UserInclinationProfile",
    "UserInclinationStore",
    "ReasoningStyle",
    "get_user_store",
    # Synthesis
    "ReasoningSynthesizer",
    "SynthesisResult",
    "synthesize_for_problem",
]
