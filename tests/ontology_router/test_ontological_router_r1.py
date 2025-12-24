"""
Test Suite for Ontological Layer Router - R1 Relaxation
=========================================================

MANDATORY TEST COVERAGE:
    1. Determinism (100-run identical outputs)
    2. Allowlist enforcement
    3. Declared hint accepted when valid
    4. Declared hint rejected when invalid
    5. Phase boundary violations (FAIL)
    6. ABSOLVING gate enforcement
    7. Mutation detection
    8. Hash stability
    9. Forbidden import detection
    10. Replay audit (request -> response determinism)

Tests MUST fail loudly on violation.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import sys
from typing import Any, List, Set
from pathlib import Path

import pytest

from symbolu.ontology.router.ontological_router_r1 import (
    BlockedReason,
    LedgerAdapter,
    LedgerSpanInput,
    OntologicalLayer,
    OntologicalLayerRouter,
    PHASE_ALLOWED_HINTS,
    PHASE_TO_LAYER_DEFAULT,
    ProjectionBlockedError,
    ProjectionRequest,
    ProjectionResponse,
    VALID_PHASE_IDS,
    route_projection,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def router() -> OntologicalLayerRouter:
    """Create a default R1 router (ABSOLVING not permitted)."""
    return OntologicalLayerRouter(explicit_absolving_opt_in=False)


@pytest.fixture
def router_with_absolving() -> OntologicalLayerRouter:
    """Create an R1 router with ABSOLVING opt-in."""
    return OntologicalLayerRouter(explicit_absolving_opt_in=True)


@pytest.fixture
def sample_request() -> ProjectionRequest:
    """Create a sample valid request."""
    return ProjectionRequest(
        artifact_id="artifact-001",
        phase_id="3",
        artifact_hash="abc123def456",
        declared_projection_hint=None,
    )


@pytest.fixture
def all_phases() -> List[str]:
    """Return all valid phase IDs."""
    return list(VALID_PHASE_IDS)


# =============================================================================
# GROUP 1: Determinism Tests (100-run identical outputs)
# =============================================================================

class TestDeterminism:
    """Tests verifying SAME INPUT -> IDENTICAL OUTPUT (byte-for-byte)."""

    def test_determinism_100_runs_no_hint(self, router: OntologicalLayerRouter) -> None:
        """Verify 100 runs produce identical output without hint."""
        request = ProjectionRequest(
            artifact_id="det-test-001",
            phase_id="5",
            artifact_hash="hash_for_determinism_test_abc123",
        )

        first_response = router.project(request)
        for i in range(100):
            response = router.project(request)
            assert response.artifact_id == first_response.artifact_id
            assert response.artifact_hash == first_response.artifact_hash
            assert response.phase_id == first_response.phase_id
            assert response.projected_layers == first_response.projected_layers
            assert response.router_version == first_response.router_version

    def test_determinism_100_runs_with_hint(self, router: OntologicalLayerRouter) -> None:
        """Verify 100 runs produce identical output with valid hint."""
        request = ProjectionRequest(
            artifact_id="det-test-002",
            phase_id="4",
            artifact_hash="hash_for_hint_test_xyz789",
            declared_projection_hint=OntologicalLayer.THINKING,
        )

        first_response = router.project(request)
        for i in range(100):
            response = router.project(request)
            assert response == first_response, f"Run {i} produced different output"

    def test_determinism_all_phases(self, router: OntologicalLayerRouter) -> None:
        """Verify determinism across all phases."""
        for phase_id in VALID_PHASE_IDS:
            request = ProjectionRequest(
                artifact_id=f"det-phase-{phase_id}",
                phase_id=phase_id,
                artifact_hash=f"hash_{phase_id}_determinism",
            )
            first = router.project(request)
            for _ in range(10):
                result = router.project(request)
                assert result.projected_layers == first.projected_layers

    def test_determinism_ledger_span_id(self) -> None:
        """Verify ledger span ID is deterministic over 100 runs."""
        span_input = LedgerSpanInput(
            artifact_hash="stable_hash_123",
            phase_id="7",
            projected_layers=(OntologicalLayer.REASONING,),
        )
        first_span_id = LedgerAdapter.generate_span_id(span_input)
        for _ in range(100):
            span_id = LedgerAdapter.generate_span_id(span_input)
            assert span_id == first_span_id

    def test_determinism_different_layer_order_same_result(self) -> None:
        """Verify layer ordering in input doesn't affect span ID."""
        span_input_1 = LedgerSpanInput(
            artifact_hash="order_test",
            phase_id="3",
            projected_layers=(OntologicalLayer.FORMING, OntologicalLayer.THINKING),
        )
        span_input_2 = LedgerSpanInput(
            artifact_hash="order_test",
            phase_id="3",
            projected_layers=(OntologicalLayer.THINKING, OntologicalLayer.FORMING),
        )
        assert LedgerAdapter.generate_span_id(span_input_1) == \
               LedgerAdapter.generate_span_id(span_input_2)

    def test_determinism_response_fields_stable(self, router: OntologicalLayerRouter) -> None:
        """Verify all response fields are stable across runs."""
        request = ProjectionRequest(
            artifact_id="stable-001",
            phase_id="6",
            artifact_hash="stable_hash_def",
        )
        responses = [router.project(request) for _ in range(50)]
        for r in responses[1:]:
            assert r.artifact_id == responses[0].artifact_id
            assert r.artifact_hash == responses[0].artifact_hash
            assert r.phase_id == responses[0].phase_id
            assert r.projected_layers == responses[0].projected_layers
            assert r.router_version == responses[0].router_version


