"""
Unit Tests for Phase-9.0 Graph Rewriting Engine (v0)
=====================================================

Minimal tests covering:
    - Canonicalization determinism
    - Idempotence
    - Exact quotient correctness
    - Reversibility
    - Fail-closed behavior

Version: 0.0
"""

import hashlib
import unittest
from dataclasses import dataclass
from typing import Tuple

from phase9_rewrite_engine_v0 import (
    PHASE9_ENGINE_VERSION,
    PHASE9_INVARIANTS,
    RewriteStatus,
    RewriteType,
    Phase9Node,
    Phase9Edge,
    Phase9Graph,
    Phase9RewriteResult,
    rewrite_phase7_to_phase9,
    validate_phase9_invariants,
    verify_expansion_map_reversibility,
    _canonicalize_graph,
    _apply_exact_quotient,
    _verify_canonicalization_idempotent,
    _compute_graph_hash,
    REWRITE_BLOCKED,
)


# ============================================================================
# TEST FIXTURES
# ============================================================================

def make_node(node_id: str, node_type: int = 0, degree: int = 0,
              flags: Tuple[bool, ...] = (True,)) -> Phase9Node:
    """Helper to create a Phase9Node with deterministic hashes."""
    struct_hash_input = f"{node_type}|{degree}|{flags}"
    structural_hash = hashlib.sha256(struct_hash_input.encode()).hexdigest()[:16]
    return Phase9Node(
        node_id=node_id,
        node_type=node_type,
        structural_hash=structural_hash,
        degree=degree,
        flags=flags
    )


def make_edge(source_id: str, target_id: str, edge_type: int = 0,
              direction: int = 0) -> Phase9Edge:
    """Helper to create a Phase9Edge with deterministic hashes."""
    edge_hash_input = f"{source_id}|{target_id}|{edge_type}|{direction}"
    edge_hash = hashlib.sha256(edge_hash_input.encode()).hexdigest()[:16]
    return Phase9Edge(
        source_id=source_id,
        target_id=target_id,
        edge_type=edge_type,
        direction=direction,
        edge_hash=edge_hash
    )


def make_graph(nodes: Tuple[Phase9Node, ...], edges: Tuple[Phase9Edge, ...],
               source_hash: str = "a" * 16) -> Phase9Graph:
    """Helper to create a Phase9Graph."""
    graph_hash = _compute_graph_hash(nodes, edges)
    return Phase9Graph(
        nodes=nodes,
        edges=edges,
        graph_hash=graph_hash,
        source_phase7_hash=source_hash
    )


# Mock Phase-7 artifact for testing
@dataclass(frozen=True)
class MockPhase7FoldedUnit:
    """Mock Phase-7 folded unit."""
    source_phase5_indices: Tuple[int, ...]
    aggregated_fold_vector: Tuple[int, ...]
    fold_adjacency: Tuple[int, ...]
    eligibility_chain: Tuple[bool, ...]
    unit_hash: str


@dataclass(frozen=True)
class MockPhase7FoldedArtifact:
    """Mock Phase-7 folded artifact."""
    folded_units: Tuple[MockPhase7FoldedUnit, ...]
    fold_graph: Tuple[Tuple[int, ...], ...]
    folding_hash: str
    source_phase5_hashes: Tuple[str, ...]
    reversible: bool
    eligible: bool


def make_mock_phase7_unit(idx: int, unit_hash: str = None) -> MockPhase7FoldedUnit:
    """Create a mock Phase-7 unit."""
    if unit_hash is None:
        unit_hash = hashlib.sha256(f"unit_{idx}".encode()).hexdigest()[:16]
    return MockPhase7FoldedUnit(
        source_phase5_indices=(idx,),
        aggregated_fold_vector=(1, 1, 1),
        fold_adjacency=(0, 1),
        eligibility_chain=(True,),
        unit_hash=unit_hash
    )


def make_mock_phase7_artifact(
    num_units: int = 3,
    eligible: bool = True,
    with_edges: bool = True
) -> MockPhase7FoldedArtifact:
    """Create a mock Phase-7 artifact."""
    units = tuple(make_mock_phase7_unit(i) for i in range(num_units))

    # Create adjacency graph (chain structure)
    fold_graph = []
    for i in range(num_units):
        row = []
        for j in range(num_units):
            if with_edges and abs(i - j) == 1:
                row.append(1)
            else:
                row.append(0)
        fold_graph.append(tuple(row))

    folding_hash = hashlib.sha256(f"folding_{num_units}".encode()).hexdigest()[:32]

    return MockPhase7FoldedArtifact(
        folded_units=units,
        fold_graph=tuple(fold_graph),
        folding_hash=folding_hash,
        source_phase5_hashes=("a" * 16,),
        reversible=True,
        eligible=eligible
    )


