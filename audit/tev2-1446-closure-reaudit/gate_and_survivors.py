"""Independent re-audit of closure finding F-09 against the MERGED head.

Rather than repeating the package's full 18-gate mutation matrix (self-tested
and self-reported), this spot-checks the one gate the PR body calls out by
name as newly load-bearing — the re-verifier's *recomputed* payload digest vs.
the envelope's *declared* `payload_canonical_digest` field — by constructing
exactly the scenario described: a signature that is valid (it was never
computed over the declared field) alongside a declared digest that lies. It
also probes whether the two claimed "structurally unreachable" gates
(capability, signature-profile) really have no path to fire, by trying the
most direct route to each rather than trusting the claim.

Run: python audit/tev2-1446-closure-reaudit/gate_and_survivors.py <repo-root>
"""
from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "packages/trusted-evidence-authority/src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ugence_trusted_evidence_authority.api as api
import _fixtures as F

failures = []


def record(ok, label):
    print(f"  [{'ok' if ok else 'FAIL'}] {label}")
    if not ok:
        failures.append(label)


print("=== the re-verifier's payload-digest gate: a lying declared digest ===")
env, sk, frame = F.genuine_envelope()
anchor = F.genuine_anchor(sk)
v = F.verifier_for(anchor)

sanity = v.verify_signature(env, evaluated_at=F.NOW)
record(sanity.verified is True, "the genuine envelope verifies before mutation (sanity)")

# The envelope's own __post_init__ already checks payload_canonical_digest
# against the payload at *construction* time (confirmed below) — so
# dataclasses.replace(), which re-runs __init__, cannot produce the lying
# envelope; it re-triggers that very check. The PR's claimed scenario is a
# deserializer that never runs __post_init__ at all — an unpickled envelope,
# or one rebuilt field-by-field — so reproduce that directly: bypass __init__
# with object.__new__ and set every field by hand, exactly as a deserializer
# would.
lying_digest = "0" * 64
assert lying_digest != env.payload_canonical_digest

try:
    dataclasses.replace(env, payload_canonical_digest=lying_digest)
    record(False, "dataclasses.replace() with a lying digest was NOT refused (unexpected: __post_init__ should re-run)")
except Exception as e:
    record(True, f"dataclasses.replace() re-runs __post_init__ and refuses the lie directly ({type(e).__name__}) "
           "— a second, construction-time gate, distinct from the re-verifier's own recompute check below")

lying_env = object.__new__(api.SignedEvidenceVerificationReceipt)
for f in dataclasses.fields(env):
    value = lying_digest if f.name == "payload_canonical_digest" else getattr(env, f.name)
    object.__setattr__(lying_env, f.name, value)
record(lying_env.payload_canonical_digest == lying_digest, "bypass-constructed envelope carries the lying digest")
record(lying_env.signature == env.signature, "signature field unchanged by the bypass (isolates this gate)")

res = v.verify_signature(lying_env, evaluated_at=F.NOW)
record(res.outcome is api.ReceiptVerificationOutcome.REFUSED, "lying declared digest -> REFUSED")
record(res.verified is False, "lying declared digest -> verified=False")
print(f"    refusal_reason: {res.refusal_reason}")

print("\n=== structurally-unreachable survivor #1: the capability gate ===")
# Claim: TrustAnchorResolution refuses an anchor whose own coordinate differs
# from the one resolved, and the resolved coordinate always names
# RECEIPT_ISSUANCE — so a capability mismatch can never reach the re-verifier.
# Try the most direct route: register an anchor under one capability, resolve
# under a different one, at the SAME (authority_id, key_id).
mismatched = api.TrustAnchorRecord(
    authority_id=F.AUTHORITY_ID, key_id=F.KEY_ID,
    capability=api.TrustAnchorCapability.EVIDENCE_PRODUCTION,  # NOT receipt-issuance
    public_key=api.encode_public_key(sk.verification_key.public_key_bytes),
    trust_anchor_set_id=F.TRUST_SET_ID, trust_anchor_set_version=F.TRUST_SET_VERSION)
directory = api.StaticTrustAnchorDirectory(
    (mismatched,), trust_anchor_set_id=F.TRUST_SET_ID, trust_anchor_set_version=F.TRUST_SET_VERSION)
coordinate = api.TrustAnchorCoordinate(F.AUTHORITY_ID, F.KEY_ID, api.TrustAnchorCapability.RECEIPT_ISSUANCE)
resolution = directory.resolve(coordinate)
record(resolution.anchor is None, "resolving RECEIPT_ISSUANCE against an EVIDENCE_PRODUCTION-only anchor finds nothing "
       "(the mismatch is refused at resolution, before any capability-gate code in the re-verifier could run)")

print("\n=== structurally-unreachable survivor #2: the signature-profile pin ===")
# Claim: both sides are pinned by exact equality to the one ratified profile,
# so no code path can ever present two different profile strings to compare.
# Try to make TrustAnchorRecord accept a different (but plausible) profile.
try:
    api.TrustAnchorRecord(
        authority_id="a", key_id="k", capability=api.TrustAnchorCapability.RECEIPT_ISSUANCE,
        public_key=api.encode_public_key(sk.verification_key.public_key_bytes),
        trust_anchor_set_id="s", trust_anchor_set_version="1",
        signature_profile="ugence.trusted-evidence-authority/signature/some-future-profile/v2")
    record(False, "TrustAnchorRecord accepted a non-ratified signature_profile (the pin gate could then fire for real)")
except Exception as e:
    record(True, f"TrustAnchorRecord refuses a non-ratified signature_profile at construction ({type(e).__name__}) "
           "— confirms there is currently no way to present two profiles to compare, matching the claim")

print()
if failures:
    print(f"FAIL: {len(failures)} check(s) did not hold: {failures}")
    sys.exit(1)
print("PASS: the named load-bearing gate (recomputed vs. declared payload digest) fires exactly as "
      "described, and both claimed structurally-unreachable survivors have no path found to fire them "
      "(F-09 holds against the merged head, for the mechanisms checked)")
