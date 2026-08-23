# ADR — Ugence Agent Constitution (AC-0)

**Status:** Accepted for AC-0 scope. Owner decisions 1–5 from the Agent
Constitution and Conformance implementation-readiness report are **not recorded
here** — see §0.

**Scope:** `packages/contracts/agent-constitution` — distribution
`ugence-agent-constitution`, namespace `ugence_agent_constitution`.

**Supersedes:** nothing. **Modifies:** no existing package.

Findings are labelled `[V]` verified, `[I]` inferred, `[R]` requires
ratification, `[G]` gap.

---

## 0. What this ADR does not record

`[G]` The implementation brief for AC-0 carried the five ratified owner decisions
as the literal placeholder `[OWNER: fill in]`. **The decision text was never
supplied to this implementation.** This ADR therefore records the decisions that
AC-0's own scope statement determines — §§1–9 below, each of which is directly
implied by the brief's explicit inclusions and exclusions and is verifiable
against the shipped code — and records **no** text for owner decisions 1–5.

`[R]` Before this ADR is treated as ratified, the owner must fill §10 with the
five decisions as actually ratified, and reconcile them against §§1–9. If any
ratified decision contradicts a section below, the code implements the wrong rule
and the section names exactly what to change. Nothing in AC-0 was built on a guess
about what those five decisions said; where the brief was silent, this ADR says so
rather than inventing a decision.

---

## 1. The package is a leaf, and stays one

`[V]` AC-0 depends on `pydantic` and the standard library and on **no other Ugence
package**. Verified by `tests/packaging/test_import_boundary.py`, which
AST-scans every module for static imports, scans for dynamic
`import_module`/`__import__` targets, asserts no `ugence_*` root other than itself
appears, cross-checks the allowlist against `pyproject.toml`'s declared
dependencies, and asserts that importing the package loads no sibling `ugence_*`
module at runtime.

**Why.** A contract package is the thing everything else is allowed to import. The
moment it imports a tooling package, an authority, or a runtime, it stops being
safely importable and every consumer inherits that package's dependency graph. The
first such import is always the cheap one that looked harmless, which is why the
gate is stated as a property of the whole module tree rather than as a list of
today's imports.

**Consequence, accepted.** Canonical JSON is duplicated rather than imported — see
§4.

## 2. A draft and a ratified constitution are different types

`[V]` `AgentRoleManifest` and `AgentConstitution` are separate frozen models.
`AgentRoleManifest.carries_authority` and `.is_ratified` are class-level `False`
constants, not fields. A manifest payload validated as a constitution is refused
with the dedicated code `AC_DRAFT_IS_NOT_A_CONSTITUTION`.
`is_ratified_constitution()` rejects a draft, a duck-typed impostor, and a
correctly-typed constitution that fails validation.

**Why one type with a `ratified: bool` was rejected.** A flag is a field somebody
sets. A type is a thing somebody has to construct. The failure mode being designed
against — a draft treated as binding — is exactly the failure mode a boolean
invites, and it would be invisible in a diff.

`[I]` The generic wrong-kind refusal (`AC_SCHEMA_VERSION_WRONG_KIND`) exists for
every other mismatch; the manifest-as-constitution case gets its own code because a
caller reading a generic type error may simply fix the annotation and move on.

## 3. Frozen artifacts, unknown fields refused

`[V]` Every artifact is a frozen pydantic model with `extra="forbid"`.

**Why frozen.** An artifact that can be mutated after its digest is computed is an
artifact whose digest means nothing.

**Why `extra="forbid"`.** A payload carrying a field this build does not know
about is not a payload this build can digest faithfully: the unknown field would
be dropped and the digest would attest to less than the author wrote. Refusing is
the fail-closed answer, and it is what makes forward-incompatible content surface
as a refusal rather than as silent truncation.

**Consequence, accepted.** Drafting still has to be possible, so
`AgentRoleManifest.revise()` is copy-on-write: a new value, an advanced
`draft_revision`, and the stale digest cleared. Editing is therefore always a new
identity, and no already-digested draft changes under a reader.

## 4. Canonical JSON is duplicated, and the duplication is gated

