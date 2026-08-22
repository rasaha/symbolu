# Changelog — ugence-benchmark-registry-authority

All notable changes to this distribution. The format follows Keep a Changelog;
versioning is Semantic Versioning, and the version ladder is the ratified one:
BR-2A `0.1.0`, BR-2B `0.2.0`, **BR-2C-0 `0.2.1`, `0.2.2` and `0.2.3`**, BR-2C
`0.3.0`, BR-2D `0.4.0`, BR-2E `0.5.0` (ADR §35 D-01, amended 2026-08-20, and
D-33 and D-36). Five of the six rungs are subphases; `BR-2C-0` is a **version
rung**, carries three versions, and mints no closure audit.

## [Unreleased] — BR-2C-0 closure: shipped-text corrections, and D-36

**No version bump.** `package_version` stays `0.2.3`. This entry moves no
**pinned surface count**, no digest domain, no pinned canonical vector, no
refusal member, no capability token and no contract type. It is prose correction
under D-30 and D-31's standing precedent, plus one ratification and the tests
that pin it. The **suite count and the property ratio do move** — five tests were
added — and both are re-stated from fresh runs below.

### Ratified — D-36: the `BR-2C-0` rung carries all three versions

`tests/_milestones.py`'s `VERSION_SUBPHASE` maps `0.2.1`, `0.2.2` and `0.2.3` to
`BR-2C-0`, but D-33 ruled only `"0.2.1"` and neither D-34's nor D-35's *Surfaces
moved* clause named a version bump. **D-36 rules the map that was already there**:
one rung, three versions. D-18 requires a version bump at each surface-count move
and both later rows moved `api.__all__` by one, so each needed a version of its
own; the rung names *what* a version ships, not how many times it shipped, and
all three ship BR-2C's contract surface and no BR-2C capability, so all three
ban the same twelve tokens. A rung per version would be an index that rules
nothing; folding the three back onto `0.2.1` would restore the
two-surfaces-one-version defect D-33 exists to end.

The gap was a **missing ratification, not a wrong mapping**, and it was never a
silent one: every consumer reads `VERSION_SUBPHASE[api.__version__]` by exact
string, so an unmapped version raises `KeyError` and fails closed rather than
widening a ban set. The `0.2.3` entry below states that nothing is left open by
it; that was true of D-33, D-34 and D-35's rulings and **not** of the rung's
version mapping, which this entry closes.

### Fixed — five shipped-text defects an independent closure audit found

- **`README.md` refusal counts.** `BenchmarkRegistryRefusalReason` holds
  **twenty-four** BR-2 reasons, not seventeen, and
  `BENCHMARK_REGISTRY_ALL_REFUSAL_REASONS` is **41** members, not 34 — the
  counts D-27 and D-28 moved and whose gates already pinned. BR-1's own frozen
  seventeen is unchanged and stays where it stood.
- **`README.md` measured-results table, re-run and re-stated, never edited.**
  Every figure below was produced by executing the named check against this tree.
- **Three headline milestone labels, BR-2B → BR-2C-0**, on D-30's precedent for
  a label that was true at the previous rung: the module docstring titles at
  `src/ugence_benchmark_registry_authority/api.py:1` and
  `src/ugence_benchmark_registry_authority/__init__.py:1`, and `pyproject.toml`'s
  `description`, which ships as the distribution **Summary**.
- **Those same three curated-surface descriptions now name what `0.2.2` and
  `0.2.3` added**: `BenchmarkTrustAnchorResolution` (D-34) and
  `BENCHMARK_VERIFICATION_REFUSAL_REASONS` (D-35). The surface moved two
  releases ago; the descriptions of it had not.
- **Two stale labels.** `__init__.py`'s `0.2.3` bullet read `api.__all__` 93 →
  **106**, which is `0.2.1`'s figure; across the rung's three versions it is 93 →
  **108**. `tests/test_adversarial_ratio.py` printed its ratio under a **BR-2B**
  heading. `version.py`'s per-version breakdown — 93 → 106 → 107 → 108 — was
  already correct and is unchanged.

**No generator literal moved**, so no manifest was regenerated, and none was
hand-edited. `tools/generate_manifests.py` and `gate_mutation_sweep.py` already
write `"milestone": "BR-2C-0"`.

### Fixed — the closure remainder, found auditing the pass above

- **`verify_benchmark_registry_authority_distribution.py:2`** still headlined
  "the BR-2B distribution" while its sibling `adversarial_probes.py:1` already
  read `BR-2C-0`. Corrected to match.
- **The same file's "six controls §20 specifies"** is **withdrawn**. ADR §20 is
  the *Readiness integration boundary (future posture, not implemented)* and
  specifies no negative control at all, so the citation ruled nothing. The
  six/eight relation is now stated outright instead: the script's own scheme
  numbers **six** isolation properties, and runs and reports **eight** controls,
  because control 6 splits into 6a (source shadowing) and 6b (a leaked
  `PYTHONPATH`) and step 8's dependency-really-required control carries no
  number. The summary counts runs, so it reads eight. No control was added,
  removed or renumbered.
- **D-36's *Surfaces moved* clause is discharged rather than left open** — the
  defect D-33's own enumeration was faulted for. Its citation now appears at
  `README.md`'s `BR-2C-0` milestone row, at `version.py`'s ladder docstring, and
  at `tests/_milestones.py`'s `VERSION_SUBPHASE` docstring, where the inferred
  "a second rung would be a second claim about capability, and D-34 makes none"
  is replaced by D-36 as the ruling.

### Fixed — one false clause struck from ADR §35.2 D-36

D-36 closed the rung-per-version option partly on "D-01's five subphases would
be outnumbered by rungs carrying no ruling". That is **false**: a rung per
version leaves five subphases against three rungs. The clause is struck. The
row's substantive ground is verified and stands alone — the extra ladder indices
produce ban sets identical to `BR-2C-0`'s, so they rule nothing. **The ruling is
unchanged**; only its reasoning is narrower.

### Added — one check, pinning D-36's ground instead of asserting it

D-36 closes the rung-per-version option because the extra ladder indices would
produce ban sets identical to `BR-2C-0`'s. That was a **derivation** from
`banned_capability_tokens` comparing by index — true, and enforced nowhere. Three
tests in `tests/packaging/test_milestone_boundary.py` now pin it:

- **`test_no_token_unlocks_at_the_br2c_0_rung_itself`** — the precondition the
  ground rests on. Every unlock in both maps is `BR-2C`, `BR-2D` or permanent. A
  token naming `BR-2C-0` would be shippable at one of the three versions and not
  the others, the split rungs would stop being interchangeable, and D-36's ground
  would be false with nothing saying so. This is the check that fails instead.
- **`test_splitting_the_br2c_0_rung_per_version_changes_no_ban_set`** — builds
  the ladder D-36 rejected and compares ban sets against the real one, at the
  three split rungs and at `BR-2C`, `BR-2D` and `BR-2E`. Measured on **both**
  unlock maps, since D-33 records that `0.3.0` unlocks twelve tokens across the
  two, not eight across one.
- **`test_the_hypothetical_ladder_is_never_the_real_one`** — a guard on the
  guard, so the rejected ladder cannot quietly become the shipped one.

**No ban set is weakened or restated.** The checks assert equality against the
live ban set rather than a copied literal, so a **one-sided** shrink fails
`test_the_effective_ban_set_is_exactly_what_br2a_froze` first. A two-sided edit
does not — see the self-attestation note below, which is the honest limit of
that guarantee. Both negative controls were exercised: injecting a token that
unlocks at `BR-2C-0` into either map fails the precondition check by name.

