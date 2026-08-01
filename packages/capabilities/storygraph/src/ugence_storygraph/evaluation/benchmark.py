"""Synthetic operational-load benchmark (§8).

Measures runtime/throughput/memory over generated corpora at multiple scales.
Timing uses the wall clock **outside** the analyzer (the analyzer core never reads
the clock); results are environment-dependent and labeled
``Measured — synthetic operational load``. No production capacity number is
extrapolated from one machine.
"""

from __future__ import annotations

import platform
import sys
import time
import tracemalloc

from ugence_storygraph import (
    BY_ACTOR, BY_CASE, DIGITAL_ONTOLOGY, FixtureProvider, ProviderRegistry,
    SequenceRiskAnalyzer, signals,
)

from . import corpus_gen


def environment() -> dict:
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "processor": platform.processor() or "unknown",
        "note": "single development host; NOT a production capacity measurement",
    }


def _percentile(sorted_vals, p):
    if not sorted_vals:
        return None
    k = max(0, min(len(sorted_vals) - 1, int(round((p / 100) * (len(sorted_vals) - 1)))))
    return sorted_vals[k]


def run_load(profile: str = "enterprise_like", scale: int = 200, seed: int = 7) -> dict:
    scenarios = corpus_gen.generate(profile, scale, seed)
    # flatten to one event stream, tagging providers per scenario via separate analyzers
    per_event_ms: list[float] = []
    total_events = 0
    escalations = 0
    unavailable = 0
    peak_assemblies = 0
    tracemalloc.start()
    t0 = time.perf_counter()
    for sc in scenarios:
        providers = None
        if sc["providers"]:
            providers = ProviderRegistry(providers=(
                FixtureProvider("bench-fx", "1.0.0", sc["providers"]),))
        specs = (BY_ACTOR,) if sc["family"] == "cross_session" else (BY_CASE,)
        az = SequenceRiskAnalyzer(DIGITAL_ONTOLOGY, specs=specs, providers=providers)
        for ev in sc["events"]:
            s = time.perf_counter()
            findings = az.observe(ev)
            per_event_ms.append((time.perf_counter() - s) * 1000.0)
            total_events += 1
            for f in findings:
                if f.signal == signals.ESCALATE:
                    escalations += 1
                elif f.signal == signals.UNAVAILABLE:
                    unavailable += 1
        for t in az.ledger._by_tenant:
            peak_assemblies = max(peak_assemblies, az.ledger.assembly_count(t))
    wall = time.perf_counter() - t0
    _cur, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    per_event_ms.sort()
    return {
        "evidence_label": "Measured — synthetic operational load",
        "environment": environment(),
        "profile": profile, "scale_scenarios": scale, "seed": seed,
        "total_events": total_events,
        "wall_seconds": round(wall, 4),
        "events_per_second": round(total_events / wall, 1) if wall else None,
        "runtime_ms_per_event": {
            "median": round(_percentile(per_event_ms, 50), 4),
            "p95": round(_percentile(per_event_ms, 95), 4),
            "p99": round(_percentile(per_event_ms, 99), 4),
        },
        "peak_traced_memory_mb": round(peak_mem / (1024 * 1024), 2),
        "peak_assemblies_per_tenant": peak_assemblies,
        "escalations": escalations,
        "unavailable": unavailable,
    }


def run_scales(seed: int = 7) -> dict:
    return {
        "small_correctness": run_load("balanced", 25, seed),
        "medium_operational": run_load("enterprise_like", 200, seed),
        "large_stress": run_load("stress", 400, seed),
    }
