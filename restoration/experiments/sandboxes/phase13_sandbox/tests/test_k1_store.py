"""
Tests for Phase-13 K1 Store
===========================

Test Categories:
    1. Deterministic Retrieval - same query → same results (100 runs)
    2. Index Operations - add/remove updates indices
    3. Ledger Recording - all operations logged
    4. Replay Proof - query can be replayed
    5. Index Rebuild - indices rebuildable from atoms
"""

import pytest
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from k1_schema import (
    K1Atom,
    K1Query,
    K1Slot,
    K1SlotTier,
    OntologicalLayer,
    DiscourseAct,
    SelectionRule,
    create_atom,
)
from k1_store import (
    K1Store,
    LedgerEntry,
    create_empty_store,
    create_store_from_atoms,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def sample_atoms() -> tuple:
    """Create sample atoms for testing."""
    return (
        create_atom(
            layer=OntologicalLayer.O1_THINKING,
            slot=K1Slot.TARGET,
            discourse_act=DiscourseAct.DECLARE,
            payload_ref="hash:target1",
            provenance="test",
        ),
        create_atom(
            layer=OntologicalLayer.O1_THINKING,
            slot=K1Slot.CAUSE,
            discourse_act=DiscourseAct.LINK,
            payload_ref="hash:cause1",
            provenance="test",
        ),
        create_atom(
            layer=OntologicalLayer.O2_FORMING,
            slot=K1Slot.TARGET,
            discourse_act=DiscourseAct.DECLARE,
            payload_ref="hash:target2",
            provenance="test",
        ),
        create_atom(
            layer=OntologicalLayer.O6_REASONING,
            slot=K1Slot.EVIDENCE,
            discourse_act=DiscourseAct.TRIGGER,
            payload_ref="hash:evidence1",
            provenance="test",
        ),
    )


@pytest.fixture
def populated_store(sample_atoms) -> K1Store:
    """Create store with sample atoms."""
    store, _ = create_store_from_atoms(sample_atoms)
    return store


# =============================================================================
# Test: Deterministic Retrieval (100-run)
# =============================================================================

class TestDeterministicRetrieval:
    """Tests for retrieval determinism."""

    def test_same_query_same_results_100_runs(self, populated_store):
        """Same query produces identical results over 100 runs."""
        query = K1Query(layer=OntologicalLayer.O1_THINKING)

        first_result = populated_store.query(query)
        first_ids = first_result.get_atom_ids()
        first_hash = first_result.result_hash

        for _ in range(100):
            result = populated_store.query(query)
            assert result.get_atom_ids() == first_ids
            assert result.result_hash == first_hash

    def test_empty_query_deterministic(self, populated_store):
        """Empty query (all atoms) is deterministic."""
        query = K1Query()

        first_result = populated_store.query(query)
        first_ids = first_result.get_atom_ids()

        for _ in range(100):
            result = populated_store.query(query)
            assert result.get_atom_ids() == first_ids

    def test_query_hash_matches_result(self, populated_store):
        """Result's query_hash matches the query."""
        query = K1Query(slot=K1Slot.TARGET)
        result = populated_store.query(query)

        assert result.query_hash == query.query_hash()


# =============================================================================
# Test: Store Operations
# =============================================================================

class TestStoreOperations:
    """Tests for store add/remove operations."""

    def test_add_atom(self):
        """Adding atom works."""
        store = create_empty_store()
        atom = create_atom(
            layer=OntologicalLayer.O1_THINKING,
            slot=K1Slot.TARGET,
            discourse_act=DiscourseAct.DECLARE,
            payload_ref="hash:test",
            provenance="test",
        )

        success, error = store.add_atom(atom)
        assert success
        assert error is None
        assert store.count() == 1

    def test_add_duplicate_fails(self, populated_store, sample_atoms):
        """Adding duplicate atom fails."""
        success, error = populated_store.add_atom(sample_atoms[0])
        assert not success
        assert "Duplicate" in error

    def test_add_atoms_atomic(self):
        """add_atoms is atomic - all or none."""
        store = create_empty_store()
        atom1 = create_atom(
            layer=OntologicalLayer.O1_THINKING,
            slot=K1Slot.TARGET,
            discourse_act=DiscourseAct.DECLARE,
            payload_ref="hash:test1",
            provenance="test",
        )
        atom2 = create_atom(
            layer=OntologicalLayer.O2_FORMING,
            slot=K1Slot.TARGET,
            discourse_act=DiscourseAct.DECLARE,
            payload_ref="hash:test2",
            provenance="test",
        )

        success, _ = store.add_atoms((atom1, atom2))
        assert success
        assert store.count() == 2

    def test_remove_atom(self, populated_store, sample_atoms):
        """Removing atom works."""
        initial_count = populated_store.count()
        atom_id = sample_atoms[0].atom_id

        success, error = populated_store.remove_atom(atom_id)
        assert success
        assert error is None
        assert populated_store.count() == initial_count - 1

    def test_remove_nonexistent_fails(self, populated_store):
        """Removing nonexistent atom fails."""
        success, error = populated_store.remove_atom("nonexistent_id")
        assert not success
        assert "not found" in error


# =============================================================================
# Test: Index Operations
# =============================================================================

class TestIndexOperations:
    """Tests for index management."""

    def test_query_uses_layer_index(self, populated_store):
        """Query by layer uses index."""
        query = K1Query(layer=OntologicalLayer.O1_THINKING)
        result = populated_store.query(query)

        # Should find 2 atoms in O1_THINKING
        assert result.count() == 2
        for atom in result.atoms:
            assert atom.layer == OntologicalLayer.O1_THINKING

    def test_query_uses_slot_index(self, populated_store):
        """Query by slot uses index."""
        query = K1Query(slot=K1Slot.TARGET)
        result = populated_store.query(query)

        # Should find TARGET atoms
        for atom in result.atoms:
            assert atom.slot == K1Slot.TARGET

    def test_query_uses_primary_index(self, populated_store):
        """Query by all three uses primary composite index."""
        query = K1Query(
            layer=OntologicalLayer.O1_THINKING,
            slot=K1Slot.TARGET,
            discourse_act=DiscourseAct.DECLARE,
        )
        result = populated_store.query(query)

        assert result.count() == 1
        assert result.atoms[0].layer == OntologicalLayer.O1_THINKING
        assert result.atoms[0].slot == K1Slot.TARGET
        assert result.atoms[0].discourse_act == DiscourseAct.DECLARE

    def test_index_stats(self, populated_store):
        """Index stats are available."""
        stats = populated_store.index_stats()
        assert "primary_keys" in stats
        assert "layer_keys" in stats
        assert "slot_keys" in stats
        assert "discourse_act_keys" in stats


# =============================================================================
# Test: Index Rebuild
# =============================================================================

class TestIndexRebuild:
    """Tests for index rebuild functionality."""

    def test_rebuild_produces_same_results(self, populated_store):
        """Rebuilding indices produces same query results."""
        query = K1Query(layer=OntologicalLayer.O1_THINKING)

        result_before = populated_store.query(query)

        populated_store.rebuild_indices()

        result_after = populated_store.query(query)

        assert result_before.get_atom_ids() == result_after.get_atom_ids()

    def test_rebuild_after_modification(self, populated_store, sample_atoms):
        """Rebuild works after modifications."""
        # Remove an atom
        populated_store.remove_atom(sample_atoms[0].atom_id)

        # Rebuild
        populated_store.rebuild_indices()

        # Query should work
        query = K1Query()
        result = populated_store.query(query)
        assert result.count() == 3  # One removed


# =============================================================================
# Test: Ledger Recording
# =============================================================================

class TestLedgerRecording:
    """Tests for ledger operations."""

    def test_add_logged(self):
        """Add operations are logged."""
        store = create_empty_store()
        atom = create_atom(
            layer=OntologicalLayer.O1_THINKING,
            slot=K1Slot.TARGET,
            discourse_act=DiscourseAct.DECLARE,
            payload_ref="hash:test",
            provenance="test",
        )

        store.add_atom(atom)

        ledger = store.get_ledger()
        assert len(ledger) == 1
        assert ledger[0].operation == "ADD"
        assert ledger[0].success

    def test_query_logged(self, populated_store):
        """Query operations are logged."""
        initial_ledger_len = len(populated_store.get_ledger())

        query = K1Query(layer=OntologicalLayer.O1_THINKING)
        populated_store.query(query)

        ledger = populated_store.get_ledger()
        assert len(ledger) > initial_ledger_len

        last_entry = ledger[-1]
        assert last_entry.operation == "QUERY"
        assert last_entry.query_hash == query.query_hash()

    def test_failed_operations_logged(self, populated_store, sample_atoms):
        """Failed operations are logged."""
        initial_ledger_len = len(populated_store.get_ledger())

        # Try to add duplicate
        populated_store.add_atom(sample_atoms[0])

        ledger = populated_store.get_ledger()
        last_entry = ledger[-1]

        assert not last_entry.success
        assert "Duplicate" in last_entry.failure_reason

    def test_ledger_entry_has_hash(self, populated_store):
        """Ledger entries have deterministic hash."""
        query = K1Query()
        populated_store.query(query)

        ledger = populated_store.get_ledger()
        last_entry = ledger[-1]

        hash_val = last_entry.entry_hash()
        assert len(hash_val) == 16


# =============================================================================
# Test: Replay Proof
# =============================================================================

class TestReplayProof:
    """Tests for query replay proof."""

    def test_result_has_replay_proof(self, populated_store):
        """Query result includes replay proof steps."""
        query = K1Query(layer=OntologicalLayer.O1_THINKING)
        result = populated_store.query(query)

        assert len(result.replay_proof) > 0

    def test_replay_proof_has_steps(self, populated_store):
        """Replay proof has expected step types."""
        query = K1Query(layer=OntologicalLayer.O1_THINKING)
        result = populated_store.query(query)

        step_types = [s.step_type for s in result.replay_proof]
        assert "index_lookup" in step_types
        assert "filter" in step_types
        assert "sort" in step_types
        assert "limit" in step_types


# =============================================================================
# Test: Selection Rules
# =============================================================================

class TestSelectionRules:
    """Tests for deterministic ordering."""

    def test_lexicographic_ordering(self, populated_store):
        """LEXICOGRAPHIC_ID orders by atom_id."""
        query = K1Query(selection_rule=SelectionRule.LEXICOGRAPHIC_ID)
        result = populated_store.query(query)

        ids = result.get_atom_ids()
        assert ids == tuple(sorted(ids))

    def test_layer_ordering(self, populated_store):
        """LAYER_ORDER orders O1 before O2, etc."""
        query = K1Query(selection_rule=SelectionRule.LAYER_ORDER)
        result = populated_store.query(query)

        # Check atoms are in layer order
        prev_layer = ""
        for atom in result.atoms:
            assert atom.layer.value >= prev_layer
            prev_layer = atom.layer.value


# =============================================================================
# Test: Store Hash
# =============================================================================

class TestStoreHash:
    """Tests for store state hashing."""

    def test_store_hash_deterministic(self, populated_store):
        """Store hash is deterministic."""
        hashes = set()
        for _ in range(100):
            hashes.add(populated_store.store_hash())

        assert len(hashes) == 1

    def test_store_hash_changes_on_add(self, populated_store):
        """Store hash changes when atom added."""
        hash_before = populated_store.store_hash()

        new_atom = create_atom(
            layer=OntologicalLayer.O3_ACTING,
            slot=K1Slot.TARGET,
            discourse_act=DiscourseAct.DECLARE,
            payload_ref="hash:new",
            provenance="test",
        )
        populated_store.add_atom(new_atom)

        hash_after = populated_store.store_hash()
        assert hash_before != hash_after


# =============================================================================
# Test: Version Tracking
# =============================================================================

class TestVersionTracking:
    """Tests for store version tracking."""

    def test_version_increments_on_add(self):
        """Version increments when atom added."""
        store = create_empty_store()
        v1 = store.version_id

        atom = create_atom(
            layer=OntologicalLayer.O1_THINKING,
            slot=K1Slot.TARGET,
            discourse_act=DiscourseAct.DECLARE,
            payload_ref="hash:test",
            provenance="test",
        )
        store.add_atom(atom)

        v2 = store.version_id
        assert v1 != v2

    def test_version_in_result(self, populated_store):
        """Query result includes store version."""
        query = K1Query()
        result = populated_store.query(query)

        assert result.store_version_id == populated_store.version_id


# =============================================================================
# Test: Factory Functions
# =============================================================================

class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_empty_store(self):
        """create_empty_store creates empty store."""
        store = create_empty_store()
        assert store.count() == 0

    def test_create_store_from_atoms(self, sample_atoms):
        """create_store_from_atoms populates store."""
        store, error = create_store_from_atoms(sample_atoms)
        assert error is None
        assert store.count() == len(sample_atoms)


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
