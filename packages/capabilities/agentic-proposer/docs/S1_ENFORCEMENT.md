# S1 — enforcement obligations discharged; contracts specified, not implemented

## What landed

The `[R]` obligations the MVP readiness ADR carries for S1 — D6–D8 as first
ratified, and the O-1 – O-4 refinements ratified after those guards were audited —
each enforced by a test rather than by prose:

| Obligation | Decision | Test module |
| --- | --- | --- |
| No auditor status may be assigned or converted into a `TerminalOutcome` or `CandidateDisposition` field | D6 standing rule | `tests/test_no_auditor_status_projection.py` |
| The advisory contract's names, kind, sole identity field, identity substrate, barred fields at any nesting depth, and barred name prefixes | D7, narrowed by O-3 | `tests/test_advisory_contract_shape.py` |
| The role projection is not re-exported from any shared contract package and takes no role lifecycle authority | D8, narrowed by O-2 | `tests/test_role_projection_bounds.py` |
| The three selection-dependent fields are nullable and coupled to `selected_candidate_id` | O-1 | `tests/test_selection_dependent_fields.py` |
| Identifier and reference fields are ASCII; human-readable text is not restricted | O-4 | `tests/test_identifier_normalization.py` |

Each guard is written to hold **before** the surface it governs exists. The parts
that can be checked today — the barred name prefixes, the kind-string bar, the
identity-substrate rule, the shared-contract export bound, the lifecycle-verb bound,
and the source shapes a status projection takes — are checked over the package and
over the repository as they stand. The parts that need a contract are parametrized
over what the package defines, so they arm themselves with the first field, model or
type that appears, which is what D6's "lands with the first such field" requires of a
test written before that field.

Every scanner is self-tested against synthetic sources. A detector that stopped
matching fails there rather than reporting a clean package — the failure mode that
matters most while the surface being guarded is still empty.

A self-test is only as good as the sample it runs on. An audit of the first version
of these guards found that D6's samples were all written with bare, unaliased names,
so the scan matched bare names too and every aliased or module-qualified projection
passed — the detector was sound against its samples and blind to the ordinary
spelling of the violation. Samples now cover each shape written three ways (bare,
aliased, module-qualified), and a scanner without a self-test is treated as a gap in
its own right, not as a scanner that happens to be untested.

## What O-1 – O-4 changed

Four owner decisions were ratified after these guards were audited. Two narrow a
guard that was over-broad, and two add one that was missing. All four are recorded in
the readiness ADR under *Ratified refinements*.

**O-2 — the lifecycle bound is on authority, not on vocabulary.** The D8 scan matched
verb stems, so it rejected `SUSPENDED`, `REVOKED`, `RoleActivationStatus`,
`activation_status` and `expires_at` — the domain's correct words for lifecycle facts
some other authority determined. A stem scan cannot tell an act from a description,
and a rename bought under that pressure removes no authority while costing the
contract its meaning. The guard now reads grammatical form and syntactic position: a
mutation form is barred everywhere, an actor form is barred as a type or a callable
and permitted as a reference to an external party, and any lifecycle-stemmed field
annotated as a callable is barred. The narrowing is mutation-tested — each rule is
weakened in turn and a real violation must escape — because a guard that has just
been narrowed is exactly the one whose remaining rules need showing to be
load-bearing.

**O-3 — one kind, one bearer.** The D7 guard required the ratified kind of both
advisory types. `CandidateAdvisory` is a subordinate per-candidate record; a kind is
what a consumer routes and stores on, so a candidate record declaring the advisory
kind would be consumable as an advisory in its own right. The kind is now required on
`ProposerAdvisory` and barred on `CandidateAdvisory`, along with any other kind in
this capability's namespace.

