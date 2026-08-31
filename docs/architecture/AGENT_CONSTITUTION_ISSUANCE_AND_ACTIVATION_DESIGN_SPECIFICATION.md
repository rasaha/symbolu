# Agent Constitution — Issuance & Activation design ballot

**The load-bearing question:** can the ratified first constitution become a
genuinely issued, resolvable, proposal-bound policy **without this repository
gaining a new authority or a single secret**? **Yes.** Every act the feature
performs is a call into an authority surface that already exists and is already
ratified: `issue_policy`, `resolve_policy` and `revoke_policy` in
`ugence_policy_authority.api`, the guarded adapter registration of `ACC-S1-Q3`,
the conformance resolver of the `ACC-S1` round, and the proposer's `ACC-AM-2`
stamping seam. What does not exist — and is this ballot's designed surface — is
the **orchestration** that wires them: a composition root, governed
reference-map population, preflight, receipts, and the end-to-end proof. The
four `ACC-FC-5` deployment gates stop being "unbuilt" and become "closable by
running shipped machinery with real custody"; they are not closed by this
repository, because keys, trust roots and approval artifacts never enter it.

**Status:** design ballot — documentation only. Nothing here is implemented,
issued or ratified by this document. **Date:** 2026-08-31.

**Authorities this round sits under:** `OD-C1..OD-C5`, `ACC-S1-*`, `ACC-AM-*`
and `ACC-FC-*` as ratified; the standing Policy Authority ADRs for the issuance,
approval, signing and resolution seams it composes.

---

## 0. Baseline verification

`[V]` Default branch `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`
head `8a67e4f9517a1a0793d5f8384a66eac6bd7f1f2a` — the merge of PR #1531, which
recorded `ACC-FC-BASE` and `ACC-FC-1`..`ACC-FC-5`. `[V]` Working tree clean.
`[V]` Substantive freeze digest recomputed this session, all checks PASS:
`d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036`. `[V]`
Agentic Proposer `0.4.0` with fifty-one names; Policy Authority `0.1.0`; both
constitution distributions `0.1.0`.

The seams this design composes, verified against source at this head:

* `issue_policy(*, policy, record_id, approval, approval_verifier, signer,
  registry, adapters, issued_at, expected_reference_tenant_id=None)` —
  `packages/policy-authority/src/ugence_policy_authority/core/issuance.py:66`.
  Approval arrives only as an `ApprovalEvidenceRef` a trusted verifier confirms;
  the signature is produced inside the authority; every failure is typed and
  leaves the registry untouched.
* `ApprovalEvidenceRef` / `ApprovalVerification` / `ApprovalVerifier` /
  `DenyAllApprovalVerifier` — `core/approval.py:63,85,140,160`. The production
  default denies: an unconfigured deployment cannot issue.
* `PolicySigner` (protocol: `authority_id`, `key_id`, `signature_alg`, `sign`),
  `PolicyKeyRing`, `DenyAllSignatureVerifier` — `core/signing.py:63,161,377`.
* `build_constitution_resolver(*, reference_map, registry, signature_verifier,
  approval_verifier, adapters=None)` — the conformance distribution's
  composition seam, which runs the `ACC-S1-Q3` family-collision guard on every
  path (`agent-constitution-conformance/src/.../composition.py:67`).
* `[V]` The resolver returns the exact `AgentConstitutionPolicy`, whose
  `agent_constitution_ref` and `metadata.policy_id`/`metadata.version`
  (`agent-constitution-policy/src/.../policy.py:217,321-322`) are precisely the
  duck-typed read shape the proposer's `_stamp_constitution_binding` consumes
  (`ACC-AM-2`) — so **resolve → bind needs no adapter at all**.

Stop condition for the eventual implementation: any of these verifications
failing at implementation time halts the change set.

---

## 1. Orchestration, not a new authority

The owner's bar for this feature, restated as testable claims:

* `[I]` **No new authority surface.** The activation package defines no signing,
  approval, canonicalization, registry or resolution semantics; every such act
  is a call into `ugence_policy_authority.api` (the only lawful import of the
  authority) or into the two constitution distributions' public surfaces. It
  mints no decision, emits no disposition or reserved authority term
  (`OD-C3=B`), and holds no lifecycle authority of its own (`OD-C4=A`) — when a
  policy is issued or revoked through it, the acting authority is the Policy
  Authority under owner-supplied trust, never this package.