`[V]` `ugence_agent_constitution.serialization.canonical_json` is semantically
identical **by value** to
`ugence_policy_workflow_compiler.serialization.canonical_json`: same recursion,
same sorted keys, same compact separators, same enums-by-value, same set ordering
by `repr`, same UTF-8 preservation.

`[V]` `tests/serialization/test_canonical_json_equivalence.py` loads the
compiler's module **directly off disk by path** and asserts byte-identical output
over a corpus chosen to hit every branch of the recursion. Loading a file by path
is not importing a distribution, so the gate costs nothing at the boundary.

**Why not import it.** §1. **Why not extract a third shared package.** That would
be a new distribution that both the compiler and this package depend on — a
dependency-graph change to an existing package, which AC-0 is not authorized to
make. `[R]` Extracting the shared module is the obvious follow-up and needs its own
ratification.

**Known limitation.** `[V]` The equivalence test skips when the compiler source is
absent (an installed wheel, a partial checkout). A skip means the equivalence was
not checked in that run, not that it holds.

## 5. Fingerprints are logical, scoped, and not signatures

`[V]` A fingerprint is `sha256:<64 hex>` over the canonical encoding. The
algorithm prefix is carried in every stored value so a future algorithm change is
visible rather than silently redefining what a bare hex string means.

`[V]` A digest-bearing artifact excludes its own digest field from its own digest
scope — otherwise the digest would have to commit to itself, which has no fixed
point. Exclusion is **top-level only**: everything nested is in scope, so a change
inside a requirement, an issuer identity or a predecessor reference is a material
change. Verified by tests over every top-level field and over nested requirement,
obligation, registry-entry and issuer edits, plus the property that reordering
requirements changes the digest because order is authored.

`[V]` `fingerprint()` reads no clock, environment, filesystem or random source.
Stamping is idempotent.

**Not signing.** `[V]` A fingerprint attests to content identity only, never to
who produced it or whether they were entitled to. `AgentConstitution.is_signed` is
permanently `False` and no cryptographic backend is a dependency.

## 6. Three outcomes, and `INDETERMINATE` is not a soft pass

`[V]` `VALID` / `INVALID` / `INDETERMINATE`, aggregated `INVALID` >
`INDETERMINATE` > `VALID`. `ValidationReport.is_usable` is true for `VALID`
**alone**, and a report's outcome is always derived from its findings rather than
passed in, so a report cannot claim `VALID` while carrying an `INVALID` finding.

The division:

* A **contradiction** is `INVALID` — the artifact says two incompatible things and
  no extra context reconciles them. A capability both `MANDATORY` and
  `PROHIBITED`; a behaviour both required and forbidden; a `CONDITIONAL`
  obligation with no condition.
* An **ambiguity** is `INDETERMINATE` — the artifact says one thing two ways, or
  says something this build cannot resolve. A duplicated `requirement_id`; a
  mandatory field carrying surrounding whitespace; a `MANDATORY` requirement
  pinning no resolvable registry entry; an unrecognized schema version.

**Why the split matters.** Collapsing ambiguity into `INVALID` would report a
defect where there is a question. Collapsing it into `VALID` would have this
package silently choose an interpretation that belongs to a person. Both refuse
use; only one is a defect report.

`[I]` Surrounding whitespace on a mandatory field is treated as ambiguity rather
than as a cosmetic nit specifically *because* these artifacts are content-addressed:
`"payments"` and `" payments"` read as one value and digest as two. Stripping
silently would change what the digest attests to; keeping silently lets two
identical-looking artifacts carry different identities.

## 7. Validation is deterministic and total

`[V]` No clock, environment, filesystem, randomness, or unsorted iteration.
Findings are sorted by severity, then code, then path. Rules are evaluated in full
with no short-circuiting, so a report lists every problem at once and re-validating
a fixed artifact does not surface a new problem each round.

`[V]` Validation never raises for bad data — a malformed payload is a *result*, so
callers can collect and compare outcomes without exception control flow. Exceptions
are reserved for programmer errors: an unknown artifact *kind* (a closed constant
of the build) raises; an unrecognized schema *version* of a known kind is data and
answers `INDETERMINATE`.

