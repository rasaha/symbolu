#!/usr/bin/env python
"""Packaged four-scenario E2E over a live HTTPS endpoint (P3E completion §12).

Drives the FULL planning surface for every approved scenario against a running
deployment (the OCI container in CI, or a live uvicorn server locally), over real
HTTPS with the deployment access gate — never in-process. Exits nonzero on any gate
failure.

    python packaged_e2e.py https://127.0.0.1:8443 <username> <password>
"""
from __future__ import annotations

import base64
import json
import ssl
import sys
import urllib.error
import urllib.request

SCENARIOS = ["procurement", "customer_support", "cybersecurity_success", "cybersecurity_no_feasible_team"]


def _ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # self-signed private cert; this test asserts behavior, not PKI
    return ctx


def _req(base: str, path: str, auth: str, method: str = "GET", body: dict | None = None) -> tuple[int, dict | None]:
    url = base.rstrip("/") + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": auth}
    if body is not None:
        headers["Content-Type"] = "application/json"
        headers["X-Ugence-Request"] = "GovernanceStudio"
        headers["Origin"] = base
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, context=_ctx(), timeout=15) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw) if raw else None
        except ValueError:
            return exc.code, None


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print("usage: packaged_e2e.py <base_url> <username> <password>", file=sys.stderr)
        return 2
    base, user, pw = argv[1], argv[2], argv[3]
    auth = "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()
    failures: list[str] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        (print if ok else lambda m: failures.append(m))(f"{'PASS' if ok else 'FAIL'} {name}{(' — ' + detail) if detail else ''}")

    # unauthenticated is 401
    status, _ = _req(base, "/api/v1/scenarios", "Basic bm9wZTpub3Bl")
    check("unauthenticated API 401", status == 401, f"got {status}")

    # authenticated catalog is exactly the four approved scenarios
    status, catalog = _req(base, "/api/v1/scenarios", auth)
    result = catalog["result"] if isinstance(catalog, dict) else None
    ids = {s["scenario_id"] for s in (result["scenarios"] if isinstance(result, dict) else result or [])}
    check("catalog authenticated 200", status == 200, f"got {status}")
    check("catalog is exactly the four synthetic scenarios", ids == set(SCENARIOS), str(ids))

    for sid in SCENARIOS:
        for suffix in ("", "/workflow", "/registry", "/eligibility", "/ranking", "/plan", "/export"):
            st, _ = _req(base, f"/api/v1/scenarios/{sid}{suffix}", auth)
            check(f"{sid}{suffix} 200", st == 200, f"got {st}")
        st, _ = _req(base, "/api/v1/explanations/plan", auth, "POST", {"scenario_id": sid})
        check(f"{sid} explain-plan 200", st == 200, f"got {st}")
        st, _ = _req(base, "/api/v1/plans/replay", auth, "POST", {"scenario_id": sid})
        check(f"{sid} replay 200 (no execution)", st == 200, f"got {st}")
        st, wf = _req(base, f"/api/v1/scenarios/{sid}/what-if", auth, "POST", {"operation": "EXPIRE_EVIDENCE", "params": {}})
        check(f"{sid} what-if 200 (temporary copy)", st == 200, f"got {st}")

    # no-feasible-team is a domain state at HTTP 200
    st, plan = _req(base, "/api/v1/scenarios/cybersecurity_no_feasible_team/plan", auth)
    state = plan["result"]["agent_team_plan"]["plan_state"] if isinstance(plan, dict) else None
    check("no-feasible-team is HTTP 200 domain state", st == 200 and state == "NO_FEASIBLE_TEAM", f"{st}/{state}")

    # deterministic export (no persistent mutation between calls)
    _, a = _req(base, "/api/v1/scenarios/procurement/export", auth)
    _, b = _req(base, "/api/v1/scenarios/procurement/export", auth)
    ra = a["result"] if isinstance(a, dict) else None
    rb = b["result"] if isinstance(b, dict) else None
    check("export deterministic", ra == rb and ra is not None)

    # what-if never mutates the baseline (two ops share one baseline fingerprint)
    _, w1 = _req(base, "/api/v1/scenarios/procurement/what-if", auth, "POST", {"operation": "TIGHTEN_COST_CEILING", "params": {"ceiling": 1.0}})
    _, w2 = _req(base, "/api/v1/scenarios/procurement/what-if", auth, "POST", {"operation": "FORBID_PROVIDER", "params": {"provider": "openai"}})
    f1 = w1["result"]["baseline_plan"]["plan_fingerprint"] if isinstance(w1, dict) else None
    f2 = w2["result"]["baseline_plan"]["plan_fingerprint"] if isinstance(w2, dict) else "x"
    check("what-if baseline immutable", f1 == f2 and f1 is not None)

    if failures:
        print("\n".join(failures), file=sys.stderr)
        print(f"\nPACKAGED E2E FAILED: {len(failures)} gate(s)", file=sys.stderr)
        return 1
    print("\nPACKAGED E2E PASSED (all four scenarios, over HTTPS)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
