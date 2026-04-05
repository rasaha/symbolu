#!/usr/bin/env python3
"""
CG Metadata → MCP Tool Call: End-to-End Demo
============================================

This script is an **honest demo** (not production). It exercises the full
Phase 1 + Phase 2 enrichment path end-to-end:

    inference output → CG metadata → request_enrichment seam
        → SafeMCPGateway.call_tool_simple(cg_metadata=...)
        → governance evaluation → audit

Why this demo exists
--------------------
Phase 1 wired ``cg_metadata`` into ``call_tool_simple()``. Phase 2 added
the reusable ``build_governance_enrichment_kwargs()`` seam. Phase 4's
audit showed that **no production component today** simultaneously owns
a CG-capable LLM adapter AND calls a governance-aware tool gateway. So
the Phase 1+2 wiring is correct but has zero real callers.

This demo is the smallest honest end-to-end exerciser of that wiring:
it shows the path *works*, prints the audit record to prove
governance actually consumed the sovereign signals, and serves as
executable documentation of the seam.

What is real, what is fake
--------------------------
Real (production code paths, not re-implemented here):
    - ``SafeMCPGateway.call_tool_simple(cg_metadata=..., tier=...)``
    - ``build_governance_enrichment_kwargs(...)``
    - ``governance_inputs_from_cg_metadata(...)``
    - the full governance/audit pipeline behind the gateway

Fake / demo-only:
    - The ``DemoCGAdapter`` class below. It has exactly the contract of
      ``MistralCGAdapter.last_cg_metadata`` (a dict with ``"state"``
      and ``"delta_S"`` keys) but produces a deterministic synthetic
      32D sovereign state instead of loading a real Mistral checkpoint.
      This keeps the demo runnable anywhere, with no GPU / torch model
      / tokenizer dependencies. The wire format it produces is
      identical to what the real adapter stores.

To use the real adapter instead, replace ``DemoCGAdapter`` with::

    from agentic.agentic_framework.llm_adapters import create_adapter
    adapter = create_adapter("mistral_cg", model_name="...")
    adapter.generate(prompt)   # populates adapter.last_cg_metadata

Nothing else in this script would need to change.

Running
-------
    python examples/cg_tool_demo.py

Expected output: one successful tool-call result, followed by the audit
record showing ``vritti_signal_source=real`` and ``entropy_available=True``
— proving the CG-metadata-derived signals were actually consumed by
governance (not the fallback approximation).
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional


# =============================================================================
# DemoCGAdapter — synthesizes the cg_metadata contract without torch
# =============================================================================

class DemoCGAdapter:
    """
    A zero-dependency stand-in for ``MistralCGAdapter``.

    Produces a ``last_cg_metadata`` dict matching the real adapter's
    wire contract (32-float sovereign ``state`` + optional ``delta_S``),
    so the downstream enrichment / governance path sees exactly the
    same shape a real run would produce.

    This class is demo-only. Do NOT use in production — production
    callers must use the real ``MistralCGAdapter`` (or another CG-capable
    adapter) whose state reflects an actual inference trajectory.
    """

    def __init__(self) -> None:
        self.last_cg_metadata: Dict[str, Any] = {}

    def generate(self, prompt: str) -> str:
        """
        Fake generation. Populates ``last_cg_metadata`` with a plausible
        32D sovereign state shaped by the prompt length (so different
        prompts produce different states, like a real adapter would).
        """
        # 32D sovereign layout (matches SovereignStateMonitor):
        #   bhava: 0..11   (12 dims)
        #   kosha: 12..16  (5 dims)
        #   vritti: 17..21 (5 dims)
        #   guna: 22..27   (6 dims)
        #   reserved: 28..31 (4 dims)
        prompt_len = max(1, len(prompt))
        base = (prompt_len % 17) / 17.0  # deterministic pseudo-signal

        state = [0.0] * 32
        # bhava — gently distributed
        for i in range(12):
            state[i] = 0.15 + 0.05 * ((i + prompt_len) % 3) / 3.0
        # kosha — moderate
        for i in range(5):
            state[12 + i] = 0.25 + 0.1 * base
        # vritti — dominant first component (represents a focused "vritti")
        state[17] = 0.55
        state[18] = 0.15
        state[19] = 0.15
        state[20] = 0.10
        state[21] = 0.05
        # guna — sattva-leaning (first dim dominant)
        state[22] = 0.65
        state[23] = 0.25
        state[24] = 0.10
        state[25] = 0.0
        state[26] = 0.0
        # last guna-region dim: coherence-ish
        state[27] = 0.9

        # Small, non-zero delta_S so velocity is "known" to the bridge
        delta_S = [0.01 * (i % 3 - 1) for i in range(32)]

        self.last_cg_metadata = {
            "state": state,
            "delta_S": delta_S,
            "delta_bhava": None,
            "intent_phase": None,
        }
        # Fake text output — the real adapter would return generated tokens.
        return f"[demo response to: {prompt!r}]"


# =============================================================================
# Demo driver
# =============================================================================

async def run_demo() -> None:
    """Execute the full enrichment path and print results."""
    # Real production imports — these are the code paths under test.
    from agentic.agentic_framework.mcp_gateway import create_mock_mcp_gateway

    # 1) Create a CG-capable adapter (demo stand-in). A real deployment
    #    would swap this for `create_adapter("mistral_cg", ...)`.
    adapter = DemoCGAdapter()

    # 2) Create a gateway. `create_mock_mcp_gateway` is a production
    #    helper exported from SafeMCPGateway — the same one the test
    #    suite uses. It registers a few safe mock tools (file_read,
    #    file_write, search) for exercising the gateway.
    gateway = create_mock_mcp_gateway()

    # 3) Run "inference" — this populates adapter.last_cg_metadata with
    #    a fresh 32D sovereign state, exactly as a real generation turn
    #    would.
    prompt = "What file should I inspect in /tmp?"
    response_text = adapter.generate(prompt)
    print(f"[1/3] adapter.generate() → {response_text}")
    print(
        f"      last_cg_metadata keys: {list(adapter.last_cg_metadata.keys())}"
    )
    print(
        f"      state length: {len(adapter.last_cg_metadata['state'])}D"
    )

    # 4) Dispatch a safe tool call, enriching with CG metadata. This is
    #    the single production line that Phase 1 + Phase 2 enabled.
    print("\n[2/3] gateway.call_tool_simple(..., cg_metadata=...)")
    result = await gateway.call_tool_simple(
        tool_name="file_read",
        parameters={"path": "/tmp/demo.txt"},
        quality_score=0.9,
        coherence_score=0.9,
        cg_metadata=adapter.last_cg_metadata,
        tier="consumer",
    )
    print(f"      success: {result.success}")
    if result.success:
        print(f"      result: {result.result}")
    else:
        print(f"      blocked: {result.reason}")

    # 5) Show the audit record proving governance consumed the signals.
    #    `vritti_signal_source == "real"` means the vritti adapter
    #    found a real ChittaVrittiResult attached to the MCPToolCall
    #    (not the fallback approximation). Similarly `entropy_available
    #    == True` proves the entropy adapter found a real EntropyResult.
    print("\n[3/3] audit record (proves governance consumed CG signals):")
    entry = gateway.audit_log[-1]
    print(f"      decision:              {entry.decision}")
    print(f"      vritti_signal_source:  {entry.vritti_signal_source}")
    print(f"      entropy_available:     {entry.entropy_available}")
    if entry.vritti_signal_source == "real" and entry.entropy_available:
        print(
            "\n      ✓ End-to-end enrichment path verified: "
            "CG metadata was translated to canonical EntropyResult + "
            "ChittaVrittiResult by the sovereign bridge, attached to "
            "the MCPToolCall by the request_enrichment seam, and "
            "consumed by the governance audit path."
        )
    else:
        print(
            "\n      ✗ Enrichment did NOT flow through — audit shows "
            "fallback/approximation path was taken. Check wiring."
        )


def main() -> None:
    asyncio.run(run_demo())


if __name__ == "__main__":
    main()
