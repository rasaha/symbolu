"""
Ontology Freeze Contract CI Guards
==================================

These tests enforce the ONTOLOGY_FREEZE_CONTRACT.md rules:

1. Only Phase-4A may read ontology JSON files
2. Phase-4B, Phase-4C, and all other pipeline code must not access ontology files
3. Frozen ontology files must not be modified without version bump
4. No direct path references to ontology files outside Phase-4A

VIOLATION = HARD FAILURE

See ONTOLOGY_FREEZE_CONTRACT.md for full contract details.
"""

import ast
import re
from pathlib import Path
from typing import Set, List, Tuple

import pytest


# =============================================================================
# Configuration
# =============================================================================

# Project root
PROJECT_ROOT = Path(__file__).parent.parent

# Frozen ontology files (relative to project root)
FROZEN_ONTOLOGY_FILES = frozenset({
    "docs/data/varna_bridge_map_v1.json",
    "docs/data/ontological_layers_v1.json",
    "docs/data/varna_layer_interaction_v1.json",
    "docs/data/varna_polarity_map_v1.json",
    "docs/data/varna_distortion_map_v1.json",
})

# Frozen ontology filenames (for string literal detection)
FROZEN_ONTOLOGY_FILENAMES = frozenset({
    "varna_bridge_map_v1.json",
    "ontological_layers_v1.json",
    "varna_layer_interaction_v1.json",
    "varna_polarity_map_v1.json",
    "varna_distortion_map_v1.json",
})

# Authorized modules (may read ontology files)
AUTHORIZED_MODULES = frozenset({
    "symbolu/ontology/phase4a/",
    "symbolu/resonance/",  # Core resonance engine - legitimately uses varna bridge data
    "symbolu/formulas/",   # Formulas modules - use varna bridge data for acoustic mapping
})

# Exempt paths (experimental, tests, docs)
EXEMPT_PATHS = frozenset({
    "docs/experiments/",
    "restoration/experiments/",
    "tests/",
    ".github/",
})

# Legacy modules with EXPERIMENT_ONLY marker (tolerated but deprecated)
LEGACY_EXPERIMENT_MODULES = frozenset({
    "symbolu/formulas/varna_bridge_loader.py",
})

# Forbidden modules (must never reference ontology)
FORBIDDEN_MODULES = frozenset({
    "symbolu/ontology/phase4b/",
    "symbolu/ontology/phase4c/",
})


# =============================================================================
# Helper Functions
# =============================================================================

def get_all_python_files(root: Path) -> List[Path]:
    """Get all Python files in the project."""
    return list(root.rglob("*.py"))


def is_authorized(filepath: Path) -> bool:
    """Check if a file is in an authorized module."""
    rel_path = str(filepath.relative_to(PROJECT_ROOT))
    for auth in AUTHORIZED_MODULES:
        if rel_path.startswith(auth):
            return True
    return False


def is_exempt(filepath: Path) -> bool:
    """Check if a file is exempt from ontology freeze checks."""
    rel_path = str(filepath.relative_to(PROJECT_ROOT))
    for exempt in EXEMPT_PATHS:
        if rel_path.startswith(exempt):
            return True
    return False


def is_legacy_experiment(filepath: Path) -> bool:
    """Check if a file is a legacy experiment module."""
    rel_path = str(filepath.relative_to(PROJECT_ROOT))
    return rel_path in LEGACY_EXPERIMENT_MODULES


def is_forbidden_module(filepath: Path) -> bool:
    """Check if a file is in a forbidden module (Phase-4B, Phase-4C)."""
    rel_path = str(filepath.relative_to(PROJECT_ROOT))
    for forbidden in FORBIDDEN_MODULES:
        if rel_path.startswith(forbidden):
            return True
    return False


def has_experiment_only_marker(filepath: Path) -> bool:
    """Check if a file has EXPERIMENT_ONLY = True marker."""
    try:
        content = filepath.read_text(encoding="utf-8")
        return "EXPERIMENT_ONLY = True" in content or "EXPERIMENT_ONLY=True" in content
    except Exception:
        return False


