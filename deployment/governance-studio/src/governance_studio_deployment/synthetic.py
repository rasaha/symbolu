"""Synthetic-data-only enforcement (P3E §8).

The deployment fails closed unless the packaged scenario fixtures match a pinned,
hashed manifest and carry the ``SYNTHETIC_DEMONSTRATION_ONLY`` classification. No
filesystem path, URL, upload, or environment variable may add or redirect scenarios.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Dict, List

from . import API_CONTRACT, DATA_CLASSIFICATION

MANIFEST_SCHEMA_VERSION = "1"


class SyntheticDataBoundaryError(Exception):
    """Raised when the synthetic-data boundary is violated (fail closed)."""

    code = "SYNTHETIC_DATA_BOUNDARY_FAILED"


def _iter_files(root: str) -> List[str]:
    out: List[str] = []
    for dirpath, _dirs, files in os.walk(root):
        for name in sorted(files):
            if name.endswith(".pyc") or "__pycache__" in dirpath:
                continue
            out.append(os.path.join(dirpath, name))
    return sorted(out)


def hash_scenario(scenario_dir: str) -> str:
    """Deterministic sha256 over a scenario directory's files (path + bytes)."""
    h = hashlib.sha256()
    base = os.path.abspath(scenario_dir)
    for path in _iter_files(base):
        rel = os.path.relpath(path, base).replace(os.sep, "/")
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        with open(path, "rb") as fh:
            h.update(fh.read())
        h.update(b"\0")
    return "sha256:" + h.hexdigest()


def bundle_hash(fixture_hashes: Dict[str, str]) -> str:
    """Aggregate hash over the per-scenario hashes (order-independent)."""
    h = hashlib.sha256()
    for scenario_id in sorted(fixture_hashes):
        h.update(scenario_id.encode("utf-8"))
        h.update(b"=")
        h.update(fixture_hashes[scenario_id].encode("utf-8"))
        h.update(b"\n")
    return "sha256:" + h.hexdigest()


@dataclass(frozen=True)
class SyntheticManifest:
    schema_version: str
    data_classification: str
    scenario_ids: List[str]
    fixture_hashes: Dict[str, str]
    bundle_hash: str
    source_contract: str

    @classmethod
    def load(cls, path: str) -> "SyntheticManifest":
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        return cls(
            schema_version=str(raw.get("schema_version", "")),
            data_classification=str(raw.get("data_classification", "")),
            scenario_ids=list(raw.get("scenario_ids", [])),
            fixture_hashes=dict(raw.get("fixture_hashes", {})),
            bundle_hash=str(raw.get("bundle_hash", "")),
            source_contract=str(raw.get("source_contract", "")),
        )


def build_manifest(scenarios_root: str, scenario_ids: List[str]) -> dict:
    """Compute a fresh manifest object from the packaged fixtures."""
    fixture_hashes = {sid: hash_scenario(os.path.join(scenarios_root, sid)) for sid in sorted(scenario_ids)}
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "data_classification": DATA_CLASSIFICATION,
        "scenario_ids": sorted(scenario_ids),
        "fixture_hashes": fixture_hashes,
        "bundle_hash": bundle_hash(fixture_hashes),
        "source_contract": API_CONTRACT,
    }


def verify_bundle(manifest: SyntheticManifest, scenarios_root: str) -> List[str]:
    """Return a list of violation strings; empty means the boundary holds."""
    violations: List[str] = []

    if manifest.schema_version != MANIFEST_SCHEMA_VERSION:
        violations.append(f"manifest schema_version {manifest.schema_version!r} != {MANIFEST_SCHEMA_VERSION!r}")
    if manifest.data_classification != DATA_CLASSIFICATION:
        violations.append(f"data_classification must be {DATA_CLASSIFICATION}")
    if manifest.source_contract != API_CONTRACT:
        violations.append(f"source_contract {manifest.source_contract!r} != {API_CONTRACT!r}")

    manifest_ids = set(manifest.scenario_ids)
    present_ids = {
        name for name in os.listdir(scenarios_root)
        if os.path.isdir(os.path.join(scenarios_root, name)) and not name.startswith("__")
    }
    # every manifest scenario exists in the package
    for sid in manifest_ids - present_ids:
        violations.append(f"manifest scenario missing from package: {sid}")
    # every packaged scenario appears in the manifest (no extra loadable scenario)
    for sid in present_ids - manifest_ids:
        violations.append(f"packaged scenario not in manifest (extra scenario): {sid}")

    # per-scenario fixture hashes match
    for sid in sorted(manifest_ids & present_ids):
        declared = manifest.fixture_hashes.get(sid)
        actual = hash_scenario(os.path.join(scenarios_root, sid))
        if declared != actual:
            violations.append(f"fixture hash mismatch for {sid}")

    # aggregate bundle hash matches
    recomputed = bundle_hash({sid: hash_scenario(os.path.join(scenarios_root, sid)) for sid in sorted(present_ids)})
    if recomputed != manifest.bundle_hash:
        violations.append("aggregate bundle hash mismatch")

    return violations


def enforce(manifest_path: str, scenarios_root: str) -> SyntheticManifest:
    """Load and verify; raise SyntheticDataBoundaryError on any violation."""
    manifest = SyntheticManifest.load(manifest_path)
    violations = verify_bundle(manifest, scenarios_root)
    if violations:
        raise SyntheticDataBoundaryError("; ".join(violations))
    return manifest