* `[I]` **No custody.** The package never generates, loads, decodes, persists
  or transports key bytes. Signer, signature verifier and approval verifier
  arrive already constructed, through the existing protocols.
* `[I]` **No defaults that grant.** Absent any dependency, composition fails or
  the deny-all implementations refuse — the same fail-closed posture the
  authority and the conformance resolver already ratified.

---

## 2. The designed surface, mapped to the owner's coverage list

One new integration distribution (per `IA-1`), `ugence-agent-constitution-activation`,
carrying roughly:

| Coverage item | Designed seam |
|---|---|
| Key custody without committing keys | constructor parameters typed to the existing `PolicySigner` / `PolicySignatureVerifier` protocols; an AST/import scan over the package's `src` proves it cannot mint or read key material (`IA-2`) |
| Approving-authority evidence | `ApprovalEvidenceRef` passed through verbatim; the always-required `ApprovalVerifier` is the composition root's injected trust, never defaulted |
| Composition root | `build_activation_root(...)` wiring registry, adapters (via `with_agent_constitution_adapter`, so the `ACC-S1-Q3` guard runs), signer, verifiers, and the constitution resolver in one construction |
| Governed reference-map population | `populate_reference_map(...)` deriving entries **only** from the issued record and the policy's own `governed_role_refs` (`IA-3`) |
| Preflight / dry-run | `preflight_issuance(...)` replaying every pre-signing check through public API calls, mutating nothing (`IA-4`) |
| Issuance and activation receipts | two frozen receipt shapes pinning coordinates, digests, signer *identity fields*, approval evidence and activated entries — never key material (`IA-4`) |
| End-to-end proof | issue → resolve → bind → conform, in tests and a pinned offline verify script, on ephemeral in-process keys (`IA-5`) |
| Fail-closed behavior | the four-way refusal matrix: missing approval, missing trust, missing mapping, revoked policy (`IA-5`) |

Package disciplines carried over from its two siblings, disclosed rather than
re-litigated: role-projection markers never appear in the package (the binding
proof constructs the role under a fragment-assembled name, the pattern already
in `_permission_runtime_fixtures.py:89`); the authority is imported via
`ugence_policy_authority.api` only; no clock reads and no local hashing beyond
the API's own helpers; reserved-vocabulary and neighbour scans re-asserted in
its suite; the shared CI workflow gains its suite.

---

## 3. What stays outside the repository

`[R]` Per `ACC-FC-BASE` and `ACC-FC-5=A`, and unchanged by this round: no
signing key, trust root or approval artifact enters the repository — not as a
file, a fixture constant, an environment-variable *value*, or a committed
receipt of a production issuance. Tests and the verify script mint ephemeral
Ed25519 keys in-process at run time and discard them; the receipts they produce
exist only inside the run. The first **production** issuance of
`agent-constitution-ugence 1.0.0` remains a deployment act: an operator runs
this composition root with real custody, real approval evidence, and the
ratified `ACC-FC-2`..`ACC-FC-4` content values. `[G]` Which operator, when, and
under which approving authority stays open — this round makes the gates
closable, not closed.

---

## 4. The end-to-end proof and the fail-closed matrix

The proof obligation (`IA-5=A`), with every value the ratified `ACC-FC` content:

1. **Issue** the first constitution (ephemeral signer, approving verifier
   fixture that verifies real evidence bytes hashed at run time) —
   `IssuedPolicyRecord` returned, issuance receipt produced.
2. **Populate** the reference map from that record: exactly one entry,
   `(GLOBAL tenant, ugence.roles/ugence/invoice-reconciler/v1) →` the issued
   coordinate — activation receipt produced.
3. **Resolve** through `build_constitution_resolver` — the exact
   `AgentConstitutionPolicy` returns, signature- and approval-verified.
4. **Bind**: pass the resolved policy as the proposer's
   `constitution_resolution`; the advisory carries the stamped pair and
   `verify_advisory_identity` holds; the role's `constitution_ref` equals the
   signed reference or construction refuses (`ACC-AM-2`'s equality, now fed by
   a genuine resolution for the first time).
5. **Conform**: `role_facts_conform(policy=…, facts=…)` is `True` for declared
   facts inside the three bounds, `False` outside the tool-scope ceiling.