**O-1 — the selection-dependent fields.** `recommended_disposition`,
`requested_review_action` and `requested_review_destination_role_ref` are nullable and
all three are `None` when `selected_candidate_id` is. The guard arms with the first
class declaring any of them and then requires the selector on the same class, a
`None`-admitting annotation on each dependent, and a coupling enforced by code rather
than by a docstring. O-1's second clause — that a dependent field agrees with the
selected candidate and its permitted routing — is a statement about values a stage
with candidates produces; nothing here has candidates, so the guard records that
boundary instead of covering it.

**O-4 — ASCII identifiers, and only identifiers.** Identity is computed through
`ugence_jcs` with an empty `nfc_paths` profile, so nothing is Unicode-normalized before
canonicalization and two normalization forms of one identifier are two identities. The
guard demonstrates that against the substrate rather than asserting it, requires the
ratified pattern on identifier and reference fields, and bars it from claims, reasons,
summaries and other human-readable text, where an ASCII restriction would reject the
languages those are written in. It also fails if a non-empty normalization profile is
ever passed, since that is the premise the whole rule rests on. How the pattern is
applied is pinned with it: `re.match` admits a trailing newline against `$`, and
`re.fullmatch` does not.

## What the D6 scan covers, and what it does not

The claim "D6 binds" is only meaningful against a stated list, so here it is. The
source scan detects a status→outcome projection written as: a conversion call; a
lookup table, whether a literal or a comprehension; a union annotation; a
status-valued assignment to a reserved field; a status-in/outcome-out function; and
member access or subscription of a reserved type inside a scope that reads an
auditor status. Each is resolved through import aliases, module-qualified
references, in-package re-export chains closed to a fixpoint, string forward
references (including under `from __future__ import annotations`), `TYPE_CHECKING`
imports, and `getattr` with a literal or concatenated name.

### Known uncovered spellings

These are gaps, not boundaries. Each is statically visible and could be closed; none
is closed today. They are listed so the enforcement is not read as complete:

| Spelling | Example |
| --- | --- |
| alias rebound by assignment | `T = TerminalOutcome` then `T.ABSTAIN` |
| class-attribute alias | `class V: Result = TerminalOutcome` then `V.Result.ABSTAIN` |
| `functools.partial` over the constructor | `_build = partial(TerminalOutcome)` |
| `globals()` / `vars()` with a literal name | `globals()["TerminalOutcome"].ABSTAIN` |
| a projection split across two modules, neither naming both vocabularies | module A maps status→key, module B maps key→outcome |

`globals()` with a literal name is statically visible in exactly the way the covered
`getattr` case is; it is uncovered because no one has written the branch, not
because analysis cannot reach it. The split-across-modules case is different in
kind: each half is lawful in isolation and only their composition projects, so
catching it means reasoning about values across module boundaries. It is listed here
rather than as a boundary because it is a real hole either way — a reader should not
have to infer it from what the scan does not say.

### Named boundaries — deliberate, not oversights

* **Dynamic construction is out of scope.** A name built at runtime from data the
  scan cannot see — `getattr(module, name_from_config)`, an import driven by
  configuration — is not detected, and cannot be by static analysis. This covers
  only genuinely runtime-determined names: a literal name reached through
  `globals()` is a gap above, not a boundary here.
* **The runtime half detects widened annotations, not projections.** It asserts that
  a field in a reserved position refuses every auditor status. Code that converts a
  status to a lawful outcome *before* assignment passes it, correctly — the field is
  sound; the conversion is the violation, and only the source scan sees it. The two
  halves are complementary, not redundant, so a source-scan gap has no second line
  of defence.
* **The scan reaches this package and the shared contract packages only.** A
  projection performed in a package neither of those covers is outside its reach.
* **The substrate floor is asserted as `pyproject.toml` text**, not as a resolved
  installed distribution. `ugence_jcs` reaches the tests through `conftest.py`'s
  `sys.path`, so nothing here proves an installed `ugence-jcs >= 0.2.0`. This is a
  boundary only as far as *installed distributions* go: the imported
  `ugence_jcs.__version__` is readable through the same path the tests already use
  and is `0.2.0` today, so a resolved-version assertion is strictly stronger than
  the text check and is not out of reach. It is not written because which of the two
  the floor should mean — a declared floor or a resolved one — is an owner
  decision, not a detail.

