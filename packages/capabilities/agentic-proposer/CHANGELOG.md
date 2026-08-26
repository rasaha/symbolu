# Changelog — ugence-agentic-proposer

## 0.0.1 — unreleased (S0 skeleton; S1 enforcement guards)

A version is declared only because the MVP readiness artifact
(`docs/architecture/ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md`) exists and
records owner decisions D1–D5. No public contract is frozen at this version and no
public-API snapshot is created or asserted.

### Added

* Package skeleton following the `agent-workforce-composer` convention: setuptools
  build with a dynamic version from `version.py`, `py.typed`, `conftest.py` for bare
  source checkouts, and an isolated-wheel distribution verifier.
* The ratified D4 vocabulary and nothing else: `TerminalOutcome`,
  `CandidateDisposition`, `SemanticAuditorFindingStatus`, and the
  `RESERVED_AUTHORITY_VOCABULARY` prohibition set.
* `tests/test_boundaries.py` — static import scan of every source file plus an
  isolated-subprocess probe of what the public API actually loads, against the
  forbidden legacy frameworks, authority-owning capabilities, envelope/identity
  reference stacks, control planes, and network/model SDKs.
* `tests/test_vocabulary.py` — equality assertions on each ratified enum, the
  reserved-term prohibition, the INDETERMINATE positional split, the
  ABSTAIN-is-not-a-denial guarantee, and a scan rejecting any ALLOW/DENY/DEFER triad
  or confidence-to-outcome gate.
* `tests/test_no_local_canonicalization.py` — proves the package defines no local
  JSON-canonicalization or digest function anywhere, imports no hashing module, and
  declares `ugence-jcs` as the only identity substrate.

### Added — S1 enforcement obligations (D6, D7, D8)

The three `[R]` obligations the readiness ADR carries for S1, each enforced by a test
that holds before the surface it governs exists and arms itself when that surface
lands. See `docs/S1_ENFORCEMENT.md`.

* `tests/test_no_auditor_status_projection.py` — D6's standing rule. Rejects the six
  source shapes a status-into-outcome projection takes, each resolved through import
  aliases and module-qualified references, and is parametrized over every field the
  package defines in a reserved position — union arms included — so it binds with the
  first such field and judges the field's own annotation rather than the bare enum.
* `tests/test_advisory_contract_shape.py` — D7. Bars the `Proposal*` and
  `Recommendation*` name prefixes, bars any unratified `ugence.agentic_proposer.*`
  kind string, requires identity to be computed only by a call into `ugence_jcs`, and
  rejects the eight barred fields at any nesting depth, statically and (when the
  types exist) over the live models.
* `tests/test_role_projection_bounds.py` — D8. Discovers every shared contract
  distribution in the repository and asserts none carries, snapshots or depends on
  the role projection; asserts the projection exists in no other package; and rejects
  every role lifecycle verb across this package's defined and imported surface.
* `tests/test_no_local_canonicalization.py` — extended to pin the three modules above
  by name and to assert that every file in `src` and `tests` is either scanned or one
  of the two named exemptions.

### Fixed — S1 enforcement defects found by audit

Three defects in the guards above, none of which changed `src/` or the version.

* **D6 did not bind.** All six shapes matched bare `ast.Name` ids, so a projection
  written through an import alias (`TerminalOutcome as T`) or a module-qualified
  reference (`vocabulary.TerminalOutcome`) was not detected — the ordinary way the
  violation would be written. Every shape now resolves both. A sixth shape covers
  member access (`TerminalOutcome.ABSTAIN`, `T[name]`) inside a scope that reads an
  auditor status: an if/elif ladder or a guarded return never calls the enum, so the
  conversion-call shape alone let it through. The runtime half now collects fields
  whose annotation admits a reserved type as a union arm, and asserts against the
  field's declared annotation instead of re-testing the enum.
* **D7's blessed identity call could not be written.** `SUSPECT_TEXT` bars the
  substring `sha256`, which `ugence_jcs.canonical_sha256_hex` contains, so the call
  D7 mandates failed the D2 text guard: the two rules were jointly unsatisfiable.
  The permitted substrate call spellings are now masked before the scan, and both
  the permitted call and a local `hashlib.sha256` in the same position are
  self-tested samples.
* **The `ugence-jcs` floor was stale and pinned.** `>=0.1.0` does not guarantee
  `canonical_sha256_hex`, which landed in 0.2.0; the floor is now `>=0.2.0`, and the
  assertions that pinned the old string were updated with it.

Scanners that had no self-test now have one — the `Proposal*`/`Recommendation*`
prefix bars, the rival-kind-string prefix, the runtime field walk, and D8's three
export scans. Shared-contract discovery is asserted against an independent read of
the same files and a floor on the count, rather than non-emptiness. The snapshot
check now skips explicitly, naming the distribution, where a package publishes no
`public_api.json`, instead of passing with zero assertions executed.

### Fixed — second audit round

