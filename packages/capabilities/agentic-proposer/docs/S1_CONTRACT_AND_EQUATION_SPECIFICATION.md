# S1 — canonical contract and equation specification

**Status:** `RATIFIED FOR S1 IMPLEMENTATION`
**Ratified against:** the default branch at merge commit
`e28538eb454fce6008e94e0772e0fd09c9c7ea7f` (PR #1474)
**Package:** `ugence-agentic-proposer` (`packages/capabilities/agentic-proposer`)
**Authority:** subordinate to D1–D10 and the ratification addenda in
`docs/architecture/ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md`.

Evidence labels: `[V]` verified against this repository by execution or by reading a
named artifact, `[I]` inferred or authored, `[G]` gap.

This document is the single canonical, implementation-ready S1 specification. It is
organised so that a reader can tell, for any statement, which of five categories it
belongs to:

| Part | Category |
| --- | --- |
| A | Verified repository constraints — facts about the substrate and the merged guards |
| B | Ratified requirements — owner decisions this document implements |
| C–H | The specification itself: model rules, contracts, validations, equations, identity, public surface |
| I | Implementation obligations S1 must discharge |
| J | Intentionally deferred future-stage behaviour |
| K | Residual limitations that are not locally decidable |

---

## Supersession

`packages/capabilities/agentic-proposer/docs/S1_CONTRACT_AND_EQUATION_RATIFICATION.md`,
proposed on the unmerged draft branch `claude/d2-enforcement-ratification-si5lmm`
(PR #1475, head `4fab9d811ff15f59acf59c1f93db502be999a801`), is a **rejected draft**.
It must not be used for implementation. An independent review found that its authored
field sets diverged from the owner's reconciled contract set on all eight contracts
and on both equations, and that its nested-composition design fails a guard merged in
PR #1474. Several of its individual judgments were correct and are carried forward
here, each marked where it appears. PR #1475 itself is left unaltered as a record of
that scrutiny.

---

## Scope

This document specifies **S1 contracts and deterministic equations only**.

It authorises **no** invoice-domain check, **no** reason-code catalogue, **no**
read-only adapter, **no** model-assisted extraction, **no** semantic auditor, **no**
HTTP service, **no** authorisation, **no** operational clearance and **no**
execution. It creates no public-API snapshot and changes no version; it specifies
what S1 will export when S1 is separately authorised.

---

# Part A — Verified repository constraints

These are facts, not decisions. Each was established by execution or by reading a
named artifact at `e28538eb`. They bound what any S1 specification may say.

## A1 — The identity substrate rejects bare numbers

`[V]` `ugence_jcs 0.2.0` (`packages/jcs/src/ugence_jcs/version.py`) raises
`BareNumberError` for any `int` and any `float`
(`packages/jcs/src/ugence_jcs/canon.py:89,92`) and `UnsupportedTypeError` for
`Decimal` (`canon.py:118`). Reproduced in the exact `P_unsigned` call path: a pydantic
model carrying `advisory_version: int = 1` dumps under `model_dump(mode="json")` to a
Python `int`, and canonicalisation then raises
`BareNumberError: bare integer at 'advisory_version'`. Nesting does not help —
a nested integer raises at path `'a.b[].c'`.

**Consequence.** No field of any contract may be `int`, `float` or `Decimal`, and no
container may carry one at any depth. `bool` is unaffected: `canon.py:76-80` renders
`True`/`False` before the `int` branch.

## A2 — `canonical_sha256_hex` returns a bare digest

`[V]` `canon.py:129-140` returns 64 lowercase hexadecimal characters with no prefix,
no domain tag, no length prefix and no envelope framing. Any `sha256:` prefix is
applied by the caller. Its `set_paths` and `nfc_paths` parameters default to
`frozenset()`.

## A3 — `content_hash` is a rival identity field, and reachability is walked at runtime

`[V]` `tests/test_advisory_contract_shape.py` defines
`RIVAL_IDENTITY_FIELDS = {"id", "uid", "uuid", "identity", "identifier", "hash",
"checksum", "content_hash", "advisory_id", "proposal_digest"}` and
`test_identity_field_is_exactly_the_ratified_one` walks the **live** `ProposerAdvisory`
and `CandidateAdvisory` models to any depth, asserting no rival name is reachable.

Executed against a nested composition in which `ProposerAdvisory` carries
`observations: tuple[ToolObservation, ...]`, the walker returns `['content_hash']`.
Executed against the reference-by-id composition specified in Part D, it returns `[]`.

**Consequence.** `ProposerAdvisory` may not nest `ToolObservation`. This is not a
preference and cannot be resolved by an allowlist: `content_hash` is on the rival list
precisely to prevent a second identity, and exempting it would defeat D7. The
reference-by-id shape in Part D is forced.

## A4 — The lifecycle-verb scan currently matches data names

`[V]` `tests/test_role_projection_bounds.py` matches `LIFECYCLE_VERBS` as
case-insensitive stems over `_defined_names`, which includes `ClassDef` names,
`AnnAssign` targets and enum member assignments. Executed against the ratified
vocabulary, it returns
`['REVOKED', 'RoleActivationStatus', 'SUSPENDED', 'activation_status', 'expires_at']`.

**Consequence.** The ratified vocabulary in B4 cannot be expressed until the guard is
narrowed as specified in I2. Verified narrowing: restricting the scan to callable
names returns `[]` for the retained vocabulary and still returns
`['ActivateRole', 'activate', 'expire_mandate', 'reactivate', 'revoke_identity',
'suspend_role']` for lifecycle authority.

## A5 — Identity may be assigned only by an inline substrate call

`[V]` `test_identity_is_computed_only_through_the_permitted_substrate` collects every
value expression assigned to `advisory_digest` — including every `advisory_digest=`
keyword in any call — and requires a call inside that expression whose root name
resolves to a `ugence_jcs` import. Executed:

| Expression | Result |
| --- | --- |
| `ProposerAdvisory(advisory_digest="sha256:" + ugence_jcs.canonical_sha256_hex(P))` | permitted |
| `ProposerAdvisory(advisory_digest=_compute_payload_digest(payload))` | **rejected** |
| `ProposerAdvisory(advisory_digest=None, …)` | **rejected** — "a literal computes nothing" |

**Consequence.** There is no two-phase draft with a null digest, and no local digest
function may be passed by name into that keyword. Part G specifies the only permitted
shape.

## A6 — `CandidateAdvisory` cannot satisfy the ratified-kind assertion

`[V]` `test_a_defined_advisory_type_declares_the_ratified_kind` is parametrised over
both `ProposerAdvisory` and `CandidateAdvisory`. Verified against `pydantic 2.13.4`: a
model without a `kind` field yields `{None}` and fails the assertion.

**Consequence.** The guard must be narrowed as specified in I3.

## A7 — The D2 scan collides with the `sha256:` prefix literal

`[V]` `tests/test_no_local_canonicalization.py` lists `"sha256"` in `SUSPECT_TEXT` and
masks only the exact spellings in `PERMITTED_SUBSTRATE_CALLS`. The ratified `"sha256:"`
prefix and the C6 pattern would be flagged. `"digest"` is in
`SUSPECT_DEF_SUBSTRINGS`, so any function or class whose lowered name contains it is
rejected; the identity function names in Part H are chosen to avoid that collision
entirely rather than to require an exemption for it.

## A8 — `hmac` is a forbidden import

`[V]` `FORBIDDEN_IMPORTS = {"hashlib", "hmac", "binascii", "struct"}`. Digest
comparison is therefore plain string equality. Both operands are public, non-secret
digests, so this is correct on its own terms and not a concession.

## A9 — pydantic serialisation behaviour

`[V]` Verified against `pydantic 2.13.4`: `model_dump(mode="json")` emits `Z` for a
UTC-aware `datetime` and `+02:00` for any other offset; `strict=True` does **not**
reject a naive `datetime`; `exclude={"advisory_digest"}` removes only the top-level
field and leaves a nested field of the same name in place; `exclude_none=False`
retains a null; `tuple` and `list` both dump to a JSON array; a `str`-valued `Enum`
dumps to its value.

---

# Part B — Ratified requirements

## B1 — D1–D10

Recorded verbatim in `docs/architecture/ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md`
and not reinterpreted here. This document implements D1 (role projection as a bounded
data projection, activation an input fact), D3 (no agent identity minted), D4 (the
ratified vocabulary and the reserved authority vocabulary), D6 (no auditor status
projected into an outcome or disposition field), D7 (`ProposerAdvisory`,
`CandidateAdvisory`, the kind string, `advisory_digest` as the sole identity field,
identity only through `ugence_jcs`, the eight barred fields, the barred name
prefixes) and D8 (the v0 role projection's containment bounds).

## B2 — D2 is a behavioural and architectural invariant

An advisory identity is valid only when an independent verifier recomputes it from the
frozen unsigned projection under the ratified `ugence-jcs` profile and obtains the
exact stored digest. Static scanning remains a mandatory release guard and
defence-in-depth; it is not the definition of the rule and is not proof. Recorded in
full in `S1_ENFORCEMENT.md`.

## B3 — V13: `PROPOSAL` requires readiness

`TerminalOutcome.PROPOSAL` requires `evaluate_readiness(...) is True` for the selected
candidate, independently recomputed by `build_proposer_advisory`.

Because S1 cannot construct `DomainCheckCompletion.COMPLETE` (C7), readiness is `False`
for every candidate S1 can construct. Therefore **S1 cannot emit `PROPOSAL`**, every S1
authority-facing advisory has `selected_candidate_id = None`, and the only terminal
outcomes S1 may emit are `NEED_EVIDENCE`, `ABSTAIN` and `ESCALATE`.

This is fail-closed and intended. A stage that authorises no domain check must not be
able to reach the proposer's strongest classification.

## B4 — Lifecycle vocabulary and lifecycle authority (O-2)

`SUSPENDED`, `REVOKED`, `RoleActivationStatus`, `activation_status` and `expires_at`
are retained. A contract **describing** a lifecycle state or a validity period
determined by an external authority is not a capability **exercising** lifecycle
authority, and the two must not be conflated by a lexical scan.

What remains prohibited is agent-owned lifecycle mutation: any method or function that
activates, deactivates, reactivates, suspends, unsuspends, ratifies, revokes,
reinstates, issues, expires, provisions, grants, authorises, enrols, replaces or
otherwise changes a lifecycle state. The guard correction and its mutation tests are
specified in I2.

## B5 — Advisory kind applies to the authority-facing advisory only (O-3)

The ratified `kind` requirement applies to `ProposerAdvisory`. `CandidateAdvisory` is a
subordinate candidate record and must not claim it. The guard narrowing is specified
in I3.

## B6 — Selection-dependent fields are nullable (O-1)

`ProposerAdvisory.recommended_disposition`, `.requested_review_action` and
`.requested_review_destination_role_ref` are each nullable. When
`selected_candidate_id is None` all three must be `None`. When a selected candidate
becomes permitted at a later stage, all three must bind consistently to that candidate,
its disposition and its permitted review routing. Under B3, S1 has no selected
candidate, so in S1 all three are always `None`.

## B7 — `advisory_version`

Required, non-null, identity-participating `str` matching `^[1-9][0-9]*$`. Initial
value `"1"`. `build_advisory_revision` increments it as canonical positive decimal
without leading zeroes. It is not `int`, because A1 forbids that; it is not
`Literal["1"]`, because that would make a revision unconstructible.

`kind = "ugence.agentic_proposer.advisory.v0"` remains a **separate axis**: `kind`
identifies the schema family, `advisory_version` identifies the advisory instance
revision. They are not redundant and not inconsistent.

## B8 — `ReviewAction`

Exactly `ROUTE_APPROVAL_BUNDLE` and `CREATE_EXCEPTION_REVIEW_BUNDLE`.

## B9 — Identifier profile (O-4)

Identifier and reference fields match `^[A-Za-z0-9][A-Za-z0-9._:/-]*$`. This applies
**only** to identifiers and references — never to `purpose`, `claim_summaries`,
`assumptions`, `uncertainties`, `declared_strategy` or any other human-readable text.

The ASCII restriction is **identity-load-bearing**: the frozen `P_unsigned` profile has
empty `nfc_paths` (C6), so the identity function performs no Unicode normalisation.
Restricting identifiers to characters with no alternative NFC spelling removes the only
route by which two visually identical advisories could carry different digests through
an identifier.

## B10 — Structural, not lexical, mandate security

`WorkMandate` security is structural. No implementation may scan `purpose` — or any
other free-text field — for substrings such as `token`, `secret`, `credential` or any
successor word list. Such a scan is defeated by spelling and simultaneously rejects
lawful prose. Authority-bearing content is excluded by `extra="forbid"` plus the D7
barred field set, so an undeclared authority-bearing field cannot be carried at all.
`purpose` is free text with no authority: nothing downstream may read a permission, a
scope, a decision or an instruction out of it.

---

# Part C — Cross-cutting model rules

## C1 — Model configuration

Every contract and nested model is a `pydantic` v2 `BaseModel` declared with:

```python
model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
```

`frozen=True` gives structural immutability; `extra="forbid"` is the structural
prohibition B10 depends on; `strict=True` stops silent coercion from changing an
identity-bearing value. `[V]` `strict=True` is carried forward from the PR #1475 draft,
which was right to add it.

## C2 — Common fields

Every one of the **eight top-level contracts** carries:

| Field | Type | Required | Nullable | Default | Validation |
| --- | --- | --- | --- | --- | --- |
| `schema_version` | `Literal["1.0"]` | yes | no | `"1.0"` | literal equality |
| `tenant_id` | `str` | yes | no | none | C5 |
| `created_at` | `datetime` | yes | no | none | C4; caller-supplied |

`[I]` `CandidateAdvisory` does **not** carry them. It is a nested public shape, not a
ninth contract: its tenant and case scope are those of the `AdvisoryCandidateSet` that
contains it, and a second `created_at` alongside `evaluated_at` would be two timestamps
for one act with no rule distinguishing them.

## C3 — No numeric field

No field of any contract or nested model is `int`, `float`, `Decimal` or any numeric
type, at any depth, including inside a container. Forced by A1.

A magnitude, if a later stage needs one, is carried as a typed decimal **string** and
its encoding is ratified then. Note that `Decimal` is not an escape: it raises
`UnsupportedTypeError`, a different fault from `BareNumberError` but equally fatal.

## C4 — Timestamps

Every `datetime` field is **caller-supplied**. No `src` module may read a wall clock:
`datetime.now`, `datetime.utcnow`, `time.time` and `time.monotonic` appear nowhere, and
no field defaults to a computed current time.

Each `datetime` is:

* **required to be timezone-aware.** A naive value is rejected by an explicit
  `@field_validator`, with no default-timezone assumption. `[V]` A9: `strict=True` does
  not reject naive datetimes, so the validator is required, not decorative.
* **normalised to UTC at validation** with `value.astimezone(timezone.utc)`. Two inputs
  naming the same instant in different offsets therefore produce the same stored value
  and the same digest.
* **serialised at full microsecond precision with a trailing `Z`** by an explicit
  `@field_serializer`:

  ```python
  value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
  ```

`[V]` A9 records that pydantic 2.13.4 already emits `Z` for a UTC-aware value. The
serializer exists to pin that spelling against library drift and to make the identity
text explicit, not because pydantic emits `+00:00`. The PR #1475 draft asserted the
latter; it is false.

**No truncation.** The PR #1475 draft truncated to milliseconds at serialisation. That
is rejected: ordering validations compare full-precision values while identity would
carry a truncated one, so two advisories a hundred microseconds apart would be distinct
objects sharing a digest. The stored value and the serialised value must agree exactly.

## C5 — Identifier and reference format

Every identifier or reference field is `str` matching
`^[A-Za-z0-9][A-Za-z0-9._:/-]*$`, per B9. Free-text fields are **not** subject to it;
each such field's own constraint is given in its contract table.

## C6 — Digest-shaped fields, and the frozen canonicalisation profile

Every digest-shaped field — `advisory_digest`, `parent_advisory_digest`,
`context_hash`, `content_hash` — is `str` matching `^sha256:[0-9a-f]{64}$`. Uppercase
hexadecimal is rejected rather than lowercased: accepting both spellings would let one
content have two identity strings.

The canonicalisation profile is frozen as:

```text
set_paths = frozenset()
nfc_paths = frozenset()
```

Ratified consequences:

* RFC 8785 / Action-Profile behaviour with **no extra path semantics**.
* **List ordering is identity-significant.** No array in `P_unsigned` is a set;
  reordering any list changes the digest. Semantic sorting a producer wants must happen
  **before** construction, never inside the identity function.
* **Unicode is not normalised by the identity function.** Validation may reject
  non-NFC text; the identity function will not rewrite it. B9 exists because of this.
* All validation occurs before canonicalisation. The canonicaliser decides nothing.
* `parent_advisory_digest` participates in identity **including when it is `null`**,
  because `exclude_none=False` retains it.

## C7 — Domain completion is structurally unconstructible

`DomainCheckCompletion` is exactly `NOT_EVALUATED` and `COMPLETE`.

`CandidateAdvisory` carries an explicit validator that **rejects `COMPLETE`
unconditionally**, raising a validation error. This is not a builder omission and not
an unexercised code path: the value is unconstructible on every path, including
`model_construct` followed by validation, and including direct construction by any
caller who can import the name.

`COMPLETE` is defined now so that the enum is closed and Equation 2 is total, and so
that adding a domain evaluator later is not a vocabulary change. It becomes
constructible only through a separately ratified S2 domain-evaluator boundary, which
must remove this validator as an explicit, reviewed act.

---

# Part D — Contracts

Eight top-level contracts. `CandidateAdvisory` and `ProposerProcessStateTransition` are
nested public shapes, exported for typing, never transported alone.

For every field: name, type, requiredness, nullability, default, cardinality, closed
vocabulary, validation, ownership, and whether it participates in the canonical
advisory identity. **"Identity: yes" means the field is reachable from
`ProposerAdvisory` and is therefore covered by `advisory_digest`.**

Every contract also carries the C2 common fields; they are not repeated in each table.
`schema_version` and `tenant_id` on `ProposerAdvisory` participate in identity;
`created_at` on `ProposerAdvisory` participates in identity. The same fields on the
other seven contracts do **not**, because those contracts are not reachable from
`ProposerAdvisory` — see D9.

## D1 — `AgentIdentityRef`

D3: the proposer mints no agent identity. Every field is an externally issued fact. No
lifecycle field is computed here and no lifecycle verb is exposed.

| Field | Type | Required | Nullable | Default | Cardinality | Vocabulary | Validation | Ownership | Identity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `agent_id` | `str` | yes | no | none | 1 | open | C5 | external identity issuer | no |
| `agent_version` | `str` | yes | no | none | 1 | open | C5 | external identity issuer | no |
| `lifecycle_state` | `AgentLifecycleState` | yes | no | none | 1 | **closed**: `ACTIVE`, `INACTIVE`, `SUSPENDED`, `REVOKED` | enum membership; an unrecognised value fails validation and coerces to no member | external identity issuer | no |
| `bound_role_contract_id` | `str` | yes | no | none | 1 | open | C5 | external identity issuer | no |
| `owner_role_ref` | `str` | yes | no | none | 1 | open | C5 | external identity issuer | no |

`bound_role_contract_id` is the binding Equation 1's `RoleMatch` reads. This package
validates it and never sets or changes it.

## D2 — `CognitiveRoleContract`

D1 and D8: a proposer-local **v0** projection, never re-exported to any shared contract
package, carrying no constitution-derived attribute, exposing no role lifecycle verb.

| Field | Type | Required | Nullable | Default | Cardinality | Vocabulary | Validation | Ownership | Identity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `role_contract_id` | `str` | yes | no | none | 1 | open | C5 | external role owner | no |
| `primary_function` | `str` | yes | no | none | 1 | open | non-empty; **opaque** — compared for equality only, never semantically interpreted | external role owner | no |
| `permitted_tool_scopes` | `list[str]` | yes | no | `[]` | 0..n | open | each C5; order preserved | external role owner | no |
| `permitted_candidate_dispositions` | `list[CandidateDisposition]` | yes | no | none | 1..4 | **closed, D4** | enum membership; **rejects an empty list**; no duplicates | external role owner | no |
| `permitted_review_actions` | `list[ReviewAction]` | yes | no | none | 1..n | **closed, B8** | enum membership; **rejects an empty list**; no duplicates | external role owner | no |
| `escalation_role_ref` | `str` | yes | no | none | 1 | open | C5 | external role owner | no |
| `activation_status` | `RoleActivationStatus` | yes | no | none | 1 | **closed**: `ACTIVE`, `INACTIVE` | enum membership | external role owner — **input fact, never computed** (D1) | no |

`CandidateDisposition` is imported unchanged from
`src/ugence_agentic_proposer/vocabulary.py`; it is not redefined.

`[V]` D8's export bound is not a field property. It is enforced by
`tests/test_role_projection_bounds.py`, which scans every shared-contract package in
this repository for `CognitiveRole`, `COGNITIVE_ROLE` and `cognitive_role`. No name
containing those substrings may be re-exported outside this package.

## D3 — `WorkMandate`

| Field | Type | Required | Nullable | Default | Cardinality | Vocabulary | Validation | Ownership | Identity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `mandate_id` | `str` | yes | no | none | 1 | open | C5 | mandate issuer | no |
| `case_ref` | `str` | yes | no | none | 1 | open | C5; **domain-neutral** | mandate issuer | no |
| `assigned_role_contract_id` | `str` | yes | no | none | 1 | open | C5 | mandate issuer | no |
| `purpose` | `str` | yes | no | none | 1 | open | non-empty; length ≤ 4000; NFC required; **no content scanning** (B10) | mandate issuer — **non-authoritative** | no |
| `allowed_source_scopes` | `list[str]` | yes | no | none | 1..n | open | each C5; rejects an empty list; no duplicates | mandate issuer | no |
| `expires_at` | `datetime` | yes | no | none | 1 | — | C4 | mandate issuer | no |

`case_ref` is domain-neutral: it is neither named nor documented as invoice-specific.

## D4 — `BoundedContextEnvelope`

| Field | Type | Required | Nullable | Default | Cardinality | Vocabulary | Validation | Ownership | Identity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `context_id` | `str` | yes | no | none | 1 | open | C5 | context assembler | no |
| `mandate_id` | `str` | yes | no | none | 1 | open | C5; must reference `WorkMandate.mandate_id` | context assembler | no |
| `allowed_record_refs` | `list[str]` | yes | no | `[]` | 0..n | open | each C5; order preserved | context assembler | no |
| `excluded_data_classes` | `list[str]` | yes | no | `[]` | 0..n | open | each C5 | context assembler | no |
| `context_hash` | `str` | yes | no | none | 1 | open | C6 **format only** | **context assembler** | no |
| `expires_at` | `datetime` | yes | no | none | 1 | — | C4 | context assembler | no |

**`context_hash` is externally supplied.** S1 validates its *format* and does nothing
else with it. S1 does not compute it, does not recompute it and does not verify it
against any content — doing so would require hashing locally, which D2 bars.

## D5 — `ToolObservation`

| Field | Type | Required | Nullable | Default | Cardinality | Vocabulary | Validation | Ownership | Identity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `observation_id` | `str` | yes | no | none | 1 | open | C5 | observation producer | no |
| `case_ref` | `str` | yes | no | none | 1 | open | C5 | observation producer | no |
| `tool_name` | `str` | yes | no | none | 1 | open | C5 | observation producer | no |
| `operation_class` | `ToolOperationClass` | yes | no | none | 1 | **closed**: `READ_ONLY` | enum membership | observation producer | no |
| `source_ref` | `str` | yes | no | none | 1 | open | C5 | observation producer | no |
| `observed_at` | `datetime` | yes | no | none | 1 | — | C4 | observation producer | no |
| `content_hash` | `str` | yes | no | none | 1 | open | C6 **format only** | **observation producer** | no |
| `normalized_fields` | `dict[str, str]` | yes | no | `{}` | 0..n keys | open | keys C5; **values `str`** | observation producer | no |
| `admission_status` | `ToolObservationAdmissionStatus` | yes | no | `NOT_EVALUATED` | 1 | **closed**: `NOT_EVALUATED` | enum membership | this package | no |

**`normalized_fields` values are `str`, not `Any`.** `[V]` A1: an `Any`-valued mapping
admits `int` and `float`, which raise `BareNumberError`, and `Decimal`, which raises
`UnsupportedTypeError`. Constraining the value type at declaration is what makes the
constraint checkable at validation rather than at canonicalisation. No code path in
this package constructs any `admission_status` other than `NOT_EVALUATED`.

## D6 — `AdvisoryCandidateSet`

A top-level contract. It is **not** nested in `ProposerAdvisory`; the advisory
references it by `candidate_set_id`.

| Field | Type | Required | Nullable | Default | Cardinality | Vocabulary | Validation | Ownership | Identity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `candidate_set_id` | `str` | yes | no | none | 1 | open | C5 | this package | no |
| `case_ref` | `str` | yes | no | none | 1 | open | C5 | this package | no |
| `candidates` | `list[CandidateAdvisory]` | yes | no | none | 1..n | — | **rejects an empty list**; `candidate_id` unique across the list; order preserved | this package | no |
| `selected_candidate_id` | `str \| None` | yes (explicit) | yes | `None` | 0..1 | open | C5 when non-null; S-1 and S-2 below | this package | no |
| `selection_reason_codes` | `list[str]` | yes | no | `[]` | 0..n | — | **rejects any non-empty value** | this package | no |

**Locally decidable selection invariants**, both decidable from this contract alone:

* **S-1 — resolution.** If `selected_candidate_id` is not `None`, exactly one element of
  `candidates` has that `candidate_id`.
* **S-2 — eligibility of the selection.** If `selected_candidate_id` is not `None`, the
  resolved candidate has `is_eligible is True`.

`selection_reason_codes` rejects any non-empty value: the reason-code catalogue is out
of scope at this stage, and an unvalidated free-form code list would become a de facto
vocabulary before one is ratified.

`[I]` The converse of S-1 — "if any candidate is eligible, one must be selected" — is
**not** an invariant. Declining to select among eligible candidates is `ABSTAIN`, which
D4 ratifies. Forcing selection would convert an abstention into a recommendation.

**Under B3, `selected_candidate_id` is `None` for every advisory S1 can construct**, so
S-1 and S-2 are satisfied vacuously in S1 and become load-bearing at S2.

### `CandidateAdvisory` — nested public shape

| Field | Type | Required | Nullable | Default | Cardinality | Vocabulary | Validation | Ownership | Identity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `candidate_id` | `str` | yes | no | none | 1 | open | C5; unique within its set | this package | no |
| `disposition` | `CandidateDisposition` | yes | no | none | 1 | **closed, D4**: `RECOMMEND_MATCHED_FOR_APPROVAL`, `RECOMMEND_WITHHOLD`, `REQUEST_EVIDENCE`, `ESCALATE_EXCEPTION` | enum membership | this package | no |
| `requested_review_action` | `ReviewAction` | yes | no | none | 1 | **closed, B8** | enum membership | this package | no |
| `is_eligible` | `bool` | yes | no | none | 1 | closed: `true`, `false` | **package-computed** — see Part G | this package | no |
| `domain_check_completion` | `DomainCheckCompletion` | yes | no | `NOT_EVALUATED` | 1 | **closed**: `NOT_EVALUATED`, `COMPLETE` | enum membership; **`COMPLETE` rejected unconditionally** (C7) | this package | no |
| `evaluated_at` | `datetime` | yes | no | none | 1 | — | C4 | caller-supplied, package-recorded | no |
| `claim_refs` | `list[str]` | yes | no | `[]` | 0..n | open | each C5 | this package | no |
| `observation_refs` | `list[str]` | yes | no | `[]` | 0..n | open | each C5; no duplicates; every entry must reference a supplied `ToolObservation.observation_id` | this package | no |
| `assumptions` | `list[str]` | yes | no | `[]` | 0..n | open | free text; no C5 | this package | no |
| `uncertainties` | `list[str]` | yes | no | `[]` | 0..n | open | free text; no C5 | this package | no |

`requested_review_action` is the candidate's **own** proposed routing. Equation 1's
`OutputPermitted` evaluates it together with `disposition` against the role's
allowlists.

`evaluated_at` is stored, not merely passed. `[I]` Equation 1 reads `evaluated_at` in
its expiry terms, so an independent verifier that recomputes eligibility from stored
content cannot do so without it. Storing it is forced by B2, not a convenience.

`[V]` No field of `CandidateAdvisory` or `ProposerAdvisory` is typed
`SemanticAuditorFindingStatus`, and none may be assigned one: D6's standing rule is
enforced by `tests/test_no_auditor_status_projection.py`.

## D7 — `ProposerAdvisory`

D7: kind `ugence.agentic_proposer.advisory.v0`; `advisory_digest` is the **sole**
identity field; identity is computed only through `ugence_jcs`; the eight barred fields
(`fingerprint`, `provider_id`, `operation`, `arguments`, `idempotency_key`,
`workflow_id`, `instance_id`, `task_id`) appear at no nesting depth; no exported name
begins with `Proposal` or `Recommendation`.

**This contract references its inputs by identifier.** It nests no other contract. `[V]`
A3: nesting `ToolObservation` makes `content_hash` reachable and fails a merged guard.

| Field | Type | Required | Nullable | Default | Cardinality | Vocabulary | Validation | Ownership | Identity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `kind` | `Literal["ugence.agentic_proposer.advisory.v0"]` | yes | no | that literal | 1 | closed, D7 | literal equality | this package | yes |
| `advisory_version` | `str` | yes | no | `"1"` | 1 | open | `^[1-9][0-9]*$` (B7) | this package | yes |
| `advisory_digest` | `str` | yes | **no** | none | 1 | open | C6; equals Equation 3 over `P_unsigned` | this package | **excluded from `P_unsigned`** |
| `parent_advisory_digest` | `str \| None` | yes (explicit) | yes | `None` | 0..1 | open | C6 when non-null; L-1 | this package | **yes, including when `null`** |
| `case_ref` | `str` | yes | no | none | 1 | open | C5 | this package | yes |
| `agent_id` | `str` | yes | no | none | 1 | open | C5; references `AgentIdentityRef.agent_id` | this package | yes |
| `role_contract_id` | `str` | yes | no | none | 1 | open | C5; references `CognitiveRoleContract.role_contract_id` | this package | yes |
| `mandate_id` | `str` | yes | no | none | 1 | open | C5; references `WorkMandate.mandate_id` | this package | yes |
| `context_id` | `str` | yes | no | none | 1 | open | C5; references `BoundedContextEnvelope.context_id` | this package | yes |
| `candidate_set_id` | `str` | yes | no | none | 1 | open | C5; references `AdvisoryCandidateSet.candidate_set_id` | this package | yes |
| `recommended_disposition` | `CandidateDisposition \| None` | yes (explicit) | yes | `None` | 0..1 | closed, D4 | R-1 (B6) | this package | yes |
| `requested_review_action` | `ReviewAction \| None` | yes (explicit) | yes | `None` | 0..1 | closed, B8 | R-1 (B6) | this package | yes |
| `requested_review_destination_role_ref` | `str \| None` | yes (explicit) | yes | `None` | 0..1 | open | C5 when non-null; R-1 (B6) | this package | yes |
| `claim_summaries` | `list[str]` | yes | no | `[]` | 0..n | open | free text; no C5 | this package | yes |
| `observation_refs` | `list[str]` | yes | no | `[]` | 0..n | open | each C5; no duplicates | this package | yes |
| `uncertainties` | `list[str]` | yes | no | `[]` | 0..n | open | free text; no C5 | this package | yes |
| `reason_codes` | `list[str]` | yes | no | `[]` | 0..n | — | **rejects any non-empty value** | this package | yes |
| `expires_at` | `datetime` | yes | no | none | 1 | — | C4 | this package | yes |

There is **no** `advisory_id`. D7 makes `advisory_digest` the only identity field, and a
second identifier would create a second, unverifiable identity. `[V]` A3: no field on
this contract, and none reachable from `CandidateAdvisory`, is named `id`, `uid`,
`uuid`, `identity`, `identifier`, `hash`, `checksum`, `content_hash`, `advisory_id` or
`proposal_digest`.

`requested_review_destination_role_ref` is an opaque role reference. It is deliberately
not named `operation`, `fingerprint`, `provider_id`, `arguments`, `idempotency_key`,
`workflow_id`, `instance_id` or `task_id`, each of which would bind the advisory to an
execution the proposer does not authorise.

`terminal_outcome` is **not** a field of `ProposerAdvisory`. It is recorded on
`ProposerProcessRecord` (D8), which is the audit artifact, and it is constrained there
by R-2. `[I]` Placing it on the advisory would put the proposer's conclusion into the
identity-bearing artifact as a caller-supplied value; placing it on the process record
keeps the advisory a statement of *what was found* and the record a statement of *how
the run ended*.

## D8 — `ProposerProcessRecord`

A non-identity-bearing audit record. It is **not** referenced by `ProposerAdvisory` and
is not reachable from `P_unsigned`, so nothing in it can alter an advisory identity.

| Field | Type | Required | Nullable | Default | Cardinality | Vocabulary | Validation | Ownership | Identity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `process_record_id` | `str` | yes | no | none | 1 | open | C5 | this package | no |
| `case_ref` | `str` | yes | no | none | 1 | open | C5 | this package | no |
| `declared_strategy` | `str` | yes | no | none | 1 | open | non-empty; **opaque, not an enum** | this package | no |
| `state_transitions` | `list[ProposerProcessStateTransition]` | yes | no | `[]` | 0..n | — | R-3 | this package | no |
| `tool_invocations` | `list[str]` | yes | no | `[]` | 0..n | open | each C5 | this package | no |
| `deterministic_checks` | `list[str]` | yes | no | `[]` | 0..n | — | **rejects any non-empty value** | this package | no |
| `candidate_ids` | `list[str]` | yes | no | `[]` | 0..n | open | each C5; no duplicates | this package | no |
| `selected_candidate_id` | `str \| None` | yes (explicit) | yes | `None` | 0..1 | open | C5 when non-null | this package | no |
| `semantic_audit_refs` | `list[str]` | yes | no | `[]` | 0..n | — | **rejects any non-empty value** | this package | no |
| `terminal_outcome` | `TerminalOutcome` | yes | no | none | 1 | **closed, D4**: `PROPOSAL`, `NEED_EVIDENCE`, `ABSTAIN`, `ESCALATE` | enum membership; R-2 | this package | no |
| `reason_codes` | `list[str]` | yes | no | `[]` | 0..n | — | **rejects any non-empty value** | this package | no |
| `advisory_digest` | `str` | yes | no | none | 1 | open | C6 | this package | no |
| `jcs_distribution_version` | `str` | yes | no | none | 1 | open | `^[0-9]+\.[0-9]+\.[0-9]+$` | resolved from the installed distribution | no |
| `started_at` | `datetime` | yes | no | none | 1 | — | C4 | this package | no |
| `completed_at` | `datetime` | yes | no | none | 1 | — | C4; `completed_at >= started_at` | this package | no |

`TerminalOutcome` is imported unchanged from `vocabulary.py`.

`advisory_digest` here **references** `ProposerAdvisory.advisory_digest`; it is a
foreign key, not a second identity. It is not reachable from either advisory type, so
A3's rival-identity walk does not see it.

`jcs_distribution_version` is read from the **installed distribution metadata**, not
from `pyproject.toml` text, so a process record states which substrate actually ran.
`[V]` Carried forward from the PR #1475 draft, which was right that the declared-floor
text check is the weaker of the two available assertions.

### `ProposerProcessStateTransition` — nested public shape

| Field | Type | Required | Nullable | Default | Validation |
| --- | --- | --- | --- | --- | --- |
| `state` | `ProposerProcessState` | yes | no | none | enum membership |
| `at` | `datetime` | yes | no | none | C4; caller-supplied |

## D9 — Identity scope, stated once

`P_unsigned` covers `ProposerAdvisory` and nothing else. The other seven contracts and
`CandidateAdvisory` are **inputs to** and **referents of** an advisory; they are not
inside its identity.

`[I]` This is the direct consequence of A3 and it has a real cost, stated plainly: an
advisory's digest binds the *identifiers* of its inputs, not their *contents*. Two
different `WorkMandate` bodies carrying the same `mandate_id` yield the same advisory
digest. Closing that would require either nesting the contracts — which A3 forbids — or
an input-digest field, which would be a second identity and which D7 forbids. It is
recorded in Part K as a residual limitation, not solved here.

---

# Part E — Cross-contract validations

Each is a validation S1 must implement at construction. Those marked *(equation term)*
also appear in Equation 1; they are listed here once as contract obligations.

| Id | Rule | Prevents |
| --- | --- | --- |
| R-1 | **Selection binding (B6).** When `selected_candidate_id is None`, `recommended_disposition`, `requested_review_action` and `requested_review_destination_role_ref` are all `None`. When it is not `None`, all three are non-null, `recommended_disposition` equals the resolved candidate's `disposition`, `requested_review_action` equals the resolved candidate's `requested_review_action`, and that action is a member of `CognitiveRoleContract.permitted_review_actions` | an advisory whose routing contradicts, or invents, the candidate it selects |
| R-2 | **V13 (B3).** `terminal_outcome is TerminalOutcome.PROPOSAL` **if and only if** `selected_candidate_id is not None` **and** `evaluate_readiness(...) is True` for the resolved candidate, recomputed at construction | a "proposal" that proposes nothing, a selection presented as an abstention, and a proposal made without domain readiness |
| R-3 | **Process ordering.** `state_transitions` is a subsequence of `RECEIVED → VALIDATED → OBSERVING → RECONCILING → EVALUATING → {PROPOSAL, NEED_EVIDENCE, ABSTAIN, ESCALATE}`: no backward transition, no repeat, at most one terminal state and only in final position, and `at` non-decreasing across the list | a fabricated or reordered process history, and — since no execution state exists in the enum — any representation of execution |
| R-4 | `terminal_outcome` on the process record equals the terminal `ProposerProcessState` when one is present in `state_transitions` | a record whose narrative and outcome disagree |
| R-5 | **Tenant scope.** `tenant_id` is identical across `AgentIdentityRef`, `CognitiveRoleContract`, `WorkMandate`, `BoundedContextEnvelope`, `AdvisoryCandidateSet`, `ProposerAdvisory` and **every** `ToolObservation` supplied to a builder | **cross-tenant acceptance** |
| R-6 | **Case scope.** `case_ref` is identical across `WorkMandate`, `AdvisoryCandidateSet`, `ProposerAdvisory` and **every** `ToolObservation` supplied to a builder | **cross-case acceptance** |
| R-7 | **Reference resolution.** Every `observation_refs` entry on a candidate and on the advisory resolves to a supplied `ToolObservation.observation_id` | a reference to evidence that was never supplied |
| R-8 | **Uniqueness.** `observation_id` unique across supplied observations; `candidate_id` unique across `candidates`; no duplicates in `observation_refs`, `candidate_ids`, `permitted_tool_scopes`, `permitted_candidate_dispositions`, `permitted_review_actions` or `allowed_source_scopes` | an identifier resolving ambiguously to two objects, and a list that overstates its breadth |
| R-9 | **Envelope binding.** `BoundedContextEnvelope.mandate_id == WorkMandate.mandate_id` *(equation term)* | an envelope assembled for a different mandate |
| R-10 | **Role binding.** `WorkMandate.assigned_role_contract_id == AgentIdentityRef.bound_role_contract_id == CognitiveRoleContract.role_contract_id` *(equation term)* | a mandate matched against an unrelated role or agent |
| L-1 | **Lineage.** `parent_advisory_digest`, when non-null, is C6-shaped and is **not equal to** this advisory's own `advisory_digest` | an immediate self-referential lineage cycle |

`[I]` R-5 and R-6 are **contract validators, not Equation 1 terms.** The owner's
Equation 1 checks tenant equality across the four principal contracts and does not
reach the observations. Rejecting a cross-tenant or cross-case observation at
construction closes that without altering the ratified equation.

---

# Part F — Equations

All are pure, deterministic, total functions. None reads a clock, a file, an
environment variable, a network or a random source. All parameters are keyword-only.

Every equation returns an **actual `bool`**. Each is written as `all((...))` rather than
chained `and`: chained `and` returns the **last operand**, so `x and y` where `y` is a
non-empty `str` returns that string, and a function annotated `-> bool` would then
return a truthy non-Boolean that a caller comparing `is True` would silently see as a
mismatch. `all()` returns a real `bool` for every input. Tests assert `is True` and
`is False` — identity against the singletons, not truthiness.

## Equation 1 — `evaluate_eligibility`

```python
def evaluate_eligibility(
    *,
    identity: AgentIdentityRef,
    role: CognitiveRoleContract,
    mandate: WorkMandate,
    context: BoundedContextEnvelope,
    observations: list[ToolObservation],
    disposition: CandidateDisposition,
    requested_review_action: ReviewAction,
    referenced_observation_ids: list[str],
    evaluated_at: datetime,
) -> bool:
```

`evaluated_at` is an **explicit, timezone-aware** parameter and is the **only** time
source for every comparison inside this function.

Let `referenced = [o for o in observations if o.observation_id in set(referenced_observation_ids)]`.

| Term | Definition |
| --- | --- |
| `IdentityActive` | `identity.lifecycle_state is AgentLifecycleState.ACTIVE` |
| `RoleMatch` | `mandate.assigned_role_contract_id == identity.bound_role_contract_id == role.role_contract_id` **and** `role.activation_status is RoleActivationStatus.ACTIVE` |
| `MandateValid` | `identity.tenant_id == mandate.tenant_id == role.tenant_id == context.tenant_id` **and** `mandate.expires_at > evaluated_at` **and** `bool(mandate.case_ref)` **and** `bool(mandate.purpose)` |
| `ContextAllowed` | `context.mandate_id == mandate.mandate_id` **and** `context.expires_at > evaluated_at` **and** `all(o.source_ref in context.allowed_record_refs for o in referenced)` |
| `ToolsAllowed` | `all(o.tool_name in role.permitted_tool_scopes and o.operation_class is ToolOperationClass.READ_ONLY for o in referenced)` |
| `OutputPermitted` | `disposition in role.permitted_candidate_dispositions` **and** `requested_review_action in role.permitted_review_actions` |

```python
return all((IdentityActive, RoleMatch, MandateValid,
            ContextAllowed, ToolsAllowed, OutputPermitted))
```

**No term compensates for another.** `bool(...)` is applied to the two string presence
checks in `MandateValid` so that the term is a Boolean and not a string.

`domain_check_completion` is **not** a term. Eligibility and domain completion are
independent; conflating them would make every S1 candidate ineligible and erase the
distinction Equation 2 exists to draw.

`[I]` **Vacuity, stated rather than removed.** `observation_refs` has cardinality 0..n
per D6, so `ContextAllowed`'s and `ToolsAllowed`'s universal quantifications pass
trivially when a candidate references no observation. This is the owner's specified
cardinality and is not overridden here. Where it bites is Equation 2's
`ObservationRefsPresent`, which requires at least one reference for a
`RECOMMEND_MATCHED_FOR_APPROVAL` candidate. Recorded in Part K.

## Equation 2 — `evaluate_readiness`

```python
def evaluate_readiness(
    *,
    candidate: CandidateAdvisory,
    identity: AgentIdentityRef,
    role: CognitiveRoleContract,
    mandate: WorkMandate,
    context: BoundedContextEnvelope,
) -> bool:
```

| Term | Definition |
| --- | --- |
| `Eligible` | `candidate.is_eligible is True` |
| `RequiredFieldsPresent` | `True` — guaranteed by successful pydantic construction of `candidate` |
| `ObservationRefsPresent` | `len(candidate.observation_refs) > 0` if `candidate.disposition is CandidateDisposition.RECOMMEND_MATCHED_FOR_APPROVAL` else `True` |
| `UncertaintyDisclosed` | `candidate.uncertainties is not None` — structural only at this stage |
| `LineageComplete` | `identity.bound_role_contract_id == role.role_contract_id == mandate.assigned_role_contract_id` **and** `context.mandate_id == mandate.mandate_id` |
| `DomainChecksComplete` | `candidate.domain_check_completion is DomainCheckCompletion.COMPLETE` |

```python
return all((Eligible, RequiredFieldsPresent, ObservationRefsPresent,
            UncertaintyDisclosed, LineageComplete, DomainChecksComplete))
```

**This returns `False` for every candidate this package can construct**, because C7
makes `COMPLETE` unconstructible. That is intended and fail-closed pending a separately
ratified S2 domain evaluator. It is what makes B3 bite.

## Equation 3 — advisory identity

Specified in Part G, because its correctness is a construction-shape property and not
only a formula.

## Equation 4 — `verify_advisory_identity`

The independent verification function B2 requires.

```python
def verify_advisory_identity(*, advisory: ProposerAdvisory) -> bool:
    return compute_advisory_identity(advisory=advisory) == advisory.advisory_digest
```

It recomputes from stored content only; it consults no cache, no memo and no side
table. `==` between two `str` values returns an actual `bool`. `[V]` A8: `hmac` is a
forbidden import, and plain equality is correct here because both operands are public,
non-secret digests.

---

# Part G — Identity construction, eligibility, and verification

## G1 — The frozen projection

`P_unsigned` is **exactly** the JSON-mode projection of the complete `ProposerAdvisory`
with only `advisory_digest` omitted and every other nullable field retained:

```python
advisory.model_dump(
    mode="json",
    exclude={"advisory_digest"},
    exclude_none=False,
)
```

under the C6 profile. `[V]` A9 confirms this excludes only the top-level field and
retains `parent_advisory_digest: null`.

## G2 — The only permitted construction shape

`[V]` A5 forbids both a null-digest draft and a locally-named digest function passed
into the `advisory_digest=` keyword. The construction is therefore:

1. `build_proposer_advisory` validates its inputs and constructs a **private**
   `_UnsignedAdvisoryPayload` — not exported — declaring exactly the fields of
   `ProposerAdvisory` **except** `advisory_digest`, with identical types, defaults,
   validators and serializers.
2. It computes `p_unsigned = payload.model_dump(mode="json", exclude_none=False)`.
3. It constructs and returns the advisory in **one expression**, with the substrate
   call inline in the `advisory_digest` keyword:

   ```python
   return ProposerAdvisory(
       **p_unsigned,
       advisory_digest="sha256:" + ugence_jcs.canonical_sha256_hex(
           p_unsigned, set_paths=frozenset(), nfc_paths=frozenset()),
   )
   ```

There is no in-place mutation path and no setter: the model is frozen.

An unsigned `ProposerAdvisory` is **not a public-valid state**. `advisory_digest` is
required and non-nullable, so no public factory can return an advisory without one, and
the unsigned representation never leaves the builder.

**Equivalence obligation.** A frozen-profile test asserts, over a fixed corpus, that
`payload.model_dump(mode="json", exclude_none=False)` equals the G1 expression
evaluated on the resulting `ProposerAdvisory`, and that both canonicalise to identical
bytes. Without that test the private payload could drift from the public contract and
produce a digest no independent verifier could reproduce — precisely the D2 failure.

`compute_advisory_identity` holds the same body over G1's expression and is what
Equation 4 calls. `[V]` It is not scanned by A5's rule, which sees assignments and
keywords named `advisory_digest`, not returns; the two call sites are pinned equal by
the equivalence test.

No other digest, no domain tag, no length prefix, no salt and no envelope is
introduced. No second identity function exists.

**Canonicalisation faults propagate unchanged.** `BareNumberError`,
`NonFiniteNumberError`, `NonNFCError`, `DuplicateSetElementError` and
`UnsupportedTypeError` are not caught: a payload that cannot be canonicalised has no
identity, and substituting a fallback would be a second identity function.

## G3 — Revisions

`build_advisory_revision` sets `parent_advisory_digest = parent.advisory_digest`,
increments `advisory_version` per B7, and reuses the parent's `case_ref`, `tenant_id`,
`agent_id`, `role_contract_id`, `mandate_id` and `context_id` unchanged. A revision is a
new advisory with a new digest; nothing about the parent is mutated. The increment is
computed as canonical positive decimal without leading zeroes; any integer arithmetic
used to compute it is local to that function and never surfaces as a field, so C3 is
not weakened.

## G4 — Eligibility: what can and cannot be claimed

`CandidateAdvisory.is_eligible` is **package-computed**. A caller does not assert it.

**What cannot be claimed.** Exporting a pydantic model does not make its constructor
unreachable. `CandidateAdvisory(...)` remains callable by anyone who can import the
name, `model_construct` bypasses validation entirely, and no amount of ordinary field
validation authenticates a caller-supplied Boolean — a validator sees the value, not its
provenance. **Any claim that field validation alone secures `is_eligible` is false and
must not appear in S1 documentation, tests or commit messages.** `[V]` Carried forward
verbatim in substance from the PR #1475 draft, which was right about this.

**The enforceable boundary, precisely.**

1. **One authoritative builder.** `build_candidate_advisory` is the sole package-owned
   construction path. It takes no `is_eligible` and no `domain_check_completion`
   parameter, so there is no channel through which a caller can supply either. It
   computes Equation 1 and passes the computed Boolean **directly** as the
   `is_eligible=` keyword of the constructor call, in the same expression that computes
   it — not via an intermediate variable holding a caller-supplied or externally sourced
   value.
2. **Authority-facing verification recomputes.** Any consumer that acts on eligibility —
   and `build_proposer_advisory` itself — **must independently recompute Equation 1 from
   the advisory's own referenced contents and reject any candidate whose stored
   `is_eligible` differs from the recomputed value.** This is the operative guarantee.
   It holds regardless of how the object was constructed, including via
   `model_construct`.
3. **The recomputation is total.** `verify_candidate_eligibility` recomputes every
   candidate in a set. `build_proposer_advisory` calls it and raises
   `EligibilityMismatchError` before constructing if any candidate's stored value
   differs, so a forged candidate cannot reach a digest.

`[I]` This is the same shape as B2: the invariant is the guarantee, and the construction
path is defence-in-depth that does not by itself constitute proof.

---

# Part H — Public surface

## H1 — Function signatures

```python
def build_candidate_advisory(
    *,
    candidate_id: str,
    identity: AgentIdentityRef,
    role: CognitiveRoleContract,
    mandate: WorkMandate,
    context: BoundedContextEnvelope,
    observations: list[ToolObservation],
    disposition: CandidateDisposition,
    requested_review_action: ReviewAction,
    observation_refs: list[str],
    claim_refs: list[str],
    assumptions: list[str],
    uncertainties: list[str],
    evaluated_at: datetime,
) -> CandidateAdvisory: ...


def build_advisory_candidate_set(
    *,
    candidate_set_id: str,
    tenant_id: str,
    case_ref: str,
    created_at: datetime,
    candidates: list[CandidateAdvisory],
    selected_candidate_id: str | None,
) -> AdvisoryCandidateSet: ...


def build_proposer_advisory(
    *,
    tenant_id: str,
    case_ref: str,
    created_at: datetime,
    identity: AgentIdentityRef,
    role: CognitiveRoleContract,
    mandate: WorkMandate,
    context: BoundedContextEnvelope,
    observations: list[ToolObservation],
    candidate_set: AdvisoryCandidateSet,
    parent_advisory_digest: str | None,
    claim_summaries: list[str],
    observation_refs: list[str],
    uncertainties: list[str],
    expires_at: datetime,
) -> ProposerAdvisory: ...


def build_advisory_revision(
    *,
    parent: ProposerAdvisory,
    candidate_set: AdvisoryCandidateSet,
    identity: AgentIdentityRef,
    role: CognitiveRoleContract,
    mandate: WorkMandate,
    context: BoundedContextEnvelope,
    observations: list[ToolObservation],
    created_at: datetime,
    expires_at: datetime,
) -> ProposerAdvisory: ...


def build_proposer_process_record(
    *,
    process_record_id: str,
    tenant_id: str,
    case_ref: str,
    created_at: datetime,
    declared_strategy: str,
    state_transitions: list[ProposerProcessStateTransition],
    tool_invocations: list[str],
    candidate_ids: list[str],
    selected_candidate_id: str | None,
    terminal_outcome: TerminalOutcome,
    advisory_digest: str,
    started_at: datetime,
    completed_at: datetime,
) -> ProposerProcessRecord: ...


def evaluate_eligibility(...) -> bool: ...          # Part F, Equation 1
def evaluate_readiness(...) -> bool: ...            # Part F, Equation 2
def verify_candidate_eligibility(
    *,
    candidate_set: AdvisoryCandidateSet,
    identity: AgentIdentityRef,
    role: CognitiveRoleContract,
    mandate: WorkMandate,
    context: BoundedContextEnvelope,
    observations: list[ToolObservation],
) -> bool: ...
def compute_advisory_identity(*, advisory: ProposerAdvisory) -> str: ...
def verify_advisory_identity(*, advisory: ProposerAdvisory) -> bool: ...
```

Notes that are part of the ratified behaviour:

* `build_candidate_advisory` takes no `is_eligible` and no `domain_check_completion`.
  It computes the first and leaves the second at its `NOT_EVALUATED` default.
* `build_proposer_advisory` **derives** `recommended_disposition`,
  `requested_review_action` and `requested_review_destination_role_ref` from the
  candidate set under R-1 rather than accepting them, so the two cannot disagree. Under
  B3 it derives `None` for all three in S1. It calls `verify_candidate_eligibility` and
  raises `EligibilityMismatchError` before constructing if any candidate's stored
  `is_eligible` differs from the recomputation.
* `build_proposer_process_record` enforces R-2, R-3 and R-4. Under B3, a `PROPOSAL`
  terminal outcome is unreachable in S1 and the builder rejects it.
* `verify_candidate_eligibility` returns `False` — it does not raise — so a read-only
  auditor can inspect a stored set without exception handling. The **builder** raises;
  the **verifier** reports.

## H2 — Exception surface

Exactly three classes of failure, and no others:

| Failure | Type | Origin |
| --- | --- | --- |
| Contract violation — type, format, cardinality, closed vocabulary, any Part E validator | `pydantic.ValidationError` | pydantic |
| A stored `is_eligible` that does not match the recomputation | `EligibilityMismatchError` | **defined and exported by this package**, subclassing `ValueError` |
| Canonicalisation fault | `ugence_jcs.JcsError` and its subclasses, re-raised unchanged | `ugence-jcs` |

`EligibilityMismatchError` is the only exception this package defines. It exists because
a recomputation mismatch is not a field-validation failure and must not be reported as
one: the value is well-formed and the object is well-typed; what failed is provenance.

## H3 — Public-API snapshot

The complete exported surface S1 will declare. Recorded here as specification; **no
`public_api.json` is created by this document**, and none may exist until S1 is
implemented and separately authorised. When it is created it must cover every item
below.

**Contracts (8):** `AgentIdentityRef`, `CognitiveRoleContract`, `WorkMandate`,
`BoundedContextEnvelope`, `ToolObservation`, `AdvisoryCandidateSet`, `ProposerAdvisory`,
`ProposerProcessRecord`

**Nested public models (2):** `CandidateAdvisory`, `ProposerProcessStateTransition`

**Enums (10):** `TerminalOutcome`, `CandidateDisposition`, `SemanticAuditorFindingStatus`
(three existing, D4); `ReviewAction`, `DomainCheckCompletion`, `AgentLifecycleState`,
`RoleActivationStatus`, `ToolOperationClass`, `ToolObservationAdmissionStatus`,
`ProposerProcessState` (seven new)

**Builders (5):** `build_candidate_advisory`, `build_advisory_candidate_set`,
`build_proposer_advisory`, `build_advisory_revision`, `build_proposer_process_record`

**Equation functions (2):** `evaluate_eligibility`, `evaluate_readiness`

**Identity functions (2):** `compute_advisory_identity`, `verify_advisory_identity`

**Verifier (1):** `verify_candidate_eligibility`

**Exceptions (1):** `EligibilityMismatchError`

**Constants (4):** `RESERVED_AUTHORITY_VOCABULARY` (existing),
`ADVISORY_KIND = "ugence.agentic_proposer.advisory.v0"`,
`ADVISORY_IDENTITY_SET_PATHS = frozenset()`,
`ADVISORY_IDENTITY_NFC_PATHS = frozenset()`

**Metadata (1):** `__version__`

**Not exported:** `_UnsignedAdvisoryPayload`.

`[V]` No exported name begins with `Proposal` or `Recommendation`, as D7 requires.
`Proposer*` is not `Proposal*`; `recommended_disposition` is a field, not an exported
name; and `PROPOSAL` and `RECOMMEND_*` are enum values, which
`tests/test_advisory_contract_shape.py` records as out of the prefix rule's scope.

---

# Part I — Implementation obligations

These are obligations on the S1 implementation. **None of them is discharged by this
document**, which changes no test and no source file.

## I1 — D2 scan: a narrow, module-scoped exemption

`[V]` A7: the ratified `"sha256:"` prefix literal and the C6 pattern
`^sha256:[0-9a-f]{64}$` collide with `SUSPECT_TEXT`.

The resolution is a **module-path-scoped mask**, not a widened rule: the text mask for
exactly the two strings `"sha256:"` and `"^sha256:[0-9a-f]{64}$"` applies only within
the single authorised identity module, and nowhere else in `src` or `tests`.

It must not permit: an arbitrary `sha256:` literal in any other module; a local
`hashlib` import anywhere; a locally defined `canonical_*`; a shadowed or relative
`ugence_jcs`; or an identity computation from any module outside the authorised one.

**No definition-name exemption is required.** The identity functions are named
`compute_advisory_identity`, `verify_advisory_identity` and `verify_candidate_eligibility`;
none contains `"digest"`, `"canonical"`, `"canon"`, `"jcs"`, `"fingerprint"` or any other
`SUSPECT_DEF_SUBSTRINGS` member, so `SUSPECT_DEF_SUBSTRINGS` is left untouched. The
field name `advisory_digest` is an `AnnAssign` target, not a `FunctionDef` or
`ClassDef`, and is not scanned. **Test function names must not contain `"digest"`**, for
the same reason.

**Mutation tests required.** The exemption is accepted only with tests proving each of
these is still rejected: `"sha256:"` in a module other than the authorised one; the
authorised name defined at class scope; the authorised name defined without the
substrate call; the authorised module importing `hashlib`; and a locally defined
`canonical_sha256_hex`.

## I2 — Lifecycle-verb guard: narrow to callables (B4)

`tests/test_role_projection_bounds.py::test_no_source_name_is_a_role_lifecycle_verb`
must scan **callable names only**:

* every `FunctionDef` and `AsyncFunctionDef` name, at module and class scope;
* every `ClassDef` name that is **not** a `BaseModel` or `Enum` subclass;
* every name bound to a `lambda`.

Exempt from the verb scan: `AnnAssign` targets (contract fields), enum member
assignments, and `ClassDef` names of model and enum types. The `LIFECYCLE_VERBS` stem
list itself is **not** relaxed.

`[V]` Verified: under this rule the retained vocabulary `SUSPENDED`, `REVOKED`,
`RoleActivationStatus`, `activation_status`, `expires_at` yields `[]`, while
`activate`, `suspend_role`, `revoke_identity`, `expire_mandate`, `ActivateRole` and
`reactivate` all remain flagged.

**Mutation tests required**, asserting exactly that: those six rejected, those five
accepted. Without them the narrowing is indistinguishable from a weakening.

The shared-contract export bound and the `CognitiveRole` re-export scan are **not**
changed.

## I3 — Ratified-kind guard: narrow to `ProposerAdvisory` (B5)

`test_a_defined_advisory_type_declares_the_ratified_kind` must be parametrised over
`ProposerAdvisory` only. `[V]` A6: `CandidateAdvisory` has no `kind` field and cannot
satisfy it.

A mutation test must assert that a `ProposerAdvisory` **without** the ratified kind
still fails, so the narrowing does not disarm the guard for the type it governs. The
rival-identity walk, the barred-field walk and the barred-prefix scans continue to
cover both types unchanged.

## I4 — Test obligations

1. **Frozen-profile suite** — a fixed advisory corpus pinned to exact canonical bytes
   and exact digests, asserting the C6 profile, the C4 `Z` serialisation at microsecond
   precision, the `exclude_none=False` retention of `parent_advisory_digest: null`, and
   the G2 payload/advisory projection equivalence.
2. **List-order significance** — reordering `candidates`, `observation_refs`,
   `claim_summaries`, `uncertainties`, `permitted_tool_scopes` or `allowed_record_refs`
   changes the digest where the field is identity-participating.
3. **No bare number** — canonicalising `P_unsigned` over the corpus raises no
   `BareNumberError`, and no `src` model declares a numeric field or an `Any`-valued
   container.
4. **No wall clock** — no `src` module references `datetime.now`, `datetime.utcnow`,
   `time.time` or `time.monotonic`, and no field defaults to a computed current time.
5. **Naive-datetime rejection** — a naive value is rejected on every `datetime` field,
   and a non-UTC offset is normalised rather than preserved.
6. **Eligibility forgery** — a candidate built with `model_construct` and a flipped
   `is_eligible` is rejected by `verify_candidate_eligibility` and raises
   `EligibilityMismatchError` from `build_proposer_advisory`.
7. **`COMPLETE` unconstructibility** — direct construction, `model_validate` and
   `model_construct`-then-validate with `domain_check_completion=COMPLETE` all raise,
   and `evaluate_readiness` returns `False` for every constructible candidate. The
   test's docstring must record that this is intentional and fail-closed pending an S2
   domain evaluator.
8. **V13** — `terminal_outcome=PROPOSAL` is unreachable in S1: every attempt to build a
   record with it is rejected, and `selected_candidate_id` is `None` on every advisory
   the builders produce.
9. **Process ordering** — R-3 rejects a backward transition, a repeat, two terminals, a
   terminal in non-final position and a non-monotonic `at`.
10. **Installed distribution** — `ugence-jcs` resolves as an installed distribution at
    or above `0.2.0` and exposes `canonical_sha256_hex`, superseding the
    `pyproject.toml` text check `S1_ENFORCEMENT.md` records as the weaker assertion.
11. **Rival-identity reachability** — an explicit test that `content_hash` is not
    reachable from either advisory type, so a future change that re-nests
    `ToolObservation` fails loudly at the design boundary rather than deep in a guard.

## I5 — Versioning and the ADR

`public_api.json` is created only when S1 is implemented, and it must cover every item
in H3. The version moves to `0.1.0` only after the public-API snapshot and its drift
test exist, and `CHANGELOG.md` must record what is frozen at it. Neither happens in this
document: the version stays `0.0.1`.

---

# Part J — Intentionally deferred

Each item below is deliberately absent and is not a gap.

* **A domain evaluator.** `DomainCheckCompletion.COMPLETE` has no producer. Until a
  separately ratified S2 boundary supplies one, C7's validator stands and Equation 2 is
  `False` everywhere.
* **Candidate selection.** Under B3, S1 selects nothing. S-1, S-2 and R-1 are specified
  now so that selection is a behaviour change at S2, not a contract change.
* **The reason-code catalogue.** `reason_codes`, `selection_reason_codes`,
  `deterministic_checks` and `semantic_audit_refs` all reject non-empty values. The
  fields exist so that populating them later is not a schema change; the validators
  exist so that they cannot become a de facto vocabulary before one is ratified.
* **A disposition-to-outcome mapping.** None is ratified. R-2 constrains
  `terminal_outcome` structurally and computes nothing.
* **The semantic auditor.** `SemanticAuditorFindingStatus` remains defined and
  unusable in any outcome or disposition field (D6).
* **Storage, transport, service and authorisation surfaces.** None is specified,
  authorised or implied.

---

# Part K — Residual limitations

These are known and **not locally decidable**. They are recorded so that no reader
mistakes their absence for coverage.

1. **Identity binds identifiers, not input contents (D9).** An advisory digest covers
   the `mandate_id`, `context_id`, `role_contract_id`, `agent_id` and `candidate_set_id`
   it references, not the bodies behind them. Two different mandates sharing an id yield
   the same advisory digest. Forced by A3; closing it needs either nesting, which a
   merged guard forbids, or an input-digest field, which D7 forbids. Whatever stores
   advisories is responsible for the immutability of what those identifiers resolve to.
2. **Lineage cycles beyond the immediate self-parent.** L-1 rejects only
   `parent_advisory_digest == advisory_digest`. Longer cycles are not decidable here:
   this package holds one advisory, not the chain. Parent existence, parent tenant and
   case continuity, and revision monotonicity all require a registry and are outside
   this package. On the builder path L-1 is additionally unachievable by construction —
   a self-referential digest would be a hash fixed point — so its real value is against a
   hand-constructed object.
3. **External hashes are format-checked only.** `context_hash` and `content_hash`
   reference content this package never holds. C6 validates their shape and asserts
   nothing about the content behind them.
4. **Vacuous quantification over an empty reference list.** Per the owner's 0..n
   cardinality, a candidate referencing no observation passes `ContextAllowed` and
   `ToolsAllowed` trivially. Equation 2's `ObservationRefsPresent` is the only place a
   missing reference bites, and only for `RECOMMEND_MATCHED_FOR_APPROVAL`.
5. **Static scanning is not proof (B2).** The disclosed helper-assembled `__import__`
   route reaches a hashing module without the scan seeing it. It authorises nothing —
   code reaching identity that way violates D2 exactly as a bare `hashlib.sha256` would
   — but it is why the invariant, and not the scan, is the rule.
6. **`[G]` The Agent Constitution still does not exist.** `CognitiveRoleContract`
   remains the D8-bounded v0 projection and must be re-derived when the document lands.
   Nothing here is conformance with it.

---

## Ratification statement

Every owner question this specification depends on is resolved: D1–D10, B2, B3 (V13),
B4 (O-2), B5 (O-3), B6 (O-1), B7, B8 and B9 (O-4). No contract shape, field type,
cardinality, vocabulary or equation term is left open, and this document contains no
placeholder.

It is **ratified for S1 implementation**, subject to the implementation obligations in
Part I, which S1 must discharge in the same change that introduces the surface they
govern.
