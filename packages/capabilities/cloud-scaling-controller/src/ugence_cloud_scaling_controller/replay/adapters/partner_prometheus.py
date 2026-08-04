"""Partner Prometheus/HPA export adapter (Track B — design-partner ingestion).

Ingests a design partner's exported telemetry (the §5 data ask:
`docs/cloud_scaling_real_validation/track_c_design_partner/03_DATA_REQUEST_NDA_CHECKLIST.md`)
into a `TraceSeries` the Tier-A detector consumes. Unlike the Azure arrival traces —
where metrics are *modeled* from a demand series — a partner export carries **real
measured metrics AND a real replica history**, so the verdict runs on real signals and
real fleet sizes. That is the whole point of partner replay.

STATUS = PENDING_DATA: the adapter + schema are implemented and validated on a
committed **synthetic schema fixture**. No real partner data exists in this
environment, so this produces **no market number** — only a tooling self-test. Real
partner runs are labelled `real-trace-replay (estimate pending live adjudication)` and
gated on SRE adjudication.

Canonical export schema
-----------------------
Metrics CSV — one row per cycle (the partner's scrape/aggregation cadence), in time
order. A `timestamp` column (epoch seconds or ISO-8601) sets the cycle grid; columns
are matched by alias:
    timestamp, cpu, memory, latency_p99[_seconds|_ms], error_rate, queue_depth,
    current_replicas, desired_replicas, pod_restarts
Incidents CSV (optional, separate file — §5 item 4):
    incident_id, start, end, severity     # start/end as epoch seconds or ISO

Normalization assumptions are FROZEN in TIER_A_DETECTOR_SPEC.md §7 and recorded in
`meta["normalization"]` on every load.
"""

from __future__ import annotations

import csv
from datetime import datetime
from typing import Dict, List, Optional

from ugence_cloud_scaling_controller.replay.adapters.base import (
    AdapterStatus,
    IncidentWindow,
    TraceAdapter,
    TraceSeries,
)

_ALIASES = {
    "cpu": ("cpu", "cpu_utilization", "cpu_util", "cpu_pct"),
    "memory": ("memory", "mem", "memory_utilization", "mem_util"),
    "latency_p99": ("latency_p99_seconds", "latency_p99", "p99_latency",
                    "latency_p99_ms", "p99_ms"),
    "error_rate": ("error_rate", "error_ratio", "errors", "error_pct"),
    "queue_depth": ("queue_depth", "queue", "queue_messages_ready", "queue_len"),
    "current_replicas": ("current_replicas", "replicas", "current", "current_replica"),
    "desired_replicas": ("desired_replicas", "desired", "desired_replica"),
    "pod_restarts": ("pod_restarts", "restarts", "pod_restart"),
}
_METRIC_KEYS = ("cpu", "memory", "latency_p99", "error_rate", "queue_depth")


def _parse_ts(s: str) -> Optional[float]:
    """Epoch seconds or ISO-8601 → epoch float. Tolerant of 'Z' and sub-second digits."""
    s = (s or "").strip()
    if not s:
        return None
    try:
        return float(s)  # already epoch seconds
    except ValueError:
        pass
    s = s.rstrip("Z")
    if "." in s:
        head, frac = s.split(".", 1)
        frac = "".join(ch for ch in frac if ch.isdigit())[:6].ljust(6, "0")
        s = f"{head}.{frac}"
        fmts = ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S.%f")
    else:
        fmts = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d")
    for fmt in fmts:
        try:
            return datetime.strptime(s, fmt).timestamp()
        except ValueError:
            continue
    return None


def _resolve(fieldnames: List[str], aliases) -> Optional[str]:
    lower = {f.lower(): f for f in fieldnames}
    for a in aliases:
        if a in lower:
            return lower[a]
    return None


def _to_fraction(series: List[float]) -> List[float]:
    """A util/ratio series: read as percent if it exceeds 1.0, else as a fraction."""
    if series and max(series) > 1.0:
        series = [v / 100.0 for v in series]
    return [max(0.0, min(1.0, v)) for v in series]


