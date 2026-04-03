"""
Master Chat Integration with ChatService
=========================================

Provides a unified chat interface that integrates:
- Existing ChatService for LLM interaction
- MasterSessionStore for bucket-based context
- MLCR/Pipeline for signal extraction
- Automatic knowledge harvesting

This is the main entry point for master chat functionality.

Usage:
    from symbolu_core.service.master_chat.integration import MasterChatService

    service = MasterChatService()

    # Chat with automatic context retrieval and harvesting
    response = await service.chat(
        user_id="user123",
        message="How is my project going?",
        tier="power_user",
    )

Version: 1.0
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional

from ..chat_service import (
    ChatService,
    ChatMessage,
    ChatResponse,
    ChatStreamChunk,
    get_chat_service,
)
from .bucket_models import MessageSignals
from .master_session import (
    MasterSessionStore,
    TurnContext,
    get_master_session_store,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class MasterChatConfig:
    """Configuration for master chat integration."""
    # Context injection
    inject_context: bool = True
    max_context_tokens: int = 2000

    # Harvesting
    enable_harvesting: bool = True
    harvest_async: bool = True  # Non-blocking harvesting

    # Signal extraction
    extract_signals: bool = True
    default_domain: str = "general"

    # Embedding
    use_embeddings: bool = True
    embedding_model: str = "all-MiniLM-L6-v2"


DEFAULT_CONFIG = MasterChatConfig()


# =============================================================================
# Master Chat Response
# =============================================================================

@dataclass
class MasterChatResponse:
    """
    Extended response with master chat context.

    Includes the original ChatResponse plus bucket context info.
    """
    # Original response fields
    content: str
    model: str
    provider: str
    tier: str
    usage: Dict[str, int] = field(default_factory=dict)
    semantic_analysis: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Master chat additions
    user_id: str = ""
    turn_id: str = ""
    context_used: bool = False
    buckets_activated: int = 0
    activated_bucket_names: List[str] = field(default_factory=list)
    facts_harvested: int = 0
    signals: Optional[MessageSignals] = None

    @classmethod
    def from_chat_response(
        cls,
        response: ChatResponse,
        user_id: str,
        turn_context: Optional[TurnContext] = None,
        facts_harvested: int = 0,
    ) -> "MasterChatResponse":
        """Create from a ChatResponse."""
        return cls(
            content=response.content,
            model=response.model,
            provider=response.provider,
            tier=response.tier,
            usage=response.usage,
            semantic_analysis=response.semantic_analysis,
            metadata=response.metadata,
            user_id=user_id,
            turn_id=turn_context.turn_id if turn_context else "",
            context_used=turn_context.has_context() if turn_context else False,
            buckets_activated=len(turn_context.activated_buckets) if turn_context else 0,
            activated_bucket_names=[
                ab.bucket.display_name
                for ab in (turn_context.activated_buckets if turn_context else [])
            ],
            facts_harvested=facts_harvested,
            signals=turn_context.signals if turn_context else None,
        )


# =============================================================================
# Signal Extractor
# =============================================================================

class SignalExtractor:
    """
    Extracts ontological signals from text using the MLCR pipeline.

    This bridges the existing Symbol-U pipeline with the master chat system.
    """

    def __init__(self, default_domain: str = "general"):
        self.default_domain = default_domain
        self._pipeline = None

    def _get_pipeline(self):
        """Lazy load the pipeline."""
        if self._pipeline is None:
            try:
                from symbolu_core.mechanical.pipeline.orchestrator import SymbolUPipeline
                self._pipeline = SymbolUPipeline()
            except ImportError:
                logger.warning("SymbolUPipeline not available")
                return None
        return self._pipeline

    def extract(
        self,
        text: str,
        domain: Optional[str] = None,
    ) -> MessageSignals:
        """
        Extract ontological signals from text.

        Args:
            text: Text to analyze
            domain: Domain context

        Returns:
            MessageSignals with extracted values
        """
        pipeline = self._get_pipeline()

        if pipeline is None:
            # Return default signals if pipeline unavailable
            return MessageSignals()

        try:
            from symbolu_core.mechanical.pipeline.models import UserRequest

            request = UserRequest(
                text=text,
                metadata={"domain": domain or self.default_domain}
            )

            result = pipeline.run(request)
            ctx = result.meta.get("context")

            if not ctx:
                return MessageSignals()

            # Extract signals from pipeline context
            signals = MessageSignals()

            # Extract ontology layer activations
            if hasattr(ctx, "mlcr_result") and ctx.mlcr_result:
                mlcr = ctx.mlcr_result
                signals.lower_mass = mlcr.get("ontology_mass", {}).get("lower", 0.5)
                signals.upper_mass = mlcr.get("ontology_mass", {}).get("upper", 0.5)

                # Map tier to layer activations
                tier = mlcr.get("tier", "hybrid")
                if tier == "lower":
                    signals.ontology_layers = {1: 0.3, 2: 0.3, 3: 0.8, 4: 0.5, 5: 0.3}
                elif tier == "upper":
                    signals.ontology_layers = {6: 0.5, 7: 0.6, 8: 0.7, 9: 0.5, 10: 0.4}
                else:
                    signals.ontology_layers = {4: 0.5, 5: 0.6, 6: 0.5, 7: 0.4}

                # Extract entropy
                entropy = mlcr.get("entropy", {})
                signals.entropy_H_D = entropy.get("H_D", 0.5)
                signals.entropy_H_G = entropy.get("H_G", 0.5)
                signals.entropy_H_K = entropy.get("H_K", 0.5)
                signals.normalized_entropy = (
                    signals.entropy_H_D + signals.entropy_H_G + signals.entropy_H_K
                ) / 3

            # Extract kosha from coherence if available
            if hasattr(ctx, "coherence") and ctx.coherence:
                coh = ctx.coherence
                # Map coherence metrics to kosha approximation
                stability = coh.get("stability", 0.5)
                signals.kosha_activations = {
                    "annamaya": 0.3,
                    "pranamaya": 0.4,
                    "manomaya": stability,
                    "vijnanamaya": 0.5,
                    "anandamaya": 0.3,
                }
                signals.kosha_resonance = stability

            # Extract guna from semantic analysis
            if hasattr(ctx, "dilchat_payload") and ctx.dilchat_payload:
                payload = ctx.dilchat_payload
                # Approximate guna from badges/hints
                badges = payload.get("badges", [])
                if "clarity" in str(badges).lower():
                    signals.guna_distribution = {"sattva": 0.6, "rajas": 0.25, "tamas": 0.15}
                elif "action" in str(badges).lower():
                    signals.guna_distribution = {"sattva": 0.25, "rajas": 0.6, "tamas": 0.15}
                else:
                    signals.guna_distribution = {"sattva": 0.4, "rajas": 0.35, "tamas": 0.25}

            return signals

        except Exception as e:
            logger.warning(f"Signal extraction failed: {e}")
            return MessageSignals()


# =============================================================================
# Master Chat Service
# =============================================================================

class MasterChatService:
    """
    Unified chat service with master session context.

    Combines:
    - LLM chat (via ChatService)
    - Bucket-based context retrieval
    - Automatic signal extraction
    - Knowledge harvesting

    This is the recommended interface for master chat functionality.
    """

    def __init__(
        self,
        config: Optional[MasterChatConfig] = None,
        chat_service: Optional[ChatService] = None,
        session_store: Optional[MasterSessionStore] = None,
        embedding_provider: Optional[callable] = None,
    ):
        """
        Initialize the master chat service.

        Args:
            config: Service configuration
            chat_service: Existing ChatService (creates new if None)
            session_store: Existing MasterSessionStore (creates new if None)
            embedding_provider: Function to compute embeddings
        """
        self.config = config or DEFAULT_CONFIG

        # Initialize components
        self.chat_service = chat_service or get_chat_service(
            enable_semantic_analysis=True
        )

        # Set up embedding provider
        if embedding_provider is None and self.config.use_embeddings:
            embedding_provider = self._create_default_embedding_provider()

        self.session_store = session_store or get_master_session_store(
            embedding_provider=embedding_provider
        )

        self.signal_extractor = SignalExtractor(
            default_domain=self.config.default_domain
        )

        logger.info("MasterChatService initialized")

    def _create_default_embedding_provider(self) -> Optional[callable]:
        """Create default embedding provider using sentence-transformers."""
        try:
            from .embeddings import get_embedding_provider
            return get_embedding_provider(self.config.embedding_model)
        except ImportError:
            logger.warning(
                "sentence-transformers not available, embeddings disabled"
            )
            return None

    async def chat(
        self,
        user_id: str,
        message: str,
        tier: str = "power_user",
        history: Optional[List[ChatMessage]] = None,
        system_prompt: Optional[str] = None,
        provider: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        domain: Optional[str] = None,
        include_context: Optional[bool] = None,
    ) -> MasterChatResponse:
        """
        Send a chat message with automatic context retrieval and harvesting.

        Args:
            user_id: User identifier for session lookup
            message: User's message
            tier: Presentation tier
            history: Previous chat messages
            system_prompt: Custom system prompt (context will be appended)
            provider: LLM provider override
            max_tokens: Maximum tokens
            temperature: Sampling temperature
            domain: Domain for signal extraction
            include_context: Override for context injection

        Returns:
            MasterChatResponse with content and context metadata
        """
        domain = domain or self.config.default_domain
        include_ctx = include_context if include_context is not None else self.config.inject_context

        # Step 1: Extract signals from message
        signals = None
        if self.config.extract_signals:
            signals = self.signal_extractor.extract(message, domain)

        # Step 2: Get context from buckets
        turn_context = None
        context_prompt_addition = ""

        if include_ctx:
            turn_context = self.session_store.get_context(
                user_id=user_id,
                message=message,
                signals=signals,
            )

            if turn_context.has_context():
                context_prompt_addition = self.session_store.assembler.assemble_for_system_prompt(
                    turn_context.activated_buckets
                )

        # Step 3: Build enhanced system prompt
        base_prompt = system_prompt or ""
        if context_prompt_addition:
            enhanced_prompt = base_prompt + context_prompt_addition if base_prompt else None
            # If no base prompt, just use the context addition in metadata
            if not base_prompt:
                enhanced_prompt = context_prompt_addition
        else:
            enhanced_prompt = system_prompt

        # Step 4: Call LLM
        response = await self.chat_service.chat(
            message=message,
            tier=tier,
            history=history,
            system_prompt=enhanced_prompt,
            provider=provider,
            max_tokens=max_tokens,
            temperature=temperature,
            domain=domain,
        )

        # Step 5: Harvest knowledge (async if configured)
        facts_harvested = 0
        if self.config.enable_harvesting:
            if self.config.harvest_async:
                # Non-blocking harvest
                asyncio.create_task(
                    self._harvest_turn(
                        user_id=user_id,
                        user_message=message,
                        assistant_response=response.content,
                        signals=signals,
                        turn_id=turn_context.turn_id if turn_context else None,
                    )
                )
            else:
                # Blocking harvest
                facts_harvested = await self._harvest_turn(
                    user_id=user_id,
                    user_message=message,
                    assistant_response=response.content,
                    signals=signals,
                    turn_id=turn_context.turn_id if turn_context else None,
                )

        # Build response
        return MasterChatResponse.from_chat_response(
            response=response,
            user_id=user_id,
            turn_context=turn_context,
            facts_harvested=facts_harvested,
        )

    async def stream_chat(
        self,
        user_id: str,
        message: str,
        tier: str = "power_user",
        history: Optional[List[ChatMessage]] = None,
        system_prompt: Optional[str] = None,
        provider: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        domain: Optional[str] = None,
    ) -> AsyncIterator[ChatStreamChunk]:
        """
        Stream a chat response with context.

        Note: Harvesting happens after streaming completes.

        Args:
            user_id: User identifier
            message: User's message
            tier: Presentation tier
            history: Previous messages
            system_prompt: Custom system prompt
            provider: LLM provider
            max_tokens: Maximum tokens
            temperature: Sampling temperature
            domain: Domain context

        Yields:
            ChatStreamChunk objects
        """
        domain = domain or self.config.default_domain

        # Extract signals
        signals = None
        if self.config.extract_signals:
            signals = self.signal_extractor.extract(message, domain)

        # Get context
        turn_context = None
        context_prompt_addition = ""

        if self.config.inject_context:
            turn_context = self.session_store.get_context(
                user_id=user_id,
                message=message,
                signals=signals,
            )

            if turn_context.has_context():
                context_prompt_addition = self.session_store.assembler.assemble_for_system_prompt(
                    turn_context.activated_buckets
                )

        # Build enhanced prompt
        enhanced_prompt = system_prompt
        if context_prompt_addition:
            enhanced_prompt = (system_prompt or "") + context_prompt_addition

        # Collect full response for harvesting
        full_response = []

        # Stream response
        async for chunk in self.chat_service.stream_chat(
            message=message,
            tier=tier,
            history=history,
            system_prompt=enhanced_prompt,
            provider=provider,
            max_tokens=max_tokens,
            temperature=temperature,
        ):
            full_response.append(chunk.content)
            yield chunk

        # Harvest after streaming completes
        if self.config.enable_harvesting:
            response_text = "".join(full_response)
            asyncio.create_task(
                self._harvest_turn(
                    user_id=user_id,
                    user_message=message,
                    assistant_response=response_text,
                    signals=signals,
                    turn_id=turn_context.turn_id if turn_context else None,
                )
            )

    async def _harvest_turn(
        self,
        user_id: str,
        user_message: str,
        assistant_response: str,
        signals: Optional[MessageSignals],
        turn_id: Optional[str],
    ) -> int:
        """Internal helper for harvesting."""
        try:
            return await self.session_store.harvest_turn(
                user_id=user_id,
                user_message=user_message,
                assistant_response=assistant_response,
                signals=signals,
                turn_id=turn_id,
            )
        except Exception as e:
            logger.error(f"Harvesting failed: {e}")
            return 0

    # -------------------------------------------------------------------------
    # Session Management Shortcuts
    # -------------------------------------------------------------------------

    def get_session_stats(self, user_id: str) -> Dict[str, Any]:
        """Get session statistics for a user."""
        return self.session_store.get_stats(user_id)

    def search_knowledge(
        self,
        user_id: str,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search user's knowledge buckets."""
        entries = self.session_store.search_buckets(
            user_id=user_id,
            query=query,
            limit=limit,
        )
        return [e.to_dict() for e in entries]

    def get_bucket_summary(self, user_id: str) -> Dict[str, Dict[str, Any]]:
        """Get summary of user's buckets."""
        session = self.session_store.get(user_id)
        if not session:
            return {}
        return session.get_bucket_summary()


# =============================================================================
# Singleton Access
# =============================================================================

_master_chat_service: Optional[MasterChatService] = None


def get_master_chat_service(
    config: Optional[MasterChatConfig] = None,
) -> MasterChatService:
    """Get or create the global master chat service."""
    global _master_chat_service

    if _master_chat_service is None:
        _master_chat_service = MasterChatService(config=config)

    return _master_chat_service


# =============================================================================
# Convenience Functions
# =============================================================================

async def master_chat(
    user_id: str,
    message: str,
    tier: str = "power_user",
) -> str:
    """
    Quick master chat function.

    Args:
        user_id: User identifier
        message: User's message
        tier: Presentation tier

    Returns:
        Response text
    """
    service = get_master_chat_service()
    response = await service.chat(user_id=user_id, message=message, tier=tier)
    return response.content


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "MasterChatConfig",
    "MasterChatResponse",
    "MasterChatService",
    "SignalExtractor",
    "get_master_chat_service",
    "master_chat",
]
