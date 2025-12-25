"""
Test Suite for Layer Visibility Policy (Exposure Gate) v1
==========================================================

Test Requirements:
    - 100-run determinism test (identical output)
    - Unknown role → deny all
    - Requested layer outside policy → deny all
    - ABSOLVING blocked by default
    - Immutability enforcement
    - No forbidden imports regression test
    - Same input → identical decision_hash

Constraints:
    - No snapshot testing
    - No mocks
    - No randomness
"""

from __future__ import annotations

import ast
import copy
import sys
from pathlib import Path

import pytest

from symbolu.ontology.layers.ontology_layer import (
    GATED_LAYERS,
    OntologicalLayer,
)
from symbolu.ontology.contracts.projection_contract import (
    ProjectionResponse,
    create_success_response,
)
from symbolu.policy.layer_visibility_policy import (
    DEFAULT_POLICY,
    LAYER_VISIBILITY_INVARIANTS,
    ExposureDecision,
    ExposureGate,
    ExposureRequest,
    ExposureResponse,
    LayerVisibilityPolicy,
    RoleId,
    compute_decision_hash,
    create_exposure_gate,
    create_exposure_request,
)


# =============================================================================
# Test Fixtures
# =============================================================================

def make_projection_response(
    layers: tuple[OntologicalLayer, ...],
) -> ProjectionResponse:
    """Create a ProjectionResponse with specified layers."""
    return create_success_response(
        layers=layers,
        artifacts=(),
        ledger_spans=(),
    )


def make_exposure_request(
    artifact_id: str = "test_artifact",
    span_id: str = "0" * 16,
    role_id: RoleId = RoleId.END_USER,
    requested_layers: tuple[OntologicalLayer, ...] | None = None,
) -> ExposureRequest:
    """Create an ExposureRequest with specified parameters."""
    return ExposureRequest(
        artifact_id=artifact_id,
        span_id=span_id,
        role_id=role_id,
        requested_layers=requested_layers,
    )


# =============================================================================
# Invariants Tests
# =============================================================================

class TestInvariants:
    """Test that all invariants are declared and hold."""

    def test_invariants_declared(self) -> None:
        """All required invariants must be declared."""
        required_invariants = {
            "DETERMINISTIC",
            "FAIL_CLOSED",
            "READ_ONLY",
            "NO_GENERATION",
            "NO_SEMANTICS",
            "HASH_STABLE",
            "STRUCTURAL_ONLY",
        }
        assert set(LAYER_VISIBILITY_INVARIANTS.keys()) == required_invariants

    def test_all_invariants_true(self) -> None:
        """All invariants must be True."""
        for key, value in LAYER_VISIBILITY_INVARIANTS.items():
            assert value is True, f"Invariant {key} is not True"


# =============================================================================
# Determinism Tests (100 runs)
# =============================================================================

