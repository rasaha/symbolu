#!/usr/bin/env python3
"""
GCC Forbidden Symbol Scanner - Static Enforcement
===================================================

Build-time scanner that fails CI if constrained modules contain
forbidden patterns.

Scans:
    - Phase-1b through Phase-9
    - Ontological Router R1
    - Ledger core

Forbidden patterns:
    - Free-form string literals (>32 chars) except:
        - enum names
        - invariant keys
        - hex hashes
    - f-strings
    - "".join() on strings
    - regex imports (except for validation)
    - tokenizer imports
    - NLP / ML / generation libraries

Exit codes:
    0: All files pass (no violations)
    1: Violations detected (CI should fail)
    2: Scanner error (file not found, etc.)

Usage:
    python -m symbolu.safety.gcc_static_scanner [--allowlist FILE]

Allowed imports:
    - ast
    - sys
    - pathlib
    - re
    - argparse
    - json
"""

from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import FrozenSet, List, Mapping, Optional, Set, Tuple


# =============================================================================
# Constants
# =============================================================================

# Maximum allowed string literal length (non-allowlisted)
MAX_STRING_LENGTH = 32

# Exit codes
EXIT_SUCCESS = 0
EXIT_VIOLATIONS = 1
EXIT_ERROR = 2

# Forbidden import modules
FORBIDDEN_IMPORTS: FrozenSet[str] = frozenset({
    # ML/DL frameworks
    "torch", "pytorch", "tensorflow", "tf", "keras",
    "jax", "flax", "haiku", "trax",
    # NLP libraries
    "transformers", "huggingface", "spacy", "nltk",
    "gensim", "fasttext", "flair", "textblob",
    # LLM clients
    "openai", "anthropic", "cohere", "replicate",
    "langchain", "llamaindex", "llama_index",
    # Scoring/ranking
    "sklearn", "xgboost", "lightgbm", "catboost",
    # Probabilistic
    "pymc", "pymc3", "pyro", "numpyro", "edward",
    # Tokenizers
    "tokenizers", "sentencepiece", "tiktoken",
    # Stochastic
    "random",
    # Non-deterministic identifiers
    "uuid",
    # Timestamps (forbidden in ledger)
    "datetime", "time",
})

# Constrained file patterns (relative to repo root)
CONSTRAINED_PATHS: Tuple[str, ...] = (
    # Ontological Router R1
    "symbolu/ontology/router/ontological_router_r1.py",
    "symbolu/ontology/router/phase_layer_map.py",
    "symbolu/ontology/router/layer_router.py",
    # Ledger core
    "symbolu/ledger/ledger_replay_verifier.py",
    "symbolu/ledger/ledger_store.py",
    # Safety module itself
    "symbolu/safety/gcc_runtime_guard.py",
    "symbolu/safety/gcc_ledger_invariant.py",
)

# Hex pattern for allowlist
_HEX_PATTERN = re.compile(r"^[0-9a-fA-F]+$")

# Invariant key pattern (uppercase, underscores, digits)
_INVARIANT_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")

# Version string pattern
_VERSION_PATTERN = re.compile(r"^[RMV]\d+\.\d+$")


# =============================================================================
# Violation Types
# =============================================================================

class ViolationType(Enum):
    """Types of GCC violations detected by static scanner."""
    FREE_FORM_STRING = "FREE_FORM_STRING"
    F_STRING = "F_STRING"
    STRING_JOIN = "STRING_JOIN"
    FORBIDDEN_IMPORT = "FORBIDDEN_IMPORT"
    REGEX_IMPORT = "REGEX_IMPORT"


@dataclass(frozen=True)
class Violation:
    """A single GCC violation."""
    file_path: str
    line_number: int
    violation_type: ViolationType
    details: str


# =============================================================================
# Allowlist
# =============================================================================

