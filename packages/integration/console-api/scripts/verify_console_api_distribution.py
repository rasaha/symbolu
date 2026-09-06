#!/usr/bin/env python3
"""Build ``ugence-console-api`` and prove the rulings against the *built artifact*.

A source tree can satisfy CP-3 and CP-5 by accident: the repository root conftest puts
every platform package on ``sys.path``, so an adapter whose dependency is undeclared
still imports, and a route surface asserted from source is asserted from a file rather
than from what a deployment actually serves. This script removes that comfort. It builds
the wheel and the sdist, installs the wheel into a clean ``--no-index`` virtual
environment alongside locally built platform wheels, and then interrogates the
*installed* package.

Four proofs, each mapped to the ruling it defends
(``docs/architecture/ADR_UGENCE_CONSOLE_PACKAGING_SCOPING.md`` §8):

1. **CP-2** — the wheel ships the ``ugence_console_api`` namespace and nothing else: no
   tests, no ``apps/console`` frontend, no second top-level package.
2. **CP-5, the negative half** — installing with a governance dependency withheld
   *fails at install*. This is the proof that matters: the fail-safe ``try`` guards
   would otherwise let that same install succeed and serve.
3. **CP-5, the positive half** — with every dependency present, all four capability
   adapters report available in the clean environment. A declared dependency that the
   installed package cannot actually import would pass a metadata test and fail here.
4. **CP-3 and CP-4** — the application built from the installed package serves exactly
   five routes, and every answer carries the audit-ceiling header.

Run:  python packages/integration/console-api/scripts/verify_console_api_distribution.py
"""

from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

PACKAGE = pathlib.Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[2]

#: The platform distributions the console declares, and where each is built from.
PLATFORM_SOURCES = {
    "ugence-context-minimization": REPO / "packages" / "capabilities" / "context-minimization",
    "ugence-governance-provider-framework": REPO / "packages" / "governance-provider-framework",
    "ugence-actiongate-provider": REPO / "packages" / "providers" / "actiongate",
    "ugence-tap-provider": REPO / "packages" / "providers" / "tap",
}

#: First-party distributions the four above require in turn. Not dependencies of the
#: console — it never imports them — but the wheelhouse must hold them or the isolated
#: install fails for a reason that says nothing about this package.
TRANSITIVE_SOURCES = {
    "ugence-governance-contracts": REPO / "packages" / "governance-contracts",
}

#: The one withheld in proof 2. Any of the four would do; ActionGate is the sharpest,
#: because it is the adapter that answers "may THIS action execute".
WITHHELD_FOR_THE_NEGATIVE_PROOF = "ugence-actiongate-provider"

EXPECTED_ROUTES = {
    ("GET", "/health"),
    ("POST", "/v1/governed-loop/shadow"),
    ("POST", "/v1/governed-loop/scenario/{scenario_id}"),
    ("GET", "/v1/audit"),
    ("GET", "/v1/audit/{correlation_id}"),
}

_failures: list[str] = []


def check(condition: bool, message: str) -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {message}")
    if not condition:
        _failures.append(message)


def run(argv: list[str], *, cwd: pathlib.Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True)


def must(argv: list[str], *, cwd: pathlib.Path | None = None) -> str:
    result = run(argv, cwd=cwd)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise SystemExit(f"command failed: {' '.join(argv)}")
    return result.stdout


#: Third-party wheels fetched once so the two isolated installs below can run
#: ``--no-index``. Without this the negative proof would have to leave an index
#: reachable, and "the install failed" would no longer be a statement about the
#: withheld first-party wheel alone.
THIRD_PARTY = ["fastapi>=0.100.0", "pydantic>=2.0.0", "httpx>=0.24.0"]


def build_all(wheelhouse: pathlib.Path) -> None:
    print(f"\nBuilding into {wheelhouse}")
    for source in [PACKAGE, *PLATFORM_SOURCES.values(), *TRANSITIVE_SOURCES.values()]:
        must([sys.executable, "-m", "build", "--outdir", str(wheelhouse), str(source)])
        print(f"  built {source.name}")
    must([sys.executable, "-m", "pip", "download", "--only-binary", ":all:",
          "--dest", str(wheelhouse), *THIRD_PARTY])
    print(f"  fetched the third-party wheels ({', '.join(THIRD_PARTY)})")


def wheel_for(wheelhouse: pathlib.Path, distribution: str) -> pathlib.Path:
    prefix = distribution.replace("-", "_") + "-"
    (found,) = [w for w in wheelhouse.glob("*.whl") if w.name.startswith(prefix)]
    return found


def proof_1_the_wheel_ships_the_namespace_alone(wheelhouse: pathlib.Path) -> None:
    import zipfile

    print("\nCP-2 — the wheel ships the namespace and nothing else")
    names = zipfile.ZipFile(wheel_for(wheelhouse, "ugence-console-api")).namelist()
    top = {n.split("/")[0] for n in names}
    check(top == {"ugence_console_api", "ugence_console_api-0.2.0.dist-info"},
          f"one top-level package plus its metadata (got {sorted(top)})")
    check(not any("/tests/" in n or n.startswith("tests/") for n in names),
          "no test module ships in the distribution")
    check(not any("frontend" in n or "console/src" in n for n in names),
          "no React frontend ships in the distribution (CP-1)")
    check("ugence_console_api/py.typed" in names, "py.typed ships")


def make_venv(root: pathlib.Path) -> pathlib.Path:
    must([sys.executable, "-m", "venv", str(root)])
    return root / "bin" / "python"