An audit of the previous revision confirmed the seven enumerated D6 spellings bind,
and found five further ordinary spellings that did not, two scanners with no
self-test, and two ways to hash locally while satisfying every by-name check. No
`src/` change, no version bump, no public-API snapshot.

* **Five more D6 spellings now bind**: an in-package re-export chain (alias
  resolution closed to a fixpoint across the package, so a two-hop relay resolves),
  a dict comprehension building the same lookup table as a literal, `getattr` —
  including a name assembled from concatenated literals — string forward references,
  and `TYPE_CHECKING` imports paired with them. Each is a self-tested sample.
* **The D6 runtime half is self-tested at last.** Nothing exercised it: the
  parametrization is empty in S0, so both the union-arm rule and the collection
  itself could be deleted with the suite green — the union-arm rule being the fix
  the previous revision was named for. It is now exercised against a synthetic
  namespace covering a pydantic model, a dataclass, a string-union dataclass and a
  plain annotated class.
* **String-annotated fields are collected.** A dataclass under
  `from __future__ import annotations` keeps its annotation as a string, so exact
  equality against the bare type names skipped exactly the fields most likely to
  carry a widened position.
* **The substrate is a distribution, not a name.** A module inside this package
  called `ugence_jcs` satisfied D7's substrate rule and the D2 text mask by spelling
  alone while hashing locally. A relative import can no longer bind the permitted
  substrate, and no file or directory here may be named for it.
* **`importlib` is barred in `src`.** `importlib.import_module("hash" + "lib")`
  reached a barred module without naming it, defeating every text scan. Barred in
  `src` only: the guards themselves import it to walk this package's modules.

`docs/S1_ENFORCEMENT.md` now states what the D6 scan covers as a list, and names
four boundaries it does not cross — dynamic construction, the runtime half detecting
widened annotations rather than projections, the packages in reach, and the
substrate floor being a text assertion rather than a resolved installed version.

### Fixed — third audit round

An audit of the previous revision confirmed the earlier findings closed, then found
that the fix had cost more than it bought in one place. No `src/` change, no version
bump, no public-API snapshot.

* **The alias map is now per module.** Merging every module's aliases into one dict
  made another module's import rename a global fact, and rejected ordinary code:
  a module importing an unrelated `Result` from a sibling, a parameter named
  `Result`, a local variable `Result = {...}`. All three are self-tested as lawful;
  the two-hop relay still binds.
* **`Literal["TerminalOutcome"]` is a value, not a forward reference.** A function
  declaring which vocabulary it names was flagged. String constants inside a
  `Literal[...]` subscript are skipped; quotes elsewhere still resolve.
* **The shadow-module detector is self-tested.** Both branches — a `ugence_jcs.py`
  and a `ugence_jcs/` package — could be deleted with the suite green. It is the
  detector this package's substrate rule leans on hardest.
* **Dynamic imports are constrained everywhere.** `__import__("hash" + "lib")`
  reached `hashlib` from `src` without importing `importlib`, which is the route
  barring `importlib` was meant to close; and a canonicalizer in `tests/` using
  `importlib.import_module("hash" + "lib")` passed, contradicting that module's own
  docstring. A dynamic import may now neither name a barred module nor be handed a
  name assembled at the call site; a plain variable is still permitted, since the
  guards walk this package's modules that way.
* **The per-file wiring is self-tested**, not only the scanners. A scanner that is
  self-tested but never applied does nothing, and dropping either scan — or the
  `src`-only bar — from the per-file check left the suite green.

`docs/S1_ENFORCEMENT.md` now separates **known uncovered spellings** (alias by
assignment, class-attribute alias, `functools.partial`, `globals()` with a literal
name — all statically visible, none closed) from the four **named boundaries**, and
no longer lets `globals()` shelter under "dynamic construction". It also records
that the substrate floor could assert the resolved `ugence_jcs.__version__` rather
than `pyproject.toml` text, and that which the floor should mean is an owner
decision.

### Fixed — fourth audit round

An audit of the previous revision found that the per-module alias fix had silently
reopened ground closed one commit earlier, and that the dynamic-import rule read as
coverage it did not have. No `src/` change, no version bump, no public-API snapshot.

* **Three import spellings the per-module map had lost now bind again**:
  `from .relay import *`, an aliased re-export reached by `from . import Name`
  through the package `__init__`, and an absolute in-package import
  `from ugence_agentic_proposer.relay import Name`. Each was caught before the
  per-module change and passed after it. The three name-reuse shapes stay lawful.
* **A dynamic import may not be handed a name this module composed**, wherever the
  composition happens. `_NAME = "hash" + "lib"` followed by `__import__(_NAME)`
  reached `hashlib` from `src` with the suite green, which composes into a working
  local identity function — the invariant D2 exists to hold. Augmented assignment,
  `bytes(...).decode()`, `%`-formatting and annotated assignment are covered with
  it. The line is composition, not indirection: a name the module merely received —
  a parameter, `info.name` — stays permitted.
