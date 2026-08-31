# Agent Constitution — lifecycle round implementation-authority ballot

**The load-bearing question:** the `ACC-LC` rulings say *what* supersession
must be; can it be built as ruled? **Yes, but two ratified phrases do not
survive contact with the registry unchanged, and this ballot exists to settle
them rather than to let an implementer settle them silently.**

`ACC-LC-1` names "an exact policy coordinate (`policy_id`, `version`, `scope`,
`tenant_id`)" — four fields. `[V]` The exact coordinate type has **six**
(`policy_family`, `policy_id`, `version`, `content_digest`, `scope`,
`tenant_id`), every one participating in identity, and the registry offers
*"exact coordinate resolution only — there is no `latest()`, `current()` or
`find_by_id()`"*. A four-field reference is therefore **not resolvable** by any
lookup that exists. `ACC-LC-2` says the signed act "transitions the predecessor
to `SUPERSEDED`" — `[V]` but issued records are **immutable and cannot be
overwritten**, in an append-only store, and `lifecycle_state` is part of the
signed artifact. No edit can transition anything. Both rulings' *intent* is
reachable; their mechanics are not what the words literally describe, and
`ACC-LC-5` reserved exactly this to the ruling that follows.

**Status:** implementation-authority ballot — documentation only. **No source
change is authorized until this ballot is answered and its ruling merges.**
**Date:** 2026-08-31.

**Governing record:**
[`ADR_UGENCE_AGENT_CONSTITUTION_LIFECYCLE_ROUND_RATIFICATION.md`](ADR_UGENCE_AGENT_CONSTITUTION_LIFECYCLE_ROUND_RATIFICATION.md)
(`ACC-LC-BASE`, `ACC-LC-1` – `ACC-LC-5`). `[R]` This ballot **refines**, and may
not overrule, those rulings: where a row below and an `ACC-LC` ruling conflict,
the `ACC-LC` ruling governs and the row is void.

---

## 0. Baseline verification

`[V]` Default branch head `69642cfc` — the merge of PR #1545, which landed the
lifecycle round's ballot and its ratification. `[V]` Working tree clean at
drafting time. `[V]` Policy Authority `0.1.0` with 66 authorized public names;
Agentic Proposer `0.4.0`; all three constitution distributions `0.1.0`.

Facts this ballot rests on, each verified at this head:

* `[V]` `PolicyCoordinate` is *"the complete, exact, family-neutral identity of
  one policy version … every component participates in identity, so an
  exact-match lookup is the only lookup the registry can perform"* — six
  fields, `content_digest` among them (`core/adapters.py:64-76`).
* `[V]` The registry is **append-only** with issuance and revocation in
  **separate stores**, offers **exact coordinate resolution only** with no
  `latest()`/`current()`/`find_by_id()`, and refuses to overwrite an issued
  record: *"issued versions are immutable and cannot be overwritten"*
  (`core/registry.py:10-20`, `:112-121`).
* `[V]` Revocation is already expressed as an **append to its own store**
  (`append_revocation`, `core/registry.py:72`), not as a mutation of the issued
  record — the precedent a supersession act would follow.
* `[V]` `REPLACED` already exists as a revocation reason code, alongside
  `CONTENT_DEFECT`, `APPROVAL_WITHDRAWN`, `COMPLIANCE_VIOLATION` and
  `ISSUED_IN_ERROR` (`core/statuses.py:141-145`).
* `[V]` Issuance runs ten numbered steps; supersession admissibility is **step
  4**, before the body digest (5), approval (6), lifecycle (7), signing (8),
  record construction (9) and the registry append (10)
  (`core/issuance.py:89-220`).

Stop condition for the eventual implementation: any of these failing at
implementation time halts the change set.

---

## 1. Owner-decision register (five)

