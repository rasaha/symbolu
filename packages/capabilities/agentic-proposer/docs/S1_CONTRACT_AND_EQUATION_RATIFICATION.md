# S1 — contract and equation ratification

**Status:** `RATIFIED FOR S1 IMPLEMENTATION`
**Ratified against:** PR #1474, merge commit `e28538eb454fce6008e94e0772e0fd09c9c7ea7f`
**Package:** `ugence-agentic-proposer` (`packages/capabilities/agentic-proposer`)
**Authority:** subordinate to D1–D10 in
`docs/architecture/ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md` and to the
D2 enforcement addendum in `S1_ENFORCEMENT.md`.

Evidence labels: `[V]` verified against this repository, `[I]` inferred,
`[R]` requires ratification, `[G]` gap.

---

## Scope

This document ratifies **S1 contracts and deterministic equations only**.

It authorizes **no** invoice-domain check, **no** read-only adapter, **no** LLM or
model-assisted extraction, **no** semantic auditor, **no** HTTP service, **no**
authorization, **no** operational clearance and **no** execution. It creates no
public-API snapshot and changes no version; it specifies what S1 will export when
S1 is separately authorized.

D1–D10 and the D2 enforcement addendum remain authoritative. Where this document
and any earlier external MVP draft disagree, **this committed document governs**;
an uncommitted draft is not an authority over this repository.

---

## Provenance of the field-level content

`[V]` Before this document, nothing in this repository defined the eight contracts
or their fields. `S1_ENFORCEMENT.md` records exactly that, and it is why S1 stopped
short of them rather than inferring them.

Two classes of content are mixed below, and the distinction is load-bearing at
review:

* **Owner-ratified verbatim** — the eight top-level contract names,
  `CandidateAdvisory` as a nested shape, the `ReviewAction` vocabulary, the
  `DomainCheckCompletion` vocabulary and its S1 restriction, the explicit
  `evaluated_at` parameter, the package-computed eligibility rule, the
  `WorkMandate` structural-security rule, the frozen `P_unsigned` projection and
  its empty-profile semantics, the external-hash rule, the immutable-construction
  rule, and the four equations that must exist.
* **Authored here** — the individual field names, types and constraints of each
  contract, derived as the minimum set that satisfies the ratified rules above
  together with D1, D3, D4, D7 and D8. These are marked `[I]` where the derivation
  is not forced.

`[R]`-free by construction: every field below is either forced by a ratified rule
or is the minimum carrier for one. **It is nevertheless the reviewer's obligation
to confirm the authored field sets against the owner's reconciled contract set
before this PR is merged.** Implementation stays unauthorized until then.

---

## Cross-cutting ratified semantics

### C1 — Model configuration

Every contract and nested model in this document is a `pydantic` v2 `BaseModel`
declared with:

```python
model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
```

`frozen=True` gives structural immutability; `extra="forbid"` is the structural
prohibition D-mandated for `WorkMandate` and is applied uniformly; `strict=True`
stops silent coercion from changing an identity-bearing value.

### C2 — No bare JSON number may appear in any advisory-reachable field

`[V]` The ratified identity substrate rejects bare JSON numbers:
`packages/jcs/src/ugence_jcs/canon.py:88-93` raises `BareNumberError` for any `int`
and for any `float`, with the module docstring recording the Action Profile rule
"NO bare JSON numbers in authorization payloads -> reject. Every numeric is a typed
string upstream." Reproduced directly against `ugence_jcs 0.2.0`
(`packages/jcs/src/ugence_jcs/version.py`): canonicalizing `{"n": 3}` raises
`BareNumberError: bare integer at 'n'`.

**Ratified consequence.** No field of any contract below is typed `int`, `float`,
`Decimal` or any numeric type. S1 needs no numeric field, so the constraint is
satisfied by having none rather than by string-encoding numbers. If a later stage
requires a magnitude, it is carried as a typed decimal string and the encoding is
ratified then.

`bool` is unaffected: `canon.py:76-80` renders `True`/`False` before reaching the
`int` branch, so a boolean field canonicalizes to `true`/`false`.

### C3 — Timestamps

Every `datetime` field is:

* **required to be timezone-aware.** A naive `datetime` is rejected at validation
  with no default-timezone assumption.
* **normalized to UTC at validation.** Any aware input is accepted and converted
  with `value.astimezone(timezone.utc)`; the stored value is always UTC. Two inputs
  naming the same instant in different offsets therefore produce the same stored
  value and the same digest.
* **serialized with a trailing `Z`,** to millisecond precision, by an explicit
  `@field_serializer`:

  ```python
  value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
  ```

`[V]` The serializer is required, not decorative: `model_dump(mode="json")` on a
UTC-aware `datetime` emits `+00:00`, not `Z`. Verified against `pydantic 2.13.4`.
Because the serialized text is what `P_unsigned` carries, the serializer is
identity-significant and is pinned by a frozen-profile test.

### C4 — Opaque identifier format

Every externally issued identifier field (`*_id`) is `str`, constrained by
`pattern=r"^[A-Za-z0-9._:-]{1,200}$"`.

`[I]` The character class is deliberately ASCII. `nfc_paths` is empty (see C6), so
the identity function performs no Unicode normalization; restricting identifiers to
characters with no alternative NFC spelling removes the only route by which two
visually identical advisories could carry different digests through an identifier.

### C5 — Digest-shaped field format

