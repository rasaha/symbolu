"""
LLM Renderer for Output Presentation

This module provides LLM-based rendering of Symbolu outputs.

IMPORTANT: LLM is used ONLY for rendering/presentation, NOT for:
- Intent parsing (keyword-based)
- Constraint generation (mechanical)
- Inference (deterministic)

The LLM takes mechanical results and presents them in natural language.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple, Callable
from enum import Enum


class LLMProvider(Enum):
    """Supported LLM providers for rendering."""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    LOCAL = "local"  # For local models or mock
    NONE = "none"    # No LLM - return raw output


@dataclass
class RenderContext:
    """Context for rendering output."""
    sequences: Tuple[Tuple[str, ...], ...]
    trajectories: Optional[List[Any]] = None
    semantic_vector: Optional[Dict[str, float]] = None
    user_intent: Optional[str] = None
    conversation_history: Optional[List[Dict[str, str]]] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class RenderedOutput:
    """LLM-rendered output."""
    text: str                          # Natural language presentation
    sequences: Tuple[Tuple[str, ...], ...]  # Original sequences (unchanged)
    raw_available: bool = True         # Can access raw data
    llm_used: bool = False             # Whether LLM was used
    provider: LLMProvider = LLMProvider.NONE


class LLMRendererInterface(ABC):
    """Abstract interface for LLM renderers."""

    @abstractmethod
    def render(self, context: RenderContext) -> RenderedOutput:
        """Render mechanical output to natural language."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this renderer is available."""
        pass


class NoLLMRenderer(LLMRendererInterface):
    """
    Fallback renderer when no LLM is available.
    Returns structured but non-conversational output.
    """

    def render(self, context: RenderContext) -> RenderedOutput:
        """Render without LLM - simple formatted output."""
        lines = []

        if context.user_intent:
            lines.append(f"Request: {context.user_intent}")

        lines.append(f"Generated {len(context.sequences)} sequences:")

        for i, seq in enumerate(context.sequences[:10], 1):  # Limit display
            seq_str = " → ".join(seq)
            lines.append(f"  {i}. {seq_str}")

        if len(context.sequences) > 10:
            lines.append(f"  ... and {len(context.sequences) - 10} more")

        if context.semantic_vector:
            non_zero = {k: v for k, v in context.semantic_vector.items() if abs(v) > 0.1}
            if non_zero:
                lines.append(f"Semantic profile: {non_zero}")

        return RenderedOutput(
            text="\n".join(lines),
            sequences=context.sequences,
            raw_available=True,
            llm_used=False,
            provider=LLMProvider.NONE,
        )

    def is_available(self) -> bool:
        return True  # Always available


class TemplateRenderer(LLMRendererInterface):
    """
    Template-based renderer - no LLM, but more natural than raw output.
    Uses predefined templates based on semantic dimensions.
    """

    TEMPLATES = {
        # Energy templates
        ("energy", "low"): [
            "Here's a gentle, settling pattern: {sequences}",
            "A calm sequence for you: {sequences}",
            "Something soft and peaceful: {sequences}",
        ],
        ("energy", "high"): [
            "Here's an energetic sequence: {sequences}",
            "A vibrant, dynamic pattern: {sequences}",
            "Something with energy: {sequences}",
        ],
        # Duration templates
        ("duration", "short"): [
            "A brief sequence: {sequences}",
            "Short and concise: {sequences}",
        ],
        ("duration", "long"): [
            "An extended sequence: {sequences}",
            "A longer pattern: {sequences}",
        ],
        # Direction templates
        ("direction", "rising"): [
            "A rising, building pattern: {sequences}",
            "An ascending sequence: {sequences}",
        ],
        ("direction", "falling"): [
            "A settling, descending pattern: {sequences}",
            "A sequence that winds down: {sequences}",
        ],
        # Default
        ("default", "default"): [
            "Generated sequences: {sequences}",
            "Here are the results: {sequences}",
        ],
    }

    def render(self, context: RenderContext) -> RenderedOutput:
        """Render using templates based on semantic context."""
        import random

        # Determine which template category to use
        template_key = ("default", "default")

        if context.semantic_vector:
            sv = context.semantic_vector

            # Find strongest dimension
            dimensions = [
                ("energy", sv.get("energy", 0)),
                ("duration", sv.get("duration", 0)),
                ("direction", sv.get("direction", 0)),
            ]

            strongest = max(dimensions, key=lambda x: abs(x[1]))
            dim_name, dim_value = strongest

            if abs(dim_value) > 0.3:
                pole = "high" if dim_value > 0 else "low"
                if dim_name == "direction":
                    pole = "rising" if dim_value > 0 else "falling"
                template_key = (dim_name, pole)

        # Select template
        templates = self.TEMPLATES.get(template_key, self.TEMPLATES[("default", "default")])
        template = random.choice(templates)  # Add some variety

        # Format sequences
        seq_strs = [" → ".join(seq) for seq in context.sequences[:5]]
        sequences_text = "\n  • " + "\n  • ".join(seq_strs)
        if len(context.sequences) > 5:
            sequences_text += f"\n  ... and {len(context.sequences) - 5} more"

        text = template.format(sequences=sequences_text)

        return RenderedOutput(
            text=text,
            sequences=context.sequences,
            raw_available=True,
            llm_used=False,
            provider=LLMProvider.LOCAL,
        )

    def is_available(self) -> bool:
        return True


