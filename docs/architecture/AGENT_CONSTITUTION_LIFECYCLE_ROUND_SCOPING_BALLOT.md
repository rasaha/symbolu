# Agent Constitution — lifecycle round scoping ballot

**The load-bearing question:** can a ratified constitution be lawfully
**replaced or paused** — superseded, suspended — without this repository
acquiring lifecycle authority over agents or roles, and without any unsigned
authority decision? **Yes for supersession, and it is the smaller half.** The
authority already owns the acts that matter (issuance, revocation, resolution)
and already refuses to guess: an artifact that declares a predecessor is
refused at issuance rather than stored on a reference nothing can bind. What is
missing is a **reference shape a successor can lawfully carry**, and the signed
act that moves a predecessor's record out of the resolvable state. That is a
contract question, not an authority question. **Suspension is a different
animal** — it needs a state that does not exist in a ratified closed
vocabulary — and this ballot's recommended path separates the two rather than
bundling them.

**Status:** scoping/design ballot — documentation only. Nothing here is
implemented, and **no implementation is authorized by this ballot**; register
labels and any later authorization belong to the ratification ADR and to the
separate implementation-authority ruling that follows it. **Date:** 2026-08-31.

**Authorities this round sits under:** `OD-C1..OD-C5`, `ACC-S1-*`, `ACC-AM-*`,
`ACC-FC-*`, `ACC-IA-*` and `ACC-PR-*` as ratified.

**Why now:** `ACC-PR-5` ruled that the pilot commits a declaration and its
proof only, and that the lifecycle round — *structured supersession and
suspension, roadmap step 3* — was **not** commissioned by that ballot. The
pilot has since merged (`534cd5ac`), closing the "no role artifact exists" half
of the `ACC-FC-3` gap. This ballot convenes the round `ACC-PR-5` deferred.

---

## 0. Baseline verification

`[V]` Default branch `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`
head `534cd5ac` — the merge of PR #1543, which landed the `ACC-PR` ratification,
the `ACC-PR-IA` implementation-authority ruling and the invoice-reconciler pilot
change set. `[V]` Working tree clean at drafting time. `[V]` Agentic Proposer
`0.4.0`; Policy Authority `0.1.0`; all three constitution distributions `0.1.0`.

Facts this design leans on, each verified at this head:

* `[V]` **Supersession is refused, not deferred silently.** `supersedes_ref` is
  an unstructured `str` defaulting to `""`
  (`core/adapters.py:112`), and any non-empty value is rejected **before** the
  digest, before approval, before any clock read, before signing and before any
  registry access — `UnsupportedSupersessionError`, on the stated ground that
  the value "cannot bind a complete exact policy coordinate, and guessing one
  would be an unsigned authority decision" (`core/issuance.py:134-141`).
* `[V]` **Resolution fails closed on the same ground.** A legacy or
  hand-assembled record that declares supersession is denied with
  `SUPERSESSION_REFERENCE_UNSUPPORTED` rather than guessed at
  (`core/resolution.py:244-252`).
* `[V]` **Two lifecycle states exist with no act that reaches them.**
  `ADMITTED_LIFECYCLE_STATES` is the closed set `DRAFT`, `APPROVED_ACTIVE`,
  `SUPERSEDED`, `WITHDRAWN`, and `ACTIVE_LIFECYCLE_STATE` names
  `APPROVED_ACTIVE` as *the single lifecycle state the authority may resolve*
  (`identifiers.py:81-97`). No signed act transitions an issued record into
  `SUPERSEDED`.
* `[V]` **No suspension concept exists anywhere.** The substring `SUSPENDED`
  appears in no source file of the authority or the three constitution
  distributions. Revocation is terminal and carries five reason codes —
  `CONTENT_DEFECT`, `APPROVAL_WITHDRAWN`, `COMPLIANCE_VIOLATION`,
  `ISSUED_IN_ERROR`, `REPLACED` (`core/statuses.py:133-145`) — and policy
  revocation, key revocation and envelope revocation imply nothing about each
  other.
* `[V]` **The activation layer holds no seam to widen.** It "holds no
  revocation seam" by ruling, and takes no role or agent lifecycle authority
  (`agent-constitution-activation/public_api.json`, `composition.py:25`).

Stop condition for the eventual implementation: any of these failing at
implementation time halts the change set.

---

## 1. What this round lawfully is — and is not

**It is a contract round over policy-version lifecycle.** A constitution is a
signed, versioned, revocable artifact; asking how one version replaces another
is asking about *that artifact's* lifecycle, and nothing else.

**It is not, and cannot become, lifecycle authority over agents or roles.**
`OD-C4=A` stands untouched: nothing this round contemplates writes or
transitions an agent lifecycle state, suspends, revokes or offboards an agent,
or mints, changes or ends a role. The word "lifecycle" appears on both sides of
that line and means different things; this round sits wholly on the policy side.
`[R]` The distinction is the round's own boundary, not a disclaimer appended to
it: a design that needed to touch a role or an agent to express supersession
would be out of scope by construction.

