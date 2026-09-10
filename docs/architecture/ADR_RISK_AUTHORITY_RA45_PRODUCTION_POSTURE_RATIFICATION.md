# ADR — Risk Authority RA-4.5: Production Posture and Attested Composition Inputs

**Status:** Accepted — §2–§5 ratified, §6 schema decisions ratified in §8 (Amendment 1)
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

## 8. Amendment 1 — the §6 decisions, ratified

§6's five decisions are ruled as follows. The chain they produce:

```
verified envelope → ActionAuthorization binding → internal verified result → RA-4.5 composition
```

No caller-created verdict, posture flag or Python object becomes authority.

**D-A — runtime derivation (option (a)).** `risk-authority-runtime` owns verification and
derivation. It verifies the signed `RiskAuthorizationEnvelope`, binds it to the returned
`ActionAuthorization`, and derives the composition input internally.
`GovernanceInputSource` may supply canonical action/proposal context and the envelope or a
resolvable reference to it, but **may no longer supply an authoritative RA verdict**.
`agent-runtime-governance` stays a transport/pass-through consumer and acquires no
authority logic.

The binding must verify: `ActionAuthorization.envelope_id` matches the verified envelope;
`action_digest` matches the canonical action; `decision` matches the effective authorized
verdict; tenant and scope agree; temporal validity holds under the injected trusted clock;
and signature, issuer, key, revocation and policy bindings are valid.

**D-B — distinct verified-flow type.** `RiskAuthorityMachineResult` is left unchanged for
reference, test and non-authoritative composition use. A distinct exact type is introduced
for the verified production path, produced only inside the runtime after the D-A checks.
It is **not exposed through `GovernanceInputSource`**. Its constructor and exact-type
identity are **not** cryptographic proof — the verified envelope and the binding checks
establish trust; the type exists to prevent accidental mixing of verified and reference
flows. Production composition must not accept a raw `RiskAuthorityMachineResult`.

**D-C — envelope digest at the binding site.** Computed from the exact canonical
`signing_payload()` bytes using the repository's established algorithm and identifier
(`crypto.hashing.sha256_hex`, `sha256:<hex>`). No second signature format; no digest logic
moved into the stdlib-only RA leaf. `envelope_id` is **not** content-addressed to that
payload — it is a caller-supplied parameter of `EnvelopeIssuer.issue` — so the computed
digest is retained in the internal verified binding. No new public envelope field is added
absent a separately demonstrated consumer need.

**D-D — authority-bound applicability.** Policy Authority owns the authoritative rule
declaring whether an action class is subject to Risk Authority. Policy Workflow Compiler
may compile that issued rule into deterministic applicability metadata; it grants no
exemptions and makes no runtime authorization decisions. The runtime resolves and enforces
the issued rule. **Absence, lookup failure, ambiguity or caller omission defaults to
authority required and fails closed.** `resolve(...) → None` may pass through only when an
authenticated, applicable policy explicitly declares the action outside Risk Authority
scope. Deployment configuration alone cannot create that exemption.

**D-E — implicit reference fallback removed at 0.2.0.** Both public classes are retained,
but zero-argument implicit `ReferenceActionGate` construction is eliminated in the next
0.2.0 release, replaced by a stable typed refusal. An explicitly named reference/test
factory and a separate fail-closed production factory are provided. A warning-only
transition is rejected: it would preserve the unsafe ambiguity. The pre-1.0 breaking change
is documented, all in-repository tests and consumers are migrated, and reference-produced
results are proven unable to enter the verified production composition path.

`RiskAuthorizationEnvelope` remains the sole signed machine-authority artifact.
`ActionAuthorization` is its action-specific binding, **not** a second authority artifact.

## 9. Amendment 2 — the caller-supplied clock (issue #1398 item 1)

Ratified after the §8 work shipped. Three decisions, lettered D-A/D-B/D-C within this
amendment — **not** the same letters as §8, which addressed the composition input.

### What the investigation found, and the correction it forced

#1398 item 1 was filed against RA-1→RA-4 and describes a facade exposure that **has since
closed**. `RiskAuthorityApplication` accepts no `now` on any public method (all seven sites
read `self._clock()`), and the HTTP surface exposes only `create_case` and
`authorize_action`, neither taking a time. No facade path and no network path can supply a
clock.

What still takes `now` is the service layer beneath the facade, and that is **not** a
defect: `EnvelopeVerifier.verify`, `check_authority_status` and `EnvelopeIssuer.issue` are
pure functions of an instant, which is what makes a stdlib-only offline leaf deterministic,
replayable from a wheel, and testable without a wall clock.

**The live exposure was introduced by §8's own implementation.**
`RiskAuthorityEnforcer.derive` — added in `d4557c81` as the production entry point that
mints `VerifiedRiskAuthorityResult` — took a bare caller timestamp. That single instant
governed envelope validity, the revocation epoch, and (after `0d012633`) the signing key's
own validity window. Everything else on that path is fail-closed and envelope-bound; the
clock was the one input still taken on trust.

**D-A — clock authority at the composition layer.** `RiskAuthorityEnforcer.production(...)`
requires an injected callable clock and refuses construction without one.
`derive` no longer accepts `now`; it reads the injected clock **once** per call, so the
envelope, the epoch and the key window are all judged at the same instant and a long
derive cannot straddle an expiry boundary. `reference(...)` may take a deterministic clock
(`lambda: FIXED_NOW`) and never claims production posture. **Every RA leaf signature and the
`ActionGatePort` protocol are preserved.**

