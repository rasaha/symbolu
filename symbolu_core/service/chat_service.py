"""
Symbol-U Chat Service

Provides chat functionality with tier-based LLM model selection.
Integrates LLM responses with Symbol-U semantic analysis.

Tiers:
    - Explorer (consumer): Fast responses with Haiku/Flash
    - Analyst (power_user): Balanced with Sonnet/Pro + semantic insights
    - Developer (admin): Full analytics with Sonnet/Pro + diagnostics

Example usage:
    from symbolu_core.service.chat_service import ChatService

    service = ChatService()

    # Simple chat
    response = await service.chat(
        message="What is quantum entanglement?",
        tier="power_user",
    )
    print(response.content)

    # Streaming chat
    async for chunk in service.stream_chat(
        message="Explain machine learning",
        tier="admin",
    ):
        print(chunk.content, end="")
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, AsyncIterator
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================================================
# TYPES
# ============================================================================

class ChatTier(Enum):
    """Chat tier levels."""
    EXPLORER = "consumer"      # RAG Lookup - fast, simple
    ANALYST = "power_user"     # Enterprise Chat - balanced
    DEVELOPER = "admin"        # Customer Chat - full features


@dataclass
class ChatMessage:
    """A message in the chat history."""
    role: str  # "user", "assistant", "system"
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatResponse:
    """Response from chat service."""
    content: str
    model: str
    provider: str
    tier: str
    usage: Dict[str, int] = field(default_factory=dict)
    semantic_analysis: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatStreamChunk:
    """A chunk from streaming chat response."""
    content: str
    is_final: bool = False
    model: Optional[str] = None
    provider: Optional[str] = None
    usage: Optional[Dict[str, int]] = None


# ============================================================================
# SYSTEM PROMPTS
# ============================================================================

SYSTEM_PROMPTS = {
    "consumer": """You are Symbol-U Explorer, a helpful AI assistant for knowledge lookup.
Be concise and informative. Focus on providing accurate, clear answers.
When uncertain, acknowledge it and suggest related topics to explore.""",

    "power_user": """You are Symbol-U Analyst, an enterprise AI assistant for internal teams.
Provide detailed, well-structured responses with clear reasoning.
Include relevant context and connections between concepts.
Balance depth with clarity for business and technical audiences.""",

    "admin": """You are Symbol-U Developer, a comprehensive AI assistant for customer support.