* **The fixpoint self-test was vacuous.** Its chain was in favourable sorted order,
  so a single pass resolved it and the loop could be reduced to `range(1)` with the
  suite green. A reverse-ordered chain now fails under that mutation.

`docs/S1_ENFORCEMENT.md` no longer says a dynamic import may not be handed a name
"assembled at the call site", which was literally true and read as coverage; it
states what is tracked and what is not. Two entries join the known-uncovered list: a
projection split across two modules where neither alone names both vocabularies, and
a name composed through a route the scan does not model as composition.

### Fixed — fifth audit round

The audit of the previous revision recommended merge and named one defect worth
closing first: the assembled-name set was built by walking the whole module, so one
scope's binding was a fact about every other. No `src/` change, no version bump, no
public-API snapshot.

* **Assembled names are tracked per scope.** A module-level `name = "age" + "ntic"`
  marked the parameter of `def load(name)` as composed, and with it
  `import_module(name) for name in infos` — the shape the guards themselves use to
  walk this package. Parameters, loop and comprehension variables, `with`/`except`
  bindings and imports now shadow an outer binding; a name rebound from a
  non-assembled source stops being composed; and an augmented assignment marks a
  name only when what it appends is text, so `n = 0; n += 1` no longer does.
* This is the third appearance of one defect: a merged package-wide alias map, then
  a merged module-wide alias map, now a merged module-wide assembled-name set. The
  rule it yields is worth stating once — **a binding in one scope is never a fact
  about another** — and is recorded in `docs/S1_ENFORCEMENT.md`.

`docs/S1_ENFORCEMENT.md` records an `[R]` owner decision: whether D2 means the
invariant (no working local digest reachable from `src`) or the scan (no modelled
composition route). An audit demonstrated a byte-correct local SHA-256 in `src` with
every guard green by assembling names through a helper function. The route is
disclosed as uncovered; which reading of D2 applies decides whether closing it is
work or waste.

### Changed — owner decisions O-1 – O-4

Four decisions ratified after the S1 enforcement guards were audited. Two narrow a
guard that was over-broad, two add one that was missing. No `src/` change, no version
bump, no public-API snapshot; all four are recorded in
`docs/architecture/ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md` under *Ratified
refinements*.

* **O-2 — the D8 lifecycle bound now prohibits authority, not vocabulary.** The scan
  matched verb stems, so it rejected `SUSPENDED`, `REVOKED`, `RoleActivationStatus`,
  `activation_status` and `expires_at`: the domain's correct words for lifecycle facts
  another authority determined. Names are now classified by grammatical form and
  syntactic position — a mutation form (`activate`, `suspending_role`) is barred in
  every position; an actor form (`RoleActivator`) is barred as a type or a callable and
  permitted as a reference to an external party; any lifecycle-stemmed field annotated
  as a callable is barred. The six verbs D8 names explicitly are still barred in every
  position, and the five retained names are pinned by equality.
* **O-2 — the narrowing is mutation-tested.** Each rule is weakened in turn and a real
  violation must escape the weakened guard, so no rule survives without a sample that
  would catch its removal; a mutant that gained a false positive against the retained
  vocabulary fails too.
* **O-3 — the ratified kind is narrowed to `ProposerAdvisory`.** The D7 guard required
  the kind of both advisory types. `CandidateAdvisory` is a subordinate per-candidate
  record, and a kind is what a consumer routes and stores on, so a candidate record
  declaring the advisory kind would be consumable as an advisory in its own right. It
  is now barred from the ratified kind and from any other kind in this namespace, and
  the kind reader is self-tested against all three spellings a type can declare one
  through.

### Added — O-1 and O-4 enforcement

* `tests/test_selection_dependent_fields.py` — O-1. `recommended_disposition`,
  `requested_review_action` and `requested_review_destination_role_ref` are nullable,
  and all three are `None` when `selected_candidate_id` is. Dormant until a class
  declares one of them, then requiring the selector on that class, a `None`-admitting
  annotation on each dependent, and a coupling enforced by code rather than by a
  docstring. The rule is stated executably on a reference model, so the required
  behaviour runs today. O-1's value-agreement clause binds the stage that introduces
  candidates and is recorded as a boundary, not covered.
* `tests/test_identifier_normalization.py` — O-4. Identifier and reference fields are
  validated against `^[A-Za-z0-9][A-Za-z0-9._:/-]*$`; claims, reasons, summaries and
  other human-readable text must not be. The premise is demonstrated against the
  substrate rather than asserted — with an empty `nfc_paths` profile, two normalization
  forms of one identifier canonicalize to different bytes — and the guard fails if a
  non-empty profile is ever passed. How the pattern is applied is pinned with it:
  `re.match` admits a trailing newline against `$`, `re.fullmatch` does not.
* Both modules are pinned by name in `tests/test_no_local_canonicalization.py`, so
  neither can leave the no-local-canonicalization scan silently.

