#!/usr/bin/env python3
"""
Verify Imports Tool for Symbolu Repository

This script verifies that all Python modules in the symbolu package can be
compiled successfully. It uses py_compile to check each file individually
and reports any import/syntax errors.

Usage:
    python tools/refactor/verify_imports.py

Exit codes:
    0 - All files compiled successfully
    1 - One or more files failed to compile
"""

import os
import py_compile
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple


def get_python_files(base_path: Path) -> List[Path]:
    """Find all Python files in the given directory recursively."""
    python_files = []
    for root, dirs, files in os.walk(base_path):
        # Skip __pycache__ directories
        dirs[:] = [d for d in dirs if d != "__pycache__"]

        for file in files:
            if file.endswith(".py"):
                python_files.append(Path(root) / file)

    return sorted(python_files)


def compile_file(file_path: Path) -> Tuple[bool, str]:
    """
    Attempt to compile a single Python file.

    Returns:
        Tuple of (success: bool, error_message: str)
    """
    try:
        py_compile.compile(str(file_path), doraise=True)
        return True, ""
    except py_compile.PyCompileError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Unexpected error: {e}"


def run_compileall(base_path: Path) -> Tuple[int, str]:
    """
    Run python -m compileall on the given path.

    Returns:
        Tuple of (return_code: int, output: str)
    """
    result = subprocess.run(
        [sys.executable, "-m", "compileall", "-q", str(base_path)],
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    return result.returncode, output


def main():
    """Main entry point."""
    # Find the symbolu directory
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent.parent
    symbolu_path = repo_root / "symbolu"

    if not symbolu_path.exists():
        print(f"ERROR: symbolu directory not found at {symbolu_path}")
        sys.exit(1)

    print("=" * 70)
    print("Symbolu Import Verification Tool")
    print("=" * 70)
    print()

    # Step 1: Run compileall
    print("Step 1: Running python -m compileall symbolu/")
    print("-" * 70)

    return_code, output = run_compileall(symbolu_path)

    if return_code == 0:
        print("SUCCESS: All files compiled successfully with compileall")
    else:
        print("FAILED: compileall reported errors:")
        print(output)

    print()

    # Step 2: Individual file check for more detailed error reporting
    print("Step 2: Individual file compilation check")
    print("-" * 70)

    python_files = get_python_files(symbolu_path)
    print(f"Found {len(python_files)} Python files")
    print()

    failures: List[Tuple[Path, str]] = []
    successes = 0

    for file_path in python_files:
        success, error = compile_file(file_path)
        if success:
            successes += 1
        else:
            failures.append((file_path, error))

    print(f"Results: {successes} passed, {len(failures)} failed")
    print()

    if failures:
        print("FAILURES:")
        print("-" * 70)
        for file_path, error in failures:
            rel_path = file_path.relative_to(repo_root)
            print(f"\n  {rel_path}")
            print(f"    Error: {error}")
        print()
        print("=" * 70)
        print("RESULT: IMPORT VERIFICATION FAILED")
        print("=" * 70)
        sys.exit(1)
    else:
        print("=" * 70)
        print("RESULT: ALL IMPORTS VERIFIED SUCCESSFULLY")
        print("=" * 70)
        sys.exit(0)


if __name__ == "__main__":
    main()
