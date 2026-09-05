# Agent Constitution — family supersession opt-in scoping ballot

**The load-bearing question:** the shared authority can now supersede one policy
version with another; **can the Agent Constitution family use it?** **Not
today.** `ACC-LC-IA-2` shipped the mechanism in Policy Authority `0.2.0`, but a
successor declares its predecessor through
`PolicyArtifactDescriptor.supersedes_coordinate`, and **no shipped adapter
produces one**. This family's adapter passes only the unstructured
`supersedes_ref` — the value the authority refuses before anything is signed. So
a v2 constitution still cannot say what it replaces, which is the exact gap the
`ACC-LC` round set out to close. This round decides how the family opts in.

**The one hard question inside it:** a constitution's body digest covers **every
metadata field except `content_digest`**, so a new metadata field changes the
digest of every constitution — including the ratified v1 content, whose identity
`ACC-FC-2` fixed. Opting in naively would move a ratified value. `AC-SU-2`
exists so that is a chosen outcome, not an accident.

**Status:** scoping/design ballot — documentation only. Nothing here is
implemented, and **no implementation is authorized by this ballot**; register
labels and any later authorization belong to the ratification ADR and to the
separate implementation-authority ruling that follows it. **Date:** 2026-08-31.

**Authorities this round sits under:** `OD-C1..OD-C5`, `ACC-S1-*`, `ACC-AM-*`,
`ACC-FC-*`, `ACC-IA-*`, `ACC-PR-*` and `ACC-LC-*` as ratified.

---

## 0. Baseline verification

`[V]` Default branch head `9c981dd9`, clean working tree, at or after
`9c616ac9` — the merge of PR #1547, which shipped structured supersession.
`[V]` Policy Authority `0.2.0`; Agentic Proposer `0.4.0`; all three
constitution distributions `0.1.0`, the family exposing 27 public names.

Facts this design leans on, each verified at this head:

* `[V]` **The family cannot declare a predecessor.**
  `AgentConstitutionPolicyFamilyAdapter.describe` passes
  `supersedes_ref=metadata.supersedes_ref` and sets no
  `supersedes_coordinate` (`adapter.py:144`); the metadata carries only the
  unstructured string (`policy.py:223`). A repository-wide search finds
  `supersedes_coordinate` **only** inside the authority core — no shipped
  adapter anywhere produces one.
* `[V]` **The unstructured string is refused, by design.** A non-empty
  `supersedes_ref` is rejected at issuance step 4 before the digest, approval,
  clock, signing and any registry access
  (`policy-authority/core/issuance.py:150-157`). Opting in must therefore add a
  *structured* path, never relax that refusal.
* `[V]` **Every metadata field is inside the body digest.** The family's
  canonical projection removes *exactly* `metadata.content_digest`
  (`adapter.py:153`, `_canonical_projection`); the digested projection's metadata
  keys are `effective_from`, `effective_to`, `lifecycle_state`, `policy_id`,
  `scope`, `supersedes_ref`, `tenant_id`, `version`. Measured this session:
  adding one further metadata key changes the digested bytes. **A new field
  that enters the projection moves every constitution's digest.**
* `[V]` **Supersession requires an issued, resolvable predecessor.**
  `ACC-LC-IA-3`'s refusals include an absent predecessor, so the act is
  unexercisable until a constitution has actually been issued — which the
  `ACC-FC-5` deployment gates still hold shut.

Stop condition for the eventual implementation: any of these failing at
implementation time halts the change set.

---

## 1. What this round lawfully is — and is not

**It is a contract round over one policy family's artifact shape.** It decides
how a constitution names the version it replaces, and nothing more.

**It is not a new authority, and not a change to the shipped mechanism.**
`ACC-LC-IA-1` – `ACC-LC-IA-5` stand as ruled; the authority is not reopened by
any option on the recommended path.

**It is not `OD-C4` territory.** `OD-C4=A` holds untouched: nothing here writes
or transitions an agent lifecycle state, or mints, changes or ends a role. A
constitution superseding a constitution is policy-version lifecycle, exactly as
`ACC-LC-BASE` recorded.

**It issues nothing.** `ACC-FC-5`'s gates are untouched and no constitution is
issued, superseded or revoked by any document or change set of this round.

---

## 2. Owner-decision register (five)

