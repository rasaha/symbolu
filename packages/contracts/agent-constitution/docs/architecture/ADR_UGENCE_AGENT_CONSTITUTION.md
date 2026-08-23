# ADR — Ugence Agent Constitution (AC-0)

**Status:** Ratified. Owner decisions 1–5 are recorded verbatim at §10 with
`[R]` status and reconciled against §§1–9. Decision 2 (canonicalization) contradicted
§4 as originally written; §4 has been rewritten and the code reframed accordingly.
The other four are consistent with the implementation as shipped.

**Scope:** `packages/contracts/agent-constitution` — distribution
`ugence-agent-constitution`, namespace `ugence_agent_constitution`.

**Supersedes:** nothing. **Modifies:** no existing package.

Findings are labelled `[V]` verified, `[I]` inferred, `[R]` requires
ratification, `[G]` gap.

---

## 0. Provenance of the owner decisions

`[V]` The AC-0 implementation brief carried the five owner decisions as the
literal placeholder `[OWNER: fill in]`, and the implementation-readiness report
they came from is not present in this repository. The package was therefore built
**without** the decision text: §§1–9 record only what AC-0's own scope statement
determines, and §10 was left an explicitly empty `[G]` table rather than filled
with a guess.

`[R]` The decisions were subsequently supplied by the owner and are recorded
verbatim at §10. Each is reconciled against §§1–9 there. Decision 2 contradicted
§4 and that section has been rewritten; the remaining four are consistent and
required no implementation change.

`[G]` Four validation questions were derived during recovery, before the decision
subjects were known, and were mistaken at the time for the owner decisions. They
are **not** owner decisions and are not ratified. They are preserved as open
design questions at §11, outside §10, so that a later session does not re-derive
them and does not mistake them for ratified text a second time.

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

## 4. This package owns canonicalization

**Rewritten under ratified decision 2.** `[R]` As originally written, this section
described `ugence_agent_constitution.serialization.canonical_json` as "identical
**by value**" to the policy-workflow compiler's module, called the test that
compares them an *equivalence* gate, said "a future divergence in **either** copy
fails a gate", and named extraction of a neutral third shared distribution as the
obvious follow-up.

That framing placed the two implementations on equal footing and treated the
compiler's copy as a co-equal reference. Decision 2 ratifies the opposite:
`agent-constitution` **is the canonical owner** of the deterministic
representation and fingerprinting rules for Agent Constitution contracts, a
consumer "must not maintain an independently authoritative implementation", and
byte-equivalence testing "may be retained only as a migration or compatibility
ratchet and must not be described as establishing two equal sources of truth".
The original §4 therefore contradicted the ratified decision, and the neutral
third-package follow-up it proposed is superseded — the destination is not a
shared leaf both packages defer to, but consumers depending on the canonicalization
contract this package publishes.

### What the ratified rule is

`[R]` `ugence_agent_constitution.serialization.canonical_json` is the
**authoritative** definition of canonical form for these contracts: sorted keys,
compact separators, enums by value, sets sorted by `repr`, UTF-8 preserved. It is
published through the curated API (`to_canonical_obj`, `dumps`, `dumps_pretty`,
`loads`) and is what a future compiler or any other consumer must use.

`[V]` AC-0 depends on no compiler for canonicalization: the import boundary gate
(§1) forbids importing `ugence_policy_workflow_compiler` statically or
dynamically, and this module reads nothing outside itself at runtime.

### The compatibility ratchet

`[V]` `tests/serialization/test_canonical_json_compatibility_ratchet.py` loads the
compiler's module directly off disk by path and asserts that **the compiler's
output still matches this package's**. The direction is deliberate and is now
stated in the assertions themselves: this package's output is the expected value,
the compiler's is the observed one. It is a migration ratchet against an existing
legacy copy, not a mutual equivalence gate, and it establishes one source of truth,
not two. If the two ever diverge, this package is correct by ratification and the
consumer is wrong — the test failing does not put the question up for debate.

`[V]` Loading a file by path is not importing a distribution, so the ratchet costs
nothing at the boundary.

**Known limitation.** `[V]` The ratchet skips when the compiler source is absent
(an installed wheel, a partial checkout). A skip means the consumer copy was not
checked in that run — it says nothing about this package's own canonicalization,
which is authoritative regardless and is gated independently by
`tests/serialization/test_canonical_json.py`.

`[G]` Migrating `ugence-policy-workflow-compiler` onto this package's published
canonicalization contract, and retiring the ratchet once it has, is follow-up work
outside AC-0: it modifies another package, which AC-0 must not do.

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

## 10. Owner decisions 1–5 — RATIFIED

`[R]` The five decisions below are recorded **verbatim** as ratified by the owner.
Reconciliation against §§1–9 follows each. One decision (2) contradicted this ADR
as originally written; the rest are consistent with the implementation as shipped.

