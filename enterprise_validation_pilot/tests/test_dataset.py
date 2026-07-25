"""Dataset schema, stability, and stored-file integrity."""
from __future__ import annotations

import pathlib

from enterprise_validation_pilot.datasets.build_dataset import DATASET_PATH, build
from enterprise_validation_pilot.schemas.dataset import Dataset
from enterprise_validation_pilot.schemas.scenario import (
    ACTION_CLASSES, ASSERTION_CLASSES, CROSS_CLASSES)
from enterprise_validation_pilot.schemas.taxonomy import DOMAINS


def test_dataset_has_90_scenarios_across_3_domains():
    ds = build()
    assert len(ds.scenarios) == 90
    for domain in DOMAINS:
        assert len(ds.by_domain(domain)) == 30


def test_dataset_covers_full_taxonomy():
    ds = build()
    assert {s.assertion_class for s in ds.scenarios} == set(ASSERTION_CLASSES)
    assert {s.action_class for s in ds.scenarios} == set(ACTION_CLASSES)
    assert {s.cross_class for s in ds.scenarios} == set(CROSS_CLASSES)


def test_dataset_hash_is_deterministic():
    assert build().content_hash == build().content_hash


def test_dataset_roundtrips_through_json():
    ds = build()
    ds2 = Dataset.from_json(ds.to_json())
    assert ds2.content_hash == ds.content_hash
    assert len(ds2.scenarios) == len(ds.scenarios)


def test_stored_dataset_file_matches_authoring():
    stored = Dataset.from_json(pathlib.Path(DATASET_PATH).read_text())
    assert stored.content_hash == build().content_hash, (
        "committed dataset is stale; re-run build_dataset")


def test_scenario_ids_are_unique_and_stable():
    ids = [s.scenario_id for s in build().scenarios]
    assert len(ids) == len(set(ids))
    assert ids == sorted(ids) or sorted(ids) == sorted(set(ids))
