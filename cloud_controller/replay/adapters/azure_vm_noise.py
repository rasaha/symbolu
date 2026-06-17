"""Azure VM-noise (noisy-neighbor) trace adapter (EXECUTED here).

Real Azure Public Dataset measurements of throughput under noisy-neighbor
interference. Each row is a real measured throughput sample for a benchmark on a
shared VM. We order samples in time and treat the *real measured variance/spike
structure* of the throughput as the workload signal — the real ingredient that
exercises the controller's damping and the guard's noisy-spike behaviour
(synthetic scenario #2 `noisy_spikes`).

Schema (vm-noise-data/.../unit=*.csv):
    value,runtime,starttime,VM_id

Mapping (documented, single choice): sort by starttime, normalise `value` to
[0,1] across the series, and use it directly as demand. Because throughput
samples under interference carry the real dip/spike structure, the variance the
controller sees is real; the absolute orientation is a modelling choice noted in
the artifacts.

Source: Azure Public Dataset — github.com/Azure/AzurePublicDataset
License: CC-BY-4.0
"""

from __future__ import annotations

import csv
from datetime import datetime
from typing import List, Optional, Tuple

from cloud_controller.replay.adapters.base import (
    AdapterStatus,
    TraceAdapter,
    TraceSeries,
)


def _parse_ts(s: str) -> Optional[float]:
    s = s.strip()
    if not s:
        return None
    if "." in s:
        head, frac = s.split(".", 1)
        frac = "".join(ch for ch in frac if ch.isdigit())[:6].ljust(6, "0")
        s = f"{head}.{frac}"
        fmt = "%Y-%m-%d %H:%M:%S.%f"
    else:
        fmt = "%Y-%m-%d %H:%M:%S"
    try:
        return datetime.strptime(s, fmt).timestamp()
    except ValueError:
        return None


class AzureVMNoiseAdapter(TraceAdapter):
    NAME = "azure_vm_noise"
    CITATION = (
        "Azure VM-noise (noisy-neighbor) dataset, Microsoft Azure Public "
        "Dataset, github.com/Azure/AzurePublicDataset"
    )
    LICENSE = "CC-BY-4.0"
    SCHEMA = "value,runtime,starttime,VM_id"
    STATUS = AdapterStatus.EXECUTED

    def load(
        self,
        path: str,
        cycle_seconds: float = 15.0,
        max_rows: Optional[int] = None,
        invert: bool = False,
        name: Optional[str] = None,
    ) -> TraceSeries:
        rows: List[Tuple[float, float]] = []  # (ts, value)
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if max_rows is not None and i >= max_rows:
                    break
                t = _parse_ts(row.get("starttime", ""))
                try:
                    v = float(row.get("value", "") or "nan")
                except ValueError:
                    continue
                if t is None or v != v:  # skip unparseable / NaN
                    continue
                rows.append((t, v))

        if not rows:
            raise ValueError(f"No parseable rows in {path}")

        rows.sort(key=lambda r: r[0])
        values = [v for _, v in rows]
        vmin, vmax = min(values), max(values)
        span = (vmax - vmin) or 1.0
        demand = []
        for v in values:
            norm = (v - vmin) / span
            demand.append(1.0 - norm if invert else norm)

        return TraceSeries(
            name=name or self.NAME,
            source=self.CITATION,
            license=self.LICENSE,
            status=self.STATUS,
            cycle_seconds=cycle_seconds,
            demand=demand,
            meta={
                "n_samples": len(values),
                "value_min": round(vmin, 3),
                "value_max": round(vmax, 3),
                "inverted": invert,
                "transfer_function": "benchmark._demand_to_metrics (shared with synthetic suite)",
                "real_variable": "measured throughput variance under noisy-neighbor interference",
            },
        )
