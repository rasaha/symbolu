import sys
P = "/tmp/claude-0/-home-user-symbolu/d3fc5d47-2faa-523b-8b2b-984ef2d9ae2b/scratchpad/tev2head/packages/trusted-evidence-authority"
sys.path.insert(0, P+"/src"); sys.path.insert(0, P+"/tests")
from datetime import datetime, timezone
import ugence_trusted_evidence_authority.api as api
from ugence_trusted_evidence_authority.contracts.reasons import (
    TrustedEvidenceRefusalReason as R, TRUSTED_EVIDENCE_REFUSAL_REASONS)
import _authority_builders as B

print("=== REFUSAL VOCABULARY ===")
mem = list(R)
print(f"total members: {len(mem)}")
vals = [m.value for m in mem]
print(f"duplicate values: {len(vals)!=len(set(vals))}")
names=[m.name for m in mem]
print(f"aliases (name!=value stem mismatch count): {sum(1 for m in mem if m.name!=m.value)}")
print(f"tuple constant length: {len(TRUSTED_EVIDENCE_REFUSAL_REASONS)}  order==declaration: "
      f"{list(TRUSTED_EVIDENCE_REFUSAL_REASONS)==mem}")
print("first 19 (TEV-1 prefix):")
for i,m in enumerate(mem[:19]): print(f"  {i:2d} {m.name}")
print(f"appended TEV-2 members: {len(mem)-19}")
for i,m in enumerate(mem[19:],19): print(f"  {i:2d} {m.name}")

print("\n=== THREE-ROLE CAPABILITY GRAPH ===")
auth = B.authority(); iss = B.issuer(); rev = B.reverifier()
import gc
def reach_keys(obj, depth=6):
    """Does a signing key / seed reachable from this object graph?"""
    seen=set(); stack=[(obj,"")]; hits=[]
    while stack:
        o,path = stack.pop()
        if id(o) in seen or len(seen)>20000: continue
        seen.add(id(o))
        if isinstance(o, api.TrustedEvidenceSigningKey): hits.append(path); continue
        if isinstance(o,(str,bytes,int,float,type(None),bool)): continue
        for attr in getattr(o,"__slots__",()) or ():
            try: stack.append((getattr(o,attr), path+"."+attr))
            except Exception: pass
        d = getattr(o,"__dict__",None)
        if isinstance(d,dict):
            for k,vv in d.items(): stack.append((vv, path+"."+k))
        if isinstance(o,(list,tuple,set,frozenset)):
            for i,vv in enumerate(o): stack.append((vv, path+f"[{i}]"))
        if isinstance(o,dict):
            for k,vv in o.items(): stack.append((vv, path+f"[{k!r}]"))
    return hits
for nm,o in (("EvidenceVerificationAuthority",auth),("ReceiptIssuer",iss),("SignedReceiptVerifier",rev)):
    hits = reach_keys(o)
    meth = sorted(m for m in dir(o) if not m.startswith("_") )
    print(f"  {nm:32s} signing-key reachable: {bool(hits)} {hits}")
    print(f"      public methods: {meth}")
print("\n  authority has sign method:", any('sign' in m for m in dir(auth) if not m.startswith('_')))
print("  issuer has verify method:", any('verif' in m for m in dir(iss) if not m.startswith('_')))
print("  reverifier has sign/issue:", any(('sign' in m or 'issue' in m) for m in dir(rev) if not m.startswith('_')))

print("\n=== arbitrary signing attempt ===")
sg = B.signer()
try:
    inp = api.ReceiptSigningInput(signed_input=b"attacker chosen bytes",
        signer_authority_id=B.VERIFIER_AUTHORITY_ID, signing_key_id=B.VERIFIER_KEY_ID,
        signature_profile=api.TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1)
    print("  direct ReceiptSigningInput construction: SUCCEEDED  <== BAD")
except Exception as e:
    print(f"  direct ReceiptSigningInput construction: refused ({type(e).__name__})")
print("  curated API exports ReceiptSigningInput:", "ReceiptSigningInput" in dir(api))
print("  curated API exports token:", [n for n in dir(api) if 'TOKEN' in n.upper()])
# private-module bypass
from ugence_trusted_evidence_authority.authority import signing as _s
inp = api.ReceiptSigningInput(signed_input=b"attacker chosen bytes",
    signer_authority_id=B.VERIFIER_AUTHORITY_ID, signing_key_id=B.VERIFIER_KEY_ID,
    signature_profile=api.TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1,
    issuance_token=_s._SIGNING_INPUT_TOKEN)
print("  via private module token -> signed arbitrary bytes:", sg.sign_receipt(inp)[:32], "(documented as undefended)")
