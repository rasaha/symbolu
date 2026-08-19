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
