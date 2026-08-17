# Ugence Cloud Scaling Risk Integration

**Distribution:** `ugence-cloud-scaling-risk-integration` · **Import package:** `ugence_cloud_scaling_risk_integration` · **Version:** `0.1.0`

Cloud Scaling **Phase 4C**: a one-way, non-executing adapter that projects an advisory
`CapacityActionRecommendation` into the Risk Authority v2 neutral subject-risk contract
and **stops at a non-executable risk decision**.

```
ugence-cloud-scaling-controller (advisory leaf) ─┐
                                                  ├─► ugence-cloud-scaling-risk-integration ─► RiskEvaluationSeam
ugence-risk-authority (stdlib-only leaf) ────────┘        (projection + one seam call)              │
                                                                                                     └─► SubjectRiskDecision (non-executable)
```

Neither dependency imports this package. The controller stays an advisory leaf; Risk
Authority stays a stdlib-only leaf.

---

## What this package is not

It owns **no runtime and no authority**. It holds no policy, no control catalog, no
evidence source, no keys, no credentials, no clock and no execution surface. It does not
issue authorization envelopes, invoke ActionGate, mint or broker credentials, call a
cloud-provider API, scale anything, verify an effect, or learn from outcomes.

Phase 5 (envelope issuance, ActionGate authorization, provider execution) and Phase 6
(effect verification, recommendation learning) remain excluded, and no capability toward
either is introduced here. Stated at the precision the tests actually check: envelope
issuance, ActionGate invocation, credential issuance, provider execution, effect
verification and learning are **not implemented in this package, not imported by any
module of this package, not publicly exported by this package, and not called by any
Phase 4C path**. That is deliberately narrower than "not reachable in the process": Risk
Authority may transitively load envelope- or ActionGate-related modules through its own
package initialization, and claiming otherwise would be false. Every outcome carries
`authorization_performed`,
`envelope_issued`, `actiongate_invoked`, `credential_issued`, `actuation_performed`,
`effect_verified` and `executable` fixed `False` — and a forged `True` on a returned
decision is **rejected**, never normalized.

---

## The authenticity boundary — what Phase 4C proves, and what it does not

This is the part worth reading carefully. The four levels below are genuinely different
claims, and conflating them would overstate the guarantee.

| Level | Established by | Status after Phase 4C |
|---|---|---|
| **Canonical consistency** — the request's carried digests reconcile with its content | `validate_subject_binding` (Phase 4A/4B) | ✅ established |
| **Recommendation authenticity** — the `recommendation_digest` corresponds to a real controller recommendation whose content hashes to an independently carried expectation | **this package** (Phase 4C) | ✅ established, with the limits below |
| **Evidence provenance** — the referenced evidence is admitted, trusted and fresh | RA-5, behind the seam | ⛔ not this package's question |
| **Risk evaluation → authorization → execution** | Risk Authority / Phase 5 | ⛔ excluded |

### What Phase 4C proves

For a **canonical serialized recommendation**, the adapter:

1. accepts only the **exact** canonical controller type or its canonical serialized form
   — a duck-typed look-alike *and a subclass* are refused at the type boundary, before
   anything on the object is invoked (see "Exact-type admission" below);
2. reconstructs it through the controller's own strict `from_dict`, which rejects unknown
   and missing fields and re-runs the full `__post_init__` revalidation (digest
   rebinding, candidate-set equality, score/feasibility/cost recomputation, temporal
   safety);
3. **independently recomputes** `rec.digest()` from that reconstruction;
4. requires equality with the **independently carried** `evidence_digest` from the input
   document.

Step 4 is genuinely independent, and that is the load-bearing fact: the controller's
`from_dict` accepts `evidence_digest` as a known field but **never validates it and never
passes it to the constructor**. The recomputed value derives purely from the record's
*content*; the compared value comes purely from the *input document*. A payload whose
content was altered while `evidence_digest` was left stale reconstructs cleanly and is
then rejected here. This is **not** the vacuous self-referential check
(`rec.digest() == rec.digest()`), which would prove nothing and which this package
explicitly refuses to perform.

### Exact-type admission