class PartnerPrometheusAdapter(TraceAdapter):
    NAME = "partner_prometheus"
    CITATION = "Design-partner Prometheus/HPA export (per NDA; not committed)"
    LICENSE = "partner-proprietary (NDA)"
    SCHEMA = ("timestamp,cpu,memory,latency_p99[_seconds|_ms],error_rate,queue_depth,"
              "current_replicas,desired_replicas,pod_restarts")
    STATUS = AdapterStatus.PENDING_DATA

    def load(
        self,
        path: str,
        incidents_path: Optional[str] = None,
        cycle_seconds: Optional[float] = None,
        latency_slo_seconds: float = 1.0,
        queue_capacity: Optional[float] = None,
        cluster: Optional[str] = None,
        org: Optional[str] = None,
        name: Optional[str] = None,
    ) -> TraceSeries:
        rows: List[Dict[str, str]] = []
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            for row in reader:
                rows.append(row)
        if not rows:
            raise ValueError(f"No rows in partner export {path}")

        cols = {k: _resolve(fieldnames, al) for k, al in _ALIASES.items()}
        ts_col = _resolve(fieldnames, ("timestamp", "time", "ts"))

        def col(row, key) -> Optional[float]:
            c = cols.get(key)
            if c is None:
                return None
            v = row.get(c, "")
            try:
                return float(v)
            except (TypeError, ValueError):
                return None

        timestamps = [_parse_ts(r.get(ts_col, "")) if ts_col else None for r in rows]
        # cycle_seconds: explicit > median timestamp delta > 15s default
        if cycle_seconds is None:
            deltas = [b - a for a, b in zip(timestamps, timestamps[1:])
                      if a is not None and b is not None and b > a]
            cycle_seconds = (sorted(deltas)[len(deltas) // 2] if deltas else 15.0)

        raw_cpu = [col(r, "cpu") or 0.0 for r in rows]
        raw_mem = [col(r, "memory") or 0.0 for r in rows]
        raw_err = [col(r, "error_rate") or 0.0 for r in rows]
        raw_lat = [col(r, "latency_p99") or 0.0 for r in rows]
        raw_q = [col(r, "queue_depth") or 0.0 for r in rows]
        replicas = [col(r, "current_replicas") or 1.0 for r in rows]

        cpu = _to_fraction(raw_cpu)
        mem = _to_fraction(raw_mem)
        err = _to_fraction(raw_err)

        lat_is_ms = bool(cols["latency_p99"]) and "ms" in cols["latency_p99"].lower()
        lat_sec = [(v / 1000.0 if lat_is_ms else v) for v in raw_lat]
        lat = [max(0.0, min(1.0, v / latency_slo_seconds)) for v in lat_sec]

        qcap = queue_capacity if queue_capacity is not None else self._percentile(raw_q, 95.0)
        queue = [max(0.0, min(1.0, (v / qcap) if qcap > 0 else 0.0)) for v in raw_q]

        metrics: List[Dict[str, float]] = [
            {"cpu": cpu[i], "memory": mem[i], "latency_p99": lat[i],
             "error_rate": err[i], "queue_depth": queue[i]}
            for i in range(len(rows))
        ]

        # Incidents → cycle indices on this trace's grid.
        incidents: List[IncidentWindow] = []
        incidents_provided = incidents_path is not None
        if incidents_path is not None:
            t0 = next((t for t in timestamps if t is not None), None)
            incidents = self._load_incidents(incidents_path, t0, cycle_seconds, len(rows))

        return TraceSeries(
            name=name or cluster or self.NAME,
            source=self.CITATION,
            license=self.LICENSE,
            status=self.STATUS,
            cycle_seconds=float(cycle_seconds),
            demand=list(cpu),                 # cpu as a load proxy; metrics supplied directly
            metrics=metrics,
            replicas=replicas,
            meta={
                "org": org or (cluster or self.NAME),
                "cluster": cluster or self.NAME,
                "n_samples": len(rows),
                "incidents": incidents,
                "incidents_provided": incidents_provided,
                "transfer_function": "real measured metrics (no demand→metric model)",
                "real_variable": "measured metrics AND real replica history",
                "normalization": {
                    "latency_slo_seconds": latency_slo_seconds,
                    "latency_units": "ms" if lat_is_ms else "seconds",
                    "queue_capacity": qcap,
                    "cpu_memory_error": "percent if series max>1 else fraction; clamped [0,1]",
                },
                "note": "PENDING_DATA: synthetic schema fixture validates tooling only; "
                        "no market number until real partner data + SRE adjudication.",
            },
        )

    def _load_incidents(self, path, t0, cycle_seconds, n_cycles) -> List[IncidentWindow]:
        out: List[IncidentWindow] = []
        with open(path, newline="") as f:
            reader = csv.DictReader(f)
            fn = reader.fieldnames or []
            id_c = _resolve(fn, ("incident_id", "id", "incident"))
            s_c = _resolve(fn, ("start", "start_time", "begin"))
            e_c = _resolve(fn, ("end", "end_time", "stop"))
            sev_c = _resolve(fn, ("severity", "sev", "priority"))
            for i, row in enumerate(reader):
                s = _parse_ts(row.get(s_c, "")) if s_c else None
                e = _parse_ts(row.get(e_c, "")) if e_c else None
                if s is None or e is None or t0 is None:
                    continue
                sc = max(0, min(n_cycles - 1, int((s - t0) // cycle_seconds)))
                ec = max(0, min(n_cycles - 1, int((e - t0) // cycle_seconds)))
                if ec < sc:
                    sc, ec = ec, sc
                out.append(IncidentWindow(
                    incident_id=(row.get(id_c) if id_c else None) or f"INC-{i+1}",
                    start_cycle=sc, end_cycle=ec,
                    severity=(row.get(sev_c, "") if sev_c else ""),
                ))
        return out

    @staticmethod
    def _percentile(values: List[float], pct: float) -> float:
        pos = sorted(v for v in values if v > 0)
        if not pos:
            return 0.0
        idx = min(len(pos) - 1, max(0, int(round((pct / 100.0) * (len(pos) - 1)))))
        return pos[idx]