**D-B — the production-v1 asymmetry is closed.** This **narrowly supersedes** the earlier
ratified rule recorded in the Risk Authority README's *Evaluation-time authority* table
("v1, any mode: honored, exactly as before — unchanged"). Both v1 and v2 production paths
now reject a caller-supplied `evaluation_time` with the same typed
`CALLER_SUPPLIED_EVALUATION_TIME` non-decision, stamped with the trusted clock so a caller
cannot influence even the timestamp of its own rejection. The reason: production v1 and v2
were held to different clock-authority rules in the same seam because of the order they
were built, not because a caller-controlled instant is less dangerous on v1 — it can move
validity and authorization on both. Reference/test mode continues to honor the field for
deterministic replay. This is an intentional security-boundary amendment and a documented
behavior change. No other v1 behavior and no historical record is modified.

**D-C — `StatusAwareActionGate` is unchanged.** Its explicit `now` remains a valid
pure-function service interface. It has no repository consumer and is not a production
authority entry point. Revisit only if a production consumer is commissioned.

### Versions

`ugence-risk-authority` 0.9.0 → **0.10.0** (D-B). `ugence-risk-authority-runtime`
0.2.0 → **0.3.0** (D-A; `derive` drops its `now` parameter and `production()` gains a
required `clock`).

## 10. Amendment 3 — the envelope temporal boundary, made half-open

Ratified after an audit of the boundary asymmetry left open by Amendment 2. Five rulings.

### What the audit found, and why the recommendation was rejected

The audit established that the key interval was half-open, `[not_before, not_after)`, while
the envelope was inclusive, `[not_before, expires_at]`, and recommended **keeping** the
asymmetry on the grounds that the reason keys are half-open — so two adjacent rotation
windows cannot both be live where they meet — cannot arise for envelopes, which are never
chained (issuance always sets `not_before` to its own issuance instant).

**The owner rejected that recommendation, and was right to.** "Envelopes are not chained"
explains why an inclusive upper bound produced no *overlap*; it never explained why a
security validity artifact should remain usable at its own stated expiration instant. The
audit's own evidence made the case against it: at `now == expires_at` the verified path
minted a GRANT with a zero-microsecond-wide effective window, and every consumer downstream
refused it anyway — the credential broker on a zero-width credential window, and
`governance_contracts.Validity` by being structurally unable to construct
`issued_at == expires_at`. The envelope was the last artifact still saying yes at an instant
nothing could act on.

### The rulings

**E-A — the envelope window is half-open.** `not_before <= now < expires_at`. At exactly
`expires_at` an envelope is expired. This supersedes the earlier ratified inclusive reading.
No signed field, canonical byte, digest or signature format changes; an envelope issued
before this amendment still verifies and simply stops authorizing one microsecond earlier.

**E-B — the verified path refuses at equality, by name.** `verify_and_bind` asks the
temporal question before reading the verification result, so exactly `expires_at` yields the
stable typed `RA_EXPIRED` DENY rather than a generic `RA_ENVELOPE_INVALID`. No GRANT is ever
minted whose effective `expires_at` equals the evaluation instant.

**E-C — `ExecutionAuthorization` is ratified as intentionally half-open.** Its
`now >= expires_at` in `cloud-scaling-operations` was correct and is no longer undocumented
divergence.

**E-D — decision expiry is half-open at both issuance paths.** `EnvelopeIssuer.issue` and
the issuance seam refuse `DECISION_EXPIRED` at equality. Previously equality passed the
named check and failed two steps later as a zero-width TTL — the right refusal reason
reached by an accident of arithmetic rather than by the rule the code states.

**E-E — conformance is behavioral, across every site.** All five sites that decide the
envelope window are asserted at `not_before − ε`, `not_before`, `expires_at − ε`,
`expires_at` and `expires_at + ε`, with a negative control proving the suite rejects the
superseded inclusive rule. The source-text tripwire is retired as normative proof:
equivalent correct code can spell the comparison many ways, so a substring assertion fails
on a correct refactor while passing on any rewrite that keeps the string.

### Two findings the implementation surfaced

`[V]` **`ActionAuthorization.expires_at` needed the same move.** It is copied verbatim from
the envelope at admission, so leaving its check inclusive would have let the derived
artifact outlive by one instant the envelope it derives from — an inconsistency created by
E-A itself. Corrected in the credential broker under E-A rather than deferred.

`[G]` **The `valid_until` family is untouched and still inclusive.** `domain/evidence.py`,
`domain/binding.py`, `domain/controls.py`, `SubjectContext.subject_valid_until` and
`AuthorityGrant.is_active` all remain `now <= bound`. They answer "is this observation still
fresh", not "may this act now". Whether they should move is a separate question and is
**not** ruled on here — the "one temporal rule" statement is scoped to authorization
validity windows and says so.

### Versions

`ugence-risk-authority` 0.10.0 → **0.11.0** (E-A, E-D).
`ugence-risk-authority-runtime` 0.3.0 → **0.4.0** (E-B).
`ugence-risk-authority-status-runtime` 0.2.0 → **0.3.0** (reaper reflects the new window).
`ugence-cloud-scaling-credential-broker` 0.1.0 → **0.2.0** (E-A on envelope and
authorization bounds).

## 7. Invariants this ADR does not touch

The composition engine mints no authority. Deployment assertions are not proof. Only the
verified signed envelope authorizes machine action. Decision Authority and ActionGate remain
additive and may only subtract. `FinalAuthority ≤ RiskAuthority` and
`FinalScope ⊆ RiskAuthorityScope` stand. F-D (#1397) is not closed and no F-D dimension is
claimed as enforced.
