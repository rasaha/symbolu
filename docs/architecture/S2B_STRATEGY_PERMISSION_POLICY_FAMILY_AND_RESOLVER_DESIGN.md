# S2-B execution blocker — strategy-permission policy family and concrete `StrategyPolicyResolver`

**Status: design proposal — documentation only. Nothing here is ratified, and no
implementation is authorized by it.** The analysis was performed read-only: it modified no
production source, test, package metadata, `public_api.json`, `version.py`, CI workflow or
platform-freeze artifact, and this document is the only file its change set adds. The eight
owner decisions in §11 are **open**; §12 is the ballot that would settle them.

**Baseline:** default branch `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`, head
`070a91281f1f3a8ad9185ebae1f422430727d974` (merge of PR #1503, the S2-B first production
implementation at `0.3.0`). Every `[V]` claim below is verifiable against that head.

**Load-bearing question, answered first.** The blocker closes with **two new integration
distributions and no change to either existing package**: a strategy-permission **policy
family + `PolicyFamilyAdapter`** package, and a **concrete resolver** package that calls
`ugence_policy_authority.api.resolve_policy` and returns Agentic Proposer's ratified
`StrategyPolicyResponse`. The adapter **may not** live inside Policy Authority and **may
not** be reached from Agentic Proposer; both bars are enforced by tests today. Agentic
Proposer stays at `0.3.0`/51 names and Policy Authority at `0.1.0`/66 names.

**Evidence labels.** `[V]` verified against this repository at the cited `file:line`;
`[I]` architectural inference; `[R]` owner ruling required; `[G]` unresolved gap.

---

## 0. Baseline verification

| Check | Result |
|---|---|
| Default-branch head | `[V]` `070a91281f1f3a8ad9185ebae1f422430727d974` — exact match |
| PR #1503 | `[V]` `state=closed`, `merged=true`, merged by `rasaha` 2026-08-29T10:00:34Z |
| Audited head ancestry | `[V]` `7ced63e728ef799fc57803be9c93fe27b9a7eeae` is `070a9128^2`; `git merge-base --is-ancestor` returns true |
| Agentic Proposer version | `[V]` `0.3.0` (`src/ugence_agentic_proposer/version.py`) |
| Public surface | `[V]` `__all__` = 51 names; `public_api.json.symbols` = 51; sorted sets equal |
| S2-B vocabulary | `[V]` `ReasoningStrategy` = `SINGLE_CANDIDATE_UNREVISED`, `MULTI_CANDIDATE_UNREVISED`, `REVISED_ADVISORY` (`vocabulary.py`) |
| Resolver protocol | `[V]` `StrategyPolicyResolver` / `StrategyPolicyRequest` / `StrategyPolicyResponse` (`contracts.py:846-927`) |
| Six-check replay | `[V]` `verify_strategy_permission` (`verification.py:530-636`), six checks in ratified order |
| No existing family or resolver under another name | `[V]` repository-wide grep for `strategy_permission` / `strategy-permission` / `StrategyPolicyResolver` outside `packages/capabilities/agentic-proposer` returns nothing; no package under `packages/integration` matches `strat` |
| Policy Authority | `[V]` `0.1.0`, 66 curated names, one registered family adapter (`adapters/uvi.py`) |

**No baseline mismatch. Proceeding.**

---

## 1. Policy family contract

### 1.1 Placement of the family artifact

`[V]` The repository already has the exact precedent: `packages/integration/cloud-scaling-capacity-bounds-policy/`
is "the authority's **second** policy family, and the first registered from *outside* the
authority's own distribution", stdlib-only frozen dataclasses, one direct dependency
(`ugence-policy-authority`), with `tests/test_authority_registration.py` driving genuine
issuance, real Ed25519 signing, the real registry and real resolution across a package
boundary. This design mirrors that package's discipline exactly.

### 1.2 Identifiers (`[R]` — every one is bound into a digest or a coordinate)

| Constant | Proposed value |
|---|---|
| `STRATEGY_PERMISSION_ADAPTER_ID` | `ugence.agentic-proposer.strategy-permission/v1` |
| `STRATEGY_PERMISSION_POLICY_FAMILY` | `agentic_proposer.strategy_permission` |
| `STRATEGY_PERMISSION_POLICY_TYPE` | `StrategyPermissionPolicy` |
| Scopes | `GLOBAL` (empty tenant component), `TENANT` (non-empty) |
| Lifecycle labels | `DRAFT`, `APPROVED_ACTIVE`, `SUPERSEDED`, `WITHDRAWN`; active iff `APPROVED_ACTIVE` |

`[V]` The family component must not collide with any UVI family value
(`PolicyFamily` values) or with `cloud_scaling.capacity_bounds`; the proposed value collides
with neither.

### 1.3 Artifact shape

Two frozen dataclasses, stdlib-only, validated at construction (capacity-bounds pattern).

**`StrategyPermissionPolicyMetadata`**

| Field | Type | Required | Rule |
|---|---|---|---|
| `policy_id` | `str` | yes | non-empty; **must also satisfy Agentic Proposer's C5b `Token` grammar** `^[A-Za-z0-9][A-Za-z0-9._:-]*$`, max 200 — `[I]` otherwise a lawfully issued policy cannot be stamped onto `ProposerAdvisory.strategy_policy_id` (`contracts.py:105-108`, `:997`) and the integration fails at construction rather than at issuance |
| `version` | `str` | yes | same grammar; **a string, never numeric** (C3) |
| `content_digest` | `str` | yes | lowercase 64-char sha-256 hex; declared, then **removed by path** from the canonical projection |
| `scope` | `str` | yes | `GLOBAL` or `TENANT` |
| `tenant_id` | `str` | yes | empty iff `GLOBAL`; non-empty iff `TENANT` |
| `policy_family` | `str` | fixed | the family constant; re-checked by the adapter |
| `lifecycle_state` | `str` | yes | one of the four labels |
| `supersedes_ref` | `str` | no, default `""` | `[V]` a non-empty value is refused at issuance by the authority itself (P-6; `issuance.py`, `SUPERSESSION_REFERENCE_UNSUPPORTED`); the family adds no interpretation |
| `effective_from` / `effective_to` | `datetime \| None` | no | tz-aware or refused `[V]` (`require_tzaware`); half-open `[from, to)` applied by `resolve_policy` |

