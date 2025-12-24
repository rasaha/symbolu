"""
Test Suite for Ledger Replay Verifier
======================================

Test Requirements:
    - 100-run determinism test (identical output)
    - Mutation guard (router + entries unchanged)
    - Each ReplayError tested explicitly
    - Order sensitivity test (permuted entries -> ORDER_MISMATCH)
    - Fixture regression tests (all fixtures)
    - Hash stability test (recompute = stored)

Constraints:
    - No snapshot testing
    - No mocks
    - No randomness
"""

from __future__ import annotations

import copy
import os
from pathlib import Path

import pytest

from symbolu.ledger import (
    LEDGER_REPLAY_INVARIANTS,
    LedgerProjectionEntry,
    LedgerReplayVerifier,
    LedgerStore,
    ReplayError,
    VerificationResult,
    canonical_serialize,
    compute_entry_hash,
    create_entry,
    dict_to_entry,
    entry_to_dict,
    load_fixture,
    record_projection,
)
from symbolu.ontology.router.ontological_router_r1 import (
    LedgerAdapter,
    LedgerSpanInput,
    OntologicalLayer,
    OntologicalLayerRouter,
    ProjectionRequest,
)


# =============================================================================
# Fixture Paths
# =============================================================================

FIXTURES_DIR = Path(__file__).parent.parent / "symbolu" / "ledger" / "fixtures"
FIXTURE_MINIMAL = FIXTURES_DIR / "fixture_minimal.json"
FIXTURE_CHAIN = FIXTURES_DIR / "fixture_chain.json"
FIXTURE_HINT_OVERRIDE = FIXTURES_DIR / "fixture_hint_override.json"
FIXTURE_ABSOLVING_BLOCK = FIXTURES_DIR / "fixture_absolving_block.json"


# =============================================================================
# Invariants Test
# =============================================================================

class TestInvariants:
    """Test that all invariants are declared and hold."""

    def test_invariants_declared(self) -> None:
        """All required invariants must be declared."""
        required_invariants = {
            "DETERMINISTIC",
            "REPLAYABLE",
            "FAIL_CLOSED",
            "NO_GENERATION",
            "NO_ROUTING_CHANGES",
            "NO_SEMANTICS",
            "HASH_STABLE",
            "APPEND_ONLY",
        }
        assert set(LEDGER_REPLAY_INVARIANTS.keys()) == required_invariants

    def test_all_invariants_true(self) -> None:
        """All invariants must be True."""
        for key, value in LEDGER_REPLAY_INVARIANTS.items():
            assert value is True, f"Invariant {key} is not True"


# =============================================================================
# Determinism Tests
# =============================================================================

class TestDeterminism:
    """Test 100-run determinism (identical output)."""

    def test_canonical_serialize_100_runs(self) -> None:
        """Canonical serialization produces identical output over 100 runs."""
        entry = create_entry(
            ledger_index=0,
            artifact_id="test_artifact",
            artifact_hash="a" * 64,
            phase_id="1b",
            projected_layers=(OntologicalLayer.ACTING,),
            span_id="0" * 16,
            router_version="R1.0",
        )

        first_result = canonical_serialize(entry)
        for _ in range(99):
            result = canonical_serialize(entry)
            assert result == first_result

    def test_entry_hash_100_runs(self) -> None:
        """Entry hash computation produces identical output over 100 runs."""
        params = {
            "ledger_index": 0,
            "artifact_id": "test_artifact",
            "artifact_hash": "b" * 64,
            "phase_id": "2",
            "projected_layers": (OntologicalLayer.TAGGING,),
            "span_id": "1" * 16,
            "router_version": "R1.0",
        }

        first_hash = compute_entry_hash(**params)
        for _ in range(99):
            result_hash = compute_entry_hash(**params)
            assert result_hash == first_hash

    def test_span_id_100_runs(self) -> None:
        """Span ID generation produces identical output over 100 runs."""
        span_input = LedgerSpanInput(
            artifact_hash="c" * 64,
            phase_id="3",
            projected_layers=(OntologicalLayer.FORMING,),
        )

        first_span_id = LedgerAdapter.generate_span_id(span_input)
        for _ in range(99):
            span_id = LedgerAdapter.generate_span_id(span_input)
            assert span_id == first_span_id

    def test_verification_100_runs(self) -> None:
        """Verification produces identical output over 100 runs."""
        router = OntologicalLayerRouter()
        store = LedgerStore()

        record_projection(
            store=store,
            artifact_id="test_artifact",
            artifact_hash="d" * 64,
            phase_id="4",
            router=router,
        )

        entries = store.read_all()
        verifier = LedgerReplayVerifier()

        first_result = verifier.verify(entries, router)
        for _ in range(99):
            result = verifier.verify(entries, router)
            assert result.success == first_result.success
            assert result.error == first_result.error
            assert result.failed_index == first_result.failed_index


# =============================================================================
# Mutation Guard Tests
# =============================================================================