**This moves the suite count**, which every earlier commit in this closure had
held fixed: 2108 → 2111 here, and → **2113** with the audit remediation below;
distinct properties 503 : 38 → **508 : 38**. Every figure is re-stated below and
in `README.md` from a fresh run, never by arithmetic. The `[0.2.3]` table further
down does **not** move with them: it records what that release shipped, and later
work is carried here.

### Fixed — what two independent audits found in the check above

The pinning check was audited by two independent sessions. Both reproduced every
figure; between them they found four defects, three of them introduced by this
closure.

- **`README.md` claimed an enforcement that does not exist.** It read "a stale
  figure fails a check rather than surviving an edit". **Nothing in this
  repository reads `README.md` or `CHANGELOG.md`** — the only document any check
  parses is BR-1's own README, for pinned digests. The sentence was false, and it
  was written by the closure pass whose whole purpose is correcting shipped text.
  Replaced with what is actually true: the figures are attested by the run
  recorded in the commit that states them, and by the discipline of re-running
  rather than editing, which is weaker than a gate.
- **The check measured a copy of the predicate, not the predicate.** The local
  `_banned_on` helper duplicated `banned_capability_tokens` with the ladder
  parameterised, so both sides of the comparison came from the copy and it could
  drift — `>` to `>=` — with the suite green. `banned_capability_tokens` now
  takes an explicit `ladder` argument and `_banned_on` is **deleted**, so the
  fork cannot reappear.
- **D-36's *ruling* was unpinned, only its ground was.** Re-mapping `0.2.2` to
  `BR-2B` left the suite green: the fail-closed `KeyError` the row relies on
  catches an *unmapped* version, never a *mis*-mapped one, and only once that
  version is live. `test_the_rung_carries_exactly_the_three_versions_d36_ruled`
  asserts the mapping itself.
- **The `reached` boundary the whole ladder turns on was never exercised.** Every
  check ran at rungs where no token unlocks, so drifting `>` to `>=` — keeping
  every capability banned one rung too long — stayed invisible even after the
  fork was removed. `test_a_token_is_banned_below_its_unlock_rung_and_not_at_it`
  pins it on both surfaces. **This gap is older than the D-36 check.**

Every one of these is mutation-proved: mis-mapping `0.2.1` or `0.2.2`, drifting
the predicate to `>=`, and injecting a token that unlocks at `BR-2C-0` into
either map were each green before and are each red now.

Two stale ADR citations are corrected, both verified against the files rather
than trusted: D-36's fourth `VERSION_SUBPHASE[api.__version__]` site is
`tests/packaging/test_milestone_boundary.py:690` — it was cited as `:522`, which
this closure's own insertions moved twice — and D-33's `tests/_milestones.py:16`
and `:21-27` are `:28` and `:49-58`, stale since `ab199013`.

**The `[0.2.3]` table is reverted** to its release-time `2108`. The argument for
tracking it live proved too much: it would oblige every future no-bump commit to
re-edit a version-tagged section, which is what `[Unreleased]` exists to prevent.
Both tables are now dated instead, so two different suite counts in one file read
as scoped rather than contradictory.

### Fixed — what a third audit found, including in the correction itself

- **The replacement enforcement prose was still false**, in a second way the
  first rewrite did not consider. It said *no* test, probe, verifier, sweep or
  generator reads this file. `pyproject.toml` sets `readme = "README.md"`, so
  setuptools embeds the **whole** README — that very paragraph, and the results
  table — in the built distribution's `METADATA`, and the offline distribution
  verifier substring-scans that blob for banned cryptographic dependency names.
  Prose in the README can therefore turn a distribution check red. The narrow
  claim survives — nothing checks these *figures* — and the broad one is
  withdrawn.

  **The first attempt at this correction broke the build check.** Naming the
  banned strings in the README to explain the scan put them into `METADATA` and
  failed the verifier. That is why the rewrite names none of them, and why it was
  validated by building metadata and asserting each of the paragraph's own claims
  against it rather than by reasoning about what the build would do.

- **The capability vocabulary is self-attested, and the docstring said
  otherwise.** `BR2A_FROZEN_CAPABILITY_TOKENS` claimed to be "pinned separately
  from the map above so a restructuring cannot drop an entry unnoticed". True of
  a one-sided edit only: both literals live in one file, so removing a token from
  each leaves the suite green — measured, by deleting `"keyparser"` and
  `"key_parser"` from both and shipping a live `class KeyParser` with a working
  `parse()` under `src/`, which passed at 2113. A capability the ADR bans until
  `0.3.0` would ship with nothing saying so. **No second authority for these
  tokens exists in this repository**: the probe harness carries none, the gate
  inventory carries none, and ADR §35.2 names them only in prose. Pinning them to
  one needs its own ratification, so the docstring now states the limit instead of
  overstating the guard. **No ban was weakened and no token added.**

- **The D-33 citation fix was half-executed.** The ruling sentence was corrected
  to `tests/_milestones.py:28` and `:49-58`; the *Surfaces moved* clause in the
  same row still read `:16` and `:21-27`. It now names the symbols —
  `SUBPHASE_LADDER` and `VERSION_SUBPHASE` — with the lines verified against the
  file.

- **§35.2 now records once that in-row line citations are frozen at
  ratification** rather than correcting them one at a time. D-30's enumeration
  alone carries six that no longer resolve, and three further citations went stale
  *during* this closure, two moved by its own insertions. A governance record
  cannot track line numbers it does not own, so the rule is stated for D-01
  through D-36: file paths and symbol names are live and corrected when wrong,
  line numbers are historical. D-33 and D-36 are named exceptions, re-verified.

- **Both scope lines are re-worded to survive the next version bump.**
  "As measured now, against this tree" and `[0.2.3]`'s pointer at `[Unreleased]`
  both go false when that section is renamed at release. `[0.2.2]` and `[0.2.1]`
  stay unlabelled: nothing invites reading them as live.

### Measured verification

**As measured after this entry's changes** — not carried forward, and not the
as-shipped figures of any released section below. Where this file shows two
different suite counts, they are scoped to different points in the history rather
than contradicting each other:

| Check | Result |
| --- | --- |
| Package suite | **2113 passed** |
| Independent adversarial probes | **83 passed** (also inside the installed wheel) |
| Distinct properties | **508 adversarial : 38 happy = 13.37 : 1** (required ≥ 2:1) |
| Gate mutation sweep | **72 inventoried, 67 KILLED, 5 SURVIVED, 0 errored** |
| Offline distribution verifier | **VERIFIED**, 8 negative controls run, 8 caught |
| pyflakes | clean |
| BR-1 freeze matrix | **VERIFIED** |

All five survivors are the pre-existing classified ones — four **shadowed**, one
**equivalent** while BR-1 is frozen. This pass introduced none, and changed no
production behaviour to reduce the number. **This is author-owned assurance**, on
the base rate D-32(5) records and accepts for BR-2C.

### What this entry does not do

**No BR-2C verifier engineering has begun**, and D-32(3) leaves the engineering
half of §35.1's blocker standing in full. Until an external cryptographic audit
is obtained and recorded, no artifact of this distribution may describe the
verifier as audited, independently reviewed or production-ready — and none does.

## [0.2.3] — which refusals a verified result may carry (D-35)

**Contracts only. No verifier ships, and the verifier these contracts describe
has not been audited and is not production-ready.** D-32 requires that statement
to stand until an external cryptographic audit of the BR-2C verifier is obtained
and recorded, and makes that audit a **hard precondition to any production use**.
It waives the *distinct in-repo reviewer* for BR-2C only; the **engineering half**
of §35.1's blocker is untouched, so the audited verifier, the composition-root
trust-resolver design and the key parser are **not begun**.

`0.2.1` recorded, and `0.2.2` carried forward, that which refusal members a
verified result may carry was "unconstrained beyond membership of the BR-2
vocabulary". **D-35 rules the subset. This is the last of the three items the
BR-2C contract slice left open.**

