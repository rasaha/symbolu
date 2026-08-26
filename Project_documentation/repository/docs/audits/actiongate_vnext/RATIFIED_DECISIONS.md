# ActionGate vNext — ratified decisions and dimension matrix

Status: **owner-ratified**. Supersedes nothing; this is the first decision record
for the ActionGate vNext evaluator. It records what was decided, what was built
against it, and what remains open.

Audit basis: the two read-only audits of `packages/providers/actiongate`,
`cyber_security/action_gate_reference`, `packages/governance-contracts`,
`packages/governance-provider-framework`, and
`packages/capabilities/action-clearance`.

## The defect this addresses

`[V]` The pre-vNext ActionGate engine branched solely on `action_type`
(`core.py:151-168`). Seven mapped governance dimensions — principal, authority,
resource, parameters, risk_context, evidence_refs, decision_refs — were never
read. Two requests differing in all seven, plus `authorization_expired`,
produced a byte-identical `AUTHORIZED` result with the identical fingerprint
`fff2e619615b`.

`[V]` Every test asserting those dimensions was a `map_request` *preservation*
assertion. Twelve such assertions existed; none asserted that changing a
dimension changed an outcome. A field can survive a mapping perfectly and still
be inert.

`[V]` `authorization_expired` was the one neutral field `map_request` dropped
entirely, while `ActionGovernanceControlPlaneAdapter` computes it
(`action_to_control_plane.py:91`) and the framework's own reference provider
honours it (`reference/action.py:64`).

## Ratified decisions

**D1 — collapsed outcome tiers: reason codes only.**
The reference evaluator's `REQUEST_MORE_EVIDENCE`, `SIMULATE_AND_RETRY` and
`ESCALATE_TO_HUMAN` are carried as reason codes on a single neutral
`INDETERMINATE`, not as new `ActionGovernanceOutcome` values. `[R]` Rationale:
adding neutral enum values is a MAJOR on the shared
`governance_providers.api` surface and would oblige every action provider and
the kernel `OUTCOME_MAP` to absorb it, not just ActionGate. Accepted cost: a
consumer reading only the outcome enum sees three distinct situations as one.

**D2 — dimension posture: hard/soft split.**
Authority, principal and decision-reference failures are boundary violations
(`DENIED`). Risk and evidence failures are uncertainty (`INDETERMINATE`).
`[R]` Rationale: mirrors the reference evaluator, where `_priv_monotonic` is a
hard pre-check yielding `DENY` but an unmet `MUST_HAVE` evidence rule yields
`REQUEST_MORE_EVIDENCE`; and honours `AUTHORIZATION_BOUNDARY.md`'s prohibition
on silently elevating missing authority.

**D3 — equivalence baseline: add a second, keep `before`.**
`actiongate_equivalence_before.json` remains the pre-migration proof; a
post-semantics baseline is added when semantics actually move. `[R]` Rationale:
regenerating in place would permanently destroy the only evidence that the
canonical package ever matched the legacy implementation byte-for-byte.
**Not yet acted on** — no semantics have moved (see "Gate status"), so a second
baseline would today be a duplicate of the first.

**D4 — CABP signing domain: deferred, recorded as a gap.**
`[G]` `grep -rn "CABP"` returns zero hits repository-wide. There is no CABP
domain tag, keyring entry, entitlement value, signing-input guard, verifier,
trust-anchor record, or revocation path. `[R]` Rationale for deferring: domain
ownership is a design decision, and the Trusted Evidence Authority's own ADR
§13.3 requires a domain tag be "fixed before signing exists" — pre-committing an
owner for an artifact class that has no definition inverts that rule.

**D5 — shared severity primitive: keep independent (default, not ratified).**
`[R]` `ugence_action_clearance.combine_statuses` and the reference evaluator's
`_SEVERITY` implement the same least-permissive-wins rule twice. They stay
separate: making ActionGate depend on `action-clearance` would invert the
layering, since Clearance is strictly downstream. Open for owner correction.

## Dimension matrix

`[I]` `resource` and `parameters` were not named in D2 and are inferred from the
same posture.

