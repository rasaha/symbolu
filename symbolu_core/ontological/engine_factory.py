#!/usr/bin/env python3
"""
Ontological Engine Factory
==========================

Provides a unified interface for creating and using ontological engines.
Supports switching between multiple engine types:

ENTERPRISE ENGINES (Classification + RAG):
------------------------------------------
1. MiniLM V2 (MINILM_V2)
   - Uses pre-trained MiniLM encoder
   - 156D output (12D ontological + 144D Bhava)
   - Best for classification and RAG
   - Faster training, smaller model

2. SymbolU12 Hybrid (SYMBOLU12_HYBRID)
   - MiniLM encoder + SymbolU12 layers
   - Best of both: transfer learning + interpretability
   - 156D output with coherence matrix

GENERATIVE ENGINES (LLM Capabilities):
--------------------------------------
3. SymbolU12 LLM (SYMBOLU12_LLM)
   - Full 12-layer ontological transformer
   - Token-level generation capabilities
   - Explicit cognitive layers

4. SymbolU12 LLM + Bhava (SYMBOLU12_LLM_BHAVA)
   - Full LLM with Vedic Bhava relationships
   - 156D output with Drishti attention
   - Interpretable inter-layer relationships

CPU-FRIENDLY ENGINES:
--------------------
5. SymbolU12 Optimized + Bhava (SYMBOLU12_OPTIMIZED_BHAVA)
   - CPU-friendly 256D model
   - Full Bhava relationship support
   - Good for edge deployment

6. SymbolU12 Tiny + Bhava (SYMBOLU12_TINY_BHAVA)
   - Smallest model (128D)
   - For IoT/edge devices

Usage:
------
    from symbolu_core.ontological.engine_factory import (
        create_ontological_engine,
        OntologicalEngineType,
    )

    # Enterprise: MiniLM-based engine (default)
    engine = create_ontological_engine(OntologicalEngineType.MINILM_V2)

    # Enterprise: Hybrid (best of both)
    engine = create_ontological_engine(OntologicalEngineType.SYMBOLU12_HYBRID)

    # Generative: Full LLM with Bhava
    engine = create_ontological_engine(OntologicalEngineType.SYMBOLU12_LLM_BHAVA)

    # CPU-Friendly: Optimized with Bhava
    engine = create_ontological_engine(OntologicalEngineType.SYMBOLU12_OPTIMIZED_BHAVA)

    # All engines provide consistent output format
    result = engine.analyze("What is consciousness?")
    print(result["dominant_layer"])
    print(result["confidence"])
    print(result["bhava_vector"])  # 144D inter-layer relationships
"""

from enum import Enum
from typing import Dict, Any, Optional, Union
from abc import ABC, abstractmethod

# Check for PyTorch
try:
    import torch
    import torch.nn as nn
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False


class OntologicalEngineType(Enum):
    """Available ontological engine types."""

    MINILM_V2 = "minilm_v2"
    """MiniLM-based engine with 156D output (12D onto + 144D Bhava)"""

    SYMBOLU12_LLM = "symbolu12_llm"
    """Full 12-layer ontological transformer LLM"""

    SYMBOLU12_SMALL = "symbolu12_small"
    """Small SymbolU12 for testing (256D)"""

    SYMBOLU12_BASE = "symbolu12_base"
    """Base SymbolU12 (768D)"""

    SYMBOLU12_LARGE = "symbolu12_large"
    """Large SymbolU12 (1024D)"""

    # Bhava-enhanced engines (156D output: 12D onto + 144D bhava)
    SYMBOLU12_LLM_BHAVA = "symbolu12_llm_bhava"
    """Full SymbolU12 LLM with Vedic Bhava relationships (768D, 156D output)"""

    SYMBOLU12_OPTIMIZED_BHAVA = "symbolu12_optimized_bhava"
    """CPU-friendly SymbolU12 with Bhava relationships (256D, 156D output)"""

    SYMBOLU12_TINY_BHAVA = "symbolu12_tiny_bhava"
    """Tiny SymbolU12 with Bhava for edge devices (128D, 156D output)"""

    SYMBOLU12_HYBRID = "symbolu12_hybrid"
    """MiniLM encoder + SymbolU12 layers (best of both)"""