### Changed — a REFUSED result carries twelve of the twenty-four

- **`_require_outcome_and_reason_agree`** (`contracts/trust.py`) narrows from
  membership of `BenchmarkRegistryRefusalReason` to membership of
  `BENCHMARK_VERIFICATION_REFUSAL_REASONS`. Before this, a verified result could
  refuse with `COORDINATE_SLOT_CONFLICT`, `STORE_UNAVAILABLE` or `NOT_FOUND`.
  The biconditional's other half is unchanged: `VERIFIED` still carries no
  reason, `REFUSED` still carries exactly one, and both other combinations stay
  unconstructible.

### Added — one specification constant, derived and not written out

- **`BENCHMARK_VERIFICATION_REFUSAL_REASONS`** — the eleven members classified
  `TRUST_AND_AUTHENTICITY`, **plus `INDETERMINATE`**. Twelve admissible; twelve
  excluded. Published on the model of `BENCHMARK_TRUST_ANCHOR_EVALUATION_ORDER`,
  for the same reason: the contract published today is the contract verified
  later, and a verifier that had to reinterpret it could reinterpret it
  differently.
- **Derived from the fault-class map, never enumerated.** §35.6 makes the
  vocabulary append-only, and a hand-copied list of twelve would need re-editing
  by hand on every appended member — the drift D-35 closed the subtractive
  option to avoid. Deriving means the next member classifies itself in or out,
  and D-27 and D-28 already require the classification to be **total**, so the
  derivation can miss none. A test and a probe both recompute it from the map,
  so a literal that had since drifted would fail rather than pass quietly.
- **Declaration order is preserved** — the enum is iterated, not a set — so a
  consumer sorting by index under §22.13 reads the order this vocabulary has
  everywhere else.

### `INDETERMINATE` joins, ruled explicitly rather than read off the map

It is its **own** fault class, not a trust one, so the class alone would have
excluded it. §35.9's Q-2C-5 records that a resolver becoming unreachable in
flight refuses through `INDETERMINATE` and so fails closed, which makes it a live
verification-time answer. A subset with no fail-closed catch-all would force an
undeterminable condition into a specific trust claim, or into no representable
answer at all.

### What is excluded, and on which ground

**Nine are registry-state facts** a subphase §35.1 forbids to ship "any storage,
and any registry state whatsoever" cannot establish: `IDEMPOTENT_DUPLICATE`,
`COORDINATE_SLOT_CONFLICT`, `DIGEST_ALREADY_BOUND`, `CONFUSABLE_COORDINATE`,
`LIFECYCLE_CONFLICT`, `UNAUTHORIZED_TRANSITION`, `STALE_REGISTRY_SNAPSHOT`,
`STORE_INTEGRITY_INVALID` and `STORE_UNAVAILABLE`.

**`UNSUPPORTED_SUPERSESSION`** is D-10's out-of-scope refusal; BR-2 infers no
supersession at any phase.

**`NOT_FOUND` and `NOT_ADMITTED`** are `READ_NON_DISCLOSURE`, and D-27
deliberately places the non-disclosure collapse at a later **external read
boundary** rather than in the verification result — admitting the read
vocabulary here would invert D-27.

The four anchor-lifecycle refusals **stay admissible**: this is the seam that
evaluates them, on D-28's published order. D-34's two resolution refusals are
among the twelve, so a refusal survives the handoff from the resolution seam to
the verification seam intact.

### Measured surface movement

| Manifest | Before | After |
| --- | --- | --- |
| `api.__all__` | 107 | **108** |
| `public_api.json` symbols | 106 | **107** |
| public-contract inventory rows | 22 | **22** |
| canonical domains / pinned vectors | 22 | **22** |
| BR-2 refusal vocabulary | 24 | **24** |
| combined BR-1/BR-2 list | 41 | **41** |

Regenerated with `tools/generate_manifests.py`, never hand-edited. A constant is
not a contract type, so nothing is sealed and the three sealed manifests do not
move. **No refusal member is added, removed, renamed, re-valued or re-ordered** —
this row narrows a constructor — so §35.6's append-only guarantee is untouched
and the composite indices stay 17..40.

### `package_version` moves to `0.2.3`, on the rung D-33 minted

Same rung, third version. `VERSION_SUBPHASE` maps `0.2.1`, `0.2.2` **and**
`0.2.3` to `BR-2C-0`: the rung names what a version ships rather than how many
times it shipped, so all three ban the same twelve capability tokens. `0.3.0`
stays the audited verifier.

Every milestone-label site D-33's amended row enumerates moved with the version,
including the two version pins **and** the independent `api.__all__` count the
offline distribution verifier re-derives — a site the row did not name until
this release added it.

### Measured verification

**As shipped at `0.2.3`.** These are the figures the release measured, and they
stay put: a version-tagged section records what that version shipped, so later
work is carried by the newer sections above rather than by re-editing this table.
The suite has since moved — the newest section above carries the current
figures.

| Check | Result |
| --- | --- |
| Package suite | **2108 passed** |
| Independent adversarial probes | **83 passed** (also inside the installed wheel) |
| Gate mutation sweep | **72 inventoried, 67 KILLED, 5 SURVIVED, 0 errored** |
| Offline distribution verifier | **VERIFIED**, 8 negative controls run, 8 caught |
| pyflakes | clean |
| BR-1 freeze matrix | **VERIFIED** |

**G-77**, the narrowed membership gate, is inventoried rather than left uncounted,
and is KILLED. All five survivors are the pre-existing classified ones; this
release introduced none. **This is author-owned assurance**, on the base rate
D-32(5) records and accepts for BR-2C.

### Nothing is left open by this entry

D-33, D-34 and D-35 are all implemented. What stands is the **engineering half**
of §35.1's BR-2C blocker, untouched by any of them: a secure verifier and a
composition-root trust-resolver design, externally audited, reusing neither the
Policy Authority nor the Risk Authority Ed25519 implementation. **No BR-2C
verifier engineering has begun**, and until that external audit is obtained and
recorded, no artifact of this distribution may describe the verifier as audited,
independently reviewed or production-ready.

## [0.2.2] — the anchor-resolution outcome (D-34)

**Contracts only, again. No verifier ships, and the verifier these contracts
describe has not been audited and is not production-ready.** D-32 requires that
statement to stand until an external cryptographic audit of the BR-2C verifier is
obtained and recorded, and makes that audit a **hard precondition to any
production use**. D-32 waives the *distinct in-repo reviewer* for BR-2C only; the
**engineering half** of §35.1's blocker is untouched here, so the audited
verifier, the composition-root trust-resolver design and the key parser are
**not begun**.

`0.2.1` recorded, under "left open here, since ruled", that `resolve_anchor`
returned `Optional[BenchmarkTrustAnchorRecord]` and that a `None` could not
distinguish `TRUST_ANCHOR_NOT_FOUND` from `TRUST_DIRECTORY_UNAVAILABLE`. **D-34
rules the remedy and this release is that remedy and nothing beyond it.**

### Changed — the seam returns a resolution, not an optional record

- **`BenchmarkPublisherTrustDirectoryPort.resolve_anchor`** (`contracts/ports.py`)
  returns `BenchmarkTrustAnchorResolution` instead of
  `Optional[BenchmarkTrustAnchorRecord]`. It still performs **no lifecycle
  evaluation** and still takes **no trusted instant**: revoked, disabled,
  not-yet-valid and expired remain the verification seam's to decide against
  D-28's published order, and a resolver that filtered on the instant would
  collapse all four into the one indistinguishable absence D-27 requires stay
  distinguishable. The port remains an inert `Protocol` that nothing in this
  package satisfies, asserted structurally.

### Added — one contract type, and no manifest that carries a digest