**It is not the `/clauses/v2` vocabulary round.** No clause content beyond the
three structural bounds is ratified here, so `ACC-AM-4`'s re-derivation re-arm
stays untriggered.

**It grants nothing.** No compute, tools, evidence access or consequential
execution follows from any ruling below.

---

## 2. The gap, stated precisely

Today a v2 constitution cannot say what it replaces. The only available path to
replacing the ratified v1 is two unlinked acts — issue the successor, then
revoke the predecessor (`REPLACED` is among the reason codes) — with **no
signed statement connecting them**. An auditor reading the registry sees a
revocation and an issuance and must infer the relationship from timing and
content. That inference is exactly what the authority refuses to make on its own
behalf at issuance; it should not be forced on the reader either.

`[I]` The refusal is the right refusal. An unstructured string cannot name an
exact policy version — `policy_id`, `version`, `scope` and `tenant_id` together
are what resolution binds — so accepting one would either store an unbindable
reference or make the authority guess a coordinate it was never given. This
round's work is to supply the shape, not to relax the check.

---

## 3. Design sketch (what the recommended path would build)

Sketched to make the ballot answerable; **nothing here is ratified by
appearing in this section**, and the rows below are what bind.

* A **structured successor reference** carrying an exact predecessor
  coordinate, reusing the coordinate type resolution already binds rather than
  minting a parallel identity notion. Empty remains the default and the
  overwhelmingly common case, so every artifact already issued or issuable
  stays valid and every existing refusal path keeps its meaning for
  unstructured values.
* **One signed act, not two.** The successor declares its predecessor at its own
  issuance; the same signed act that admits the successor transitions the
  predecessor's record to `SUPERSEDED`. A record never leaves the resolvable
  state by an unsigned edit.
* **The predecessor stops resolving and stays readable.** `SUPERSEDED` is
  already outside `ACTIVE_LIFECYCLE_STATE`, so resolution refuses it with the
  authority's own lifecycle reason — no new refusal vocabulary is needed, and
  the historical record remains legible.
* **Fail-closed asymmetry preserved:** a successor naming a predecessor that
  does not exist, is not resolvable, or sits in another tenant or scope is
  refused before anything is signed or stored.

---

## 4. Owner-decision register (five)

| Row | Question | Recommended (A) | Alternative (B) |
|---|---|---|---|
| `LC-1` | The successor reference's **shape** | replace the unstructured `supersedes_ref: str` with a **structured reference binding an exact policy coordinate** (`policy_id`, `version`, `scope`, `tenant_id`), reusing the coordinate type resolution binds; empty stays the default and no already-valid artifact is invalidated | keep the string and add a parser that must resolve it to an exact coordinate, refusing anything it cannot parse |
| `LC-2` | Which **act** performs supersession | the successor declares its predecessor **at its own issuance**, and that one signed act both admits the successor and transitions the predecessor to `SUPERSEDED`; no unsigned edit ever moves a record | a **separate signed supersession act**, distinct from issuance, on `revoke_policy`'s precedent |
| `LC-3` | Whether **suspension** belongs to this round | **no** — this round settles supersession only; suspension is deferred to its own round, because a reversible pause needs a state that is not in the ratified closed set `ADMITTED_LIFECYCLE_STATES`, which makes it a vocabulary act rather than a mechanics act | settle both now: this round also introduces a reversible suspended state with its own signed suspend and reinstate acts |
| `LC-4` | **Where** the mechanics live | the **shared Policy Authority**, family-neutral, beside the issuance, revocation and resolution it extends; the constitution family and the activation root gain no new seam and no new public name | a constitution-family-local mechanism, leaving the shared authority untouched |
| `LC-5` | What this round **commits** | **contract, design and ratification only** — documentation, no source change; the implementation is a separate change set authorized by the ruling that follows, on the `ACC-FC-5` / `ACC-PR` precedent | additionally authorize the implementation change set now, in one round |

Couplings, disclosed: `LC-1` and `LC-2` interact — a structured reference
(`LC-1=A`) is what makes the single-act path (`LC-2=A`) expressible, and
`LC-1=B` weakens it, since a parsed string must still be validated at the same
points. `LC-3=B` widens `LC-1` and `LC-4` to cover a state transition that has
no successor reference at all. No other pair interacts.

`[R]` **The bite of `LC-3=A`, disclosed:** choosing it means an operator whose
approval is questioned but not withdrawn still has only the terminal
instrument — revoke and re-issue. That is a real cost, accepted deliberately,
on the ground that extending a ratified closed vocabulary deserves its own
round rather than riding in on a mechanics change.

---

## 5. The fixed surface put to ratification

Ratified whole alongside the rows, with the standing precedence rule: **where
an `LC` row and this surface overlap, the `LC` ruling governs.**