class OntologicalEngineInterface(ABC):
    """
    Abstract interface for all ontological engines.

    All engines must implement:
    - analyze(text) -> Dict with standard output format
    - forward(x) -> Dict with model outputs
    """

    @abstractmethod
    def analyze(self, text: str) -> Dict[str, Any]:
        """
        Analyze text and return ontological classification.

        Returns:
            Dict with:
                - dominant_layer: str (e.g., "O5_COGNITION")
                - confidence: float (0-1)
                - coherence: float (0-1)
                - uncertainty: float (0-1)
                - certainty_level: str
                - ontological_vector: List[float] (12D)
                - bhava_vector: List[float] (144D for V2, variable for LLM)
                - full_vector: List[float] (156D for V2)
                - reasoning_score: float
                - creativity_score: float
                - strongest_relationships: List[Dict]
        """
        pass

    @abstractmethod
    def get_engine_type(self) -> OntologicalEngineType:
        """Return the engine type."""
        pass

    @abstractmethod
    def get_output_dim(self) -> int:
        """Return the output vector dimension."""
        pass


if PYTORCH_AVAILABLE:
    from symbolu_core.ontological.types import LAYER_NAMES, LAYER_INDEX

    class MiniLMEngineWrapper(OntologicalEngineInterface, nn.Module):
        """
        Wrapper for UnifiedOntologicalEngineV2 (MiniLM-based).

        Provides the standard OntologicalEngineInterface.
        """

        def __init__(self):
            nn.Module.__init__(self)
            from symbolu_core.ontological.unified_engine import UnifiedOntologicalEngineV2
            self._engine = UnifiedOntologicalEngineV2()

        def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
            return self._engine.forward(x)

        def analyze(self, text: str) -> Dict[str, Any]:
            return self._engine.analyze(text)

        def get_engine_type(self) -> OntologicalEngineType:
            return OntologicalEngineType.MINILM_V2

        def get_output_dim(self) -> int:
            return 156  # 12D onto + 144D bhava

        def load_state_dict(self, state_dict, strict=True):
            return self._engine.load_state_dict(state_dict, strict)

        def state_dict(self):
            return self._engine.state_dict()

        @property
        def encoder(self):
            return self._engine.encoder


    class SymbolU12EngineWrapper(OntologicalEngineInterface, nn.Module):
        """
        Wrapper for SymbolU12_LLM to provide OntologicalEngineInterface.

        Adapts the LLM's token-level outputs to document-level analysis.
        """

        def __init__(
            self,
            vocab_size: int = 50257,
            embed_dim: int = 768,
            max_seq_len: int = 2048,
            num_heads: int = 8,
        ):
            nn.Module.__init__(self)
            from symbolu_core.ontological.symbolu12_llm import SymbolU12_LLM
            self._llm = SymbolU12_LLM(
                vocab_size=vocab_size,
                embed_dim=embed_dim,
                max_seq_len=max_seq_len,
                num_heads=num_heads,
            )
            self._tokenizer = None
            self._embed_dim = embed_dim

        def _get_tokenizer(self):
            """Lazy load tokenizer."""
            if self._tokenizer is None:
                try:
                    from transformers import GPT2Tokenizer
                    self._tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
                    self._tokenizer.pad_token = self._tokenizer.eos_token
                except ImportError:
                    # Fallback: simple character tokenizer
                    self._tokenizer = SimpleTokenizer()
            return self._tokenizer

        def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
            """Forward pass for token IDs."""
            return self._llm.forward(x)

        def analyze(self, text: str) -> Dict[str, Any]:
            """
            Analyze text using SymbolU12 LLM.

            Tokenizes text, runs through all 12 layers, and aggregates
            to document-level ontological classification.
            """
            import numpy as np

            self._llm.eval()
            tokenizer = self._get_tokenizer()

            # Tokenize
            if hasattr(tokenizer, 'encode'):
                tokens = tokenizer.encode(text, return_tensors="pt")
            else:
                tokens = tokenizer(text)

            device = next(self._llm.parameters()).device
            tokens = tokens.to(device)

            with torch.no_grad():
                outputs = self._llm(tokens)

            # Aggregate layer embeddings to get 12D ontological vector
            layer_embeds = outputs['layer_embeddings']  # List of [B, dim]
            stacked = torch.stack(layer_embeds, dim=1)  # [B, 12, dim]

            # Compute layer activations (mean activation per layer)
            layer_activations = stacked.abs().mean(dim=-1).squeeze(0)  # [12]
            probs = torch.softmax(layer_activations, dim=0).cpu().numpy()

            # Get dominant layer
            dominant_idx = int(np.argmax(probs))
            dominant_layer = LAYER_NAMES[dominant_idx]
            confidence = float(probs[dominant_idx])

            # Get coherence from C' matrix
            coherence = float(outputs['global_coherence'].mean().item())

            # Get witness confidence as uncertainty proxy
            witness_conf = float(outputs['witness_confidence'].mean().item())
            uncertainty = 1.0 - witness_conf

            # Certainty level
            if uncertainty > 0.7:
                certainty_level = "very_uncertain"
            elif uncertainty > 0.4:
                certainty_level = "uncertain"
            elif uncertainty > 0.2:
                certainty_level = "moderate"
            else:
                certainty_level = "confident"

            # Build output
            probabilities = {
                LAYER_NAMES[i]: float(probs[i])
                for i in range(len(LAYER_NAMES))
            }

            # Flatten coherence matrix for bhava vector
            coherence_matrix = outputs['coherence_matrix'].squeeze(0)  # [12, 12]
            bhava_vector = coherence_matrix.flatten().cpu().numpy().tolist()

            # Full vector
            full_vector = probs.tolist() + bhava_vector

            # Strongest relationships from coherence matrix
            strongest_relationships = self._extract_relationships(coherence_matrix)

            # Task scores (simplified from layer activations)
            reasoning_layers = [5, 6, 7]  # Cognition, Agency, Reasoning
            creativity_layers = [3, 4, 8]  # Execution, Structure, Purpose
            reasoning_score = float(np.mean([probs[i] for i in reasoning_layers]))
            creativity_score = float(np.mean([probs[i] for i in creativity_layers]))

            return {
                "dominant_layer": dominant_layer,
                "confidence": confidence,
                "probabilities": probabilities,
                "uncertainty": uncertainty,
                "certainty_level": certainty_level,
                "coherence": coherence,
                "reasoning_score": reasoning_score,
                "creativity_score": creativity_score,
                "ontological_vector": probs.tolist(),
                "bhava_vector": bhava_vector,
                "full_vector": full_vector,
                "strongest_relationships": strongest_relationships,
                "witness_confidence": witness_conf,
                "engine_type": "symbolu12_llm",
            }

        def _extract_relationships(
            self,
            coherence_matrix: torch.Tensor,
            top_k: int = 5,
        ) -> list:
            """Extract strongest relationships from coherence matrix."""
            from symbolu_core.ontological.bhava_relationships import get_relationship_meaning

            matrix = coherence_matrix.cpu().numpy()
            relationships = []

            for i in range(12):
                for j in range(12):
                    if i != j:
                        strength = float(matrix[i, j])
                        meaning = get_relationship_meaning(i, j)
                        relationships.append({
                            "from_layer": LAYER_NAMES[i],
                            "to_layer": LAYER_NAMES[j],
                            "strength": strength,
                            "bhava_name": meaning.get("bhava_name", ""),
                            "bhava_interpretation": meaning.get("interpretation", ""),
                        })

            # Sort by strength
            relationships.sort(key=lambda x: x["strength"], reverse=True)
            return relationships[:top_k]

        def get_engine_type(self) -> OntologicalEngineType:
            return OntologicalEngineType.SYMBOLU12_LLM

        def get_output_dim(self) -> int:
            return 12 + 144  # 12D onto + 144D C' matrix

        def generate(
            self,
            input_ids: torch.Tensor,
            max_new_tokens: int = 50,
            temperature: float = 1.0,
        ) -> torch.Tensor:
            """
            Generate tokens autoregressively.

            Only available for SymbolU12 LLM engine.
            """
            self._llm.eval()
            device = next(self._llm.parameters()).device
            generated = input_ids.to(device)

            for _ in range(max_new_tokens):
                outputs = self._llm(generated)
                logits = outputs['logits'][:, -1, :] / temperature

                # Check completion
                completion = outputs['completion'][:, -1, 0]
                if completion.mean() > 0.9:
                    break

                probs = torch.softmax(logits, dim=-1)
                next_token = torch.multinomial(probs, num_samples=1)
                generated = torch.cat([generated, next_token], dim=1)

            return generated


    class SymbolU12BhavaEngineWrapper(OntologicalEngineInterface, nn.Module):
        """
        Wrapper for SymbolU12LLMWithBhava.

        Full LLM with Vedic Bhava inter-layer relationships.
        Output: 156D (12D ontological + 144D bhava)
        """

        def __init__(self, model_type: str = "full"):
            nn.Module.__init__(self)
            from symbolu_core.ontological.symbolu12_bhava import (
                create_symbolu12_llm_bhava,
                create_symbolu12_optimized_bhava,
                create_symbolu12_tiny_bhava,
            )

            if model_type == "full":
                self._model = create_symbolu12_llm_bhava()
                self._engine_type = OntologicalEngineType.SYMBOLU12_LLM_BHAVA
            elif model_type == "optimized":
                self._model = create_symbolu12_optimized_bhava()
                self._engine_type = OntologicalEngineType.SYMBOLU12_OPTIMIZED_BHAVA
            elif model_type == "tiny":
                self._model = create_symbolu12_tiny_bhava()
                self._engine_type = OntologicalEngineType.SYMBOLU12_TINY_BHAVA
            else:
                raise ValueError(f"Unknown model type: {model_type}")

        def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
            return self._model.forward(x)

        def analyze(self, text: str) -> Dict[str, Any]:
            """Analyze text with Bhava relationships."""
            if hasattr(self._model, 'analyze'):
                return self._model.analyze(text)

            # Fallback for optimized models
            import numpy as np
            self._model.eval()

            # Simple tokenization
            tokens = [ord(c) % 32000 for c in text[:512]]
            input_ids = torch.tensor([tokens], device=next(self._model.parameters()).device)

            with torch.no_grad():
                outputs = self._model(input_ids)

            probs = outputs['ontological_probs'].squeeze(0).cpu().numpy()
            bhava = outputs['bhava_vector'].squeeze(0).cpu().numpy()

            dominant_idx = int(np.argmax(probs))
            dominant_layer = LAYER_NAMES[dominant_idx]

            return {
                'dominant_layer': dominant_layer,
                'confidence': float(probs[dominant_idx]),
                'probabilities': {LAYER_NAMES[i]: float(probs[i]) for i in range(12)},
                'coherence': float(outputs['global_coherence'].mean().item()),
                'witness_confidence': float(outputs['witness_confidence'].mean().item()),
                'ontological_vector': probs.tolist(),
                'bhava_vector': bhava.tolist(),
                'full_vector': outputs['full_vector'].squeeze(0).cpu().numpy().tolist(),
                'engine_type': self._engine_type.value,
            }

        def get_engine_type(self) -> OntologicalEngineType:
            return self._engine_type

        def get_output_dim(self) -> int:
            return 156  # 12D onto + 144D bhava


    class SymbolU12HybridEngineWrapper(OntologicalEngineInterface, nn.Module):
        """
        Wrapper for SymbolU12Hybrid (MiniLM + SymbolU12 layers).

        Best of both: pre-trained encoder + interpretable layers.
        """

        def __init__(self):
            nn.Module.__init__(self)
            from symbolu_core.ontological.symbolu12_hybrid import SymbolU12Hybrid
            self._model = SymbolU12Hybrid()

        def forward(self, x: torch.Tensor) -> Dict[str, torch.Tensor]:
            return self._model.forward(x)

        def analyze(self, text: str) -> Dict[str, Any]:
            return self._model.analyze(text)

        def get_engine_type(self) -> OntologicalEngineType:
            return OntologicalEngineType.SYMBOLU12_HYBRID

        def get_output_dim(self) -> int:
            return 156


    class SimpleTokenizer:
        """Simple character-level tokenizer fallback."""

        def __init__(self, vocab_size: int = 256):
            self.vocab_size = vocab_size

        def __call__(self, text: str) -> torch.Tensor:
            # Simple ASCII encoding
            tokens = [ord(c) % self.vocab_size for c in text]
            return torch.tensor([tokens])

        def encode(self, text: str, **kwargs) -> torch.Tensor:
            return self(text)

        def decode(self, tokens: torch.Tensor) -> str:
            return "".join(chr(t.item()) for t in tokens.flatten())