# ============================================================================
# CANONICALIZATION TESTS
# ============================================================================

class TestCanonicalization(unittest.TestCase):
    """Tests for Rewrite A - Canonicalization."""

    def test_canonicalization_determinism_same_input(self):
        """Same input always produces same canonical output."""
        node1 = make_node("b" * 16, node_type=1, degree=2)
        node2 = make_node("a" * 16, node_type=0, degree=1)
        edge1 = make_edge("b" * 16, "a" * 16)

        graph = make_graph((node1, node2), (edge1,))

        canon1, trace1 = _canonicalize_graph(graph)
        canon2, trace2 = _canonicalize_graph(graph)

        self.assertEqual(canon1.graph_hash, canon2.graph_hash)
        self.assertEqual(canon1.nodes, canon2.nodes)
        self.assertEqual(canon1.edges, canon2.edges)

    def test_canonicalization_determinism_different_order(self):
        """Different input orders produce same canonical output."""
        node_a = make_node("a" * 16, node_type=0, degree=1)
        node_b = make_node("b" * 16, node_type=1, degree=2)
        edge = make_edge("a" * 16, "b" * 16)

        # Order 1: A, B
        graph1 = make_graph((node_a, node_b), (edge,))
        # Order 2: B, A
        graph2 = make_graph((node_b, node_a), (edge,))

        canon1, _ = _canonicalize_graph(graph1)
        canon2, _ = _canonicalize_graph(graph2)

        self.assertEqual(canon1.graph_hash, canon2.graph_hash)
        self.assertEqual(canon1.nodes, canon2.nodes)

    def test_canonicalization_idempotence(self):
        """Canonicalizing a canonical graph returns same graph."""
        node1 = make_node("c" * 16, node_type=2, degree=0)
        node2 = make_node("d" * 16, node_type=1, degree=1)
        edge1 = make_edge("c" * 16, "d" * 16)

        graph = make_graph((node1, node2), (edge1,))

        canon1, trace1 = _canonicalize_graph(graph)
        canon2, trace2 = _canonicalize_graph(canon1)

        self.assertEqual(canon1.graph_hash, canon2.graph_hash)
        self.assertEqual(len(trace2), 0)  # No changes on second canonicalization

    def test_canonicalization_idempotence_verify(self):
        """Verify idempotence using dedicated function."""
        node1 = make_node("e" * 16, node_type=0, degree=0)
        node2 = make_node("f" * 16, node_type=0, degree=0)

        graph = make_graph((node2, node1), ())

        self.assertTrue(_verify_canonicalization_idempotent(graph))

    def test_canonicalization_uses_structural_hash_primary(self):
        """Nodes are ordered primarily by structural_hash."""
        # Create nodes with different structural hashes
        node_high = make_node("a" * 16, node_type=1, degree=5)  # type=1, degree=5 -> higher hash
        node_low = make_node("f" * 16, node_type=0, degree=0)   # type=0, degree=0 -> lower hash

        graph = make_graph((node_high, node_low), ())

        canon, _ = _canonicalize_graph(graph)

        # Lower structural hash should come first
        first_hash = canon.nodes[0].structural_hash
        second_hash = canon.nodes[1].structural_hash
        self.assertLessEqual(first_hash, second_hash)

    def test_canonicalization_tie_break_by_node_id(self):
        """When structural_hash ties, use node_id."""
        # Create nodes with same properties (same structural hash)
        node_a = make_node("a" * 16, node_type=0, degree=0)
        node_f = make_node("f" * 16, node_type=0, degree=0)

        graph = make_graph((node_f, node_a), ())

        canon, _ = _canonicalize_graph(graph)

        # Should be sorted by node_id after structural_hash tie
        self.assertEqual(canon.nodes[0].node_id, "a" * 16)
        self.assertEqual(canon.nodes[1].node_id, "f" * 16)

    def test_canonicalization_empty_graph(self):
        """Empty graph remains empty after canonicalization."""
        graph = make_graph((), ())

        canon, trace = _canonicalize_graph(graph)

        self.assertEqual(len(canon.nodes), 0)
        self.assertEqual(len(canon.edges), 0)
        self.assertEqual(len(trace), 0)

    def test_canonicalization_preserves_structure(self):
        """Canonicalization does not modify graph structure."""
        node1 = make_node("a" * 16, node_type=0, degree=1)
        node2 = make_node("b" * 16, node_type=1, degree=1)
        edge = make_edge("a" * 16, "b" * 16, edge_type=1, direction=1)

        graph = make_graph((node1, node2), (edge,))

        canon, _ = _canonicalize_graph(graph)

        # Same nodes (content)
        orig_node_ids = {n.node_id for n in graph.nodes}
        canon_node_ids = {n.node_id for n in canon.nodes}
        self.assertEqual(orig_node_ids, canon_node_ids)

        # Same edges (content)
        orig_edge_pairs = {(e.source_id, e.target_id) for e in graph.edges}
        canon_edge_pairs = {(e.source_id, e.target_id) for e in canon.edges}
        self.assertEqual(orig_edge_pairs, canon_edge_pairs)


