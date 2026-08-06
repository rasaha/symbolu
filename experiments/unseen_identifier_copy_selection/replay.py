"""Deterministic replay for the unseen-identifier diagnostic (Decision 6).

Replay = COMPLETE deterministic retraining and re-evaluation from the frozen recipe and one
explicitly-authorized seed, compared against the original run by ACTUAL DIGEST VALUES (never
booleans). Any digest mismatch FAILS CLOSED and blocks evidence acceptance. torch and the frozen
model are imported lazily via the training/evaluation modules. Replay is never executed during
implementation or fixture tests; its orchestration is exercised only through mocks.
"""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass

# Digest fields reconstructed and compared on replay (a subset of the run manifest that a
# deterministic retrain+re-eval reproduces exactly).
REPLAYED_DIGEST_FIELDS: tuple[str, ...] = (
    "dataset_digest",
    "serializer_digest",
    "identifier_pool_digest",
    "initialization_digest",
    "batch_order_digest",
    "checkpoint_parameter_digest",
    "prediction_digest",
)


class ReplayMismatch(RuntimeError):
    """Raised (fail-closed) when any replayed digest differs from the original run's digest."""


@dataclass(frozen=True)
class ReplayReport:
    seed: int
    cohort: str
    comparisons: dict[str, dict[str, str]]  # field -> {original, replay}
    matched: bool


def _reconstruct_digests(seed: int, cohort: str, token: str | None, work_dir: str) -> dict[str, str]:
    """Rebuild cohort → retrain → re-evaluate and collect the actual reproduced digest values."""
    from .identifiers import build_pools
    from .manifest import example_hash_digest
    from .runner import build_cohort
    from .training import train_cohort
    from .evaluation import evaluate_cohort

    cohort_by_split = build_cohort(int(seed), cohort, token=token)
    pools = build_pools(int(seed), token=token)
    identifier_pool_digest = example_hash_digest(
        pools["train"] + pools["final"] + pools["evidence"]
    )

    checkpoint_dir = os.path.join(work_dir, "checkpoint")
    train = train_cohort(int(seed), cohort, [e for split in sorted(cohort_by_split) for e in cohort_by_split[split]], checkpoint_dir)
    ev = evaluate_cohort(train.checkpoint_path, cohort_by_split)

    return {
        "dataset_digest": train.dataset_digest,
        "serializer_digest": train.serializer_digest,
        "identifier_pool_digest": identifier_pool_digest,
        "initialization_digest": train.initialization_digest,
        "batch_order_digest": train.batch_order_digest,
        "checkpoint_parameter_digest": train.checkpoint_parameter_digest,
        "prediction_digest": ev.prediction_digest,
    }


def replay_run(
    seed: int,
    cohort: str,
    original_digests: dict[str, str],
    *,
    token: str | None = None,
    reconstruct=None,
) -> ReplayReport:
    """Replay one authorized (seed, cohort) and compare ACTUAL digests to the original run.

    `reconstruct(seed, cohort, token, work_dir) -> dict[field, digest]` is injectable for fixture
    tests (so no real retrain occurs); by default a full deterministic retrain+re-eval is performed.
    Any missing or differing digest raises `ReplayMismatch` (fail-closed)."""
    reconstruct = reconstruct or _reconstruct_digests
    with tempfile.TemporaryDirectory(prefix="unseen-id-replay-") as work_dir:
        replayed = reconstruct(int(seed), cohort, token, work_dir)

    comparisons: dict[str, dict[str, str]] = {}
    matched = True
    for field_name in REPLAYED_DIGEST_FIELDS:
        original = original_digests.get(field_name)
        current = replayed.get(field_name)
        comparisons[field_name] = {"original": original, "replay": current}
        if original is None or current is None or original != current:
            matched = False

    if not matched:
        raise ReplayMismatch(
            "deterministic replay digest mismatch: "
            + ", ".join(
                f"{name}(orig={c['original']}, replay={c['replay']})"
                for name, c in comparisons.items()
                if c["original"] != c["replay"]
            )
        )
    return ReplayReport(seed=int(seed), cohort=cohort, comparisons=comparisons, matched=True)