class TestMutationGuard:
    """Test that router and entries are not mutated during verification."""

    def test_router_not_mutated(self) -> None:
        """Router state is not mutated during verification."""
        router = OntologicalLayerRouter()
        original_version = router.ROUTER_VERSION
        original_opt_in = router._explicit_absolving_opt_in

        store = LedgerStore()
        record_projection(
            store=store,
            artifact_id="test_artifact",
            artifact_hash="e" * 64,
            phase_id="5",
            router=router,
        )

        entries = store.read_all()
        verifier = LedgerReplayVerifier()
        verifier.verify(entries, router)

        assert router.ROUTER_VERSION == original_version
        assert router._explicit_absolving_opt_in == original_opt_in

    def test_entries_not_mutated(self) -> None:
        """Entries are not mutated during verification."""
        router = OntologicalLayerRouter()
        store = LedgerStore()

        record_projection(
            store=store,
            artifact_id="test_artifact",
            artifact_hash="f" * 64,
            phase_id="6",
            router=router,
        )

        entries = store.read_all()
        entries_copy = tuple(
            LedgerProjectionEntry(
                ledger_index=e.ledger_index,
                artifact_id=e.artifact_id,
                artifact_hash=e.artifact_hash,
                phase_id=e.phase_id,
                projected_layers=e.projected_layers,
                span_id=e.span_id,
                router_version=e.router_version,
                entry_hash=e.entry_hash,
            )
            for e in entries
        )

        verifier = LedgerReplayVerifier()
        verifier.verify(entries, router)

        for original, after in zip(entries_copy, entries):
            assert original.ledger_index == after.ledger_index
            assert original.artifact_id == after.artifact_id
            assert original.artifact_hash == after.artifact_hash
            assert original.phase_id == after.phase_id
            assert original.projected_layers == after.projected_layers
            assert original.span_id == after.span_id
            assert original.router_version == after.router_version
            assert original.entry_hash == after.entry_hash


# =============================================================================
# ReplayError Tests (Each tested explicitly)
# =============================================================================

class TestReplayErrors:
    """Test each ReplayError code explicitly."""

    def test_entry_id_mismatch(self) -> None:
        """ENTRY_ID_MISMATCH is returned when entry_hash doesn't match."""
        router = OntologicalLayerRouter()
        store = LedgerStore()

        entry = record_projection(
            store=store,
            artifact_id="test_artifact",
            artifact_hash="g" * 64,
            phase_id="7",
            router=router,
        )

        tampered_entry = LedgerProjectionEntry(
            ledger_index=entry.ledger_index,
            artifact_id=entry.artifact_id,
            artifact_hash=entry.artifact_hash,
            phase_id=entry.phase_id,
            projected_layers=entry.projected_layers,
            span_id=entry.span_id,
            router_version=entry.router_version,
            entry_hash="0" * 16,
        )

        verifier = LedgerReplayVerifier()
        result = verifier.verify((tampered_entry,), router)

        assert result.success is False
        assert result.error == ReplayError.ENTRY_ID_MISMATCH
        assert result.failed_index == 0

    def test_span_id_mismatch(self) -> None:
        """SPAN_ID_MISMATCH is returned when span_id doesn't match."""
        router = OntologicalLayerRouter()
        store = LedgerStore()

        entry = record_projection(
            store=store,
            artifact_id="test_artifact",
            artifact_hash="h" * 64,
            phase_id="8",
            router=router,
        )

        wrong_span_id = "f" * 16
        recalculated_entry_hash = compute_entry_hash(
            ledger_index=entry.ledger_index,
            artifact_id=entry.artifact_id,
            artifact_hash=entry.artifact_hash,
            phase_id=entry.phase_id,
            projected_layers=entry.projected_layers,
            span_id=wrong_span_id,
            router_version=entry.router_version,
        )

        tampered_entry = LedgerProjectionEntry(
            ledger_index=entry.ledger_index,
            artifact_id=entry.artifact_id,
            artifact_hash=entry.artifact_hash,
            phase_id=entry.phase_id,
            projected_layers=entry.projected_layers,
            span_id=wrong_span_id,
            router_version=entry.router_version,
            entry_hash=recalculated_entry_hash,
        )

        verifier = LedgerReplayVerifier()
        result = verifier.verify((tampered_entry,), router)

        assert result.success is False
        assert result.error == ReplayError.SPAN_ID_MISMATCH
        assert result.failed_index == 0

    def test_layer_mismatch(self) -> None:
        """LAYER_MISMATCH is returned when projected_layers don't match."""
        router = OntologicalLayerRouter()
        store = LedgerStore()

        entry = record_projection(
            store=store,
            artifact_id="test_artifact",
            artifact_hash="i" * 64,
            phase_id="1b",
            router=router,
        )

        wrong_layers = (OntologicalLayer.TAGGING,)
        wrong_span_input = LedgerSpanInput(
            artifact_hash=entry.artifact_hash,
            phase_id=entry.phase_id,
            projected_layers=wrong_layers,
        )
        wrong_span_id = LedgerAdapter.generate_span_id(wrong_span_input)

        wrong_entry_hash = compute_entry_hash(
            ledger_index=entry.ledger_index,
            artifact_id=entry.artifact_id,
            artifact_hash=entry.artifact_hash,
            phase_id=entry.phase_id,
            projected_layers=wrong_layers,
            span_id=wrong_span_id,
            router_version=entry.router_version,
        )

        tampered_entry = LedgerProjectionEntry(
            ledger_index=entry.ledger_index,
            artifact_id=entry.artifact_id,
            artifact_hash=entry.artifact_hash,
            phase_id=entry.phase_id,
            projected_layers=wrong_layers,
            span_id=wrong_span_id,
            router_version=entry.router_version,
            entry_hash=wrong_entry_hash,
        )

        verifier = LedgerReplayVerifier()
        result = verifier.verify((tampered_entry,), router)

        assert result.success is False
        assert result.error == ReplayError.LAYER_MISMATCH
        assert result.failed_index == 0

    def test_order_mismatch(self) -> None:
        """ORDER_MISMATCH is returned when ledger_index doesn't match position."""
        router = OntologicalLayerRouter()
        store = LedgerStore()

        record_projection(
            store=store,
            artifact_id="test_artifact_1",
            artifact_hash="j" * 64,
            phase_id="2",
            router=router,
        )
        record_projection(
            store=store,
            artifact_id="test_artifact_2",
            artifact_hash="k" * 64,
            phase_id="3",
            router=router,
        )

        entries = store.read_all()
        swapped_entries = (entries[1], entries[0])

        verifier = LedgerReplayVerifier()
        result = verifier.verify(swapped_entries, router)

        assert result.success is False
        assert result.error == ReplayError.ORDER_MISMATCH
        assert result.failed_index == 0

    def test_router_version_mismatch(self) -> None:
        """ROUTER_VERSION_MISMATCH is returned when versions don't match."""
        router = OntologicalLayerRouter()
        store = LedgerStore()

        entry = record_projection(
            store=store,
            artifact_id="test_artifact",
            artifact_hash="l" * 64,
            phase_id="4",
            router=router,
        )

        wrong_version = "R0.9"
        span_input = LedgerSpanInput(
            artifact_hash=entry.artifact_hash,
            phase_id=entry.phase_id,
            projected_layers=entry.projected_layers,
        )
        span_id = LedgerAdapter.generate_span_id(span_input)

        wrong_entry_hash = compute_entry_hash(
            ledger_index=entry.ledger_index,
            artifact_id=entry.artifact_id,
            artifact_hash=entry.artifact_hash,
            phase_id=entry.phase_id,
            projected_layers=entry.projected_layers,
            span_id=span_id,
            router_version=wrong_version,
        )

        tampered_entry = LedgerProjectionEntry(
            ledger_index=entry.ledger_index,
            artifact_id=entry.artifact_id,
            artifact_hash=entry.artifact_hash,
            phase_id=entry.phase_id,
            projected_layers=entry.projected_layers,
            span_id=span_id,
            router_version=wrong_version,
            entry_hash=wrong_entry_hash,
        )

        verifier = LedgerReplayVerifier()
        result = verifier.verify((tampered_entry,), router)

        assert result.success is False
        assert result.error == ReplayError.ROUTER_VERSION_MISMATCH
        assert result.failed_index == 0


