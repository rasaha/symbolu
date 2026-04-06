"""
LLM Adapters

Adapter classes for various LLM providers.
Each adapter implements the LLMClient protocol (call method).

Supported providers:
- OpenAI (GPT-4, GPT-3.5)
- Anthropic (Claude)
- Google (Gemini)
- Mistral (mistral-large, mistral-medium via API)
- MistralCG (local Mistral + Conscious Generation)
- Mock (for testing)

Usage:
    from agentic.agentic_framework.llm_adapters import OpenAIAdapter

    llm = OpenAIAdapter(api_key="...")
    response = llm.call("Hello!")
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional


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

    def call_stream(self, prompt: str) -> Iterator[str]:
        """
        Stream text chunks from the LLM.

        Default implementation calls ``call()`` and yields the full
        response as a single chunk.  Subclasses with native streaming
        support may override to yield incremental tokens.
        """
        yield self.call(prompt)

    async def call_stream_async(self, prompt: str) -> AsyncIterator[str]:
        """
        Async streaming variant.

        Default wraps the sync ``call_stream()`` via
        ``asyncio.to_thread`` for each chunk.  Subclasses with native
        async streaming (e.g. ``openai.AsyncOpenAI``) may override.
        """
        import asyncio

        # Run sync call in a thread to avoid blocking the event loop.
        result = await asyncio.to_thread(self.call, prompt)
        yield result

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


class MistralAdapter(BaseLLMAdapter):
    """
    Adapter for Mistral API (mistral-large, mistral-medium, etc.).

    Requires: mistralai package

    Usage:
        adapter = MistralAdapter(api_key="...")
        response = adapter.call("Hello!")
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "mistral-large-latest",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: Any,
    ):
        """
        Initialize Mistral adapter.

        Args:
            api_key: Mistral API key (uses MISTRAL_API_KEY env var if not provided)
            model: Model name (default: mistral-large-latest)
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            **kwargs: Additional parameters for API calls
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.kwargs = kwargs

        try:
            from mistralai import Mistral  # type: ignore

            self.client = Mistral(api_key=api_key)
        except ImportError:
            raise ImportError(
                "mistralai package required. Install with: pip install mistralai"
            )

    def call(self, prompt: str) -> str:
        """Call Mistral API with prompt."""
        response = self.client.chat.complete(
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
        """Call Mistral API with message history."""
        response = self.client.chat.complete(
            model=self.model,
            messages=messages,  # type: ignore
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            **self.kwargs,
        )
        return response.choices[0].message.content or ""


class MistralCGAdapter(BaseLLMAdapter):
    """
    Adapter for local MistralCGWrapper (Conscious Generation) model.

    Bridges the PyTorch nn.Module (tensor in/out) to the BaseLLMAdapter
    interface (string in/out) so MistralCGWrapper can serve as the llm_client
    for AgenticLLMWrapper.

    After each call(), CG metadata (state, delta_S, delta_bhava, intent_phase)
    is stored in self.last_cg_metadata and can be fed to the Sovereign Bridge
    for ConfidenceGate / SafetyContract integration.

    Requires: torch, transformers (+ optional bitsandbytes for quantized models)

    Usage:
        from agentic.agentic_framework.llm_adapters import MistralCGAdapter

        adapter = MistralCGAdapter(model_name="mistralai/Mistral-7B-v0.3")
        response = adapter.call("What is consciousness?")

        # Access CG metadata for sovereign bridge
        from agentic.agentic_framework.sovereign_bridge import (
            signals_from_sovereign_state,
        )
        signals = signals_from_sovereign_state(
            adapter.last_cg_metadata['state'],
            adapter.last_cg_metadata['delta_S'],
        )
    """

    def __init__(
        self,
        model_name: str = "mistralai/Mistral-7B-v0.3",
        quantize: Optional[str] = None,
        max_new_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        top_k: int = 50,
        repetition_penalty: float = 1.1,
        device_map: str = "auto",
        trust_remote_code: bool = False,
        pretrained_model: Optional[Any] = None,
        pretrained_tokenizer: Optional[Any] = None,
        **kwargs: Any,
    ):
        """
        Initialize MistralCG adapter.

        Args:
            model_name: HuggingFace model identifier
            quantize: Quantization mode (None, "4bit", "8bit")
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0 = greedy)
            top_p: Nucleus sampling threshold
            top_k: Top-k sampling
            repetition_penalty: Penalty for repeated tokens
            device_map: Device placement strategy
            trust_remote_code: Trust remote code in model hub
            pretrained_model: Pre-loaded nn.Module (skips loading)
            pretrained_tokenizer: Pre-loaded tokenizer (skips loading)
            **kwargs: Additional kwargs for MistralCGWrapper
        """
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.top_k = top_k
        self.repetition_penalty = repetition_penalty

        # CG metadata from most recent call — consumed by sovereign_bridge
        self.last_cg_metadata: Dict[str, Any] = {}
        self.call_history: List[str] = []

        # Import and build model
        try:
            import torch  # noqa: F811

            self._torch = torch
        except ImportError:
            raise ImportError("torch required. Install with: pip install torch")

        try:
            try:
                from symbolu_training.training.unified.mistral_wrapper import (
                    MistralCGWrapper,
                )
            except ImportError:
                from symbolu_training.training.unified.mistral_wrapper import (
                    MistralCGWrapper,
                )

            self.model = MistralCGWrapper(
                model_name=model_name,
                quantize=quantize,
                device_map=device_map,
                trust_remote_code=trust_remote_code,
                pretrained_model=pretrained_model,
                pretrained_tokenizer=pretrained_tokenizer,
                **kwargs,
            )
            self.model.eval()
            self.tokenizer = self.model.tokenizer
        except ImportError:
            raise ImportError(
                "symbolu.training.unified.mistral_wrapper required. "
                "Ensure the symbolu package is installed."
            )

        if self.tokenizer is None:
            raise ValueError(
                "Tokenizer not available. Provide pretrained_tokenizer or "
                "ensure model_name can be loaded from HuggingFace."
            )

        # Ensure pad token is set
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

    def call(self, prompt: str) -> str:
        """
        Generate text from prompt using MistralCGWrapper.

        Tokenizes input, runs autoregressive generation through the CG model,
        decodes output, and stores CG metadata for sovereign bridge consumption.
        """
        self.call_history.append(prompt)
        torch = self._torch

        # Tokenize
        inputs = self.tokenizer(
            prompt,
            return_tensors="pt",
            padding=True,
            truncation=True,
        )
        device = next(self.model.parameters()).device
        input_ids = inputs["input_ids"].to(device)
        attention_mask = inputs.get("attention_mask")
        if attention_mask is not None:
            attention_mask = attention_mask.to(device)

        # Run a single forward pass to capture CG metadata
        with torch.no_grad():
            cg_outputs = self.model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                reset_state=True,
            )

        # Store CG metadata for sovereign bridge
        self.last_cg_metadata = {
            'state': cg_outputs.get('state'),
            'delta_S': cg_outputs.get('delta_S'),
            'delta_bhava': cg_outputs.get('delta_bhava'),
            'intent_phase': cg_outputs.get('intent_phase'),
            'adapter_gate': cg_outputs.get('adapter_gate'),
        }

        # Autoregressive generation
        generated_ids = input_ids.clone()
        past_mask = attention_mask

        for _ in range(self.max_new_tokens):
            with torch.no_grad():
                outputs = self.model(
                    input_ids=generated_ids,
                    attention_mask=past_mask,
                )
            logits = outputs['logits']  # [B, T, V]
            next_token_logits = logits[:, -1, :]  # [B, V]

            # Apply repetition penalty
            if self.repetition_penalty != 1.0:
                for token_id in set(generated_ids[0].tolist()):
                    if next_token_logits[0, token_id] > 0:
                        next_token_logits[0, token_id] /= self.repetition_penalty
                    else:
                        next_token_logits[0, token_id] *= self.repetition_penalty

            # Apply temperature
            if self.temperature > 0:
                next_token_logits = next_token_logits / self.temperature

                # Top-k filtering
                if self.top_k > 0:
                    top_k_vals, _ = torch.topk(next_token_logits, self.top_k)
                    min_top_k = top_k_vals[:, -1].unsqueeze(-1)
                    next_token_logits = torch.where(
                        next_token_logits < min_top_k,
                        torch.full_like(next_token_logits, float('-inf')),
                        next_token_logits,
                    )

                # Top-p (nucleus) filtering
                if self.top_p < 1.0:
                    sorted_logits, sorted_indices = torch.sort(
                        next_token_logits, descending=True
                    )
                    cumulative_probs = torch.cumsum(
                        torch.softmax(sorted_logits, dim=-1), dim=-1
                    )
                    sorted_mask = cumulative_probs - torch.softmax(
                        sorted_logits, dim=-1
                    ) >= self.top_p
                    sorted_logits[sorted_mask] = float('-inf')
                    # Unsort
                    next_token_logits = sorted_logits.scatter(
                        1, sorted_indices, sorted_logits
                    )

                probs = torch.softmax(next_token_logits, dim=-1)
                next_token = torch.multinomial(probs, num_samples=1)
            else:
                # Greedy decoding
                next_token = next_token_logits.argmax(dim=-1, keepdim=True)

            # Check for EOS
            if next_token.item() == self.tokenizer.eos_token_id:
                break

            generated_ids = torch.cat([generated_ids, next_token], dim=-1)
            if past_mask is not None:
                past_mask = torch.cat(
                    [past_mask, torch.ones(1, 1, device=device, dtype=past_mask.dtype)],
                    dim=-1,
                )

        # Decode only the new tokens
        new_token_ids = generated_ids[0, input_ids.shape[1]:]
        response = self.tokenizer.decode(new_token_ids, skip_special_tokens=True)
        return response.strip()

    def get_cg_metadata(self) -> Dict[str, Any]:
        """Return CG metadata from the most recent call."""
        return self.last_cg_metadata


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


class StubCGLLMAdapter(MockLLMAdapter):
    """
    === DEV / TEST ONLY — lightweight CG-capable adapter ===

    Drop-in for ``MistralCGAdapter`` that satisfies the same wire
    contract (``last_cg_metadata`` dict with ``state``/``delta_S``/
    ``delta_bhava``/``intent_phase``) WITHOUT loading torch,
    transformers, or any model checkpoint.

    **Intended use:** integration tests, developer loops, and early
    wiring validation of the MCP/tool-use runtime path (see
    ``docs/RUNTIME_MCP_PATH.md``). Not intended for production
    inference — the 32D sovereign state is a **deterministic
    hand-picked fixture** (sattva-leaning, vritti-region dominant),
    not a live inference signal.

    **Provenance markers:**

    - ``IS_STUB = True`` lets runtime assemblers detect the stub
      and warn / refuse / log when they see it in a non-test context.
    - ``STATE_PROVENANCE = "stub-fixture-deterministic"`` is the
      canonical provenance tag for the state vector.

    The ``build_cg_mcp_agent`` factory in ``cg_tool_dispatcher.py``
    checks ``IS_STUB`` and emits a warning if a stub adapter is
    wired into a runtime agent without ``allow_stub=True``. That is
    the substitution seam: swap in a ``MistralCGAdapter`` (or any
    other adapter whose ``IS_STUB`` is absent/False) to move from
    the stub path to a real-inference path without changing any
    surrounding wiring.

    Wire contract preserved exactly: ``last_cg_metadata`` is
    refreshed on every ``call(prompt)``, so the request-boundary
    enrichment seam (``request_enrichment.py``) still produces
    real — not fabricated — ``entropy_result``/``vritti_result``
    on the next ``CGToolDispatcher.dispatch`` call. The signals
    *derived* from the fixture are honest (they really come from a
    live adapter.last_cg_metadata); only the *fixture itself* is
    synthetic.

    Usage (test/dev):
        from agentic.agentic_framework.llm_adapters import StubCGLLMAdapter
        from agentic.agentic_framework.cg_tool_dispatcher import (
            build_cg_mcp_agent,
        )

        adapter = StubCGLLMAdapter(default_response="OK")
        agent = build_cg_mcp_agent(adapter=adapter, allow_stub=True)
        result = agent.run("please handle my request")
    """

    #: Explicit marker: this adapter is a synthetic stub and its
    #: ``last_cg_metadata`` is NOT derived from a real inference
    #: step. Runtime assemblers MUST check this before wiring the
    #: adapter into production.
    IS_STUB: bool = True

    #: Provenance tag for the 32D state fixture. Any audit consumer
    #: wanting to distinguish stub-sourced signals from real
    #: inference can read this off the adapter.
    STATE_PROVENANCE: str = "deterministic_stub"

    # Hand-picked fixture: vritti-region dominance + sattva-leaning guna.
    # Kept as a class constant so tests can assert against it.
    _STATE_FIXTURE: List[float] = (
        [0.0] * 17
        + [0.55, 0.15, 0.15, 0.10, 0.05]  # vritti region (indices 17-21)
        + [0.65, 0.25]                     # sattva/rajas (indices 22-23)
        + [0.0] * 3
        + [0.9]                            # index 27
        + [0.0] * 4
    )

    def call(self, prompt: str) -> str:
        """Call mock LLM and refresh ``last_cg_metadata`` with the
        deterministic stub fixture. Marked DEV/TEST ONLY at the
        class level — see class docstring."""
        response = super().call(prompt)
        self.last_cg_metadata: Dict[str, Any] = {
            "state": list(self._STATE_FIXTURE),
            "delta_S": [0.01] * 32,
            "delta_bhava": None,
            "intent_phase": None,
        }
        return response


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
    elif provider_lower == "mistral":
        return MistralAdapter(api_key=api_key, **kwargs)
    elif provider_lower in ("mistral_cg", "mistralcg"):
        return MistralCGAdapter(**kwargs)
    elif provider_lower == "mock":
        return MockLLMAdapter(**kwargs)
    else:
        raise ValueError(f"Unknown provider: {provider}")