| # | Decision | Status | Reconciles with |
|---|---|---|---|
| 1 | Compiler | `[R]` Consistent; no implementation change | §§1, 6, "Out of scope" |
| 2 | Canonicalization | `[R]` **Contradiction** — §4 rewritten, code and tests reframed | §4 (rewritten), §1 |
| 3 | Conformance Authority signing | `[R]` Consistent; no implementation change | §§5, 9, "Out of scope" |
| 4 | `packages/contracts/` tier | `[R]` Consistent; no implementation change | Scope header; §1 |
| 5 | Credential Broker | `[R]` Consistent; no implementation change | §1, "Out of scope" |

### Decision 1 — Compiler

> AC-0 SHALL NOT implement, embed or depend upon an Agent Constitution compiler. A
> Constitution MAY be constructed and validated directly through the AC-0 contract
> surface. Compiler-produced Constitutions are not required in AC-0. Any future
> compiler is a separate capability and must consume the ratified Agent Constitution
> contracts without acquiring authority to ratify, authorize or activate a
> Constitution.

**Consistent; no implementation change.** `[V]` No compiler is implemented,
embedded or depended upon: `version_info().compiler_implemented` is `False`, no
`CompilationResult`-shaped type exists, and `tests/packaging/test_import_boundary.py`
forbids importing `ugence_policy_workflow_compiler` statically or dynamically.
`[V]` A constitution is constructed and validated directly through the contract
surface — `AgentConstitution(...)`, `.with_content_digest()`,
`validate_constitution(...)` — with no compilation step anywhere in the path, which
is what every test in `tests/contract/` exercises. `[V]` Nothing in AC-0 marks an
artifact as compiler-produced or requires it to be; provenance is recorded only as
`source_manifest_id` / `source_manifest_digest` / `source_manifest_author_id`.
`[V]` The constraint on a future compiler — that it may not acquire authority to
ratify, authorize or activate — is consistent with §9's position that AC-0 makes no
authority decision and confers none: `AgentConstitution.makes_authority_decision` is
a permanently `False` class constant, so no consumer inherits such a power from
these contracts.

### Decision 2 — Canonicalization

> `agent-constitution` SHALL be the canonical owner of the deterministic
> representation and fingerprinting rules for Agent Constitution contracts. AC-0
> SHALL NOT depend upon a future compiler for canonicalization. A future compiler or
> other consumer must use the published canonicalization contract owned by
> `agent-constitution`; it must not maintain an independently authoritative
> implementation. Temporary byte-equivalence testing may be retained only as a
> migration or compatibility ratchet and must not be described as establishing two
> equal sources of truth.

**Contradiction.** `[R]` §4 as originally written described this package's
canonicalization as "identical **by value**" to the compiler's, called the
comparison an *equivalence* gate, stated that "a future divergence in **either**
copy fails a gate", named the compiler's module `REFERENCE` in the test, and
proposed extracting a neutral third distribution that both packages would defer to.
Every one of those framings treats the two implementations as co-equal sources of
truth, which the ratified decision forbids. The behaviour was already correct — this
package has never depended on the compiler for canonicalization — but the described
ownership was wrong, and an ADR that describes the wrong ownership is the artifact a
future consumer would read before writing its own copy.

**Smallest change made.** `[V]` No canonicalization *logic* changed; canonical
output is byte-identical before and after, which the unchanged
`tests/serialization/test_canonical_json.py` and the pinned digest literal in
`tests/contract/test_fingerprint.py` both hold fixed. What changed is ownership
framing and the direction of the ratchet:

| File | Change |
|---|---|
| §4 of this ADR | Rewritten: this package owns canonicalization; the comparison is a one-directional migration ratchet; the neutral-third-package follow-up is superseded |
| `serialization/canonical_json.py` | Module docstring: authoritative definition, not a duplicate held equal to a reference |
| `tests/serialization/test_canonical_json_equivalence.py` | Renamed to `test_canonical_json_compatibility_ratchet.py`; `REFERENCE` → `LEGACY_CONSUMER_COPY`; assertions reworded so this package is the expected value and the consumer copy the observed one |
| `README.md`, `CHANGELOG.md`, `public_api.json` note | Same reframing, so no consumer-facing document still describes two equal implementations |

`[G]` Migrating the compiler onto this package's published contract, and retiring
the ratchet, is follow-up work outside AC-0 — it modifies another package.

### Decision 3 — Conformance Authority signing

> AC-0 SHALL NOT implement cryptographic signing, signature verification, key
> management, trust resolution or a Conformance Authority. AC-0 fingerprints
> establish deterministic content identity only and SHALL NOT be represented as
> signatures, ratification, authorization or proof of authority. A future signing
> capability must use an independently governed trust root and must not permit the
> Constitution package, compiler, proposer or conformance evaluator to approve its
> own output.

**Consistent; no implementation change.** `[V]` No signing, verification, key
management, trust resolution or authority surface exists:
`version_info().signing_implemented` is `False`,
`AgentConstitution.is_signed` is a permanently `False` class constant, and
`tests/packaging/test_import_boundary.py` names `cryptography`, `nacl`, `jwt` and
`jose` among the prohibited roots — AC-0 fingerprints content, it does not sign it.
`[V]` §5 already states that a fingerprint "attests to content identity only, never
to who produced it or whether they were entitled to", and `IssuerIdentity` is
documented at every occurrence as an unverified claim of provenance. `[V]` No
fingerprint is represented as ratification: `is_ratified` is a property of the
*type*, never derived from a digest, and a valid digest on a self-ratified
constitution still yields `INVALID` (§9). `[V]` The self-approval constraint on a
future signing capability is the same principle §9 already implements structurally
for ratification.

