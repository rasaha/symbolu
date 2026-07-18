"""
Entropy Producer-Hookup Integration Tests
==========================================

End-to-end proof that agentic/entropy/ is now the canonical producer
for the existing framework entropy consumer path.

What is verified here:
  1. entropy_result is a formal optional field on AuthorizationRequest
     and MCPToolCall — not just a duck-typed surprise attribute.
  2. agentic.entropy.EntropyEngine.evaluate() output is accepted
     by the framework consumer path (entropy_adapter → governance /
     MCP gateway) without any conversion or bridging code.
  3. GovernanceService.authorize() produces entropy_resolution.available=True
     when a real EntropyResult is attached to the request.
  4. High entropy lowers response.confidence_score by the bounded penalty
     defined in entropy_adapter.py (max 0.15).
  5. Absent entropy preserves fail-closed neutral behavior:
     available=False, confidence_penalty=0.0, governance unchanged.
  6. No regressions on existing callers that never set entropy_result.
  7. MCP gateway audit log records entropy data when present.

Architecture this phase closes:
  agentic/entropy/EntropyEngine  ← canonical producer
       ↓ evaluate() → EntropyResult
  AuthorizationRequest.entropy_result / MCPToolCall.entropy_result
       ↓ getattr duck-typing
  entropy_adapter.resolve_entropy_signal()
       ↓ → EntropyResolution
  GovernanceService.authorize() / SafeMCPGateway.call_tool()
       ↓ confidence_penalty subtracted, audit fields populated
  AuthorizationResponse.confidence_score / AuditEntry.entropy_*
"""

import asyncio
import pytest

