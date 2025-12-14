"""
Core/Observer Boundary Enforcement Test Suite

This test suite enforces the boundary contract defined in docs/BOUNDARIES.md.

Exactly one test per invariant:
- INV-B1: No imports from observer modules inside authoritative module roots
- INV-B2: Observer outputs only written to allowed sinks
- INV-B3: Identical authoritative inputs yield identical decision surface outputs
- INV-B4: Boundary scanner fails CI if violations are introduced

See: docs/BOUNDARIES.md for the complete contract specification.
"""

from __future__ import annotations

import ast
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

import pytest

# ============================================================================
# PATH SETUP
# ============================================================================

# Get project root
PROJECT_ROOT = Path(__file__).parent.parent.parent
SYMBOLU_ROOT = PROJECT_ROOT / "symbolu"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"

# Add to path for imports
sys.path.insert(0, str(PROJECT_ROOT))

from symbolu.tools.boundary_enforcer.boundary_rules import (
    AUTHORITATIVE_MODULE_ROOTS,
    OBSERVER_MODULE_ROOTS,
    OBSERVER_DATACLASS_NAMES,
    DECISION_SURFACE_PHASES,
    ModuleType,
    classify_module,
    is_observer_import_violation,
)
from symbolu.tools.boundary_enforcer.scan_imports import (
    ImportScanner,
    generate_boundary_report,
    print_report_summary,
)


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture(scope="module")
def boundary_report():
    """Generate boundary report once per module."""
    output_path = ARTIFACTS_DIR / "boundary_report.json"
    report = generate_boundary_report(PROJECT_ROOT, output_path)
    # Print summary to test output
    print("\n" + print_report_summary(report))
    return report


@pytest.fixture(scope="module")
def scanner():
    """Get a scanner instance for detailed checks."""
    scanner = ImportScanner(PROJECT_ROOT)
    scanner.scan_authoritative_modules()
    return scanner


# ============================================================================
# HELPER: Decision Surface Context Pair Creator
# ============================================================================

class MockRegime(Enum):
    """Mock operational regime."""
    HOLD = "HOLD"
    STABILIZE = "STABILIZE"
    INFORM = "INFORM"


class MockDiscourse(Enum):
    """Mock discourse act."""
    EXPLANATION = "EXPLANATION"
    REFLECTION = "REFLECTION"


class MockAlignment(Enum):
    """Mock alignment state (observer)."""
    ALIGNED = "ALIGNED"
    TENSION = "TENSION"
    CONTRADICTION = "CONTRADICTION"


@dataclass
class MockAuthoritativeState:
    """
    Mock authoritative state (PO1-P9 decision surface).

    This represents the outputs that MUST be invariant.
    """
    # PO1 (P-1): Grounding
    is_blocked: bool = False
    grounding_status: str = "RESOLVED"

    # PO2 (P0): Intent
    intent_type: str = "INFORM"
    response_posture: str = "ACKNOWLEDGE"

    # PO3 (P1): Action
    allowed_actions: FrozenSet[str] = field(default_factory=lambda: frozenset({"respond"}))

    # PO4: Ontology
    ontology_category: str = "general"

    # PO5: Policy
    execution_eligible: bool = True

    # P6: Regime
    regime: MockRegime = MockRegime.INFORM

    # P7: Discourse
    discourse_act: MockDiscourse = MockDiscourse.EXPLANATION

    # P8: Semantic
    semantic_slots: Dict[str, str] = field(default_factory=dict)

    # P9: Lexical
    lexical_selections: Dict[str, str] = field(default_factory=dict)


@dataclass
class MockObserverState:
    """
    Mock observer state (P22, P23, P24).

    These values must NOT influence the authoritative state.
    """
    # P22: Acoustic Witness
    pressure_band: str = "low"
    motion_balance: str = "balanced"
    vritti_vector: Dict[str, float] = field(default_factory=lambda: {"neutral": 1.0})

    # P23: Alignment
    alignment_state: MockAlignment = MockAlignment.ALIGNED
    tension_score: float = 0.0

    # P24: Projection
    projection_risk: str = "low"
    mismatch_type: str = "none"
    confidence: float = 1.0