# ============================================================================
# EXACT QUOTIENT TESTS
# ============================================================================

class TestExactQuotient(unittest.TestCase):
    """Tests for Rewrite B - Exact Structural Quotient."""

    def test_quotient_merges_identical_nodes(self):
        """Identical nodes should be merged."""
        # Two identical nodes (same type, degree, flags)
        node1 = make_node("a" * 16, node_type=0, degree=0, flags=(True,))
        node2 = make_node("b" * 16, node_type=0, degree=0, flags=(True,))
        node3 = make_node("c" * 16, node_type=1, degree=0, flags=(True,))  # Different type

        graph = make_graph((node1, node2, node3), ())

        merged, exp_map, trace, success = _apply_exact_quotient(graph)

        self.assertTrue(success)
        self.assertIsNotNone(merged)
        self.assertEqual(len(merged.nodes), 2)  # node1 and node2 merged, node3 separate
        self.assertIsNotNone(exp_map)
        self.assertEqual(len(exp_map), 1)  # One merge group

    def test_quotient_no_merge_different_types(self):
        """Nodes with different types should not merge."""
        node1 = make_node("a" * 16, node_type=0, degree=0)
        node2 = make_node("b" * 16, node_type=1, degree=0)
        node3 = make_node("c" * 16, node_type=2, degree=0)

        graph = make_graph((node1, node2, node3), ())

        merged, exp_map, trace, success = _apply_exact_quotient(graph)

        self.assertTrue(success)
        self.assertEqual(len(merged.nodes), 3)  # No merges
        self.assertIsNone(exp_map)  # No expansion map needed

    def test_quotient_no_merge_different_degree(self):
        """Nodes with different degrees should not merge."""
        node1 = make_node("a" * 16, node_type=0, degree=0)
        node2 = make_node("b" * 16, node_type=0, degree=1)

        graph = make_graph((node1, node2), ())

        merged, exp_map, trace, success = _apply_exact_quotient(graph)

        self.assertTrue(success)
        self.assertEqual(len(merged.nodes), 2)  # No merges
        self.assertIsNone(exp_map)

    def test_quotient_no_merge_different_flags(self):
        """Nodes with different flags should not merge."""
        node1 = make_node("a" * 16, node_type=0, degree=0, flags=(True,))
        node2 = make_node("b" * 16, node_type=0, degree=0, flags=(False,))

        graph = make_graph((node1, node2), ())

        merged, exp_map, trace, success = _apply_exact_quotient(graph)

        self.assertTrue(success)
        self.assertEqual(len(merged.nodes), 2)  # No merges

    def test_quotient_expansion_map_correctness(self):
        """Expansion map should correctly track merged nodes."""
        # Three identical nodes
        node1 = make_node("a" * 16, node_type=0, degree=0, flags=(True,))
        node2 = make_node("b" * 16, node_type=0, degree=0, flags=(True,))
        node3 = make_node("c" * 16, node_type=0, degree=0, flags=(True,))

        graph = make_graph((node1, node2, node3), ())

        merged, exp_map, trace, success = _apply_exact_quotient(graph)

        self.assertTrue(success)
        self.assertIsNotNone(exp_map)

        # The representative (lexicographically first) should be "a" * 16
        rep_id = "a" * 16
        self.assertIn(rep_id, exp_map)

        # Merged IDs should be the other two
        merged_ids = exp_map[rep_id]
        self.assertIn("b" * 16, merged_ids)
        self.assertIn("c" * 16, merged_ids)

    def test_quotient_empty_graph(self):
        """Empty graph has no quotient operation."""
        graph = make_graph((), ())

        merged, exp_map, trace, success = _apply_exact_quotient(graph)

        self.assertTrue(success)
        self.assertEqual(len(merged.nodes), 0)
        self.assertIsNone(exp_map)