class TestDeterminism:
    """Test 100-run determinism (identical output)."""

    def test_compute_decision_hash_100_runs(self) -> None:
        """Decision hash computation produces identical output over 100 runs."""
        params = {
            "artifact_id": "test_artifact",
            "span_id": "0" * 16,
            "role_id": RoleId.END_USER,
            "effective_layers": (OntologicalLayer.EXECUTION, OntologicalLayer.IDENTITY),
        }

        first_hash = compute_decision_hash(**params)
        for _ in range(99):
            result_hash = compute_decision_hash(**params)
            assert result_hash == first_hash

    def test_evaluate_100_runs(self) -> None:
        """ExposureGate.evaluate produces identical output over 100 runs."""
        gate = create_exposure_gate()

        projection = make_projection_response(
            layers=(OntologicalLayer.EXECUTION, OntologicalLayer.IDENTITY)
        )
        request = make_exposure_request(
            role_id=RoleId.END_USER,
            requested_layers=(OntologicalLayer.EXECUTION,),
        )

        first_result = gate.evaluate(projection, request)
        for _ in range(99):
            result = gate.evaluate(projection, request)
            assert result.allowed_layers == first_result.allowed_layers
            assert result.denied_layers == first_result.denied_layers
            assert result.effective_layers == first_result.effective_layers
            assert result.decision_hash == first_result.decision_hash

    def test_decision_hash_identical_across_runs(self) -> None:
        """Same input produces identical decision_hash over 100 runs."""
        gate = create_exposure_gate()

        projection = make_projection_response(
            layers=(
                OntologicalLayer.STRUCTURE,
                OntologicalLayer.COGNITION,
                OntologicalLayer.AGENCY,
            )
        )
        request = make_exposure_request(
            artifact_id="determinism_test",
            span_id="a" * 16,
            role_id=RoleId.DEVELOPER,
            requested_layers=(OntologicalLayer.STRUCTURE, OntologicalLayer.COGNITION),
        )

        first_response = gate.evaluate(projection, request)
        for _ in range(99):
            response = gate.evaluate(projection, request)
            assert response.decision_hash == first_response.decision_hash

    def test_evaluate_implicit_layers_100_runs(self) -> None:
        """Implicit layer computation produces identical output over 100 runs."""
        gate = create_exposure_gate()

        projection = make_projection_response(
            layers=(
                OntologicalLayer.EXECUTION,
                OntologicalLayer.IDENTITY,
                OntologicalLayer.STRUCTURE,
            )
        )
        request = make_exposure_request(
            role_id=RoleId.END_USER,
            requested_layers=None,  # Implicit
        )

        first_result = gate.evaluate(projection, request)
        for _ in range(99):
            result = gate.evaluate(projection, request)
            assert result.effective_layers == first_result.effective_layers
            assert result.decision_hash == first_result.decision_hash


# =============================================================================
# Unknown Role Tests (Fail-Closed)
# =============================================================================

class TestUnknownRole:
    """Test that unknown roles result in deny all."""

    def test_unknown_role_in_custom_policy_deny_all(self) -> None:
        """Unknown role in custom policy results in deny all."""
        # Create policy without END_USER
        custom_policy = LayerVisibilityPolicy(
            role_allowed_layers=(
                (RoleId.DEVELOPER, frozenset({OntologicalLayer.EXECUTION})),
            )
        )

        gate = ExposureGate(policy=custom_policy)

        projection = make_projection_response(
            layers=(OntologicalLayer.EXECUTION,)
        )
        request = make_exposure_request(
            role_id=RoleId.END_USER,  # Not in policy
            requested_layers=(OntologicalLayer.EXECUTION,),
        )

        response = gate.evaluate(projection, request)

        assert response.allowed_layers == ()
        assert response.denied_layers == ()
        assert response.effective_layers == ()

    def test_empty_policy_deny_all(self) -> None:
        """Empty policy results in deny all for any role."""
        empty_policy = LayerVisibilityPolicy(role_allowed_layers=())

        gate = ExposureGate(policy=empty_policy)

        projection = make_projection_response(
            layers=(OntologicalLayer.EXECUTION,)
        )
        request = make_exposure_request(
            role_id=RoleId.SYSTEM,
            requested_layers=(OntologicalLayer.EXECUTION,),
        )

        response = gate.evaluate(projection, request)

        assert response.effective_layers == ()


# =============================================================================
# Requested Layer Outside Policy Tests
# =============================================================================

class TestRequestedLayerOutsidePolicy:
    """Test that requesting layers outside policy results in deny all."""

    def test_layer_outside_policy_deny_all(self) -> None:
        """Requesting a layer outside policy results in deny all."""
        # Policy only allows ACTING for END_USER
        custom_policy = LayerVisibilityPolicy(
            role_allowed_layers=(
                (RoleId.END_USER, frozenset({OntologicalLayer.EXECUTION})),
            )
        )

        gate = ExposureGate(policy=custom_policy)

        projection = make_projection_response(
            layers=(OntologicalLayer.EXECUTION, OntologicalLayer.IDENTITY)
        )
        request = make_exposure_request(
            role_id=RoleId.END_USER,
            requested_layers=(OntologicalLayer.EXECUTION, OntologicalLayer.IDENTITY),
        )

        response = gate.evaluate(projection, request)

        # TAGGING is outside policy -> deny ALL
        assert response.allowed_layers == ()
        assert response.effective_layers == ()

    def test_single_invalid_layer_deny_all(self) -> None:
        """Single invalid layer in request results in deny all."""
        gate = create_exposure_gate()

        projection = make_projection_response(
            layers=(OntologicalLayer.EXECUTION, OntologicalLayer.ABSOLVING)
        )
        # END_USER cannot access ABSOLVING in default policy
        request = make_exposure_request(
            role_id=RoleId.END_USER,
            requested_layers=(OntologicalLayer.EXECUTION, OntologicalLayer.ABSOLVING),
        )

        response = gate.evaluate(projection, request)

        assert response.effective_layers == ()

    def test_all_valid_layers_succeed(self) -> None:
        """All valid layers in request succeeds."""
        gate = create_exposure_gate()

        projection = make_projection_response(
            layers=(OntologicalLayer.EXECUTION, OntologicalLayer.IDENTITY)
        )
        request = make_exposure_request(
            role_id=RoleId.END_USER,
            requested_layers=(OntologicalLayer.EXECUTION, OntologicalLayer.IDENTITY),
        )

        response = gate.evaluate(projection, request)

        assert OntologicalLayer.EXECUTION in response.effective_layers
        assert OntologicalLayer.IDENTITY in response.effective_layers