### Added — reconciliation with the canonical S1 specification

`docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md` is the authoritative S1 contract and
equation specification. The guards are reconciled to it and are exact mirrors of it: a
test originates, adds, renames or reinterprets no contract field.

* `tests/s1_specification_mirror.py` — the pinned registries, transcribed from the
  specification and citing the section each block comes from, with
  `test_the_registry_cites_its_source` failing if a cited section is renamed there. It
  also builds **temporary representative shapes** — live models declared in the ratified
  `Annotated[str, StringConstraints(...)]` spelling — so the guards are exercised
  behaviourally before a production contract surface exists. These shapes declare no
  contract, are exported from nothing, and authorize nothing.
* **Registry authority (G-1).** `FIELD_CLASSIFICATION` pins the exact class set, the
  exact field set for every contract against Part D's stated cardinality, and the exact
  C5 category for every classified field. Self-tests fail on a field added, omitted,
  renamed or reclassified. Reconciled to the merged specification: the fourth mechanical
  class **C5d** for the six reserved lists; `AgentIdentityRef.lifecycle_state` and
  `ProposerAdvisory.candidates` as non-`str` entries; the C5a-keys/C5c-values shape of
  `normalized_fields`; the 23-field `ProposerAdvisory`; the retained `candidate_set_id`
  beside the nested `candidates`; and the eight contracts plus two nested shapes.
* **Behavioural O-1 coupling (G-2).** The bearer is constructed from a complete valid
  fixture supplying all twenty-three required fields, and the four coupling cases are
  exercised as live validation outcomes. Static AST inspection is retained as
  supplemental and is no longer described as proof of behaviour;
  `test_the_suite_kills_a_no_op_validator_mutant` shows a validator naming all four
  fields and enforcing nothing passing the static layer and being killed behaviourally.
* **Registry weakening (G-3).** Every C5a and C5b entry is mutation-pinned, not a
  sample. The mutated registry is fed through the guard's own verdict helper, and the
  sweep is 47 patterned entries × 8 weakening categories = 376 cases, all killed when
  that helper is sabotaged. The weakening domain is derived from the guard's predicate
  rather than hand-listed; the sibling patterned class is excluded as a *narrowing* and
  covered by its own 47-case sweep, so every registered category falls into one or the
  other.
* **Free text (G-4).** C5c bars the *mechanism*: no pattern or regex constraint of any
  kind, including arbitrary ASCII-only grammars that are neither named literal. Lawful
  Unicode free text is proved accepted by live model probes.
* **Decorative patterns (G-5).** Syntactic discovery is restricted to constraints that
  actually bind the field value; a pattern in `json_schema_extra`, a `description` or an
  `examples` entry is read as validating nothing. Live probes prove C5a rejects invalid
  identifiers, C5b rejects invalid tokens including slash, spaces, newline and
  homoglyphs, sequence-valued fields validate every element, and C5c accepts Unicode.
* **Dependency baseline (G-6).** `DEPENDENCY_BASELINE_MODULES` is derived from the
  declared dependency registry in `pyproject.toml` rather than written beside it, and the
  generated baseline setup is pinned by equality — a baseline carrying an added
  `import socket` fails a self-test. Pydantic's transitive schema-construction behaviour
  stays permitted, direct networking imports stay prohibited, and the two-entry
  allowlist is unchanged.
* **Dynamic imports (G-7).** Detection extended to a literal bound to a local name and
  passed to `__import__` or `import_module`, `exec("import socket")`,
  `eval("__import__('socket')")`, an import inside `compile(...)`, and the prohibited
  relative-import spellings — each with a negative control. The remaining ceiling is
  stated and demonstrated: arbitrary runtime composition, externally supplied strings and
  reflection are not proven absent by static scanning.
* **Documentation gates (G-8).** The Agentic Proposer documents are added to
  `scripts/check_doc_links.py`'s curated list, so its link coverage of them is real;
  `tests/test_documentation_consistency.py` asserts that and enforces the same rule
  package-locally. No terminology-gate coverage is claimed, and a self-test fails if such
  a claim is introduced.
* **Composition and identity (G-9).** `tests/test_advisory_contract_shape.py` discharges
  I7.11 against the corrected nested candidate graph: it bars a nested `ToolObservation`,
  **requires** the nested `CandidateAdvisory` sequence so a reversion to reference-by-id
  fails loudly, and bars any second identity on the candidate — the last as real mutated
  models, built by subclassing the ratified `CandidateAdvisory` shape and run through the
  same reachability verdict the live guard calls, directly and through a nesting advisory
  root, with a negative control proving a blinded walker lets the mutant escape. The C8
  `Annotated[str, StringConstraints(...)]` spelling is required and tested, and the
  declared-dependency count is corrected to two.

### Added — R-3 process ordering recorded as an explicit obligation