# =============================================================================
# GROUP 2: Allowlist Enforcement Tests
# =============================================================================

class TestAllowlistEnforcement:
    """Tests verifying strict allowlist enforcement for R1 hints."""

    def test_all_phases_have_allowlists(self) -> None:
        """Verify every valid phase has an allowlist entry."""
        for phase_id in VALID_PHASE_IDS:
            assert phase_id in PHASE_ALLOWED_HINTS, \
                f"Phase {phase_id} missing from PHASE_ALLOWED_HINTS"

    def test_all_phases_have_default_mappings(self) -> None:
        """Verify every valid phase has a default mapping."""
        for phase_id in VALID_PHASE_IDS:
            assert phase_id in PHASE_TO_LAYER_DEFAULT, \
                f"Phase {phase_id} missing from PHASE_TO_LAYER_DEFAULT"

    def test_default_layer_in_allowlist(self) -> None:
        """Verify default layer is always in the allowlist for each phase."""
        for phase_id in VALID_PHASE_IDS:
            default_layers = PHASE_TO_LAYER_DEFAULT[phase_id]
            allowed_hints = PHASE_ALLOWED_HINTS[phase_id]
            for layer in default_layers:
                # ABSOLVING is special - may be default but gated
                if layer != OntologicalLayer.ABSOLVING:
                    assert layer in allowed_hints, \
                        f"Default layer {layer} not in allowlist for phase {phase_id}"

    def test_allowlist_is_frozenset(self) -> None:
        """Verify allowlists are immutable frozensets."""
        for phase_id, hints in PHASE_ALLOWED_HINTS.items():
            assert isinstance(hints, frozenset), \
                f"Allowlist for phase {phase_id} is not a frozenset"

    def test_allowlist_contains_only_ontological_layers(self) -> None:
        """Verify allowlists contain only OntologicalLayer enums."""
        for phase_id, hints in PHASE_ALLOWED_HINTS.items():
            for hint in hints:
                assert isinstance(hint, OntologicalLayer), \
                    f"Invalid type in allowlist for phase {phase_id}: {type(hint)}"

    def test_phase_4_allows_two_hints(self, router: OntologicalLayerRouter) -> None:
        """Verify phase 4 allows both FORMING and THINKING hints."""
        # FORMING hint
        request_forming = ProjectionRequest(
            artifact_id="p4-forming",
            phase_id="4",
            artifact_hash="hash_p4_forming",
            declared_projection_hint=OntologicalLayer.FORMING,
        )
        response_forming = router.project(request_forming)
        assert response_forming.projected_layers == (OntologicalLayer.FORMING,)

        # THINKING hint
        request_thinking = ProjectionRequest(
            artifact_id="p4-thinking",
            phase_id="4",
            artifact_hash="hash_p4_thinking",
            declared_projection_hint=OntologicalLayer.THINKING,
        )
        response_thinking = router.project(request_thinking)
        assert response_thinking.projected_layers == (OntologicalLayer.THINKING,)

    def test_phase_5_allows_two_hints(self, router: OntologicalLayerRouter) -> None:
        """Verify phase 5 allows both THINKING and UNIFYING hints."""
        for hint in [OntologicalLayer.THINKING, OntologicalLayer.UNIFYING]:
            request = ProjectionRequest(
                artifact_id=f"p5-{hint.name}",
                phase_id="5",
                artifact_hash=f"hash_p5_{hint.name}",
                declared_projection_hint=hint,
            )
            response = router.project(request)
            assert response.projected_layers == (hint,)

    def test_no_absolving_in_standard_allowlists(self) -> None:
        """Verify ABSOLVING is not in any standard phase allowlist."""
        for phase_id, hints in PHASE_ALLOWED_HINTS.items():
            assert OntologicalLayer.ABSOLVING not in hints, \
                f"ABSOLVING should not be in allowlist for phase {phase_id}"


# =============================================================================
# GROUP 3: Declared Hint Accepted When Valid
# =============================================================================

