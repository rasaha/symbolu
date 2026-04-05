#!/usr/bin/env python3
"""
Mistral Inference for AgenticLLMWrapper

Runnable entry point that wires the Mistral API adapter into
AgenticLLMWrapper and exercises the full agentic pipeline:

  Goal Decomposition -> Memory -> Reflective Generation ->
  Coherence Tracking -> Safety Contract -> Action Execution

Usage:
    # Interactive mode (default)
    python -m symbolu.agentic_framework.inference_mistral

    # Single query
    python -m symbolu.agentic_framework.inference_mistral --query "What is quantum computing?"

    # Multi-turn demo
    python -m symbolu.agentic_framework.inference_mistral --demo

    # Custom model
    python -m symbolu.agentic_framework.inference_mistral --model mistral-medium-latest

    # Verbose (show all pipeline metrics)
    python -m symbolu.agentic_framework.inference_mistral --verbose

    # Opt-in CG-capable runtime (local MistralCGWrapper + MCP governance)
    python -m symbolu.agentic_framework.inference_mistral --cg \\
        --cg-model mistralai/Mistral-7B-v0.3 --query "..."

Environment:
    MISTRAL_API_KEY  - Required for the default (API) path.
    SYMBOLU_RUN_CG_SMOKE - When set to "1", opt-in CG smoke test is enabled
                           (see tests/test_inference_mistral_cg_smoke.py).
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any, Dict, Optional


def _print_header(text: str) -> None:
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def _print_result(result, verbose: bool = False) -> None:
    """Print an AgentResult with optional verbose pipeline metrics."""
    print(f"\n  Response: {result.response}")
    print(f"  Quality:  {result.quality_score:.3f}  "
          f"(revisions: {result.revision_count})")
    print(f"  Coherence: overall={result.coherence.get('overall', 0):.3f}  "
          f"drift={result.coherence.get('drift_direction', 'n/a')}")

    if verbose:
        print(f"\n  --- Pipeline Details ---")
        print(f"  Session:    {result.session_id}")
        print(f"  Turn:       {result.turn_id}")
        print(f"  Coherence:  {result.coherence}")
        print(f"  Blocked:    {result.actions_blocked}")
        if result.blocking_reasons:
            print(f"  Reasons:    {result.blocking_reasons}")
        print(f"  Actions:    {result.actions_executed}")
        print(f"  Intervene:  {result.intervention_needed}")
        if result.intervention_reason:
            print(f"  Why:        {result.intervention_reason}")

        contract = result.safety_contract
        if contract:
            print(f"  Contract:   eligible={contract.eligible}")
            if contract.satisfied_preconditions:
                print(f"    satisfied: {contract.satisfied_preconditions}")
            if contract.violated_preconditions:
                print(f"    violated:  {contract.violated_preconditions}")


def create_agent(
    model: str = "mistral-large-latest",
    api_key: Optional[str] = None,
    max_revisions: int = 2,
    quality_threshold: float = 0.70,
    use_llm_decomposition: bool = True,
):
    """
    Create AgenticLLMWrapper wired to Mistral API.

    Returns:
        Configured AgenticLLMWrapper instance.
    """
    from agentic.agentic_framework import AgenticLLMWrapper
    from agentic.agentic_framework.llm_adapters import MistralAdapter

    key = api_key or os.environ.get("MISTRAL_API_KEY")
    if not key:
        print("Error: MISTRAL_API_KEY not set. "
              "Export it or pass --api-key.")
        sys.exit(1)

    llm = MistralAdapter(
        api_key=key,
        model=model,
        temperature=0.7,
        max_tokens=1024,
    )

    agent = AgenticLLMWrapper(
        llm,
        max_revisions=max_revisions,
        quality_threshold=quality_threshold,
        memory_window=20,
        coherence_window=10,
        use_llm_for_decomposition=use_llm_decomposition,
    )

    return agent


def create_cg_agent(
    cg_model: str = "mistralai/Mistral-7B-v0.3",
    cg_quantize: Optional[str] = None,
    cg_device: str = "auto",
    max_revisions: int = 2,
    quality_threshold: float = 0.70,
    use_llm_decomposition: bool = True,
    allow_stub: bool = False,
):
    """
    Create the CG-capable runtime: MistralCGAdapter + CGToolDispatcher +
    SafeMCPGateway, composed through ``build_cg_mcp_agent(...)``.

    This is the real-runtime proof path described in
    ``docs/RUNTIME_MCP_PATH.md`` § "The substitution seam". The returned
    wrapper is functionally identical to the one produced by
    ``create_agent(...)`` except that it (a) uses a local CG-capable
    adapter which populates ``last_cg_metadata`` per call, and (b)
    routes mapped action types through the dispatcher into MCP
    governance.

    Args:
        cg_model: HuggingFace model id for the underlying MistralCGWrapper.
        cg_quantize: Quantization mode passed through to MistralCGWrapper
            (None, "4bit", "8bit").
        cg_device: Device-map strategy for MistralCGWrapper.
        max_revisions, quality_threshold, use_llm_decomposition: Forwarded
            to AgenticLLMWrapper.
        allow_stub: When True, falls back to ``StubCGLLMAdapter`` if the
            heavy inference stack (torch / transformers / MistralCGWrapper)
            is unavailable. Off by default.

    Returns:
        Configured AgenticLLMWrapper wired through the CG/MCP runtime path.
    """
    from agentic.agentic_framework.cg_tool_dispatcher import (
        build_cg_mcp_agent,
    )

    try:
        from agentic.agentic_framework.llm_adapters import MistralCGAdapter
        adapter = MistralCGAdapter(
            model_name=cg_model,
            quantize=cg_quantize,
            device_map=cg_device,
        )
        using_stub = False
    except Exception as exc:  # torch / transformers / wrapper missing
        if not allow_stub:
            print(
                "Error: CG runtime requested but MistralCGAdapter could "
                f"not be constructed: {exc}\n"
                "Install the heavy inference stack (torch, transformers, "
                "symbolu_training.training.unified.mistral_wrapper) or "
                "pass --cg-allow-stub to fall back to StubCGLLMAdapter "
                "(deterministic fixture — dev/test only)."
            )
            sys.exit(1)
        print(
            f"  [warn] MistralCGAdapter unavailable ({exc}); falling "
            "back to StubCGLLMAdapter (deterministic fixture — dev/test "
            "only)."
        )
        from agentic.agentic_framework.llm_adapters import StubCGLLMAdapter
        adapter = StubCGLLMAdapter(
            default_response="[stub CG response]",
        )
        using_stub = True

    return build_cg_mcp_agent(
        adapter=adapter,
        allow_stub=using_stub or allow_stub,
        max_revisions=max_revisions,
        quality_threshold=quality_threshold,
        memory_window=20,
        coherence_window=10,
        use_llm_for_decomposition=use_llm_decomposition,
    )


def _build_agent(
    *,
    cg: bool,
    model: str,
    api_key: Optional[str],
    cg_config: Optional[Dict[str, Any]],
):
    """Dispatch to either the API-adapter path or the CG-runtime path.

    Returns (agent, model_label) — `model_label` is what the CLI prints
    to tell the user which backend they're actually on.
    """
    if cg:
        cfg = dict(cg_config or {})
        agent = create_cg_agent(**cfg)
        label = f"[CG] {cfg.get('cg_model', 'mistralai/Mistral-7B-v0.3')}"
        return agent, label
    agent = create_agent(model=model, api_key=api_key)
    return agent, model


def run_single(
    query: str,
    model: str = "mistral-large-latest",
    api_key: Optional[str] = None,
    verbose: bool = False,
    cg: bool = False,
    cg_config: Optional[Dict[str, Any]] = None,
) -> None:
    """Run a single query through the full agentic pipeline."""
    _print_header("MISTRAL AGENTIC INFERENCE")

    agent, model_label = _build_agent(
        cg=cg, model=model, api_key=api_key, cg_config=cg_config,
    )
    agent.new_session()

    print(f"\n  Model: {model_label}")
    print(f"  Query: {query}")

    result = agent.run(query)
    _print_result(result, verbose=verbose)

    # Show goal decomposition
    goal = agent.goal_state
    if goal and verbose:
        print(f"\n  --- Goal Decomposition ---")
        print(f"  Purpose:  {goal.purpose_type}")
        print(f"  Agency:   {goal.agency_level}")
        if goal.actions:
            for a in goal.actions:
                print(f"    [{a.status}] {a.action_type}: {a.description}")


def run_demo(
    model: str = "mistral-large-latest",
    api_key: Optional[str] = None,
    verbose: bool = False,
    cg: bool = False,
    cg_config: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Run a multi-turn demo exercising all pipeline features:
    goal decomposition, memory, reflective loop, coherence, safety.
    """
    _print_header("MISTRAL AGENTIC DEMO — Multi-Turn Pipeline")

    agent, model_label = _build_agent(
        cg=cg, model=model, api_key=api_key, cg_config=cg_config,
    )
    agent.new_session("mistral-demo")

    print(f"\n  Model:   {model_label}")
    print(f"  Session: {agent.session_id}")

    turns = [
        # Turn 1: informational — tests basic generation + goal decomposition
        "Explain how a transformer neural network works in 3 sentences.",
        # Turn 2: follow-up — tests memory (references prior context)
        "What is the role of the attention mechanism you just described?",
        # Turn 3: task-oriented — tests action decomposition + safety
        "Compare the computational complexity of self-attention vs linear attention.",
        # Turn 4: creative — tests quality critic + coherence on topic shift
        "Write a one-paragraph analogy explaining transformers to a 10-year-old.",
        # Turn 5: meta — tests memory export + session summary
        "Summarize what we've discussed about transformers so far.",
    ]

    for i, user_msg in enumerate(turns, 1):
        print(f"\n{'─' * 60}")
        print(f"  Turn {i}: {user_msg}")
        print(f"{'─' * 60}")

        result = agent.run(user_msg)
        _print_result(result, verbose=verbose)

    # Session summary
    _print_header("SESSION SUMMARY")
    summary = agent.get_session_summary()
    print(f"  Session ID:      {summary.get('session_id')}")
    print(f"  Total turns:     {summary.get('turn_count')}")
    print(f"  Avg quality:     {summary.get('average_quality', 0):.3f}")
    print(f"  Coherence trend: {summary.get('coherence_trend')}")
    print(f"  Blocked count:   {summary.get('blocked_count')}")

    # Conversation export
    history = agent.export_conversation()
    print(f"\n  Exported {len(history)} turns to conversation history.")

    # Goal state
    goal = agent.goal_state
    if goal:
        print(f"\n  Final goal state:")
        print(f"    Purpose: {goal.purpose_type}")
        print(f"    Agency:  {goal.agency_level}")

    _print_header("DEMO COMPLETE")


