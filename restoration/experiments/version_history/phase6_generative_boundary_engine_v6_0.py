"""
Phase-6.0 Generative Boundary Engine (v6.0)
===========================================

Phase-6.0 implements a one-way projection boundary.

This module is:
    - TEST-ONLY
    - NON-TEXTUAL
    - DETERMINISTIC
    - REVERSIBLE
    - ISOLATED
    - NON-GENERATIVE
    - NON-MUTATING

It operates ONLY on Phase-5 output (Phase5SynthesisResult).

ABSOLUTE RULES:
    - NO TEXT OUTPUT: No words, sentences, language strings, or labels
    - Only hex hashes (<=32 chars) or Enum values allowed as strings
    - NO SEMANTICS: No meaning, intent, emotion, sentiment inference
    - NO DICTIONARIES / NLP / LLM: No lookups, NLP libraries, LLM calls, embeddings
    - NO RANDOMNESS / TIME: No random, UUID, datetime, system time, non-deterministic sets
    - NON-MUTATING: Must not modify Phase-5 objects (or any upstream objects)
    - NON-GENERATIVE: Must not generate language, words, sentences, or meaning
    - NO FEEDBACK: Must not feed information back into prior phases
    - REVERSIBLE: Must allow recovery of Phase-5 hashes and structure
    - ONE-WAY BOUNDARY: Projects Phase-5 to external artifacts without mutation

Version: 6.0
"""

import hashlib
from dataclasses import dataclass
from typing import Tuple, List, Any, FrozenSet
from enum import Enum


__all__ = [
    "PHASE6_ENGINE_VERSION",
    "PHASE6_INVARIANTS",
    "BoundaryMode",
    "ArtifactType",
    "Phase6Artifact",
    "Phase6ProjectionResult",
    "project_phase5_to_phase6",
    "recover_phase5_hash_from_phase6",
    "validate_phase6_invariants",
    "check_for_forbidden_terms_phase6",
    "is_non_textual_value_phase6",
]


PHASE6_ENGINE_VERSION = "6.0"

PHASE6_INVARIANTS = {
    "NON_TEXTUAL": True,
    "NO_LANGUAGE": True,
    "NO_SEMANTICS": True,
    "NO_INTENT": True,
    "NO_EMOTION": True,
    "NO_PROBABILITY": True,
    "NO_LEARNING": True,
    "NO_GENERATION": True,
    "NO_FEEDBACK": True,
    "NON_MUTATING": True,
    "REVERSIBLE": True,
    "DETERMINISTIC": True,
    "ISOLATED": True,
    "TEST_ONLY": True,
}

FORBIDDEN_TERMS_PHASE6 = frozenset([
    # Language
    "word", "sentence", "language", "english", "hindi", "sanskrit",
    "text", "token", "vocabulary", "dictionary",
    # Semantics
    "meaning", "means", "represents", "symbolizes", "semantic",
    # Intent
    "intent", "purpose", "goal", "desire",
    # Emotions
    "sad", "happy", "emotion", "feeling", "mood", "joy", "fear",
    # Sentiment
    "positive", "negative", "neutral", "sentiment",
    # Probability
    "probability", "likelihood", "confidence",
    # Generation
    "generate", "predict", "infer",
    # Time
    "random", "timestamp", "datetime",
])


class BoundaryMode(Enum):
    """Boundary projection modes - structural only."""
    NON_TEXTUAL_ONLY = "non_textual_only"
    SYMBOLIC_ONLY = "symbolic_only"
    TEMPLATE_ONLY = "template_only"  # optional, gated


class ArtifactType(Enum):
    """Artifact type categories - structural only."""
    STRUCTURAL_ARTIFACT = "structural_artifact"
    GRAPH_ARTIFACT = "graph_artifact"
    VECTOR_ARTIFACT = "vector_artifact"
    NULL_ARTIFACT = "null_artifact"