| Row | Question | Recommended (A) | Alternative (B) |
|---|---|---|---|
| `LC-IA-1` | The successor reference's **field set** | the **full six-field `PolicyCoordinate`**, reused as-is — the only shape the registry can resolve. `[I]` Read as *fulfilling* `ACC-LC-1`, whose operative phrase is "an exact policy coordinate"; the four-field parenthetical is illustrative, and the exact coordinate type is six | the four fields `ACC-LC-1` lists literally, plus a new registry lookup that finds a record without a `content_digest` |
| `LC-IA-2` | How the predecessor's **supersession is recorded**, given immutability | a **third append-only store of signed supersession records**, on revocation's exact precedent; each names predecessor and successor coordinates, and resolution consults it and denies the predecessor with its own typed supersession reason | reuse the **revocation store** with reason code `REPLACED`, carrying the successor coordinate on the revocation record |
| `LC-IA-3` | Whether issuance **verifies the predecessor** | **yes** — at step 4 the predecessor must exist and be resolvable at the issuance instant; a successor naming an absent, revoked, already-superseded, wrong-tenant, wrong-scope or self-referential predecessor is refused before signing. `[I]` Step 4 gains a registry **read**; the invariant that matters — nothing from a rejected artifact is *stored* — is untouched | structural acceptance only: no registry read at issuance; a dangling reference surfaces later, at resolution |
| `LC-IA-4` | The **proof obligations** | the full fail-closed matrix as its own test module — the six refusals of `LC-IA-3`, the preserved refusal of the unstructured string, the predecessor ceasing to resolve after supersession while remaining readable, and one happy-path chain issuing a v2 over the ratified v1 on ephemeral keys | the happy path plus absence/revoked refusals only |
| `LC-IA-5` | **Packaging and versioning** | Policy Authority **minor version bump** with `public_api.json` regenerated for the new public names, plus a CHANGELOG entry; the constitution family, the conformance distribution and the activation root are **untouched** — no new seam, no new public name, no version move (`ACC-LC-4`) | a larger surface: the owner names which distributions move |

Couplings, disclosed: `LC-IA-1` and `LC-IA-3` interact — the six-field
reference (`A`) makes the predecessor lookup a direct exact-match read, while
`LC-IA-1=B` makes `LC-IA-3=A` require the new search capability that `B` would
have to add. `LC-IA-2` is independent of both. No other pair interacts.

`[R]` **The bite of `LC-IA-1=A`, disclosed:** a successor's author must know
the predecessor's `content_digest` to name it. That is a real burden, accepted
deliberately: it is also precisely what makes the reference bind exact bytes
rather than a mutable notion of "version 1.0.0", and the digest is already
carried on every issuance receipt.

---

## 2. The fixed surface put to ratification

Ratified whole alongside the rows, with the standing precedence rule: **where a
`LC-IA` row and this surface overlap, the `LC-IA` ruling governs.**

The authorized change set touches the **shared Policy Authority only**
(`ACC-LC-4`): a structured successor reference, the step-4 admissibility
checks, the supersession act and its store, the resolution consultation, the
proof module, `public_api.json`, the version and the CHANGELOG — and nothing
else. No agent or role lifecycle authority is taken, implied or prepared for
(`OD-C4=A`); no disposition or reserved authority term is emitted (`OD-C3=B`);
no signing key, trust root or approval artifact enters the repository and every
proof runs on ephemeral in-process keys; **no already-valid artifact is
invalidated and no existing refusal is relaxed** — a non-empty *unstructured*
value keeps being refused exactly as today; suspension is not implemented
(`ACC-LC-3`); `/clauses/v2` stays out of scope and `ACC-AM-4`'s re-arm stays
untriggered; no constitution is issued, superseded, suspended or revoked by any
act of this repository, and no agent runs, is enrolled or is claimed governed.
**YES/NO.**

---

## 3. Paste-ready owner-ratification ballot