Every digest-shaped field — `advisory_digest`, `parent_advisory_digest`,
`context_hash`, `content_hash` — is `str` constrained by
`pattern=r"^sha256:[0-9a-f]{64}$"`: the literal prefix `sha256:`, then exactly 64
lowercase hexadecimal characters. Uppercase hexadecimal is rejected rather than
lowercased, because accepting both spellings would let one content have two
identity strings.

### C6 — Frozen canonicalization profile

```text
set_paths = empty
nfc_paths = empty
```

Consequences, ratified:

* RFC 8785 / Action-Profile behaviour is used **without any extra path semantics**.
* **List ordering is identity-significant.** No array in `P_unsigned` is treated as
  a set; reordering `observations`, `candidates`, `referenced_observation_ids` or
  `permitted_advisory_scopes` produces a different digest. Any semantic sorting a
  producer wants must happen **before** construction, never inside the identity
  function.
* **Unicode is not normalized by the identity function.** Validation may reject
  non-NFC text; the identity function will not rewrite it.
* All validation occurs before canonicalization. The canonicalizer decides nothing.
* `parent_advisory_digest` participates in identity **including when it is
  `null`**, because `exclude_none=False` retains it.

---

## Contracts

Eight top-level contracts. `CandidateAdvisory` is a **nested public shape**, not a
ninth top-level contract: it is exported for typing and is never constructed or
transported on its own.

For every field: name, type, requiredness, nullability, default, cardinality, closed
vocabulary, validation, ownership, lineage, and whether it participates in the
canonical advisory identity (`P_unsigned`). "Identity: yes" means the field is
reachable from `ProposerAdvisory` and is therefore covered by `advisory_digest`.

### 1. `AgentIdentityRef`

D3: the proposer mints no agent identity. Every field is an externally issued fact.

| Field | Type | Required | Nullable | Default | Cardinality | Vocabulary | Validation | Ownership | Lineage | Identity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `agent_id` | `str` | yes | no | none | 1 | open | C4 | external identity issuer | root of the agent reference chain | yes |
| `issuer_id` | `str` | yes | no | none | 1 | open | C4 | external identity issuer | names the issuing authority | yes |
| `identity_binding_ref` | `str` | yes | no | none | 1 | open | C4 | external identity issuer | the declared binding D3 permits validating | yes |
| `tenant_id` | `str` | yes | no | none | 1 | open | C4 | external identity issuer | tenant scope root (see V5) | yes |

No lifecycle field and no lifecycle verb: D3 bars create, activate, suspend,
replace and enlarge.

### 2. `CognitiveRoleContract`

D1 and D8: a proposer-local **v0** projection, never exported to shared contracts,
carrying no constitution-derived attribute, exposing no role lifecycle verb.

| Field | Type | Required | Nullable | Default | Cardinality | Vocabulary | Validation | Ownership | Lineage | Identity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `role_id` | `str` | yes | no | none | 1 | open | C4 | external role owner | root of the role reference chain | yes |
| `role_projection_version` | `Literal["v0"]` | yes | no | `"v0"` | 1 | closed: `v0` | literal equality | this package | pins the D8 containment bound | yes |
| `tenant_id` | `str` | yes | no | none | 1 | open | C4 | external role owner | must equal `AgentIdentityRef.tenant_id` (V5) | yes |
| `is_active` | `bool` | yes | no | none | 1 | closed: `true`, `false` | strict bool | external role owner | **input fact, never computed** (D1) | yes |
| `permitted_advisory_scopes` | `tuple[str, ...]` | yes | no | none | 1..N | open | each element C4; no duplicates; order identity-significant | external role owner | the minimum immutable attributes for deterministic matching (D1) | yes |

`[I]` `permitted_advisory_scopes` has a floor of one element. A role projection with
no permitted scope can satisfy no mandate, so it can only ever produce a vacuously
ineligible advisory; rejecting it at validation is strictly more informative.

`[V]` D8's export bound is not a field property and is enforced separately by
`tests/test_role_projection_bounds.py`.

### 3. `WorkMandate`

| Field | Type | Required | Nullable | Default | Cardinality | Vocabulary | Validation | Ownership | Lineage | Identity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `mandate_id` | `str` | yes | no | none | 1 | open | C4 | mandate issuer | root of the mandate chain | yes |
| `tenant_id` | `str` | yes | no | none | 1 | open | C4 | mandate issuer | must equal `AgentIdentityRef.tenant_id` (V5) | yes |
| `case_id` | `str` | yes | no | none | 1 | open | C4 | mandate issuer | case scope root (V6) | yes |
| `agent_id` | `str` | yes | no | none | 1 | open | C4 | mandate issuer | **must equal** `AgentIdentityRef.agent_id` (V1) | yes |
| `role_id` | `str` | yes | no | none | 1 | open | C4 | mandate issuer | **must equal** `CognitiveRoleContract.role_id` (V2) | yes |
| `required_advisory_scope` | `str` | yes | no | none | 1 | open | C4 | mandate issuer | **must be a member of** `CognitiveRoleContract.permitted_advisory_scopes` (V4) | yes |
| `purpose_text` | `str \| None` | yes (explicit) | yes | none | 0..1 | open | length ≤ 4000; NFC required; no content-based scanning | mandate issuer | **non-authoritative** | yes |

