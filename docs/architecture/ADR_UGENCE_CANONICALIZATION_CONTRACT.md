# ADR — Canonicalization Ownership: Extraction of a Neutral Contract (Rejected)

**Status:** **Rejected (ratified).** Extraction was considered on measured evidence and
declined. **No shared canonicalization package is authorized.** **No migration of
`agent-workforce-composer` onto a shared contract is authorized.** The §6
enforcement-test correction is independently accepted and stands.
**Date:** 2026-08-23 (proposed) / 2026-08-23 (rejected)
**Owners:** Ugence platform architecture
**Related:**
- [`ADR_AGENT_WORKFORCE_COMPOSER_H16_CANONICALIZATION.md`](ADR_AGENT_WORKFORCE_COMPOSER_H16_CANONICALIZATION.md) — the canonicalization-ownership pattern this ADR applies
- `packages/tooling/policy-workflow-compiler/src/ugence_policy_workflow_compiler/serialization/canonical_json.py`
- `packages/capabilities/agent-workforce-composer/src/ugence_agent_workforce_composer/canonical.py`

> *This ADR changes no production code, wheel, public API, schema, frozen identifier,
> serialization, or digest. Its proposal was **rejected**; §3's surface sketch is
> retained only as the rejected object and is **not** an approved future contract.
> The one completed change it records is the test correction in §6.*

---

## 1. Central decision — ruled

The proposal put to the owner was to extract the compiler's canonicalization rules into
a new neutral leaf distribution, `ugence-canonical-json`, and have the compiler consume
it. **`[R]` The owner selected Option B and rejected extraction.**

> **Ruling: canonicalization remains domain-owned. No shared canonicalization package
> is authorized. No AWC migration is authorized.** Canonicalization stays with each
> domain wherever its rules carry contract, policy, signing, authority or compatibility
> semantics. Four implementations have documented reasons to remain distinct;
> `producer-attestation` already converges by re-export and needs no further package;
> AWC is the only presently eligible consumer. A separately versioned contract serving
> **one** consumer would add package, compatibility and governance surface without
> demonstrating sufficient reuse.

**Scope of the ruling.** It does **not** ratify every existing implementation as
permanently correct. It rejects *extraction* on the evidence currently available, and
nothing more. The measured analysis in §2 and §5 is preserved as the record that
evidence rests on, and §8 states what would have to become true to reopen it.

---

## 2. Context — what was actually measured

A migration of the compiler onto an existing published canonicalization contract was
attempted and **stopped before any code change**. The findings, all verified against
the working tree at `3cdaaf64`:

`[V]` **The named target does not exist.** `ugence-agent-constitution` is absent from
the working tree and from every object reachable in git history
(`git rev-list --all --objects`). There is no `packages/contracts/` directory.

`[V]` **Six independent canonicalization implementations exist**: the compiler,
`agent-workforce-composer`, `cloud-scaling-controller`, `policy-authority`,
`risk_authority`, and `cloud-scaling-producer-attestation` (the last being a
re-export of `risk_authority`, not a sixth rule set).

`[V]` **The compiler's four-name surface is unique to it.** All five others publish
`to_canonical_obj`. **None** publishes `dumps`, `dumps_pretty`, or `loads`.
`dumps_pretty` — indent-2 plus trailing newline, used by `package_io` for on-disk
package files — has no counterpart anywhere in the repository.

`[V]` **Four of the five cannot encode the compiler's inputs at all.** Differential
harness over compiler-representative values:

| implementation | outcome against compiler inputs |
|---|---|
| `cloud-scaling-controller` | raises `CanonicalizationError` on pydantic `BaseModel`; normalizes `-0.0`→`0.0` |
| `risk_authority` | raises `TypeError` on `BaseModel` **and** on every `float` |
| `policy-authority` | same float rejection; additionally requires NFC input |
| `producer-attestation` | re-export of `risk_authority`; inherits both failures |

`[V]` **`agent-workforce-composer` is digest-equivalent but architecturally barred.**
Substituting AWC's implementation into the compiler at import time reproduced **97
digest fields byte-for-byte** across `workflow_ir`, `assurance_manifest`,
`audit_schema`, `compiled_package`, both compact and pretty encodings, `logical_digest`
and the v2 fingerprints (`diff` empty), with the compiler suite at 153 passed /
1 skipped — identical to baseline. It is nonetheless barred in both directions:

- AWC declares `compiler-reference = ["ugence-policy-workflow-compiler>=0.1.0"]`, so a
  core compiler→AWC edge closes a distribution cycle through that extra.