class TestValidHintAccepted:
    """Tests verifying valid declared hints are accepted."""

    def test_valid_hint_phase_1b_acting(self, router: OntologicalLayerRouter) -> None:
        """Verify ACTING hint accepted for phase 1b."""
        request = ProjectionRequest(
            artifact_id="valid-1b",
            phase_id="1b",
            artifact_hash="hash_1b",
            declared_projection_hint=OntologicalLayer.ACTING,
        )
        response = router.project(request)
        assert response.projected_layers == (OntologicalLayer.ACTING,)

    def test_valid_hint_phase_2_tagging(self, router: OntologicalLayerRouter) -> None:
        """Verify TAGGING hint accepted for phase 2."""
        request = ProjectionRequest(
            artifact_id="valid-2",
            phase_id="2",
            artifact_hash="hash_2",
            declared_projection_hint=OntologicalLayer.TAGGING,
        )
        response = router.project(request)
        assert response.projected_layers == (OntologicalLayer.TAGGING,)

    def test_valid_hint_phase_3_forming(self, router: OntologicalLayerRouter) -> None:
        """Verify FORMING hint accepted for phase 3."""
        request = ProjectionRequest(
            artifact_id="valid-3",
            phase_id="3",
            artifact_hash="hash_3",
            declared_projection_hint=OntologicalLayer.FORMING,
        )
        response = router.project(request)
        assert response.projected_layers == (OntologicalLayer.FORMING,)

    def test_valid_hint_overrides_default(self, router: OntologicalLayerRouter) -> None:
        """Verify valid hint replaces default projection."""
        # Phase 4 default is FORMING, but THINKING is also allowed
        request_no_hint = ProjectionRequest(
            artifact_id="override-test",
            phase_id="4",
            artifact_hash="hash_override",
        )
        response_no_hint = router.project(request_no_hint)
        assert response_no_hint.projected_layers == (OntologicalLayer.FORMING,)

        # With THINKING hint, should override
        request_with_hint = ProjectionRequest(
            artifact_id="override-test",
            phase_id="4",
            artifact_hash="hash_override",
            declared_projection_hint=OntologicalLayer.THINKING,
        )
        response_with_hint = router.project(request_with_hint)
        assert response_with_hint.projected_layers == (OntologicalLayer.THINKING,)

    def test_hint_same_as_default_works(self, router: OntologicalLayerRouter) -> None:
        """Verify hint same as default still works."""
        request = ProjectionRequest(
            artifact_id="same-as-default",
            phase_id="6",
            artifact_hash="hash_same",
            declared_projection_hint=OntologicalLayer.DIRECTING,
        )
        response = router.project(request)
        assert response.projected_layers == (OntologicalLayer.DIRECTING,)

    def test_all_valid_hints_accepted(self, router: OntologicalLayerRouter) -> None:
        """Verify all valid hints are accepted for each phase."""
        for phase_id, allowed_hints in PHASE_ALLOWED_HINTS.items():
            for hint in allowed_hints:
                request = ProjectionRequest(
                    artifact_id=f"all-valid-{phase_id}-{hint.name}",
                    phase_id=phase_id,
                    artifact_hash=f"hash_{phase_id}_{hint.name}",
                    declared_projection_hint=hint,
                )
                response = router.project(request)
                assert response.projected_layers == (hint,), \
                    f"Hint {hint} should be accepted for phase {phase_id}"


# =============================================================================
# GROUP 4: Declared Hint Rejected When Invalid
# =============================================================================

class TestInvalidHintRejected:
    """Tests verifying invalid declared hints cause fail-closed."""

    def test_invalid_hint_phase_1b_rejected(self, router: OntologicalLayerRouter) -> None:
        """Verify non-ACTING hints rejected for phase 1b."""
        for layer in OntologicalLayer:
            if layer != OntologicalLayer.ACTING:
                request = ProjectionRequest(
                    artifact_id=f"invalid-1b-{layer.name}",
                    phase_id="1b",
                    artifact_hash="hash_invalid_1b",
                    declared_projection_hint=layer,
                )
                with pytest.raises(ProjectionBlockedError) as exc:
                    router.project(request)
                assert exc.value.reason == BlockedReason.HINT_NOT_IN_ALLOWLIST

    def test_invalid_hint_phase_2_rejected(self, router: OntologicalLayerRouter) -> None:
        """Verify non-TAGGING hints rejected for phase 2."""
        invalid_hints = [l for l in OntologicalLayer if l != OntologicalLayer.TAGGING]
        for hint in invalid_hints:
            request = ProjectionRequest(
                artifact_id=f"invalid-2-{hint.name}",
                phase_id="2",
                artifact_hash="hash_invalid_2",
                declared_projection_hint=hint,
            )
            with pytest.raises(ProjectionBlockedError) as exc:
                router.project(request)
            assert exc.value.reason in (
                BlockedReason.HINT_NOT_IN_ALLOWLIST,
                BlockedReason.ABSOLVING_NOT_PERMITTED,
            )

    def test_cross_phase_hint_rejected(self, router: OntologicalLayerRouter) -> None:
        """Verify hints valid for other phases are rejected."""
        # TAGGING is valid for phase 2, but not phase 3
        request = ProjectionRequest(
            artifact_id="cross-phase",
            phase_id="3",
            artifact_hash="hash_cross",
            declared_projection_hint=OntologicalLayer.TAGGING,
        )
        with pytest.raises(ProjectionBlockedError) as exc:
            router.project(request)
        assert exc.value.reason == BlockedReason.HINT_NOT_IN_ALLOWLIST

    def test_purposing_rejected_for_all_standard_phases(
        self, router: OntologicalLayerRouter
    ) -> None:
        """Verify PURPOSING is rejected for all phases (not in any allowlist)."""
        for phase_id in VALID_PHASE_IDS:
            request = ProjectionRequest(
                artifact_id=f"purposing-{phase_id}",
                phase_id=phase_id,
                artifact_hash=f"hash_purposing_{phase_id}",
                declared_projection_hint=OntologicalLayer.PURPOSING,
            )
            with pytest.raises(ProjectionBlockedError) as exc:
                router.project(request)
            assert exc.value.reason == BlockedReason.HINT_NOT_IN_ALLOWLIST

    def test_error_message_includes_allowed_hints(
        self, router: OntologicalLayerRouter
    ) -> None:
        """Verify error message includes allowed hints for debugging."""
        request = ProjectionRequest(
            artifact_id="error-msg-test",
            phase_id="4",
            artifact_hash="hash_error_msg",
            declared_projection_hint=OntologicalLayer.REASONING,
        )
        with pytest.raises(ProjectionBlockedError) as exc:
            router.project(request)
        error_msg = str(exc.value)
        assert "FORMING" in error_msg or "THINKING" in error_msg


