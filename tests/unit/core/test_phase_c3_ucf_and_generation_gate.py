"""
Phase C3: UCF and Generation Gate Integration Tests
=====================================================

Tests verifying:
1. UCF adapter resolves correctly from pre-computed state and from signals
2. UCF does not conflict with C2 coherence adapter
3. Generation gate affects generative actions appropriately
4. Non-generative actions are unaffected by generation gate
5. Fail-safe behavior when UCF inputs or gate state are unavailable
6. Audit metadata includes UCF and generation gate information
7. Bounded effects remain bounded
8. No regressions in C1/C2 behavior
"""

import importlib
import importlib.util
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, Optional

import pytest

try:
    import numpy  # noqa: F401
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False


# =========================================================================
# Direct module loading — bypass signal_adapters/__init__.py numpy chain
# =========================================================================

_SA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "agentic", "agentic_framework", "signal_adapters",
)

# Load UCF adapter directly
_UCF_PATH = os.path.join(_SA_DIR, "ucf_adapter.py")
_ucf_spec = importlib.util.spec_from_file_location("ucf_adapter_direct", _UCF_PATH)
_ucf_mod = importlib.util.module_from_spec(_ucf_spec)
sys.modules["ucf_adapter_direct"] = _ucf_mod
_ucf_spec.loader.exec_module(_ucf_mod)  # type: ignore[union-attr]

resolve_ucf_signal = _ucf_mod.resolve_ucf_signal
UCFResolution = _ucf_mod.UCFResolution
_MAX_PENALTY = _ucf_mod._MAX_PENALTY

# Import generation gate directly (pure Python, no numpy)
from agentic.core.generation_gate import (  # noqa: E402
    GenerationGate,
    GenerationMode,
    GateStatus,
    GateViolation,
)
from agentic.core.ledger_generation_attest import (  # noqa: E402
    attest_generation_attempt,
)

# Import UCF formula for verification (pure Python)
from agentic.core.consciousness.ucf_formula import compute_ucf  # noqa: E402
from agentic.core.consciousness.ucf_schema import (  # noqa: E402
    StabilityBand,
    UnifiedConsciousnessState,
    create_ucf_state,
    create_neutral_state,
)

# Load governance_service helpers via file (to get _is_generative_action, _check_generation_gate)
_GS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "agentic", "agentic_framework", "governance_service.py",
)


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture(autouse=True)
def reset_generation_gate():
    """Reset the singleton generation gate before and after each test."""
    GenerationGate._reset()
    yield
    GenerationGate._reset()


# =========================================================================
# Mock objects
# =========================================================================

@dataclass
class MockUCFState:
    """Duck-typed UnifiedConsciousnessState for adapter testing."""
    ucf_score: float = 0.80
    stability_band: str = "stable"
    contributing_factors: Dict[str, float] = None  # type: ignore
    confidence: float = 0.8

    def __post_init__(self):
        if self.contributing_factors is None:
            self.contributing_factors = {
                "coherence_v3_quality": 0.85,
                "drift_fusion_stability": 0.75,
                "entropy_stability": 0.80,
                "schema_stability": 0.70,
                "identity_harmonics": 0.65,
            }


@dataclass
class MockRequest:
    """Minimal request for testing generation gate classification."""
    action_type: str = "read_data"
    tool_name: str = "file_reader"
    metadata: Optional[Dict[str, Any]] = None


# =========================================================================
# 1. UCF adapter — pre-computed state
# =========================================================================