# ============================================================================
# REVERSIBILITY TESTS
# ============================================================================

class TestReversibility(unittest.TestCase):
    """Tests for reversibility guarantee."""

    def test_expansion_map_reversibility(self):
        """Expansion map should allow recovery of original node count."""
        # Create nodes with identical structure
        node1 = make_node("a" * 16, node_type=0, degree=0, flags=(True,))
        node2 = make_node("b" * 16, node_type=0, degree=0, flags=(True,))
        node3 = make_node("c" * 16, node_type=1, degree=0, flags=(True,))

        original_graph = make_graph((node1, node2, node3), ())

        merged, exp_map, trace, success = _apply_exact_quotient(original_graph)

        self.assertTrue(success)
        self.assertIsNotNone(exp_map)

        # Verify reversibility
        is_reversible = verify_expansion_map_reversibility(
            original_graph, merged, exp_map
        )
        self.assertTrue(is_reversible)

    def test_no_expansion_map_is_reversible(self):
        """No expansion map (no merges) is trivially reversible."""
        node1 = make_node("a" * 16, node_type=0, degree=0)
        node2 = make_node("b" * 16, node_type=1, degree=0)

        graph = make_graph((node1, node2), ())

        is_reversible = verify_expansion_map_reversibility(graph, graph, None)
        self.assertTrue(is_reversible)


# ============================================================================
# FAIL-CLOSED TESTS
# ============================================================================

class TestFailClosed(unittest.TestCase):
    """Tests for fail-closed behavior."""

    def test_blocked_on_none_input(self):
        """None input should produce blocked result."""
        result = rewrite_phase7_to_phase9(None)

        self.assertEqual(result.status, RewriteStatus.BLOCKED)
        self.assertIsNone(result.phase9_graph)

    def test_blocked_on_ineligible_input(self):
        """Ineligible Phase-7 artifact should produce blocked result."""
        artifact = make_mock_phase7_artifact(eligible=False)

        result = rewrite_phase7_to_phase9(artifact)

        self.assertEqual(result.status, RewriteStatus.BLOCKED)
        self.assertIsNone(result.phase9_graph)

    def test_blocked_on_empty_units(self):
        """Phase-7 artifact with no units should produce blocked result."""
        artifact = MockPhase7FoldedArtifact(
            folded_units=(),
            fold_graph=(),
            folding_hash="a" * 32,
            source_phase5_hashes=("b" * 16,),
            reversible=True,
            eligible=True
        )

        result = rewrite_phase7_to_phase9(artifact)

        self.assertEqual(result.status, RewriteStatus.BLOCKED)

    def test_trace_contains_blocked_reason(self):
        """Blocked result should have trace with reason."""
        result = rewrite_phase7_to_phase9(None)

        self.assertGreater(len(result.rewrite_trace), 0)
        # First trace entry should indicate conversion blocked
        first_trace = result.rewrite_trace[0]
        self.assertIn("blocked", first_trace[1])


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration(unittest.TestCase):
    """Integration tests for full rewrite pipeline."""

    def test_full_rewrite_canonicalization_only(self):
        """Full rewrite with canonicalization only."""
        artifact = make_mock_phase7_artifact(num_units=3)

        result = rewrite_phase7_to_phase9(artifact, enable_exact_quotient=False)

        self.assertIn(result.status, (RewriteStatus.SUCCESS, RewriteStatus.NO_CHANGE))
        self.assertIsNotNone(result.phase9_graph)
        self.assertIsNotNone(result.phase9_hash)
        self.assertGreaterEqual(len(result.phase9_hash), 16)
        self.assertIsNone(result.expansion_map)  # Quotient not enabled

    def test_full_rewrite_with_quotient(self):
        """Full rewrite with exact quotient enabled."""
        artifact = make_mock_phase7_artifact(num_units=3)

        result = rewrite_phase7_to_phase9(artifact, enable_exact_quotient=True)

        self.assertIn(result.status, (RewriteStatus.SUCCESS, RewriteStatus.NO_CHANGE))
        self.assertIsNotNone(result.phase9_graph)

    def test_execution_order_canonicalization_first(self):
        """Canonicalization should be applied before quotient."""
        artifact = make_mock_phase7_artifact(num_units=2)

        result = rewrite_phase7_to_phase9(artifact, enable_exact_quotient=True)

        if result.status == RewriteStatus.SUCCESS and len(result.rewrites_applied) > 0:
            # If canonicalization was applied, it should be first
            if RewriteType.CANONICALIZATION in result.rewrites_applied:
                first_rewrite_idx = list(result.rewrites_applied).index(RewriteType.CANONICALIZATION)
                if RewriteType.EXACT_QUOTIENT in result.rewrites_applied:
                    quotient_idx = list(result.rewrites_applied).index(RewriteType.EXACT_QUOTIENT)
                    self.assertLess(first_rewrite_idx, quotient_idx)

    def test_required_outputs_present(self):
        """All required outputs should be present."""
        artifact = make_mock_phase7_artifact()

        result = rewrite_phase7_to_phase9(artifact, enable_exact_quotient=True)

        # phase9_graph
        if result.status != RewriteStatus.BLOCKED:
            self.assertIsNotNone(result.phase9_graph)

        # phase9_hash
        self.assertIsNotNone(result.phase9_hash)
        self.assertGreaterEqual(len(result.phase9_hash), 16)

        # rewrite_trace
        self.assertIsNotNone(result.rewrite_trace)
        self.assertIsInstance(result.rewrite_trace, tuple)

        # status
        self.assertIsNotNone(result.status)
        self.assertIsInstance(result.status, RewriteStatus)

    def test_determinism_multiple_runs(self):
        """Multiple runs with same input produce same output."""
        artifact = make_mock_phase7_artifact(num_units=4)

        result1 = rewrite_phase7_to_phase9(artifact, enable_exact_quotient=True)
        result2 = rewrite_phase7_to_phase9(artifact, enable_exact_quotient=True)

        self.assertEqual(result1.phase9_hash, result2.phase9_hash)
        self.assertEqual(result1.status, result2.status)
        self.assertEqual(result1.rewrite_trace, result2.rewrite_trace)


