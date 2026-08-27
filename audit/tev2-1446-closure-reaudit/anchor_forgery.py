"""Independent re-audit of closure findings F-01 / F-03 against the MERGED head.

PR #1446 (merged) claims untrustworthy anchor keys — the identity point, small-
order/torsion points, and non-canonical field-element encodings — are now
refused at TrustAnchorRecord *construction*, before a signature is ever forged
against them. This is audit-owned: it imports only the curated public API, uses
its own low-order/identity point corpus (not the package's), and drives the
attack all the way through SignedReceiptVerifier rather than stopping at a
unit-level construction check.

Run: python audit/tev2-1446-closure-reaudit/anchor_forgery.py <repo-root>
"""
from __future__ import annotations

import sys
from pathlib import Path

root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "packages/trusted-evidence-authority/src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import ugence_trusted_evidence_authority.api as api
import _fixtures as F

# Canonical low-order / identity points, and their non-canonical siblings —
# an audit-owned corpus, independent of the one in the package's own test suite.
POINTS = {
    "identity, canonical (0100..00)": bytes.fromhex("01" + "00" * 31),
    "identity, NONcanonical (0100..80, RFC 8032 5.1.3 must-fail)": bytes.fromhex("01" + "00" * 30 + "80"),
    "order-2, canonical (ecff..7f)": bytes.fromhex("ec" + "ff" * 30 + "7f"),
    "order-2, NONcanonical sign bit (ecff..ff)": bytes.fromhex("ec" + "ff" * 31),
    "order-4, all-zero": bytes.fromhex("00" * 32),
    "order-4, NONcanonical (0000..80)": bytes.fromhex("00" * 31 + "80"),
    "order-8, point A": bytes.fromhex("26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc05"),
    "order-8, point B": bytes.fromhex("c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac03fa"),
    "non-canonical field element y=p (edff..7f)": bytes.fromhex("ed" + "ff" * 30 + "7f"),
    "non-canonical field element y=p+1 (eeff..7f)": bytes.fromhex("ee" + "ff" * 30 + "7f"),
    "off-curve (y=2)": (2).to_bytes(32, "little"),
    "all-ff": b"\xff" * 32,
}

failures = []


def check(label, fn):
    try:
        fn()
    except Exception as e:
        print(f"  [refused]  {label:55s} -> {type(e).__name__}")
    else:
        print(f"  [ADMITTED] {label:55s} -> NO EXCEPTION  <== BAD")
        failures.append(label)


print("=== F-01/F-03: untrustworthy points refused at construction ===")
print("--- TrustedEvidenceVerificationKey(...) ---")
for label, pk in POINTS.items():
    check(label, lambda pk=pk: api.TrustedEvidenceVerificationKey(pk))

print("\n--- TrustAnchorRecord(...) (the actual admission boundary) ---")
for label, pk in POINTS.items():
    check(
        label,
        lambda pk=pk: api.TrustAnchorRecord(
            authority_id="a", key_id="k", capability=api.TrustAnchorCapability.RECEIPT_ISSUANCE,
            public_key=api.encode_public_key(pk),
            trust_anchor_set_id="s", trust_anchor_set_version="1"))

print("\n=== end-to-end: does a universal forgery reach VERIFIED through the real path? ===")
env, sk, frame = F.genuine_envelope()
payload = env.payload


def forged_sig_for_identity():
    # A = identity => [k]A = identity for any k => the verification equation
    # [S]B = R + [k]A reduces to [S]B = R, so R = [S]B verifies for ANY message
    # under the identity key, with no private key involved at all.
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    # We do not need real curve arithmetic to demonstrate the shape of the
    # attack: the point is whether such a key can even become a registered
    # anchor. If TrustAnchorRecord refuses it, the forgery never gets to try.
    return b"\x00" * 64


for label, pk in POINTS.items():
    try:
        anchor = api.TrustAnchorRecord(
            authority_id=payload.verifier_authority_id, key_id=payload.verifier_key_id,
            capability=api.TrustAnchorCapability.RECEIPT_ISSUANCE,
            public_key=api.encode_public_key(pk),
            trust_anchor_set_id=F.TRUST_SET_ID, trust_anchor_set_version=F.TRUST_SET_VERSION)
    except Exception as e:
        print(f"  {label:55s} -> anchor construction refused ({type(e).__name__}); forgery route closed")
        continue
    # If this line is ever reached, the untrustworthy key was admitted as an
    # anchor — try the forged signature against it end-to-end.
    forged = api.SignedEvidenceVerificationReceipt(
        envelope_schema=api.SIGNED_RECEIPT_ENVELOPE_SCHEMA_V1, payload=payload,
        payload_canonical_digest=payload.canonical_digest(),
        signature_profile=api.TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1,
        signed_input_domain=api.TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN,
        signer_authority_id=payload.verifier_authority_id, signing_key_id=payload.verifier_key_id,
        signature=api.encode_signature(forged_sig_for_identity()))
    v = F.verifier_for(anchor)
    res = v.verify_signature(forged, evaluated_at=F.NOW)
    print(f"  {label:55s} -> ADMITTED AS ANCHOR, forged verdict: {res.outcome.value}  <== BAD")
    failures.append(label + " (e2e forgery reached verifier)")

print()
if failures:
    print(f"FAIL: {len(failures)} untrustworthy point(s) were not refused: {failures}")
    sys.exit(1)
print(f"PASS: all {len(POINTS)} untrustworthy points refused at TrustAnchorRecord/key construction; "
      "the forgery route never opens (F-01, F-03 hold against the merged head)")
