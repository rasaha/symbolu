#!/usr/bin/env python3
"""Measured gate-deletion mutation sweep for the effect-attestation verifier.

Each gate below is one load-bearing check, neutralized by a textual
substitution in a copy of the package; the suite runs against the copy and the
result is KILLED (something failed) or SURVIVED. A survivor is reported and
classified, never designed away, and a mutation that no longer applies is an
error, never a silent skip.

Run:  python packages/integration/risk-authority-effect-attestation/scripts/mutation_sweep.py
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

PKG = pathlib.Path(__file__).resolve().parents[1]
REPO = PKG.parents[2]
SRC_REL = pathlib.Path("src") / "ugence_risk_authority_effect_attestation"

#: (id, category, module, description, old, new)
GATES = [
    ("G-01", "input-admission", "verification.py", "absent attestation refuses",
     "        if attestation is None:\n            return refuse(_Reason.ATTESTATION_ABSENT",
     "        if False:\n            return refuse(_Reason.ATTESTATION_ABSENT"),
    ("G-02", "input-admission", "verification.py", "exact attestation type",
     "        if type(attestation) is not EffectAttestation:", "        if False:"),
    ("G-03", "contract-admission", "verification.py", "schema version pinned",
     "        if attestation.schema_version != EFFECT_ATTESTATION_SCHEMA_VERSION:", "        if False:"),
    ("G-04", "contract-admission", "verification.py", "signing domain pinned",
     "        if attestation.signing_domain != EFFECT_ATTESTATION_SIGNING_DOMAIN:", "        if False:"),
    ("G-05", "contract-admission", "verification.py", "algorithm pinned",
     "        if attestation.signature_algorithm != EFFECT_ATTESTATION_SIGNATURE_ALGORITHM:", "        if False:"),
    ("G-06", "contract-admission", "verification.py", "profile pinned",
     "        if attestation.signature_profile != EFFECT_ATTESTATION_SIGNATURE_PROFILE:", "        if False:"),
    ("G-07", "contract-admission", "verification.py", "encoding pinned",
     "        if attestation.signature_encoding != EFFECT_ATTESTATION_SIGNATURE_ENCODING:", "        if False:"),
    ("G-08", "reconciliation", "verification.py", "role must match the caller's",
     "        if attestation.attester_role is not role:", "        if False:"),
    ("G-09", "reconciliation", "verification.py", "tenant must match the caller's",
     "        if attestation.tenant_id != tenant:", "        if False:"),
    ("G-10", "reconciliation", "verification.py", "observation digest must match the caller's",
     "        if attestation.observation_digest != expected_digest:", "        if False:"),
    ("G-11", "anchor-resolution", "verification.py", "resolution exact type",
     "        if type(resolution) is not TrustAnchorResolution:", "        if False:"),
    ("G-12", "anchor-resolution", "verification.py", "resolution answers the asked coordinate",
     "        if resolution.coordinate != coordinate:", "        if False:"),
    ("G-13", "anchor-resolution", "verification.py", "anchor exact type",
     "        if type(anchor) is not TrustAnchorRecord:", "        if False:"),
    ("G-14", "anchor-resolution", "verification.py", "record cross-checked against the coordinate",
     "            anchor.authority_id != coordinate.authority_id\n            or anchor.key_id != coordinate.key_id\n            or anchor.capability is not coordinate.capability",
     "            False"),
    ("G-15", "role-separation", "verification.py", "capability must be the role's",
     "        if anchor.capability is not capability_for_role(role):", "        if False:"),
    ("G-16", "lifecycle", "verification.py", "lifecycle refusal is applied",
     "        if lifecycle is not None:", "        if False:"),
    ("G-17", "lifecycle", "verification.py", "expected anchor revision is compared",
     "        if expected_anchor_record_digest is not None and revision != expected_anchor_record_digest:",
     "        if False:"),
    ("G-18", "key-admission", "verification.py", "a key refused at admission is a refusal, not a pass-through",
     "        except Exception as exc:  # noqa: BLE001 - a key that fails the point check\n            return refuse(_Reason.KEY_MATERIAL_INVALID,\n                          f\"the anchor's public key was refused at admission: {type(exc).__name__}\",\n                          anchor_digest=revision)",
     "        except Exception as exc:  # noqa: BLE001 - a key that fails the point check\n            raise"),
    ("G-19", "payload", "verification.py", "recomputed payload must equal the claimed bytes",
     "        if recomputed != attestation.signed_bytes():", "        if False:"),
    ("G-20", "signature", "verification.py", "the signature must verify",
     "        if key.verify(recomputed, signature) is not True:", "        if False:"),
    ("G-21", "role-separation", "roles.py", "provider role maps to the provider capability",
     "            EffectAttesterRole.EXECUTING_PROVIDER: (\n                TrustAnchorCapability.EFFECT_ATTESTATION_EXECUTING_PROVIDER\n            ),",
     "            EffectAttesterRole.EXECUTING_PROVIDER: (\n                TrustAnchorCapability.EFFECT_ATTESTATION_INDEPENDENT_OBSERVER\n            ),"),
    ("G-22", "production-posture", "trust.py", "reference resolver refused in production",
     "    if isinstance(resolver, REFERENCE_GRADE_RESOLVERS):", "    if False:"),
    ("G-23", "production-posture", "signing.py", "reference signer refused in production",
     "    if production_mode and (", "    if False and ("),
    ("G-24", "frame", "canonical.py", "the domain length prefix",
     "    return len(tag).to_bytes(_LENGTH_PREFIX_BYTES, \"big\") + tag + canonical_bytes(value)",
     "    return tag + canonical_bytes(value)"),
    ("G-25", "frame", "canonical.py", "sorted keys in the canonical form",
     "        sort_keys=True,", "        sort_keys=False,"),
    ("G-26", "canonical", "canonical.py", "non-NFC text refused",
     "    if unicodedata.normalize(\"NFC\", value) != value:", "    if False:"),
    ("G-27", "canonical", "canonical.py", "str subclasses refused",
     "    if type(value) is not str:\n        raise _Error(\n            f\"{name} must be exactly a str",
     "    if not isinstance(value, str):\n        raise _Error(\n            f\"{name} must be exactly a str"),
    ("G-28", "no-factual-claim", "verification.py", "factual correctness never established",
     "        return False\n\n\n@runtime_checkable", "        return self.outcome is _Outcome.VERIFIED\n\n\n@runtime_checkable"),
    ("G-29", "input-admission", "verification.py", "aware instant required at the seam",
     "        instant = require_aware_utc(\"as_of\", as_of)", "        instant = as_of"),
    ("G-30", "result-shape", "verification.py", "VERIFIED must bind the anchor revision",
     "            if not is_canonical_digest(self.anchor_record_digest):\n                raise _Error(\"a VERIFIED result must bind the anchor revision it trusted\")",
     "            pass"),
]

#: Survivors that are understood. Each entry is a classification, not an excuse.
#: EQUIVALENT_DEFENSE_IN_DEPTH: an earlier or outer check makes the mutated branch
#: unreachable, so no observable behaviour changes; the gate stays in the source
#: because the check it duplicates lives in another module or another object.
CLASSIFIED_SURVIVORS: dict = {
    "G-12": "EQUIVALENT_DEFENSE_IN_DEPTH: TEA's TrustAnchorResolution refuses at construction "
            "any anchor whose coordinate differs from the resolution's, and G-14 re-checks the "
            "record against the asked coordinate; a resolution answering another coordinate "
            "therefore cannot carry a record that passes G-14. Kept as the package's own check.",
    "G-15": "EQUIVALENT_DEFENSE_IN_DEPTH: the coordinate is built from capability_for_role(role) "
            "and G-14 requires anchor.capability is coordinate.capability, so the role-capability "
            "comparison is already decided one line earlier. Kept so SE-2 is stated at the seam.",
    "G-19": "EQUIVALENT_DEFENSE_IN_DEPTH: G-10 has already required the caller's observation "
            "digest to equal the attestation's, the payload is recomputed from the same pinned "
            "fields, and canonicalization is deterministic; the recomputed frame can differ from "
            "signed_bytes() only under a SHA-256 collision, and G-20 still verifies over the "
            "recomputed frame, never the claimed one. Kept as the byte-for-byte statement of SE-3.",
}


def _run_suite(working: pathlib.Path) -> tuple:
    env = dict(os.environ, UGENCE_REPO_ROOT=str(REPO))
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-q", "-x", "-o", "addopts=", "-p", "no:cacheprovider"],
        cwd=str(working), env=env, capture_output=True, text=True,
    )
    if result.returncode == 0:
        return True, ""
    lines = [l for l in result.stdout.splitlines() if l.startswith("FAILED") or l.startswith("ERROR")]
    if lines:
        return False, lines[0]
    tail = result.stdout.strip().splitlines()
    return False, tail[-1] if tail else "no output"


def main() -> int:
    print(f"gates inventoried: {len(GATES)}")
    work = pathlib.Path(tempfile.mkdtemp(prefix="effect-attestation-mutants-"))
    pristine = work / "pristine"
    working = work / "working"
    ledger = []
    try:
        shutil.copytree(PKG, pristine, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "build", "*.egg-info"))
        shutil.copytree(pristine, working)
        ok, detail = _run_suite(working)
        if not ok:
            print(f"BASELINE FAILED on the pristine tree: {detail}")
            return 1
        killed = survived = 0
        for gate_id, category, module, description, old, new in GATES:
            shutil.rmtree(working)
            shutil.copytree(pristine, working)
            target = working / SRC_REL / module
            text = target.read_text(encoding="utf-8")
            if text.count(old) != 1:
                print(f"ERROR {gate_id}: mutation target appears {text.count(old)} times in {module}")
                return 1
            target.write_text(text.replace(old, new), encoding="utf-8")
            ok, detail = _run_suite(working)
            status = "SURVIVED" if ok else "KILLED"
            if ok:
                survived += 1
            else:
                killed += 1
            ledger.append({"gate": gate_id, "category": category, "module": module,
                           "description": description, "status": status, "first_failure": detail,
                           "classification": CLASSIFIED_SURVIVORS.get(gate_id)})
            print(f"{'ok  ' if not ok else 'SURV'}  {gate_id} {status:8s} {category:20s} {detail[:70]}")
        print(f"TOTALS  inventoried {len(GATES)}  killed {killed}  survived {survived}")
        unclassified = [r["gate"] for r in ledger if r["status"] == "SURVIVED" and not r["classification"]]
        (PKG / "mutation_ledger.json").write_text(
            json.dumps({"gates_inventoried": len(GATES), "killed": killed, "survived": survived,
                        "ledger": ledger}, indent=2) + "\n", encoding="utf-8")
        if unclassified:
            print(f"UNCLASSIFIED SURVIVORS: {unclassified}")
            return 1
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
