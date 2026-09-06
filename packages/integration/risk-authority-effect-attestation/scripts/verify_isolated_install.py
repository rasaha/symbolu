#!/usr/bin/env python3
"""Reproducible proof that the distribution installs and operates from its DECLARED
dependencies alone, in a fresh virtualenv with no monorepo path.

Phases: **A (online)** build the first-party wheels and download the dependency closure
into a local wheelhouse; **B (offline)** install into a throwaway venv from that wheelhouse
with ``--no-index`` and ``PIP_NO_INDEX=1``; **C (offline)** negative controls; **D (offline)**
behaviour probes inside the isolated environment, importing nothing from the checkout.
Only phase B is the offline guarantee, and the closing banner says exactly that.

Run:  python packages/integration/risk-authority-effect-attestation/scripts/verify_isolated_install.py
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
    REPO / "packages" / "governance-contracts",
    REPO / "packages" / "trusted-evidence-authority",
    PKG,
]
REQUIRED = (
    "ugence_risk_authority_effect_attestation-",
    "ugence_trusted_evidence_authority-",
    "ugence_governance_contracts-",
    "cryptography-",
    "pynacl-",
)
FORBIDDEN_INSTALLED = ("ugence_risk_authority_execution_assurance", "ugence_decision_authority",
                       "ugence_agent_runtime", "pydantic", "requests", "httpx", "boto3")
OFFLINE_SENTINEL_INDEX = "http://offline.invalid/simple"

_PROBE = r'''
import json, sys, dataclasses
from datetime import datetime, timezone
import ugence_risk_authority_effect_attestation as ea
from ugence_governance_contracts import ExecutionBusinessOutcome, ExecutionObservation
assert "site-packages" in ea.__file__, ea.__file__
obs = ExecutionObservation(business_outcome=ExecutionBusinessOutcome.SUCCEEDED,
                           observed_parameters={"order_id": "o-1", "amount": "12.50"},
                           final=True, reason="", provider_trace_id="trace-1", fingerprint="fp-1")
T = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)
AS_OF = datetime(2026, 9, 6, 12, 5, tzinfo=timezone.utc)
signer = ea.ReferenceEd25519EffectAttestationSigner(b"\x01" * 32, attester_identity="provider-alpha",
                                                     attester_key_id="provider-key-1",
                                                     attester_role=ea.EffectAttesterRole.EXECUTING_PROVIDER)
anchor = signer.trust_anchor(trust_anchor_set_id="effect-anchors", trust_anchor_set_version="1",
                             effective_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
                             effective_to=datetime(2027, 1, 1, tzinfo=timezone.utc))
att = ea.mint_effect_attestation(obs, signer=signer, tenant_id="tenant-a", attested_at=T)
d = ea.StaticTrustAnchorDirectory([anchor], trust_anchor_set_id="effect-anchors", trust_anchor_set_version="1")
v = ea.Ed25519EffectAttestationVerifier(trust_anchor_resolver=d)
ok = v.verify(attestation=att, expected_role=ea.EffectAttesterRole.EXECUTING_PROVIDER,
              expected_tenant_id="tenant-a", expected_observation=obs, as_of=AS_OF)
assert ok.outcome.name == "VERIFIED" and ok.factual_correctness_established is False
R = ea.EffectAttestationRefusalReason
def refused(**kw):
    args = dict(attestation=att, expected_role=ea.EffectAttesterRole.EXECUTING_PROVIDER,
                expected_tenant_id="tenant-a", expected_observation=obs, as_of=AS_OF)
    args.update(kw); return v.verify(**args).refusal_reason
assert refused(attestation=None) is R.ATTESTATION_ABSENT
assert refused(expected_role=ea.EffectAttesterRole.INDEPENDENT_OBSERVER) is R.ROLE_MISMATCH
assert refused(expected_tenant_id="tenant-b") is R.WRONG_TENANT
assert refused(expected_observation=ExecutionObservation(business_outcome=ExecutionBusinessOutcome.FAILED)) is R.OBSERVATION_MISMATCH
assert refused(attestation=dataclasses.replace(att, signature="ab" * 64)) is R.SIGNATURE_INVALID
assert ea.Ed25519EffectAttestationVerifier(trust_anchor_resolver=ea.DenyAllTrustAnchorDirectory(), production_mode=True).verify(
    attestation=att, expected_role=ea.EffectAttesterRole.EXECUTING_PROVIDER, expected_tenant_id="tenant-a",
    expected_observation=obs, as_of=AS_OF).refusal_reason is R.ANCHOR_UNKNOWN
try:
    ea.Ed25519EffectAttestationVerifier(trust_anchor_resolver=d, production_mode=True); raise SystemExit("static resolver admitted in production")
except ea.EffectAttestationConfigurationError: pass
try:
    ea.mint_effect_attestation(obs, signer=signer, tenant_id="tenant-a", attested_at=T, production_mode=True); raise SystemExit("reference signer admitted in production")
except ea.EffectAttestationSigningBoundaryError: pass
for forbidden in %(forbidden)r:
    try:
        __import__(forbidden); raise SystemExit("forbidden module importable: " + forbidden)
    except ImportError: pass
print(json.dumps({"version": ea.__version__, "maturity": ea.MATURITY, "api": sorted(ea.__all__),
                  "observation_digest": att.observation_digest, "payload_digest": att.signing_payload_digest,
                  "signature": att.signature, "anchor_digest": ea.anchor_record_digest(anchor)}))
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
    work = Path(tempfile.mkdtemp(prefix="effect-attestation-iso-"))
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
        wheel = next(wheelhouse.glob("ugence_risk_authority_effect_attestation-*.whl"))
        members = zipfile.ZipFile(wheel).namelist()
        step("the wheel carries no test, conftest or fixture material",
             not any(m.startswith("tests/") or "/tests/" in m or m.rsplit("/", 1)[-1].startswith("test_") or "conftest" in m or "_fixtures" in m for m in members))
        step("the wheel ships py.typed", "ugence_risk_authority_effect_attestation/py.typed" in members)
        metadata = next(m for m in members if m.endswith("METADATA"))
        requires = [l.split(":", 1)[1].strip() for l in zipfile.ZipFile(wheel).read(metadata).decode().splitlines()
                    if l.startswith("Requires-Dist:") and "extra ==" not in l]
        step("the wheel declares exactly the two ratified dependencies",
             sorted(r.split(">=")[0].split("<")[0].strip() for r in requires) == sorted(
                 ["ugence-governance-contracts", "ugence-trusted-evidence-authority"]), str(requires))

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
             {"ugence-risk-authority-effect-attestation", "ugence-trusted-evidence-authority",
              "ugence-governance-contracts", "cryptography", "pynacl"} <= installed_names, str(sorted(installed_names)))
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
        probe_missing = subprocess.run([str(bpy), "-c", "import ugence_risk_authority_effect_attestation"],
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
             out["observation_digest"] == "sha256:4f33a01727086b55bfb9a1753e1ff2005d35dbd9c523a1885fec1b0d5b54ec94"
             and out["payload_digest"] == "sha256:efe8b45dd3bc750d3f23df74703c920d24458f6db5df5cfffd937b458f744e3b"
             and out["signature"].startswith("86284602d9e63ce04d931db8f411b67e"), json.dumps(out)[:200])
        print("=" * 72)
        print(f"{len(_steps)} steps passed. Phase B is the offline guarantee; phase A reached an index to collect the closure.")
        print("ISOLATED EFFECT-ATTESTATION DISTRIBUTION VERIFIED ✔")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