def run_interactive(
    model: str = "mistral-large-latest",
    api_key: Optional[str] = None,
    verbose: bool = False,
    cg: bool = False,
    cg_config: Optional[Dict[str, Any]] = None,
) -> None:
    """Interactive REPL — type queries, see full pipeline output."""
    _print_header("MISTRAL AGENTIC INTERACTIVE")

    agent, model_label = _build_agent(
        cg=cg, model=model, api_key=api_key, cg_config=cg_config,
    )
    agent.new_session()

    print(f"\n  Model:   {model_label}")
    print(f"  Session: {agent.session_id}")
    print(f"\n  Type a message to chat. Commands:")
    print(f"    /summary  — show session summary")
    print(f"    /export   — export conversation")
    print(f"    /goal     — show current goal state")
    print(f"    /new      — start new session")
    print(f"    /verbose  — toggle verbose mode")
    print(f"    /quit     — exit")

    while True:
        try:
            user_input = input("\n  You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n  Goodbye.")
            break

        if not user_input:
            continue

        # Commands
        if user_input.lower() == "/quit":
            print("  Goodbye.")
            break
        elif user_input.lower() == "/summary":
            summary = agent.get_session_summary()
            print(f"\n  Session: {summary}")
            continue
        elif user_input.lower() == "/export":
            history = agent.export_conversation()
            print(f"\n  Conversation ({len(history)} turns):")
            for t in history:
                print(f"    [{t.get('quality_score', 0):.2f}] "
                      f"User: {str(t.get('user_input', ''))[:60]}...")
            continue
        elif user_input.lower() == "/goal":
            goal = agent.goal_state
            if goal:
                print(f"\n  Purpose: {goal.purpose_type}")
                print(f"  Agency:  {goal.agency_level}")
                for a in (goal.actions or []):
                    print(f"    [{a.status}] {a.action_type}: {a.description}")
            else:
                print("  No goal state yet.")
            continue
        elif user_input.lower() == "/new":
            agent.new_session()
            print(f"  New session: {agent.session_id}")
            continue
        elif user_input.lower() == "/verbose":
            verbose = not verbose
            print(f"  Verbose: {'ON' if verbose else 'OFF'}")
            continue

        # Run through full pipeline
        result = agent.run(user_input)
        _print_result(result, verbose=verbose)


