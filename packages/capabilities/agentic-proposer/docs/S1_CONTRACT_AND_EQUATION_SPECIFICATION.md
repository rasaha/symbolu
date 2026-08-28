# S1 — canonical contract and equation specification

**Status:** `CONTRACT SPECIFICATION FROZEN FOR IMPLEMENTATION`
**Frozen:** 2026-08-26, by owner declaration, after independent review. The contract
surface below is closed to change: a field, type, cardinality, vocabulary, equation term
or validation rule may be altered only by a **ratified amendment** recorded in the
readiness ADR's owner-decision table, never by an implementation change reconciling this
document to code. Where code and this document disagree, this document is right.
**Ratified against:** the default branch as of PR #1474
**Package:** `ugence-agentic-proposer` (`packages/capabilities/agentic-proposer`)
**Authority:** subordinate to D1–D10 and the ratification addenda in
`docs/architecture/ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md`.

Evidence labels: `[V]` verified against this repository by execution or by reading a
named artifact committed here, `[I]` inferred or authored, `[R]` requires ratification,
or verified only against a temporary representative shape and therefore to be
re-verified against the production contract surface, `[G]` gap.

This document is the single canonical, implementation-ready S1 specification. It is
organised so that a reader can tell, for any statement, which of five categories it
belongs to:

| Part | Category |
| --- | --- |
| A | Verified repository constraints — facts about the substrate and the committed guards |
| B | Ratified requirements — owner decisions this document implements |
| C–H | The specification itself: model rules, contracts, validations, equations, identity, public surface |
| I | Implementation obligations S1 must discharge |
| J | Intentionally deferred future-stage behaviour |
| K | Residual limitations that are not locally decidable |

**OD-4 is resolved.** Ratified 2026-08-25, resolution **(a)**: `ProposerAdvisory`
carries its `CandidateAdvisory` entries, as ratified D7 says. The reference-by-id
shape — the advisory carrying only `candidate_set_id`, with the candidates reachable
solely through a separately transported `AdvisoryCandidateSet` — is the **rejected
alternative**. Part D is written for the ratified nesting. See A3, D6, D7, D9, K.1 and
the closing section.

**OD-6 is resolved.** Ratified 2026-08-27, in three parts, against an internal
inconsistency an independent implementation review found between B3, H1 and R-1b(iv).
**(i)** The S1 no-selection ceiling is enforced by a construction-time validator on
`AdvisoryCandidateSet.selected_candidate_id` (new C9), not by a refusal in
`build_proposer_advisory`, and not by dropping B3's null requirement — both alternatives
are recorded as rejected, with their costs, in C9. **(ii)** H2's exception surface gains
a fourth class, `CrossContractViolationError`, for the Part E rules that compare fields
across more than one contract instance and so cannot be decided by any single model's own
validator. **(iii)** `ProposerProcessState`'s nine-member composition, its terminal
members' shared wire values with `TerminalOutcome`, and R-4's value-based comparison are
ratified as the specification's own text rather than left for an implementation to infer.
See B3, C9, D6, the `ProposerProcessStateTransition` section, Part E's header note, H1,
H2 and H3.