- `packages/capabilities/agent-workforce-composer/tests/test_boundaries.py:24` adds
  `ugence_policy_workflow_compiler` to `_FORBIDDEN_ROOTS`.
- `packages/tooling/policy-workflow-compiler/tests/test_v2_determinism_and_boundaries.py`
  bans `ugence_agent_workforce_composer` from compiler source.

`[I]` **AWC's `model_dump(mode="json")` is a widening, not a divergence.** It differs
from the compiler's `mode="python"` on `datetime`, `date`, `Decimal`, `UUID` and
`bytes` — but no compiler model field uses those types (`provenance.effective_date` is
deliberately `str`, "kept as text to stay deterministic"). The compiler *raises* where
AWC would silently encode. Adopting `mode="json"` would remove a fail-closed guard
without moving a single existing digest.

---

## 3. The rejected proposal, recorded for the record

> **Not an approved contract.** What follows is the object the owner declined in §1. It
> is retained so a future reader can see precisely what was rejected and on what terms.
> The four-name surface below is **not** authorized, **not** a target for any package,
> and **not** a design any implementation may cite as ratified.

`ugence-canonical-json` — namespace `ugence_canonical_json`, a true leaf.

**Published surface (exactly four names):** `to_canonical_obj`, `dumps`,
`dumps_pretty`, `loads`.

**Binding rules**, lifted verbatim from the compiler's current implementation so the
extraction is a move, not a redesign:

- pydantic `BaseModel` → `model_dump(mode="python")`. **The mode is normative**, not an
  implementation detail: `mode="json"` is a different contract (§2, `[I]`) and must not
  be substituted without a new contract version.
- `Enum` → `.value`; mappings → sorted string keys; tuples → lists; sets → sorted lists.
- `dumps`: `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`.
- `dumps_pretty`: as above with `indent=2`, plus a trailing newline.
- Unicode is **not** normalized and floats are **not** rejected — both differ from
  `risk_authority` and `policy-authority`, and both are load-bearing here (§5).

**Dependencies:** stdlib + `pydantic>=2`. Nothing else, ever. This preserves the
compiler's declared core boundary ("Minimal core: only pydantic") because the contract's
own closure is a subset of what the compiler already admits.

**Acceptance gate as proposed (moot — the package is not authorized):**
1. All 97 compiler digest fields byte-identical to the pre-adoption baseline.
2. `WORKFLOW_IR_V1_DIGEST_COMPILER_VERSION` frozen at `"0.1.0"`.
3. Compiler suite at its then-current baseline, no skips added.
4. No new edge in either direction between the compiler and AWC.

---

## 4. Why this cannot be solved by picking an existing implementation

Because the compiler's rules are not a subset of any other package's rules — they are
in direct conflict with the two most widely consumed ones. `risk_authority` and
`policy-authority` both reject `float` outright and both require NFC. The compiler
canonicalizes pydantic models containing floats and does not normalize Unicode.
Adopting either would not be a migration; it would be a redefinition of what the
compiler can compile.

---

## 5. The convergence question — decided: **no forced convergence**

Each of the five argues for its own rules in its own module docstring, and in four
cases the argument is sound and the divergence must be preserved.

**`risk_authority` — must not converge.** `canonical_bytes` is the **signature
substrate**: `canonical.py` → `hashing.py` → `signing.py`. Changing it invalidates every
signature already issued. Its float rejection ("use integer minor units") is a
deliberate monetary fail-closed invariant, and its NFC requirement is a
digest-identity guarantee. Six modules import it, and
`cloud-scaling-producer-attestation` pins **25 digests** computed under it.

**`policy-authority` — must not converge.** Its Unicode posture is *versioned*
(`CANONICALIZATION_VERSION`, ADR §12.1 option (a)) and its digest shape is bare
64-hex, deliberately matched to what its policy contracts validate. Changing the rules
requires a new canonicalization version by its own stated design. Seven modules import it.

**`cloud-scaling-controller` — must not converge.** Its docstring states the reason
directly: it is "a numpy-only advisory leaf and must not gain a reverse dependency on
an authority/orchestration package merely to reuse a convenience type." It is also
float-*tolerant* by necessity (metrics are floats) with `-0.0` normalization, which is
incompatible with the authority canonicalizers. 31 modules import it — the largest
blast radius of any of the six.

**`producer-attestation` — already converged.** It is a re-export of `risk_authority`
with validation helpers; it introduces no rules. Nothing to decide.

**`agent-workforce-composer` — the sole eligible consumer; migration not authorized.**
It is the only one whose rules were compatible with the rejected proposal. Its
adoption is **not** authorized by §1 and is not deferred to a later phase — reopening
it requires the §8 triggers. AWC keeps its own canonicalizer, its own fingerprints and
its own `mode="json"` rule.