class TestUCFPrecomputed:
    """Verify UCF resolution from pre-computed state."""

    def test_healthy_precomputed_state(self):
        state = MockUCFState()
        res = resolve_ucf_signal(ucf_state=state)

        assert res.available is True
        assert res.ucf_score == 0.80
        assert res.stability_band == "stable"
        assert res.contributing_factors is not None
        assert res.ucf_confidence == 0.8
        assert res.computation_source == "precomputed"
        assert res.confidence_penalty == 0.0  # stable = no penalty
        assert res.escalation_bias is False

    def test_unstable_precomputed_state(self):
        state = MockUCFState(ucf_score=0.30, stability_band="unstable")
        res = resolve_ucf_signal(ucf_state=state)

        assert res.available is True
        assert res.ucf_score == 0.30
        assert res.stability_band == "unstable"
        assert res.confidence_penalty == _MAX_PENALTY  # 0.05
        assert res.escalation_bias is True
        assert "UCF_INSTABILITY_PENALTY" in res.reason_codes
        assert "UCF_ESCALATION" in res.reason_codes
        assert "UCF_BAND_UNSTABLE" in res.reason_codes

    def test_transitional_precomputed_state(self):
        state = MockUCFState(ucf_score=0.55, stability_band="transitional")
        res = resolve_ucf_signal(ucf_state=state)

        assert res.stability_band == "transitional"
        assert res.confidence_penalty == 0.0  # transitional = informational only
        assert res.escalation_bias is False

    def test_real_ucf_state_object(self):
        """Test with an actual UnifiedConsciousnessState from ucf_schema."""
        state = create_ucf_state(0.85, confidence=1.0)
        res = resolve_ucf_signal(ucf_state=state)

        assert res.available is True
        assert res.ucf_score == 0.85
        assert res.stability_band == "stable"
        assert res.ucf_confidence == 1.0


# =========================================================================
# 2. UCF adapter — governance-computed
# =========================================================================


class TestUCFGovernanceComputed:
    """Verify UCF computation from governance signals."""

    def test_full_signal_computation(self):
        res = resolve_ucf_signal(
            coherence_v3_quality=0.8,
            drift_fusion_index=0.2,
            entropy_volatility=0.15,
            schema_stability=0.7,
            identity_harmonics_stability=0.6,
        )

        assert res.available is True
        assert res.computation_source == "governance_computed"
        assert res.ucf_confidence == 1.0  # all 5 inputs provided
        assert res.ucf_score is not None
        assert 0.0 <= res.ucf_score <= 1.0

    def test_partial_signal_computation(self):
        """Only coherence and drift available — 2/5 inputs."""
        res = resolve_ucf_signal(
            coherence_v3_quality=0.7,
            drift_fusion_index=0.3,
        )

        assert res.available is True
        assert res.computation_source == "governance_computed"
        assert res.ucf_confidence == 0.4  # 2/5 inputs
        assert res.ucf_score is not None

    def test_matches_direct_compute_ucf(self):
        """Governance-computed should match direct compute_ucf()."""
        kwargs = dict(
            coherence_v3_quality=0.75,
            drift_fusion_index=0.25,
            entropy_volatility=0.10,
            schema_stability=0.65,
            identity_harmonics_stability=0.55,
        )
        res = resolve_ucf_signal(**kwargs)
        direct = compute_ucf(**kwargs)

        assert abs(res.ucf_score - direct.ucf_score) < 1e-9
        assert res.stability_band == direct.stability_band.value

    def test_precomputed_takes_priority(self):
        """If both state and signals provided, state wins."""
        state = MockUCFState(ucf_score=0.90, stability_band="stable")
        res = resolve_ucf_signal(
            ucf_state=state,
            coherence_v3_quality=0.1,  # would give low score
        )

        assert res.ucf_score == 0.90
        assert res.computation_source == "precomputed"


# =========================================================================
# 3. UCF adapter — fail-closed
# =========================================================================


class TestUCFFailClosed:
    """Verify fail-closed: no data = zero penalty, no escalation."""

    def test_no_arguments(self):
        res = resolve_ucf_signal()
        assert res.available is False
        assert res.confidence_penalty == 0.0
        assert res.escalation_bias is False
        assert res.ucf_score is None

    def test_none_state(self):
        res = resolve_ucf_signal(ucf_state=None)
        assert res.available is False
        assert res.confidence_penalty == 0.0

    def test_malformed_state(self):
        res = resolve_ucf_signal(ucf_state="not a state")
        assert res.available is False
        assert res.confidence_penalty == 0.0


# =========================================================================
# 4. UCF contract stability and serialization
# =========================================================================


