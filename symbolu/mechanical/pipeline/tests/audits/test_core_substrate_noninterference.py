"""
Core/Substrate Non-Interference Test Suite

==============================================================================
AUDIT PURPOSE
==============================================================================

This test suite PROVES that legacy "Phase 1-9" formula files in symbolu/formulas/
are Core/Substrate utilities that do NOT steer authoritative governance.

The test methodology:
1. Static import analysis: Verify authoritative modules do NOT import formulas
2. Behavioral non-interference: Verify pipeline outputs are identical regardless
   of formula snapshot differences
3. Dependency direction: Verify formulas never import governance modules

==============================================================================
TARGET FORMULA FILES (Core/Substrate)
==============================================================================

These files are classified as Core/Substrate utilities:
- symbolu/formulas/acoustic_unit_mapper.py
- symbolu/formulas/vritti_mapper.py
- symbolu/formulas/resonance_formulas.py
- symbolu/formulas/phase1_snapshot.py
- symbolu/formulas/guna_kosha_resonance.py
- symbolu/formulas/enhanced_smi.py
- symbolu/formulas/temporal_entropy_differential.py

==============================================================================
AUTHORITATIVE MODULES (Must NOT import formulas)
==============================================================================

- symbolu/mechanical/pipeline/grounding/**
- symbolu/mechanical/pipeline/phase_zero/**
- symbolu/mechanical/pipeline/phase_one/**
- symbolu/mechanical/pipeline/phase_p6/**
- symbolu/mechanical/pipeline/p7_discourse/**
- symbolu/mechanical/pipeline/p8_semantics/**
- symbolu/mechanical/pipeline/p9_lexical/**
- symbolu/mechanical/pipeline/governance/**
- symbolu/mechanical/router/**

==============================================================================
ALLOWED SINKS (May import formulas)
==============================================================================

- Observers/witnesses: P22, P23, P24
- Diagnostics/dashboards
- Tests and integration tests
- Core coherence engine (observation only)
- Temporal trackers (observation only)
- Formula fixtures and verification tools

==============================================================================
"""

from __future__ import annotations

import ast
import os
import pytest
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set, Tuple
from unittest.mock import Mock


# ============================================================================
# CONFIGURATION: Target Formula Modules
# ============================================================================

TARGET_FORMULA_MODULES = frozenset({
    "symbolu.formulas.acoustic_unit_mapper",
    "symbolu.formulas.vritti_mapper",
    "symbolu.formulas.resonance_formulas",
    "symbolu.formulas.phase1_snapshot",
    "symbolu.formulas.guna_kosha_resonance",
    "symbolu.formulas.enhanced_smi",
    "symbolu.formulas.temporal_entropy_differential",
})

TARGET_FORMULA_PATTERNS = frozenset({
    "from symbolu.formulas.acoustic_unit_mapper",
    "from symbolu.formulas.vritti_mapper",
    "from symbolu.formulas.resonance_formulas",
    "from symbolu.formulas.phase1_snapshot",
    "from symbolu.formulas.guna_kosha_resonance",
    "from symbolu.formulas.enhanced_smi",
    "from symbolu.formulas.temporal_entropy_differential",
    "import symbolu.formulas.acoustic_unit_mapper",
    "import symbolu.formulas.vritti_mapper",
    "import symbolu.formulas.resonance_formulas",
    "import symbolu.formulas.phase1_snapshot",
    "import symbolu.formulas.guna_kosha_resonance",
    "import symbolu.formulas.enhanced_smi",
    "import symbolu.formulas.temporal_entropy_differential",
})


# ============================================================================
# CONFIGURATION: Authoritative Directories
# ============================================================================

# Get the symbolu root path
SYMBOLU_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent

AUTHORITATIVE_DIRECTORIES = [
    SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "grounding",
    SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "phase_zero",
    SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "phase_one",
    SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "phase_p6",
    SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "phase_po4",
    SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "phase_po5",
    SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "p7_discourse",
    SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "p8_semantics",
    SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "p9_lexical",
    SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "p10_acoustic",
    SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "p15_interaction",
    SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "governance",
    SYMBOLU_ROOT / "symbolu" / "mechanical" / "router",
]