| Row | Question | Recommended (A) | Alternative (B) |
|---|---|---|---|
| `AC-SU-1` | Where the structured predecessor **lives** | a new field on `AgentConstitutionPolicyMetadata` carrying the exact predecessor coordinate, which the adapter maps into `supersedes_coordinate` — the artifact states what it replaces, as `supersedes_ref` always intended | the predecessor is supplied **at issuance** as a caller argument, leaving the artifact contract untouched. Cost: the authority takes its predecessor from the descriptor today, so this reopens `ACC-LC-IA-1` and the shipped mechanism |
| `AC-SU-2` | Whether the ratified **v1 identity** moves | **no** — the new field is excluded from the canonical projection, on the same ground `content_digest` is: what a version replaces is a claim about the registry, not part of the bytes it is identified by. Every existing digest, the ratified v1 content's included, is unmoved and `ACC-FC-2` is untouched | accept the digest move and **re-ratify** `ACC-FC-2`'s identity values, since the ratified content would then digest differently |
| `AC-SU-3` | **Proof** scope | three legs: a **digest-invariance** proof that the ratified v1 content's body digest is byte-identical before and after the change; a v2-supersedes-v1 chain driven through the shipped authority on ephemeral in-process keys; and the six `ACC-LC-IA-3` refusals re-driven over this family | the chain leg only; invariance and refusals deferred |
| `AC-SU-4` | Which **distributions and versions** move | `agent-constitution-policy` only — minor bump, `public_api.json` regenerated if the surface grows, CHANGELOG note; the conformance and activation distributions and the Policy Authority are **untouched**. The implementation-authority ballot must first **enumerate every consumer** of this family's artifact shape and closed vocabularies, harnesses included (`ACC-LC-IA-BASE-A1`) | the owner names a wider set now |
| `AC-SU-5` | What the round **commits** | contract, design and ratification only — documentation, no source change; implementation is a separate change set under the ruling that follows, on the `ACC-FC-5` / `ACC-PR` / `ACC-LC` precedent | additionally authorize the implementation change set now |

Couplings, disclosed: `AC-SU-1` and `AC-SU-2` interact — `AC-SU-1=B` puts
nothing in the artifact, so the digest question does not arise and `AC-SU-2`
becomes moot; that is the only route by which `B` on the first row is cheaper,
and it is paid for by reopening the shipped authority. `AC-SU-3`'s invariance
leg exists only under `AC-SU-1=A`. No other pair interacts.

`[G]` **The bite of the recommended path, disclosed:** opting in grants the
*ability to declare* a predecessor. It does not make supersession exercisable —
`ACC-LC-IA-3` refuses an absent predecessor, and no constitution has been
issued, because the `ACC-FC-5` deployment gates are still shut. This round
closes a contract gap, not an operational one.

---

## 3. The fixed surface put to ratification

Ratified whole alongside the rows, with the standing precedence rule: **where an
`AC-SU` row and this surface overlap, the `AC-SU` ruling governs.**

This is a contract and design act over one family's artifact shape: no new
authority, and the shipped supersession mechanism is not reopened on the
recommended path; `OD-C4=A` holds untouched — no agent or role lifecycle
authority is taken, implied or prepared for; `OD-C3=B` holds; no signing key,
trust root or approval artifact enters the repository, and no issuance,
revocation or supersession is performed by any document or change set of this
round; **no existing artifact is invalidated and no existing refusal is
relaxed** — the unstructured `supersedes_ref` keeps being refused exactly as
today; no agent runs, is enrolled or is claimed governed; suspension stays
unimplemented and its round uncommissioned (`ACC-LC-3`); `/clauses/v2` stays out
of scope and `ACC-AM-4`'s re-arm stays untriggered. **YES/NO.**

---

## 4. Paste-ready owner-ratification ballot

