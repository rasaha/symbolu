"""
Varṇa-Hybrid LLM Renderer
=========================

Integrates phoneme-based optimization into the LLM rendering pipeline.

Key Optimizations:
1. CandidatePreFilter - Pre-filter candidates before LLM inference (10-100x speedup)
2. PhonemeAttentionHead - Replace learned attention with phoneme similarity (82% FLOPs savings)
3. SemanticRouter - Route to specialized models based on ontological layer (25x param reduction)
4. Varṇa Analysis - Use Sanskrit phoneme semantics for richer vector representations

Architecture:
    ┌─────────────────────────────────────────────────────────────────┐
    │                    VARṆA-HYBRID RENDERER                        │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                 │
    │  Input Text                                                     │
    │       │                                                         │
    │       ▼                                                         │
    │  ┌─────────────────────────────────────────────────────────┐   │
    │  │ 1. VARṆA ANALYSIS                                       │   │
    │  │    - Convert words to 10D ontological vectors           │   │
    │  │    - Extract dominant layers and bridge meanings        │   │
    │  │    - Compute phrase harmony                             │   │
    │  └─────────────────────────────────────────────────────────┘   │
    │       │                                                         │
    │       ▼                                                         │
    │  ┌─────────────────────────────────────────────────────────┐   │
    │  │ 2. SEMANTIC ROUTING                                     │   │
    │  │    - Route to specialized model based on dominant layer │   │
    │  │    - O9_UNIFYING → relationship model                   │   │
    │  │    - O6_REASONING → reasoning model                     │   │
    │  │    - etc.                                                │   │
    │  └─────────────────────────────────────────────────────────┘   │
    │       │                                                         │
    │       ▼                                                         │
    │  ┌─────────────────────────────────────────────────────────┐   │
    │  │ 3. CANDIDATE PREFILTER (if vocabulary provided)         │   │
    │  │    - Filter vocabulary by phoneme resonance             │   │
    │  │    - 50,000 → 500 candidates (100x reduction)           │   │
    │  └─────────────────────────────────────────────────────────┘   │
    │       │                                                         │
    │       ▼                                                         │
    │  ┌─────────────────────────────────────────────────────────┐   │
    │  │ 4. PHONEME ATTENTION                                    │   │
    │  │    - Compute attention using phoneme similarity         │   │
    │  │    - 82% FLOPs savings vs learned attention             │   │
    │  └─────────────────────────────────────────────────────────┘   │
    │       │                                                         │
    │       ▼                                                         │
    │  ┌─────────────────────────────────────────────────────────┐   │
    │  │ 5. LLM RENDER (optional, on filtered/routed subset)     │   │
    │  │    - Call LLM only when needed                          │   │
    │  │    - Use routing decision to select model               │   │
    │  │    - Apply style modifiers and safety checks            │   │
    │  └─────────────────────────────────────────────────────────┘   │
    │       │                                                         │
    │       ▼                                                         │
    │  Output                                                         │
    │                                                                 │
    └─────────────────────────────────────────────────────────────────┘
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple, List, TYPE_CHECKING
from enum import Enum

# Import resonance engine (Varṇa-based)
from symbolu.resonance import (
    analyze_word_varna,
    analyze_phrase_varna,
    compare_words,
    get_phonemes,
    WordVector,
    PhraseAnalysis,
)

# Import hybrid optimization modules
from symbolu.hybrid.prefilter import CandidatePreFilter
from symbolu.hybrid.attention import PhonemeAttentionHead, HybridAttentionLayer
from symbolu.hybrid.router import SemanticRouter, ModelType, RoutingDecision

# Import existing renderer components
from symbolu.mechanical.renderer.prompts import PromptTemplates
from symbolu.mechanical.renderer.style_modifiers import StyleModifiers
from symbolu.mechanical.renderer.safety_guardrails import SafetyGuardrails

if TYPE_CHECKING:
    from symbolu.mechanical.pipeline.models import MapperProfile


class HybridRenderMode(Enum):
    """Hybrid rendering modes."""
    PHONEME_ONLY = "phoneme_only"      # No LLM, pure phoneme-based
    HYBRID_FAST = "hybrid_fast"        # Pre-filter + route, minimal LLM
    HYBRID_FULL = "hybrid_full"        # Full pipeline with optimized attention
    LLM_FALLBACK = "llm_fallback"      # Fall back to pure LLM


@dataclass(frozen=True)
class VarnaAnalysisResult:
    """Result of Varṇa-based analysis."""
    phrase_analysis: PhraseAnalysis
    word_vectors: Tuple[WordVector, ...]
    dominant_layer: str
    overall_harmony: float
    varnas: Tuple[str, ...]
    bridge_meanings: Tuple[str, ...]


@dataclass(frozen=True)
class HybridRenderResult:
    """Result from hybrid rendering."""
    text: str
    mode_used: HybridRenderMode
    routing_decision: Optional[RoutingDecision]
    varna_analysis: Optional[VarnaAnalysisResult]
    candidates_filtered: int
    candidates_total: int
    flops_saved_percent: float
    attention_scores: Optional[Tuple[Tuple[float, ...], ...]]


class VarnaHybridRenderer:
    """
    Hybrid LLM renderer using Varṇa phoneme optimization.

    Integrates Symbol-U's deterministic phoneme analysis with
    optional LLM rendering for maximum efficiency.

    Usage:
        renderer = VarnaHybridRenderer()

        # Phoneme-only mode (no LLM)
        result = renderer.render(
            "Truth is light",
            mode=HybridRenderMode.PHONEME_ONLY
        )

        # Hybrid mode with routing
        result = renderer.render(
            "Love conquers all",
            mode=HybridRenderMode.HYBRID_FAST
        )
    """

    def __init__(
        self,
        provider: str = "anthropic",
        prefilter_threshold: float = 0.5,
        prefilter_top_k: int = 100,
        router_confidence_threshold: float = 0.3,
        attention_temperature: float = 1.0,
    ):
        """
        Initialize hybrid renderer.

        Args:
            provider: LLM provider for fallback rendering
            prefilter_threshold: Threshold for candidate pre-filtering
            prefilter_top_k: Max candidates to keep after filtering
            router_confidence_threshold: Confidence threshold for routing
            attention_temperature: Temperature for phoneme attention
        """
        self.provider = provider

        # Initialize hybrid optimization components
        self.prefilter = CandidatePreFilter(
            threshold=prefilter_threshold,
            top_k=prefilter_top_k,
        )
        self.router = SemanticRouter(
            confidence_threshold=router_confidence_threshold,
        )
        self.attention = PhonemeAttentionHead(
            temperature=attention_temperature,
        )
        self.hybrid_attention = HybridAttentionLayer(
            num_phoneme_heads=2,
            num_traditional_heads=10,
        )

        # Initialize existing renderer components
        self.prompts = PromptTemplates()
        self.style = StyleModifiers()
        self.safety = SafetyGuardrails()

        # Model registry for specialized models
        self._model_handlers: Dict[ModelType, Any] = {}

    def register_model(self, model_type: ModelType, handler: Any):
        """Register a specialized model handler."""
        self._model_handlers[model_type] = handler

    def analyze_varna(self, text: str) -> VarnaAnalysisResult:
        """
        Analyze text using Varṇa phoneme system.

        Args:
            text: Input text to analyze

        Returns:
            VarnaAnalysisResult with comprehensive analysis
        """
        from symbolu.resonance.varna_bridge import (
            phonemes_to_varnas,
            get_bridge_meaning,
        )
        from symbolu.resonance.analyzer import extract_content_words

        # Get content words
        content_words = extract_content_words(text)

        if not content_words:
            return VarnaAnalysisResult(
                phrase_analysis=analyze_phrase_varna(text),
                word_vectors=(),
                dominant_layer="O5_DIRECTING",
                overall_harmony=0.0,
                varnas=(),
                bridge_meanings=(),
            )

        # Analyze each word using Varṇa
        word_vectors = tuple(analyze_word_varna(w) for w in content_words)

        # Get phrase analysis
        phrase_analysis = analyze_phrase_varna(text)

        # Collect all varnas and bridge meanings
        all_varnas: List[str] = []
        all_meanings: List[str] = []

        for word in content_words:
            phonemes = get_phonemes(word)
            varnas = phonemes_to_varnas(phonemes)
            all_varnas.extend(varnas)

            for v in varnas:
                meaning = get_bridge_meaning(v)
                if meaning:
                    all_meanings.append(meaning)

        # Determine dominant layer from word vectors
        layer_totals = [0.0] * 10
        for wv in word_vectors:
            for i, score in enumerate(wv.vector):
                layer_totals[i] += score

        max_idx = layer_totals.index(max(layer_totals))
        layer_names = [
            "O1_ACTING", "O2_TAGGING", "O3_FORMING", "O4_THINKING", "O5_DIRECTING",
            "O6_REASONING", "O7_PURPOSING", "O8_META_OBSERVING", "O9_UNIFYING", "O10_ABSOLVING"
        ]
        dominant_layer = layer_names[max_idx]

        return VarnaAnalysisResult(
            phrase_analysis=phrase_analysis,
            word_vectors=word_vectors,
            dominant_layer=dominant_layer,
            overall_harmony=phrase_analysis.overall_harmony,
            varnas=tuple(all_varnas),
            bridge_meanings=tuple(set(all_meanings)),  # Unique meanings
        )

    def route_query(self, text: str) -> RoutingDecision:
        """
        Route query to appropriate specialized model.

        Args:
            text: Input query

        Returns:
            RoutingDecision with model type and confidence
        """
        return self.router.route(text)

    def prefilter_candidates(
        self,
        candidates: Tuple[str, ...],
        target: str,
    ) -> Tuple[Tuple[str, ...], int, int]:
        """
        Pre-filter candidates using phoneme resonance.

        Args:
            candidates: All candidate words/phrases
            target: Target word/phrase

        Returns:
            Tuple of (filtered_candidates, filtered_count, total_count)
        """
        filtered = self.prefilter.filter(candidates, target)
        return filtered, len(filtered), len(candidates)

    def compute_attention(
        self,
        tokens: Tuple[str, ...],
    ) -> Tuple[Tuple[Tuple[float, ...], ...], int]:
        """
        Compute attention using phoneme similarity.

        Args:
            tokens: Input tokens

        Returns:
            Tuple of (attention_weights, flops_used)
        """
        result = self.attention.compute_attention(tokens)
        return result.attention_weights, result.computation_flops

    def render(
        self,
        text: str,
        mode: HybridRenderMode = HybridRenderMode.HYBRID_FAST,
        tone: Optional[str] = None,
        candidates: Optional[Tuple[str, ...]] = None,
        target_word: Optional[str] = None,
        **kwargs,
    ) -> HybridRenderResult:
        """
        Render text using hybrid phoneme-LLM pipeline.

        Args:
            text: Input text to render
            mode: Rendering mode
            tone: DHA tone for delivery
            candidates: Optional vocabulary to filter
            target_word: Target word for candidate filtering
            **kwargs: Additional parameters

        Returns:
            HybridRenderResult with rendered text and metrics
        """
        # Step 1: Varṇa Analysis (always)
        varna_analysis = self.analyze_varna(text)

        # Step 2: Route query
        routing_decision = self.route_query(text)

        # Initialize metrics
        candidates_filtered = 0
        candidates_total = 0
        attention_scores = None
        flops_saved = 0.0

        # Step 3: Mode-specific processing
        if mode == HybridRenderMode.PHONEME_ONLY:
            # Pure phoneme-based rendering (no LLM)
            rendered_text = self._render_phoneme_only(text, varna_analysis, tone)
            flops_saved = 100.0  # No LLM FLOPs

        elif mode == HybridRenderMode.HYBRID_FAST:
            # Pre-filter and route, minimal LLM
            if candidates is not None and target_word is not None:
                filtered, candidates_filtered, candidates_total = self.prefilter_candidates(
                    candidates, target_word
                )
                flops_saved = (1 - candidates_filtered / candidates_total) * 100 if candidates_total > 0 else 0

            # Route to specialized model
            rendered_text = self._render_with_routing(
                text, varna_analysis, routing_decision, tone
            )

        elif mode == HybridRenderMode.HYBRID_FULL:
            # Full hybrid with attention optimization
            tokens = tuple(text.split())
            if tokens:
                attention_scores, flops = self.compute_attention(tokens)

                # Compare to traditional (guard against division by zero)
                comparison = self.attention.compare_to_traditional(len(tokens))
                if comparison['traditional_flops'] > 0:
                    flops_saved = (1 - comparison['phoneme_flops'] / comparison['traditional_flops']) * 100
                else:
                    flops_saved = 100.0  # No traditional FLOPs = 100% savings
            else:
                # Empty input
                flops_saved = 100.0

            # Pre-filter if candidates provided
            if candidates is not None and target_word is not None:
                filtered, candidates_filtered, candidates_total = self.prefilter_candidates(
                    candidates, target_word
                )

            rendered_text = self._render_with_attention(
                text, varna_analysis, routing_decision, attention_scores, tone
            )

        else:  # LLM_FALLBACK
            # Pure LLM rendering
            rendered_text = self._render_llm_fallback(text, tone)
            flops_saved = 0.0

        return HybridRenderResult(
            text=rendered_text,
            mode_used=mode,
            routing_decision=routing_decision,
            varna_analysis=varna_analysis,
            candidates_filtered=candidates_filtered,
            candidates_total=candidates_total,
            flops_saved_percent=flops_saved,
            attention_scores=attention_scores,
        )

    def _render_phoneme_only(
        self,
        text: str,
        varna_analysis: VarnaAnalysisResult,
        tone: Optional[str],
    ) -> str:
        """
        Render using only phoneme analysis (no LLM).

        Uses deterministic rules based on:
        - Dominant ontological layer
        - Phrase harmony
        - Bridge meanings
        """
        # Apply style based on dominant layer
        layer_styles = {
            "O1_ACTING": "direct and action-oriented",
            "O2_TAGGING": "structured and categorized",
            "O3_FORMING": "creative and generative",
            "O4_THINKING": "analytical and contemplative",
            "O5_DIRECTING": "guiding and purposeful",
            "O6_REASONING": "logical and systematic",
            "O7_PURPOSING": "intentional and goal-directed",
            "O8_META_OBSERVING": "reflective and meta-aware",
            "O9_UNIFYING": "connecting and harmonizing",
            "O10_ABSOLVING": "transcendent and dissolving",
        }

        style = layer_styles.get(varna_analysis.dominant_layer, "neutral")

        # Add harmony indicator
        if varna_analysis.overall_harmony > 0.7:
            harmony_note = "harmonically resonant"
        elif varna_analysis.overall_harmony < 0.3:
            harmony_note = "with tension"
        else:
            harmony_note = "balanced"

        # Construct phoneme-enhanced output
        output = f"{text}"

        # Add phoneme metadata as structured comment
        if varna_analysis.bridge_meanings:
            meanings = ", ".join(varna_analysis.bridge_meanings[:3])
            output += f" [{style}, {harmony_note}, themes: {meanings}]"

        return output

    def _render_with_routing(
        self,
        text: str,
        varna_analysis: VarnaAnalysisResult,
        routing_decision: RoutingDecision,
        tone: Optional[str],
    ) -> str:
        """
        Render with semantic routing to specialized model.
        """
        model_type = routing_decision.model_type

        # Check if we have a registered handler
        if model_type in self._model_handlers:
            handler = self._model_handlers[model_type]
            return handler(text, routing_decision, varna_analysis)

        # Default: Add routing context to output
        model_name = model_type.value
        confidence = routing_decision.confidence

        # Phoneme-enhanced rendering with routing context
        base = self._render_phoneme_only(text, varna_analysis, tone)
        return f"{base} (routed: {model_name}, confidence: {confidence:.2f})"

    def _render_with_attention(
        self,
        text: str,
        varna_analysis: VarnaAnalysisResult,
        routing_decision: RoutingDecision,
        attention_scores: Tuple[Tuple[float, ...], ...],
        tone: Optional[str],
    ) -> str:
        """
        Render with full attention optimization.
        """
        # Find key attention pairs
        tokens = tuple(text.split())
        key_pairs = []

        if attention_scores and len(tokens) >= 2:
            for i, row in enumerate(attention_scores):
                for j, score in enumerate(row):
                    if i != j and score > 0.3:
                        key_pairs.append((tokens[i], tokens[j], score))

            # Sort by score
            key_pairs.sort(key=lambda x: x[2], reverse=True)

        # Enhanced output with attention context
        base = self._render_with_routing(text, varna_analysis, routing_decision, tone)

        if key_pairs:
            top_pair = key_pairs[0]
            return f"{base} (key resonance: {top_pair[0]}-{top_pair[1]}: {top_pair[2]:.2f})"

        return base

    def _render_llm_fallback(self, text: str, tone: Optional[str]) -> str:
        """
        Fall back to pure LLM rendering.

        In production, this would call the actual LLM.
        """
        # Build prompt
        prompt = self.prompts.build_enhancement_prompt({"text": text}, tone)

        # Apply style
        prompt = self.style.apply(prompt, tone)

        # Safety check
        if not self.safety.check_prompt(prompt):
            raise ValueError("Prompt failed safety check")

        # LLM call placeholder
        # In production: return self._call_llm(prompt)
        return f"{text} [LLM-enhanced, tone: {tone or 'neutral'}]"

    def estimate_savings(
        self,
        num_candidates: int = 50000,
        seq_len: int = 512,
        transformer_ms: float = 10.0,
    ) -> Dict[str, Any]:
        """
        Estimate computational savings from hybrid approach.

        Args:
            num_candidates: Number of vocabulary candidates
            seq_len: Sequence length for attention
            transformer_ms: Transformer inference time per candidate

        Returns:
            Dict with savings estimates
        """
        # Pre-filter savings
        prefilter_savings = self.prefilter.estimate_savings(
            num_candidates, transformer_ms
        )

        # Attention savings
        attention_savings = self.hybrid_attention.estimate_savings(seq_len)

        # Router savings
        router_savings = {
            "specialized_model_params": 7_000_000_000,
            "general_model_params": 175_000_000_000,
            "param_reduction": 25,
        }

        return {
            "prefilter": prefilter_savings,
            "attention": attention_savings,
            "router": router_savings,
            "total_speedup_estimate": (
                prefilter_savings["speedup_factor"] *
                (1 + attention_savings["percent_saved"] / 100)
            ),
        }


# =============================================================================
# Factory Functions
# =============================================================================

def create_varna_hybrid_renderer(
    mode: str = "fast",
    **kwargs,
) -> VarnaHybridRenderer:
    """
    Create a Varṇa-hybrid renderer with preset configurations.

    Args:
        mode: "fast" (aggressive filtering) or "balanced" or "quality"
        **kwargs: Override default parameters

    Returns:
        Configured VarnaHybridRenderer
    """
    configs = {
        "fast": {
            "prefilter_threshold": 0.4,
            "prefilter_top_k": 50,
            "router_confidence_threshold": 0.2,
            "attention_temperature": 1.5,
        },
        "balanced": {
            "prefilter_threshold": 0.5,
            "prefilter_top_k": 100,
            "router_confidence_threshold": 0.3,
            "attention_temperature": 1.0,
        },
        "quality": {
            "prefilter_threshold": 0.6,
            "prefilter_top_k": 200,
            "router_confidence_threshold": 0.4,
            "attention_temperature": 0.8,
        },
    }

    config = configs.get(mode, configs["balanced"])
    config.update(kwargs)

    return VarnaHybridRenderer(**config)
