from dataclasses import dataclass
from typing import Any, Tuple, Optional

try:
    # Adjust these imports if your actual module paths differ.
    from mechanical.pipeline.orchestrator import SymbolUPipeline
except ImportError:  # pragma: no cover
    SymbolUPipeline = None  # type: ignore

try:
    from mechanical.pipeline.models import (
        UserRequest,
        RenderedOutput,
        PipelineContext,
    )
except ImportError:  # pragma: no cover
    @dataclass
    class UserRequest:  # type: ignore
        text: str

    @dataclass
    class RenderedOutput:  # type: ignore
        text: str

    @dataclass
    class PipelineContext:  # type: ignore
        persona: Any = None
        mlcr: Any = None
        fusion: Any = None
        dha: Any = None
        renderer: Any = None


class MockLLMRenderer:
    """
    Deterministic mock renderer used for integration tests.
    Ensures no external LLM calls are made.
    """

    def __init__(self, prefix: str = "MOCK_LLM: ") -> None:
        self.prefix = prefix
        self.calls = []  # type: list[dict[str, Any]]

    def render(self, *args: Any, **kwargs: Any) -> str:
        self.calls.append({"args": args, "kwargs": kwargs})
        prompt = kwargs.get("prompt")

        if prompt is None and args:
            prompt = args[0]
        if prompt is None:
            prompt = "LLM output"

        return f"{self.prefix}{str(prompt)}"

    def __call__(self, *args: Any, **kwargs: Any) -> str:
        return self.render(*args, **kwargs)


def build_test_request(text: str) -> UserRequest:
    """
    Construct a minimal UserRequest for integration tests.
    """
    return UserRequest(text=text)  # type: ignore[arg-type]


def _ensure_pipeline_available() -> None:
    """
    Fail early if pipeline imports are misconfigured.
    """
    if SymbolUPipeline is None:  # pragma: no cover
        raise RuntimeError(
            "SymbolUPipeline could not be imported. "
            "Fix imports in utils.py to match repository structure."
        )


def run_pipeline_and_capture_context(
    text: str,
    routing_mode: str = "auto",
    render_mode: str = "minimal",
    llm_renderer: Optional[Any] = None,
) -> Tuple[RenderedOutput, PipelineContext, Any]:
    """
    Run the Symbol-U pipeline end-to-end and return:

        rendered_output, pipeline_context, pipeline_instance
    """
    _ensure_pipeline_available()

    if llm_renderer is None:
        llm_renderer = MockLLMRenderer()

    pipeline = SymbolUPipeline(
        render_mode=render_mode,
        routing_mode=routing_mode,
        llm_renderer=llm_renderer,  # type: ignore[arg-type]
    )

    request = build_test_request(text)
    result = pipeline.run(request)  # type: ignore[call-arg]

    if isinstance(result, tuple) and len(result) == 2:
        rendered, ctx = result  # type: ignore[misc]
    else:
        rendered = result
        ctx = getattr(pipeline, "last_context", None)

    if ctx is None:
        raise AssertionError(
            "PipelineContext was not provided by the pipeline. "
            "Ensure pipeline.run returns (RenderedOutput, PipelineContext) "
            "or sets pipeline.last_context."
        )

    if not isinstance(rendered, RenderedOutput):
        raise AssertionError(
            f"Expected RenderedOutput, got {type(rendered).__name__}"
        )
    if not isinstance(ctx, PipelineContext):
        raise AssertionError(
            f"Expected PipelineContext, got {type(ctx).__name__}"
        )

    return rendered, ctx, pipeline