# =============================================================================
# ABSOLVING Gated Layer Tests
# =============================================================================

class TestAbsolvingGated:
    """Test that ABSOLVING is blocked by default."""

    def test_absolving_blocked_for_end_user(self) -> None:
        """ABSOLVING is blocked for END_USER in default policy."""
        gate = create_exposure_gate()

        projection = make_projection_response(
            layers=(OntologicalLayer.EXECUTION, OntologicalLayer.ABSOLVING)
        )
        request = make_exposure_request(
            role_id=RoleId.END_USER,
            requested_layers=(OntologicalLayer.ABSOLVING,),
        )

        response = gate.evaluate(projection, request)

        assert OntologicalLayer.ABSOLVING not in response.effective_layers
        assert response.effective_layers == ()

    def test_absolving_blocked_for_developer(self) -> None:
        """ABSOLVING is blocked for DEVELOPER in default policy."""
        gate = create_exposure_gate()

        projection = make_projection_response(
            layers=(OntologicalLayer.EXECUTION, OntologicalLayer.ABSOLVING)
        )
        request = make_exposure_request(
            role_id=RoleId.DEVELOPER,
            requested_layers=(OntologicalLayer.ABSOLVING,),
        )

        response = gate.evaluate(projection, request)

        assert OntologicalLayer.ABSOLVING not in response.effective_layers

    def test_absolving_allowed_for_auditor_explicit(self) -> None:
        """ABSOLVING is allowed for AUDITOR when explicitly requested."""
        gate = create_exposure_gate()

        projection = make_projection_response(
            layers=(OntologicalLayer.EXECUTION, OntologicalLayer.ABSOLVING)
        )
        request = make_exposure_request(
            role_id=RoleId.AUDITOR,
            requested_layers=(OntologicalLayer.ABSOLVING,),
        )

        response = gate.evaluate(projection, request)

        assert OntologicalLayer.ABSOLVING in response.effective_layers

    def test_absolving_allowed_for_system_explicit(self) -> None:
        """ABSOLVING is allowed for SYSTEM when explicitly requested."""
        gate = create_exposure_gate()

        projection = make_projection_response(
            layers=(OntologicalLayer.ABSOLVING,)
        )
        request = make_exposure_request(
            role_id=RoleId.SYSTEM,
            requested_layers=(OntologicalLayer.ABSOLVING,),
        )

        response = gate.evaluate(projection, request)

        assert OntologicalLayer.ABSOLVING in response.effective_layers

    def test_absolving_not_implicitly_included(self) -> None:
        """ABSOLVING is NOT included in implicit requests even for AUDITOR."""
        gate = create_exposure_gate()

        projection = make_projection_response(
            layers=(OntologicalLayer.EXECUTION, OntologicalLayer.ABSOLVING)
        )
        request = make_exposure_request(
            role_id=RoleId.AUDITOR,
            requested_layers=None,  # Implicit
        )

        response = gate.evaluate(projection, request)

        # ABSOLVING should NOT be in effective layers for implicit request
        assert OntologicalLayer.ABSOLVING not in response.effective_layers
        assert OntologicalLayer.EXECUTION in response.effective_layers

    def test_absolving_requires_explicit_request_and_policy(self) -> None:
        """ABSOLVING requires both explicit request AND policy allowlist."""
        # Create policy without ABSOLVING for AUDITOR
        custom_policy = LayerVisibilityPolicy(
            role_allowed_layers=(
                (RoleId.AUDITOR, frozenset({OntologicalLayer.EXECUTION})),
            )
        )

        gate = ExposureGate(policy=custom_policy)

        projection = make_projection_response(
            layers=(OntologicalLayer.EXECUTION, OntologicalLayer.ABSOLVING)
        )
        request = make_exposure_request(
            role_id=RoleId.AUDITOR,
            requested_layers=(OntologicalLayer.ABSOLVING,),  # Explicit but not in policy
        )

        response = gate.evaluate(projection, request)

        # Should be denied - not in policy
        assert response.effective_layers == ()

    def test_gated_layers_constant_is_absolving(self) -> None:
        """GATED_LAYERS constant contains only ABSOLVING."""
        assert GATED_LAYERS == frozenset({OntologicalLayer.ABSOLVING})