# =============================================================================
# GROUP 5: Phase Boundary Violations (FAIL)
# =============================================================================

class TestPhaseBoundaryViolations:
    """Tests verifying invalid phase IDs cause fail-closed."""

    def test_invalid_phase_id_rejected(self, router: OntologicalLayerRouter) -> None:
        """Verify invalid phase IDs are rejected."""
        invalid_phases = ["0", "1", "1a", "10", "99", "abc", "", "phase1"]
        for phase_id in invalid_phases:
            if phase_id == "":
                # Empty string raises during ProjectionRequest construction
                with pytest.raises(ProjectionBlockedError) as exc:
                    ProjectionRequest(
                        artifact_id="invalid-phase",
                        phase_id=phase_id,
                        artifact_hash="hash_invalid_phase",
                    )
                assert exc.value.reason == BlockedReason.INVALID_PHASE_ID
            else:
                request = ProjectionRequest(
                    artifact_id="invalid-phase",
                    phase_id=phase_id,
                    artifact_hash="hash_invalid_phase",
                )
                with pytest.raises(ProjectionBlockedError) as exc:
                    router.project(request)
                assert exc.value.reason == BlockedReason.PHASE_NOT_IN_MAPPING

    def test_numeric_phase_id_rejected(self, router: OntologicalLayerRouter) -> None:
        """Verify numeric-only phase IDs that look valid are rejected if not in mapping."""
        request = ProjectionRequest(
            artifact_id="numeric-phase",
            phase_id="10",
            artifact_hash="hash_numeric",
        )
        with pytest.raises(ProjectionBlockedError) as exc:
            router.project(request)
        assert exc.value.reason == BlockedReason.PHASE_NOT_IN_MAPPING

    def test_whitespace_phase_id_rejected(self, router: OntologicalLayerRouter) -> None:
        """Verify whitespace-only phase IDs are handled."""
        request = ProjectionRequest(
            artifact_id="whitespace-phase",
            phase_id="  ",
            artifact_hash="hash_whitespace",
        )
        with pytest.raises(ProjectionBlockedError) as exc:
            router.project(request)
        assert exc.value.reason == BlockedReason.PHASE_NOT_IN_MAPPING

    def test_case_sensitivity(self, router: OntologicalLayerRouter) -> None:
        """Verify phase IDs are case-sensitive."""
        # "1B" should fail (only "1b" is valid)
        request = ProjectionRequest(
            artifact_id="case-test",
            phase_id="1B",
            artifact_hash="hash_case",
        )
        with pytest.raises(ProjectionBlockedError) as exc:
            router.project(request)
        assert exc.value.reason == BlockedReason.PHASE_NOT_IN_MAPPING

    def test_all_valid_phases_accepted(self, router: OntologicalLayerRouter) -> None:
        """Verify all valid phase IDs are accepted."""
        for phase_id in VALID_PHASE_IDS:
            request = ProjectionRequest(
                artifact_id=f"valid-phase-{phase_id}",
                phase_id=phase_id,
                artifact_hash=f"hash_valid_{phase_id}",
            )
            response = router.project(request)
            assert response.phase_id == phase_id


# =============================================================================
# GROUP 6: ABSOLVING Gate Enforcement
# =============================================================================

