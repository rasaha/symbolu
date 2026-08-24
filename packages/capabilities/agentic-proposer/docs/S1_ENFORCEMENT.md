# S1 — enforcement obligations discharged, contracts blocked

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

### `[R]` Owner decision — does D2 require the invariant or the scan?

This is not a scanner detail and should not be settled as one. An audit demonstrated
a working, byte-correct local SHA-256 identity function living in `src/` with every
guard green, by assembling the module and attribute names through a helper function:

```python
def _b(*p): return ''.join(p)
_m = __import__(_b('hash', 'lib'))
```

The route is disclosed above as uncovered, but disclosure is not closure. Two
readings of D2 are available and they differ in cost:

* **D2 means the invariant** — no working local digest is reachable from `src` at
  all. Closing this means tracking assembly through call returns, subscripts and
  external inputs: materially more analysis, and a scan that will keep growing
  as new routes are found.
* **D2 means the scan** — no *modelled* composition route reaches a hashing module,
  and identity computed by deliberately defeating the scan is a governance failure
  rather than a test failure.

Five rounds of hardening have closed every route an auditor named and disclosed the
rest. Which of the two D2 means decides whether a sixth round is work or waste.

`tests/test_no_local_canonicalization.py` now pins the three modules by name and
asserts that every file in `src` and `tests` is either scanned or one of the two
named exemptions, so a module cannot leave the scan silently.

## What did not land, and why

The eight canonical contracts and Equations 1–3 remain unimplemented. **Nothing in
this repository defines them**: not the ADR, which lists them only as out of scope at
S0 and does not name them; not `docs/S0_SCOPE.md`; not any committed design document.
The task that authorized S1 carried an empty specification block for them.

They were therefore not inferred, derived or invented. What is undefined is recorded
in the session report: the eight contract names, their fields and cardinality, and
the inputs and outputs of each of Equations 1–3.

`ProposerAdvisory` and `CandidateAdvisory` are **not** defined here for the same
reason. D7 ratifies their names, kind, identity field and exclusions, but not their
field sets; defining them from D7 alone would be inventing a contract and freezing a
guess. The D7 guard is complete and dormant instead — it fails the moment either type
appears without the ratified shape.

## Version

`0.0.1`, unchanged. No public contract is frozen at it and no public-API snapshot is
created: the S1 contract surface is undefined, and the S0 surface (the D4 vocabulary)
is already pinned by equality in `tests/test_vocabulary.py`.