def proof_2_a_missing_governance_dependency_fails_at_install(
        wheelhouse: pathlib.Path, workspace: pathlib.Path) -> None:
    print("\nCP-5 — a missing governance dependency is an install-time failure")
    partial = workspace / "wheelhouse-partial"
    partial.mkdir()
    withheld_prefix = WITHHELD_FOR_THE_NEGATIVE_PROOF.replace("-", "_") + "-"
    for wheel in wheelhouse.glob("*.whl"):
        if not wheel.name.startswith(withheld_prefix):
            shutil.copy2(wheel, partial)

    python = make_venv(workspace / "venv-partial")
    result = run([str(python), "-m", "pip", "install", "--no-index",
                  "--find-links", str(partial),
                  str(wheel_for(wheelhouse, "ugence-console-api"))])
    check(result.returncode != 0,
          f"install refuses without {WITHHELD_FOR_THE_NEGATIVE_PROOF}")
    check(WITHHELD_FOR_THE_NEGATIVE_PROOF in (result.stdout + result.stderr),
          "pip names the missing distribution in its refusal")
    check(run([str(python), "-c", "import ugence_console_api"]).returncode != 0,
          "and nothing importable was left behind")


def proof_3_and_4_the_installed_service(
        wheelhouse: pathlib.Path, workspace: pathlib.Path) -> None:
    print("\nCP-5 — every declared dependency is importable from the clean install")
    python = make_venv(workspace / "venv-full")
    must([str(python), "-m", "pip", "install", "--no-index",
          "--find-links", str(wheelhouse),
          str(wheel_for(wheelhouse, "ugence-console-api"))])
    # httpx is the TestClient transport, not a dependency of the service. Installed
    # here only so proof 4 can drive the installed application over HTTP.
    must([str(python), "-m", "pip", "install", "--no-index",
          "--find-links", str(wheelhouse), "httpx"])

    probe = r'''
import json, sys
from ugence_console_api.capabilities import (
    action_control, context_gateway, operational_safety, truth_evidence)
from ugence_console_api.app import AUDIT_CEILING_HEADER, create_app
from ugence_console_api.models import AUDIT_CEILING
from fastapi.testclient import TestClient

adapters = {
    "context_minimization": context_gateway.available(),
    "tap": truth_evidence.available(),
    "actiongate": action_control.available(),
    "autonomous_control_plane": operational_safety.available(),
}
app = create_app()
framework = {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}
routes = sorted(
    [m, r.path]
    for r in app.routes
    for m in (getattr(r, "methods", None) or ())
    if getattr(r, "path", None) not in framework and m not in {"HEAD", "OPTIONS"}
    and getattr(r, "path", None) is not None
)
client = TestClient(app, raise_server_exceptions=False)
probes = [("GET", "/health"), ("GET", "/v1/audit"),
          ("GET", "/v1/audit/none"), ("POST", "/v1/governed-loop/scenario/none"),
          ("POST", "/v1/governed-loop/shadow")]
headers = {
    f"{m} {p}": client.request(m, p, json={} if m == "POST" else None)
                      .headers.get(AUDIT_CEILING_HEADER)
    for m, p in probes
}
withheld = [
    [m, p, client.request(m, p, json={}).status_code]
    for m, p in [("POST", "/v1/actions/authorize"), ("POST", "/v1/actions/clear"),
                 ("POST", "/v1/assertions/evaluate"), ("GET", "/v1/modules"),
                 ("GET", "/v1/scenarios"), ("POST", "/v1/gateway/minimize")]
]
print(json.dumps({
    "adapters": {k: [ok, reason] for k, (ok, reason) in adapters.items()},
    "routes": routes,
    "headers": headers,
    "ceiling": AUDIT_CEILING,
    "health_ceiling": client.get("/health").json().get("audit_ceiling"),
    "withheld": withheld,
}))
'''
    report = json.loads(must([str(python), "-c", probe]).strip().splitlines()[-1])

    for name, (ok, reason) in report["adapters"].items():
        check(bool(ok), f"{name} adapter available in the clean install ({reason or 'ok'})")

    print("\nCP-3 — the installed application serves exactly five routes")
    served = {(m, p) for m, p in report["routes"]}
    check(served == EXPECTED_ROUTES,
          f"served surface is the ruled five (got {sorted(served)})")
    for method, path, status in report["withheld"]:
        check(status == 404, f"withheld {method} {path} is not routed (status {status})")

    print("\nCP-4 — every answer declares the audit ceiling")
    for route, header in report["headers"].items():
        check(header == report["ceiling"], f"{route} carries the ceiling header")
    check(report["health_ceiling"] == report["ceiling"],
          "/health carries the ceiling in its body")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="console-api-dist-") as tmp:
        workspace = pathlib.Path(tmp)
        wheelhouse = workspace / "wheelhouse"
        wheelhouse.mkdir()
        build_all(wheelhouse)
        proof_1_the_wheel_ships_the_namespace_alone(wheelhouse)
        proof_2_a_missing_governance_dependency_fails_at_install(wheelhouse, workspace)
        proof_3_and_4_the_installed_service(wheelhouse, workspace)

    print()
    if _failures:
        print(f"DISTRIBUTION VERIFICATION FAILED — {len(_failures)} check(s):")
        for failure in _failures:
            print(f"  {failure}")
        return 1
    print("DISTRIBUTION VERIFICATION OK — CP-2, CP-3, CP-4 and CP-5 hold for the "
          "built artifact, not only for the source tree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
