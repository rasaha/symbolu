import sys, hashlib, json
P = "/tmp/claude-0/-home-user-symbolu/d3fc5d47-2faa-523b-8b2b-984ef2d9ae2b/scratchpad/tev2head/packages/trusted-evidence-authority"
sys.path.insert(0, P+"/src"); sys.path.insert(0, P+"/tests")
from datetime import datetime, timezone
import ugence_trusted_evidence_authority.api as api
import _authority_builders as B, _builders as B1

print("=== TEV-1 PINNED DIGESTS ===")
EXP = {
 "EvidenceSchemaRef":"54b9bd615aa13dd133f88580128b4c4094363c75f96b6bcf1d3b2f582683fa62",
 "CanonicalEvidenceIdentity":"26ee959e4c87cc0660895a269c2805af1065ba4f634c9c73070848de7bf51029",
}
print("  EvidenceSchemaRef      ", api.EvidenceSchemaRef(schema_id="ugence.evidence.model-benchmark", schema_version="1").canonical_digest())
ident = B1.identity()
print("  CanonicalEvidenceIdentity", ident.canonical_digest())
env = B.envelope()
print("  receipt payload (env)  ", env.payload.canonical_digest())
print("  envelope digest        ", env.envelope_digest())
print("  authority public key   ", api.encode_public_key(B.authority_signing_key().verification_key.public_key_bytes))
print("  receipt signature      ", env.signature[:8]+"..."+env.signature[-8:])
print("  receipt id             ", env.payload.receipt_id)

print("\n=== API PARITY (source vs public_api.json) ===")
manifest = json.load(open(P+"/public_api.json"))
def names(m):
    if isinstance(m, dict):
        for k in ("symbols","api","exports","public_api"):
            if k in m: return m[k]
        return m
    return m
sym = names(manifest)
mn = set(sym.keys()) if isinstance(sym, dict) else set(sym)
actual = set(api.__all__)
print(f"  manifest symbols: {len(mn)}   api.__all__: {len(actual)}")
print(f"  missing from source: {sorted(mn-actual)}")
print(f"  extra in source   : {sorted(actual-mn)}")
import ugence_trusted_evidence_authority as pkg
print(f"  package root __all__ == api.__all__: {set(pkg.__all__)==actual}")

print("\n=== INDEPENDENT SIGNING-FRAME RECONSTRUCTION (no package helpers) ===")
from ugence_trusted_evidence_authority.contracts.canonical import canonical_bytes, canonical_digest
pb = canonical_bytes(env.payload); pd = canonical_digest(env.payload)
els = [b"ugence.trusted-evidence-authority/signed-receipt-input/v1",
       b"ugence.trusted-evidence-authority/signed-receipt-envelope/v1",
       b"ugence.trusted-evidence-authority/signature/ed25519-sha512-pure/v1",
       api.TRUSTED_EVIDENCE_CANONICALIZATION_VERSION.encode(),
       api.EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN.encode(),
       env.signer_authority_id.encode(), env.signing_key_id.encode(),
       env.payload.verification_protocol_id.encode(),
       env.payload.verification_protocol_version.encode(),
       pd.encode(), pb]
frame = len(els).to_bytes(8,"big") + b"".join(len(e).to_bytes(8,"big")+e for e in els)
pkg_frame = env.signed_input_bytes()
print(f"  hand-built frame == package frame: {frame==pkg_frame}")
print(f"  frame length: {len(frame)}  sha256: {hashlib.sha256(frame).hexdigest()}")
# verify signature with INDEPENDENT implementation
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
pk = api.decode_public_key(api.encode_public_key(B.authority_signing_key().verification_key.public_key_bytes))
try:
    Ed25519PublicKey.from_public_bytes(pk).verify(bytes.fromhex(env.signature), frame)
    print("  OpenSSL verifies the PR receipt signature over the hand-built frame: TRUE")
except Exception as e:
    print("  OpenSSL verify FAILED:", e)