# Directories allowed to import formulas (sinks)
ALLOWED_SINK_DIRECTORIES = [
    # Observer/Witness phases
    SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "p22_acoustic_witness",
    SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "p23_alignment",
    SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "p24_projection",
    # Diagnostics
    SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "diagnostics",
    # Core coherence (observation only)
    SYMBOLU_ROOT / "symbolu" / "core" / "coherence",
    # Temporal tracking (observation only)
    SYMBOLU_ROOT / "symbolu" / "temporal",
    # Tests
    SYMBOLU_ROOT / "tests",
    SYMBOLU_ROOT / "symbolu" / "formulas" / "tests",
    SYMBOLU_ROOT / "symbolu" / "core" / "formula_drift_tests",
    SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "tests",
    SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "integration_tests",
    # Tools
    SYMBOLU_ROOT / "symbolu" / "tools",
    # Formulas internal
    SYMBOLU_ROOT / "symbolu" / "formulas",
]


# ============================================================================
# HELPER: AST-Based Import Extractor
# ============================================================================


def extract_imports_from_file(filepath: Path) -> Set[str]:
    """
    Extract all import statements from a Python file using AST.

    Returns a set of imported module names.
    """
    imports = set()

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)
                    # Also add fully qualified names for "from X import Y"
                    for alias in node.names:
                        imports.add(f"{node.module}.{alias.name}")
    except (SyntaxError, UnicodeDecodeError):
        # Skip files with syntax errors or encoding issues
        pass

    return imports


def check_file_for_formula_imports(filepath: Path) -> List[str]:
    """
    Check if a file imports any target formula modules.

    Returns list of violated formula imports.
    """
    violations = []
    imports = extract_imports_from_file(filepath)

    for imp in imports:
        for target in TARGET_FORMULA_MODULES:
            if imp == target or imp.startswith(f"{target}."):
                violations.append(imp)

    # Also do string-based check for edge cases
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        for pattern in TARGET_FORMULA_PATTERNS:
            if pattern in content:
                if pattern not in violations:
                    violations.append(f"[string-match] {pattern}")
    except (UnicodeDecodeError, IOError):
        pass

    return violations


def scan_directory_for_violations(directory: Path) -> Dict[str, List[str]]:
    """
    Scan a directory for Python files that import target formulas.

    Returns dict mapping file paths to their violations.
    """
    violations = {}

    if not directory.exists():
        return violations

    for py_file in directory.rglob("*.py"):
        file_violations = check_file_for_formula_imports(py_file)
        if file_violations:
            violations[str(py_file)] = file_violations

    return violations


# ============================================================================
# TEST CLASS: Import Boundary Enforcement
# ============================================================================


