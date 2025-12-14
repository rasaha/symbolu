"""
Scan Imports: Static import scanner for boundary violation detection.

This module statically scans Python files for imports and produces a report
of any boundary violations (authoritative modules importing observer modules).
"""

from __future__ import annotations

import ast
import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from .boundary_rules import (
    AUTHORITATIVE_MODULE_ROOTS,
    OBSERVER_MODULE_ROOTS,
    ModuleType,
    classify_module,
    is_observer_import_violation,
)


# ============================================================================
# VIOLATION DATACLASS
# ============================================================================

@dataclass
class ImportViolation:
    """Represents a single boundary violation."""
    file: str
    line: int
    violation_type: str
    source_module: str
    imported_module: str
    details: str

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ImportEdge:
    """Represents an import relationship."""
    source: str
    target: str
    source_type: str
    target_type: str


# ============================================================================
# IMPORT SCANNER CLASS
# ============================================================================

class ImportScanner:
    """
    Static import scanner for Python files.

    Scans files using AST to extract import statements and detect
    boundary violations.
    """

    def __init__(self, root_path: Path):
        """
        Initialize the scanner.

        Args:
            root_path: Root path of the symbolu codebase.
        """
        self.root_path = root_path
        self.violations: List[ImportViolation] = []
        self.import_edges: List[ImportEdge] = []
        self.scanned_files: int = 0
        self.authoritative_files: int = 0
        self.observer_files: int = 0

    def _file_to_module_path(self, file_path: Path) -> str:
        """Convert a file path to a module path."""
        try:
            relative = file_path.relative_to(self.root_path)
            # Remove .py extension and convert path separators to dots
            module = str(relative).replace(os.sep, ".").replace("/", ".")
            if module.endswith(".py"):
                module = module[:-3]
            if module.endswith(".__init__"):
                module = module[:-9]
            return module
        except ValueError:
            return str(file_path)

    def _extract_imports_from_ast(self, file_path: Path) -> List[Tuple[str, int]]:
        """
        Extract all imports from a Python file using AST.

        Args:
            file_path: Path to the Python file.

        Returns:
            List of (imported_module, line_number) tuples.
        """
        imports = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append((alias.name, node.lineno))
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append((node.module, node.lineno))

        except (SyntaxError, UnicodeDecodeError, IOError):
            pass

        return imports

    def _is_in_authoritative_root(self, module_path: str) -> bool:
        """Check if a module is within an authoritative root."""
        for root in AUTHORITATIVE_MODULE_ROOTS:
            if module_path == root or module_path.startswith(f"{root}."):
                return True
        return False

    def _is_observer_module(self, module_path: str) -> bool:
        """Check if a module is an observer module."""
        for root in OBSERVER_MODULE_ROOTS:
            if module_path == root or module_path.startswith(f"{root}."):
                return True
        return False

    def scan_file(self, file_path: Path) -> List[ImportViolation]:
        """
        Scan a single file for boundary violations.

        Args:
            file_path: Path to the Python file.

        Returns:
            List of violations found in this file.
        """
        violations = []
        source_module = self._file_to_module_path(file_path)
        source_type = classify_module(source_module)

        # Track file type
        if source_type == ModuleType.AUTHORITATIVE:
            self.authoritative_files += 1
        elif source_type == ModuleType.OBSERVER:
            self.observer_files += 1

        imports = self._extract_imports_from_ast(file_path)

        for imported_module, line_no in imports:
            target_type = classify_module(imported_module)

            # Record edge
            self.import_edges.append(ImportEdge(
                source=source_module,
                target=imported_module,
                source_type=source_type.value,
                target_type=target_type.value,
            ))

            # Check for violation
            if is_observer_import_violation(source_module, imported_module):
                violation = ImportViolation(
                    file=str(file_path),
                    line=line_no,
                    violation_type="forbidden_import",
                    source_module=source_module,
                    imported_module=imported_module,
                    details=f"Authoritative module imports observer: {imported_module}",
                )
                violations.append(violation)
                self.violations.append(violation)

        self.scanned_files += 1
        return violations

    def scan_directory(self, directory: Path, recursive: bool = True) -> List[ImportViolation]:
        """
        Scan a directory for boundary violations.

        Args:
            directory: Directory to scan.
            recursive: Whether to scan recursively.

        Returns:
            List of violations found.
        """
        violations = []

        if not directory.exists():
            return violations

        pattern = "**/*.py" if recursive else "*.py"
        for py_file in directory.glob(pattern):
            # Skip __pycache__ and test directories in authoritative scan
            if "__pycache__" in str(py_file):
                continue
            file_violations = self.scan_file(py_file)
            violations.extend(file_violations)

        return violations

    def scan_authoritative_modules(self) -> List[ImportViolation]:
        """
        Scan all authoritative module roots for observer imports.

        Returns:
            List of violations found.
        """
        violations = []

        for root in AUTHORITATIVE_MODULE_ROOTS:
            # Convert module path to directory path
            dir_path = self.root_path / root.replace(".", os.sep)
            if dir_path.exists():
                dir_violations = self.scan_directory(dir_path)
                violations.extend(dir_violations)

        return violations

    def get_authoritative_to_observer_edges(self) -> List[ImportEdge]:
        """Get all import edges from authoritative to observer modules."""
        return [
            edge for edge in self.import_edges
            if edge.source_type == "authoritative" and edge.target_type == "observer"
        ]


