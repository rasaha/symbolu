#!/usr/bin/env python3
"""Shadow-harness integrity verifier for ugence-cloud-scaling-operations.

Verifies the environment-independent read-only shadow harness WITHOUT touching a real
cluster: harness source imports no live executor and performs no credential
auto-discovery; import has no side effects; the transport barrier blocks every write
method; mutation canaries pass with zero transmissions; fixture decisions are all
proposed-only; committed fixture evidence is deterministic, clearly fake-labelled, and
free of secret material; authorization/staleness/HPA scenarios are complete and
reproducible; and the advisory package remains advisory-only while operations stays
dry-run-by-default.

Emits artifacts/shadow_harness/verification_report.json and exits nonzero on any failure.
The verifier connects to no Kubernetes or ArgoCD endpoint.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PKG = Path(__file__).resolve().parent
OPS_SRC = PKG / "src"
ADV = PKG.parent / "cloud-scaling-controller"
ADV_SRC = ADV / "src"
COMMITTED_FIXTURE = PKG / "artifacts" / "shadow_harness_fixture"
REPORT_DIR = PKG / "artifacts" / "shadow_harness"

for p in (str(PKG), str(OPS_SRC), str(ADV_SRC)):
    if p not in sys.path:
        sys.path.insert(0, p)

# Artifacts whose bytes must be reproducible across environments (exclude canary /
# integrity / aggregate, which embed environment-dependent detail).
DETERMINISTIC_ARTIFACTS = [
    "fixture_environment_manifest.json",
    "fixture_target_allowlist.json",
    "fixture_session_manifest.json",
    "fixture_observation_records.jsonl",
    "fixture_shadow_decisions.jsonl",
    "fixture_authorization_validation.json",
    "fixture_stale_state_results.json",
    "fixture_hpa_interaction_results.json",
    "fixture_request_method_ledger.jsonl",
    "fixture_network_failure_results.json",
    "fixture_secret_redaction_report.json",
]


class Checks:
    def __init__(self):
        self.results = []
        self.ok = True

    def check(self, name, passed, detail=""):
        self.results.append({"check": name, "passed": bool(passed), "detail": str(detail)})
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
        if not passed:
            self.ok = False


def _sha(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode()).hexdigest()


def _import_side_effect_probe() -> dict:
    prog = (
        "import sys, json\n"
        f"sys.path.insert(0, {str(PKG)!r})\n"
        f"sys.path.insert(0, {str(OPS_SRC)!r})\n"
        f"sys.path.insert(0, {str(ADV_SRC)!r})\n"
        "import socket, threading\n"
        "_o = socket.socket\n"
        "st = {'socket': False, 'tb': threading.active_count()}\n"
        "class _T(_o):\n"
        "    def __init__(self,*a,**k):\n"
        "        st['socket']=True; super().__init__(*a,**k)\n"
        "socket.socket=_T\n"
        "import shadow_validation\n"
        "st['ta']=threading.active_count()\n"
        "forb=['kubernetes','boto3','botocore','azure','google.cloud','prometheus_client',"
        "'opentelemetry','yaml','requests']\n"
        "st['forbidden']=[m for m in forb if m in sys.modules]\n"
        "print(json.dumps(st))\n"
    )
    out = subprocess.run([sys.executable, "-I", "-c", prog], capture_output=True, text=True)
    if out.returncode != 0:
        return {"error": out.stderr}
    return json.loads(out.stdout.strip().splitlines()[-1])


def main() -> int:
    c = Checks()
    ev = {"verifier": "cloud-scaling-operations-shadow-harness",
          "evidence_class": "HARNESS_VERIFICATION",
          "real_environment_observed": False, "real_cluster_accessed": False}

    from shadow_validation.integrity import (
        scan_harness_source, verify_evidence_dir, reproduce_scenarios)
    from shadow_validation.evidence import generate_fixture_evidence, FIXTURE_ARTIFACT_NAMES
    from shadow_mutation_canaries import run_mutation_canaries
    from ugence_cloud_scaling_operations import __version__ as OPS_V
    from ugence_cloud_scaling_controller import __version__ as ADV_V

    # 1. Source boundary.
    violations = scan_harness_source()
    c.check("harness_source_imports_no_live_executor", not violations, ",".join(violations))

    # 2. Import side effects.
    probe = _import_side_effect_probe()
    c.check("import_no_side_effects",
            probe.get("socket") is False and probe.get("ta") == probe.get("tb")
            and not probe.get("forbidden"),
            probe.get("error") or f"forbidden={probe.get('forbidden')}")

    # 3. Mutation canaries.
    canaries = run_mutation_canaries()
    c.check("mutation_canaries_all_blocked", canaries["all_blocked"],
            f"{canaries['passed']}/{canaries['total']}")
    c.check("no_transmitted_write_methods",
            not canaries["transmitted_write_methods"]
            and canaries["real_network_transmissions"] == 0)

    # 4. Fresh fixture generation + integrity.
    tmp = Path(tempfile.mkdtemp(prefix="shadow-verify-"))
    fresh_report = verify_evidence_dir_generate(tmp, canaries)
    c.check("fresh_fixture_integrity_ok", fresh_report["ok"],
            ",".join(x["check"] for x in fresh_report["checks"] if not x["passed"]))

    # 5. Committed fixture present + integrity + deterministic byte match.
    committed_present = COMMITTED_FIXTURE.exists() and all(
        (COMMITTED_FIXTURE / n).exists() for n in FIXTURE_ARTIFACT_NAMES)
    c.check("committed_fixture_present", committed_present, str(COMMITTED_FIXTURE))
    if committed_present:
        committed_report = verify_evidence_dir(str(COMMITTED_FIXTURE))
        c.check("committed_fixture_integrity_ok", committed_report["ok"],
                ",".join(x["check"] for x in committed_report["checks"] if not x["passed"]))
        mism = []
        for n in DETERMINISTIC_ARTIFACTS:
            a = (COMMITTED_FIXTURE / n).read_text()
            b = (tmp / n).read_text()
            if _sha(a) != _sha(b):
                mism.append(n)
        c.check("committed_evidence_hashes_match", not mism, ",".join(mism))
        # No artifact claims real access.
        real_claim = []
        for n in FIXTURE_ARTIFACT_NAMES:
            if n.endswith(".json"):
                obj = json.loads((COMMITTED_FIXTURE / n).read_text())
                if obj.get("real_environment_observed") is True or obj.get("real_cluster_accessed") is True:
                    real_claim.append(n)
        c.check("no_committed_artifact_claims_real_access", not real_claim, ",".join(real_claim))

    # 6. Scenario reproducibility.
    rep = reproduce_scenarios()
    c.check("scenarios_reproducible_and_ok", rep["reproducible"] and rep["all_ok"],
            f"{rep['count']} scenarios")

    # 7. Package versions + boundaries.
    c.check("package_versions", OPS_V == "0.1.0" and ADV_V == "0.1.1",
            f"ops={OPS_V}, advisory={ADV_V}")
    adv_manifest = json.loads((ADV / "module_manifest.json").read_text())
    c.check("advisory_remains_advisory_only",
            adv_manifest.get("execution_capability") == "NONE"
            and adv_manifest.get("authority_class") == "ADVISORY")
    ops_manifest = json.loads((PKG / "module_manifest.json").read_text())
    c.check("operations_default_dry_run",
            ops_manifest.get("default_execution_mode") == "dry_run"
            and ops_manifest.get("requires_external_authorization") is True)

    # Finalize.
    ev.update({
        "ops_version": OPS_V, "advisory_version": ADV_V,
        "canaries": {"passed": canaries["passed"], "total": canaries["total"],
                     "all_blocked": canaries["all_blocked"]},
        "checks": c.results, "ok": c.ok,
        "verdict": ("CLOUD_SCALING_OPERATIONS_SHADOW_HARNESS_VERIFIED" if c.ok
                    else "CLOUD_SCALING_OPERATIONS_SHADOW_HARNESS_FAILED"),
    })
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "verification_report.json").write_text(
        json.dumps(ev, indent=2, sort_keys=True) + "\n")
    print(f"\n{ev['verdict']}  (report: {REPORT_DIR / 'verification_report.json'})")
    return 0 if c.ok else 1


def verify_evidence_dir_generate(tmp: Path, canaries: dict) -> dict:
    """Generate a fresh fixture into tmp and verify it."""
    from shadow_validation.evidence import generate_fixture_evidence
    from shadow_validation.integrity import verify_evidence_dir
    generate_fixture_evidence(str(tmp), canary_results=canaries)
    return verify_evidence_dir(str(tmp))


if __name__ == "__main__":
    raise SystemExit(main())