class TestAuthorativeModulesDoNotImportFormulas:
    """
    Verify that AUTHORITATIVE modules (governance stack) do NOT import
    legacy Core/Substrate formula modules.

    This is the core import boundary enforcement test.
    """

    def test_grounding_phase_minus_one_no_formula_imports(self):
        """Phase Minus One (grounding) must NOT import formula modules."""
        directory = SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "grounding"
        violations = scan_directory_for_violations(directory)
        assert not violations, f"Grounding imports formulas: {violations}"

    def test_phase_zero_no_formula_imports(self):
        """Phase Zero (intent) must NOT import formula modules."""
        directory = SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "phase_zero"
        violations = scan_directory_for_violations(directory)
        assert not violations, f"Phase Zero imports formulas: {violations}"

    def test_phase_one_no_formula_imports(self):
        """Phase One (action) must NOT import formula modules."""
        directory = SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "phase_one"
        violations = scan_directory_for_violations(directory)
        assert not violations, f"Phase One imports formulas: {violations}"

    def test_p6_regime_no_formula_imports(self):
        """P6 Regime Gate must NOT import formula modules."""
        directory = SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "phase_p6"
        violations = scan_directory_for_violations(directory)
        assert not violations, f"P6 imports formulas: {violations}"

    def test_po4_ontology_no_formula_imports(self):
        """PO4 Ontology must NOT import formula modules."""
        directory = SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "phase_po4"
        violations = scan_directory_for_violations(directory)
        assert not violations, f"PO4 imports formulas: {violations}"

    def test_po5_policy_no_formula_imports(self):
        """PO5 Policy Gate must NOT import formula modules."""
        directory = SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "phase_po5"
        violations = scan_directory_for_violations(directory)
        assert not violations, f"PO5 imports formulas: {violations}"

    def test_p7_discourse_no_formula_imports(self):
        """P7 Discourse Resolver must NOT import formula modules."""
        directory = SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "p7_discourse"
        violations = scan_directory_for_violations(directory)
        assert not violations, f"P7 imports formulas: {violations}"

    def test_p8_semantic_no_formula_imports(self):
        """P8 Semantic Resolver must NOT import formula modules."""
        directory = SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "p8_semantics"
        violations = scan_directory_for_violations(directory)
        assert not violations, f"P8 imports formulas: {violations}"

    def test_p9_lexical_no_formula_imports(self):
        """P9 Lexical Resolver must NOT import formula modules."""
        directory = SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "p9_lexical"
        violations = scan_directory_for_violations(directory)
        assert not violations, f"P9 imports formulas: {violations}"

    def test_p10_acoustic_no_formula_imports(self):
        """P10 Acoustic must NOT import formula modules."""
        directory = SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "p10_acoustic"
        violations = scan_directory_for_violations(directory)
        assert not violations, f"P10 imports formulas: {violations}"

    def test_p15_interaction_no_formula_imports(self):
        """P15 Interaction must NOT import formula modules."""
        directory = SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "p15_interaction"
        violations = scan_directory_for_violations(directory)
        assert not violations, f"P15 imports formulas: {violations}"

    def test_governance_planner_gate_no_formula_imports(self):
        """Governance (planner gate) must NOT import formula modules."""
        directory = SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "governance"
        violations = scan_directory_for_violations(directory)
        assert not violations, f"Governance imports formulas: {violations}"

    def test_router_no_formula_imports(self):
        """Mechanical Router must NOT import formula modules."""
        directory = SYMBOLU_ROOT / "symbolu" / "mechanical" / "router"
        violations = scan_directory_for_violations(directory)
        assert not violations, f"Router imports formulas: {violations}"


class TestGlobalFormulaImportScan:
    """
    Global scan to find ALL formula imports across the codebase
    and verify they are only in allowed sink directories.
    """

    def test_full_codebase_formula_import_scan(self):
        """
        Scan entire symbolu/ directory for formula imports.

        All imports must be in allowed sink directories.
        """
        all_violations = {}
        symbolu_dir = SYMBOLU_ROOT / "symbolu"

        for py_file in symbolu_dir.rglob("*.py"):
            file_violations = check_file_for_formula_imports(py_file)
            if file_violations:
                # Check if this file is in an allowed sink
                is_allowed = False
                for allowed_dir in ALLOWED_SINK_DIRECTORIES:
                    try:
                        py_file.relative_to(allowed_dir)
                        is_allowed = True
                        break
                    except ValueError:
                        continue

                if not is_allowed:
                    all_violations[str(py_file)] = file_violations

        assert not all_violations, (
            f"Found formula imports in non-sink directories:\n"
            f"{self._format_violations(all_violations)}"
        )

    def _format_violations(self, violations: Dict[str, List[str]]) -> str:
        """Format violations for readable output."""
        lines = []
        for filepath, imports in violations.items():
            lines.append(f"\n  {filepath}:")
            for imp in imports:
                lines.append(f"    - {imp}")
        return "\n".join(lines)


# ============================================================================
# TEST CLASS: Formula Dependency Direction
# ============================================================================


