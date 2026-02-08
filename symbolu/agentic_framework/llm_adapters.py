"""
LLM Adapters

Adapter classes for various LLM providers.
Each adapter implements the LLMClient protocol (call method).

Supported providers:
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- Google (Gemini)
- Mock (for testing)

Usage:
    from symbolu.agentic_framework.llm_adapters import OpenAIAdapter

    llm = OpenAIAdapter(api_key="...")
    response = llm.call("Hello!")
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class BaseLLMAdapter(ABC):
    """
    Base class for LLM adapters.

    All adapters must implement the call() method.
    """

    @abstractmethod
    def call(self, prompt: str) -> str:
        """
        Call LLM with prompt and return response.

        Args:
            prompt: Input prompt string

        Returns:
            Response string from LLM
        """
        pass

    def call_with_messages(
        self,
        messages: List[Dict[str, str]],
    ) -> str:
        """
        Call LLM with message history.

        Default implementation converts to single prompt.
        Override for proper chat handling.
        """
        # Convert messages to single prompt
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            prompt_parts.append(f"{role}: {content}")
        prompt = "\n".join(prompt_parts)
        return self.call(prompt)


class OpenAIAdapter(BaseLLMAdapter):
    """
    Adapter for OpenAI API (GPT-4, GPT-3.5, etc.).

    Requires: openai package

    Usage:
        from openai import OpenAI

        adapter = OpenAIAdapter(api_key="sk-...")
        response = adapter.call("Hello!")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ):
        """
        Initialize OpenAI adapter.

        Args:
            api_key: OpenAI API key (uses OPENAI_API_KEY env var if not provided)
            model: Model name (default: gpt-4)
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            **kwargs: Additional parameters for API calls
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.kwargs = kwargs

        # Import and initialize client
        try:
            from openai import OpenAI  # type: ignore

            self.client = OpenAI(api_key=api_key)
        except ImportError:
            raise ImportError(
                "openai package required. Install with: pip install openai"
            )

    def call(self, prompt: str) -> str:
        """Call OpenAI API with prompt."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            **self.kwargs,
        )
        return response.choices[0].message.content or ""

    def call_with_messages(
        self,
        messages: List[Dict[str, str]],
    ) -> str:
        """Call OpenAI API with message history."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            **self.kwargs,
        )
        return response.choices[0].message.content or ""


class AnthropicAdapter(BaseLLMAdapter):
    """
    Adapter for Anthropic API (Claude).

    Requires: anthropic package

    Usage:
        adapter = AnthropicAdapter(api_key="sk-ant-...")
        response = adapter.call("Hello!")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 1024,
        **kwargs: Any,
    ):
        """
        Initialize Anthropic adapter.

        Args:
            api_key: Anthropic API key (uses ANTHROPIC_API_KEY env var if not provided)
            model: Model name (default: claude-sonnet-4-20250514)
            max_tokens: Maximum tokens in response
            **kwargs: Additional parameters for API calls
        """
        self.model = model
        self.max_tokens = max_tokens
        self.kwargs = kwargs

        # Import and initialize client
        try:
            from anthropic import Anthropic  # type: ignore

            self.client = Anthropic(api_key=api_key)
        except ImportError:
            raise ImportError(
                "anthropic package required. Install with: pip install anthropic"
            )

    def call(self, prompt: str) -> str:
        """Call Anthropic API with prompt."""
        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
            **self.kwargs,
        )
        # Handle content blocks
        content = message.content
        if isinstance(content, list) and len(content) > 0:
            first_block = content[0]
            if hasattr(first_block, "text"):
                return first_block.text
        return str(content)

    def call_with_messages(
        self,
        messages: List[Dict[str, str]],
    ) -> str:
        """Call Anthropic API with message history."""
        message = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=messages,  # type: ignore
            **self.kwargs,
        )
        content = message.content
        if isinstance(content, list) and len(content) > 0:
            first_block = content[0]
            if hasattr(first_block, "text"):
                return first_block.text
        return str(content)