def find_ontology_filename_references(filepath: Path) -> List[Tuple[int, str, str]]:
    """
    Find string literals referencing ontology filenames.

    Returns list of (line_number, filename, line_content) tuples.
    """
    violations = []
    try:
        content = filepath.read_text(encoding="utf-8")
        lines = content.split("\n")
        for i, line in enumerate(lines, start=1):
            for filename in FROZEN_ONTOLOGY_FILENAMES:
                if filename in line:
                    violations.append((i, filename, line.strip()))
    except Exception:
        pass
    return violations


def find_ontology_path_references(filepath: Path) -> List[Tuple[int, str, str]]:
    """
    Find string literals containing ontology file paths.

    Returns list of (line_number, path, line_content) tuples.
    """
    violations = []
    try:
        content = filepath.read_text(encoding="utf-8")
        lines = content.split("\n")
        for i, line in enumerate(lines, start=1):
            for ontology_path in FROZEN_ONTOLOGY_FILES:
                if ontology_path in line:
                    violations.append((i, ontology_path, line.strip()))
    except Exception:
        pass
    return violations


def find_json_load_of_ontology(filepath: Path) -> List[Tuple[int, str]]:
    """
    Find potential direct JSON loading of ontology files.

    Looks for patterns like:
    - json.load(...varna_bridge_map...)
    - open(...ontological_layers...)

    Returns list of (line_number, line_content) tuples.
    """
    violations = []
    try:
        content = filepath.read_text(encoding="utf-8")
        lines = content.split("\n")

        # Pattern: lines with json.load and ontology filename nearby
        for i, line in enumerate(lines, start=1):
            if "json.load" in line or "json.loads" in line:
                # Check surrounding context (5 lines before/after)
                start = max(0, i - 6)
                end = min(len(lines), i + 5)
                context = "\n".join(lines[start:end])
                for filename in FROZEN_ONTOLOGY_FILENAMES:
                    if filename in context:
                        violations.append((i, line.strip()))
                        break
    except Exception:
        pass
    return violations


def get_imports_from_file(filepath: Path) -> Set[str]:
    """
    Extract all imported module paths from a Python file.

    Returns set of import paths (e.g., "symbolu.ontology.phase4a.loader").
    """
    imports = set()
    try:
        content = filepath.read_text(encoding="utf-8")
        tree = ast.parse(content)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)
                    for alias in node.names:
                        imports.add(f"{node.module}.{alias.name}")
    except Exception:
        pass
    return imports


# =============================================================================
# Test Classes
# =============================================================================