`[V]` Property-based tests over generated drafts and constitutions assert
totality, determinism finding-for-finding, and that every emitted code is a
declared code.

## 8. Two version questions, kept apart

`[V]` **Schema** compatibility (`SUPPORTED` / `RETIRED` / `UNRECOGNIZED`) asks
whether this build can read a shape. `UNRECOGNIZED` yields `INDETERMINATE`: a
build that has never seen a shape cannot know an artifact in it is well-formed, and
guessing "probably compatible" is the failure mode the rule exists to prevent.
`RETIRED` yields `INVALID` — a shape deliberately dropped is known-wrong, not
unknown. `RETIRED_SCHEMA_VERSIONS` is empty in this release and exists so the
distinction is available before it is needed.

`[V]` **Succession** asks whether one artifact legitimately supersedes another: same
lineage identity, `artifact_version` bumped strictly upward, content materially
different. Reusing or lowering the version is `INVALID`
(`AC_SUCCESSION_VERSION_NOT_BUMPED`) — two artifacts sharing a version are
indistinguishable to anyone holding a reference to "that version". Reusing the
predecessor's digest is `INVALID`: a successor that supersedes nothing is not a
successor.

`[V]` Only release `MAJOR.MINOR.PATCH` versions are ordered. Pre-release and
build-metadata suffixes are **refused rather than ordered**, because their ordering
rules are subtle enough that a silent wrong answer is likelier than a right one,
and this comparison decides whether one governance artifact supersedes another.

`[I]` Schema versions participate in an artifact's digest; the *distribution*
version never does. A package-version bump must not perturb a stored digest.

## 9. Self-ratification is refused structurally

`[V]` An issuer whose `issuer_id` equals the `source_manifest_author_id` of the
draft being ratified yields `AC_SELF_RATIFICATION` (`INVALID`). Comparison is on
stripped identifiers, so trailing whitespace does not slip past. Two blank
identities are reported as *missing*, not as self-ratification — a second
misleading finding about one defect helps nobody.

**Why this is not an authority decision.** The package does not decide who *may*
ratify; that is out of AC-0 scope entirely. It observes that an artifact naming one
identity in both roles has recorded no independent act at all, which is a
structural property of the record, decidable from the artifact alone.

`[I]` `IssuerIdentity` is unverified provenance. AC-0 ships no signing, so nothing
about the issuer is proven and no `IssuerKind` value confers authority.

## 10. Owner decisions 1–5 — NOT RECORDED

`[G]` Reserved. Fill with the five decisions as ratified in the Agent Constitution
and Conformance implementation-readiness report, then reconcile against §§1–9. See
§0.

| # | Decision | Ratified text | Reconciles with |
|---|---|---|---|
| 1 | — | *not supplied* | — |
| 2 | — | *not supplied* | — |
| 3 | — | *not supplied* | — |
| 4 | — | *not supplied* | — |
| 5 | — | *not supplied* | — |

---

## Out of scope for AC-0 — by decision, not by omission

`[V]` No compiler, no capability registry, no conformance findings or verdicts, no
signing, no UI, no LLM assistance, no runtime binding, no authority decision. Each
is reported `False` by `version_info()`, and
`tests/packaging/test_public_api.py` asserts the curated surface carries no
matching name.

`[V]` The names `CapabilityRegistry`, `CapabilityDefinition`,
`CapabilityManifest`, `CompilationResult`, `AuthorityRequirement`,
`GovernanceDisposition` and `resolve_policy` belong to other packages and are not
reused. `CapabilityRegistryEntryRef` is the one exported name containing
"registry"; it is a *reference to* an entry in a registry this package does not
own — the opposite of owning one — and a test pins it to four fields with no
resolve or lookup surface.

## Maturity

`[V]` Deterministic and offline. 222 tests pass in this build, including negative
controls that assert each invariant test fails when its invariant is inverted, and
two meta-controls demonstrating that an always-accept and an always-refuse checker
would both be caught by the control table.

`[V]` **Not** pilot-validated. **Not** production-certified. No claim is made about
behaviour under any workload, and no artifact defined here has been exercised by any
consumer — AC-0 has none by design.
