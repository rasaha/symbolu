"""The property ledger: every test is categorised, and the ratio is machine-counted.

The ratified design requires **at least 2:1 adversarial-to-happy distinct properties**,
counted as properties and not as parametrisations. A claimed ratio is worth nothing, so it
is counted here from the markers themselves and asserted.

Three categories, and the boundaries between them are deliberate:

``happy``
    A positive control — something the boundary must **admit**. Without these the suite
    could pass by refusing everything, which would prove nothing.

``adversarial``
    An attack that must be **refused**, or a dangerous capability that must be **absent**.
    Structural absence properties count here: "no verifier returns unconditional success"
    is an adversarial property, because a placeholder verifier is an attack that already
    succeeded.

``invariant``
    A structural, packaging or frozen-value regression anchor — neither an attack nor a
    success path. Frozen digests, the public-API manifest, the dependency manifest, "Phase
    5A is still 0.1.0". They are reported **separately** and are deliberately excluded from
    the ratio, so the ratio cannot be inflated by counting bookkeeping as adversarial.

Each module declares a default with ``pytestmark`` and names every departure explicitly, so
a reader can audit the classification without running anything.
"""

from __future__ import annotations

import collections
import pathlib

import pytest

pytestmark = pytest.mark.invariant

CATEGORIES = ("happy", "adversarial", "invariant")
#: The ratio the ratified design requires, over DISTINCT properties.
REQUIRED_RATIO = 2.0


def _collect(pytestconfig) -> tuple[dict, dict]:
    """Walk the whole suite once and count distinct properties and parametrised cases."""

    import subprocess
    import sys

    root = pathlib.Path(__file__).resolve().parents[1]
    distinct: collections.Counter = collections.Counter()
    cases: collections.Counter = collections.Counter()
    uncategorised: list[str] = []

    for category in CATEGORIES:
        # One collection pass per marker. ``--collect-only -q`` lists node ids, so a
        # parametrised test contributes one line per case and the function name
        # de-duplicates them back into one distinct property.
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests", "-m", category,
             "--collect-only", "-p", "no:cacheprovider"],
            cwd=str(root), capture_output=True, text=True,
        )
        ids = [
            line.strip()
            for line in result.stdout.splitlines()
            if "::" in line and line.strip().startswith("tests/")
        ]
        cases[category] = len(ids)
        distinct[category] = len({node.split("[")[0] for node in ids})

    total = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "--collect-only",
         "-p", "no:cacheprovider"],
        cwd=str(root), capture_output=True, text=True,
    )
    all_ids = [
        line.strip()
        for line in total.stdout.splitlines()
        if "::" in line and line.strip().startswith("tests/")
    ]
    categorised = sum(cases.values())
    if categorised != len(all_ids):
        marked = set()
        for category in CATEGORIES:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "tests", "-m", category,
                 "--collect-only", "-p", "no:cacheprovider"],
                cwd=str(root), capture_output=True, text=True,
            )
            marked |= {
                line.strip()
                for line in result.stdout.splitlines()
                if "::" in line and line.strip().startswith("tests/")
            }
        uncategorised = sorted(set(all_ids) - marked)
    return {"distinct": distinct, "cases": cases}, {
        "total": len(all_ids),
        "uncategorised": uncategorised,
    }


@pytest.fixture(scope="module")
def ledger(pytestconfig):
    return _collect(pytestconfig)


def test_every_test_carries_exactly_one_property_category(ledger):
    """PL-1: no test escapes the ledger, so the ratio covers the whole suite."""

    counts, meta = ledger
    assert meta["uncategorised"] == [], meta["uncategorised"]
    assert sum(counts["cases"].values()) == meta["total"]


def test_the_adversarial_to_happy_distinct_property_ratio_is_at_least_two_to_one(ledger):
    """PL-2: the ratified requirement, counted as DISTINCT properties."""

    counts, _ = ledger
    adversarial = counts["distinct"]["adversarial"]
    happy = counts["distinct"]["happy"]
    assert happy > 0, "a suite with no positive control proves nothing"
    assert adversarial / happy >= REQUIRED_RATIO, (
        f"adversarial:happy distinct properties = {adversarial}:{happy} "
        f"= {adversarial / happy:.2f}:1, below the required {REQUIRED_RATIO}:1"
    )


def test_the_adversarial_to_happy_parametrised_case_ratio_is_at_least_two_to_one(ledger):
    """PL-3: and again over parametrised cases, reported separately."""

    counts, _ = ledger
    adversarial = counts["cases"]["adversarial"]
    happy = counts["cases"]["happy"]
    assert adversarial / happy >= REQUIRED_RATIO, (
        f"adversarial:happy cases = {adversarial}:{happy} = {adversarial / happy:.2f}:1"
    )


def test_the_ledger_is_reportable(ledger, capsys):
    """PL-4: print the ledger, so a CI log carries the numbers a reviewer needs."""

    counts, meta = ledger
    distinct, cases = counts["distinct"], counts["cases"]
    with capsys.disabled():
        print("\n  Phase 5B-0A property ledger")
        print(f"    distinct happy properties        {distinct['happy']}")
        print(f"    distinct adversarial properties  {distinct['adversarial']}")
        print(f"    distinct invariant properties    {distinct['invariant']}")
        print(f"    parametrised happy cases         {cases['happy']}")
        print(f"    parametrised adversarial cases   {cases['adversarial']}")
        print(f"    parametrised invariant cases     {cases['invariant']}")
        print(
            f"    distinct ratio                   "
            f"{distinct['adversarial'] / distinct['happy']:.2f}:1"
        )
        print(
            f"    case ratio                       "
            f"{cases['adversarial'] / cases['happy']:.2f}:1"
        )
        print(f"    total collected                  {meta['total']}")
    assert meta["total"] > 0