**Ratified security rule.** `WorkMandate` security is **structural, not lexical**.
No implementation may scan `purpose_text` — or any other free-text field — for
substrings such as `token`, `secret`, `credential`, or any successor word list.
Such a scan is trivially defeated by spelling and simultaneously rejects lawful
prose. Authority-bearing content is excluded by `extra="forbid"` plus the D7 barred
field set, so an undeclared authority-bearing field cannot be carried at all.
`purpose_text` is free text with no authority: nothing downstream may read a
permission, a scope, a decision or an instruction out of it.

`purpose_text` is **required as a field and nullable as a value**: the caller must
state `None` explicitly. `[I]` A default would make "no purpose supplied" and
"purpose deliberately withheld" produce identical bytes without the caller ever
deciding which they meant, and the field participates in identity.

### 4. `BoundedContextEnvelope`

| Field | Type | Required | Nullable | Default | Cardinality | Vocabulary | Validation | Ownership | Lineage | Identity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `context_id` | `str` | yes | no | none | 1 | open | C4 | context assembler | root of the context chain | yes |
| `tenant_id` | `str` | yes | no | none | 1 | open | C4 | context assembler | must equal `AgentIdentityRef.tenant_id` (V5) | yes |
| `case_id` | `str` | yes | no | none | 1 | open | C4 | context assembler | must equal `WorkMandate.case_id` (V6) | yes |
| `context_hash` | `str` | yes | no | none | 1 | open | C5 **format only** | **context assembler** | binds the envelope to assembled content | yes |
| `assembler_id` | `str` | yes | no | none | 1 | open | C4 | context assembler | names the producer | yes |
| `assembled_at` | `datetime` | yes | no | none | 1 | — | C3 | context assembler | ordering fact (V9) | yes |

**`context_hash` is externally supplied.** S1 validates its *format* under C5 and
does nothing else with it. S1 does not compute it, does not recompute it, and does
not verify it against any content — doing so would require hashing locally, which
D2 bars.

### 5. `ToolObservation`

| Field | Type | Required | Nullable | Default | Cardinality | Vocabulary | Validation | Ownership | Lineage | Identity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `observation_id` | `str` | yes | no | none | 1 | open | C4; unique within its containing tuple (V7) | observation producer | referent of `CandidateAdvisory.referenced_observation_ids` | yes |
| `tenant_id` | `str` | yes | no | none | 1 | open | C4 | observation producer | must equal `AgentIdentityRef.tenant_id` (V5) | yes |
| `case_id` | `str` | yes | no | none | 1 | open | C4 | observation producer | must equal `WorkMandate.case_id` (V6) | yes |
| `context_id` | `str` | yes | no | none | 1 | open | C4 | observation producer | **must equal** `BoundedContextEnvelope.context_id` (V3) | yes |
| `producer_id` | `str` | yes | no | none | 1 | open | C4 | observation producer | names the producer | yes |
| `content_hash` | `str` | yes | no | none | 1 | open | C5 **format only** | **observation producer** | binds the observation to its content | yes |
| `observed_at` | `datetime` | yes | no | none | 1 | — | C3 | observation producer | ordering fact (V9) | yes |

**`content_hash` is externally supplied**, on the same terms as `context_hash`.

### 6. `AdvisoryCandidateSet`

| Field | Type | Required | Nullable | Default | Cardinality | Vocabulary | Validation | Ownership | Lineage | Identity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `candidate_set_id` | `str` | yes | no | none | 1 | open | C4 | this package | root of the candidate chain | yes |
| `candidates` | `tuple[CandidateAdvisory, ...]` | yes | no | none | 1..N | — | `candidate_id` unique across the tuple (V7); order identity-significant (C6) | this package | contains the nested shape | yes |
| `selected_candidate_id` | `str \| None` | yes (explicit) | yes | none | 0..1 | open | C4 when non-null; **S1**, **S2** below | this package | selects exactly one member of `candidates` | yes |

**Locally computable selection invariants.** `AdvisoryCandidateSet` carries no
terminal outcome, so it cannot validate against one. Both invariants below are
decidable from this contract's own contents alone:

* **S1 — resolution.** If `selected_candidate_id` is not `None`, then exactly one
  element of `candidates` has that `candidate_id`. Since candidate ids are unique
  (V7), "exactly one" and "at least one" coincide; the rule is written as *exactly
  one* so that it stays correct if uniqueness is ever relaxed.
* **S2 — eligibility of the selection.** If `selected_candidate_id` is not `None`,
  the resolved candidate has `is_eligible is True`. A set may never select an
  ineligible candidate.

`[I]` The converse ("if any candidate is eligible then one must be selected") is
**not** an invariant. Declining to select among eligible candidates is `ABSTAIN`,
which D4 ratifies and which the ADR records as the proposer's inverse of a denial.
Forcing selection would convert an abstention into a recommendation.

The cross-contract relationship to `TerminalOutcome` is stated at `ProposerAdvisory`
level as V10, where both operands exist.

### `CandidateAdvisory` — nested public shape