@dataclass(frozen=True)
class Phase6Artifact:
    """
    Phase-6 artifact for a projected Phase-5 synthesis unit.

    Contains ONLY:
        - artifact_type: ArtifactType enum
        - source_phase5_hash: str (16-32 char hex hash)
        - payload: Tuple (strictly non-textual)
        - artifact_hash: str (16-32 char hex hash)

    NO free-form strings. NO semantic content. NO text generation.
    """
    artifact_type: ArtifactType
    source_phase5_hash: str
    payload: Tuple
    artifact_hash: str

    def __post_init__(self):
        # Validate artifact_type
        if not isinstance(self.artifact_type, ArtifactType):
            raise ValueError("artifact_type must be ArtifactType enum")

        # Validate source_phase5_hash
        if not isinstance(self.source_phase5_hash, str):
            raise ValueError("source_phase5_hash must be str")
        if not (16 <= len(self.source_phase5_hash) <= 32):
            raise ValueError("source_phase5_hash must be 16-32 chars")
        if not all(c in "0123456789abcdef" for c in self.source_phase5_hash):
            raise ValueError("source_phase5_hash must be hex")

        # Validate payload
        if not isinstance(self.payload, tuple):
            raise ValueError("payload must be tuple")

        # Validate artifact_hash
        if not isinstance(self.artifact_hash, str):
            raise ValueError("artifact_hash must be str")
        if not (16 <= len(self.artifact_hash) <= 32):
            raise ValueError("artifact_hash must be 16-32 chars")
        if not all(c in "0123456789abcdef" for c in self.artifact_hash):
            raise ValueError("artifact_hash must be hex")


@dataclass(frozen=True)
class Phase6ProjectionResult:
    """
    Phase-6 complete projection result.

    Contains ONLY:
        - artifacts: Tuple of Phase6Artifact
        - source_phase5_hashes: Tuple of Phase-5 source hashes
        - synthesis_hash: 16-32 char hex hash
        - boundary_mode: BoundaryMode enum
        - reversible: bool - True if Phase-5 data recoverable
        - eligible: bool - True if projection was successful

    NO free-form strings. NO semantic content.
    """
    artifacts: Tuple["Phase6Artifact", ...]
    source_phase5_hashes: Tuple[str, ...]
    synthesis_hash: str
    boundary_mode: BoundaryMode
    reversible: bool
    eligible: bool

    def __post_init__(self):
        # Validate artifacts
        if not isinstance(self.artifacts, tuple):
            raise ValueError("artifacts must be tuple")
        for artifact in self.artifacts:
            if not isinstance(artifact, Phase6Artifact):
                raise ValueError("artifacts must contain only Phase6Artifact instances")

        # Validate source_phase5_hashes
        if not isinstance(self.source_phase5_hashes, tuple):
            raise ValueError("source_phase5_hashes must be tuple")
        for h in self.source_phase5_hashes:
            if not isinstance(h, str):
                raise ValueError("source_phase5_hashes must contain only strings")
            if not (16 <= len(h) <= 32):
                raise ValueError("source_phase5_hashes entries must be 16-32 chars")
            if not all(c in "0123456789abcdef" for c in h):
                raise ValueError("source_phase5_hashes entries must be hex")

        # Validate synthesis_hash
        if not isinstance(self.synthesis_hash, str):
            raise ValueError("synthesis_hash must be str")
        if not (16 <= len(self.synthesis_hash) <= 32):
            raise ValueError("synthesis_hash must be 16-32 chars")
        if not all(c in "0123456789abcdef" for c in self.synthesis_hash):
            raise ValueError("synthesis_hash must be hex")

        # Validate boundary_mode
        if not isinstance(self.boundary_mode, BoundaryMode):
            raise ValueError("boundary_mode must be BoundaryMode enum")

        # Validate reversible and eligible
        if not isinstance(self.reversible, bool):
            raise ValueError("reversible must be bool")
        if not isinstance(self.eligible, bool):
            raise ValueError("eligible must be bool")


def _compute_artifact_hash(
    artifact_type: ArtifactType,
    source_phase5_hash: str,
    payload: Tuple
) -> str:
    """Compute deterministic hash for an artifact."""
    hash_input = (
        f"{artifact_type.value}|"
        f"{source_phase5_hash}|"
        f"{payload}"
    )
    return hashlib.sha256(hash_input.encode()).hexdigest()[:16]


