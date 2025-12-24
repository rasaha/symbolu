"""
Phase-12: Proof of Concept - Governed Generative Pipeline
=========================================================

This module demonstrates the complete Phase-12 governed generative pipeline,
integrating all components:

    1. PPV Conditioning Encoder (deterministic)
    2. Template Retriever (deterministic)
    3. Generator (probabilistic - mock for PoC)
    4. Verifier (deterministic)

Architecture:
    ┌─────────────────────────────────────────────────────────────────┐
    │              GOVERNED GENERATIVE COMPILER (PoC)                 │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                  │
    │  Phase-11B.3 Input                                              │
    │    ↓                                                             │
    │  PPV Encoding ─────────────────────────────────────────────────  │
    │    ├── Raw PPV → Canonical Signature                            │
    │    └── Signature → Conditioning Signal                          │
    │    ↓                                                             │
    │  Template Retrieval ───────────────────────────────────────────  │
    │    ├── Family + Signature → Candidate Templates                 │
    │    └── Similarity Scoring → Ranked Few-Shot Context             │
    │    ↓                                                             │
    │  Context Assembly ─────────────────────────────────────────────  │
    │    └── GenerationContext (all deterministic components)         │
    │    ↓                                                             │
    │  LLM Generation ────────────────────────────────────────────── ◀ PROBABILISTIC
    │    └── MockGenerator (for PoC) / Real LLM (production)          │
    │    ↓                                                             │
    │  Verification ─────────────────────────────────────────────────  │
    │    ├── Structural Check                                         │
    │    ├── Ontological Check                                        │
    │    ├── PPV Alignment Check                                      │
    │    └── Content Policy Check                                     │
    │    ↓                                                             │
    │  Output (or GENERATION_BLOCKED)                                 │
    │                                                                  │
    └─────────────────────────────────────────────────────────────────┘

INVARIANTS:
    - Only LLM generation is probabilistic
    - All other components are deterministic
    - Same routing → same conditioning → (probabilistic generation) → deterministic verification

Usage:
    from phase12_poc import run_governed_generation

    result = run_governed_generation(
        family=OntologicalFamily.THINKING,
        ppv_values=(0, 1, 2, 3, 4, 5, 6, 7),
        canonical_signature="L0_L0_L2_M0_M0_M2_H0_H1",
        slot_plan="basic_vc",
        vc_data={"observation": "The sky is blue."},
        mode=RenderMode.GOVERNED,
    )
"""

from __future__ import annotations

import hashlib
import random
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from phase12_schema import (
    FewShotContext,
    GenerationContext,
    OntologicalContext,
    OntologicalFamily,
    Phase12Pipeline,
    Phase12Response,
    PPVConditioningSignal,
    RawGenerationResult,
    RenderMode,
    VerificationResult,
    GENERATION_BLOCKED,
)
from phase12_ppv_encoder import (
    FrozenPPVEncoder,
    create_text_prefix_encoder,
)
from phase12_verifier import (
    Phase12Verifier,
    create_lenient_verifier,
)
from phase12_retriever import (
    Phase12TemplateRetriever,
    build_few_shot_context,
    create_default_retriever,
)


# =============================================================================
# Mock Generator (for PoC)
# =============================================================================