| Dimension | Posture | Condition | Tier | Reason code |
|---|---|---|---|---|
| `action_type` | hard | in denied set | DENIED | `POLICY_DENIED` |
| `action_type` | hard | in unknown set | ESCALATION_REQUIRED | `POLICY_UNKNOWN` |
| `authority` | hard | required, absent | DENIED | `AUTHORITY_ABSENT` |
| `authority` | hard | present, not accepted | DENIED | `AUTHORITY_INSUFFICIENT` |
| `principal` | hard | required, empty | DENIED | `PRINCIPAL_UNRESOLVED` |
| `principal` | hard | outside allowlist | DENIED | `PRINCIPAL_UNRECOGNIZED` |
| `decision_refs` | hard | required, absent | DENIED | `DECISION_REF_MISSING` |
| `resource` `[I]` | hard | required, empty | DENIED | `RESOURCE_UNRESOLVED` |
| `resource` `[I]` | hard | outside permitted prefixes | DENIED | `RESOURCE_NOT_PERMITTED` |
| `parameters` `[I]` | mixed | exceeds `deny_above` | DENIED | `PARAMETER_LIMIT_EXCEEDED` |
| `parameters` `[I]` | mixed | above `constrain_above` | AUTH_W_CONSTRAINTS | `PARAMETER_BOUND_APPLIED` |
| `parameters` `[I]` | mixed | bound declared, unparseable | EVIDENCE_REQUIRED | `PARAMETER_UNRESOLVED` |
| `risk_context` | soft | required, absent | EVIDENCE_REQUIRED | `RISK_CONTEXT_UNAVAILABLE` |
| `risk_context` | soft | in deny scores | DENIED | `RISK_THRESHOLD_EXCEEDED` |
| `risk_context` | soft | in constrain scores | AUTH_W_CONSTRAINTS | `RISK_THRESHOLD_CONSTRAINED` |
| `evidence_refs` | soft | below minimum | EVIDENCE_REQUIRED | `EVIDENCE_INSUFFICIENT` |
| `policy_context` | soft | required, absent | ESCALATION_REQUIRED | `POLICY_NO_RULE` |
| `authorization_expired` | terminal | true | EXPIRED | `AUTHORIZATION_EXPIRED` |
| tenant / correlation / idempotency | binding only | — | — | not dispositive |

Precedence, non-compensatory and least-permissive-wins, ported from
`action_gate_ref/gate.py:37-38` with `EXPIRED` inserted below `DENIED` because
expiry is evaluated before policy is consulted at all:

    EXPIRED < DENIED < EVIDENCE_REQUIRED < SIMULATION_REQUIRED
            < ESCALATION_REQUIRED < AUTHORIZED_WITH_CONSTRAINTS < AUTHORIZED

A policy may **elevate** a soft finding; it may never **soften** a member of
`NON_SOFTENABLE` (the hard dimensions plus expiry), because a policy able to
downgrade a boundary violation could authorize its way around the boundary.

## What was built

| Step | Delivered | Status |
|---|---|---|
| 2 | `cyber_security/action_gate_reference/pyproject.toml` (pytest rootdir only) and `.github/workflows/action-gate-reference-ci.yml` | done — 195 tests now gated, previously ungated |
| 3 | `ugence_actiongate_provider/vnext/` — closed reason-code catalogue, severity lattice, dimension policy model, evaluator | done — staged, not on the public API surface |
| 4 | `tests/vnext/` — 52 tests, each asserting an outcome *change* | done |
| 5 | `authorization_expired` wired through `map_request` + native `EXPIRED` outcome | done — MAJOR, in its own commit |

`[V]` The reference harness is **not** installable as a wheel:
`action_gate_ref.conformance` resolves fixtures as
`Path(__file__).parent.parent / "fixtures"`, a source-checkout layout. The
`pyproject.toml` added here declares no build system and no distribution
metadata for exactly that reason. Making it installable requires moving fixtures
into package data first.