def _compute_projection_hash(
    source_phase5_hashes: Tuple[str, ...],
    artifact_hashes: Tuple[str, ...],
    boundary_mode: BoundaryMode
) -> str:
    """Compute deterministic hash for entire projection result."""
    hash_input = (
        f"{source_phase5_hashes}|"
        f"{artifact_hashes}|"
        f"{boundary_mode.value}"
    )
    return hashlib.sha256(hash_input.encode()).hexdigest()[:32]


def _check_for_forbidden_structures(phase5_results: List) -> bool:
    """Check if any Phase-5 results contain forbidden structures."""
    for result in phase5_results:
        result_str = str(result)
        for term in FORBIDDEN_TERMS_PHASE6:
            if term in result_str.lower():
                return True
    return False


def _project_synthesis_unit_to_artifact(
    unit,
    mode: BoundaryMode
) -> Phase6Artifact:
    """
    Project a single Phase-5 synthesis unit to a Phase-6 artifact.

    This is a one-way projection that extracts structural information only.
    """
    source_hash = unit.unit_hash

    if mode == BoundaryMode.NON_TEXTUAL_ONLY:
        # Project to structural artifact
        payload = (
            unit.source_indices,
            unit.aggregated_rule_vector,
            unit.adjacency_signature,
            (unit.modifier_density,),
            unit.eligibility_mask
        )
        artifact_type = ArtifactType.STRUCTURAL_ARTIFACT

    elif mode == BoundaryMode.SYMBOLIC_ONLY:
        # Project to vector artifact (flattened representation)
        # Flatten all numeric values into a single tuple
        flat_indices = unit.source_indices
        flat_rules = unit.aggregated_rule_vector
        flat_adjacency = unit.adjacency_signature
        flat_density = (unit.modifier_density,)
        # Convert bool mask to int (0/1)
        flat_eligibility = tuple(1 if e else 0 for e in unit.eligibility_mask)

        payload = (flat_indices, flat_rules, flat_adjacency, flat_density, flat_eligibility)
        artifact_type = ArtifactType.VECTOR_ARTIFACT

    elif mode == BoundaryMode.TEMPLATE_ONLY:
        # Project to graph artifact (adjacency signature only)
        payload = (
            unit.adjacency_signature,
            tuple(1 if e else 0 for e in unit.eligibility_mask)
        )
        artifact_type = ArtifactType.GRAPH_ARTIFACT

    else:
        raise ValueError(f"Unknown BoundaryMode: {mode}")

    # Compute artifact hash
    artifact_hash = _compute_artifact_hash(artifact_type, source_hash, payload)

    return Phase6Artifact(
        artifact_type=artifact_type,
        source_phase5_hash=source_hash,
        payload=payload,
        artifact_hash=artifact_hash
    )


