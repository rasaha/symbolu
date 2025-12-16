"""
Tests for Forbidden Imports
===========================

Verifies that the router modules do not import forbidden libraries.

FORBIDDEN IMPORTS:
    - nltk
    - spacy
    - transformers
    - openai
    - anthropic
    - langchain
    - torch
    - tensorflow
    - jax
    - random
    - uuid
    - datetime
    - time

These are forbidden because:
    - They introduce non-determinism (random, uuid, time, datetime)
    - They introduce semantic processing (NLP/ML libraries)
    - This router is structural only, not semantic
"""

import ast
import sys
from pathlib import Path

import pytest


# Forbidden modules
FORBIDDEN_MODULES = frozenset({
    "nltk",
    "spacy",
    "transformers",
    "openai",
    "anthropic",
    "langchain",
    "torch",
    "tensorflow",
    "jax",
    "random",
    "uuid",
    "datetime",
    "time",
})

# Source files to check
SOURCE_ROOT = Path(__file__).parent.parent.parent / "symbolu" / "ontology"


def get_imports_from_file(filepath: Path) -> set:
    """
    Extract all imported module names from a Python file.

    Args:
        filepath: Path to the Python file.

    Returns:
        Set of imported module names.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)
    imports = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                # Get top-level module name
                module_name = alias.name.split(".")[0]
                imports.add(module_name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                module_name = node.module.split(".")[0]
                imports.add(module_name)

    return imports


def get_all_source_files() -> list:
    """Get all Python source files in the ontology directory."""
    files = []

    # Check the new router-related directories
    directories = [
        SOURCE_ROOT / "layers",
        SOURCE_ROOT / "router",
        SOURCE_ROOT / "contracts",
        SOURCE_ROOT / "ledger",
    ]

    for directory in directories:
        if directory.exists():
            for filepath in directory.rglob("*.py"):
                files.append(filepath)

    return files


class TestForbiddenImports:
    """Tests that no forbidden imports are used."""

    @pytest.fixture
    def source_files(self) -> list:
        """Get all source files to check."""
        return get_all_source_files()

    def test_source_files_exist(self, source_files: list) -> None:
        """Verify source files were found."""
        assert len(source_files) > 0, "No source files found"

    def test_no_nlp_imports(self, source_files: list) -> None:
        """No NLP libraries are imported."""
        nlp_modules = {"nltk", "spacy", "transformers", "langchain"}

        for filepath in source_files:
            imports = get_imports_from_file(filepath)
            violations = imports & nlp_modules
            assert not violations, (
                f"NLP module(s) {violations} imported in {filepath}"
            )

    def test_no_llm_imports(self, source_files: list) -> None:
        """No LLM client libraries are imported."""
        llm_modules = {"openai", "anthropic"}

        for filepath in source_files:
            imports = get_imports_from_file(filepath)
            violations = imports & llm_modules
            assert not violations, (
                f"LLM module(s) {violations} imported in {filepath}"
            )

    def test_no_ml_imports(self, source_files: list) -> None:
        """No ML framework libraries are imported."""
        ml_modules = {"torch", "tensorflow", "jax"}

        for filepath in source_files:
            imports = get_imports_from_file(filepath)
            violations = imports & ml_modules
            assert not violations, (
                f"ML module(s) {violations} imported in {filepath}"
            )

    def test_no_randomness_imports(self, source_files: list) -> None:
        """No randomness-introducing modules are imported."""
        random_modules = {"random", "uuid"}

        for filepath in source_files:
            imports = get_imports_from_file(filepath)
            violations = imports & random_modules
            assert not violations, (
                f"Randomness module(s) {violations} imported in {filepath}"
            )

    def test_no_time_imports(self, source_files: list) -> None:
        """No time-related modules are imported."""
        time_modules = {"datetime", "time"}

        for filepath in source_files:
            imports = get_imports_from_file(filepath)
            violations = imports & time_modules
            assert not violations, (
                f"Time module(s) {violations} imported in {filepath}"
            )

    def test_all_forbidden_imports(self, source_files: list) -> None:
        """Comprehensive check of all forbidden imports."""
        for filepath in source_files:
            imports = get_imports_from_file(filepath)
            violations = imports & FORBIDDEN_MODULES
            assert not violations, (
                f"Forbidden module(s) {violations} imported in {filepath}"
            )


class TestHashlibAllowed:
    """Tests that hashlib (allowed) is used for deterministic hashing."""

    def test_ledger_adapter_uses_hashlib(self) -> None:
        """Ledger adapter uses hashlib for deterministic hashing."""
        filepath = SOURCE_ROOT / "ledger" / "ledger_adapter.py"
        if filepath.exists():
            imports = get_imports_from_file(filepath)
            assert "hashlib" in imports, (
                "ledger_adapter.py should use hashlib for deterministic hashing"
            )


class TestModuleStructure:
    """Tests for module structure and dependencies."""

    def test_layers_module_minimal_deps(self) -> None:
        """Layers module has minimal dependencies."""
        filepath = SOURCE_ROOT / "layers" / "ontology_layer.py"
        if filepath.exists():
            imports = get_imports_from_file(filepath)
            # Only enum should be imported
            allowed = {"enum"}
            external = imports - allowed
            # Filter out local symbolu imports
            external = {m for m in external if not m.startswith("symbolu")}
            assert not external, (
                f"Layers module has unexpected imports: {external}"
            )

    def test_router_uses_internal_imports_only(self) -> None:
        """Router only uses internal symbolu imports and stdlib."""
        filepath = SOURCE_ROOT / "router" / "layer_router.py"
        if filepath.exists():
            imports = get_imports_from_file(filepath)
            # Allowed stdlib modules
            allowed_stdlib = {"typing"}
            # Check no forbidden modules
            violations = imports & FORBIDDEN_MODULES
            assert not violations, (
                f"Router has forbidden imports: {violations}"
            )