Admission is `type(source) is CapacityActionRecommendation`, **not** `isinstance`. Every
value the adapter reads — `digest()`, `to_canonical_dict()`, `_digest_payload()`, the
embedded objects' serializers — is reached through dynamic dispatch, so a subclass
overriding any one of them controls what gets "recomputed". Recomputing with the unbound
base method is *not* a sufficient fix: `CapacityActionRecommendation.digest(source)`
still calls `self._digest_payload()` → `self.to_canonical_dict()`, so an override further
down the chain is reached anyway and silently produces a digest over attacker-supplied
content. The guard therefore runs **before any attribute of the object is touched**;
only `type()` and `isinstance()` are consulted.

A caller holding a legitimate subclass is not locked out: serialize it and submit the
canonical document, which reconstructs an exact base instance and re-digests from
content. (Note that the *document* produced by a hostile subclass is untrusted too — its
`evidence_digest` is filled via `self.digest()` — but the serialized path recomputes from
content and rejects the mismatch, which is the correct outcome.)

For a **live in-process object** there is no carried digest — `evidence_digest` is
excluded from the dataclass and computed on demand — and the object has already passed
`__post_init__` by construction. The caller must therefore supply
`expected_recommendation_digest` from an independent source. Without one the adapter
**fails closed** rather than claiming an authenticity it cannot establish.

### The authenticated token's own integrity invariant

`AuthenticatedRecommendation` is the **token** every downstream consumer trusts: holding
one is what entitles a caller to project a recommendation into a v2 request. So the token
must not be able to lie about itself. This invariant is enforced:

```
token.recommendation_digest == token.recommendation.digest()
```

It is checked in `__post_init__`, so **no supported construction can mint a mismatched
token** — a hand-built token pairing an exact canonical recommendation with a
syntactically perfect but incorrect digest is refused. And it is **re-checked at every
consumption boundary** (`project_recommendation`, `CloudScalingRiskAdapter.project`,
`CloudScalingRiskAdapter.evaluate`), which is the load-bearing half: a frozen dataclass is
not a security boundary. `object.__new__` skips `__post_init__` entirely,
`object.__setattr__` rewrites a frozen field afterwards, and a token *subclass* can make
`recommendation` a property returning a different object on each read — against which
"validate, then use" is not a defence at any level of care, because the value validated is
by construction not the value consumed.

Consumers therefore require the **exact** `AuthenticatedRecommendation` type, not
`isinstance`, before reading anything; establish the **exact** embedded
`CapacityActionRecommendation` type before invoking `digest()`, so the recomputation
cannot be redirected by subclass dispatch; and use the values the check returned rather
than re-reading the token. Every rejection is a controlled typed failure raised **before**
any clock read, any `SubjectContext`, any `SubjectBinding`, any v2 request and any seam
call — asserted as such in `tests/test_token_integrity.py`, which counts clock reads,
construction calls, seam calls and resolver calls rather than only checking the error.

`AuthenticatedAbstention` gets the symmetric exact-type treatment. No digest semantics are
invented for abstentions — `abstention_digest` remains optional — but a digest that *is*
carried must describe the carried abstention.

**This is content integrity, not signed producer authenticity.** It proves the token's
digest describes the token's content; it proves nothing about who authored that content,
and it narrows none of the limits below.

### What Phase 4C does **not** prove

- **It is not a signature.** The controller digest is a canonical content *identity* over
  an unkeyed SHA-256 with a domain-separated preimage. It proves the content hashes to
  the expected value; it proves nothing about **who** produced it.
- **The expectation's own provenance is assumed.** On the object path the adapter cannot
  verify where `expected_recommendation_digest` came from. A caller that computes it from
  the same object it passes in has performed the self-referential check itself, and the
  adapter has no way to detect that.
- **A fully self-consistent forgery still passes.** An attacker able to author a
  complete, internally valid `CapacityActionRecommendation` and serialize it with a
  matching `evidence_digest` produces an authentic-looking input. Detecting that requires
  a signed provenance chain over the controller's output, which does not exist anywhere
  in the repository today and which Phase 4C does not invent. No placeholder
  authenticator was added, because a placeholder would read as a control while providing
  none. **The token-integrity invariant above does not narrow this**: such a forgery
  satisfies it precisely because the forgery *is* content-consistent. That case is
  asserted as a passing test rather than left implicit.