# =============================================================================
# Immutability Enforcement Tests
# =============================================================================

class TestImmutability:
    """Test that all contracts enforce immutability."""

    def test_exposure_request_frozen(self) -> None:
        """ExposureRequest is frozen (immutable)."""
        request = make_exposure_request()

        with pytest.raises(AttributeError):
            request.artifact_id = "new_value"  # type: ignore

    def test_exposure_response_frozen(self) -> None:
        """ExposureResponse is frozen (immutable)."""
        response = ExposureResponse(
            allowed_layers=(),
            denied_layers=(),
            effective_layers=(),
            decision_hash="0" * 16,
        )

        with pytest.raises(AttributeError):
            response.decision_hash = "new_value"  # type: ignore

    def test_layer_visibility_policy_frozen(self) -> None:
        """LayerVisibilityPolicy is frozen (immutable)."""
        policy = LayerVisibilityPolicy(
            role_allowed_layers=((RoleId.END_USER, frozenset()),)
        )

        with pytest.raises(AttributeError):
            policy.role_allowed_layers = ()  # type: ignore

    def test_projection_response_not_mutated(self) -> None:
        """ProjectionResponse is not mutated by evaluate."""
        gate = create_exposure_gate()

        original_layers = (OntologicalLayer.EXECUTION, OntologicalLayer.IDENTITY)
        projection = make_projection_response(layers=original_layers)

        # Store original values
        original_projection_layers = projection.layers

        request = make_exposure_request(
            requested_layers=(OntologicalLayer.EXECUTION,)
        )

        gate.evaluate(projection, request)

        # Verify projection was not mutated
        assert projection.layers == original_projection_layers

    def test_exposure_request_not_mutated(self) -> None:
        """ExposureRequest is not mutated by evaluate."""
        gate = create_exposure_gate()

        projection = make_projection_response(
            layers=(OntologicalLayer.EXECUTION,)
        )
        request = make_exposure_request(
            artifact_id="test_artifact",
            span_id="a" * 16,
            role_id=RoleId.END_USER,
            requested_layers=(OntologicalLayer.EXECUTION,),
        )

        # Store original values
        original_artifact_id = request.artifact_id
        original_span_id = request.span_id
        original_role_id = request.role_id
        original_requested_layers = request.requested_layers

        gate.evaluate(projection, request)

        # Verify request was not mutated
        assert request.artifact_id == original_artifact_id
        assert request.span_id == original_span_id
        assert request.role_id == original_role_id
        assert request.requested_layers == original_requested_layers


# =============================================================================
# Forbidden Imports Regression Tests
# =============================================================================

