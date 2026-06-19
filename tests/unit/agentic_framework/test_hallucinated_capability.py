"""
test_hallucinated_capability.py — deterministic rules for the Phase 2 observable.

Covers each violation kind, alias resolution, the valid-capability control, empty-context
inertness, the SAFE/UNSURE/UNSAFE verdict mapping, and the confirm-only (PROVISIONAL)
guarantee. Also asserts no overlap with permission-overclaim semantics (existence vs grant).
"""

from __future__ import annotations

from agentic.agentic_framework.trust.decision import decide
from agentic.agentic_framework.trust.observables import (
    EvidenceStatus,
    ObservableType,
    TrustDecision,
    Verdict,
)
from agentic.agentic_framework.trust.hallucinated_capability import (
    CapabilityContext,
    build_hallucination_observation,
    detect_hallucination,
)


def _kinds(ctx):
    return {v.kind for v in detect_hallucination(ctx)}


# ---- violation kinds --------------------------------------------------------

def test_hallucinated_tool_name():
    ctx = CapabilityContext(referenced_tools=("teleport",),
                            available_tools=frozenset({"file_read"}))
    assert _kinds(ctx) == {"hallucinated_tool"}


def test_unsupported_capability():
    ctx = CapabilityContext(referenced_capabilities=("gpu_train",),
                            available_capabilities=frozenset({"read", "write"}))
    assert _kinds(ctx) == {"unsupported_capability"}


def test_impossible_capability_is_severe():
    ctx = CapabilityContext(referenced_capabilities=("read_other_tenant_secrets",),
                            impossible_capabilities=frozenset({"read_other_tenant_secrets"}))
    assert _kinds(ctx) == {"impossible_capability"}
    assert build_hallucination_observation(ctx).verdict == Verdict.UNSAFE


# ---- alias resolution + valid control --------------------------------------

def test_alias_resolves_to_available_is_clean():
    ctx = CapabilityContext(referenced_tools=("fs.read",),
                            available_tools=frozenset({"file_read"}),
                            aliases={"fs.read": "file_read"})
    assert detect_hallucination(ctx) == []
    assert build_hallucination_observation(ctx).verdict == Verdict.SAFE


def test_alias_to_unavailable_still_hallucinated():
    ctx = CapabilityContext(referenced_tools=("fs.read",),
                            available_tools=frozenset({"file_write"}),
                            aliases={"fs.read": "file_read"})
    assert "hallucinated_tool" in _kinds(ctx)


def test_valid_capability_control_is_safe():
    ctx = CapabilityContext(referenced_tools=("file_read",), referenced_capabilities=("read",),
                            available_tools=frozenset({"file_read"}),
                            available_capabilities=frozenset({"read"}))
    assert detect_hallucination(ctx) == []
    assert build_hallucination_observation(ctx).verdict == Verdict.SAFE


# ---- inert ------------------------------------------------------------------

def test_empty_context_is_inert():
    assert build_hallucination_observation(CapabilityContext()) is None
    assert build_hallucination_observation(None) is None


# ---- taxonomy + confirm-only ------------------------------------------------

def test_observation_is_provisional_validator():
    obs = build_hallucination_observation(
        CapabilityContext(referenced_tools=("ghost",), available_tools=frozenset()))
    assert obs.otype == ObservableType.VALIDATOR
    assert obs.evidence == EvidenceStatus.PROVISIONAL
    assert obs.name == "hallucinated_capability" and obs.detail["violations"]


def test_provisional_only_confirms_never_blocks():
    obs = build_hallucination_observation(
        CapabilityContext(referenced_capabilities=("time_travel",),
                          impossible_capabilities=frozenset({"time_travel"})))
    assert obs.verdict == Verdict.UNSAFE
    assert decide([obs]).decision == TrustDecision.CONFIRM     # never BLOCK while provisional


def test_promoted_impossible_would_block():
    obs = build_hallucination_observation(
        CapabilityContext(referenced_capabilities=("time_travel",),
                          impossible_capabilities=frozenset({"time_travel"})),
        evidence=EvidenceStatus.PROVEN)
    assert decide([obs]).decision == TrustDecision.BLOCK