# =============================================================================
# Order Sensitivity Tests
# =============================================================================

class TestOrderSensitivity:
    """Test that permuted entries result in ORDER_MISMATCH."""

    def test_permuted_entries_fail(self) -> None:
        """Permuted entries produce ORDER_MISMATCH."""
        router = OntologicalLayerRouter()
        store = LedgerStore()

        for i in range(5):
            record_projection(
                store=store,
                artifact_id=f"artifact_{i}",
                artifact_hash=chr(ord("m") + i) * 64,
                phase_id=["1b", "2", "3", "4", "5"][i],
                router=router,
            )

        entries = store.read_all()

        permuted = (
            entries[0],
            entries[2],
            entries[1],
            entries[3],
            entries[4],
        )

        verifier = LedgerReplayVerifier()
        result = verifier.verify(permuted, router)

        assert result.success is False
        assert result.error == ReplayError.ORDER_MISMATCH

    def test_reversed_entries_fail(self) -> None:
        """Reversed entries produce ORDER_MISMATCH."""
        router = OntologicalLayerRouter()
        store = LedgerStore()

        for i in range(3):
            record_projection(
                store=store,
                artifact_id=f"artifact_{i}",
                artifact_hash=chr(ord("r") + i) * 64,
                phase_id=["1b", "2", "3"][i],
                router=router,
            )

        entries = store.read_all()
        reversed_entries = tuple(reversed(entries))

        verifier = LedgerReplayVerifier()
        result = verifier.verify(reversed_entries, router)

        assert result.success is False
        assert result.error == ReplayError.ORDER_MISMATCH


# =============================================================================
# Fixture Regression Tests
# =============================================================================

class TestFixtureRegression:
    """Test all fixtures for regression."""

    def test_fixture_minimal_passes(self) -> None:
        """fixture_minimal.json verifies successfully."""
        entries = load_fixture(str(FIXTURE_MINIMAL))
        router = OntologicalLayerRouter()
        verifier = LedgerReplayVerifier()

        result = verifier.verify(entries, router)

        assert result.success is True
        assert result.error is None
        assert result.failed_index is None

    def test_fixture_chain_passes(self) -> None:
        """fixture_chain.json verifies successfully."""
        entries = load_fixture(str(FIXTURE_CHAIN))
        router = OntologicalLayerRouter()
        verifier = LedgerReplayVerifier()

        result = verifier.verify(entries, router)

        assert result.success is True
        assert result.error is None
        assert result.failed_index is None

    def test_fixture_hint_override_passes(self) -> None:
        """fixture_hint_override.json verifies successfully."""
        entries = load_fixture(str(FIXTURE_HINT_OVERRIDE))
        router = OntologicalLayerRouter()
        verifier = LedgerReplayVerifier()

        result = verifier.verify(entries, router)

        assert result.success is True
        assert result.error is None
        assert result.failed_index is None

    def test_fixture_absolving_block_fails(self) -> None:
        """fixture_absolving_block.json fails verification without opt-in."""
        entries = load_fixture(str(FIXTURE_ABSOLVING_BLOCK))
        router = OntologicalLayerRouter(explicit_absolving_opt_in=False)
        verifier = LedgerReplayVerifier()

        result = verifier.verify(entries, router)

        assert result.success is False
        assert result.error == ReplayError.LAYER_MISMATCH
        assert result.failed_index == 0


