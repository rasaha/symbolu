"""
Phase-12: Generation Interface Schema
======================================

This module defines the contract between:
    - Deterministic routing layer (Phase-11B.3)
    - Probabilistic generation layer (LLM)
    - Deterministic verification layer (Phase-12)

Architecture:
    ┌─────────────────────────────────────────────────────────────┐
    │                    GOVERNED GENERATIVE COMPILER              │
    ├─────────────────────────────────────────────────────────────┤
    │                                                              │
    │  Phase-11B.3 (Deterministic)                                │
    │    ├── Ontological Routing → Family selection               │
    │    ├── PPV Canonicalization → Conditioning signal           │
    │    └── Template Retrieval → Few-shot context                │
    │                        ↓                                     │
    │  Phase-12 Generation (Probabilistic)                        │
    │    ├── PPV Conditioning Encoder                             │
    │    ├── Context Assembly                                     │
    │    └── LLM Call                                             │
    │                        ↓                                     │
    │  Phase-12 Verification (Deterministic)                      │
    │    ├── Structural Checks                                    │
    │    ├── Ontological Consistency                              │
    │    └── PPV Alignment Score                                  │
    │                                                              │
    └─────────────────────────────────────────────────────────────┘

INVARIANTS:
    - Routing is deterministic (same input → same routing decision)
    - PPV encoding is deterministic (same PPV → same conditioning)
    - Only LLM call is probabilistic
    - Verification is deterministic (same output → same verdict)
    - GOVERNED mode may reject outputs that OPEN mode accepts

CONSTRAINTS:
    - No training/fine-tuning at inference time
    - PPV encoder weights are frozen
    - No back-propagation from output to PPV definitions
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum, unique
from typing import (
    Dict,
    FrozenSet,
    List,
    Mapping,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    Union,
)

# =============================================================================
# Version
# =============================================================================

PHASE12_VERSION = "0.1.0"  # Draft


# =============================================================================
# PPV Conditioning Types
# =============================================================================

# PPV dimensions (from Phase-11B)
PPV_DIM_COUNT = 8
PPV_VALUE_RANGE = (0, 7)

# Canonical representatives from Phase-11B.3
CANONICAL_SUBBANDS = ("L0", "L2", "M0", "M2", "H0", "H1")


@unique
class PPVEncodingStrategy(str, Enum):
    """Strategy for encoding PPV into conditioning signal."""

    # Direct embedding: PPV → learned embedding vector
    EMBEDDING = "EMBEDDING"

    # Soft prompt: PPV → sequence of learned prompt tokens
    SOFT_PROMPT = "SOFT_PROMPT"

    # Adapter selection: PPV → LoRA/IA³ adapter weights
    ADAPTER = "ADAPTER"

    # Prefix: PPV → text prefix injected into prompt
    TEXT_PREFIX = "TEXT_PREFIX"


@dataclass(frozen=True)
class PPVConditioningConfig:
    """Configuration for PPV → conditioning signal conversion."""

    strategy: PPVEncodingStrategy

    # For EMBEDDING strategy
    embedding_dim: int = 64

    # For SOFT_PROMPT strategy
    num_prompt_tokens: int = 8

    # For ADAPTER strategy
    adapter_rank: int = 8

    # For TEXT_PREFIX strategy
    prefix_template: str = "[PPV:{ppv_signature}]"

    # Whether encoder weights are frozen (MUST be True for governance)
    frozen: bool = True


@dataclass(frozen=True)
class PPVConditioningSignal:
    """
    The conditioning signal derived from PPV.

    This is what gets passed to the generation layer.
    PPV values → deterministic encoding → conditioning signal.
    """

    # Original PPV values (0-7 each)
    raw_ppv: Tuple[int, ...]

    # Canonical signature from Phase-11B.3 (e.g., "L0_M2_H1_...")
    canonical_signature: str

    # Encoding strategy used
    strategy: PPVEncodingStrategy

    # The actual conditioning data (strategy-dependent)
    # - EMBEDDING: Tuple[float, ...] of embedding_dim floats
    # - SOFT_PROMPT: Tuple[int, ...] of token IDs
    # - ADAPTER: str adapter identifier
    # - TEXT_PREFIX: str text to prepend
    conditioning_data: Union[Tuple[float, ...], Tuple[int, ...], str]

    def __post_init__(self) -> None:
        if len(self.raw_ppv) != PPV_DIM_COUNT:
            raise ValueError(f"raw_ppv must have {PPV_DIM_COUNT} elements")

    def signal_hash(self) -> str:
        """Deterministic hash of conditioning signal."""
        canonical = f"ppv:{self.raw_ppv}|sig:{self.canonical_signature}|strategy:{self.strategy.value}"
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]


# =============================================================================
# Ontological Routing Context
# =============================================================================

@unique
class OntologicalFamily(str, Enum):
    """Ontological families (from Phase-11B)."""
    ACTING = "ACTING"
    TAGGING = "TAGGING"
    FORMING = "FORMING"
    THINKING = "THINKING"
    DIRECTING = "DIRECTING"
    REASONING = "REASONING"
    PURPOSING = "PURPOSING"
    META_OBSERVING = "META_OBSERVING"
    UNIFYING = "UNIFYING"
    ABSOLVING = "ABSOLVING"


@dataclass(frozen=True)
class OntologicalContext:
    """
    Ontological routing context from Phase-11B.

    Determines which "expert" or "head" handles generation.
    """

    # Primary family (from ontological_path[0])
    family: OntologicalFamily

    # Full ontological path
    path: Tuple[str, ...]

    # Slot plan (determines VC structure)
    slot_plan: str

    # VC facts required for this slot plan
    required_vc_facts: Tuple[str, ...]

    def context_hash(self) -> str:
        """Deterministic hash of ontological context."""
        canonical = f"family:{self.family.value}|path:{self.path}|slot:{self.slot_plan}"
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]


# =============================================================================
# Template Retrieval (Few-Shot Context)
# =============================================================================

@dataclass(frozen=True)
class RetrievedTemplate:
    """
    A template retrieved for few-shot context.

    Templates are no longer direct output - they are examples
    that guide generation.
    """

    template_id: str
    template_text: str

    # Similarity to current request (for ranking)
    similarity_score: float

    # The routing key that produced this template
    family: str
    variant_id: str
    slot_plan: str


@dataclass(frozen=True)
class FewShotContext:
    """
    Few-shot examples assembled from template retrieval.
    """

    # Retrieved templates, ordered by relevance
    templates: Tuple[RetrievedTemplate, ...]

    # Maximum number of templates to include in prompt
    max_examples: int = 3

    # Whether to include template metadata in prompt
    include_metadata: bool = False

    def get_top_k(self, k: Optional[int] = None) -> Tuple[RetrievedTemplate, ...]:
        """Get top-k templates by similarity."""
        limit = k if k is not None else self.max_examples
        return self.templates[:limit]


# =============================================================================
# Generation Context (Input to LLM)
# =============================================================================

@unique
class RenderMode(str, Enum):
    """Render mode affects verification strictness, not generation."""
    OPEN = "OPEN"
    GOVERNED = "GOVERNED"


@dataclass(frozen=True)
class GenerationContext:
    """
    Complete context for generation.

    This is assembled from Phase-11B routing and passed to the LLM.
    Everything here is deterministic except the LLM's response.
    """

    # Request identification
    request_id: str
    artifact_hash: str

    # Ontological routing (deterministic)
    ontological: OntologicalContext

    # PPV conditioning (deterministic encoding)
    ppv_signal: PPVConditioningSignal

    # Few-shot context (deterministic retrieval)
    few_shot: FewShotContext

    # VC source data for slot filling
    vc_source_data: Mapping[str, str]

    # Mode (affects verification, not generation)
    mode: RenderMode

    # Generation parameters (deterministic config, probabilistic execution)
    temperature: float = 0.7
    max_tokens: int = 512

    def context_hash(self) -> str:
        """
        Deterministic hash of generation context.

        Same context → same hash (even if LLM output differs).
        """
        canonical = (
            f"req:{self.request_id}|"
            f"ont:{self.ontological.context_hash()}|"
            f"ppv:{self.ppv_signal.signal_hash()}|"
            f"mode:{self.mode.value}"
        )
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]


# =============================================================================
# Generation Result (Output from LLM)
# =============================================================================

@dataclass(frozen=True)
class RawGenerationResult:
    """
    Raw output from LLM before verification.
    """

    # The generated text
    text: str

    # Generation metadata
    model_id: str
    tokens_used: int
    generation_time_ms: int

    # The context that produced this (for tracing)
    context_hash: str

    def output_hash(self) -> str:
        """Hash of generated text."""
        return hashlib.sha256(self.text.encode()).hexdigest()[:16]


# =============================================================================
# Verification Layer
# =============================================================================

@unique
class VerificationStatus(str, Enum):
    """Verification outcome."""
    PASSED = "PASSED"
    FAILED_STRUCTURAL = "FAILED_STRUCTURAL"
    FAILED_ONTOLOGICAL = "FAILED_ONTOLOGICAL"
    FAILED_PPV_ALIGNMENT = "FAILED_PPV_ALIGNMENT"
    FAILED_CONTENT_POLICY = "FAILED_CONTENT_POLICY"


@dataclass(frozen=True)
class VerificationCheck:
    """A single verification check result."""

    check_name: str
    passed: bool
    score: float  # 0.0 to 1.0
    details: str


@dataclass(frozen=True)
class VerificationResult:
    """
    Complete verification result.

    Verification is deterministic: same output → same verdict.
    """

    # Overall status
    status: VerificationStatus

    # Individual checks
    checks: Tuple[VerificationCheck, ...]

    # Aggregate scores
    structural_score: float
    ontological_score: float
    ppv_alignment_score: float

    # Whether output is allowed in current mode
    allowed_in_open: bool
    allowed_in_governed: bool

    def is_allowed(self, mode: RenderMode) -> bool:
        """Check if output is allowed in given mode."""
        if mode == RenderMode.OPEN:
            return self.allowed_in_open
        return self.allowed_in_governed


# =============================================================================
# Final Response
# =============================================================================

GENERATION_BLOCKED = "GENERATION_BLOCKED"


@dataclass(frozen=True)
class Phase12Response:
    """
    Final Phase-12 response after generation and verification.
    """

    # Output text (or GENERATION_BLOCKED)
    output_text: str

    # Whether output was blocked
    blocked: bool

    # Generation trace
    context_hash: str
    generation_hash: Optional[str]  # None if blocked before generation

    # Verification result
    verification: Optional[VerificationResult]

    # Routing trace (from Phase-11B.3)
    routing_trace_hash: str

    # Mode used
    mode: RenderMode

    # Ledger span ID (deterministic)
    ledger_span_id: str

    def response_hash(self) -> str:
        """Deterministic hash of response."""
        canonical = (
            f"output:{self.output_text}|"
            f"blocked:{self.blocked}|"
            f"mode:{self.mode.value}"
        )
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]


# =============================================================================
# Protocol Definitions (Interfaces)
# =============================================================================

class PPVEncoder(Protocol):
    """Protocol for PPV → conditioning signal encoder."""

    def encode(
        self,
        ppv_values: Tuple[int, ...],
        canonical_signature: str,
    ) -> PPVConditioningSignal:
        """Encode PPV values into conditioning signal."""
        ...

    @property
    def config(self) -> PPVConditioningConfig:
        """Get encoder configuration."""
        ...


class TemplateRetriever(Protocol):
    """Protocol for template retrieval."""

    def retrieve(
        self,
        family: OntologicalFamily,
        canonical_signature: str,
        slot_plan: str,
        top_k: int = 5,
    ) -> Tuple[RetrievedTemplate, ...]:
        """Retrieve similar templates for few-shot context."""
        ...


class Generator(Protocol):
    """Protocol for LLM generation."""

    def generate(
        self,
        context: GenerationContext,
    ) -> RawGenerationResult:
        """Generate text from context."""
        ...


class Verifier(Protocol):
    """Protocol for output verification."""

    def verify(
        self,
        context: GenerationContext,
        generation: RawGenerationResult,
    ) -> VerificationResult:
        """Verify generated output."""
        ...


# =============================================================================
# Pipeline Orchestrator
# =============================================================================

@dataclass
class Phase12Pipeline:
    """
    Orchestrates the Phase-12 generation pipeline.

    Pipeline stages:
        1. Receive routing result from Phase-11B.3
        2. Encode PPV → conditioning signal
        3. Retrieve few-shot templates
        4. Assemble generation context
        5. Call LLM (probabilistic)
        6. Verify output (deterministic)
        7. Return response or GENERATION_BLOCKED
    """

    ppv_encoder: PPVEncoder
    template_retriever: TemplateRetriever
    generator: Generator
    verifier: Verifier

    def execute(
        self,
        request_id: str,
        artifact_hash: str,
        ontological_path: Tuple[str, ...],
        ppv_values: Tuple[int, ...],
        canonical_signature: str,
        slot_plan: str,
        vc_facts: Tuple[str, ...],
        vc_source_data: Mapping[str, str],
        mode: RenderMode,
    ) -> Phase12Response:
        """
        Execute the full Phase-12 pipeline.

        All inputs come from Phase-11B.3 routing.
        """
        # Import here to avoid circular dependency
        from phase11b1_routing import LAYER_TO_FAMILY

        # Stage 1: Parse ontological context
        family_str = ontological_path[0] if ontological_path else "DEFAULT"
        family = OntologicalFamily(family_str) if family_str in [f.value for f in OntologicalFamily] else None

        if family is None:
            # Fail-closed: unknown family
            return Phase12Response(
                output_text=GENERATION_BLOCKED,
                blocked=True,
                context_hash="",
                generation_hash=None,
                verification=None,
                routing_trace_hash=hashlib.sha256(f"{ontological_path}".encode()).hexdigest()[:16],
                mode=mode,
                ledger_span_id=f"span_{request_id[:16]}",
            )

        ontological = OntologicalContext(
            family=family,
            path=ontological_path,
            slot_plan=slot_plan,
            required_vc_facts=vc_facts,
        )

        # Stage 2: Encode PPV
        ppv_signal = self.ppv_encoder.encode(ppv_values, canonical_signature)

        # Stage 3: Retrieve templates
        templates = self.template_retriever.retrieve(
            family=family,
            canonical_signature=canonical_signature,
            slot_plan=slot_plan,
        )
        few_shot = FewShotContext(templates=templates)

        # Stage 4: Assemble context
        context = GenerationContext(
            request_id=request_id,
            artifact_hash=artifact_hash,
            ontological=ontological,
            ppv_signal=ppv_signal,
            few_shot=few_shot,
            vc_source_data=vc_source_data,
            mode=mode,
        )

        # Stage 5: Generate (probabilistic)
        generation = self.generator.generate(context)

        # Stage 6: Verify (deterministic)
        verification = self.verifier.verify(context, generation)

        # Stage 7: Return based on verification
        if not verification.is_allowed(mode):
            return Phase12Response(
                output_text=GENERATION_BLOCKED,
                blocked=True,
                context_hash=context.context_hash(),
                generation_hash=generation.output_hash(),
                verification=verification,
                routing_trace_hash=ontological.context_hash(),
                mode=mode,
                ledger_span_id=f"span_{request_id[:16]}",
            )

        return Phase12Response(
            output_text=generation.text,
            blocked=False,
            context_hash=context.context_hash(),
            generation_hash=generation.output_hash(),
            verification=verification,
            routing_trace_hash=ontological.context_hash(),
            mode=mode,
            ledger_span_id=f"span_{request_id[:16]}",
        )


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Version
    "PHASE12_VERSION",
    # Constants
    "PPV_DIM_COUNT",
    "PPV_VALUE_RANGE",
    "CANONICAL_SUBBANDS",
    "GENERATION_BLOCKED",
    # Enums
    "PPVEncodingStrategy",
    "OntologicalFamily",
    "RenderMode",
    "VerificationStatus",
    # Config
    "PPVConditioningConfig",
    # Data classes - PPV
    "PPVConditioningSignal",
    # Data classes - Ontological
    "OntologicalContext",
    # Data classes - Retrieval
    "RetrievedTemplate",
    "FewShotContext",
    # Data classes - Generation
    "GenerationContext",
    "RawGenerationResult",
    # Data classes - Verification
    "VerificationCheck",
    "VerificationResult",
    # Data classes - Response
    "Phase12Response",
    # Protocols
    "PPVEncoder",
    "TemplateRetriever",
    "Generator",
    "Verifier",
    # Pipeline
    "Phase12Pipeline",
]