# ============================================================================
# INVARIANT TESTS
# ============================================================================

class TestInvariants(unittest.TestCase):
    """Tests for Phase-9 invariants."""

    def test_all_invariants_enabled(self):
        """All invariants should be True."""
        self.assertTrue(validate_phase9_invariants())

        for key, value in PHASE9_INVARIANTS.items():
            self.assertTrue(value, f"Invariant {key} should be True")

    def test_version_defined(self):
        """Engine version should be defined."""
        self.assertEqual(PHASE9_ENGINE_VERSION, "0.0")

    def test_no_probability_in_output(self):
        """Output should not contain probability-like values."""
        artifact = make_mock_phase7_artifact()

        result = rewrite_phase7_to_phase9(artifact)

        if result.phase9_graph is not None:
            for node in result.phase9_graph.nodes:
                # Node type should be int, not float
                self.assertIsInstance(node.node_type, int)
                # Degree should be int
                self.assertIsInstance(node.degree, int)
                # Flags should be bool
                for f in node.flags:
                    self.assertIsInstance(f, bool)


# ============================================================================
# NODE/EDGE VALIDATION TESTS
# ============================================================================

class TestValidation(unittest.TestCase):
    """Tests for node and edge validation."""

    def test_node_invalid_id_length(self):
        """Node with invalid ID length should raise."""
        with self.assertRaises(ValueError) as ctx:
            Phase9Node(
                node_id="abc",  # Too short
                node_type=0,
                structural_hash="a" * 16,
                degree=0,
                flags=(True,)
            )
        self.assertIn("node_id must be 16-32 chars", str(ctx.exception))

    def test_node_invalid_hash_chars(self):
        """Node with non-hex hash should raise."""
        with self.assertRaises(ValueError) as ctx:
            Phase9Node(
                node_id="a" * 16,
                node_type=0,
                structural_hash="x" * 16,  # Not hex
                degree=0,
                flags=(True,)
            )
        self.assertIn("structural_hash must be hex", str(ctx.exception))

    def test_edge_invalid_direction(self):
        """Edge with invalid direction should raise."""
        with self.assertRaises(ValueError) as ctx:
            Phase9Edge(
                source_id="a" * 16,
                target_id="b" * 16,
                edge_type=0,
                direction=2,  # Invalid
                edge_hash="c" * 16
            )
        self.assertIn("direction must be -1, 0, or 1", str(ctx.exception))

    def test_graph_invalid_node_type(self):
        """Graph with non-Phase9Node should raise."""
        with self.assertRaises(ValueError) as ctx:
            Phase9Graph(
                nodes=("not a node",),
                edges=(),
                graph_hash="a" * 16,
                source_phase7_hash="b" * 16
            )
        self.assertIn("nodes must contain only Phase9Node", str(ctx.exception))


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
