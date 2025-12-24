"""
Semantic Router
===============

Routes queries to specialized sub-models based on phoneme signature.

Key Insight (12D layers):
    Different ontological layers suggest different processing needs:
    - O10_UNIFYING dominant → relationship/connection queries
    - O7_REASONING dominant → logical/analytical queries
    - O3_EXECUTION dominant → action/procedural queries

Instead of one giant model, route to smaller specialized models.

Computational Savings:
    - General model: 175B parameters
    - Specialized models: 7B parameters each
    - 25x parameter reduction for most queries
"""

from dataclasses import dataclass
from typing import Tuple, Optional, Dict, Callable, Any, Set, List
from enum import Enum
import re
import math

from symbolu.resonance import (
    analyze_phrase,
    analyze_word,
    PhraseAnalysis,
    WordVector,
    LAYER_NAMES,
)

# Vṛtti-Aspect Coupling Matrix (5×12) for cross-domain disambiguation
# This enables the p_v[v] formula: weights[a] = Σ_v p_v[v] · R[v,a]
# When chitta_vritti module is available, use it; otherwise inline the matrix
try:
    from symbolu.chitta_vritti.coupling import get_aspect_weights, VRITTI_NAMES
    VRITTI_COUPLING_AVAILABLE = True
except ImportError:
    VRITTI_COUPLING_AVAILABLE = False
    VRITTI_NAMES = ["pramana", "viparyaya", "vikalpa", "smrti", "nidra"]
    # Inline R[v,a] matrix (5×12) for when numpy unavailable
    R_MATRIX_INLINE = [
        # POT    ID     EXEC   STR    COG    AGN    RSN    PUR    WIT    UNI    INT    ABS
        [0.40, 0.80, 0.70, 0.60, 0.70, 0.50, 0.95, 0.60, 0.80, 0.70, 0.75, 0.60],  # Pramāṇa
        [0.30, 0.70, 0.50, 0.40, 0.60, 0.90, 0.40, 0.30, 0.50, 0.30, 0.35, 0.20],  # Viparyaya
        [0.50, 0.50, 0.60, 0.50, 0.85, 0.60, 0.70, 0.50, 0.60, 0.40, 0.55, 0.30],  # Vikalpa
        [0.70, 0.60, 0.80, 0.70, 0.70, 0.50, 0.60, 0.80, 0.50, 0.60, 0.70, 0.40],  # Smṛti
        [0.85, 0.30, 0.30, 0.70, 0.40, 0.30, 0.20, 0.40, 0.60, 0.50, 0.55, 0.75],  # Nidrā
    ]

    def get_aspect_weights(vritti_distribution: Dict[str, float]) -> Dict[str, float]:
        """Compute 12D layer weights from vṛtti distribution (inline version)."""
        vritti_vec = [
            vritti_distribution.get("pramana", 0.0),
            vritti_distribution.get("viparyaya", 0.0),
            vritti_distribution.get("vikalpa", 0.0),
            vritti_distribution.get("smrti", 0.0),
            vritti_distribution.get("nidra", 0.0),
        ]
        # Matrix multiply: (1×5) @ (5×12) = (1×12)
        weights = [0.0] * 12
        for v_idx, v_prob in enumerate(vritti_vec):
            for a_idx in range(12):
                weights[a_idx] += v_prob * R_MATRIX_INLINE[v_idx][a_idx]
        return {LAYER_NAMES[i]: weights[i] for i in range(12)}


# Intent keyword patterns for boosting
# These augment phoneme analysis with common linguistic patterns

ACTION_PATTERNS: Set[str] = {
    "run", "execute", "start", "stop", "deploy", "install", "send", "book",
    "schedule", "create", "delete", "build", "test", "compile", "launch",
    "restart", "shutdown", "upload", "download", "push", "pull", "commit",
    "cancel", "reset", "update", "configure", "setup", "migrate", "backup",
    "restore", "subscribe", "unsubscribe", "register", "login", "logout",
}

REASONING_PATTERNS: Set[str] = {
    "how", "why", "what", "explain", "analyze", "calculate", "compute",
    "derive", "prove", "solve", "understand", "theory", "logic", "reason",
    "cause", "effect", "because", "therefore", "hypothesis", "theorem",
    "work", "works", "difference", "compare", "evaluate", "assess",
    "determine", "figure", "clarify", "describe", "define", "means",
}

