# S1 — enforcement obligations discharged; contracts specified, not implemented

## What landed

The three `[R]` obligations the MVP readiness ADR carries for S1, each enforced by a
test rather than by prose:

| Obligation | Decision | Test module |
| --- | --- | --- |
| No auditor status may be assigned or converted into a `TerminalOutcome` or `CandidateDisposition` field | D6 standing rule | `tests/test_no_auditor_status_projection.py` |
| The advisory contract's names, kind, sole identity field, identity substrate, barred fields at any nesting depth, and barred name prefixes | D7 | `tests/test_advisory_contract_shape.py` |
| The role projection is not re-exported from any shared contract package and exposes no role lifecycle verb | D8 | `tests/test_role_projection_bounds.py` |

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

## What did not land, and why

The eight canonical contracts and Equations 1–4 remain **unimplemented**. They are no
longer **undefined**: `S1_CONTRACT_AND_EQUATION_SPECIFICATION.md` specifies them
literally — every contract, every field, the frozen `P_unsigned` projection and every
equation signature. Specification is not authorization: no contract module exists in
`src/`, the version is unchanged, and implementation stays unauthorized until that
document is independently reviewed and merged.

When this section was first written, nothing in this repository defined them: not the
ADR, which lists them only as out of scope at S0 and does not name them; not
`docs/S0_SCOPE.md`; not any committed design document. The task that authorized S1
carried an empty specification block for them.

They were therefore not inferred, derived or invented **at that time**: defining them
from D7 alone would have been inventing a contract and freezing a guess. The D7 guard
was left complete and dormant instead, and it still is — it fails the moment either
type appears without the ratified shape.

What closed the gap was an owner ratification, not an inference. The field sets now
recorded in `S1_CONTRACT_AND_EQUATION_SPECIFICATION.md` derive from that ratification
together with D1, D3, D4, D7 and D8, and that document marks which content is
owner-ratified and which is authored from it.

### Guard corrections: what is done, and what is left

The O-1 – O-4 refinements and their guards are recorded under *What O-1 – O-4 changed*
above; that is the canonical account and this section does not restate it. What follows
is only the residue the contract specification adds.

| Item | Status |
| --- | --- |
| Lifecycle bound narrowed to authority, not vocabulary (O-2) | **done** — `tests/test_role_projection_bounds.py` |
| Ratified kind required on `ProposerAdvisory`, barred on `CandidateAdvisory` (O-3) | **done** — `tests/test_advisory_contract_shape.py` |
| Selection-dependent coupling (O-1) | **done** — `tests/test_selection_dependent_fields.py`, with one correction outstanding: the dependent-field set is matched by name alone, so `CandidateAdvisory.requested_review_action` — the candidate's own required, non-null routing — is caught as if it were selection-dependent. It must be scoped to its bearer contract |
| Identifier normalization (O-4) | **done** — `tests/test_identifier_normalization.py`, with one gap outstanding: classification is by name suffix, which reaches neither `tool_name` nor the scope fields. The specification classifies every field explicitly and requires the guard to read an exact pinned registry |
| `sha256:` prefix literal vs. `SUSPECT_TEXT` | **outstanding** — a module-path-scoped text mask in the one authorised identity module, with mutation tests. No definition-name exemption is needed: the ratified identity functions are named `compute_advisory_identity` and `verify_advisory_identity`, which carry no suspect substring |
| `pydantic` loads `socket`, which `tests/test_boundaries.py` forbids | **outstanding, owner decision** — bare `import pydantic` does not load `socket`; defining any `BaseModel` does. Every contract is a `BaseModel` and `pydantic>=2` is a ratified core dependency, so the first contract module trips that guard for a reason unrelated to the contracts |
| `tests/test_vocabulary.py` pins the S0 export surface by equality | **outstanding** — it must be updated to the full S1 surface in the same change that exports the first contract, and not before |

None of these is discharged by the specification document, which changes no test.

## Version

`0.0.1`, unchanged. No public contract is frozen at it and no public-API snapshot is
created: the S1 contract surface is undefined, and the S0 surface (the D4 vocabulary)
is already pinned by equality in `tests/test_vocabulary.py`.