def main():
    parser = argparse.ArgumentParser(
        description="Mistral inference through AgenticLLMWrapper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --demo                                    # Multi-turn demo
  %(prog)s --query "What is quantum computing?"      # Single query
  %(prog)s                                           # Interactive REPL
  %(prog)s --model mistral-medium-latest --verbose   # Custom model, verbose
""",
    )
    parser.add_argument(
        "--query", "-q",
        type=str,
        help="Single query to run (exits after response)",
    )
    parser.add_argument(
        "--demo", "-d",
        action="store_true",
        help="Run multi-turn demo exercising all pipeline features",
    )
    parser.add_argument(
        "--model", "-m",
        type=str,
        default="mistral-large-latest",
        help="Mistral model name (default: mistral-large-latest)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Mistral API key (default: MISTRAL_API_KEY env var)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show full pipeline metrics on each turn",
    )
    parser.add_argument(
        "--max-revisions",
        type=int,
        default=2,
        help="Max reflective revisions per turn (default: 2)",
    )
    parser.add_argument(
        "--quality-threshold",
        type=float,
        default=0.70,
        help="Quality threshold for accepting responses (default: 0.70)",
    )
    # --- CG-runtime opt-in flags -------------------------------------
    # When --cg is passed, the CLI constructs a MistralCGAdapter and
    # routes the agent through build_cg_mcp_agent(...) — the real
    # CG/MCP runtime path described in docs/RUNTIME_MCP_PATH.md.
    # Without --cg, behavior is exactly as before.
    parser.add_argument(
        "--cg",
        action="store_true",
        help=(
            "Opt-in: use local CG-capable runtime (MistralCGAdapter + "
            "CGToolDispatcher + SafeMCPGateway) instead of the Mistral "
            "API adapter."
        ),
    )
    parser.add_argument(
        "--cg-model",
        type=str,
        default="mistralai/Mistral-7B-v0.3",
        help="HuggingFace model id for --cg mode.",
    )
    parser.add_argument(
        "--cg-quantize",
        type=str,
        default=None,
        choices=["4bit", "8bit"],
        help="Quantization mode for --cg mode (default: none).",
    )
    parser.add_argument(
        "--cg-device",
        type=str,
        default="auto",
        help="Device-map strategy for --cg mode (default: auto).",
    )
    parser.add_argument(
        "--cg-allow-stub",
        action="store_true",
        help=(
            "In --cg mode, fall back to StubCGLLMAdapter if the heavy "
            "inference stack is unavailable. Dev/test only."
        ),
    )

    args = parser.parse_args()

    cg_config = {
        "cg_model": args.cg_model,
        "cg_quantize": args.cg_quantize,
        "cg_device": args.cg_device,
        "max_revisions": args.max_revisions,
        "quality_threshold": args.quality_threshold,
        "allow_stub": args.cg_allow_stub,
    }

    if args.query:
        run_single(
            query=args.query,
            model=args.model,
            api_key=args.api_key,
            verbose=args.verbose,
            cg=args.cg,
            cg_config=cg_config,
        )
    elif args.demo:
        run_demo(
            model=args.model,
            api_key=args.api_key,
            verbose=args.verbose,
            cg=args.cg,
            cg_config=cg_config,
        )
    else:
        run_interactive(
            model=args.model,
            api_key=args.api_key,
            verbose=args.verbose,
            cg=args.cg,
            cg_config=cg_config,
        )


if __name__ == "__main__":
    main()
