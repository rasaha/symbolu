"""
Symbol-U LLM Providers

Unified interface for LLM providers with tier-based model selection.

Supported Providers:
    - Anthropic (Claude 3.5 Haiku, Claude 3.5 Sonnet)
    - Google (Gemini 1.5 Flash, Gemini 1.5 Pro)

Tier Model Mapping:
    - Explorer (consumer): Fast, cheap models (Haiku/Flash)
    - Analyst (power_user): Balanced models (Sonnet/Pro)
    - Developer (admin): Best reasoning models (Sonnet/Pro)

Environment Variables:
    - ANTHROPIC_API_KEY: Anthropic API key
    - GOOGLE_API_KEY: Google AI API key
    - LLM_PROVIDER: Default provider ("anthropic" or "google")
"""

import os
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, AsyncIterator
from enum import Enum

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMS & TYPES
# ============================================================================

class LLMProvider(Enum):
    """Supported LLM providers."""
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class ModelTier(Enum):
    """Model tier for cost/quality tradeoff."""
    FAST = "fast"      # Haiku, Flash - cheap & fast
    BALANCED = "balanced"  # Sonnet, Pro - good balance
    BEST = "best"      # Same as balanced for now


# Tier to model mapping
ANTHROPIC_MODELS = {
    ModelTier.FAST: "claude-3-5-haiku-20241022",
    ModelTier.BALANCED: "claude-3-5-sonnet-20241022",
    ModelTier.BEST: "claude-3-5-sonnet-20241022",
}

GOOGLE_MODELS = {
    ModelTier.FAST: "gemini-1.5-flash",
    ModelTier.BALANCED: "gemini-1.5-pro",
    ModelTier.BEST: "gemini-1.5-pro",
}

# Presentation tier to model tier mapping
PRESENTATION_TIER_MAP = {
    "consumer": ModelTier.FAST,      # Explorer - RAG Lookup
    "power_user": ModelTier.BALANCED,  # Analyst - Enterprise Chat
    "admin": ModelTier.BALANCED,     # Developer - Customer Chat
}


@dataclass
class LLMMessage:
    """A message in a conversation."""
    role: str  # "user", "assistant", "system"
    content: str


@dataclass
class LLMResponse:
    """Response from LLM provider."""
    content: str
    model: str
    provider: str
    usage: Dict[str, int] = field(default_factory=dict)
    stop_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StreamChunk:
    """A chunk from streaming response."""
    content: str
    is_final: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# BASE PROVIDER INTERFACE
# ============================================================================