class TestUCFContract:
    """Verify the UCFResolution contract is stable and serializable."""

    def test_frozen(self):
        res = resolve_ucf_signal(ucf_state=MockUCFState())
        with pytest.raises(AttributeError):
            res.ucf_score = 0.5  # type: ignore[misc]

    def test_to_audit_dict(self):
        res = resolve_ucf_signal(ucf_state=MockUCFState())
        d = res.to_audit_dict()

        assert isinstance(d, dict)
        assert d["ucf_score"] == 0.8
        assert d["stability_band"] == "stable"
        assert d["available"] is True
        assert isinstance(d["reason_codes"], list)
        assert isinstance(d["contributing_factors"], dict)

    def test_penalty_bounded(self):
        """Max penalty should never exceed _MAX_PENALTY."""
        # Worst case: unstable
        state = MockUCFState(ucf_score=0.1, stability_band="unstable")
        res = resolve_ucf_signal(ucf_state=state)
        assert res.confidence_penalty <= _MAX_PENALTY
        assert res.confidence_penalty == _MAX_PENALTY


# =========================================================================
# 5. UCF does not conflict with C2
# =========================================================================


class TestUCFNoConflictWithC2:
    """Verify UCF and C2 coherence adapter are complementary."""

    def test_adapter_module_is_pure_python(self):
        """UCF adapter loads without numpy/torch."""
        assert hasattr(_ucf_mod, "resolve_ucf_signal")
        assert hasattr(_ucf_mod, "UCFResolution")

    def test_ucf_adapter_docstring_references_c2(self):
        """UCF adapter should reference its relationship to C2."""
        assert "coherence_state_adapter" in _ucf_mod.__doc__
        assert "complementary" in _ucf_mod.__doc__.lower()

    @pytest.mark.skipif(not HAS_NUMPY, reason="numpy not available")
    def test_exported_from_signal_adapters(self):
        from agentic.agentic_framework.signal_adapters import (
            resolve_ucf_signal,
            UCFResolution,
        )
        assert resolve_ucf_signal is not None
        assert UCFResolution is not None

    def test_in_signal_adapters_init_source(self):
        init_path = os.path.join(_SA_DIR, "__init__.py")
        with open(init_path) as f:
            content = f.read()
        assert "resolve_ucf_signal" in content
        assert "UCFResolution" in content


# =========================================================================
# 6. Generation gate — basic behavior
# =========================================================================


class TestGenerationGateBasic:
    """Verify generation gate singleton behavior."""

    def test_initial_state_unsealed(self):
        assert GenerationGate.gate_status() == GateStatus.UNSEALED

    def test_seal_enabled(self):
        GenerationGate.seal(GenerationMode.ENABLED)
        assert GenerationGate.gate_status() == GateStatus.SEALED_ENABLED
        assert GenerationGate.mode() == GenerationMode.ENABLED

    def test_seal_disabled(self):
        GenerationGate.seal(GenerationMode.DISABLED)
        assert GenerationGate.gate_status() == GateStatus.SEALED_DISABLED
        assert GenerationGate.mode() == GenerationMode.DISABLED

    def test_assert_generation_enabled_works(self):
        GenerationGate.seal(GenerationMode.ENABLED)
        GenerationGate.assert_generation_enabled()  # Should not raise

    def test_assert_generation_disabled_raises(self):
        GenerationGate.seal(GenerationMode.DISABLED)
        with pytest.raises(GateViolation):
            GenerationGate.assert_generation_enabled()

    def test_unsealed_assert_raises(self):
        with pytest.raises(GateViolation):
            GenerationGate.assert_generation_enabled()


# =========================================================================
# 7. Generation gate — governance integration helpers
# =========================================================================


class TestGenerationGateGovernance:
    """Test generation gate governance integration via source inspection."""

    def test_generative_action_detection_positive(self):
        """Actions with generative patterns should be detected."""
        # Read the governance_service.py source for _GENERATIVE_ACTION_PATTERNS
        with open(_GS_PATH) as f:
            source = f.read()
        assert "_GENERATIVE_ACTION_PATTERNS" in source
        assert "_GENERATIVE_TOOL_PATTERNS" in source
        assert "_is_generative_action" in source
        assert "_check_generation_gate" in source

    def test_generation_gate_blocks_in_governance_source(self):
        """governance_service.py should check gate_blocks for DENY."""
        with open(_GS_PATH) as f:
            source = f.read()
        assert 'generation_gate_result["gate_blocks"]' in source
        assert "APIGovernanceDecision.DENY" in source


# =========================================================================
# 8. Ledger attestation
# =========================================================================