| Field | Type | Required | Nullable | Default | Cardinality | Vocabulary | Validation | Ownership | Lineage | Identity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `candidate_id` | `str` | yes | no | none | 1 | open | C4; unique within its set (V7) | this package | referent of `selected_candidate_id` | yes |
| `disposition` | `CandidateDisposition` | yes | no | none | 1 | **closed, D4**: `RECOMMEND_MATCHED_FOR_APPROVAL`, `RECOMMEND_WITHHOLD`, `REQUEST_EVIDENCE`, `ESCALATE_EXCEPTION` | enum membership | this package | — | yes |
| `requested_review_action` | `ReviewAction` | yes | no | none | 1 | **closed**: `ROUTE_APPROVAL_BUNDLE`, `CREATE_EXCEPTION_REVIEW_BUNDLE` | enum membership | this package | must equal `ProposerAdvisory.requested_review_action` when selected (V11) | yes |
| `referenced_observation_ids` | `tuple[str, ...]` | yes | no | none | **1..N** | open | each C4; no duplicates (V8); every id resolves (E1-T9); order identity-significant | this package | references `ToolObservation.observation_id` | yes |
| `domain_check_completion` | `DomainCheckCompletion` | yes | no | none | 1 | **closed**: `NOT_EVALUATED`, `COMPLETE` | enum membership; **S1 may construct only `NOT_EVALUATED`** | this package | — | yes |
| `is_eligible` | `bool` | yes | no | none | 1 | closed: `true`, `false` | **package-computed** — see *Eligibility construction* | this package | the recorded result of Equation 1 | yes |
| `evaluated_at` | `datetime` | yes | no | none | 1 | — | C3 | caller-supplied, package-recorded | the explicit evaluation instant passed to Equation 1 | yes |

`referenced_observation_ids` has a **floor of one element**. This is what makes
Equation 1's reference check non-vacuous: an empty tuple would satisfy a universal
quantification trivially, and a candidate that references no observation has no
evidentiary basis to advise from.

`[V]` No field of `CandidateAdvisory` or `ProposerAdvisory` is typed
`SemanticAuditorFindingStatus`, and none may be assigned one: D6's standing rule is
enforced by `tests/test_no_auditor_status_projection.py`.

### 7. `ProposerAdvisory`

D7: kind `ugence.agentic_proposer.advisory.v0`; `advisory_digest` is the **sole**
identity field; identity is computed only through `ugence_jcs`; the eight barred
fields (`fingerprint`, `provider_id`, `operation`, `arguments`, `idempotency_key`,
`workflow_id`, `instance_id`, `task_id`) appear at no nesting depth; no exported
name begins with `Proposal` or `Recommendation`.

| Field | Type | Required | Nullable | Default | Cardinality | Vocabulary | Validation | Ownership | Lineage | Identity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `kind` | `Literal["ugence.agentic_proposer.advisory.v0"]` | yes | no | `"ugence.agentic_proposer.advisory.v0"` | 1 | closed, D7 | literal equality | this package | — | yes |
| `tenant_id` | `str` | yes | no | none | 1 | open | C4; V5 | this package | tenant scope assertion | yes |
| `case_id` | `str` | yes | no | none | 1 | open | C4; V6 | this package | case scope assertion | yes |
| `agent_identity` | `AgentIdentityRef` | yes | no | none | 1 | — | nested model | external issuer | V1 | yes |
| `role` | `CognitiveRoleContract` | yes | no | none | 1 | — | nested model | external role owner | V2 | yes |
| `mandate` | `WorkMandate` | yes | no | none | 1 | — | nested model | mandate issuer | V1, V2, V4 | yes |
| `context` | `BoundedContextEnvelope` | yes | no | none | 1 | — | nested model | context assembler | V3 | yes |
| `observations` | `tuple[ToolObservation, ...]` | yes | no | none | 1..N | — | `observation_id` unique (V7); order identity-significant | observation producers | referents for every candidate | yes |
| `candidate_set` | `AdvisoryCandidateSet` | yes | no | none | 1 | — | nested model; S1, S2 | this package | V10, V11 | yes |
| `terminal_outcome` | `TerminalOutcome` | yes | no | none | 1 | **closed, D4**: `PROPOSAL`, `NEED_EVIDENCE`, `ABSTAIN`, `ESCALATE` | enum membership; V10 | caller-supplied input fact | — | yes |
| `requested_review_action` | `ReviewAction \| None` | yes (explicit) | yes | none | 0..1 | closed | V11 | this package | mirrors the selected candidate's action | yes |
| `parent_advisory_digest` | `str \| None` | yes (explicit) | yes | none | 0..1 | open | C5 when non-null; V12 | this package | lineage link to a prior advisory | **yes, including when `null`** |
| `constructed_at` | `datetime` | yes | no | none | 1 | — | C3; V9 | this package | — | yes |
| `advisory_digest` | `str` | yes | **no** | none | 1 | open | C5; equals Equation 3 over `P_unsigned` | this package | **the sole identity field** | **excluded from `P_unsigned`** |

There is no `advisory_id`. D7 makes `advisory_digest` the only identity field, and a
second identifier would create a second, unverifiable identity.

`[I]` **`terminal_outcome` is a supplied input fact, not a computed value.** S1
computes no mapping from candidate dispositions to a terminal outcome, and none has
been ratified. This follows the pattern D1 and D3 already establish for this
capability — role activation state and agent identity are both supplied facts that
the proposer validates and never computes — rather than inventing a projection.
S1 enforces the one part that *is* locally decidable (V10) and nothing more. A
disposition-to-outcome mapping, if one is ever wanted, is a separate ratification.

### 8. `ProposerProcessRecord`

A non-identity-bearing audit record. It is **not** a field of `ProposerAdvisory` and
is not reachable from `P_unsigned`, so nothing in it can alter an advisory identity.