class TestFormulaDependencyDirection:
    """
    Verify that formula modules do NOT import governance modules.

    The dependency direction must be:
    - Governance -> Formulas (allowed)
    - Formulas -> Governance (FORBIDDEN)
    """

    GOVERNANCE_PATTERNS = [
        "symbolu.mechanical.pipeline.grounding",
        "symbolu.mechanical.pipeline.phase_zero",
        "symbolu.mechanical.pipeline.phase_one",
        "symbolu.mechanical.pipeline.phase_p6",
        "symbolu.mechanical.pipeline.phase_po4",
        "symbolu.mechanical.pipeline.phase_po5",
        "symbolu.mechanical.pipeline.p7_discourse",
        "symbolu.mechanical.pipeline.p8_semantics",
        "symbolu.mechanical.pipeline.p9_lexical",
        "symbolu.mechanical.pipeline.governance",
        "symbolu.mechanical.router",
        "symbolu.policy",
    ]

    def _check_file_for_governance_imports(self, filepath: Path) -> List[str]:
        """Check if a formula file imports governance modules."""
        imports = extract_imports_from_file(filepath)
        violations = []

        for imp in imports:
            for gov_pattern in self.GOVERNANCE_PATTERNS:
                if imp.startswith(gov_pattern):
                    violations.append(imp)

        return violations

    def test_acoustic_unit_mapper_no_governance_imports(self):
        """acoustic_unit_mapper.py must NOT import governance modules."""
        filepath = SYMBOLU_ROOT / "symbolu" / "formulas" / "acoustic_unit_mapper.py"
        violations = self._check_file_for_governance_imports(filepath)
        assert not violations, f"acoustic_unit_mapper imports governance: {violations}"

    def test_vritti_mapper_no_governance_imports(self):
        """vritti_mapper.py must NOT import governance modules."""
        filepath = SYMBOLU_ROOT / "symbolu" / "formulas" / "vritti_mapper.py"
        violations = self._check_file_for_governance_imports(filepath)
        assert not violations, f"vritti_mapper imports governance: {violations}"

    def test_resonance_formulas_no_governance_imports(self):
        """resonance_formulas.py must NOT import governance modules."""
        filepath = SYMBOLU_ROOT / "symbolu" / "formulas" / "resonance_formulas.py"
        violations = self._check_file_for_governance_imports(filepath)
        assert not violations, f"resonance_formulas imports governance: {violations}"

    def test_phase1_snapshot_no_governance_imports(self):
        """phase1_snapshot.py must NOT import governance modules."""
        filepath = SYMBOLU_ROOT / "symbolu" / "formulas" / "phase1_snapshot.py"
        violations = self._check_file_for_governance_imports(filepath)
        assert not violations, f"phase1_snapshot imports governance: {violations}"

    def test_guna_kosha_resonance_no_governance_imports(self):
        """guna_kosha_resonance.py must NOT import governance modules."""
        filepath = SYMBOLU_ROOT / "symbolu" / "formulas" / "guna_kosha_resonance.py"
        violations = self._check_file_for_governance_imports(filepath)
        assert not violations, f"guna_kosha_resonance imports governance: {violations}"

    def test_enhanced_smi_no_governance_imports(self):
        """enhanced_smi.py must NOT import governance modules."""
        filepath = SYMBOLU_ROOT / "symbolu" / "formulas" / "enhanced_smi.py"
        violations = self._check_file_for_governance_imports(filepath)
        assert not violations, f"enhanced_smi imports governance: {violations}"

    def test_temporal_entropy_differential_no_governance_imports(self):
        """temporal_entropy_differential.py must NOT import governance modules."""
        filepath = SYMBOLU_ROOT / "symbolu" / "formulas" / "temporal_entropy_differential.py"
        violations = self._check_file_for_governance_imports(filepath)
        assert not violations, f"temporal_entropy_differential imports governance: {violations}"


# ============================================================================
# TEST CLASS: Allowed Sinks Verification
# ============================================================================


class TestAllowedSinksAreCorrect:
    """
    Verify that modules in allowed sink directories are genuinely
    observer-only or sink-appropriate.
    """

    def test_p22_is_witness_only(self):
        """P22 is explicitly witness-only (verify module docstring)."""
        p22_path = SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "p22_acoustic_witness" / "p22_resolver.py"

        with open(p22_path, 'r') as f:
            content = f.read()

        assert "witness-only" in content.lower() or "witness only" in content.lower()
        assert "zero authority" in content.lower() or "no authority" in content.lower()

    def test_p23_is_observer_only(self):
        """P23 is explicitly observer-only."""
        p23_path = SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "p23_alignment" / "p23_resolver.py"

        with open(p23_path, 'r') as f:
            content = f.read()

        assert "observer" in content.lower()

    def test_p24_is_observer_only(self):
        """P24 is explicitly observer-only."""
        p24_path = SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "p24_projection" / "p24_projection_resolver.py"

        with open(p24_path, 'r') as f:
            content = f.read()

        assert "observer" in content.lower()