# =============================================================================
# Hash Stability Tests
# =============================================================================

class TestHashStability:
    """Test that recomputed hashes match stored hashes."""

    def test_entry_hash_recompute_matches_stored(self) -> None:
        """Recomputed entry_hash matches stored value."""
        router = OntologicalLayerRouter()
        store = LedgerStore()

        entry = record_projection(
            store=store,
            artifact_id="test_artifact",
            artifact_hash="u" * 64,
            phase_id="5",
            router=router,
        )

        recomputed_hash = compute_entry_hash(
            ledger_index=entry.ledger_index,
            artifact_id=entry.artifact_id,
            artifact_hash=entry.artifact_hash,
            phase_id=entry.phase_id,
            projected_layers=entry.projected_layers,
            span_id=entry.span_id,
            router_version=entry.router_version,
        )

        assert recomputed_hash == entry.entry_hash

    def test_span_id_recompute_matches_stored(self) -> None:
        """Recomputed span_id matches stored value."""
        router = OntologicalLayerRouter()
        store = LedgerStore()

        entry = record_projection(
            store=store,
            artifact_id="test_artifact",
            artifact_hash="v" * 64,
            phase_id="6",
            router=router,
        )

        span_input = LedgerSpanInput(
            artifact_hash=entry.artifact_hash,
            phase_id=entry.phase_id,
            projected_layers=entry.projected_layers,
        )
        recomputed_span_id = LedgerAdapter.generate_span_id(span_input)

        assert recomputed_span_id == entry.span_id

    def test_fixture_hash_stability(self) -> None:
        """All fixtures have stable hashes."""
        fixtures = [
            FIXTURE_MINIMAL,
            FIXTURE_CHAIN,
            FIXTURE_HINT_OVERRIDE,
            FIXTURE_ABSOLVING_BLOCK,
        ]

        for fixture_path in fixtures:
            entries = load_fixture(str(fixture_path))
            for entry in entries:
                recomputed_hash = compute_entry_hash(
                    ledger_index=entry.ledger_index,
                    artifact_id=entry.artifact_id,
                    artifact_hash=entry.artifact_hash,
                    phase_id=entry.phase_id,
                    projected_layers=entry.projected_layers,
                    span_id=entry.span_id,
                    router_version=entry.router_version,
                )
                assert recomputed_hash == entry.entry_hash, (
                    f"Hash mismatch in {fixture_path.name} at index {entry.ledger_index}"
                )


# =============================================================================
# LedgerStore Tests
# =============================================================================

class TestLedgerStore:
    """Test LedgerStore append-only behavior."""

    def test_append_sequential_indices(self) -> None:
        """Entries must have sequential indices."""
        store = LedgerStore()
        router = OntologicalLayerRouter()

        entry0 = record_projection(
            store=store,
            artifact_id="artifact_0",
            artifact_hash="w" * 64,
            phase_id="7",
            router=router,
        )
        assert entry0.ledger_index == 0

        entry1 = record_projection(
            store=store,
            artifact_id="artifact_1",
            artifact_hash="x" * 64,
            phase_id="8",
            router=router,
        )
        assert entry1.ledger_index == 1

    def test_append_wrong_index_raises(self) -> None:
        """Appending entry with wrong index raises ValueError."""
        store = LedgerStore()

        entry = create_entry(
            ledger_index=5,
            artifact_id="test_artifact",
            artifact_hash="y" * 64,
            phase_id="9",
            projected_layers=(OntologicalLayer.UNIFYING,),
            span_id="0" * 16,
            router_version="R1.0",
        )

        with pytest.raises(ValueError, match="ledger_index mismatch"):
            store.append(entry)

    def test_read_all_returns_tuple(self) -> None:
        """read_all returns immutable tuple."""
        store = LedgerStore()
        router = OntologicalLayerRouter()

        record_projection(
            store=store,
            artifact_id="artifact",
            artifact_hash="z" * 64,
            phase_id="1b",
            router=router,
        )

        entries = store.read_all()
        assert isinstance(entries, tuple)


# =============================================================================
# Serialization Tests
# =============================================================================