`tests/test_process_ordering_obligation.py` states R-3 as a **named skip**, not as a
green test. Before it, R-3 appeared in the specification and in no test file at all, so a
reader counting green tests would have found no signal that a ratified invariant was
uncovered. The module documents why the representative shape cannot exercise the rule —
`ProposerProcessStateTransition.state` is typed `ProposerProcessState` by the
specification, `vocabulary.py` does not declare that enum, and the mirror may not
originate a vocabulary the specification assigns to the public surface — pins that the
placeholder is still documented as one, and **arms itself** when the enum is declared, at
which point it fails until forward-only ordering is enforced. `[G]` What is not stated in the
specification is the enum's **cardinality** and R-4's **comparison basis**; terminal
membership follows by entailment from D8's typing and R-4's "when one is present". R-3
carries no weight in that argument — it permits at most one terminal state, it does not
require one. The module refuses to settle either open item and names both as questions for
the specification.

### Changed — documentation status language

Temporary status wording — unmerged-branch claims and SHA-based truths — is removed from
the readiness ADR, the specification, the README and `docs/S1_ENFORCEMENT.md`. Durable
text states that a decision is ratified, that a named guard enforces it, and that
production implementation remains separately gated; those are three distinct statuses and
are not collapsed. OD-1 – OD-4 have one **decision record**, the table in the readiness
ADR, with guard evidence and enforcement limitations folded beneath it as subordinate
detail; the specification states each decision in full as the implementation-ready
document, and the two must agree.

### Fixed — sixth audit round: controls that did not run the guard

* `tests/test_identifier_normalization.py` — the G-1 completeness check's decision is
  factored into `_completeness_verdict`, in the style of `_pattern_verdict`, and
  `test_the_registry_matches_the_declared_field_set_exactly` is refactored onto it. The
  three mutation controls — an added field, an omitted entry, a rename — now feed their
  mutated surface or registry through that function and assert the verdict changes,
  instead of asserting set inequality directly. They were controls in name only: with the
  live assertion neutered the whole suite stayed green at 1223 passed, and all three now
  fail.
* `tests/test_documentation_consistency.py` — the OD-4 agreement check anchored on
  `RATIFIED` and so read exactly one statement per document. Both documents state OD-4's
  resolution three times, including in Part D where an implementer reads contract shape,
  and flipping one of the unread statements to `(b)` left the suite green.
  `test_every_resolution_statement_in_each_document_says_the_same_thing` now collects
  **every** `resolved (x)` statement through a tempered match, requires each to name OD-4
  and `(a)`, pins the count per document, and checks the attributed count against the bare
  population so an unattributable statement is reported rather than skipped. Falsified
  against all six occurrences and against a deleted statement.
* `tests/test_advisory_contract_shape.py` — `RATIFIED_DIGEST_FIELDS` is applied by name
  over the whole reachable graph, so a `CandidateAdvisory` bearing `advisory_digest` or
  `parent_advisory_digest` is invisible from the advisory root and is caught only by the
  candidate root's empty exemption. That assertion had no mutation control. The per-root
  exemption is factored into `_exemption_for` / `_root_failures`, the live guard and the
  controls both run it, and both names are added to `RIVAL_IDENTITY_MUTATIONS`. Widening
  the candidate root's exemption now kills three tests. The stale cross-reference naming
  `test_the_digest_exemption_…` is corrected to `test_the_identity_exemption_…`.
* `tests/test_identifier_normalization.py` — the assertion
  `weakenings | narrowings == others` was a set identity that cannot fail; it is replaced
  by the denominator itself, `47 x 8 = 376` weakening cases plus `47` narrowing cases
  exhausting the `47 x 9 = 423` candidate reclassifications, with self-reclassification
  standing outside that count as the tenth candidate rather than inside it.

### Changed — what the guards do not yet establish, stated more completely

`docs/S1_ENFORCEMENT.md` gains two rows, both derived rather than hand-written.

The first records that the mirror declares two model validators, C7 and R-1a, and that
**every** other rule decidable from one instance of one contract is unenforced —
nineteen constructions the representative shapes accept: L-1; the three `candidates`
rules on both `ProposerAdvisory` (D7) and `AdvisoryCandidateSet` (D6); R-8's
no-duplicates rule on all six lists it names; the three Part D rejects-an-empty-list
rules; and R-1b(v) and R-1b(vi), whose local halves became decidable when OD-4(a) nested
the candidates. `tests/test_unenforced_local_rules.py` constructs a violating instance
for each, so the row cannot claim a rule is unenforced once it is, nor omit one that
still is. `CandidateAdvisory.claim_refs` is deliberately excluded and the exclusion is
tested: R-8 does not name it and its Part D row states `each C5a` only, so a duplicate
there is lawful and listing it would be a test originating a rule.

The second records that R-2, R-5, R-6, R-7, R-9 and R-10 are **named but not covered**,
and that a mention in a scope paragraph establishes nothing behavioural. These are
omissions of enforcement, not departures from the declared shape: every field name, type
and nullability in the mirror matches Part D. The "one decision record" gloss is restated
as a claim about **authority** rather than as an enumeration of four facts the
specification also states.