- **`BenchmarkTrustAnchorResolution`** — frozen, binding the exact
  `(role, identity, key_id)` triple the lookup asked and carrying **exactly one**
  of an anchor record or a typed refusal reason. Both the "resolved and refused"
  and the "neither" states are **unconstructible**, enforced in `__post_init__`,
  and there is **no Boolean success flag**: a caller branches on which half is
  present. A record answered at a different role, identity or key than the one
  asked is refused — a resolver may not answer a question it was not asked, and
  D-26 makes the role part of the question rather than something a shared
  physical directory may infer.
- **The only two admissible refusals are `TRUST_ANCHOR_NOT_FOUND` and
  `TRUST_DIRECTORY_UNAVAILABLE`** — the two conditions in which no record exists
  to return. D-28 rules the second fails closed with **never** a fallback to a
  cached, default or previously successful answer, and an unreachable directory
  reading as *no such anchor* is exactly such a substituted default. Every other
  member of the 24 is refused at construction, the four lifecycle refusals
  included. A third member would be a ratification, not an implementation choice.

### Not added, deliberately

- **No digest domain, no pinned vector and no contract-inventory row.** The type
  is exported but **not registered as root-canonicalizable** in
  `contracts/_seal.py`, so the encoder refuses to render it. §05 forbids byte
  space an artifact does not need, and D-25 rules the anchor record's own
  canonical digest **is** the anchor revision — a second digest over the
  resolution carrying that record would be a competing identity for one fact, the
  parallel revision D-25 refuses. Asserted in all four registers rather than
  assumed, since "it is absent" is what a later regeneration could quietly
  falsify.
- **No second exported symbol.** The admissible-refusal tuple stays
  module-private: D-34's *Surfaces moved* clause ratifies one new type and no
  second symbol, and D-18 keeps the curated surface a thing that moves by
  ratification. The constructor enforces the membership and its refusal names
  both members.
- **No `resolved()` / `refused()` classmethod factories**, unlike the
  trusted-evidence precedent this shape is copied from: §17 forbids a convenience
  resolver, and a classmethod named `resolved` on an exported type in a package
  whose exported-function ban lists `resolve` is a name no contract needs.
- **No field defaults on either half of the exclusive-or**, so the unset half is
  written at every call site rather than defaulted into silence — the rule
  `BenchmarkTrustAnchorRecord.revoked_at` already follows.

### Copied, never imported

The record-XOR-refusal shape is the trusted-evidence layer's
`TrustAnchorResolution`. It is **copied and not imported**:
`ugence_trusted_evidence_authority` is the first entry on this package's
forbidden-import list, §23 restricts BR-2 to `governance-contracts`, D-04's
fourth constraint forbids importing that layer's trust-anchor directory, and
**D-22(4) is the ratified precedent for copying a shape and not the code**. The
dependency list is unchanged and no cryptographic library is linked.

### Measured surface movement

| Manifest | Before | After |
| --- | --- | --- |
| `api.__all__` | 106 | **107** |
| `public_api.json` symbols | 105 | **106** |
| public-contract inventory rows | 22 | **22** |
| canonical domains / pinned vectors | 22 | **22** |
| BR-2 refusal vocabulary | 24 | **24** |
| combined BR-1/BR-2 list | 41 | **41** |

Regenerated with `tools/generate_manifests.py`, never hand-edited. **No refusal
member is added, removed, renamed, re-valued or re-ordered** — both reasons this
release admits already existed under D-27 and D-28 — so §35.6's append-only
guarantee is untouched.

### `package_version` moves to `0.2.2`, on the rung D-33 already minted

Same rung, second version. `VERSION_SUBPHASE` maps **both** `0.2.1` and `0.2.2`
to `BR-2C-0`, because the rung names what a version ships rather than how many
times it shipped: both are BR-2C's contract surface with no BR-2C capability, so
both must ban the same twelve tokens. A second rung would be a second claim about
capability, and D-34 makes none. `0.3.0` stays the audited verifier.

Every milestone-label site D-33's amended row enumerates moved with the version:
`version.py`, `tests/_milestones.py`, the two version literals, the two pins at
`verify_benchmark_registry_authority_distribution.py:157-158`, the `milestone`
literals written into `public_contract_inventory.json` and `gate_inventory.json`
by their generators, `pyproject.toml`, `README.md`, `api.py` and the package
docstring's own milestone-boundary list.

### Measured verification

| Check | Result |
| --- | --- |
| Package suite | **2013 passed** |
| Independent adversarial probes | **79 passed** (also inside the installed wheel) |
| Gate mutation sweep | **71 inventoried, 66 KILLED, 5 SURVIVED, 0 errored** |
| Offline distribution verifier | **VERIFIED**, 8 negative controls run, 8 caught |
| pyflakes | clean |
| BR-1 freeze matrix | **VERIFIED** |

The sweep grew by three: **G-74** (the record-XOR-refusal gate), **G-75** (the
admissible-refusal membership gate) and **G-76** (the asked-versus-answered
triple gate) are inventoried rather than left uncounted, and all three are
KILLED. All five survivors are the pre-existing classified ones; this release
introduced none. **This is author-owned assurance**, on the base rate D-32(5) records and
accepts for BR-2C.

### Still left open here, since ruled

- **Which refusal members a verified result may carry.** **Ruled by D-35**: the
  eleven-member `TRUST_AND_AUTHENTICITY` fault class plus `INDETERMINATE`, twelve
  of the twenty-four. `contracts/trust.py`'s biconditional still admits all 24.
  **Not implemented here; shipped in `0.2.3`.**

## [0.2.1] — BR-2C contract surface (D-24, D-25, D-32, D-33)

**Contracts only. No verifier ships, and the verifier these contracts describe
has not been audited and is not production-ready.**

ADR §35.2 D-32 requires that statement to stand until an external cryptographic
audit of the BR-2C verifier is obtained and recorded, and forbids any artifact
of this distribution — this CHANGELOG included — from describing the verifier as
audited, independently reviewed or production-ready before then. That audit is a
**hard precondition to any production use** of it. D-32 waives the *distinct
in-repo reviewer* for BR-2C only, and nothing else: the **engineering half** of
§35.1's blocker stands untouched, so the audited verifier, the composition-root
trust-resolver design and the key parser are **not begun here**.

D-23 classifies BR-2C as blocked on unratified governance *and* audited
engineering, independently. D-24, D-25 and D-26 clear the governance half by
ruling the contract change; this entry is that change and nothing beyond it.

### Changed — the two `bool` seams are replaced

- **`BenchmarkApprovalVerifierPort`** (`contracts/ports.py`) — both methods
  return exact types instead of `bool`, and D-26 adds a third seam,
  `verify_revocation`. Each takes the **explicit trusted instant** as an
  argument: D-28 records that BR-2C ships no clock, so the instant is an *input*
  to verification and never a clock read. D-11 is unamended and the
  authoritative clock still arrives at BR-2D.
- **`BenchmarkPublisherTrustDirectoryPort.is_entitled` → `.resolve_anchor`** —
  Boolean entitlement is replaced by exact anchor resolution (D-25), role-scoped
  in its parameters (D-26). It performs **no lifecycle evaluation**: a resolver
  that filtered on the trusted instant would collapse revoked, disabled,
  not-yet-valid and expired into one indistinguishable absence, which is what
  D-27 requires stay distinguishable.
- Both ports remain **inert `Protocol` declarations exactly as BR-2A shipped
  them**. Nothing in this package satisfies either, asserted structurally.

### Added — four contract types, three enums, seven refusals