**`StrategyPermissionPolicy`** (the body)

| Field | Type | Required | Rule |
|---|---|---|---|
| `metadata` | `StrategyPermissionPolicyMetadata` | yes | — |
| `strategy_policy_ref` | `str` | yes | `[R]` **the reference this policy asserts it is named by**; C5a `Identifier` grammar `^[A-Za-z0-9][A-Za-z0-9._:/-]*$`, max 200. See §5.2 — this is what makes the ref→policy binding *signed* rather than deployment configuration |
| `permitted_strategies` | `tuple[str, ...]` | yes | **non-empty**; every element an exact member of the three ratified spellings; **no duplicates**; stored in **ascending codepoint order, rejected if unsorted** (never reordered — capacity-bounds `CapacityBoundsOrderingError` precedent) |
| `vocabulary_version` | `str` | yes | `[R]` names the vocabulary the members are drawn from, e.g. `ugence.agentic-proposer.reasoning-strategy/v1`. `[V]` `S2B-D7=A` requires the **strategy vocabulary or profile version** to remain a distinct identity from the issuing policy |

**Permitted strategy representation.** `[R]` The stored element is the **enum's string value**,
validated against `ReasoningStrategy` at construction (see §3 for the import ruling).
`[V]` `to_canonical_obj` maps `Enum` to `.value` (`core/canonical.py:136-137`), so storing
members or their values produces an identical digest; strings are recommended because the
artifact must stay a plain stdlib dataclass for the adapter's canonicalization.

**Explicitly absent, and none may be added without a new ruling** `[R]`: required strategies;
composition, ordering or subordinate strategies (`S2B-D3=A`); compute budgets, quotas or
token counts; model capability tiers (`S2B-D2=A` bars them); provider names; terminal
outcomes or dispositions; any execution or runtime-authorization field; any role identity
(permission is role-level and the role *references* the policy — a role list inside the
policy would invert the ratified direction and require the proposer to send a role identity
it does not send).

### 1.4 Canonical projection

`[I]` Identical discipline to both shipped adapters: project the whole artifact through
`to_canonical_obj`, then remove **exactly one declared path**, `metadata.content_digest` —
removed, never blanked; by path, not by name; no sentinel; no fixed point. The artifact has
no signature field, so the projection is structurally incapable of depending on a signature.

### 1.5 Values participating in the signed identity

`[V]` From `records.py` / `payload.py`, the issuance signature covers:
`record_id`, the full `PolicyCoordinate` (`policy_family`, `policy_id`, `version`,
`content_digest`, `scope`, `tenant_id`), `adapter_id`, `policy_body_digest`,
`approving_authority_id`, `approval_ref`, `approval_digest`, `issuing_authority_id`,
`key_id`, `signature_alg`, `issued_at` — framed with `AUTHORITY_PROTOCOL_ID` and
`CANONICALIZATION_VERSION`. `policy_body_digest` is `framed_body_digest(adapter_id,
policy_type, projection)`.

`[I]` **Conditional on the §1.4 projection**, therefore, every field in §1.3 except
`metadata.content_digest` is transitively signed — including `permitted_strategies`,
`strategy_policy_ref`, `vocabulary_version`, the lifecycle label and the effective period.
That is an inference about a projection this document proposes, not a repository fact: the
authority signs whatever the adapter projects, so the coverage claim holds exactly as far as
§1.4 is implemented as written. A projection that dropped or flattened a field would narrow
what is signed without any authority-side check noticing, which is why §9.2 recomputes the
framed digest independently rather than trusting the adapter's own output.

### 1.6 Coordinate and version handling

`[V]` `PolicyCoordinate` is exact and hashable; `identity_slot` excludes the digest, so two
artifacts sharing family/id/version/scope/tenant but differing in content are a registry
**conflict**, not two versions. `[V]` There is no `latest()`, `current()` or `find_by_id()`
on the trusted path — a floating reference is unrepresentable. A new permitted set is a new
`version` and therefore a new coordinate.

---

## 2. Authority separation

`[V]` `P-4` keeps five roles distinct, and this design adds no sixth and merges no two.

| Role | Owner here |
|---|---|
| Author | humans / an external authoring process producing a `StrategyPermissionPolicy` |
| Approver | external governance process, binding the **exact content digest** |
| Approval verifier | the composition root's injected `ApprovalVerifier` `[V]` — production ships only `DenyAllApprovalVerifier`; permissive verifiers exist only under `tests/` |
| Issuer / signer | **Policy Authority** (`issue_policy`, `Ed25519PolicySigner`) |
| Registry / resolver | **Policy Authority** (`InMemoryPolicyRegistry`, `resolve_policy`) |
| Policy-version revoker | **Policy Authority** (`revoke_policy`, signed and entitlement-checked) |
| Runtime authorizer | **nobody in this design** — remains Risk Authority / ActionGate |

**What Policy Authority proves** on a `RESOLVED` answer `[V]` (`core/resolution.py:33-46`):
under the trust roots this call was configured with, and at this explicit `as_of`, the
returned artifact was signed by an authorized, entitled, un-revoked key of the named issuing
authority over exactly this canonical body; the declared digest equals the recomputed body
digest and equals the digest bound into the signature; external approval evidence verified
(and, when an approval verifier is supplied at resolution, still verifies now); no
unstructured supersession is declared; the lifecycle is active; `as_of` lies in the half-open
effective interval; and no verified revocation applies.

**What it never decides** `[V]`: whether the permitted set is wise, correct, lawful or
commercially sound; whether the role should be governed by this policy; whether any advisory
is good; what a permission failure should cause operationally; and **it authorizes no runtime
action** — `§19.8` bars it from ever sitting on the hot path as an authorizer. `[V]` Raw
registry retrieval is not resolution, and a hand-assembled `IssuedPolicyRecord` fails exactly
like a tampered one.

---

## 3. Adapter placement and the `ReasoningStrategy` import

### 3.1 The adapter may not live inside Policy Authority — checked, not assumed

`[V]` `packages/policy-authority/tests/packaging/test_dependency_boundary.py` enforces three
independent bars:

1. `test_only_stdlib_self_and_the_uvi_contracts_leaf` — every module under
   `ugence_policy_authority` may import only stdlib, `__future__`, itself and
   `ugence_uvi_policy_contracts`;
2. `test_the_declared_distribution_dependencies_match_the_imports` — declared dependencies
   must equal exactly `{"ugence-uvi-policy-contracts"}`;
3. `test_no_prohibited_imports` — `PROHIBITED` includes `pydantic` outright, and
   `ugence-agentic-proposer` declares `pydantic>=2` as a runtime dependency.

`[I]` A strategy-permission adapter inside the authority that imported `ReasoningStrategy`
**fails bars 1 and 2**. `[V]` It does **not** fail bar 3 on that import alone: the scan
collects **import roots** from each module's AST, so it would see `ugence_agentic_proposer`
and never `pydantic`, which arrives transitively at runtime rather than as an import
statement in authority source. Bar 3 bites only on a **direct** `pydantic` import. Two
independent bars are decisive, and the conclusion is unchanged; the third is a weaker
backstop than the first draft of this section implied.

The adapter therefore lives **outside** the authority distribution —
which is the ratified additive path anyway (`P-9`: a second family is added by registering a
second adapter, with no core change), and is already exercised across a real package boundary
by the capacity-bounds package `[V]`.

### 3.2 May the outside adapter import `ReasoningStrategy` from Agentic Proposer? — **Yes**

Every rule that could bar it was checked:

* `[V]` Agentic Proposer's reverse-dependency guard
  (`tests/test_role_projection_bounds.py::test_no_shared_contract_package_depends_on_this_capability`)
  applies only to distributions whose **name contains `contract`**
  (`_shared_contract_packages`). A distribution named `ugence-agentic-proposer-strategy-permission-policy`
  is outside that set.
* `[V]` Policy Authority's `test_no_package_anywhere_imports_an_authority_internal` allows
  consumers to name `ugence_policy_authority` and `ugence_policy_authority.api` and nothing
  else — the adapter imports only `…api`, as the capacity-bounds adapter does.
* `[V]` **A real constraint that does apply:**
  `test_the_projection_is_local_to_this_package_wherever_it_is_defined` scans **every** `.py`
  under `packages/` outside Agentic Proposer for the substrings `CognitiveRole`,
  `COGNITIVE_ROLE`, `cognitive_role` — including docstrings. Neither new package may name the
  role contract anywhere in its source, prose included. `[I]` This costs nothing: the resolver
  receives a `StrategyPolicyRequest`, never a role.
* `[V]` Agentic Proposer's own `BARRED_IMPORTS`
  (`tests/test_s2b_strategy_permission.py:805`) bars `ugence_policy_authority` **from
  Agentic Proposer's source** — a one-way bar, unaffected by a third package importing both.

### 3.3 Single source of truth for the three ratified spellings — alternatives

| Option | Single source of truth | Assessment |
|---|---|---|
| **A. Import `ReasoningStrategy` from `ugence_agentic_proposer` into the family package (recommended)** | the ratified enum itself | No fork is possible: the family validates every stored token with `ReasoningStrategy(value)` and a test asserts its accepted set equals `set(ReasoningStrategy)`. Cost: the family package depends on Agentic Proposer (and transitively pydantic). No cycle — Agentic Proposer imports nothing new. |
| B. Re-declare three constants in the family package, pinned by a test that imports both | the enum, guarded by a test | Avoids a runtime dependency, but the guard has to import Agentic Proposer anyway, so the dependency reappears in `test`. A fork is possible for exactly as long as a test is skipped. |
| C. Move the vocabulary to a new shared contract distribution both depend on | the new package | `[V]` Rejected on the repository: `S2B-S1-Q6=A` ratified 46 → 51 with **no removals and no renames**; moving `ReasoningStrategy` out of Agentic Proposer removes a ratified public name, and duplicating it re-creates the fork. |
| D. Store opaque tokens, validated nowhere | none | Rejected: a policy could permit a token no advisory can ever declare, and the divergence would be silent — the exact failure the ruling's "closed vocabulary, no escape member" was written against. |

**Recommendation: A.** `[R]`

---

## 4. Concrete resolver location