```
Agent Constitution — lifecycle round implementation-authority ballot
Baseline: rasaha/symbolu default head 69642cfc
Governed by OD-C1..OD-C5, ACC-S1-*, ACC-AM-*, ACC-FC-*, ACC-IA-*, ACC-PR-* and
ACC-LC-* as ratified. Where a row conflicts with an ACC-LC ruling, the ACC-LC
ruling governs and the row is void. Answer each with A or B. A = recommended.

LC_IA_SURFACE  Ratify the fixed surface: the authorized change set touches the
      shared Policy Authority only — a structured successor reference, the
      step-4 admissibility checks, the supersession act and its store, the
      resolution consultation, the proof module, public_api.json, the version
      and the CHANGELOG, and nothing else. No agent or role lifecycle authority
      is taken, implied or prepared for (OD-C4=A); no disposition or reserved
      authority term is emitted (OD-C3=B); no signing key, trust root or
      approval artifact enters the repository and every proof runs on ephemeral
      in-process keys; no already-valid artifact is invalidated and no existing
      refusal is relaxed — a non-empty unstructured value keeps being refused;
      suspension is not implemented (ACC-LC-3); /clauses/v2 stays out of scope
      and ACC-AM-4's re-arm stays untriggered; no constitution is issued,
      superseded, suspended or revoked by any act of this repository; no agent
      runs, is enrolled or is claimed governed — with the precedence rule: where
      a LC-IA row and this surface overlap, the LC-IA ruling governs.  YES/NO.

LC-IA-1  The successor reference's field set.
      A = the full six-field PolicyCoordinate (policy_family, policy_id,
          version, content_digest, scope, tenant_id), reused as-is — the only
          shape the registry can resolve, since exact-match lookup is the only
          lookup it performs. Read as fulfilling ACC-LC-1, whose operative
          phrase is "an exact policy coordinate". Bite: a successor's author
          must know the predecessor's content_digest.
      B = the four fields ACC-LC-1 lists literally, plus a new registry lookup
          that finds a record without a content_digest.

LC-IA-2  How the predecessor's supersession is recorded.
      A = a third append-only store of signed supersession records, on
          revocation's exact precedent; each names predecessor and successor
          coordinates, and resolution consults it and denies the predecessor
          with its own typed supersession reason. Issued records stay immutable
          and are never edited.
      B = reuse the revocation store with reason code REPLACED, carrying the
          successor coordinate on the revocation record.

LC-IA-3  Whether issuance verifies the predecessor.
      A = yes — at step 4 the predecessor must exist and be resolvable at the
          issuance instant; absent, revoked, already-superseded, wrong-tenant,
          wrong-scope and self-referential predecessors are refused before
          signing. Step 4 gains a registry read; nothing from a rejected
          artifact is stored, as today.
      B = structural acceptance only: no registry read at issuance; a dangling
          reference surfaces later, at resolution.

LC-IA-4  The proof obligations.
      A = the full fail-closed matrix as its own test module — the six refusals
          above, the preserved refusal of the unstructured string, the
          predecessor ceasing to resolve after supersession while remaining
          readable, and one happy-path chain issuing a v2 over the ratified v1
          on ephemeral keys.
      B = the happy path plus absence and revoked refusals only.

LC-IA-5  Packaging and versioning.
      A = Policy Authority minor version bump with public_api.json regenerated
          for the new public names, plus a CHANGELOG entry; the constitution
          family, the conformance distribution and the activation root are
          untouched — no new seam, no new public name, no version move.
      B = a larger surface; the owner names which distributions move.

Record as: LC_IA_SURFACE=? LC-IA-1=? LC-IA-2=? LC-IA-3=? LC-IA-4=? LC-IA-5=?
This ballot authorizes no implementation by itself; register labels and the
authorization belong to the ruling ADR that records these answers.
```

---

## 4. Paste-ready independent-review prompt

```
Review, do not implement. Repository rasaha/symbolu at default head 69642cfc.
Read docs/architecture/AGENT_CONSTITUTION_LIFECYCLE_IMPLEMENTATION_AUTHORITY_BALLOT.md
and judge four things against the repository, not against the document:

1. Are §0's facts true — the six-field coordinate, exact-match-only resolution,
   append-only separate stores, issued-record immutability, and step 4's
   position before signing and registry access?
2. LC-IA-1 reads ACC-LC-1's four-field parenthetical as illustrative rather
   than binding. Is that reading legitimate, or does it overrule a ratified
   row? If the latter, say so plainly — the ballot is void on that row.
3. Does LC-IA-3=A's registry read at step 4 weaken any stated issuance
   invariant, or only the narrower "no registry access before signing" phrasing
   in the module comment?
4. Does any option, if ruled, require touching a role or an agent (OD-C4=A), or
   relax an existing refusal?

Report findings labelled [V]/[I]/[R]/[G] with file:line support.
```

---

## 5. Readiness verdict

`[R]` **Ready to put, with one caveat named.** `LC-IA-1` and `LC-IA-2` exist
because the ratified wording and the registry disagree; both rows are framed as
fulfilling the rulings' intent, and §4's review prompt asks a reviewer to check
that framing rather than trusting it. `[G]` If the owner reads `ACC-LC-1`'s
four-field list as binding rather than illustrative, `LC-IA-1=A` is void and
the round needs an amendment to `ACC-LC-1` before implementation can proceed —
that is the one path where this ballot cannot simply be answered.