```
Agent Constitution — family supersession opt-in scoping ballot
Baseline: rasaha/symbolu default head 9c981dd9 (at or after 9c616ac9)
Governed by OD-C1..OD-C5, ACC-S1-*, ACC-AM-*, ACC-FC-*, ACC-IA-*, ACC-PR-* and
ACC-LC-* as ratified. Answer each with A or B. A = the recommended path.

AC_SU_SURFACE  Ratify the fixed surface: a contract and design act over one
      family's artifact shape — no new authority, and the shipped supersession
      mechanism is not reopened on the recommended path; OD-C4=A holds untouched
      (no agent or role lifecycle authority is taken, implied or prepared for);
      OD-C3=B holds; no signing key, trust root or approval artifact enters the
      repository and no issuance, revocation or supersession is performed; no
      existing artifact is invalidated and no existing refusal is relaxed — the
      unstructured supersedes_ref keeps being refused; no agent runs, is
      enrolled or is claimed governed; suspension stays unimplemented and its
      round uncommissioned (ACC-LC-3); /clauses/v2 stays out of scope and
      ACC-AM-4's re-arm stays untriggered — with the precedence rule: where an
      AC-SU row and this surface overlap, the AC-SU ruling governs.  YES/NO.

AC-SU-1  Where the structured predecessor lives.
      A = a new field on AgentConstitutionPolicyMetadata carrying the exact
          predecessor coordinate, which the adapter maps into the descriptor's
          supersedes_coordinate. The artifact states what it replaces.
      B = the predecessor is supplied at issuance as a caller argument, leaving
          the artifact contract untouched. Cost: the authority takes its
          predecessor from the descriptor today, so this reopens ACC-LC-IA-1
          and the shipped mechanism.

AC-SU-2  Whether the ratified v1 identity moves.
      A = no — the new field is excluded from the canonical projection, on the
          same ground content_digest is: what a version replaces is a claim
          about the registry, not part of the bytes it is identified by. Every
          existing digest, the ratified v1 content's included, is unmoved and
          ACC-FC-2 is untouched.
      B = accept the digest move and re-ratify ACC-FC-2's identity values.

AC-SU-3  Proof scope.
      A = three legs: a digest-invariance proof that the ratified v1 content's
          body digest is byte-identical before and after; a v2-supersedes-v1
          chain driven through the shipped authority on ephemeral in-process
          keys; and the six ACC-LC-IA-3 refusals re-driven over this family.
      B = the chain leg only; invariance and refusals deferred.

AC-SU-4  Which distributions and versions move.
      A = agent-constitution-policy only — minor bump, public_api.json
          regenerated if the surface grows, CHANGELOG note; the conformance and
          activation distributions and the Policy Authority are untouched. The
          implementation-authority ballot must first enumerate every consumer
          of this family's artifact shape and closed vocabularies, harnesses
          included (ACC-LC-IA-BASE-A1).
      B = the owner names a wider set now.

AC-SU-5  What the round commits.
      A = contract, design and ratification only — documentation, no source
          change; implementation is a separate change set under the ruling that
          follows.
      B = additionally authorize the implementation change set now.

Record as: AC_SU_SURFACE=? AC-SU-1=? AC-SU-2=? AC-SU-3=? AC-SU-4=? AC-SU-5=?
No implementation is authorized by this ballot; register labels and the
implementation-authority ruling belong to the ratification ADR that records
these answers and to the separate ruling that follows it.
```

---

## 5. Paste-ready independent-review prompt

```
Review, do not implement. Repository rasaha/symbolu at default head 9c981dd9.
Read docs/architecture/AGENT_CONSTITUTION_FAMILY_SUPERSESSION_OPT_IN_SCOPING_BALLOT.md
and judge four things against the repository, not against the document:

1. Are §0's facts true — that no shipped adapter produces supersedes_coordinate,
   that the unstructured supersedes_ref is refused at issuance step 4, that the
   family's canonical projection removes exactly metadata.content_digest, and
   that adding a metadata key therefore changes the body digest?
2. AC-SU-2=A excludes the new field from the digest. Is that sound, or does a
   constitution's claim about what it supersedes belong inside the bytes it is
   identified by? Argue the strongest case for B, including what an auditor
   loses when the claim is unsigned content.
3. Does AC-SU-1=B (predecessor as an issuance argument) really reopen
   ACC-LC-IA-1, or could it be added without touching the shipped authority?
4. Does any option, if ruled, touch a role or an agent (OD-C4=A), relax the
   unstructured refusal, or invalidate an already-valid artifact?

Report findings labelled [V]/[I]/[R]/[G] with file:line support. Name any row
whose A and B are not genuinely exclusive, or whose recommendation the
repository does not support.
```

---

## 6. Readiness verdict

`[R]` **Ready to put.** Each recommendation rests on a fact verified at §0
rather than on preference, the one genuine coupling is disclosed, and the
round's real cost — that opting in still leaves supersession unexercisable until
the `ACC-FC-5` gates are closed — is stated in the register rather than in a
footnote. `[G]` `AC-SU-2` is the row where being wrong is expensive: it decides
whether a ratified identity value moves, and §5 asks a reviewer to argue against
the recommendation rather than to confirm it.
