"""Frozen Phase 5I dataset reuse + identity verification (Task 4).

The benchmark reuses the exact ``enterprise_pilot_v1`` dataset through the pilot's
public API — it never regenerates scenarios or modifies expected labels. The
scenario type IS the pilot's frozen ``Scenario``; the benchmark treats its
``expected`` region as ground truth handled only by the evaluation oracle.
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass

from enterprise_validation_pilot.schemas.dataset import Dataset
from enterprise_validation_pilot.schemas.scenario import (
    ACTION_CLASSES, ASSERTION_CLASSES, CROSS_CLASSES, Scenario)
from enterprise_validation_pilot.schemas.taxonomy import DOMAINS

from ..version import DATASET_HASH_PREFIX, DATASET_VERSION

EnterpriseScenario = Scenario

_DATASET_PATH = (pathlib.Path(enterprise_pilot_dir := __import__(
    "enterprise_validation_pilot").__file__).parent / "datasets" / "enterprise_pilot_v1.json")


@dataclass(frozen=True)
class DatasetIdentity:
    version: str
    content_hash: str
    scenario_count: int
    domain_count: int
    assertion_classes: int
    action_classes: int
    cross_classes: int
    expected_present: bool
    stable_ordering: bool

    @property
    def ok(self) -> bool:
        return (self.version == DATASET_VERSION
                and self.content_hash.startswith(DATASET_HASH_PREFIX)
                and self.scenario_count == 90 and self.domain_count == 3
                and self.assertion_classes == len(ASSERTION_CLASSES)
                and self.action_classes == len(ACTION_CLASSES)
                and self.cross_classes == len(CROSS_CLASSES)
                and self.expected_present and self.stable_ordering)


def load_frozen_dataset() -> Dataset:
    return Dataset.from_json(_DATASET_PATH.read_text())


def verify_identity(dataset: Dataset) -> DatasetIdentity:
    scenarios = dataset.scenarios
    ids = [s.scenario_id for s in dataset.ordered()]
    return DatasetIdentity(
        version=dataset.version, content_hash=dataset.content_hash,
        scenario_count=len(scenarios),
        domain_count=len({s.domain for s in scenarios}),
        assertion_classes=len({s.assertion_class for s in scenarios}),
        action_classes=len({s.action_class for s in scenarios}),
        cross_classes=len({s.cross_class for s in scenarios}),
        expected_present=all(s.expected is not None for s in scenarios),
        stable_ordering=(ids == sorted(ids)))


DOMAIN_NAMES = DOMAINS