**Bars, checked:** `[V]` it cannot live in Agentic Proposer (`ugence_policy_authority` is in
that package's `BARRED_IMPORTS`, and `S2B-D1=A` excludes Agentic Proposer as an issuer); `[V]`
it cannot live in Policy Authority (§3.1's three dependency bars, plus `§19.8` — the authority
must not become a runtime component).

| Candidate | Verdict |
|---|---|
| A Policy Authority integration adapter **inside** `packages/policy-authority/` | **Rejected `[V]`** — fails the declared-dependency equality test and the stdlib-only import test; also makes the authority a runtime resolver. |
| An Agent Runtime integration | **Rejected for now `[I]`** — architecturally possible (the bar is one-way), but it places a proposer-specific resolver inside a capability that owns different authority and is untouched by S2-B. It also widens the change set well past the blocker. |
| An existing integration package | **Rejected `[I]`** — each of the eleven is scoped to a named pair of capabilities it integrates (cloud scaling, risk authority, and context minimization with agent runtime). None integrates the Agentic Proposer with anything, so none has a plausible claim to proposer strategy permission, and reusing one would mis-own it. |
| **A new narrowly scoped integration package (recommended)** | **Accepted `[I]`** — the capacity-bounds precedent, one level up: the family package is the artifact side, the resolver package is the runtime side. |

### Recommended ownership and dependency direction `[R]`

```
ugence-policy-authority (0.1.0, unchanged)        ugence-agentic-proposer (0.3.0, unchanged)
        ▲  api only                                        ▲  ReasoningStrategy only
        │                                                  │
  ugence-agentic-proposer-strategy-permission-policy  ─────┘      (family artifact + adapter)
        ▲
        │
  ugence-agentic-proposer-strategy-permission-runtime  ───▶ ugence-agentic-proposer
                                                             (StrategyPolicyRequest/Response)
                                                       ───▶ ugence-policy-authority.api
                                                             (resolve_policy)
```

* `packages/integration/agentic-proposer-strategy-permission-policy/` — distribution
  `ugence-agentic-proposer-strategy-permission-policy`, namespace
  `ugence_agentic_proposer_strategy_permission_policy`. Artifact, adapter, identifiers,
  errors. **No resolution, no signing, no clock, no network.**
* `packages/integration/agentic-proposer-strategy-permission-runtime/` — distribution
  `ugence-agentic-proposer-strategy-permission-runtime`, namespace
  `…_strategy_permission_runtime`. One concrete
  `PolicyAuthorityStrategyPolicyResolver`, its failure taxonomy, and the end-to-end proof.
  `[I]` Naming follows `context-minimization-token-accounting-runtime` `[V]`.

`[R]` **One package instead of two** is a defensible alternative (identical dependency set,
one fewer distribution) and is on the ballot. The split is recommended because registering the
family with the authority should not drag a runtime resolver into the importing process.

**Neither existing package changes.** Agentic Proposer never imports Policy Authority;
Policy Authority never imports Agentic Proposer; the new packages import both.

---

## 5. Resolution semantics

### 5.1 `strategy_policy_ref` → an exact coordinate

`[V]` `StrategyPolicyRequest.strategy_policy_ref` is one opaque C5a `Identifier`
(`contracts.py:858-859`); `PolicyCoordinate` has six components. Two mappings are possible:

* **(i) a parseable structured reference** — the role's own string encodes family, id,
  version, digest, scope and tenant;
* **(ii) an injected, composition-root-owned, immutable mapping** keyed by
  `(tenant_id, strategy_policy_ref)` → `PolicyCoordinate`.

**Recommended: (ii)** `[R]`. Under (i) a caller-supplied field would name any coordinate it
likes, including its content digest — `[V]` "a caller-supplied value is not authoritative
merely because it is structured or digest-bound" (`S2B-D7=A`). Under (ii) the reachable set
is deployment trust configuration; the role's reference **selects among pre-registered
coordinates and can mint none**. The mapping is defensively copied and exposed read-only at
construction, on `PolicyKeyRing`'s ratified pattern `[V]` (§15.5). An unknown key fails
closed: no fallback, no prefix match, no "latest".

`[V]` This preserves the ratified bar on floating references — the mapping stores complete
coordinates including the content digest, so a new permitted set requires a new configured
entry, not a silent re-point.

### 5.2 The binding is also made *signed*, not merely configured

`[G]` Nothing in a signed policy names the reference a role uses to reach it, so under (ii)
alone the ref→policy binding is unsigned deployment state. `[R]` The recommended fix is inside
this family and costs one field: `StrategyPermissionPolicy.strategy_policy_ref` (§1.3), and a
resolver check that `resolution.policy.strategy_policy_ref == request.strategy_policy_ref`
**exactly**. The caller's value never becomes authoritative — it must *match* a value the
issuing authority signed. Configuration then only locates the policy; the authority states
which reference it answers to.

### 5.3 `tenant_id`, `case_ref`, `as_of`

* **`tenant_id`** — used twice. First, as part of the mapping key, so one tenant's reference
  can never resolve another tenant's coordinate. Second, it supplies the value passed as
  `resolve_policy(expected_reference_tenant_id=…)`, which must be **derived from the request,
  never read off the coordinate**: `[V]` the authority's check is
  `coordinate.tenant_id != expected_reference_tenant_id` (`core/resolution.py:149`), so
  passing `coordinate.tenant_id` makes that comparison **vacuous for every coordinate** —
  not merely for a `GLOBAL` one, as an earlier draft of this section said. The resolver
  therefore passes `request.tenant_id` when the configured coordinate's scope is `TENANT`,
  and `GLOBAL_TENANT` (the canonical empty component) when it is `GLOBAL` — in both branches
  a value the coordinate did not supply, so the authority's comparison independently
  re-establishes the binding. The resolver additionally pre-checks scope/tenant agreement
  itself and fails closed on disagreement, so the two checks are redundant rather than
  co-dependent. `[V]` `expected_reference_tenant_id`
  checks the *reference's declared tenant identity*, never caller entitlement — this resolver
  performs no caller authorization and claims none.
* **`case_ref`** — `[R]` **correlation and audit context only. It never affects policy
  selection.** It is not in the mapping key, not in any coordinate, and `resolve_policy`
  accepts no such parameter `[V]`. Letting it select would be per-invocation authorization,
  which `S2B-D4=A` did not ratify (permission is role-level).
* **`as_of`** — caller-supplied, passed through verbatim to `resolve_policy(as_of=…)`. `[V]`
  Both sides already require a timezone-aware instant, and no module in either package reads
  a wall clock. The policy consulted is the one in force at the instant the advisory asserts.

### 5.4 Fail-closed matrix

The resolver returns a `StrategyPolicyResponse` **only** when `resolve_policy` returns
`status == RESOLVED`. Every other outcome raises; nothing degraded, partial or defaulted is
returned.

| Condition | Mechanism | Resolver behaviour |
|---|---|---|
| Unknown `(tenant, ref)` | mapping lookup | raise `UnknownStrategyPolicyReferenceError` |
| Scope/tenant disagreement | resolver pre-check | raise `StrategyPolicyTenantScopeError` |
| Signature / key unknown / revoked / not entitled | `SIGNATURE_INVALID`, `KEY_UNKNOWN`, `KEY_REVOKED`, `KEY_NOT_ENTITLED` `[V]` | raise `StrategyPolicyUnresolvedError(reason=…)` |
| Approval withdrawn after issuance | `APPROVAL_PROOF_INVALID` `[V]`, reached only when an approval verifier is supplied at resolution | raise, same class |
| Digest tampering | `CONTENT_DIGEST_MISMATCH` / `BODY_DIGEST_MISMATCH` | raise, same class |
| Revoked version | `REVOKED`; `historical_resolution` left at the default `DENY_ALWAYS` `[V]` — no historical answers are requested or accepted | raise, same class |
| Unverifiable revocation record | `REVOCATION_INTEGRITY_INVALID` `[V]` — neither denies as valid revocation nor is ignored | raise, same class |
| Outside the effective window | `NOT_YET_EFFECTIVE` / `EXPIRED` | raise, same class |
| Lifecycle not `APPROVED_ACTIVE` | `LIFECYCLE_NOT_ACTIVE` | raise, same class |
| Wrong coordinate / missing record | `NOT_FOUND`, `REFERENCE_MISMATCH`, `ARTIFACT_REFERENCE_MISMATCH`, `NO_ADAPTER_REGISTERED` | raise, same class |
| Resolved artifact is not exactly `StrategyPermissionPolicy` | resolver post-check (exact runtime type) | raise `StrategyPolicyArtifactError` |
| Signed `strategy_policy_ref` ≠ request ref (§5.2) | resolver post-check | raise `StrategyPolicyReferenceBindingError` |
| A stored token is not a `ReasoningStrategy` member | resolver post-check | raise `StrategyPolicyVocabularyError` |

`[V]` **Three `PolicyResolutionReason` members are deliberately not given their own rows**:
`TENANT_SCOPE_MISMATCH` (the resolver's own pre-check refuses first, so the authority's
reason is reachable only if the pre-check is wrong), `ARTIFACT_NOT_CANONICALIZABLE` and
`SUPERSESSION_REFERENCE_UNSUPPORTED`. None is unhandled: the **only-`RESOLVED`** rule above
covers the whole enum by construction — anything that is not `RESOLVED` raises — and the
table enumerates the reasons worth naming separately, not the reasons that are handled.

`[R]` **Approval re-verification at resolution is OD-E and remains open.** Under the
recommended **OD-E=A** the resolver always supplies an approval verifier, because without one
an approval withdrawn after issuance still resolves: `[V]` the issuance signature proves only
that the approval was bound **at issuance time**. Under **OD-E=B** that is accepted, and the
`APPROVAL_PROOF_INVALID` row above becomes unreachable.

---

## 6. Response mapping

| `StrategyPolicyResponse` field | Source | Evidence supporting it |
|---|---|---|
| `strategy_policy_id` | `resolution.policy.metadata.policy_id` | `[V]` equals `coordinate.policy_id` — `resolve_policy` refuses with `ARTIFACT_REFERENCE_MISMATCH` unless the artifact re-derives the stored coordinate, and the coordinate is inside the issuance signature |
| `strategy_policy_version` | `resolution.policy.metadata.version`, **a `str`** | same; `[V]` C3 bars a numeric type on the advisory this value is stamped onto |
| `permitted_strategies` | `tuple(ReasoningStrategy(v) for v in policy.permitted_strategies)`, artifact order preserved | `[V]` transitively signed via `policy_body_digest`; `[V]` order is not significant to Agentic Proposer — membership is the only operation performed |
| `strategy_policy_ref` | `request.strategy_policy_ref`, verbatim | the resolver's own copy of the request field; also, under §5.2, equal to a value the issuing authority signed |
| `verified` | **absent** | `[V]` ratified absent — a boolean a resolver sets is the resolver asserting its own trustworthiness. The evidence is structural instead: a response exists *only* on `RESOLVED` |

**What digest inclusion still does not prove** `[R]`: that the policy is wise, correct or
lawful; that the issuing authority is the one a reader expects (only that it is the one the
configured trust anchors name); that the producer executed any procedure; that private
reasoning matched the declaration; and — on the Agentic Proposer side — that the resolver is
honest. `[V]` The echo is a request/response **correlation** check: a resolver that wishes to
mislead echoes back what it was handed while resolving something else, and nothing in that
boundary can detect it. `[V]` Digest membership proves integrity after construction, never
provenance.

---

## 7. Failure taxonomy

### 7.1 Resolver-side (new, owned by the runtime package)

One base class `StrategyPermissionResolverError`, with the subclasses named in §5.4 and a
stable `reason` attribute carrying the Policy Authority `PolicyResolutionReason` value
verbatim where one exists.

`[R]` **None of them emits a denial, `ABSTAIN`, a reserved authority term, a
`TerminalOutcome`, a `CandidateDisposition`, or any operational disposition.** They name
resolution and integrity facts only, and a guard scans every class name and message template
against `RESERVED_AUTHORITY_VOCABULARY`, `TerminalOutcome` and `CandidateDisposition` — the
same scan the S2-B implementation already applies to its own refusal messages `[V]`.
Mapping a structural permission failure to an operational outcome remains **unruled and
unowned** `[V]` (`S2B-D5=A`), and nothing here maps one.

**A collision the scan makes real, disclosed rather than discovered later.** `[V]`
`RESERVED_AUTHORITY_VOCABULARY` contains **`EXPIRED`**, **`UNSUPPORTED`** and **`SUPPORTED`**
(`vocabulary.py:123-134`), and the scan **uppercases the message and tests substring
containment** (`tests/test_s2b_strategy_permission.py:491-499`). Two Policy Authority
resolution reasons therefore collide with it directly: `EXPIRED` is a reserved term verbatim,
and `SUPERSESSION_REFERENCE_UNSUPPORTED` contains both `UNSUPPORTED` and `SUPPORTED`.

`[R]` **The rule this forces:** a `PolicyResolutionReason` token may appear **only in the
exception's `reason` attribute**, never in a message template, a docstring rendered into a
message, or an f-string interpolation of the reason into prose. A caller that wants the
authority's reason reads the attribute. `[I]` This costs nothing operationally — the reason
is machine-readable where a consumer wants it — and it keeps the resolver's messages clear of
the reserved vocabulary without renaming anything the authority owns. `[R]` The guard in
§9.11 must scan message templates with the **same uppercased-substring rule**, or it will not
catch the collision it exists to prevent.

### 7.2 Proposer boundary (existing, unchanged)

`[V]` A raising resolver, a `None` response, an uncorrelated echo, an empty permitted set and
a non-member declaration are all re-raised as `CrossContractViolationError`; replay returns
`False`. H2 stays at five classes.

### 7.3 The known non-blocking `0.3.0` behaviour

`[V]` **Reproduced in this session**, not merely read: in `_resolve_strategy_policy`
(`identity.py`), the echo access sits outside the `try`, so a resolver returning a
structurally alien object raises `AttributeError: 'Alien' object has no attribute
'strategy_policy_ref'` rather than an H2 class. `[V]` PR #1503 discloses this and deliberately
leaves it.

**Recommended: option A — leave it as garbage-input behaviour, in this change set.** `[R]`

* `[I]` The recommended concrete resolver returns a real `StrategyPolicyResponse` or raises,
  so the path is unreachable from this integration; it is not the execution blocker and
  closing it closes nothing.
* `[V]` Every *ratified* failure condition is already covered by an H2 class; this is the
  garbage-input case and behaves as garbage input does elsewhere in the package.
* `[V]` Touching Agentic Proposer here is precisely the "while we're in there" edit the §8
  gate discipline prohibits.

Option **B** (widen the guard so an alien response becomes `CrossContractViolationError`) is a
**behaviour change to a shipped `0.3.0` public builder's failure class** and is therefore an
explicit owner decision with its own change set — `[R]` never an incidental detail of resolver
implementation. It would be a patch release (`0.3.1`): public surface unchanged, failure class
changed. Option **C** is unavailable: `[V]` `S2B-S1-Q8=A` closed H2 at five classes and
ratified no new exception type, so there is no other already-authorized mechanism to reach for.

---

## 8. Version and public-surface impact

| Package | Version | Public surface | Nature |
|---|---|---|---|
| `ugence-agentic-proposer` | **`0.3.0`, unchanged** | **51 names, unchanged** | `[I]` No source change is required by this design. `[R]` Only owner-decision OD-G option B would move it, to `0.3.1`, still 51 names |
| `ugence-policy-authority` | **`0.1.0`, unchanged** | **66 names, unchanged** | `[V]` `P-9` makes a second family additive by adapter registration with **no core change**, already proven across a package boundary |
| `ugence-agentic-proposer-strategy-permission-policy` | **`0.1.0`, new** | new curated surface: artifact, metadata, adapter, `…_coordinate`, identifiers, errors | additive; nothing to be compatible with |
| `ugence-agentic-proposer-strategy-permission-runtime` | **`0.1.0`, new** | `PolicyAuthorityStrategyPolicyResolver`, its error family, a composition helper | additive |

**Requiring a compatibility decision:** nothing, under the recommendation. **Additive
adapter/resolver work only.** `[R]` The single item that would cross into compatibility is
OD-G option B.

### 8.1 Prose in Agentic Proposer that this work makes stale `[G]`

Two `[G]` notes inside the proposer assert, as present-tense fact, that no strategy-permission
policy family is registered:

* `[V]` `src/ugence_agentic_proposer/version.py:12-13` — "Execution remains blocked, and this
  release does not unblock it: no strategy-permission policy family is registered with Policy
  Authority";
* `[V]` `src/ugence_agentic_proposer/contracts.py:839-842` — "Disclosed, and not this
  package's to fix: no strategy-permission policy family is registered with Policy Authority",
  so "nothing here can EXECUTE end to end today".

Both become **false the moment the family package exists**, and `[V]` **no test pins either
string**, so nothing fails and nothing announces the drift. They cannot be reconciled without
editing Agentic Proposer source, which §8 otherwise says need not change — a real tension, not
a wording problem, and it is disclosed here rather than resolved by quietly widening the
change set.

`[I]` The narrowest honest reading is that both statements remain **true of the `0.3.0`
release they describe**: `version.py`'s note is scoped to that release by its own words, and
the `CHANGELOG` entry is historical record that should not be rewritten. `contracts.py`'s
comment is the weaker case — it is written in the present tense about the package, not about a
release. `[R]` Whether to leave both (accepting stale prose in a shipped module), or to correct
`contracts.py` in a documentation-only patch release, is an owner call that this document does
**not** put on the ballot, because it arises only *after* the family lands and its answer
changes nothing about the design. It is recorded here so it is not discovered as a surprise.

---

## 9. End-to-end proof

Deterministic, clock-free, network-free tests in the runtime package (with the family's own
tests in the family package), on the pattern of
`cloud-scaling-capacity-bounds-policy/tests/test_authority_registration.py`, which drives
genuine issuance, real Ed25519 signing, the real registry and real resolution `[V]`.

1. **External authorship and approval.** Build the artifact; approve its exact content digest
   through a `tests/`-only verifier; assert `DenyAllApprovalVerifier` refuses issuance, and
   that no production module in either new package defines a permissive verifier.
2. **Issuance and signing.** `issue_policy` with the family adapter registered on an
   `AdapterRegistry`; assert the record's signature verifies and that
   `framed_body_digest(adapter_id, policy_type, projection)` recomputed independently equals
   `record.policy_body_digest`.
3. **Exact resolution.** The concrete resolver returns the four ratified fields; assert the
   version is a `str`, the id equals the coordinate's, and the mapping is exact-only (a
   near-miss reference raises).