class TestForbiddenImports:
    """Test that no forbidden imports are used."""

    FORBIDDEN_MODULES = {
        "random",
        "uuid",
        "datetime",
        "time",
        # ML / NLP / LLM libraries
        "torch",
        "tensorflow",
        "transformers",
        "sklearn",
        "numpy",  # Not strictly forbidden but good to check
        "pandas",
        "openai",
        "anthropic",
    }

    def test_no_forbidden_imports_in_module(self) -> None:
        """layer_visibility_policy.py does not import forbidden modules."""
        module_path = (
            Path(__file__).parent.parent
            / "symbolu"
            / "policy"
            / "layer_visibility_policy.py"
        )

        with open(module_path, "r", encoding="utf-8") as f:
            source = f.read()

        tree = ast.parse(source)

        imported_modules: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_modules.add(node.module.split(".")[0])

        forbidden_found = imported_modules & self.FORBIDDEN_MODULES
        assert len(forbidden_found) == 0, f"Forbidden imports found: {forbidden_found}"

    def test_random_not_used_at_runtime(self) -> None:
        """random module is not used at runtime."""
        # Check that random is not in sys.modules after importing our module
        # First, ensure our module is imported
        from symbolu.policy import layer_visibility_policy  # noqa: F401

        # Check if random was imported by our module
        # Note: random might be imported by other modules, so we just check our module doesn't use it
        assert "random" not in dir(layer_visibility_policy)

    def test_uuid_not_used_at_runtime(self) -> None:
        """uuid module is not used at runtime."""
        from symbolu.policy import layer_visibility_policy  # noqa: F401

        assert "uuid" not in dir(layer_visibility_policy)

    def test_datetime_not_used_at_runtime(self) -> None:
        """datetime module is not used at runtime."""
        from symbolu.policy import layer_visibility_policy  # noqa: F401

        assert "datetime" not in dir(layer_visibility_policy)


# =============================================================================
# Hash Stability Tests
# =============================================================================

class TestHashStability:
    """Test that hash computation is stable and deterministic."""

    def test_decision_hash_length(self) -> None:
        """Decision hash is exactly 16 characters."""
        hash_value = compute_decision_hash(
            artifact_id="test",
            span_id="0" * 16,
            role_id=RoleId.END_USER,
            effective_layers=(OntologicalLayer.EXECUTION,),
        )

        assert len(hash_value) == 16

    def test_decision_hash_hex_chars(self) -> None:
        """Decision hash contains only hex characters."""
        hash_value = compute_decision_hash(
            artifact_id="test",
            span_id="0" * 16,
            role_id=RoleId.END_USER,
            effective_layers=(OntologicalLayer.EXECUTION,),
        )

        assert all(c in "0123456789abcdef" for c in hash_value)

    def test_same_input_same_hash(self) -> None:
        """Same input produces identical hash."""
        params = {
            "artifact_id": "hash_test",
            "span_id": "b" * 16,
            "role_id": RoleId.DEVELOPER,
            "effective_layers": (OntologicalLayer.COGNITION, OntologicalLayer.REASONING),
        }

        hash1 = compute_decision_hash(**params)
        hash2 = compute_decision_hash(**params)

        assert hash1 == hash2

    def test_different_input_different_hash(self) -> None:
        """Different input produces different hash."""
        hash1 = compute_decision_hash(
            artifact_id="test1",
            span_id="0" * 16,
            role_id=RoleId.END_USER,
            effective_layers=(OntologicalLayer.EXECUTION,),
        )

        hash2 = compute_decision_hash(
            artifact_id="test2",
            span_id="0" * 16,
            role_id=RoleId.END_USER,
            effective_layers=(OntologicalLayer.EXECUTION,),
        )

        assert hash1 != hash2

    def test_layer_order_does_not_affect_hash(self) -> None:
        """Layer order in effective_layers does not affect hash (sorted internally)."""
        hash1 = compute_decision_hash(
            artifact_id="test",
            span_id="0" * 16,
            role_id=RoleId.END_USER,
            effective_layers=(OntologicalLayer.EXECUTION, OntologicalLayer.IDENTITY),
        )

        hash2 = compute_decision_hash(
            artifact_id="test",
            span_id="0" * 16,
            role_id=RoleId.END_USER,
            effective_layers=(OntologicalLayer.IDENTITY, OntologicalLayer.EXECUTION),
        )

        assert hash1 == hash2

    def test_response_hash_matches_recomputed(self) -> None:
        """Response decision_hash matches recomputed hash."""
        gate = create_exposure_gate()

        projection = make_projection_response(
            layers=(OntologicalLayer.EXECUTION, OntologicalLayer.STRUCTURE)
        )
        request = make_exposure_request(
            artifact_id="recompute_test",
            span_id="c" * 16,
            role_id=RoleId.END_USER,
            requested_layers=(OntologicalLayer.EXECUTION,),
        )

        response = gate.evaluate(projection, request)

        recomputed_hash = compute_decision_hash(
            artifact_id=request.artifact_id,
            span_id=request.span_id,
            role_id=request.role_id,
            effective_layers=response.effective_layers,
        )

        assert response.decision_hash == recomputed_hash


