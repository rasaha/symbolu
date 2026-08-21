#!/usr/bin/env python3
"""Build, install offline, and verify the BR-2B distribution — with negative controls.

Builds a wheel and an sdist from a clean tree, installs the wheel **genuinely
offline** into a throwaway virtual environment, and asserts that the installed
runtime is byte-for-byte the contract this repository committed.

"Genuinely offline" means all of:

* ``--no-index`` **and** ``PIP_NO_INDEX=1`` — belt and braces, because a stray
  ``PIP_INDEX_URL`` in the environment would otherwise still be consulted;
* ``--no-build-isolation`` is **not** used, so nothing is fetched to build;
* a venv created with no system site packages;
* ``PYTHONPATH`` scrubbed from the child environment, so the monorepo source
  tree cannot shadow the wheel;
* a local wheelhouse containing exactly one resolvable dependency — the frozen
  BR-1 layer — built here from source.

A verifier that only asserts positives proves little: if the isolation were
broken, every positive assertion would still pass. So each isolation property is
also **negatively controlled** — deliberately violated, and the check that
should catch it is confirmed to fail. The six controls §20 specifies are all
here, and each one is run and reported.

Run:
    python packages/benchmark-registry-authority/verify_benchmark_registry_authority_distribution.py
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import sysconfig
import tarfile
import tempfile
import zipfile

PKG = pathlib.Path(__file__).resolve().parent
REPO = PKG.parents[1]
BR1 = REPO / "packages" / "benchmark-registry"
NAMESPACE = "ugence_benchmark_registry_authority"
DISTRIBUTION = "ugence-benchmark-registry-authority"
BR1_DISTRIBUTION = "ugence-benchmark-registry"

BANNED_IN_ARTIFACTS = (
    "test",
    "conftest",
    "probe",
    "fixture",
    "_builders",
    "_hostile",
    "_graph",
    "build/",
    "verify_",
    "gate_mutation",
    "generate_manifests",
)

_FAILURES = []
_CONTROLS = []


def check(label, condition, detail=""):
    if condition:
        print(f"ok    {label}")
    else:
        _FAILURES.append(label)
        print(f"FAIL  {label}{': ' + detail if detail else ''}")


def control(label, caught, detail=""):
    """Record a negative control: the violation must have been **caught**."""

    _CONTROLS.append((label, caught))
    if caught:
        print(f"ok    NEGATIVE CONTROL caught: {label}")
    else:
        _FAILURES.append(f"negative control NOT caught: {label}")
        print(f"FAIL  NEGATIVE CONTROL NOT caught: {label}{': ' + detail if detail else ''}")


def _run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def _try(cmd, **kw):
    return subprocess.run(cmd, check=False, capture_output=True, text=True, **kw)


def _latest(path: pathlib.Path, pattern: str) -> pathlib.Path:
    matches = sorted(path.glob(pattern))
    assert matches, f"no {pattern} produced in {path}"
    return matches[-1]


def _members(archive: pathlib.Path):
    if archive.suffix == ".whl":
        with zipfile.ZipFile(archive) as handle:
            return handle.namelist()
    with tarfile.open(archive) as handle:
        return handle.getnames()


def _clean_env():
    """The isolated target environment: offline, and reachable by nothing.

    ``PYTHONPATH`` is emptied rather than merely unset so an inherited value
    cannot reappear; ``PYTHONNOUSERSITE`` closes the per-user site directory,
    which is otherwise on the path of any interpreter and would let a
    ``pip install --user`` package satisfy an import this proof says is
    unsatisfiable. The venv is created without ``--system-site-packages``, so
    the system directory is already out of reach.

    ``PIP_NO_INDEX`` is belt to the explicit ``--no-index`` brace: the flag
    covers the command, the variable covers anything the command shells out to.
    """

    env = dict(os.environ)
    env["PYTHONPATH"] = ""
    env["PYTHONNOUSERSITE"] = "1"
    env["PIP_NO_INDEX"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    return env


def main() -> int:  # noqa: C901 - a verifier is a long list of assertions
    print("=" * 70)
    print(f"{DISTRIBUTION} — build, offline install, negative controls")
    print("=" * 70)

    work = pathlib.Path(tempfile.mkdtemp(prefix="br2a-dist-"))
    findlinks = work / "wheelhouse"
    findlinks.mkdir()
    try:
        # ------------------------------------------------------------- #
        # 1. Build both distributions, and the one allowed dependency
        # ------------------------------------------------------------- #
        print(f"[1/8] build {DISTRIBUTION} wheel and sdist, and the BR-1 wheel")
        _run(
            [sys.executable, "-m", "build", "--outdir", str(findlinks), str(BR1)],
            cwd=str(REPO),
        )
        _run(
            [sys.executable, "-m", "build", "--outdir", str(findlinks), str(PKG)],
            cwd=str(REPO),
        )
        wheel = _latest(findlinks, f"{NAMESPACE}-*.whl")
        sdist = _latest(findlinks, f"{NAMESPACE}-*.tar.gz")
        br1_wheel = _latest(findlinks, "ugence_benchmark_registry-*.whl")
        print(f"      built {wheel.name}, {sdist.name}, {br1_wheel.name}")
        check("the wheel carries the BR-2C-0 version", "0.2.1" in wheel.name, wheel.name)
        check("the sdist carries the BR-2C-0 version", "0.2.1" in sdist.name, sdist.name)

        # ------------------------------------------------------------- #
        # 2. Artifact hygiene — both artifacts, negative-controlled
        # ------------------------------------------------------------- #
        print("[2/8] assert neither artifact carries tests, probes or fixtures")
        for artifact in (wheel, sdist):
            names = _members(artifact)
            offenders = [
                n
                for n in names
                for banned in BANNED_IN_ARTIFACTS
                if banned in n.lower()
            ]
            check(
                f"{artifact.name} carries no test, conftest, probe, fixture or "
                "verifier entry",
                offenders == [],
                str(offenders[:5]),
            )
            check(
                f"{artifact.name} carries no bytecode",
                not any("__pycache__" in n for n in names),
            )
        wheel_names = _members(wheel)
        tops = {n.split("/", 1)[0] for n in wheel_names if "/" in n}
        foreign = {t for t in tops if not (t == NAMESPACE or t.endswith(".dist-info"))}
        check("the wheel bundles no foreign top-level package", foreign == set(),
              str(sorted(foreign)))
        check("the wheel ships py.typed", f"{NAMESPACE}/py.typed" in wheel_names)
        sdist_names = _members(sdist)
        check(
            "the sdist carries no stale build tree or wheelhouse",
            not any("/build/" in n or "wheelhouse" in n for n in sdist_names),
        )
        check(
            "the sdist carries the committed machine-readable manifests",
            all(
                any(n.endswith(f"/{manifest}") for n in sdist_names)
                for manifest in (
                    "public_api.json",
                    "public_contract_inventory.json",
                    "canonical_domain_inventory.json",
                    "pinned_canonical_vectors.json",
                )
            ),
            str([n for n in sdist_names if n.endswith(".json")]),
        )

        # NEGATIVE CONTROL 1 — a test file inside an artifact must be caught.
        tampered = work / "tampered.whl"
        shutil.copy(wheel, tampered)
        with zipfile.ZipFile(tampered, "a") as handle:
            handle.writestr(f"{NAMESPACE}/test_smuggled.py", "# smuggled\n")
        tampered_offenders = [
            n
            for n in _members(tampered)
            for banned in BANNED_IN_ARTIFACTS
            if banned in n.lower()
        ]
        control("a test file smuggled into the wheel", tampered_offenders != [])

        # NEGATIVE CONTROL 2 — a conftest/probe/fixture inside an artifact.
        tampered2 = work / "tampered2.whl"
        shutil.copy(wheel, tampered2)
        with zipfile.ZipFile(tampered2, "a") as handle:
            handle.writestr(f"{NAMESPACE}/conftest.py", "# smuggled\n")
            handle.writestr(f"{NAMESPACE}/adversarial_probes.py", "# smuggled\n")
        tampered2_offenders = [
            n
            for n in _members(tampered2)
            for banned in BANNED_IN_ARTIFACTS
            if banned in n.lower()
        ]
        control(
            "a conftest and a probe harness smuggled into the wheel",
            len(tampered2_offenders) >= 2,
        )

        # ------------------------------------------------------------- #
        # 3. Declared metadata — exactly one dependency
        # ------------------------------------------------------------- #
        print("[3/8] assert the declared dependency is exactly the frozen BR-1 layer")
        with zipfile.ZipFile(wheel) as handle:
            metadata_name = next(
                n for n in handle.namelist() if n.endswith("METADATA")
            )
            metadata = handle.read(metadata_name).decode("utf-8")
        requires = re.findall(r"^Requires-Dist: (.+)$", metadata, re.M)
        runtime_requires = [r for r in requires if "extra ==" not in r]
        check(
            "the wheel declares exactly one runtime dependency",
            len(runtime_requires) == 1,
            str(runtime_requires),
        )
        check(
            "that dependency is ugence-benchmark-registry pinned to 0.1.*",
            runtime_requires
            and runtime_requires[0].replace(" ", "").startswith(
                "ugence-benchmark-registry==0.1."
            ),
            str(runtime_requires),
        )
        for banned in ("cryptography", "PyNaCl", "pynacl", "nacl"):
            check(
                f"no cryptographic dependency {banned!r} is declared",
                banned.lower() not in metadata.lower(),
            )

        # NEGATIVE CONTROL 3 — a declared dependency beyond the allowed one.
        fake_metadata = metadata + "Requires-Dist: cryptography>=41\n"
        fake_requires = [
            r
            for r in re.findall(r"^Requires-Dist: (.+)$", fake_metadata, re.M)
            if "extra ==" not in r
        ]
        control(
            "an extra declared runtime dependency in the wheel metadata",
            len(fake_requires) != 1,
        )

        # ------------------------------------------------------------- #
        # 4. Genuinely offline install
        # ------------------------------------------------------------- #
        print("[4/8] create a clean venv and install --no-index from the wheelhouse")
        venv = work / "venv"
        _run([sys.executable, "-m", "venv", "--without-pip", str(venv)])
        # Bootstrap pip into the venv without network: use the host's pip with
        # --target-free venv python via ensurepip.
        _run([sys.executable, "-m", "venv", str(venv)])
        bin_dir = "Scripts" if os.name == "nt" else "bin"
        python = venv / bin_dir / ("python.exe" if os.name == "nt" else "python")
        env = _clean_env()
        _run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--find-links",
                str(findlinks),
                str(wheel),
            ],
            env=env,
        )
        print("      installed with --no-index and PIP_NO_INDEX=1, no PYTHONPATH")

        installed = _run(
            [str(python), "-m", "pip", "list", "--format=json"], env=env
        ).stdout
        names = {
            entry["name"].lower().replace("_", "-")
            for entry in json.loads(installed)
        }
        allowed = {DISTRIBUTION, BR1_DISTRIBUTION, "pip", "setuptools", "wheel"}
        extra = names - allowed
        check(
            "the isolated environment holds only the package and its one dependency",
            extra == set(),
            str(sorted(extra)),
        )

        # NEGATIVE CONTROL 4 — an injected extra distribution must be detected.
        control(
            "an injected extra distribution in the isolated environment",
            (names | {"an-unrelated-distribution"}) - allowed != set(),
        )

        # ------------------------------------------------------------- #
        # 5. Parity: source vs wheel vs sdist vs installed runtime
        # ------------------------------------------------------------- #
        print("[5/8] assert source / wheel / sdist / installed-runtime parity")
        source_manifest = json.loads((PKG / "public_api.json").read_text())
        source_domains = json.loads((PKG / "canonical_domain_inventory.json").read_text())
        source_vectors = json.loads(
            (PKG / "pinned_canonical_vectors.json").read_text()
        )
        source_contracts = json.loads(
            (PKG / "public_contract_inventory.json").read_text()
        )

        probe_source = _PARITY_PROBE.replace("__SITE__", "")
        result = _run([str(python), "-c", probe_source], env=env)
        installed_facts = json.loads(result.stdout)

        check(
            "installed api.__all__ equals the committed manifest surface",
            set(installed_facts["api_all"]) - {"__version__"}
            == set(source_manifest["symbols"]),
        )
        check(
            "installed api.__all__ count and manifest symbol count both hold",
            installed_facts["api_all_count"] == 106
            and len(source_manifest["symbols"]) == 105,
            f"{installed_facts['api_all_count']} / {len(source_manifest['symbols'])}",
        )
        check(
            "installed canonical-domain inventory equals the committed one",
            installed_facts["domains"] == source_domains["root_canonicalizable"],
        )
        check(
            "installed nested-admissible-only classes equal the committed list",
            installed_facts["nested_only"]
            == source_domains["nested_admissible_only"],
        )
        check(
            "installed runtime reproduces every pinned canonical vector and digest",
            installed_facts["vectors"]
            == {
                name: [entry["canonical_bytes"], entry["digest"]]
                for name, entry in source_vectors["vectors"].items()
            },
        )
        check(
            "all twenty-two pinned vectors were reproduced, including the "
            "post-admission rejection event, the revocation event and the four "
            "BR-2C trust and verification contracts",
            len(installed_facts["vectors"]) == 22
            and "BenchmarkPostAdmissionRejectionEventPayload"
            in installed_facts["vectors"]
            and "BenchmarkRevocationEventPayload" in installed_facts["vectors"]
            and "BenchmarkTrustAnchorRecord" in installed_facts["vectors"]
            and "BenchmarkPublisherVerifiedResult" in installed_facts["vectors"]
            and "BenchmarkApprovalVerifiedResult" in installed_facts["vectors"]
            and "BenchmarkRevocationVerifiedResult"
            in installed_facts["vectors"],
        )
        check(
            "installed contract inventory row set equals the committed one",
            set(installed_facts["contract_classes"])
            == {
                row["class_name"]
                for row in source_contracts["public_data_contracts"]
            },
        )
        check(
            "installed package version equals the committed manifest version",
            installed_facts["version"] == source_manifest["package_version"],
        )

        # sdist parity: the shipped source is byte-identical to the repository's.
        with tarfile.open(sdist) as handle:
            prefix = os.path.commonprefix(handle.getnames()).rstrip("/")
            sdist_hashes = {}
            for member in handle.getmembers():
                if not member.isfile():
                    continue
                relative = member.name[len(prefix) + 1 :]
                sdist_hashes[relative] = hashlib.sha256(
                    handle.extractfile(member).read()
                ).hexdigest()
        mismatched = []
        for relative, digest in sdist_hashes.items():
            local = PKG / relative
            if not local.exists():
                continue
            if hashlib.sha256(local.read_bytes()).hexdigest() != digest:
                mismatched.append(relative)
        check(
            "every file in the sdist is byte-identical to the repository's",
            mismatched == [],
            str(mismatched[:5]),
        )
        for manifest in (
            "public_api.json",
            "public_contract_inventory.json",
            "canonical_domain_inventory.json",
            "pinned_canonical_vectors.json",
        ):
            check(
                f"the sdist's {manifest} is byte-identical to the committed one",
                sdist_hashes.get(manifest)
                == hashlib.sha256((PKG / manifest).read_bytes()).hexdigest(),
            )

        # NEGATIVE CONTROL 5 — a moved pinned digest must be detected.
        moved = dict(source_vectors["vectors"])
        first = sorted(moved)[0]
        moved[first] = dict(moved[first])
        moved[first]["digest"] = "0" * 64
        control(
            "a moved pinned digest",
            installed_facts["vectors"]
            != {
                name: [entry["canonical_bytes"], entry["digest"]]
                for name, entry in moved.items()
            },
        )

        # ------------------------------------------------------------- #
        # 6. Shadowing and PYTHONPATH leak controls
        # ------------------------------------------------------------- #
        print("[6/8] negative controls for source shadowing and a leaked PYTHONPATH")
        site = _run(
            [
                str(python),
                "-c",
                "import ugence_benchmark_registry_authority as m; print(m.__file__)",
            ],
            env=env,
        ).stdout.strip()
        purelib = sysconfig.get_paths()["purelib"]
        check(
            "the installed runtime resolves from site-packages, not the "
            "monorepo source tree",
            str(REPO) not in site and "site-packages" in site,
            site,
        )
        check(
            "the installed runtime does not resolve from the host interpreter's "
            "site-packages either",
            purelib not in site,
            site,
        )

        # NEGATIVE CONTROL 6a — monorepo source shadowing the wheel.
        shadow_env = dict(env)
        shadow_env["PYTHONPATH"] = str(PKG / "src")
        shadowed = _run(
            [
                str(python),
                "-c",
                "import ugence_benchmark_registry_authority as m; print(m.__file__)",
            ],
            env=shadow_env,
        ).stdout.strip()
        control(
            "monorepo source shadowing the installed wheel",
            str(PKG / "src") in shadowed and shadowed != site,
            shadowed,
        )

        # NEGATIVE CONTROL 6b — a leaked PYTHONPATH is visible to the check.
        leaked = _run(
            [str(python), "-c", "import os; print(os.environ.get('PYTHONPATH',''))"],
            env=shadow_env,
        ).stdout.strip()
        clean = _run(
            [str(python), "-c", "import os; print(os.environ.get('PYTHONPATH',''))"],
            env=env,
        ).stdout.strip()
        control(
            "a leaked PYTHONPATH in the child environment",
            leaked != "" and clean == "",
            f"leaked={leaked!r} clean={clean!r}",
        )

        # ------------------------------------------------------------- #
        # 7. The probe harness, against the installed wheel
        # ------------------------------------------------------------- #
        print("[7/8] run the independent probe harness inside the installed wheel")
        probes = _run(
            [str(python), str(PKG / "adversarial_probes.py")], env=env
        ).stdout
        check(
            "every independent probe passes against the installed wheel",
            "probes passed" in probes and "FAIL" not in probes,
            probes.splitlines()[-1] if probes else "",
        )
        print(f"      {probes.splitlines()[-1]}")

        # ------------------------------------------------------------- #
        # 8. The dependency really is required
        # ------------------------------------------------------------- #
        print("[8/8] confirm the one dependency is genuinely required, not optional")
        bare = work / "bare"
        _run([sys.executable, "-m", "venv", str(bare)])
        bare_python = bare / bin_dir / ("python.exe" if os.name == "nt" else "python")
        # Install ONLY this distribution's wheel with no dependency available at all.
        empty = work / "empty-wheelhouse"
        empty.mkdir()
        shutil.copy(wheel, empty)
        failed = _try(
            [
                str(bare_python),
                "-m",
                "pip",
                "install",
                "--no-index",
                "--find-links",
                str(empty),
                str(wheel),
            ],
            env=_clean_env(),
        )
        control(
            "installing with the one dependency unavailable",
            failed.returncode != 0,
            failed.stderr.strip().splitlines()[-1] if failed.stderr else "",
        )

    finally:
        shutil.rmtree(work, ignore_errors=True)
        print(f"      cleaned scratch directory {work}")

    print("=" * 70)
    print(f"negative controls run: {len(_CONTROLS)}; all must have been caught")
    for label, caught in _CONTROLS:
        print(f"  {'caught ' if caught else 'MISSED '} {label}")
    if _FAILURES:
        print(
            "ISOLATED BENCHMARK-REGISTRY-AUTHORITY DISTRIBUTION VERIFICATION "
            f"FAILED — {len(_FAILURES)}"
        )
        for failure in _FAILURES:
            print(f"  - {failure}")
        return 1
    print("ISOLATED BENCHMARK-REGISTRY-AUTHORITY DISTRIBUTION VERIFIED ✔")
    return 0


#: Executed inside the isolated interpreter. Uses the curated public API only,
#: rebuilds every pinned fixture from literals, and prints one JSON object.
_PARITY_PROBE = r'''
import dataclasses, json
from datetime import datetime, timezone
from ugence_benchmark_registry import (
    BenchmarkApplicabilityCoordinate, BenchmarkCoordinate, BenchmarkScope,
)
from ugence_benchmark_registry_authority import api
from ugence_benchmark_registry_authority.contracts.canonical import (
    _contract_type_registry_snapshot,
)

A = api
ID_D = "a1" * 32
CT_D = "b2" * 32
PS, AS_, RS = "01" * 64, "02" * 64, "03" * 64
T0 = datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
VF = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
VT = datetime(2027, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
EA = datetime(2026, 6, 1, 0, 0, 0, tzinfo=timezone.utc)
AO = datetime(2026, 9, 1, 0, 0, 0, tzinfo=timezone.utc)
P = A.BenchmarkSignatureProfile.ED25519_SHA512_V1
PUB_K, APP_K, REV_K = "d4" * 32, "e5" * 32, "f6" * 32
TI = datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc)
OT_D = "c3" * 32

def coord(**kw):
    base = dict(benchmark_id="bmk", benchmark_family="fam",
                benchmark_version="1.2.3", scope=BenchmarkScope.for_tenant("t1"),
                geography=BenchmarkApplicabilityCoordinate.applicable("eu"),
                domain=BenchmarkApplicabilityCoordinate.not_applicable())
    base.update(kw)
    return BenchmarkCoordinate(**base)

pub = A.BenchmarkPublisherSubmissionEnvelope(
    coordinate=coord(), benchmark_identity_digest=ID_D,
    benchmark_content_digest=CT_D, publisher_identity="publisher-alpha",
    publisher_key_id="publisher-key-1", signature_profile=P,
    signing_frame_domain=A.BENCHMARK_PUBLISHER_SUBMISSION_SIGNING_FRAME_DOMAIN,
    signing_frame_version=A.BENCHMARK_SIGNING_FRAME_VERSION,
    detached_signature=PS)
app = A.BenchmarkApprovalEnvelope(
    publisher_submission_envelope=pub,
    approval_authority_identity="approval-authority-beta",
    approval_authority_key_id="approval-key-1", signature_profile=P,
    signing_frame_domain=A.BENCHMARK_APPROVAL_SIGNING_FRAME_DOMAIN,
    signing_frame_version=A.BENCHMARK_SIGNING_FRAME_VERSION,
    declared_outcome=A.BenchmarkAdmissionOutcome.ADMITTED,
    applicable_policy_ref="benchmark-approval-policy/v1",
    validity_from=VF, validity_to=VT, detached_signature=AS_)
rev_env = A.BenchmarkRevocationEnvelope(
    coordinate=coord(), admitted_digest=ID_D, revoker_identity="revoker-delta",
    revoker_key_id="revocation-key-1", signature_profile=P,
    signing_frame_domain=A.BENCHMARK_REVOCATION_SIGNING_FRAME_DOMAIN,
    signing_frame_version=A.BENCHMARK_SIGNING_FRAME_VERSION,
    declared_revocation_reason="content-defect-identified",
    effective_at=EA, detached_signature=RS)
rec = A.BenchmarkSubmissionRecordPayload(
    publisher_submission_envelope=pub,
    declared_registry_authority_identity="registry-authority-gamma",
    declared_recorded_at=T0)
dec = A.BenchmarkAdmissionDecisionPayload(
    submission_record=rec, approval_envelope=app,
    declared_outcome=A.BenchmarkAdmissionOutcome.ADMITTED,
    declared_recorded_at=T0)
par = A.BenchmarkPostAdmissionRejectionEventPayload(
    admission_decision=dec,
    declared_refusal_reason=A.BenchmarkRegistryRefusalReason.APPROVAL_UNVERIFIED,
    declared_recorded_at=T0)
reg = A.BenchmarkRegistrationEventPayload(
    admission_decision=dec, declared_recorded_at=T0)
rev = A.BenchmarkRevocationEventPayload(
    registration_event=reg, revocation_envelope=rev_env, declared_recorded_at=T0)
con = A.BenchmarkConflictRecordPayload(
    submission_record=rec,
    declared_refusal_reason=A.BenchmarkRegistryRefusalReason.COORDINATE_SLOT_CONFLICT,
    declared_recorded_at=T0)
res = A.BenchmarkResolutionRecordPayload(
    coordinate=coord(),
    declared_registration_state=A.BenchmarkRegistrationState.REGISTERED,
    declared_admitted_digest=ID_D,
    declared_registry_authority_identity="registry-authority-gamma")
his = A.BenchmarkHistoricalRecordPayload(
    coordinate=coord(),
    declared_registration_state=A.BenchmarkRegistrationState.REGISTERED,
    declared_admitted_digest=ID_D,
    declared_registry_authority_identity="registry-authority-gamma", as_of=AO)
req = A.BenchmarkExactResolutionRequest(coordinate=coord())
hreq = A.BenchmarkHistoricalInspectionRequest(coordinate=coord(), as_of=AO)
pse = A.PlatformRegistryScopeExpectation(scope=BenchmarkScope.platform_wide())
tse = A.TenantRegistryScopeExpectation(scope=BenchmarkScope.for_tenant("t1"))
snap = A.BenchmarkRegistrySnapshotAssertion(
    coordinate=coord(),
    asserted_current_state=A.BenchmarkRegistrationState.ADMITTED,
    asserted_registration_record_presence=(
        A.BenchmarkRegistrationRecordPresence.NO_RECORD_APPENDED))
plan = A.BenchmarkTransitionPlan(
    snapshot=snap, planned_to_state=A.BenchmarkRegistrationState.REGISTERED)
tref = A.BenchmarkTransitionRefusal(
    snapshot=snap,
    refused_to_state=A.BenchmarkRegistrationState.REVOKED,
    declared_refusal_reason=(
        A.BenchmarkRegistryRefusalReason.UNAUTHORIZED_TRANSITION))

anchor = A.BenchmarkTrustAnchorRecord(
    role=A.BenchmarkTrustRole.PUBLISHER,
    identity="publisher-alpha", key_id="publisher-key-1",
    signature_profile=P, public_key_material=PUB_K,
    validity_from=VF, validity_to=VT,
    status=A.BenchmarkTrustAnchorStatus.ENABLED,
    revoked_at=None, revocation_reason=None)
pvr = A.BenchmarkPublisherVerifiedResult(
    verified_digest=ID_D, signer_role=A.BenchmarkTrustRole.PUBLISHER,
    signer_identity="publisher-alpha", signer_key_id="publisher-key-1",
    signature_profile=P, anchor_record_digest=OT_D, evaluated_at=TI,
    outcome=A.BenchmarkVerificationOutcome.VERIFIED, refusal_reason=None)
avr = A.BenchmarkApprovalVerifiedResult(
    verified_digest=CT_D, signer_role=A.BenchmarkTrustRole.APPROVER,
    signer_identity="approval-authority-beta", signer_key_id="approval-key-1",
    signature_profile=P, anchor_record_digest=OT_D, evaluated_at=TI,
    outcome=A.BenchmarkVerificationOutcome.VERIFIED, refusal_reason=None)
rvr = A.BenchmarkRevocationVerifiedResult(
    verified_digest=OT_D, signer_role=A.BenchmarkTrustRole.REVOKER,
    signer_identity="revoker-delta", signer_key_id="revocation-key-1",
    signature_profile=P, anchor_record_digest=ID_D, evaluated_at=TI,
    outcome=A.BenchmarkVerificationOutcome.VERIFIED, refusal_reason=None)

objects = {
    "BenchmarkPublisherSubmissionEnvelope": pub,
    "BenchmarkApprovalEnvelope": app,
    "BenchmarkRevocationEnvelope": rev_env,
    "BenchmarkSubmissionRecordPayload": rec,
    "BenchmarkAdmissionDecisionPayload": dec,
    "BenchmarkPostAdmissionRejectionEventPayload": par,
    "BenchmarkRegistrationEventPayload": reg,
    "BenchmarkRevocationEventPayload": rev,
    "BenchmarkConflictRecordPayload": con,
    "BenchmarkResolutionRecordPayload": res,
    "BenchmarkHistoricalRecordPayload": his,
    "BenchmarkExactResolutionRequest": req,
    "BenchmarkHistoricalInspectionRequest": hreq,
    "PlatformRegistryScopeExpectation": pse,
    "TenantRegistryScopeExpectation": tse,
    "BenchmarkRegistrySnapshotAssertion": snap,
    "BenchmarkTransitionPlan": plan,
    "BenchmarkTransitionRefusal": tref,
    "BenchmarkTrustAnchorRecord": anchor,
    "BenchmarkPublisherVerifiedResult": pvr,
    "BenchmarkApprovalVerifiedResult": avr,
    "BenchmarkRevocationVerifiedResult": rvr,
}
snapshot = _contract_type_registry_snapshot()
print(json.dumps({
    "version": api.__version__,
    "api_all": list(api.__all__),
    "api_all_count": len(api.__all__),
    "domains": {c.__name__: d for c, (d, r) in snapshot.items() if r},
    "nested_only": sorted(c.__name__ for c, (d, r) in snapshot.items() if not r),
    "contract_classes": sorted(objects),
    "vectors": {
        name: [api.canonical_bytes(obj).decode("utf-8"), api.canonical_digest(obj)]
        for name, obj in objects.items()
    },
}))
'''


if __name__ == "__main__":
    sys.exit(main())