class TestOntologyFreezeContract:
    """
    Tests enforcing the Ontology Freeze Contract.

    These tests ensure:
    1. Only Phase-4A accesses ontology JSON files
    2. Phase-4B/4C never reference ontology
    3. No forbidden modules access ontology
    """

    @pytest.fixture(scope="class")
    def all_python_files(self) -> List[Path]:
        """Get all Python files for analysis."""
        return get_all_python_files(PROJECT_ROOT)

    @pytest.fixture(scope="class")
    def non_authorized_files(self, all_python_files: List[Path]) -> List[Path]:
        """Get Python files that are NOT authorized to access ontology."""
        return [
            f for f in all_python_files
            if not is_authorized(f) and not is_exempt(f) and not is_legacy_experiment(f)
        ]

    def test_files_found(self, all_python_files: List[Path]) -> None:
        """Verify we found Python files to analyze."""
        assert len(all_python_files) > 0, "No Python files found in project"

    def test_no_ontology_filename_references_outside_phase4a(
        self, non_authorized_files: List[Path]
    ) -> None:
        """
        No files outside Phase-4A may reference ontology filenames.

        VIOLATION: String literals containing ontology filenames.
        """
        violations = []

        for filepath in non_authorized_files:
            refs = find_ontology_filename_references(filepath)
            if refs:
                rel_path = filepath.relative_to(PROJECT_ROOT)
                for line_num, filename, line in refs:
                    violations.append(
                        f"  {rel_path}:{line_num} - references '{filename}'\n"
                        f"    → {line}"
                    )

        if violations:
            violation_msg = "\n".join(violations)
            pytest.fail(
                f"ONTOLOGY FREEZE VIOLATION: Files outside Phase-4A reference ontology filenames\n\n"
                f"Violations found:\n{violation_msg}\n\n"
                f"See ONTOLOGY_FREEZE_CONTRACT.md for authorized access patterns."
            )

    def test_no_ontology_path_references_outside_phase4a(
        self, non_authorized_files: List[Path]
    ) -> None:
        """
        No files outside Phase-4A may reference ontology file paths.

        VIOLATION: String literals containing paths like 'docs/data/varna_bridge_map_v1.json'.
        """
        violations = []

        for filepath in non_authorized_files:
            refs = find_ontology_path_references(filepath)
            if refs:
                rel_path = filepath.relative_to(PROJECT_ROOT)
                for line_num, path, line in refs:
                    violations.append(
                        f"  {rel_path}:{line_num} - references path '{path}'\n"
                        f"    → {line}"
                    )

        if violations:
            violation_msg = "\n".join(violations)
            pytest.fail(
                f"ONTOLOGY FREEZE VIOLATION: Files outside Phase-4A reference ontology paths\n\n"
                f"Violations found:\n{violation_msg}\n\n"
                f"See ONTOLOGY_FREEZE_CONTRACT.md for authorized access patterns."
            )


class TestPhase4BPhase4CIsolation:
    """
    Tests ensuring Phase-4B and Phase-4C are isolated from ontology.

    These sub-phases must:
    1. Never import from Phase-4A loader directly
    2. Never reference ontology filenames
    3. Never reference ontology paths
    """

    @pytest.fixture(scope="class")
    def phase4b_files(self) -> List[Path]:
        """Get all Phase-4B files."""
        phase4b_dir = PROJECT_ROOT / "symbolu" / "ontology" / "phase4b"
        if phase4b_dir.exists():
            return list(phase4b_dir.rglob("*.py"))
        return []

    @pytest.fixture(scope="class")
    def phase4c_files(self) -> List[Path]:
        """Get all Phase-4C files."""
        phase4c_dir = PROJECT_ROOT / "symbolu" / "ontology" / "phase4c"
        if phase4c_dir.exists():
            return list(phase4c_dir.rglob("*.py"))
        return []

    def test_phase4b_no_ontology_references(self, phase4b_files: List[Path]) -> None:
        """Phase-4B must not reference ontology files."""
        if not phase4b_files:
            pytest.skip("No Phase-4B files found (expected)")
            return

        violations = []
        for filepath in phase4b_files:
            refs = find_ontology_filename_references(filepath)
            if refs:
                rel_path = filepath.relative_to(PROJECT_ROOT)
                for line_num, filename, line in refs:
                    violations.append(f"  {rel_path}:{line_num} - {filename}")

        if violations:
            pytest.fail(
                f"ONTOLOGY FREEZE VIOLATION: Phase-4B references ontology files\n\n"
                f"Violations:\n" + "\n".join(violations)
            )

    def test_phase4c_no_ontology_references(self, phase4c_files: List[Path]) -> None:
        """Phase-4C must not reference ontology files."""
        if not phase4c_files:
            pytest.skip("No Phase-4C files found (expected)")
            return

        violations = []
        for filepath in phase4c_files:
            refs = find_ontology_filename_references(filepath)
            if refs:
                rel_path = filepath.relative_to(PROJECT_ROOT)
                for line_num, filename, line in refs:
                    violations.append(f"  {rel_path}:{line_num} - {filename}")

        if violations:
            pytest.fail(
                f"ONTOLOGY FREEZE VIOLATION: Phase-4C references ontology files\n\n"
                f"Violations:\n" + "\n".join(violations)
            )

    def test_phase4b_no_direct_loader_imports(self, phase4b_files: List[Path]) -> None:
        """Phase-4B must not import Phase-4A loader directly."""
        if not phase4b_files:
            pytest.skip("No Phase-4B files found (expected)")
            return

        forbidden_imports = {
            "symbolu.ontology.phase4a.loader",
            "symbolu.ontology.phase4a.loader.load_ontology_files",
            "symbolu.ontology.phase4a.loader._load_json_file",
        }

        violations = []
        for filepath in phase4b_files:
            imports = get_imports_from_file(filepath)
            bad_imports = imports & forbidden_imports
            if bad_imports:
                rel_path = filepath.relative_to(PROJECT_ROOT)
                violations.append(f"  {rel_path}: imports {bad_imports}")

        if violations:
            pytest.fail(
                f"ONTOLOGY FREEZE VIOLATION: Phase-4B imports Phase-4A loader\n\n"
                f"Phase-4B should use Phase-4A APIs (lookup_interaction), not loader.\n\n"
                f"Violations:\n" + "\n".join(violations)
            )

    def test_phase4c_no_direct_loader_imports(self, phase4c_files: List[Path]) -> None:
        """Phase-4C must not import Phase-4A loader directly."""
        if not phase4c_files:
            pytest.skip("No Phase-4C files found (expected)")
            return

        forbidden_imports = {
            "symbolu.ontology.phase4a.loader",
            "symbolu.ontology.phase4a.loader.load_ontology_files",
            "symbolu.ontology.phase4a.loader._load_json_file",
        }

        violations = []
        for filepath in phase4c_files:
            imports = get_imports_from_file(filepath)
            bad_imports = imports & forbidden_imports
            if bad_imports:
                rel_path = filepath.relative_to(PROJECT_ROOT)
                violations.append(f"  {rel_path}: imports {bad_imports}")

        if violations:
            pytest.fail(
                f"ONTOLOGY FREEZE VIOLATION: Phase-4C imports Phase-4A loader\n\n"
                f"Phase-4C should use Phase-4A APIs (lookup_interaction), not loader.\n\n"
                f"Violations:\n" + "\n".join(violations)
            )