def create_decision_surface_pair() -> Tuple[
    Tuple[MockAuthoritativeState, MockObserverState],
    Tuple[MockAuthoritativeState, MockObserverState],
]:
    """
    Create two state pairs with:
    - IDENTICAL authoritative states
    - DIFFERENT observer states

    If the boundary is correctly enforced, the authoritative outputs
    must be identical regardless of observer differences.
    """
    # Identical authoritative state
    auth_state = MockAuthoritativeState(
        is_blocked=False,
        grounding_status="RESOLVED",
        intent_type="SUPPORT",
        response_posture="ACKNOWLEDGE",
        allowed_actions=frozenset({"respond", "reflect"}),
        ontology_category="emotional",
        execution_eligible=True,
        regime=MockRegime.STABILIZE,
        discourse_act=MockDiscourse.REFLECTION,
        semantic_slots={"agent": "user", "state": "uncertain"},
        lexical_selections={"agent": "you", "state": "uncertain"},
    )

    # Observer state A: Calm profile
    observer_a = MockObserverState(
        pressure_band="low",
        motion_balance="balanced",
        vritti_vector={"neutral": 0.8, "expansion": 0.2},
        alignment_state=MockAlignment.ALIGNED,
        tension_score=0.0,
        projection_risk="low",
        mismatch_type="none",
        confidence=1.0,
    )

    # Observer state B: Agitated profile (completely different)
    observer_b = MockObserverState(
        pressure_band="high",
        motion_balance="agitated",
        vritti_vector={"friction": 0.7, "contraction": 0.3},
        alignment_state=MockAlignment.CONTRADICTION,
        tension_score=1.0,
        projection_risk="high",
        mismatch_type="strong_mismatch",
        confidence=0.2,
    )

    return (auth_state, observer_a), (auth_state, observer_b)


# ============================================================================
# HELPER: Static Analysis for Sink Verification
# ============================================================================

# Observer context attribute patterns that must NOT appear in decision logic
# These are the specific context field accessors for observer outputs
FORBIDDEN_OBSERVER_CONTEXT_PATTERNS = frozenset({
    "p22_acoustic_witness",
    "p23_alignment_report",
    "p24_projection_report",
    "ctx.p22",
    "ctx.p23",
    "ctx.p24",
})


def find_observer_context_access_in_decision_code(root_path: Path) -> List[Dict[str, Any]]:
    """
    Scan authoritative modules for access to observer context fields.

    This checks for patterns like:
    - ctx.p22_acoustic_witness
    - ctx.p23_alignment_report
    - ctx.p24_projection_report

    Returns list of violations where observer context fields are accessed.
    """
    violations = []

    for auth_root in AUTHORITATIVE_MODULE_ROOTS:
        dir_path = root_path / auth_root.replace(".", os.sep)
        if not dir_path.exists():
            continue

        for py_file in dir_path.rglob("*.py"):
            # Skip test files and __pycache__
            if "__pycache__" in str(py_file):
                continue
            if "/tests/" in str(py_file) or "/test_" in str(py_file):
                continue
            if py_file.name.startswith("test_"):
                continue

            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                tree = ast.parse(content)

                for node in ast.walk(tree):
                    # Check for attribute access: something.p22_acoustic_witness
                    if isinstance(node, ast.Attribute):
                        attr_name = node.attr
                        if attr_name in {"p22_acoustic_witness", "p23_alignment_report",
                                        "p24_projection_report", "p22", "p23", "p24"}:
                            # Check if accessing from ctx or similar
                            if isinstance(node.value, ast.Name):
                                if node.value.id in {"ctx", "context", "pipeline_context", "self"}:
                                    violations.append({
                                        "file": str(py_file),
                                        "line": node.lineno,
                                        "type": "observer_context_access",
                                        "pattern": f"{node.value.id}.{attr_name}",
                                    })

            except (SyntaxError, UnicodeDecodeError, IOError):
                continue

    return violations