- **Subject-digest equality is not whole-request authenticity.** Per ADR Amendment 3,
  substituting a *routing* field (`requested_purpose`, `requested_domain`,
  `requested_risk_class`, `requested_scope`, `evidence_references`) moves `request_digest`
  only and leaves `subject_digest` byte-identical. Those fields have their own commitment
  and their own controls.

### The remaining upstream trust assumption

Phase 4C trusts that the canonical recommendation document — or the independently carried
digest expectation — reached the adapter over a channel the composition root trusts.
Establishing *that* is a transport/provenance concern and remains unaddressed.

---

## Public API

```python
from ugence_cloud_scaling_risk_integration import (
    CloudScalingRiskAdapter,          # the production entry point
    RiskEvaluationSeamPort,           # the narrow production-facing seam port

    project_recommendation,           # deterministic recommendation -> v2 request
    build_idempotency_key,            # the D-6 formula
    CapacityRiskSubjectProjection,    # the reconciled binding chain

    authenticate_controller_output,   # the authenticity boundary
    AuthenticatedRecommendation, AuthenticatedAbstention, DigestExpectationSource,

    CloudScalingRiskOutcome,          # the typed adapter outcome
    AdapterOutcomeStatus, AdapterRejectionReason,

    PURPOSE_CAPACITY_ACTION, DOMAIN_CLOUD_SCALING,     # D-4 ratified identifiers
    SUBJECT_TYPE_CAPACITY_SUBJECT, CANONICAL_ACTION_TYPES, canonical_action_type,
)
```

### Usage

```python
adapter = CloudScalingRiskAdapter(
    seam=production_seam,   # an ALREADY-CONSTRUCTED RiskEvaluationSeam.production(...)
    clock=trusted_clock,    # the same trusted clock the seam was given
)

outcome = adapter.evaluate(recommendation.to_canonical_dict())

if outcome.status is AdapterOutcomeStatus.RISK_DECISION:
    decision = outcome.decision          # non-executable SubjectRiskDecision
elif outcome.status is AdapterOutcomeStatus.PROJECTION_ABSTAINED_UPSTREAM:
    reason = outcome.abstention_reason   # the controller's typed abstention reason
else:
    reason = outcome.rejection_reason    # a typed AdapterRejectionReason
```

`outcome.grants_authority` is always `False`, on every status. A risk **PASS** is not an
authorization.

---

## D-4 ratified identifiers

| | Value |
|---|---|
| `requested_purpose` | `cloud_scaling.capacity_action` |
| `requested_domain` | `cloud_scaling` |
| `subject_type` | `cloud_scaling.capacity_subject` |
| `action_type` ∈ | `no_change`, `scale_up`, `scale_down`, `coordinated` |

The action types are the controller's exact canonical `ActionKind` values, with no
aliases and no translation table — the set is asserted against `ActionKind` at **import
time**, so controller-side drift fails this package closed rather than projecting an
unratified value.

`subject_type` is the one identifier ratified differently from the ADR's original
proposal (which reused `cloud_scaling.capacity_action` for both purpose and subject
type). It names *what* is evaluated rather than *why*; collapsing the two would make the
routing purpose and the subject identity indistinguishable in an audit record. D-4 was
explicitly unratified and Phase 4B froze none of it, so this is a ratification rather than
a contract change — no frozen schema, digest or Risk Authority behavior moves.

---

## The projection

Curated neutral facts only, populated **field by field**. The controller's
`to_canonical_dict()` is never handed to the Risk Authority canonicalizer, so the
controller's float-valued analytics (confidence, forecast coverage, cost ratios,
`timing_seconds`) have no path into the Risk Authority digest chain.

| `SubjectContext` field | Source |
|---|---|
| `environment` / `region` / `zone` | `subject.environment` / `.region` / `.zone` |
| `compute_group` | `subject.cluster` |
| `resource_class` | `subject.resource_id` |
| `action_type` | `selected_plan.action_kind.value` |
| `magnitude_before` / `magnitude_after` | the selected plan's **primary** `ResourceChange` |
| `subject_asserted_at` / `subject_valid_from` | `recommendation_time` (canonical UTC) |
| `subject_valid_until` | `recommendation_time + validity_seconds` |