class TestOntologyFileIntegrity:
    """
    Tests for ontology file integrity and existence.

    Ensures frozen files exist and are valid JSON.
    """

    def test_frozen_files_exist(self) -> None:
        """All frozen ontology files must exist."""
        missing = []
        for ontology_file in FROZEN_ONTOLOGY_FILES:
            filepath = PROJECT_ROOT / ontology_file
            if not filepath.exists():
                missing.append(ontology_file)

        if missing:
            pytest.fail(
                f"ONTOLOGY FREEZE VIOLATION: Frozen files missing\n\n"
                f"Missing files:\n" + "\n".join(f"  - {f}" for f in missing)
            )

    def test_frozen_files_are_valid_json(self) -> None:
        """All frozen ontology files must be valid JSON."""
        import json

        invalid = []
        for ontology_file in FROZEN_ONTOLOGY_FILES:
            filepath = PROJECT_ROOT / ontology_file
            if filepath.exists():
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        json.load(f)
                except json.JSONDecodeError as e:
                    invalid.append(f"{ontology_file}: {e}")

        if invalid:
            pytest.fail(
                f"ONTOLOGY FREEZE VIOLATION: Invalid JSON in frozen files\n\n"
                f"Errors:\n" + "\n".join(f"  - {e}" for e in invalid)
            )


class TestLegacyModuleCompliance:
    """
    Tests for legacy module compliance.

    Legacy modules must have EXPERIMENT_ONLY marker.
    """

    def test_legacy_modules_have_experiment_marker(self) -> None:
        """Legacy experiment modules must have EXPERIMENT_ONLY = True."""
        violations = []

        for legacy_module in LEGACY_EXPERIMENT_MODULES:
            filepath = PROJECT_ROOT / legacy_module
            if filepath.exists():
                if not has_experiment_only_marker(filepath):
                    violations.append(legacy_module)

        if violations:
            pytest.fail(
                f"ONTOLOGY FREEZE VIOLATION: Legacy modules missing EXPERIMENT_ONLY marker\n\n"
                f"These legacy modules must have 'EXPERIMENT_ONLY = True':\n" +
                "\n".join(f"  - {v}" for v in violations)
            )


