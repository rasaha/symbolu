"""
Opt-in CG-runtime smoke test for ``inference_mistral.py``.

Skipped by default. Enable by exporting ``SYMBOLU_RUN_CG_SMOKE=1`` in
the environment (and only when the heavy inference stack or the
explicit stub fallback is available).

What it pins:
  - ``create_cg_agent(..., allow_stub=True)`` composes an
    AgenticLLMWrapper with a CGToolDispatcher and a gateway.
  - The agent is runnable: ``agent.run(query)`` completes without
    raising and returns an ``AgentResult``-shaped object.
  - The adapter actually generated: ``adapter.last_cg_metadata``
    carries a 32D sovereign state after the run.

This is the **real-runtime proof path** — it exercises the exact wiring
the production ``--cg`` CLI flag would use, just with the stub adapter
fallback so the test has no heavyweight dependencies.
"""

from __future__ import annotations

import os

import pytest

_SMOKE_ENABLED = os.environ.get("SYMBOLU_RUN_CG_SMOKE") == "1"

pytestmark = pytest.mark.skipif(
    not _SMOKE_ENABLED,
    reason=(
        "CG smoke test is opt-in. Set SYMBOLU_RUN_CG_SMOKE=1 to enable."
    ),
)


def test_cg_runtime_smoke_with_stub_fallback():
    """End-to-end smoke: build CG runtime via the same path --cg uses,
    then run one query through it.

    Uses ``allow_stub=True`` so the test does not require torch /
    transformers / the MistralCGWrapper checkpoint to be present.
    When that stack IS present, ``create_cg_agent`` will prefer the
    real ``MistralCGAdapter`` and this test still holds.
    """
    from agentic.agentic_framework.inference_mistral import create_cg_agent
    from agentic.agentic_framework.cg_tool_dispatcher import CGToolDispatcher

    agent = create_cg_agent(allow_stub=True)

    # Wiring assertions — same shape the runtime factory guarantees.
    assert agent.dispatcher is not None
    assert isinstance(agent.dispatcher, CGToolDispatcher)
    assert agent.dispatcher.gateway is not None

    agent.new_session("cg-smoke")
    result = agent.run("What is the capital of France?")

    # Result shape (pinned by AgenticLLMWrapper.run contract).
    assert hasattr(result, "response")
    assert hasattr(result, "coherence")
    assert hasattr(result, "safety_contract")

    # Adapter generated at least once — ``last_cg_metadata`` populated.
    md = agent.dispatcher.adapter.last_cg_metadata
    assert "state" in md
    assert len(md["state"]) == 32