| Field | Type | Required | Nullable | Default | Cardinality | Vocabulary | Validation | Ownership | Lineage | Identity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `record_id` | `str` | yes | no | none | 1 | open | C4 | this package | root of the record chain | no |
| `tenant_id` | `str` | yes | no | none | 1 | open | C4; must equal the referenced advisory's | this package | — | no |
| `case_id` | `str` | yes | no | none | 1 | open | C4; must equal the referenced advisory's | this package | — | no |
| `advisory_digest` | `str` | yes | no | none | 1 | open | C5 | this package | **references** `ProposerAdvisory.advisory_digest` | no |
| `eligibility_equation_version` | `Literal["ugence.agentic_proposer.equation.eligibility.v1"]` | yes | no | that literal | 1 | closed | literal equality | this package | pins Equation 1 | no |
| `readiness_equation_version` | `Literal["ugence.agentic_proposer.equation.readiness.v1"]` | yes | no | that literal | 1 | closed | literal equality | this package | pins Equation 2 | no |
| `identity_profile_version` | `Literal["ugence.agentic_proposer.identity.jcs-empty-profile.v1"]` | yes | no | that literal | 1 | closed | literal equality | this package | pins the C6 profile | no |
| `jcs_distribution_version` | `str` | yes | no | none | 1 | open | `^[0-9]+\.[0-9]+\.[0-9]+$` | resolved from the installed distribution | records the substrate actually used | no |
| `recorded_at` | `datetime` | yes | no | none | 1 | — | C3 | this package | — | no |

`jcs_distribution_version` is read from the **installed distribution metadata**, not
from `pyproject.toml` text. `[V]` `S1_ENFORCEMENT.md` records the declared-floor
text check as the weaker of the two available assertions; this field carries the
resolved value so that a process record states which substrate actually ran.

---

## Reference, lineage and scope validations

Each is a validation S1 must implement. V1–V4 and V7–V9 are also Equation 1 terms;
listed once here as contract obligations and referenced from the equation.

| Id | Rule | Prevents |
| --- | --- | --- |
| V1 | `mandate.agent_id == agent_identity.agent_id` | a mandate executed against an unrelated agent |
| V2 | `mandate.role_id == role.role_id` | a mandate matched against an unrelated role |
| V3 | every `observations[i].context_id == context.context_id` | observations from a different context bundle |
| V4 | `mandate.required_advisory_scope in role.permitted_advisory_scopes` | advising outside the role's permitted scope |
| V5 | `tenant_id` is identical across `ProposerAdvisory`, `agent_identity`, `role`, `mandate`, `context` and **every** observation | **cross-tenant acceptance** |
| V6 | `case_id` is identical across `ProposerAdvisory`, `mandate`, `context` and **every** observation | **cross-case acceptance** |
| V7 | `observation_id` is unique across `observations`; `candidate_id` is unique across `candidate_set.candidates`; `permitted_advisory_scopes` elements are unique | an id resolving ambiguously to two objects |
| V8 | `referenced_observation_ids` contains no duplicate, per candidate | a reference list that overstates its evidentiary breadth |
| V9 | `constructed_at >= candidate.evaluated_at` for every candidate; `evaluated_at >= context.assembled_at`; `evaluated_at >= observed_at` for every **referenced** observation | an advisory evaluated before the facts it cites existed |
| V10 | `terminal_outcome is TerminalOutcome.PROPOSAL` **if and only if** `candidate_set.selected_candidate_id is not None` | a "proposal" that proposes nothing, and a selection presented as an abstention |
| V11 | `requested_review_action is None` **iff** `selected_candidate_id is None`; when non-null it **equals** the resolved candidate's `requested_review_action` | an advisory whose routing contradicts the candidate it selected |
| V12 | `parent_advisory_digest`, when non-null, is C5-shaped and is **not equal to** this advisory's own `advisory_digest` | a self-referential lineage cycle |

**Missing-reference rule.** V3, V5, V6, V7 and Equation-1 term T9 together make
every reference *resolve to a present object in the same tenant and case*. No
reference in these contracts is validated by format alone — except the two external
hashes (C5), which by ratified rule reference content this package never holds.

`[I]` V12 rejects only the immediate self-cycle. Longer lineage cycles are not
locally decidable: this package holds one advisory, not the chain. Chain-level
lineage validation belongs to whatever stores advisories, and this document does not
claim S1 provides it.

---

## Eligibility construction — the enforceable boundary

`CandidateAdvisory.is_eligible` is **package-computed**. A caller does not assert it.

**What cannot be claimed.** Exporting a `pydantic` model does not make its
constructor unreachable. `CandidateAdvisory(...)` remains callable by anyone who can
import the name, `model_construct` bypasses validation entirely, and no amount of
ordinary field validation authenticates a caller-supplied Boolean — a validator
sees the value, not its provenance. Any claim that field validation alone secures
`is_eligible` is false and must not appear in S1 documentation, tests or commit
messages.

**The enforceable boundary, precisely.**

1. **One authoritative builder.** `build_candidate_advisory` (signature below) is
   the sole package-owned construction path. It receives the identity, role,
   mandate, context, the relevant observations, the candidate disposition, the
   requested review action and an explicit `evaluated_at`; it computes Equation 1;
   and it returns the frozen `CandidateAdvisory` carrying that computed result. It
   takes no `is_eligible` parameter, so there is no channel through which a caller
   can supply one.
2. **Authority-facing verification recomputes.** Any consumer that acts on
   eligibility — and `build_proposer_advisory` itself — **must independently
   recompute Equation 1 from the advisory's own contents and reject any candidate
   whose stored `is_eligible` differs from the recomputed value.** This is the
   operative guarantee. It holds regardless of how the object was constructed,
   including via `model_construct`.