### Decision 4 — `packages/contracts/` tier

> `packages/contracts/` IS RATIFIED as the intended repository category for new
> packages whose primary responsibility is immutable cross-component contracts and
> deterministic contract validation. `packages/contracts/agent-constitution` SHALL
> remain in that tier. Existing contract-oriented packages located directly under
> `packages/` are legacy placement and SHALL NOT be moved as part of AC-0. This
> decision does not automatically require all future packages containing contracts
> to live in this tier; packages whose primary responsibility is an operational
> authority, runtime or capability remain in their appropriate category.

**Consistent; no implementation change.** `[V]` The package already sits at
`packages/contracts/agent-constitution` and is the tier's only occupant — AC-0
created the tier. Its primary responsibility is exactly the ratified criterion:
immutable cross-component contracts (§3) and deterministic contract validation
(§§6–7). `[V]` The legacy placements are `packages/governance-contracts` and
`packages/uvi-policy-contracts`, both directly under `packages/`. Neither is moved,
touched or referenced by AC-0, which modifies no package other than this one. `[V]`
No path anywhere in the package is hard-coded to the tier in a way that would
resist a future migration: the two tests that compute repository-relative paths do
so with `parents[N]` from their own location.

### Decision 5 — Credential Broker

> AC-0 SHALL NOT depend upon, invoke, emulate or issue artifacts on behalf of the
> Credential Broker. It SHALL NOT contain credentials, credential grants,
> broker-issued tokens or credential-release logic. Future Constitution versions may
> declare abstract capability, access or credential requirements through non-secret
> references, but satisfying those requirements and releasing credentials remain
> responsibilities of independently governed components outside AC-0.

**Consistent; no implementation change.** `[V]` Nothing in the package depends on,
invokes, emulates or issues on behalf of a Credential Broker; the name appears
nowhere in the source, and the import boundary permits only `pydantic` and the
standard library. `[V]` No model carries a credential, grant, token or release
path. The nearest surface is `CapabilityRegistryEntryRef`, which is exactly the
"non-secret reference" the decision contemplates: a registry namespace, an entry
identifier, an entry version and a content digest — four opaque, non-secret fields
that this package pins but never resolves. `[V]` Satisfying a requirement is
explicitly nobody's job here: a `MANDATORY` requirement that pins no resolvable
entry yields `INDETERMINATE` rather than any attempt to obtain what it names (§6),
and `ConformanceSubject.conformance_evaluated` is a permanently `False` class
constant.

---

## 11. Open design questions — `[G]` generated, unratified

`[G]` **These are not owner decisions and were never ratified.** They were derived
during recovery of the missing decision register, at a point when the decision
*subjects* were unknown, by inspecting where the implementation had to commit to a
rule the repository cannot settle. Four of them were mistaken at the time for the
owner decisions; they are not. The actual owner decisions are at §10, and these are
recorded here — deliberately outside §10 — only so the analysis is not lost and is
not re-derived and re-mistaken later.

Each is a real open question. None blocks AC-0, and the current behaviour of each is
already gated by tests and by a negative control that fails if the invariant is
inverted.

| Question | Current behaviour | Anchor |
|---|---|---|
| Should self-ratification be refused at all, permitted-and-recorded, or left wholly to a later authority layer? | Refused: `AC_SELF_RATIFICATION`, `INVALID` | §9; `semantic_validation.py` |
| May a constitution state a `MANDATORY` requirement pinning no resolvable registry entry? | `INDETERMINATE`, not usable | §6; `AC_REQUIREMENT_UNRESOLVABLE` |
| Should a mandatory field with surrounding whitespace be refused, normalized, or accepted as written? | `INDETERMINATE`: neither stripped silently nor accepted | §6; `AC_MANDATORY_FIELD_AMBIGUOUS` |
| Should an unknown field be refused, preserved-and-digested, or dropped? | Refused: `extra="forbid"` | §3; `models/common.py` |

`[G]` Three further questions are lower-stakes and cheaply reversible, because none
changes which stored artifact validates: pre-release / build-metadata version
ordering (§8, currently refused rather than ordered), an absent `content_digest` as
`INDETERMINATE` rather than `INVALID` (§5), and whether a no-op successor reusing
its predecessor's digest is refused (§8).

`[R]` Any of these becoming a ratified rule requires an owner decision recorded at
§10, not an edit here.

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

`[V]` Deterministic and offline. 223 tests pass in this build (222 at `a261e28b`, plus one added with the decision-2 reconciliation), including negative
controls that assert each invariant test fails when its invariant is inverted, and
two meta-controls demonstrating that an always-accept and an always-refuse checker
would both be caught by the control table.

`[V]` **Not** pilot-validated. **Not** production-certified. No claim is made about
behaviour under any workload, and no artifact defined here has been exercised by any
consumer — AC-0 has none by design.