4. **Valid signature required.** Store a mutated artifact under the same coordinate → resolution
   reason is a digest mismatch → the resolver raises and returns nothing.
5. **Revocation and expiration.** `revoke_policy` (signed, entitled) → `REVOKED` → raise; an
   `as_of` at or after `effective_to` → `EXPIRED` → raise; an `as_of` before
   `effective_from` → `NOT_YET_EFFECTIVE` → raise. Also: an unverifiable revocation record →
   `REVOCATION_INTEGRITY_INVALID` → raise (it neither denies as valid revocation nor is ignored).
6. **Echo correlation.** The response's ref is the request's exact value; a deliberately
   mis-echoing stub makes `build_proposer_advisory` refuse.
7. **Permitted-set mapping.** Artifact tokens map to `ReasoningStrategy` members with order
   preserved; a hand-forged artifact carrying an alien token raises the vocabulary error; a
   test asserts the family's accepted token set equals `set(ReasoningStrategy)`.
8. **Construction with the concrete resolver.** `build_proposer_advisory(...,
   strategy_policy_resolver=<concrete>, declared_strategy=…)` produces an advisory whose
   stamped `strategy_policy_id` / `strategy_policy_version` equal the issued policy's, and a
   process record built from it via `build_proposer_process_record(advisory=…)`.