- **`BenchmarkTrustAnchorRecord`** (D-25) — the immutable role-scoped anchor the
  resolution seam returns, binding role, identity, key identifier, profile,
  public-key material, validity interval, status and revocation facts. **The
  anchor revision is this record's canonical digest**; no parallel revision
  counter is minted. Key material is validated as a 64-hex-character *encoding*
  and never decoded — this package still parses no key material and links no
  cryptographic library.
- **`BenchmarkPublisherVerifiedResult`, `BenchmarkApprovalVerifiedResult`,
  `BenchmarkRevocationVerifiedResult`** (D-24, D-26) — three **distinct exact
  types**, each pinning its own role and owning its own digest domain, each
  binding D-24's nine facts. A result establishes **cryptographic verification
  only — never admission, never registration, never trusted resolution**: all
  five of §09's authority derivations stay permanently `False`, including on a
  result reading `outcome=VERIFIED`.
- **`BenchmarkTrustRole`, `BenchmarkTrustAnchorStatus`,
  `BenchmarkVerificationOutcome`** — closed vocabularies. The verification
  outcome is deliberately *not* `BenchmarkAdmissionOutcome`: spelling a
  verification answer in the admission vocabulary is the confusion D-24 forbids.
  The in-force anchor status is `ENABLED`, not `ACTIVE`, because `ACTIVE` is a
  banned floating lifecycle name under D-08.