class TestAbsolvingGate:
    """Tests verifying ABSOLVING is gated and fail-closed."""

    def test_absolving_rejected_without_opt_in(
        self, router: OntologicalLayerRouter
    ) -> None:
        """Verify ABSOLVING hint rejected without opt-in."""
        request = ProjectionRequest(
            artifact_id="absolving-no-opt-in",
            phase_id="9",
            artifact_hash="hash_absolving_no_opt_in",
            declared_projection_hint=OntologicalLayer.ABSOLVING,
        )
        with pytest.raises(ProjectionBlockedError) as exc:
            router.project(request)
        # Should fail at allowlist check first (ABSOLVING not in allowlist)
        assert exc.value.reason == BlockedReason.HINT_NOT_IN_ALLOWLIST

    def test_absolving_rejected_all_phases(
        self, router: OntologicalLayerRouter
    ) -> None:
        """Verify ABSOLVING is rejected for all phases without opt-in."""
        for phase_id in VALID_PHASE_IDS:
            request = ProjectionRequest(
                artifact_id=f"absolving-{phase_id}",
                phase_id=phase_id,
                artifact_hash=f"hash_absolving_{phase_id}",
                declared_projection_hint=OntologicalLayer.ABSOLVING,
            )
            with pytest.raises(ProjectionBlockedError) as exc:
                router.project(request)
            # Should fail - either not in allowlist or no opt-in
            assert exc.value.reason in (
                BlockedReason.HINT_NOT_IN_ALLOWLIST,
                BlockedReason.ABSOLVING_NOT_PERMITTED,
            )

    def test_absolving_rejected_even_with_opt_in_if_not_in_allowlist(
        self, router_with_absolving: OntologicalLayerRouter
    ) -> None:
        """Verify ABSOLVING rejected even with opt-in if not in allowlist."""
        # ABSOLVING is not in any phase's allowlist
        for phase_id in VALID_PHASE_IDS:
            request = ProjectionRequest(
                artifact_id=f"absolving-opt-in-{phase_id}",
                phase_id=phase_id,
                artifact_hash=f"hash_absolving_opt_{phase_id}",
                declared_projection_hint=OntologicalLayer.ABSOLVING,
            )
            with pytest.raises(ProjectionBlockedError) as exc:
                router_with_absolving.project(request)
            assert exc.value.reason == BlockedReason.HINT_NOT_IN_ALLOWLIST

    def test_default_router_absolving_opt_in_false(self) -> None:
        """Verify default router has ABSOLVING opt-in disabled."""
        router = OntologicalLayerRouter()
        assert router._explicit_absolving_opt_in is False

    def test_opt_in_router_has_flag_set(self) -> None:
        """Verify opt-in router has ABSOLVING flag set."""
        router = OntologicalLayerRouter(explicit_absolving_opt_in=True)
        assert router._explicit_absolving_opt_in is True

    def test_absolving_not_reachable_via_default_projection(
        self, router: OntologicalLayerRouter
    ) -> None:
        """Verify ABSOLVING is not in any default projection."""
        for phase_id in VALID_PHASE_IDS:
            request = ProjectionRequest(
                artifact_id=f"default-{phase_id}",
                phase_id=phase_id,
                artifact_hash=f"hash_default_{phase_id}",
            )
            response = router.project(request)
            assert OntologicalLayer.ABSOLVING not in response.projected_layers


# =============================================================================
# GROUP 7: Mutation Detection Tests
# =============================================================================

class TestMutationDetection:
    """Tests verifying no mutation of request or artifacts."""

    def test_request_immutable(self) -> None:
        """Verify ProjectionRequest is frozen (immutable)."""
        request = ProjectionRequest(
            artifact_id="immutable-test",
            phase_id="3",
            artifact_hash="hash_immutable",
        )
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            request.artifact_id = "modified"  # type: ignore

    def test_response_immutable(self, router: OntologicalLayerRouter) -> None:
        """Verify ProjectionResponse is frozen (immutable)."""
        request = ProjectionRequest(
            artifact_id="response-immutable",
            phase_id="3",
            artifact_hash="hash_response_immutable",
        )
        response = router.project(request)
        with pytest.raises(Exception):  # FrozenInstanceError or AttributeError
            response.artifact_id = "modified"  # type: ignore

    def test_projected_layers_tuple_immutable(
        self, router: OntologicalLayerRouter
    ) -> None:
        """Verify projected_layers is a tuple (immutable)."""
        request = ProjectionRequest(
            artifact_id="layers-immutable",
            phase_id="3",
            artifact_hash="hash_layers",
        )
        response = router.project(request)
        assert isinstance(response.projected_layers, tuple)

    def test_request_not_modified_after_projection(
        self, router: OntologicalLayerRouter
    ) -> None:
        """Verify request is not modified by projection."""
        original_artifact_id = "no-modify-test"
        original_phase_id = "5"
        original_hash = "hash_no_modify"

        request = ProjectionRequest(
            artifact_id=original_artifact_id,
            phase_id=original_phase_id,
            artifact_hash=original_hash,
        )

        router.project(request)

        assert request.artifact_id == original_artifact_id
        assert request.phase_id == original_phase_id
        assert request.artifact_hash == original_hash

    def test_ledger_span_input_immutable(self) -> None:
        """Verify LedgerSpanInput is frozen (immutable)."""
        span_input = LedgerSpanInput(
            artifact_hash="immutable_span",
            phase_id="3",
            projected_layers=(OntologicalLayer.FORMING,),
        )
        with pytest.raises(Exception):
            span_input.artifact_hash = "modified"  # type: ignore

    def test_phase_to_layer_default_not_mutated(
        self, router: OntologicalLayerRouter
    ) -> None:
        """Verify PHASE_TO_LAYER_DEFAULT is not mutated by routing."""
        original = dict(PHASE_TO_LAYER_DEFAULT)

        for phase_id in VALID_PHASE_IDS:
            request = ProjectionRequest(
                artifact_id=f"no-mutate-{phase_id}",
                phase_id=phase_id,
                artifact_hash=f"hash_{phase_id}",
            )
            router.project(request)

        assert dict(PHASE_TO_LAYER_DEFAULT) == original


# =============================================================================
# GROUP 8: Hash Stability Tests
# =============================================================================