RELATIONSHIP_PATTERNS: Set[str] = {
    # Core emotional states
    "feel", "feeling", "feelings", "emotion", "emotional", "emotions",
    "sad", "sadness", "happy", "happiness", "anxious", "anxiety", "worried", "worry",
    "lonely", "loneliness", "scared", "fear", "afraid", "nervous",
    # Relationships
    "love", "loving", "hate", "hating", "friend", "friends", "friendship",
    "family", "relationship", "relationships", "partner", "spouse", "husband", "wife",
    "boyfriend", "girlfriend", "parent", "parents", "child", "children", "sibling",
    "colleague", "coworker", "boss", "team", "people",
    # Emotional actions
    "hurt", "hurting", "heart", "heartbreak", "care", "caring",
    "connect", "connection", "bond", "bonding", "trust", "trusting",
    "empathy", "compassion", "understand", "understanding",
    # Negative emotions
    "frustrated", "frustration", "angry", "anger", "upset", "stressed", "stress",
    "overwhelmed", "depressed", "depression", "miss", "missing", "grief", "grieving",
    # Support-seeking
    "cope", "coping", "support", "talk", "talking", "listen", "listening",
    "comfort", "help", "advice", "guidance", "someone", "anyone",
    # Relational phrases (first word patterns)
    "i'm", "im", "i", "my", "we", "our", "need", "struggling",
}

CREATIVE_PATTERNS: Set[str] = {
    "write", "compose", "design", "create", "imagine", "paint", "draw",
    "poem", "story", "song", "art", "music", "illustration", "sketch",
    "novel", "lyrics", "melody", "artistic", "creative", "invent",
    "haiku", "logo", "concept", "character", "backstory", "fiction",
    "describe", "picture", "scene", "narrative", "plot", "draft",
}

REFLECTIVE_PATTERNS: Set[str] = {
    "meaning", "life", "exist", "existence", "consciousness", "free",
    "will", "death", "truth", "reality", "nature", "being", "soul",
    "spirit", "philosophy", "metaphysics", "purpose", "destiny", "fate",
    "why", "nothing", "everything", "universe", "god", "afterlife",
}


class ModelType(Enum):
    """Types of specialized models."""
    GENERAL = "general"           # Fallback for mixed/unclear
    RELATIONSHIP = "relationship"  # O10_UNIFYING - connections, love, unity
    REASONING = "reasoning"        # O7_REASONING - logic, analysis
    ACTION = "action"             # O3_EXECUTION - procedures, commands
    CREATIVE = "creative"         # O4_STRUCTURE - creation, art, structure
    REFLECTIVE = "reflective"     # O5_COGNITION - contemplation, philosophy
    DIRECTIVE = "directive"       # O6_AGENCY - guidance, commands
    TRANSCENDENT = "transcendent" # O12_ABSOLVING - abstract, spiritual


@dataclass(frozen=True)
class RoutingDecision:
    """Result of routing decision."""
    model_type: ModelType
    confidence: float  # 0.0 to 1.0
    dominant_layer: str
    layer_scores: Tuple[Tuple[str, float], ...]  # Top layers
    query_analysis: PhraseAnalysis


# Layer → Model mapping (12D patent-exact sequence)
LAYER_TO_MODEL: Dict[str, ModelType] = {
    "O1_POTENTIAL": ModelType.GENERAL,      # Dormant → general
    "O2_IDENTITY": ModelType.GENERAL,       # Classification → general
    "O3_EXECUTION": ModelType.ACTION,       # Action/karma → action
    "O4_STRUCTURE": ModelType.CREATIVE,     # Form/shape → creative
    "O5_COGNITION": ModelType.REFLECTIVE,   # Perception → reflective
    "O6_AGENCY": ModelType.DIRECTIVE,       # Direction/control → directive
    "O7_REASONING": ModelType.REASONING,    # Logic → reasoning
    "O8_PURPOSE": ModelType.DIRECTIVE,      # Intent/goals → directive
    "O9_WITNESSES": ModelType.REFLECTIVE,   # Meta-observation → reflective
    "O10_UNIFYING": ModelType.RELATIONSHIP, # Connection → relationship
    "O11_INTEGRATION": ModelType.RELATIONSHIP,  # Consolidation → relationship
    "O12_ABSOLVING": ModelType.TRANSCENDENT,    # Dissolution → transcendent
}