class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def generate(
        self,
        messages: List[LLMMessage],
        model_tier: ModelTier = ModelTier.BALANCED,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """Generate a response from the LLM."""
        pass

    @abstractmethod
    async def stream(
        self,
        messages: List[LLMMessage],
        model_tier: ModelTier = ModelTier.BALANCED,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a response from the LLM."""
        pass

    @abstractmethod
    def get_model_name(self, tier: ModelTier) -> str:
        """Get the model name for a given tier."""
        pass


# ============================================================================
# ANTHROPIC PROVIDER
# ============================================================================

class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key not provided. "
                "Set ANTHROPIC_API_KEY environment variable."
            )
        self._client = None

    def _get_client(self):
        """Lazy load the Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.AsyncAnthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "anthropic package not installed. "
                    "Install with: pip install anthropic"
                )
        return self._client

    def get_model_name(self, tier: ModelTier) -> str:
        return ANTHROPIC_MODELS.get(tier, ANTHROPIC_MODELS[ModelTier.BALANCED])

    async def generate(
        self,
        messages: List[LLMMessage],
        model_tier: ModelTier = ModelTier.BALANCED,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """Generate a response using Claude."""
        client = self._get_client()
        model = self.get_model_name(model_tier)

        # Convert messages to Anthropic format
        anthropic_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
            if msg.role != "system"
        ]

        # Build request kwargs
        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": anthropic_messages,
        }

        # Add system prompt if provided
        if system_prompt:
            kwargs["system"] = system_prompt
        elif any(msg.role == "system" for msg in messages):
            # Extract system message
            system_msg = next(msg for msg in messages if msg.role == "system")
            kwargs["system"] = system_msg.content

        try:
            response = await client.messages.create(**kwargs)

            return LLMResponse(
                content=response.content[0].text,
                model=model,
                provider="anthropic",
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
                stop_reason=response.stop_reason,
            )
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise

    async def stream(
        self,
        messages: List[LLMMessage],
        model_tier: ModelTier = ModelTier.BALANCED,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a response using Claude."""
        client = self._get_client()
        model = self.get_model_name(model_tier)

        # Convert messages to Anthropic format
        anthropic_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
            if msg.role != "system"
        ]

        # Build request kwargs
        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": anthropic_messages,
        }

        # Add system prompt if provided
        if system_prompt:
            kwargs["system"] = system_prompt
        elif any(msg.role == "system" for msg in messages):
            system_msg = next(msg for msg in messages if msg.role == "system")
            kwargs["system"] = system_msg.content

        try:
            async with client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield StreamChunk(content=text, is_final=False)

                # Final chunk with metadata
                final_message = await stream.get_final_message()
                yield StreamChunk(
                    content="",
                    is_final=True,
                    metadata={
                        "model": model,
                        "usage": {
                            "input_tokens": final_message.usage.input_tokens,
                            "output_tokens": final_message.usage.output_tokens,
                        },
                        "stop_reason": final_message.stop_reason,
                    }
                )
        except Exception as e:
            logger.error(f"Anthropic streaming error: {e}")
            raise


# ============================================================================
# GOOGLE GEMINI PROVIDER
# ============================================================================

class GoogleProvider(BaseLLMProvider):
    """Google Gemini provider."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Google API key not provided. "
                "Set GOOGLE_API_KEY environment variable."
            )
        self._client = None

    def _get_client(self, model: str):
        """Get or create Gemini model client."""
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            return genai.GenerativeModel(model)
        except ImportError:
            raise ImportError(
                "google-generativeai package not installed. "
                "Install with: pip install google-generativeai"
            )

    def get_model_name(self, tier: ModelTier) -> str:
        return GOOGLE_MODELS.get(tier, GOOGLE_MODELS[ModelTier.BALANCED])

    async def generate(
        self,
        messages: List[LLMMessage],
        model_tier: ModelTier = ModelTier.BALANCED,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """Generate a response using Gemini."""
        import asyncio

        model_name = self.get_model_name(model_tier)

        # Build system instruction
        system_instruction = system_prompt
        if not system_instruction:
            system_msgs = [msg for msg in messages if msg.role == "system"]
            if system_msgs:
                system_instruction = system_msgs[0].content

        # Create model with system instruction
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)

            model = genai.GenerativeModel(
                model_name,
                system_instruction=system_instruction,
                generation_config={
                    "max_output_tokens": max_tokens,
                    "temperature": temperature,
                }
            )
        except ImportError:
            raise ImportError(
                "google-generativeai package not installed. "
                "Install with: pip install google-generativeai"
            )

        # Convert messages to Gemini format (history + current)
        history = []
        current_content = None

        for msg in messages:
            if msg.role == "system":
                continue
            elif msg.role == "user":
                if current_content:
                    history.append({"role": "user", "parts": [current_content]})
                current_content = msg.content
            elif msg.role == "assistant":
                if current_content:
                    history.append({"role": "user", "parts": [current_content]})
                    current_content = None
                history.append({"role": "model", "parts": [msg.content]})

        try:
            # Start chat with history
            chat = model.start_chat(history=history)

            # Send current message (run in thread pool for async)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: chat.send_message(current_content or messages[-1].content)
            )

            # Extract usage if available
            usage = {}
            if hasattr(response, 'usage_metadata'):
                usage = {
                    "input_tokens": getattr(response.usage_metadata, 'prompt_token_count', 0),
                    "output_tokens": getattr(response.usage_metadata, 'candidates_token_count', 0),
                }

            return LLMResponse(
                content=response.text,
                model=model_name,
                provider="google",
                usage=usage,
                stop_reason="stop",
            )
        except Exception as e:
            logger.error(f"Google API error: {e}")
            raise

    async def stream(
        self,
        messages: List[LLMMessage],
        model_tier: ModelTier = ModelTier.BALANCED,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a response using Gemini."""
        import asyncio

        model_name = self.get_model_name(model_tier)

        # Build system instruction
        system_instruction = system_prompt
        if not system_instruction:
            system_msgs = [msg for msg in messages if msg.role == "system"]
            if system_msgs:
                system_instruction = system_msgs[0].content

        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)

            model = genai.GenerativeModel(
                model_name,
                system_instruction=system_instruction,
                generation_config={
                    "max_output_tokens": max_tokens,
                    "temperature": temperature,
                }
            )
        except ImportError:
            raise ImportError(
                "google-generativeai package not installed. "
                "Install with: pip install google-generativeai"
            )

        # Convert messages to Gemini format
        history = []
        current_content = None

        for msg in messages:
            if msg.role == "system":
                continue
            elif msg.role == "user":
                if current_content:
                    history.append({"role": "user", "parts": [current_content]})
                current_content = msg.content
            elif msg.role == "assistant":
                if current_content:
                    history.append({"role": "user", "parts": [current_content]})
                    current_content = None
                history.append({"role": "model", "parts": [msg.content]})

        try:
            chat = model.start_chat(history=history)

            # Stream response
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: chat.send_message(
                    current_content or messages[-1].content,
                    stream=True
                )
            )

            for chunk in response:
                if chunk.text:
                    yield StreamChunk(content=chunk.text, is_final=False)

            # Final chunk
            yield StreamChunk(
                content="",
                is_final=True,
                metadata={
                    "model": model_name,
                    "stop_reason": "stop",
                }
            )
        except Exception as e:
            logger.error(f"Google streaming error: {e}")
            raise


# ============================================================================
# UNIFIED CLIENT
# ============================================================================

class LLMClient:
    """
    Unified LLM client with tier-based model selection.

    Example usage:
        client = LLMClient()

        # Generate response
        response = await client.generate(
            messages=[LLMMessage(role="user", content="Hello!")],
            presentation_tier="consumer",  # Uses fast model
        )

        # Stream response
        async for chunk in client.stream(
            messages=[LLMMessage(role="user", content="Hello!")],
            presentation_tier="admin",  # Uses balanced model
        ):
            print(chunk.content, end="")
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        google_api_key: Optional[str] = None,
    ):
        """
        Initialize the LLM client.

        Args:
            provider: Default provider ("anthropic" or "google")
            anthropic_api_key: Anthropic API key (or use ANTHROPIC_API_KEY env)
            google_api_key: Google API key (or use GOOGLE_API_KEY env)
        """
        self.default_provider = provider or os.getenv("LLM_PROVIDER", "anthropic")

        self._providers: Dict[str, BaseLLMProvider] = {}

        # Initialize available providers
        if anthropic_api_key or os.getenv("ANTHROPIC_API_KEY"):
            try:
                self._providers["anthropic"] = AnthropicProvider(anthropic_api_key)
            except (ValueError, ImportError) as e:
                logger.warning(f"Anthropic provider not available: {e}")

        if google_api_key or os.getenv("GOOGLE_API_KEY"):
            try:
                self._providers["google"] = GoogleProvider(google_api_key)
            except (ValueError, ImportError) as e:
                logger.warning(f"Google provider not available: {e}")

        if not self._providers:
            raise ValueError(
                "No LLM providers available. Set ANTHROPIC_API_KEY or GOOGLE_API_KEY."
            )

    def _get_provider(self, provider: Optional[str] = None) -> BaseLLMProvider:
        """Get the requested provider or default."""
        provider_name = provider or self.default_provider

        if provider_name not in self._providers:
            # Fall back to any available provider
            if self._providers:
                provider_name = next(iter(self._providers))
                logger.warning(f"Requested provider not available, using {provider_name}")
            else:
                raise ValueError("No LLM providers available")

        return self._providers[provider_name]

    def _get_model_tier(self, presentation_tier: Optional[str] = None) -> ModelTier:
        """Convert presentation tier to model tier."""
        if presentation_tier:
            return PRESENTATION_TIER_MAP.get(presentation_tier, ModelTier.BALANCED)
        return ModelTier.BALANCED

    async def generate(
        self,
        messages: List[LLMMessage],
        presentation_tier: Optional[str] = None,
        model_tier: Optional[ModelTier] = None,
        provider: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        """
        Generate a response from the LLM.

        Args:
            messages: List of conversation messages
            presentation_tier: "consumer", "power_user", or "admin"
            model_tier: Override model tier directly
            provider: Override default provider
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            system_prompt: System prompt to use

        Returns:
            LLMResponse with generated content
        """
        llm_provider = self._get_provider(provider)
        tier = model_tier or self._get_model_tier(presentation_tier)

        return await llm_provider.generate(
            messages=messages,
            model_tier=tier,
            max_tokens=max_tokens,
            temperature=temperature,
            system_prompt=system_prompt,
        )

    async def stream(
        self,
        messages: List[LLMMessage],
        presentation_tier: Optional[str] = None,
        model_tier: Optional[ModelTier] = None,
        provider: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream a response from the LLM.

        Args:
            messages: List of conversation messages
            presentation_tier: "consumer", "power_user", or "admin"
            model_tier: Override model tier directly
            provider: Override default provider
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            system_prompt: System prompt to use

        Yields:
            StreamChunk objects with content
        """
        llm_provider = self._get_provider(provider)
        tier = model_tier or self._get_model_tier(presentation_tier)

        async for chunk in llm_provider.stream(
            messages=messages,
            model_tier=tier,
            max_tokens=max_tokens,
            temperature=temperature,
            system_prompt=system_prompt,
        ):
            yield chunk

    @property
    def available_providers(self) -> List[str]:
        """List of available providers."""
        return list(self._providers.keys())


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

_default_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get or create the default LLM client singleton."""
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client


async def generate(
    text: str,
    presentation_tier: str = "power_user",
    system_prompt: Optional[str] = None,
    provider: Optional[str] = None,
) -> str:
    """
    Quick generate function for simple use cases.

    Args:
        text: User message
        presentation_tier: "consumer", "power_user", or "admin"
        system_prompt: Optional system prompt
        provider: Optional provider override

    Returns:
        Generated text response
    """
    client = get_llm_client()
    messages = [LLMMessage(role="user", content=text)]

    response = await client.generate(
        messages=messages,
        presentation_tier=presentation_tier,
        system_prompt=system_prompt,
        provider=provider,
    )

    return response.content
