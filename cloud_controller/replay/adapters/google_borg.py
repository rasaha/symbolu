"""Google Borg cluster-data adapter (PENDING_DATA).

Implemented and unit-tested against a schema fixture, but NOT executed on the
full trace here: the Borg traces (2011 `clusterdata-2011-2`, 2019) are hosted on
Google Cloud Storage (accessed via gsutil; the 2019 set is multi-TB and queried
through BigQuery) behind hosts this environment's egress policy blocks. Any
number from this adapter must be labelled real ONLY when run against the genuine
download.

Primary signal used: the 2011 `task_usage` table's mean CPU usage rate per
measurement window, summed across tasks per cycle → demand. The 2011 task_usage
CSVs have **no header**; the relevant columns (0-indexed) are:
    0 start_time, 1 end_time, 2 job_id, 3 task_index, 4 machine_id,
    5 mean_cpu_usage_rate, 6 canonical_memory_usage, ...

How to obtain: github.com/google/cluster-data → ClusterData2011_2;
`gsutil cp gs://clusterdata-2011-2/task_usage/part-*.csv.gz` . Place CSVs under
data/cloud_traces/google/ and pass a task_usage file path.
License: per Google cluster-data repository terms.
"""

from __future__ import annotations

import csv
from typing import Dict, List, Optional

from cloud_controller.replay.adapters.base import (
    AdapterStatus,
    TraceAdapter,
    TraceSeries,
)


class GoogleBorgAdapter(TraceAdapter):
    NAME = "google_borg"
    CITATION = "Google cluster-data (Borg) 2011/2019, github.com/google/cluster-data"
    LICENSE = "Google cluster-data repository terms"
    SCHEMA = "task_usage (headerless): col5=mean_cpu_usage_rate, col0=start_time(us)"
    STATUS = AdapterStatus.PENDING_DATA

    def load(
        self,
        path: str,
        cycle_seconds: float = 15.0,
        time_col: int = 0,
        cpu_col: int = 5,
        time_unit_seconds: float = 1e-6,   # 2011 timestamps are microseconds
        has_header: bool = False,
        max_rows: Optional[int] = None,
        name: Optional[str] = None,
    ) -> TraceSeries:
        buckets: Dict[int, float] = {}
        t_min: Optional[float] = None
        n = 0
        with open(path, newline="") as f:
            reader = csv.reader(f)
            if has_header:
                next(reader, None)
            for i, row in enumerate(reader):
                if max_rows is not None and i >= max_rows:
                    break
                try:
                    t = float(row[time_col]) * time_unit_seconds
                    cpu = float(row[cpu_col])
                except (IndexError, ValueError, TypeError):
                    continue
                t_min = t if t_min is None else min(t_min, t)
                n += 1
                # Defer bucketing until we know t_min; store raw for a second pass.
                buckets.setdefault(int(t // cycle_seconds), 0.0)
                buckets[int(t // cycle_seconds)] += cpu

        if not buckets or t_min is None:
            raise ValueError(f"No parseable rows in {path}")

        b0, b1 = min(buckets), max(buckets)
        loads = [buckets.get(b, 0.0) for b in range(b0, b1 + 1)]
        demand = self._normalize_to_demand(loads, capacity_percentile=95.0)

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
                "real_variable": "aggregate task CPU usage-rate distribution",
                "note": "PENDING_DATA — schema fixture only; not run on full Borg trace here",
            },
        )