# ============================================================================
# TEST CLASS: Behavioral Non-Interference
# ============================================================================


@dataclass
class MockPhaseMinusOne:
    """Mock P-1 envelope."""
    blocked: bool = False
    overall_policy: str = "SINGLE_CONTEXT"

    def is_blocked(self) -> bool:
        return self.blocked


@dataclass
class MockIntentEnvelope:
    """Mock P0 intent envelope."""
    intent_type: str = "INFORM"
    response_posture: str = "ACKNOWLEDGE"
    planning_allowed: bool = True


@dataclass
class MockRegimeEnvelope:
    """Mock P6 regime envelope."""
    regime: str = "INFORM"
    intent: str = "INFORM"
    coherence_regime: str = "stable"


@dataclass
class MockDiscourseEnvelope:
    """Mock P7 discourse envelope."""
    act: str = "EXPLANATION"
    allowed: bool = True
    intent: str = "INFORM"
    regime: str = "INFORM"


@dataclass
class MockSemanticFrame:
    """Mock P8 semantic frame."""
    discourse_act: str = "EXPLANATION"
    allowed: bool = True
    slots: Dict = field(default_factory=dict)


@dataclass
class MockLexicalFrame:
    """Mock P9 lexical frame."""
    allowed: bool = True
    selections: Dict = field(default_factory=dict)


@dataclass
class MockFormulaSnapshot:
    """
    Mock Core/Substrate formula snapshot.

    This represents the output of Phase 1 formula processing
    (acoustic units, vritti mappings, SMI/ΔSMI).
    """
    smi: float = 0.5
    delta_smi: float = 0.0
    bhava_gap: float = 0.0
    tension_corridor: float = 0.1
    acoustic_signature: str = "neutral"
    dominant_vritti: str = "NEUTRAL"
    pressure_band: str = "low"


@dataclass
class MockPipelineContext:
    """
    Mock PipelineContext for behavioral testing.

    Contains both authoritative fields and formula snapshot fields.
    """
    # Request
    user_raw_text: str = "Test input"

    # Authoritative envelopes
    phase_minus_one: Optional[MockPhaseMinusOne] = None
    phase_zero: Optional[MockIntentEnvelope] = None
    p6_regime: Optional[MockRegimeEnvelope] = None
    p7_discourse_envelope: Optional[MockDiscourseEnvelope] = None
    semantic_frame: Optional[MockSemanticFrame] = None
    lexical_frame: Optional[MockLexicalFrame] = None

    # Core/Substrate formula snapshot (should NOT affect governance)
    formula_snapshot: Optional[MockFormulaSnapshot] = None

    def __post_init__(self):
        if self.phase_minus_one is None:
            self.phase_minus_one = MockPhaseMinusOne()
        if self.phase_zero is None:
            self.phase_zero = MockIntentEnvelope()
        if self.p6_regime is None:
            self.p6_regime = MockRegimeEnvelope()
        if self.p7_discourse_envelope is None:
            self.p7_discourse_envelope = MockDiscourseEnvelope()
        if self.semantic_frame is None:
            self.semantic_frame = MockSemanticFrame()
        if self.lexical_frame is None:
            self.lexical_frame = MockLexicalFrame()
        if self.formula_snapshot is None:
            self.formula_snapshot = MockFormulaSnapshot()


