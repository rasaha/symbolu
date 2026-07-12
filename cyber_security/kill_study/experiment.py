"""Experiment orchestrator: (family x grid cell x seed x arm) -> raw records.

Deterministic. Generates each event once and runs all nine arms on the
identical trajectory (paired design). Writes a machine-readable manifest and
a per-event JSONL. No clock, no global RNG, no network.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Dict, Iterator, List, Tuple

from .config import (
    ALL_FAMILIES,
    DEV_GRID,
    DEV_SEED_BASE,
    EVAL_GRID,
    EVAL_SEED_BASE,
    StudyConfig,
)
from .calibration import fit_calibration
from .detectors import ARM_ORDER, score
from .metrics import event_record
from .trajectories import generate

RESULTS_DIR = Path(__file__).parent / "results"


def _cells(grid: Dict[str, List[float]]) -> List[Tuple[float, float, float, float]]:
    keys = ("sigma", "separation", "ramp_duration", "missing_rate")
    return list(itertools.product(*(grid[k] for k in keys)))


def _seed_for(family_idx: int, cell_idx: int, seed_idx: int, base: int) -> int:
    return base + family_idx * 100_000 + cell_idx * 1_000 + seed_idx


def iter_events(
    cfg: StudyConfig, split: str
) -> Iterator[Tuple[str, tuple, int, int]]:
    grid = DEV_GRID if split == "dev" else EVAL_GRID
    base = DEV_SEED_BASE if split == "dev" else EVAL_SEED_BASE
    n_seeds = cfg.dev_seeds_per_cell if split == "dev" else cfg.eval_seeds_per_cell
    cells = _cells(grid)
    for family_idx, family in enumerate(ALL_FAMILIES):
        for cell_idx, cell in enumerate(cells):
            for seed_idx in range(n_seeds):
                seed = _seed_for(family_idx, cell_idx, seed_idx, base)
                yield family, cell, seed_idx, seed


def run(cfg: StudyConfig, results_dir: Path = RESULTS_DIR) -> dict:
    results_dir.mkdir(parents=True, exist_ok=True)
    events_path = results_dir / "events.jsonl"
    manifest_path = results_dir / "manifest.json"

    counts: Dict[str, int] = {"dev": 0, "eval": 0}
    family_counts: Dict[str, int] = {}

    # Calibrate each arm's score on the DEV-legit null before scoring anything.
    calibration = fit_calibration(cfg)

    with events_path.open("w") as fh:
        for split in ("dev", "eval"):
            for family, cell, seed_idx, seed in iter_events(cfg, split):
                sigma, separation, ramp_duration, missing_rate = cell
                event = generate(
                    family,
                    seed=seed,
                    cfg=cfg,
                    sigma=sigma,
                    separation=separation,
                    ramp_duration=ramp_duration,
                    missing_rate=missing_rate,
                )
                for arm_key in ARM_ORDER:
                    arm_out = score(arm_key, event, cfg, calibration)
                    rec = event_record(arm_key, arm_out, event, cfg, split)
                    rec["seed"] = seed
                    rec["seed_idx"] = seed_idx
                    fh.write(json.dumps(rec) + "\n")
                counts[split] += 1
                if split == "eval":
                    family_counts[family] = family_counts.get(family, 0) + 1

    manifest = {
        "study": "bcvf_bio_adversarial_synthetic_kill_study",
        "scope": "synthetic_falsification_only",
        "config": cfg.to_dict(),
        "arms": list(ARM_ORDER),
        "families": list(ALL_FAMILIES),
        "event_counts": counts,
        "eval_events_per_family": family_counts,
        "records_written": counts["dev"] * len(ARM_ORDER)
        + counts["eval"] * len(ARM_ORDER),
        "events_file": events_path.name,
        "calibration": calibration.to_dict(),
        "deterministic": True,
    }
    with manifest_path.open("w") as fh:
        json.dump(manifest, fh, indent=2)
    return manifest
