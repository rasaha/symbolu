"""Azure LLM/LMM inference trace adapter (EXECUTED here).

Real Azure Public Dataset inference traces — each row is one real inference
request. We bucket arrivals into fixed cycles and use per-cycle *token work*
(or request count) as the load, then map to demand ∈ [0,1] via the shared
capacity-percentile model. This yields a REAL arrival/burst distribution — the
exact thing Track B makes real relative to the synthetic demand shapes.

Schema (data/AzureLLMInferenceTrace_{conv,code}.csv):
    TIMESTAMP,ContextTokens,GeneratedTokens
Multimodal (AzureLMMInferenceTrace_multimodal.csv):
    TIMESTAMP,NumImages,ContextTokens,GeneratedTokens

Source: Azure Public Dataset — github.com/Azure/AzurePublicDataset
License: CC-BY-4.0
"""

from __future__ import annotations

import csv
from datetime import datetime
from typing import List, Optional

from cloud_controller.replay.adapters.base import (
    AdapterStatus,
    TraceAdapter,
    TraceSeries,
)


def _parse_ts(s: str) -> Optional[float]:
    """Parse an Azure timestamp to epoch seconds. Tolerant of fractional digits
    longer than microseconds and of trailing 'Z'."""
    s = s.strip().rstrip("Z")
    if not s:
        return None
    # Split fractional seconds (Azure uses up to 7 digits; datetime allows 6).
    if "." in s:
        head, frac = s.split(".", 1)
        frac = "".join(ch for ch in frac if ch.isdigit())[:6].ljust(6, "0")
        s = f"{head}.{frac}"
        fmts = ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S.%f")
    else:
        fmts = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S")
    for fmt in fmts:
        try:
            return datetime.strptime(s, fmt).timestamp()
        except ValueError:
            continue
    return None


class AzureLLMInferenceAdapter(TraceAdapter):
    NAME = "azure_llm_inference"
    CITATION = (
        "Azure LLM/LMM Inference Trace (2023-2025), Microsoft Azure Public "
        "Dataset, github.com/Azure/AzurePublicDataset"
    )
    LICENSE = "CC-BY-4.0"
    SCHEMA = "TIMESTAMP,[NumImages,]ContextTokens,GeneratedTokens"
    STATUS = AdapterStatus.EXECUTED

    def load(
        self,
        path: str,
        cycle_seconds: float = 15.0,
        load_metric: str = "tokens",   # "tokens" | "count"
        capacity_percentile: float = 95.0,
        max_rows: Optional[int] = None,
        name: Optional[str] = None,
    ) -> TraceSeries:
        ts_list: List[float] = []
        work_list: List[float] = []

        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if max_rows is not None and i >= max_rows:
                    break
                t = _parse_ts(row.get("TIMESTAMP", ""))
                if t is None:
                    continue
                try:
                    ctx = float(row.get("ContextTokens", 0) or 0)
                    gen = float(row.get("GeneratedTokens", 0) or 0)
                except ValueError:
                    ctx = gen = 0.0
                ts_list.append(t)
                work_list.append((ctx + gen) if load_metric == "tokens" else 1.0)

        if not ts_list:
            raise ValueError(f"No parseable rows in {path}")

        t0 = min(ts_list)
        t_end = max(ts_list)
        n_buckets = max(1, int((t_end - t0) // cycle_seconds) + 1)
        loads = [0.0] * n_buckets
        for t, w in zip(ts_list, work_list):
            b = int((t - t0) // cycle_seconds)
            if 0 <= b < n_buckets:
                loads[b] += w

        demand = self._normalize_to_demand(loads, capacity_percentile)

        return TraceSeries(
            name=name or self.NAME,
            source=self.CITATION,
            license=self.LICENSE,
            status=self.STATUS,
            cycle_seconds=cycle_seconds,
            demand=demand,
            meta={
                "n_requests": len(ts_list),
                "duration_seconds": round(t_end - t0, 1),
                "load_metric": load_metric,
                "capacity_percentile": capacity_percentile,
                "transfer_function": "benchmark._demand_to_metrics (shared with synthetic suite)",
                "real_variable": "workload distribution (real request arrival process)",
            },
        )