class AnthropicRenderer(LLMRendererInterface):
    """
    Anthropic Claude-based renderer.

    Requires: anthropic package and ANTHROPIC_API_KEY
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-haiku-20240307",  # Fast, cheap model for rendering
    ):
        self.api_key = api_key
        self.model = model
        self._client = None

    def _get_client(self):
        """Lazy initialization of Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                import os
                api_key = self.api_key or os.environ.get("ANTHROPIC_API_KEY")
                if api_key:
                    self._client = anthropic.Anthropic(api_key=api_key)
            except ImportError:
                pass
        return self._client

    def render(self, context: RenderContext) -> RenderedOutput:
        """Render using Claude API."""
        client = self._get_client()

        if not client:
            # Fallback to template renderer
            return TemplateRenderer().render(context)

        # Build prompt for rendering
        prompt = self._build_render_prompt(context)

        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )

            text = response.content[0].text

            return RenderedOutput(
                text=text,
                sequences=context.sequences,
                raw_available=True,
                llm_used=True,
                provider=LLMProvider.ANTHROPIC,
            )

        except Exception as e:
            # Fallback on error
            fallback = TemplateRenderer().render(context)
            fallback.text = f"[Rendering fallback] {fallback.text}"
            return fallback

    def _build_render_prompt(self, context: RenderContext) -> str:
        """Build prompt for LLM rendering."""
        parts = [
            "You are presenting generated varna sequences to a user.",
            "Present the results in a natural, conversational way.",
            "Do NOT explain what varnas are or how they work.",
            "Keep the response concise (2-3 sentences max).",
            "",
        ]

        if context.user_intent:
            parts.append(f"User requested: {context.user_intent}")

        # Format sequences
        seq_strs = ["-".join(seq) for seq in context.sequences[:5]]
        parts.append(f"Generated sequences: {', '.join(seq_strs)}")

        if context.semantic_vector:
            # Describe semantic profile
            sv = context.semantic_vector
            descriptors = []
            if sv.get("energy", 0) < -0.3:
                descriptors.append("calm")
            elif sv.get("energy", 0) > 0.3:
                descriptors.append("energetic")
            if sv.get("direction", 0) < -0.3:
                descriptors.append("settling")
            elif sv.get("direction", 0) > 0.3:
                descriptors.append("rising")

            if descriptors:
                parts.append(f"Semantic qualities: {', '.join(descriptors)}")

        parts.append("")
        parts.append("Present these results naturally:")

        return "\n".join(parts)

    def is_available(self) -> bool:
        """Check if Anthropic API is available."""
        return self._get_client() is not None