class SemanticRouter:
    """
    Routes queries to specialized models based on phoneme signature.

    Usage:
        router = SemanticRouter()
        decision = router.route("Love conquers all")
        # decision.model_type = ModelType.RELATIONSHIP
        # decision.confidence = 0.85

        # Now dispatch to appropriate model
        if decision.model_type == ModelType.RELATIONSHIP:
            result = relationship_model(query)
        elif decision.model_type == ModelType.REASONING:
            result = reasoning_model(query)
        ...

        # With custom vocabulary for domain terms:
        from symbolu.hybrid.vocabulary import VocabularyLoader
        vocab = VocabularyLoader.from_file("company_terms.json")
        router = SemanticRouter(vocabulary=vocab)
    """

    # Pattern sets mapped to model types
    PATTERN_TO_MODEL: Dict[ModelType, Set[str]] = {
        ModelType.ACTION: ACTION_PATTERNS,
        ModelType.REASONING: REASONING_PATTERNS,
        ModelType.RELATIONSHIP: RELATIONSHIP_PATTERNS,
        ModelType.CREATIVE: CREATIVE_PATTERNS,
        ModelType.REFLECTIVE: REFLECTIVE_PATTERNS,
    }

    # Intent string → ModelType mapping
    INTENT_TO_MODEL: Dict[str, ModelType] = {
        "action": ModelType.ACTION,
        "reasoning": ModelType.REASONING,
        "relationship": ModelType.RELATIONSHIP,
        "creative": ModelType.CREATIVE,
        "reflective": ModelType.REFLECTIVE,
        "directive": ModelType.DIRECTIVE,
        "transcendent": ModelType.TRANSCENDENT,
        "general": ModelType.GENERAL,
    }

    def __init__(
        self,
        confidence_threshold: float = 0.3,
        fallback_model: ModelType = ModelType.GENERAL,
        pattern_boost: float = 0.3,
        vocabulary: Optional[Any] = None,
    ):
        """
        Initialize router.

        Args:
            confidence_threshold: Minimum dominant layer score to route
            fallback_model: Model to use when confidence is low
            pattern_boost: Amount to boost confidence when keyword patterns match
            vocabulary: Optional CustomVocabulary for domain-specific terms
        """
        self.confidence_threshold = confidence_threshold
        self.fallback_model = fallback_model
        self.pattern_boost = pattern_boost
        self.vocabulary = vocabulary

    def _check_vocabulary(self, query: str) -> Optional[Tuple[ModelType, float]]:
        """
        Check if any words in the query have vocabulary overrides.

        Args:
            query: The input query

        Returns:
            Tuple of (ModelType, confidence) if vocabulary match found, None otherwise
        """
        if not self.vocabulary:
            return None

        # Tokenize query
        words = re.findall(r'\b[a-zA-Z0-9/&]+\b', query)

        vocab_matches = []

        for word in words:
            intent = self.vocabulary.get_intent_override(word)
            if intent:
                model_type = self.INTENT_TO_MODEL.get(intent.lower())
                if model_type:
                    # Get layer vector for confidence boost
                    layer_vec = self.vocabulary.get_layer_vector(word)
                    if layer_vec:
                        # Use max layer affinity as confidence
                        confidence = max(layer_vec)
                    else:
                        confidence = 0.7  # Default confidence for vocab match

                    vocab_matches.append((model_type, confidence, word))

        if vocab_matches:
            # Return highest confidence match
            best = max(vocab_matches, key=lambda x: x[1])
            return (best[0], best[1])

        return None

    def _detect_intent_patterns(self, query: str) -> Dict[ModelType, float]:
        """
        Detect intent patterns in the query using keyword matching.

        Args:
            query: The input query

        Returns:
            Dict mapping ModelType to match score (0.0 to 1.0)
        """
        # Tokenize query into lowercase words
        words = set(re.findall(r'\b[a-z]+\b', query.lower()))

        scores: Dict[ModelType, float] = {}

        for model_type, patterns in self.PATTERN_TO_MODEL.items():
            matches = words & patterns
            if matches:
                # Score based on number of matches and their position
                # First word matching gets extra weight (imperative detection)
                first_word = query.lower().split()[0] if query.strip() else ""
                first_word_match = first_word in patterns

                base_score = len(matches) / max(len(words), 1)
                if first_word_match:
                    base_score += 0.3  # Boost for imperative commands

                scores[model_type] = min(base_score, 1.0)

        return scores

    def _cosine_similarity(self, vec_a: Tuple[float, ...], vec_b: Tuple[float, ...]) -> float:
        """
        Compute cosine similarity between two vectors.

        Args:
            vec_a: First vector
            vec_b: Second vector

        Returns:
            Cosine similarity (0.0 to 1.0)
        """
        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)

    def _detect_vritti_distribution(
        self,
        query: str,
        word_vectors: List[WordVector],
        pattern_scores: Dict["ModelType", float],
    ) -> Dict[str, float]:
        """
        Detect cognitive mode (vṛtti) distribution from context signals.

        Uses keyword patterns and phoneme characteristics to estimate
        which cognitive mode the query represents:
        - Pramāṇa (valid cognition): factual, logical queries
        - Viparyaya (misperception): conflicting or uncertain queries
        - Vikalpa (conceptualization): creative, imaginative queries
        - Smṛti (memory): historical, reference-based queries
        - Nidrā (dormancy): abstract, philosophical queries

        Args:
            query: The input query
            word_vectors: Analyzed word vectors
            pattern_scores: Detected intent pattern scores

        Returns:
            Dict mapping vṛtti names to probabilities (sums to 1.0)
        """
        # Initialize with uniform prior
        vritti = {
            "pramana": 0.2,
            "viparyaya": 0.2,
            "vikalpa": 0.2,
            "smrti": 0.2,
            "nidra": 0.2,
        }

        # Adjust based on pattern detection (increased weights for stronger influence)
        if pattern_scores:
            # Reasoning patterns → boost Pramāṇa (valid cognition)
            if ModelType.REASONING in pattern_scores:
                vritti["pramana"] += pattern_scores[ModelType.REASONING] * 0.6
                vritti["vikalpa"] -= pattern_scores[ModelType.REASONING] * 0.2

            # Creative patterns → boost Vikalpa (conceptualization)
            if ModelType.CREATIVE in pattern_scores:
                vritti["vikalpa"] += pattern_scores[ModelType.CREATIVE] * 0.6

            # Action patterns → boost Smṛti (memory/procedure recall) and Pramāṇa
            if ModelType.ACTION in pattern_scores:
                vritti["smrti"] += pattern_scores[ModelType.ACTION] * 0.4
                vritti["pramana"] += pattern_scores[ModelType.ACTION] * 0.3

            # Relationship patterns → boost Vikalpa (emotional conceptualization)
            if ModelType.RELATIONSHIP in pattern_scores:
                vritti["vikalpa"] += pattern_scores[ModelType.RELATIONSHIP] * 0.4

            # Reflective patterns → boost Nidrā (abstract dormancy)
            if ModelType.REFLECTIVE in pattern_scores:
                vritti["nidra"] += pattern_scores[ModelType.REFLECTIVE] * 0.5

        # Domain-specific context detection for cross-domain disambiguation
        query_lower = query.lower()

        # Financial/transactional domain → Pramāṇa (factual cognition)
        financial_terms = ["money", "deposit", "account", "balance", "loan", "bank account",
                          "credit", "debit", "payment", "transaction", "financial"]
        if any(term in query_lower for term in financial_terms):
            vritti["pramana"] += 0.4
            vritti["smrti"] += 0.2  # Procedural memory

        # Nature/scenic domain → Vikalpa (creative conceptualization)
        nature_terms = ["river", "stream", "sunset", "sunrise", "meadow", "garden",
                       "forest", "mountain", "ocean", "sky", "peaceful", "grassy"]
        if any(term in query_lower for term in nature_terms):
            vritti["vikalpa"] += 0.4
            vritti["nidra"] += 0.2  # Contemplative stillness

        # Technical/procedural domain → Pramāṇa + Smṛti
        technical_terms = ["test", "database", "migration", "deploy", "code", "script",
                          "system", "server", "algorithm", "function"]
        if any(term in query_lower for term in technical_terms):
            vritti["pramana"] += 0.3
            vritti["smrti"] += 0.3

        # Question markers
        if any(q in query_lower for q in ["how", "why", "what is", "explain"]):
            vritti["pramana"] += 0.3  # Question-seeking = valid cognition
        if any(q in query_lower for q in ["imagine", "pretend", "what if"]):
            vritti["vikalpa"] += 0.4  # Hypothetical = conceptualization
        if any(q in query_lower for q in ["remember", "recall", "when did"]):
            vritti["smrti"] += 0.3  # Memory-based = smṛti

        # Normalize to probability distribution
        total = sum(vritti.values())
        if total > 0:
            vritti = {k: v / total for k, v in vritti.items()}

        return vritti

    def _apply_vritti_weighting(
        self,
        layer_totals: List[float],
        vritti_distribution: Dict[str, float],
        weight: float = 0.3,
    ) -> List[float]:
        """
        Apply vṛtti-based weighting to layer totals using R[v,a] matrix.

        Implements: biased_totals[a] = layer_totals[a] + weight * Σ_v p_v[v] · R[v,a]

        This allows cognitive mode to influence layer selection, improving
        cross-domain disambiguation for homonyms.

        Args:
            layer_totals: Raw 12D layer totals from phoneme analysis
            vritti_distribution: 5-element vṛtti probability distribution
            weight: How much to weight the vṛtti bias (0.0 to 1.0)

        Returns:
            Biased layer totals
        """
        # Get aspect weights from vṛtti distribution via R[v,a]
        aspect_weights = get_aspect_weights(vritti_distribution)

        # Apply weighting to layer totals
        biased_totals = layer_totals.copy()
        for i, layer_name in enumerate(LAYER_NAMES):
            bias = aspect_weights.get(layer_name, 0.0)
            biased_totals[i] += weight * bias

        return biased_totals

    def _compute_cross_resonance(
        self, word_vectors: List[WordVector]
    ) -> Dict[str, float]:
        """
        Compute semantic cross-resonance between words in a sentence.

        Words that resonate on the same layers create a "semantic field"
        that can help disambiguate homonyms.

        Args:
            word_vectors: List of WordVector from phrase analysis

        Returns:
            Dict mapping layer names to cluster strength scores
        """
        if len(word_vectors) < 2:
            return {}

        # Compute pairwise resonance and accumulate by shared dominant layers
        layer_cluster_scores: Dict[str, float] = {layer: 0.0 for layer in LAYER_NAMES}

        for i, vec_a in enumerate(word_vectors):
            for j, vec_b in enumerate(word_vectors):
                if i >= j:
                    continue

                # Compute similarity between word vectors
                similarity = self._cosine_similarity(vec_a.vector, vec_b.vector)

                if similarity > 0.5:  # Only consider resonant pairs
                    # Find shared high-scoring layers
                    for k, layer in enumerate(LAYER_NAMES):
                        # Both words have significant score in this layer
                        if vec_a.vector[k] > 0.1 and vec_b.vector[k] > 0.1:
                            # Weight by both the similarity and the layer scores
                            layer_cluster_scores[layer] += (
                                similarity * (vec_a.vector[k] + vec_b.vector[k]) / 2
                            )

        return layer_cluster_scores

    def _get_disambiguated_layer(
        self,
        word_vectors: List[WordVector],
        initial_dominant: str,
        layer_totals: List[float],
    ) -> Tuple[str, float]:
        """
        Use cross-resonance to potentially adjust the dominant layer.

        If the sentence has a strong semantic cluster in a different layer
        than the simple aggregation suggests, prefer the cluster.

        Args:
            word_vectors: Word vectors from phrase analysis
            initial_dominant: Initially computed dominant layer
            layer_totals: Raw layer totals from aggregation

        Returns:
            Tuple of (adjusted_dominant_layer, cluster_confidence_boost)
        """
        cluster_scores = self._compute_cross_resonance(word_vectors)

        if not cluster_scores:
            return initial_dominant, 0.0

        # Find the strongest cluster
        max_cluster_layer = max(cluster_scores, key=cluster_scores.get)
        max_cluster_score = cluster_scores[max_cluster_layer]

        # Normalize cluster score relative to total
        total_cluster = sum(cluster_scores.values())
        if total_cluster > 0:
            cluster_dominance = max_cluster_score / total_cluster
        else:
            cluster_dominance = 0.0

        # If cluster strongly disagrees with initial dominant, consider switching
        if max_cluster_layer != initial_dominant and cluster_dominance > 0.25:
            # Check if the cluster layer has reasonable support in raw totals
            cluster_layer_idx = LAYER_NAMES.index(max_cluster_layer)
            initial_layer_idx = LAYER_NAMES.index(initial_dominant)

            # Only switch if cluster layer is not too far behind in raw scores
            if layer_totals[cluster_layer_idx] > layer_totals[initial_layer_idx] * 0.7:
                return max_cluster_layer, cluster_dominance * 0.2

        # Cluster confirms initial - boost confidence
        if max_cluster_layer == initial_dominant:
            return initial_dominant, cluster_dominance * 0.15

        return initial_dominant, 0.0

    def route(self, query: str) -> RoutingDecision:
        """
        Route a query to the appropriate model.

        Combines phoneme layer analysis with keyword pattern detection
        and semantic cross-matching for improved accuracy.

        Args:
            query: The input query/prompt

        Returns:
            RoutingDecision with model type and confidence
        """
        # Analyze the query using phoneme analysis
        analysis = analyze_phrase(query)

        if not analysis.words:
            # Empty or all stop words
            return RoutingDecision(
                model_type=self.fallback_model,
                confidence=0.0,
                dominant_layer=LAYER_NAMES[0],
                layer_scores=(),
                query_analysis=analysis,
            )

        # Aggregate layer scores across content words (12D)
        layer_totals = [0.0] * 12
        for word_vec in analysis.words:
            for i, score in enumerate(word_vec.vector):
                layer_totals[i] += score

        # Detect intent patterns early for vṛtti computation
        pattern_scores = self._detect_intent_patterns(query)

        # Apply p_v[v] formula: Compute vṛtti distribution and bias layer totals
        # This enables cross-domain disambiguation for homonyms
        # weight=0.5 for stronger vṛtti influence on layer selection
        vritti_dist = self._detect_vritti_distribution(
            query, list(analysis.words), pattern_scores
        )
        biased_layer_totals = self._apply_vritti_weighting(
            layer_totals, vritti_dist, weight=0.5
        )

        # Find initial dominant layer using vṛtti-biased totals
        max_idx = 0
        max_total = biased_layer_totals[0]
        for i in range(1, 12):
            if biased_layer_totals[i] > max_total:
                max_total = biased_layer_totals[i]
                max_idx = i

        initial_dominant = LAYER_NAMES[max_idx]

        # Apply cross-resonance disambiguation for homonyms
        # This uses pairwise word similarity to find semantic clusters
        # NOTE: Using biased_layer_totals for vṛtti-aware disambiguation
        dominant_layer, cluster_boost = self._get_disambiguated_layer(
            list(analysis.words), initial_dominant, biased_layer_totals
        )

        # Calculate confidence using the best word-level dominant score
        max_word_score = 0.0
        for word_vec in analysis.words:
            if word_vec.dominant_score > max_word_score:
                max_word_score = word_vec.dominant_score

        # Add cluster boost to confidence
        max_word_score = min(max_word_score + cluster_boost, 1.0)

        # Normalize for layer_scores display (using biased totals)
        total = sum(biased_layer_totals)
        if total > 0:
            normalized = [s / total for s in biased_layer_totals]
        else:
            normalized = biased_layer_totals

        # Get top 3 layers for context
        indexed = [(LAYER_NAMES[i], normalized[i]) for i in range(12)]
        sorted_layers = sorted(indexed, key=lambda x: x[1], reverse=True)
        top_layers = tuple(sorted_layers[:3])

        # Check vocabulary for domain-specific term overrides (highest priority)
        vocab_result = self._check_vocabulary(query)
        if vocab_result:
            vocab_model, vocab_confidence = vocab_result
            return RoutingDecision(
                model_type=vocab_model,
                confidence=vocab_confidence,
                dominant_layer=dominant_layer,
                layer_scores=top_layers,
                query_analysis=analysis,
            )

        # pattern_scores already computed above for vṛtti detection

        # Determine model type by combining phoneme analysis with pattern matching
        phoneme_model = LAYER_TO_MODEL.get(dominant_layer, self.fallback_model)

        # If pattern detection has a strong signal, use it to override or confirm
        if pattern_scores:
            # Get the best pattern match
            best_pattern_model = max(pattern_scores, key=pattern_scores.get)
            best_pattern_score = pattern_scores[best_pattern_model]

            # Strong pattern match overrides phoneme if phoneme confidence is weak
            if best_pattern_score >= 0.2:
                # Pattern is strong enough to consider
                if max_word_score < self.confidence_threshold:
                    # Low phoneme confidence - trust pattern
                    model_type = best_pattern_model
                    confidence = min(max_word_score + best_pattern_score * self.pattern_boost, 1.0)
                elif best_pattern_model == phoneme_model:
                    # Pattern confirms phoneme - boost confidence
                    model_type = phoneme_model
                    confidence = min(max_word_score + best_pattern_score * self.pattern_boost, 1.0)
                else:
                    # Pattern and phoneme disagree - use pattern if score is high
                    if best_pattern_score >= 0.4:
                        model_type = best_pattern_model
                        confidence = min(max_word_score + best_pattern_score * self.pattern_boost, 1.0)
                    else:
                        # Stick with phoneme but note conflict
                        model_type = phoneme_model
                        confidence = max_word_score
            else:
                # Pattern too weak - use phoneme
                model_type = phoneme_model if max_word_score >= self.confidence_threshold else self.fallback_model
                confidence = max_word_score
        else:
            # No pattern matches - use pure phoneme analysis
            if max_word_score < self.confidence_threshold:
                model_type = self.fallback_model
                confidence = max_word_score
            else:
                model_type = phoneme_model
                confidence = max_word_score

        return RoutingDecision(
            model_type=model_type,
            confidence=confidence,
            dominant_layer=dominant_layer,
            layer_scores=top_layers,
            query_analysis=analysis,
        )

    def route_batch(
        self,
        queries: Tuple[str, ...],
    ) -> Tuple[RoutingDecision, ...]:
        """Route multiple queries."""
        return tuple(self.route(q) for q in queries)

    def estimate_savings(
        self,
        queries: Tuple[str, ...],
        general_model_params: int = 175_000_000_000,  # 175B
        specialized_model_params: int = 7_000_000_000,  # 7B
    ) -> dict:
        """
        Estimate parameter savings from routing.

        Args:
            queries: Sample queries to analyze
            general_model_params: Parameters in general model
            specialized_model_params: Parameters in specialized models

        Returns:
            Dict with savings estimates
        """
        decisions = self.route_batch(queries)

        general_count = sum(1 for d in decisions if d.model_type == ModelType.GENERAL)
        specialized_count = len(decisions) - general_count

        # Without routing: all queries use general model
        without_routing = len(queries) * general_model_params

        # With routing: some use specialized
        with_routing = (
            general_count * general_model_params +
            specialized_count * specialized_model_params
        )

        return {
            "queries_to_general": general_count,
            "queries_to_specialized": specialized_count,
            "percent_specialized": specialized_count / len(queries) * 100 if queries else 0,
            "params_without_routing": without_routing,
            "params_with_routing": with_routing,
            "param_reduction_factor": without_routing / with_routing if with_routing > 0 else 0,
        }