## The substrate is a distribution, not a name

One interaction is worth recording because it is not obvious from either rule alone.
D7 requires identity to be produced by `ugence_jcs.canonical_sha256_hex`; D2's text
guard bars the substring `sha256` anywhere in this package. Read literally, no source
can satisfy both. The text guard therefore masks the permitted substrate call
spellings before scanning: the exemption is those exact spellings and nothing wider,
so a local `hashlib.sha256` in the same position is still caught — by the text scan,
the import scan, and D7's own substrate rule.

That mask keys on a name, which makes the name itself load-bearing. A module inside
this package called `ugence_jcs`, reached by `from . import ugence_jcs`, would
satisfy every by-name check while hashing locally. Three rules close that together:
a relative import can never bind the permitted substrate (the substrate is reached
absolutely or not at all); no file or directory here may be named for it; and dynamic
imports are constrained everywhere. A call to `import_module` or `__import__` may
not name a barred module, and may not be handed a name this module composed —
whether the composition is written at the call site (`"hash" + "lib"`, an f-string,
a `join`, `bytes(...).decode()`) or bound to a variable first (`_n = "hash";
_n += "lib"; __import__(_n)`). The line is composition, not indirection: a name the
module merely received — a parameter, an attribute such as `info.name` — stays
permitted, which is how the guards walk this package's own modules. `importlib`
itself is additionally barred as an import in `src`.

The tracking is per binding and per scope: a binding in one scope is never a fact
about another, so a module-level `name = "age" + "ntic"` says nothing about the
parameter of `def load(name)` or about `import_module(name) for name in infos` — the
shape the guards themselves use. A name rebound from a non-assembled source stops
being composed, and an augmented assignment marks a name only when what it appends
is text.

It is per binding, not per value: a name assembled through a route the scan does not
model as composition — a helper function returning a built string, a name read from
a file, an environment variable, a dict or list element — is not caught. That is the
dynamic-construction boundary below, reached by a different road.

### Ratified — D2 is the invariant, and the scan is a release guard

**This is settled. It is no longer an owner decision.**

**D2 is a behavioural and architectural invariant.** An advisory identity is valid
only when an independent verifier recomputes it from the frozen unsigned advisory
projection using the ratified `ugence-jcs` canonicalization profile and obtains the
exact stored digest. Identity that no independent recomputation reproduces is not
identity, whatever produced it and whatever passed.

**Static scanning remains a mandatory release guard** for declared imports, ordinary
aliases, known dynamic-import forms and accidental local canonicalization. It is
defence-in-depth. It does not constitute proof against every intentionally obfuscated
Python construction, and it is not the definition of the rule.

The distinction matters in both directions. A green scan is not proof of identity
correctness — only recomputation is. And a construction that defeats the scan does not
thereby acquire authority: it produces a digest no independent verifier is obliged to
accept.

#### The disclosed exploit, and what it is

An audit demonstrated a working, byte-correct local SHA-256 identity function living
in `src/` with every guard green, by assembling the module and attribute names through
a helper function:

```python
def _b(*p): return ''.join(p)
_m = __import__(_b('hash', 'lib'))
```

The route is per value rather than per binding: the composition happens inside a callee
and returns as an ordinary string, so the per-binding tracking described above never
sees it. It is disclosed rather than closed.

This is **an enforcement limitation of static analysis, not an unresolved owner
decision, and not an authorization.** Code reaching identity by this route violates D2
exactly as a bare `hashlib.sha256` would; it violates it invisibly to the scan, which
is why the invariant and not the scan is the rule.

Closing it would mean tracking assembly through call returns, subscripts and external
inputs — materially more analysis, and a scan that keeps growing as new routes are
found. That work is optional hardening. It is not what makes D2 hold.

#### What S1 must additionally provide

Because the scan is a guard and not a proof, S1 must carry the invariant itself:

* **package-owned construction** — a single authoritative builder that produces the
  unsigned projection, computes its digest through the substrate in one expression, and
  returns a frozen advisory, with no in-place mutation path and no null-digest draft;
* **independent canonical replay** — a verifier that recomputes the digest from stored
  advisory content alone and compares it with the stored value, sharing no state with
  the builder;
* **frozen-profile tests** — a fixed corpus pinned to exact canonical bytes and exact
  digests under the ratified empty-`set_paths`, empty-`nfc_paths` profile, so a
  substrate or serialization drift fails loudly rather than silently reminting
  identities;
* **installed-distribution verification** — `ugence-jcs` resolved as an installed
  distribution exposing `canonical_sha256_hex`, superseding the `pyproject.toml` text
  check recorded above as the weaker of the two available assertions.

The contracts, the projection, the equations and these obligations are specified in
`S1_CONTRACT_AND_EQUATION_SPECIFICATION.md`.

`tests/test_no_local_canonicalization.py` pins the three modules by name and asserts
that every file in `src` and `tests` is either scanned or one of the two named
exemptions, so a module cannot leave the scan silently.

## Guard corrections, and what they enforce

Auditing the O-1 – O-4 guards against representative contract shapes — declaring the
contracts and watching what armed — found three things prose review had not. All three
were ratified as owner decisions on 2026-08-25. **The single decision record is the
OD-1 – OD-4 table in
[`docs/architecture/ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md`](../../../../docs/architecture/ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md);
this section does not restate it and is subordinate to it.** What follows is what the
guards do.

Three statuses are kept apart throughout, and a reader must not collapse them: a
**decision is ratified**; a **named guard implements** it; and **production
implementation remains separately gated** (ADR addendum A11). A guard that enforces a
ratified decision authorizes no production contract.

**OD-3 — the selection coupling was class-blind.** It matched the three dependent field
names anywhere, so `CandidateAdvisory.requested_review_action` — the candidate's **own**
required, non-null routing — was treated as selection-dependent, and the guard demanded
a selector on the candidate record and demanded that field admit `None`. Both contradict
the ratified contract. The coupling is now pinned to one bearer, `ProposerAdvisory`, by
an exact registry mirrored from B6; a class that merely shares a field name is not
reached.

**Enforcement is behavioural first.** `tests/test_selection_dependent_fields.py`
constructs the bearer from a **complete valid fixture supplying all twenty-three
required fields** and observes what validation does: a null selector with any non-null
dependent is rejected; a non-null selector with any null dependent is rejected; a null
selector with all three dependents null passes; a non-null selector with all three
non-null passes **locally**; `CandidateAdvisory.requested_review_action` stays required
and non-null; and the same field name on another class does not trigger the
bearer-scoped rule. Static AST inspection is retained as a **supplemental** layer and is
**not** evidence of behaviour — a mutant validator naming all four fields and enforcing
nothing passes the AST layer, and `test_the_suite_kills_a_no_op_validator_mutant`
demonstrates both halves: that the mutant survives the static reading, and that the
behavioural probes kill it.

The local rule remains local. A model validator holds `candidate_set_id`, not the set,
so it establishes nothing about the referenced candidate set; correspondence is R-1b,
discharged by the builder and re-established by independent replay.

**OD-1 — suffix inference classified six fields as nothing.** `agent_version`,
`tool_name`, `allowed_source_scopes`, `excluded_data_classes`, `permitted_tool_scopes`
and `tool_invocations` end in no identifier suffix and carry no free-text marker, so they
were neither required to carry a pattern nor barred from one — they were checked by
nothing. `tool_name` is the sharpest case, since it is matched by equality against
`permitted_tool_scopes`.

Classification now comes from `FIELD_CLASSIFICATION`, which is an **exact enforcement
mirror** of the specification's C5 tables and nothing else. It **originates no contract
field**: it adds none, renames none and reinterprets none, and where it and the
specification disagree the specification is right. It is carried in
`tests/s1_specification_mirror.py`, cites the specification section each block comes
from, and `test_the_registry_cites_its_source` fails if a cited section is renamed there.

