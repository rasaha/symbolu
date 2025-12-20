"""
Snapshot Testing Utilities
===========================

Helper functions for snapshot-based testing of renderer outputs.

Features:
- Exact text comparison against stored golden files
- Automatic snapshot generation when missing or REGENERATE_SNAPSHOTS=1
- Normalized line endings for cross-platform consistency
- Diff output on failure for debugging

Usage:
    from renderer.tests.snapshot_utils import assert_snapshot

    output = renderer.render(input_data)
    assert_snapshot(output, "path/to/snapshot.snap")

Environment Variables:
    REGENERATE_SNAPSHOTS=1  - Force regeneration of all snapshots

Version: 1.0
"""

import os
from pathlib import Path
from typing import Union


def normalize_line_endings(text: str) -> str:
    """
    Normalize line endings to Unix-style (LF).

    Converts:
    - CRLF (Windows) -> LF
    - CR (old Mac) -> LF

    Args:
        text: Input text with any line ending style

    Returns:
        Text with normalized LF line endings
    """
    # First convert CRLF to LF, then convert any remaining CR to LF
    return text.replace("\r\n", "\n").replace("\r", "\n")


def read_snapshot(snapshot_path: Path) -> str:
    """
    Read snapshot file content with normalized line endings.

    Args:
        snapshot_path: Path to the snapshot file

    Returns:
        Normalized content of the snapshot file
    """
    with open(snapshot_path, "r", encoding="utf-8") as f:
        content = f.read()
    return normalize_line_endings(content)


def write_snapshot(snapshot_path: Path, content: str) -> None:
    """
    Write content to snapshot file with normalized line endings.

    Creates parent directories if they don't exist.

    Args:
        snapshot_path: Path to the snapshot file
        content: Content to write (will be normalized)
    """
    # Ensure parent directory exists
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)

    # Normalize and write
    normalized_content = normalize_line_endings(content)
    with open(snapshot_path, "w", encoding="utf-8") as f:
        f.write(normalized_content)


def should_regenerate_snapshots() -> bool:
    """
    Check if snapshot regeneration is enabled.

    Returns:
        True if REGENERATE_SNAPSHOTS environment variable is set to "1"
    """
    return os.environ.get("REGENERATE_SNAPSHOTS", "0") == "1"


def generate_diff(expected: str, actual: str) -> str:
    """
    Generate a unified diff between expected and actual content.

    Args:
        expected: Expected content (from snapshot)
        actual: Actual content (from renderer)

    Returns:
        Unified diff as string
    """
    import difflib

    expected_lines = expected.splitlines(keepends=True)
    actual_lines = actual.splitlines(keepends=True)

    diff = difflib.unified_diff(
        expected_lines,
        actual_lines,
        fromfile="expected (snapshot)",
        tofile="actual (output)",
        lineterm=""
    )

    return "".join(diff)


def write_diff_file(snapshot_path: Path, diff_content: str) -> Path:
    """
    Write diff content to a .diff file alongside the snapshot.

    Args:
        snapshot_path: Path to the snapshot file
        diff_content: The diff content to write

    Returns:
        Path to the created diff file
    """
    diff_path = snapshot_path.with_suffix(".diff")
    with open(diff_path, "w", encoding="utf-8") as f:
        f.write(diff_content)
    return diff_path


def assert_snapshot(
    output: str,
    snapshot_path: Union[str, Path],
    write_diff_on_failure: bool = True
) -> None:
    """
    Assert that output matches the stored snapshot.

    Behavior:
    - If snapshot exists and REGENERATE_SNAPSHOTS!=1:
        Compare exact text -> fail if mismatch
    - If snapshot missing or REGENERATE_SNAPSHOTS=1:
        Write snapshot -> pass

    On mismatch, optionally writes a .diff file for debugging.

    Args:
        output: The actual output from the renderer
        snapshot_path: Path to the snapshot file (relative or absolute)
        write_diff_on_failure: If True, write a .diff file when test fails

    Raises:
        AssertionError: If output doesn't match stored snapshot
    """
    # Convert to Path object
    if isinstance(snapshot_path, str):
        snapshot_path = Path(snapshot_path)

    # Make path absolute if relative
    if not snapshot_path.is_absolute():
        # Resolve relative to the renderer directory
        base_dir = Path(__file__).parent.parent
        snapshot_path = base_dir / snapshot_path

    # Normalize the output
    normalized_output = normalize_line_endings(output)

    # Check if we should regenerate
    regenerate = should_regenerate_snapshots()

    if regenerate or not snapshot_path.exists():
        # Generate/regenerate snapshot
        write_snapshot(snapshot_path, normalized_output)

        if regenerate:
            print(f"[SNAPSHOT] Regenerated: {snapshot_path}")
        else:
            print(f"[SNAPSHOT] Created: {snapshot_path}")

        return  # Pass - snapshot was created/updated

    # Compare against existing snapshot
    expected = read_snapshot(snapshot_path)

    if normalized_output == expected:
        return  # Pass - output matches snapshot

    # Mismatch - generate diff and fail
    diff = generate_diff(expected, normalized_output)

    if write_diff_on_failure:
        diff_path = write_diff_file(snapshot_path, diff)
        error_msg = (
            f"Snapshot mismatch for: {snapshot_path}\n"
            f"Diff written to: {diff_path}\n\n"
            f"--- Diff ---\n{diff}\n"
            f"---\n\n"
            f"To update the snapshot, run with REGENERATE_SNAPSHOTS=1"
        )
    else:
        error_msg = (
            f"Snapshot mismatch for: {snapshot_path}\n\n"
            f"--- Diff ---\n{diff}\n"
            f"---\n\n"
            f"To update the snapshot, run with REGENERATE_SNAPSHOTS=1"
        )

    raise AssertionError(error_msg)


def cleanup_diff_files(snapshot_dir: Union[str, Path]) -> int:
    """
    Clean up .diff files from a snapshot directory.

    Useful for cleaning up after test runs.

    Args:
        snapshot_dir: Directory containing snapshot files

    Returns:
        Number of diff files removed
    """
    if isinstance(snapshot_dir, str):
        snapshot_dir = Path(snapshot_dir)

    count = 0
    for diff_file in snapshot_dir.glob("*.diff"):
        diff_file.unlink()
        count += 1

    return count


__all__ = [
    "assert_snapshot",
    "normalize_line_endings",
    "should_regenerate_snapshots",
    "cleanup_diff_files"
]