def create_ontological_engine(
    engine_type: OntologicalEngineType = OntologicalEngineType.MINILM_V2,
    **kwargs,
) -> OntologicalEngineInterface:
    """
    Factory function to create ontological engines.

    Args:
        engine_type: Type of engine to create
        **kwargs: Engine-specific configuration

    Returns:
        Engine implementing OntologicalEngineInterface

    Examples:
        # Default MiniLM engine
        engine = create_ontological_engine()

        # SymbolU12 LLM
        engine = create_ontological_engine(
            OntologicalEngineType.SYMBOLU12_LLM,
            embed_dim=768,
        )

        # Small SymbolU12 for testing
        engine = create_ontological_engine(
            OntologicalEngineType.SYMBOLU12_SMALL
        )
    """
    if not PYTORCH_AVAILABLE:
        raise ImportError("PyTorch is required for ontological engines")

    if engine_type == OntologicalEngineType.MINILM_V2:
        return MiniLMEngineWrapper()

    elif engine_type == OntologicalEngineType.SYMBOLU12_LLM:
        return SymbolU12EngineWrapper(
            vocab_size=kwargs.get("vocab_size", 50257),
            embed_dim=kwargs.get("embed_dim", 768),
            max_seq_len=kwargs.get("max_seq_len", 2048),
            num_heads=kwargs.get("num_heads", 8),
        )

    elif engine_type == OntologicalEngineType.SYMBOLU12_SMALL:
        return SymbolU12EngineWrapper(
            vocab_size=50257,
            embed_dim=256,
            max_seq_len=512,
            num_heads=4,
        )

    elif engine_type == OntologicalEngineType.SYMBOLU12_BASE:
        return SymbolU12EngineWrapper(
            vocab_size=50257,
            embed_dim=768,
            max_seq_len=2048,
            num_heads=8,
        )

    elif engine_type == OntologicalEngineType.SYMBOLU12_LARGE:
        return SymbolU12EngineWrapper(
            vocab_size=50257,
            embed_dim=1024,
            max_seq_len=4096,
            num_heads=16,
        )

    # Bhava-enhanced engines
    elif engine_type == OntologicalEngineType.SYMBOLU12_LLM_BHAVA:
        return SymbolU12BhavaEngineWrapper(model_type="full")

    elif engine_type == OntologicalEngineType.SYMBOLU12_OPTIMIZED_BHAVA:
        return SymbolU12BhavaEngineWrapper(model_type="optimized")

    elif engine_type == OntologicalEngineType.SYMBOLU12_TINY_BHAVA:
        return SymbolU12BhavaEngineWrapper(model_type="tiny")

    elif engine_type == OntologicalEngineType.SYMBOLU12_HYBRID:
        return SymbolU12HybridEngineWrapper()

    else:
        raise ValueError(f"Unknown engine type: {engine_type}")