The refusal matrix, each case typed, mutation-free and proven at both the
issuance and the resolution seam where applicable: **missing approval**
(deny-all or unverified evidence → `PolicyApprovalError`, nothing registered);
**missing trust** (deny-all signature verifier or unknown key id → resolution
refuses); **missing mapping** (unmapped pair → `ConstitutionUnresolvedError`
with its typed reason); **revoked policy** (issue, revoke, resolve → refusal
with the revocation reason). `[I]` All four already exist as authority and
resolver behaviors; the matrix proves the *composed* system preserves them.

---

## 5. Owner-decision register (five)

| # | Decision | A (recommended) | B |
|---|---|---|---|
| IA-1 | Packaging | one new integration distribution `ugence-agent-constitution-activation` (namespace `ugence_agent_constitution_activation`), `0.1.0`, joining the shared agent-constitution CI workflow; no existing package's version moves | fold activation modules into the conformance distribution |
| IA-2 | Custody and trust seams | signer and verifiers arrive already constructed via the existing protocols; the package's `src` provably cannot mint, read or persist key material (AST/import scan: no key construction, no `nacl`, no environment or filesystem reads); ephemeral in-process keys in tests only | also ship custody adapters (env/KMS loaders); the ballot returns until a custody backend is named |
| IA-3 | Reference-map population | entries derive only from the issued record: one entry per reference in the policy's `governed_role_refs`, each mapped to the issued coordinate under the policy's scope tenant; free-form entries refused; conflicting existing entries fail closed; the activation receipt lists every entry — narrowing the standing `ACC-FC-3` gap from "ungoverned" to "governed by derivation" | accept caller-supplied entries with validation only |
| IA-4 | Preflight and receipts | `preflight_issuance` replays every pre-signing check via public API calls and mutates nothing; `IssuanceReceipt`/`ActivationReceipt` are frozen shapes pinning coordinate, digests, record id, signer identity fields (`authority_id`/`key_id`/`signature_alg` — never key material), approval ref + digest, caller-supplied tz-aware times, activated entries | vary the receipt fields or drop preflight; owner specifies |
| IA-5 | Proof scope | the full issue → resolve → bind → conform chain plus the four-way refusal matrix, in tests and a pinned offline verify script, on ephemeral keys | prove issuance and resolution only; the binding leg deferred to the pilot round |

Couplings, disclosed: `IA-3=A` is what makes step 2 of §4 lawful — under
`IA-3=B` the reference map stays effectively ungoverned and the `ACC-FC-3` gap
does not narrow. `IA-5=A` requires the proposer-binding fixtures and therefore
a test-side dependency on the proposer package; `IA-5=B` removes that
dependency and the strongest claim this round can make. `IA-2=B` widens scope
into custody engineering this ballot deliberately excludes. No other pair
interacts. The fixed surface below is put to ratification whole alongside the
rows, with the standing precedence rule: where an `IA` row and the fixed
surface overlap, **the `IA` ruling governs**.

---

## 6. Paste-ready owner-ratification ballot

