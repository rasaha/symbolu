"""Versioned ground-truth dataset container + deterministic hash (Task 102/103)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .scenario import Scenario


def _canonical(scenarios: list[dict]) -> str:
    # stable ordering by scenario_id; canonical JSON (sorted keys, no whitespace)
    ordered = sorted(scenarios, key=lambda s: s["scenario_id"])
    return json.dumps(ordered, sort_keys=True, separators=(",", ":"))


def dataset_hash(scenarios) -> str:
    dicts = [s.to_dict() if isinstance(s, Scenario) else s for s in scenarios]
    return hashlib.sha256(_canonical(dicts).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Dataset:
    version: str
    scenarios: tuple[Scenario, ...]

    @property
    def content_hash(self) -> str:
        return dataset_hash(self.scenarios)

    def by_id(self, scenario_id: str) -> Scenario:
        for s in self.scenarios:
            if s.scenario_id == scenario_id:
                return s
        raise KeyError(scenario_id)

    def by_domain(self, domain: str) -> tuple[Scenario, ...]:
        return tuple(s for s in self.scenarios if s.domain == domain)

    def ordered(self) -> tuple[Scenario, ...]:
        return tuple(sorted(self.scenarios, key=lambda s: s.scenario_id))

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "content_hash": self.content_hash,
            "scenario_count": len(self.scenarios),
            "scenarios": [s.to_dict() for s in self.ordered()],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)

    @staticmethod
    def from_dict(data: dict) -> "Dataset":
        scenarios = tuple(Scenario.from_dict(s) for s in data["scenarios"])
        ds = Dataset(version=data["version"], scenarios=scenarios)
        stored = data.get("content_hash")
        if stored is not None and stored != ds.content_hash:
            raise ValueError(
                f"dataset hash mismatch: stored {stored} != computed {ds.content_hash}")
        return ds

    @staticmethod
    def from_json(text: str) -> "Dataset":
        return Dataset.from_dict(json.loads(text))