# =============================================================================
# Policy Tests
# =============================================================================

class TestLayerVisibilityPolicy:
    """Test LayerVisibilityPolicy behavior."""

    def test_get_allowed_layers_returns_correct_layers(self) -> None:
        """get_allowed_layers returns correct layers for role."""
        allowed = DEFAULT_POLICY.get_allowed_layers(RoleId.END_USER)

        assert OntologicalLayer.EXECUTION in allowed
        assert OntologicalLayer.IDENTITY in allowed
        assert OntologicalLayer.ABSOLVING not in allowed

    def test_get_allowed_layers_unknown_role(self) -> None:
        """get_allowed_layers returns empty frozenset for unknown role."""
        # Create policy without END_USER
        policy = LayerVisibilityPolicy(
            role_allowed_layers=(
                (RoleId.DEVELOPER, frozenset({OntologicalLayer.EXECUTION})),
            )
        )

        allowed = policy.get_allowed_layers(RoleId.END_USER)

        assert allowed == frozenset()

    def test_is_layer_allowed(self) -> None:
        """is_layer_allowed returns correct boolean."""
        assert DEFAULT_POLICY.is_layer_allowed(RoleId.END_USER, OntologicalLayer.EXECUTION) is True
        assert DEFAULT_POLICY.is_layer_allowed(RoleId.END_USER, OntologicalLayer.ABSOLVING) is False
        assert DEFAULT_POLICY.is_layer_allowed(RoleId.AUDITOR, OntologicalLayer.ABSOLVING) is True

    def test_default_policy_roles(self) -> None:
        """Default policy has all four roles."""
        roles_in_policy = {role for role, _ in DEFAULT_POLICY.role_allowed_layers}

        assert RoleId.END_USER in roles_in_policy
        assert RoleId.DEVELOPER in roles_in_policy
        assert RoleId.AUDITOR in roles_in_policy
        assert RoleId.SYSTEM in roles_in_policy


# =============================================================================
# ExposureGate Tests
# =============================================================================

class TestExposureGate:
    """Test ExposureGate behavior."""

    def test_default_policy_used(self) -> None:
        """Default policy is used when none specified."""
        gate = create_exposure_gate()

        assert gate.policy is DEFAULT_POLICY

    def test_custom_policy_used(self) -> None:
        """Custom policy is used when specified."""
        custom_policy = LayerVisibilityPolicy(
            role_allowed_layers=((RoleId.END_USER, frozenset()),)
        )

        gate = create_exposure_gate(policy=custom_policy)

        assert gate.policy is custom_policy

    def test_evaluate_returns_exposure_response(self) -> None:
        """evaluate returns ExposureResponse."""
        gate = create_exposure_gate()

        projection = make_projection_response(
            layers=(OntologicalLayer.EXECUTION,)
        )
        request = make_exposure_request()

        response = gate.evaluate(projection, request)

        assert isinstance(response, ExposureResponse)

    def test_effective_layers_subset_of_projected(self) -> None:
        """effective_layers is always subset of projected layers."""
        gate = create_exposure_gate()

        projected = (OntologicalLayer.EXECUTION, OntologicalLayer.IDENTITY)
        projection = make_projection_response(layers=projected)

        request = make_exposure_request(
            requested_layers=(
                OntologicalLayer.EXECUTION,
                OntologicalLayer.IDENTITY,
                OntologicalLayer.STRUCTURE,  # Not in projection
            )
        )

        response = gate.evaluate(projection, request)

        for layer in response.effective_layers:
            assert layer in projected

    def test_denied_layers_complement_of_effective(self) -> None:
        """denied_layers contains layers that were requested but not effective."""
        gate = create_exposure_gate()

        projection = make_projection_response(
            layers=(OntologicalLayer.EXECUTION,)
        )
        request = make_exposure_request(
            requested_layers=(OntologicalLayer.EXECUTION, OntologicalLayer.IDENTITY)
        )

        response = gate.evaluate(projection, request)

        # TAGGING was requested but not in projection
        assert OntologicalLayer.IDENTITY in response.denied_layers
        assert OntologicalLayer.EXECUTION in response.effective_layers

    def test_implicit_layers_exclude_absolving(self) -> None:
        """Implicit layer requests exclude ABSOLVING even when projected."""
        gate = create_exposure_gate()

        projection = make_projection_response(
            layers=(OntologicalLayer.EXECUTION, OntologicalLayer.ABSOLVING)
        )
        request = make_exposure_request(
            role_id=RoleId.AUDITOR,  # Can access ABSOLVING
            requested_layers=None,  # Implicit
        )

        response = gate.evaluate(projection, request)

        # ABSOLVING should be excluded from implicit requests
        assert OntologicalLayer.ABSOLVING not in response.effective_layers
        assert OntologicalLayer.EXECUTION in response.effective_layers