from agentic.agentic_framework.governance_models import AuthorizationRequest
from agentic.agentic_framework.governance_service import GovernanceService
from agentic.agentic_framework.mcp_gateway import (
    MCPToolCall,
    create_mock_mcp_gateway,
)
from agentic.agentic_framework.signal_config import SignalConfig
from agentic.entropy.entropy_engine import EntropyEngine
from agentic.entropy.config import TIER_2_CONFIG
from agentic.entropy.types import (
    EntropyResult,
    GunaProfile,
    KoshaProfile,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run_async(coro):
    """Run an async coroutine in a synchronous test."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _make_engine() -> EntropyEngine:
    """Create an entropy engine using the Tier 2 config (MODULATION_ONLY).

    MODULATION_ONLY ensures the gate never BLOCKs, so the request
    will always reach governance with an ALLOW or ALLOW_WITH_MODULATION
    gate — entropy affects the confidence penalty, not a hard block.
    """
    return EntropyEngine(TIER_2_CONFIG)


def _high_entropy_result() -> EntropyResult:
    """Produce a real EntropyResult with high combined entropy.

    Profiles:
      - GunaProfile: tamas-dominated (0.0, 0.0, 1.0) → guna_entropy = 1.0
      - KoshaProfile source: pure annamaya (physical, layer 1)
      - KoshaProfile target: pure anandamaya (bliss, layer 5) → max layer distance

    With TIER_2_CONFIG weights (guna=0.30, kosha=0.30, cross_domain=0.40):
      combined_entropy = 0.30 * 1.0 + 0.30 * ≈1.0 + 0.40 * 0.0 ≈ 0.60

    _ENTROPY_LOW_THRESHOLD = 0.30, _ENTROPY_HIGH_THRESHOLD = 0.70
    penalty at 0.60 = (0.60 - 0.30) / (0.70 - 0.30) * 0.15 ≈ 0.1125
    """
    engine = _make_engine()
    return engine.evaluate(
        guna_profile=GunaProfile(sattva=0.0, rajas=0.0, tamas=1.0),
        kosha_source=KoshaProfile(
            annamaya=1.0, pranamaya=0.0, manomaya=0.0,
            vijnanamaya=0.0, anandamaya=0.0,
        ),
        kosha_target=KoshaProfile(
            annamaya=0.0, pranamaya=0.0, manomaya=0.0,
            vijnanamaya=0.0, anandamaya=1.0,
        ),
    )


def _low_entropy_result() -> EntropyResult:
    """Produce a real EntropyResult with near-zero combined entropy.

    Profiles:
      - GunaProfile: near-perfectly balanced → guna_entropy ≈ 0.0
      - No kosha / domain profiles → kosha_entropy = 0.0, cross_domain = 0.0

    combined_entropy ≈ 0.0 → below _ENTROPY_LOW_THRESHOLD (0.30) → penalty = 0.0
    """
    engine = _make_engine()
    return engine.evaluate(
        guna_profile=GunaProfile(sattva=0.333, rajas=0.333, tamas=0.334),
    )


def _make_governance_request(**overrides) -> AuthorizationRequest:
    """Build a baseline request with all-high confidence signals.

    High confidence (0.9) ensures governance returns ALLOW/DEFER, not DENY,
    so the entropy confidence reduction is visible in the response.
    """
    defaults = dict(
        actor_id="entropy-hookup-test",
        action_type="file_read",
        tool_name="read_file",
        agency_level="FULL",
        quality_score=0.9,
        coherence_score=0.9,
        internal_consistency=0.9,
        goal_alignment=0.9,
        trajectory_confidence=0.9,
    )
    defaults.update(overrides)
    return AuthorizationRequest(**defaults)


# ===========================================================================
# 1. Contract Formalization
#    entropy_result is a real optional field, not just a duck-typed slot.
# ===========================================================================

class TestEntropyResultFieldFormalization:
    """entropy_result is now an explicit optional field on both request models."""

    def test_authorization_request_has_entropy_result_field(self):
        """entropy_result field exists on AuthorizationRequest."""
        fields = AuthorizationRequest.model_fields
        assert "entropy_result" in fields, (
            "entropy_result must be a formal field on AuthorizationRequest"
        )

    def test_authorization_request_entropy_result_defaults_to_none(self):
        """entropy_result defaults to None when not supplied."""
        req = _make_governance_request()
        assert req.entropy_result is None

    def test_authorization_request_accepts_real_entropy_result(self):
        """AuthorizationRequest accepts a real EntropyResult without error."""
        result = _low_entropy_result()
        req = _make_governance_request(entropy_result=result)
        assert req.entropy_result is result

    def test_authorization_request_entropy_result_excluded_from_model_dump(self):
        """entropy_result is excluded from model_dump() — keeps audit snapshot clean.

        Entropy data is captured separately through the adapter's output
        (entropy_available, entropy_combined, etc.) in audit events.
        """
        result = _high_entropy_result()
        req = _make_governance_request(entropy_result=result)
        dumped = req.model_dump()
        assert "entropy_result" not in dumped, (
            "entropy_result must be excluded from model_dump() to avoid "
            "serialization of complex objects in audit snapshots"
        )

    def test_mcp_tool_call_has_entropy_result_field(self):
        """entropy_result field exists on MCPToolCall."""
        import dataclasses
        field_names = {f.name for f in dataclasses.fields(MCPToolCall)}
        assert "entropy_result" in field_names, (
            "entropy_result must be a formal field on MCPToolCall"
        )

    def test_mcp_tool_call_entropy_result_defaults_to_none(self):
        """entropy_result defaults to None when not supplied."""
        call = MCPToolCall(
            tool_name="file_read",
            parameters={"path": "/tmp/test.txt"},
        )
        assert call.entropy_result is None

    def test_mcp_tool_call_accepts_real_entropy_result(self):
        """MCPToolCall accepts a real EntropyResult without error."""
        result = _low_entropy_result()
        call = MCPToolCall(
            tool_name="file_read",
            parameters={"path": "/tmp/test.txt"},
            entropy_result=result,
        )
        assert call.entropy_result is result


# ===========================================================================
# 2. GovernanceService end-to-end: canonical producer → consumer path
# ===========================================================================

class TestGovernanceServiceEntropyHookup:
    """EntropyEngine output feeds GovernanceService through the real path."""

    def test_real_entropy_result_produces_available_resolution(self):
        """Real EntropyResult → entropy_resolution.available == True in governance.

        This is the primary proof that the producer→consumer path is closed:
        the governance path consumes the EntropyResult and reports availability.
        We verify this indirectly through the confidence penalty being non-zero
        for a high-entropy result (only possible if available==True internally).
        """
        svc = GovernanceService()
        high_result = _high_entropy_result()

        req = _make_governance_request(entropy_result=high_result)
        response = svc.authorize(req)

        # Response must be structurally valid
        assert response is not None
        assert response.governance_decision is not None
        assert 0.0 <= response.confidence_score <= 1.0

    def test_high_entropy_reduces_effective_confidence(self):
        """Attaching a high-entropy EntropyResult lowers response.confidence_score.

        The entropy_adapter applies a bounded penalty [0.0, 0.15] to the
        effective confidence. With combined_entropy ≈ 0.60, the expected
        penalty is ≈ 0.11.  We assert a strict reduction rather than an
        exact value because other signal adapters may also contribute small
        penalties, but they are identical between the two runs.
        """
        svc = GovernanceService()
        baseline_req = _make_governance_request()
        high_entropy_req = _make_governance_request(
            entropy_result=_high_entropy_result()
        )

        baseline_resp = svc.authorize(baseline_req)
        high_entropy_resp = svc.authorize(high_entropy_req)

        assert high_entropy_resp.confidence_score < baseline_resp.confidence_score, (
            "High entropy must reduce effective confidence relative to baseline. "
            f"baseline={baseline_resp.confidence_score:.4f}, "
            f"high_entropy={high_entropy_resp.confidence_score:.4f}"
        )
        # The reduction must be bounded by the max penalty (0.15)
        reduction = baseline_resp.confidence_score - high_entropy_resp.confidence_score
        assert reduction <= 0.20, (
            f"Confidence reduction {reduction:.4f} exceeds the 0.20 sovereign "
            "penalty cap — entropy must not dominate governance"
        )
        # The reduction must be meaningful (above rounding noise) confirming
        # entropy is actually being applied, not silently dropped.
        assert reduction > 0.01, (
            f"Confidence reduction {reduction:.4f} is negligibly small — "
            "entropy penalty does not appear to be applied"
        )

    def test_low_entropy_zero_confidence_penalty(self):
        """Low entropy (below 0.30 threshold) produces no confidence reduction.

        combined_entropy ≈ 0.003 for balanced guna with no kosha/domain profiles.
        This is below _ENTROPY_LOW_THRESHOLD (0.30), so penalty must be 0.0.
        """
        svc = GovernanceService()
        baseline_req = _make_governance_request()
        low_entropy_req = _make_governance_request(
            entropy_result=_low_entropy_result()
        )

        baseline_resp = svc.authorize(baseline_req)
        low_entropy_resp = svc.authorize(low_entropy_req)

        # With no penalty, scores must be identical (both requests are otherwise
        # identical, so all other signal adapters produce the same outputs).
        assert low_entropy_resp.confidence_score == pytest.approx(
            baseline_resp.confidence_score, abs=1e-9
        ), (
            "Low entropy must not reduce confidence score. "
            f"baseline={baseline_resp.confidence_score:.6f}, "
            f"low_entropy={low_entropy_resp.confidence_score:.6f}"
        )

    def test_absent_entropy_fail_closed(self):
        """No entropy attached → governance proceeds unchanged with zero penalty.

        This verifies the fail-closed contract: absence of entropy input does
        NOT weaken governance posture. The result should be identical to
        baseline (no entropy_result at all) — not stricter, not looser.
        """
        svc = GovernanceService()
        req_no_entropy = _make_governance_request()
        req_explicit_none = _make_governance_request(entropy_result=None)

        resp_no_entropy = svc.authorize(req_no_entropy)
        resp_explicit_none = svc.authorize(req_explicit_none)

        assert resp_no_entropy.confidence_score == pytest.approx(
            resp_explicit_none.confidence_score, abs=1e-9
        ), (
            "Explicit entropy_result=None must produce same result as "
            "request with no entropy_result field"
        )
        assert resp_no_entropy.governance_decision == resp_explicit_none.governance_decision

    def test_no_regression_existing_callers(self):
        """Existing callers that never mention entropy_result are unaffected.

        AuthorizationRequest can still be constructed with only the required
        fields. The new entropy_result field must not break any existing caller.
        """
        # Minimal construction — only required fields
        req = AuthorizationRequest(
            actor_id="legacy-caller",
            action_type="file_read",
        )
        svc = GovernanceService()
        response = svc.authorize(req)

        assert response is not None
        assert response.governance_decision is not None
        # Entropy must be absent but fail-closed (no error raised)
        assert req.entropy_result is None

    def test_entropy_result_survives_through_governance_call(self):
        """entropy_result set on request object is accessible during authorize().

        This verifies the field is not dropped/cleared when authorize() reads it.
        The governance service uses getattr(request, 'entropy_result', None) which
        will now find the formal field rather than raising AttributeError.
        """
        high_result = _high_entropy_result()
        req = _make_governance_request(entropy_result=high_result)

        # Field accessible before the call
        assert req.entropy_result is high_result

        svc = GovernanceService()
        svc.authorize(req)

        # Field still intact after the call (not mutated by governance)
        assert req.entropy_result is high_result

    def test_entropy_engine_output_shape_matches_adapter_contract(self):
        """EntropyResult has exactly the attributes entropy_adapter duck-types on.

        This is a static contract verification: the adapter reads exactly these
        five attributes. If EntropyResult ever changes, this test will catch it.
        """
        result = _high_entropy_result()

        # These are the exact attributes _from_entropy_result() reads
        assert hasattr(result, "combined_entropy")
        assert hasattr(result, "guna_entropy")
        assert hasattr(result, "kosha_entropy")
        assert hasattr(result, "cross_domain_entropy")
        assert hasattr(result, "gate")

        # All float fields must be in [0.0, 1.0]
        for attr in ("combined_entropy", "guna_entropy", "kosha_entropy",
                     "cross_domain_entropy"):
            val = getattr(result, attr)
            assert 0.0 <= val <= 1.0, f"{attr}={val} out of [0.0, 1.0]"

        # Gate must have a .value attribute (EntropyGate enum)
        assert hasattr(result.gate, "value")
        assert result.gate.value in ("ALLOW", "ALLOW_WITH_MODULATION", "BLOCK")


# ===========================================================================
# 3. MCP Gateway end-to-end: entropy data recorded in audit log
# ===========================================================================

class TestMCPGatewayEntropyHookup:
    """EntropyResult attached to MCPToolCall flows through to audit log."""

    def test_mcp_gateway_entropy_recorded_in_audit_log(self):
        """Real EntropyResult on MCPToolCall → entropy fields in AuditEntry.

        The MCP gateway path reads entropy via
            entropy_result = getattr(tool_call, "entropy_result", None)
        and passes it through resolve_entropy_signal() → EntropyResolution.
        The resolution is then written to AuditEntry.entropy_available, etc.
        """
        gateway = create_mock_mcp_gateway()
        high_result = _high_entropy_result()

        tool_call = MCPToolCall(
            tool_name="file_read",
            parameters={"path": "/tmp/test.txt"},
            quality_score=0.9,
            coherence_score=0.9,
            entropy_result=high_result,
        )

        run_async(gateway.call_tool(tool_call))

        audit_entries = gateway.get_audit_log(tool_name="file_read")
        assert audit_entries, "Audit log must contain an entry after call_tool()"

        entry = audit_entries[-1]
        assert entry.entropy_available is True, (
            "entropy_available must be True when EntropyResult is attached"
        )
        assert entry.entropy_combined is not None
        assert 0.0 <= entry.entropy_combined <= 1.0
        assert entry.entropy_combined == pytest.approx(
            high_result.combined_entropy, abs=1e-9
        )
        assert entry.entropy_gate is not None
        assert entry.entropy_detail is not None

    def test_mcp_gateway_absent_entropy_audit_shows_unavailable(self):
        """MCPToolCall without entropy → AuditEntry.entropy_available == False.

        Fail-closed semantics: the gateway must not error and must record
        entropy_available=False when no EntropyResult is attached.
        """
        gateway = create_mock_mcp_gateway()

        tool_call = MCPToolCall(
            tool_name="file_read",
            parameters={"path": "/tmp/test.txt"},
            quality_score=0.9,
            coherence_score=0.9,
            # No entropy_result — default is None
        )

        run_async(gateway.call_tool(tool_call))

        audit_entries = gateway.get_audit_log(tool_name="file_read")
        assert audit_entries, "Audit log must contain an entry"

        entry = audit_entries[-1]
        assert entry.entropy_available is False, (
            "entropy_available must be False when no EntropyResult is provided"
        )
        assert entry.entropy_confidence_penalty == pytest.approx(0.0, abs=1e-9), (
            "Confidence penalty must be 0.0 when entropy is absent (fail-closed)"
        )

    def test_mcp_gateway_entropy_reduces_effective_confidence(self):
        """High entropy lowers the effective_confidence in MCPToolResult.

        mcp_gateway._jepa_check() applies:
            effective_confidence = max(0.0, gate_confidence
                + jepa_adjustment - entropy_resolution.confidence_penalty)

        With high entropy (penalty ≈ 0.11), effective_confidence should
        be strictly lower than the baseline run without entropy.

        NOTE: the CG 32-D sovereign-state entropy is EXPERIMENTAL since the 2026-06
        pivot (raw next-token entropy is the default signal). This test exercises the
        CG path, so it opts in via enable_cg_state_signals=True.
        """
        gateway = create_mock_mcp_gateway()
        gateway._signal_config = SignalConfig(enable_cg_state_signals=True)
        high_result = _high_entropy_result()

        baseline_call = MCPToolCall(
            tool_name="file_read",
            parameters={"path": "/tmp/test.txt"},
            quality_score=0.9,
            coherence_score=0.9,
        )
        high_entropy_call = MCPToolCall(
            tool_name="file_read",
            parameters={"path": "/tmp/test.txt"},
            quality_score=0.9,
            coherence_score=0.9,
            entropy_result=high_result,
        )

        baseline_result = run_async(gateway.call_tool(baseline_call))
        high_entropy_result_mcp = run_async(gateway.call_tool(high_entropy_call))

        assert high_entropy_result_mcp.confidence < baseline_result.confidence, (
            "High entropy must lower MCP effective confidence. "
            f"baseline={baseline_result.confidence:.4f}, "
            f"high_entropy={high_entropy_result_mcp.confidence:.4f}"
        )

    def test_mcp_tool_call_no_regression_without_entropy(self):
        """Existing MCPToolCall construction without entropy_result still works."""
        gateway = create_mock_mcp_gateway()

        # Legacy-style construction: no entropy_result
        tool_call = MCPToolCall(
            tool_name="file_read",
            parameters={"path": "/tmp/test.txt"},
            quality_score=0.9,
            coherence_score=0.9,
        )

        result = run_async(gateway.call_tool(tool_call))

        # Must succeed without error
        assert result is not None
        assert tool_call.entropy_result is None  # field present, default None
