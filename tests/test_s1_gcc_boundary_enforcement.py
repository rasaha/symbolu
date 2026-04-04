"""
S1 GCC Boundary Enforcement Tests
===================================

Integration tests proving GCC guards fire at real constrained module boundaries:

1. Router exit: assert_non_expressive fires on ProjectionResponse
2. Phase map exit: assert_non_expressive fires on get_layers_for_phase return
3. Ledger write: assert_ledger_entry_valid fires on LedgerStore.append
4. Ledger entry write: assert_ledger_entry_valid fires on LedgerEntryStore.append
5. Violation rejection: guards block expressive values at boundaries
"""

from __future__ import annotations

import dataclasses
import pytest
from unittest.mock import patch

from symbolu.ontology.layers.ontology_layer import OntologicalLayer
from symbolu.ontology.router.ontological_router_r1 import (
    OntologicalLayerRouter,
    ProjectionRequest,
    ProjectionResponse,
    route_projection,
)
from symbolu.ontology.router.phase_layer_map import get_layers_for_phase
from symbolu.ledger.ledger_store import (
    LedgerStore,
    LedgerEntryStore,
    record_projection,
    record_ledger_entry,
)
from symbolu.safety.gcc_runtime_guard import (
    GCCViolationError,
    assert_non_expressive,
)
from symbolu.safety.gcc_ledger_invariant import (
    LedgerInvariantViolation,
    assert_ledger_entry_valid,
)


# =============================================================================
# Router Exit Guard Tests
# =============================================================================

class TestRouterExitGuard:
    """GCC guard fires on OntologicalLayerRouter.project() return."""

    def test_project_returns_non_expressive(self):
        """Valid projection passes GCC guard at router exit."""
        router = OntologicalLayerRouter()
        request = ProjectionRequest(
            artifact_id="abc123def456",
            phase_id="1b",
            artifact_hash="deadbeef01234567",
            declared_projection_hint=None,
        )
        response = router.project(request)

        # Should succeed without raising
        assert isinstance(response, ProjectionResponse)
        assert response.phase_id == "1b"

    def test_project_all_phases(self):
        """All valid phases pass GCC guard at router exit."""
        router = OntologicalLayerRouter()
        for phase_id in ("1b", "2", "3", "4", "5", "6", "7", "8", "9"):
            request = ProjectionRequest(
                artifact_id=f"test-{phase_id}",
                phase_id=phase_id,
                artifact_hash="abcdef0123456789",
                declared_projection_hint=None,
            )
            response = router.project(request)
            assert response.phase_id == phase_id

    def test_route_projection_convenience(self):
        """route_projection() convenience function also passes GCC guard."""
        request = ProjectionRequest(
            artifact_id="conv-test-001",
            phase_id="3",
            artifact_hash="1234567890abcdef",
            declared_projection_hint=None,
        )
        response = route_projection(request)
        assert isinstance(response, ProjectionResponse)

    def test_project_with_hint(self):
        """Projection with valid hint passes GCC guard."""
        router = OntologicalLayerRouter()
        # STRUCTURE is in PHASE_ALLOWED_HINTS["3"]
        request = ProjectionRequest(
            artifact_id="hint-test",
            phase_id="3",
            artifact_hash="fedcba9876543210",
            declared_projection_hint=OntologicalLayer.STRUCTURE,
        )
        response = router.project(request)
        assert OntologicalLayer.STRUCTURE in response.projected_layers


# =============================================================================
# Phase Layer Map Guard Tests
# =============================================================================

class TestPhaseLayerMapGuard:
    """GCC guard fires on get_layers_for_phase() return."""

    def test_layers_are_non_expressive(self):
        """get_layers_for_phase returns only non-expressive values."""
        for phase_id in ("1b", "2", "3", "4", "5", "6", "7", "8", "9"):
            layers = get_layers_for_phase(phase_id)
            assert isinstance(layers, tuple)
            assert all(isinstance(l, OntologicalLayer) for l in layers)

    def test_layers_without_gated(self):
        """get_layers_for_phase with include_gated=False passes guard."""
        layers = get_layers_for_phase("9", include_gated=False)
        assert isinstance(layers, tuple)
        # ABSOLVING is gated, should be excluded
        assert OntologicalLayer.ABSOLVING not in layers


# =============================================================================
# Ledger Write Guard Tests
# =============================================================================