### Fixed — seventh audit round: a real escape, and three false statements

* `tests/test_advisory_contract_shape.py` — **the rival-identity exemption is now scoped
  to the bearer.** It was applied by name over the whole reachable graph, so a shape
  hanging off `ProposerAdvisory` but not reachable from `CandidateAdvisory` and declaring
  `advisory_digest` was reported by **neither** root: the advisory exempted the name
  wherever it appeared, and the candidate could not reach the shape. That is a second
  identity inside `P_unsigned`, which is what D6 bars. The walk now carries ownership —
  `_runtime_owned_fields_reachable_from` yields `(owner, field)` pairs and
  `_runtime_fields_reachable_from` is its projection, so the guards that bar a name at any
  depth are unchanged — and `exempt` is honoured only for a field the root itself
  declares. The special-case branch that pinned the old blindness as expected behaviour is
  deleted, and
  `test_a_sanctioned_name_on_a_shape_off_the_advisory_alone_still_fails` is the
  regression. Falsified two ways: un-scoping the exemption and discarding ownership each
  kill four tests.
* `docs/S1_ENFORCEMENT.md` — the "named in no test file" row was wrong in both directions
  at once: it named R-4, which `tests/test_process_ordering_obligation.py` mentions five
  times in text the previous commit added, and omitted R-7, which nothing mentioned at
  all. The row is replaced by two derived checks —
  `test_every_ratified_rule_is_named_somewhere_under_tests` and
  `test_the_named_but_unexercised_row_is_derived_from_the_test_tree` — which recompute
  membership from the specification's rule table and a scan of `tests/`, discounting the
  scope paragraph that only records why a rule is out of scope. The derivation excludes
  its own module, so it cannot read its own prose as coverage.
* `docs/S1_ENFORCEMENT.md` and `tests/test_process_ordering_obligation.py` — the terminal
  membership argument rested on a false premise. R-3 (`spec:1032`, not `:1030`) says "at
  most one terminal state and only in final position": it **permits** a terminal state
  and does not require one. The entailment survives on D8's typing plus R-4's "when one is
  present", and now rests on those alone. A second open item is recorded alongside
  cardinality: R-4 equates a `TerminalOutcome` with a `ProposerProcessState`, and a
  cross-enum `==` is never true in Python, so R-4 must mean equality of name or of value
  and does not say which.
* `tests/test_documentation_consistency.py` — the docstring of
  `test_there_is_exactly_one_owner_decision_record` still asserted the sentence the
  previous commit corrected in `docs/S1_ENFORCEMENT.md`. The two artifacts agreed on
  authority and disagreed in text; they now agree in both.
* `tests/test_boundaries.py` — `test_a_widened_baseline_setup_fails` was the same defect
  class as the three registry controls: deleting the equality pin at
  `test_the_baseline_setup_is_pinned_by_equality` left the file at 51 passed. The pin is
  factored into `_baseline_pin_verdict` and both the live assertion and the control run
  it. Falsified: neutering the verdict kills the control.

### Fixed — eighth audit round: the placeholder's reach, and coverage by registry

* `tests/test_unenforced_local_rules.py` — the registry grows from nineteen constructed
  violations to **twenty-eight**. Added: **S-1** on `AdvisoryCandidateSet`, both halves —
  a selector naming no member and a selector resolving to two; **S-2** on
  `AdvisoryCandidateSet` and, labelled `S-2 (via R-1b)`, on `ProposerAdvisory`, where
  R-1b(iii)/(iv) carry it rather than the specification stating it twice; **R-1b(vii)**'s
  local half — `requested_review_action` contradicting the selected nested candidate;
  **R-3**'s `at`-monotonicity, no-repeat and entangled terminal-count/terminal-position
  clauses; and **R-4**. Every one was confirmed accepted by the representative shapes
  before being listed. The module's boundary paragraph now states, per rule, why anything
  omitted is out of scope rather than leaving it to be inferred from the list's silence,
  and records that S-1 and S-2 are vacuous in S1 under B3 but exercised anyway, because
  the shapes do not enforce B3 either.
* `tests/test_process_ordering_obligation.py` and `docs/S1_ENFORCEMENT.md` — the claim
  that R-3's ordering rule "has nothing to be exercised against" was **false**. The
  `TerminalOutcome` placeholder blocks exactly two clauses — no backward transition, and
  subsequence of the chain — because each needs a process state to state a violation. The
  other four are violable with terminal states alone. Both documents now say which
  clauses are blocked and which are not, the skip reason names the distinction, and
  **R-4's uncovered status is recorded explicitly**: the placeholder does not block it at
  all, since both sides of R-4's comparison are `TerminalOutcome`, so the comparison-basis
  ambiguity does not arise there.
