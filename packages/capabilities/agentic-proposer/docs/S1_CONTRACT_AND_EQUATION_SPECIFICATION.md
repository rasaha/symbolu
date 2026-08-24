# S1 — canonical contract and equation specification

**Status:** `RATIFIED FOR S1 IMPLEMENTATION, QUALIFIED BY OD-4`
**Ratified against:** the default branch at merge commit
`e28538eb454fce6008e94e0772e0fd09c9c7ea7f` (PR #1474)
**Package:** `ugence-agentic-proposer` (`packages/capabilities/agentic-proposer`)
**Authority:** subordinate to D1–D10 and the ratification addenda in
`docs/architecture/ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md`.

Evidence labels: `[V]` verified against this repository by execution or by reading a
named artifact on a merged branch, `[I]` inferred or authored, `[R]` requires
ratification, or verified only against an unmerged branch or an uncommitted planted
shape and therefore to be re-verified, `[G]` gap.

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

**OD-4 is open and bears on contract shape.** Whether `ProposerAdvisory` carries its
`CandidateAdvisory` entries, as ratified D7 says, or references them by
`candidate_set_id`, as Part D specifies, is unresolved. See A3, D9, K.1 and the closing
section.

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
and `CandidateAdvisory` models to any depth, asserting no rival name is reachable. `[V]`
The match is `reachable & RIVAL_IDENTITY_FIELDS` — exact-name set intersection, not a
substring, prefix or suffix rule.

`[R]` Executed against a nested composition in which `ProposerAdvisory` carries
`observations: tuple[ToolObservation, ...]`, the walker returned `['content_hash']`;
executed against the reference-by-id composition specified in Part D, it returned `[]`.
Both runs were against shapes planted in `src/` on the guard branch, against a contract
surface that does not exist on any merged branch. They are recorded here as claims to be
re-verified when the first contract module lands, not as facts about this repository's
committed source.

**Consequence, exactly.** `ProposerAdvisory` may not nest `ToolObservation`. That is not
a preference and cannot be resolved by an allowlist: `content_hash` is on the rival list
precisely to prevent a second identity, and exempting it would defeat D7. **This is the
whole of what the guard forces.**

**What the guard does not force.** `[V]` No field of `CandidateAdvisory` —
`candidate_id`, `disposition`, `requested_review_action`, `is_eligible`,
`domain_check_completion`, `evaluated_at`, `claim_refs`, `observation_refs`,
`assumptions`, `uncertainties` — is a member of `RIVAL_IDENTITY_FIELDS`. Nesting
`CandidateAdvisory` inside `ProposerAdvisory` is therefore **not** prohibited by this
guard. An earlier reading of A3 extended the bar from `ToolObservation` to every nested
contract; that generalisation is withdrawn here.

**Why this matters.** Ratified D7 states the composition directly. `[V]`
`docs/architecture/ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:333-334`:

> The proposer's recommendation artifact is named **`ProposerAdvisory`**, carrying
> per-candidate **`CandidateAdvisory`** entries.

Part D's reference-by-id shape — `ProposerAdvisory` carrying `candidate_set_id` and the
candidates living on a separately transported `AdvisoryCandidateSet` — is therefore a
**departure from ratified D7**, not a consequence of this guard. `[R]` It is recorded,
with its cost and with the alternative of restoring the nesting, as owner decision
**OD-4** in the closing section. This document does not settle it.

## A4 — The lifecycle-verb scan currently matches data names

`[V]` `tests/test_role_projection_bounds.py` matches `LIFECYCLE_VERBS` as
case-insensitive stems over `_defined_names`, which includes `ClassDef` names,
`AnnAssign` targets and enum member assignments. Executed against the ratified
vocabulary, it returns
`['REVOKED', 'RoleActivationStatus', 'SUSPENDED', 'activation_status', 'expires_at']`.

**Consequence.** The ratified vocabulary in B4 cannot be expressed until the guard is
narrowed as specified in I2. `[R]` Against shapes planted in `src/` on the guard branch,
restricting the scan to callable names returned `[]` for the retained vocabulary and
still returned `['ActivateRole', 'activate', 'expire_mandate', 'reactivate',
'revoke_identity', 'suspend_role']` for lifecycle authority. That run was against a
contract surface no merged branch carries; it is a claim to be re-verified when the
first contract module lands.

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

`[V]` On the merged default branch, `test_a_defined_advisory_type_declares_the_ratified_kind`
is parametrised over both `ProposerAdvisory` and `CandidateAdvisory`, and `[V]` against
`pydantic 2.13.4` a model without a `kind` field yields `{None}`, which fails that
assertion.

`[R]` That the assertion actually fires against `CandidateAdvisory` was observed only
against shapes planted in `src/` on the guard branch. It is to be re-verified when the
first contract module lands.

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

## B6 — Selection-dependent fields are nullable and coupled (O-1)

`ProposerAdvisory` carries `selected_candidate_id: str | None` — required as a field,
nullable as a value, C5a-constrained when non-null, and **identity-participating in
`P_unsigned`** — alongside the three fields that depend on it:
`recommended_disposition`, `requested_review_action` and
`requested_review_destination_role_ref`, each nullable.

Enforcement is at **two distinct levels**, specified as R-1a and R-1b and explained in
E1: a local model validator that couples presence to presence and absence to absence,
and a cross-contract obligation on the builder and the replay verifier that resolves
the referenced `AdvisoryCandidateSet` and checks correspondence. The local validator
does not, and cannot, establish the second.

Under B3, S1 has no selected candidate, so in S1 all four are always `None`. The
future-stage branch is preserved in the contract and is not reachable in S1.

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
Fields that are neither — closed symbolic tokens and scope names — carry their own
canonical token pattern and are **not** silently treated as free text. The full
classification — three semantic categories plus the mechanical C5d — is C5.

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
| `tenant_id` | `str` | yes | no | none | C5a |
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

## C5 — Field classification: four categories, assigned explicitly

Every `str`-valued field — including every element of a `list[str]` and every key and
value of a `dict[str, str]` — belongs to exactly one of four categories. The category is
**declared per field in its contract table**, never inferred from its name. A guard
that classified by suffix alone would silently miss `tool_name` and the scope fields,
which are neither `*_id`-shaped nor free text.

Three categories are semantic: C5a, C5b and C5c say what a value *is*. The fourth, C5d,
is **mechanical**: it says that no value is admitted at all, so no content class applies.

### C5a — Identifier or reference

An opaque, externally minted handle. `str` matching `^[A-Za-z0-9][A-Za-z0-9._:/-]*$`,
maximum 200 characters (B9). `/` is permitted because an external issuer may mint a
path-shaped handle.

### C5b — Canonical symbolic token

A vocabulary term **matched by equality against an allowlist**. `str` matching
`^[A-Za-z0-9][A-Za-z0-9._:-]*$`, maximum 200 characters — the C5a class **minus `/`**.

`[I]` The distinction is semantic, not cosmetic. A C5a value is carried and compared
whole; a C5b value is the operand of a membership test, and a path-shaped spelling
invites a consumer to split or normalise it before comparing, which would make
`tool_name in permitted_tool_scopes` depend on the consumer. Excluding `/` removes
that invitation. Both classes are ASCII, so both are NFC-invariant, which is what B9
requires of anything reachable from `P_unsigned`.

**C5b fields:** `agent_version`; `tool_name`; and each element of
`allowed_source_scopes`, `excluded_data_classes`, `permitted_tool_scopes` and
`tool_invocations`.

### C5c — Human-readable free text

**A C5c field admits no pattern or regex constraint of any kind.** Not the C5a pattern,
not the C5b pattern, not a narrowed variant of either, not an anchored character class,
and not a "lenient" pattern intended to catch obvious junk. This is a prohibition on the
*mechanism*, not only on the two named patterns: any `pattern=`, any `StringConstraints`
carrying a `pattern`, any `re` match applied at validation, and any custom validator
whose effect is to test a C5c value against a regular expression is barred.

`[I]` The reason is that a pattern on free text is a defect and not a safeguard.
`purpose`, `claim_summaries`, `assumptions` and `uncertainties` are written in whatever
language the case is conducted in; every regular expression narrow enough to reject
anything rejects some lawful prose, and none of them is matched, routed or joined on, so
there is nothing for the pattern to protect. B10 makes the same point about substring
scanning; this is that rule stated as a positive constraint on declaration.

The only constraints a C5c field may carry are non-pattern ones — length, NFC, non-empty
— and each is given explicitly in its contract table.

**C5c fields:** `purpose`, `primary_function`, `declared_strategy`, each element of
`claim_summaries`, `assumptions` and `uncertainties`, and each **value** of
`normalized_fields` (its *keys* are C5a). `[I]` A normalised field value is content a
tool reported; this package neither matches nor routes on it, and `ToolObservation` is
not reachable from `P_unsigned` (D9), so the B9 hazard does not reach it and no pattern
may be imposed on it.

`[I]` `primary_function` and `declared_strategy` are described as opaque and compared
for equality only, which is the C5b shape — but neither is reachable from
`P_unsigned` (D9), so the NFC hazard that motivates B9 does not apply to them, and the
less restrictive classification cannot reject a lawful value. Recorded as owner
decision **OD-1** in the closing section.

### C5d — Structurally empty reserved list

A `list[str]` field that **rejects any non-empty value**. It is reserved so that
populating it later is not a schema change, and it is closed now so that it cannot become
a de facto vocabulary before one is ratified (Part J).

**C5d fields:** `AdvisoryCandidateSet.selection_reason_codes`,
`ProposerAdvisory.reason_codes`, `ProposerProcessRecord.deterministic_checks`,
`ProposerProcessRecord.semantic_audit_refs` and `ProposerProcessRecord.reason_codes`.

`[I]` These are the fourth, **mechanical** class rather than members of C5a, C5b or C5c.
Their element type is `str`, so a registry that admitted only the three semantic classes
would have to assign one of them — and each assignment would be a false statement about a
value that cannot exist. Assigning C5a or C5b would pin an identifier or token pattern
that is never applied to anything and would read as a ratified spelling for codes whose
catalogue is explicitly unratified. Assigning C5c would say the elements are prose for a
person to read, which is the one thing a reason code is not. C5d states the truth: the
constraint is emptiness, and a content class attaches only when the catalogue is ratified
and the field is reopened.

The C5d validator is the **whole** of the field's element validation. No C5a, C5b or C5c
pattern is declared alongside it; a pattern that can never be reached is a claim about a
vocabulary this stage does not have.

**No field is left unclassified.** Every `str`-valued field in Part D carries C5a, C5b,
C5c or C5d in its Validation column, and I5 requires the guards to enforce that
classification from an exact pinned registry rather than from name shape.

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

## C8 — How a constrained `str` field is declared

**Normative.** Every `str` field carrying a pattern, a length bound or any other string
constraint is declared as

```python
field_name: Annotated[str, StringConstraints(pattern=..., max_length=...)]
```

and **never** as

```python
field_name: str = Field(pattern=..., max_length=...)
```

The two spellings are equivalent to pydantic. They are **not** equivalent to the merged
identity-source guard.

`[V]` `test_identity_is_computed_only_through_the_permitted_substrate` collects, via
`_identity_assignments`, every value expression assigned to `advisory_digest`, including
every `ast.AnnAssign` whose target is that name and whose `value` is not `None`. It then
requires that expression to contain a call whose root name resolves to a `ugence_jcs`
import, and rejects it otherwise. Under `Annotated[...]` the annotated assignment has no
value, so nothing is collected. Under `Field(...)` the annotated assignment's value is
`Call(Field, …)`; `Field` does not resolve to the substrate, and the declaration is
reported as an unpermitted identity source. **The contract module would fail a merged
guard at import-scan time for declaring its own identity field's pattern.**

The rule is stated for *every* constrained `str` field, not only `advisory_digest`.
Confining it to the one field that trips the guard would leave the codebase two
spellings for one thing and the guard one rename away from being tripped again.

`Field(...)` remains permitted for anything that is not a string constraint — a
`default`, a `default_factory`, an alias or a description — on any field other than
`advisory_digest`, which takes no `Field(...)` at all.

`[I]` This also composes with C5c and C5d: a C5c field is `Annotated[str,
StringConstraints(max_length=...)]` with **no** `pattern` argument, and a C5d field
carries its emptiness rule in a validator rather than as a string constraint at all.

The mutation obligation is I7.12.

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

**Cardinality: 8 fields** — the five below plus the three C2 common fields
(`schema_version`, `tenant_id`, `created_at`). Stated because I5's pinned registry is
checked by exact membership, and a contract whose field count is left implicit is a
contract whose registry entry cannot be checked for completeness.

D3: the proposer mints no agent identity. Every field is an externally issued fact. No
lifecycle field is computed here and no lifecycle verb is exposed.

| Field | Type | Required | Nullable | Default | Cardinality | Vocabulary | Validation | Ownership | Identity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `agent_id` | `str` | yes | no | none | 1 | open | C5a | external identity issuer | no |
| `agent_version` | `str` | yes | no | none | 1 | open | C5b | external identity issuer | no |
| `lifecycle_state` | `AgentLifecycleState` | yes | no | none | 1 | **closed**: `ACTIVE`, `INACTIVE`, `SUSPENDED`, `REVOKED` | enum membership; an unrecognised value fails validation and coerces to no member | external identity issuer | no |
| `bound_role_contract_id` | `str` | yes | no | none | 1 | open | C5a | external identity issuer | no |
| `owner_role_ref` | `str` | yes | no | none | 1 | open | C5a | external identity issuer | no |

`bound_role_contract_id` is the binding Equation 1's `RoleMatch` reads. This package
validates it and never sets or changes it.

## D2 — `CognitiveRoleContract`

D1 and D8: a proposer-local **v0** projection, never re-exported to any shared contract
package, carrying no constitution-derived attribute, exposing no role lifecycle verb.

| Field | Type | Required | Nullable | Default | Cardinality | Vocabulary | Validation | Ownership | Identity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `role_contract_id` | `str` | yes | no | none | 1 | open | C5a | external role owner | no |
| `primary_function` | `str` | yes | no | none | 1 | open | **C5c**; non-empty; **opaque** — compared for equality only, never semantically interpreted (OD-1) | external role owner | no |
| `permitted_tool_scopes` | `list[str]` | yes | no | `[]` | 0..n | open | each C5b; order preserved | external role owner | no |
| `permitted_candidate_dispositions` | `list[CandidateDisposition]` | yes | no | none | 1..4 | **closed, D4** | enum membership; **rejects an empty list**; no duplicates | external role owner | no |
| `permitted_review_actions` | `list[ReviewAction]` | yes | no | none | 1..n | **closed, B8** | enum membership; **rejects an empty list**; no duplicates | external role owner | no |
| `escalation_role_ref` | `str` | yes | no | none | 1 | open | C5a | external role owner | no |
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
| `mandate_id` | `str` | yes | no | none | 1 | open | C5a | mandate issuer | no |
| `case_ref` | `str` | yes | no | none | 1 | open | C5a; **domain-neutral** | mandate issuer | no |
| `assigned_role_contract_id` | `str` | yes | no | none | 1 | open | C5a | mandate issuer | no |
| `purpose` | `str` | yes | no | none | 1 | open | **C5c**; non-empty; length ≤ 4000; NFC required; **no content scanning** (B10) | mandate issuer — **non-authoritative** | no |
| `allowed_source_scopes` | `list[str]` | yes | no | none | 1..n | open | each C5b; rejects an empty list; no duplicates | mandate issuer | no |
| `expires_at` | `datetime` | yes | no | none | 1 | — | C4 | mandate issuer | no |

`case_ref` is domain-neutral: it is neither named nor documented as invoice-specific.

## D4 — `BoundedContextEnvelope`

| Field | Type | Required | Nullable | Default | Cardinality | Vocabulary | Validation | Ownership | Identity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `context_id` | `str` | yes | no | none | 1 | open | C5a | context assembler | no |
| `mandate_id` | `str` | yes | no | none | 1 | open | C5a; must reference `WorkMandate.mandate_id` | context assembler | no |
| `allowed_record_refs` | `list[str]` | yes | no | `[]` | 0..n | open | each C5a; order preserved | context assembler | no |
| `excluded_data_classes` | `list[str]` | yes | no | `[]` | 0..n | open | each C5b | context assembler | no |
| `context_hash` | `str` | yes | no | none | 1 | open | C6 **format only** | **context assembler** | no |
| `expires_at` | `datetime` | yes | no | none | 1 | — | C4 | context assembler | no |

**`context_hash` is externally supplied.** S1 validates its *format* and does nothing
else with it. S1 does not compute it, does not recompute it and does not verify it
against any content — doing so would require hashing locally, which D2 bars.

## D5 — `ToolObservation`

| Field | Type | Required | Nullable | Default | Cardinality | Vocabulary | Validation | Ownership | Identity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `observation_id` | `str` | yes | no | none | 1 | open | C5a | observation producer | no |
| `case_ref` | `str` | yes | no | none | 1 | open | C5a | observation producer | no |
| `tool_name` | `str` | yes | no | none | 1 | open | C5b | observation producer | no |
| `operation_class` | `ToolOperationClass` | yes | no | none | 1 | **closed**: `READ_ONLY` | enum membership | observation producer | no |
| `source_ref` | `str` | yes | no | none | 1 | open | C5a | observation producer | no |
| `observed_at` | `datetime` | yes | no | none | 1 | — | C4 | observation producer | no |
| `content_hash` | `str` | yes | no | none | 1 | open | C6 **format only** | **observation producer** | no |
| `normalized_fields` | `dict[str, str]` | yes | no | `{}` | 0..n keys | open | keys C5a; values **C5c** and **`str`** | observation producer | no |
| `admission_status` | `ToolObservationAdmissionStatus` | yes | no | `NOT_EVALUATED` | 1 | **closed**: `NOT_EVALUATED` | enum membership | this package | no |

**`normalized_fields` values are `str`, not `Any`.** `[V]` A1: an `Any`-valued mapping
admits `int` and `float`, which raise `BareNumberError`, and `Decimal`, which raises
`UnsupportedTypeError`. Constraining the value type at declaration is what makes the
constraint checkable at validation rather than at canonicalisation. No code path in
this package constructs any `admission_status` other than `NOT_EVALUATED`.

## D6 — `AdvisoryCandidateSet`

A top-level contract. Under the shape specified here it is **not** nested in
`ProposerAdvisory`; the advisory references it by `candidate_set_id`. `[R]` That
reference-by-id shape is a departure from ratified D7 and is open as **OD-4**; if OD-4
resolves toward restoring the nesting, this contract becomes a nested public shape and
`ProposerAdvisory.candidate_set_id` is replaced by the set itself.

| Field | Type | Required | Nullable | Default | Cardinality | Vocabulary | Validation | Ownership | Identity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `candidate_set_id` | `str` | yes | no | none | 1 | open | C5a | this package | no |
| `case_ref` | `str` | yes | no | none | 1 | open | C5a | this package | no |
| `candidates` | `list[CandidateAdvisory]` | yes | no | none | 1..n | — | **rejects an empty list**; `candidate_id` unique across the list; order preserved | this package | no |
| `selected_candidate_id` | `str \| None` | yes (explicit) | yes | `None` | 0..1 | open | C5a when non-null; S-1 and S-2 below | this package | no |
| `selection_reason_codes` | `list[str]` | yes | no | `[]` | 0..n | — | **C5d** — rejects any non-empty value | this package | no |

**Locally decidable selection invariants**, both decidable from this contract alone:

* **S-1 — resolution.** If `selected_candidate_id` is not `None`, exactly one element of
  `candidates` has that `candidate_id`.
* **S-2 — eligibility of the selection.** If `selected_candidate_id` is not `None`, the
  resolved candidate has `is_eligible is True`.

`selection_reason_codes` is C5d: it rejects any non-empty value, because the reason-code
catalogue is out of scope at this stage and an unvalidated free-form code list would
become a de facto vocabulary before one is ratified.

`[I]` The converse of S-1 — "if any candidate is eligible, one must be selected" — is
**not** an invariant. Declining to select among eligible candidates is `ABSTAIN`, which
D4 ratifies. Forcing selection would convert an abstention into a recommendation.

**Under B3, `selected_candidate_id` is `None` for every advisory S1 can construct**, so
S-1 and S-2 are satisfied vacuously in S1 and become load-bearing at S2.

### `CandidateAdvisory` — nested public shape

| Field | Type | Required | Nullable | Default | Cardinality | Vocabulary | Validation | Ownership | Identity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `candidate_id` | `str` | yes | no | none | 1 | open | C5a; unique within its set | this package | no |
| `disposition` | `CandidateDisposition` | yes | no | none | 1 | **closed, D4**: `RECOMMEND_MATCHED_FOR_APPROVAL`, `RECOMMEND_WITHHOLD`, `REQUEST_EVIDENCE`, `ESCALATE_EXCEPTION` | enum membership | this package | no |
| `requested_review_action` | `ReviewAction` | yes | no | none | 1 | **closed, B8** | enum membership | this package | no |
| `is_eligible` | `bool` | yes | no | none | 1 | closed: `true`, `false` | **package-computed** — see Part G | this package | no |
| `domain_check_completion` | `DomainCheckCompletion` | yes | no | `NOT_EVALUATED` | 1 | **closed**: `NOT_EVALUATED`, `COMPLETE` | enum membership; **`COMPLETE` rejected unconditionally** (C7) | this package | no |
| `evaluated_at` | `datetime` | yes | no | none | 1 | — | C4 | caller-supplied, package-recorded | no |
| `claim_refs` | `list[str]` | yes | no | `[]` | 0..n | open | each C5a | this package | no |
| `observation_refs` | `list[str]` | yes | no | `[]` | 0..n | open | each C5a; no duplicates; every entry must reference a supplied `ToolObservation.observation_id` | this package | no |
| `assumptions` | `list[str]` | yes | no | `[]` | 0..n | open | C5c | this package | no |
| `uncertainties` | `list[str]` | yes | no | `[]` | 0..n | open | C5c | this package | no |

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

**This contract references its inputs by identifier.** It nests no other contract.

`[V]` A3 forces exactly one half of that: nesting `ToolObservation` makes `content_hash`
reachable and fails the merged rival-identity walk. `[R]` The other half — that
`CandidateAdvisory` is referenced through `candidate_set_id` rather than carried
inline — is **not** forced by any guard, and it departs from ratified D7, which says
`ProposerAdvisory` carries per-candidate `CandidateAdvisory` entries. It is open as
**OD-4**. The field set below is written for the reference-by-id shape; restoring the
nesting would replace `candidate_set_id` with the candidate entries and would change
`P_unsigned` (G1), D9 and K.1 accordingly.

| Field | Type | Required | Nullable | Default | Cardinality | Vocabulary | Validation | Ownership | Identity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `kind` | `Literal["ugence.agentic_proposer.advisory.v0"]` | yes | no | that literal | 1 | closed, D7 | literal equality | this package | yes |
| `advisory_version` | `str` | yes | no | `"1"` | 1 | open | `^[1-9][0-9]*$` (B7) | this package | yes |
| `advisory_digest` | `str` | yes | **no** | none | 1 | open | C6; equals Equation 3 over `P_unsigned` | this package | **excluded from `P_unsigned`** |
| `parent_advisory_digest` | `str \| None` | yes (explicit) | yes | `None` | 0..1 | open | C6 when non-null; L-1 | this package | **yes, including when `null`** |
| `case_ref` | `str` | yes | no | none | 1 | open | C5a | this package | yes |
| `agent_id` | `str` | yes | no | none | 1 | open | C5a; references `AgentIdentityRef.agent_id` | this package | yes |
| `role_contract_id` | `str` | yes | no | none | 1 | open | C5a; references `CognitiveRoleContract.role_contract_id` | this package | yes |
| `mandate_id` | `str` | yes | no | none | 1 | open | C5a; references `WorkMandate.mandate_id` | this package | yes |
| `context_id` | `str` | yes | no | none | 1 | open | C5a; references `BoundedContextEnvelope.context_id` | this package | yes |
| `candidate_set_id` | `str` | yes | no | none | 1 | open | C5a; references `AdvisoryCandidateSet.candidate_set_id` | this package | yes |
| `selected_candidate_id` | `str \| None` | yes (explicit) | yes | `None` | 0..1 | open | C5a when non-null; **R-1a** (local), **R-1b** (cross-contract) | this package | yes |
| `recommended_disposition` | `CandidateDisposition \| None` | yes (explicit) | yes | `None` | 0..1 | closed, D4 | R-1a, R-1b (B6) | this package | yes |
| `requested_review_action` | `ReviewAction \| None` | yes (explicit) | yes | `None` | 0..1 | closed, B8 | R-1a, R-1b (B6) | this package | yes |
| `requested_review_destination_role_ref` | `str \| None` | yes (explicit) | yes | `None` | 0..1 | open | C5a when non-null; R-1a, R-1b (B6) | this package | yes |
| `claim_summaries` | `list[str]` | yes | no | `[]` | 0..n | open | C5c | this package | yes |
| `observation_refs` | `list[str]` | yes | no | `[]` | 0..n | open | each C5a; no duplicates | this package | yes |
| `uncertainties` | `list[str]` | yes | no | `[]` | 0..n | open | C5c | this package | yes |
| `reason_codes` | `list[str]` | yes | no | `[]` | 0..n | — | **C5d** — rejects any non-empty value | this package | yes |
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
| `process_record_id` | `str` | yes | no | none | 1 | open | C5a | this package | no |
| `case_ref` | `str` | yes | no | none | 1 | open | C5a | this package | no |
| `declared_strategy` | `str` | yes | no | none | 1 | open | **C5c**; non-empty; **opaque, not an enum** (OD-1) | this package | no |
| `state_transitions` | `list[ProposerProcessStateTransition]` | yes | no | `[]` | 0..n | — | R-3 | this package | no |
| `tool_invocations` | `list[str]` | yes | no | `[]` | 0..n | open | each C5b | this package | no |
| `deterministic_checks` | `list[str]` | yes | no | `[]` | 0..n | — | **C5d** — rejects any non-empty value | this package | no |
| `candidate_ids` | `list[str]` | yes | no | `[]` | 0..n | open | each C5a; no duplicates | this package | no |
| `selected_candidate_id` | `str \| None` | yes (explicit) | yes | `None` | 0..1 | open | C5a when non-null | this package | no |
| `semantic_audit_refs` | `list[str]` | yes | no | `[]` | 0..n | — | **C5d** — rejects any non-empty value | this package | no |
| `terminal_outcome` | `TerminalOutcome` | yes | no | none | 1 | **closed, D4**: `PROPOSAL`, `NEED_EVIDENCE`, `ABSTAIN`, `ESCALATE` | enum membership; R-2 | this package | no |
| `reason_codes` | `list[str]` | yes | no | `[]` | 0..n | — | **C5d** — rejects any non-empty value | this package | no |
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

`[I]` This has a real cost, stated plainly: an advisory's digest binds the *identifiers*
of its inputs, not their *contents*. Two different `WorkMandate` bodies carrying the same
`mandate_id` yield the same advisory digest.

`[V]` For `ToolObservation` the cost is forced: A3 bars nesting it, and an input-digest
field would be a second identity, which D7 forbids.

`[R]` For `CandidateAdvisory` the cost is **not** forced. A3 does not bar nesting it, and
ratified D7 says it is carried. Excluding the candidate entries from `P_unsigned` is a
consequence of **OD-4**, not of any guard: under the reference-by-id shape an advisory's
digest does not cover the dispositions, eligibility Booleans or observation references of
the candidates it was derived from, and two candidate sets sharing a `candidate_set_id`
yield the same advisory digest. Restoring the nesting would bring all of that inside
`P_unsigned` and would make R-1b locally decidable. Both are recorded in Part K.

---

# Part E — Cross-contract validations

Each is a validation S1 must implement at construction. Those marked *(equation term)*
also appear in Equation 1; they are listed here once as contract obligations.

| Id | Rule | Prevents |
| --- | --- | --- |
| R-1a | **Selection binding — local (B6).** A `ProposerAdvisory` model validator enforces: if `selected_candidate_id is None`, then `recommended_disposition`, `requested_review_action` and `requested_review_destination_role_ref` are **all** `None`; if `selected_candidate_id is not None`, those three are **all** non-null. Decidable from this contract's own fields alone | a routing request standing next to no selection, and a selection with no routing — two failure modes that call for opposite responses |
| R-1b | **Selection binding — cross-contract (B6).** `build_proposer_advisory` and the replay verifier resolve the referenced `AdvisoryCandidateSet` and enforce: `ProposerAdvisory.selected_candidate_id == AdvisoryCandidateSet.selected_candidate_id`; the selected id identifies **exactly one** candidate in that set; `recommended_disposition` equals that candidate's `disposition`; `requested_review_action` equals that candidate's `requested_review_action` and is a member of `CognitiveRoleContract.permitted_review_actions`; `requested_review_destination_role_ref` is consistent with that candidate's routing; and tenant, case and candidate-set references are continuous | an advisory whose routing contradicts, or invents, the candidate it claims to select |
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

## E1 — The two levels of selection enforcement, and what neither proves

R-1a and R-1b are **not** two statements of one rule. They live at different levels and
prove different things, and conflating them would be the same error this document
refuses to make about `is_eligible`.

**R-1a is local and structural.** It is a `ProposerAdvisory` model validator. It sees
only this advisory's own fields, so all it can decide is whether the selector and its
three dependents are *jointly present or jointly absent*.

> **R-1a proves nothing about the referenced `AdvisoryCandidateSet`.** A model
> validator cannot resolve `candidate_set_id`; it has an identifier, not the set. It
> cannot know whether the selected candidate exists, whether the recorded disposition
> is that candidate's, or whether the routing is permitted. Any claim that the local
> validator establishes correspondence with the candidate set is **false** and must not
> appear in S1 documentation, tests or commit messages.

**R-1b is cross-contract and behavioural.** It is discharged by
`build_proposer_advisory` at construction and **independently re-established** by the
replay verifier, each of which is given the `AdvisoryCandidateSet`, the
`CognitiveRoleContract` and the observations, and each of which resolves the selection
and checks correspondence itself. This mirrors B2 exactly: construction is
defence-in-depth, and independent replay is the guarantee.

`[I]` The mirrored `selected_candidate_id` on `ProposerAdvisory` exists to make R-1a
decidable at all. Under the reference-by-id shape A3 forces, the advisory would
otherwise carry three selection-dependent fields and no selector, so the coupling could
not be checked on the advisory in isolation and would be enforceable only by a builder
a consumer has no way to audit. Because it is identity-participating, a stored advisory
also carries the selection it claims into its digest, so replay can detect a selector
altered after signing.

**Under V13 (B3), S1 sets `selected_candidate_id` and all three dependents to `None`.**
The non-null branch is specified so that it is a behaviour change at S2 rather than a
contract change, and it is not reachable in S1: `build_proposer_advisory` derives all
four from the candidate set, and B3 makes a selection unconstructible.

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


def verify_advisory_selection(
    *,
    advisory: ProposerAdvisory,
    candidate_set: AdvisoryCandidateSet,
    role: CognitiveRoleContract,
) -> bool: ...
```

`verify_advisory_selection` is the independent replay of R-1b. It is a **separate
function from `verify_advisory_identity`** because the two answer different questions:
identity asks whether the stored bytes are the ones that were signed, correspondence
asks whether what was signed agrees with the candidate set it references. A caller
acting on an advisory's routing must call both. It returns `False` rather than raising,
on the same terms as `verify_candidate_eligibility`.

Notes that are part of the ratified behaviour:

* `build_candidate_advisory` takes no `is_eligible` and no `domain_check_completion`.
  It computes the first and leaves the second at its `NOT_EVALUATED` default.
* `build_proposer_advisory` **derives** `selected_candidate_id`,
  `recommended_disposition`, `requested_review_action` and
  `requested_review_destination_role_ref` from the candidate set under R-1b rather than
  accepting them, so the two cannot disagree. It resolves the set, checks
  correspondence, and rejects a mismatch. Under B3 it derives `None` for all four in S1.
  It calls `verify_candidate_eligibility` and raises `EligibilityMismatchError` before
  constructing if any candidate's stored `is_eligible` differs from the recomputation.
  R-1a is additionally enforced by the model validator on every construction path,
  including one the builder did not produce.
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

**Verifiers (2):** `verify_candidate_eligibility`, `verify_advisory_selection`

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

> **Status note.** `[R]` O-2 and O-3 below are implemented on branch
> `claude/governance-refinements-o1-o4-k96vbz` (head `96510a1c4`, first landed at
> `30945dac8`), together with a new O-1 guard and a new O-4 guard. **That branch is not
> merged.** Nothing in this note is a fact about any merged branch, and every "implemented"
> below means "implemented there, to be re-verified on merge".
>
> `[R]` That branch changes tests and documentation only — no `src/`, `version.py`,
> `pyproject.toml`, CI workflow, `public_api.json` or platform-freeze artifact is
> touched — and its suite is green at 418 passed, 14 skipped, where the skips are dormant
> parametrisations over a contract surface that does not exist yet. `[R]` Planting
> representative contract shapes in `src/` arms them; those planted shapes are not
> committed on any branch, so every count taken against them is a claim about a
> throwaway working tree and is re-verifiable only by repeating the planting.
>
> That branch is expected to merge **before** this specification, and the whole of this
> note is to be re-verified at that point. I1, I5, I6 and I7 remain outstanding; I2 and
> I3 record what that branch did.

## I1 — D2 scan: a narrow, module-scoped exemption *(outstanding)*

`[V]` A7: the ratified `"sha256:"` prefix literal and the C6 pattern
`^sha256:[0-9a-f]{64}$` collide with `SUSPECT_TEXT`. `[R]` The guard branch does not
address this — its only change to `test_no_local_canonicalization.py` adds the two new
guard modules to the pinned module list — but that branch is unmerged, so the statement
is about its head `96510a1c4` and must be re-verified against whatever merges.

The resolution is a **module-path-scoped mask**, not a widened rule: the text mask for
exactly the two strings `"sha256:"` and `"^sha256:[0-9a-f]{64}$"` applies only within
the single authorised identity module, and nowhere else in `src` or `tests`.

It must not permit: an arbitrary `sha256:` literal in any other module; a local
`hashlib` import anywhere; a locally defined `canonical_*`; a shadowed or relative
`ugence_jcs`; or an identity computation from any module outside the authorised one.

**No definition-name exemption is required.** The identity functions are named
`compute_advisory_identity`, `verify_advisory_identity`, `verify_advisory_selection` and
`verify_candidate_eligibility`; none contains `"digest"`, `"canonical"`, `"canon"`,
`"jcs"`, `"fingerprint"` or any other `SUSPECT_DEF_SUBSTRINGS` member, so
`SUSPECT_DEF_SUBSTRINGS` is left untouched. The field name `advisory_digest` is an
`AnnAssign` target, not a `FunctionDef` or `ClassDef`, and is not scanned. **Test
function names must not contain `"digest"`**, for the same reason.

**Mutation tests required**, proving each of these is still rejected: `"sha256:"` in a
module other than the authorised one; the authorised name defined at class scope; the
authorised name defined without the substrate call; the authorised module importing
`hashlib`; and a locally defined `canonical_sha256_hex`.

## I2 — Lifecycle-verb guard: narrowed to authority, not vocabulary (B4) *(implemented on an unmerged branch)*

`[R]` Implemented on the guard branch `claude/governance-refinements-o1-o4-k96vbz`,
which is not merged. Everything in this section is read from that branch and is to be
re-verified on merge. It classifies by **grammatical form and
syntactic position** rather than by stem: a mutation form is barred in every position;
an actor form is barred as a type or callable and permitted as a field naming an
external party; any lifecycle-stemmed field annotated `Callable` is barred. The
retained vocabulary — `SUSPENDED`, `REVOKED`, `RoleActivationStatus`,
`activation_status`, `expires_at` — is pinned permitted **by equality**, and the six
verbs D8 names are pinned barred in all four positions. Six mutants each weaken one
rule and must let a real violation escape without gaining a false positive on the
retained vocabulary.

This supersedes the cruder "callables only" rule an earlier draft of this document
specified. `[R]` Both accept the retained vocabulary; the implemented rule additionally
distinguishes an actor noun used as a field from one used as a type, which the cruder
rule could not. Both halves were observed on the unmerged branch.

## I3 — Ratified-kind guard: narrowed to `ProposerAdvisory` (B5) *(implemented on an unmerged branch)*

`[R]` Implemented on the guard branch, which is not merged: the kind is **required** on `ProposerAdvisory`
and **barred** on `CandidateAdvisory`, along with any other kind in this capability's
namespace, and the kind reader is self-tested against all three spellings (`KIND`,
`kind`, a `kind` field default). This is stronger than the narrowing this document
originally specified, which only removed `CandidateAdvisory` from the assertion.

## I4 — Two corrections the guard branch needs before it merges

`[R]` Both were found by running that branch's suite against representative contract
shapes planted in `src/`. The shapes are not committed anywhere, and the branch is not
merged, so neither observation below is a fact about this repository: both are claims to
be re-verified when the first contract module lands.

1. **The O-1 guard has a class-blind false positive.** `DEPENDENT_FIELDS` is matched by
   name alone, so `CandidateAdvisory.requested_review_action` — the candidate's **own**
   proposed routing, required and non-null by D6 of this document — is treated as a
   selection-dependent field. The guard then demands a `selected_candidate_id` on
   `CandidateAdvisory` and demands the field admit `None`, which contradicts the
   ratified contract. Four tests fail on that class:
   `test_a_dependent_field_is_declared_with_its_selector`,
   `test_every_dependent_field_admits_none`, `test_the_coupling_is_enforced_in_code` and
   `test_a_live_dependent_field_accepts_none`.

   `[R]` The corrected `ProposerAdvisory` specified here — carrying the mirrored
   `selected_candidate_id` and the R-1a validator — passed all four against the planted
   shapes. The defect appeared confined to `CandidateAdvisory`.

   The fix is to scope the dependent-field set to the bearer contract: the three fields
   are selection-dependent **on `ProposerAdvisory`**, and `requested_review_action` on a
   candidate is a different field with the same name. Since `DEPENDENT_FIELDS` is pinned
   by equality, the scoping must be pinned the same way.

2. **`test_boundaries.py` will fail on the first contract module, for a reason unrelated
   to either branch.** `[V]` Reproduced against `pydantic 2.13.4` in this environment:
   bare `import pydantic` does **not** load `socket`, but *defining any* `BaseModel` does — pydantic-core's schema build pulls it
   in. `socket` is in that guard's `FORBIDDEN` set, and its own docstring records that
   the probe "is meaningful only because the package is a stdlib-light leaf." Every
   contract in Part D is a `BaseModel` and `pydantic>=2` is a ratified core dependency,
   so this is unavoidable and is not a defect in the contracts. `[R]` That the first
   contract module actually fails that guard follows from the two facts above and is to
   be verified when such a module exists.

   This needs an owner ruling before S1 code lands — recorded as **OD-2**. It does not
   affect any contract shape in this document.

## I5 — Field classification must be pinned, not guessed (O-4)

**The suffix-inference defect this section originally reported is fixed.** `[R]` At
`30945dac8` the O-4 guard classified by name suffix (`_id`, `_ids`, `_ref`, `_refs`,
`_key`, `_keys`, `_uri`, `_uris`, `_urn`, `_code`, `_codes`, `_slug`) with a free-text
marker list, and six fields — `agent_version`, `tool_name`, `allowed_source_scopes`,
`excluded_data_classes`, `permitted_tool_scopes` and `tool_invocations` — fell in
neither bucket and were checked by nothing. `[R]` At `96510a1c4` that branch replaced
inference with an exact per-contract registry in which every declared field must appear,
an unregistered field being a failure rather than a skip, and retained inference only as
a secondary cross-check. The obligation below is therefore **what the merged guard must
still carry**, not a defect report against it; the branch remains unmerged, so its state
is `[R]` either way.

`tool_name` remains the sharpest case for why the registry is the primary mechanism — it
is matched by equality against `permitted_tool_scopes`, so an unnormalised spelling
changes an eligibility outcome.

**The registry, as S1 must carry it.** Every field of every contract in Part D mapped to
C5a, C5b, C5c or C5d, keyed by *bearer contract and field name* — never by field name
alone, since `requested_review_action` is a different field on `ProposerAdvisory` than on
`CandidateAdvisory` (I4.1, OD-3). A test fails if any field declared in `src` is absent
from the registry, and a second test fails if any registry entry names a field `src` does
not declare, so the registry cannot drift in either direction.

**It must carry non-`str` fields too.** In particular it must carry
`AgentIdentityRef.lifecycle_state`. `[I]` A registry populated only from `str`-annotated
fields is a registry whose completeness check is circular: it can never report a missing
entry for a field it declines to look at, so a field silently retyped from `str` to an
enum — or from an enum to `str` — passes unexamined in exactly the direction that
matters. `lifecycle_state` is the field where that bites hardest: it is the sole input to
Equation 1's `IdentityActive` term, its vocabulary is closed by D1's table, and a `str`
spelling of it would be an unclassified identity-adjacent field carrying no pattern at
all. The registry entry records it as a **closed enum, not a `str` class**, and D1's
stated cardinality of 8 is what makes that entry checkable for completeness.

**Mutation tests required**, proving each category is recognised:

* `tool_name` and each of the five scope/token fields as C5b, carrying the C5b pattern
  and not the C5a one, and not unchecked;
* `case_ref`, `mandate_id` and `observation_refs` as C5a;
* `purpose`, `primary_function`, `declared_strategy`, `claim_summaries`, `assumptions`,
  `uncertainties` and every value of `normalized_fields` as C5c, and **barred from
  carrying a pattern or regex constraint of any kind** — not merely barred from the C5a
  and C5b patterns. A mutant that swaps a C5c field's constraint for a *third*,
  narrower-looking pattern, or that reaches the same effect through a custom validator
  applying `re.fullmatch`, must fail (C5c);
* the five C5d fields as C5d, rejecting every non-empty value and declaring no element
  pattern at all; a mutant that adds a C5a or C5b pattern alongside the emptiness rule
  must fail (C5d);
* `AgentIdentityRef.lifecycle_state` present in the registry as a closed enum, and a
  mutant retyping it to a bare `str` failing rather than passing unclassified;
* a field added to `src` but missing from the registry failing loudly, and a registry
  entry naming a field `src` does not declare failing loudly.

## I6 — The S0 export pin must be updated with the first contract

`[V]` `tests/test_vocabulary.py::test_public_api_exports_only_the_vocabulary_and_version`
pins the S0 public surface by equality on the merged default branch. `[R]` That it fails
the moment a contract is exported was observed only against the uncommitted planted
shapes, and is to be re-verified when the first contract is exported. It must be updated in the same change that
introduces the first contract, to the full H3 surface, and not before.

## I7 — Test obligations

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
    The test must assert `ToolObservation` specifically and must **not** be written so
    that it also bars nesting `CandidateAdvisory`, which no rival name reaches (A3) and
    which ratified D7 places inside the advisory (OD-4).
12. **Constrained-`str` declaration form (C8)** — a mutation test asserting that
    `advisory_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")` is reported as an
    unpermitted identity source by
    `test_identity_is_computed_only_through_the_permitted_substrate`, and that the
    `Annotated[str, StringConstraints(pattern=...)]` spelling is not; plus a scan
    asserting no `src` model declares a string constraint through `Field(...)` on any
    field.

## I8 — Versioning and the ADR

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
  `deterministic_checks` and `semantic_audit_refs` are C5d: they reject non-empty values.
  The fields exist so that populating them later is not a schema change; the validators
  exist so that they cannot become a de facto vocabulary before one is ratified. A
  content class attaches to them only when the catalogue is ratified.
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
   the same advisory digest. `[V]` For `ToolObservation` this is forced: closing it needs
   either nesting, which the merged rival-identity walk forbids, or an input-digest
   field, which D7 forbids. `[R]` For `CandidateAdvisory` it is **not** forced — it
   follows from the reference-by-id shape that **OD-4** leaves open — so under the
   current shape the candidate dispositions, eligibility Booleans and observation
   references behind `candidate_set_id` are outside the digest. Whatever stores
   advisories is responsible for the immutability of what those identifiers resolve to
   until OD-4 is resolved.
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

## Outstanding owner decisions

Four items remain for the owner. **OD-1 to OD-3 change no contract, field type,
cardinality, vocabulary or equation term**; all three are about guards and dependencies.
**OD-4 does change contract shape**, and it is the reason this document's status is
qualified in the ratification statement below.

**OD-1 — `primary_function` and `declared_strategy` are classified C5c.** Both are
described as opaque and compared for equality only, which is the C5b shape. They are
classified as free text because neither is reachable from `P_unsigned` (D9), so the NFC
hazard that motivates B9 does not apply, and the less restrictive classification cannot
reject a lawful value — a role's primary function may legitimately contain a space.
`[I]` This is a derivation from B9 and O-4, resolved here rather than left open;
reviewer confirmation is invited but implementation is not blocked on it. Reclassifying
either to C5b would be a narrowing, not a redesign.

**OD-2 — `pydantic` loads `socket`, which `test_boundaries.py` forbids.** `[V]`
Reproduced: bare `import pydantic` does not load `socket`; defining any `BaseModel`
does. Every contract here is a `BaseModel` and `pydantic>=2` is a ratified core
dependency, so the first S1 contract module fails
`test_isolated_subprocess_import_loads_no_forbidden_module`. The narrowest resolution is
to exempt exactly the transitive route — `socket` reached through `pydantic` — while
keeping the bar on any direct import in `src/`, which is the allowlist shape this
package already uses elsewhere. Dropping `socket` from `FORBIDDEN` outright would give
up a real boundary. **This must be ruled on before S1 code lands.**

**OD-3 — the O-1 guard's dependent-field set must be scoped to its bearer.** See I4.1.
`DEPENDENT_FIELDS` is pinned by equality, so scoping it to `ProposerAdvisory` is a
change to a pinned constant and should be ratified rather than adjusted in passing.

**`[R]` OD-4 — `ProposerAdvisory` references its candidates by id, and ratified D7 says
it carries them.** This is the one open decision that changes contract shape.

`[V]` Ratified D7, at
`docs/architecture/ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:333-334`, reads:

> The proposer's recommendation artifact is named **`ProposerAdvisory`**, carrying
> per-candidate **`CandidateAdvisory`** entries.

Part D specifies the opposite: `ProposerAdvisory` carries `candidate_set_id`, and the
candidates live on a separately transported `AdvisoryCandidateSet`.

`[V]` **This departure is not forced by any merged guard.** A3 forces only that
`ToolObservation` is not nested, because `content_hash` is a rival identity name. No
field of `CandidateAdvisory` is in `RIVAL_IDENTITY_FIELDS`, and that set is matched by
exact name, so nesting `CandidateAdvisory` fails nothing. Any earlier statement in this
document that the reference-by-id shape was *forced* was an over-generalisation of A3 and
is withdrawn.

**The cost of the departure, stated plainly.**

* **Identity coverage.** Under reference-by-id, `P_unsigned` covers `candidate_set_id`
  and not the candidates. An advisory's digest therefore says nothing about the
  dispositions, `is_eligible` Booleans, `observation_refs`, assumptions or uncertainties
  it was derived from. Two materially different candidate sets sharing a
  `candidate_set_id` produce byte-identical advisories. This is K.1, and under a nested
  shape it would not exist.
* **A validation split that would otherwise be unnecessary.** R-1a and R-1b, and the
  whole of E1, exist because a model validator holds an identifier and not the set. Under
  a nested shape the selection correspondence — selected id resolves to exactly one
  carried candidate, and the three dependent values equal that candidate's — is
  **locally decidable**, R-1b collapses into R-1a, and the mirrored
  `selected_candidate_id` added for decidability is no longer load-bearing for that
  purpose.
* **A second transported artifact.** `AdvisoryCandidateSet` is a top-level contract only
  because the advisory does not carry the candidates. Under a nested shape it is a nested
  public shape or disappears, and H3's contract count drops from eight to seven.
* **Deviation from a ratified decision.** D7 is ratified text. Specifying against it,
  however defensibly, is precisely what this repository's evidence rules require be
  recorded as an owner decision rather than absorbed.

**What the departure buys.** One thing, and it is real: an advisory that references its
inputs uniformly by identifier has one composition rule rather than two, so no future
reviewer has to ask why `CandidateAdvisory` is inside the digest and `ToolObservation` is
not. `[I]` That is a consistency argument, not a constraint, and it does not outrank
ratified D7 on its own.

**The two resolutions.**

1. **Restore the nesting**, as D7 says. `ProposerAdvisory` carries the candidate entries;
   `candidate_set_id` is dropped or demoted to a provenance reference; `P_unsigned` (G1)
   widens to cover the candidates; D9's identity scope and K.1's limitation are rewritten
   to cover only the remaining by-identifier inputs; R-1b folds into R-1a; H3 is
   recounted. `ToolObservation` stays referenced by id, because A3 does force that.
2. **Keep reference-by-id**, and ratify it as an amendment narrowing D7, with K.1 and
   this section standing as the recorded cost.

**Until this is decided, Part D's shape is provisional.** It is written for resolution 2
because that is what the previous revision of this document specified, and rewriting it
for resolution 1 before the owner rules would substitute one unratified shape for
another.

---

## Ratification statement

D1–D10, B2, B3 (V13), B4 (O-2), B5 (O-3), B6 (O-1), B7, B8 and B9 (O-4) are resolved,
and this document contains no placeholder: every field carries a type, a requiredness, a
nullability, a default, a cardinality, a vocabulary, a classification and an identity
participation.

**One question remains open, and it bears on contract shape: OD-4.** Whether
`ProposerAdvisory` carries its `CandidateAdvisory` entries, as ratified D7 says, or
references them through `candidate_set_id`, as Part D specifies, is an owner decision
that this document raises rather than settles. Everything in Part D other than that
composition is unaffected by it.

The status line at the head of this document reads `RATIFIED FOR S1 IMPLEMENTATION`
because it was ratified against the previous revision. **That status is now qualified**:
this document is ratified for S1 implementation subject to

* the implementation obligations in Part I, which S1 must discharge in the same change
  that introduces the surface they govern;
* OD-2 being ruled on before the first contract module lands; and
* **OD-4 being ruled on before `ProposerAdvisory` is implemented**, because the two
  resolutions produce different contracts.

`[R]` No contract module may be written against the reference-by-id shape until OD-4 is
resolved.
