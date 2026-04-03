"""
Bucket Router for Master Chat Context Retrieval
================================================

Signal-based router that activates relevant knowledge buckets
based on ontological signals from the incoming message.

The router compares message signals against bucket signal profiles
to determine activation strength. Activated buckets contribute
context entries for LLM injection.

Routing Algorithm:
    1. Extract signals from message (12D, Kosha, Vritti, Guna, Entropy)
    2. For each bucket, compute activation score based on signal match
    3. Apply recency and access frequency boosts
    4. Retrieve top-K entries from activated buckets
    5. Assemble context for LLM injection

Version: 1.0
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

from .bucket_models import (
    Bucket,
    BucketCategory,
    BucketEntry,
    ActivatedBucket,
    MessageSignals,
    SignalProfile,
    LAYER_TO_BUCKET,
)


# =============================================================================
# Router Configuration
# =============================================================================

@dataclass
class RouterConfig:
    """
    Configuration for bucket routing behavior.

    Attributes:
        top_k_buckets: Maximum number of buckets to activate
        top_k_entries_per_bucket: Maximum entries to retrieve per bucket
        min_activation_threshold: Minimum score to activate a bucket
        recency_boost_hours: Hours within which recency boost applies
        recency_boost_factor: Maximum boost for recently accessed buckets
        frequency_boost_factor: Maximum boost for frequently accessed buckets
        semantic_weight: Weight for semantic similarity (if embeddings available)
        signal_weight: Weight for signal profile matching
    """
    top_k_buckets: int = 3
    top_k_entries_per_bucket: int = 5
    min_activation_threshold: float = 0.3
    recency_boost_hours: float = 24.0
    recency_boost_factor: float = 0.2
    frequency_boost_factor: float = 0.1
    semantic_weight: float = 0.4
    signal_weight: float = 0.6


# Default configuration
DEFAULT_ROUTER_CONFIG = RouterConfig()


# =============================================================================
# Signal Matching Functions
# =============================================================================

def compute_layer_match(
    message_layers: Dict[int, float],
    profile_layers: Tuple[int, ...],
) -> float:
    """
    Compute match score between message layer activations and profile layers.

    Args:
        message_layers: Dict mapping layer index to activation weight
        profile_layers: Tuple of preferred layer indices for the bucket

    Returns:
        Match score in [0.0, 1.0]
    """
    if not message_layers or not profile_layers:
        return 0.0

    # Sum activations for layers that match profile
    matched_activation = sum(
        message_layers.get(layer, 0.0)
        for layer in profile_layers
    )

    # Normalize by total activation
    total_activation = sum(message_layers.values())
    if total_activation == 0:
        return 0.0

    # Score is proportion of activation in matching layers
    return min(1.0, matched_activation / total_activation)


def compute_kosha_match(
    message_kosha_level: float,
    profile_kosha_range: Tuple[float, float],
) -> float:
    """
    Compute match score between message kosha level and profile range.

    Args:
        message_kosha_level: Normalized kosha level [0.0, 1.0]
        profile_kosha_range: (low, high) preferred range

    Returns:
        Match score in [0.0, 1.0]
    """
    low, high = profile_kosha_range

    if low <= message_kosha_level <= high:
        # Perfect match - within range
        return 1.0
    elif message_kosha_level < low:
        # Below range - decay based on distance
        distance = low - message_kosha_level
        return max(0.0, 1.0 - distance * 2)
    else:
        # Above range - decay based on distance
        distance = message_kosha_level - high
        return max(0.0, 1.0 - distance * 2)


def compute_vritti_match(
    message_vritti_dist: Dict[str, float],
    profile_vritti_types: Tuple[str, ...],
) -> float:
    """
    Compute match score between message vritti distribution and profile.

    Args:
        message_vritti_dist: Dict mapping vritti type to weight
        profile_vritti_types: Tuple of preferred vritti types

    Returns:
        Match score in [0.0, 1.0]
    """
    if not message_vritti_dist or not profile_vritti_types:
        return 0.5  # Neutral if no vritti info

    # Sum weights for matching vritti types
    matched_weight = sum(
        message_vritti_dist.get(vt, 0.0)
        for vt in profile_vritti_types
    )

    total_weight = sum(message_vritti_dist.values())
    if total_weight == 0:
        return 0.5

    return min(1.0, matched_weight / total_weight)


def compute_guna_match(
    message_guna_dist: Dict[str, float],
    profile_guna_bias: Optional[str],
) -> float:
    """
    Compute match score between message guna distribution and profile bias.

    Args:
        message_guna_dist: Dict mapping guna name to probability
        profile_guna_bias: Preferred dominant guna (or None for balanced)

    Returns:
        Match score in [0.0, 1.0]
    """
    if not message_guna_dist:
        return 0.5  # Neutral if no guna info

    if profile_guna_bias is None:
        # Profile prefers balanced - reward low variance
        values = list(message_guna_dist.values())
        if len(values) < 2:
            return 0.5
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        # Low variance = high score
        return max(0.0, 1.0 - variance * 3)
    else:
        # Profile prefers specific guna - check if it's dominant
        bias_value = message_guna_dist.get(profile_guna_bias, 0.0)
        return min(1.0, bias_value * 1.5)  # Boost if dominant


def compute_entropy_match(
    message_entropy: float,
    profile_entropy_range: Tuple[float, float],
) -> float:
    """
    Compute match score between message entropy and profile range.

    Args:
        message_entropy: Normalized entropy [0.0, 1.0]
        profile_entropy_range: (low, high) preferred range

    Returns:
        Match score in [0.0, 1.0]
    """
    low, high = profile_entropy_range

    if low <= message_entropy <= high:
        return 1.0
    elif message_entropy < low:
        distance = low - message_entropy
        return max(0.0, 1.0 - distance * 2)
    else:
        distance = message_entropy - high
        return max(0.0, 1.0 - distance * 2)


def compute_profile_match(
    signals: MessageSignals,
    profile: SignalProfile,
) -> Tuple[float, Dict[str, float]]:
    """
    Compute overall match score between message signals and bucket profile.

    Args:
        signals: Message ontological signals
        profile: Bucket signal profile

    Returns:
        Tuple of (overall_score, component_scores_dict)
    """
    # Compute individual component scores
    layer_score = compute_layer_match(
        signals.ontology_layers,
        profile.ontology_layers,
    )

    kosha_score = compute_kosha_match(
        signals.get_kosha_level(),
        profile.kosha_range,
    )

    vritti_score = compute_vritti_match(
        signals.vritti_distribution,
        profile.vritti_types,
    )

    guna_score = compute_guna_match(
        signals.guna_distribution,
        profile.guna_bias,
    )

    entropy_score = compute_entropy_match(
        signals.normalized_entropy,
        profile.entropy_range,
    )

    # Weighted combination
    # Layer match is most important (it's the primary router)
    weights = {
        "layer": 0.35,
        "kosha": 0.20,
        "vritti": 0.15,
        "guna": 0.15,
        "entropy": 0.15,
    }

    overall = (
        weights["layer"] * layer_score
        + weights["kosha"] * kosha_score
        + weights["vritti"] * vritti_score
        + weights["guna"] * guna_score
        + weights["entropy"] * entropy_score
    )

    component_scores = {
        "layer": layer_score,
        "kosha": kosha_score,
        "vritti": vritti_score,
        "guna": guna_score,
        "entropy": entropy_score,
    }

    return overall, component_scores


# =============================================================================
# Bucket Router
# =============================================================================

class BucketRouter:
    """
    Signal-based router for activating knowledge buckets.

    Routes incoming messages to relevant buckets based on
    ontological signal matching, recency, and access patterns.
    """

    def __init__(
        self,
        config: Optional[RouterConfig] = None,
    ):
        """
        Initialize the bucket router.

        Args:
            config: Router configuration (uses defaults if not provided)
        """
        self.config = config or DEFAULT_ROUTER_CONFIG

    def route(
        self,
        signals: MessageSignals,
        buckets: Dict[str, Bucket],
        query_embedding: Optional[List[float]] = None,
    ) -> List[ActivatedBucket]:
        """
        Route message signals to activate relevant buckets.

        Args:
            signals: Ontological signals extracted from the message
            buckets: Available buckets to route to
            query_embedding: Optional semantic embedding for similarity search

        Returns:
            List of ActivatedBucket results, sorted by activation score
        """
        if not buckets:
            return []

        # Score all buckets
        scored_buckets: List[Tuple[str, float, Dict[str, float]]] = []

        for bucket_id, bucket in buckets.items():
            # Compute signal profile match
            profile_score, component_scores = compute_profile_match(
                signals,
                bucket.signal_profile,
            )

            # Apply recency boost
            recency_boost = self._compute_recency_boost(bucket)

            # Apply frequency boost
            frequency_boost = self._compute_frequency_boost(bucket, buckets)

            # Compute semantic similarity if embeddings available
            semantic_score = 0.0
            if query_embedding and bucket.centroid_embedding:
                semantic_score = self._cosine_similarity(
                    query_embedding,
                    bucket.centroid_embedding,
                )

            # Combine scores
            if semantic_score > 0:
                base_score = (
                    self.config.signal_weight * profile_score
                    + self.config.semantic_weight * semantic_score
                )
            else:
                base_score = profile_score

            final_score = base_score + recency_boost + frequency_boost

            # Store component scores for explanation
            component_scores["recency_boost"] = recency_boost
            component_scores["frequency_boost"] = frequency_boost
            component_scores["semantic"] = semantic_score
            component_scores["base"] = base_score
            component_scores["final"] = final_score

            scored_buckets.append((bucket_id, final_score, component_scores))

        # Sort by score descending
        scored_buckets.sort(key=lambda x: x[1], reverse=True)

        # Activate top-K buckets above threshold
        activated: List[ActivatedBucket] = []

        for bucket_id, score, components in scored_buckets[:self.config.top_k_buckets]:
            if score < self.config.min_activation_threshold:
                continue

            bucket = buckets[bucket_id]

            # Retrieve relevant entries
            entries = self._retrieve_entries(
                bucket,
                signals,
                query_embedding,
            )

            # Generate activation reason
            reason = self._generate_activation_reason(
                bucket,
                signals,
                components,
            )

            # Record access
            bucket.record_access()

            activated.append(ActivatedBucket(
                bucket=bucket,
                activation_score=score,
                retrieved_entries=entries,
                activation_reason=reason,
            ))

        return activated

    def route_by_layer(
        self,
        dominant_layer: int,
        buckets: Dict[str, Bucket],
    ) -> Optional[ActivatedBucket]:
        """
        Quick route based on dominant ontology layer only.

        Useful for simple/fast routing when full signal analysis
        is not available.

        Args:
            dominant_layer: Dominant 12D layer index [1-12]
            buckets: Available buckets

        Returns:
            Single activated bucket or None
        """
        category = LAYER_TO_BUCKET.get(dominant_layer)
        if not category:
            return None

        bucket_id = category.value
        bucket = buckets.get(bucket_id)
        if not bucket:
            return None

        entries = bucket.get_recent_entries(self.config.top_k_entries_per_bucket)
        bucket.record_access()

        return ActivatedBucket(
            bucket=bucket,
            activation_score=0.8,  # High confidence for direct layer match
            retrieved_entries=entries,
            activation_reason=f"Direct layer match: Layer {dominant_layer} → {category.value}",
        )

    def _compute_recency_boost(self, bucket: Bucket) -> float:
        """Compute recency boost based on last access time."""
        if not bucket.last_accessed:
            return 0.0

        hours_since_access = (
            datetime.utcnow() - bucket.last_accessed
        ).total_seconds() / 3600

        if hours_since_access > self.config.recency_boost_hours:
            return 0.0

        # Linear decay
        decay = 1.0 - (hours_since_access / self.config.recency_boost_hours)
        return self.config.recency_boost_factor * decay

    def _compute_frequency_boost(
        self,
        bucket: Bucket,
        all_buckets: Dict[str, Bucket],
    ) -> float:
        """Compute frequency boost based on access count relative to others."""
        if not all_buckets:
            return 0.0

        max_access = max(b.access_count for b in all_buckets.values())
        if max_access == 0:
            return 0.0

        relative_frequency = bucket.access_count / max_access
        return self.config.frequency_boost_factor * relative_frequency

    def _retrieve_entries(
        self,
        bucket: Bucket,
        signals: MessageSignals,
        query_embedding: Optional[List[float]],
    ) -> List[BucketEntry]:
        """Retrieve most relevant entries from a bucket."""
        if not bucket.entries:
            return []

        limit = self.config.top_k_entries_per_bucket

        # If we have embeddings, use semantic similarity
        if query_embedding:
            entries_with_scores = []
            for entry in bucket.entries:
                if entry.embedding:
                    sim = self._cosine_similarity(query_embedding, entry.embedding)
                    entries_with_scores.append((entry, sim))
                else:
                    entries_with_scores.append((entry, 0.0))

            # Sort by similarity, then by importance
            entries_with_scores.sort(
                key=lambda x: (x[1], x[0].importance_score),
                reverse=True,
            )
            return [e for e, _ in entries_with_scores[:limit]]

        # Fall back to importance-weighted recent entries
        # Combine recency and importance
        now = datetime.utcnow()
        entries_with_scores = []

        for entry in bucket.entries:
            age_hours = (now - entry.timestamp).total_seconds() / 3600
            recency_score = math.exp(-age_hours / 24)  # Decay over 24 hours
            combined = 0.6 * entry.importance_score + 0.4 * recency_score
            entries_with_scores.append((entry, combined))

        entries_with_scores.sort(key=lambda x: x[1], reverse=True)
        return [e for e, _ in entries_with_scores[:limit]]

    def _generate_activation_reason(
        self,
        bucket: Bucket,
        signals: MessageSignals,
        components: Dict[str, float],
    ) -> str:
        """Generate human-readable activation reason."""
        parts = []

        # Identify strongest signal matches
        signal_components = ["layer", "kosha", "vritti", "guna", "entropy"]
        strong_matches = [
            (name, score)
            for name, score in components.items()
            if name in signal_components and score > 0.6
        ]
        strong_matches.sort(key=lambda x: x[1], reverse=True)

        if strong_matches:
            match_names = [m[0] for m in strong_matches[:2]]
            parts.append(f"Strong {'/'.join(match_names)} match")

        if components.get("recency_boost", 0) > 0.05:
            parts.append("recently accessed")

        if components.get("semantic", 0) > 0.5:
            parts.append("semantic similarity")

        if not parts:
            parts.append(f"profile match ({components['final']:.2f})")

        return f"{bucket.display_name}: {', '.join(parts)}"

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if len(a) != len(b) or not a:
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot_product / (norm_a * norm_b)


# =============================================================================
# Context Assembler
# =============================================================================

class ContextAssembler:
    """
    Assembles context from activated buckets for LLM injection.

    Formats activated bucket entries into a coherent context block
    that can be prepended to the user's message or added to the
    system prompt.
    """

    def __init__(
        self,
        max_context_tokens: int = 2000,
        avg_chars_per_token: float = 4.0,
    ):
        """
        Initialize the context assembler.

        Args:
            max_context_tokens: Maximum tokens for context injection
            avg_chars_per_token: Average characters per token (for estimation)
        """
        self.max_context_tokens = max_context_tokens
        self.avg_chars_per_token = avg_chars_per_token
        self.max_chars = int(max_context_tokens * avg_chars_per_token)

    def assemble(
        self,
        activated_buckets: List[ActivatedBucket],
        include_metadata: bool = False,
    ) -> str:
        """
        Assemble context from activated buckets.

        Args:
            activated_buckets: List of activated buckets with entries
            include_metadata: Whether to include activation scores

        Returns:
            Formatted context string for LLM injection
        """
        if not activated_buckets:
            return ""

        lines = ["<relevant_context>"]
        current_chars = len(lines[0])

        for ab in activated_buckets:
            if not ab.retrieved_entries:
                continue

            # Add bucket header
            if include_metadata:
                header = f"\n[{ab.bucket.display_name}] (relevance: {ab.activation_score:.2f})"
            else:
                header = f"\n[{ab.bucket.display_name}]"

            if current_chars + len(header) > self.max_chars:
                break

            lines.append(header)
            current_chars += len(header)

            # Add entries
            for entry in ab.retrieved_entries:
                text = entry.summary or entry.content
                # Truncate long entries
                if len(text) > 200:
                    text = text[:197] + "..."

                entry_line = f"  • {text}"

                if current_chars + len(entry_line) > self.max_chars:
                    break

                lines.append(entry_line)
                current_chars += len(entry_line)

        lines.append("</relevant_context>")

        return "\n".join(lines)

    def assemble_for_system_prompt(
        self,
        activated_buckets: List[ActivatedBucket],
    ) -> str:
        """
        Assemble context formatted for system prompt injection.

        Args:
            activated_buckets: List of activated buckets

        Returns:
            System prompt addition with context
        """
        context = self.assemble(activated_buckets, include_metadata=False)
        if not context:
            return ""

        return (
            "\n\nYou have access to relevant context from the user's history:\n"
            f"{context}\n"
            "Use this context to inform your responses when relevant, "
            "but don't explicitly mention that you're using stored context."
        )


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Configuration
    "RouterConfig",
    "DEFAULT_ROUTER_CONFIG",
    # Main classes
    "BucketRouter",
    "ContextAssembler",
    # Matching functions
    "compute_layer_match",
    "compute_kosha_match",
    "compute_vritti_match",
    "compute_guna_match",
    "compute_entropy_match",
    "compute_profile_match",
]
