import sys
P = "/tmp/claude-0/-home-user-symbolu/d3fc5d47-2faa-523b-8b2b-984ef2d9ae2b/scratchpad/tev2head/packages/trusted-evidence-authority"
sys.path.insert(0, P+"/src"); sys.path.insert(0, P+"/tests")
from datetime import datetime, timezone
from dataclasses import fields, asdict
from ugence_trusted_evidence_authority.api import SignedReceiptVerifier
import _authority_builders as B
NOW = datetime(2026, 6, 2, tzinfo=timezone.utc)
env = B.envelope(); v = SignedReceiptVerifier(trust_anchors=B.directory())
sc = env.payload.scope

print("=== ReceiptVerification fields ===")
r_none = v.verify(env, evaluated_at=NOW)
r_full = v.verify(env, evaluated_at=NOW,
    expected_tenant_id=sc.tenant_id,
    expected_assessment_context_ref=sc.assessment_context_ref,
    expected_subject_ref=sc.subject_ref,
    expected_assessed_system_binding_digest=sc.assessed_system_binding_digest,
    expected_assessment_purpose_ref=sc.assessment_purpose_ref,
    expected_usage_scope_ref=sc.usage_scope_ref,
    expected_verification_protocol_id=env.payload.verification_protocol_id,
    expected_verification_protocol_version=env.payload.verification_protocol_version,
    expected_evidence_content_digest=env.payload.evidence_content_digest)
for f in fields(r_none):
    if f.name == "verification_token": continue
    print(f"  {f.name:28s} nochecks={getattr(r_none,f.name)!r:.70s}")
print()
print("signature-only  : outcome=%s verified=%s stages=%s" % (r_none.outcome.value, r_none.verified,
      [s.name for s in r_none.established_trust_stages]))
print("fully scope-bound: outcome=%s verified=%s stages=%s" % (r_full.outcome.value, r_full.verified,
      [s.name for s in r_full.established_trust_stages]))
print()
same = all(getattr(r_none,f.name)==getattr(r_full,f.name)
           for f in fields(r_none) if f.name!="verification_token")
print(f">>> signature-only result INDISTINGUISHABLE from fully-bound result: {same}")
print(f">>> r_none == r_full (dataclass equality): {r_none == r_full}")
print(f">>> repr identical: {repr(r_none)==repr(r_full)}")
print(f">>> any attribute recording which coordinates were checked: "
      f"{[a for a in dir(r_none) if 'check' in a.lower() or 'expect' in a.lower() or 'bound' in a.lower() or 'scope' in a.lower()]}")

print("\n=== silent-omission matrix ===")
def t(label, **kw):
    r = v.verify(env, evaluated_at=NOW, **kw)
    print(f"  {label:52s} -> {r.outcome.value:8s} verified={r.verified}")
t("no expected_* at all (third-party mode)")
t("expected_tenant_id = correct", expected_tenant_id=sc.tenant_id)
t("expected_tenant_id = WRONG", expected_tenant_id="other-tenant")
t('expected_tenant_id = "" (empty -> silently unchecked)', expected_tenant_id="")
try:
    t("expected_tenant_id = None (explicit None)", expected_tenant_id=None)
except Exception as e:
    print(f"  {'expected_tenant_id = None':52s} -> RAISES {type(e).__name__}")
t("each coordinate WRONG one at a time: subject", expected_subject_ref="wrong")
t("each coordinate WRONG one at a time: purpose", expected_assessment_purpose_ref="wrong")
t("each coordinate WRONG one at a time: usage scope", expected_usage_scope_ref="wrong")
t("each coordinate WRONG one at a time: system binding",
  expected_assessed_system_binding_digest="a"*64)
t("each coordinate WRONG one at a time: content digest",
  expected_evidence_content_digest="b"*64)
t("each coordinate WRONG one at a time: protocol id", expected_verification_protocol_id="wrong")
t("MISSPELLED kwarg would TypeError? -> test", )
try:
    v.verify(env, evaluated_at=NOW, expected_tenant="typo")
    print("  misspelled kwarg silently ignored  <== BAD")
except TypeError:
    print("  misspelled kwarg -> TypeError (good)")
try:
    v.verify(env, NOW)
    print("  positional evaluated_at accepted <== check")
except TypeError:
    print("  positional evaluated_at -> TypeError (kw-only, good)")