Provide thorough, well-organized responses with actionable insights.
Consider multiple perspectives and potential follow-up questions.
Include technical details when relevant while remaining accessible.
Help users understand the 'why' behind information, not just the 'what'.""",
}


# ============================================================================
# CHAT SERVICE
# ============================================================================

class ChatService:
    """
    Chat service with tier-based LLM selection and optional semantic analysis.

    Integrates:
    - LLM providers (Anthropic Claude, Google Gemini)
    - Tier-based model selection
    - Optional Symbol-U semantic analysis
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        enable_semantic_analysis: bool = False,
    ):
        """
        Initialize the chat service.

        Args:
            provider: Default LLM provider ("anthropic" or "google")
            enable_semantic_analysis: Enable Symbol-U semantic analysis
        """
        self.default_provider = provider
        self.enable_semantic_analysis = enable_semantic_analysis
        self._llm_client = None

    def _get_llm_client(self):
        """Lazy load the LLM client."""
        if self._llm_client is None:
            from agentic.llm.providers import LLMClient
            self._llm_client = LLMClient(provider=self.default_provider)
        return self._llm_client

    def _get_system_prompt(self, tier: str, custom_prompt: Optional[str] = None) -> str:
        """Get system prompt for tier."""
        if custom_prompt:
            return custom_prompt
        return SYSTEM_PROMPTS.get(tier, SYSTEM_PROMPTS["power_user"])

    async def _run_semantic_analysis(
        self,
        text: str,
        domain: str = "general",
    ) -> Optional[Dict[str, Any]]:
        """Run Symbol-U semantic analysis on text."""
        if not self.enable_semantic_analysis:
            return None

        try:
            from symbolu_core.mechanical.pipeline.orchestrator import SymbolUPipeline
            from symbolu_core.mechanical.pipeline.models import UserRequest

            pipeline = SymbolUPipeline()
            user_request = UserRequest(
                text=text,
                metadata={"domain": domain}
            )

            result = pipeline.run(user_request)
            ctx = result.meta.get("context")

            if ctx and ctx.dilchat_payload:
                return {
                    "badges": ctx.dilchat_payload.get("badges", []),
                    "coherence": ctx.dilchat_payload.get("coherence", {}),
                    "hints": ctx.dilchat_payload.get("hints", []),
                    "domain": ctx.dilchat_payload.get("domain", domain),
                }
        except Exception as e:
            logger.warning(f"Semantic analysis failed: {e}")

        return None

    async def chat(
        self,
        message: str,
        tier: str = "power_user",
        history: Optional[List[ChatMessage]] = None,
        system_prompt: Optional[str] = None,
        provider: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        domain: str = "general",
    ) -> ChatResponse:
        """
        Send a chat message and get a response.

        Args:
            message: User message
            tier: Presentation tier ("consumer", "power_user", "admin")
            history: Previous chat messages
            system_prompt: Custom system prompt (overrides tier default)
            provider: LLM provider override
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            domain: Domain for semantic analysis

        Returns:
            ChatResponse with content and metadata
        """
        from agentic.llm.providers import LLMMessage

        client = self._get_llm_client()

        # Build messages
        messages = []

        # Add history if provided
        if history:
            for msg in history:
                messages.append(LLMMessage(role=msg.role, content=msg.content))

        # Add current message
        messages.append(LLMMessage(role="user", content=message))

        # Get system prompt
        sys_prompt = self._get_system_prompt(tier, system_prompt)

        # Generate response
        response = await client.generate(
            messages=messages,
            presentation_tier=tier,
            provider=provider or self.default_provider,
            max_tokens=max_tokens,
            temperature=temperature,
            system_prompt=sys_prompt,
        )

        # Run semantic analysis if enabled
        semantic = await self._run_semantic_analysis(response.content, domain)

        return ChatResponse(
            content=response.content,
            model=response.model,
            provider=response.provider,
            tier=tier,
            usage=response.usage,
            semantic_analysis=semantic,
            metadata=response.metadata,
        )

    async def stream_chat(
        self,
        message: str,
        tier: str = "power_user",
        history: Optional[List[ChatMessage]] = None,
        system_prompt: Optional[str] = None,
        provider: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncIterator[ChatStreamChunk]:
        """
        Stream a chat response.

        Args:
            message: User message
            tier: Presentation tier
            history: Previous chat messages
            system_prompt: Custom system prompt
            provider: LLM provider override
            max_tokens: Maximum tokens
            temperature: Sampling temperature

        Yields:
            ChatStreamChunk objects
        """
        from agentic.llm.providers import LLMMessage

        client = self._get_llm_client()

        # Build messages
        messages = []

        if history:
            for msg in history:
                messages.append(LLMMessage(role=msg.role, content=msg.content))

        messages.append(LLMMessage(role="user", content=message))

        # Get system prompt
        sys_prompt = self._get_system_prompt(tier, system_prompt)

        # Stream response
        async for chunk in client.stream(
            messages=messages,
            presentation_tier=tier,
            provider=provider or self.default_provider,
            max_tokens=max_tokens,
            temperature=temperature,
            system_prompt=sys_prompt,
        ):
            yield ChatStreamChunk(
                content=chunk.content,
                is_final=chunk.is_final,
                model=chunk.metadata.get("model") if chunk.is_final else None,
                provider=chunk.metadata.get("provider") if chunk.is_final else None,
                usage=chunk.metadata.get("usage") if chunk.is_final else None,
            )


# ============================================================================
# SINGLETON
# ============================================================================

_default_service: Optional[ChatService] = None


def get_chat_service(
    provider: Optional[str] = None,
    enable_semantic_analysis: bool = False,
) -> ChatService:
    """Get or create the default chat service."""
    global _default_service
    if _default_service is None:
        _default_service = ChatService(
            provider=provider,
            enable_semantic_analysis=enable_semantic_analysis,
        )
    return _default_service


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

async def chat(
    message: str,
    tier: str = "power_user",
    provider: Optional[str] = None,
) -> str:
    """
    Quick chat function for simple use cases.

    Args:
        message: User message
        tier: Presentation tier
        provider: Optional provider override

    Returns:
        Response text
    """
    service = get_chat_service()
    response = await service.chat(message=message, tier=tier, provider=provider)
    return response.content
