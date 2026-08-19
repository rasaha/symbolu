"""pytest fixtures and the property-category ledger for the Phase 5B-0A suite.

The builders themselves live in :mod:`_producer_fixtures`, under a name that cannot
collide with any neighbouring package's ``conftest`` on ``sys.path`` — the Phase 5A test
tree is importable here on purpose, and two modules called ``conftest`` would shadow one
another silently.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from _producer_fixtures import (
    AS_OF,
    ProducerAttestationVerifier,
    StaticTrustAnchorDirectory,
    TrustAnchorRecord,
    build_anchor,
    build_attestation,
    build_candidate,
    build_directory,
    build_verifier,
)
from _producer_fixtures import ProducerAttestationV2


@pytest.fixture
def candidate():
    return build_candidate()


@pytest.fixture
def anchor() -> TrustAnchorRecord:
    return build_anchor()


@pytest.fixture
def directory(anchor) -> StaticTrustAnchorDirectory:
    return build_directory(anchor)


@pytest.fixture
def verifier(directory) -> ProducerAttestationVerifier:
    return build_verifier(directory=directory)


@pytest.fixture
def attestation(candidate) -> ProducerAttestationV2:
    return build_attestation(candidate)


@pytest.fixture
def as_of() -> datetime:
    return AS_OF


# --------------------------------------------------------------------------------------- #
# Property categories — one auditable table, and the override always wins
# --------------------------------------------------------------------------------------- #

#: The three categories. See ``tests/test_property_ledger.py`` for what each means and why
#: ``invariant`` is excluded from the adversarial-to-happy ratio.
PROPERTY_CATEGORIES = frozenset({"happy", "adversarial", "invariant"})

#: Each module's DEFAULT category. A test that departs from its module's default carries its
#: own ``@pytest.mark.<category>``, and that marker wins — the default is only applied to
#: tests that declare nothing, so no test is ever counted twice.
MODULE_PROPERTY_CATEGORY = {
    "test_happy_path": "happy",
    "test_adversarial": "adversarial",
    "test_authenticity_laundering": "adversarial",
    "test_no_placeholder_verifier": "adversarial",
    "test_import_boundary": "adversarial",
    "test_time_authority": "adversarial",
    "test_typed_outcomes": "adversarial",
    "test_signer_boundary": "adversarial",
    "test_trust_reuse": "adversarial",
    "test_verified_artifact": "adversarial",
    "test_frozen_digests": "invariant",
    "test_phase5a_invariants": "invariant",
    "test_packaging": "invariant",
    "test_property_ledger": "invariant",
    "test_gate_isolation": "adversarial",
}


def pytest_collection_modifyitems(config, items):
    """Resolve exactly one property category per collected test.

    An explicit marker on the test wins outright; otherwise the module default applies. A
    module missing from the table fails the run rather than being silently uncounted — an
    uncategorised test would quietly shrink whichever side of the ratio it belonged on.
    """

    for item in items:
        own = {marker.name for marker in item.own_markers} & PROPERTY_CATEGORIES
        if len(own) > 1:
            raise pytest.UsageError(
                f"{item.nodeid} declares more than one property category: {sorted(own)}"
            )
        if own:
            continue
        module = item.module.__name__.rsplit(".", 1)[-1]
        category = MODULE_PROPERTY_CATEGORY.get(module)
        if category is None:
            raise pytest.UsageError(
                f"{item.nodeid}: module {module!r} has no property category. Add it to "
                "MODULE_PROPERTY_CATEGORY in tests/conftest.py."
            )
        item.add_marker(getattr(pytest.mark, category))
