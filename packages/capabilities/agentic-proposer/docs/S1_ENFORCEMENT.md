# S1 — enforcement obligations discharged, contracts blocked

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

One interaction is worth recording because it is not obvious from either rule alone.
D7 requires identity to be produced by `ugence_jcs.canonical_sha256_hex`; D2's text
guard bars the substring `sha256` anywhere in this package. Read literally, no source
can satisfy both. The text guard therefore masks the permitted substrate call
spellings before scanning: the exemption is those exact spellings and nothing wider,
so a local `hashlib.sha256` in the same position is still caught — by the text scan,
the import scan, and D7's own substrate rule.

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