class ModelRegistry:
    """
    Registry of specialized models for the router.

    Register actual model handlers and let the router dispatch to them.
    """

    def __init__(self):
        self._models: Dict[ModelType, Callable] = {}
        self._router = SemanticRouter()

    def register(self, model_type: ModelType, handler: Callable):
        """Register a model handler."""
        self._models[model_type] = handler

    def invoke(self, query: str) -> Any:
        """
        Route and invoke the appropriate model.

        Args:
            query: Input query

        Returns:
            Result from the selected model
        """
        decision = self._router.route(query)
        handler = self._models.get(decision.model_type)

        if handler is None:
            # Fallback to general if no handler registered
            handler = self._models.get(ModelType.GENERAL)

        if handler is None:
            raise RuntimeError(f"No handler for {decision.model_type}")

        return handler(query, decision)


# Example specialized model stubs
def relationship_model_stub(query: str, decision: RoutingDecision) -> str:
    """Stub for relationship-focused model."""
    return f"[RELATIONSHIP MODEL] Processing: {query}"


def reasoning_model_stub(query: str, decision: RoutingDecision) -> str:
    """Stub for reasoning-focused model."""
    return f"[REASONING MODEL] Processing: {query}"


def action_model_stub(query: str, decision: RoutingDecision) -> str:
    """Stub for action-focused model."""
    return f"[ACTION MODEL] Processing: {query}"


def create_demo_registry() -> ModelRegistry:
    """Create a demo registry with stub handlers."""
    registry = ModelRegistry()
    registry.register(ModelType.RELATIONSHIP, relationship_model_stub)
    registry.register(ModelType.REASONING, reasoning_model_stub)
    registry.register(ModelType.ACTION, action_model_stub)
    registry.register(ModelType.GENERAL, lambda q, d: f"[GENERAL MODEL] {q}")
    return registry