# =============================================================================
# Validation Tests
# =============================================================================

class TestValidation:
    """Test input validation."""

    def test_empty_artifact_id_raises(self) -> None:
        """Empty artifact_id raises ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            ExposureRequest(
                artifact_id="",
                span_id="0" * 16,
                role_id=RoleId.END_USER,
            )

    def test_empty_span_id_raises(self) -> None:
        """Empty span_id raises ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            ExposureRequest(
                artifact_id="test",
                span_id="",
                role_id=RoleId.END_USER,
            )

    def test_invalid_role_id_type_raises(self) -> None:
        """Invalid role_id type raises TypeError."""
        with pytest.raises(TypeError, match="RoleId"):
            ExposureRequest(
                artifact_id="test",
                span_id="0" * 16,
                role_id="invalid",  # type: ignore
            )

    def test_invalid_requested_layers_type_raises(self) -> None:
        """Invalid requested_layers type raises TypeError."""
        with pytest.raises(TypeError, match="tuple"):
            ExposureRequest(
                artifact_id="test",
                span_id="0" * 16,
                role_id=RoleId.END_USER,
                requested_layers=[OntologicalLayer.EXECUTION],  # type: ignore
            )

    def test_invalid_layer_in_requested_layers_raises(self) -> None:
        """Invalid layer in requested_layers raises TypeError."""
        with pytest.raises(TypeError, match="OntologicalLayer"):
            ExposureRequest(
                artifact_id="test",
                span_id="0" * 16,
                role_id=RoleId.END_USER,
                requested_layers=("invalid",),  # type: ignore
            )

    def test_response_wrong_hash_length_raises(self) -> None:
        """Response with wrong hash length raises ValueError."""
        with pytest.raises(ValueError, match="16 characters"):
            ExposureResponse(
                allowed_layers=(),
                denied_layers=(),
                effective_layers=(),
                decision_hash="0" * 32,  # Wrong length
            )


# =============================================================================
# Enum Tests
# =============================================================================

class TestEnums:
    """Test enum definitions."""

    def test_role_id_values(self) -> None:
        """RoleId enum has expected values."""
        assert RoleId.END_USER.value == "end_user"
        assert RoleId.DEVELOPER.value == "developer"
        assert RoleId.AUDITOR.value == "auditor"
        assert RoleId.SYSTEM.value == "system"

    def test_exposure_decision_values(self) -> None:
        """ExposureDecision enum has expected values."""
        assert ExposureDecision.ALLOWED.value == "allowed"
        assert ExposureDecision.DENIED.value == "denied"


# =============================================================================
# Success Path Tests
# =============================================================================

