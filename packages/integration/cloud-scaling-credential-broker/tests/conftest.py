"""pytest fixtures and the property-category ledger for the Phase 5X suite."""

from __future__ import annotations

import pytest

from _broker_fixtures import World, build_broker_world


@pytest.fixture
def world() -> World:
    return build_broker_world()


PROPERTY_CATEGORIES = frozenset({"happy", "adversarial", "invariant"})

MODULE_PROPERTY_CATEGORY = {
    "test_happy_path": "happy",
    "test_adversarial": "adversarial",
    "test_production_posture": "adversarial",
    "test_no_secret_material": "adversarial",
    "test_time_authority": "adversarial",
    "test_import_boundary": "adversarial",
    "test_typed_outcomes": "adversarial",
    "test_packaging": "invariant",
    "test_property_ledger": "invariant",
}


def pytest_collection_modifyitems(config, items):
    for item in items:
        own = {marker.name for marker in item.own_markers} & PROPERTY_CATEGORIES
        if len(own) > 1:
            raise pytest.UsageError(f"{item.nodeid} declares more than one property category: {sorted(own)}")
        if own:
            continue
        module = item.module.__name__.rsplit(".", 1)[-1]
        category = MODULE_PROPERTY_CATEGORY.get(module)
        if category is None:
            raise pytest.UsageError(
                f"{item.nodeid}: module {module!r} has no property category. Add it to "
                "MODULE_PROPERTY_CATEGORY in tests/conftest.py.")
        item.add_marker(getattr(pytest.mark, category))
