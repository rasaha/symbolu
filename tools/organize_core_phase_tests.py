#!/usr/bin/env python3
"""
organize_core_phase_tests.py

Utility script to reorganize core substrate phase tests (Phase-1b through Phase-4)
into a dedicated `tests/core_phases/` directory.

These core tests are:
- Foundational
- Deterministic
- Non-generative
- Not runtime regression tests

This script moves ONLY the specified files and leaves all other test files untouched.

Usage:
    python tools/organize_core_phase_tests.py

Must be run from the repository root directory.
"""

import os
import shutil
import sys
from pathlib import Path

# Files to move (relative to tests/ directory)
CORE_PHASE_FILES = [
    # Phase-1b
    "test_phase1b_validation_v3_1.py",
    # Phase-2
    "test_phase2_modifiers_v1.py",
    # Phase-3
    "test_phase3_rule_engine_v3_0.py",
    # Phase-4
    "test_phase4_transform_v4_0.py",
    "test_phase4_transform_v4_0_results.md",
    "test_phase4_transform_v4_0_summary.md",
    "test_phase4_transform_v4_0_readme.md",
]

TESTS_DIR = "tests"
CORE_PHASES_DIR = "tests/core_phases"


def verify_repository_root() -> bool:
    """Verify script is running from repository root."""
    # Check for common repository root indicators
    indicators = [".git", "tests", "src", "symbolu"]
    found = sum(1 for ind in indicators if os.path.exists(ind))
    return found >= 2


def main() -> int:
    """Main entry point."""
    print("=" * 60)
    print("Core Phase Test Organizer")
    print("=" * 60)
    print()

    # Step 1: Verify repository root
    if not verify_repository_root():
        print("ERROR: This script must be run from the repository root.")
        print("       Please cd to the repository root and run again.")
        return 1

    # Step 2: Verify tests/ exists
    if not os.path.isdir(TESTS_DIR):
        print(f"ERROR: '{TESTS_DIR}/' directory not found.")
        print("       Are you in the correct repository?")
        return 1

    print(f"✔ Repository root verified")
    print(f"✔ Found '{TESTS_DIR}/' directory")
    print()

    # Step 3: Create tests/core_phases/ if missing
    if not os.path.exists(CORE_PHASES_DIR):
        os.makedirs(CORE_PHASES_DIR)
        print(f"✔ Created '{CORE_PHASES_DIR}/' directory")
    else:
        print(f"✔ '{CORE_PHASES_DIR}/' directory already exists")
    print()

    # Step 4: Check for conflicts (target files that already exist)
    conflicts = []
    for filename in CORE_PHASE_FILES:
        source = os.path.join(TESTS_DIR, filename)
        target = os.path.join(CORE_PHASES_DIR, filename)
        if os.path.exists(source) and os.path.exists(target):
            conflicts.append(filename)

    if conflicts:
        print("ERROR: Target files already exist in core_phases/:")
        for f in conflicts:
            print(f"       - {f}")
        print()
        print("       Please resolve conflicts manually before running again.")
        return 1

    # Step 5: Move files
    print("Moving core phase test files:")
    print("-" * 40)

    moved_count = 0
    skipped_count = 0

    for filename in CORE_PHASE_FILES:
        source = os.path.join(TESTS_DIR, filename)
        target = os.path.join(CORE_PHASES_DIR, filename)

        if not os.path.exists(source):
            print(f"⚠ Skipped (not found): {filename}")
            skipped_count += 1
            continue

        # Move the file
        shutil.move(source, target)
        print(f"✔ Moved: {filename}")
        moved_count += 1

    print()
    print("-" * 40)
    print(f"Summary: {moved_count} moved, {skipped_count} skipped")
    print()

    if moved_count > 0:
        print("✔ Core phase test isolation complete")
        print()
        print("Next steps:")
        print("  1. Review the changes: git status")
        print("  2. Run tests to verify: pytest tests/core_phases/")
        print("  3. Commit when satisfied: git add -A && git commit")
    else:
        print("⚠ No files were moved (all files already organized or missing)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