3. **The recomputation is total.** `verify_candidate_eligibility` (signature below)
   recomputes every candidate in an advisory. `build_proposer_advisory` calls it and
   refuses to construct an advisory containing a mismatched candidate, so a forged
   candidate cannot reach a digest.

`[I]` This is the same shape as the D2 addendum: the invariant is the guarantee, and
the construction path is defence-in-depth that does not by itself constitute proof.

---

## Domain completion

`DomainCheckCompletion` is exactly:

* `NOT_EVALUATED`
* `COMPLETE`

**S1 may construct only `NOT_EVALUATED`.** `build_candidate_advisory` takes no
completion parameter and hard-codes `NOT_EVALUATED`; a test asserts that no S1 code
path produces `COMPLETE`.

**Therefore Equation 2 is `False` for every S1-constructible candidate.** This is
correct and intended, not a defect: S1 authorizes no invoice-domain check, so no S1
candidate can be domain-complete. `COMPLETE` becomes constructible only through a
later, **separately ratified** domain-evaluator boundary. `COMPLETE` is defined now
so that the enum is closed and Equation 2 is total, and so that adding the evaluator
later is not a vocabulary change.

---

## Canonical advisory projection

`P_unsigned` is frozen as **exactly** the JSON-mode projection of the complete
`ProposerAdvisory` with only `advisory_digest` omitted and every other nullable field
retained:

```python
advisory.model_dump(
    mode="json",
    exclude={"advisory_digest"},
    exclude_none=False,
)
```

with the profile of C6 (`set_paths` empty, `nfc_paths` empty).

`compute_advisory_digest` uses **only**:

```python
ugence_jcs.canonical_sha256_hex(P_unsigned)
```

and stores `"sha256:"` concatenated with the 64 lowercase hexadecimal characters
returned. `[V]` `canonical_sha256_hex` returns a bare hex digest with no prefix and
no envelope framing (`packages/jcs/src/ugence_jcs/canon.py:129-140`), so the prefix
is applied by this package and nowhere else.

No other digest, no domain tag, no length prefix, no salt and no envelope is
introduced. No second identity function exists.

### Immutable construction, and the unsigned payload

An unsigned `ProposerAdvisory` is **not a public-valid state**: `advisory_digest` is
required and non-nullable, so the public contract always carries a digest.

The construction representation is a **private** model:

```python
class _UnsignedAdvisoryPayload(BaseModel):   # not exported
```

declaring exactly the fields of `ProposerAdvisory` **except** `advisory_digest`, with
identical types, defaults, validators and serializers. `build_proposer_advisory`
constructs the payload, computes its digest, and returns a fully populated frozen
`ProposerAdvisory`. There is no in-place mutation path and no setter.

**Equivalence obligation.** A frozen-profile test asserts, over a fixed corpus of
advisories, that

```python
payload.model_dump(mode="json", exclude_none=False)
```

is equal to the ratified `P_unsigned` expression evaluated on the resulting
`ProposerAdvisory`, and that both canonicalize to identical bytes. Without that test
the private payload could drift from the public contract and produce a digest that
no independent verifier could reproduce — which is precisely the D2 failure.

**Verification is separate.** `verify_advisory_digest` recomputes the digest from
the stored `ProposerAdvisory` content and compares it with `advisory_digest`. It
shares no code path with the builder beyond `compute_advisory_digest` itself, and it
imports no hashing module. Comparison is a plain string equality: both operands are
public, non-secret digests, and `hmac.compare_digest` is unavailable here because
`hmac` is a forbidden import in `src`
(`tests/test_no_local_canonicalization.py::FORBIDDEN_IMPORTS`).

---

## Equations

All four are pure, deterministic, total functions. None reads a clock, a file, an
environment variable, a network or a random source. All parameters are
keyword-only.

### Equation 1 — `evaluate_eligibility`

```python
def evaluate_eligibility(
    *,
    identity: AgentIdentityRef,
    role: CognitiveRoleContract,
    mandate: WorkMandate,
    context: BoundedContextEnvelope,
    observations: tuple[ToolObservation, ...],
    referenced_observation_ids: tuple[str, ...],
    evaluated_at: datetime,
) -> bool:
```

`evaluated_at` is an **explicit, timezone-aware** parameter. No internal wall-clock
read is permitted anywhere in S1: `datetime.now`, `datetime.utcnow`, `time.time` and
`time.monotonic` appear in no `src` module, asserted by a test.

Terms, each an actual `bool`:

| Term | Definition |
| --- | --- |
| T1 | `mandate.agent_id == identity.agent_id` |
| T2 | `mandate.role_id == role.role_id` |
| T3 | `role.is_active is True` |
| T4 | `mandate.required_advisory_scope in role.permitted_advisory_scopes` |
| T5 | `len({identity.tenant_id, role.tenant_id, mandate.tenant_id, context.tenant_id} \| {o.tenant_id for o in observations}) == 1` |
| T6 | `len({mandate.case_id, context.case_id} \| {o.case_id for o in observations}) == 1` |
| T7 | `all(o.context_id == context.context_id for o in observations)` |
| T8 | `len(referenced_observation_ids) > 0` |
| T9 | `set(referenced_observation_ids) <= {o.observation_id for o in observations}` |
| T10 | `len(set(referenced_observation_ids)) == len(referenced_observation_ids)` |
| T11 | `len({o.observation_id for o in observations}) == len(observations)` |
| T12 | `evaluated_at.tzinfo is not None and evaluated_at.utcoffset() is not None` |
| T13 | `evaluated_at >= context.assembled_at` |
| T14 | `all(o.observed_at <= evaluated_at for o in observations if o.observation_id in set(referenced_observation_ids))` |

