#!/usr/bin/env python3
"""
Apply All Patches
=================

Runs all available patches to bring the codebase up to date.

Usage:
    python patches/apply_all.py
"""

import subprocess
import sys
from pathlib import Path

PATCHES_DIR = Path(__file__).parent

PATCHES = [
    "fix_unfold_oom.py",
    "fix_lra_intro_banner.py",
]


def main():
    print("=" * 60)
    print("  APPLYING ALL PATCHES")
    print("=" * 60)
    print()

    success_count = 0
    fail_count = 0

    for patch_name in PATCHES:
        patch_path = PATCHES_DIR / patch_name
        if not patch_path.exists():
            print(f"[SKIP] {patch_name} - not found")
            continue

        print(f"[RUN] {patch_name}")
        result = subprocess.run(
            [sys.executable, str(patch_path)],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            print(f"[OK] {patch_name}")
            success_count += 1
        else:
            print(f"[FAIL] {patch_name}")
            if result.stderr:
                print(f"       {result.stderr.strip()}")
            fail_count += 1
        print()

    print("=" * 60)
    print(f"  SUMMARY: {success_count} passed, {fail_count} failed")
    print("=" * 60)

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
