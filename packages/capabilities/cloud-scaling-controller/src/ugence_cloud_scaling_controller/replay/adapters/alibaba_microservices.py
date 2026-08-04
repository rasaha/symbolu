"""Alibaba cluster-trace-microservices adapter (PENDING_DATA).

Implemented and unit-tested against a schema fixture, but NOT executed on the
full trace here: the Alibaba microservices data (v2021/v2022) is distributed via
Alibaba cloud storage (10s-100s of GB) behind a host this environment's egress
policy blocks. Any number from this adapter must be labelled real ONLY when run
against the genuine download.

Primary signal used: per-microservice CPU utilisation over time (MSResource),
bucketed to cycles and averaged → demand. The call-graph latency tables
(MSCallGraph, with `rt` response times) are the natural source for the
cascading/conflicting-signal scenarios; this adapter focuses on the resource
series, which maps cleanly to the controller's demand contract.

Expected MSResource schema (column names are matched case-insensitively;
positions tolerated):
    timestamp, msname, msinstanceid, nodeid, cpu_utilization, memory_utilization

How to obtain: github.com/alibaba/clusterdata →
cluster-trace-microservices-v2021. Place CSVs under
data/cloud_traces/alibaba/ and pass the MSResource file path.
License: per Alibaba clusterdata repository terms.
"""

from __future__ import annotations

import csv
from typing import Dict, List, Optional

from ugence_cloud_scaling_controller.replay.adapters.base import (
    AdapterStatus,
    TraceAdapter,
    TraceSeries,
)


class AlibabaMicroservicesAdapter(TraceAdapter):
    NAME = "alibaba_microservices"
    CITATION = (
        "Alibaba cluster-trace-microservices-v2021, "
        "github.com/alibaba/clusterdata"
    )
    LICENSE = "Alibaba clusterdata repository terms"
    SCHEMA = "timestamp,msname,msinstanceid,nodeid,cpu_utilization,memory_utilization"
    STATUS = AdapterStatus.PENDING_DATA

    def load(
        self,
        path: str,
        cycle_seconds: float = 15.0,
        ts_col: str = "timestamp",
        cpu_col: str = "cpu_utilization",
        max_rows: Optional[int] = None,
        name: Optional[str] = None,
    ) -> TraceSeries:
        # Alibaba timestamps are integer ms-since-trace-start in many tables; we
        # treat the column as a monotonically increasing time unit and bucket by
        # cycle. Bucketing is unit-agnostic as long as ts is in seconds; pass a
        # pre-scaled column or adjust cycle_seconds accordingly.
        buckets: Dict[int, List[float]] = {}
        n = 0
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            fields = {k.lower(): k for k in (reader.fieldnames or [])}
            tk = fields.get(ts_col.lower(), ts_col)
            ck = fields.get(cpu_col.lower(), cpu_col)
            for i, row in enumerate(reader):
                if max_rows is not None and i >= max_rows:
                    break
                try:
                    t = float(row[tk])
                    cpu = float(row[ck])
                except (KeyError, ValueError, TypeError):
                    continue
                b = int(t // cycle_seconds)
                buckets.setdefault(b, []).append(cpu)
                n += 1

        if not buckets:
            raise ValueError(f"No parseable rows in {path}")

        b0, b1 = min(buckets), max(buckets)
        # Average CPU utilisation per cycle → demand. Utilisation is already a
        # fraction/percentage; normalise to [0,1] by the series max.
        per_cycle = []
        for b in range(b0, b1 + 1):
            vals = buckets.get(b)
            per_cycle.append(sum(vals) / len(vals) if vals else 0.0)
        m = max(per_cycle) or 1.0
        demand = [v / m for v in per_cycle]

        return TraceSeries(
            name=name or self.NAME,
            source=self.CITATION,
            license=self.LICENSE,
            status=self.STATUS,
            cycle_seconds=cycle_seconds,
            demand=demand,
            meta={
                "n_rows": n,
                "transfer_function": "benchmark._demand_to_metrics (shared with synthetic suite)",
                "real_variable": "per-microservice CPU utilisation distribution",
                "note": "PENDING_DATA — schema fixture only; not run on full Alibaba trace here",
            },
        )
