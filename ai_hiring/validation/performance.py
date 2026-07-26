"""Performance characterization (H5) — local, descriptive only (no scale claims)."""
from __future__ import annotations

import statistics
import time

from .composition import build_validation_env
from .lifecycle import CaseSpec, run_lifecycle


def time_case(repeats: int = 5) -> dict:
    """Median/tail wall-clock for a full lifecycle case (local, single process)."""
    samples = []
    for i in range(repeats):
        env = build_validation_env()
        t0 = time.perf_counter()
        run_lifecycle(env, CaseSpec(case_id=f"perf{i}"))
        samples.append(time.perf_counter() - t0)
    samples.sort()
    return {
        "repeats": repeats,
        "median_s": round(statistics.median(samples), 6),
        "p95_s": round(samples[min(len(samples) - 1, int(0.95 * len(samples)))], 6),
        "max_s": round(max(samples), 6),
        "stdev_s": round(statistics.pstdev(samples), 6),
        "note": "local single-process validation timing; NOT a production-scale claim",
    }


def batch_audit_growth(n: int = 12) -> dict:
    """Audit-record growth over a bounded batch (descriptive)."""
    from .pilot import run_pilot, build_cohort
    env = build_validation_env()
    from .lifecycle import run_lifecycle as _run
    specs = build_cohort()[:n]
    for s in specs:
        _run(env, s)
    return {"cases": len(specs), "hiring_audit_events": len(env.audit_repo.all_events()),
            "kernel_audit_events": len(env.kernel_audit_repo.all())}
