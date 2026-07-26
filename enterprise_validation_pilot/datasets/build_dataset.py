"""Deterministic dataset builder — writes the versioned ground-truth JSON.

Run:  python -m enterprise_validation_pilot.datasets.build_dataset

Regenerates ``enterprise_pilot_v1.json`` from the provider-free authoring module.
The generated file is checked in; this script only needs re-running when the
authoring changes (which changes the dataset version/hash intentionally).
"""
from __future__ import annotations

import pathlib

from ..schemas.dataset import Dataset
from ..scenarios import build_dataset_scenarios
from ..version import DATASET_VERSION

DATASET_PATH = pathlib.Path(__file__).resolve().parent / "enterprise_pilot_v1.json"


def build() -> Dataset:
    return Dataset(version=DATASET_VERSION, scenarios=tuple(build_dataset_scenarios()))


def write(path: pathlib.Path = DATASET_PATH) -> str:
    ds = build()
    path.write_text(ds.to_json() + "\n")
    return ds.content_hash


if __name__ == "__main__":
    h = write()
    print(f"wrote {DATASET_PATH.name} ({DATASET_VERSION}) hash={h}")
