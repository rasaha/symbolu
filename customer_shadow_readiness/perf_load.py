"""Performance & load (M10). Actual WALL-CLOCK latency of the governance stages (no model call),
bounded cost/storage, and a load/concurrency test that verifies throughput AND tenant isolation under
concurrent load. Wall-clock varies run to run, so results are reported as bounds and NOT hash-pinned.
Shadow-only; reuses the GIP corpus + pilot API read-only.
"""
from __future__ import annotations

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from typing import Any, Dict, List

from governed_inference_pilot import dataset
from . import pilot_api, security, killswitch, observability


def _cases(tenant: str, n: int) -> List[Dict[str, Any]]:
    out = []
    for c in [asdict(x) for x in dataset.all_cases()[:n]]:
        c["request"]["tenant_id"] = tenant
        out.append(c)
    return out


def latency_study(n: int = 200) -> Dict[str, Any]:
    killswitch.restore_pilot()
    tok = security.issue_token("tok-acme-analyst")
    cases = _cases("acme", n)
    lat = []
    for c in cases:
        t0 = time.perf_counter()
        pilot_api.submit(tok, "acme", c)
        lat.append((time.perf_counter() - t0) * 1000.0)   # ms
    lat.sort()
    m = len(lat)
    return {"n": m, "median_ms": round(lat[m // 2], 3), "p90_ms": round(lat[int(m * 0.9)], 3),
            "p95_ms": round(lat[int(m * 0.95)], 3), "p99_ms": round(lat[min(m - 1, int(m * 0.99))], 3),
            "max_ms": round(lat[-1], 3),
            "note": "governance stages only; NO model call; fixture mode; wall-clock varies per run"}


def cost_storage(n: int = 200) -> Dict[str, Any]:
    from . import data_controls as dc
    tok = security.issue_token("tok-acme-analyst")
    store = dc.TenantDataStore()
    pol = dc.RetentionPolicy("acme", max_records=1000)
    bytes_total = 0
    for c in _cases("acme", n):
        r = pilot_api.submit(tok, "acme", c)
        rec = {"request_id": c["request"]["request_id"], "tenant_id": "acme",
               "risk_tier": c["request"]["risk_tier"], "domain": c["request"]["domain"],
               "final_shadow_disposition": r.final_shadow_disposition,
               "stage_dispositions": r.stage_dispositions, "reason_codes": r.reason_codes}
        store.put("acme", rec, pol)
        bytes_total += len(json.dumps(dc.minimize(rec)))
    return {"n": n, "mean_record_bytes": round(bytes_total / n, 1),
            "est_storage_per_1k_kb": round(bytes_total / n * 1000 / 1024, 1),
            "governance_token_cost_usd": 0.0, "note": "storage is minimized+redacted; token cost ~0 (no model call)"}


def load_concurrency(n_per_tenant: int = 50, workers: int = 8) -> Dict[str, Any]:
    """Concurrent submits across two tenants; verify throughput AND that no response leaks another
    tenant's data (isolation under concurrency)."""
    killswitch.restore_pilot()
    jobs = []
    for tenant, tok_id in (("acme", "tok-acme-analyst"), ("globex", "tok-globex-analyst")):
        tok = security.issue_token(tok_id)
        for c in _cases(tenant, n_per_tenant):
            jobs.append((tok, tenant, c))
    leaks = 0
    t0 = time.perf_counter()
    def run(job):
        tok, tenant, c = job
        r = pilot_api.submit(tok, tenant, c)
        return (tenant, r.tenant, r.accepted)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(run, jobs))
    elapsed = time.perf_counter() - t0
    for submitted_tenant, response_tenant, accepted in results:
        if response_tenant != submitted_tenant:      # a response scoped to the wrong tenant = leak
            leaks += 1
    return {"total_requests": len(jobs), "workers": workers,
            "wall_seconds": round(elapsed, 3),
            "throughput_rps": round(len(jobs) / elapsed, 1) if elapsed else 0.0,
            "cross_tenant_leaks": leaks, "all_accepted": all(a for _, _, a in results),
            "isolation_held": leaks == 0}


def run() -> Dict[str, Any]:
    return {"latency": latency_study(), "cost_storage": cost_storage(),
            "load_concurrency": load_concurrency()}


def main():
    r = run()
    o = os.path.join(os.path.dirname(__file__), "results", "perf_load.json")
    os.makedirs(os.path.dirname(o), exist_ok=True)
    with open(o, "w") as fh:
        json.dump(r, fh, indent=2, sort_keys=True)
    print("latency (ms):", {k: r["latency"][k] for k in ("median_ms", "p95_ms", "max_ms")})
    print("cost/storage:", {k: r["cost_storage"][k] for k in ("mean_record_bytes", "governance_token_cost_usd")})
    print("load:", {k: r["load_concurrency"][k] for k in ("total_requests", "throughput_rps", "cross_tenant_leaks", "isolation_held")})
    print(f"wrote {o}")


if __name__ == "__main__":
    main()