Return value:

```python
return all((T1, T2, T3, T4, T5, T6, T7, T8, T9, T10, T11, T12, T13, T14))
```

`all(...)` is used deliberately. Chained `and` returns the **last operand**, so
`x and y` where `y` is a non-empty `str` returns that string, not `True`; a function
annotated `-> bool` would then return a truthy non-Boolean and a caller comparing
`is True` would silently see a mismatch. `all()` returns an actual `bool` for every
input. A test asserts `evaluate_eligibility(...) is True` / `is False` — identity
against the singletons, not truthiness.

**Non-vacuity.** T8 gives `referenced_observation_ids` a floor of one, so T9's
subset test and T14's universal quantification can never pass over an empty set.
T9 fails whenever **any** referenced id is absent from `observations`: the subset
relation is exactly "every reference resolves". T11 makes the resolution
unambiguous.

`domain_check_completion` is **not** a term of Equation 1. Eligibility and domain
completion are independent; conflating them would make every S1 candidate ineligible
and erase the distinction Equation 2 exists to draw.

### Equation 2 — `evaluate_readiness`

```python
def evaluate_readiness(*, candidate: CandidateAdvisory) -> bool:
    return all((
        candidate.is_eligible is True,
        candidate.domain_check_completion is DomainCheckCompletion.COMPLETE,
    ))
```

`is True` and `is` are identity comparisons; `all()` returns an actual `bool`.
Because S1 constructs only `NOT_EVALUATED`, this returns `False` for every
S1-constructible candidate, as ratified above.

### Equation 3 — `compute_advisory_digest`

```python
def compute_advisory_digest(*, advisory: ProposerAdvisory) -> str:
    return "sha256:" + ugence_jcs.canonical_sha256_hex(
        advisory.model_dump(
            mode="json",
            exclude={"advisory_digest"},
            exclude_none=False,
        )
    )
```

The builder's private counterpart over `_UnsignedAdvisoryPayload` is
`_compute_payload_digest`, holding the same body over
`payload.model_dump(mode="json", exclude_none=False)`. The two are pinned equal by
the frozen-profile test above.

Canonicalization faults (`BareNumberError`, `NonFiniteNumberError`, `NonNFCError`,
`DuplicateSetElementError`, `UnsupportedTypeError`) propagate unchanged. S1 catches
none of them: a payload that cannot be canonicalized has no identity, and
substituting a fallback would be a second identity function.

### Equation 4 — `verify_advisory_digest`

The independent verification function D2 requires.

```python
def verify_advisory_digest(*, advisory: ProposerAdvisory) -> bool:
    return compute_advisory_digest(advisory=advisory) == advisory.advisory_digest
```

`==` between two `str` values returns an actual `bool`. It recomputes from stored
content only; it consults no cache, no memo and no side table.

---

## Function signatures

```python
def build_candidate_advisory(
    *,
    candidate_id: str,
    identity: AgentIdentityRef,
    role: CognitiveRoleContract,
    mandate: WorkMandate,
    context: BoundedContextEnvelope,
    observations: tuple[ToolObservation, ...],
    referenced_observation_ids: tuple[str, ...],
    disposition: CandidateDisposition,
    requested_review_action: ReviewAction,
    evaluated_at: datetime,
) -> CandidateAdvisory: ...


def build_proposer_advisory(
    *,
    tenant_id: str,
    case_id: str,
    identity: AgentIdentityRef,
    role: CognitiveRoleContract,
    mandate: WorkMandate,
    context: BoundedContextEnvelope,
    observations: tuple[ToolObservation, ...],
    candidate_set: AdvisoryCandidateSet,
    terminal_outcome: TerminalOutcome,
    parent_advisory_digest: str | None,
    constructed_at: datetime,
) -> ProposerAdvisory: ...


def build_advisory_revision(
    *,
    parent: ProposerAdvisory,
    candidate_set: AdvisoryCandidateSet,
    terminal_outcome: TerminalOutcome,
    constructed_at: datetime,
) -> ProposerAdvisory: ...


def verify_candidate_eligibility(*, advisory: ProposerAdvisory) -> bool: ...


def compute_advisory_digest(*, advisory: ProposerAdvisory) -> str: ...


def verify_advisory_digest(*, advisory: ProposerAdvisory) -> bool: ...
```

Notes that are part of the ratified behaviour:

* `build_candidate_advisory` takes **no** `is_eligible` and **no**
  `domain_check_completion`. It computes the first and hard-codes the second to
  `NOT_EVALUATED`.
* `build_proposer_advisory` derives `requested_review_action` from the selected
  candidate (V11) rather than accepting it, so the two cannot disagree. It calls
  `verify_candidate_eligibility` and raises before constructing if any candidate's
  stored `is_eligible` differs from the recomputation.
* `build_advisory_revision` sets `parent_advisory_digest=parent.advisory_digest` and
  reuses the parent's identity, role, mandate, context, observations, `tenant_id`
  and `case_id` unchanged. A revision is a new advisory with a new digest; nothing
  about the parent is mutated.
* `verify_candidate_eligibility` returns `False` — it does not raise — so that a
  read-only auditor can inspect a stored advisory without exception handling.

---

## Public-API snapshot for S1