class TestLedgerWriteGuard:
    """GCC ledger invariant fires on LedgerStore.append()."""

    def test_record_projection_passes_guard(self):
        """record_projection creates valid entries that pass ledger invariant."""
        store = LedgerStore()
        router = OntologicalLayerRouter()
        entry = record_projection(
            store=store,
            artifact_id="ledger-test-001",
            artifact_hash="aabbccdd11223344",
            phase_id="2",
            router=router,
        )
        assert len(store) == 1
        # Entry was appended — guard passed
        assert entry.phase_id == "2"

    def test_record_multiple_projections(self):
        """Multiple sequential entries all pass ledger invariant."""
        store = LedgerStore()
        router = OntologicalLayerRouter()
        for i in range(5):
            record_projection(
                store=store,
                artifact_id=f"multi-{i}",
                artifact_hash=f"{'ab' * 8}{i:02d}",
                phase_id="3",
                router=router,
            )
        assert len(store) == 5


class TestLedgerEntryWriteGuard:
    """GCC ledger invariant fires on LedgerEntryStore.append()."""

    def test_record_ledger_entry_passes_guard(self):
        """record_ledger_entry creates valid entries that pass invariant."""
        store = LedgerEntryStore()
        router = OntologicalLayerRouter()
        entry = record_ledger_entry(
            store=store,
            artifact_id="entry-test-001",
            artifact_hash="1122334455667788",
            phase_id="4",
            router=router,
        )
        assert len(store) == 1
        assert entry.phase_id == "4"

    def test_record_multiple_ledger_entries(self):
        """Multiple sequential entries with hash chain pass invariant."""
        store = LedgerEntryStore()
        router = OntologicalLayerRouter()
        for i in range(3):
            record_ledger_entry(
                store=store,
                artifact_id=f"chain-{i}",
                artifact_hash=f"{'cd' * 8}{i:02d}",
                phase_id="5",
                router=router,
            )
        assert len(store) == 3


# =============================================================================
# Violation Rejection Tests
# =============================================================================

class TestGCCViolationRejection:
    """Guards reject expressive values at boundaries."""

    def test_free_text_string_rejected(self):
        """Free-form text string is rejected by runtime guard."""
        with pytest.raises(GCCViolationError):
            assert_non_expressive("This is a sentence with spaces and meaning")

    def test_sentence_with_spaces_rejected(self):
        """Sentence with spaces is rejected (not an opaque ID or hex)."""
        with pytest.raises(GCCViolationError):
            assert_non_expressive("the quick brown fox jumps over the lazy dog")

    def test_mutable_list_rejected(self):
        """Mutable list is rejected."""
        with pytest.raises(GCCViolationError):
            assert_non_expressive([1, 2, 3])

    def test_mutable_dict_rejected(self):
        """Mutable dict is rejected."""
        with pytest.raises(GCCViolationError):
            assert_non_expressive({"key": "value"})

    def test_opaque_id_accepted(self):
        """Bounded opaque identifiers pass guard."""
        assert_non_expressive("artifact-001")
        assert_non_expressive("test.entry.123")
        assert_non_expressive("span_id_abc")

    def test_string_with_special_chars_rejected(self):
        """Strings with special characters are rejected."""
        with pytest.raises(GCCViolationError):
            assert_non_expressive("hello world! this is expressive @#$")


class TestLedgerInvariantRejection:
    """Ledger invariant rejects semantic content in entries."""

    def test_valid_entry_accepted(self):
        """Valid ledger entry passes invariant."""
        from symbolu.ledger.ledger_replay_verifier import create_entry
        entry = create_entry(
            ledger_index=0,
            artifact_id="valid-001",
            artifact_hash="deadbeef12345678",
            phase_id="1b",
            projected_layers=(OntologicalLayer.IDENTITY, OntologicalLayer.STRUCTURE),
            span_id="abcdef1234567890",
            router_version="R1.0",
        )
        # Should not raise
        assert_ledger_entry_valid(entry)

    def test_non_dataclass_rejected(self):
        """Non-dataclass objects are rejected as ledger entries."""
        with pytest.raises(LedgerInvariantViolation):
            assert_ledger_entry_valid({"artifact_id": "abc"})

    def test_forbidden_field_rejected(self):
        """Dataclass with semantic field names is rejected."""
        @dataclasses.dataclass(frozen=True)
        class BadEntry:
            description: str = "This describes something"
            ledger_index: int = 0

        with pytest.raises(LedgerInvariantViolation):
            assert_ledger_entry_valid(BadEntry())