class TestSerialization:
    """Test entry serialization/deserialization."""

    def test_entry_to_dict_and_back(self) -> None:
        """Entry survives roundtrip through dict serialization."""
        original = create_entry(
            ledger_index=0,
            artifact_id="test_artifact",
            artifact_hash="0" * 64,
            phase_id="2",
            projected_layers=(OntologicalLayer.TAGGING,),
            span_id="1" * 16,
            router_version="R1.0",
        )

        as_dict = entry_to_dict(original)
        restored = dict_to_entry(as_dict)

        assert restored.ledger_index == original.ledger_index
        assert restored.artifact_id == original.artifact_id
        assert restored.artifact_hash == original.artifact_hash
        assert restored.phase_id == original.phase_id
        assert restored.projected_layers == original.projected_layers
        assert restored.span_id == original.span_id
        assert restored.router_version == original.router_version
        assert restored.entry_hash == original.entry_hash

    def test_canonical_serialize_deterministic_key_order(self) -> None:
        """Canonical serialization has deterministic key ordering."""
        entry = create_entry(
            ledger_index=0,
            artifact_id="test_artifact",
            artifact_hash="2" * 64,
            phase_id="3",
            projected_layers=(OntologicalLayer.FORMING,),
            span_id="3" * 16,
            router_version="R1.0",
        )

        serialized = canonical_serialize(entry)
        decoded = serialized.decode("utf-8")

        artifact_hash_pos = decoded.find('"artifact_hash"')
        artifact_id_pos = decoded.find('"artifact_id"')
        ledger_index_pos = decoded.find('"ledger_index"')

        assert artifact_hash_pos < artifact_id_pos < ledger_index_pos


# =============================================================================
# Validation Tests
# =============================================================================

