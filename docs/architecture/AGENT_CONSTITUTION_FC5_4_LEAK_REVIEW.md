# Agent Constitution — `ACC-FC5R-4` leak review

**The load-bearing answer: the permitted set is not clean. One value in it is a
digest of a secret, and it should be excluded.**

`ACC-FC5R-4` admits, into this repository, *"public identifiers and digests"*
about a closed gate. `[V]` The word **digests**, unqualified, admits
`approval_digest` — the sha-256 of an **externally produced approval artifact's
bytes** (`policy-authority/core/approval.py:63-74`). A digest is one-way only
when its preimage is unguessable; an approval artifact is a structured
governance record of unknown and probably low entropy. Committing its digest
publishes a **confirmation oracle** for the approval evidence that
`ACC-FC5R-4`'s own prohibition says must never be reconstructable.

`[V]` **No incident has occurred.** No gate has been closed, no closure has been
recorded, and no approval digest appears anywhere in `docs/architecture/`. This
is a defect in a rule that has not yet been exercised — which is the cheapest
moment to fix it, and the reason the row was flagged as the one that cannot be
undone.

**Status:** audit finding — documentation only. `[R]` This review **does not**
amend `ACC-FC5R-4`; narrowing a ratified ruling is an owner act, and §4 puts it.
**Date:** 2026-09-01.

**Scope.** The check the ratification recorded as open: *"whether any listed
identifier or digest could reconstruct key material, a trust root or approval
evidence."* Run against the repository at default head `65c90d31`, clean tree.

---

## 1. The permitted set, value by value

| Value | Preimage / what it is | Reconstruction risk | Verdict |
|---|---|---|---|
| gate name, closure date, responsible **role** | operational facts; a role, never a person | none | `[V]` **safe** |
| `key_id` | a **label** for a signing key | none — a label is not a key, and the trust root is the set of verification keys with entitlements, none of which this exposes | `[V]` **safe** |
| issuing / approving `authority_id` | organisational identifiers | none | `[V]` **safe** |
| `approval_ref` | a **pointer** to where an approval artifact lives — the record itself says it carries *"only where the artifact lives"* (`approval.py:64-69`) | none by itself; it names a location, not contents | `[V]` **safe** |
| `record_id` | a caller-chosen issuance label | none | `[V]` **safe** |
| the issued **coordinate** (`policy_family`, `policy_id`, `version`, `content_digest`, `scope`, `tenant_id`) | its `content_digest` is the canonical projection of **ratified, public** constitution content | none — the preimage is already public by ratification, so confirming it reveals nothing not already ratified | `[V]` **safe** |
| **`approval_digest`** | sha-256 of an **external approval artifact's bytes** | **yes** — see §2 | `[G]` **the finding** |

---

## 2. The finding

`[R]` **`approval_digest` must be excluded from what the repository may hold.**

* `[V]` It is the digest of bytes the repository is expressly forbidden to
  hold: `ACC-FC5R-4` names *"approval-artifact bytes"* among the things that may
  never enter, and the same sentence's *"or any value from which they could be
  reconstructed"* is precisely what a digest of a low-entropy preimage is.
* `[I]` **Why a digest is not automatically safe here.** Hashing protects a
  preimage only when the preimage cannot be guessed. An approval artifact is a
  governance record — an authority, a policy identity, a date, a decision — drawn
  from a small space. An adversary who can enumerate plausible artifacts can
  test each against the committed digest and learn, with certainty, which one is
  real. That is reconstruction of approval evidence by confirmation, and version
  control makes it permanent and retroactive.
* `[V]` **The contrast that proves the rule is about preimages, not digests.**
  The coordinate's `content_digest` is equally a sha-256, and is **safe** —
  because its preimage is the ratified constitution content, already public.
  Confirming it discloses nothing. The two digests differ in exactly one
  respect, and it is the one that matters.
* `[V]` **The gap is an unintended widening, not a decision.** `FC5-2`'s
  attestation list — the one the round actually reasoned about — names
  `key_id`, the two authority ids, `approval_ref`, `record_id` and the issued
  coordinate. It **does not name `approval_digest`**. Only `FC5-4`'s general word
  *"digests"* admits it. The round never weighed this value on its merits.

`[G]` **Residual, recorded but not a finding:** publishing `key_id` across
successive closures discloses key-rotation cadence, and `authority_id` discloses
who holds which role. Both are organisational metadata, not material, and both
are inherent to recording that a gate closed at all. Named so the review is
complete, not because it recommends a change.

---

## 3. What this review did **not** find

`[V]` No value in the permitted set exposes key material, and none exposes a
trust root: the signer and verifiers arrive already constructed, and the source
*"cannot mint, read or persist key material"*
(`agent-constitution-activation/tests/test_import_boundary.py:6-10`). No path was
found by which a `key_id`, an authority id or a coordinate yields a private key
or a verification-key set. `[R]` The finding is narrow and single: one value, one
reason, one fix.

---

## 4. Proposed amendment, for the owner

The fix narrows a ratified ruling, so it is the owner's. It makes
`ACC-FC5R-4` **stricter**, never looser.

```
Agent Constitution — ACC-FC5R-4 leak-review amendment
Baseline: rasaha/symbolu default head 65c90d31
Answer each with A or B. A = the recommended path.

LR-1  Whether to narrow ACC-FC5R-4's permitted set.
      A = yes. Replace the unqualified "public identifiers and digests" with an
          explicit list: gate name, closure date, responsible role, key_id, the
          issuing and approving authority ids, approval_ref, record_id, and the
          issued coordinate INCLUDING its content_digest. approval_digest is
          excluded by name, on the ground that its preimage is an external
          approval artifact of unknown entropy, which makes the digest a
          confirmation oracle for evidence ACC-FC5R-4 forbids.
      B = leave ACC-FC5R-4 as ratified; the owner accepts the exposure.

LR-2  Whether the exclusion is absolute.
      A = absolute. No approval-artifact digest enters the repository, whatever
          entropy the artifact is claimed to carry: an entropy claim cannot be
          checked from inside this repository, and the value is not needed for
          any purpose ACC-FC5R-2 names.
      B = conditional — admitted when the approval artifact is attested to
          carry a high-entropy nonce.

Record as: LR-1=? LR-2=?
No implementation is authorized by this ballot; the amendment belongs to the
ADR that records these answers.
```

---

## 5. Paste-ready independent-review prompt

```
Review this review, do not implement. Repository rasaha/symbolu at default head
65c90d31. Read docs/architecture/AGENT_CONSTITUTION_FC5_4_LEAK_REVIEW.md and
judge:

1. Is the finding right — is approval_digest's preimage genuinely lower-entropy
   than the coordinate's content_digest, and does that difference matter for a
   value committed to version control? Argue the strongest case that it does
   NOT, i.e. that a sha-256 is safe regardless of preimage.
2. Is the review COMPLETE? Name any value ACC-FC5R-4 or ACC-FC5R-2 permits that
   the §1 table omits, and any reconstruction path it missed — including
   combinations of two or more permitted values that leak more than each alone.
3. Is the §3 negative claim sound: does nothing in the permitted set expose key
   material or a trust root?
4. Does the §4 amendment narrow ACC-FC5R-4 without loosening anything?

Report findings labelled [V]/[I]/[R]/[G] with file:line support.
```

---

## 6. Verdict

`[R]` **Not clean; one material finding, with a narrowing fix.** `[V]` Nothing
has been committed under `ACC-FC5R-4`, so the defect is prospective and the
repository is presently uncompromised. `[G]` The open check the ratification
recorded stays open until the §4 ballot is answered — this review supplies the
analysis, not the ruling.