* `tests/test_documentation_consistency.py` — **coverage is decided by a registry, never
  by a textual mention.** Deriving it from mentions made the opposite error to the
  hand-written list it replaced: it classified R-4 as covered by the very module that
  states it covers none of R-4. `_rules_exercised_by_some_test` now reads
  `UNENFORCED`, the new `ENFORCED` registry, and the obligation module's new
  `OBLIGATION_RULES`, and `test_exercise_is_decided_by_a_registry_and_never_by_a_mention`
  asserts the reason rather than the outcome, so deleting a case fails rather than passing
  on a mention.
* `tests/test_documentation_consistency.py` — `_specified_rule_ids()` is pinned by set
  equality against `RATIFIED_RULE_IDS`, in the same form as `RATIFIED_DIGEST_FIELDS`, so a
  rule added to or removed from the specification fails here rather than silently changing
  what every derivation is quantified over. `_RULE_ID` now matches the bold-bullet form as
  well as table rows, so **S-1 and S-2** — stated as prose under D6, and previously invisible
  to every derivation — fall inside the "every ratified rule is named somewhere" check.
  The headline count in the enforcement row is pinned against the registry's length.

### Changed — reasoning functions and strategies (OD-5)

Documentation and guards only. No `src/` change, no version change, no
public-API snapshot, no platform-freeze artifact touched.

* **`CognitiveRoleContract.permitted_reasoning_strategies` added as a C5d reserved
  list**, rejecting every non-empty value. D2's stated cardinality goes from 10 to 11 and
  the C5d roster from five fields to six; `docs/S1_ENFORCEMENT.md` and this file are
  updated in the same change so no document states the old count. `[R]` The eventual
  ratified form is an **allowlist that rejects an empty list**, which is the opposite
  rule on the same axis: S2 **replaces** the C5d validator and **retypes** the element
  rather than widening the reserved field, and that transition **requires separate
  ratification** which OD-5 does not give. No strategy catalogue is drafted or ratified,
  and no individual strategy is named.
* **The four-way distinction is stated once, in D8:** `primary_function` (the role's
  organizational purpose), `permitted_reasoning_strategies` (the methods the role may
  select among), `declared_strategy` (the method the process record asserts was used),
  and the terminal outcome. Evidence collection and verification stay **contract
  mechanisms**, and abstention and escalation stay **outcomes**; none is a reasoning
  strategy.
* **R-3's lifecycle is unchanged**, and a new D8 subsection states what the record does
  not represent: a forward-only record deliberately carries no internal strategy control
  flow, so the **absence of repeated or branching transitions is not evidence that no
  internal iteration or branching occurred**.
* **`declared_strategy` carries no authority.** It is metadata outside `P_unsigned`;
  declaration does not establish conformance; and S1 neither selects, validates nor
  cryptographically binds a reasoning strategy — selection and enforcement are S2's.
* **Guards.** `CONTRACT_CARDINALITY`, `FIELD_CLASSIFICATION` and the
  `CognitiveRoleContract` representative shape in `tests/s1_specification_mirror.py`; the
  `C5D_ENTRIES` set-equality pin extended to six entries plus a behavioural probe that
  the new field rejects every non-empty value, in
  `tests/test_identifier_normalization.py`; assertions in
  `tests/test_advisory_contract_shape.py` that neither `declared_strategy` nor
  `permitted_reasoning_strategies` appears in the `P_unsigned` projection field list; and
  a **heuristic spot-check** in `tests/test_documentation_consistency.py` refusing claims
  of S1 authority over a reasoning strategy — selection, validation or binding. `[I]` It
  is a regex over English prose and is **not** coverage of a class: it is not proof that
  no such claim can be written, and it is stated here as what it is proven against rather
  than as a guarantee. It classifies each sentence by **actor**, which is what the subject
  matter turns on — the same sentence is a defect with S1 as its subject and correct with
  S2 as its subject. Proven against a named corpus of twenty-two claims it must catch and
  eighteen correct statements it must leave alone, the latter including true statements
  about S2 and the reserved field's own emptiness rule.

### Fixed — ninth audit round: OD-5's own overstatements

An independent audit of the OD-5 commit confirmed the four-way distinction, the C5d
classification and the unchanged R-3 lifecycle, and found five defects. Documentation and
guards only.

* **A rename left three dangling cross-references and a contradicted sentence.** Renaming
  the ADR's table to *Owner decisions OD-1 – OD-5* left two references to the old heading,
  a sentence crediting OD-4 with shape-bearing that OD-5 also has, and a
  three-statuses sentence still scoped to four. The suite was green over all four because every existing guard
  read the table rather than the prose around it. Two new scans close the class: italic
  cross-references to the owner-decision section must resolve against the live heading, and
  no document may claim one decision alone bears on contract shape.
