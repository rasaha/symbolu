"""
AGI Context
===========

Wrapper that integrates 10D backbone AGI capabilities into the engine architecture.

This provides:
    - Event tagging and 10D encoding
    - Mirror pair balance checking
    - Persona query tracking
    - Experiential storage and retrieval
    - Cross-domain reasoning
    - Phoneme validation
    - Insight generation

Usage:
    from symbolu.engine.agi_context import AGIContext

    ctx = AGIContext(persona_id="user_123")

    # Process a query with full AGI pipeline
    result = ctx.process_query(
        query="Why did my startup fail?",
        domain="business",
    )

    # Get cross-domain insights
    insights = ctx.get_insights(mode=InsightMode.NEW_POSSIBILITIES)

    # Check if an experiential should be stored
    validated = ctx.validate_and_store(event_text, domain="history")
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from enum import Enum

from symbolu.engine.query_type import (
    classify_query_type,
    QueryType,
    QueryTypeResult,
    is_problem_query,
)
from symbolu.ontology.backbone import (
    # Core encoding
    encode_10d,
    encode_with_events,
    tag_events,
    DimensionalVector,
    EventType,
    # Mirror pairs
    compute_balance,
    propagate_to_mirror,
    is_transferable_insight,
    explain_balance,
    BalanceReport,
    # Persona tracking
    PersonaStore,
    get_persona_store,
    track_query,
    get_persona_insights,
    PersonaProfile,
    # Experiential storage
    ExperientialObject,
    ExperientialStore,
    get_experiential_store,
    create_experiential,
    PatternType,
    # Phoneme validation
    validate_event,
    validate_experiential_before_store,
    ValidationResult,
    ValidationReport,
    # Semantic checks
    check_semantic_contradiction,
    SemanticCheck,
    # Learning pipeline
    learn_from_event,
    retrieve_similar,
    LearningResult,
    RetrievalResult,
    MatchType,
    # Similarity
    compute_similarity,
    find_similar,
    SimilarityResult,
    # Reasoning synthesis
    ReasoningSynthesizer,
    synthesize_for_problem,
    SynthesisResult,
    # Cross-domain config
    get_cross_domain_config,
    CrossDomainConfig,
    DomainPairPolicy,
    # Insight generation
    InsightMode,
    generate_insights,
    PersonalInsight,
    InsightType,
)


class AGILevel(Enum):
    """AGI capability level for different tiers."""
    NONE = "none"          # Enterprise Search: No AGI
    LIGHT = "light"        # Enterprise Chat: Persona + retrieval only
    FULL = "full"          # Consumer: Full AGI pipeline


@dataclass
class QueryContext:
    """Context for a processed query."""
    query: str
    domain: Optional[str]

    # Query type classification (problem vs information)
    query_type: QueryType
    query_type_confidence: float

    # 10D encoding
    vector_10d: Tuple[float, ...]
    events: Tuple[EventType, ...]

    # Mirror balance
    balance_score: float
    balance_report: BalanceReport
    is_transferable: bool

    # Validation
    semantic_check: Optional[SemanticCheck] = None
    phoneme_validation: Optional[ValidationReport] = None

    # Cross-domain retrieval (only populated for PROBLEM queries)
    similar_experientials: List[RetrievalResult] = field(default_factory=list)
    cross_domain_skipped: bool = False  # True if skipped due to INFORMATION query

    # Synthesis (if requested)
    synthesis: Optional[SynthesisResult] = None


@dataclass
class AGISignal:
    """AGI signal to include in engine results."""
    level: AGILevel
    persona_id: Optional[str]

    # Query type (problem vs information)
    query_type: str  # "problem" or "information"
    query_type_confidence: float
    cross_domain_enabled: bool  # Whether cross-domain was enabled for this query

    # What was computed
    events_detected: List[str]
    balance_score: float
    is_transferable: bool

    # Cross-domain matches (if any - only for PROBLEM queries)
    cross_domain_matches: int
    top_match_domain: Optional[str]
    top_match_similarity: float

    # Insights available
    insights_available: int

    # Learning outcome
    learned: bool
    learning_outcome: Optional[str]


class AGIContext:
    """
    AGI Context integrating backbone capabilities.

    This wraps the 10D backbone modules to provide a unified interface
    for the engine architecture.

    Example:
        ctx = AGIContext(persona_id="user_123", level=AGILevel.FULL)

        # Process query
        query_ctx = ctx.process_query(
            query="My startup co-founders disagree",
            domain="business",
        )

        # Check cross-domain matches
        for match in query_ctx.similar_experientials:
            print(f"{match.source_domain}: {match.similarity:.2f}")

        # Get insights
        insights = ctx.get_insights()
    """

    def __init__(
        self,
        persona_id: Optional[str] = None,
        level: AGILevel = AGILevel.FULL,
        auto_learn: bool = True,
        cross_domain_config: Optional[CrossDomainConfig] = None,
    ):
        """
        Initialize AGI context.

        Args:
            persona_id: User/session identifier for tracking
            level: AGI capability level
            auto_learn: Automatically store validated experientials
            cross_domain_config: Admin-level domain policy (uses default if None)
        """
        self.persona_id = persona_id
        self.level = level
        self.auto_learn = auto_learn

        # Get stores
        self.persona_store = get_persona_store()
        self.experiential_store = get_experiential_store()
        self.cross_domain_config = cross_domain_config or get_cross_domain_config()

        # Track last query for continuity
        self._last_query_context: Optional[QueryContext] = None

    def process_query(
        self,
        query: str,
        domain: Optional[str] = None,
        synthesize: bool = False,
        max_matches: int = 5,
    ) -> QueryContext:
        """
        Process a query through the AGI pipeline.

        Steps:
            1. Tag events in query
            2. Encode to 10D with events
            3. Check mirror balance
            4. Validate semantically
            5. Track persona query
            6. Retrieve similar experientials
            7. Optionally synthesize cross-domain reasoning

        Args:
            query: Input query text
            domain: Optional domain hint (auto-detected if not provided)
            synthesize: Whether to run full reasoning synthesis
            max_matches: Maximum cross-domain matches to retrieve

        Returns:
            QueryContext with full AGI analysis
        """
        # Step 0: Classify query type (problem vs information)
        # Cross-domain reasoning only activates for PROBLEM queries
        query_type_result = classify_query_type(query)
        is_problem = query_type_result.query_type == QueryType.PROBLEM

        if self.level == AGILevel.NONE:
            # Minimal processing for Enterprise Search
            vector = encode_10d(query)
            return QueryContext(
                query=query,
                domain=domain,
                query_type=query_type_result.query_type,
                query_type_confidence=query_type_result.confidence,
                vector_10d=tuple(vector.values),
                events=(),
                balance_score=0.0,
                balance_report=BalanceReport(
                    pairs=[],
                    total_imbalance=0.0,
                    balance_score=0.0,
                    dominant_state="none",
                    propagation_needed=[],
                ),
                is_transferable=False,
                cross_domain_skipped=True,  # Always skip for Enterprise Search
            )

        # Step 1-3: Encode with events (includes tagging and balance)
        balanced_vector, tagged_events, balance_report = encode_with_events(query)
        vector_10d = tuple(balanced_vector.values)
        events = tuple(e.event_type for e in tagged_events)
        balance_score = balance_report.balance_score
        is_transferable = is_transferable_insight(balanced_vector)

        # Step 4: Semantic validation
        semantic_check = None
        if self.level == AGILevel.FULL:
            words = query.lower().split()
            if len(words) >= 2:
                # Check for contradictions in key word pairs
                semantic_check = check_semantic_contradiction(words[0], words[-1])

        # Step 5: Track persona query
        if self.persona_id and self.level in (AGILevel.LIGHT, AGILevel.FULL):
            track_query(
                persona_id=self.persona_id,
                query_text=query,
                domain=domain or "general",
            )

        # Step 6: Retrieve similar experientials (ONLY for PROBLEM queries)
        # Cross-domain reasoning adds noise for information-gathering queries
        similar = []
        cross_domain_skipped = False
        if self.level in (AGILevel.LIGHT, AGILevel.FULL):
            if is_problem:
                # Problem query - enable cross-domain reasoning
                similar = retrieve_similar(
                    query=query,
                    current_domain=domain,
                    top_k=max_matches,
                    config=self.cross_domain_config,
                )
            else:
                # Information query - skip cross-domain (reduces noise)
                cross_domain_skipped = True

        # Step 7: Synthesize if requested
        synthesis = None
        if synthesize and self.level == AGILevel.FULL and similar:
            synthesis = synthesize_for_problem(
                problem=query,
                experientials=[r.experiential for r in similar],
                persona_id=self.persona_id,
            )

        # Step 8: Phoneme validation (for full level)
        phoneme_validation = None
        if self.level == AGILevel.FULL:
            phoneme_validation = validate_event(
                event_text=query,
                event_words=query.split()[:5],  # First 5 words
            )

        ctx = QueryContext(
            query=query,
            domain=domain,
            query_type=query_type_result.query_type,
            query_type_confidence=query_type_result.confidence,
            vector_10d=vector_10d,
            events=events,
            balance_score=balance_score,
            balance_report=balance_report,
            is_transferable=is_transferable,
            semantic_check=semantic_check,
            phoneme_validation=phoneme_validation,
            similar_experientials=similar,
            cross_domain_skipped=cross_domain_skipped,
            synthesis=synthesis,
        )

        self._last_query_context = ctx
        return ctx

    def learn_from_query(
        self,
        query_context: Optional[QueryContext] = None,
        insight: Optional[str] = None,
        causal_chain: Optional[List[str]] = None,
        pattern_type: PatternType = PatternType.CAUSAL,
    ) -> LearningResult:
        """
        Learn from a processed query, storing as experiential.

        Only stores if:
            - Phoneme validation passes
            - Balance score indicates transferability
            - No semantic contradictions

        Args:
            query_context: Query context (uses last if not provided)
            insight: Optional insight text to associate
            causal_chain: Optional causal chain
            pattern_type: Type of pattern

        Returns:
            LearningResult indicating success/failure and reason
        """
        ctx = query_context or self._last_query_context
        if not ctx:
            return LearningResult(
                success=False,
                outcome="no_context",
                reason="No query context available",
            )

        return learn_from_event(
            event_text=ctx.query,
            domain=ctx.domain or "general",
            insight=insight,
            causal_chain=causal_chain,
            pattern_type=pattern_type,
        )

    def get_insights(
        self,
        mode: InsightMode = InsightMode.NEW_POSSIBILITIES,
        current_domain: Optional[str] = None,
        max_insights: int = 5,
    ) -> List[PersonalInsight]:
        """
        Get personalized insights based on persona history.

        Args:
            mode: Insight mode (RECENT_MEMORY, DOMAIN_RELATIVE, NEW_POSSIBILITIES)
            current_domain: Current domain context
            max_insights: Maximum insights to return

        Returns:
            List of PersonalInsight objects
        """
        if not self.persona_id or self.level != AGILevel.FULL:
            return []

        ctx = self._last_query_context
        current_context = ctx.query if ctx else ""
        domain = current_domain or (ctx.domain if ctx else "general")

        return generate_insights(
            persona_id=self.persona_id,
            current_context=current_context,
            current_domain=domain,
            mode=mode,
        )[:max_insights]

    def get_persona_profile(self) -> Optional[PersonaProfile]:
        """Get the current persona's profile."""
        if not self.persona_id:
            return None
        return self.persona_store.get_or_create(self.persona_id)

    def get_cross_domain_bridges(self) -> Dict[Tuple[str, str], int]:
        """
        Get discovered cross-domain bridges for this persona.

        Returns:
            Dict mapping (domain_a, domain_b) to bridge count
        """
        profile = self.get_persona_profile()
        if not profile:
            return {}
        return profile.bridges

    def to_signal(self) -> AGISignal:
        """
        Convert current state to AGISignal for engine results.

        Returns:
            AGISignal with summary of AGI computations
        """
        ctx = self._last_query_context

        if not ctx:
            return AGISignal(
                level=self.level,
                persona_id=self.persona_id,
                query_type="information",
                query_type_confidence=0.0,
                cross_domain_enabled=False,
                events_detected=[],
                balance_score=0.0,
                is_transferable=False,
                cross_domain_matches=0,
                top_match_domain=None,
                top_match_similarity=0.0,
                insights_available=0,
                learned=False,
                learning_outcome=None,
            )

        # Get top match info
        top_match_domain = None
        top_match_similarity = 0.0
        if ctx.similar_experientials:
            top = ctx.similar_experientials[0]
            top_match_domain = top.source_domain
            top_match_similarity = top.similarity

        return AGISignal(
            level=self.level,
            persona_id=self.persona_id,
            query_type=ctx.query_type.value,
            query_type_confidence=ctx.query_type_confidence,
            cross_domain_enabled=not ctx.cross_domain_skipped,
            events_detected=[e.value for e in ctx.events],
            balance_score=ctx.balance_score,
            is_transferable=ctx.is_transferable,
            cross_domain_matches=len(ctx.similar_experientials),
            top_match_domain=top_match_domain,
            top_match_similarity=top_match_similarity,
            insights_available=len(self.get_insights()) if self.persona_id else 0,
            learned=False,
            learning_outcome=None,
        )

    def explain_query_balance(self) -> str:
        """Get human-readable explanation of last query's balance."""
        ctx = self._last_query_context
        if not ctx:
            return "No query processed yet."
        return explain_balance(ctx.balance_report)