**OD-7 is ratified and implemented, and ratifies a boundary rather than a
complete executable algorithm.** Ratified 2026-08-27, in eight parts, scoping the S2
boundary that removes C7 and C9: a narrow injected domain-evaluator protocol this
package does not implement; a new `DomainEvaluationOutcome` vocabulary kept separate
from `DomainCheckCompletion`; an in-package deterministic selector; new C5b
identity-bound fields on `CandidateAdvisory`, `AdvisoryCandidateSet` and
`ProposerAdvisory` binding the evaluation profile, each candidate's result and the
selector-policy identity into `P_unsigned`; two new replay functions; a fail-closed
table; and a same-change-set requirement for removing C7 and C9. Two decisions OD-7
did **not** resolve, **OD-8** (the selector's substantive ranking criterion) and
**OD-9** (the `INCONCLUSIVE`-to-terminal-outcome mapping), together with **OD-10** (the
residual completed no-selection outcome), are **ratified 2026-08-28** and recorded in
part 4 and part 7 below; OD-8 also narrowly corrects OD-7's `candidate_id` tie-break
statement. Substantive multi-candidate ranking remains deferred to a separate future
ruling. Unlike every prior owner decision, OD-7 **amends the frozen
contract surface** rather than merely clarifying it. `[V]` Part 8's transition controls
are satisfied: C7 and C9 were removed in the single change set that introduced every
replacement field, coupling validator, vocabulary member, protocol, identity mirror,
equation term, replay function, selector behaviour, exception and `I8.1`–`I8.15` test
obligation, and `src/`, `public_api.json` (39 -> 46 names) and `version.py`
(`0.1.0` -> `0.2.0`) were changed in that same change set and no earlier. See the
Owner decisions section below for the full ruling.

---

## Supersession

`packages/capabilities/agentic-proposer/docs/S1_CONTRACT_AND_EQUATION_RATIFICATION.md`,
proposed on the draft branch `claude/d2-enforcement-ratification-si5lmm` (PR #1475), is
a **rejected draft**.
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
named artifact committed in PR #1474. They bound what any S1 specification may say.

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
executed against the reference-by-id composition an earlier revision of Part D
specified, it returned `[]`.
Both runs were against temporary representative shapes rather than a declared contract
module. They are recorded here as claims to be re-verified when the first contract
module lands, not as facts about this repository's production source. `[V]` The
corrected nested-candidate graph is re-established on every run by
`tests/test_advisory_contract_shape.py`, which walks the representative shapes and
asserts `reachable & RIVAL_IDENTITY_FIELDS` is empty for both advisory roots.

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

Part D therefore **carries the nesting**. The reference-by-id shape — `ProposerAdvisory`
carrying `candidate_set_id` and the candidates living only on a separately transported
`AdvisoryCandidateSet` — was a **departure from ratified D7**, not a consequence of this
guard, and owner decision **OD-4** is resolved **(a)** in the closing section: the
nesting is restored and reference-by-id is the rejected alternative. `candidate_set_id`
remains, as the reference to the top-level `AdvisoryCandidateSet`, which stays a
top-level contract and is not itself nested.

**The corrected object graph, walked.** `[R]` Against the composition Part D now
specifies — `ProposerAdvisory` carrying `candidates: tuple[CandidateAdvisory, ...]` and
continuing to reference `ToolObservation` by id — the names nesting adds to
`ProposerAdvisory`'s reachable set are exactly `candidate_id`, `disposition`,
`requested_review_action`, `is_eligible`, `domain_check_completion`, `evaluated_at`,
`claim_refs`, `observation_refs`, `assumptions` and `uncertainties`, and
`reachable & RIVAL_IDENTITY_FIELDS` is **empty**. **No prohibited identity field becomes
reachable.** `[V]` `test_identity_field_is_exactly_the_ratified_one` is parametrised over
`ADVISORY_TYPES == ("ProposerAdvisory", "CandidateAdvisory")` and already asserts that
intersection empty for each root **independently**, so nesting adds to
`ProposerAdvisory`'s reachable set only names the committed guard already asserts clean —
which is why the result follows from that guard rather than from a new argument.
The corrected-graph run is nonetheless labelled `[R]`, per this document's evidence
convention: it is a claim about a contract surface `src/` does not yet declare, to be
re-verified when the first contract module lands.

## A4 — The lifecycle-verb scan currently matches data names

`[V]` `tests/test_role_projection_bounds.py` matches `LIFECYCLE_VERBS` as
case-insensitive stems over `_defined_names`, which includes `ClassDef` names,
`AnnAssign` targets and enum member assignments. Executed against the ratified
vocabulary, it returns
`['REVOKED', 'RoleActivationStatus', 'SUSPENDED', 'activation_status', 'expires_at']`.

**Consequence.** The ratified vocabulary in B4 cannot be expressed until the guard is
narrowed as specified in I2. `[R]` Against temporary representative shapes,
restricting the scan to callable names returned `[]` for the retained vocabulary and
still returned `['ActivateRole', 'activate', 'expire_mandate', 'reactivate',
'revoke_identity', 'suspend_role']` for lifecycle authority. That run was against
temporary representative shapes rather than a declared contract module; it is a claim to
be re-verified when the first contract module lands.

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

Because S1 could not construct `DomainCheckCompletion.COMPLETE` (C7), readiness was
`False` for every candidate S1 could construct. Therefore **S1 could not emit
`PROPOSAL`**, and the only terminal outcomes S1 could emit were `NEED_EVIDENCE`,
`ABSTAIN` and `ESCALATE`.

`[V]` **Superseded by OD-7 as to reachability, not as to the rule.** C7 is removed, so
`COMPLETE` is constructible and `PROPOSAL` is reachable. What V13 enforces is unchanged
and is now enforced as R-2 states it — **recomputed, not assumed**: readiness is
recomputed by `build_proposer_advisory` for the candidate selection resolved (this
section's own first sentence), and `ProposerProcessRecord`'s own validator enforces
R-2's locally decidable half, that `PROPOSAL` requires a selection. Equation 2's
seventh term (Part F, OD-7 part 6) is what keeps a completed-but-unsatisfied candidate
out of that path, in place of C7's structural closure.

**`[V]` OD-6(i), correcting a non-sequitur an independent review found here.** An
earlier revision of this paragraph continued "…therefore every S1 authority-facing
advisory has `selected_candidate_id = None`," offered as a consequence of the readiness
argument just given. It is not one: R-2 conditions `PROPOSAL` on selection **and**
readiness together, so barring readiness bars `PROPOSAL` specifically, but says nothing
about a selection paired with `ABSTAIN` or `ESCALATE`, and `AdvisoryCandidateSet` was
constructible in S1 with a non-null `selected_candidate_id` — S-1 and S-2 require only
that the selection resolve and be eligible, and eligibility does not require readiness.
**The null-selector ceiling is ratified separately, in OD-6(i) (C9): a non-null
`AdvisoryCandidateSet.selected_candidate_id` is structurally unconstructible in S1**, on
the same pattern C7 uses for `DomainCheckCompletion.COMPLETE`. That ceiling, not the
readiness argument above, is why every S1 authority-facing advisory has
`selected_candidate_id = None`.

This was fail-closed and intended. A stage that authorises no domain check must not be
able to reach the proposer's strongest classification, and a stage that authorises no
candidate selection must not be able to construct one. `[V]` S2 authorises both, through
the boundary OD-7 ratifies, and the fail-closed property is carried by the coupling
validators, selection-policy v1 and the two replay functions rather than by the two
removed ceilings.

**Nesting changed nothing here.** OD-4(a) puts the candidate entries inside
`ProposerAdvisory` and inside `P_unsigned`. It supplied no `DomainCheckCompletion`
producer, so C7 still made `COMPLETE` unconstructible, and neither a selection nor
`PROPOSAL` became reachable in S1. Carrying a candidate is not selecting one — a
statement OD-7 does not weaken: `[V]` what makes a candidate selectable now is
selection-policy v1's recomputation over the set's own members, not its presence in the
set.

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
the referenced `AdvisoryCandidateSet` and checks correspondence against it. The local
validator does not, and cannot, establish the second. `[I]` OD-4(a) makes the advisory
carry its own nested candidates, so *some* of what R-1b once had to reach for — that the
selector resolves to exactly one carried candidate, and that the two dependent values
equal that candidate's — is now locally decidable; but the referenced
`AdvisoryCandidateSet` is still a separate artifact, so correspondence **with it**
remains cross-contract and R-1b does not collapse into R-1a.

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

**C5b fields:** `agent_version`; `tool_name`; each element of
`allowed_source_scopes`, `excluded_data_classes`, `permitted_tool_scopes` and
`tool_invocations`; and, since OD-7 part 5, `domain_evaluation_profile_id`,
`domain_evaluation_profile_version`, `selection_policy_id` and
`selection_policy_version` on **both** `AdvisoryCandidateSet` and `ProposerAdvisory`.
Each of those four is matched by equality — the profile pair against an independently
supplied expected profile, the policy pair against this package's own ratified selector
identity — rather than carried and compared whole, which is what makes them C5b and not
C5a.

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
populating it later is not a schema change — the element stays `str`, the default stays
`[]`, and only a content class is added — and it is closed now so that it cannot become a
de facto vocabulary before one is ratified (Part J).

**C5d fields:** `AdvisoryCandidateSet.selection_reason_codes`,
`ProposerAdvisory.reason_codes`, `ProposerProcessRecord.deterministic_checks`,
`ProposerProcessRecord.semantic_audit_refs` and `ProposerProcessRecord.reason_codes`.

`[I]` **The five are not all reason-code fields, and each awaits its own catalogue.**
`selection_reason_codes` and the two `reason_codes` fields await a reason-code catalogue;
`ProposerProcessRecord.deterministic_checks` names checks that were run and awaits a
catalogue of those; `ProposerProcessRecord.semantic_audit_refs` holds references to audit
records and awaits a reference scheme for them. Neither of the last two is a reason code,
and ratifying a reason-code catalogue would tell an implementer nothing about either.
What the five share is the *mechanism*, not the catalogue.

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

## C7 — Domain completion was structurally unconstructible (removed by OD-7 part 8)

`DomainCheckCompletion` is exactly `NOT_EVALUATED` and `COMPLETE`.

`[V]` **C7's validator is removed.** The rule this section states is the S1 ceiling, and
it is recorded here rather than deleted because the reasoning is what OD-7 part 8's
handover is a handover *of*. What stood: `CandidateAdvisory` carried an explicit
validator that **rejected `COMPLETE` unconditionally**, on every path, including
`model_construct` followed by validation and direct construction by any caller who
could import the name.

`COMPLETE` was defined then so that the enum was closed and Equation 2 was total, and so
that adding a domain evaluator later was not a vocabulary change. It became
constructible through the separately ratified S2 domain-evaluator boundary OD-7 states,
which removed this validator as an explicit, reviewed act — in the same change set that
added `DomainEvaluationOutcome`, the coupled `CandidateAdvisory.domain_evaluation_
outcome` field, the `AdvisoryCandidateSet`/`ProposerAdvisory` profile and policy fields,
the `DomainEvaluationProvider` boundary, both replay functions and Equation 2's seventh
term. **What took over C7's fail-closed role** is the completion/outcome coupling
(present iff `COMPLETE`, absent iff `NOT_EVALUATED`) together with that seventh term:
`COMPLETE` can no longer be asserted with no bound evaluation result to check it
against, and a completed-but-unsatisfied candidate can no longer reach `PROPOSAL`.

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

## C9 — Selection was structurally unconstructible in S1 (OD-6(i); removed by OD-7 part 8)

`[V]` **C9's validator is removed, in the same change set that removed C7's.** What
stood: `AdvisoryCandidateSet` carried an explicit validator that **rejected a non-null
`selected_candidate_id` unconditionally**, on every path, including `model_construct`
followed by validation and direct construction by any caller who could import the name.
It was the same pattern C7 used for `DomainCheckCompletion.COMPLETE`, and the placement
reasoning below is preserved because it is what the handover replaces.

**What took over C9's fail-closed role**, at the same construction point and in the same
`pydantic.ValidationError` form: the two `AdvisoryCandidateSet` couplings (the
evaluation-profile pair present iff some candidate is `COMPLETE`; the selector-policy
pair present iff a candidate is selected, and naming this package's own ratified
selector) and **selection-policy v1's recomputation** — a non-null selector is
constructible exactly when the ratified policy produces it over the set's own members,
and refused otherwise. The ceiling is narrower than C9's and strictly stronger than what
C9 could offer at S2: C9 barred every selection; this bars every selection the ratified
policy did not make. `verify_deterministic_selection` re-establishes the same rule
independently on replay, on B2's terms.

**Why the ceiling sits here rather than at the builder.** OD-6(i) considered three
mutually exclusive placements and rejected two:

* **Rejected — refuse at `build_proposer_advisory` only.** `AdvisoryCandidateSet` stays
  permissive and the advisory builder raises on a non-null selector. This leaves a
  public contract — `AdvisoryCandidateSet` with a selection — that is constructible but
  unusable by any S1 builder: a dead end reachable through the public API. It would also
  have required recasting H1's non-null-selector paragraph as S2-only by amendment, new
  test coverage for the refusal, and an explicit statement that `build_advisory_revision`
  inherits it — three amendment obligations this placement avoids entirely, because the
  ceiling is enforced once, upstream, and both builders inherit it structurally.
* **Rejected — derive faithfully and drop B3's null requirement where the set carries a
  selection.** R-2 permits this (readiness, not selection, gates `PROPOSAL`), but it
  would let S1 emit a `requested_review_destination_role_ref` for which no S1 contract
  specifies a source, and would have required amending this ADR's ratified decision
  record, not only the specification.
* **Ratified — refuse at `AdvisoryCandidateSet` construction.** No dead-end object
  exists: a caller who supplies a selection never obtains a constructed set to pass to a
  builder in the first place. The refusal is a `pydantic.ValidationError`, inside H2's
  declared exception surface, at the point the caller errs. `build_proposer_advisory` and
  `build_advisory_revision` both inherit the ceiling with no separate builder-side check,
  because neither can ever receive a set that violates it. **Cost, accepted:** S-1 and
  S-2 (D6) are satisfied vacuously in S1 by construction, one level earlier than B3
  already stated they were; the S2 transition removes this validator as an explicit,
  reviewed act, rather than changing a builder.

`selected_candidate_id` was defined as `str | None`, rather than narrowed to a
`Literal[None]`, so that the field was closed by a validator naming its own removal
condition (the C7 pattern) rather than by a type that would have had to be widened at
S2. `[V]` That is why the S2 transition changed no field type: the validator was
removed and replaced, and the declaration is unchanged.

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

**Cardinality: 10 fields** — the seven below plus the three C2 common fields (`schema_version`, `tenant_id`, `created_at`). Stated in D1's form so that I5's pinned registry can be checked
for completeness by exact membership.

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

## D3 — `WorkMandate`

**Cardinality: 9 fields** — the six below plus the three C2 common fields (`schema_version`, `tenant_id`, `created_at`). Stated in D1's form so that I5's pinned registry can be checked
for completeness by exact membership.

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

**Cardinality: 9 fields** — the six below plus the three C2 common fields (`schema_version`, `tenant_id`, `created_at`). Stated in D1's form so that I5's pinned registry can be checked
for completeness by exact membership.

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

**Cardinality: 12 fields** — the nine below plus the three C2 common fields (`schema_version`, `tenant_id`, `created_at`). Stated in D1's form so that I5's pinned registry can be checked
for completeness by exact membership.

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

**Cardinality: 12 fields** — the nine below plus the three C2 common fields (`schema_version`, `tenant_id`, `created_at`); OD-7 part 5 took this from 8 to 12. Stated in D1's form so that I5's pinned registry can be checked
for completeness by exact membership.

A top-level contract, and OD-4(a) leaves it one. `AdvisoryCandidateSet` is **not**
nested in `ProposerAdvisory` and is not demoted to a nested public shape: the advisory
carries its own nested `candidates` sequence (D7) **and** retains `candidate_set_id` as
the reference to this contract. The two must correspond exactly — membership, order and
candidate content — which is R-1b.

| Field | Type | Required | Nullable | Default | Cardinality | Vocabulary | Validation | Ownership | Identity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `candidate_set_id` | `str` | yes | no | none | 1 | open | C5a | this package | no |
| `case_ref` | `str` | yes | no | none | 1 | open | C5a | this package | no |
| `candidates` | `tuple[CandidateAdvisory, ...]` | yes | no | none | 1..n | — | **rejects an empty sequence**; `candidate_id` unique across it; **one ratified canonical order — ascending by `candidate_id`**; the builder **rejects** out-of-order caller input rather than silently reordering it | this package | no |
| `domain_evaluation_profile_id` | `str \| None` | yes (explicit) | yes | `None` | 0..1 | open | C5b when non-null; **present iff some nested candidate is `COMPLETE`** (OD-7 part 5) | this package | no |
| `domain_evaluation_profile_version` | `str \| None` | yes (explicit) | yes | `None` | 0..1 | open | C5b when non-null; coupled with `domain_evaluation_profile_id` | this package | no |
| `selected_candidate_id` | `str \| None` | yes (explicit) | yes | `None` | 0..1 | open | C5a when non-null; S-1 and S-2 below; **must equal selection-policy v1's own recomputation over `candidates`** (OD-8; replaced C9's unconditional refusal) | this package | no |
| `selection_policy_id` | `str \| None` | yes (explicit) | yes | `None` | 0..1 | open | C5b when non-null; **present iff `selected_candidate_id` is**, and must name this package's own ratified selector (OD-7 part 5) | this package | no |
| `selection_policy_version` | `str \| None` | yes (explicit) | yes | `None` | 0..1 | open | C5b when non-null; coupled with `selection_policy_id` | this package | no |
| `selection_reason_codes` | `list[str]` | yes | no | `[]` | 0..n | — | **C5d** — rejects any non-empty value | this package | no |

**Locally decidable selection invariants**, both decidable from this contract alone:

* **S-1 — resolution.** If `selected_candidate_id` is not `None`, exactly one element of
  `candidates` has that `candidate_id` — exactly one, never none and never two. Where
  this set is the one a `ProposerAdvisory` references, the same selector must also
  resolve to **exactly one** element of that advisory's own nested `candidates`
  sequence, and the two resolved candidates must be the same candidate. The second half
  is decidable only with both artifacts in hand and is therefore discharged under R-1b;
  S-1 proper is the half decidable from this contract alone.
* **S-2 — eligibility of the selection.** If `selected_candidate_id` is not `None`, the
  resolved candidate has `is_eligible is True`.

**The ordering rule is `ProposerAdvisory.candidates`' rule, stated once.** Both
sequences are ordered ascending by `candidate_id`, and neither builder reorders: an
input in any other order is rejected. `[I]` This was previously "order preserved" here
and would have been a second, weaker rule beside the nested sequence's. C6 makes list
order identity-significant, and R-1b checks order equality between the nested sequence
and this one, so two divergent ordering rules would let a caller produce a set and an
advisory that are equal in membership and content yet fail correspondence — a
correspondence failure caused by nothing but the ordering rules disagreeing. One rule on
both sides removes that. Semantic ordering a producer wants happens before construction,
never inside the identity function (C6).

**And the container is the same on both sides: `tuple[CandidateAdvisory, ...]`.** `[I]`
This field was `list[CandidateAdvisory]` while `ProposerAdvisory.candidates` was
`tuple[CandidateAdvisory, ...]`, which was a defect and not a stylistic difference.
`[V]` Verified against `pydantic 2.13.4`: a `tuple` and a `list` of the same elements
are **not** equal in Python, so any R-1b implementation that compared the two containers
directly would report a mismatch on every well-formed pair. R-1b(ii) is therefore stated
as an element-wise positional comparison, and the containers are made the same type so
that the two rules cannot drift apart again. `[V]` A9 records that `tuple` and `list`
both dump to a JSON array, so this retyping changes no canonical byte and no digest; it
is a mutability and comparability statement. `[V]` Under C1's `strict=True` a `list`
passed to this field is rejected with `tuple_type`, so the constraint is enforced at
validation rather than trusted.

`selection_reason_codes` is C5d: it rejects any non-empty value, because the reason-code
catalogue is out of scope at this stage and an unvalidated free-form code list would
become a de facto vocabulary before one is ratified.

`[I]` The converse of S-1 — "if any candidate is eligible, one must be selected" — is
**not** an invariant. Declining to select among eligible candidates is `ABSTAIN`, which
D4 ratifies. Forcing selection would convert an abstention into a recommendation.

**Under C9 (OD-6(i)) — now removed — `selected_candidate_id` was `None` for every `AdvisoryCandidateSet`
S1 can construct**, and therefore for every `ProposerAdvisory` derived from one, so S-1
and S-2 are satisfied vacuously in S1 and become load-bearing at S2.

### `CandidateAdvisory` — nested public shape

**Cardinality: 11 fields** — the eleven below; OD-7 part 5 added the eleventh,
`domain_evaluation_outcome`. It carries **no** C2 common field
(`schema_version`, `tenant_id`, `created_at`), for the reason C2 gives: it is a nested
public shape, not a ninth contract. Under OD-4(a) it is nested in **two** places — in
`AdvisoryCandidateSet.candidates` and in `ProposerAdvisory.candidates` — with the same
eleven fields in both, and R-1b requires the two copies to be equal.

| Field | Type | Required | Nullable | Default | Cardinality | Vocabulary | Validation | Ownership | Identity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `candidate_id` | `str` | yes | no | none | 1 | open | C5a; unique within its set | this package | no |
| `disposition` | `CandidateDisposition` | yes | no | none | 1 | **closed, D4**: `RECOMMEND_MATCHED_FOR_APPROVAL`, `RECOMMEND_WITHHOLD`, `REQUEST_EVIDENCE`, `ESCALATE_EXCEPTION` | enum membership | this package | no |
| `requested_review_action` | `ReviewAction` | yes | no | none | 1 | **closed, B8** | enum membership | this package | no |
| `is_eligible` | `bool` | yes | no | none | 1 | closed: `true`, `false` | **package-computed** — see Part G | this package | no |
| `domain_check_completion` | `DomainCheckCompletion` | yes | no | `NOT_EVALUATED` | 1 | **closed**: `NOT_EVALUATED`, `COMPLETE` | enum membership; gates only **whether evaluation ran**, never its result (OD-7 part 3); coupled to `domain_evaluation_outcome` below | this package | no |
| `domain_evaluation_outcome` | `DomainEvaluationOutcome \| None` | yes (explicit) | yes | `None` | 0..1 | **closed**: `SATISFIED`, `NOT_SATISFIED`, `INCONCLUSIVE` | enum membership; **present iff `domain_check_completion is COMPLETE`, absent iff `NOT_EVALUATED`** (OD-7 part 3); provider-produced, replayed by `verify_domain_evaluation` | this package | no |
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

`[R]` **No field of `CandidateAdvisory` or `ProposerAdvisory` may be typed
`SemanticAuditorFindingStatus`, and none may be assigned one.** This is a **requirement
on the unwritten contract surface**, not an observation about it: no contract module
exists, so there is no field set to have verified. It is to be verified when the first
contract module lands. `[V]` What is merged and verified is the guard:
`tests/test_no_auditor_status_projection.py` enforces D6's standing rule. `[V]` The ADR
records that the rule is not yet mechanically exercised, because S0 has no field into
which a status could be projected; S1 must add the rejecting assertion in the same
change that introduces the first such field.

#### What `CandidateAdvisory` may never carry — a standing prohibition

**`CandidateAdvisory` must not carry `content_hash`, `advisory_digest`, or any other
independently minted identity, and must not nest a `ToolObservation`.** The ten fields
above are the whole of it, and each of the following is barred:

* **`content_hash`, `advisory_digest`, `proposal_digest`, `advisory_id`, `id`, `uid`,
  `uuid`, `identity`, `identifier`, `hash`, `checksum`** — every member of
  `RIVAL_IDENTITY_FIELDS` (A3), by exact name.
* **Any renamed equivalent** — a field of any name whose value is a digest, fingerprint
  or hash of this candidate's content, or of anything else. D7 makes
  `ProposerAdvisory.advisory_digest` the **sole** identity field; a per-candidate digest
  would be a second identity inside the first, and now that the candidates are inside
  `P_unsigned` it would be a second identity **covered by** the first, which is worse
  than one standing beside it.
* **A nested `ToolObservation`, at any depth.** `[V]` A3: `ToolObservation.content_hash`
  is a rival identity name, and nesting the observation makes it reachable from
  `ProposerAdvisory` through the candidate. Nesting `CandidateAdvisory` is lawful
  **precisely because** none of its ten fields is a rival name; nesting an observation
  inside it would reintroduce through the candidate exactly what A3 bars directly.

Observation evidence stays **reference-by-id**, through `observation_refs`: each entry
is a C5a reference to a `ToolObservation.observation_id` supplied to the builder, and
R-7 requires every entry to resolve. That is the whole of the evidence link. The cost —
that the advisory's digest covers the observation *references* and not the observation
*bodies* — is real, is not closed by OD-4(a), and is recorded in K.1.

**Test obligation.** This is not a remark. I7.11 carries it: a test must assert that
`ToolObservation` is not reachable from either advisory type at any depth, and that no
field of `CandidateAdvisory` is a member of `RIVAL_IDENTITY_FIELDS` or is otherwise
digest-shaped under C6. A change that adds a per-candidate digest field, or that nests
an observation, must fail that test rather than pass unexamined.

## D7 — `ProposerAdvisory`

D7: kind `ugence.agentic_proposer.advisory.v0`; `advisory_digest` is the **sole**
identity field; identity is computed only through `ugence_jcs`; the eight barred fields
(`fingerprint`, `provider_id`, `operation`, `arguments`, `idempotency_key`,
`workflow_id`, `instance_id`, `task_id`) appear at no nesting depth; no exported name
begins with `Proposal` or `Recommendation`.

**Cardinality: 27 fields** — the twenty-four below plus the three C2 common fields
(`schema_version`, `tenant_id`, `created_at`). Stated in D1's form so that I5's pinned
registry can be checked for completeness by exact membership. `[I]` OD-4(a) took the
count to twenty-three by adding `candidates`, with `candidate_set_id` retained alongside
it rather than replaced by it; OD-7 part 5 took it to twenty-seven by mirroring
`AdvisoryCandidateSet`'s evaluation-profile and selector-policy pairs, which is what
puts them inside `P_unsigned`.

**This contract carries its candidates and references every other input by identifier.**

`[V]` A3 forces one half of that: nesting `ToolObservation` makes `content_hash`
reachable and fails the merged rival-identity walk, so observations are referenced
through `observation_refs` and never carried. The other half is now settled the other
way: **OD-4 is resolved (a)**, and `ProposerAdvisory` carries per-candidate
`CandidateAdvisory` entries as ratified D7 says. `[V]` No guard forced the reference-by-id
shape — the rival-identity walk matches by exact name and reaches no field of
`CandidateAdvisory` — so restoring the nesting removes a departure from ratified text
without conceding a guard. The field set below is written for the nested shape;
`candidate_set_id` remains as the reference to the top-level `AdvisoryCandidateSet`, and
R-1b binds the nested sequence to that set's `candidates`.

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
| `candidate_set_id` | `str` | yes | no | none | 1 | open | C5a; references `AdvisoryCandidateSet.candidate_set_id`; **R-1b** — the referenced set's `candidates` must equal `candidates` below in membership, order and candidate content | this package | yes |
| `candidates` | `tuple[CandidateAdvisory, ...]` | yes | no | none | 1..n | — | **rejects an empty sequence**; `candidate_id` unique across it; **one ratified canonical order — ascending by `candidate_id`**, the builder rejecting out-of-order caller input rather than silently reordering it; **R-1b** | this package | **yes** |
| `domain_evaluation_profile_id` | `str \| None` | yes (explicit) | yes | `None` | 0..1 | open | C5b when non-null; mirrored from `AdvisoryCandidateSet` (OD-7 part 5); **R-1b** correspondence | this package | yes |
| `domain_evaluation_profile_version` | `str \| None` | yes (explicit) | yes | `None` | 0..1 | open | C5b when non-null; mirrored; **R-1b** correspondence | this package | yes |
| `selected_candidate_id` | `str \| None` | yes (explicit) | yes | `None` | 0..1 | open | C5a when non-null; **R-1a** (local), **R-1b** (cross-contract); selection-policy v1 (OD-8) | this package | yes |
| `selection_policy_id` | `str \| None` | yes (explicit) | yes | `None` | 0..1 | open | C5b when non-null; present iff `selected_candidate_id` is; mirrored; **R-1b** correspondence | this package | yes |
| `selection_policy_version` | `str \| None` | yes (explicit) | yes | `None` | 0..1 | open | C5b when non-null; mirrored; **R-1b** correspondence | this package | yes |
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
`proposal_digest`. That holds of the nested `candidates` sequence too, and the standing
prohibition under D6 keeps it holding: no `CandidateAdvisory` field may be a rival
identity name or a renamed digest, and no `ToolObservation` may be nested inside one.

**`candidates` is an immutable deterministic sequence.** It is `tuple[...]`, not `list`,
on a `frozen=True` model (C1): a stored advisory's candidate sequence cannot be mutated
in place after the digest is computed. `[V]` A9: `tuple` and `list` both dump to a JSON
array, so the choice of `tuple` changes no canonical byte and is a mutability statement,
not an encoding one. Order is identity-significant under C6, and the ordering rule is
the ratified ascending-`candidate_id` order stated once under D6.

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

**Cardinality: 18 fields** — the fifteen below plus the three C2 common fields (`schema_version`, `tenant_id`, `created_at`). Stated in D1's form so that I5's pinned registry can be checked
for completeness by exact membership.

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

### `declared_strategy` — an assertion, and only an assertion (OD-5)

The field carries **the method the process record asserts was used**. Four properties
hold together, and dropping any one of them makes the field read as more than it is:

* **It is metadata outside `P_unsigned`.** `ProposerProcessRecord` is not referenced by
  `ProposerAdvisory` and is not reachable from it (D9), so `declared_strategy` is not
  covered by `advisory_digest` and no value it takes can change an advisory identity.
* **Declaration does not establish conformance.** The value states what the producer
  says it did. It is not evidence that the producer did it, and nothing in this stage
  compares the declaration against the process it describes. `[I]` A record whose
  `declared_strategy` names one method and whose work followed another is a **truthful
  record of a false declaration**: it is well-formed under every rule in this document,
  and this document supplies nothing that would detect it.
* **S1 neither selects, validates nor cryptographically binds a reasoning strategy.**
  It does not choose a method, does not check the declared value against any permitted
  set — no S1 contract carries one — does not check it against a vocabulary, and does not
  bring it inside any digest.
* **Strategy selection and enforcement are S2.** Both are deferred in whole, together
  with the permission concept a declaration would be checked against (Part J). `[R]` The
  correspondence between a declaration and a role's permitted set is an S2 obligation and
  is recorded here as a boundary, not as a rule this stage enforces.

`[I]` OD-1 classifies `declared_strategy` C5c, which is consistent with all of this and
is a separate matter: C5c is why the field carries no pattern, and the four properties
above are why it carries no authority.

### The four-way distinction (OD-5)

Four things are routinely collapsed into one another, and each is a different kind of
statement made by a different party. They are stated together once, here, because no
single contract table shows all four:

| | Where it lives | What it is | Who asserts it |
| --- | --- | --- | --- |
| `primary_function` | `CognitiveRoleContract` (D2) | the role's **organizational purpose** — what the role is *for* | external role owner |
| a role's **permitted reasoning strategies** | **nowhere in S1 — an S2 concept** (Part J) | the **methods the role may select among** when it works | external role owner, at S2 |
| `declared_strategy` | `ProposerProcessRecord` (D8) | the **method the process record asserts was used** on this occasion | this package, on the producer's word |
| `terminal_outcome` | `ProposerProcessRecord` (D8) | the **terminal outcome** the work reached | this package, structurally constrained by R-2 and R-4 |

The first is a purpose and not a method. The second is a permission and not a claim
about what happened. The third is a claim about what happened and not a permission, and
under the preceding subsection not evidence either. The fourth is where the work ended
and says nothing about how it got there.

`[V]` **Only three of the four are S1 fields.** The second is named here as a *concept*,
so that the distinction can be stated whole and so that an implementer does not read
`primary_function` or `declared_strategy` as carrying the permission. **S1 declares no
field for it**, `CognitiveRoleContract`'s cardinality is unchanged at 10, and the concept
arrives at S2 with the vocabulary that gives it content (Part J, OD-5(iii)).

**What is *not* a reasoning strategy.** Evidence collection, verification, and
abstention or escalation are named here because each is regularly mistaken for one:

* **Evidence collection** is a contract mechanism. It is `ToolObservation` (D5),
  `observation_refs`, and R-7's resolution obligation.
* **Verification** is a contract mechanism. It is Equation 4, `verify_advisory_identity`,
  `verify_advisory_selection` and E2's replay of observation resolution.
* **Abstention and escalation** are **outcomes**, not methods: `ABSTAIN` and `ESCALATE`
  are members of the `TerminalOutcome` vocabulary constrained by R-2 and R-4.

`[I]` The distinction is load-bearing rather than tidy. Each of the three is already
specified, enforced and — for the third — closed by a ratified vocabulary. Treating any
of them as a method the role selects would recast a mechanism this stage enforces, or an
outcome this stage constrains, as a matter of permitted method, and would make a role's
freedom to *abstain* look like a choice of approach rather than the structural rule R-2
makes it. `[R]` The point is recorded for whoever ratifies the S2 vocabulary: none of the
three belongs in it.

### `ProposerProcessStateTransition` — nested public shape

**Cardinality: 2 fields** — the two below. It carries **no** C2 common field, for the
reason C2 gives for `CandidateAdvisory`: it is a nested public shape, not a contract.

| Field | Type | Required | Nullable | Default | Validation |
| --- | --- | --- | --- | --- | --- |
| `state` | `ProposerProcessState` | yes | no | none | enum membership |
| `at` | `datetime` | yes | no | none | C4; caller-supplied |

**`ProposerProcessState` is closed, nine members (OD-6(iii)):** `RECEIVED`,
`VALIDATED`, `OBSERVING`, `RECONCILING`, `EVALUATING` — the five process states R-3's
chain names before its terminal position — plus `PROPOSAL`, `NEED_EVIDENCE`, `ABSTAIN`,
`ESCALATE` — the four terminal states the same chain names in its final position, which
are exactly `TerminalOutcome`'s four members.

**`[V]` OD-6(iii), ratifying what R-3 and R-4 entail but do not, by themselves,
spell out.** R-3 (Part E) names all nine spellings in the chain
`RECEIVED → VALIDATED → OBSERVING → RECONCILING → EVALUATING → {PROPOSAL, NEED_EVIDENCE,
ABSTAIN, ESCALATE}`, and the `state` field above was already typed `ProposerProcessState`
exactly, so the nine-member *membership* was already entailed and is not a new decision.
What R-3 and R-4 left unstated, and what this amendment settles: **the four terminal
members carry exactly `TerminalOutcome`'s wire values**, so
`ProposerProcessState.PROPOSAL == TerminalOutcome.PROPOSAL` and the corresponding pair
for `NEED_EVIDENCE`, `ABSTAIN` and `ESCALATE` compare equal and serialise identically —
and **R-4's "equals" is value equality**: `terminal_outcome == state_transitions[-1].state`
on the shared wire value, not equality of enum identity or member name. A record whose
`terminal_outcome` disagrees with the terminal `ProposerProcessState` fails R-4 exactly
when the two values differ; it does not fail merely because the two names come from
different enum classes. `pydantic`'s `strict=True` still refuses to substitute one enum
for the other at *validation* — a `ProposerProcessStateTransition.state` may not be
assigned a `TerminalOutcome` member or vice versa — so the shared values do not weaken
either field's own type constraint; they settle only what R-4 compares.

**Ratification, not reconciliation.** `docs/S1_ENFORCEMENT.md` and this package's test
suite previously recorded the cardinality and comparison basis as an open question this
document had to settle before a test could decide it. This paragraph is that settlement,
recorded here as the amendment requires; it is not a description of code already written
reconciled backward into the specification.

### What the forward-only record does not represent (R-3, OD-5)

R-3 makes `state_transitions` a **subsequence** of a single forward chain: no backward
transition, no repeat, at most one terminal state and only in final position. That
shape is **deliberate, and it is a property of the record, not a claim about the work.**

**The record represents the process's progress through its stages. It does not represent
internal strategy control flow, and it is not capable of representing it.** There is no
state for iterating, no state for branching, no state for revisiting, and R-3 forbids
the two spellings — a repeat and a backward step — by which a forward-only vocabulary
could otherwise have approximated either.

`[I]` The consequence must be stated explicitly, because the natural reading of a
forward-only list is the wrong one: **the absence of repeated or branching transitions
in a conformant record is not evidence that no internal iteration or branching
occurred.** A producer that revisited its evidence, explored several lines and discarded
all but one, or re-entered a stage it had already left, produces exactly the same
`state_transitions` as one that proceeded straight through — because R-3 admits only
that spelling from either. A reader who infers a linear process from a linear record has
inferred something the record cannot say. Whether internal iteration occurred, and what
it was, is not recorded at this stage by any field: `declared_strategy` names a method
and does not describe an execution, and no other field in D8 carries control flow.

`[I]` This is also why R-3's bar on *any* representation of execution state is not
weakened by OD-5. Reasoning strategies are **method labels that operate within** the
R-3 lifecycle; they do not add states to it, reorder it, branch it or make it
re-entrant. A ratified strategy vocabulary would change what a role may declare, and
would change nothing about `ProposerProcessState`, R-3 or R-4.

## D9 — Identity scope, stated once

`P_unsigned` covers `ProposerAdvisory` **and everything reachable from it**, which under
OD-4(a) means the advisory's own fields **plus every field of every `CandidateAdvisory`
in its nested `candidates` sequence**. Nothing else. The seven other top-level
contracts — `AgentIdentityRef`, `CognitiveRoleContract`, `WorkMandate`,
`BoundedContextEnvelope`, `ToolObservation`, `AdvisoryCandidateSet` and
`ProposerProcessRecord` — are **inputs to** and **referents of** an advisory; they are
not inside its identity.

**What the candidates bring inside.** Each nested candidate's `candidate_id`,
`disposition`, `requested_review_action`, `is_eligible`, `domain_check_completion`,
`evaluated_at`, `claim_refs`, `observation_refs`, `assumptions` and `uncertainties` are
covered by `advisory_digest`. Changing any one of them, or reordering the sequence
(C6), changes the digest. Two advisories that recommend differently, or that rest on
different eligibility Booleans or different evidence references, can no longer be
byte-identical.

`[I]` The residual cost, stated plainly: for what is still referenced, an advisory's
digest binds the *identifiers* of its inputs, not their *contents*. Two different
`WorkMandate` bodies carrying the same `mandate_id` yield the same advisory digest, and
the same holds of `context_id`, `role_contract_id`, `agent_id` and `candidate_set_id`.

`[V]` For `ToolObservation` that cost is **forced**: A3 bars nesting it, and an
input-digest field would be a second identity, which D7 forbids. It is not closed by
OD-4(a) and it is not closeable here; it stays open in K.1.

`[V]` For `CandidateAdvisory` it was **never** forced — A3 does not bar nesting it, and
ratified D7 says it is carried — and OD-4(a) closes it. The candidate content is inside
`P_unsigned`, and a `candidate_set_id` shared by two materially different sets no longer
yields the same advisory: the advisory carries the candidates it was derived from, and
they are in the digest.

`[I]` R-1b does **not** collapse into R-1a as a result. The nested copy makes the
selection correspondence locally decidable *within the advisory*; correspondence with
the separately transported `AdvisoryCandidateSet` still requires that set in hand. See
E1.

---

# Part E — Cross-contract validations

Each is a validation S1 must implement at construction. Those marked *(equation term)*
also appear in Equation 1; they are listed here once as contract obligations.

**`[V]` OD-6(ii): which exception a Part E rule's failure raises depends on whether it
is decidable from one contract instance or requires more than one, and this line was
missing from H2.** R-1a, R-2, R-3, R-4, and the local half of R-1b ((v), (vi), and the
local half of (vii)) are each decidable from a single already-constructed model's own
fields, are implemented as that model's own validator, and their failure is therefore a
`pydantic.ValidationError` exactly as H2's first row already stated. **R-1b's remaining
clauses ((i)–(iv), (viii), (ix)) and R-5, R-6, R-7, R-9 and R-10 are not**: each compares
fields across two or more independently constructed contract instances that no single
model's validator can see at once, so a builder function — not a model — is where the
comparison happens. H2 previously had no exception type for that residual class and the
implementation raised a bare `ValueError`, which is not one of H2's three declared
classes. `CrossContractViolationError` is that fourth class, defined in H2 for exactly
this residue.

| Id | Rule | Prevents |
| --- | --- | --- |
| R-1a | **Selection binding — local (B6).** A `ProposerAdvisory` model validator enforces: if `selected_candidate_id is None`, then `recommended_disposition`, `requested_review_action` and `requested_review_destination_role_ref` are **all** `None`; if `selected_candidate_id is not None`, those three are **all** non-null. Decidable from this contract's own fields alone | a routing request standing next to no selection, and a selection with no routing — two failure modes that call for opposite responses |
| R-1b | **Candidate and selection binding — cross-contract (B6, OD-4(a)).** `build_proposer_advisory` and `verify_advisory_selection` each resolve the referenced `AdvisoryCandidateSet` and enforce **correspondence of the candidates, not selector equality alone**: (i) `ProposerAdvisory.candidates` and `AdvisoryCandidateSet.candidates` are equal in **membership** — the same `candidate_id` set, no extra, no missing; (ii) equal in **order**, compared **element by element at each position** — for `i` in `0..n-1`, the element at position `i` of one sequence is compared with the element at position `i` of the other — after **both** sequences have independently been checked to satisfy the same ascending-`candidate_id` invariant (D6). The comparison is never a single equality between the two containers: `[V]` a `tuple` and a `list` of identical elements compare unequal in Python, and both sides are `tuple[CandidateAdvisory, ...]` precisely so that no implementation is tempted to rely on container equality across differing types. Lengths are compared first, so a shorter or longer sequence is a membership failure under (i) rather than a truncated positional walk; (iii) equal in **candidate content** — for each position, all ten `CandidateAdvisory` fields compare equal, so a disposition, an `is_eligible` Boolean, an `observation_refs` list, an `evaluated_at` or a free-text entry that differs is a mismatch; (iv) `ProposerAdvisory.selected_candidate_id == AdvisoryCandidateSet.selected_candidate_id`; (v) when that selector is non-null it identifies **exactly one** element of `ProposerAdvisory.candidates` **and exactly one** element of `AdvisoryCandidateSet.candidates`, and those two are the same candidate; (vi) `recommended_disposition` equals the **selected nested candidate's** `disposition`; (vii) `requested_review_action` equals the **selected nested candidate's** `requested_review_action` and is a member of `CognitiveRoleContract.permitted_review_actions`; (viii) `requested_review_destination_role_ref` is consistent with that candidate's routing; and (ix) tenant, case and candidate-set references are continuous. A failure is a rejection: the builder raises **`CrossContractViolationError` (H2, OD-6(ii)) for (i)–(iv), (viii) and (ix)**, and `pydantic.ValidationError` for the locally-decidable (v), (vi) and the local half of (vii); the verifier returns `False` for all of them | an advisory whose carried candidates differ from the set it names, and an advisory whose routing contradicts, or invents, the candidate it claims to select |
| R-2 | **V13 (B3).** `terminal_outcome is TerminalOutcome.PROPOSAL` **if and only if** `selected_candidate_id is not None` **and** `evaluate_readiness(...) is True` for the resolved candidate, recomputed at construction | a "proposal" that proposes nothing, a selection presented as an abstention, and a proposal made without domain readiness |
| R-3 | **Process ordering.** `state_transitions` is a subsequence of `RECEIVED → VALIDATED → OBSERVING → RECONCILING → EVALUATING → {PROPOSAL, NEED_EVIDENCE, ABSTAIN, ESCALATE}`: no backward transition, no repeat, at most one terminal state and only in final position, and `at` non-decreasing across the list | a fabricated or reordered process history, and — since no execution state exists in the enum — any representation of execution |
| R-4 | `terminal_outcome` on the process record equals **(by value; OD-6(iii))** the terminal `ProposerProcessState` when one is present in `state_transitions` | a record whose narrative and outcome disagree |
| R-5 | **Tenant scope.** `tenant_id` is identical across `AgentIdentityRef`, `CognitiveRoleContract`, `WorkMandate`, `BoundedContextEnvelope`, `AdvisoryCandidateSet`, `ProposerAdvisory` and **every** `ToolObservation` supplied to a builder. Cross-contract; raises `CrossContractViolationError` (H2, OD-6(ii)) | **cross-tenant acceptance** |
| R-6 | **Case scope.** `case_ref` is identical across `WorkMandate`, `AdvisoryCandidateSet`, `ProposerAdvisory` and **every** `ToolObservation` supplied to a builder. Cross-contract; raises `CrossContractViolationError` (H2, OD-6(ii)) | **cross-case acceptance** |
| R-7 | **Reference resolution, at construction and on replay.** Every `observation_refs` entry — on every nested candidate and on the advisory itself — resolves to **exactly one** supplied `ToolObservation.observation_id`, and the resolved observation satisfies tenant, case and context continuity. Enforced by `build_proposer_advisory` at construction **and independently re-established on replay** by `verify_observation_resolution`, which `verify_advisory_selection` invokes. It is **not** a builder-only rule; the replay algorithm is specified in E2. Cross-contract; the builder raises `CrossContractViolationError` (H2, OD-6(ii)), the replay verifiers return `False` | a reference to evidence that was never supplied, evidence substituted after signing, and a reference that resolves ambiguously or not at all |
| R-8 | **Uniqueness.** `observation_id` unique across supplied observations; `candidate_id` unique across `candidates`; no duplicates in `observation_refs`, `candidate_ids`, `permitted_tool_scopes`, `permitted_candidate_dispositions`, `permitted_review_actions` or `allowed_source_scopes` | an identifier resolving ambiguously to two objects, and a list that overstates its breadth |
| R-9 | **Envelope binding.** `BoundedContextEnvelope.mandate_id == WorkMandate.mandate_id` *(equation term)*. Cross-contract; raises `CrossContractViolationError` (H2, OD-6(ii)) | an envelope assembled for a different mandate |
| R-10 | **Role binding.** `WorkMandate.assigned_role_contract_id == AgentIdentityRef.bound_role_contract_id == CognitiveRoleContract.role_contract_id` *(equation term)*. Cross-contract; raises `CrossContractViolationError` (H2, OD-6(ii)) | a mandate matched against an unrelated role or agent |
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
`build_proposer_advisory` at construction and **independently re-established** by
`verify_advisory_selection`, each of which is given the `AdvisoryCandidateSet`, the
`CognitiveRoleContract` and the observations, and each of which resolves the selection
and checks correspondence itself. This mirrors B2 exactly: construction is
defence-in-depth, and independent replay is the guarantee.

`[I]` **R-1b survives OD-4(a), and grows.** Under the nested shape the advisory carries
its own candidates, so R-1b is no longer only about a selector: it is a **correspondence
check between two copies of the same candidate list**, one inside the advisory's digest
and one on the separately transported set, checked for equal membership, equal order and
equal candidate content, not selector equality alone. It cannot fold into R-1a, because
R-1a still holds only the advisory.

**What happens if the referenced set is later amended.** This is the case R-1b is for,
and the answer is that **replay fails rather than silently re-resolving**:

* The stored advisory's `advisory_digest` covers its **own nested copy** of the
  candidates (D9, G1). Amending the `AdvisoryCandidateSet` behind `candidate_set_id`
  changes nothing about the stored advisory and cannot change its digest.
  `verify_advisory_identity` therefore still returns `True` — correctly, because the
  bytes that were signed are unaltered.
* `verify_advisory_selection`, given the amended set, finds the two candidate lists
  unequal in membership, order or content, and returns **`False`**. A caller acting on
  the advisory's routing must call both functions (H1); the amendment surfaces as a
  correspondence failure, not as a quietly different answer.
* There is no re-resolution path. Nothing reads the amended set and substitutes its
  candidates for the stored ones: the advisory's candidates are the advisory's, fixed at
  construction and immutable (`frozen=True`, `tuple`). An amended set makes replay fail
  **loudly**; it never re-derives the recommendation.
* `[I]` This is a strengthening, not a new obligation on storage. Under the rejected
  reference-by-id shape an amended set would have produced a digest-valid advisory whose
  candidates could not be checked at all, which is why K.1 previously made whatever
  stores advisories responsible for the immutability of what `candidate_set_id` resolves
  to. That responsibility is now discharged by the contract for candidates. It still
  stands for every input that remains referenced by identifier.

`[I]` The mirrored `selected_candidate_id` on `ProposerAdvisory` exists to make R-1a
decidable at all: without it the advisory would carry three selection-dependent fields
and no selector, so the coupling could not be checked on the advisory in isolation and
would be enforceable only by a builder a consumer has no way to audit. That reasoning is
independent of OD-4 and is unaffected by its resolution — it was never a consequence of
A3, which forces only that `ToolObservation` is not nested. Because the field is
identity-participating, a stored advisory also carries the selection it claims into its
digest, so replay can detect a selector altered after signing.

**Under V13 (B3), S1 sets `selected_candidate_id` and all three dependents to `None`.**
The non-null branch is specified so that it is a behaviour change at S2 rather than a
contract change, and it is not reachable in S1: `build_proposer_advisory` derives all
four from the candidate set, and B3 makes a selection unconstructible.

`[I]` R-5 and R-6 are **contract validators, not Equation 1 terms.** The owner's
Equation 1 checks tenant equality across the four principal contracts and does not
reach the observations. Rejecting a cross-tenant or cross-case observation at
construction closes that without altering the ratified equation.

## E2 — R-7 on replay: the observation resolution algorithm

R-7 is **not** a builder-only limitation. B2's rule is that construction is
defence-in-depth and independent replay is the guarantee, and an evidence reference
that only the builder ever checked is exactly the shape B2 refuses. R-7 therefore has a
replay counterpart, `verify_observation_resolution`, which takes the **complete
observation collection** and is invoked by `verify_advisory_selection` (H1).

**Input.** The advisory, the `CognitiveRoleContract`, the `BoundedContextEnvelope`, and
`observations` — the complete collection the caller holds, not a pre-filtered subset.
`[I]` Passing a pre-filtered subset is the defect the algorithm exists to prevent: a
caller who filters to "the observations this advisory references" and then checks that
each reference is present has verified nothing, because the filter constructed the
answer. The resolver is given everything and does the resolution itself.

**Algorithm.** Let `required` be the concatenation of the advisory's own
`observation_refs` with the `observation_refs` of **every** nested candidate — every
reference, in order, including duplicates across candidates.

1. **Index, detecting ambiguity.** Group `observations` by `observation_id`. Any id
   holding more than one observation is an **ambiguous resolution** and is a refusal in
   itself, before any reference is looked up. R-8's uniqueness rule is thereby
   re-established on replay rather than assumed from construction.
2. **Resolve every required reference — each one, not a membership test.** For each
   entry of `required`: it must resolve to **exactly one** observation. Zero is a
   **dangling reference**; more than one is **ambiguous**. Both are refusals. `[I]` The
   quantifier is "exactly one", not "at least one", and the walk is over `required`
   rather than over `observations`, so no reference can be skipped and none can be
   satisfied by a set-membership shortcut.
3. **Check continuity on each resolved observation.** `tenant_id` equals the advisory's
   (R-5); `case_ref` equals the advisory's (R-6); and `source_ref` is a member of
   `BoundedContextEnvelope.allowed_record_refs` (context continuity). A **substituted**
   observation — same `observation_id`, different body — fails here if it moved tenant,
   case or source, and is caught by the observation's own `content_hash` under its
   producer's verification otherwise (K.1).
4. **An extra supplied observation is not evidence.** Any `observation_id` in
   `observations` that appears in no entry of `required` is **unreferenced**. It is not
   an error — a caller may hold more observations than one advisory uses — but it is
   **not advisory evidence**, contributes nothing to any equation term, and must be
   reported as unreferenced rather than silently absorbed. `[I]` Equation 1 already
   evaluates its quantified terms over `referenced`, not over `observations`; this makes
   the same boundary explicit on the replay side, so an extra observation cannot be
   presented afterwards as something the advisory rested on.
5. **Refuse in a typed way.** A missing, substituted, duplicated or ambiguously resolved
   observation causes a typed refusal naming which reference failed and how — dangling,
   ambiguous, or a named continuity break. `verify_observation_resolution` **returns
   `False`** on the same terms as `verify_candidate_eligibility` and
   `verify_advisory_selection`, and reports the failing references; the **builder**
   raises. A silent `True`, or a refusal that does not say which reference failed, is
   not conformant.

**Vacuity is bounded, not accidental.** A candidate with an empty `observation_refs`
contributes no entry to `required`, and Equation 1's `ContextAllowed` and `ToolsAllowed`
pass trivially for it — the owner's 0..n cardinality, recorded in K.4. What this
algorithm forbids is the different thing: a **non-empty** reference list passing because
nothing resolved it. `[V]` Verified on the specified algorithm against a representative
resolver: a well-formed pair passes; a dangling reference, a duplicated
`observation_id`, an observation substituted to another tenant, and an observation whose
`source_ref` is outside `allowed_record_refs` are each refused with the failing
reference named; and an extra supplied observation passes while being reported
unreferenced.

**What replay does and does not establish.** It establishes that the advisory's
references resolve, unambiguously and continuously, to the observations the caller
holds. It does **not** establish that those observation *bodies* are the ones the
proposer saw: the observations are referenced, not nested, so their content is outside
`P_unsigned` and outside `advisory_digest` (A3, D9). Each observation's own
`content_hash`, minted and verified by its producer under D5, is what binds its content.
Any claim that `verify_advisory_selection` or `verify_advisory_identity` binds
observation content is **false** and must not appear in S1 documentation, tests or
commit messages. The residue is K.1.

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
| `DomainEvaluationSatisfied` | `candidate.domain_evaluation_outcome is DomainEvaluationOutcome.SATISFIED` — **added by OD-7 part 6 and implemented**. It is what closes R-2's `PROPOSAL` path now that C7 no longer does: a `COMPLETE` candidate whose evaluation concluded `NOT_SATISFIED` or `INCONCLUSIVE` returns `False` here |

```python
return all((Eligible, RequiredFieldsPresent, ObservationRefsPresent,
            UncertaintyDisclosed, LineageComplete, DomainChecksComplete,
            DomainEvaluationSatisfied))
```

**This returned `False` for every candidate S1 could construct**, because C7 made
`COMPLETE` unconstructible. That was intended and fail-closed pending the separately
ratified S2 domain evaluator OD-7 states, and it is what made B3 bite. `[V]` With C7
removed, the equation is `True` exactly for a candidate that is eligible, has matching
lineage, discloses its uncertainties, meets `ObservationRefsPresent`, and whose
evaluation both **ran** (`DomainChecksComplete`) and **concluded `SATISFIED`**
(`DomainEvaluationSatisfied`). The two are separate terms because they are separate
facts, and Part F's **No term compensates for another** rule is what forbids the second
being read off the first.

`[V]` **Why `DomainEvaluationSatisfied` is a term and not an orchestration
convention.** OD-7's first draft held that Equation 2 needed no amended term, on the
ground that `evaluate_readiness` is invoked only after selection and only on the
selected candidate, which selection already requires to be `SATISFIED`. That ground
does not hold against the repository. `evaluate_readiness` is an **exported public
symbol** (`equations.py:32`'s `__all__`, `__init__.py:106`, and `public_api.json`)
with **no caller anywhere in `src/`**: the ordering is a convention this package
states, not one it can impose on a consumer who imports the function and calls it
directly. With C7 removed, a candidate carrying `domain_check_completion is
COMPLETE`, `domain_evaluation_outcome is NOT_SATISFIED` (or `INCONCLUSIVE`),
`is_eligible is True` and matching lineage would make `evaluate_readiness` return
`True` — which is exactly R-2's condition for `terminal_outcome=PROPOSAL`. `[V]` It
does not, because the term is implemented; `I8.10` exercises both directions against
the exported function and mutation-tests the six-term form, which must fail.

`[V]` **Precisely when that became reachable.** V13 as implemented before this change
set was a **blanket** refusal of `PROPOSAL`, not a recomputation:
it rejects the value unconditionally and never calls `evaluate_readiness` — the only
occurrence of that name in `contracts.py` is inside its error message. It can be
blanket precisely because C7 makes `COMPLETE` unconstructible, which its own docstring
says. R-2 (Part E) is the ratified rule V13 stands in for, and it requires readiness to
be **recomputed at construction**. So the exposure does not open on C7's removal alone;
it opens in the same change set, when V13 is reimplemented to enforce R-2 as ratified
against candidates that can now carry `COMPLETE`. Since OD-7's transition controls
(part 8) require exactly that to happen together, the distinction changes when the hole
appears, not whether: leaving the outcome out of the equation would therefore
let the proposer's strongest classification be reached for a candidate its own domain
evaluation rejected, and would make `DomainChecksComplete` silently stand in for a
substantive result it does not carry — the precise failure the **No term compensates
for another** rule above forbids. The term closes that path structurally, in the same
place C7 closed it, rather than relying on call-site discipline.

`[V]` The term names `domain_evaluation_outcome` and `DomainEvaluationOutcome`, and
both exist. Like every other part of OD-7 it was added to `equations.py` in the single
change set that also added the field, the vocabulary and the rest of the OD-7 surface,
and that removed C7 and C9 together. V13's two halves landed with it: `ProposerProcess
Record` enforces R-2's locally decidable half (`PROPOSAL` requires a selection) and
`build_proposer_advisory` recomputes Equation 2 for the resolved candidate, which is
where B3 says V13 recomputes it.

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

**The nested candidates are inside it.** Under OD-4(a) `ProposerAdvisory.candidates` is
a field of the advisory, so `model_dump(mode="json")` renders the whole sequence and
every field of every `CandidateAdvisory` in it into `P_unsigned`. `[V]` A9:
`exclude={"advisory_digest"}` removes only the **top-level** field, which is exactly
what is wanted here — no candidate carries a field of that name (D6's standing
prohibition), so there is nothing nested for the exclusion to have to reach, and the
prohibition is what keeps that true. `[V]` A9: a `tuple` dumps to a JSON array, so the
sequence canonicalises as an array whose order is identity-significant under C6, and the
ratified ascending-`candidate_id` order is what makes that order reproducible by an
independent verifier rather than an artifact of caller input.

## G2 — The only permitted construction shape

`[V]` A5 forbids both a null-digest draft and a locally-named digest function passed
into the `advisory_digest=` keyword. The construction is therefore:

1. `build_proposer_advisory` validates its inputs and constructs a **private**
   `_UnsignedAdvisoryPayload` — not exported — declaring exactly the fields of
   `ProposerAdvisory` **except** `advisory_digest`, with identical types, defaults,
   validators and serializers. Call the validated instance `payload`.
2. It computes the canonicalisation input:
   `p_unsigned = payload.model_dump(mode="json", exclude_none=False)`.
   **This is the only thing `p_unsigned` is for.** It is the JSON-mode projection G1
   defines, it is what is handed to the substrate, and it is **never** fed back into a
   model constructor.
3. It constructs and returns the advisory in **one expression**, from the **validated
   payload's Python-typed field values**, with the substrate call inline in the
   `advisory_digest=` keyword:

   ```python
   return ProposerAdvisory(
       schema_version=payload.schema_version,
       tenant_id=payload.tenant_id,
       created_at=payload.created_at,
       kind=payload.kind,
       advisory_version=payload.advisory_version,
       parent_advisory_digest=payload.parent_advisory_digest,
       case_ref=payload.case_ref,
       agent_id=payload.agent_id,
       role_contract_id=payload.role_contract_id,
       mandate_id=payload.mandate_id,
       context_id=payload.context_id,
       candidate_set_id=payload.candidate_set_id,
       candidates=payload.candidates,
       selected_candidate_id=payload.selected_candidate_id,
       recommended_disposition=payload.recommended_disposition,
       requested_review_action=payload.requested_review_action,
       requested_review_destination_role_ref=payload.requested_review_destination_role_ref,
       claim_summaries=payload.claim_summaries,
       observation_refs=payload.observation_refs,
       uncertainties=payload.uncertainties,
       reason_codes=payload.reason_codes,
       expires_at=payload.expires_at,
       advisory_digest="sha256:" + ugence_jcs.canonical_sha256_hex(
           p_unsigned, set_paths=frozenset(), nfc_paths=frozenset()),
   )
   ```

   The twenty-two pass-through keywords are the twenty-two D7 fields other than
   `advisory_digest`; `advisory_digest` is the twenty-third and is the one computed
   here. **Explicit field pass-through is the normative spelling**, and the reason is
   given below: no `model_dump()` of any mode is a lawful constructor input for this
   model.

   **The keyword set must equal the field set exactly, and this is checked
   structurally.** `[V]` Twelve of the twenty-three fields are declared with a default —
   `schema_version`, `kind`, `advisory_version`, `parent_advisory_digest`,
   `selected_candidate_id`, `recommended_disposition`, `requested_review_action`,
   `requested_review_destination_role_ref`, `claim_summaries`, `observation_refs`,
   `uncertainties` and `reason_codes` — so omitting one from this call **can be silently
   well-formed**: construction succeeds and the field takes its default. That is the
   hazard the pass-through introduces in exchange for being the only lawful spelling, and
   it is why I7.16 requires a structural test that the call's keyword set equals
   `set(ProposerAdvisory.model_fields)` exactly.

   `[V]` **The hazard is five of the twelve, not all twelve**, and the three-way split is
   worth stating because it shows what is and is not already caught. Verified on a
   representative payload carrying a selection, omitting each defaulted keyword in turn
   from an advisory whose model validator implements R-1a:

   | Omitted field | Outcome |
   | --- | --- |
   | `advisory_version`, `parent_advisory_digest`, `claim_summaries`, `observation_refs`, `uncertainties` | **constructs silently, digest fails to verify** — the real hazard, five fields |
   | `selected_candidate_id`, `recommended_disposition`, `requested_review_action`, `requested_review_destination_role_ref` | **`ValidationError`** — R-1a fires, because omitting one breaks the joint-presence coupling. Not silent |
   | `kind`, `schema_version`, `reason_codes` | constructs, **digest still verifies** — each admits only its default (`kind` and `schema_version` are `Literal`s, `reason_codes` is C5d-empty), so no other value could have been passed |

   `[I]` R-1a is therefore load-bearing here in a way E1 does not claim for it: it is a
   selection-coupling rule, and catching four omissions from the construction call is an
   incidental consequence of that coupling, not a guarantee it offers. It would stop
   catching them the moment a selection-dependent field ceased to be coupled. I7.16 does
   not rest on it.

   `[V]` The equivalence obligation below does **not** cover the five. Verified: with one
   of them omitted and given a **non-default** value on the payload, construction
   succeeds, the advisory silently carries the default, and the digest does not verify —
   the D2 failure. With the same omission and the field left at its **default**, the G1
   projection equals `p_unsigned` and the digest verifies, so a corpus that does not
   happen to vary that field passes. Only a structural check on the call catches the
   omission, and only I7.16 requires one.

**Why the payload is not dumped back into the constructor.** `[V]` Verified against
`pydantic 2.13.4` on a representative `strict=True` payload carrying timezone-aware
datetimes and a `tuple` of candidates:

| Construction input | Result |
| --- | --- |
| explicit field pass-through, as above | **accepted** — `created_at` is a `datetime`, `candidates` a `tuple` of `CandidateAdvisory` |
| `**payload.model_dump(mode="json", exclude_none=False)` | **rejected**, 3 errors: `datetime_type` on `created_at` and `expires_at`, `tuple_type` on `candidates` |
| `**payload.model_dump()` — Python mode | **rejected**, 4 `datetime_type` errors |

**A JSON-mode dump cannot be fed back into a `strict=True` model.** JSON has no
datetime and no tuple: `model_dump(mode="json")` renders every `datetime` as an ISO-8601
`str` and every `tuple` as a `list`. `strict=True` performs no coercion — that is the
whole point of C1's `strict=True` — so the string is rejected as `datetime_type` and the
list as `tuple_type`. Passing such a dump to `ProposerAdvisory(...)` does not merely
risk drift; it **fails validation outright**.

`[V]` **A Python-mode dump does not fix it either, and the reason is C4.** C4 requires an
explicit `@field_serializer` on every `datetime` field. A pydantic field serializer runs
in **both** dump modes unless it is declared `when_used="json"`, so `payload.model_dump()`
also yields ISO-8601 strings for the datetimes and is rejected for the same
`datetime_type` reason. Python mode additionally converts each nested `CandidateAdvisory`
to a `dict`. Neither dump mode is a constructor input; only the model's own Python-typed
field values are.

`[I]` This is why the shape is spelled out field by field rather than left to a
`**dump` idiom. The idiom reads as the obvious one and is wrong under this contract's own
ratified rules — `strict=True` from C1 and the mandatory serializer from C4 — and the
failure is a construction-time `ValidationError`, not a silent one. The pass-through is
also what an A5 reader wants: the substrate call stands inline in the `advisory_digest=`
keyword with nothing between the computation and the field.

**Canonicalisation happens exactly once.** `p_unsigned` is computed in step 2 and passed
to `canonical_sha256_hex` in step 3. There is no second dump, no second canonicalisation,
and no locally named digest helper — A5 rejects a local function passed by name into that
keyword, and A7's `SUSPECT_DEF_SUBSTRINGS` would reject one named for what it does.

There is no in-place mutation path and no setter: the model is frozen.

An unsigned `ProposerAdvisory` is **not a public-valid state**. `advisory_digest` is
required and non-nullable, so no public factory can return an advisory without one, and
the unsigned representation never leaves the builder.

**Equivalence obligation.** A frozen-profile test asserts, over a fixed corpus, that
`payload.model_dump(mode="json", exclude_none=False)` equals the G1 expression
evaluated on the resulting `ProposerAdvisory`, and that both canonicalise to identical
bytes. Without that test the private payload could drift from the public contract and
produce a digest no independent verifier could reproduce — precisely the D2 failure.
`[V]` Verified on the representative payload: the G1 projection of the constructed
advisory equals `p_unsigned` exactly, the two canonicalise to the same 64-character
digest, and `verify_advisory_identity` therefore returns `True`.

**Construction-shape obligation.** A second test asserts that feeding
`payload.model_dump(mode="json", exclude_none=False)` into `ProposerAdvisory(...)`
**raises** `ValidationError` with `datetime_type` and `tuple_type` among the error types,
and that the explicit pass-through succeeds and yields a `datetime`-typed `created_at`
and a `tuple`-typed `candidates`. Asserting the failure, and not only the success, is
what keeps the round-trip idiom from being reintroduced as a "simplification" once
`strict=True` or C4's serializer is quietly relaxed.

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

`build_advisory_revision` sets `parent_advisory_digest = parent.advisory_digest` and
increments `advisory_version` per B7. A revision is a new advisory with a new digest;
nothing about the parent is mutated. The increment is computed as canonical positive
decimal without leading zeroes; any integer arithmetic used to compute it is local to
that function and never surfaces as a field, so C3 is not weakened.

**Every identity-participating field of a revision has exactly one declared source.**
There are four, and no field falls outside them. `[I]` The table below is a completeness
statement about the *sources*; the corresponding completeness statement about the
*construction call* is G2's, enforced by I7.16 — a field may not be omitted from the
pass-through merely because it carries a default, and twelve of the twenty-three do.

| Source | Fields |
| --- | --- |
| **Inherited from the parent unchanged** — the ratified continuity fields | `tenant_id`, `case_ref`, `agent_id`, `role_contract_id`, `mandate_id`, `context_id` |
| **Computed by the builder** | `advisory_version` (incremented, B7), `parent_advisory_digest` (`= parent.advisory_digest`), `advisory_digest` (Equation 3), `kind` and `schema_version` (literals) |
| **Derived from the supplied `AdvisoryCandidateSet` under R-1b** | `candidate_set_id`, `candidates`, `selected_candidate_id`, `recommended_disposition`, `requested_review_action`; and, since OD-7 part 5, the mirrored `domain_evaluation_profile_id`, `domain_evaluation_profile_version`, `selection_policy_id` and `selection_policy_version` |
| **Required of the caller, explicitly** | `claim_summaries`, `observation_refs`, `uncertainties`, `created_at`, `expires_at`, `requested_review_destination_role_ref` (see H1: no contract states a source for it, so it is a caller-supplied selection input, checked for joint presence with the selection rather than derived), the injected `provider` and the expected profile identity; and `reason_codes` is C5d-empty and takes no caller value |

**`claim_summaries`, `observation_refs` and `uncertainties` are required keyword
parameters and are not inherited from the parent.** This is the correction the
independent review required, and the reasoning is the point of B2. A revision is a
**newly asserted identity-bearing advisory**, not an annotation on an old one: it
carries its own digest over its own `P_unsigned`, and a consumer who verifies that
digest is told that everything inside it is what this advisory asserts. Silently
copying the parent's claim summaries, evidence references and uncertainties into a new
digest would mint a fresh assertion out of stale content that no caller restated —
and the three fields are exactly the ones that carry what the proposer *found*, which
is what a revision most often exists to change.

The builder therefore **validates** the three supplied values under their ratified
classifications (`claim_summaries` and `uncertainties` C5c, `observation_refs` each C5a
with no duplicates and every entry resolving under R-7), **binds them into the new
`P_unsigned`**, increments `advisory_version`, and binds the parent through
`parent_advisory_digest`.

**Omission is refused, not defaulted.** All three are required keyword-only parameters
with no default. A caller who omits one gets a `TypeError` from the call, not an
inherited value and not an empty list; a caller who means "unchanged" must pass the
parent's values explicitly, which is a statement they have made rather than one the
builder made for them. `[I]` An empty-list default would be the worse of the two
failures available here: it is silently well-formed, it canonicalises, and it would
produce a digest-valid revision asserting that the proposer found nothing.

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
    provider: DomainEvaluationProvider,
    profile_id: str,
    profile_version: str,
) -> CandidateAdvisory: ...


def build_advisory_candidate_set(
    *,
    candidate_set_id: str,
    tenant_id: str,
    case_ref: str,
    created_at: datetime,
    candidates: tuple[CandidateAdvisory, ...],
    selected_candidate_id: str | None,
    domain_evaluation_profile_id: str | None,
    domain_evaluation_profile_version: str | None,
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
    provider: DomainEvaluationProvider,
    expected_profile_id: str,
    expected_profile_version: str,
    requested_review_destination_role_ref: str | None,
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
    claim_summaries: list[str],
    observation_refs: list[str],
    uncertainties: list[str],
    created_at: datetime,
    expires_at: datetime,
    provider: DomainEvaluationProvider,
    expected_profile_id: str,
    expected_profile_version: str,
    requested_review_destination_role_ref: str | None,
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
    context: BoundedContextEnvelope,
    observations: list[ToolObservation],
) -> bool: ...


def verify_observation_resolution(
    *,
    advisory: ProposerAdvisory,
    context: BoundedContextEnvelope,
    observations: list[ToolObservation],
) -> bool: ...
```

`[I]` **Why `build_candidate_advisory` and `build_advisory_candidate_set` gain
parameters, when OD-7's own "new or changed functions" list names only the two advisory
builders.** `[V]` That list is accurate about what it names and is **not** exhaustive
about the rest of H1: it is a summary of the ruling's novel surface, not a closed
enumeration of every signature the ruling touches. Each of the four additions here is
**entailed** by a ratified field plus a ratified prohibition, not chosen:

* `provider`, `profile_id` and `profile_version` on `build_candidate_advisory`. Part 5
  makes `domain_evaluation_outcome` a `CandidateAdvisory` field; part 6 requires the
  instance to be constructed **exactly once**, after evaluation, with every field
  already known; and part 2 bars this package from importing, discovering, loading or
  embedding any evaluator. The only remaining way for the builder that constructs a
  `CandidateAdvisory` to obtain the outcome is to be handed the provider and the
  profile it is evaluating under.
* `domain_evaluation_profile_id` and `domain_evaluation_profile_version` on
  `build_advisory_candidate_set`. Part 5 makes the pair a **set-level** field, present
  if and only if some nested candidate is `COMPLETE`. This is the only builder for
  `AdvisoryCandidateSet`, so a pair it could not accept would be a required field with
  no lawful producer.

`[V]` The selector-policy pair is deliberately **not** a parameter of that builder: it
names this package's own ratified selector, so accepting it from a caller would let a
caller label a selection with a policy that did not make it. The builder stamps it from
this package's own constants when a selection is present.

`[V]` **The exact signatures above are owner-ratified for 0.2.0 (A13).** What was
previously marked `[R]` here — the parameters' spelling, their names, their documented
order, and the choice of two scalar profile parameters over one pair object — is
**resolved**, together with the injected `provider` parameter and the decision not to
accept caller-supplied selector-policy identity parameters. They are compatibility
decisions for this version, not an implementation shape a later change may vary freely.
The ruling ratifies the **callable shape already implemented and documented** and
nothing else: it authorizes no additional field, protocol, behaviour or public symbol,
and it does not authorize substantive ranking, a concrete evaluator, networking,
storage, service discovery, plugin loading or multi-provider evaluation. The entailment
reasoning above is unchanged by it; what changes is that the shape is no longer an open
question. See `docs/architecture/ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md`'s **A13**
for the declaration.

`verify_advisory_selection` is the independent replay of R-1b **and R-7**. It is a
**separate function from `verify_advisory_identity`** because the two answer different
questions: identity asks whether the stored bytes are the ones that were signed,
correspondence asks whether what was signed agrees with the artifacts it references. A
caller acting on an advisory's routing must call both. It returns `False` rather than
raising, on the same terms as `verify_candidate_eligibility`.

`[I]` It takes `observations` and `context` because R-7 has a replay counterpart. A
verifier given only the advisory, the set and the role can check candidate
correspondence but cannot tell whether a single `observation_refs` entry resolves to
anything, which would leave R-7 enforced by the builder alone — the shape B2 refuses.
`verify_advisory_selection` therefore invokes `verify_observation_resolution` and
returns `False` if it does.

`verify_observation_resolution` is the E2 algorithm as a separately named function. It
is exported in its own right so that a read-only auditor can replay evidence resolution
without also replaying selection, and so that a failure can be attributed to R-7 rather
than to R-1b. It returns `False` and reports the failing references; it does not raise.

Notes that are part of the ratified behaviour:

* `build_candidate_advisory` takes no `is_eligible`, no `domain_check_completion` and
  no `domain_evaluation_outcome`. It computes the first from Equation 1 and **derives
  the other two from the injected provider's verified answer** (OD-7 parts 2, 3 and 6):
  it resolves the candidate's `observation_refs`, issues one
  `DomainEvaluationRequest` under the supplied profile, checks the response's echoed
  profile and `candidate_id`, and constructs the candidate once with
  `domain_check_completion=COMPLETE` and the returned outcome. `[V]` **The pre-OD-7
  statement that it "leaves `domain_check_completion` at its `NOT_EVALUATED` default"
  no longer describes the ordinary path.** That default survives in exactly one case,
  and it is the one part 7's first row names: an `observation_refs` entry that does not
  resolve. There the provider is **not called at all**, `_resolve_references` warns
  naming the failing reference, and the candidate is constructed `NOT_EVALUATED` with no
  outcome — which keeps it out of every qualifying pool. Directing that run to
  `NEED_EVIDENCE` is the caller's orchestration decision, not a return value.
* `build_proposer_advisory` and `build_advisory_revision` **derive** the nested
  `candidates` sequence from the supplied `AdvisoryCandidateSet` under R-1b rather than
  accepting it, **on the same terms as the four selection fields**. Neither builder takes
  a `candidates` parameter: the sequence is constructed from `candidate_set.candidates`,
  placed in the ratified ascending-`candidate_id` order, and checked for equal
  membership, order and content against the set it came from, so the carried copy and
  the referenced set cannot disagree at construction. A caller-supplied sequence is not
  accepted, and out-of-order input to `build_advisory_candidate_set` is rejected there
  rather than reordered here.
* `build_proposer_advisory` **derives** `selected_candidate_id`,
  `recommended_disposition` and `requested_review_action` from the candidate set under
  R-1b rather than accepting them, so the two cannot disagree.
  `requested_review_destination_role_ref` is **not** among the derived three, and the
  pre-OD-7 wording that listed it there is corrected here: `[I]` under C9 all four were
  `None` on every constructible path, so nothing distinguished a field derived from the
  set from one that merely had no other value; with a selection reachable, the
  distinction bites. `[V]` No contract in this specification states a source for it —
  C9's own rejected-alternative note says so in terms, which is one of the two grounds
  on which deriving faithfully was rejected there — and OD-7's amended builder
  paragraph names "the selection inputs" among the required keyword parameters both
  advisory builders gain. It is therefore **caller-supplied**, and the builder checks
  only what R-1a and R-1b(viii) let it check: that it is present exactly when a
  selection is, and absent exactly when one is not. Inventing it from
  `CognitiveRoleContract.escalation_role_ref` or `AgentIdentityRef.owner_role_ref` was
  rejected: both mean something else, and either would be this package choosing a
  referral destination the owner has not ratified. It resolves the set, checks
  correspondence, and rejects a mismatch. When the selector is non-null it must resolve
  to exactly one nested candidate and exactly one candidate in the referenced set, and
  the two dependent values must equal that **nested** candidate's `disposition` and
  `requested_review_action`. Under B3 it derived `None` for all four in S1, because C9
  made a candidate set carrying a non-null selector unconstructible, so the derivation
  was exercised only on the always-null case. `[V]` **With C9 removed (OD-7 part 8) the
  derivation is exercised on both branches.** Both builders gain required keyword
  parameters for the injected `provider`, the expected profile identity, and the
  selection inputs; they call `verify_domain_evaluation` and
  `verify_deterministic_selection` before constructing and raise
  `DomainEvaluationProviderError` if either fails (part 7, row 2); they mirror the four
  evaluation/policy fields from the set; and where a selection is derived they recompute
  Equation 2 for the resolved candidate, which is the recomputation B3 assigns to
  `build_proposer_advisory`.
  It calls `verify_candidate_eligibility` and raises `EligibilityMismatchError` before
  constructing if any candidate's stored `is_eligible` differs from the recomputation.
  R-1a is additionally enforced by the model validator on every construction path,
  including one the builder did not produce.
* `build_proposer_process_record` enforces R-2, R-3 and R-4. Under B3, a `PROPOSAL`
  terminal outcome was unreachable in S1 and the builder rejected it. `[V]` It is
  reachable now: what the record's own validator enforces is R-2's locally decidable
  half — `PROPOSAL` requires a `selected_candidate_id` — since R-2's readiness conjunct
  needs the identity, role, mandate, context and candidate this record does not carry,
  and is recomputed by `build_proposer_advisory` instead.
* `verify_candidate_eligibility` returns `False` — it does not raise — so a read-only
  auditor can inspect a stored set without exception handling. The **builder** raises;
  the **verifier** reports.

## H2 — Exception surface

**Exactly five classes of failure, and no others (OD-6(ii), OD-7):**

| Failure | Type | Origin |
| --- | --- | --- |
| Contract violation — type, format, cardinality, closed vocabulary, a Part E rule decidable from one contract instance's own fields | `pydantic.ValidationError` | pydantic |
| A Part E rule that compares fields across two or more independently constructed contract instances — R-1b(i)–(iv), (viii), (ix), R-5, R-6, R-7, R-9, R-10 | `CrossContractViolationError` | **defined and exported by this package**, subclassing `ValueError` |
| A stored `is_eligible` that does not match the recomputation | `EligibilityMismatchError` | **defined and exported by this package**, subclassing `ValueError` |
| A provider's echoed profile identity, echoed `candidate_id`, returned outcome, or a recorded selector-policy identity that cannot be verified — or `provider` itself raising during the original build (OD-7) | `DomainEvaluationProviderError` | **defined and exported by this package**, subclassing `ValueError` |
| Canonicalisation fault | `ugence_jcs.JcsError` and its subclasses, re-raised unchanged | `ugence-jcs` |

`EligibilityMismatchError`, `CrossContractViolationError` and
`DomainEvaluationProviderError` are the only exceptions this
package defines. Each exists for the same reason: the failure it reports is not a
field-validation failure and must not be reported as one, because the value is
well-formed and the object is well-typed on its own terms; what failed is provenance (for
`EligibilityMismatchError`) or a relationship between two otherwise-valid objects (for
`CrossContractViolationError`). `[V]` OD-6(ii) adds `CrossContractViolationError`
because H2's original three-class table gave no exception type to the residue of Part E
that a single model's validator structurally cannot decide — R-1b's cross-contract
clauses and R-5, R-6, R-7, R-9 and R-10 each require two or more independently
constructed instances in hand at once, which is a builder function's obligation, not a
model's — and an implementation reporting that residue as a bare `ValueError` (a fourth,
undeclared class in fact if not in name) would already have violated the closed "exactly
three, and no others" text this amendment corrects to four. **Restructuring these checks
into single-model validators to reach `pydantic.ValidationError` instead was considered
and rejected**: several of them (R-5, R-6, R-7 in particular) are stated over an
unbounded list of supplied `ToolObservation` instances a single contract cannot carry
without becoming a second identity surface, and forcing a multi-instance comparison into
one model's validator would either require constructing a throwaway aggregate model for
the sole purpose of obtaining the right exception type, which asserts nothing true about
the object being validated, or silently narrowing which instances a rule is checked
against. A named, purpose-built exception class states plainly what actually failed.

## H3 — Public-API snapshot

The complete exported surface, as amended by OD-7. Recorded here as specification; **no
`public_api.json` is created by this document**, and none could exist until S1 was
implemented and separately authorised. `[V]` It exists now and covers every item below:
forty-six names, the thirty-nine 0.1.0 froze plus OD-7's seven, at `0.2.0`.

**Contracts (8):** `AgentIdentityRef`, `CognitiveRoleContract`, `WorkMandate`,
`BoundedContextEnvelope`, `ToolObservation`, `AdvisoryCandidateSet`, `ProposerAdvisory`,
`ProposerProcessRecord`

**Nested public models (2):** `CandidateAdvisory`, `ProposerProcessStateTransition`

**Call-boundary shapes and the injected-evaluator protocol (3, OD-7 part 2):**
`DomainEvaluationRequest`, `DomainEvaluationResponse`, `DomainEvaluationProvider`. None
is a contract: none carries a C2 common field, none is stored, transported or reachable
from `P_unsigned`, and none has an identity role.

**Enums (11):** `TerminalOutcome`, `CandidateDisposition`, `SemanticAuditorFindingStatus`
(three existing, D4); `ReviewAction`, `DomainCheckCompletion`, `AgentLifecycleState`,
`RoleActivationStatus`, `ToolOperationClass`, `ToolObservationAdmissionStatus`,
`ProposerProcessState` (seven new); `DomainEvaluationOutcome` (OD-7 part 3)

**Builders (5):** `build_candidate_advisory`, `build_advisory_candidate_set`,
`build_proposer_advisory`, `build_advisory_revision`, `build_proposer_process_record`

**Equation functions (2):** `evaluate_eligibility`, `evaluate_readiness`

**Identity functions (2):** `compute_advisory_identity`, `verify_advisory_identity`

**Verifiers (5):** `verify_candidate_eligibility`, `verify_advisory_selection`,
`verify_observation_resolution`; `verify_domain_evaluation`,
`verify_deterministic_selection` (OD-7 part 5)

**Exceptions (3):** `EligibilityMismatchError`, `CrossContractViolationError` (OD-6(ii)),
`DomainEvaluationProviderError` (OD-7)

**Constants (4):** `RESERVED_AUTHORITY_VOCABULARY` (existing),
`ADVISORY_KIND = "ugence.agentic_proposer.advisory.v0"`,
`ADVISORY_IDENTITY_SET_PATHS = frozenset()`,
`ADVISORY_IDENTITY_NFC_PATHS = frozenset()`

**Metadata (1):** `__version__`

**Not exported:** `_UnsignedAdvisoryPayload`.

`[R]` **No exported name may begin with `Proposal` or `Recommendation`, as D7
requires.** This is a **requirement on the surface specified above**, which is not yet
implemented or exported, and it is to be verified when S1 declares its
`public_api.json` (I6, I8). The names in H3 are authored to satisfy it: `Proposer*` is
not `Proposal*`, and `recommended_disposition` is a field, not an exported name. `[V]`
What is merged and verified is the scope of the rule —
`tests/test_advisory_contract_shape.py` records that `PROPOSAL` and `RECOMMEND_*` are
enum **values** and out of the prefix rule's reach.

---

# Part I — Implementation obligations

These are obligations on the S1 implementation. **None of them is discharged by this
document**, which changes no test and no source file.

> **Status note.** The O-1 – O-4 and OD-1 – OD-3 guards are implemented in
> `packages/capabilities/agentic-proposer/tests/`, and "implemented" below means exactly
> that: a named guard enforces the ratified rule. It does **not** mean the rule has been
> checked against a production contract surface, because none exists, and it does **not**
> authorize one — production implementation is gated on the Part I obligations (A12).
>
> `[R]` The guards are exercised against **temporary representative shapes** derived from
> Part D and carried in `tests/s1_specification_mirror.py`. Those shapes are test support:
> they declare no contract, are exported from nothing, and ship in no wheel. Every claim
> below that a guard *arms* on a contract is a claim about those shapes and is to be
> re-verified when the first contract module lands.
>
> The guards change tests and documentation only — no `src/`, `version.py`,
> `pyproject.toml`, CI workflow, `public_api.json` or platform-freeze artifact is
> touched. I1, I6 and the unbuilt parts of I7 remain outstanding; I2, I3, I4 and I5
> record what the guards do.

## I1 — D2 scan: a narrow, module-scoped exemption *(outstanding)*

`[V]` A7: the ratified `"sha256:"` prefix literal and the C6 pattern
`^sha256:[0-9a-f]{64}$` collide with `SUSPECT_TEXT`. `[V]` The guards do not address
this: their only change to `test_no_local_canonicalization.py` adds the new guard modules
to the pinned module list. It is outstanding, and lands with the identity module it
governs.

The resolution is a **module-path-scoped mask**, not a widened rule: the text mask for
exactly the two strings `"sha256:"` and `"^sha256:[0-9a-f]{64}$"` applies only within
the single authorised identity module, and nowhere else in `src` or `tests`.

It must not permit: an arbitrary `sha256:` literal in any other module; a local
`hashlib` import anywhere; a locally defined `canonical_*`; a shadowed or relative
`ugence_jcs`; or an identity computation from any module outside the authorised one.

**No definition-name exemption is required.** The identity functions are named
`compute_advisory_identity`, `verify_advisory_identity`, `verify_advisory_selection`,
`verify_observation_resolution` and
`verify_candidate_eligibility`; none contains `"digest"`, `"canonical"`, `"canon"`,
`"jcs"`, `"fingerprint"` or any other `SUSPECT_DEF_SUBSTRINGS` member, so
`SUSPECT_DEF_SUBSTRINGS` is left untouched. The field name `advisory_digest` is an
`AnnAssign` target, not a `FunctionDef` or `ClassDef`, and is not scanned. **Test
function names must not contain `"digest"`**, for the same reason.

**Mutation tests required**, proving each of these is still rejected: `"sha256:"` in a
module other than the authorised one; the authorised name defined at class scope; the
authorised name defined without the substrate call; the authorised module importing
`hashlib`; and a locally defined `canonical_sha256_hex`.

## I2 — Lifecycle-verb guard: narrowed to authority, not vocabulary (B4) *(implemented)*

`[V]` Implemented by `tests/test_role_projection_bounds.py`. It classifies by **grammatical form and
syntactic position** rather than by stem: a mutation form is barred in every position;
an actor form is barred as a type or callable and permitted as a field naming an
external party; any lifecycle-stemmed field annotated `Callable` is barred. The
retained vocabulary — `SUSPENDED`, `REVOKED`, `RoleActivationStatus`,
`activation_status`, `expires_at` — is pinned permitted **by equality**, and the six
verbs D8 names are pinned barred in all four positions. Six mutants each weaken one
rule and must let a real violation escape without gaining a false positive on the
retained vocabulary.

This supersedes the cruder "callables only" rule an earlier draft of this document
specified. `[V]` Both accept the retained vocabulary; the implemented rule additionally
distinguishes an actor noun used as a field from one used as a type, which the cruder
rule could not. Both halves are exercised by the module's mutation controls.

## I3 — Ratified-kind guard: narrowed to `ProposerAdvisory` (B5) *(implemented)*

`[V]` Implemented by `tests/test_advisory_contract_shape.py`: the kind is **required** on `ProposerAdvisory`
and **barred** on `CandidateAdvisory`, along with any other kind in this capability's
namespace, and the kind reader is self-tested against all three spellings (`KIND`,
`kind`, a `kind` field default). This is stronger than the narrowing this document
originally specified, which only removed `CandidateAdvisory` from the assertion.

## I4 — Two corrections the guards have applied

**Both corrections this section previously reported as outstanding are applied.** An
earlier revision described them as repairs still needed; that reading was taken before
they landed and the correction is recorded here rather than quietly absorbed. `[V]` Each
is implemented by a named guard below. "Implemented" is not "authorized": production
implementation remains gated on the Part I obligations (A12), and the guards are exercised against
temporary representative shapes rather than a declared contract module.

1. **The O-1 guard's class-blind false positive — fixed.** An earlier revision matched
   `DEPENDENT_FIELDS` by name alone, so
   `CandidateAdvisory.requested_review_action` — the candidate's **own** proposed
   routing, required and non-null by D6 of this document — was treated as a
   selection-dependent field, and the guard then demanded a `selected_candidate_id` on
   `CandidateAdvisory` and demanded the field admit `None`, contradicting the ratified
   contract.

   `[V]` The guard is now **bearer-scoped**, exactly as OD-3 ratifies.
   `tests/test_selection_dependent_fields.py` declares `SELECTION_BEARER =
   "ProposerAdvisory"`, holds `SELECTION_FIELD = "selected_candidate_id"` separately
   from a three-element `DEPENDENT_FIELDS`, and registers both in `SELECTION_COUPLING`.
   The class filter examines a class **only** when its name is a key of that registry,
   and the live-type filter gates on it too. `NON_BEARERS_SHARING_A_FIELD_NAME =
   ("CandidateAdvisory",)` names the exclusion so it is deliberate and visible rather
   than a silent consequence. Three self-tests pin the registry by equality —
   `test_the_coupling_is_pinned_to_the_ratified_fields`,
   `test_the_bearer_registry_is_pinned` and the assertion on
   `NON_BEARERS_SHARING_A_FIELD_NAME` — so it cannot be widened to another contract or
   narrowed to fewer fields without failing.

   `[V]` **Enforcement is behavioural first.** The guard constructs the bearer from a
   complete valid fixture supplying all twenty-three required fields and exercises the
   four coupling cases as live validation outcomes, keeps
   `CandidateAdvisory.requested_review_action` required and non-null, and proves the
   bearer-scoped rule does not reach a class merely sharing the field name. Static AST
   inspection is **supplemental** and is not described as proof of behaviour:
   `test_the_suite_kills_a_no_op_validator_mutant` shows a validator that names all four
   fields and enforces nothing passing the static layer and being killed by the
   behavioural probes.

2. **The `pydantic`/`socket` boundary probe — fixed.** `[V]` The underlying fact is
   unchanged and reproduces against `pydantic 2.13.4`: bare `import pydantic` does
   **not** load `socket`, but *defining any* `BaseModel` does, because pydantic-core's
   schema build pulls it in. `socket` is in that guard's `FORBIDDEN` set, so a
   whole-process `sys.modules` assertion fails the moment the first contract model
   exists, for a reason unrelated to this package's authority.

   `[V]` `tests/test_boundaries.py` implements the OD-2 design in **five
   layers**, none load-bearing alone: a static import scan of every production source;
   an extension of that scan to aliases, `from` imports, module-qualified use and the
   dynamic-import spellings — a literal passed to `import_module` or `__import__`, a
   literal bound to a local name and then passed to either, `exec("import socket")`,
   `eval("__import__('socket')")`, an import inside `compile(...)`, and the prohibited
   relative-import spellings, each with its own negative control; an isolated subprocess that establishes the
   approved-dependency baseline first — `import pydantic`, define a minimal model — and
   then imports this package, asserting it adds **no additional** forbidden root beyond
   that baseline; the declared-dependency allowlist, so the exemption can never
   authorize a new networking library; and negative controls proving a direct `socket`
   import or use still fails. `DEPENDENCY_BASELINE_MODULES` is **derived** from the
   declared dependency registry in `pyproject.toml` rather than written beside it, the
   generated baseline setup is **pinned by equality** so a baseline carrying an added
   `import socket` fails `test_a_widened_baseline_setup_fails`, and
   `test_the_dependency_baseline_is_what_it_claims_to_be` demonstrates the premise
   rather than assuming it — asserting that bare `import pydantic` does not load
   `socket` **and** that defining a model does, each with a message saying what to
   re-read if the behaviour changes.

   `[V]` The whole-process assertion this document previously cited by name,
   `test_isolated_subprocess_import_loads_no_forbidden_module`, **no longer exists**: the
   repair replaced it with
   `test_isolated_subprocess_adds_no_forbidden_module_beyond_the_baseline`. A citation to
   the old name is a citation to a superseded revision.

   The ruling is OD-2, ratified 2026-08-25. No ruling is outstanding, and this affects
   no contract shape in this document.

**What this means.** `[V]` This section names no outstanding repair to either guard.
`[R]` Both are exercised against temporary representative shapes rather than a declared
contract module, so every claim that a guard *arms on a contract* is to be re-verified
when the first contract module lands. Neither guard authorizes that module.

## I5 — Field classification must be pinned, not guessed (O-4)

**The suffix-inference defect this section originally reported is fixed.** An earlier
revision of the O-4 guard classified by name suffix (`_id`, `_ids`, `_ref`, `_refs`,
`_key`, `_keys`, `_uri`, `_uris`, `_urn`, `_code`, `_codes`, `_slug`) with a free-text
marker list, and six fields — `agent_version`, `tool_name`, `allowed_source_scopes`,
`excluded_data_classes`, `permitted_tool_scopes` and `tool_invocations` — fell in
neither bucket and were checked by nothing. `[V]` Inference is replaced by an exact
per-contract registry in which every declared field must appear, an unregistered field
being a failure rather than a skip, with inference retained only as a secondary
cross-check.

`[V]` **The registry is an enforcement mirror of this document and nothing else.** It is
carried in `tests/s1_specification_mirror.py`, transcribed from the C5 tables and Part D
above; it **originates no contract field**, adds none, renames none and reinterprets
none, and where the registry and this document disagree, this document is right.
`test_the_registry_cites_its_source` asserts that each block's cited section still
resolves here. The obligation below is therefore **what the registry carries**, together
with what it must additionally carry once a production surface exists; `[R]` its
completeness check against `src/` is dormant until then.

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
* `ProposerAdvisory.candidates` present in the registry as a **non-`str`, non-enum
  structured field** carrying a sequence of `CandidateAdvisory`, on the same reasoning
  that puts `AgentIdentityRef.lifecycle_state` there: a registry populated only from
  `str`-annotated fields could not report its absence, and it is the field OD-4(a) added,
  so it is exactly the field a stale registry would miss;
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
2. **List-order significance** — reordering `ProposerAdvisory.candidates`, a nested
   candidate's `observation_refs`, `claim_refs`, `assumptions` or `uncertainties`, or the
   advisory's own `observation_refs`, `claim_summaries` or `uncertainties`, changes the
   digest; reordering `permitted_tool_scopes` or `allowed_record_refs` does not, those
   fields not being identity-participating. The test must distinguish the two rather than
   assert one rule over the whole set. Separately, a `ProposerAdvisory.candidates` or
   `AdvisoryCandidateSet.candidates` supplied in any order other than ascending
   `candidate_id` must be **rejected** by its builder, not reordered into place (D6).
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
11. **Rival-identity reachability, and the composition it pins** — an explicit test
    that asserts **both halves** of the ratified composition, so that a future change in
    either direction fails loudly at the design boundary rather than deep in a guard.

    * It **must bar a nested `ToolObservation`**: `content_hash` must not be reachable
      from either advisory type at any depth, and `ToolObservation` must not appear in
      either type's reachable model set. `[V]` A3 forces this half. A change that
      re-nests the observation must fail here.
    * It **must require a nested `CandidateAdvisory`**: `ProposerAdvisory.candidates`
      must be declared, must be a sequence of `CandidateAdvisory`, and
      `CandidateAdvisory` must appear in `ProposerAdvisory`'s reachable model set. This
      is the ratified D7 composition (OD-4(a)), so **a future change back to
      reference-by-id must fail this test**, not pass it. An earlier statement of this
      obligation said only that the test must not be written so as to bar the nesting;
      that is too weak — a test that merely permits the nesting leaves the ratified shape
      unpinned, and the departure OD-4 recorded could recur without any guard noticing.
    * It **must bar a second identity on the candidate** (D6's standing prohibition): no
      field of `CandidateAdvisory` may be a member of `RIVAL_IDENTITY_FIELDS`, and none
      may be digest-shaped under C6. A mutant adding a per-candidate `content_hash`,
      `advisory_digest` or renamed digest field must fail.
    * `[R]` The corrected-graph walk recorded in A3 — nesting `CandidateAdvisory` adds
      only names the committed guard already asserts clean, and
      `reachable & RIVAL_IDENTITY_FIELDS` stays empty — is what this test re-establishes
      against a real contract module. It is `[R]` until that module exists.
12. **Constrained-`str` declaration form (C8)** — a mutation test asserting that
    `advisory_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")` is reported as an
    unpermitted identity source by
    `test_identity_is_computed_only_through_the_permitted_substrate`, and that the
    `Annotated[str, StringConstraints(pattern=...)]` spelling is not; plus a scan
    asserting no `src` model declares a string constraint through `Field(...)` on any
    field.
13. **Construction shape under `strict=True` (G2)** — the explicit field pass-through
    constructs a `ProposerAdvisory` whose `created_at` is a `datetime` and whose
    `candidates` is a `tuple` of `CandidateAdvisory`; and feeding
    `payload.model_dump(mode="json", exclude_none=False)` into the same constructor
    **raises** `ValidationError` carrying `datetime_type` and `tuple_type`, while
    `payload.model_dump()` raises with `datetime_type`. Asserting both failures, not
    only the success, is what stops the `**dump` idiom being reintroduced. A companion
    assertion pins that a `list` passed to either `candidates` field is rejected with
    `tuple_type`.
14. **R-7 replay (E2)** — `verify_observation_resolution` returns `False`, naming the
    failing reference, for each of: a dangling `observation_ref`; two supplied
    observations sharing an `observation_id`; an observation substituted to another
    tenant, another case, or a `source_ref` outside `allowed_record_refs`. It returns
    `True` while reporting the extra as unreferenced when a supplied observation is
    referenced by nothing, and that extra observation contributes to no equation term.
    A candidate with an empty `observation_refs` must **not** be usable to make a
    non-empty reference list pass vacuously. `verify_advisory_selection` must return
    `False` whenever `verify_observation_resolution` does.
15. **Revision inputs (G3)** — `build_advisory_revision` refuses a call omitting
    `claim_summaries`, `observation_refs` or `uncertainties` rather than inheriting the
    parent's or defaulting to empty; the three supplied values, and not the parent's,
    appear in the revision's `P_unsigned`; the continuity fields are inherited unchanged;
    and `advisory_version` increments while `parent_advisory_digest` binds the parent.
16. **Construction-call completeness (G2)** — an introspection or AST test asserting
    that the keyword set of the `ProposerAdvisory(...)` construction call in the identity
    module equals `set(ProposerAdvisory.model_fields)` **exactly**: no field missing, no
    keyword that is not a field, compared as sets rather than by count. The test reads
    the call itself — by `ast` over the module's source, or by introspecting the bound
    call — and not the builder's result, because the result is exactly what cannot
    distinguish an omission from a default.

    `[V]` It is required because omission can be silent: twelve of the twenty-three
    fields are declared with a default, and for **five** of them — `advisory_version`,
    `parent_advisory_digest`, `claim_summaries`, `observation_refs` and `uncertainties` —
    dropping one from the pass-through constructs successfully, silently carries the
    default, and produces a digest that does not verify, while the equivalence corpus
    passes unchanged if it happens not to vary that field. G2 gives the full three-way
    split: R-1a incidentally catches the four selection-coupled fields, and three admit
    only their default. Five silent-omission fields is the justification; the test must
    not be narrowed to those five, because the partition is a property of today's field
    set and not of the rule.

    `[I]` The obligation is stated over the *field set*, not over a written list of
    twenty-three names, so that adding a twenty-fourth field to `ProposerAdvisory`
    fails this test until the pass-through is updated. A newly added defaulted
    identity-participating field is precisely the case that would otherwise enter
    `P_unsigned` through the payload while never being passed to the constructor.

## I8 — Versioning and the ADR

`public_api.json` is created only when S1 is implemented, and it must cover every item
in H3. The version moves to `0.1.0` only after the public-API snapshot and its drift
test exist, and `CHANGELOG.md` must record what is frozen at it. Neither happens in this
document.

`[V]` **Both moves have since been made, in the order this section requires.** The
snapshot and its drift test landed with the S1 contracts at `0.1.0` (39 names). OD-7's
amendment then took the surface to 46 names and the version to `0.2.0`, in the single
change set that implemented it — not before, and not as a snapshot regenerated ahead of
the code and tests it describes. `CHANGELOG.md` records what each version carries.

---

# Part J — Intentionally deferred

Each item below is deliberately absent and is not a gap.

* **A domain evaluator.** `[V]` **The boundary is no longer deferred; a concrete
  evaluator still is, and deliberately.** OD-7 supplies the boundary — an injected
  `DomainEvaluationProvider` protocol, its request and response shapes, the
  orchestration and the replay — so `DomainCheckCompletion.COMPLETE` has a producer and
  C7's validator is removed. What remains absent, and is not a gap, is any **concrete
  business-domain evaluator**: none is imported, discovered, loaded or embedded here,
  and no network, storage, service-discovery or plugin-loading mechanism is authorized
  by that ruling. Multi-provider evaluation is likewise unratified.
* **Candidate selection.** Under B3, S1 selected nothing. S-1, S-2, R-1a and R-1b were
  specified so that selection would be a behaviour change at S2, not a contract change.
  `[V]` **Selection is implemented under OD-8 as selection-policy v1 (fail-closed
  uniqueness).** What stays deferred is **substantive multi-candidate ranking**, which
  needs its own ruling naming a business objective, an authoritative producer, a
  non-floating-point representation, an identity binding and a replay path no untrusted
  caller can steer; under v1 more than one qualifying candidate produces no selection
  and `ABSTAIN`, and the `candidate_id` tie-break is deliberately unexercised.
  `[G]` **Superseded by OD-7.** That last clause no longer holds: OD-7 is ratified as
  bearing on contract shape, adding `selection_policy_id`/`selection_policy_version`
  to `AdvisoryCandidateSet` and, mirrored, to `ProposerAdvisory`, so selection arrives
  at S2 as a contract change **and** a behaviour change. What survives is the weaker
  and still-true claim that S-1, S-2, R-1a and R-1b themselves need no amendment. See
  OD-7 parts 4 and 5 below; OD-8 is ratified as selection-policy v1
  (fail-closed uniqueness), with substantive multi-candidate ranking deferred.
* **Three catalogues, not one.** `reason_codes` (on both bearers) and
  `selection_reason_codes` await a **reason-code catalogue**; `deterministic_checks`
  awaits a **catalogue of the checks a producer may name**; `semantic_audit_refs` awaits
  a **reference scheme for audit records**. `[I]` The three were previously deferred
  under the reason-code heading alone, which misdescribed the last two: a check that was
  run and a reference to an audit record are not reason codes, and ratifying a
  reason-code catalogue would not tell an implementer what may go in either. All five
  fields are C5d and reject non-empty values; the fields exist so that populating them
  later is not a schema change, and the validators exist so that none becomes a de facto
  vocabulary before its own catalogue is ratified. A content class attaches to each only
  when **that** catalogue is ratified.
* **The reasoning-strategy permission concept and its vocabulary — deferred together
  (OD-5(iii)).** `permitted_reasoning_strategies` is **not an S1 field**. No contract in
  Part D declares it, `CognitiveRoleContract`'s cardinality is unchanged at 10, and the
  C5d roster is unchanged at five. The concept and the vocabulary that would give it
  content arrive together at S2, so that the field is declared once, in its ratified
  form, against a vocabulary that already exists. `[I]` Reserving it here was considered
  and **rejected by the owner**: a reserved empty-only list would have had to be retyped
  and have its default removed to reach that form, so reserving would not have spared a
  schema change, while it would have made every S1-era role contract carry the one value
  the ratified form must refuse. Selection of a strategy, validation of a declared one
  against a role's permitted set, and any binding of either into an identity are **S2's
  in whole**; S1 does none of them. `[R]` No member, spelling, bound or default of the
  eventual vocabulary is ratified, and none is ratified by this deferral.
* **A disposition-to-outcome mapping.** None is ratified. R-2 constrains
  `terminal_outcome` structurally and computes nothing.
* **The semantic auditor.** `SemanticAuditorFindingStatus` remains defined and
  unusable in any outcome or disposition field (D6).
* **Storage, transport, service and authorisation surfaces.** None is specified,
  authorised or implied.
* **Compute, cost and model-capability governance.** No contract in Part D carries a
  compute budget, a token or call ceiling, a model capability class or a cost value, and
  none is implied by any field here. An exploratory, non-ratified scoping of that
  cross-cutting concern is recorded in
  [`ROADMAP_UGENCE_REASONING_COMPUTE_GOVERNANCE.md`](../../../../docs/architecture/ROADMAP_UGENCE_REASONING_COMPUTE_GOVERNANCE.md).
  That document ratifies nothing, adds nothing to this specification, and authorises no
  implementation; C3 would in any case bar a bare numeric budget from every contract in
  this family.

---

# Part K — Residual limitations

These are known and **not locally decidable**. They are recorded so that no reader
mistakes their absence for coverage.

1. **Identity binds referenced identifiers, not referenced contents (D9) — narrowed by
   OD-4(a), and not closed.**

   **The candidate-content limitation is closed.** OD-4(a) puts the
   `CandidateAdvisory` entries inside `ProposerAdvisory` and therefore inside
   `P_unsigned`, so an advisory's digest now covers the dispositions, `is_eligible`
   Booleans, `observation_refs`, `evaluated_at` values, `claim_refs`, assumptions and
   uncertainties of the candidates it was derived from, and covers their order. Two
   materially different candidate sets sharing a `candidate_set_id` no longer produce
   byte-identical advisories, and an amended set makes replay fail rather than
   silently re-resolve (E1). What was recorded here as the cost of the reference-by-id
   shape is no longer a limitation of this specification.

   **The residue is open, and is the whole of what remains.** An advisory digest still
   covers the *identifiers* of everything the advisory does not carry, not the bodies
   behind them:

   * **Externally referenced observations — narrowed by the E2 replay obligation, and
     still open.** `observation_refs` entries are `ToolObservation.observation_id`
     values; the observation bodies are outside the digest. `[V]` This is **forced**:
     A3 bars nesting `ToolObservation` because `content_hash` is a rival identity name,
     and an input-digest field on the advisory would be a second identity, which D7
     forbids. It is not closeable here.

     **What E2 closes.** R-7 is no longer enforced by the builder alone.
     `verify_observation_resolution`, invoked by `verify_advisory_selection`, replays
     resolution against the complete observation collection and refuses a dangling
     reference, an ambiguous or duplicated `observation_id`, an observation that has
     moved tenant, case or source, and any attempt to present an unreferenced
     observation as evidence. So an advisory whose evidence references do not resolve,
     or resolve to observations outside its own scope, is now detectable on replay by
     any holder of the observations, not merely by whoever built it.

     **What remains open, exactly.** Replay establishes correspondence to the
     *referenced artifact*; it does not make the advisory digest bind the observation
     *content*. An observation whose body was altered while keeping its
     `observation_id`, `tenant_id`, `case_ref` and `source_ref` unchanged is **not**
     detected by anything in this package: `P_unsigned` never covered it, and E2 checks
     resolution and continuity, not content. Each observation carries its own
     `content_hash`, minted and verified by the observation producer under D5, and that
     separately verified identity — not this advisory's digest and not E2 — is what
     binds an observation's content. A consumer that needs the content bound must verify
     each observation against its producer's identity as a distinct step.
   * **Governance artifacts referenced by identifier** — `mandate_id`, `context_id`,
     `role_contract_id` and `agent_id`. Two different `WorkMandate` bodies sharing a
     `mandate_id` yield the same advisory digest, and likewise for the envelope, the
     role contract and the agent identity reference. Each of those artifacts is minted
     and verified by its own issuer under its own identity and replay checks (D1–D4);
     this package validates the reference and asserts nothing about the body.
   * **`candidate_set_id`.** The reference to the top-level `AdvisoryCandidateSet`
     remains by identifier. `[I]` The set's *candidates*, however, are pinned: R-1b
     requires the referenced set's `candidates` to equal the advisory's nested copy in
     membership, order and content, and the nested copy is in the digest. So an amended
     set is detected; what is not covered is the set's own C2 fields and
     `selection_reason_codes`, which are C5d-empty in S1.

   **Whatever stores advisories remains responsible** for the immutability of what those
   remaining identifiers resolve to, and for running each referent's own verification.
   That responsibility no longer extends to the candidates. **This residue stays open**;
   nothing in OD-4(a) closes it, and closing it would require either a nesting A3 forbids
   or an input-digest field D7 forbids.
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

7. **A conformant process record is not evidence about how the work was done (OD-5).**
   Two distinct absences, both outside what this stage can decide. The detailed
   statements are in D8 — *What the forward-only record does not represent* and
   *`declared_strategy` — an assertion, and only an assertion* — and are recorded here
   the way K.1 records D9's and G1's, so a reader consulting this part for what the
   specification does not evidence is not told less than the truth.

   * **Control flow is not represented.** R-3 admits only a forward subsequence, so a
     producer that iterated, branched or revisited a stage yields the same
     `state_transitions` as one that proceeded straight through. **The absence of
     repeated or branching transitions is therefore not evidence that no internal
     iteration or branching occurred**, and no other field in D8 carries control flow.
     Not locally decidable: closing it would require a representation of execution that
     R-3 exists to forbid.

   * **The declared method is unverified.** `declared_strategy` states what the producer
     says it did. Nothing in this stage compares that against the work, and — the field
     being outside `P_unsigned` — nothing binds it either. A record naming one method
     while the work followed another is well-formed under every rule in this document.
     Not locally decidable at S1: no S1 contract carries a permitted set, so there is
     nothing here to check a declaration against (Part J).

---

## Owner decisions

**All five owner decisions are resolved.** OD-1 to OD-3 change no contract, field type,
cardinality, vocabulary or equation term; all three are about guards and dependencies.
OD-4 did change contract shape, and its resolution is recorded below and implemented
throughout Part D. OD-5, ratified 2026-08-26, does **not** bear on contract shape: it
defers the strategy permission concept and its vocabulary together to S2, so no field is
added and `CognitiveRoleContract`'s cardinality is unchanged at 10.

**Each of OD-1 – OD-3 therefore carries three distinct statuses**, and a reader must not
collapse them. A ratified decision is not an implemented guard, and an implemented guard
is not an authorization to write production code:

| Axis | What it means | State for OD-1 – OD-3 |
| --- | --- | --- |
| **Owner decision** | Has the owner ruled? | **Resolved — ratified 2026-08-25.** No further ruling is sought or required. |
| **Enforcement implementation** | Does a named guard enforce the ruling? | **Implemented.** `[V]` All three are enforced by guards in `packages/capabilities/agentic-proposer/tests/`, including the two corrections I4 previously reported as outstanding — the O-1 guard's bearer scoping (I4.1) and the `pydantic`/`socket` boundary probe (I4.2). `[R]` They are exercised against temporary representative shapes rather than a declared contract module, so every claim that a guard arms on a contract is to be re-verified when the first contract module lands. |
| **S1 production implementation** | May contract code be written? | **Authorized on merge (A12)**, independently of the two axes above: A11's review-and-merge condition is discharged by the freeze. What remains is not a ruling and not a review — the undischarged Part I obligations, which are implementation work. |

`[R]` The middle axis is `[R]` for all three: every statement about the guard branch is
read against temporary representative shapes and is to be re-verified against the
production contract surface. The first axis is not `[R]` — a ratified decision is not a
pending ratification, and neither is an implemented guard.

**OD-1 — `primary_function` and `declared_strategy` are classified C5c. RATIFIED
2026-08-25.**

*Owner decision:* **resolved.** Both fields are C5c human-readable free text, not C5b
canonical tokens. Both are described as opaque and compared for equality only, which is
the C5b shape; they are classified as free text because neither is reachable from
`P_unsigned` (D9), so the NFC hazard that motivates B9 does not apply, and the more
restrictive classification could only reject lawful values — a role's primary function
may legitimately contain a space. `[I]` This is a derivation from B9 and O-4.

**Ratified rider — the condition on any future identity participation.** The
classification rests on unreachability from `P_unsigned`, not on a property of the
values themselves. So if either field is ever made identity-participating, the C5c
classification does **not** carry over: bringing it inside `P_unsigned` would expose it
to exactly the hazard B9 exists to close, because C6 freezes `nfc_paths` empty and the
identity function performs no Unicode normalisation, so two visually identical values
with different NFC spellings would carry different digests. **Making either field
identity-participating therefore requires a separately ratified normalization profile**
— a ruling on which normal form applies, at which paths, and at which point relative to
validation — and must not be done by reclassifying the field to C5b in passing.
Reclassifying to C5b while the field stays outside `P_unsigned` remains a narrowing, not
a redesign, and needs no new ratification.

*Enforcement implementation:* the classification is carried by the O-4 registry on
`tests/s1_specification_mirror.py`, which pins `primary_function` and `declared_strategy`
as C5c and asserts they carry no pattern constraint of any kind; I5 states what the
registry must carry.

*S1 production implementation:* authorized on merge (A12); the Part I obligations remain.

**OD-2 — `pydantic` loads `socket`, which `test_boundaries.py` forbids. RATIFIED
2026-08-25.**

*Owner decision:* **resolved.** `[V]` Reproduced: bare `import pydantic` does not load
`socket`; defining any `BaseModel` does. Every contract here is a `BaseModel` and
`pydantic>=2` is a ratified core dependency, so the first S1 contract module would fail
a whole-process `sys.modules` assertion for a reason unrelated to this package's
authority. (`[R]` That assertion was named
`test_isolated_subprocess_import_loads_no_forbidden_module` in an earlier revision; the
repair replaced it with
`test_isolated_subprocess_adds_no_forbidden_module_beyond_the_baseline`.) The ruling is to **exempt exactly the transitive route** —
`socket` reached through an approved dependency — and to keep the bar on any direct
import in `src/`. Dropping `socket` from `FORBIDDEN` outright is rejected: it would give
up a real boundary.

**The ratified enforcement design.** The exemption is not a suppression, and it is
specified so that it cannot become one. Three parts, all required:

1. **Direct-source checks.** The bar on a direct import stays absolute and is checked at
   the source: no module under `src/` may name `socket` in an `import` or `from ... import`
   statement, at module scope or inside a function, and none may reach it through
   `importlib.import_module("socket")` or an equivalent named call. This check does not
   consult the runtime module table at all, so nothing a dependency loads can mask a
   direct import.
2. **Approved-dependency baseline comparison.** The runtime probe is not relaxed to "some
   forbidden modules are fine". It compares the module table after importing this package
   against a **baseline captured from the approved dependencies alone** — importing
   `pydantic` and defining a `BaseModel`, and nothing of this package. Only modules
   already present in that baseline are exempt, and the baseline is recomputed by the
   test rather than pinned as a hand-written allowlist, so a dependency upgrade that
   starts pulling in something new is visible as a baseline change under review rather
   than as a silent pass.
3. **Negative controls.** The guard must be proven still capable of failing. A control
   module that imports `socket` directly must be rejected; a control that reaches a
   forbidden module **not** in the approved-dependency baseline must be rejected; and a
   control that imports `socket` through a *locally written* indirection rather than
   through an approved dependency must also be rejected. Without these the exemption is
   indistinguishable from a disabled test.

**The ceiling, disclosed honestly.** `[V]` This design does not close the
dynamic-import route, and no source-level or baseline check can. K.5 already records the
general form: a helper-assembled `__import__` reaches a module without a static scan
seeing it, and such a call can also run after the baseline comparison has been taken.
The guard therefore establishes that **no module in `src/` imports `socket` statically,
and that this package's import-time module table adds nothing beyond what its approved
dependencies already add** — which is a real and checkable boundary — and it does **not**
establish that no code path anywhere can reach a socket at runtime. Claiming the latter
would be false and must not appear in S1 documentation, tests or commit messages. As
with D2, the invariant is the rule and the scan is defence-in-depth.

*Enforcement implementation:* **implemented.** `[V]` I4.2 records what landed: the
five-layer probe, `DEPENDENCY_BASELINE_MODULES` derived from the declared dependency
registry, a generated baseline setup pinned by equality so an added `import socket`
fails a self-test, and `test_the_dependency_baseline_is_what_it_claims_to_be`, which
demonstrates the premise instead of assuming it. The whole-process assertion was
replaced, not exempted.

*S1 production implementation:* authorized on merge (A12); the Part I obligations remain.

**OD-3 — the O-1 guard's dependent-field set is scoped to its bearer. RATIFIED
2026-08-25.**

*Owner decision:* **resolved.** `DEPENDENT_FIELDS` is scoped to the **bearer contract**.
The **three** dependent fields — `recommended_disposition`, `requested_review_action` and
`requested_review_destination_role_ref` — are selection-dependent **on
`ProposerAdvisory`**, coupled to its `selected_candidate_id` **selector**, which is not
itself a dependent field and is held separately (B6).
`CandidateAdvisory.requested_review_action` — the candidate's own required, non-null
routing — is a different field that happens to share a name. Because `DEPENDENT_FIELDS`
is pinned by equality, the scoping must be pinned the same way: by bearer **and** field
name, never by field name alone.

*Enforcement implementation:* **implemented.** `[V]` I4.1 records what landed: `SELECTION_BEARER`, a `SELECTION_FIELD` held apart from a
three-element `DEPENDENT_FIELDS`, a `SELECTION_COUPLING` registry the class and live-type
filters both gate on, `NON_BEARERS_SHARING_A_FIELD_NAME` naming the exclusion
explicitly, and **two** self-tests pinning all of it by equality —
`test_the_coupling_is_pinned_to_the_ratified_fields` on `SELECTION_FIELD` and
`DEPENDENT_FIELDS`, and `test_the_bearer_registry_is_pinned` on `SELECTION_BEARER`,
`SELECTION_COUPLING` and `NON_BEARERS_SHARING_A_FIELD_NAME`, the latter also asserting
that the registry and the non-bearer list are **disjoint**, so a contract cannot be both
a bearer and a named exclusion.

*S1 production implementation:* authorized on merge (A12); the Part I obligations remain.

**OD-4 — `ProposerAdvisory` carries its `CandidateAdvisory` entries. RATIFIED,
resolved (a), 2026-08-25.**

**Resolution.** `ProposerAdvisory` carries per-candidate `CandidateAdvisory` entries in
an immutable `candidates` sequence, as ratified D7 states. The nesting is restored;
`candidate_set_id` is retained as the reference to the top-level `AdvisoryCandidateSet`,
which stays a top-level contract. This is no longer a question and is not reopened by
this document.

`[V]` The ratified text it restores, at
`docs/architecture/ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:333-334`:

> The proposer's recommendation artifact is named **`ProposerAdvisory`**, carrying
> per-candidate **`CandidateAdvisory`** entries.

**Rejected alternative: reference by id.** `ProposerAdvisory` carrying only
`candidate_set_id`, with the candidates reachable solely through a separately
transported `AdvisoryCandidateSet`, and ratified as an amendment narrowing D7. It is
rejected. What it offered was one real thing — an advisory that references every input
uniformly by identifier has one composition rule rather than two, so no reviewer has to
ask why `CandidateAdvisory` is inside the digest and `ToolObservation` is not. `[I]` That
is a consistency argument, not a constraint, and it does not outrank ratified D7. What it
cost was three things, each now avoided:

* **Identity coverage.** `P_unsigned` would have covered `candidate_set_id` and not the
  candidates, so an advisory's digest would have said nothing about the dispositions,
  `is_eligible` Booleans, `observation_refs`, assumptions or uncertainties it was derived
  from, and two materially different candidate sets sharing an id would have produced
  byte-identical advisories. Under (a) that content is in the digest (D9, G1, K.1).
* **A validation split with no way to close it.** R-1a and R-1b would have been split
  because a model validator holds an identifier and not the set, and an amended set
  would have left a digest-valid advisory whose candidates could not be checked at all.
  Under (a) the advisory carries its own copy, R-1b checks the two for equality of
  membership, order and content, and an amendment makes replay fail rather than
  silently re-resolve (E1).
* **Deviation from a ratified decision.** D7 is ratified text; specifying against it,
  however defensibly, is what this repository's evidence rules require be recorded as an
  owner decision rather than absorbed. (a) removes the deviation.

**What (a) does not do.**

* It does **not** bar `ToolObservation` from being nested any less firmly. `[V]` A3
  forces that bar, and observation evidence stays reference-by-id through
  `observation_refs` (D6's standing prohibition, K.1).
* It does **not** demote `AdvisoryCandidateSet`. That contract stays top-level, H3's
  contract count stays at eight, and the nested-public-model count stays at two.
* It does **not** collapse R-1b into R-1a. The referenced set is still a separate
  artifact (E1, D9).
* It does **not** make selection or `PROPOSAL` reachable in S1. C7 still makes
  `DomainCheckCompletion.COMPLETE` unconstructible, so under V13 (B3)
  `selected_candidate_id` and its three dependents are `None` on every advisory S1 can
  construct, and the fail-closed ceiling remains `NEED_EVIDENCE`, `ABSTAIN`, `ESCALATE`.
* `[R]` It does **not** trip the rival-identity walk. The corrected object graph was
  re-analysed and `reachable & RIVAL_IDENTITY_FIELDS` is empty for both roots; the
  analysis is recorded in A3 and stays `[R]` until the contract module exists.

**Where it is implemented in this document.** The intro note; A3 (conclusion and the
corrected-graph walk); B3 and B6; D6 (`AdvisoryCandidateSet` stays top-level, the
ascending-`candidate_id` ordering rule, S-1, and `CandidateAdvisory`'s standing
prohibition); D7 (the `candidates` field, cardinality 23); D9; R-1b and E1; G1; H1;
I5; I7.11; K.1.

**OD-5 — reasoning functions and strategies are distinguished, and the strategy
permission concept is deferred to S2. RATIFIED 2026-08-26.**

*Owner decision:* **resolved.** The ruling has four parts.

**(i) R-3's lifecycle is unchanged, and reasoning strategies operate within it.** A
reasoning strategy is a **method label**, not a process state. No state is added to
`ProposerProcessState`, none is removed, and R-3's forward-only subsequence rule, R-4's
agreement rule and the bar on representing execution state all stand exactly as
ratified. `[I]` The two are different kinds of thing: the lifecycle says which stages a
record passed through, and a strategy says by what method the work inside those stages
was done. A ratified strategy vocabulary would change what a role may declare and would
change nothing about the lifecycle.

**(ii) The four-way distinction is preserved and stated.** `primary_function` is the
role's organizational purpose; a role's **permitted reasoning strategies** — an S2
concept, not an S1 field — is the set of methods the role may select among;
`declared_strategy` is the method the process record asserts was used; and
`terminal_outcome` is where the work ended. The full statement, with the bearer of each
and the party who asserts it, is in D8; three of the four are S1 fields and the second is
named as a concept so the distinction can be stated whole. **Evidence collection and
verification remain contract mechanisms, and abstention and escalation remain outcomes;
none of the three is a reasoning strategy.**

**(iii) `permitted_reasoning_strategies` is deferred to S2, together with its
vocabulary.** **No field is added to D2, and OD-5 does not change S1 contract shape.**
`CognitiveRoleContract`'s cardinality stays **10** and the C5d roster stays at **five**.
The concept and the vocabulary that gives it content arrive together, so the field is
declared once, in its ratified form, against a vocabulary that already exists.

*Reserving it at S1 was considered and rejected.* A reserved C5d empty-only list would
have had to be **retyped, revalidated and stripped of its default** to reach the intended
allowlist — which rejects an empty list, the opposite rule on the same axis — so
reserving would not have spared a schema change, which is the one thing reservation
normally buys. Against that it would have cost three disclosed consequences: every
conformant S1 pair internally unsatisfiable on this axis, every S1-era role contract
carrying the one value the ratified form must refuse, and every stored contract needing
reissue at the transition. `[R]` No member, spelling, bound or default of the eventual
vocabulary is ratified here, and none is ratified by deferring it.

**(iv) S1 neither selects, validates nor cryptographically binds a reasoning strategy.**
`declared_strategy` is metadata outside `P_unsigned`; declaration does not establish
conformance; and strategy selection and enforcement are S2's in whole (Part J). A
conformant record may declare a method it did not use, and nothing in this stage detects
that.

*Bears on contract shape:* **no.** No field is added, no cardinality changes, no
classification roster changes, and no field type, vocabulary or equation term changes.
Every part of the ruling is a statement about what S1 does **not** do, or a distinction
recorded so that it is not collapsed later.

*Enforcement:* `[V]` the `P_unsigned` projection-absence assertion for
`declared_strategy` in `tests/test_advisory_contract_shape.py`; the strategy-authority
document scan, with its corpus of claims it must catch and correct statements it must
leave alone, in `tests/test_documentation_consistency.py`; and — unchanged, and now
pinning the *absence* of the deferred field — the ten-field `CONTRACT_CARDINALITY` entry
and the five-entry `C5D_ENTRIES` equality pin, which fail if it is reintroduced without a
ruling.
`[R]` As with OD-1 – OD-4, the guards are exercised against representative shapes rather
than a declared contract module, and every claim that a guard arms on a contract is to be
re-verified when the first contract module lands.

*Where it is implemented in this document.* D8 (`declared_strategy`, the four-way
distinction, and what the forward-only record does not represent); Part J's deferral;
K.7. Nothing in Part C or Part D changes.

**OD-6 — B3, H1 and R-1b(iv) were mutually inconsistent; the inconsistency is resolved
in three parts. RATIFIED 2026-08-27.**

*Owner decision:* **resolved.** An independent review of implementation commit
`6ef305fbe3ee0ff9960a7b52a1810a26f1e11953` found that B3 derived "every S1 advisory has
`selected_candidate_id = None`" from `evaluate_readiness(...)` being `False`, but R-2
conditions `PROPOSAL` on readiness **and** selection, not selection alone, and
`AdvisoryCandidateSet` was constructible in S1 with a non-null selector — S-1 and S-2
require only that it resolve and be eligible, and eligibility does not require
readiness. B3's derivation was a non sequitur.

**(i) Where the no-selection ceiling is enforced.** A non-null
`AdvisoryCandidateSet.selected_candidate_id` is structurally unconstructible in S1 (new
C9), on the same pattern C7 already uses for `DomainCheckCompletion.COMPLETE`, rather
than being refused by `build_proposer_advisory`. No dead-end object exists;
`build_proposer_advisory` and `build_advisory_revision` inherit the ceiling with no
separate builder-side check; H1's derivation paragraph needs no amendment.

**(ii) H2's exception surface.** H2 gains a fourth class, `CrossContractViolationError`
(subclassing `ValueError`, on the same pattern as `EligibilityMismatchError`), for the
Part E rules — R-1b(i)–(iv), (viii), (ix), and R-5, R-6, R-7, R-9, R-10 — that compare
fields across more than one contract instance and so cannot be decided by any single
model's own validator.

**(iii) `ProposerProcessState`'s membership and R-4's comparison basis.** The nine
members were already entailed by R-3's stated chain; what R-3 and R-4 left unstated —
the four terminal members' wire values and R-4's comparison basis — is ratified here:
the terminal four carry exactly `TerminalOutcome`'s wire values, and R-4's "equals" is
value equality.

**Rejected alternatives, for (i).** Refusing only at `build_proposer_advisory` (the
implementation this decision replaces) leaves a public object — a set carrying a
selection — that is constructible but unusable in S1, and would have required recasting
H1's non-null-selector paragraph as S2-only, new test coverage, and an explicit
statement that `build_advisory_revision` inherits the refusal. Deriving faithfully and
dropping B3's null requirement is permitted by R-2, but lets S1 emit a
`requested_review_destination_role_ref` with no specified source, and needs an
amendment to the ADR's decision record, not only to this specification.

**Rejected alternative, for (ii).** Restructuring the affected checks into single-model
validators to reach `pydantic.ValidationError` instead: rejected because several of them
(R-5, R-6, R-7) are stated over an unbounded list of supplied `ToolObservation`
instances no single contract can carry without becoming a second identity surface, so
reaching `ValidationError` this way would require a throwaway aggregate model
constructed for the sole purpose of obtaining the right exception type.

*Bears on contract shape:* **no.** No field is added, removed or retyped, and no
cardinality changes. (i) narrows an already-declared field's constructibility on the C7
pattern; (ii) adds an exported exception class; (iii) ratifies a previously unstated
vocabulary/comparison-basis detail of an already-declared field and enum.

*Enforcement:* `[V]` **implemented, and (i) subsequently superseded.** The C9 validator
(`AdvisoryCandidateSet._selection_is_unconstructible`, `contracts.py`) stood at
`0.1.0` and was **removed by OD-7 part 8** at `0.2.0`, in the same change set that
introduced the couplings and selection-policy v1 that took over its fail-closed role;
(ii) and (iii) are unaffected. `CrossContractViolationError` (`verification.py`, exported via `__init__.py` and
`public_api.json`) at its three actual raise-statement sites in `identity.py` — the
shared `_require_equal` helper (R-5, R-6, R-10) and two inline raises (R-9, R-7) —
and the corresponding test coverage are recorded in
`docs/architecture/ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md`'s OD-6 row and
guard-evidence paragraph and in `CHANGELOG.md`.

*S1 production implementation:* the C9 validator, `CrossContractViolationError` and its
three call sites were written and tested; that is what ran at `0.1.0`. `[V]` At `0.2.0`
the C9 validator is gone and its ceiling is carried by the OD-7 part 5 couplings and
OD-8's selection recomputation; `CrossContractViolationError` and its call sites are
unchanged.

*Where it is implemented in this document.* B3; new C9; D6 (`selected_candidate_id`'s
Validation column); the `ProposerProcessStateTransition` section; Part E's header note
and the R-1b/R-4/R-5/R-6/R-7/R-9/R-10 rows; H1; H2; H3.

---

## Ratification statement

D1–D10, B2, B3 (V13), B4 (O-2), B5 (O-3), B6 (O-1), B7, B8 and B9 (O-4) are resolved,
and this document contains no placeholder: every field carries a type, a requiredness, a
nullability, a default, a cardinality, a vocabulary, a classification and an identity
participation.

**OD-4 is resolved (a)**, and with it the question that had been open longest about
contract shape. `ProposerAdvisory` carries its `CandidateAdvisory` entries, as ratified
D7 says; Part D is written for that shape and no longer for an alternative. **Of the six
owner decisions, OD-4 is the one that bears on contract shape**; OD-5 and OD-6 were
ruled not to, and Part D is unchanged by either.

**All six owner decisions are resolved, and so are OD-7 through OD-10: OD-1 through
OD-10 are decided. No owner decision is outstanding; substantive multi-candidate
ranking is deferred to a future ruling that does not yet have a number.** OD-7 is
stated separately below, because it is itself a boundary ratification, not a complete
executable algorithm. `[R]` **OD-8, OD-9 and OD-10 are ratified
2026-08-28** and are recorded inside OD-7's own entry, in part 4 and part 7; `[V]` like
OD-7 they are now **implemented**, in the single change set part 8 requires. OD-1,
OD-2 and OD-3 are ratified 2026-08-25 and are recorded above with their riders and
their enforcement designs; none changes a contract, a field type, a cardinality, a
vocabulary or an equation term. **OD-5 is ratified 2026-08-26**: it changes no
contract, field type, cardinality, vocabulary or equation term either. It states what
S1 does not do with a reasoning strategy, preserves the four-way distinction, and
defers the strategy permission concept and its vocabulary together to S2. `[R]` That
vocabulary requires its own ruling and is not given one here. **OD-6 is ratified
2026-08-27**: it adds a validation rule (C9), an exported exception class (H2), and a
previously unstated vocabulary/comparison-basis detail (`ProposerProcessState`, R-4) —
none of which is a contract field, type or cardinality change — resolving an
inconsistency between B3, H1 and R-1b(iv) that an independent implementation review
found. `[V]` Its three parts are ratified as specification text and implemented
against the contract module, with test coverage in `tests/test_s1_implementation_
obligations.py`'s `OD-6` sections and `tests/test_process_ordering_obligation.py`.

**OD-7 is ratified 2026-08-27 and implemented.** It resolves the S2 domain-evaluation
and candidate-selection boundary in eight parts (above), and — unlike OD-1 – OD-3, OD-5
and OD-6 — it **does** bear on contract shape: `CandidateAdvisory`,
`AdvisoryCandidateSet` and `ProposerAdvisory` each gained fields when it was built.
`[V]` C7 and C9 are removed, in that same change set and no earlier. **Production and
behavioural guards exercise the OD-7 selection surface** in
`packages/capabilities/agentic-proposer/tests/test_od7_domain_evaluation_boundary.py`,
which discharges `I8.1` – `I8.15`; `[V]` the **documentation-consistency guards** in
`tests/test_documentation_consistency.py` remain what they were — they pin the
OD-8/OD-9/OD-10 meanings and the OD-7 statements those rulings amended, part 5's replay
rule and part 7's fail-closed table — and are still **not production enforcement**:
they check what these documents say, not what any selector does, which is why the
behavioural module stands beside them rather than replacing them. `public_api.json`
moves from 39 to 46 names and `version.py` from `0.1.0` to `0.2.0`, both in that same
change set. The three-status discipline this section states for OD-1 – OD-6 — a
decision is ratified; a named guard implements it; S1 production implementation is a
separate, later authorization — applies to OD-7 exactly as written, and all three
statuses are now true of it: its own transition controls (part 8) are satisfied, and
the independent consistency review the ruling directs is the remaining step.

**OD-7 — S2 domain-evaluation and candidate-selection boundary. RATIFIED 2026-08-27;
IMPLEMENTED.**

*Owner decision:* **resolved**, in eight parts. OD-7 scopes only the boundary that
removes C7 and C9 — the domain evaluator and the candidate selector. It does not scope
reasoning-strategy permissions (OD-5(iii)), the three deferred catalogues (Part J),
semantic auditing, or storage, transport, HTTP or deployment surfaces; those remain
separately deferred to S2 without a ruling here.

**(1) Domain evaluation and candidate selection are separate responsibilities, shipped
in one ordered boundary.** The evaluator determines domain-specific results; the
selector consumes verified results. Selection must never determine, influence or
retroactively complete domain evaluation — the two are decided by different code, on
different inputs, and neither may read the other's not-yet-settled state.

**(2) The domain-evaluator boundary is a narrow injected protocol, not an embedded
implementation.** Agentic Proposer owns a `DomainEvaluationProvider` protocol, the
provider's input and output shapes, orchestration (the call) and verification (the
replay). A concrete business-domain evaluator lives outside this package and is
supplied by the caller as an already-constructed object satisfying the protocol;
Agentic Proposer imports, discovers, loads or embeds no particular evaluator, and no
network, storage, service-discovery or plugin-loading mechanism is authorized by this
ruling — the injected object is a plain in-process callable, nothing more.

The protocol:

```python
class DomainEvaluationProvider(Protocol):
    def evaluate(self, *, request: DomainEvaluationRequest) -> DomainEvaluationResponse: ...
```

`DomainEvaluationRequest` and `DomainEvaluationResponse` are call-boundary shapes,
exported for typing like `CandidateAdvisory` and `ProposerProcessStateTransition` are
today, but with no C2 common field and no identity role of their own — neither is ever
stored, transported or included in `P_unsigned`; only the outcome the response carries
is bound (part 5, below). `DomainEvaluationRequest` is assembled solely from
already-identity-bound public content — the one candidate under evaluation, its
referenced `ToolObservation`s, the `WorkMandate` and `BoundedContextEnvelope` in force,
and the profile identity/version the caller is requesting evaluation under — so the
evaluator receives no hidden state. `DomainEvaluationResponse` carries the outcome
(part 3) and echoes back **both** the profile identity/version it actually evaluated
under **and** the `candidate_id` it actually evaluated, on the same reasoning in both
cases.

`[I]` **What the echo is, and what it is not.** It is a **request/response correlation
check**: it catches a provider that mixed up concurrent or batched requests, answered
under a stale profile, returned a cached result for a different candidate, or was
wired up wrongly — the ordinary integration faults that would otherwise bind a
mismatched outcome into `P_unsigned` silently. It is **not** a defence against a
dishonest provider, and must not be described as one: a provider that wishes to
mislead simply echoes back the profile and `candidate_id` it was handed while
evaluating something else, or nothing at all. Nothing in this boundary can detect
that, because the provider is the sole authority on its own result. `[G]` The
provider is trusted for the substance of what it returns; the echo constrains only
that the substance is labelled with the request it answers.

**(3) `DomainCheckCompletion` continues to gate only whether evaluation ran; it does
not encode the result — and its substantive reading is stated here for the first
time, not carried over from C7's own wording.** C7 itself says only that `COMPLETE`
closes the enum and makes Equation 2 total; it does not say what "evaluation having
run" consists of. **OD-7 supplies that reading**: `COMPLETE` means every check the
applicable versioned domain-evaluation profile requires reached a *per-check*
determinate reading — none left pending, none erroring, none timed out — regardless
of whether those readings, taken together, resolve to a clean pass or fail. The
*result* of aggregating those per-check readings — `SATISFIED`, `NOT_SATISFIED` or
`INCONCLUSIVE` — is carried by a new, separate closed vocabulary,
`DomainEvaluationOutcome`, on a new field, `CandidateAdvisory.domain_evaluation_
outcome: Optional[DomainEvaluationOutcome] = None`, coupled to `domain_check_
completion` by a new validator on the same terms R-1a already couples fields: present
if and only if `domain_check_completion is COMPLETE`, absent if and only if it is
`NOT_EVALUATED`.

`[I]` **Why `INCONCLUSIVE` is reachable under that coupling, not excluded by it.**
`COMPLETE`'s "determinate result" is a claim about *process* — every check ran to a
recorded per-check conclusion — not a claim about *substance*, that those conclusions
agree with one another. `INCONCLUSIVE` is itself one of `DomainEvaluationOutcome`'s
three closed members: recording it is a determinate act — the aggregation logic
reached a definite, recorded answer, *the checks do not converge*, rather than
leaving anything unresolved — even though the answer it records is an absence of
convergence. A profile whose checks all ran and each individually resolved, but whose
aggregation rule cannot state a clean `SATISFIED` or `NOT_SATISFIED` across them, is
`COMPLETE` (nothing is still pending or broken) **and** reports `INCONCLUSIVE` (the
aggregate reading is stated ambiguity) at the same time. If `COMPLETE` instead meant
*the aggregate is itself unambiguous*, `INCONCLUSIVE` could never be stored — which
would be exactly the `DomainCheckCompletion` overload the Rejected Alternatives list
below already forbids, reintroduced through the coupling rule rather than through the
field's own type.

`DomainEvaluationOutcome` deliberately does **not** reuse `INDETERMINATE`: D4 reserves
that spelling to exactly two authority-adjacent positions (`TerminalOutcome`,
`CandidateDisposition`) and ratifies it in exactly one non-authority position
(`SemanticAuditorFindingStatus`). A third position was not ratified by D4 and this
ruling does not ratify one; `INCONCLUSIVE` is used instead, and the two spellings are
asserted never to collide by a boundary test (I8.8, below).

**(4) Candidate selection, for the S2 MVP, is a deterministic, versioned, in-package
function — not an injected provider.** The selector considers only candidates that are
`is_eligible is True` **and** carry `domain_evaluation_outcome is SATISFIED` — call
these the **qualifying pool** — ; it consumes no state outside the candidate set's own
fields; it selects at most one candidate; and it selects none when no unique lawful
candidate exists.

`[R]` **Per-candidate scope (OD-9).** `domain_evaluation_outcome` is evaluated **per
candidate** and does **not** poison the candidate set. A candidate carrying
`NOT_SATISFIED` or `INCONCLUSIVE` is **filtered out of the qualifying pool, and
nothing more**: it does not prevent selection of a different candidate that is
eligible and `SATISFIED`. A set containing exactly one qualifying candidate alongside
any number of `INCONCLUSIVE` or `NOT_SATISFIED` candidates therefore **selects that
one candidate**. The fail-closed conditions below are conditions on the **qualifying
pool**, never on the presence of any individual non-qualifying candidate. Model-assisted
candidate generation and explanation remain permitted upstream of selection (unchanged
from S1); an LLM may not populate `selected_candidate_id` directly, and model-assisted
selection is out of scope of OD-7 and requires its own separate ratification.

**OD-8 — RATIFIED: selection-policy v1 is fail-closed uniqueness.** `[R]` The selector
automatically selects a candidate **only when exactly one** candidate is both
`is_eligible is True` and `domain_evaluation_outcome is SATISFIED`. When **more than
one** candidate qualifies, selection-policy v1 makes **no selection** and the run
terminates `ABSTAIN` — consistent with S-1's already-ratified reading that declining
to select among eligible candidates is `ABSTAIN`, not a forced recommendation.

`[R]` **No existing candidate field is ratified as a substantive measure of
preference.** Timestamps, identifiers, dispositions, review actions, reference counts,
assumption counts and uncertainty counts **must not** be repurposed as merit proxies.
`[I]` The reason is provenance, not expressiveness: of `CandidateAdvisory`'s fields
only `is_eligible` is package-computed and replay-verified, and only
`domain_evaluation_outcome` will be provider-produced and replay-verified. Every other
field — `candidate_id` included — enters through caller-supplied builder parameters,
so ranking on any of them would let the caller steer selection; ranking on fewer
`uncertainties` would additionally punish honest disclosure.

`[G]` **Substantive multi-candidate ranking remains deferred**, and no new ranking
field is introduced by this ruling. It requires a separate ruling identifying: the
business objective defining candidate merit; the authority entitled to produce the
ranking input; its deterministic, **non-floating-point** representation (`[V]` the
canonicalisation substrate raises `BareNumberError` on any `int` or `float` and
`UnsupportedTypeError` on `Decimal`, so any numeric rank must be a canonical decimal
*string*); its provenance and identity binding; and how replay verifies it without
allowing an untrusted caller to steer selection. `[R]` The `DomainEvaluationProvider`
is authoritative **only** for the domain-evaluation responsibility OD-7 ratifies; it
does **not** acquire business-preference authority through this or the OD-8 ruling.

`[R]` **Ratified constraint on any future criterion: it must be computable from the
candidate set's own fields.** Part 4 states the selector "consumes no state outside
the candidate set's own fields", and `verify_deterministic_selection(*, candidate_set)`
takes the set as its only argument, so a criterion needing anything else — a scoring
service, a per-tenant policy table, a model call, wall-clock time, or any datum not
carried by `AdvisoryCandidateSet` — would be unreplayable by the very function OD-7
ratifies to replay it, and is therefore excluded.

`[R]` **Tie-break correction to OD-7.** An earlier statement of part 4 held that
ascending `candidate_id` is "always decisive" over whatever OD-8 leaves tied. That is
**too broad and conflicts with fail-closed uniqueness**, and is corrected here as a
change to ratified selection semantics, not an implementation detail. The corrected
rule, in four parts: (i) `candidate_id` may break a tie **only after** a ratified
substantive selection policy has established that the tied candidates are equally
preferable and lawfully selectable; (ii) `candidate_id` **must not** substitute for a
missing substantive preference criterion; (iii) under selection-policy v1 more than one
qualifying candidate produces **no selection**, so the tie-break is **deliberately
unexercised**; (iv) a future selection-policy version may activate it only after that
version's substantive ranking criterion and authoritative inputs are separately
ratified. `[V]` The underlying mechanical fact is unchanged and still holds —
`_check_candidate_sequence` (`contracts.py:169-177`, mirrored on the `P_unsigned`
payload at `identity.py:111`) requires `candidate_id` to be unique within a set and
supplied in ascending order, so the ordering *is* total over distinct keys. What is
withdrawn is the inference that totality alone licenses using it to resolve a
substantive preference the owner has not ratified.

**(5) Identity and replay: this is not a zero-contract-shape transition.**
`P_unsigned` must bind the domain-evaluation profile identity actually used, each
candidate's domain-evaluation result, and the selector-policy identity actually used.
Recording any of these only on `ProposerProcessRecord` is rejected, on the owner's own
ground: that record is outside `P_unsigned` and can change without changing advisory
identity, so nothing about it is provable by `verify_advisory_identity`.

Field ownership (all `Optional`, all coupled by new validators on the terms stated):

| Contract | New field | Coupled to |
| --- | --- | --- |
| `CandidateAdvisory` | `domain_evaluation_outcome: Optional[DomainEvaluationOutcome]` | `domain_check_completion is COMPLETE` (part 3) |
| `AdvisoryCandidateSet` | `domain_evaluation_profile_id: Optional[Token]`, `domain_evaluation_profile_version: Optional[Token]` | present iff any nested candidate's `domain_check_completion is COMPLETE`; a set-level fact, not a selection-dependent one |
| `AdvisoryCandidateSet` | `selection_policy_id: Optional[Token]`, `selection_policy_version: Optional[Token]` | present iff `selected_candidate_id` is not `None`, on the R-1a pattern, scoped to this bearer alone (OD-3's lesson: scoped by bearer and name, never by name alone) |
| `ProposerAdvisory` | the same four `AdvisoryCandidateSet` fields, mirrored | reachable inside `P_unsigned` only because they are `ProposerAdvisory`'s own fields; R-1b gains two correspondence clauses requiring the mirrored values to equal `AdvisoryCandidateSet`'s |

`[I]` **C5 classification.** All four of `domain_evaluation_profile_id`,
`domain_evaluation_profile_version`, `selection_policy_id` and
`selection_policy_version` are **C5b**: each is a vocabulary term matched by
equality — the profile pair against an independently supplied expected profile, the
policy pair against this package's own ratified selector identity (both below) — not
an opaque handle carried and compared whole, so all four take the `Token` pattern,
not `Identifier`. Once implemented, the C5b roster (currently `agent_version`,
`tool_name`, and each element of `allowed_source_scopes`, `excluded_data_classes`,
`permitted_tool_scopes` and `tool_invocations`) grows by these four.

`CandidateAdvisory`'s cardinality moves from the ratified 10 to 11; `AdvisoryCandidateSet`'s
from 8 to 12; `ProposerAdvisory`'s from 23 to 27. `[V]` **All three current numbers are
pinned by existing tests, and those pins are part of the change set.**
`CONTRACT_CARDINALITY` in `tests/s1_specification_mirror.py:212-223` declares
`AdvisoryCandidateSet: 8`, `CandidateAdvisory: 10` and `ProposerAdvisory: 23`,
enforced by `tests/test_identifier_normalization.py:743-750`
(`test_the_registry_carries_exactly_the_stated_cardinality`, parametrized over every
entry) and again at `:756`
(`test_the_advisory_carries_the_twenty_three_ratified_fields`, a hard-coded 23), with
a third assertion of the same 23 at `tests/test_selection_dependent_fields.py:664`.
Adding the OD-7 fields will fail all three until they are updated in the same commit;
that update is an obligation of the change set (I8.11), not a repair after it. The
target numbers 11, 12 and 27 remain the amendment's own arithmetic and are to be
re-verified against `src/` once implemented, exactly as OD-4's cardinality claims were.

`[I]` The evaluation profile identity is held once per set, not once per candidate,
because a single proposer run evaluates every one of its candidates for one case under
one profile; a per-candidate profile identity would let two candidates in the same set
be evaluated under different, non-comparable profile versions with nothing in this
document forbidding it, which would make the eventual selection incomparable across
candidates. If the owner intends multiple profiles within one set, that is a further
ruling this amendment does not make.

Two new replay functions, both recomputing from stored content only:

* `verify_domain_evaluation(*, provider, candidate_set, mandate, context, observations,
  expected_profile_id, expected_profile_version) -> bool` — **not** a self-check
  against the candidate set's own recorded profile: `expected_profile_id` and
  `expected_profile_version` are supplied by the caller from a source outside the
  advisory under test (the profile currently configured or ratified for this case),
  precisely so the function cannot be satisfied merely by a provider echoing back
  whatever profile identity a tampered `AdvisoryCandidateSet` happens to record. For
  every candidate whose `domain_check_completion is COMPLETE`, it (a) checks the
  stored `domain_evaluation_profile_id`/`version` equal `expected_profile_id`/
  `expected_profile_version`; (b) re-issues a `DomainEvaluationRequest` carrying the
  *expected* profile and the candidate's own `candidate_id` to `provider`; and (c)
  checks the response's echoed profile identity, its echoed `candidate_id` (part 2),
  and its outcome equal, respectively, the expected profile, the candidate under
  test, and the stored `domain_evaluation_outcome`. `[G]` **Disclosed ceiling**: this
  proves the recorded profile matches what was independently expected and that
  invoking `provider` again under that profile reproduces the stored outcome; it does
  **not** and cannot prove the *original* evaluation was correct if `provider` is
  non-deterministic or its behaviour has since changed under an unchanged version
  label — the same class of ceiling C9's docstring already discloses for
  `model_construct`, stated here for a different mechanism. Four further limits, all
  of them consequences of what replay operates on, are disclosed rather than left for
  a reader to discover:
  * **Candidate suppression is invisible.** Replay iterates the candidates the set
    *contains*. A candidate never added — dropped upstream of `AdvisoryCandidateSet`
    construction, whether by fault or by choice — leaves no trace in `P_unsigned` and
    no verifier can report its absence. Identity binds what was recorded, not what
    could have been.
  * **A profile label is not a profile.** `domain_evaluation_profile_id`/`version` are
    `Token`s compared by equality. Two different providers, or one provider before and
    after an unversioned change to its own rules, can present the same label; replay
    then confirms agreement between two things that share a name and nothing more.
    Binding the profile's own content by digest would close this and is deliberately
    not adopted here (Rejected Alternatives, below).
  * **There is no selector-policy registry.** `verify_deterministic_selection` checks
    `selection_policy_id`/`version` against this package's own ratified constants, so
    it detects a foreign or stale label; it does not and cannot establish that the
    named policy *is* the logic that produced the stored selection on some other
    installation, because no registry maps a policy identity to its ratified
    definition. Within one installation at one version this is sound; across versions
    it degrades to a label comparison.
  * **Replay proves reproducibility, never authority.** Every check above answers
    "does re-running agree with what was stored", which is a different question from
    "was the stored answer right". The provider remains the sole authority on domain
    substance, and OD-7 does not change that.
* `verify_deterministic_selection(*, candidate_set) -> bool` — `[R]` recomputes the
  **qualifying pool** solely from the candidate set's own members that are
  `is_eligible is True` **and** carry `domain_evaluation_outcome is SATISFIED`, then
  checks the stored selector against **selection-policy v1** (OD-8, part 4): when the
  qualifying pool holds **exactly one** candidate, `selected_candidate_id` must equal
  that candidate's identifier; when the qualifying pool holds **zero or more than one**
  candidate, `selected_candidate_id` must be `None`. **Selection-policy v1 does not
  apply the `candidate_id` tie-break**, so the verifier neither computes nor consults
  it; a future policy version may activate a tie-break only after a separately ratified
  substantive criterion establishes that the remaining candidates are equally preferable
  and lawfully selectable. It **also** checks that the
  stored `selection_policy_id`/`selection_policy_version` equal this package's own
  ratified selector identity/version constants — so a `selected_candidate_id` that
  happens to match the recomputation but is *labelled* as coming from a different,
  unratified policy still fails replay. This is what `verify_advisory_selection`'s
  existing structural correspondence check does **not** do today (it checks the two
  selectors *agree with each other*, not that either is the ratified selector's own
  lawful output), so `verify_advisory_selection` gains a call to this function rather
  than being replaced by it.

**Malformed input, a provider exception, and missing evidence are three different
things, and OD-7 does not let them collapse.**

* **Malformed input** — a `candidate_set` or `advisory` that bypasses the
  construction-time coupling validators above via `model_construct` or
  `model_copy(update=...)`, the same disclosed bypass C7 and C9 already state: both
  replay functions return `False`, never raise, on H1's unchanged terms.
* **A provider exception raised during replay** (inside `verify_domain_evaluation`'s
  own call to `provider.evaluate(...)`): caught internally and treated as a
  verification failure — the function returns `False` and does **not** propagate the
  exception — so a read-only auditor calling a verifier never needs exception
  handling, exactly as H1 requires of every verifier.
* **A provider exception raised during the original build** (inside
  `build_proposer_advisory` or `build_advisory_revision`'s own call to the provider):
  caught and re-raised as `DomainEvaluationProviderError` (H2), so a caller catches one
  named exception family for every OD-7 construction-time failure rather than an
  arbitrary third-party type — builders raise, verifiers report, H1's own distinction,
  applied here.
* **Missing evidence needed to assemble a `DomainEvaluationRequest`** (an
  `observation_refs` entry that does not resolve): detected by the same
  `_resolve_references` replay E2 already uses, **before** the provider is ever
  called. It **warns**, via `warnings.warn` naming the failing reference, on the same
  terms E2 already does — it does not raise and does not return a bare `False` from
  either new replay function, because it is not either function's concern. The
  builder does not call the provider at all in this case, and the run is directed to
  `NEED_EVIDENCE` (part 7's first row): this is an orchestration decision, not a
  return value.

**(6) Required execution order**, an orchestration requirement rather than a contract
field: candidate construction -> Equation 1 eligibility -> domain evaluation ->
domain-result verification -> deterministic selection -> Equation 2 readiness ->
advisory construction. `[I]` **"Candidate construction" here names an internal,
pre-contract representation, not the frozen `CandidateAdvisory` instance.**
`CandidateAdvisory` is frozen (C1); nothing in this package mutates a constructed
instance, and OD-7 creates no exception to that. The actual `CandidateAdvisory`
object — the one carrying `domain_evaluation_outcome` — is instantiated exactly once,
with every field already known, only *after* domain evaluation and its verification
complete for that candidate, on the same G2 discipline `ProposerAdvisory` itself
already follows: constructed in one expression, never assembled incrementally. What
precedes that single construction — eligibility, the request sent to `provider`, the
response received — operates over plain, non-contract data assembled from the
candidate's other already-known values, not over a `CandidateAdvisory` missing one
field and later completed. Selection must not be attempted until every candidate it
would consider has a verified, `COMPLETE` domain evaluation on its own
already-constructed `CandidateAdvisory`; Equation 2 readiness is evaluated only after
selection. This is a builder-sequencing obligation, enforced when implemented by an
ordering test on the S2 construction entrypoint, on the same style R-3 enforces
process ordering today — no new contract field encodes it.

`[V]` **Equation 2 gains a term, and Part F is amended by this ruling.** An earlier
draft of OD-7 held the opposite — that `evaluate_readiness`'s existing
`domain_checks_complete` term sufficed, because under the order above Equation 2 is
invoked only *after* selection and only against the candidate selection chose, which
the selector (part 4) already requires to be `is_eligible is True` and
`domain_evaluation_outcome is SATISFIED`. **That reasoning is withdrawn: the
repository contradicts it.** `evaluate_readiness` is an exported public symbol
(`equations.py:32`, `__init__.py:106`, `public_api.json`) with no caller anywhere in
`src/`, so "invoked only after selection" is a convention this package states and
cannot enforce against a consumer calling the function directly. With C7 removed, a
candidate carrying `COMPLETE`, `NOT_SATISFIED` (or `INCONCLUSIVE`), `is_eligible is
True` and matching lineage would return `True` from Equation 2 — R-2's condition for
`terminal_outcome=PROPOSAL`. `[V]` Today's V13 (`contracts.py:747-763`) is a blanket
refusal of `PROPOSAL` that never calls `evaluate_readiness`, which it can be only
because C7 makes `COMPLETE` unconstructible; the exposure therefore opens not on C7's
removal alone but when V13 is reimplemented to enforce R-2's recomputation as
ratified — which part 8 requires to happen in the same change set. The effect is the
strongest classification reached for a candidate domain evaluation rejected, with
`domain_checks_complete` compensating for a substantive result it does not carry,
against Part F's own **No term compensates for another** rule.

**Resolved: Equation 2 gains a seventh term**, `DomainEvaluationSatisfied` —
`candidate.domain_evaluation_outcome is DomainEvaluationOutcome.SATISFIED` — recorded
in Part F's Equation 2 table and its `all((...))` form. The term is inert in S1, where
the field does not exist and C7 already forces the equation `False`; it is added to
`equations.py` only in the single change set that adds the field and the vocabulary
and removes C7 and C9 together (part 8). **Rejected alternative — leave Part F
unchanged and rely on the documented call order.** Rejected because the order is
unenforceable against an exported function, so the guarantee would rest on consumer
discipline at exactly the point where fail-closed behavior matters most; C7 performs
that closure structurally today, and its removal must hand the closure to a term, not
to a convention.

**(7) Fail-closed behavior.** None of the following may fall through to a silently
chosen candidate:

`[R]` **The rows are evaluated in the order given and do not overlap.** Each condition
is stated on the **qualifying pool** (part 4) — candidates that are `is_eligible is
True` **and** `domain_evaluation_outcome is SATISFIED` — never on the presence of an
individual non-qualifying candidate. The first matching row governs; exactly one row
matches any completed run.

| # | Condition | Outcome |
| --- | --- | --- |
| 1 | Missing evidence, or the evaluator is unavailable | no selection; `NEED_EVIDENCE` |
| 2 | The provider's echoed profile, its echoed `candidate_id`, its result, or the selector-policy identity cannot be verified | refuse construction |
| 3 | **Exactly one** candidate in the qualifying pool | **select it** |
| 4 | **More than one** candidate in the qualifying pool | no selection; `ABSTAIN` — **OD-8**, selection-policy v1 fail-closed uniqueness; the `candidate_id` tie-break is deliberately unexercised |
| 5 | Qualifying pool **empty**, and at least one evaluated candidate is `INCONCLUSIVE` | no selection; `ABSTAIN` — **OD-9** |
| 6 | Qualifying pool **empty**, and **no** candidate is `INCONCLUSIVE` (e.g. every evaluated candidate is `NOT_SATISFIED`, or none is eligible) | no selection; `ABSTAIN` — **OD-10** |

`[R]` **OD-9 — `INCONCLUSIVE` maps to `ABSTAIN`** (row 5), unconditionally for the S2
MVP. `ESCALATE` is **not** selected, on two grounds the repository supports: no
authoritative, replayable severity or escalation condition is ratified, so any
conditional mapping would rest on a caller-supplied input; and `[V]` no ratified rule
connects this outcome to an effective referral destination — under R-1a a no-selection
run carries `requested_review_destination_role_ref = None` (`contracts.py:602-618`),
so a terminal `ESCALATE` here would assert a referral with no in-contract destination.
`CognitiveRoleContract.escalation_role_ref` (`contracts.py:294`) exists but `[G]` no
ratified rule connects it to a terminal `ESCALATE`. A later ruling may revisit this
once a severity authority exists; nothing here forecloses that.

`[R]` **OD-10 — the residual completed no-selection outcome** (row 6). When domain
evaluation has **completed**, no candidate is both eligible and `SATISFIED`, and no
candidate is `INCONCLUSIVE`, the selector makes no selection and the terminal outcome
is `ABSTAIN`. This covers every evaluated candidate being `NOT_SATISFIED`, and no
candidate being eligible. It does **not** cover missing evidence, evaluator
unavailability or verification failure, whose OD-7 behaviour (rows 1 and 2) is
unchanged. OD-10 exists so that a completed run cannot fall through the table with no
ratified outcome.

`[I]` **Two rows an earlier draft of this table carried, and why they are gone.** That
draft also listed "an unresolved tie survives the ratified ranking criterion and the
`candidate_id` tie-break" as an `ESCALATE` trigger, and listed "evaluators disagree"
alongside `INCONCLUSIVE`. Neither survives, though the first is now gone for a
**different reason than the one originally given**. `[R]` The original reasoning — that
the `candidate_id` tie-break is always decisive, so no tie can survive it — is
**withdrawn by OD-8's tie-break correction** (part 4): totality over distinct keys is
still a fact, but it no longer licenses resolving a substantive preference, and under
selection-policy v1 the tie-break is deliberately unexercised. The row is absent under
OD-8 because more than one qualifying candidate is not an escalation trigger at all:
it is row 4 above, no selection and `ABSTAIN`. "Evaluators disagree"
presupposes more than one evaluator; OD-7 ratifies exactly one injected `provider`
returning one outcome per candidate, and multi-provider evaluation is not ratified by
it (Rejected Alternatives, below) — so the row above states only the single-provider
case, `INCONCLUSIVE`, which already covers a provider's own internal non-convergence
across a profile's checks.

`[G]` The exact disposition-to-terminal-outcome mapping beyond the row above remains
separately ratified where it is not already fixed by R-2 and R-4.

**(8) Transition controls.** `[V]` **Satisfied.** C7 and C9 remained active and
unmodified until every OD-7
contract field, vocabulary member, protocol, identity projection, replay function and
test obligation below was ratified **and** implemented in the same change set, and were
removed in that change set and no earlier. Neither
validator may be removed as an isolated edit: removing C9 alone would let a caller
hand-construct a non-null `selected_candidate_id` with no evidence it came from the
ratified deterministic policy, and removing C7 alone would let `COMPLETE` be asserted
with no bound evaluation result to check it against. The coupling validators in part
5's table, together with the two replay functions, are what take over C7's and C9's
fail-closed role; that handover is the reason the two removals and the new machinery
must land together.

**OD-7 ratifies a boundary, not a complete executable algorithm.** The contracts,
vocabulary, protocol, identity bindings and fail-closed structure above are ratified.
`[R]` **OD-8** (selection-policy v1, part 4), **OD-9** (`INCONCLUSIVE` to `ABSTAIN`,
part 7) and **OD-10** (the residual completed no-selection outcome, part 7) are
**ratified 2026-08-28** and are recorded in those parts. What remains deferred is
**substantive multi-candidate ranking**, which OD-8 declines to invent and which needs
its own ruling naming a business objective, an authoritative producer, a
non-floating-point representation, an identity binding, and a replay path no untrusted
caller can steer. `[V]` The OD-7 surface is implemented, on part 8's terms.

*Bears on contract shape:* **yes.** Unlike OD-1 – OD-3, OD-5 and OD-6, OD-7 adds fields
to three contracts (part 5's table) and is the second of the seven owner decisions,
after OD-4, to do so. Unlike OD-4, OD-7 amends a specification this document has
already declared frozen (below); implementation is authorized only on the terms part 8
states, exactly as A12 already separates ratification from production authorization
for every other decision in this section.

*New vocabulary:* `DomainEvaluationOutcome` — `SATISFIED`, `NOT_SATISFIED`,
`INCONCLUSIVE`.

*New exception (H2 gains a fifth class):* `DomainEvaluationProviderError(ValueError)` —
raised when a provider's echoed profile identity, its echoed `candidate_id`, its
returned outcome, or the recorded selector-policy identity cannot be verified against
what the request or the ratified policy actually specifies, or when `provider` itself
raises during the original build (part 5's malformed-input/exception/missing-evidence
subsection); not a field-validation failure, on the same grounds
`EligibilityMismatchError` and `CrossContractViolationError` are not.

*New call-boundary shapes (not top-level contracts, no identity role):*
`DomainEvaluationProvider` (a `typing.Protocol`), `DomainEvaluationRequest`,
`DomainEvaluationResponse`.

*New or changed functions* — `[V]` all implemented, and added to `public_api.json` in
the change set that implemented them rather than by this amendment:
`verify_domain_evaluation` (taking
`expected_profile_id`/`expected_profile_version` as caller-supplied parameters, part
5), `verify_deterministic_selection`; `build_proposer_advisory` and `build_advisory_
revision` gain required keyword parameters for the injected `provider`, the expected
profile identity, and the selection inputs; `verify_advisory_selection` gains an
internal call to `verify_deterministic_selection`.

**Rejected alternatives.**

* *Overloading `DomainCheckCompletion` with a pass/fail/authority reading* — rejected
  by the owner's ruling itself (part 3): it would make a structural "did evaluation
  run" fact indistinguishable from a substantive "did it pass" fact, and would put an
  authority-shaped value on a field D4's four-way discipline was written to keep clean
  of exactly that.
* *Recording the evaluation result and selector-policy identity only on
  `ProposerProcessRecord`* — rejected by the owner's ruling itself (part 5): that
  record sits outside `P_unsigned` and can change without changing advisory identity,
  so nothing about it is provable by `verify_advisory_identity`.
* *A per-candidate domain-evaluation profile identity* — rejected (part 5's `[I]` note
  above): nothing would then forbid two candidates in one set being evaluated under
  incomparable profile versions.
* *A single combined digest field for the evaluation profile and the selector policy,
  in place of an identity/version pair* — considered, and an identity/version pair was
  kept instead, for consistency with how every other versioned component in this
  specification is bound (`agent_version`, `jcs_distribution_version`) rather than
  digested; a digest of the policy's own decision logic remains available as a future
  strengthening and is not foreclosed by this ruling, but is not adopted by it either.
* *Granting the provider network, storage, service-discovery or plugin-loading
  capability* — barred outright by the owner's ruling (part 2); the provider is a
  plain injected callable and nothing about its own implementation is this package's
  concern or within its authority.
* *Choosing a substantive ranking criterion for the selector in this amendment* —
  rejected, and still rejected under OD-8: it is a business decision the owner's
  ruling does not make, and inventing one would misrepresent an unratified choice as
  settled. OD-8 instead ratifies fail-closed uniqueness (part 4), under which more
  than one qualifying candidate produces no selection and `ABSTAIN`.

*Public-API consequences.* `[V]` **Applied, in the implementing change set.**
`public_api.json` moved from its 39-name snapshot to 46 and `version.py` from `0.1.0`
to `0.2.0`, adding exactly the seven names this ratification authorized —
`DomainEvaluationOutcome`, `DomainEvaluationProvider`, `DomainEvaluationRequest`,
`DomainEvaluationResponse`, `DomainEvaluationProviderError`, `verify_domain_evaluation`
and `verify_deterministic_selection` — and removing none. The snapshot was not
regenerated ahead of the exported code and its tests, exactly as A12 separates a
ratified decision from production authorization elsewhere in this document.

**Enforcement and mutation-test obligations (I8).** `[V]` **All fifteen are
discharged**, in
`packages/capabilities/agentic-proposer/tests/test_od7_domain_evaluation_boundary.py`
unless another module is named. The wording below is the ruling's own and is unchanged.

* **I8.1** — `CandidateAdvisory.domain_evaluation_outcome`/`domain_check_completion`
  coupling holds in both directions, mutation-tested against a validator that names
  both fields and enforces neither.
* **I8.2** — `AdvisoryCandidateSet`'s two new coupling rules (evaluation-profile fields
  present iff any candidate is `COMPLETE`; selection-policy fields present iff
  `selected_candidate_id` is set) hold in both directions and are scoped to this bearer
  alone, on OD-3's lesson.
* **I8.3** — R-1b's two new correspondence clauses are replayed by `verify_advisory_
  selection` and fail on a mirrored field that diverges from `AdvisoryCandidateSet`'s.
* **I8.4** — `verify_domain_evaluation` returns `False` when the stored
  `domain_evaluation_profile_id`/`version` diverges from an independently supplied
  `expected_profile_id`/`expected_profile_version`, and separately when re-invoking a
  provider stub under the expected profile does not reproduce the stored outcome or
  the stored `candidate_id`; the test states explicitly that this does **not**
  establish the original evaluation's correctness under a non-deterministic or
  since-changed provider (part 5's disclosed ceiling).
* **I8.5** — `verify_deterministic_selection` returns `False` on a `selected_candidate_
  id` not produced by the ratified selector (including a hand-constructed one that
  happens to satisfy R-1b's structural correspondence), and separately on a
  `selection_policy_id`/`version` naming a policy other than this package's own
  ratified selector identity even when the recomputed selection matches.
* **I8.6** — one test per row of part 7's fail-closed table.
* **I8.7** — a same-change-set discipline check: C7 and C9 are removed only in a commit
  that also introduces every field, vocabulary member and replay function this
  amendment specifies; this is a review-time obligation, not something one runtime test
  can enforce alone.
* **I8.8** — `DomainEvaluationOutcome`'s members are asserted disjoint from `RESERVED_
  AUTHORITY_VOCABULARY` and from `SemanticAuditorFindingStatus`'s ratified
  `INDETERMINATE` position.
* **I8.9** — a provider stub that raises during `verify_domain_evaluation`'s own
  replay call is confirmed to produce `False`, not a propagated exception; a provider
  stub that raises during a builder's original call is confirmed to surface as
  `DomainEvaluationProviderError`, not the provider's own exception type; and a
  fixture with an unresolved `observation_refs` entry is confirmed to warn (not raise,
  not silently return `False` from either new replay function) and to route the build
  to `NEED_EVIDENCE` without invoking `provider` at all.
* **I8.10** — Equation 2's new `DomainEvaluationSatisfied` term (part 6) is exercised
  directly against `evaluate_readiness` as an exported function, not only through a
  builder: a candidate carrying `domain_check_completion is COMPLETE`,
  `is_eligible is True`, matching lineage and `domain_evaluation_outcome` of
  `NOT_SATISFIED` and of `INCONCLUSIVE` must each return `False`, and the same
  candidate with `SATISFIED` must return `True`. Mutation-tested against a
  six-term equation that omits the new term, which must fail. The test states that
  this is what replaces C7's structural closure of R-2/V13's `PROPOSAL` path, and a
  companion assertion confirms `terminal_outcome=PROPOSAL` is unreachable for a
  `NOT_SATISFIED` or `INCONCLUSIVE` candidate once C7 is gone **and V13 recomputes
  readiness per R-2** rather than refusing `PROPOSAL` outright as it does today. That
  companion assertion is therefore meaningful only against the reimplemented V13; a
  test written against today's blanket refusal would pass for the wrong reason and
  must not be mistaken for coverage of this obligation.
* **I8.11** — the `CONTRACT_CARDINALITY` pins named in part 5 (`AdvisoryCandidateSet`
  8 -> 12, `CandidateAdvisory` 10 -> 11, `ProposerAdvisory` 23 -> 27) are updated in
  `tests/s1_specification_mirror.py` in the same change set, together with the
  hard-coded twenty-three in `tests/test_identifier_normalization.py` and
  `tests/test_selection_dependent_fields.py`. These are existing guards that will fail
  on the field additions; updating them is part of the change set, not a repair after
  it.
* **I8.12** — **OD-8 selection-policy v1.** The selector selects iff the qualifying
  pool holds **exactly one** candidate; a two-qualifier set produces no selection and
  `ABSTAIN`, and a zero-qualifier set produces no selection. Mutation-tested against a
  selector that falls back to ascending `candidate_id` on a two-qualifier set, which
  must fail. A companion assertion pins that the tie-break is **unexercised** under
  v1: no code path may resolve a multi-qualifier set to a selection.
* **I8.13** — **OD-8 non-repurposing.** No merit ordering is computed from
  `evaluated_at`, `candidate_id`, `disposition`, `requested_review_action`, or the
  lengths of `claim_refs`, `observation_refs`, `assumptions` or `uncertainties`.
  Enforced structurally where possible (the v1 selector reads only `is_eligible` and
  `domain_evaluation_outcome`) and, for the prose, by the documentation-consistency
  guard, which must refuse a claim that any of those fields ranks candidates.
* **I8.14** — **OD-9 / OD-10 per-candidate scope.** A set holding one eligible,
  `SATISFIED` candidate **plus** an `INCONCLUSIVE` candidate **selects the qualifying
  one** — the case that distinguishes the ratified reading from the run-wide one, and
  the one an implementer is most likely to get backwards. Separately: a zero-qualifier
  set with an `INCONCLUSIVE` candidate terminates `ABSTAIN` under OD-9, and a
  zero-qualifier set with none terminates `ABSTAIN` under OD-10.
* **I8.15** — **Fail-closed table totality and disjointness.** I8.6 already requires
  one test per row; this adds the property the rows must hold *together* — over a
  completed run, exactly one row matches, the rows are mutually exclusive, and no
  completed run falls through without a ratified outcome. It is what makes OD-10 do
  its job rather than merely exist.

*Enforcement:* `[V]` **implemented.** **Production and behavioural guards exercise the
OD-7 selection surface** in
`packages/capabilities/agentic-proposer/tests/test_od7_domain_evaluation_boundary.py`,
which discharges every obligation above (`I8.1` – `I8.15`); the cardinality pins I8.11
names were updated in `tests/s1_specification_mirror.py`,
`tests/test_identifier_normalization.py`, `tests/test_selection_dependent_fields.py`
and `tests/test_advisory_contract_shape.py` in the same change set, and the C7/C9
replacements are additionally constructed in `tests/test_unenforced_local_rules.py`'s
`ENFORCED` registry. `[V]` The **documentation-consistency guards** in
`tests/test_documentation_consistency.py` are unchanged in kind: they pin the
OD-8/OD-9/OD-10 meanings and the OD-7 statements those rulings amended — part 5's
replay rule and part 7's fail-closed table — against a silent revert to the pre-ruling
prose, and nothing else in OD-7. Those are still **not production enforcement**: they
check what these documents say, not what any selector does, which is why the
behavioural module stands beside them rather than replacing them. C7 and C9 are removed
and `src/`, `public_api.json` and `version.py` are changed — all in the single change
set part 8 requires, and none of it authorized by this entry alone.

*Where it is implemented in this document:* C7
and C9's own sections (a migration note); D6 (`CandidateAdvisory` and
`AdvisoryCandidateSet`'s new fields); D7 (`ProposerAdvisory`'s mirrored fields); C5
(the classification registry, extending the C5b roster by the four fields part 5
names); Part F (Equation 2's seventh term, `DomainEvaluationSatisfied` — part 6); Part
G — specifically `identity.py`'s private `_UnsignedAdvisoryPayload` mirror, which
G2's equivalence obligation requires to carry the same fields, defaults, validators
and serializers `ProposerAdvisory` does, so the four mirrored fields (part 5) must be
added there too, or the two models drift apart; Part H (the two new replay functions,
the fifth exception class, H3's snapshot); Part J (this item replaces the "domain
evaluator" and "candidate selection" bullets' deferral with a boundary).

**The specification is frozen.** The status line at the head of this document reads
`CONTRACT SPECIFICATION FROZEN FOR IMPLEMENTATION`. Freezing closes the contract
surface to change and discharges A11's review condition; it does **not** discharge the
Part I obligations, which are implementation work rather than specification questions.
The two things that stood between this document and S1 code are therefore now one. The
ADR's introduction states both, and what remains of each:

* **The Part I obligations**, which S1 must discharge in the same change that introduces
  the surface they govern. `[V]` The guards implementing O-1 – O-4 and OD-1 – OD-3 are
  in `packages/capabilities/agentic-proposer/tests/`, including both corrections I4
  previously reported as outstanding; `[R]` they are exercised against temporary
  representative shapes rather than a declared contract module, and I1, I6 and the
  unbuilt parts of I7 remain outstanding.
* **A11 — discharged.** `[V]` The review-and-merge condition is met and the freeze is
  recorded as **A12** in the readiness ADR. An implemented guard never lifted this; an
  independent review and a merge did.

There is no gate on the contract *shape* for want of a ruling: every composition
question is ratified, and the shape is now frozen. `[V]` The gate that stood — writing
production code before the enforcement that would catch a departure from it had been
independently reviewed alongside the specification it enforces — is discharged: the
review happened and the freeze records it. What is left is to arm that enforcement
against a real contract module, which is the Part I obligation above and is work, not
permission.