The round is a contract and design act over **policy-version lifecycle only**:
no new authority is created and no existing authority's bounds move; `OD-C4=A`
holds untouched — no agent or role lifecycle authority is taken, implied or
prepared for; `OD-C3=B` holds — no verifier emits a disposition or reserved
authority term; no signing key, trust root or approval artifact enters the
repository, and no issuance, revocation or supersession is performed by any
document of this round; no already-valid artifact is invalidated and no
existing refusal is relaxed — the unstructured value keeps being refused;
`/clauses/v2` stays out of scope and `ACC-AM-4`'s re-arm stays untriggered; no
agent runs, is enrolled or is claimed governed. **YES/NO.**

---

## 6. Paste-ready owner-ratification ballot

```
Agent Constitution — lifecycle round scoping ballot
Baseline: rasaha/symbolu default head 534cd5ac
Governed by OD-C1..OD-C5, ACC-S1-*, ACC-AM-*, ACC-FC-*, ACC-IA-* and ACC-PR-*
as ratified. Answer each with A or B. A = the recommended path.

LIFECYCLE_SURFACE  Ratify the fixed surface: this is a contract and design act
      over policy-version lifecycle only — no new authority, no movement of any
      existing authority's bounds; OD-C4=A holds untouched (no agent or role
      lifecycle authority is taken, implied or prepared for); OD-C3=B holds; no
      signing key, trust root or approval artifact enters the repository and no
      issuance, revocation or supersession is performed; no already-valid
      artifact is invalidated and no existing refusal is relaxed; /clauses/v2
      stays out of scope and ACC-AM-4's re-arm stays untriggered; no agent runs,
      is enrolled or is claimed governed — with the precedence rule: where an LC
      row and this surface overlap, the LC ruling governs.  YES/NO.

LC-1  The successor reference's shape.
      A = replace the unstructured supersedes_ref: str with a structured
          reference binding an exact policy coordinate (policy_id, version,
          scope, tenant_id), reusing the coordinate type resolution already
          binds; empty stays the default and no already-valid artifact is
          invalidated.
      B = keep the string and add a parser that must resolve it to an exact
          coordinate, refusing anything it cannot parse.

LC-2  Which act performs supersession.
      A = the successor declares its predecessor at its own issuance, and that
          one signed act both admits the successor and transitions the
          predecessor to SUPERSEDED; no unsigned edit ever moves a record.
      B = a separate signed supersession act, distinct from issuance, on
          revoke_policy's precedent.

LC-3  Whether suspension belongs to this round.
      A = no — this round settles supersession only; suspension is deferred to
          its own round, because a reversible pause needs a state absent from
          the ratified closed set ADMITTED_LIFECYCLE_STATES, which makes it a
          vocabulary act rather than a mechanics act. Bite: until that round,
          an operator whose approval is questioned but not withdrawn has only
          the terminal instrument.
      B = settle both now: this round also introduces a reversible suspended
          state with its own signed suspend and reinstate acts.

LC-4  Where the mechanics live.
      A = the shared Policy Authority, family-neutral, beside the issuance,
          revocation and resolution it extends; the constitution family and the
          activation root gain no new seam and no new public name.
      B = a constitution-family-local mechanism, leaving the shared authority
          untouched.

LC-5  What this round commits.
      A = contract, design and ratification only — documentation, no source
          change; the implementation is a separate change set authorized by the
          ruling that follows, on the ACC-FC-5 / ACC-PR precedent.
      B = additionally authorize the implementation change set now.

Record as: LIFECYCLE_SURFACE=? LC-1=? LC-2=? LC-3=? LC-4=? LC-5=?
No implementation is authorized by this ballot; register labels and the
implementation-authority ruling belong to the ratification ADR that records
these answers and to the separate ruling that follows it.
```

---

## 7. Paste-ready independent-review prompt

```
Review, do not implement. Repository rasaha/symbolu at default head 534cd5ac.
Read docs/architecture/AGENT_CONSTITUTION_LIFECYCLE_ROUND_SCOPING_BALLOT.md and
judge three things against the repository, not against the document's own
account of itself:

1. Are §0's verified facts true at this head — the issuance-time refusal of a
   non-empty supersedes_ref, the resolution-time denial, the closed lifecycle
   set with only APPROVED_ACTIVE resolvable, the total absence of a suspension
   concept, and the activation layer's lack of a revocation seam?
2. Is the LC-3 recommendation (defer suspension) right, or does splitting the
   round leave the repository in a worse intermediate state than settling both
   at once? Argue the strongest case for B.
3. Does any option on any row, if ruled, require touching a role or an agent —
   which would breach OD-C4=A and put the round out of its own scope?

Report findings labelled [V]/[I]/[R]/[G] with file:line support. Name any row
whose A and B are not genuinely exclusive, or whose recommendation the
repository does not support.
```

---

## 8. Readiness verdict

`[R]` **Ready to put.** The five rows are mutually exclusive within each row,
the one real coupling is disclosed, and each recommendation is supported by a
verified fact at §0 rather than by preference. `[G]` The round leaves
suspension open by design under `LC-3=A`, and says so in the row itself rather
than in a footnote. Nothing here is implemented, and no implementation is
authorized by this document.