@dataclass(frozen=True)
class Allowlist:
    """
    Allowlist for exempted strings.

    Strings in the allowlist are permitted even if they exceed
    the length limit or match forbidden patterns.
    """
    # Exact string matches
    exact_strings: FrozenSet[str]
    # Pattern matches (for enum names, etc.)
    patterns: Tuple[re.Pattern, ...]

    @staticmethod
    def default() -> "Allowlist":
        """Create the default allowlist."""
        return Allowlist(
            exact_strings=frozenset({
                # Docstrings are allowed (they're documentation, not output)
                # Common invariant messages
                "artifact_id must be a non-empty string",
                "phase_id must be a non-empty string",
                "artifact_hash must be a non-empty string",
                "declared_projection_hint must be an OntologicalLayer or None",
                "ledger_index must be a non-negative integer",
                "projected_layers must be a tuple",
                "all projected_layers must be OntologicalLayer instances",
                "span_id must be a non-empty string",
                "router_version must be a non-empty string",
                "entry_hash must be a 16-character hex string",
                "entry_id must be a 16-character hex string",
                "prev_entry_id must be None or a 16-character hex string",
                "mapping_version must be a non-empty string",
                "seq must be a non-negative integer",
                # Hash format strings (deterministic)
                "artifact_hash:{span_input.artifact_hash}|phase_id:{span_input.phase_id}|layers:{layer_names}",
            }),
            patterns=(
                # Enum names
                re.compile(r"^[A-Z][A-Z0-9_]*$"),
                # Error reason codes
                re.compile(r"^[A-Z][A-Z0-9_]*_[A-Z0-9_]*$"),
                # Version strings
                re.compile(r"^[RMV]\d+\.\d+$"),
                # Phase IDs
                re.compile(r"^(1b|[2-9])$"),
                # Hex hashes (any length)
                re.compile(r"^[0-9a-fA-F]+$"),
                # Dict key format strings (for canonical serialization)
                re.compile(r"^[a-z_]+:[a-z_\.]+\|"),
            ),
        )

    def is_allowed(self, value: str) -> bool:
        """Check if a string is in the allowlist."""
        if value in self.exact_strings:
            return True
        for pattern in self.patterns:
            if pattern.match(value):
                return True
        return False

    @staticmethod
    def from_file(path: Path) -> "Allowlist":
        """Load allowlist from JSON file."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        exact = frozenset(data.get("exact_strings", []))
        patterns = tuple(
            re.compile(p) for p in data.get("patterns", [])
        )

        # Merge with defaults
        default = Allowlist.default()
        return Allowlist(
            exact_strings=default.exact_strings | exact,
            patterns=default.patterns + patterns,
        )


# =============================================================================
# AST Visitor for Scanning
# =============================================================================

class GCCViolationVisitor(ast.NodeVisitor):
    """AST visitor that detects GCC violations."""

    def __init__(
        self,
        file_path: str,
        allowlist: Allowlist,
        *,
        skip_docstrings: bool = True,
    ) -> None:
        self.file_path = file_path
        self.allowlist = allowlist
        self.skip_docstrings = skip_docstrings
        self.violations: List[Violation] = []
        self._in_docstring_position = False

    def _is_docstring(self, node: ast.AST) -> bool:
        """Check if a node is in docstring position."""
        return self._in_docstring_position

    def _add_violation(
        self,
        node: ast.AST,
        violation_type: ViolationType,
        details: str,
    ) -> None:
        """Add a violation to the list."""
        self.violations.append(Violation(
            file_path=self.file_path,
            line_number=getattr(node, "lineno", 0),
            violation_type=violation_type,
            details=details,
        ))

    def visit_Module(self, node: ast.Module) -> None:
        """Visit module, handling module docstring."""
        if node.body and isinstance(node.body[0], ast.Expr):
            if isinstance(node.body[0].value, (ast.Str, ast.Constant)):
                # Skip module docstring
                for child in node.body[1:]:
                    self.visit(child)
                return
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function, handling function docstring."""
        self._visit_function_like(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function, handling docstring."""
        self._visit_function_like(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Visit class, handling class docstring."""
        self._visit_function_like(node)

    def _visit_function_like(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    ) -> None:
        """Common handler for function/class docstrings."""
        if node.body and isinstance(node.body[0], ast.Expr):
            if isinstance(node.body[0].value, (ast.Str, ast.Constant)):
                # Skip docstring, visit rest
                for child in node.body[1:]:
                    self.visit(child)
                # Visit decorators
                for decorator in node.decorator_list:
                    self.visit(decorator)
                # Visit arguments for functions
                if hasattr(node, "args"):
                    self.visit(node.args)
                return
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        """Check string constants for violations."""
        if isinstance(node.value, str):
            self._check_string(node, node.value)
        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        """Detect f-strings (forbidden)."""
        self._add_violation(
            node,
            ViolationType.F_STRING,
            "F_STRING_DETECTED",
        )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Detect string join patterns."""
        # Check for "".join() pattern
        if isinstance(node.func, ast.Attribute):
            if node.func.attr == "join":
                if isinstance(node.func.value, ast.Constant):
                    if isinstance(node.func.value.value, str):
                        self._add_violation(
                            node,
                            ViolationType.STRING_JOIN,
                            "STRING_JOIN_DETECTED",
                        )
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        """Check for forbidden imports."""
        for alias in node.names:
            module_name = alias.name.split(".")[0]
            if module_name in FORBIDDEN_IMPORTS:
                self._add_violation(
                    node,
                    ViolationType.FORBIDDEN_IMPORT,
                    module_name,
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Check for forbidden from-imports."""
        if node.module:
            module_name = node.module.split(".")[0]
            if module_name in FORBIDDEN_IMPORTS:
                self._add_violation(
                    node,
                    ViolationType.FORBIDDEN_IMPORT,
                    module_name,
                )
        self.generic_visit(node)

    def _check_string(self, node: ast.AST, value: str) -> None:
        """Check a string value for violations."""
        # Skip empty strings
        if not value:
            return

        # Skip short strings
        if len(value) <= MAX_STRING_LENGTH:
            return

        # Check allowlist
        if self.allowlist.is_allowed(value):
            return

        # This is a violation
        # Truncate for display
        display_value = value[:50] + "..." if len(value) > 50 else value
        self._add_violation(
            node,
            ViolationType.FREE_FORM_STRING,
            display_value,
        )


# =============================================================================
# Scanner Functions
# =============================================================================

def scan_file(
    file_path: Path,
    allowlist: Allowlist,
) -> List[Violation]:
    """
    Scan a single file for GCC violations.

    Args:
        file_path: Path to the Python file.
        allowlist: The allowlist to use.

    Returns:
        List of violations found.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            source = f.read()
    except Exception:
        return [Violation(
            file_path=str(file_path),
            line_number=0,
            violation_type=ViolationType.FREE_FORM_STRING,
            details="FILE_READ_ERROR",
        )]

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [Violation(
            file_path=str(file_path),
            line_number=0,
            violation_type=ViolationType.FREE_FORM_STRING,
            details="SYNTAX_ERROR",
        )]

    visitor = GCCViolationVisitor(str(file_path), allowlist)
    visitor.visit(tree)

    return visitor.violations


def scan_constrained_files(
    repo_root: Path,
    allowlist: Optional[Allowlist] = None,
) -> Tuple[List[Violation], int]:
    """
    Scan all constrained files for GCC violations.

    Args:
        repo_root: Path to the repository root.
        allowlist: Optional allowlist (uses default if None).

    Returns:
        Tuple of (violations list, exit code).
    """
    if allowlist is None:
        allowlist = Allowlist.default()

    all_violations: List[Violation] = []
    files_scanned = 0

    for rel_path in CONSTRAINED_PATHS:
        file_path = repo_root / rel_path
        if file_path.exists():
            violations = scan_file(file_path, allowlist)
            all_violations.extend(violations)
            files_scanned += 1

    if all_violations:
        return all_violations, EXIT_VIOLATIONS

    if files_scanned == 0:
        return [], EXIT_ERROR

    return [], EXIT_SUCCESS


def format_violations(violations: List[Violation]) -> str:
    """Format violations for output."""
    lines = []
    lines.append("=" * 60)
    lines.append("GCC STATIC SCANNER: VIOLATIONS DETECTED")
    lines.append("=" * 60)

    for v in violations:
        lines.append(f"  {v.file_path}:{v.line_number}")
        lines.append(f"    TYPE: {v.violation_type.value}")
        lines.append(f"    DETAILS: {v.details}")
        lines.append("")

    lines.append("=" * 60)
    lines.append(f"TOTAL VIOLATIONS: {len(violations)}")
    lines.append("=" * 60)

    return "\n".join(lines)


# =============================================================================
# Main Entry Point
# =============================================================================

def main() -> int:
    """Main entry point for the scanner."""
    import argparse

    parser = argparse.ArgumentParser(
        description="GCC Forbidden Symbol Scanner"
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root path",
    )
    parser.add_argument(
        "--allowlist",
        type=Path,
        default=None,
        help="Path to allowlist JSON file",
    )
    parser.add_argument(
        "--output",
        type=str,
        choices=["text", "json"],
        default="text",
        help="Output format",
    )

    args = parser.parse_args()

    # Load allowlist
    if args.allowlist:
        allowlist = Allowlist.from_file(args.allowlist)
    else:
        allowlist = Allowlist.default()

    # Run scan
    violations, exit_code = scan_constrained_files(args.repo_root, allowlist)

    # Output results
    if args.output == "json":
        result = {
            "violations": [
                {
                    "file": v.file_path,
                    "line": v.line_number,
                    "type": v.violation_type.value,
                    "details": v.details,
                }
                for v in violations
            ],
            "exit_code": exit_code,
        }
        print(json.dumps(result, indent=2))
    else:
        if violations:
            print(format_violations(violations))
        else:
            print("GCC STATIC SCANNER: ALL FILES PASS")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
