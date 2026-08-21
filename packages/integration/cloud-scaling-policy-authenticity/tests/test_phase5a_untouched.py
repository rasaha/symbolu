"""D-5B0B-6: the proof travels alongside the candidate, and Phase 5A does not move.

The measurement that decided it: widening ``PolicyTargetBindingReference`` in place with the
three missing coordinate components moves **two** pinned digests —
``FROZEN_POLICY_BINDING_DIGEST`` and ``FROZEN_CANDIDATE_DIGEST`` — because
``digest_payload()`` embeds the binding's canonical dictionary whole. Carrying the proof
alongside moves **none**.

So this suite re-runs Phase 5A's own frozen-digest tests rather than asserting the choice in
prose. If this package ever grows a change that moves one, the failure surfaces here, in the
package that would have caused it.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys

import pytest

from _policy_fixtures import _find_repo_root

REPO = _find_repo_root()
pytestmark = pytest.mark.skipif(
    REPO is None, reason="no source checkout; Phase 5A's test tree is unavailable"
)


def _phase5a() -> pathlib.Path:
    return REPO / "packages" / "integration" / "cloud-scaling-authorization-contracts"


@pytest.mark.invariant
def test_phase_5a_stays_at_0_1_0():
    version = (_phase5a() / "src" / "ugence_cloud_scaling_authorization_contracts" / "version.py").read_text()
    assert '__version__ = "0.1.0"' in version


@pytest.mark.invariant
def test_the_policy_authority_stays_at_0_1_0():
    init = (REPO / "packages" / "policy-authority" / "src" / "ugence_policy_authority" / "__init__.py").read_text()
    assert '__version__ = "0.1.0"' in init


@pytest.mark.invariant
def test_this_package_ships_at_0_1_0_and_adds_a_distribution_rather_than_changing_one():
    from ugence_cloud_scaling_policy_authenticity import __version__

    assert __version__ == "0.1.0"


@pytest.mark.invariant
def test_phase_5a_still_pins_exactly_ten_frozen_digests():
    source = (_phase5a() / "tests" / "test_frozen_digests.py").read_text()
    frozen = re.findall(r"^FROZEN_[A-Z0-9_]+ = ", source, flags=re.MULTILINE)
    assert len(frozen) == 10


@pytest.mark.invariant
def test_all_ten_frozen_digests_still_hold():
    """Runs Phase 5A's own suite, in its own tree, as a subprocess. No mocking, no stubbing."""

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_frozen_digests.py",
            "-p",
            "no:cacheprovider",
            "-q",
        ],
        cwd=str(_phase5a()),
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


@pytest.mark.adversarial
def test_this_package_changes_no_phase_5a_or_policy_authority_file():
    """A leaf package adds a directory. It does not reach into its dependencies' trees."""

    here = pathlib.Path(__file__).resolve().parents[1]
    assert here.name == "cloud-scaling-policy-authenticity"
    # Nothing this distribution ships lives outside its own directory.
    shipped = list((here / "src").rglob("*.py")) + list((here / "tests").rglob("*.py"))
    for path in shipped:
        assert here in path.parents
