"""A workflow may not leave superseded runs in the queue, or re-download its dependencies.

Three of ninety-three workflows declared a ``concurrency`` group and five of two hundred
and fifty ``setup-python`` steps set a cache when this was written. The consequence was
visible rather than theoretical: a four-commit pull request fanned out four complete
times, every run kept going, and failure notifications arrived for commits that had
already been fixed while the current head sat behind them in the queue.

These tests assert the class, not the ninety instances.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import yaml

REPO = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "check_workflow_efficiency.py"

sys.path.insert(0, str(REPO / "scripts"))
import check_workflow_efficiency as efficiency  # noqa: E402


def test_every_workflow_declares_a_concurrency_group():
    missing = efficiency.missing_concurrency()
    assert not missing, (
        "these workflows declare no concurrency group, so a superseded run keeps "
        "occupying the queue:\n  " + "\n  ".join(missing))


def test_every_setup_python_step_declares_a_dependency_cache():
    missing = efficiency.uncached_setup_python()
    assert not missing, (
        "these setup-python steps re-download what the last job already had:\n  "
        + "\n  ".join(missing))


def test_the_script_agrees_with_the_tests_and_exits_zero():
    """The gate CI runs and the gate the suite runs are the same gate."""

    result = subprocess.run([sys.executable, str(SCRIPT)],
                            capture_output=True, text=True, cwd=str(REPO))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "WORKFLOW EFFICIENCY OK" in result.stdout


def test_the_checks_can_actually_fail(tmp_path):
    """A gate that cannot fail is not a gate.

    Both detectors are pointed at a directory holding one workflow that declares
    neither, and asserted to report it.
    """
    (tmp_path / "bad.yml").write_text(
        "name: bad\n"
        "on: { pull_request: {} }\n"
        "jobs:\n"
        "  j:\n"
        "    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - uses: actions/setup-python@v5\n"
        "        with:\n"
        "          python-version: '3.11'\n")

    real = efficiency.WORKFLOWS
    try:
        efficiency.WORKFLOWS = tmp_path
        assert efficiency.missing_concurrency() == ["bad.yml"]
        assert efficiency.uncached_setup_python() == ["bad.yml:j"]
    finally:
        efficiency.WORKFLOWS = real

    # and the real tree is still clean afterwards
    assert efficiency.missing_concurrency() == []
    assert efficiency.uncached_setup_python() == []


def test_a_workflow_that_serialises_instead_of_cancelling_still_passes():
    """`demo-export-publish` declares a group and sets ``cancel-in-progress: false``,
    because "two runs replacing the same content would race".

    That is the mechanism working, not an absence of it, so the gate requires a group
    and takes no view on the cancel policy. If this file ever stops being the example,
    the assertion below should be moved rather than deleted.
    """
    document = yaml.safe_load(
        (efficiency.WORKFLOWS / "demo-export-publish.yml").read_text(encoding="utf-8"))
    concurrency = document["concurrency"]

    assert concurrency["group"] == "demo-export-publish"
    assert concurrency["cancel-in-progress"] is False
    assert "demo-export-publish.yml" not in efficiency.missing_concurrency()


def test_pull_request_runs_cancel_and_branch_pushes_do_not():
    """The standard group, on the workflows that use it.

    A branch push must never cancel: each commit's run is the evidence that commit was
    green, and a cancelled run is not evidence of anything.
    """
    standard = 0
    for path in efficiency._workflows():
        concurrency = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("concurrency")
        if not isinstance(concurrency, dict):
            continue
        if concurrency.get("group") == "${{ github.workflow }}-${{ github.ref }}":
            assert concurrency["cancel-in-progress"] == \
                "${{ github.event_name == 'pull_request' }}", path.name
            standard += 1

    assert standard > 50, f"only {standard} workflows use the standard group"


def test_the_discovery_finds_the_workflows_that_exist():
    """The detectors' own input, pinned: a detector that scanned nothing would pass."""
    found = efficiency._workflows()
    assert len(found) > 80, len(found)
    for known in ("package-suites-ci.yml", "agent-workforce-composer-p1-ci.yml"):
        assert any(f.name == known for f in found), known


def test_no_workflow_is_exempt_without_a_stated_reason():
    """The EXEMPT maps are places to defend a decision, not to park a workflow."""
    for name, reason in efficiency.EXEMPT_CONCURRENCY.items():
        assert reason.strip(), name
        assert (efficiency.WORKFLOWS / name).is_file(), f"{name} is exempt but does not exist"
    for location, reason in efficiency.EXEMPT_CACHE.items():
        assert reason.strip(), location