@dataclass
class MockGenerator:
    """
    Mock LLM generator for proof-of-concept.

    In production, this would call an actual LLM API.
    For PoC, it generates deterministic-ish output based on context.
    """

    model_id: str = "mock-llm-v1"
    deterministic_mode: bool = False  # If True, use hash-based generation

    def generate(self, context: GenerationContext) -> RawGenerationResult:
        """
        Generate text based on context.

        For PoC, generates output that:
            1. Includes family-appropriate markers
            2. Reflects PPV energy level
            3. Uses few-shot templates as structure guide
        """
        start_time = time.time()

        # Extract key context elements
        family = context.ontological.family
        ppv_signal = context.ppv_signal
        templates = context.few_shot.get_top_k(2)

        # Determine energy from canonical signature
        sig_parts = ppv_signal.canonical_signature.split("_")
        high_count = sum(1 for p in sig_parts if p.startswith("H"))
        low_count = sum(1 for p in sig_parts if p.startswith("L"))

        if high_count > low_count:
            energy_words = ["boldly", "powerfully", "intensely"]
            energy_level = "HIGH"
        elif low_count > high_count:
            energy_words = ["quietly", "gently", "calmly"]
            energy_level = "LOW"
        else:
            energy_words = ["steadily", "reasonably", "moderately"]
            energy_level = "MID"

        # Generate family-specific output
        vc_observation = context.vc_source_data.get("observation", "the situation")

        family_outputs = {
            OntologicalFamily.THINKING: (
                f"I {random.choice(energy_words)} consider and reflect upon {vc_observation}. "
                f"Perhaps we might think about the deeper implications. "
                f"We should ponder these matters carefully before proceeding."
            ),
            OntologicalFamily.FORMING: (
                f"Let us {random.choice(energy_words)} create something from {vc_observation}. "
                f"We can build and design a meaningful response. "
                f"Through shaping and crafting, we develop our vision."
            ),
            OntologicalFamily.ACTING: (
                f"We {random.choice(energy_words)} act upon {vc_observation}. "
                f"It is time to execute and implement our plans. "
                f"Through decisive action, we move forward."
            ),
            OntologicalFamily.REASONING: (
                f"Because of {vc_observation}, we {random.choice(energy_words)} reason. "
                f"Therefore, the logic leads us to this conclusion. "
                f"Thus, we can deduce the appropriate path forward."
            ),
            OntologicalFamily.DIRECTING: (
                f"Let us {random.choice(energy_words)} guide our attention to {vc_observation}. "
                f"We direct and navigate toward our objective. "
                f"The path forward becomes clear as we orient ourselves."
            ),
        }

        # Default output for other families
        default_output = (
            f"We {random.choice(energy_words)} engage with {vc_observation}. "
            f"This [{family.value}] approach reveals new perspectives. "
            f"We proceed with intention and purpose."
        )

        generated_text = family_outputs.get(family, default_output)

        # Add PPV prefix if using text prefix strategy
        if isinstance(ppv_signal.conditioning_data, str):
            generated_text = f"{ppv_signal.conditioning_data}\n{generated_text}"

        # Calculate generation time
        generation_time_ms = int((time.time() - start_time) * 1000)

        return RawGenerationResult(
            text=generated_text,
            model_id=self.model_id,
            tokens_used=len(generated_text.split()),
            generation_time_ms=generation_time_ms,
            context_hash=context.context_hash(),
        )


# =============================================================================
# Governed Generation Pipeline
# =============================================================================

@dataclass
class GovernedGenerativePipeline:
    """
    Complete governed generative pipeline.

    Orchestrates:
        1. PPV encoding (deterministic)
        2. Template retrieval (deterministic)
        3. Context assembly (deterministic)
        4. Generation (probabilistic)
        5. Verification (deterministic)
    """

    ppv_encoder: FrozenPPVEncoder
    retriever: Phase12TemplateRetriever
    generator: MockGenerator
    verifier: Phase12Verifier

    def generate(
        self,
        family: OntologicalFamily,
        ppv_values: Tuple[int, ...],
        canonical_signature: str,
        slot_plan: str,
        vc_data: Dict[str, str],
        mode: RenderMode = RenderMode.GOVERNED,
        request_id: Optional[str] = None,
    ) -> Phase12Response:
        """
        Execute the complete governed generation pipeline.

        Returns Phase12Response with either generated text or GENERATION_BLOCKED.
        """
        # Generate request ID if not provided
        if request_id is None:
            request_id = f"req_{hashlib.sha256(str(time.time()).encode()).hexdigest()[:12]}"

        # 1. Encode PPV (deterministic)
        ppv_signal = self.ppv_encoder.encode(ppv_values, canonical_signature)

        # 2. Retrieve templates (deterministic)
        few_shot = build_few_shot_context(
            self.retriever,
            family,
            canonical_signature,
            slot_plan,
            max_examples=3,
        )

        # 3. Assemble context (deterministic)
        ontological = OntologicalContext(
            family=family,
            path=(family.value,),
            slot_plan=slot_plan,
            required_vc_facts=tuple(vc_data.keys()),
        )

        context = GenerationContext(
            request_id=request_id,
            artifact_hash=hashlib.sha256(str(vc_data).encode()).hexdigest(),
            ontological=ontological,
            ppv_signal=ppv_signal,
            few_shot=few_shot,
            vc_source_data=vc_data,
            mode=mode,
        )

        # 4. Generate (PROBABILISTIC - only non-deterministic step)
        generation = self.generator.generate(context)

        # 5. Verify (deterministic)
        verification = self.verifier.verify(context, generation)

        # 6. Build response
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
# Factory Functions
# =============================================================================

def create_default_pipeline() -> GovernedGenerativePipeline:
    """Create pipeline with default components."""
    return GovernedGenerativePipeline(
        ppv_encoder=create_text_prefix_encoder(),
        retriever=create_default_retriever(),
        generator=MockGenerator(),
        verifier=create_lenient_verifier(),  # Lenient for PoC demo
    )