9. **Six-check replay.** `verify_strategy_permission(...) is True` on the real triple; then
   each of the six checks mutated independently and asserted `False` (check 3 remains
   outcome-subsumed by check 4 — a property of the ratified list, disclosed rather than
   papered over `[V]`).
10. **Shape-derived strategy outside the permitted set fails replay.** Issue a policy permitting
    only `SINGLE_CANDIDATE_UNREVISED`; construct a two-candidate advisory declaring
    `SINGLE_CANDIDATE_UNREVISED` — construction **succeeds** (`[V]` check 6 is replay-only, never
    construction) — and assert replay returns `False`. A second variant with both members
    permitted isolates check 6 from check 4.
11. **No compute authorization and no execution authority.** Assert: neither new package exports
    any budget, quota, token-count, tier or provider name; no name gives lifecycle or
    authorization authority; no `TerminalOutcome`, `CandidateDisposition` or reserved authority
    term appears in any exception name or message template — scanned **uppercased, as a
    substring**, matching the existing guard `[V]`, so that the §7.1 collisions (`EXPIRED`;
    `SUPERSESSION_REFERENCE_UNSUPPORTED` containing `UNSUPPORTED` and `SUPPORTED`) are actually
    caught; a companion assertion that every `PolicyResolutionReason` token reaches a caller
    only through the `reason` attribute; no networking, storage, service-discovery or
    plugin-loading import; and no module reads a clock.

