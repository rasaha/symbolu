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
  class **C5d** for the five reserved lists; `AgentIdentityRef.lifecycle_state` and
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
specification is the enum's **cardinality**; terminal membership follows by entailment
from D8's typing, R-3's chain and R-4's phrase "the terminal `ProposerProcessState`". The
module refuses to settle the cardinality and names it as a question for the
specification.

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

`docs/S1_ENFORCEMENT.md` gains two rows. The mirror declares two model validators, C7 and
R-1a, and **not** five further rules of the same locally decidable kind: L-1's self-parent
bar, D7's three `candidates` rules (empty, duplicate `candidate_id`, descending order) and
R-8's no-duplicates rule on `observation_refs`; `WorkMandate.allowed_source_scopes`
rejecting an empty list is likewise unenforced. The representative shapes construct
successfully in violation of each. These are omissions of enforcement, not departures from
the declared shape — every field name, type and nullability matches Part D. Separately,
R-2, R-4, R-5, R-6, R-8, R-9 and R-10 are named in no test file at all, unlike R-3, and
that is now recorded. The "one decision record" gloss is restated as a claim about
**authority** rather than as an enumeration of four facts the specification also states.

### Not implemented

The eight canonical contracts, Equations 1–4, proposal identity, invoice-domain
checks, reason codes, read-only adapters, model-assisted extraction, the semantic
auditor, and any HTTP endpoint.

The contracts and equations are **specified and unimplemented**: no contract module
exists in `src/`, and the guards that would catch a departure from the specification are
dormant on that surface and exercised against temporary representative shapes instead.
Production implementation is separately gated. No public-API snapshot is created: there
is no S1 contract surface to freeze, and the version stays `0.0.1`.