# =============================================================================
# Convenience Function
# =============================================================================

def run_governed_generation(
    family: OntologicalFamily,
    ppv_values: Tuple[int, ...],
    canonical_signature: str,
    slot_plan: str = "basic_vc",
    vc_data: Optional[Dict[str, str]] = None,
    mode: RenderMode = RenderMode.GOVERNED,
) -> Phase12Response:
    """
    Run governed generation with default pipeline.

    Convenience function for quick demonstrations.
    """
    if vc_data is None:
        vc_data = {"observation": "an interesting phenomenon"}

    pipeline = create_default_pipeline()
    return pipeline.generate(
        family=family,
        ppv_values=ppv_values,
        canonical_signature=canonical_signature,
        slot_plan=slot_plan,
        vc_data=vc_data,
        mode=mode,
    )


# =============================================================================
# Demo / CLI
# =============================================================================

def run_demo():
    """
    Run a demonstration of the governed generative pipeline.
    """
    print("=" * 70)
    print("PHASE-12: GOVERNED GENERATIVE PIPELINE - PROOF OF CONCEPT")
    print("=" * 70)
    print()

    # Create pipeline
    pipeline = create_default_pipeline()

    # Demo 1: THINKING family, mixed energy
    print("Demo 1: THINKING family, mixed PPV signature")
    print("-" * 50)
    result1 = pipeline.generate(
        family=OntologicalFamily.THINKING,
        ppv_values=(0, 1, 2, 3, 4, 5, 6, 7),
        canonical_signature="L0_L0_L2_M0_M0_M2_H0_H1",
        slot_plan="basic_vc",
        vc_data={"observation": "the complexity of human thought"},
        mode=RenderMode.GOVERNED,
    )
    print(f"Blocked: {result1.blocked}")
    print(f"Mode: {result1.mode.value}")
    print(f"Output:\n{result1.output_text}")
    print(f"Verification Status: {result1.verification.status.value if result1.verification else 'N/A'}")
    print()

    # Demo 2: FORMING family, high energy
    print("Demo 2: FORMING family, high energy signature")
    print("-" * 50)
    result2 = pipeline.generate(
        family=OntologicalFamily.FORMING,
        ppv_values=(7, 7, 7, 7, 7, 7, 7, 7),
        canonical_signature="H1_H1_H1_H1_H1_H1_H1_H1",
        slot_plan="basic_vc",
        vc_data={"observation": "a vision for the future"},
        mode=RenderMode.GOVERNED,
    )
    print(f"Blocked: {result2.blocked}")
    print(f"Mode: {result2.mode.value}")
    print(f"Output:\n{result2.output_text}")
    print(f"Verification Status: {result2.verification.status.value if result2.verification else 'N/A'}")
    print()

    # Demo 3: REASONING family, low energy
    print("Demo 3: REASONING family, low energy signature")
    print("-" * 50)
    result3 = pipeline.generate(
        family=OntologicalFamily.REASONING,
        ppv_values=(0, 0, 0, 0, 0, 0, 0, 0),
        canonical_signature="L0_L0_L0_L0_L0_L0_L0_L0",
        slot_plan="basic_vc",
        vc_data={"observation": "the evidence before us"},
        mode=RenderMode.OPEN,
    )
    print(f"Blocked: {result3.blocked}")
    print(f"Mode: {result3.mode.value}")
    print(f"Output:\n{result3.output_text}")
    print(f"Verification Status: {result3.verification.status.value if result3.verification else 'N/A'}")
    print()

    # Summary
    print("=" * 70)
    print("PIPELINE SUMMARY")
    print("=" * 70)
    print(f"Total Runs: 3")
    print(f"Passed: {sum(1 for r in [result1, result2, result3] if not r.blocked)}")
    print(f"Blocked: {sum(1 for r in [result1, result2, result3] if r.blocked)}")
    print()
    print("KEY OBSERVATIONS:")
    print("  1. PPV conditioning affects generation style (energy level)")
    print("  2. Family determines semantic content (thinking/forming/reasoning)")
    print("  3. Verification is deterministic (same output → same verdict)")
    print("  4. Only LLM generation is probabilistic")
    print("=" * 70)


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Mock generator
    "MockGenerator",
    # Pipeline
    "GovernedGenerativePipeline",
    # Factory
    "create_default_pipeline",
    # Convenience
    "run_governed_generation",
    # Demo
    "run_demo",
]


if __name__ == "__main__":
    run_demo()