class OpenAIRenderer(LLMRendererInterface):
    """
    OpenAI GPT-based renderer.

    Requires: openai package and OPENAI_API_KEY
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-3.5-turbo",
    ):
        self.api_key = api_key
        self.model = model
        self._client = None

    def _get_client(self):
        """Lazy initialization of OpenAI client."""
        if self._client is None:
            try:
                import openai
                import os
                api_key = self.api_key or os.environ.get("OPENAI_API_KEY")
                if api_key:
                    self._client = openai.OpenAI(api_key=api_key)
            except ImportError:
                pass
        return self._client

    def render(self, context: RenderContext) -> RenderedOutput:
        """Render using OpenAI API."""
        client = self._get_client()

        if not client:
            return TemplateRenderer().render(context)

        prompt = self._build_render_prompt(context)

        try:
            response = client.chat.completions.create(
                model=self.model,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )

            text = response.choices[0].message.content

            return RenderedOutput(
                text=text,
                sequences=context.sequences,
                raw_available=True,
                llm_used=True,
                provider=LLMProvider.OPENAI,
            )

        except Exception:
            return TemplateRenderer().render(context)

    def _build_render_prompt(self, context: RenderContext) -> str:
        """Build prompt - same logic as Anthropic."""
        return AnthropicRenderer()._build_render_prompt(context)

    def is_available(self) -> bool:
        return self._get_client() is not None


class OutputRenderer:
    """
    Main renderer that selects appropriate backend.

    Tries renderers in order of preference, falls back as needed.
    """

    def __init__(
        self,
        preferred_provider: LLMProvider = LLMProvider.NONE,
        anthropic_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
    ):
        self.preferred_provider = preferred_provider

        # Initialize renderers
        self.renderers: Dict[LLMProvider, LLMRendererInterface] = {
            LLMProvider.NONE: NoLLMRenderer(),
            LLMProvider.LOCAL: TemplateRenderer(),
            LLMProvider.ANTHROPIC: AnthropicRenderer(api_key=anthropic_api_key),
            LLMProvider.OPENAI: OpenAIRenderer(api_key=openai_api_key),
        }

    def render(
        self,
        sequences: Tuple[Tuple[str, ...], ...],
        trajectories: Optional[List[Any]] = None,
        semantic_vector: Optional[Dict[str, float]] = None,
        user_intent: Optional[str] = None,
        **kwargs
    ) -> RenderedOutput:
        """
        Render sequences to natural language.

        Args:
            sequences: Generated sequences
            trajectories: Optional trajectory data
            semantic_vector: Optional semantic profile
            user_intent: Original user request
            **kwargs: Additional context

        Returns:
            RenderedOutput with natural language presentation
        """
        context = RenderContext(
            sequences=sequences,
            trajectories=trajectories,
            semantic_vector=semantic_vector,
            user_intent=user_intent,
            metadata=kwargs,
        )

        # Try preferred provider first
        renderer = self.renderers.get(self.preferred_provider)
        if renderer and renderer.is_available():
            return renderer.render(context)

        # Fallback chain: Anthropic → OpenAI → Template → None
        fallback_order = [
            LLMProvider.ANTHROPIC,
            LLMProvider.OPENAI,
            LLMProvider.LOCAL,
            LLMProvider.NONE,
        ]

        for provider in fallback_order:
            if provider == self.preferred_provider:
                continue  # Already tried
            renderer = self.renderers.get(provider)
            if renderer and renderer.is_available():
                return renderer.render(context)

        # Should never reach here, but safety fallback
        return NoLLMRenderer().render(context)

    def get_available_providers(self) -> List[LLMProvider]:
        """List available rendering providers."""
        return [
            provider for provider, renderer in self.renderers.items()
            if renderer.is_available()
        ]


# Convenience function
def render_output(
    sequences: Tuple[Tuple[str, ...], ...],
    user_intent: Optional[str] = None,
    use_llm: bool = False,
    **kwargs
) -> str:
    """
    Simple function to render sequences to text.

    Args:
        sequences: Generated sequences
        user_intent: Original request
        use_llm: Whether to try LLM rendering
        **kwargs: Additional context

    Returns:
        Rendered text string
    """
    provider = LLMProvider.ANTHROPIC if use_llm else LLMProvider.LOCAL
    renderer = OutputRenderer(preferred_provider=provider)

    result = renderer.render(
        sequences=sequences,
        user_intent=user_intent,
        **kwargs
    )

    return result.text