`[V]` The vNext subpackage is deliberately absent from
`ugence_actiongate_provider.api.__all__`. Everything on that surface is covered
by a literal snapshot hash. Staging the evaluator off-surface keeps the
semantics reviewable while leaving the versioned decision to add it separate.

## Gate status

Steps 2–4 (MINOR) moved no frozen hash. Step 5 (MAJOR) re-baselined four, each
deliberately:

| Gate | Before | After step 5 |
|---|---|---|
| ActionGate `.api` snapshot | `9eeb66e3…` | `5334cca1…` |
| `public_api_manifests["actiongate_provider.api"]` | `9eeb66e3…` | `5334cca1…` |
| `core_tree_hashes["actiongate_provider"]` | `9cbeb833…` | `a0010fcf…` |
| `conformance_hashes[…ugence_actiongate_provider]` | `07e08bd4…` | `ff605bf9…` |
| behavioural-equivalence `capture_hash` | `d805e6cf…` (kept as `before`) | `e1ff5d2a…` (new `after_semantics` baseline) |
| `core_tree_hashes` for the other three trees | — | unmoved |
| `public_api_manifests` for the other three modules | — | unmoved |
| clean-wheel dependency verification | — | PASS, no dependency added |

`[V]` The facade tree moved exactly once: `actiongate_provider/tests/` was
touched only in the step-5 commit.

Suites: 258 passed (ActionGate packages, facade, and provider framework);
195 passed (reference harness). Six failures elsewhere
(`governance-contracts` packaging, `ai-hiring` import-isolation) are
**pre-existing** — verified identical against the pre-change tree.

## Change classification

Steps 2–4 are **MINOR** — *"additive public APIs, new capabilities, new
conformance assertions"*. They added a subpackage and tests, changed no existing
API or semantics, and moved no frozen hash.

Step 5 is **MAJOR**, not PATCH. `PATCH` is defined as *"no API or semantic
change"*; `MAJOR` explicitly covers *"authority/lifecycle/dependency-direction/
fail-safe changes"*. A live input that previously yielded `AUTHORIZED` and now
yields a non-authorizing outcome is a fail-safe change by the manifest's own
words.

`[V]` **The platform's own classifier disagrees, and it is wrong to rely on.**
`platform_freeze.compat.classify` reports this change as `MINOR`/`ADDITIVE`:
all eight API diffs are additions, with no removal or signature break. The
classifier compares API *shape*, and a semantic change that inverts an outcome
leaves shape untouched. Anything relying on that classifier to gate a release
would have waved this through as MINOR.

## Open items

1. `[R]` `resource` and `parameters` postures are inferred, not ratified.
2. `[R]` D5 — whether the two least-permissive-wins implementations converge.
3. `[R]` **Version bump not taken.** Implementation and distribution versions
   remain `0.1.0` despite a MAJOR change. Bumping them reaches
   `platform_freeze.version.COMPONENT_VERSIONS`, the facade packaging test and
   `ai-hiring` provider-dependency metadata, which is outside what was
   authorized here. `MAPPING_VERSION` (`actiongate-map-1` → `-2`) and the engine
   `policy_version` (`policy-1` → `-2`) *were* bumped, being self-contained.
4. `[R]` **Reason-code rename is a consumer-visible break.** Any consumer
   string-matching `policy_allow` / `policy_denied` / `policy_unknown` /
   `policy_allow_with_constraints` must be updated. No in-repo consumer does —
   verified — but external ones cannot be checked from here.
5. `[G]` CABP signing domain and trust model — unowned, undesigned.
6. `[G]` ActionGate and `action-clearance` share no reason-code vocabulary.
7. `[G]` **The platform's API-diff classifier cannot see fail-safe changes.** It
   classified this MAJOR change as MINOR/ADDITIVE. Any release process gating on
   it inherits that blind spot.

## Resolved by step 5

- `[G]` The behavioural-equivalence probe now varies all eleven governance
  dimensions in permissive/offending pairs, asserts every pair differs, and
  asserts request mapping is total against the neutral dataclass's own fields.
  The old probe varied `action_type` alone and never set
  `authorization_expired`, so it could not have detected the defect it was
  supposed to guard.