# ============================================================================
# REPORT GENERATION
# ============================================================================

@dataclass
class BoundaryReport:
    """Complete boundary scan report."""
    timestamp: str
    violations: List[Dict]
    import_graph: Dict
    counts: Dict

    def to_dict(self) -> Dict:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


def scan_for_violations(root_path: Path) -> Tuple[List[ImportViolation], ImportScanner]:
    """
    Scan the codebase for boundary violations.

    Args:
        root_path: Root path of the symbolu codebase.

    Returns:
        Tuple of (violations list, scanner instance).
    """
    scanner = ImportScanner(root_path)
    violations = scanner.scan_authoritative_modules()
    return violations, scanner


def generate_boundary_report(
    root_path: Path,
    output_path: Optional[Path] = None
) -> BoundaryReport:
    """
    Generate a complete boundary scan report.

    Args:
        root_path: Root path of the symbolu codebase.
        output_path: Optional path to write the JSON report.

    Returns:
        BoundaryReport instance.
    """
    violations, scanner = scan_for_violations(root_path)

    auth_to_observer_edges = scanner.get_authoritative_to_observer_edges()

    report = BoundaryReport(
        timestamp=datetime.utcnow().isoformat() + "Z",
        violations=[v.to_dict() for v in violations],
        import_graph={
            "authoritative_to_observer_edges": [
                {"source": e.source, "target": e.target}
                for e in auth_to_observer_edges
            ],
            "total_edges_scanned": len(scanner.import_edges),
        },
        counts={
            "authoritative_modules_scanned": scanner.authoritative_files,
            "observer_modules_scanned": scanner.observer_files,
            "total_files_scanned": scanner.scanned_files,
            "violations_found": len(violations),
        },
    )

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report.to_json())

    return report


def print_report_summary(report: BoundaryReport) -> str:
    """
    Generate a human-readable summary of the boundary report.

    Args:
        report: The boundary report to summarize.

    Returns:
        Human-readable summary string.
    """
    lines = [
        "=" * 70,
        "BOUNDARY SCAN REPORT",
        "=" * 70,
        f"Timestamp: {report.timestamp}",
        "",
        "SCAN COUNTS:",
        f"  Authoritative modules scanned: {report.counts['authoritative_modules_scanned']}",
        f"  Observer modules scanned: {report.counts['observer_modules_scanned']}",
        f"  Total files scanned: {report.counts['total_files_scanned']}",
        "",
        "IMPORT GRAPH:",
        f"  Total import edges: {report.import_graph['total_edges_scanned']}",
        f"  Authoritative->Observer edges: {len(report.import_graph['authoritative_to_observer_edges'])}",
        "",
    ]

    if report.violations:
        lines.extend([
            "VIOLATIONS FOUND:",
            "-" * 40,
        ])
        for v in report.violations:
            lines.append(f"  {v['file']}:{v['line']}")
            lines.append(f"    {v['details']}")
        lines.append("")
    else:
        lines.extend([
            "VIOLATIONS: NONE",
            "",
            "All authoritative modules respect the observer boundary.",
        ])

    lines.extend([
        "",
        "=" * 70,
        f"RESULT: {'FAIL' if report.violations else 'PASS'}",
        "=" * 70,
    ])

    return "\n".join(lines)


# ============================================================================
# CLI ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import sys

    # Determine root path
    script_dir = Path(__file__).parent
    root_path = script_dir.parent.parent.parent  # symbolu/tools/boundary_enforcer -> symbolu root

    # Generate report
    output_path = root_path / "artifacts" / "boundary_report.json"
    report = generate_boundary_report(root_path, output_path)

    # Print summary
    print(print_report_summary(report))

    # Exit with error code if violations found
    sys.exit(1 if report.violations else 0)