What the registry pins, each by equality:

* the **exact class set** — C5a, C5b, C5c, C5d, and the mechanical classes a content
  category does not describe (`other-pattern`, `closed`, `non-string`, `structured`, and
  the C5a-keys/C5c-values mapping);
* the **exact field set for every contract**, checked against Part D's stated
  cardinality, so a field added, omitted or renamed fails;
* the **exact C5 category for every classified field**, with **every** C5a and C5b entry
  mutation-pinned — not a chosen sample: reclassifying any one of them to
  `non-string`, `other-pattern`, C5c, C5d, `closed`, `structured` or an unregistered
  category fails;
* a **citation** to the canonical specification for each mirrored block.

Four things the registry now carries that inference could not: the fourth, mechanical
class **C5d** for the five reserved lists that admit no value; the non-`str` fields
`AgentIdentityRef.lifecycle_state` and `ProposerAdvisory.candidates`, without which the
completeness check would be circular; the C5a-keys/C5c-values shape of
`ToolObservation.normalized_fields`; and the twenty-three-field cardinality OD-4(a)
produced.

**C5c bars the mechanism, not two literals.** A free-text field carries **no pattern or
regex constraint of any kind** — not the C5a pattern, not the C5b pattern, not a
narrowed variant, not an anchored character class, not a "lenient" junk filter, and not
a custom validator whose effect is a regular-expression test. Arbitrary ASCII-only
grammars are rejected as such, and lawful Unicode free text is proved **accepted** by
live model probes rather than asserted: a purpose written in German, Japanese, Russian
or Arabic constructs, and would not under either pattern.

**A pattern is not accepted for being present.** Syntactic discovery is restricted to
constraints that actually **bind** the field value — a `pattern=` argument to `Field`,
`StringConstraints` or `constr`, outside decorative metadata. A pattern written into
`json_schema_extra`, a `description` or an `examples` entry validates nothing and is
read as validating nothing; accepting one would report a constrained field that nothing
constrains. Live model probes carry the weight: C5a rejects every invalid identifier
value, C5b rejects every invalid token value **including slash, spaces, newline and
homoglyphs**, sequence-valued C5a and C5b fields are validated **element by element**,
and C5c accepts lawful Unicode.

**OD-2 — the boundary probe would have failed on the first contract.** Bare
`import pydantic` does not load `socket`; *defining any* `BaseModel` does. Every contract
is a `BaseModel` and `pydantic>=2` is ratified, so the whole-process `sys.modules`
assertion was going to fail for a reason unrelated to this package's authority. The
invariant is about possessing or exercising networking authority, not about module
residency, and enforcement is layered:

1. a static scan of production source;
2. that scan extended to aliases, `from` imports, module-qualified use and the
   dynamic-import spellings — a literal passed to `importlib.import_module` or
   `__import__`; a literal **bound to a local name** and then passed to either;
   `exec("import socket")`; `eval("__import__('socket')")`; an import inside
   `compile(...)`; source text bound to a name and then executed; and the prohibited
   relative-import spellings, since a relative import can never bind the permitted
   identity substrate. **Each spelling carries a negative control** proving the detector
   reports the reach and not the mechanism, so an ordinary `import_module` of a
   permitted module stays lawful;
3. a fresh-interpreter probe that establishes the ratified dependency baseline first and
   then asserts this package introduces no **additional** forbidden root;
4. the declared-dependency allowlist, from which `DEPENDENCY_BASELINE_MODULES` is
   **derived** rather than hand-written, with the generated baseline setup **pinned by
   equality** so it cannot be silently widened — a baseline carrying an added
   `import socket` fails `test_a_widened_baseline_setup_fails`;
5. negative controls proving a direct `socket` import still fails.

Three things are preserved exactly: pydantic's transitive schema-construction behaviour
stays **permitted**; any **direct** Agentic Proposer import or use of a networking module
stays **prohibited**; and the declared dependency allowlist is unchanged — `pydantic>=2`
and `ugence-jcs>=0.2.0`, **two** dependencies, asserted by equality and by count.