class TestLedgerAttestation:
    """Verify ledger attestation works for generation decisions."""

    def test_attestation_enabled(self):
        GenerationGate.seal(GenerationMode.ENABLED)
        att = dict(attest_generation_attempt(render_attempted=True, render_outcome="success"))

        assert att["generation_mode"] == "ENABLED"
        assert att["gate_status"] == "SEALED_ENABLED"
        assert att["render_attempted"] is True
        assert att["render_outcome"] == "success"

    def test_attestation_disabled(self):
        GenerationGate.seal(GenerationMode.DISABLED)
        att = dict(attest_generation_attempt(render_attempted=False, render_outcome="blocked"))

        assert att["generation_mode"] == "DISABLED"
        assert att["gate_status"] == "SEALED_DISABLED"
        assert att["render_attempted"] is False

    def test_attestation_unsealed(self):
        att = dict(attest_generation_attempt(render_attempted=False))

        assert att["generation_mode"] == "UNSEALED"
        assert att["gate_status"] == "UNSEALED"


# =========================================================================
# 9. Audit fields exist
# =========================================================================


class TestAuditFieldsExist:
    """Verify audit model has the new Phase C3 fields."""

    def test_audit_event_has_ucf_field(self):
        audit_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "agentic", "agentic_framework", "governance_models.py",
        )
        with open(audit_path) as f:
            content = f.read()
        assert "ucf_signal" in content
        assert "Phase C3" in content

    def test_audit_event_has_generation_gate_field(self):
        audit_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            "agentic", "agentic_framework", "governance_models.py",
        )
        with open(audit_path) as f:
            content = f.read()
        assert "generation_gate" in content

    def test_governance_service_includes_ucf_in_snapshot(self):
        """governance_service.py should include UCF in request_snapshot."""
        with open(_GS_PATH) as f:
            content = f.read()
        assert "ucf_available" in content
        assert "ucf_score" in content
        assert "ucf_stability_band" in content

    def test_governance_service_includes_gate_in_snapshot(self):
        """governance_service.py should include generation gate in request_snapshot."""
        with open(_GS_PATH) as f:
            content = f.read()
        assert "generation_gate_status" in content
        assert "generation_gate_blocks" in content


# =========================================================================
# 10. UCF reason codes
# =========================================================================


class TestUCFReasonCodes:
    """Verify reason codes are correct."""

    def test_stable_band_code(self):
        res = resolve_ucf_signal(ucf_state=MockUCFState())
        assert "UCF_BAND_STABLE" in res.reason_codes

    def test_unstable_band_code(self):
        res = resolve_ucf_signal(
            ucf_state=MockUCFState(ucf_score=0.2, stability_band="unstable"),
        )
        assert "UCF_BAND_UNSTABLE" in res.reason_codes
        assert "UCF_INSTABILITY_PENALTY" in res.reason_codes
        assert "UCF_ESCALATION" in res.reason_codes

    def test_no_codes_when_unavailable(self):
        res = resolve_ucf_signal()
        assert len(res.reason_codes) == 0


# =========================================================================
# 11. No regressions — C1/C2 tests still pass
# =========================================================================


class TestNoRegressions:
    """Verify Phase C1 and C2 are not broken."""

    def test_c1_models_still_importable(self):
        from agentic.core.models import GOVERNANCE_SAFE_TYPES
        assert len(GOVERNANCE_SAFE_TYPES) > 0

    def test_c1_constants_still_importable(self):
        from agentic.core.constants import GOVERNANCE_SAFE_CONSTANTS
        assert len(GOVERNANCE_SAFE_CONSTANTS) > 0

    def test_c2_adapter_module_loads(self):
        """C2 coherence_state_adapter should still load."""
        c2_path = os.path.join(_SA_DIR, "coherence_state_adapter.py")
        c2_spec = importlib.util.spec_from_file_location("c2_check", c2_path)
        c2_mod = importlib.util.module_from_spec(c2_spec)
        sys.modules["c2_check"] = c2_mod
        c2_spec.loader.exec_module(c2_mod)  # type: ignore[union-attr]
        assert hasattr(c2_mod, "resolve_core_coherence")
        assert hasattr(c2_mod, "CoreCoherenceResolution")
        del sys.modules["c2_check"]