def test_the_invariant_bucket_is_not_counted_as_adversarial(ledger):
    """PL-5: the ratio cannot be inflated by reclassifying bookkeeping as an attack."""

    counts, _ = ledger
    assert counts["distinct"]["invariant"] > 0
    adversarial_including_invariants = (
        counts["distinct"]["adversarial"] + counts["distinct"]["invariant"]
    )
    assert adversarial_including_invariants > counts["distinct"]["adversarial"], (
        "the invariant bucket is empty, so the separation is not doing any work"
    )


# --------------------------------------------------------------------------------------- #
# The deselection the guard sweep applies must not shrink what the guard sweep scores
# --------------------------------------------------------------------------------------- #

#: The environment switch the sweep sets to deselect the expensive packaging properties.
DESELECTION_SWITCH = "UGENCE_SKIP_SLOW_PACKAGING"

#: Attributes of this package a deselected module may touch in-process. All metadata: a
#: mutated ``if`` in ``src/`` cannot change any of them, so reading one scores no guard.
METADATA_ONLY = frozenset({"__file__", "__version__", "__all__", "__name__", "__doc__"})


def _deselected_modules() -> list[pathlib.Path]:
    root = pathlib.Path(__file__).resolve().parents[1]
    return sorted(
        path
        for path in root.rglob("tests/**/test_*.py")
        if DESELECTION_SWITCH in path.read_text(encoding="utf-8")
    )


def test_nothing_behind_the_sweep_deselection_scores_a_guard_the_sweep_does_not_run():
    """PL-6: the condition that makes the guard sweep's deselection honest.

    The sweep runs the whole suite once per guard, and deselects
    ``tests/packaging/test_sdist_payload.py`` to avoid building a distribution ninety-one
    times. That module was documented as scoring nothing — "a mutated package builds into a
    distribution exactly as an unmutated one does" — and that justification is false. SD-6 …
    SD-9 build the sdist **from the package under test** and run the shipped suite against
    it, so a mutated guard fails there as surely as it fails in the sweep's own run.

    So the deselection is a **cost** decision, and it is sound for one reason only: what the
    extracted sdist runs, the sweep already runs directly. This property asserts both halves
    of that, mechanically:

    #. every ``test_*.py`` module the sdist ships is itself free of the deselection switch,
       so the sweep runs it un-deselected — nothing the sdist would catch is dropped;
    #. no deselected module reaches ``src/`` behaviour in-process. Its only permitted use of
       this package is metadata a mutation cannot move.

    Add a property behind the switch that calls the verifier, the minting routine or the
    revalidator directly and this fails — because that property really would be the sweep's
    blind spot, which the previous justification would have let pass unnoticed.
    """

    import ast

    root = pathlib.Path(__file__).resolve().parents[1]
    # Read the shipped-payload manifest out of its own source rather than importing the
    # module: importing a deselected module to check the deselection would be circular,
    # and this property must hold whether or not that module can be imported at all.
    payload_source = (root / "tests/packaging/test_sdist_payload.py").read_text(
        encoding="utf-8"
    )
    REQUIRED_SDIST_PAYLOAD = next(
        ast.literal_eval(node.value)
        for node in ast.walk(ast.parse(payload_source))
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "REQUIRED_SDIST_PAYLOAD"
            for target in node.targets
        )
    )

    deselected = _deselected_modules()
    assert deselected, (
        f"no module carries {DESELECTION_SWITCH}; if the sweep no longer deselects "
        "anything, delete this property rather than letting it pass vacuously"
    )

    # (1) Nothing the sdist ships is deselected.
    deselected_relative = {str(path.relative_to(root)) for path in deselected}
    shipped_tests = {
        name for name in REQUIRED_SDIST_PAYLOAD if name.rsplit("/", 1)[-1].startswith("test_")
    }
    assert shipped_tests, "the shipped payload lists no test modules"
    overlap = shipped_tests & deselected_relative
    assert not overlap, (
        f"{sorted(overlap)} are shipped in the sdist AND deselected by the sweep. SD-7 "
        "runs them against the mutated package, so deselecting them removes scoring the "
        "sweep does not recover elsewhere"
    )

    # (2) No deselected module exercises src/ behaviour in-process.
    for path in deselected:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        aliases = set()
        imported_names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("ugence_cloud_scaling_producer_attestation"):
                        aliases.add(alias.asname or alias.name)
            elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "ugence_cloud_scaling_producer_attestation"
            ):
                imported_names |= {alias.asname or alias.name for alias in node.names}

        offending = imported_names - METADATA_ONLY
        assert not offending, (
            f"{path.relative_to(root)} is deselected by {DESELECTION_SWITCH} and imports "
            f"{sorted(offending)} from the package. A property behind the switch that "
            "exercises src/ behaviour is scoring the sweep silently loses — either drop "
            "the deselection or move the property to a module the sweep runs"
        )
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id in aliases
                and node.attr not in METADATA_ONLY
            ):
                raise AssertionError(
                    f"{path.relative_to(root)}:{node.lineno} reads "
                    f"{node.value.id}.{node.attr} while deselected by "
                    f"{DESELECTION_SWITCH}; only {sorted(METADATA_ONLY)} are mutation-inert"
                )
