# ADR — Risk Authority RA-4.5: Production Posture and Attested Composition Inputs

**Status:** Accepted (rulings recorded; implementation gated on the schema decisions in §6)
**Date:** 2026-09-09
**Owners:** Ugence platform architecture
**Related:**
- [`ADR_RISK_AUTHORITY_RA45_GOVERNANCE_COMPOSITION.md`](./ADR_RISK_AUTHORITY_RA45_GOVERNANCE_COMPOSITION.md) — the composition this ADR gives a production posture to
- [`ADR_CLOUD_SCALING_PHASE5C_ACTION_ADMISSION_SCOPING.md`](./ADR_CLOUD_SCALING_PHASE5C_ACTION_ADMISSION_SCOPING.md) — the RA 0.8 seam this ratification deliberately does **not** adopt
- [`RISK_AUTHORITY_RA45_IMPLEMENTATION_REPORT.md`](./RISK_AUTHORITY_RA45_IMPLEMENTATION_REPORT.md) — "production deployment validation remains pending", which this ADR converts into named requirements
- Issue #1397 (F-D), #1398 (F-G), #1399 (F-H) — open, unchanged by this ADR

> *This ADR records owner rulings. Of the four, only ruling 4 (dependency floors) is
> applied in the same change. Rulings 1 and 3 touch public API and are gated on the
> schema and compatibility decisions in §6, which are open. No authority boundary,
> digest, serialization, frozen identifier or signature format is changed here, and
> none may be changed to satisfy this ADR without a further ruling.*

---

## 1. What prompted this

An audit of `packages/integration/risk-authority-runtime` reported that
`RiskAuthorityEnforcer` defaults to `ReferenceActionGate()` with no production posture
gate, unlike `ActionAdmissionSeam.production(...)` in the RA 0.8 kernel, which refuses a
reference gate, refuses a port that has not declared `is_production_authoritative`, and
exposes `is_production`.

A read-only investigation **corrected that finding and found a different one.** Both are
recorded, because the correction is what makes the ruling in §2 the right shape.

**Corrected:** `RiskAuthorityEnforcer` is unreached. Repo-wide it appears only in its own
`__init__.py` export and the runtime's `tests/conftest.py:243`. No downstream package
constructs one. The same silent `gate or ReferenceActionGate()` default exists in
`StatusAwareActionGate` (`risk-authority-status-runtime`, `enforcement.py:85`) and is
likewise unreached. Neither default is on a live path today.

**Found instead:** every downstream consumer calls `RiskAuthorityCompositionEngine.compose`
with a `RiskAuthorityMachineResult` it supplied itself, through the `GovernanceInputSource`
Protocol (`agent-runtime-governance/interfaces.py:54`), which a *deployment* implements.

- `compose` performs no type validation on its three inputs.
- `RiskAuthorityMachineResult` is a plain frozen dataclass with no `__post_init__`.
- `CompositionInputs` has no `__post_init__`; the hook checks only
  `isinstance(inputs, CompositionInputs)` (`hook.py:190`) — the container, not the verdict.
- `source_version` carries `risk_authority.__version__`, identical under any gate, so
  nothing records which enforcement produced an `ALLOW`.
- `governed-review`'s "production `GovernanceInputSource`" is a wrapper that delegates to
  "a deployment's real input source".

No package in this repository constructs a production `RiskAuthorityMachineResult` from an
actual Risk Authority enforcement path. The chain terminates outside the tree, and the
composition layer's `FinalAuthority ≤ RiskAuthority` invariant — asserted "by construction"
in the package README — in fact holds only if the caller's supplied verdict was genuine.

**Existing mitigation, genuine and retained:** the RA-6 commit-point recheck
(`make_pre_effect_recheck`) calls `risk_authority.services.authority_status.check_authority_status`
— a Risk Authority kernel function taking a `key_ring` and an injected `clock`, not a
reference gate.

---

## 2. Ruling 1 — a deployment-supplied `RiskAuthorityMachineResult` is not a trust boundary

A raw machine result supplied through `GovernanceInputSource` is **non-authoritative**,
regardless of its Python type or any caller-populated posture field. Only a successfully
verified, signed `RiskAuthorizationEnvelope` carries machine authority.

The runtime composition path must require the RA result to be cryptographically bound to an
existing `RiskAuthorizationEnvelope`, **or derive the result from that verified envelope**.
Reuse the canonical envelope and verification path. **Do not create a parallel attestation
authority or an independent signature format.**

The binding must cover at least: the effective verdict; canonical action identity/digest;
authority and policy identity; scope; temporal validity; and envelope identity/digest.
Verification must fail closed on missing, invalid, expired, revoked, mismatched or
unresolved authority evidence.

A posture field may be recorded **for diagnostics only**. It is not proof. A constructor
guard alone is likewise insufficient — deployment code can construct the object.

RA-6 commit-point rechecking remains mandatory defense in depth and is **not** a substitute
for authenticating the upstream RA result. `resolve(...) → None` may pass through only when
trusted policy resolution establishes the action is not authority-bound; **caller omission
alone must not establish exemption.**

## 3. Ruling 2 — RA-4.5 ratified as a pre-RA-0.8-seam composition layer

RA-4.5 remains the fail-closed **production** composition layer above the RA-1→RA-4 spine.
It does not adopt or duplicate RA 0.8's `ActionAdmissionSeam`, and the composition engine
remains independent of gate implementation details.

"Pre-seam" means RA-4.5 predates and does not consume the RA 0.8 seam. It does **not** mean
RA-4.5 is research-only or intrinsically non-production. Production eligibility depends on
authenticated inputs, including the envelope binding ruled in §2.

