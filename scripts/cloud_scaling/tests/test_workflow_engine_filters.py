"""Every workflow that runs the shared sweep engine must watch it.

The three Cloud Scaling sweeps — Phase 5A `authorization-contracts`, Phase 5B
`policy-authenticity`, and `capacity-bounds-policy` — all invoke
``scripts/cloud_scaling/guard_sweep.py``. For a long time only the last of them listed
that path in its filters, so a commit touching the engine and nothing else re-ran one
sweep of the three, and the two packages carrying 114 and 119 inventoried guards kept a
green tick earned by a run against the *previous* engine.

That gap was invisible because it never showed up in practice: every engine change so far
also regenerated a checked-in inventory inside those packages, which matched their
package-scoped filters. The one change that would have exposed it — an adversarial audit's
fix to `_raising_helpers`, which touched the engine alone — is exactly the shape this
guards against.

Deliberately dependency-free. These tests run under jobs that install nothing but
``pytest``, so importing ``yaml`` here would turn a passing gate into an ImportError in
three workflows at once. The parse below reads only the ``on:`` block's ``paths:`` lists
and asserts its own preconditions, so a workflow it fails to understand fails loudly
rather than passing vacuously.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
WORKFLOWS = REPO / ".github" / "workflows"
ENGINE = "scripts/cloud_scaling/guard_sweep.py"


def _trigger_paths(text: str) -> dict:
    """``{trigger: [path, ...]}`` for each ``paths:`` list inside the top-level ``on:``.

    A deliberately small reader: it walks the ``on:`` block by indentation, tracks which
    trigger it is inside, and collects the items of that trigger's ``paths:`` sequence.
    Anything it cannot account for is left out, and the callers below assert the result is
    non-empty, so a shape this does not model cannot quietly satisfy a test.
    """

    lines = text.splitlines()
    try:
        start = next(i for i, l in enumerate(lines) if re.match(r"^on:\s*$", l))
    except StopIteration:  # pragma: no cover - every workflow here has a block `on:`
        return {}

    found: dict = {}
    trigger = None
    in_paths = False
    for line in lines[start + 1:]:
        if line.strip() == "" or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0:  # left the `on:` block entirely
            break
        stripped = line.strip()
        if indent == 2 and stripped.endswith(":"):
            trigger = stripped[:-1]
            in_paths = False
            continue
        if indent == 4 and stripped == "paths:":
            in_paths = True
            found.setdefault(trigger, [])
            continue
        if indent == 4 and stripped.endswith(":"):
            in_paths = False
            continue
        if in_paths and stripped.startswith("- "):
            found[trigger].append(stripped[2:].strip().strip('"').strip("'"))
    return found


def _runs_the_shared_engine(text: str) -> bool:
    """True when a `run:` step invokes the shared engine — not merely names the path."""

    return bool(re.search(r"python[0-9.]*\s+" + re.escape(ENGINE), text))


SHARED_ENGINE_WORKFLOWS = sorted(
    path
    for path in WORKFLOWS.glob("*.yml")
    if _runs_the_shared_engine(path.read_text(encoding="utf-8"))
)


def test_the_shared_engine_is_run_by_the_four_sweeps_this_expects():
    """A floor, not an equality: a fifth adopter must not silently go unchecked."""

    names = {p.name for p in SHARED_ENGINE_WORKFLOWS}
    assert names >= {
        "cloud-scaling-authorization-contracts-ci.yml",
        "cloud-scaling-policy-authenticity-ci.yml",
        "cloud-scaling-capacity-bounds-policy-ci.yml",
        "cloud-scaling-producer-attestation-ci.yml",
    }, f"a sweep stopped invoking the shared engine, or moved: {sorted(names)}"


def test_producer_attestation_adopted_the_shared_engine():
    """The in-package fork is retired; the ruled adoption must not quietly regress.

    This test used to assert the opposite — that the package's workflow ran its own
    ``scripts/guard_sweep.py`` and was not in the shared engine's scope. The adoption
    ruling retired the fork for the shared engine's ``producer-attestation`` entry, so a
    workflow that reintroduced a package-local sweep script, or stopped invoking the
    shared engine, would be un-ruling that decision.
    """

    text = (WORKFLOWS / "cloud-scaling-producer-attestation-ci.yml").read_text(encoding="utf-8")
    assert _runs_the_shared_engine(text)
    assert "cloud-scaling-producer-attestation/scripts/guard_sweep.py" not in text


@pytest.mark.parametrize(
    "workflow", SHARED_ENGINE_WORKFLOWS, ids=lambda p: p.name.replace("-ci.yml", "")
)
@pytest.mark.parametrize("trigger", ["pull_request", "push"])
def test_a_workflow_that_runs_the_engine_watches_the_engine(workflow, trigger):
    """Both triggers, because they are specified separately and a gap in either is a gap.

    A `push`-only miss is the quieter half: the branch patterns mean it bites on exactly
    the long-lived integration branches where a stale sweep result survives longest.
    """

    paths = _trigger_paths(workflow.read_text(encoding="utf-8"))
    assert trigger in paths and paths[trigger], (
        f"{workflow.name} has no readable `{trigger}.paths` list; this test cannot "
        "confirm anything about it, which is a failure rather than a pass"
    )
    assert ENGINE in paths[trigger], (
        f"{workflow.name} runs {ENGINE} but its `{trigger}` filter does not watch it, so "
        f"an engine-only change re-runs this sweep nowhere. Filter is: {paths[trigger]}"
    )