The complete exported surface S1 will declare. Recorded here as specification; **no
`public_api.json` is created by this document**, and none may exist until S1 is
implemented and separately authorized.

**Contracts (8):** `AgentIdentityRef`, `CognitiveRoleContract`, `WorkMandate`,
`BoundedContextEnvelope`, `ToolObservation`, `AdvisoryCandidateSet`,
`ProposerAdvisory`, `ProposerProcessRecord`

**Nested public model (1):** `CandidateAdvisory`

**Enums (5):** `TerminalOutcome`, `CandidateDisposition`,
`SemanticAuditorFindingStatus` (all three existing, D4), `ReviewAction` (new),
`DomainCheckCompletion` (new)

**Builders (3):** `build_candidate_advisory`, `build_proposer_advisory`,
`build_advisory_revision`

**Equation functions (3):** `evaluate_eligibility`, `evaluate_readiness`,
`compute_advisory_digest`

**Verifier functions (2):** `verify_advisory_digest`, `verify_candidate_eligibility`

**Constants (4):** `RESERVED_AUTHORITY_VOCABULARY` (existing),
`ADVISORY_KIND = "ugence.agentic_proposer.advisory.v0"`,
`ADVISORY_IDENTITY_SET_PATHS = frozenset()`,
`ADVISORY_IDENTITY_NFC_PATHS = frozenset()`

**Metadata (1):** `__version__`

Not exported: `_UnsignedAdvisoryPayload` and `_compute_payload_digest`.

`[V]` No exported name begins with `Proposal` or `Recommendation`, as D7 requires.

---

## Enforcement obligations S1 must discharge

Beyond the D6/D7/D8 obligations already carried by `S1_ENFORCEMENT.md`:

1. **`test_no_local_canonicalization` must be amended before the first S1 module
   lands, and the amendment is narrow.** `[V]` Two ratified names collide with the
   guard as written:
   * `SUSPECT_DEF_SUBSTRINGS` contains `"digest"`, and the definition scan rejects
     any `FunctionDef`/`ClassDef` whose lowered name contains it
     (`tests/test_no_local_canonicalization.py:567-575`). `compute_advisory_digest`
     and `verify_advisory_digest` — both ratified by name — would fail on the
     commit that introduces them.
   * `SUSPECT_TEXT` contains `"sha256"`, and the text scan rejects it wherever it
     appears outside the masked substrate-call spellings
     (`tests/test_no_local_canonicalization.py:42-70`). The ratified `"sha256:"`
     prefix literal and the C5 pattern `^sha256:[0-9a-f]{64}$` would fail the same
     way.

   The resolution is the mechanism the guard already uses for the substrate calls: a
   pinned allowlist of exact spellings, not a widened rule. Specifically — a
   `PERMITTED_IDENTITY_DEFINITIONS` frozenset holding exactly
   `{"compute_advisory_digest", "verify_advisory_digest", "_compute_payload_digest"}`,
   each additionally required to contain a call to `ugence_jcs.canonical_sha256_hex`
   or to one of those three names and to import no hashing module; and an extension
   of `PERMITTED_SUBSTRATE_CALLS` masking exactly the strings `"sha256:"` and
   `"^sha256:[0-9a-f]{64}$"`. Nothing wider. A locally defined `canonical_*`, a bare
   `hashlib.sha256`, and any fourth digest-named definition all remain caught.

   `[I]` This is a test change, not a decision change: D7 ratified the identity
   field and D2 ratified the substrate before either guard was written, and the
   guard was authored over a package that had no identity surface. Recording it here
   is what stops it being discovered as a red CI run on the first S1 commit.
2. **A frozen-profile test suite:** fixed advisory corpus → pinned canonical bytes
   and pinned digests, asserting the C6 profile, the `Z` serialization, the
   `exclude_none=False` retention of `parent_advisory_digest: null`, and the
   payload/advisory projection equivalence.
3. **A list-order significance test:** reordering `observations`, `candidates`,
   `referenced_observation_ids` or `permitted_advisory_scopes` changes the digest.
4. **A no-bare-number test:** the canonicalization of `P_unsigned` over the corpus
   raises no `BareNumberError`, and no `src` model declares a numeric field.
5. **A no-wall-clock test:** no `src` module references `datetime.now`,
   `datetime.utcnow`, `time.time` or `time.monotonic`.
6. **An eligibility-forgery test:** a candidate built with `model_construct` and a
   flipped `is_eligible` is rejected by `verify_candidate_eligibility` and by
   `build_proposer_advisory`.
7. **A `COMPLETE`-unreachability test:** no S1 code path constructs
   `DomainCheckCompletion.COMPLETE`.
8. **An installed-distribution test:** `ugence-jcs` resolves as an installed
   distribution at or above `0.2.0` and exposes `canonical_sha256_hex`, replacing
   the `pyproject.toml` text check `S1_ENFORCEMENT.md` records as the weaker
   assertion.

---

## What this document does not settle

* `[G]` The Agent Constitution still does not exist. `CognitiveRoleContract` remains
  the D8-bounded v0 projection and must be re-derived when the document lands.
  Nothing here is conformance with it.
* No mapping from candidate dispositions to `TerminalOutcome` is ratified; S1 takes
  the outcome as a supplied fact under V10.
* `DomainCheckCompletion.COMPLETE` has no producer and no evaluator boundary.
* Chain-level lineage validation beyond the immediate self-cycle (V12) is outside
  this package.
* No storage, transport, service or authorization surface is specified, authorized
  or implied.