**Where enforcement stops, and what remains unprovable** `[G]`: private model reasoning and
chain-of-thought; that the declared procedure was *executed*; observable-stage conformance
beyond what the advisory's own shape shows — no component records reasoning stages, so
`S2B-D8=B`'s later stage still has no producer; resolver honesty beyond echo correlation;
whether the deployment's trust anchors, approval verifier and reference mapping are the right
ones; whether omitted candidates or evidence ever existed; and the operational disposition of a
permission failure, which is deliberately unruled.

---

## 10. Implementation order

| # | Step | Depends on | Atomicity |
|---|---|---|---|
| 1 | **New ADR** recording the family identifiers, the resolution semantics, and the owner rulings from §11's register | ratification | Land first: identifiers are digest identity, and `S2B-D1=A`'s design-ready/implementation-blocked state is closed by a ruling, not by code |
| 2 | **Family package**: identifiers, errors, artifact, adapter, `__init__`, `version.py`, `pyproject.toml`, `CHANGELOG.md`, `README.md`, `public_api.json`, tests (construction, projection, import boundary, authority registration end-to-end) | 1 | **One atomic change set.** Artifact + adapter + identifiers move the digest together; none may land alone |
| 3 | **Runtime package**: resolver, failure taxonomy, composition helper, packaging, tests §9.3–§9.7 and §9.11 | 2 | **One atomic change set** |
| 4 | **End-to-end proof against Agentic Proposer** (§9.8–§9.10) | 3 | Lands with step 3 — it is what proves the blocker closed |
| 5 | **Distribution verification** for both packages (clean-venv build/install/exercise scripts on the existing `verify_*_distribution.py` pattern) plus CI wiring | 2, 3 | May land with its own package |
| 6 | **Documentation reconciliation**: the new ADR supersedes the standing `[G]` "no strategy-permission policy family is registered". `[G]` Note that the two in-proposer statements at `version.py:12-13` and `contracts.py:839-842` are **not** reachable from here — see §8.1; correcting either means editing Agentic Proposer source, and no test pins them, so nothing will flag the drift | 3, 4 | Independent, **after** the code — never ahead of it, on the I8/OD-7 part 8 ordering |
| 7 | *(Only if OD-G = B)* Agentic Proposer `0.3.1`: widen the resolver-boundary guard | separate ruling | **Separate change set, never bundled** |

**Independently implementable:** step 2 (the family can be registered and issued against with
no resolver — it closes half the blocker on its own); step 5 per package; step 6.
**Must land together:** everything inside step 2; everything inside steps 3–4.

---

## 11. Recommended architecture, in brief

Two new integration distributions. The **family package** holds a stdlib-only
`StrategyPermissionPolicy` (metadata envelope, a signed `strategy_policy_ref`, a non-empty
sorted duplicate-free permitted set drawn from the imported `ReasoningStrategy`, and a
`vocabulary_version`) plus its `PolicyFamilyAdapter`, registered on an `AdapterRegistry` by the
composition root. The **runtime package** holds one `PolicyAuthorityStrategyPolicyResolver`
that maps `(tenant_id, strategy_policy_ref)` to an exact `PolicyCoordinate` through an injected
immutable mapping, calls `resolve_policy` with the caller's `as_of`, an approval re-verifier and
`DENY_ALWAYS` historical resolution, checks the signed reference binding and the artifact type,
and returns Agentic Proposer's ratified `StrategyPolicyResponse` — or raises. `case_ref` is
correlation only. Agentic Proposer and Policy Authority are untouched.

### Contract / public-surface delta

| Package | Before | After | Delta |
|---|---|---|---|
| `ugence-agentic-proposer` | `0.3.0`, 51 names | `0.3.0`, 51 names | **none** (`0.3.1`, 51 names, only under OD-G=B) |
| `ugence-policy-authority` | `0.1.0`, 66 names, 1 registered family | `0.1.0`, 66 names, 1 registered family in-distribution | **none** — the second family registers from outside |
| `…-strategy-permission-policy` | — | `0.1.0` | **new**: `StrategyPermissionPolicy`, `StrategyPermissionPolicyMetadata`, `StrategyPermissionPolicyFamilyAdapter`, `strategy_permission_coordinate`, 8 identifier constants, 4 error classes |
| `…-strategy-permission-runtime` | — | `0.1.0` | **new**: `PolicyAuthorityStrategyPolicyResolver`, `StrategyPermissionResolverError` + 6 subclasses, one composition helper |
| `CognitiveRoleContract` / `ProposerAdvisory` / `ProposerProcessRecord` | 11 / 30 / 18 fields | unchanged | **none** |

### Owner-decision register (eight; options within each are mutually exclusive)

| # | Decision | A (recommended) | B |
|---|---|---|---|
| OD-A | Packaging | Two packages: family, runtime | One combined package |
| OD-B | Empty permitted set at issuance | Refused — a policy permitting nothing is expressed by revocation or lifecycle | Permitted, issuable |
| OD-C | Signed `strategy_policy_ref` in the artifact body, checked at resolution | Yes | No — the ref→coordinate binding stays deployment configuration only |
| OD-D | Reference→coordinate mapping | Injected immutable `(tenant, ref)` → coordinate mapping | Parseable structured reference |
| OD-E | Approval re-verification at resolution | Required | Optional (issuance-bound approval stands) |
| OD-F | `vocabulary_version` field in the artifact | Yes | No |
| OD-G | `0.3.0` alien-response `AttributeError` | Leave as garbage-input behaviour | Wrap as `CrossContractViolationError` in a separate Agentic Proposer `0.3.1` change set |
| OD-H | Family package ships `public_api.json` | Yes | No, following the capacity-bounds precedent |

