#!/usr/bin/env python3
"""Reproducible proof that the distribution installs and operates from its DECLARED
dependencies alone, in a fresh virtualenv with no monorepo path.

Phases: **A (online)** build the first-party wheels and download the dependency closure
into a local wheelhouse; **B (offline)** install into a throwaway venv from that wheelhouse
with ``--no-index`` and ``PIP_NO_INDEX=1``; **C (offline)** negative controls; **D (offline)**
behaviour probes inside the isolated environment, importing nothing from the checkout.
Only phase B is the offline guarantee, and the closing banner says exactly that.

Run:  python packages/integration/reasoning-method-result-attestation/scripts/verify_isolated_install.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
REPO = PKG.parents[2]
FIRST_PARTY = [
    REPO / "packages" / "jcs",
    REPO / "packages" / "governance-contracts",
    REPO / "packages" / "uvi-policy-contracts",
    REPO / "packages" / "capabilities" / "reasoning-method-governance",
    REPO / "packages" / "trusted-evidence-authority",
    PKG,
]
REQUIRED = (
    "ugence_reasoning_method_result_attestation-",
    "ugence_reasoning_method_governance-",
    "ugence_trusted_evidence_authority-",
    "ugence_governance_contracts-",
    "ugence_uvi_policy_contracts-",
    "ugence_jcs-",
    "cryptography-",
    "pynacl-",
)
FORBIDDEN_INSTALLED = ("ugence_readiness_comparison", "ugence_reasoning_method_advisor",
                       "ugence_workflow_fit_pilot", "ugence_agentic_proposer",
                       "ugence_risk_authority_effect_attestation", "pydantic", "requests", "httpx", "boto3")
OFFLINE_SENTINEL_INDEX = "http://offline.invalid/simple"

_PROBE = r'''
import json, sys, dataclasses
from datetime import datetime, timezone
import ugence_reasoning_method_result_attestation as ra
from ugence_reasoning_method_governance.api import (
    AUTHORITY_RESOLUTION_BASIS_V1, COMPARISON_RESULT_SCHEMA_VERSION, EVIDENCE_STATUS_SOURCE_V1,
    FIT_SCHEMA_VERSION, USAGE_SCOPE_RESEARCH_ONLY, FitOutcome, ReadinessComparisonResult,
    ReasoningMethodCatalogRef, ReasoningMethodFitAssessment, ReasoningMethodRef, ResourceDimension,
)
assert "site-packages" in ra.__file__, ra.__file__
ENGINE_ID = "ugence-readiness-comparison"
PRODUCED_AT = datetime(2026, 9, 6, 11, 0, tzinfo=timezone.utc)
T = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)
AS_OF = datetime(2026, 9, 6, 12, 5, tzinfo=timezone.utc)
cref = ReasoningMethodCatalogRef("catalog.synthetic", "1", "a" * 64)
a = ReasoningMethodFitAssessment(
    FIT_SCHEMA_VERSION, "a.1", "study.synthetic", "b" * 64, "d" * 64, "",
    ReasoningMethodRef(cref, "map_reduce", "1"), ReasoningMethodRef(cref, "linear_chain", "1"),
    FitOutcome.SUFFICIENT_PARETO_EFFICIENT, None, None, (), (), (ResourceDimension.LLM_CALLS,), "pol.cmp", "1", "",
    (), EVIDENCE_STATUS_SOURCE_V1, USAGE_SCOPE_RESEARCH_ONLY, ENGINE_ID, "0.2.0", PRODUCED_AT, "synthetic fixture",
)
res = ReadinessComparisonResult(COMPARISON_RESULT_SCHEMA_VERSION, "cmp.synthetic", "a" * 64, (a,), (), (), (),
                                AUTHORITY_RESOLUTION_BASIS_V1, ENGINE_ID, "0.2.0", PRODUCED_AT)
signer = ra.ReferenceEd25519ComparisonResultSigner(b"\x01" * 32, signer_identity=ENGINE_ID,
                                                    signer_key_id="engine-key-1",
                                                    signer_role=ra.ComparisonResultAttesterRole.COMPARISON_ENGINE)
anchor = signer.trust_anchor(trust_anchor_set_id="comparison-result-anchors", trust_anchor_set_version="1",
                             effective_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
                             effective_to=datetime(2027, 1, 1, tzinfo=timezone.utc))
sr = ra.sign_comparison_result(res, signer=signer, signed_at=T)
d = ra.StaticTrustAnchorDirectory([anchor], trust_anchor_set_id="comparison-result-anchors", trust_anchor_set_version="1")
v = ra.Ed25519ComparisonResultVerifier(trust_anchor_resolver=d)
ROLE = ra.ComparisonResultAttesterRole.COMPARISON_ENGINE
ok = v.verify(signed_result=sr, expected_role=ROLE, expected_engine_identity=ENGINE_ID, expected_result=res, as_of=AS_OF)
assert ok.outcome.name == "VERIFIED" and ok.factual_correctness_established is False
R = ra.ComparisonResultRefusalReason
def refused(**kw):
    args = dict(signed_result=sr, expected_role=ROLE, expected_engine_identity=ENGINE_ID, expected_result=res, as_of=AS_OF)
    args.update(kw); return v.verify(**args).refusal_reason
assert refused(signed_result=None) is R.ATTESTATION_ABSENT
assert refused(expected_engine_identity="someone-else") is R.WRONG_ENGINE_IDENTITY
assert refused(expected_result=dataclasses.replace(res, request_id="cmp.other", result_digest="")) is R.RESULT_MISMATCH
assert refused(signed_result=dataclasses.replace(sr, signature="ab" * 64)) is R.SIGNATURE_INVALID
assert ra.Ed25519ComparisonResultVerifier(trust_anchor_resolver=ra.DenyAllTrustAnchorDirectory(), production_mode=True).verify(
    signed_result=sr, expected_role=ROLE, expected_engine_identity=ENGINE_ID, expected_result=res, as_of=AS_OF).refusal_reason is R.ANCHOR_UNKNOWN
try:
    ra.Ed25519ComparisonResultVerifier(trust_anchor_resolver=d, production_mode=True); raise SystemExit("static resolver admitted in production")
except ra.ComparisonResultAttestationConfigurationError: pass
try:
    ra.sign_comparison_result(res, signer=signer, signed_at=T, production_mode=True); raise SystemExit("reference signer admitted in production")
except ra.ComparisonResultAttestationSigningBoundaryError: pass
for forbidden in %(forbidden)r:
    try:
        __import__(forbidden); raise SystemExit("forbidden module importable: " + forbidden)
    except ImportError: pass
print(json.dumps({"version": ra.__version__, "maturity": ra.MATURITY, "api": sorted(ra.__all__),
                  "result_digest": sr.result_digest, "projection_digest": sr.comparison_result_digest,
                  "payload_digest": sr.signing_payload_digest,
                  "signature": sr.signature, "anchor_digest": ra.anchor_record_digest(anchor)}))
'''

_steps = []


def step(label, ok, detail=""):
    _steps.append((label, ok))
    print(("ok    " if ok else "FAIL  ") + label + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(1)


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="comparison-result-iso-"))
    wheelhouse = work / "wheelhouse"
    wheelhouse.mkdir()
    try:
        # ---- Phase A (online): build first-party wheels, collect the closure ----------
        for project in FIRST_PARTY:
            run([sys.executable, "-m", "build", "--wheel", "--outdir", str(wheelhouse), str(project)])
        run([sys.executable, "-m", "pip", "download", "-q", "cryptography>=41.0.7,<47.0.0",
             "PyNaCl>=1.5.0,<2.0.0", "--dest", str(wheelhouse)])
        names = sorted(p.name for p in wheelhouse.iterdir())
        step("phase A: first-party wheels built and the closure collected",
             all(any(n.lower().startswith(r.lower()) for n in names) for r in REQUIRED), str(names))
        wheel = next(wheelhouse.glob("ugence_reasoning_method_result_attestation-*.whl"))
        members = zipfile.ZipFile(wheel).namelist()
        step("the wheel carries no test, conftest or fixture material",
             not any(m.startswith("tests/") or "/tests/" in m or m.rsplit("/", 1)[-1].startswith("test_") or "conftest" in m or "_fixtures" in m for m in members))
        step("the wheel ships py.typed", "ugence_reasoning_method_result_attestation/py.typed" in members)
        metadata = next(m for m in members if m.endswith("METADATA"))
        requires = [l.split(":", 1)[1].strip() for l in zipfile.ZipFile(wheel).read(metadata).decode().splitlines()
                    if l.startswith("Requires-Dist:") and "extra ==" not in l]
        step("the wheel declares exactly the two ratified dependencies",
             sorted(r.split(">=")[0].split("<")[0].strip() for r in requires) == sorted(
                 ["ugence-reasoning-method-governance", "ugence-trusted-evidence-authority"]), str(requires))

        # ---- Phase B (offline): the isolated install --------------------------------
        env_dir = work / "venv"
        venv.EnvBuilder(with_pip=True, system_site_packages=False).create(env_dir)
        py = env_dir / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
        clean = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV")}
        clean["PIP_NO_INDEX"] = "1"
        clean["PIP_INDEX_URL"] = OFFLINE_SENTINEL_INDEX
        run([str(py), "-m", "pip", "install", "-q", "--no-index", "--find-links", str(wheelhouse), str(wheel)], env=clean)
        installed = json.loads(run([str(py), "-m", "pip", "list", "--format=json"], env=clean).stdout)
        installed_names = {e["name"].lower().replace("_", "-") for e in installed}
        step("phase B: installed --no-index from the wheelhouse, no PYTHONPATH",
             {"ugence-reasoning-method-result-attestation", "ugence-reasoning-method-governance",
              "ugence-trusted-evidence-authority", "ugence-governance-contracts", "ugence-uvi-policy-contracts",
              "ugence-jcs", "cryptography", "pynacl"} <= installed_names, str(sorted(installed_names)))
        step("no forbidden distribution is installed alongside",
             not any(f.replace("_", "-") in installed_names for f in FORBIDDEN_INSTALLED))

        # ---- Phase C (offline): negative controls -----------------------------------
        empty = work / "empty"
        empty.mkdir()
        bare = work / "bare"
        venv.EnvBuilder(with_pip=True, system_site_packages=False).create(bare)
        bpy = bare / ("Scripts" if os.name == "nt" else "bin") / ("python.exe" if os.name == "nt" else "python")
        failed = subprocess.run([str(bpy), "-m", "pip", "install", "-q", "--no-index", "--find-links", str(empty), str(wheel)],
                                capture_output=True, text=True, env=clean)
        step("negative control: installing with the dependencies unavailable fails", failed.returncode != 0)
        probe_missing = subprocess.run([str(bpy), "-c", "import ugence_reasoning_method_result_attestation"],
                                       capture_output=True, text=True, env=clean)
        step("negative control: the package is not importable where it was not installed", probe_missing.returncode != 0)

        # ---- Phase D (offline): behaviour inside the isolated environment -----------
        probe = _PROBE % {"forbidden": FORBIDDEN_INSTALLED}
        out = json.loads(run([str(py), "-c", probe], env=clean, cwd=str(work)).stdout)
        manifest = json.loads((PKG / "public_api.json").read_text(encoding="utf-8"))
        step("phase D: the installed API equals the committed manifest, symbol for symbol",
             out["api"] == sorted(manifest["symbols"]))
        step("phase D: version and maturity match", out["version"] == manifest["package_version"]
             and out["maturity"] == "REFERENCE_GRADE_NOT_PRODUCTION_READY")
        step("phase D: the pinned vectors reproduce inside the installed wheel",
             out["result_digest"] == "248b60571017af0469da6e66a54aef882320e765349c7abd850e1d897cb3f930"
             and out["projection_digest"] == "sha256:5e4fda256ddacd50f33c06d38b1a8c3fd5a46ab24ea9251d48697722c3b400ec"
             and out["payload_digest"] == "sha256:a6f69c1a5be6278e7e01e2d014a2ca43f36d324068caa70c2922a52d0827099a"
             and out["signature"].startswith("bd4803e5a61d50c67ad07c35fb3043c9"), json.dumps(out)[:200])
        print("=" * 72)
        print(f"{len(_steps)} steps passed. Phase B is the offline guarantee; phase A reached an index to collect the closure.")
        print("ISOLATED COMPARISON-RESULT-ATTESTATION DISTRIBUTION VERIFIED ✔")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