class TestHashStability:
    """Tests verifying hash stability across runs."""

    def test_response_hash_stable(self, router: OntologicalLayerRouter) -> None:
        """Verify response can be hashed consistently."""
        request = ProjectionRequest(
            artifact_id="hash-stable-test",
            phase_id="3",
            artifact_hash="hash_stable",
        )
        responses = [router.project(request) for _ in range(10)]

        # Compute hash of repr for stability check
        hashes = [hash(repr(r)) for r in responses]
        assert len(set(hashes)) == 1

    def test_ledger_span_id_hash_stable_100_runs(self) -> None:
        """Verify ledger span ID hash stable over 100 runs."""
        span_input = LedgerSpanInput(
            artifact_hash="stable_100",
            phase_id="7",
            projected_layers=(OntologicalLayer.REASONING,),
        )
        first_hash = LedgerAdapter.generate_span_id(span_input)
        for _ in range(100):
            current_hash = LedgerAdapter.generate_span_id(span_input)
            assert current_hash == first_hash

    def test_span_id_length_consistent(self) -> None:
        """Verify span ID length is always SPAN_ID_LENGTH."""
        for phase_id in VALID_PHASE_IDS:
            default_layers = PHASE_TO_LAYER_DEFAULT[phase_id]
            span_input = LedgerSpanInput(
                artifact_hash=f"length_test_{phase_id}",
                phase_id=phase_id,
                projected_layers=default_layers,
            )
            span_id = LedgerAdapter.generate_span_id(span_input)
            assert len(span_id) == LedgerAdapter.SPAN_ID_LENGTH

    def test_span_id_is_hex(self) -> None:
        """Verify span ID contains only hex characters."""
        span_input = LedgerSpanInput(
            artifact_hash="hex_test",
            phase_id="5",
            projected_layers=(OntologicalLayer.THINKING,),
        )
        span_id = LedgerAdapter.generate_span_id(span_input)
        assert all(c in "0123456789abcdef" for c in span_id)

    def test_different_inputs_different_hashes(self) -> None:
        """Verify different inputs produce different span IDs."""
        span_ids = set()
        for phase_id in VALID_PHASE_IDS:
            span_input = LedgerSpanInput(
                artifact_hash=f"unique_{phase_id}",
                phase_id=phase_id,
                projected_layers=PHASE_TO_LAYER_DEFAULT[phase_id],
            )
            span_ids.add(LedgerAdapter.generate_span_id(span_input))
        # All should be unique
        assert len(span_ids) == len(VALID_PHASE_IDS)

    def test_artifact_hash_affects_span_id(self) -> None:
        """Verify changing artifact_hash changes span ID."""
        span_input_1 = LedgerSpanInput(
            artifact_hash="hash_a",
            phase_id="3",
            projected_layers=(OntologicalLayer.FORMING,),
        )
        span_input_2 = LedgerSpanInput(
            artifact_hash="hash_b",
            phase_id="3",
            projected_layers=(OntologicalLayer.FORMING,),
        )
        assert LedgerAdapter.generate_span_id(span_input_1) != \
               LedgerAdapter.generate_span_id(span_input_2)


# =============================================================================
# GROUP 9: Forbidden Import Detection
# =============================================================================

class TestForbiddenImports:
    """Tests verifying no NLP/ML/LLM imports."""

    FORBIDDEN_MODULES = {
        # ML/DL frameworks
        "torch", "pytorch", "tensorflow", "tf", "keras",
        "jax", "flax", "haiku", "trax",
        # NLP libraries
        "transformers", "huggingface", "spacy", "nltk",
        "gensim", "fasttext", "flair",
        # LLM clients
        "openai", "anthropic", "cohere", "replicate",
        "langchain", "llamaindex", "llama_index",
        # Scoring/ranking
        "sklearn", "scikit-learn", "xgboost", "lightgbm",
        "catboost",
        # Probabilistic
        "pymc", "pymc3", "pyro", "numpyro", "edward",
        # Inference
        "onnx", "onnxruntime", "tensorrt", "tflite",
    }

    def test_no_forbidden_imports_in_router_module(self) -> None:
        """Verify router module has no forbidden imports."""
        from symbolu.ontology.router import ontological_router_r1
        source_file = inspect.getfile(ontological_router_r1)

        with open(source_file, "r") as f:
            source_code = f.read()

        tree = ast.parse(source_code)

        imported_modules: Set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_modules.add(node.module.split(".")[0])

        forbidden_found = imported_modules & self.FORBIDDEN_MODULES
        assert not forbidden_found, \
            f"Forbidden imports found: {forbidden_found}"

    def test_no_random_imports(self) -> None:
        """Verify no random/stochastic imports in router."""
        from symbolu.ontology.router import ontological_router_r1
        source_file = inspect.getfile(ontological_router_r1)

        with open(source_file, "r") as f:
            source_code = f.read()

        # Check for random-related imports
        forbidden_patterns = ["import random", "from random", "numpy.random"]
        for pattern in forbidden_patterns:
            assert pattern not in source_code, \
                f"Forbidden pattern found: {pattern}"

    def test_no_uuid_imports(self) -> None:
        """Verify no UUID imports (non-deterministic)."""
        from symbolu.ontology.router import ontological_router_r1
        source_file = inspect.getfile(ontological_router_r1)

        with open(source_file, "r") as f:
            source_code = f.read()

        assert "import uuid" not in source_code
        assert "from uuid" not in source_code

    def test_no_datetime_imports(self) -> None:
        """Verify no datetime imports (timestamps forbidden)."""
        from symbolu.ontology.router import ontological_router_r1
        source_file = inspect.getfile(ontological_router_r1)

        with open(source_file, "r") as f:
            source_code = f.read()

        assert "import datetime" not in source_code
        assert "from datetime" not in source_code
        assert "import time" not in source_code