class TestSuccessPath:
    """Test successful evaluation paths."""

    def test_simple_allowed_request(self) -> None:
        """Simple allowed request succeeds."""
        gate = create_exposure_gate()

        projection = make_projection_response(
            layers=(OntologicalLayer.EXECUTION,)
        )
        request = make_exposure_request(
            role_id=RoleId.END_USER,
            requested_layers=(OntologicalLayer.EXECUTION,),
        )

        response = gate.evaluate(projection, request)

        assert OntologicalLayer.EXECUTION in response.effective_layers
        assert len(response.decision_hash) == 16

    def test_multiple_allowed_layers(self) -> None:
        """Multiple allowed layers succeed."""
        gate = create_exposure_gate()

        projection = make_projection_response(
            layers=(
                OntologicalLayer.EXECUTION,
                OntologicalLayer.IDENTITY,
                OntologicalLayer.STRUCTURE,
            )
        )
        request = make_exposure_request(
            role_id=RoleId.DEVELOPER,
            requested_layers=(
                OntologicalLayer.EXECUTION,
                OntologicalLayer.IDENTITY,
            ),
        )

        response = gate.evaluate(projection, request)

        assert OntologicalLayer.EXECUTION in response.effective_layers
        assert OntologicalLayer.IDENTITY in response.effective_layers
        assert OntologicalLayer.STRUCTURE not in response.effective_layers

    def test_auditor_with_absolving(self) -> None:
        """Auditor can access ABSOLVING when explicitly requested."""
        gate = create_exposure_gate()

        projection = make_projection_response(
            layers=(
                OntologicalLayer.EXECUTION,
                OntologicalLayer.ABSOLVING,
            )
        )
        request = make_exposure_request(
            role_id=RoleId.AUDITOR,
            requested_layers=(
                OntologicalLayer.EXECUTION,
                OntologicalLayer.ABSOLVING,
            ),
        )

        response = gate.evaluate(projection, request)

        assert OntologicalLayer.EXECUTION in response.effective_layers
        assert OntologicalLayer.ABSOLVING in response.effective_layers

    def test_all_standard_layers(self) -> None:
        """All 9 standard layers can be accessed."""
        gate = create_exposure_gate()

        all_standard = (
            OntologicalLayer.EXECUTION,
            OntologicalLayer.IDENTITY,
            OntologicalLayer.STRUCTURE,
            OntologicalLayer.COGNITION,
            OntologicalLayer.AGENCY,
            OntologicalLayer.REASONING,
            OntologicalLayer.PURPOSE,
            OntologicalLayer.WITNESSES,
            OntologicalLayer.UNIFYING,
        )

        projection = make_projection_response(layers=all_standard)
        request = make_exposure_request(
            role_id=RoleId.END_USER,
            requested_layers=all_standard,
        )

        response = gate.evaluate(projection, request)

        for layer in all_standard:
            assert layer in response.effective_layers


# =============================================================================
# Deterministic Ordering Tests
# =============================================================================

class TestDeterministicOrdering:
    """Test that output ordering is deterministic."""

    def test_effective_layers_sorted_by_value(self) -> None:
        """effective_layers are sorted by enum value."""
        gate = create_exposure_gate()

        # Request in reverse order
        projection = make_projection_response(
            layers=(
                OntologicalLayer.UNIFYING,
                OntologicalLayer.EXECUTION,
                OntologicalLayer.AGENCY,
            )
        )
        request = make_exposure_request(
            role_id=RoleId.END_USER,
            requested_layers=(
                OntologicalLayer.UNIFYING,
                OntologicalLayer.EXECUTION,
                OntologicalLayer.AGENCY,
            ),
        )

        response = gate.evaluate(projection, request)

        # Should be sorted by value (EXECUTION=3, AGENCY=6, UNIFYING=10)
        expected_order = (
            OntologicalLayer.EXECUTION,
            OntologicalLayer.AGENCY,
            OntologicalLayer.UNIFYING,
        )
        assert response.effective_layers == expected_order

    def test_allowed_layers_sorted_by_value(self) -> None:
        """allowed_layers are sorted by enum value."""
        gate = create_exposure_gate()

        projection = make_projection_response(
            layers=(OntologicalLayer.IDENTITY, OntologicalLayer.EXECUTION)
        )
        request = make_exposure_request(
            role_id=RoleId.END_USER,
            requested_layers=(OntologicalLayer.IDENTITY, OntologicalLayer.EXECUTION),
        )

        response = gate.evaluate(projection, request)

        # Should be sorted by value (IDENTITY=2, EXECUTION=3)
        expected_order = (OntologicalLayer.IDENTITY, OntologicalLayer.EXECUTION)
        assert response.allowed_layers == expected_order
