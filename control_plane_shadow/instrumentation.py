"""Latency + complexity instrumentation (Phase 15). Measures per-stage DETERMINISTIC-LOCAL
timings and complexity proxies (component calls, records, serialization bytes). All timings are
labeled `deterministic_local` — they are NOT production latency and must never be reported as
such. Human-wait and live-provider time are out of scope (never incurred here).

Timing uses time.perf_counter (monotonic; allowed — not Date.now/random). Because runs are
deterministic, timings are for relative stage comparison only.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List

from control_plane_shadow.orchestrator import ShadowOrchestrator
from control_plane_shadow.traces.v1.dataset import Trace, all_traces


@dataclass
class StageTiming:
    label: str = "deterministic_local"
    per_trace_ms: List[float] = field(default_factory=list)

    def p(self, q: float) -> float:
        if not self.per_trace_ms:
            return 0.0
        s = sorted(self.per_trace_ms)
        i = min(len(s) - 1, int(q * (len(s) - 1)))
        return round(s[i], 4)


def measure(traces: List[Trace] = None) -> Dict:
    traces = traces or all_traces()
    o = ShadowOrchestrator()
    total = StageTiming()
    calls: List[int] = []
    records: List[int] = []
    ser_bytes: List[int] = []
    for tr in traces:
        t0 = time.perf_counter()
        r = o.run(tr)
        dt = (time.perf_counter() - t0) * 1000.0
        total.per_trace_ms.append(dt)
        calls.append(r.component_calls)
        records.append(r.records)
        ser_bytes.append(len(json.dumps(r.reason_codes) + json.dumps(r.information_loss)))
    return {
        "label": "deterministic_local (NOT production latency)",
        "traces": len(traces),
        "total_ms_p50": total.p(0.5),
        "total_ms_p95": total.p(0.95),
        "component_calls_avg": round(sum(calls) / len(calls), 2),
        "component_calls_max": max(calls),
        "records_avg": round(sum(records) / len(records), 2),
        "serialization_bytes_avg": round(sum(ser_bytes) / len(ser_bytes), 1),
        "note": "human-wait and live-provider time excluded (never incurred); timings are for "
                "relative stage comparison only",
    }


if __name__ == "__main__":
    print(json.dumps(measure(), indent=2))