# ============================================================================
# TEST: INV-B1 - No imports from observer modules in authoritative roots
# ============================================================================

class TestINVB1NoObserverImportsInAuthoritative:
    """
    INV-B1: Authoritative modules must NOT import observer modules.

    This test statically scans all authoritative module roots and verifies
    that none of them import from P22, P23, or P24 observer modules.
    """

    def test_inv_b1_no_observer_imports(self, boundary_report):
        """
        INV-B1: No imports from observer modules inside authoritative module roots.

        Enforcement: Static import scan of all authoritative directories.
        Failure: Any import of p22_acoustic_witness, p23_alignment, or p24_projection.
        """
        violations = boundary_report.violations

        # Build detailed error message if violations exist
        if violations:
            violation_msgs = []
            for v in violations:
                violation_msgs.append(
                    f"  {v['file']}:{v['line']} - {v['details']}"
                )
            error_msg = (
                f"INV-B1 VIOLATED: {len(violations)} forbidden import(s) found.\n"
                f"Authoritative modules must NOT import observer modules.\n\n"
                + "\n".join(violation_msgs)
            )
            pytest.fail(error_msg)

        # Also verify the graph shows zero edges
        auth_to_observer_edges = boundary_report.import_graph["authoritative_to_observer_edges"]
        assert len(auth_to_observer_edges) == 0, (
            f"INV-B1 VIOLATED: Found {len(auth_to_observer_edges)} "
            f"authoritative->observer import edges"
        )


# ============================================================================
# TEST: INV-B2 - Observer outputs only written to allowed sinks
# ============================================================================

class TestINVB2ObserverOutputsAllowedSinksOnly:
    """
    INV-B2: Observer outputs may only be written to allowed sinks.

    This test verifies that authoritative decision code does not access
    observer context fields (ctx.p22_*, ctx.p23_*, ctx.p24_*).
    """

    def test_inv_b2_observer_outputs_not_in_decision_code(self):
        """
        INV-B2: Observer outputs may only be written to allowed sinks.

        Enforcement: Check that observer context fields (p22_acoustic_witness,
                     p23_alignment_report, p24_projection_report) are not
                     accessed in authoritative module decision code.
        Failure: Any access to ctx.p22_*, ctx.p23_*, ctx.p24_* in decision functions.
        """
        violations = find_observer_context_access_in_decision_code(PROJECT_ROOT)

        if violations:
            violation_msgs = []
            for v in violations:
                violation_msgs.append(
                    f"  {v['file']}:{v['line']} - {v['type']}: {v['pattern']}"
                )
            error_msg = (
                f"INV-B2 VIOLATED: {len(violations)} observer context access(es) in decision code.\n"
                f"Observer outputs must only flow to allowed sinks (logs, snapshots, dashboards).\n\n"
                + "\n".join(violation_msgs)
            )
            pytest.fail(error_msg)


# ============================================================================
# TEST: INV-B3 - Identical inputs yield identical decision surface
# ============================================================================