`tenant_id`, `subject_id`, `recommendation_digest` and `evidence_references` are
authoritative on the **outer request only** and appear nowhere inside `SubjectContext` —
the closed v2 contract has no field for any of them, so there is structurally no second
source to disagree. Evidence references are validated, deduplicated and canonically
ordered. Missing optionals stay the explicit `null` sentinel and are never coerced to
`""` or `0`; a naive timestamp is rejected rather than assumed UTC; a non-NFC string is
rejected rather than silently normalized.

### Time authority

The adapter never populates `evaluation_time` — there is no API parameter that could set
it, and the request always carries `None` so the seam uses its own trusted clock as the
sole evaluation-time authority. The injected clock is used **only** for the adapter-side
expiry re-check and is never forwarded.

**Composition requirement:** inject the *same* trusted clock into the adapter and the
seam. They read different clock objects, and if they disagree across a validity boundary
the seam's check governs and fails closed — the disagreement can never open the window,
only close it.

The D-6 idempotency key is `digest(tenant_id + subject_id + recommendation_digest +
purpose + request schema_version)` — deliberately **timestamp-free**, so it is stable
across retries of the same recommendation and is never a nonce.

### One boundary the adapter does not police

It cannot verify that an injected seam is production-grade: the seam exposes no public
production flag, and inferring one from a private attribute would be a guess dressed as a
control. Supplying a seam built by `RiskEvaluationSeam.production(...)` — which itself
fails closed on any reference-grade dependency — is the composition root's
responsibility.

---

## Abstention

A `RecommendationAbstention` produces a typed **non-evaluation**. It is never converted
into a scaling recommendation, never enters the evaluation seam, never manufactures a
subject digest, never produces PASS/ALLOW/authorization, and never triggers ActionGate or
execution. Its typed reason and whatever input digests the controller had bound before
abstaining are preserved so the record is auditable — and nothing beyond them is claimed,
because nothing beyond them was evaluated. In particular `recommendation_digest` stays
`None`: there was no recommendation.

---

## Development

```bash
# Test from a bare checkout (no editable install required)
python -m pytest packages/integration/cloud-scaling-risk-integration/tests -q

# Build
python -m build packages/integration/cloud-scaling-risk-integration

# Offline isolated-installation stage verification (source-vs-installed digest equality).
# Phase A of this script is ONLINE by design; phase B is the offline stage it verifies.
# See the phase table below.
python packages/integration/cloud-scaling-risk-integration/scripts/verify_isolated_install.py
```

**The verifier run as a whole is not offline, and does not claim to be.** It has
distinct phases, and only one of them is the guarantee:

| Phase | Network | What it does |
|---|---|---|
| **A** | **online** | builds the first-party wheels and downloads the full dependency closure (including numpy) into a local wheelhouse |
| **B** | **genuinely offline** | installs into a throwaway virtualenv from that wheelhouse alone — this is the isolated-installation stage being verified |
| **C** | offline | negative controls on the phase-B guarantee |
| **D** | offline | behavior probes inside the isolated environment |

Phase A must reach an index; that is what collecting a dependency closure means. The
claim under test is scoped to **phase B**, and the closing banner names it:
`OFFLINE ISOLATED INSTALLATION STAGE VERIFIED`.

Inside phase B the index is disabled by `--no-index` and `PIP_NO_INDEX=1` — those two are
the actual prohibition. The unroutable sentinel index URL is **defense in depth**: it
supplies no protection of its own, and exists so that if a future edit dropped a flag,
resolution fails loudly against an unroutable host instead of quietly succeeding against
the real PyPI. Phase B additionally uses no cache, no pip upgrade and no editable install.

Phase C proves the guarantee by negative control rather than asserting it: a missing wheel
fails the install, a bogus index cannot rescue it, and a failed install leaves nothing
importable. The banner is printed only after all eight steps record completion, and any
failed subprocess exits non-zero.

The suite includes **gate-removal probes** (`tests/test_gate_removal_probes.py`): each
disables one security gate and asserts the corresponding attack *now succeeds*. A probe
that fails means the gate it targets was not what was stopping the attack, and the
adversarial test guarding it is weaker than it looks.

## References

- `docs/architecture/ADR_CLOUD_SCALING_RISK_AUTHORITY_INTEGRATION_PHASE4.md`
  (§5, §7, §10–§14; Amendments 1–4)
- `docs/architecture/RISK_AUTHORITY_EVALUATION_SEAM.md`
