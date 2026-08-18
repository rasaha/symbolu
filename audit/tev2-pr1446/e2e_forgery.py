"""End-to-end: is the low-order / non-canonical key weakness reachable through
SignedReceiptVerifier and the trust-anchor layer? Audit-owned, no package test helpers."""
import sys, hashlib
P = "/tmp/claude-0/-home-user-symbolu/d3fc5d47-2faa-523b-8b2b-984ef2d9ae2b/scratchpad/tev2head/packages/trusted-evidence-authority"
sys.path.insert(0, P+"/src"); sys.path.insert(0, P+"/tests")
from datetime import datetime, timezone
import ugence_trusted_evidence_authority.authority.ed25519 as prm
from ugence_trusted_evidence_authority.api import (
    SignedEvidenceVerificationReceipt, SignedReceiptVerifier, StaticTrustAnchorDirectory,
    TrustAnchorRecord, TrustAnchorCapability, encode_signature,
    SIGNED_RECEIPT_ENVELOPE_SCHEMA_V1, TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1,
    TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN, signed_receipt_input_bytes,
)
import _authority_builders as B

NOW = datetime(2026, 6, 2, tzinfo=timezone.utc)
genuine = B.envelope()
payload = genuine.payload
print("genuine envelope authority:", genuine.signer_authority_id, "/", genuine.signing_key_id)

# sanity: genuine verifies
r = SignedReceiptVerifier(trust_anchors=B.directory()).verify(genuine, evaluated_at=NOW)
print("genuine re-verification:", r.outcome.value, "verified=", r.verified)

# ---- attack: trust anchor whose public key is a LOW-ORDER point ------------
# No private key exists for these. A forged signature verifies for ANY message.
def forged_sig_for_identity(frame):
    s = 12345
    R = prm._encode_point(prm._scalarmult(prm._B, s))
    return R + s.to_bytes(32, "little")

CASES = {
 "canonical identity  0100..00": bytes.fromhex("01"+"00"*31),
 "NONcanonical identity 0100..80 (RFC 8032 5.1.3 MUST fail)": bytes.fromhex("01"+"00"*30+"80"),
}
for label, pkbytes in CASES.items():
    anchor = TrustAnchorRecord(
        authority_id=genuine.signer_authority_id,
        key_id=genuine.signing_key_id,
        capability=TrustAnchorCapability.RECEIPT_ISSUANCE,
        public_key=pkbytes.hex(),
        trust_anchor_set_id=B.TRUST_ANCHOR_SET_ID,
        trust_anchor_set_version=B.TRUST_ANCHOR_SET_VERSION,
        effective_from=B.KEY_FROM, effective_to=B.KEY_TO,
    )
    frame = signed_receipt_input_bytes(
        payload=payload,
        signer_authority_id=genuine.signer_authority_id,
        signing_key_id=genuine.signing_key_id,
    )
    forged = SignedEvidenceVerificationReceipt(
        envelope_schema=SIGNED_RECEIPT_ENVELOPE_SCHEMA_V1,
        payload=payload,
        payload_canonical_digest=payload.canonical_digest(),
        signature_profile=TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1,
        signed_input_domain=TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN,
        signer_authority_id=genuine.signer_authority_id,
        signing_key_id=genuine.signing_key_id,
        signature=encode_signature(forged_sig_for_identity(frame)),
    )
    d = StaticTrustAnchorDirectory((anchor,),
        trust_anchor_set_id=B.TRUST_ANCHOR_SET_ID,
        trust_anchor_set_version=B.TRUST_ANCHOR_SET_VERSION)
    res = SignedReceiptVerifier(trust_anchors=d).verify(forged, evaluated_at=NOW)
    print(f"  anchor pubkey [{label}]")
    print(f"    TrustAnchorRecord constructed: YES (no curve/low-order validation)")
    print(f"    forged receipt verdict: {res.outcome.value}  verified={res.verified}"
          f"  reason={res.refusal_reason}")