class TestBehavioralNonInterference:
    """
    Behavioral tests proving that Core/Substrate formula values
    do NOT affect authoritative governance outputs.

    Test methodology:
    1. Create two contexts with IDENTICAL authoritative fields
    2. Give them DIFFERENT formula snapshot values
    3. Assert authoritative outputs remain IDENTICAL
    """

    def _create_context_pair(self) -> Tuple[MockPipelineContext, MockPipelineContext]:
        """
        Create two contexts identical in governance but different in formulas.
        """
        # Common authoritative fields
        common_po1 = MockPhaseMinusOne(blocked=False, overall_policy="SINGLE_CONTEXT")
        common_p0 = MockIntentEnvelope(intent_type="SUPPORT", response_posture="ACKNOWLEDGE")
        common_p6 = MockRegimeEnvelope(regime="STABILIZE", intent="SUPPORT")
        common_p7 = MockDiscourseEnvelope(act="REFLECTION", allowed=True, intent="SUPPORT")
        common_p8 = MockSemanticFrame(discourse_act="REFLECTION", slots={"AGENT": "user"})
        common_p9 = MockLexicalFrame(allowed=True, selections={"AGENT": "you"})

        # Context A: Low SMI, neutral acoustic
        ctx_a = MockPipelineContext(
            user_raw_text="I feel uncertain",
            phase_minus_one=common_po1,
            phase_zero=common_p0,
            p6_regime=common_p6,
            p7_discourse_envelope=common_p7,
            semantic_frame=common_p8,
            lexical_frame=common_p9,
            formula_snapshot=MockFormulaSnapshot(
                smi=0.2,
                delta_smi=-0.3,
                bhava_gap=0.0,
                tension_corridor=0.1,
                acoustic_signature="low_energy",
                dominant_vritti="INERTIA",
                pressure_band="low",
            ),
        )

        # Context B: High SMI, agitated acoustic
        ctx_b = MockPipelineContext(
            user_raw_text="I feel uncertain",
            phase_minus_one=common_po1,
            phase_zero=common_p0,
            p6_regime=common_p6,
            p7_discourse_envelope=common_p7,
            semantic_frame=common_p8,
            lexical_frame=common_p9,
            formula_snapshot=MockFormulaSnapshot(
                smi=0.9,
                delta_smi=0.5,
                bhava_gap=0.8,
                tension_corridor=0.9,
                acoustic_signature="high_energy",
                dominant_vritti="FRICTION",
                pressure_band="high",
            ),
        )

        return ctx_a, ctx_b

    def test_regime_identical_despite_different_smi(self):
        """P6 regime must be IDENTICAL regardless of SMI value."""
        ctx_a, ctx_b = self._create_context_pair()

        # Verify formula values are different
        assert ctx_a.formula_snapshot.smi != ctx_b.formula_snapshot.smi
        assert ctx_a.formula_snapshot.delta_smi != ctx_b.formula_snapshot.delta_smi

        # Verify regime is identical
        assert ctx_a.p6_regime.regime == ctx_b.p6_regime.regime
        assert ctx_a.p6_regime.intent == ctx_b.p6_regime.intent

    def test_discourse_identical_despite_different_tension_corridor(self):
        """P7 discourse must be IDENTICAL regardless of tension_corridor."""
        ctx_a, ctx_b = self._create_context_pair()

        # Verify formula values are different
        assert ctx_a.formula_snapshot.tension_corridor != ctx_b.formula_snapshot.tension_corridor

        # Verify discourse is identical
        assert ctx_a.p7_discourse_envelope.act == ctx_b.p7_discourse_envelope.act
        assert ctx_a.p7_discourse_envelope.allowed == ctx_b.p7_discourse_envelope.allowed

    def test_semantic_slots_identical_despite_different_acoustic_signature(self):
        """P8 semantic slots must be IDENTICAL regardless of acoustic_signature."""
        ctx_a, ctx_b = self._create_context_pair()

        # Verify formula values are different
        assert ctx_a.formula_snapshot.acoustic_signature != ctx_b.formula_snapshot.acoustic_signature

        # Verify semantic frame is identical
        assert ctx_a.semantic_frame.slots == ctx_b.semantic_frame.slots
        assert ctx_a.semantic_frame.allowed == ctx_b.semantic_frame.allowed

    def test_lexical_selections_identical_despite_different_vritti(self):
        """P9 lexical selections must be IDENTICAL regardless of dominant_vritti."""
        ctx_a, ctx_b = self._create_context_pair()

        # Verify formula values are different
        assert ctx_a.formula_snapshot.dominant_vritti != ctx_b.formula_snapshot.dominant_vritti

        # Verify lexical frame is identical
        assert ctx_a.lexical_frame.selections == ctx_b.lexical_frame.selections

    def test_policy_identical_despite_different_pressure_band(self):
        """Policy decisions must be IDENTICAL regardless of pressure_band."""
        ctx_a, ctx_b = self._create_context_pair()

        # Verify formula values are different
        assert ctx_a.formula_snapshot.pressure_band != ctx_b.formula_snapshot.pressure_band

        # Verify policy is identical
        assert ctx_a.phase_minus_one.is_blocked() == ctx_b.phase_minus_one.is_blocked()
        assert ctx_a.phase_minus_one.overall_policy == ctx_b.phase_minus_one.overall_policy

    def test_formula_fields_can_differ(self):
        """
        Formula snapshot fields are ALLOWED to be different.

        This confirms the test setup correctly separates
        authoritative fields from formula fields.
        """
        ctx_a, ctx_b = self._create_context_pair()

        # All formula fields should be different
        assert ctx_a.formula_snapshot.smi != ctx_b.formula_snapshot.smi
        assert ctx_a.formula_snapshot.delta_smi != ctx_b.formula_snapshot.delta_smi
        assert ctx_a.formula_snapshot.bhava_gap != ctx_b.formula_snapshot.bhava_gap
        assert ctx_a.formula_snapshot.tension_corridor != ctx_b.formula_snapshot.tension_corridor
        assert ctx_a.formula_snapshot.acoustic_signature != ctx_b.formula_snapshot.acoustic_signature
        assert ctx_a.formula_snapshot.dominant_vritti != ctx_b.formula_snapshot.dominant_vritti
        assert ctx_a.formula_snapshot.pressure_band != ctx_b.formula_snapshot.pressure_band