### The enforcement ceiling, stated honestly

The static layers catch every declared import, alias, `from` import, module-qualified
use, and each dynamic spelling enumerated above. They do **not** catch **arbitrary
runtime composition**: a module name assembled by a helper and returned as an ordinary
string, **externally supplied**, read from a file, an environment variable or a data
structure, or reached by **reflection**. Those routes and equivalent undecidable
behaviour are **not proven absent** by static scanning — a green suite is not evidence
they do not exist — and they remain subject to **review, packaging and runtime
isolation**. `test_a_name_assembled_through_a_call_return_is_the_disclosed_ceiling`
demonstrates the hole rather than conceding it in prose.

The differential layer catches an indirect load whatever spelled it, but only along the
import path the probe executes, and once `socket` is in the baseline it structurally
cannot see a direct import. Neither layer is sufficient alone and the pair is not a
proof. The invariant stays architectural and review-enforced.

## What the contracts are, and what has not been built

The eight canonical contracts and Equations 1–4 are **specified and unimplemented**.
`S1_CONTRACT_AND_EQUATION_SPECIFICATION.md` is the authoritative record and states them
literally: every contract, every field with its type, requiredness, nullability, default,
cardinality, vocabulary, classification, ownership and identity participation; the frozen
`P_unsigned` projection; and every equation signature. That document is the canonical
authority, and **the enforcement registries in `tests/` are exact mirrors of it — a test
originates no contract field.**

Specification is not authorization. No contract module exists in `src/`, the version is
unchanged, and **production implementation remains separately gated**: the Part I
obligations are undischarged, and A11 keeps implementation unauthorized until this
documentation is independently reviewed.

The ratified shape the guards now pin, in the terms Part D states it:

* **eight top-level contracts** — `AgentIdentityRef`, `CognitiveRoleContract`,
  `WorkMandate`, `BoundedContextEnvelope`, `ToolObservation`, `AdvisoryCandidateSet`,
  `ProposerAdvisory`, `ProposerProcessRecord` — plus **two subordinate nested public
  shapes**, `CandidateAdvisory` and `ProposerProcessStateTransition`, which carry no C2
  common field and are never transported alone;
* **`ProposerAdvisory` carries twenty-three fields**, including a nested
  `candidates: tuple[CandidateAdvisory, ...]` (OD-4(a)) and a **retained**
  `candidate_set_id` referencing the top-level `AdvisoryCandidateSet`, which is not
  demoted. Both candidate sequences are the same container type, ordered ascending by
  `candidate_id`, with the builder rejecting out-of-order input rather than reordering
  it;
* **`selected_candidate_id`** is the selector, held apart from its three dependents;
* **R-1a** is the local model validator — jointly present or jointly absent — and
  **R-1b** is the cross-contract correspondence between the advisory's nested candidates
  and the referenced set, in membership, order and candidate content, discharged by the
  builder and re-established by independent replay;
* **E2** specifies R-7's **observation-resolution replay**: `verify_observation_resolution`
  takes the complete observation collection, indexes it detecting ambiguity, resolves
  every required reference to exactly one observation, checks tenant, case and source
  continuity on each, and reports an unreferenced extra rather than absorbing it;
* **C5a / C5b / C5c** classify identifier, canonical-token and free-text fields, with
  the mechanical **C5d** for the reserved lists;
* **V13** makes `terminal_outcome = PROPOSAL` conditional on a selection and on
  readiness, and C7 makes readiness unconstructible in S1, so the fail-closed ceiling is
  `NEED_EVIDENCE`, `ABSTAIN`, `ESCALATE`;
* **`P_unsigned`** covers `ProposerAdvisory` and everything reachable from it — under
  OD-4(a), every field of every nested candidate — and nothing else;