# =============================================================================
# GROUP 10: Replay Audit Tests
# =============================================================================

class TestReplayAudit:
    """Tests verifying request -> response determinism for replay."""

    def test_replay_identical_request(self, router: OntologicalLayerRouter) -> None:
        """Verify replaying identical request produces identical response."""
        request = ProjectionRequest(
            artifact_id="replay-001",
            phase_id="7",
            artifact_hash="hash_replay_001",
            declared_projection_hint=OntologicalLayer.REASONING,
        )

        response_1 = router.project(request)
        response_2 = router.project(request)

        assert response_1.artifact_id == response_2.artifact_id
        assert response_1.artifact_hash == response_2.artifact_hash
        assert response_1.phase_id == response_2.phase_id
        assert response_1.projected_layers == response_2.projected_layers
        assert response_1.router_version == response_2.router_version

    def test_replay_all_phases(self, router: OntologicalLayerRouter) -> None:
        """Verify replay determinism for all phases."""
        for phase_id in VALID_PHASE_IDS:
            request = ProjectionRequest(
                artifact_id=f"replay-{phase_id}",
                phase_id=phase_id,
                artifact_hash=f"hash_replay_{phase_id}",
            )
            responses = [router.project(request) for _ in range(5)]
            for r in responses[1:]:
                assert r.projected_layers == responses[0].projected_layers

    def test_replay_with_different_routers(self) -> None:
        """Verify different router instances produce same result."""
        request = ProjectionRequest(
            artifact_id="diff-router",
            phase_id="5",
            artifact_hash="hash_diff_router",
            declared_projection_hint=OntologicalLayer.UNIFYING,
        )

        router_1 = OntologicalLayerRouter()
        router_2 = OntologicalLayerRouter()

        response_1 = router_1.project(request)
        response_2 = router_2.project(request)

        assert response_1.projected_layers == response_2.projected_layers
        assert response_1.router_version == response_2.router_version

    def test_replay_convenience_function(self) -> None:
        """Verify convenience function produces same result as router."""
        request = ProjectionRequest(
            artifact_id="convenience-test",
            phase_id="8",
            artifact_hash="hash_convenience",
        )

        router = OntologicalLayerRouter()
        response_router = router.project(request)
        response_func = route_projection(request)

        assert response_router.projected_layers == response_func.projected_layers

    def test_replay_ledger_span(self) -> None:
        """Verify ledger span replay produces identical results."""
        span_input = LedgerSpanInput(
            artifact_hash="replay_span",
            phase_id="6",
            projected_layers=(OntologicalLayer.DIRECTING,),
        )

        span_ids = [LedgerAdapter.generate_span_id(span_input) for _ in range(20)]
        assert len(set(span_ids)) == 1


# =============================================================================
# Additional Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Additional edge case tests."""

    def test_router_version_format(self, router: OntologicalLayerRouter) -> None:
        """Verify router version is R1.x format."""
        request = ProjectionRequest(
            artifact_id="version-test",
            phase_id="3",
            artifact_hash="hash_version",
        )
        response = router.project(request)
        assert response.router_version.startswith("R1.")

    def test_empty_artifact_id_rejected(self) -> None:
        """Verify empty artifact_id is rejected."""
        with pytest.raises(ProjectionBlockedError) as exc:
            ProjectionRequest(
                artifact_id="",
                phase_id="3",
                artifact_hash="hash_empty_id",
            )
        assert exc.value.reason == BlockedReason.INVALID_ARTIFACT_ID

    def test_empty_artifact_hash_rejected(self) -> None:
        """Verify empty artifact_hash is rejected."""
        with pytest.raises(ProjectionBlockedError) as exc:
            ProjectionRequest(
                artifact_id="valid-id",
                phase_id="3",
                artifact_hash="",
            )
        assert exc.value.reason == BlockedReason.INVALID_ARTIFACT_HASH

    def test_none_hint_uses_default(self, router: OntologicalLayerRouter) -> None:
        """Verify None hint uses default projection."""
        request = ProjectionRequest(
            artifact_id="none-hint",
            phase_id="7",
            artifact_hash="hash_none_hint",
            declared_projection_hint=None,
        )
        response = router.project(request)
        assert response.projected_layers == (OntologicalLayer.REASONING,)

    def test_long_artifact_id_accepted(self, router: OntologicalLayerRouter) -> None:
        """Verify long artifact IDs are accepted."""
        long_id = "a" * 1000
        request = ProjectionRequest(
            artifact_id=long_id,
            phase_id="3",
            artifact_hash="hash_long_id",
        )
        response = router.project(request)
        assert response.artifact_id == long_id

    def test_special_characters_in_hash(self, router: OntologicalLayerRouter) -> None:
        """Verify special characters in hash are handled."""
        special_hash = "hash!@#$%^&*()_+-=[]{}|;':\",./<>?"
        request = ProjectionRequest(
            artifact_id="special-hash",
            phase_id="3",
            artifact_hash=special_hash,
        )
        response = router.project(request)
        assert response.artifact_hash == special_hash

    def test_unicode_in_artifact_id(self, router: OntologicalLayerRouter) -> None:
        """Verify unicode in artifact_id is handled."""
        unicode_id = "artifact-日本語-🎉"
        request = ProjectionRequest(
            artifact_id=unicode_id,
            phase_id="3",
            artifact_hash="hash_unicode",
        )
        response = router.project(request)
        assert response.artifact_id == unicode_id


