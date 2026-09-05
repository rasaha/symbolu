"""A package may not ship a test suite that no CI workflow runs.

This exists because twenty-two of sixty-one packages had exactly that — including
every package of the wave 2 and wave 3 governance programme and four of the five
wave 1 seams. Each shipped with its suite green locally, and nothing ran it
afterwards, for months. The repository's one-workflow-per-package convention is
sound; what was missing was anything that noticed when a workflow failed to arrive.

These tests assert the class, not the twenty-two instances.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "check_package_ci_coverage.py"

sys.path.insert(0, str(REPO / "scripts"))
import check_package_ci_coverage as coverage  # noqa: E402


def test_every_package_with_a_suite_is_named_by_some_workflow():
    missing = coverage.uncovered()
    assert not missing, (
        "these packages have a tests/ directory that no workflow runs:\n  "
        + "\n  ".join(missing))


def test_the_script_agrees_with_the_test_and_exits_zero():
    """The gate CI runs and the gate the suite runs are the same gate."""

    result = subprocess.run([sys.executable, str(SCRIPT)],
                            capture_output=True, text=True, cwd=str(REPO))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PACKAGE CI COVERAGE OK" in result.stdout


def test_the_check_can_actually_fail():
    """A gate that cannot fail is not a gate.

    Rather than trusting the report, this hides every workflow from the detector and
    asserts that the packages then come back uncovered.
    """

    real = coverage.WORKFLOWS
    try:
        coverage.WORKFLOWS = REPO / "scripts"     # a directory with no workflows
        blinded = coverage.uncovered()
    finally:
        coverage.WORKFLOWS = real

    assert blinded, "with no workflows visible, every package must be uncovered"
    assert len(blinded) == len(coverage.packages_with_suites())
    # and the real answer is restored afterwards
    assert coverage.uncovered() == []


def test_no_package_is_exempt_without_a_stated_reason():
    """``EXEMPT`` is a place to defend a decision, not to park a package."""

    for package, reason in coverage.EXEMPT.items():
        assert reason.strip(), package
        assert (REPO / package).is_dir(), f"{package} is exempt but does not exist"


def test_the_discovery_finds_the_packages_that_exist():
    """The detector's own inputs, pinned: a package is one with a pyproject and a
    tests/ directory, and there are more than fifty of them."""

    found = coverage.packages_with_suites()
    assert len(found) > 50, len(found)
    for known in ("packages/governance-contracts",
                  "packages/integration/control-plane-root",
                  "packages/capabilities/storygraph"):
        assert known in found, known