* **OD-1 through OD-4** are ratified, recorded once in the readiness ADR;
* and every constrained `str` field is declared
  **`Annotated[str, StringConstraints(...)]`**, never `field: str = Field(pattern=...)`.
  The two are equivalent to pydantic and are **not** equivalent to the identity-source
  guard, which collects every value expression assigned to `advisory_digest`: under
  `Annotated` nothing is collected, and under `Field(...)` the assignment's value is a
  call that does not resolve to the substrate, so the contract module would be reported
  as declaring its own identity field from an unpermitted source. The rule is stated for
  every constrained `str` field, not only that one.

### What the guards do not yet establish

Each guard is written to hold **before** the surface it governs exists, and is exercised
today against **temporary representative shapes** derived from the specification rather
than against a declared contract module. That dormancy is the design, and it is stated
here so a green suite is not read as a verified contract:

| Obligation | State |
| --- | --- |
| The registry's completeness check against `src/` | dormant — it binds on the first declared contract module |
| E2's replay verifier, the frozen-profile corpus, the equivalence corpus, and the R-7 behavioural suite | **not built** — they need builders and verifiers this stage does not authorize (I7.1, I7.14) |
| `sha256:` prefix literal vs. `SUSPECT_TEXT` | **outstanding** — a module-path-scoped text mask in the one authorised identity module, with mutation tests. No definition-name exemption is needed: the ratified identity functions are named `compute_advisory_identity` and `verify_advisory_identity`, which carry no suspect substring |
| `tests/test_vocabulary.py` pins the S0 export surface by equality | **outstanding** — it must be updated to the full H3 surface in the same change that exports the first contract, and not before |
| Installed-distribution verification of `ugence-jcs` | **outstanding** — the `pyproject.toml` text check is the weaker of the two available assertions (I7.10) |

## Documentation gates, and exactly what they cover

`scripts/check_doc_links.py` validates relative-link resolution over a **curated list**,
and this package's documents — the README, `S1_ENFORCEMENT.md`,
`S1_CONTRACT_AND_EQUATION_SPECIFICATION.md`, `S0_SCOPE.md` and the readiness ADR — are
named in it, so its coverage of them is real rather than assumed.
`tests/test_documentation_consistency.py` asserts that the curated list still names them,
and enforces the same link rule package-locally so a document added here is covered
without waiting for the repository list to be edited.

`scripts/validate_terminology.py` runs over a **different** curated list, and these
documents are deliberately **not** in it. Its rules are specific to the Decision
Governance terminology ADR and do not apply to an advisory capability's contract
specification. **No terminology-gate coverage is claimed for these documents**, and
`test_no_terminology_coverage_is_claimed_for_these_documents` fails if such a claim is
introduced. A gate whose curated input does not name a document does not cover it,
whatever the gate's title suggests.

The package-local guard additionally checks what a multi-document decision record can get
wrong: that OD-1 – OD-4 have **one decision record**, the table in the readiness ADR, and
that no document outside the ADR carries a rival ratification heading; that the ADR and
the specification **agree** on every decision, since the specification states each in
full and two full statements are only safe while they say the same thing; that no *Open
owner decisions* section is restored; that no document both carries a section and says
that section does not exist; and that no status claim rests on a branch state or a commit
identifier whose truth was temporary.

`[I]` The specification's own *Owner decisions* section is not a duplication to be
removed. The ADR carries the **record** — ratified, on what date, whether it bears on
contract shape, which guard enforces it — and the specification carries each decision in
full because it is the implementation-ready document: OD-4 changed contract shape, and
OD-1 and OD-2 carry riders an implementer must read where the contracts are stated.
What is barred is a **second place a decision is made**, not a second place it is
explained. The agreement check is what keeps that distinction from decaying: it compares
the ratification dates and OD-4's resolution letter across both documents, and pins that
OD-4 is the only decision either records as bearing on contract shape.

## Version

`0.0.1`, unchanged. No public contract is frozen at it and no public-API snapshot is
created: no S1 contract module exists in `src/`, and the S0 surface (the D4 vocabulary)
is already pinned by equality in `tests/test_vocabulary.py`.
