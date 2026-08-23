# ADR — A Neutral Canonicalization Contract for the Policy Workflow Compiler

**Status:** Proposed — **not ratified**. No implementation may begin until the owner
decision in §7 is recorded.
**Date:** 2026-08-23
**Owners:** Ugence platform architecture
**Related:**
- [`ADR_AGENT_WORKFORCE_COMPOSER_H16_CANONICALIZATION.md`](ADR_AGENT_WORKFORCE_COMPOSER_H16_CANONICALIZATION.md) — the canonicalization-ownership pattern this ADR extends
- `packages/tooling/policy-workflow-compiler/src/ugence_policy_workflow_compiler/serialization/canonical_json.py`
- `packages/capabilities/agent-workforce-composer/src/ugence_agent_workforce_composer/canonical.py`

> *This ADR changes no production code, wheel, public API, schema, frozen identifier,
> serialization, or digest. It proposes a package and records one completed test
> correction (§6). Every implied code change is deferred to a ratified later phase.*

---

## 1. Central decision put to the owner

> **Extract the Policy Workflow Compiler's canonicalization rules into a new neutral
> leaf distribution, `ugence-canonical-json`, and have the compiler consume it — while
> leaving the other five canonicalization implementations divergent by design.**

The counter-proposal, which this ADR does **not** dismiss, is §7 Option B: change
nothing, and record the six implementations as deliberate. §5 is where that argument
is strongest.

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

## 3. The proposed contract

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

**Acceptance gate (all four, or the package is not adopted):**
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

**`agent-workforce-composer` — eligible, deferred.** It is the only one whose rules are
compatible with the proposed contract, and adoption would collapse two implementations
into one. But AWC has its own fingerprints and its own frozen-object tests, so its
adoption needs its own digest-neutrality proof and its `mode="json"` choice needs an
explicit ruling. Deferred to a later phase, not bundled here.

**Consequence, stated plainly:** the contract launches with **one** consumer, with a
second plausible later. That is the strongest argument against it and is put to the
owner as Option B in §7 rather than argued away.

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

## 7. Owner decisions required

1. **`[R]` Option A (extract) or Option B (record the six as intentional and stop)?**
   Option B is defensible: §5 concludes four of five must never converge, so the
   contract serves one consumer today. Option A's case rests on AWC adopting it later
   and on the compiler's rules gaining a citable, testable definition of their own.
2. **`[R]` If A: is `mode="python"` ratified as normative** in the contract, freezing
   the compiler's current fail-closed behaviour on `datetime`/`Decimal`/`UUID`/`bytes`?
3. **`[R]` If A: does AWC adopt it in a later phase**, or is its `mode="json"` rule
   ratified as a permanent second contract?
4. **`[R]` Is the six-implementation state recorded as an accepted architectural
   property** of this repository, so future audits stop re-raising it as drift?

No implementation may begin until 1 is recorded. If 1 resolves to B, §6 stands and the
rest of this ADR is closed unimplemented.