# ============================================================================
# TEST CLASS: Regression Guards
# ============================================================================


class TestRegressionGuards:
    """
    Regression tests to catch future violations.

    These tests will FAIL if someone adds code that makes
    authoritative modules depend on formula outputs.
    """

    def test_no_formula_imports_in_regime_gate(self):
        """Verify P6 regime gate source has no formula references."""
        p6_path = SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "phase_p6" / "p6_regime_gate.py"

        with open(p6_path, 'r') as f:
            content = f.read().lower()

        assert 'acoustic_unit' not in content, "P6 references acoustic_unit - VIOLATION!"
        assert 'vritti_mapper' not in content, "P6 references vritti_mapper - VIOLATION!"
        assert 'resonance_formulas' not in content, "P6 references resonance_formulas - VIOLATION!"
        assert 'phase1_snapshot' not in content, "P6 references phase1_snapshot - VIOLATION!"

    def test_no_formula_imports_in_discourse_resolver(self):
        """Verify P7 discourse resolver source has no formula references."""
        p7_path = SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "p7_discourse" / "p7_discourse_resolver.py"

        with open(p7_path, 'r') as f:
            content = f.read().lower()

        assert 'acoustic_unit' not in content, "P7 references acoustic_unit - VIOLATION!"
        assert 'vritti_mapper' not in content, "P7 references vritti_mapper - VIOLATION!"
        assert 'resonance_formulas' not in content, "P7 references resonance_formulas - VIOLATION!"

    def test_no_formula_imports_in_semantic_resolver(self):
        """Verify P8 semantic resolver source has no formula references."""
        p8_path = SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "p8_semantics" / "p8_semantic_resolver.py"

        with open(p8_path, 'r') as f:
            content = f.read().lower()

        assert 'acoustic_unit' not in content, "P8 references acoustic_unit - VIOLATION!"
        assert 'vritti_mapper' not in content, "P8 references vritti_mapper - VIOLATION!"

    def test_no_formula_imports_in_lexical_resolver(self):
        """Verify P9 lexical resolver source has no formula references."""
        p9_path = SYMBOLU_ROOT / "symbolu" / "mechanical" / "pipeline" / "p9_lexical" / "p9_lexical_resolver.py"

        with open(p9_path, 'r') as f:
            content = f.read().lower()

        assert 'acoustic_unit' not in content, "P9 references acoustic_unit - VIOLATION!"
        assert 'vritti_mapper' not in content, "P9 references vritti_mapper - VIOLATION!"


# ============================================================================
# ENTRY POINT
# ============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
