"""Deterministic fingerprint / manifest utilities for the unseen-identifier diagnostic.

Records ACTUAL digest values (not booleans). Reused frozen-recipe source hashes are computed from
the merged implementation so a future run can prove it used the exact recipe. No run is performed
here.
"""
from __future__ import annotations

import hashlib
import os
from typing import Any, Iterable

from experiments.single_hop_typed_vs_prose import config as _tvp_config

_TVP_DIR = os.path.dirname(_tvp_config.__file__)
# Recipe-bearing frozen sources reused by this diagnostic.
FROZEN_RECIPE_SOURCES = ("config.py", "tokenizer.py", "model.py", "trainer.py")

# Bumping this version invalidates prior manifests (they must be re-emitted, never silently reused).
RUN_MANIFEST_SCHEMA_VERSION: str = "unseen-id-run-manifest/1"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json(obj: Any) -> str:
    """Canonical JSON: sorted keys, ASCII, fixed separators. Deterministic across runs."""
    import json

    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_json(obj: Any) -> str:
    """SHA-256 over the canonical JSON serialization of `obj`."""
    return sha256_text(canonical_json(obj))


def frozen_recipe_source_hashes() -> dict[str, str]:
    out: dict[str, str] = {}
    for name in FROZEN_RECIPE_SOURCES:
        with open(os.path.join(_TVP_DIR, name), "rb") as fh:
            out[name] = sha256_bytes(fh.read())
    return out


def dataset_digest(serialized_examples: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for text in serialized_examples:
        digest.update(text.encode("ascii"))
        digest.update(b"\x00")
    return digest.hexdigest()


def example_hash_digest(example_hashes: Iterable[str]) -> str:
    return hashlib.sha256("".join(example_hashes).encode("ascii")).hexdigest()


# The exact digest fields a completed run manifest must carry (actual values, never booleans).
RUN_MANIFEST_DIGEST_FIELDS: tuple[str, ...] = (
    "source_digest",
    "config_digest",
    "tokenizer_digest",
    "authorization_record_digest",
    "identifier_pool_digest",
    "dataset_digest",
    "serializer_digest",
    "initialization_digest",
    "batch_order_digest",
    "checkpoint_parameter_digest",
    "prediction_digest",
    "evaluator_digest",
    "environment_digest",
)


def build_run_manifest(
    *,
    seed: int,
    cohort: str,
    source_commit: str,
    protocol_lock_commit: str,
    implementation_authorization_commit: str,
    implementation_commit: str,
    digests: dict[str, str],
    parser_category_counts: dict[str, dict[str, int]],
    per_task_metrics: dict[str, dict[str, float]],
    shortcut_results: dict,
    resource_measurements: dict[str, float],
    protocol_compliance: dict[str, bool],
    replay_comparison: dict | None = None,
) -> dict:
    """Assemble a canonical run manifest carrying ACTUAL digest values and provenance labels.

    Every required digest field must be present (a missing digest is an implementation defect, not a
    silently-omitted field). This is a pure assembler: it performs no I/O and no run."""
    missing = [name for name in RUN_MANIFEST_DIGEST_FIELDS if name not in digests]
    if missing:
        raise ValueError(f"run manifest is missing required digest fields: {missing}")
    manifest = {
        "schema_version": RUN_MANIFEST_SCHEMA_VERSION,
        "seed": int(seed),
        "cohort": cohort,
        "source_commit": source_commit,
        "protocol_lock_commit": protocol_lock_commit,
        "implementation_authorization_commit": implementation_authorization_commit,
        "implementation_commit": implementation_commit,
        "digests": {name: digests[name] for name in RUN_MANIFEST_DIGEST_FIELDS},
        "parser_category_counts": parser_category_counts,
        "per_task_metrics": per_task_metrics,
        "shortcut_results": shortcut_results,
        "resource_measurements": resource_measurements,
        "protocol_compliance": protocol_compliance,
        "replay_comparison": replay_comparison,
    }
    manifest["manifest_digest"] = digest_json(
        {k: v for k, v in manifest.items() if k != "manifest_digest"}
    )
    return manifest