def compare_engines(text: str) -> Dict[str, Dict[str, Any]]:
    """
    Compare outputs from all available engines on the same text.

    Args:
        text: Input text to analyze

    Returns:
        Dict mapping engine type to analysis results
    """
    results = {}

    for engine_type in OntologicalEngineType:
        try:
            engine = create_ontological_engine(engine_type)
            results[engine_type.value] = engine.analyze(text)
        except Exception as e:
            results[engine_type.value] = {"error": str(e)}

    return results


# =============================================================================
# DEMO
# =============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("   ONTOLOGICAL ENGINE FACTORY - DEMO")
    print("=" * 70)

    print("\nAvailable engine types:")
    for engine_type in OntologicalEngineType:
        print(f"  - {engine_type.value}: {engine_type.name}")

    print("\n" + "-" * 70)
    print("Creating engines...")

    # Test MiniLM engine
    try:
        print("\n1. MiniLM V2 Engine:")
        engine1 = create_ontological_engine(OntologicalEngineType.MINILM_V2)
        print(f"   Type: {engine1.get_engine_type().value}")
        print(f"   Output dim: {engine1.get_output_dim()}D")
    except Exception as e:
        print(f"   Error: {e}")

    # Test SymbolU12 engine
    try:
        print("\n2. SymbolU12 Small Engine:")
        engine2 = create_ontological_engine(OntologicalEngineType.SYMBOLU12_SMALL)
        print(f"   Type: {engine2.get_engine_type().value}")
        print(f"   Output dim: {engine2.get_output_dim()}D")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n" + "=" * 70)
    print("   ENGINE COMPARISON")
    print("=" * 70)
    print("""
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MiniLM V2 vs SymbolU12 LLM                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  MiniLM V2 (UnifiedOntologicalEngineV2)                                    │
│  ─────────────────────────────────────                                      │
│  • Uses pre-trained MiniLM encoder (384D)                                  │
│  • Adds evidential classification + Bhava relationships                    │
│  • Output: 156D (12D onto + 144D Bhava)                                    │
│  • Best for: Classification, RAG, fine-tuning                              │
│  • Training: Fine-tune heads only                                          │
│  • Faster, smaller model                                                    │
│                                                                             │
│  SymbolU12 LLM (SymbolU12_LLM)                                             │
│  ─────────────────────────────                                              │
│  • Full 12-layer ontological transformer                                   │
│  • Each layer has explicit cognitive function                              │
│  • Output: Token-level logits + coherence matrix                           │
│  • Best for: Generation, interpretability, research                        │
│  • Training: Full model from scratch                                       │
│  • Larger, more interpretable                                               │
│                                                                             │
│  Common Interface:                                                          │
│  ─────────────────                                                          │
│  Both provide: analyze(text) → {dominant_layer, confidence, coherence, ...}│
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
""")