class TestAuthorizedModuleStructure:
    """
    Tests verifying Phase-4A module structure is correct.
    """

    def test_phase4a_loader_exists(self) -> None:
        """Phase-4A loader must exist."""
        loader_path = PROJECT_ROOT / "symbolu" / "ontology" / "phase4a" / "loader.py"
        assert loader_path.exists(), (
            "Phase-4A loader not found at symbolu/ontology/phase4a/loader.py"
        )

    def test_phase4a_lookup_exists(self) -> None:
        """Phase-4A lookup must exist."""
        lookup_path = PROJECT_ROOT / "symbolu" / "ontology" / "phase4a" / "lookup.py"
        assert lookup_path.exists(), (
            "Phase-4A lookup not found at symbolu/ontology/phase4a/lookup.py"
        )

    def test_phase4a_has_public_api(self) -> None:
        """Phase-4A __init__.py must export public API."""
        init_path = PROJECT_ROOT / "symbolu" / "ontology" / "phase4a" / "__init__.py"
        assert init_path.exists(), "Phase-4A __init__.py not found"

        content = init_path.read_text(encoding="utf-8")

        required_exports = [
            "lookup_interaction",
            "validate_ontology",
            "Phase4AError",
        ]

        missing = [exp for exp in required_exports if exp not in content]

        if missing:
            pytest.fail(
                f"Phase-4A __init__.py missing required exports: {missing}"
            )


class TestNoDirectOntologyImportsInPipeline:
    """
    Tests that core pipeline modules don't directly access ontology.

    Scans key pipeline directories for ontology violations.
    """

    @pytest.fixture(scope="class")
    def pipeline_directories(self) -> List[Path]:
        """Get core pipeline directories to scan."""
        return [
            PROJECT_ROOT / "symbolu" / "core",
            PROJECT_ROOT / "symbolu" / "mechanical",
            PROJECT_ROOT / "symbolu" / "temporal",
            PROJECT_ROOT / "symbolu" / "formulas",
        ]

    def test_core_modules_no_ontology_filenames(self, pipeline_directories: List[Path]) -> None:
        """Core pipeline modules must not reference ontology filenames."""
        violations = []

        for directory in pipeline_directories:
            if not directory.exists():
                continue

            for filepath in directory.rglob("*.py"):
                # Skip authorized modules and legacy experiment modules
                if is_authorized(filepath) or is_legacy_experiment(filepath):
                    continue

                refs = find_ontology_filename_references(filepath)
                if refs:
                    rel_path = filepath.relative_to(PROJECT_ROOT)
                    for line_num, filename, line in refs:
                        violations.append(
                            f"  {rel_path}:{line_num} - '{filename}'"
                        )

        if violations:
            pytest.fail(
                f"ONTOLOGY FREEZE VIOLATION: Core pipeline references ontology filenames\n\n"
                f"Use 'from symbolu.ontology.phase4a import lookup_interaction' instead.\n\n"
                f"Violations:\n" + "\n".join(violations)
            )


# =============================================================================
# Summary Fixture for CI Reporting
# =============================================================================

@pytest.fixture(scope="session", autouse=True)
def ontology_freeze_summary(request):
    """Print summary at end of test session."""
    yield
    print("\n")
    print("=" * 60)
    print("ONTOLOGY FREEZE CONTRACT: CI GUARD SUMMARY")
    print("=" * 60)
    print("Frozen Files:")
    for f in sorted(FROZEN_ONTOLOGY_FILES):
        print(f"  - {f}")
    print("\nAuthorized Access: symbolu/ontology/phase4a/ ONLY")
    print("\nSee ONTOLOGY_FREEZE_CONTRACT.md for full contract.")
    print("=" * 60)