```
Agent Constitution — issuance & activation design ballot
Baseline: rasaha/symbolu default head 8a67e4f9517a1a0793d5f8384a66eac6bd7f1f2a
Governed by OD-C1..OD-C5, ACC-S1-*, ACC-AM-* and ACC-FC-* as ratified.
Answer each with A or B. A = the recommended path.

ISSUANCE_SURFACE  Ratify the fixed surface: the feature is orchestration over the
      existing Policy Authority and constitution distributions — it defines no
      signing, approval, canonicalization, registry or resolution semantics, mints
      no decision, emits no disposition or reserved authority term, and holds no
      lifecycle authority of its own; no signing key, trust root or approval
      artifact enters the repository in any form (tests use ephemeral in-process
      keys); the only first-constitution values used are the ratified ACC-FC
      content values; proposer 0.4.0, Policy Authority 0.1.0 and both constitution
      distributions 0.1.0 are unchanged by this round's ratification; /clauses/v2
      stays out of scope and ACC-AM-4's re-arm stays untriggered — with the
      precedence rule: where an IA row and this surface overlap, the IA ruling
      governs.  YES/NO.

IA-1  Packaging.
      A = one new integration distribution ugence-agent-constitution-activation
          (namespace ugence_agent_constitution_activation), 0.1.0, joining the
          shared agent-constitution CI workflow; no existing version moves.
      B = fold activation modules into the conformance distribution.

IA-2  Custody and trust seams.
      A = signer, signature verifier and approval verifier arrive already
          constructed via the existing ugence_policy_authority.api protocols; the
          package src provably cannot mint, read or persist key material (AST and
          import scan); ephemeral in-process keys in tests and the verify script
          only.
      B = additionally ship custody adapters (env/KMS loaders); the ballot
          returns until a custody backend is named.

IA-3  Governed reference-map population.
      A = entries derive only from the issued record — one per reference in the
          policy's governed_role_refs, mapped to the issued coordinate under the
          policy's scope tenant; free-form entries refused; conflicts fail
          closed; the activation receipt lists every entry.
      B = accept caller-supplied entries with validation only.

IA-4  Preflight and receipts.
      A = preflight_issuance replays every pre-signing check via public API calls
          and mutates nothing; frozen IssuanceReceipt/ActivationReceipt pin
          coordinate, digests, record id, signer identity fields (never key
          material), approval ref + digest, caller-supplied tz-aware times, and
          the activated entries.
      B = the owner varies the receipt fields or drops preflight.

IA-5  Proof scope.
      A = the full issue → resolve → bind → conform chain plus the four-way
          fail-closed matrix (missing approval, missing trust, missing mapping,
          revoked policy), in tests and a pinned offline verify script.
      B = prove issuance and resolution only; the binding leg deferred to the
          invoice-reconciler pilot round.

Record as: ISSUANCE_SURFACE=? IA-1=? IA-2=? IA-3=? IA-4=? IA-5=?
No implementation is authorized by this ballot; register labels and the
implementation-authority ruling belong to the ratification ADR that records
these answers and to the separate ruling that follows it.
```

---

## 7. Paste-ready independent-review prompt

```
Read-only independent review. Do not modify files, create a branch, commit, push or open a PR.

Repository: rasaha/symbolu
Expected default-branch head: 8a67e4f9517a1a0793d5f8384a66eac6bd7f1f2a
Artifact under review: docs/architecture/AGENT_CONSTITUTION_ISSUANCE_AND_ACTIVATION_DESIGN_SPECIFICATION.md

Verify the baseline first (head, clean tree, the ACC-FC ratification ADR merged via
PR #1531, proposer 0.4.0/51, Policy Authority 0.1.0, both constitution distributions
0.1.0, freeze digest d993093570bb8ee132d4ab58406a14dd8c9b774b9de2c6d7ac45d3dfd3fac036
unchanged); stop on mismatch. Then judge against the repository, not this document's
prose:

1. Are the §0 seam citations accurate — issue_policy's signature and fail-closed
   posture, the approval boundary's shapes and deny-all default, the PolicySigner
   protocol, build_constitution_resolver's guard-on-every-path, and the claim that
   the resolver's returned AgentConstitutionPolicy duck-types the proposer's
   constitution_resolution read shape exactly (no adapter needed)?
2. Is "orchestration, not a new authority" real in the design — does anything here
   define signing/approval/registry/resolution semantics, mint a decision, emit a
   disposition or reserved term, or hold lifecycle authority of its own?
3. Is the no-secrets claim airtight as designed — including that IA-2=A's scan
   obligations are checkable, that ephemeral test keys don't leak into fixtures or
   receipts committed to the repository, and that no production issuance is
   performed or implied by this round?
4. Does the reference-map derivation rule (IA-3=A) genuinely narrow the ACC-FC-3
   gap, and is the four-way fail-closed matrix already backed by existing authority
   and resolver behaviors as claimed?
5. Are the five IA rows genuinely open decisions with defensible recommendations,
   is anything described as implemented/issued/settled that is not, and does
   anything trigger ACC-AM-4's re-arm or touch /clauses/v2?
Return SOUND, SOUND_WITH_CORRECTIONS, or BLOCKED, findings cited to file:line.
```

---

## 8. Readiness verdict

**READY_FOR_OWNER_RATIFICATION.** Baseline verified in full; the substantive
freeze digest is unchanged; five owner decisions plus the fixed-surface question
are open, and none is settled here. After ratification: the ratification ADR
recording the answers and assigning register labels; a separate
implementation-authority ruling; then one atomic change set building the
distribution, the CI wiring and the proof — at whose merge the four `ACC-FC-5`
gates become closable by any operator holding real custody, which is exactly as
far as a repository can lawfully take them.