class GeminiAdapter(BaseLLMAdapter):
    """
    Adapter for Google Gemini API.

    Requires: google-generativeai package

    Usage:
        adapter = GeminiAdapter(api_key="...")
        response = adapter.call("Hello!")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-pro",
        **kwargs: Any,
    ):
        """
        Initialize Gemini adapter.

        Args:
            api_key: Google API key (uses GOOGLE_API_KEY env var if not provided)
            model: Model name (default: gemini-pro)
            **kwargs: Additional parameters for API calls
        """
        self.model_name = model
        self.kwargs = kwargs

        # Import and initialize
        try:
            import google.generativeai as genai  # type: ignore

            if api_key:
                genai.configure(api_key=api_key)

            self.model = genai.GenerativeModel(model)
        except ImportError:
            raise ImportError(
                "google-generativeai package required. Install with: pip install google-generativeai"
            )

    def call(self, prompt: str) -> str:
        """Call Gemini API with prompt."""
        response = self.model.generate_content(prompt)
        return response.text


class MockLLMAdapter(BaseLLMAdapter):
    """
    Mock LLM adapter for testing.

    Returns predefined responses or echoes input.

    Usage:
        adapter = MockLLMAdapter(responses={"hello": "Hi there!"})
        response = adapter.call("hello")  # Returns "Hi there!"
    """

    def __init__(
        self,
        responses: Optional[Dict[str, str]] = None,
        default_response: str = "Mock response",
        echo: bool = False,
    ):
        """
        Initialize mock adapter.

        Args:
            responses: Dict mapping inputs to outputs
            default_response: Response when input not in responses
            echo: If True, echo input back
        """
        self.responses = responses or {}
        self.default_response = default_response
        self.echo = echo
        self.call_history: List[str] = []

    def call(self, prompt: str) -> str:
        """Return mock response."""
        self.call_history.append(prompt)

        if self.echo:
            return f"Echo: {prompt}"

        # Check for matching response
        prompt_lower = prompt.lower()
        for key, value in self.responses.items():
            if key.lower() in prompt_lower:
                return value

        return self.default_response

    def reset_history(self) -> None:
        """Reset call history."""
        self.call_history = []


class SequentialMockAdapter(BaseLLMAdapter):
    """
    Mock adapter that returns responses in sequence.

    Useful for testing multi-turn conversations.

    Usage:
        adapter = SequentialMockAdapter([
            "First response",
            "Second response",
            "Third response",
        ])
    """

    def __init__(
        self,
        responses: List[str],
        loop: bool = False,
    ):
        """
        Initialize sequential mock adapter.

        Args:
            responses: List of responses to return in order
            loop: If True, loop back to start when exhausted
        """
        self.responses = responses
        self.loop = loop
        self.index = 0
        self.call_history: List[str] = []

    def call(self, prompt: str) -> str:
        """Return next response in sequence."""
        self.call_history.append(prompt)

        if not self.responses:
            return "No responses configured"

        response = self.responses[self.index]

        self.index += 1
        if self.index >= len(self.responses):
            if self.loop:
                self.index = 0
            else:
                self.index = len(self.responses) - 1

        return response

    def reset(self) -> None:
        """Reset to first response."""
        self.index = 0
        self.call_history = []


# --- Embedding Adapters ---


class BaseEmbeddingAdapter(ABC):
    """Base class for embedding adapters."""

    @abstractmethod
    def embed(self, text: str) -> List[float]:
        """Generate embedding for text."""
        pass


class OpenAIEmbeddingAdapter(BaseEmbeddingAdapter):
    """
    Adapter for OpenAI embeddings.

    Usage:
        embedder = OpenAIEmbeddingAdapter(api_key="...")
        vector = embedder.embed("Hello world")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "text-embedding-ada-002",
    ):
        """
        Initialize OpenAI embedding adapter.

        Args:
            api_key: OpenAI API key
            model: Embedding model name
        """
        self.model = model

        try:
            from openai import OpenAI  # type: ignore

            self.client = OpenAI(api_key=api_key)
        except ImportError:
            raise ImportError(
                "openai package required. Install with: pip install openai"
            )

    def embed(self, text: str) -> List[float]:
        """Generate embedding using OpenAI."""
        response = self.client.embeddings.create(
            model=self.model,
            input=text,
        )
        return response.data[0].embedding


class MockEmbeddingAdapter(BaseEmbeddingAdapter):
    """
    Mock embedding adapter for testing.

    Returns simple hash-based "embeddings".
    """

    def __init__(self, dimension: int = 128):
        """
        Initialize mock embedding adapter.

        Args:
            dimension: Embedding dimension
        """
        self.dimension = dimension

    def embed(self, text: str) -> List[float]:
        """Generate mock embedding based on text hash."""
        # Simple deterministic "embedding" based on text
        import hashlib

        hash_bytes = hashlib.sha256(text.encode()).digest()
        # Convert to floats
        embedding = []
        for i in range(self.dimension):
            byte_idx = i % len(hash_bytes)
            value = (hash_bytes[byte_idx] / 255.0) * 2 - 1  # Normalize to [-1, 1]
            embedding.append(value)
        return embedding


# --- Factory Functions ---


def create_adapter(
    provider: str,
    api_key: Optional[str] = None,
    **kwargs: Any,
) -> BaseLLMAdapter:
    """
    Create LLM adapter for specified provider.

    Args:
        provider: Provider name ("openai", "anthropic", "gemini", "mock")
        api_key: API key for provider
        **kwargs: Additional parameters for adapter

    Returns:
        LLM adapter instance
    """
    provider_lower = provider.lower()

    if provider_lower == "openai":
        return OpenAIAdapter(api_key=api_key, **kwargs)
    elif provider_lower in ("anthropic", "claude"):
        return AnthropicAdapter(api_key=api_key, **kwargs)
    elif provider_lower in ("gemini", "google"):
        return GeminiAdapter(api_key=api_key, **kwargs)
    elif provider_lower == "mock":
        return MockLLMAdapter(**kwargs)
    else:
        raise ValueError(f"Unknown provider: {provider}")