**Coupling between decisions, disclosed.** `[I]` The eight are **independently answerable** —
every one of the 2⁸ combinations yields a buildable design — but they are **not mutually
independent in motivation**, and an earlier draft's "mutually exclusive" overstated it. Two
couplings matter when voting:

* **OD-C is motivated by OD-D=A.** The signed `strategy_policy_ref` exists to turn the
  injected mapping from an authority into a lookup hint. Under **OD-D=B** the reference is
  itself the structured coordinate, so the signed field becomes **largely redundant** — it
  would restate what the caller already supplied, catching only a coordinate that resolves to
  a policy claiming a different reference. `[R]` `OD-C=A` with `OD-D=B` is defensible but buys
  much less; `OD-C=B` with `OD-D=A` leaves the reference-to-policy binding as unsigned
  deployment state, which §5.2 records as the gap it was written to close.
* **OD-E=B makes one §5.4 row unreachable.** Without an approval verifier at resolution, the
  `APPROVAL_PROOF_INVALID` row never fires, and the §9.1 approval test narrows to issuance
  only. Nothing else changes.

`[R]` No other pair interacts. OD-A, OD-B, OD-F, OD-G and OD-H stand alone.

---

## 12. Paste-ready owner-ratification ballot

```
S2-B strategy-permission Policy Authority family and concrete resolver — owner ballot
Baseline: rasaha/symbolu default head 070a91281f1f3a8ad9185ebae1f422430727d974
Answer each with A or B. A = the recommended path.

OD-A  Packaging.
      A = two new integration distributions: ugence-agentic-proposer-strategy-permission-policy
          (artifact + PolicyFamilyAdapter) and ugence-agentic-proposer-strategy-permission-runtime
          (concrete StrategyPolicyResolver).
      B = one combined distribution.

OD-B  Empty permitted set at issuance.
      A = the family refuses to construct or issue a policy whose permitted set is empty.
      B = an empty permitted set is issuable.

OD-C  Signed reference binding.
      A = StrategyPermissionPolicy carries strategy_policy_ref in its digest-bound body, and the
          resolver requires exact equality with the request's reference.
      B = no such field; the reference-to-coordinate binding is deployment configuration only.

OD-D  Reference resolution mechanism.
      A = an injected, immutable, defensively copied mapping keyed by (tenant_id,
          strategy_policy_ref) to a complete PolicyCoordinate; unknown keys fail closed.
      B = a parseable structured reference the resolver decomposes into a coordinate.

OD-E  Approval re-verification.
      A = resolution always supplies an approval verifier, so an approval withdrawn after
          issuance invalidates resolution.
      B = optional; the approval bound into the issuance signature stands.

OD-F  Vocabulary version.
      A = the artifact carries a required vocabulary_version naming the strategy vocabulary.
      B = no such field.

OD-G  The disclosed 0.3.0 alien-response AttributeError in _resolve_strategy_policy.
      A = leave it as garbage-input behaviour; no Agentic Proposer change in this work.
      B = authorize a SEPARATE Agentic Proposer 0.3.1 change set wrapping it as
          CrossContractViolationError (public surface unchanged at 51 names).

OD-H  Family package public_api.json snapshot.
      A = ship one.  B = do not, following the capacity-bounds precedent.

Record as: OD-A=? OD-B=? OD-C=? OD-D=? OD-E=? OD-F=? OD-G=? OD-H=?
```

## 13. Paste-ready independent-review prompt

```
Read-only independent review. Do not modify files, create a branch, commit, push or open a PR.

Repository: rasaha/symbolu
Expected default-branch head: 070a91281f1f3a8ad9185ebae1f422430727d974
Artifact under review: the S2-B strategy-permission policy family and concrete
StrategyPolicyResolver design proposal (sections 1-13), supplied with this prompt.

First verify the baseline independently: the default-branch SHA; PR #1503 merged with its
audited head 7ced63e728ef799fc57803be9c93fe27b9a7eeae an ancestor; Agentic Proposer 0.3.0 with
__all__ and public_api.json both at exactly 51 names; the three ReasoningStrategy members, the
StrategyPolicyResolver protocol and the six-check verify_strategy_permission present; Policy
Authority 0.1.0 with one registered family adapter; and no strategy-permission family or
concrete resolver already present under any other name. Stop on a mismatch.

Then judge, against the repository rather than against the proposal's own prose:

1. Is the claim that a strategy-permission adapter cannot live inside packages/policy-authority
   correct, and is every bar it cites actually enforced by a test that runs?
2. Is the claim that a new integration package may import ReasoningStrategy from
   ugence_agentic_proposer correct, and did the proposal miss any guard that would bar it —
   including the repository-wide role-projection substring scan?
3. Does the proposed family contract stay inside permission only? Flag any field that smuggles in
   required strategies, composition, compute, capability tiers, provider identity, terminal
   outcomes or execution authority.
4. Are the values said to participate in the signed identity actually signed, per payload.py and
   records.py? Is anything claimed as proven that a RESOLVED resolution does not prove?
5. Does the resolution design fail closed on every Policy Authority resolution reason, and does
   any caller-supplied value become authoritative merely because it is structured?
6. Is case_ref correctly confined to correlation, and is the tenant handling non-vacuous for a
   GLOBAL-scope coordinate?
7. Does the failure taxonomy emit any denial, ABSTAIN, reserved authority term or operational
   disposition, directly or by implication?
8. Is the version and public-surface delta right — specifically, is it true that neither existing
   package must change?
9. Would the end-to-end tests actually demonstrate what they claim, in particular the
   shape-derived-strategy replay failure and the absence of any compute or execution authority?
10. Is any [R] item silently settled anywhere in the proposal?

Return one verdict: SOUND, SOUND_WITH_CORRECTIONS, or BLOCKED, with each finding cited to a
file:line in the repository.
```

## 14. Readiness verdict

**READY_FOR_OWNER_RATIFICATION**

Baseline verified in full; no repository contradiction found; eight mutually exclusive owner
decisions are open and none is settled here.