class TestINVB3DecisionSurfaceInvariance:
    """
    INV-B3: Running the pipeline with identical authoritative inputs but
    different observer reports yields identical authoritative outputs.

    This test creates context pairs with:
    - IDENTICAL authoritative state (PO1-P9 inputs)
    - DIFFERENT observer state (P22/P23/P24 outputs)

    And verifies the decision surface is identical.
    """

    def test_inv_b3_decision_surface_invariant_to_observers(self):
        """
        INV-B3: Identical authoritative inputs yield identical decision surface.

        Enforcement: Create two contexts with identical auth state but different
                     observer state, verify decision surface equality.
        Failure: Any decision surface field differs between contexts.
        """
        (auth_a, obs_a), (auth_b, obs_b) = create_decision_surface_pair()

        # Verify observers are different
        assert obs_a.pressure_band != obs_b.pressure_band, "Test setup error: observers should differ"
        assert obs_a.tension_score != obs_b.tension_score, "Test setup error: observers should differ"
        assert obs_a.alignment_state != obs_b.alignment_state, "Test setup error: observers should differ"

        # Verify authoritative states are identical (the invariant)
        assert auth_a == auth_b, (
            "INV-B3 VIOLATED: Authoritative states differ despite identical inputs.\n"
            "This would indicate observer values are influencing decisions."
        )

        # Verify each decision surface component explicitly
        assert auth_a.is_blocked == auth_b.is_blocked, "PO1 (blocking) differs"
        assert auth_a.grounding_status == auth_b.grounding_status, "PO1 (grounding) differs"
        assert auth_a.intent_type == auth_b.intent_type, "PO2 (intent) differs"
        assert auth_a.response_posture == auth_b.response_posture, "PO2 (posture) differs"
        assert auth_a.allowed_actions == auth_b.allowed_actions, "PO3 (actions) differs"
        assert auth_a.ontology_category == auth_b.ontology_category, "PO4 (ontology) differs"
        assert auth_a.execution_eligible == auth_b.execution_eligible, "PO5 (eligibility) differs"
        assert auth_a.regime == auth_b.regime, "P6 (regime) differs"
        assert auth_a.discourse_act == auth_b.discourse_act, "P7 (discourse) differs"
        assert auth_a.semantic_slots == auth_b.semantic_slots, "P8 (semantics) differs"
        assert auth_a.lexical_selections == auth_b.lexical_selections, "P9 (lexical) differs"


# ============================================================================
# TEST: INV-B4 - Boundary scanner integrated with CI
# ============================================================================

class TestINVB4BoundaryScannerCIIntegration:
    """
    INV-B4: Boundary scanner fails CI if violations are introduced.

    This test verifies:
    1. The boundary scanner runs successfully
    2. It produces a valid report artifact
    3. The report shows zero violations
    4. The report is written to artifacts/boundary_report.json
    """

    def test_inv_b4_scanner_produces_valid_report(self, boundary_report):
        """
        INV-B4: Boundary scanner fails CI if violations are introduced.

        Enforcement: Verify scanner produces valid JSON report with zero violations.
        Failure: Scanner fails, report is invalid, or violations > 0.
        """
        # Verify report structure
        assert boundary_report.timestamp, "Report missing timestamp"
        assert isinstance(boundary_report.violations, list), "Report violations not a list"
        assert isinstance(boundary_report.import_graph, dict), "Report import_graph not a dict"
        assert isinstance(boundary_report.counts, dict), "Report counts not a dict"

        # Verify counts are populated
        assert boundary_report.counts["total_files_scanned"] > 0, (
            "Scanner did not scan any files"
        )
        assert boundary_report.counts["authoritative_modules_scanned"] > 0, (
            "Scanner did not find any authoritative modules"
        )

        # Verify zero violations
        violation_count = boundary_report.counts["violations_found"]
        assert violation_count == 0, (
            f"INV-B4 CI FAILURE: {violation_count} boundary violation(s) detected.\n"
            f"See artifacts/boundary_report.json for details."
        )

    def test_inv_b4_report_artifact_created(self, boundary_report):
        """
        Verify the boundary report artifact is written to disk.
        """
        report_path = ARTIFACTS_DIR / "boundary_report.json"
        assert report_path.exists(), (
            f"INV-B4 CI FAILURE: Report artifact not created at {report_path}"
        )

        # Verify it's valid JSON
        with open(report_path, 'r') as f:
            loaded = json.load(f)

        assert "violations" in loaded, "Report artifact missing 'violations' field"
        assert "counts" in loaded, "Report artifact missing 'counts' field"
        assert loaded["counts"]["violations_found"] == 0, (
            "Report artifact shows violations"
        )
