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

### Not implemented

The eight canonical contracts, Equations 1–3, proposal identity, invoice-domain
checks, reason codes, read-only adapters, model-assisted extraction, the semantic
auditor, and any HTTP endpoint.

The contracts and equations are not merely unauthorized now: nothing in this
repository defines them. They were not inferred, derived or invented, so
`ProposerAdvisory` and `CandidateAdvisory` are not defined either — D7 ratifies their
names and exclusions but not their field sets. The D7 guard is complete and dormant
instead. No public-API snapshot is created: there is no S1 contract surface to freeze,
and the version stays `0.0.1`.
