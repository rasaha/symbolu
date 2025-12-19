"""
Phase-13: K1 Store - Knowledge Storage and Retrieval (Minimal)
==============================================================

K1Store provides:
    - Deterministic storage and retrieval of K1 atoms
    - Indexed access by (layer, slot, discourse_act)
    - Ledger integration for audit trail
    - Replay-provable queries

INVARIANTS:
    - Same query over same store state → same ordered results
    - Indices are derived structures; rebuildable from atoms
    - Every query writes to ledger
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from k1_schema import (
    K1Atom,
    K1Query,
    K1ResultSet,
    K1Slot,
    K1SlotTier,
    OntologicalLayer,
    DiscourseAct,
    SelectionRule,
    RetrievalStep,
    compute_result_hash,
)


# =============================================================================
# Ledger Entry
# =============================================================================

@dataclass(frozen=True)
class LedgerEntry:
    """Ledger entry for K1 operations."""
    entry_id: str
    operation: str              # "QUERY", "ADD", "REMOVE"
    timestamp_ms: int
    query_hash: Optional[str]   # For QUERY operations
    result_hash: Optional[str]  # For QUERY operations
    atom_ids: Tuple[str, ...]
    store_version_id: str
    success: bool
    failure_reason: Optional[str] = None

    def entry_hash(self) -> str:
        """Compute deterministic hash of entry."""
        content = (
            f"{self.entry_id}|{self.operation}|{self.timestamp_ms}|"
            f"{self.query_hash or 'none'}|{self.result_hash or 'none'}|"
            f"{'_'.join(self.atom_ids)}|{self.store_version_id}|{self.success}"
        )
        return hashlib.sha256(content.encode()).hexdigest()[:16]


# =============================================================================
# K1 Store (Minimal)
# =============================================================================

@dataclass
class K1Store:
    """
    K1 Knowledge Store with indexed retrieval.

    Primary Index: (layer, slot, discourse_act)

    INVARIANT: Same query over same store state returns same ordered results.
    """

    # Primary storage
    _atoms: Dict[str, K1Atom] = field(default_factory=dict)

    # Primary composite index: (layer, slot, discourse_act) -> atom_ids
    _idx_primary: Dict[Tuple[str, str, str], Set[str]] = field(default_factory=dict)

    # Secondary indices for partial queries
    _idx_layer: Dict[str, Set[str]] = field(default_factory=dict)
    _idx_slot: Dict[str, Set[str]] = field(default_factory=dict)
    _idx_discourse_act: Dict[str, Set[str]] = field(default_factory=dict)

    # Ledger
    _ledger: List[LedgerEntry] = field(default_factory=list)

    # Version tracking
    _version: int = 0

    # ==========================================================================
    # Version Management
    # ==========================================================================

    @property
    def version_id(self) -> str:
        """Get current store version ID."""
        return f"v{self._version}"

    def _increment_version(self) -> None:
        """Increment store version."""
        self._version += 1

    # ==========================================================================
    # Index Management
    # ==========================================================================

    def _add_to_indices(self, atom: K1Atom) -> None:
        """Add atom to all indices."""
        atom_id = atom.atom_id

        # Primary composite index
        key = (atom.layer.value, atom.slot.value, atom.discourse_act.value)
        if key not in self._idx_primary:
            self._idx_primary[key] = set()
        self._idx_primary[key].add(atom_id)

        # Layer index
        if atom.layer.value not in self._idx_layer:
            self._idx_layer[atom.layer.value] = set()
        self._idx_layer[atom.layer.value].add(atom_id)

        # Slot index
        if atom.slot.value not in self._idx_slot:
            self._idx_slot[atom.slot.value] = set()
        self._idx_slot[atom.slot.value].add(atom_id)

        # Discourse act index
        if atom.discourse_act.value not in self._idx_discourse_act:
            self._idx_discourse_act[atom.discourse_act.value] = set()
        self._idx_discourse_act[atom.discourse_act.value].add(atom_id)

    def _remove_from_indices(self, atom: K1Atom) -> None:
        """Remove atom from all indices."""
        atom_id = atom.atom_id

        # Primary composite index
        key = (atom.layer.value, atom.slot.value, atom.discourse_act.value)
        if key in self._idx_primary:
            self._idx_primary[key].discard(atom_id)

        # Layer index
        if atom.layer.value in self._idx_layer:
            self._idx_layer[atom.layer.value].discard(atom_id)

        # Slot index
        if atom.slot.value in self._idx_slot:
            self._idx_slot[atom.slot.value].discard(atom_id)

        # Discourse act index
        if atom.discourse_act.value in self._idx_discourse_act:
            self._idx_discourse_act[atom.discourse_act.value].discard(atom_id)

    def rebuild_indices(self) -> None:
        """Rebuild all indices from atoms (for recovery/verification)."""
        self._idx_primary.clear()
        self._idx_layer.clear()
        self._idx_slot.clear()
        self._idx_discourse_act.clear()

        for atom in self._atoms.values():
            self._add_to_indices(atom)

    # ==========================================================================
    # Ledger Management
    # ==========================================================================

    def _log_operation(
        self,
        operation: str,
        atom_ids: Tuple[str, ...],
        success: bool,
        query_hash: Optional[str] = None,
        result_hash: Optional[str] = None,
        failure_reason: Optional[str] = None,
    ) -> LedgerEntry:
        """Log an operation to the ledger."""
        entry = LedgerEntry(
            entry_id=f"le_{len(self._ledger):08d}",
            operation=operation,
            timestamp_ms=int(time.time() * 1000),
            query_hash=query_hash,
            result_hash=result_hash,
            atom_ids=atom_ids,
            store_version_id=self.version_id,
            success=success,
            failure_reason=failure_reason,
        )
        self._ledger.append(entry)
        return entry

    def get_ledger(self) -> Tuple[LedgerEntry, ...]:
        """Get all ledger entries."""
        return tuple(self._ledger)

    def get_ledger_since(self, entry_id: str) -> Tuple[LedgerEntry, ...]:
        """Get ledger entries since a given entry ID."""
        found = False
        result = []
        for entry in self._ledger:
            if found:
                result.append(entry)
            elif entry.entry_id == entry_id:
                found = True
        return tuple(result)

    # ==========================================================================
    # Write Operations
    # ==========================================================================

    def add_atom(self, atom: K1Atom) -> Tuple[bool, Optional[str]]:
        """
        Add an atom to the store.

        Returns:
            (success, error_message)
        """
        # Check for duplicate
        if atom.atom_id in self._atoms:
            self._log_operation(
                "ADD", (atom.atom_id,), False,
                failure_reason="Duplicate atom_id"
            )
            return False, "Duplicate atom_id"

        # Add to store
        self._atoms[atom.atom_id] = atom
        self._add_to_indices(atom)
        self._increment_version()

        self._log_operation("ADD", (atom.atom_id,), True)
        return True, None

    def add_atoms(self, atoms: Tuple[K1Atom, ...]) -> Tuple[bool, Optional[str]]:
        """
        Add multiple atoms atomically.

        Either all succeed or none are added.
        """
        # Check for duplicates
        atom_ids = [a.atom_id for a in atoms]
        for atom_id in atom_ids:
            if atom_id in self._atoms:
                return False, f"Duplicate atom_id: {atom_id}"

        # Check for internal duplicates
        if len(atom_ids) != len(set(atom_ids)):
            return False, "Duplicate atom_ids in batch"

        # Add all atoms
        for atom in atoms:
            self._atoms[atom.atom_id] = atom
            self._add_to_indices(atom)

        self._increment_version()
        self._log_operation("ADD", tuple(atom_ids), True)
        return True, None

    def remove_atom(self, atom_id: str) -> Tuple[bool, Optional[str]]:
        """Remove an atom from the store."""
        if atom_id not in self._atoms:
            self._log_operation(
                "REMOVE", (atom_id,), False,
                failure_reason="Atom not found"
            )
            return False, "Atom not found"

        atom = self._atoms[atom_id]
        self._remove_from_indices(atom)
        del self._atoms[atom_id]
        self._increment_version()

        self._log_operation("REMOVE", (atom_id,), True)
        return True, None

    # ==========================================================================
    # Read Operations
    # ==========================================================================

    def get_atom(self, atom_id: str) -> Optional[K1Atom]:
        """Get a single atom by ID."""
        return self._atoms.get(atom_id)

    def get_all_atoms(self) -> Tuple[K1Atom, ...]:
        """Get all atoms in the store."""
        return tuple(self._atoms.values())

    def count(self) -> int:
        """Get total number of atoms."""
        return len(self._atoms)

    # ==========================================================================
    # Query Execution
    # ==========================================================================

    def query(self, q: K1Query) -> K1ResultSet:
        """
        Execute a query and return results.

        INVARIANT: Same query over same store state → same ordered results.
        """
        steps: List[RetrievalStep] = []

        # Step 1: Initial candidate set from indices
        candidates: Set[str]

        # Use most specific index available
        if q.layer and q.slot and q.discourse_act:
            # Use primary composite index
            key = (q.layer.value, q.slot.value, q.discourse_act.value)
            candidates = self._idx_primary.get(key, set()).copy()
        elif q.layer and q.slot:
            # Intersect layer and slot
            layer_set = self._idx_layer.get(q.layer.value, set())
            slot_set = self._idx_slot.get(q.slot.value, set())
            candidates = layer_set.intersection(slot_set)
        elif q.layer and q.discourse_act:
            # Intersect layer and discourse_act
            layer_set = self._idx_layer.get(q.layer.value, set())
            act_set = self._idx_discourse_act.get(q.discourse_act.value, set())
            candidates = layer_set.intersection(act_set)
        elif q.slot and q.discourse_act:
            # Intersect slot and discourse_act
            slot_set = self._idx_slot.get(q.slot.value, set())
            act_set = self._idx_discourse_act.get(q.discourse_act.value, set())
            candidates = slot_set.intersection(act_set)
        elif q.layer:
            candidates = self._idx_layer.get(q.layer.value, set()).copy()
        elif q.slot:
            candidates = self._idx_slot.get(q.slot.value, set()).copy()
        elif q.discourse_act:
            candidates = self._idx_discourse_act.get(q.discourse_act.value, set()).copy()
        else:
            candidates = set(self._atoms.keys())

        initial_count = len(candidates)
        steps.append(RetrievalStep(
            step_type="index_lookup",
            input_count=len(self._atoms),
            output_count=initial_count,
            step_hash=hashlib.sha256(f"index:{initial_count}".encode()).hexdigest()[:8],
        ))

        # Step 2: Filter by additional query constraints
        filtered: List[K1Atom] = []
        for atom_id in candidates:
            atom = self._atoms.get(atom_id)
            if atom and q.matches(atom):
                filtered.append(atom)

        steps.append(RetrievalStep(
            step_type="filter",
            input_count=initial_count,
            output_count=len(filtered),
            step_hash=hashlib.sha256(f"filter:{len(filtered)}".encode()).hexdigest()[:8],
        ))

        # Step 3: Sort by selection rule (deterministic)
        if q.selection_rule == SelectionRule.LEXICOGRAPHIC_ID:
            filtered.sort(key=lambda a: a.atom_id)
        elif q.selection_rule == SelectionRule.TIER_PRIORITY:
            # Lower tier number first
            tier_order = {
                "TIER_1_CORE": 1,
                "TIER_2_CONTROL": 2,
                "TIER_3_FRAMING": 3,
                "TIER_4_GOVERNANCE": 4,
            }
            filtered.sort(key=lambda a: (tier_order.get(a.get_slot_tier().value, 5), a.atom_id))
        elif q.selection_rule == SelectionRule.LAYER_ORDER:
            # O1 before O2, etc.
            filtered.sort(key=lambda a: (a.layer.value, a.atom_id))

        steps.append(RetrievalStep(
            step_type="sort",
            input_count=len(filtered),
            output_count=len(filtered),
            step_hash=hashlib.sha256(f"sort:{q.selection_rule.value}".encode()).hexdigest()[:8],
        ))

        # Step 4: Apply limit
        limited = filtered[:q.limit]

        steps.append(RetrievalStep(
            step_type="limit",
            input_count=len(filtered),
            output_count=len(limited),
            step_hash=hashlib.sha256(f"limit:{q.limit}".encode()).hexdigest()[:8],
        ))

        # Build result
        atom_ids = tuple(a.atom_id for a in limited)
        query_hash = q.query_hash()
        result_hash = compute_result_hash(query_hash, atom_ids)
        ledger_span_id = f"span_{hashlib.sha256(f'{query_hash}_{time.time()}'.encode()).hexdigest()[:12]}"

        # Log to ledger
        self._log_operation(
            "QUERY",
            atom_ids,
            True,
            query_hash=query_hash,
            result_hash=result_hash,
        )

        return K1ResultSet(
            atoms=tuple(limited),
            query_hash=query_hash,
            result_hash=result_hash,
            ledger_span_id=ledger_span_id,
            store_version_id=self.version_id,
            replay_proof=tuple(steps),
        )

    # ==========================================================================
    # Store Info
    # ==========================================================================

    def store_hash(self) -> str:
        """Compute deterministic hash of entire store state."""
        # Sort atom IDs for determinism
        sorted_ids = sorted(self._atoms.keys())
        atom_hashes = "_".join(self._atoms[aid].atom_hash() for aid in sorted_ids)
        content = f"v{self._version}|{len(self._atoms)}|{atom_hashes}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def index_stats(self) -> Dict[str, int]:
        """Get index statistics."""
        return {
            "primary_keys": len(self._idx_primary),
            "layer_keys": len(self._idx_layer),
            "slot_keys": len(self._idx_slot),
            "discourse_act_keys": len(self._idx_discourse_act),
        }


# =============================================================================
# Factory Functions
# =============================================================================

def create_empty_store() -> K1Store:
    """Create an empty K1 store."""
    return K1Store()


def create_store_from_atoms(atoms: Tuple[K1Atom, ...]) -> Tuple[K1Store, Optional[str]]:
    """
    Create a store pre-populated with atoms.

    Returns:
        (store, error_message) - error_message is None on success
    """
    store = K1Store()
    success, error = store.add_atoms(atoms)
    if not success:
        return store, error
    return store, None


# =============================================================================
# Public Exports
# =============================================================================

__all__ = [
    # Types
    "LedgerEntry",
    "K1Store",
    # Factory functions
    "create_empty_store",
    "create_store_from_atoms",
]
