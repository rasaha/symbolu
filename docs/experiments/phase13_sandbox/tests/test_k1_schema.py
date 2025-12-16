"""
Tests for Phase-13 K1 Schema
============================

Test Categories:
    1. Atom Creation - deterministic atom_id generation
    2. Query Matching - constraint matching logic
    3. Hash Determinism - same input → same hash
    4. Tier Classification - slots and discourse acts properly tiered
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
    DiscourseActTier,
    SelectionRule,
    K1EntityRef,
    create_atom,
    create_atom_id,
    get_slot_tier,
    get_tier_slots,
    get_discourse_act_tier,
    compute_result_hash,
    ALL_SLOTS,
    CORE_SLOTS,
    ALL_LAYERS,
    ALL_DISCOURSE_ACTS,
)


# =============================================================================
# Test: Atom Creation
# =============================================================================

class TestAtomCreation:
    """Tests for K1Atom creation."""

    def test_create_atom_generates_id(self):
        """create_atom generates deterministic atom_id."""
        atom = create_atom(
            layer=OntologicalLayer.O1_THINKING,
            slot=K1Slot.TARGET,
            discourse_act=DiscourseAct.DECLARE,
            payload_ref="hash:abc123",
            provenance="test_source",
        )

        assert atom.atom_id.startswith("k1_")
        assert len(atom.atom_id) == 15  # "k1_" + 12 hex chars

    def test_atom_id_deterministic(self):
        """Same inputs produce same atom_id."""
        ids = set()
        for _ in range(100):
            atom_id = create_atom_id(
                layer=OntologicalLayer.O1_THINKING,
                slot=K1Slot.TARGET,
                discourse_act=DiscourseAct.DECLARE,
                payload_ref="hash:abc123",
                provenance="test_source",
            )
            ids.add(atom_id)

        assert len(ids) == 1

    def test_different_inputs_different_ids(self):
        """Different inputs produce different atom_ids."""
        atom1 = create_atom(
            layer=OntologicalLayer.O1_THINKING,
            slot=K1Slot.TARGET,
            discourse_act=DiscourseAct.DECLARE,
            payload_ref="hash:abc123",
            provenance="test",
        )
        atom2 = create_atom(
            layer=OntologicalLayer.O2_FORMING,  # Different layer
            slot=K1Slot.TARGET,
            discourse_act=DiscourseAct.DECLARE,
            payload_ref="hash:abc123",
            provenance="test",
        )

        assert atom1.atom_id != atom2.atom_id

    def test_atom_is_frozen(self):
        """K1Atom is immutable."""
        atom = create_atom(
            layer=OntologicalLayer.O1_THINKING,
            slot=K1Slot.TARGET,
            discourse_act=DiscourseAct.DECLARE,
            payload_ref="hash:abc123",
            provenance="test",
        )

        with pytest.raises(AttributeError):
            atom.slot = K1Slot.CAUSE  # type: ignore


# =============================================================================
# Test: Atom Hash
# =============================================================================

class TestAtomHash:
    """Tests for K1Atom hashing."""

    def test_atom_hash_deterministic(self):
        """atom_hash is deterministic."""
        atom = create_atom(
            layer=OntologicalLayer.O1_THINKING,
            slot=K1Slot.TARGET,
            discourse_act=DiscourseAct.DECLARE,
            payload_ref="hash:abc123",
            provenance="test",
        )

        hashes = set()
        for _ in range(100):
            hashes.add(atom.atom_hash())

        assert len(hashes) == 1

    def test_atom_hash_length(self):
        """atom_hash is 16 hex characters."""
        atom = create_atom(
            layer=OntologicalLayer.O1_THINKING,
            slot=K1Slot.TARGET,
            discourse_act=DiscourseAct.DECLARE,
            payload_ref="hash:abc123",
            provenance="test",
        )

        hash_val = atom.atom_hash()
        assert len(hash_val) == 16
        assert all(c in "0123456789abcdef" for c in hash_val)


# =============================================================================
# Test: Slot Tiers
# =============================================================================

class TestSlotTiers:
    """Tests for slot tier classification."""

    def test_all_slots_have_tiers(self):
        """Every slot has a tier assigned."""
        for slot in ALL_SLOTS:
            tier = get_slot_tier(slot)
            assert tier in K1SlotTier

    def test_core_slots_are_tier_1(self):
        """Core slots are all Tier 1."""
        core = [K1Slot.TARGET, K1Slot.CAUSE, K1Slot.EFFECT, K1Slot.CONSTRAINT, K1Slot.EVIDENCE]
        for slot in core:
            assert get_slot_tier(slot) == K1SlotTier.TIER_1_CORE

    def test_get_tier_slots_returns_correct_slots(self):
        """get_tier_slots returns slots for a tier."""
        tier_1_slots = get_tier_slots(K1SlotTier.TIER_1_CORE)
        assert K1Slot.TARGET in tier_1_slots
        assert K1Slot.CAUSE in tier_1_slots
        assert K1Slot.EFFECT in tier_1_slots

    def test_17_slots_total(self):
        """There are exactly 17 slots."""
        assert len(ALL_SLOTS) == 17


# =============================================================================
# Test: Discourse Act Tiers
# =============================================================================

class TestDiscourseActTiers:
    """Tests for discourse act tier classification."""

    def test_all_acts_have_tiers(self):
        """Every discourse act has a tier assigned."""
        for act in ALL_DISCOURSE_ACTS:
            tier = get_discourse_act_tier(act)
            assert tier in DiscourseActTier

    def test_flow_acts_are_tier_a(self):
        """Flow acts are Tier A."""
        flow_acts = [DiscourseAct.DECLARE, DiscourseAct.QUERY, DiscourseAct.LINK,
                     DiscourseAct.COMPARE, DiscourseAct.NEGATE]
        for act in flow_acts:
            assert get_discourse_act_tier(act) == DiscourseActTier.TIER_A_FLOW

    def test_terminal_acts_are_tier_d(self):
        """Terminal acts are Tier D."""
        terminal_acts = [DiscourseAct.BOUND, DiscourseAct.RELEASE, DiscourseAct.ABORT]
        for act in terminal_acts:
            assert get_discourse_act_tier(act) == DiscourseActTier.TIER_D_TERMINAL

    def test_14_discourse_acts_total(self):
        """There are exactly 14 discourse acts."""
        assert len(ALL_DISCOURSE_ACTS) == 14


# =============================================================================
# Test: Query Creation
# =============================================================================

class TestQueryCreation:
    """Tests for K1Query creation."""

    def test_empty_query_matches_all(self):
        """Empty query matches all atoms."""
        query = K1Query()

        atom = create_atom(
            layer=OntologicalLayer.O1_THINKING,
            slot=K1Slot.TARGET,
            discourse_act=DiscourseAct.DECLARE,
            payload_ref="hash:abc123",
            provenance="test",
        )

        assert query.matches(atom)

    def test_layer_filter(self):
        """Query with layer filter works."""
        query = K1Query(layer=OntologicalLayer.O1_THINKING)

        atom_match = create_atom(
            layer=OntologicalLayer.O1_THINKING,
            slot=K1Slot.TARGET,
            discourse_act=DiscourseAct.DECLARE,
            payload_ref="hash:abc123",
            provenance="test",
        )
        atom_no_match = create_atom(
            layer=OntologicalLayer.O2_FORMING,
            slot=K1Slot.TARGET,
            discourse_act=DiscourseAct.DECLARE,
            payload_ref="hash:abc123",
            provenance="test",
        )

        assert query.matches(atom_match)
        assert not query.matches(atom_no_match)

    def test_slot_filter(self):
        """Query with slot filter works."""
        query = K1Query(slot=K1Slot.TARGET)

        atom_match = create_atom(
            layer=OntologicalLayer.O1_THINKING,
            slot=K1Slot.TARGET,
            discourse_act=DiscourseAct.DECLARE,
            payload_ref="hash:abc123",
            provenance="test",
        )
        atom_no_match = create_atom(
            layer=OntologicalLayer.O1_THINKING,
            slot=K1Slot.CAUSE,
            discourse_act=DiscourseAct.DECLARE,
            payload_ref="hash:abc123",
            provenance="test",
        )

        assert query.matches(atom_match)
        assert not query.matches(atom_no_match)

    def test_discourse_act_filter(self):
        """Query with discourse_act filter works."""
        query = K1Query(discourse_act=DiscourseAct.DECLARE)

        atom_match = create_atom(
            layer=OntologicalLayer.O1_THINKING,
            slot=K1Slot.TARGET,
            discourse_act=DiscourseAct.DECLARE,
            payload_ref="hash:abc123",
            provenance="test",
        )
        atom_no_match = create_atom(
            layer=OntologicalLayer.O1_THINKING,
            slot=K1Slot.TARGET,
            discourse_act=DiscourseAct.QUERY,
            payload_ref="hash:abc123",
            provenance="test",
        )

        assert query.matches(atom_match)
        assert not query.matches(atom_no_match)

    def test_combined_filters(self):
        """Query with multiple filters works."""
        query = K1Query(
            layer=OntologicalLayer.O1_THINKING,
            slot=K1Slot.TARGET,
            discourse_act=DiscourseAct.DECLARE,
        )

        atom_match = create_atom(
            layer=OntologicalLayer.O1_THINKING,
            slot=K1Slot.TARGET,
            discourse_act=DiscourseAct.DECLARE,
            payload_ref="hash:abc123",
            provenance="test",
        )

        assert query.matches(atom_match)


# =============================================================================
# Test: Query Hash
# =============================================================================

class TestQueryHash:
    """Tests for K1Query hashing."""

    def test_query_hash_deterministic(self):
        """query_hash is deterministic."""
        query = K1Query(
            layer=OntologicalLayer.O1_THINKING,
            slot=K1Slot.TARGET,
        )

        hashes = set()
        for _ in range(100):
            hashes.add(query.query_hash())

        assert len(hashes) == 1

    def test_different_queries_different_hashes(self):
        """Different queries produce different hashes."""
        query1 = K1Query(layer=OntologicalLayer.O1_THINKING)
        query2 = K1Query(layer=OntologicalLayer.O2_FORMING)

        assert query1.query_hash() != query2.query_hash()


# =============================================================================
# Test: Result Hash
# =============================================================================

class TestResultHash:
    """Tests for result hash computation."""

    def test_result_hash_deterministic(self):
        """compute_result_hash is deterministic."""
        query_hash = "abc123"
        atom_ids = ("id1", "id2", "id3")

        hashes = set()
        for _ in range(100):
            hashes.add(compute_result_hash(query_hash, atom_ids))

        assert len(hashes) == 1

    def test_different_order_different_hash(self):
        """Different atom order produces different hash."""
        query_hash = "abc123"

        hash1 = compute_result_hash(query_hash, ("id1", "id2"))
        hash2 = compute_result_hash(query_hash, ("id2", "id1"))

        assert hash1 != hash2


# =============================================================================
# Test: Entity Reference
# =============================================================================

class TestEntityRef:
    """Tests for K1EntityRef."""

    def test_entity_ref_creation(self):
        """K1EntityRef can be created."""
        ref = K1EntityRef(entity_id="ent_123", entity_type="person")
        assert ref.entity_id == "ent_123"
        assert ref.entity_type == "person"

    def test_entity_ref_default_type(self):
        """K1EntityRef has default empty type."""
        ref = K1EntityRef(entity_id="ent_123")
        assert ref.entity_type == ""


# =============================================================================
# Test: Ontological Layers
# =============================================================================

class TestOntologicalLayers:
    """Tests for OntologicalLayer enum."""

    def test_10_layers(self):
        """There are exactly 10 ontological layers."""
        assert len(ALL_LAYERS) == 10

    def test_layer_naming(self):
        """Layers are named O1 through O10."""
        layer_names = [l.value for l in ALL_LAYERS]
        assert "O1_THINKING" in layer_names
        assert "O10_ABSOLVING" in layer_names


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