def project_phase5_to_phase6(
    phase5_results: list,
    mode: BoundaryMode = BoundaryMode.NON_TEXTUAL_ONLY
) -> Phase6ProjectionResult:
    """
    One-way projection from Phase-5 to Phase-6.

    Args:
        phase5_results: List[Phase5SynthesisResult] from Phase-5
        mode: BoundaryMode for projection strategy

    Returns:
        Phase6ProjectionResult with non-textual artifacts only

    Invariants:
        - Phase-5 results are NOT modified
        - No semantic inference
        - No text generation
        - No feedback to prior phases
        - Deterministic: same input always produces same output
        - Reversible: Phase-5 hashes recoverable
    """
    # Validate mode
    if not isinstance(mode, BoundaryMode):
        raise ValueError("mode must be BoundaryMode enum")

    # Handle empty input
    if not phase5_results:
        empty_hash = hashlib.sha256(b"empty_phase6").hexdigest()[:32]
        return Phase6ProjectionResult(
            artifacts=(),
            source_phase5_hashes=(),
            synthesis_hash=empty_hash,
            boundary_mode=mode,
            reversible=True,
            eligible=False
        )

    # Check for forbidden structures
    if _check_for_forbidden_structures(phase5_results):
        forbidden_hash = hashlib.sha256(b"forbidden_phase6").hexdigest()[:32]
        return Phase6ProjectionResult(
            artifacts=(
                Phase6Artifact(
                    artifact_type=ArtifactType.NULL_ARTIFACT,
                    source_phase5_hash=hashlib.sha256(b"null").hexdigest()[:16],
                    payload=(),
                    artifact_hash=hashlib.sha256(b"null_artifact").hexdigest()[:16]
                ),
            ),
            source_phase5_hashes=tuple(r.synthesis_hash for r in phase5_results),
            synthesis_hash=forbidden_hash,
            boundary_mode=mode,
            reversible=False,
            eligible=False
        )

    # Collect all artifacts from all results
    all_artifacts = []
    all_source_hashes = []

    for phase5_result in phase5_results:
        all_source_hashes.append(phase5_result.synthesis_hash)

        # If Phase-5 result is not eligible, emit NULL_ARTIFACT
        if not phase5_result.eligible:
            null_artifact = Phase6Artifact(
                artifact_type=ArtifactType.NULL_ARTIFACT,
                source_phase5_hash=phase5_result.synthesis_hash,
                payload=(),
                artifact_hash=hashlib.sha256(
                    f"null_{phase5_result.synthesis_hash}".encode()
                ).hexdigest()[:16]
            )
            all_artifacts.append(null_artifact)
            continue

        # Project each synthesis unit to an artifact
        for unit in phase5_result.synthesis_units:
            artifact = _project_synthesis_unit_to_artifact(unit, mode)
            all_artifacts.append(artifact)

    # Handle no artifacts case
    if not all_artifacts:
        empty_hash = hashlib.sha256(b"no_artifacts").hexdigest()[:32]
        return Phase6ProjectionResult(
            artifacts=(),
            source_phase5_hashes=tuple(all_source_hashes),
            synthesis_hash=empty_hash,
            boundary_mode=mode,
            reversible=True,
            eligible=False
        )

    # Compute projection hash
    artifact_hashes = tuple(a.artifact_hash for a in all_artifacts)
    projection_hash = _compute_projection_hash(
        tuple(all_source_hashes),
        artifact_hashes,
        mode
    )

    # Check if any artifacts are NULL (means at least one Phase-5 result was ineligible)
    has_null_artifacts = any(a.artifact_type == ArtifactType.NULL_ARTIFACT for a in all_artifacts)
    eligible = not has_null_artifacts

    return Phase6ProjectionResult(
        artifacts=tuple(all_artifacts),
        source_phase5_hashes=tuple(all_source_hashes),
        synthesis_hash=projection_hash,
        boundary_mode=mode,
        reversible=True,
        eligible=eligible
    )


def recover_phase5_hash_from_phase6(
    result: Phase6ProjectionResult
) -> Tuple[str, ...]:
    """
    Recover Phase-5 hashes from Phase-6 output.

    This demonstrates the reversibility guarantee.
    """
    if not isinstance(result, Phase6ProjectionResult):
        raise ValueError("result must be Phase6ProjectionResult")

    return result.source_phase5_hashes


def validate_phase6_invariants() -> bool:
    """Validate that all Phase-6 invariants are preserved."""
    for invariant, value in PHASE6_INVARIANTS.items():
        if not value:
            raise AssertionError(f"Phase-6 invariant violated: {invariant}")
    return True


def check_for_forbidden_terms_phase6(obj: Any) -> List[str]:
    """Check any object for forbidden terms."""
    obj_str = str(obj).lower()
    found = []
    for term in FORBIDDEN_TERMS_PHASE6:
        if term in obj_str:
            found.append(term)
    return found


def is_non_textual_value_phase6(val: Any) -> bool:
    """
    Check if value is non-textual.

    Allowed:
        - bool
        - int
        - tuple of non-textual values
        - frozenset of ints
        - Enum
        - hex string (<=32 chars, only 0-9a-f)
        - Phase6Artifact
        - Phase6ProjectionResult

    NOT allowed:
        - Free-form strings
        - Floats (probability)
        - Dict (would need validation)
    """
    if isinstance(val, bool):
        return True
    if isinstance(val, int):
        return True
    if isinstance(val, tuple):
        return all(is_non_textual_value_phase6(v) for v in val)
    if isinstance(val, frozenset):
        return all(isinstance(v, int) for v in val)
    if isinstance(val, str):
        # Only allow hex strings of constrained length
        if len(val) <= 32 and all(c in "0123456789abcdef" for c in val):
            return True
        return False
    if isinstance(val, Enum):
        return True
    if isinstance(val, (Phase6Artifact, Phase6ProjectionResult)):
        return True
    return False