## 4. Ruling 3 — gate the reference-defaulting classes, do not delete them

`RiskAuthorityEnforcer` and `StatusAwareActionGate` are retained for compatibility and
reference/test use: repository non-use does not prove no external consumer exists.

Their implicit `ReferenceActionGate` construction must never be production-eligible. Add an
explicit reference/test construction path and a fail-closed production construction path.
Reference-mode instances and their outputs must be unmistakably non-production and
**incapable of satisfying the attested-input requirement** of §2. The existing default must
not be silently converted into production behavior. If removing the implicit default is a
breaking public-API change, deprecate now and remove only at the appropriate version
boundary.

## 5. Ruling 4 — dependency floors corrected (applied)

| Distribution | Was | Now | Why |
|---|---|---|---|
| `ugence-risk-authority` | `>=0.1.0` | `>=0.4.0` | The RA-1→RA-4 spine the composition is specified against. **Not** `>=0.8.0` — §3 does not adopt `ActionAdmissionSeam`, and that floor would misstate this package as seam-adopting. |
| `ugence-decision-authority` | `>=0.1.0` | `>=1.0.0` | The distribution's first and frozen release; `>=0.1.0` admitted versions that never existed. The adapter matches the `DecisionOutcome` values 1.0.0 froze. |
| `ugence-actiongate-provider` | `>=0.1.0` | `>=0.1.0` | Retained — the provider's current version. |

Verified through the isolated-wheel installation probe
(`scripts/verify_isolated_install.py`), which installs from the declared dependencies and
imports all three distributions: **PASS**. The probe proves the corrected floors resolve; it
does not prove they are minimal.

---

## 6. Open — schema and compatibility decisions, reported before any public-field change

§2 requires reporting these before `RiskAuthorityMachineResult`'s public fields change.
**No public field is changed by this ADR.**

The load-bearing discovery: **the binding artifact §2 asks for already exists in the RA
kernel and is already produced on the canonical path.** `ActionAuthorization`
(`risk_authority/domain/actions.py:48`) carries `authorization_id`, `envelope_id`,
`action_digest`, `decision`, `tenant_id`, `reason_codes` and `expires_at`. It is the return
value of `ActionGatePort.authorize`, and `RiskAuthorityEnforcer` today receives it and
**discards everything except `decision` and `reason_codes`**. Every element §2 enumerates is
therefore available from `(verified envelope, ActionAuthorization)` with no new schema and
no new signature format:

| §2 requires | Source | Present |
|---|---|---|
| effective verdict | `ActionAuthorization.decision` | yes |
| canonical action identity/digest | `ActionAuthorization.action_digest` / `CanonicalAction.digest` | yes |
| authority and policy identity | envelope `decision_id`, `issuer`, `key_id`, `bindings.workflow_ir_digest` | yes |
| scope | `envelope.scope` | yes |
| temporal validity | `envelope.not_before` / `expires_at` | yes |
| envelope identity/digest | `envelope.envelope_id`; digest over `envelope.signing_payload()` | id yes; digest has no named helper |

The decisions that remain are about **where verification runs** and **which package absorbs
the breaking change** — not about inventing a schema.

**D-A — where the derivation happens.** Either (a) the runtime derives: `compose` accepts
only a result minted by the runtime's own enforcer from a verified envelope, or (b) the
consumer derives: `GovernanceInputSource` returns envelope + action + verification inputs
and `agent-runtime-governance` performs the derivation. (a) keeps authority logic in the
package that owns it and makes `agent-runtime-governance` a pass-through; (b) spreads
verification into a consumer. **Recommended: (a).**

**D-B — new attested type, or new fields on the existing one.** Adding `envelope`/
`authorization` fields to `RiskAuthorityMachineResult` does not by itself satisfy §2, since
deployment code can populate them — and §2 forecloses relying on a constructor guard. A
distinct type mintable only by the verifying path (exact-type admitted at the boundary, as
Phase 4C and RA 0.8 already do) is what lets §4's requirement that reference-mode outputs be
"incapable of satisfying the attested-input requirement" be expressed at all. **Recommended:
a new attested type; leave `RiskAuthorityMachineResult` unchanged for reference/test use.**

**D-C — envelope digest helper.** §2 names "envelope identity/digest". `envelope_id` exists;
a named envelope-digest helper does not. Either compute `digest(signing_payload())` at the
binding site, or add a helper to the stdlib-only RA leaf (additive, but a change to the
kernel). **Recommended: compute at the binding site**, adding nothing to the leaf.

**D-D — who owns "not authority-bound".** §2 says `resolve(...) → None` may pass through
only under trusted policy resolution. Today it is caller omission
(`risk-authority-status-runtime/enforcement.py:187-188`), a fourth package. This needs an
owner and a policy source before the pass-through can be called trusted.

**D-E — deprecation mechanics for §4.** `RiskAuthorityEnforcer()` and
`StatusAwareActionGate()` currently accept zero arguments. Making the reference path
explicit is a breaking change to two packages at 0.1.0. Decide the deprecation signal
(warning vs. typed refusal) and the version boundary for removal.

---

## 7. Invariants this ADR does not touch

The composition engine mints no authority. Deployment assertions are not proof. Only the
verified signed envelope authorizes machine action. Decision Authority and ActionGate remain
additive and may only subtract. `FinalAuthority ≤ RiskAuthority` and
`FinalScope ⊆ RiskAuthorityScope` stand. F-D (#1397) is not closed and no F-D dimension is
claimed as enforced.
