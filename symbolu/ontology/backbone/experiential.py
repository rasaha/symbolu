"""
Experiential Reasoning Objects
==============================

Stores extracted reasonings, patterns, and insights from content
as structured objects that can be retrieved and applied across domains.

An ExperientialObject captures not just content, but the REASONING
that can be transferred to new problems.

Example:
    Source: "The Civil War divided the nation..."

    Extracted Experiential:
        Pattern: "polarity_escalation_to_bifurcation"
        Insight: "When opposing forces can't find middle ground, systems split"
        Causal Chain: polarization → failed_negotiation → bifurcation → conflict
        Transferable To: ["organizational_conflict", "family_dynamics", "markets"]
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any, Set
from enum import Enum
import hashlib
import json
import re
from datetime import datetime

from .encoder import DimensionalVector, Dimension, encode_10d
from .extractors import ProjectionDirection, detect_projection_direction


class PatternType(Enum):
    """Types of reasoning patterns."""
    CAUSAL = "causal"                    # A causes B
    CYCLICAL = "cyclical"                # A → B → C → A
    ESCALATION = "escalation"            # A → A+ → A++
    TRANSFORMATION = "transformation"    # A becomes B
    BIFURCATION = "bifurcation"          # A splits into B and C
    CONVERGENCE = "convergence"          # A and B merge into C
    EQUILIBRIUM = "equilibrium"          # Forces balance
    THRESHOLD = "threshold"              # Gradual until tipping point
    HIERARCHICAL = "hierarchical"        # Levels of abstraction
    ANALOGICAL = "analogical"            # A is like B


class ReasoningStrength(Enum):
    """Confidence in extracted reasoning."""
    STRONG = "strong"        # Clear, explicit reasoning
    MODERATE = "moderate"    # Implied reasoning
    WEAK = "weak"            # Speculative connection


@dataclass
class CausalChain:
    """
    Represents a causal sequence extracted from content.

    Example: ["polarization", "failed_negotiation", "bifurcation", "conflict"]
    """
    steps: List[str]
    direction: str = "forward"  # "forward", "backward", "bidirectional"
    strength: ReasoningStrength = ReasoningStrength.MODERATE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "steps": self.steps,
            "direction": self.direction,
            "strength": self.strength.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CausalChain":
        return cls(
            steps=data["steps"],
            direction=data.get("direction", "forward"),
            strength=ReasoningStrength(data.get("strength", "moderate")),
        )


@dataclass
class ApplicabilityCondition:
    """
    Conditions under which this reasoning applies.

    Expressed in terms of 10D dimensional requirements.
    """
    requires: Dict[Dimension, float] = field(default_factory=dict)      # Must have >= threshold
    strengthened_by: Dict[Dimension, float] = field(default_factory=dict)  # Better if present
    weakened_by: Dict[Dimension, float] = field(default_factory=dict)   # Worse if present

    def matches(self, vector: DimensionalVector) -> Tuple[bool, float]:
        """
        Check if vector matches conditions.

        Returns:
            Tuple of (matches_required, match_strength)
        """
        # Check required conditions
        for dim, threshold in self.requires.items():
            if vector.get(dim) < threshold:
                return False, 0.0

        # Calculate match strength
        strength = 1.0

        for dim, threshold in self.strengthened_by.items():
            if vector.get(dim) >= threshold:
                strength += 0.1

        for dim, threshold in self.weakened_by.items():
            if vector.get(dim) >= threshold:
                strength -= 0.1

        return True, max(0.0, min(2.0, strength))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requires": {d.name: v for d, v in self.requires.items()},
            "strengthened_by": {d.name: v for d, v in self.strengthened_by.items()},
            "weakened_by": {d.name: v for d, v in self.weakened_by.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ApplicabilityCondition":
        return cls(
            requires={Dimension[k]: v for k, v in data.get("requires", {}).items()},
            strengthened_by={Dimension[k]: v for k, v in data.get("strengthened_by", {}).items()},
            weakened_by={Dimension[k]: v for k, v in data.get("weakened_by", {}).items()},
        )


@dataclass
class ExperientialObject:
    """
    A stored reasoning/insight that can be applied across domains.

    This is the core unit of cross-domain knowledge transfer.
    """
    # Identity
    experiential_id: str
    created_at: str

    # 10D encoding
    vector_10d: DimensionalVector
    projection_direction: ProjectionDirection

    # Source information
    source_domain: str
    source_content: str
    source_reference: Optional[str] = None

    # Extracted reasoning
    pattern_type: PatternType = PatternType.CAUSAL
    pattern_name: str = ""
    insight: str = ""
    causal_chain: Optional[CausalChain] = None

    # Transferability
    transferable_to: List[str] = field(default_factory=list)
    applicability: Optional[ApplicabilityCondition] = None

    # Metadata
    tags: List[str] = field(default_factory=list)
    confidence: ReasoningStrength = ReasoningStrength.MODERATE

    # User interaction tracking
    user_affinities: Dict[str, float] = field(default_factory=dict)
    usage_count: int = 0
    success_count: int = 0

    def __post_init__(self):
        if not self.experiential_id:
            self.experiential_id = self._generate_id()
        if not self.created_at:
            self.created_at = datetime.utcnow().isoformat()

    def _generate_id(self) -> str:
        """Generate deterministic ID from content."""
        content = f"{self.source_domain}:{self.source_content[:100]}:{self.pattern_name}"
        return "exp_" + hashlib.sha256(content.encode()).hexdigest()[:12]

    def get_user_affinity(self, user_id: str) -> float:
        """Get affinity score for a user."""
        return self.user_affinities.get(user_id, 0.5)  # Default neutral

    def update_user_affinity(self, user_id: str, was_useful: bool, rating: float = 0.5):
        """Update user affinity based on feedback."""
        current = self.user_affinities.get(user_id, 0.5)

        # Exponential moving average
        if was_useful:
            new_value = current * 0.7 + rating * 0.3
            self.success_count += 1
        else:
            new_value = current * 0.7 + (1.0 - rating) * 0.3

        self.user_affinities[user_id] = max(0.0, min(1.0, new_value))
        self.usage_count += 1

    def matches_problem(self, problem_vector: DimensionalVector) -> Tuple[bool, float]:
        """Check if this experiential applies to a problem."""
        if self.applicability:
            return self.applicability.matches(problem_vector)

        # Default: use structural similarity
        from .similarity import structural_similarity
        sim = structural_similarity(self.vector_10d, problem_vector)
        return sim > 0.5, sim

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiential_id": self.experiential_id,
            "created_at": self.created_at,
            "vector_10d": self.vector_10d.to_dict(),
            "projection_direction": self.projection_direction.value,
            "source_domain": self.source_domain,
            "source_content": self.source_content,
            "source_reference": self.source_reference,
            "pattern_type": self.pattern_type.value,
            "pattern_name": self.pattern_name,
            "insight": self.insight,
            "causal_chain": self.causal_chain.to_dict() if self.causal_chain else None,
            "transferable_to": self.transferable_to,
            "applicability": self.applicability.to_dict() if self.applicability else None,
            "tags": self.tags,
            "confidence": self.confidence.value,
            "user_affinities": self.user_affinities,
            "usage_count": self.usage_count,
            "success_count": self.success_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExperientialObject":
        return cls(
            experiential_id=data["experiential_id"],
            created_at=data["created_at"],
            vector_10d=DimensionalVector.from_dict(data["vector_10d"]),
            projection_direction=ProjectionDirection(data["projection_direction"]),
            source_domain=data["source_domain"],
            source_content=data["source_content"],
            source_reference=data.get("source_reference"),
            pattern_type=PatternType(data.get("pattern_type", "causal")),
            pattern_name=data.get("pattern_name", ""),
            insight=data.get("insight", ""),
            causal_chain=CausalChain.from_dict(data["causal_chain"]) if data.get("causal_chain") else None,
            transferable_to=data.get("transferable_to", []),
            applicability=ApplicabilityCondition.from_dict(data["applicability"]) if data.get("applicability") else None,
            tags=data.get("tags", []),
            confidence=ReasoningStrength(data.get("confidence", "moderate")),
            user_affinities=data.get("user_affinities", {}),
            usage_count=data.get("usage_count", 0),
            success_count=data.get("success_count", 0),
        )


# =============================================================================
# Experiential Store
# =============================================================================

class ExperientialStore:
    """
    Storage and retrieval for ExperientialObjects.

    Enables:
    - Add/retrieve experientials by ID
    - Search by 10D similarity
    - Filter by domain, pattern type, applicability
    - Rank by user affinity
    """

    def __init__(self):
        self._store: Dict[str, ExperientialObject] = {}
        self._by_domain: Dict[str, Set[str]] = {}
        self._by_pattern: Dict[PatternType, Set[str]] = {}
        self._by_tag: Dict[str, Set[str]] = {}

    def add(self, exp: ExperientialObject) -> None:
        """Add experiential to store."""
        self._store[exp.experiential_id] = exp

        # Index by domain
        if exp.source_domain not in self._by_domain:
            self._by_domain[exp.source_domain] = set()
        self._by_domain[exp.source_domain].add(exp.experiential_id)

        # Index by pattern
        if exp.pattern_type not in self._by_pattern:
            self._by_pattern[exp.pattern_type] = set()
        self._by_pattern[exp.pattern_type].add(exp.experiential_id)

        # Index by tags
        for tag in exp.tags:
            if tag not in self._by_tag:
                self._by_tag[tag] = set()
            self._by_tag[tag].add(exp.experiential_id)

    def get(self, experiential_id: str) -> Optional[ExperientialObject]:
        """Get experiential by ID."""
        return self._store.get(experiential_id)

    def search(
        self,
        problem_vector: DimensionalVector,
        user_id: Optional[str] = None,
        domains: Optional[List[str]] = None,
        pattern_types: Optional[List[PatternType]] = None,
        tags: Optional[List[str]] = None,
        min_similarity: float = 0.4,
        top_k: int = 10,
    ) -> List[Tuple[ExperientialObject, float]]:
        """
        Search for relevant experientials.

        Args:
            problem_vector: 10D encoding of the problem
            user_id: User ID for affinity weighting
            domains: Filter to these domains (None = all)
            pattern_types: Filter to these patterns (None = all)
            tags: Filter to these tags (None = all)
            min_similarity: Minimum structural similarity
            top_k: Number of results

        Returns:
            List of (experiential, score) tuples sorted by score
        """
        from .similarity import structural_similarity

        # Determine candidate set
        candidates = set(self._store.keys())

        if domains:
            domain_candidates = set()
            for domain in domains:
                domain_candidates.update(self._by_domain.get(domain, set()))
            candidates &= domain_candidates

        if pattern_types:
            pattern_candidates = set()
            for pt in pattern_types:
                pattern_candidates.update(self._by_pattern.get(pt, set()))
            candidates &= pattern_candidates

        if tags:
            tag_candidates = set()
            for tag in tags:
                tag_candidates.update(self._by_tag.get(tag, set()))
            candidates &= tag_candidates

        # Score candidates
        results = []
        for exp_id in candidates:
            exp = self._store[exp_id]

            # Check applicability
            matches, match_strength = exp.matches_problem(problem_vector)
            if not matches:
                continue

            # Compute structural similarity
            sim = structural_similarity(exp.vector_10d, problem_vector)
            if sim < min_similarity:
                continue

            # Compute final score
            score = sim * 0.5 + match_strength * 0.3

            # Add user affinity if available
            if user_id:
                affinity = exp.get_user_affinity(user_id)
                score = score * 0.7 + affinity * 0.3

            results.append((exp, score))

        # Sort by score
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def get_cross_domain(
        self,
        problem_vector: DimensionalVector,
        exclude_domain: str,
        top_k: int = 5
    ) -> List[Tuple[ExperientialObject, float]]:
        """Get experientials from OTHER domains."""
        other_domains = [d for d in self._by_domain.keys() if d != exclude_domain]
        return self.search(
            problem_vector,
            domains=other_domains,
            top_k=top_k
        )

    @property
    def size(self) -> int:
        return len(self._store)

    @property
    def domains(self) -> List[str]:
        return list(self._by_domain.keys())

    def export(self) -> Dict[str, Any]:
        """Export store to dictionary."""
        return {
            "experientials": [exp.to_dict() for exp in self._store.values()],
            "domains": self.domains,
            "size": self.size,
        }

    def import_data(self, data: Dict[str, Any]) -> int:
        """Import from dictionary. Returns count imported."""
        count = 0
        for exp_data in data.get("experientials", []):
            exp = ExperientialObject.from_dict(exp_data)
            self.add(exp)
            count += 1
        return count


# =============================================================================
# Factory Functions
# =============================================================================

def create_experiential(
    content: str,
    domain: str,
    pattern_name: str,
    insight: str,
    causal_steps: Optional[List[str]] = None,
    transferable_to: Optional[List[str]] = None,
    tags: Optional[List[str]] = None,
    reference: Optional[str] = None,
) -> ExperientialObject:
    """
    Factory function to create an ExperientialObject.

    Automatically encodes content to 10D and detects projection direction.
    """
    vector = encode_10d(content)
    direction, _, _ = detect_projection_direction(content)

    causal_chain = None
    if causal_steps:
        causal_chain = CausalChain(steps=causal_steps)

    # Auto-detect pattern type from name
    pattern_type = PatternType.CAUSAL
    name_lower = pattern_name.lower()
    if "cycl" in name_lower:
        pattern_type = PatternType.CYCLICAL
    elif "escal" in name_lower:
        pattern_type = PatternType.ESCALATION
    elif "transform" in name_lower:
        pattern_type = PatternType.TRANSFORMATION
    elif "bifurc" in name_lower or "split" in name_lower:
        pattern_type = PatternType.BIFURCATION
    elif "converg" in name_lower or "merg" in name_lower:
        pattern_type = PatternType.CONVERGENCE
    elif "equilib" in name_lower or "balance" in name_lower:
        pattern_type = PatternType.EQUILIBRIUM
    elif "threshold" in name_lower or "tipping" in name_lower:
        pattern_type = PatternType.THRESHOLD

    return ExperientialObject(
        experiential_id="",  # Will be auto-generated
        created_at="",  # Will be auto-generated
        vector_10d=vector,
        projection_direction=direction,
        source_domain=domain,
        source_content=content,
        source_reference=reference,
        pattern_type=pattern_type,
        pattern_name=pattern_name,
        insight=insight,
        causal_chain=causal_chain,
        transferable_to=transferable_to or [],
        tags=tags or [],
    )


# Global store singleton
_global_store: Optional[ExperientialStore] = None


def get_experiential_store() -> ExperientialStore:
    """Get or create global experiential store."""
    global _global_store
    if _global_store is None:
        _global_store = ExperientialStore()
    return _global_store