**The consequence that decided it:** the proposed contract would have launched with
**one** consumer. §1 ruled that this does not justify a separately versioned package,
and §8 records what would have to change for that to be revisited.

---

## 6. Completed in this change: the boundary-test scoping gap

`[V]` `tests/test_v2_determinism_and_boundaries.py::test_compiler_never_imports_awc_or_runtime`
asserted that the compiler never imports AWC, but implemented that by reading **three
named module files** and grepping their text. A forbidden import anywhere else passed
unnoticed — including in `serialization/canonical_json.py`, through which every emitted
digest flows.

Demonstrated, not assumed: injecting `import ugence_agent_workforce_composer.canonical`
into `canonical_json.py` and running the **pre-fix assertion verbatim** yields
`1 passed`. The assertion did not cover what its name claimed.

The test now (a) walks the AST of every `.py` file in the distribution against a named
`_FORBIDDEN_ROOTS` set, and (b) adds `test_importing_api_does_not_load_forbidden_modules`,
which imports the public API in an isolated subprocess and inspects `sys.modules` —
catching deferred and aliased imports a static scan cannot see. Against the same
injection both fail. Compiler suite: **154 passed, 1 skipped** (153 + 1, the new test);
`agent-workforce-composer`: **201 passed, 1 skipped**, unchanged.

This correction stands on its own and is independent of the §7 decision.

---

## 7. Recorded decisions

1. **`[R]` Ratified — Option B: do not extract `ugence-canonical-json`.** Rationale as
   recorded in §1. No shared package is authorized; no AWC migration is authorized.
2. **`[R]` Moot.** Whether `mode="python"` is normative in a shared contract does not
   arise, there being no shared contract. The compiler's own `mode="python"` behaviour
   is unchanged and remains its own to define.
3. **`[R]` Moot.** AWC does not adopt a shared contract. Its `mode="json"` rule stays
   its own; §2 `[I]` records that the difference is a widening, not a digest divergence.
4. **`[R]` Ratified, narrowly.** The six-implementation state is accepted **as the
   current architectural position on the evidence available**, not as a permanent
   ruling that each implementation is correct. A future audit should cite this ADR
   rather than re-raise extraction as drift — but §8 remains open.

---

## 8. Reconsideration triggers

Extraction may be reopened only when **all six** of the following hold. Any one of them
failing is sufficient to leave this ADR rejected.

1. **At least two independent consumers** require identical canonical bytes — not one
   consumer plus a plausible future one.
2. Their **accepted and rejected input domains are proven equivalent** — a
   canonicalizer that accepts what another refuses is not the same contract. §2 records
   how far apart the current six are on exactly this point.
3. **Unicode, float, numeric, ordering and serialization semantics are identical**,
   including `model_dump` mode, `-0.0` handling, NFC posture and set ordering.
4. The **dependency direction remains valid** — extraction must not create or restore
   an edge between the compiler and AWC in either direction (§2).
5. **Extraction removes more governance surface than it creates**, counting the new
   distribution's own versioning, compatibility and release obligations.
6. **Migration preserves every pinned digest and signature invariant** — demonstrated,
   not asserted, against the pins named in §5.

---

## 9. `[G]` Open gap the ruling depends on

The ratified rationale contemplates that duplication between AWC and the compiler "may
remain guarded by the existing byte-equivalence compatibility ratchet."

`[V]` **No such ratchet exists.** No test in either distribution compares AWC's
canonical bytes to the compiler's. The nearest candidates do something else:
`agent-workforce-composer/tests/test_compiler_reference.py` checks *adapter fidelity*
against a live `WorkflowIR` and digests it with AWC's own canonicalizer (and skips
entirely unless the optional `compiler-reference` extra is installed);
`tests/test_p2_1_equivalence.py` compares v1/v2 *planning outcomes* within AWC. Neither
would fail if the two canonicalizers drifted apart.

The 97-field byte-equivalence result in §2 was produced by a one-off harness in the
session that drafted this ADR. It was a measurement, not a committed guard, and it
protects nothing going forward.

**Consequence:** the duplication the ruling accepts is currently **unguarded**. Two
implementations that agree byte-for-byte today can diverge silently tomorrow, and
trigger 3 in §8 would then be unprovable without re-deriving the comparison by hand.

**`[R]` Requires a separate owner decision:** either commission a committed
byte-equivalence ratchet as a guard on the accepted duplication, or ratify that the
duplication stays unguarded and that drift between AWC and the compiler is acceptable.
This ADR does not decide it, and rejecting extraction does not resolve it.
