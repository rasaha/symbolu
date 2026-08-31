"""Independent re-audit of closure findings F-04 / F-05 against the MERGED head.

F-04: a signature-only result must be a different, non-equal, distinctly-typed
result from a fully scope-bound one.
F-05: `verify_bound`'s expectation must be mandatory, exactly typed, and every
coordinate compared unconditionally — no falsy value may silently skip a check.

Run: python audit/tev2-1446-closure-reaudit/reverification_shapes.py <repo-root>
"""
from __future__ import annotations

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


env, sk, frame = F.genuine_envelope()
anchor = F.genuine_anchor(sk)
v = F.verifier_for(anchor)

print("=== F-04: signature-only vs scope-bound are distinct, non-equal types ===")
r_sig = v.verify_signature(env, evaluated_at=F.NOW)
r_bound = v.verify_bound(env, F.full_expectation(), evaluated_at=F.NOW)
record(type(r_sig) is api.SignatureOnlyVerificationResult, "verify_signature returns SignatureOnlyVerificationResult")
record(type(r_bound) is api.ScopeBoundVerificationResult, "verify_bound returns ScopeBoundVerificationResult")
record(type(r_sig) is not type(r_bound), "the two result types are not the same class")
record((r_sig == r_bound) is False, "r_sig == r_bound is False (not NotImplemented-then-True)")
record(repr(r_sig) != repr(r_bound), "distinct repr()")
record(r_sig.verification_kind is api.ReceiptVerificationKind.SIGNATURE_ONLY, "signature-only kind tag correct")
record(r_bound.verification_kind is api.ReceiptVerificationKind.SCOPE_BOUND, "scope-bound kind tag correct")
record(r_sig.scope_bound is False, "SignatureOnlyVerificationResult.scope_bound is False")
record(api.EvidenceTrustStage.CONTEXT_SYSTEM_BOUND not in r_sig.established_trust_stages,
       "signature-only never reports CONTEXT_SYSTEM_BOUND")
record(api.EvidenceTrustStage.CONTEXT_SYSTEM_BOUND in r_bound.established_trust_stages,
       "scope-bound reports CONTEXT_SYSTEM_BOUND on success")
record(hasattr(r_bound, "scope_expectation_digest") and r_bound.scope_expectation_digest != "",
       "scope-bound result records which expectation it was checked against")
record(not hasattr(r_sig, "scope_expectation_digest") or r_sig.scope_expectation_digest == "",
       "signature-only result carries no scope-expectation digest to misread")

print("\n=== a caller cannot manufacture a VERIFIED result directly ===")
try:
    forged = api.SignatureOnlyVerificationResult(
        outcome=api.ReceiptVerificationOutcome.VERIFIED, evaluated_at=F.NOW,
        coordinate=api.TrustAnchorCoordinate(F.AUTHORITY_ID, F.KEY_ID, api.TrustAnchorCapability.RECEIPT_ISSUANCE),
        envelope_digest="x" * 64, payload_canonical_digest="y" * 64)
    record(False, "direct construction of a VERIFIED result was NOT refused")
except Exception as e:
    record(True, f"direct construction of a VERIFIED result refused ({type(e).__name__})")

print("\n=== F-05: verify_bound's expectation is mandatory and exactly typed ===")
try:
    v.verify_bound(env, None, evaluated_at=F.NOW)
    record(False, "verify_bound(expectation=None) was NOT refused")
except TypeError:
    record(True, "verify_bound(expectation=None) TypeError (positional required)")
except Exception as e:
    record(True, f"verify_bound(expectation=None) refused ({type(e).__name__})")

# duck-typed lookalike: same fields, wrong exact type
class _Lookalike:
    def __init__(self, exp):
        for name in exp.REQUIRED_COORDINATES:
            setattr(self, name, getattr(exp, name))

    def expectation_digest(self):
        return "not-a-real-digest"


try:
    v.verify_bound(env, _Lookalike(F.full_expectation()), evaluated_at=F.NOW)
    record(False, "verify_bound(duck-typed lookalike) was NOT refused")
except Exception as e:
    record(True, f"verify_bound(duck-typed lookalike) refused ({type(e).__name__})")


class _Subclass(api.ReceiptScopeExpectation):
    pass


try:
    sub = _Subclass(**{n: getattr(F.full_expectation(), n) for n in api.ReceiptScopeExpectation.REQUIRED_COORDINATES})
    v.verify_bound(env, sub, evaluated_at=F.NOW)
    record(False, "verify_bound(subclass instance) was NOT refused (exact-type check bypassed by subclassing)")
except Exception as e:
    record(True, f"verify_bound(subclass instance) refused ({type(e).__name__})")

print("\n=== F-05: no coordinate can be omitted or left falsy inside the expectation itself ===")
base_kwargs = {n: getattr(F.full_expectation(), n) for n in api.ReceiptScopeExpectation.REQUIRED_COORDINATES}
for coord in api.ReceiptScopeExpectation.REQUIRED_COORDINATES:
    kwargs = dict(base_kwargs)
    del kwargs[coord]
    try:
        api.ReceiptScopeExpectation(**kwargs)
        record(False, f"omitting {coord} was accepted (no TypeError for a missing required field)")
    except TypeError:
        record(True, f"omitting {coord} -> TypeError (no default exists)")

for coord in api.ReceiptScopeExpectation.REQUIRED_COORDINATES:
    if coord == "assessed_system_binding_digest":
        continue  # "" is the one ratified empty spelling, via a named constructor only
    kwargs = dict(base_kwargs)
    kwargs[coord] = ""
    try:
        api.ReceiptScopeExpectation(**kwargs)
        record(False, f"{coord}='' was silently accepted (F-05 truthiness gate reintroduced)")
    except Exception as e:
        record(True, f"{coord}='' refused at construction ({type(e).__name__})")

print("\n=== F-05: a wrong-but-truthy coordinate must still be caught by verify_bound ===")
for coord in api.ReceiptScopeExpectation.REQUIRED_COORDINATES:
    kwargs = dict(base_kwargs)
    if coord == "evidence_content_digest":
        kwargs[coord] = "b" * 64
    elif coord == "assessed_system_binding_digest":
        kwargs[coord] = "c" * 64
    else:
        kwargs[coord] = kwargs[coord] + "-WRONG"
    exp = api.ReceiptScopeExpectation(**kwargs)
    res = v.verify_bound(env, exp, evaluated_at=F.NOW)
    record(res.outcome is api.ReceiptVerificationOutcome.REFUSED and res.verified is False,
           f"wrong {coord} -> REFUSED (verified={res.verified})")

print("\n=== F-05: the one ratified empty coordinate is explicit-only, not a default ===")
exp_indep = api.ReceiptScopeExpectation.for_system_independent_evidence(
    **{k: v_ for k, v_ in base_kwargs.items() if k != "assessed_system_binding_digest"})
record(exp_indep.assessed_system_binding_digest == "", "for_system_independent_evidence sets '' explicitly")
try:
    api.ReceiptScopeExpectation.for_system_independent_evidence(**base_kwargs)
    record(False, "for_system_independent_evidence accepted an explicit assessed_system_binding_digest kwarg too")
except Exception as e:
    record(True, f"passing assessed_system_binding_digest to for_system_independent_evidence refused ({type(e).__name__})")

print()
if failures:
    print(f"FAIL: {len(failures)} check(s) did not hold: {failures}")
    sys.exit(1)
print("PASS: F-04 and F-05 both hold against the merged head — the two result types are "
      "structurally distinct and non-equal, and every scope coordinate is mandatory, "
      "exactly typed, and unconditionally compared")