* **The strategy-authority scan was narrower than its stated coverage.** The ADR and this
  file said it refused *any* affirmative claim; an audit found eight ordinary spellings
  passing — an active-voice cross-field check naming the two fields is the representative
  one, and the set is pinned in the test module rather than restated here. The
  cause was structural: `\b` does not break at an underscore, so a pattern anchored on
  `\breasoning` never reached `permitted_reasoning_strategies`, and the subject of such a
  sentence is as often "the builder" as "S1". The patterns now cover both voices, three
  subjects and the underscored field names; the eight escaping spellings are pinned as a
  named regression set; and the coverage claim is stated as the forms enumerated rather
  than as "any".
* **C5d's class definition was false for its sixth member.** It said reservation means
  "populating it later is not a schema change", which is untrue of a field whose ratified
  form retypes the element and removes the default. The definition now states what C5d
  guarantees in both cases — no value accrues before a vocabulary is ratified — instead of
  leaving the correction to a note beneath it.
* **The ADR labelled "Ratified rider" what the specification marks `[R]`.** Restated so
  the two agree: what OD-5 ratifies is the **bar on the route**, the field may not be
  brought into service by widening it in place. The allowlist form itself is not ratified.
* **Two consequences went unstated.** The forward-only-record and unverified-declaration
  limitations are now **K.7**, where a reader consulting Part K for what the specification
  does not evidence will find them. D2 now states that `declared_strategy` is required and
  non-empty while `permitted_reasoning_strategies` admits only `[]`, so every conformant S1
  pair declares a method the role is not permitted to select, and `[R]` no S1-era role
  contract survives the allowlist transition unrepopulated.

`[R]` One question raised by the audit is **not** answered here and is recorded rather
than resolved: whether a role's permitted **methods** fall within ratified D1's *minimum
immutable attributes required for deterministic role matching* and outside D2's bar on a
**constitution-derived attribute**. It is an instance of a question the readiness ADR
already carries under *Open architectural dependency: the Agent Constitution*, and is
recorded there. Nothing turns on it while the field admits no value; the ratification that
lands the allowlist must answer it first.

### Fixed — tenth audit round: three contradictions and a rebuilt scan

Documentation and guards only. `permitted_reasoning_strategies`' presence in D2 and D2's
preamble are untouched; they are under a separate owner decision.

* **The specification contradicted its own OD-5 entry.** Its ratification statement
  credited OD-4 with closing the last shape-bearing question, while its OD-5 entry records
  *Bears on contract shape: yes*. Corrected, and `_SOLE_SHAPE_BEARER_CLAIM` now carries
  six wordings rather than two. `[I]` The two instances found so far are phrased so
  differently — one about a decision, one about a question, sharing almost no substring —
  that a fixed-sentence check would have caught one and certified the other. The wordings
  themselves are enumerated in the test module, not restated here, since this scan reads
  this file too.
* **The ADR named guards for four of the five decisions** while asserting each of five
  carries an implementing guard. OD-5's four are now named.
* **C5d called all five original members reason-code fields.** `deterministic_checks`
  names checks that were run and `semantic_audit_refs` holds references to audit records;
  neither is a reason code, and ratifying a reason-code catalogue would tell an
  implementer nothing about either. Corrected in the class definition, in the sixth-member
  note, and in Part J, which deferred all three under one heading and now defers three
  catalogues separately.
* **The strategy-authority scan is rebuilt to discriminate by actor.** An audit found nine
  of ten fresh claims escaping — verbs it did not carry, and "Stage S1" and "The advisory
  builder" as subjects it did not know — and, in the other direction, two patterns that
  named no actor and so flagged *true* statements about what S2 does. The scan now
  classifies whole sentences: an authority claim offends when an S1 actor is the subject
  of the verb and the subject matter its object; binding and conformance claims offend
  without an actor, since identity is S1's by definition and a declaration evidences
  nothing at any stage. `[V]` All ten fresh claims are caught, no true S2 statement is
  flagged, and the guard is stated in the ADR and here as a **heuristic spot-check proven
  against a named corpus**, not as coverage of a class.

`[I]` Two things the rebuild had to keep, recorded because each was tried and reverted.
**Adjacency**: a first draft let the actor, verb and subject matter fall anywhere in the
sentence and flagged four true sentences from these documents, so the actor must stand
within two words of its verb. **Block splitting**: collapsing a whole document merges list
items that do not end in a full stop, pairing one item's actor with another's verb, so
blocks are cut at blank lines, list markers, headings and table rows before sentences are
split. Both failure modes are pinned as tests.

### Not implemented

The eight canonical contracts, Equations 1–4, proposal identity, invoice-domain
checks, reason codes, read-only adapters, model-assisted extraction, the semantic
auditor, and any HTTP endpoint.

The contracts and equations are **specified and unimplemented**: no contract module
exists in `src/`, and the guards that would catch a departure from the specification are
dormant on that surface and exercised against temporary representative shapes instead.
Production implementation is separately gated. No public-API snapshot is created: there
is no S1 contract surface to freeze, and the version stays `0.0.1`.
