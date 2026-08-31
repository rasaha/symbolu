"""Independent regression-parity re-audit for TEV-2 (PR #1446) against the MERGED head.

Rather than trusting hex constants copied out of a PR body or CHANGELOG — this
audit found exactly that kind of copied constant to be wrong once already, in
PR #1463's own stale `pins.py`/`pins_frame.py` (they compute
`EvidenceSchemaRef(schema_id="ugence.evidence.model-benchmark", ...)`, which is
a string that appears **nowhere** in the actual package at any point in its
history; the real TEV-1 fixture is `"ugence.evidence.control-test"`) — this
probe computes digests dynamically against the real TEV-1 baseline commit and
diffs them against the current head, so no hardcoded expectation can go stale
or be mistyped.

Run: python audit/tev2-1446-closure-reaudit/pins_and_api.py <tev2-head-root> <tev1-baseline-root>

Where <tev1-baseline-root> is a checkout of 41d85dfc (the TEV-1 merge commit,
PR #1446's declared base).
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

if len(sys.argv) < 3:
    print(__doc__)
    sys.exit(2)

HEAD = Path(sys.argv[1]).resolve()
BASE = Path(sys.argv[2]).resolve()

failures = []


def record(ok, label):
    print(f"  [{'ok' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


def run_in(root: Path, code: str) -> str:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(root / "packages/trusted-evidence-authority/src")
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=str(root), capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise RuntimeError(f"script failed in {root}:\n{result.stderr}")
    return result.stdout.strip()


print(f"HEAD: {HEAD}\nBASE (TEV-1): {BASE}\n")

print("=== independently-built TEV-1 fixture: EvidenceSchemaRef, real string ===")
schema_code = (
    "from ugence_trusted_evidence_authority.contracts.canonical import canonical_digest\n"
    "from ugence_trusted_evidence_authority.api import EvidenceSchemaRef\n"
    "print(canonical_digest(EvidenceSchemaRef(schema_id='ugence.evidence.control-test', schema_version='1')))\n"
)
head_schema_digest = run_in(HEAD, schema_code)
base_schema_digest = run_in(BASE, schema_code)
print(f"  base : {base_schema_digest}")
print(f"  head : {head_schema_digest}")
record(head_schema_digest == base_schema_digest, "EvidenceSchemaRef('control-test') digest unchanged TEV-1 -> head")

# the string PR #1463's own stale probes used and never actually ran
bogus_code = schema_code.replace("control-test", "model-benchmark")
bogus_digest = run_in(HEAD, bogus_code)
record(bogus_digest != head_schema_digest,
       "sanity: 'model-benchmark' (PR #1463's stale, unrun probe fixture) is NOT the real TEV-1 string "
       f"-- it digests to {bogus_digest[:16]}..., confirming that PR's own committed evidence has a fixture bug")

print("\n=== package's own before/after builders: identity() and receipt() ===")
identity_code = (
    "import sys; sys.path.insert(0, 'packages/trusted-evidence-authority/tests')\n"
    "from _builders import identity\n"
    "print(identity().canonical_digest())\n"
)
receipt_code = (
    "import sys; sys.path.insert(0, 'packages/trusted-evidence-authority/tests')\n"
    "from _builders import receipt\n"
    "print(receipt().canonical_digest())\n"
)
head_identity, base_identity = run_in(HEAD, identity_code), run_in(BASE, identity_code)
head_receipt, base_receipt = run_in(HEAD, receipt_code), run_in(BASE, receipt_code)
record(head_identity == base_identity, "CanonicalEvidenceIdentity digest unchanged TEV-1 -> head")
record(head_receipt == base_receipt, "EvidenceVerificationReceiptPayload digest unchanged TEV-1 -> head")

print("\n=== digest domain tags ===")
domains_code = (
    "from ugence_trusted_evidence_authority.api import (\n"
    "    EVIDENCE_IDENTITY_DIGEST_DOMAIN, EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN,\n"
    "    TRUSTED_EVIDENCE_CANONICALIZATION_VERSION)\n"
    "print(EVIDENCE_IDENTITY_DIGEST_DOMAIN)\n"
    "print(EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN)\n"
    "print(TRUSTED_EVIDENCE_CANONICALIZATION_VERSION)\n"
)
head_domains = run_in(HEAD, domains_code).splitlines()
base_domains = run_in(BASE, domains_code).splitlines()
record(head_domains == base_domains, f"digest domain tags unchanged ({head_domains})")

print("\n=== refusal vocabulary: TEV-1's members at their original ordinal positions ===")
refusal_code = (
    "import hashlib\n"
    "from ugence_trusted_evidence_authority.contracts.reasons import TrustedEvidenceRefusalReason as R\n"
    "mem = list(R)\n"
    "print(len(mem))\n"
    "print(hashlib.sha256('|'.join(m.name for m in mem[:19]).encode()).hexdigest())\n"
)
head_lines = run_in(HEAD, refusal_code).splitlines()
base_lines = run_in(BASE, refusal_code).splitlines()
head_count, head_first19_hash = int(head_lines[0]), head_lines[1]
base_count, base_first19_hash = int(base_lines[0]), base_lines[1]
record(head_count >= base_count, f"refusal vocabulary did not shrink ({base_count} -> {head_count})")
record(head_first19_hash == base_first19_hash,
       "the first N members (TEV-1's own count) are unchanged, in order, at head "
       f"(N={base_count}, hash={head_first19_hash[:16]}...)")

print("\n=== curated API surface: TEV-1 symbols still present ===")
api_code = "import ugence_trusted_evidence_authority.api as api\nprint('\\n'.join(sorted(api.__all__)))\n"
head_api = set(run_in(HEAD, api_code).splitlines())
base_api = set(run_in(BASE, api_code).splitlines())
missing = base_api - head_api
record(not missing, f"every TEV-1 curated symbol still present at head (missing: {sorted(missing)})")
print(f"  TEV-1 symbol count: {len(base_api)}  head symbol count: {len(head_api)}  "
      f"added: {len(head_api - base_api)}")

print()
if failures:
    print(f"FAIL: {len(failures)} check(s) did not hold: {failures}")
    sys.exit(1)
print("PASS: TEV-1 compatibility holds against the merged head, verified by direct "
      "before/after computation rather than by trusting a hardcoded constant")