# =============================================================================
# Structural Invariant Tests
# =============================================================================

class TestStructuralInvariants:
    """Tests verifying structural invariants."""

    def test_ontological_layer_has_10_members(self) -> None:
        """Verify OntologicalLayer enum has exactly 10 members."""
        assert len(OntologicalLayer) == 10

    def test_ontological_layer_values_are_sequential(self) -> None:
        """Verify layer values are 1-10 sequential."""
        expected = list(range(1, 11))
        actual = sorted([layer.value for layer in OntologicalLayer])
        assert actual == expected

    def test_ontological_layer_names_match_spec(self) -> None:
        """Verify layer names match specification."""
        expected_names = {
            "ACTING", "TAGGING", "FORMING", "THINKING", "DIRECTING",
            "REASONING", "PURPOSING", "META_OBSERVING", "UNIFYING", "ABSOLVING",
        }
        actual_names = {layer.name for layer in OntologicalLayer}
        assert actual_names == expected_names

    def test_valid_phase_ids_match_spec(self) -> None:
        """Verify valid phase IDs match specification."""
        expected = {"1b", "2", "3", "4", "5", "6", "7", "8", "9"}
        assert VALID_PHASE_IDS == expected

    def test_projection_response_is_dataclass(self) -> None:
        """Verify ProjectionResponse is a frozen dataclass."""
        from dataclasses import is_dataclass
        assert is_dataclass(ProjectionResponse)
        assert ProjectionResponse.__dataclass_fields__

    def test_projection_request_is_dataclass(self) -> None:
        """Verify ProjectionRequest is a frozen dataclass."""
        from dataclasses import is_dataclass
        assert is_dataclass(ProjectionRequest)
        assert ProjectionRequest.__dataclass_fields__


# =============================================================================
# Additional Invariance Tests (for ~75 total)
# =============================================================================

class TestAdditionalInvariance:
    """Additional tests for complete coverage."""

    def test_blocked_reason_enum_values(self) -> None:
        """Verify BlockedReason enum has expected values."""
        expected_reasons = {
            "INVALID_ARTIFACT_ID",
            "INVALID_PHASE_ID",
            "INVALID_ARTIFACT_HASH",
            "INVALID_HINT_TYPE",
            "PHASE_NOT_IN_MAPPING",
            "HINT_NOT_IN_ALLOWLIST",
            "ABSOLVING_NOT_PERMITTED",
            "HASH_MISMATCH",
        }
        actual_reasons = {r.value for r in BlockedReason}
        assert actual_reasons == expected_reasons

    def test_route_projection_with_absolving_opt_in(self) -> None:
        """Verify route_projection convenience function with opt-in."""
        request = ProjectionRequest(
            artifact_id="opt-in-test",
            phase_id="9",
            artifact_hash="hash_opt_in",
        )
        # Should work with opt-in even though ABSOLVING not in allowlist
        response = route_projection(request, explicit_absolving_opt_in=True)
        assert response.projected_layers == (OntologicalLayer.UNIFYING,)

    def test_projection_blocked_error_has_reason(self) -> None:
        """Verify ProjectionBlockedError contains reason."""
        request = ProjectionRequest(
            artifact_id="error-reason",
            phase_id="3",
            artifact_hash="hash_error_reason",
            declared_projection_hint=OntologicalLayer.REASONING,
        )
        router = OntologicalLayerRouter()
        with pytest.raises(ProjectionBlockedError) as exc:
            router.project(request)
        assert hasattr(exc.value, 'reason')
        assert isinstance(exc.value.reason, BlockedReason)

    def test_ledger_adapter_span_id_length_constant(self) -> None:
        """Verify SPAN_ID_LENGTH is a class constant."""
        assert hasattr(LedgerAdapter, 'SPAN_ID_LENGTH')
        assert isinstance(LedgerAdapter.SPAN_ID_LENGTH, int)
        assert LedgerAdapter.SPAN_ID_LENGTH == 16

    def test_router_stateless_after_multiple_calls(self) -> None:
        """Verify router remains stateless after multiple calls."""
        router = OntologicalLayerRouter()

        for i in range(10):
            for phase_id in VALID_PHASE_IDS:
                request = ProjectionRequest(
                    artifact_id=f"stateless-{i}-{phase_id}",
                    phase_id=phase_id,
                    artifact_hash=f"hash_{i}_{phase_id}",
                )
                router.project(request)

        # Router should still work identically
        final_request = ProjectionRequest(
            artifact_id="final-test",
            phase_id="5",
            artifact_hash="hash_final",
        )
        response = router.project(final_request)
        assert response.projected_layers == (OntologicalLayer.THINKING,)