- **Seven refusal members, appended and never inserted** (§35.6) —
  `TRUST_ANCHOR_NOT_FOUND`, `TRUST_ANCHOR_REVOKED`, `TRUST_ANCHOR_DISABLED`,
  `TRUST_ANCHOR_NOT_YET_VALID`, `TRUST_ANCHOR_EXPIRED` (D-27's five, role-neutral)
  and `TRUST_DIRECTORY_UNAVAILABLE`, `STALE_TRUST_SNAPSHOT` (D-28's two).
  Each is classified `TRUST_AND_AUTHENTICITY`; the classification is total.
- `BENCHMARK_TRUST_ANCHOR_EVALUATION_ORDER` publishes D-28's ratified order —
  revoked, disabled, not yet valid, expired — as a **specification constant**.
  Nothing here evaluates it.

### Measured surface movement

Every number below was **measured after regenerating the manifests with
`tools/generate_manifests.py`**, never predicted and never hand-edited.

| Manifest | Before | After |
| --- | --- | --- |
| `api.__all__` | 93 | **106** |
| `public_api.json` symbols | 92 | **105** |
| public-contract inventory rows | 18 | **22** |
| canonical domains / pinned vectors | 18 | **22** |
| BR-2 refusal vocabulary | 17 | **24** |
| combined BR-1/BR-2 list | 34 | **41** |

BR-2's members now occupy composite indices 17..40; BR-1's frozen seventeen are
untouched in value, order and index.

### Measured verification

| Check | Result |
| --- | --- |
| Package suite | **1970 passed** |
| Independent adversarial probes | **74 passed** (also inside the installed wheel) |
| Distinct properties | **471 adversarial : 35 happy = 13.46 : 1** |
| Gate mutation sweep | **68 inventoried, 63 KILLED, 5 SURVIVED, 0 errored** |
| Offline distribution verifier | **VERIFIED**, 8 negative controls run, 8 caught |
| pyflakes | clean |
| BR-1 freeze matrix | **VERIFIED** |

All five survivors are the pre-existing classified ones; the slice introduced
none. **Every row above was re-run at the `0.2.1` rung and is unchanged**, with
the offline distribution verifier re-pinned to the moved version and returning
VERIFIED, and the gate ledger regenerated rather than hand-edited.
**This is author-owned assurance.** D-32(5) records the cost it accepts:
three closure audits across BR-2B found seven defects, none in the boundary and
every one in a rule asserting it, and that is the measured base rate this
waiver accepts for BR-2C.

### `package_version` moves to `0.2.1`, on a rung minted for the purpose (D-33)

The BR-2C contract slice moved this distribution's curated surface —
`api.__all__` 93 → 106, `public_api.json` 92 → 105 — at an unchanged `0.2.0`.
D-18 rules those counts are milestone-scoped snapshots that move **deliberately
at each version bump**, so leaving the version alone left two different surfaces
wearing one version. That was recorded here as an owner decision and is now
taken: **D-33 mints `BR-2C-0` at `0.2.1`**, inserted at index 2 of
`tests/_milestones.py`'s ladder between `BR-2B` and `BR-2C`, meaning *BR-2C's
contract surface landed; no BR-2C capability did*.

It is a **version rung, not a subphase.** D-01's five separately auditable
subphases are unamended, §35.1's five-row table is unamended, and the rung mints
no closure audit: BR-2C still closes at `0.3.0`, on D-32's terms and its
external cryptographic audit.

**`0.3.0` was not available, and it unlocks twelve capability tokens, not
eight.** §35.1 defines `0.3.0` as the *audited verifier*, which this release
does not ship and D-32(4) forbids describing as audited. Mapping this
distribution to **BR-2C** would unlock the eight at
`tests/packaging/test_milestone_boundary.py:44-51` — `signature_verifier`,
`key_parser`, `trust_anchor_store`, `approval_verifier` and their unseparated
spellings — **and four more** from the exported-symbol table at
`tests/contract/test_confusable_and_ports.py:50-53`: `denyall`, `deny_all`,
`verifier` and `trust_store`. The earlier text of this section said eight; D-24
and D-25 name all twelve between them, four of them in D-25's own *Surfaces
moved* clause. Corrected here rather than carried forward.

**The token bans were never the only mechanical enforcement**, and D-33 records
that alongside the count. Five gates are unconditional at every rung and no
version bump moves any of them: no cryptographic dependency may be declared
(`tests/packaging/test_dependency_boundary.py:88`); no module may import a
forbidden package, `ugence_trusted_evidence_authority` first among them
(`:93-94`); nothing in the package performs cryptography
(`tests/packaging/test_milestone_boundary.py:423`); no concrete class satisfies
any port (`tests/contract/test_confusable_and_ports.py:205`); and no
cryptographic module is imported at all
(`tests/contract/test_trust_contracts.py:410`). The rung protects the twelve
tokens. What no test here can assert is the external cryptographic audit itself,
which stays a hard precondition to any production use.

**Measured, on the ladder edit at `fd604dc4`:** minting the rung turns exactly
two tests red — the two version literals — and unlocks nothing.
`banned_capability_tokens` compares by ladder **index**, so inserting a rung
shifts BR-2C, BR-2D and BR-2E without lifting a ban. Bare `0.3.0` turns five
red, three of them the assertions that the bans did not weaken.

### Three BR-2A-era gates narrowed, each explicitly and with its citation

None was weakened to a pattern; each names the exact class and field it excuses.

- **The key-material ban** (`test_envelopes.py`) — D-25 ratifies that the anchor
  record binds public-key material. The exemption is one field on one class, is
  asserted in both directions so it cannot grow a second member, and licenses no
  parsing.
- **The visibility-dimension ban** (`test_tenancy.py`) — the `public_` token
  collision is incidental: that ban is about *audience*, and "public key" is
  cryptographic terminology. Every other token still applies to the field.
- **The caller-supplied-digest ban** (`test_chain_integrity.py`, and
  independently in `adversarial_probes.py`) — D-24 names both digests among the
  nine bound facts. The rule exists because chain payloads *chain*; a verified
  result chains nothing and is permanently `authority_verified is False`, so a
  settable digest admits no forgery the type did not already admit. Nesting was
  rejected because it would make `TRUST_ANCHOR_NOT_FOUND` and
  `TRUST_DIRECTORY_UNAVAILABLE` — refusals in which no anchor exists to nest —
  structurally unrepresentable.

### Left open here, since ruled — and not implemented in this release

Both items this entry recorded as needing a further owner decision have one.
Neither ruling is implemented at `0.2.1`: the shapes below are still what ships,
and the rulings land in a later release.

- **`resolve_anchor` returns `Optional[BenchmarkTrustAnchorRecord]`**, so a
  `None` cannot distinguish `TRUST_ANCHOR_NOT_FOUND` from
  `TRUST_DIRECTORY_UNAVAILABLE` at the seam itself. This follows the rulings
  literally — D-25 enumerates exactly one new type and D-28 says "no further
  type is minted here", and both D-27 and D-28 locate the distinctions in the
  verified result — but D-28's fail-closed posture needs the two separable.
  **Ruled by D-34**: the seam returns a resolution type carrying an anchor
  record **XOR** a typed refusal. Not implemented here; shipped in `0.2.2`.
- **Which refusal members a verified result may carry** is unconstrained beyond
  membership of the BR-2 vocabulary. **Ruled by D-35**: the eleven-member
  `TRUST_AND_AUTHENTICITY` fault class plus `INDETERMINATE`, twelve of the
  twenty-four. No refusal member is added or re-ordered by that ruling. Not
  implemented here.
- **D-31(a)'s deferred README obligation is discharged here**: the
  measured-results table is re-stated from the fresh runs above rather than
  edited, and its BR-2A-era marking withdrawn with it.

## [0.2.0] — BR-2B: the non-authoritative lifecycle kernel

**Determines what a transition would be. Makes none occur.**

Ships no store, no verifier, no clock, no append path and no authority-issued
result, and cannot admit, register, revoke or resolve. Non-authoritative *by
construction*, not by an injected default: there is nothing here for a
substituted component to unlock.

### Added

- `BenchmarkRegistrySnapshotAssertion` — what a caller **asserts** the registry
  holds for one exact locator. Never a reading; every field is `asserted_`.
- `BenchmarkTransitionPlan` — a move that would be admissible against exactly
  the nested assertion. Unconstructible for an inadmissible one, and bound to
  the assertion it was computed from by a recomputed digest.
- `BenchmarkTransitionRefusal` — the typed negative, carrying one reason from
  the BR-2 vocabulary.
- `BenchmarkRegistrationRecordPresence` — a closed two-member enum, not a
  Boolean, gating `ADMITTED -> REJECTED`.
- `plan_transition`, `plan_submission_outcome`, `is_byte_identical_resubmission`
  and the `BenchmarkPlanningOutcome` alias. Total functions: exact contracts in,
  a plan or a refusal out, no third outcome and no raw digest or byte argument.
- Three digest domains, appended never inserted: registry-snapshot-assertion,
  transition-plan, transition-refusal.

### Ruling notes

- Idempotence compares canonical **bytes**, recomputed from both records
  (D-06). Neither side may be supplied as bytes or as a digest.
- Confusable handling stays **rejection-only**. No algorithm is claimed, no
  locator is normalized, casefolded, rewritten or stored.
- Self-inconsistent assertions fail closed with `STALE_REGISTRY_SNAPSHOT`
  rather than being repaired.
- **No exported callable accepts a `BenchmarkTransitionPlan`.** Asserted on live
  signatures and again over the source tree, so the seam through which applying
  a plan could arrive does not exist.

### Changed

- Curated surface 82 -> 93 symbols; `public_api.json` 81 -> 92; pinned vectors
  and digest domains 15 -> 18. Moved deliberately in every assertion site, per
  D-18.
- Capability-token bans are milestone-conditional (D-19) and, at this version,
  identical to the set BR-2A froze. Permanent bans stay permanent.
- The distribution's own four-phase prose is corrected to the five-phase
  ratification (ADR §35 D-01, amended 2026-08-20).

### Closure-audit remediation

The first closure audit confirmed the property — *no callable consumes a
`BenchmarkTransitionPlan`* — and **refuted the gates asserting it**. Three plan-
consumption gates matched the literal substring `"BenchmarkTransitionPlan"` and
skipped parameters annotated `None`; the return-type gate claimed to read a live
annotation but, under PEP 563, read the *string* `"BenchmarkPlanningOutcome"`
without ever inspecting the Union's members. A plan-consuming, event-returning
exported callable would have passed all four.

- Annotations are now resolved to **class objects** via `typing.get_type_hints`,
  with every `Union`/`Optional`/generic walked to its leaves, and membership
  decided by identity. An alias, a nested `Optional` and a PEP 563 string are
  each seen.
- An unannotated parameter under `contracts/` is a **failure**, not a skip.
  `self`/`cls` remain exempt; dataclass- and Enum-synthesized methods are
  excluded by checking that a function's code lives in a file this package
  contains.
- The return gate resolves hints and walks `typing.get_args`, so widening the
  outcome alias is visible.
- `BenchmarkPlanningOutcome` was recorded as `"kind": "pure_validation_function"`
  — a `Union` described as a function, because a `Union` is callable in CPython.
  It is now `"closed_type_alias"` with its **member set pinned**, so widening it
  fails a gate rather than only moving a symbol count.
- Thirteen new properties plant each attack — aliased parameter, nested
  `Optional`, PEP 563 string, unannotated parameter, private helper,
  keyword-only parameter, widened return Union — and require the checking logic
  to report it. Three new mutation gates (G-54, G-55, G-56) plant the same
  attacks in the shipped source; all three are killed.
- D-06 gains a **behavioural** discriminator alongside the source assertion: two
  submissions whose asserted identity *and* content digests are identical but
  whose canonical bytes differ. A digest-only rule returns
  `IDEMPOTENT_DUPLICATE`; comparing bytes returns `COORDINATE_SLOT_CONFLICT`.
  Only one of those is D-06's answer, and no source string is consulted.

### Second closure-audit remediation

The second audit confirmed `tests/_boundary.py` resolves correctly and found the
gates **consuming** it were scoped to `contracts/` and asked each function where
its code came from. Three planted callables kept the suite and probes green:

- **D** — a function `exec`-compiled inside `planning.py` with
  `co_filename="/tmp/not_under_contracts.py"`.
- **E** — the same exemption via one `__code__.replace(co_filename=...)` on an
  ordinary `def`, no `exec` at all.
- **F** — a module-level alias and a plain plan-consuming `def` in `api.py`,
  which the `contracts/`-scoped module walk and alias walk never visited.

D and E are the same mistake as the substring rule they replaced: letting
something the attacker supplies decide what this package contains. `co_filename`
travels with the code object and is chosen by whoever compiled it. **Ownership
now follows the scanned path** — the module walk imports exactly the files the
AST scan reads, and the alias set is gathered from every one of them.

- The plan-consumption check carries **no exemption of any kind**. A synthesized
  method has no annotation naming a plan, so excluding one would buy nothing and
  cost the guarantee.
- The annotation requirement keeps a narrow exemption, decided by **identity
  against a base class** (`EnumType` copies `_generate_next_value_` into every
  subclass), by the dataclass machinery's fixed method set, or by the module's
  **own source text** (`typing.Protocol` installs `__init__` and
  `__subclasshook__`; `from dataclasses import fields` binds a stdlib function).
  Never by a filename.
- The return check is scoped to planners, since BR-2A's
  `require_exact_resolution_record_payload` legitimately returns a resolution
  record and `BenchmarkRegistryStorePort.read_historical` legitimately declares
  one. Nothing rests on it: a callable consuming a plan and returning an event
  is caught by the parameter check.
- Probe Q-62 had the identical `contracts/` blind spot and is widened the same
  way, verified to catch F independently of the suite.
- G-57, G-58 and G-59 plant exactly D, E and F in shipped source; all three are
  killed by `test_no_callable_anywhere_under_src_accepts_a_plan_however_spelled`.
  The sweep gained explicit support for gates outside `contracts/`, since a
  sweep confined to `contracts/` could not have planted F.

### Owner ruling: the universal callable claim is withdrawn

A third audit found four more bypasses — a dunder-named plan-consuming lambda,
a class whose `__module__` was reassigned to `"builtins"`, a base class given
the same treatment so a derived method looked generated, and a reserved
authority name bound by `NewType` rather than `class`.

That made **seven defects across three audits, none of them in the boundary**
and every one in a rule asserting it. The delivering session's answer was a
frozen 2207-entry inventory of every callable reachable under `src/`, compared
for exact equality. **The owner ruled that design out on 2026-08-20 (ADR §35
D-20), and the claim behind it with it.**

The claim was never provable. Python permits closures, callables held in
containers, dynamic attributes, `exec`, `type()`, `__getattr__`,
`functools.partial` and runtime rebinding; every design only changed *what
counted as discoverable*, which is why each fix produced the next bypass. The
inventory additionally failed against its own adversary: a contributor who can
modify production source can regenerate the inventory in the same commit, and
a 2207-entry JSON diff dominated by stdlib imports and synthesized methods is
not something a reviewer reads closely. It was also Python-version-dependent —
it failed on 3.10, 3.12 and 3.13, three of the four versions this distribution
declares.

**Removed:** `public_callable_inventory.json`, `tools/generate_callable_inventory.py`,
the five tests that compared against it, and mutation gates G-57, G-58, G-60,
G-61 and G-62, which planted plan consumers in *private* source and asserted
the package could discover them. The removals are recorded in
`gate_mutation_sweep.py` beside the gates that remain, not dropped silently.

**The enforceable claim, in four decidable parts.** BR-2B asserts:

1. **No exported callable and no declared Protocol port method accepts a
   transition plan** — 22 callables, by resolved type identity through
   `typing.get_type_hints` with every `Union`, `Optional` and generic walked to
   its leaves, so an alias or a nested plan is as visible as a bare one. That
   surface must be fully annotated, or the check would pass vacuously on an
   unannotated parameter, and its size is pinned so it cannot shrink quietly.
2. **No authority-issued result type exists** — the reserved names bind to
   nothing, under any binding form, anywhere under `src/`.
3. **No store, verifier, clock, append or apply operation, composition root or
   prohibited dependency exists** — the capability, dependency and clock gates,
   unchanged.
4. **Planning returns only a structural plan or a typed refusal.**

**Why that is enough.** A private helper taking a plan computes a value and can
do nothing with it: there is no store to append to, no clock to read, no
authority-issued result to return and no effectful operation to call. That is
what "non-authoritative by construction" means, and it survives the introduction
of a private helper or a verifier — which the universal claim was never needed
to prevent.

**Private-source expansion is governed, not gated.** `.github/CODEOWNERS` now
covers this package's source, its manifests, its boundary tests, its probe and
mutation harnesses, its distribution verifiers, the frozen BR-1 layer and the
ADR. **CODEOWNERS is not enforcement** — it routes review requests. It becomes a
control only with branch protection requiring a pull request, review from code
owners, and an approval from someone other than the author. **A single owner
approving their own change is not an independent review**; naming a distinct
reviewer is an open owner action, recorded in the file itself.

**Python versions.** `requires-python = ">=3.10"` declares four interpreters and
CI now runs the suite on all four. Two test-harness defects blocked 3.10 and were
fixed: the metaclass forgery in `tests/_hostile.py` and in probe Q-14 let
`@dataclass` synthesize `__doc__`, and CPython 3.10 builds a missing `__doc__`
from `str(inspect.signature(cls))`, which raises on a class whose metaclass
forges `__eq__`. Supplying `__doc__` avoids the call and changes nothing about
the forgery. **Open item, BR-1:** the frozen layer declares the same range but
its dependency-boundary test imports `tomllib` (3.11+), so BR-1's suite cannot
run on 3.10. Its shipped source is unaffected — 592 of 593 tests and all 57
probes pass there. Resolving it is a BR-1 decision; BR-2 changes no BR-1 file.

### Verification performed for this release

Measured, not asserted. Every number came from a run against this tree, after
purging every `__pycache__` and `*.pyc`, with `PYTHONDONTWRITEBYTECODE=1` and
`pytest -p no:cacheprovider`.

- **Suite** 1731 tests on **each of Python 3.10, 3.11, 3.12 and 3.13**. 470
  distinct properties, 438 adversarial : 32 happy, 13.69:1. Movement from
  1733/472 is **−2**: eight inventory-dependent tests removed, six narrowed-claim
  tests added.
- **Independent probes** 65/65 on each of the four interpreters, and 65/65 again
  from inside the installed wheel. Q-62 was rewritten from the withdrawn
  universal claim to the exported-plus-port surface, and now walks **both**
  curated surfaces rather than trusting the gate that pins them equal. It was
  proven non-vacuous against a planted exported plan consumer, and its assertion
  order was corrected so an offender is reported as an offender rather than as a
  surface-size change.
- **Mutation sweep** 60 inventoried, 55 killed, 5 survived, 0 errored. Movement
  from 65/60 is **−5**, all of them gates asserting the withdrawn claim. G-54 and
  G-55 were re-aimed from private helpers at the exported surface, G-59 from a
  `contracts/`-scope bypass at a declared port method; each is killed by the
  named narrowed-claim test, not by an import failure.
- **Offline distribution verifier** PASSED, 41 checks, 8/8 negative controls.
  Wheels built in the host environment; the isolated environment only ever
  installs a wheel — fresh venv, no system site packages, `--no-index`,
  `PIP_NO_INDEX=1`, emptied `PYTHONPATH`, `PYTHONNOUSERSITE=1`, wheelhouse of
  exactly two wheels.
- **BR-1 freeze matrix** VERIFIED; BR-1 suite 593 and probes 57 on 3.11, probes
  57 on all four. No BR-1 file is touched.
- **`pyflakes`** clean over both packages.
- **Public surface unmoved**: `api.__all__` 93, `public_api.json` 92, 18 pinned
  vectors, 18 root-canonicalizable domains, 18 public data contracts.

The five mutation survivors are unchanged and none is a gap: **G-12** is shadowed
by G-11 (identical bytes necessarily hash identically); **G-28**, **G-29** and
**G-30** are the encoder's float, NFC and aware-datetime branches, each shadowed
by construction-time validation and graph revalidation (G-17); **G-43** is
equivalent while BR-1 is frozen, and the freeze matrix would catch that drift.

**Not claimed.** The narrowed design has had no independent audit. Three audits
examined the *previous* designs, and what they found is why the claim was
narrowed rather than patched again. The delivering session wrote, ran and
reported everything above, and an author-owned test, probe or mutation run is not
an audit. **Nor is the governance control live**: CODEOWNERS ships in this
change, branch protection and an independent reviewer do not.

### Residue remediation (ADR §35.2 D-30 and D-31)

Prose-only correction of BR-2A-era statements that survived the `0.2.0` surface
move. **No behaviour, no surface and no version changed**: `api.__all__` stays
at 93, `public_api.json` at 92, the BR-2 refusal vocabulary at 17 and the
combined BR-1/BR-2 list at 34, and `package_version` stays `0.2.0`. No
capability token was unlocked and no BR-2C work is begun.

- **Three stale counts inside `src/` corrected from fifteen to eighteen**, the
  number of root-canonicalizable classes `canonical_domain_inventory.json`
  registers at
  `package_version` `0.2.0` — `api.py:23`, the domain-block comment at
  `contracts/canonical.py:254-255`, and the `canonical_bytes` docstring at
  `contracts/canonical.py:684`. Each now follows the phrasing already correct at
  `contracts/canonical.py:73-74`, `:129` and `:362`: BR-2A's fifteen and BR-2B's
  three.
- **Three milestone labels corrected from BR-2A to BR-2B** — the `api.py` module
  docstring's title and layer sentence, and the `milestone` field of
  `public_contract_inventory.json`, whose source moved with it in
  `tools/generate_manifests.py` so regeneration no longer reverts the label.
- **Three stale counts corrected outside `src/`** — the canonicalization heading
  in `README.md`, and the two generator strings in `tools/generate_manifests.py`
  (the `_root_canonicalizable_classes` docstring and the public-contract
  inventory note).

Manifests were regenerated with `tools/generate_manifests.py` rather than
hand-edited; the only bytes that moved in a committed manifest are the
`milestone` field and the note's count word.

**The three items outside D-30's enumeration are ruled by D-31**, all
correct-now, and are corrected in this release rather than deferred:

- `README.md` — the three missing rows are added to the table under the
  corrected heading, transcribed from `canonical_domain_inventory.json` and
  `pinned_canonical_vectors.json`; `README.md:1`'s `BR-2A` title moves to
  `BR-2B`; and the "Measured results" table is marked **BR-2A-era**, with its
  re-measurement deferred to a README pass at BR-2C. No number in it is edited.
- `tests/_builders.py:300` — corrected to eighteen classes, and the one-to-one
  builder claim is dropped: twenty builders cover the eighteen classes, because
  `rejected_admission_decision` and `unoccupied_assertion` are second fixtures.
- `gate_mutation_sweep.py:1147` — the `milestone` literal moves to `BR-2B` and
  `gate_inventory.json` is regenerated by an actual sweep run. That run
  reproduced the committed ledger exactly — **60 inventoried, 55 killed, 5
  survived, 0 errored** — so the only byte that moved in the ledger is the
  label. The label is **not** derived from `tests/_milestones.py`.

**A second, independent audit found further shipped-text residue, corrected
here.** Three of the sites reach a consumer of the built artifacts:

- `pyproject.toml` — the distribution `description`, which ships as the
  wheel and sdist `Summary`, still announced BR-2A "contracts only, no
  registry". It now names the BR-2B kernel and what `0.2.0` actually ships.
- `src/ugence_benchmark_registry_authority/__init__.py:1` — the top-level
  package docstring title, moved on D-30's ground for `api.py:1`.
- `canonical_domain_inventory.json`'s `note` — said "a BR-2A graph" and
  "NO BR-2A domain" in a shipped machine-readable manifest. The generator
  literal at `tools/generate_manifests.py:482` moved to **BR-2**, the span the
  sentence actually describes, and the file was regenerated.

`api.py:11-12` attributed BR-2A's ratified title *and* D-01–D-17 to BR-2B; it
now names the `0.2.0` surface as BR-2A's ratified contracts plus the kernel
BR-2B adds, and the bullet list gained the three lifecycle-kernel contracts it
had omitted. Corrected alongside, none of them shipped: the `README.md`
dependency-diagram and nested-admissible prose, the `tests/_builders.py` module
title, the probe-harness title, the sweep banner, and the distribution
verifier's title, comment and failure line.

**Verification for this correction.** Measured against this tree on Python 3.11,
with every `__pycache__` purged, `PYTHONDONTWRITEBYTECODE=1` and
`pytest -p no:cacheprovider`.

- **Suite** 1731 passed.
- **Offline distribution verifier** PASSED; 8/8 negative controls caught,
  including "all eighteen pinned vectors were reproduced"; 65/65 probes inside
  the installed wheel.
- **Mutation sweep** 60 inventoried, 55 killed, 5 survived, 0 errored —
  unchanged from the committed ledger.
- **Manifest regeneration** 18 data contracts, 74 other symbols, 18 domains,
  3 nested-only, 18 vectors, 92 symbols against `api.__all__` = 93.

Nothing pinned moved: `api.__all__` 93, `public_api.json` 92, refusal counts 17
and 34, `package_version` `0.2.0`, and every canonical domain, pinned vector and
digest byte-identical.

## [0.1.0] — BR-2A: registry and exact-resolution contracts

First release. **Contracts and pure validation only.**

### Added

* **Three inbound assertion envelopes** carrying *declared* signature material:
  `BenchmarkPublisherSubmissionEnvelope` (the sole source of publisher identity
  in the entire chain), `BenchmarkApprovalEnvelope` (nesting the exact publisher
  envelope, never its digest) and `BenchmarkRevocationEnvelope`. Each declares a
  closed signature profile — never an unconstrained algorithm string — and its
  own pinned signing-frame domain, so a signature under one frame can never be
  replayed under another.
* **A completely specified signing frame** — framing order, `uint32_be` length
  prefixing of every element including the framing elements, domain tag and
  version — published as `BENCHMARK_SIGNING_FRAME_SPECIFICATION` so BR-2C need
  never reinterpret a contract this milestone already published. Nothing here
  builds, signs or verifies a signing input.
* **Six administrative chain payloads**, one structural representation bound to
  each transition, including `BenchmarkPostAdmissionRejectionEventPayload` for
  `ADMITTED → REJECTED` — a distinct type because that transition has a distinct
  predecessor. Every payload except the initial submission record exposes a
  mandatory `prev_event_digest` derived from its exact nested predecessor.
* **Two read payloads** as different exact types, so a historical answer cannot
  be consumed as a current one, with pure type guards proving the separation.
* **Two request shapes and two registry scope expectations.** The trusted
  resolution request has no `as_of` at all; the scope expectation is derived from
  the locator's own scope rather than accepted as a second, disagreeable field.
* **One canonicalization path and one digest path**, versioned, with fifteen
  minted domain-separation tags — one per artifact class this subphase actually
  ships, and no tag for an artifact that does not exist — and a pinned canonical
  byte vector and digest for every one of them.
* **`BenchmarkRegistrationState`** (`SUBMITTED · ADMITTED · REGISTERED · REVOKED
  · REJECTED`), its closed transition relation with terminal states expressed as
  empty sets, and the immutable, test-asserted transition-to-payload binding.
* **`BenchmarkRegistryRefusalReason`** — seventeen BR-2 reasons, provably
  disjoint from BR-1's frozen seventeen — the ordered composite
  `BENCHMARK_REGISTRY_ALL_REFUSAL_REASONS`, and a total classification into
  seven `BenchmarkRegistryFaultClass` members.
* **Four inert `Protocol` ports**, a frozen consistency descriptor with no
  flippable Boolean, and the typed `BenchmarkRegistryCompositionError` — defined
  for later use and raised by nothing here.
* **The confusable comparison contract**, rejection-only, with its algorithm slot
  explicitly empty and no completeness claimed.
* **Machine-readable manifests**: `public_api.json`,
  `public_contract_inventory.json`, `canonical_domain_inventory.json`,
  `pinned_canonical_vectors.json` and `gate_inventory.json`, every one asserted
  against the live surface rather than maintained by hand.
* **Verification tooling**: an independent probe harness, a distribution
  verifier with eight negative controls, a BR-1 freeze-matrix verifier, and a
  gate-deletion mutation sweep over a 48-gate inventory.

### Deliberately not added

No admission engine, storage implementation, signature verifier, key parser,
trust-anchor store, approval verifier, clock read, resolver, convenience
resolver, selection API, supersession implementation, adapter registry, identity
allow-list, production composition root, or cryptographic dependency. No
placeholder verifier, permissive fallback, dormant capability field, reserved
future field, executable stub, TODO-backed runtime path, or `NotImplementedError`
pretending to be a port implementation.

The authority-issued result types `BenchmarkAdmissionDecision`,
`BenchmarkRegistrationEvent` and `BenchmarkResolution` are **reserved and
undefined**.

### Unchanged elsewhere

`ugence-benchmark-registry` stays at `0.1.0` with its zero-dependency proof, its
593 tests, its 57 probes and its pinned digests intact. No other package and no
existing CI workflow is modified.