class TestValidation:
    """Test entry validation."""

    def test_negative_ledger_index_raises(self) -> None:
        """Negative ledger_index raises ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            LedgerProjectionEntry(
                ledger_index=-1,
                artifact_id="test",
                artifact_hash="a" * 64,
                phase_id="1b",
                projected_layers=(OntologicalLayer.ACTING,),
                span_id="0" * 16,
                router_version="R1.0",
                entry_hash="0" * 16,
            )

    def test_empty_artifact_id_raises(self) -> None:
        """Empty artifact_id raises ValueError."""
        with pytest.raises(ValueError, match="non-empty"):
            LedgerProjectionEntry(
                ledger_index=0,
                artifact_id="",
                artifact_hash="a" * 64,
                phase_id="1b",
                projected_layers=(OntologicalLayer.ACTING,),
                span_id="0" * 16,
                router_version="R1.0",
                entry_hash="0" * 16,
            )

    def test_wrong_entry_hash_length_raises(self) -> None:
        """Entry hash with wrong length raises ValueError."""
        with pytest.raises(ValueError, match="16-character"):
            LedgerProjectionEntry(
                ledger_index=0,
                artifact_id="test",
                artifact_hash="a" * 64,
                phase_id="1b",
                projected_layers=(OntologicalLayer.ACTING,),
                span_id="0" * 16,
                router_version="R1.0",
                entry_hash="0" * 32,
            )


# =============================================================================
# Success Path Tests
# =============================================================================

class TestSuccessPath:
    """Test successful verification paths."""

    def test_empty_ledger_verifies(self) -> None:
        """Empty ledger verifies successfully."""
        router = OntologicalLayerRouter()
        verifier = LedgerReplayVerifier()

        result = verifier.verify((), router)

        assert result.success is True
        assert result.error is None
        assert result.failed_index is None

    def test_single_entry_verifies(self) -> None:
        """Single entry verifies successfully."""
        router = OntologicalLayerRouter()
        store = LedgerStore()

        record_projection(
            store=store,
            artifact_id="single_artifact",
            artifact_hash="4" * 64,
            phase_id="4",
            router=router,
        )

        entries = store.read_all()
        verifier = LedgerReplayVerifier()
        result = verifier.verify(entries, router)

        assert result.success is True

    def test_multiple_entries_verify(self) -> None:
        """Multiple entries verify successfully."""
        router = OntologicalLayerRouter()
        store = LedgerStore()

        phases = ["1b", "2", "3", "4", "5", "6", "7", "8", "9"]
        for i, phase in enumerate(phases):
            record_projection(
                store=store,
                artifact_id=f"artifact_{i}",
                artifact_hash=chr(ord("5") + i) * 64,
                phase_id=phase,
                router=router,
            )

        entries = store.read_all()
        verifier = LedgerReplayVerifier()
        result = verifier.verify(entries, router)

        assert result.success is True

    def test_hint_override_verifies(self) -> None:
        """Entry with declared hint verifies successfully."""
        router = OntologicalLayerRouter()
        store = LedgerStore()

        record_projection(
            store=store,
            artifact_id="hint_artifact",
            artifact_hash="?" * 64,
            phase_id="4",
            router=router,
            declared_hint=OntologicalLayer.THINKING,
        )

        entries = store.read_all()
        verifier = LedgerReplayVerifier()
        result = verifier.verify(entries, router)

        assert result.success is True
        assert entries[0].projected_layers == (OntologicalLayer.THINKING,)


# =============================================================================
# LedgerEntry Tests (Spec-Compliant)
# =============================================================================

from symbolu.ledger import (
    LedgerEntry,
    LedgerEntryStore,
    MAPPING_VERSION,
    compute_entry_id,
    create_ledger_entry,
    dict_to_ledger_entry,
    ledger_entry_to_dict,
    record_ledger_entry,
    verify_ledger_replay,
)


class TestLedgerEntryDeterminism:
    """Test 100-run determinism for LedgerEntry (spec-compliant)."""

    def test_entry_id_100_runs(self) -> None:
        """Entry ID computation produces identical output over 100 runs."""
        params = {
            "prev_entry_id": None,
            "span_id": "0" * 16,
            "artifact_id": "test_artifact",
            "artifact_hash": "a" * 64,
            "phase_id": "1b",
            "projected_layers": (OntologicalLayer.ACTING,),
            "router_version": "R1.0",
            "mapping_version": MAPPING_VERSION,
            "seq": 0,
        }

        first_id = compute_entry_id(**params)
        for _ in range(99):
            result_id = compute_entry_id(**params)
            assert result_id == first_id

    def test_verify_ledger_replay_100_runs(self) -> None:
        """verify_ledger_replay produces identical output over 100 runs."""
        router = OntologicalLayerRouter()
        store = LedgerEntryStore()

        record_ledger_entry(
            store=store,
            artifact_id="test_artifact",
            artifact_hash="b" * 64,
            phase_id="2",
            router=router,
        )

        entries = store.read_all()

        first_result = verify_ledger_replay(entries, router)
        for _ in range(99):
            result = verify_ledger_replay(entries, router)
            assert result.success == first_result.success
            assert result.error == first_result.error
            assert result.failed_index == first_result.failed_index


class TestLedgerEntrySingleBitCorruption:
    """Test replay failure on single-bit corruption."""

    def test_corrupted_entry_id_fails(self) -> None:
        """Single-bit corruption in entry_id causes verification failure."""
        router = OntologicalLayerRouter()
        store = LedgerEntryStore()

        entry = record_ledger_entry(
            store=store,
            artifact_id="test_artifact",
            artifact_hash="c" * 64,
            phase_id="3",
            router=router,
        )

        corrupted_char = chr((ord(entry.entry_id[0]) + 1) % 256)
        corrupted_entry_id = corrupted_char + entry.entry_id[1:]

        corrupted_entry = LedgerEntry(
            entry_id=corrupted_entry_id,
            prev_entry_id=entry.prev_entry_id,
            span_id=entry.span_id,
            artifact_id=entry.artifact_id,
            artifact_hash=entry.artifact_hash,
            phase_id=entry.phase_id,
            projected_layers=entry.projected_layers,
            router_version=entry.router_version,
            mapping_version=entry.mapping_version,
            seq=entry.seq,
        )

        result = verify_ledger_replay((corrupted_entry,), router)

        assert result.success is False
        assert result.error == ReplayError.ENTRY_ID_MISMATCH
        assert result.failed_index == 0

    def test_corrupted_artifact_hash_fails(self) -> None:
        """Single-bit corruption in artifact_hash without updating span_id causes failure."""
        router = OntologicalLayerRouter()
        store = LedgerEntryStore()

        entry = record_ledger_entry(
            store=store,
            artifact_id="test_artifact",
            artifact_hash="d" * 64,
            phase_id="4",
            router=router,
        )

        corrupted_artifact_hash = "e" + entry.artifact_hash[1:]

        new_entry_id = compute_entry_id(
            prev_entry_id=entry.prev_entry_id,
            span_id=entry.span_id,
            artifact_id=entry.artifact_id,
            artifact_hash=corrupted_artifact_hash,
            phase_id=entry.phase_id,
            projected_layers=entry.projected_layers,
            router_version=entry.router_version,
            mapping_version=entry.mapping_version,
            seq=entry.seq,
        )

        corrupted_entry = LedgerEntry(
            entry_id=new_entry_id,
            prev_entry_id=entry.prev_entry_id,
            span_id=entry.span_id,
            artifact_id=entry.artifact_id,
            artifact_hash=corrupted_artifact_hash,
            phase_id=entry.phase_id,
            projected_layers=entry.projected_layers,
            router_version=entry.router_version,
            mapping_version=entry.mapping_version,
            seq=entry.seq,
        )

        result = verify_ledger_replay((corrupted_entry,), router)

        assert result.success is False
        assert result.error == ReplayError.SPAN_ID_MISMATCH
        assert result.failed_index == 0


class TestLedgerEntryReorderedEntries:
    """Test replay failure on reordered entries."""

    def test_reordered_entries_fail_seq(self) -> None:
        """Reordered entries produce SEQ_MISMATCH."""
        router = OntologicalLayerRouter()
        store = LedgerEntryStore()

        for i in range(3):
            record_ledger_entry(
                store=store,
                artifact_id=f"artifact_{i}",
                artifact_hash=chr(ord("f") + i) * 64,
                phase_id=["1b", "2", "3"][i],
                router=router,
            )

        entries = store.read_all()
        reordered = (entries[1], entries[0], entries[2])

        result = verify_ledger_replay(reordered, router)

        assert result.success is False
        assert result.error == ReplayError.SEQ_MISMATCH
        assert result.failed_index == 0

    def test_reversed_entries_fail(self) -> None:
        """Reversed entries produce SEQ_MISMATCH."""
        router = OntologicalLayerRouter()
        store = LedgerEntryStore()

        for i in range(3):
            record_ledger_entry(
                store=store,
                artifact_id=f"artifact_{i}",
                artifact_hash=chr(ord("i") + i) * 64,
                phase_id=["1b", "2", "3"][i],
                router=router,
            )

        entries = store.read_all()
        reversed_entries = tuple(reversed(entries))

        result = verify_ledger_replay(reversed_entries, router)

        assert result.success is False
        assert result.error == ReplayError.SEQ_MISMATCH


class TestLedgerEntryWrongProjection:
    """Test replay failure on wrong projection."""

    def test_wrong_projected_layers_fails(self) -> None:
        """Wrong projected_layers causes LAYER_MISMATCH."""
        router = OntologicalLayerRouter()
        store = LedgerEntryStore()

        entry = record_ledger_entry(
            store=store,
            artifact_id="test_artifact",
            artifact_hash="l" * 64,
            phase_id="1b",
            router=router,
        )

        wrong_layers = (OntologicalLayer.TAGGING,)
        wrong_span_input = LedgerSpanInput(
            artifact_hash=entry.artifact_hash,
            phase_id=entry.phase_id,
            projected_layers=wrong_layers,
        )
        wrong_span_id = LedgerAdapter.generate_span_id(wrong_span_input)

        wrong_entry_id = compute_entry_id(
            prev_entry_id=entry.prev_entry_id,
            span_id=wrong_span_id,
            artifact_id=entry.artifact_id,
            artifact_hash=entry.artifact_hash,
            phase_id=entry.phase_id,
            projected_layers=wrong_layers,
            router_version=entry.router_version,
            mapping_version=entry.mapping_version,
            seq=entry.seq,
        )

        wrong_entry = LedgerEntry(
            entry_id=wrong_entry_id,
            prev_entry_id=entry.prev_entry_id,
            span_id=wrong_span_id,
            artifact_id=entry.artifact_id,
            artifact_hash=entry.artifact_hash,
            phase_id=entry.phase_id,
            projected_layers=wrong_layers,
            router_version=entry.router_version,
            mapping_version=entry.mapping_version,
            seq=entry.seq,
        )

        result = verify_ledger_replay((wrong_entry,), router)

        assert result.success is False
        assert result.error == ReplayError.LAYER_MISMATCH
        assert result.failed_index == 0


class TestLedgerEntryExactReproduction:
    """Test replay success on exact reproduction."""

    def test_single_entry_verifies(self) -> None:
        """Single entry verifies successfully."""
        router = OntologicalLayerRouter()
        store = LedgerEntryStore()

        record_ledger_entry(
            store=store,
            artifact_id="single_artifact",
            artifact_hash="m" * 64,
            phase_id="4",
            router=router,
        )

        entries = store.read_all()
        result = verify_ledger_replay(entries, router)

        assert result.success is True
        assert result.error is None
        assert result.failed_index is None

    def test_multiple_entries_verify(self) -> None:
        """Multiple entries verify successfully."""
        router = OntologicalLayerRouter()
        store = LedgerEntryStore()

        phases = ["1b", "2", "3", "4", "5", "6", "7", "8", "9"]
        for i, phase in enumerate(phases):
            record_ledger_entry(
                store=store,
                artifact_id=f"artifact_{i}",
                artifact_hash=chr(ord("n") + i) * 64,
                phase_id=phase,
                router=router,
            )

        entries = store.read_all()
        result = verify_ledger_replay(entries, router)

        assert result.success is True

    def test_empty_ledger_verifies(self) -> None:
        """Empty ledger verifies successfully."""
        router = OntologicalLayerRouter()

        result = verify_ledger_replay((), router)

        assert result.success is True
        assert result.error is None
        assert result.failed_index is None


class TestHashChainIntegrity:
    """Test hash chain integrity verification."""

    def test_broken_chain_fails(self) -> None:
        """Broken hash chain causes HASH_CHAIN_MISMATCH."""
        router = OntologicalLayerRouter()
        store = LedgerEntryStore()

        for i in range(3):
            record_ledger_entry(
                store=store,
                artifact_id=f"artifact_{i}",
                artifact_hash=chr(ord("w") + i) * 64,
                phase_id=["1b", "2", "3"][i],
                router=router,
            )

        entries = list(store.read_all())

        wrong_prev_entry_id = "0" * 16
        broken_entry = LedgerEntry(
            entry_id=entries[1].entry_id,
            prev_entry_id=wrong_prev_entry_id,
            span_id=entries[1].span_id,
            artifact_id=entries[1].artifact_id,
            artifact_hash=entries[1].artifact_hash,
            phase_id=entries[1].phase_id,
            projected_layers=entries[1].projected_layers,
            router_version=entries[1].router_version,
            mapping_version=entries[1].mapping_version,
            seq=entries[1].seq,
        )

        broken_entries = (entries[0], broken_entry, entries[2])

        result = verify_ledger_replay(broken_entries, router)

        assert result.success is False
        assert result.error == ReplayError.HASH_CHAIN_MISMATCH
        assert result.failed_index == 1

    def test_first_entry_with_wrong_prev_fails(self) -> None:
        """First entry with non-None prev_entry_id fails."""
        router = OntologicalLayerRouter()
        store = LedgerEntryStore()

        entry = record_ledger_entry(
            store=store,
            artifact_id="test_artifact",
            artifact_hash="z" * 64,
            phase_id="5",
            router=router,
        )

        wrong_prev = "0" * 16

        wrong_entry_id = compute_entry_id(
            prev_entry_id=wrong_prev,
            span_id=entry.span_id,
            artifact_id=entry.artifact_id,
            artifact_hash=entry.artifact_hash,
            phase_id=entry.phase_id,
            projected_layers=entry.projected_layers,
            router_version=entry.router_version,
            mapping_version=entry.mapping_version,
            seq=entry.seq,
        )

        wrong_entry = LedgerEntry(
            entry_id=wrong_entry_id,
            prev_entry_id=wrong_prev,
            span_id=entry.span_id,
            artifact_id=entry.artifact_id,
            artifact_hash=entry.artifact_hash,
            phase_id=entry.phase_id,
            projected_layers=entry.projected_layers,
            router_version=entry.router_version,
            mapping_version=entry.mapping_version,
            seq=entry.seq,
        )

        result = verify_ledger_replay((wrong_entry,), router)

        assert result.success is False
        assert result.error == ReplayError.HASH_CHAIN_MISMATCH
        assert result.failed_index == 0

    def test_chain_integrity_across_entries(self) -> None:
        """Chain integrity is verified across all entries."""
        router = OntologicalLayerRouter()
        store = LedgerEntryStore()

        for i in range(5):
            record_ledger_entry(
                store=store,
                artifact_id=f"artifact_{i}",
                artifact_hash=chr(ord("0") + i) * 64,
                phase_id=["1b", "2", "3", "4", "5"][i],
                router=router,
            )

        entries = store.read_all()

        for i, entry in enumerate(entries):
            if i == 0:
                assert entry.prev_entry_id is None
            else:
                assert entry.prev_entry_id == entries[i - 1].entry_id

        result = verify_ledger_replay(entries, router)
        assert result.success is True


class TestLedgerEntryStore:
    """Test LedgerEntryStore operations."""

    def test_append_returns_entry_id(self) -> None:
        """Append returns the entry_id."""
        store = LedgerEntryStore()
        router = OntologicalLayerRouter()

        entry = record_ledger_entry(
            store=store,
            artifact_id="test",
            artifact_hash="1" * 64,
            phase_id="6",
            router=router,
        )

        assert entry.entry_id is not None
        assert len(entry.entry_id) == 16

    def test_get_returns_entry(self) -> None:
        """Get returns entry by entry_id."""
        store = LedgerEntryStore()
        router = OntologicalLayerRouter()

        entry = record_ledger_entry(
            store=store,
            artifact_id="test",
            artifact_hash="2" * 64,
            phase_id="7",
            router=router,
        )

        retrieved = store.get(entry.entry_id)
        assert retrieved is not None
        assert retrieved.entry_id == entry.entry_id

    def test_get_returns_none_for_missing(self) -> None:
        """Get returns None for missing entry_id."""
        store = LedgerEntryStore()

        result = store.get("0" * 16)
        assert result is None

    def test_head_returns_last_entry(self) -> None:
        """Head returns the most recent entry."""
        store = LedgerEntryStore()
        router = OntologicalLayerRouter()

        for i in range(3):
            record_ledger_entry(
                store=store,
                artifact_id=f"artifact_{i}",
                artifact_hash=chr(ord("3") + i) * 64,
                phase_id=["1b", "2", "3"][i],
                router=router,
            )

        head = store.head()
        assert head is not None
        assert head.seq == 2

    def test_head_returns_none_for_empty(self) -> None:
        """Head returns None for empty store."""
        store = LedgerEntryStore()

        result = store.head()
        assert result is None

    def test_iter_all_yields_entries(self) -> None:
        """iter_all yields all entries in order."""
        store = LedgerEntryStore()
        router = OntologicalLayerRouter()

        for i in range(3):
            record_ledger_entry(
                store=store,
                artifact_id=f"artifact_{i}",
                artifact_hash=chr(ord("6") + i) * 64,
                phase_id=["1b", "2", "3"][i],
                router=router,
            )

        entries_list = list(store.iter_all())
        assert len(entries_list) == 3
        for i, entry in enumerate(entries_list):
            assert entry.seq == i


class TestLedgerEntrySerialization:
    """Test LedgerEntry serialization/deserialization."""

    def test_roundtrip_serialization(self) -> None:
        """LedgerEntry survives roundtrip through dict serialization."""
        router = OntologicalLayerRouter()
        store = LedgerEntryStore()

        original = record_ledger_entry(
            store=store,
            artifact_id="test",
            artifact_hash="9" * 64,
            phase_id="8",
            router=router,
        )

        as_dict = ledger_entry_to_dict(original)
        restored = dict_to_ledger_entry(as_dict)

        assert restored.entry_id == original.entry_id
        assert restored.prev_entry_id == original.prev_entry_id
        assert restored.span_id == original.span_id
        assert restored.artifact_id == original.artifact_id
        assert restored.artifact_hash == original.artifact_hash
        assert restored.phase_id == original.phase_id
        assert restored.projected_layers == original.projected_layers
        assert restored.router_version == original.router_version
        assert restored.mapping_version == original.mapping_version
        assert restored.seq == original.seq


class TestLedgerEntryValidation:
    """Test LedgerEntry validation."""

    def test_negative_seq_raises(self) -> None:
        """Negative seq raises ValueError."""
        with pytest.raises(ValueError, match="non-negative"):
            LedgerEntry(
                entry_id="0" * 16,
                prev_entry_id=None,
                span_id="0" * 16,
                artifact_id="test",
                artifact_hash="a" * 64,
                phase_id="1b",
                projected_layers=(OntologicalLayer.ACTING,),
                router_version="R1.0",
                mapping_version=MAPPING_VERSION,
                seq=-1,
            )

    def test_wrong_entry_id_length_raises(self) -> None:
        """Wrong entry_id length raises ValueError."""
        with pytest.raises(ValueError, match="16-character"):
            LedgerEntry(
                entry_id="0" * 32,
                prev_entry_id=None,
                span_id="0" * 16,
                artifact_id="test",
                artifact_hash="a" * 64,
                phase_id="1b",
                projected_layers=(OntologicalLayer.ACTING,),
                router_version="R1.0",
                mapping_version=MAPPING_VERSION,
                seq=0,
            )
