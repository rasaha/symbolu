# Agent Constitution — `/clauses/v2` round scoping ballot

**The load-bearing question:** `/clauses/v2` has been "not commissioned" since
`ACC-FC-5`. Convening it costs more than one round, and the ballot's job is to
say so before the owner answers. **Ratifying clause content beyond the three
structural bounds re-arms `ACC-AM-4`** — `[V]` an obligation ruled *"not
discharged"*, which *"re-arms the first time clause content beyond the three
structural bounds is ratified, at which point re-derivation gets its own round."*
So `/clauses/v2` is not a vocabulary round with a re-derivation footnote; it is
**two rounds, and the second is triggered by the first**.

**What is new since the deferral, and makes this tractable at all:** a v2
constitution can now *declare what it replaces*. `[V]` The authority carries
structured supersession (`ACC-LC-IA-*`) and the family produces the predecessor
coordinate (`ACC-SU-IA-*`). `/clauses/v2` would be the **first artifact in this
repository with a genuine use for that machinery** — authored as a successor to
the ratified v1, even though `[G]` neither can be issued while the `ACC-FC-5`
gates are shut.

**Status:** scoping/design ballot — documentation only. **No implementation is
authorized, no clause content is ratified, and `ACC-AM-4` is not re-armed by
this ballot** — only by a later ruling that actually ratifies clause content.
**Date:** 2026-09-01.

**Authorities:** `OD-C1..OD-C5`, `ACC-S1-*`, `ACC-AM-*`, `ACC-FC-*`, `ACC-IA-*`,
`ACC-PR-*`, `ACC-LC-*`, `ACC-SU-*` and `ACC-FC5R-*` as ratified.

---

## 0. Baseline, and what convening this actually triggers

`[V]` Default head `65c90d31`, clean tree. Policy Authority `0.2.0`;
`agent-constitution-policy` `0.2.0`; conformance and activation `0.1.0`.

* `[V]` **The v1 content is three structural bounds and nothing else**
  (`ACC-FC-4`): the disposition vocabulary, the review-action vocabulary, and the
  tool-scope ceiling. "Clause content" means anything a constitution says beyond
  those three.
* `[V]` **`ACC-AM-4` re-arms on the first such ratification**, and its ground is
  specific: *"the projection's field set is not derivable from bounds alone"*.
  Re-derivation then *"gets its own round"*. `[R]` Nothing in this repository may
  be read as evidence that the proposer's projection anticipates the
  constitution correctly.
* `[V]` **A successor can now be declared.** `supersedes_coordinate` exists on
  the family's metadata and is carried to the descriptor, and the authority
  admits a successor in one signed act — so a v2 is expressible as a *successor
  to v1*, not merely as a second document.
* `[G]` **Neither can be issued.** `ACC-LC-IA-3` refuses an absent predecessor,
  and v1 has never been issued because the `ACC-FC-5` gates are shut. A v2
  authored today is authored text with a signed future, exactly as v1 is.

`[I]` **The consequence for sequencing.** If v2 is authored *as a successor*,
its predecessor coordinate must name v1's **exact** coordinate — including a
`content_digest` that only exists once v1's content is fixed. That is available
today (v1's content is ratified), but it means a v2 that supersedes v1 pins v1's
digest permanently, and any later change to v1's content would orphan it.

---

## 1. Owner-decision register (five)

| Row | Question | Recommended (A) | Alternative (B) |
|---|---|---|---|
| `CV2-1` | Whether to commission the round **at all, now** | **not yet.** Defer until at least one `ACC-FC-5` gate is closed. Every capability this arc built is unexercisable, and clause content is the one addition that would also **re-arm `ACC-AM-4`** and commit a second round. Deferring costs nothing that is not already costless | commission it now, accepting that it triggers the re-derivation round while nothing can be issued |
| `CV2-2` | If commissioned, whether v2 is authored **as a successor to v1** | yes — a v2 declares `supersedes_coordinate` naming v1's exact coordinate, which is the first genuine use of the `ACC-LC`/`ACC-SU` machinery. Disclosed: it pins v1's `content_digest` permanently | v2 is authored as an independent document, with supersession left to issuance time |
| `CV2-3` | How the **`ACC-AM-4` re-derivation** round is sequenced | **before** clause content is ratified: re-derivation is scoped and ruled first, so the projection's field set is settled against the clause content that is *proposed*, not retrofitted to content already ratified | after, or concurrently |
| `CV2-4` | What **counts** as clause content, for the purpose of the re-arm | ruled **explicitly in the ratification**, not left to reading: any constitution field that is not one of the three structural bounds, the identity fields, or the governed-role references. The re-arm is mechanical once the definition is written down | left to be argued when the first clause is proposed |
| `CV2-5` | What this round **commits** | scoping only — this ballot commissions nothing by being answered; a `YES` on `CV2-1=B` would itself require a further content ballot before any clause text is ratified | the answer to `CV2-1=B` also authorizes drafting the v2 content specification |

Couplings, disclosed: `CV2-1` gates the rest — if it is ruled `A` (defer), rows
`CV2-2` to `CV2-5` are recorded as *pre-settled for whenever the round is
convened*, not as immediately operative. That is the point of answering them
now: the round arrives with its shape already decided.

`[G]` **The bite of `CV2-1=A`, disclosed:** deferring leaves the constitution at
three structural bounds indefinitely. If clause content is what makes the
constitution *useful* rather than merely well-formed, deferring postpones the
value, not just the work.

---

## 2. The fixed surface put to ratification

Ratified whole, with the precedence rule: **where a `CV2` row and this surface
overlap, the row governs.**

This is a scoping act. **No clause content is ratified and `ACC-AM-4` is not
re-armed by this document or by any answer to it** — the re-arm is triggered only
by a later ruling that ratifies clause content. No constitution is authored,
issued, superseded, suspended or revoked; `OD-C4=A` and `OD-C3=B` hold; no
signing key, trust root or approval artifact enters the repository; no
already-valid artifact is invalidated, no existing refusal relaxed and no
existing digest moved — in particular **v1's ratified content and digest are
untouched**; suspension stays unimplemented (`ACC-LC-3`); the `ACC-FC-5` gates
are neither closed nor advanced; no agent runs, is enrolled or is claimed
governed. **YES/NO.**

---

## 3. Paste-ready owner-ratification ballot

```
Agent Constitution — /clauses/v2 round scoping ballot
Baseline: rasaha/symbolu default head 65c90d31
Governed by OD-C1..OD-C5, ACC-S1-*, ACC-AM-*, ACC-FC-*, ACC-IA-*, ACC-PR-*,
ACC-LC-*, ACC-SU-* and ACC-FC5R-* as ratified. Answer each with A or B.
A = the recommended path.

CV2_SURFACE  Ratify the fixed surface: a scoping act. No clause content is
      ratified and ACC-AM-4 is NOT re-armed by this document or by any answer to
      it -- the re-arm is triggered only by a later ruling that ratifies clause
      content. No constitution is authored, issued, superseded, suspended or
      revoked; OD-C4=A and OD-C3=B hold; no signing key, trust root or approval
      artifact enters the repository; no already-valid artifact is invalidated,
      no existing refusal relaxed and no existing digest moved -- in particular
      v1's ratified content and digest are untouched; suspension stays
      unimplemented (ACC-LC-3); the ACC-FC-5 gates are neither closed nor
      advanced; no agent runs, is enrolled or is claimed governed -- with the
      precedence rule: where a CV2 row and this surface overlap, the CV2 ruling
      governs.  YES/NO.

CV2-1  Whether to commission the round at all, now.
      A = not yet. Defer until at least one ACC-FC-5 gate is closed. Every
          capability this arc built is unexercisable, and clause content is the
          one addition that would also re-arm ACC-AM-4 and commit a second
          round. Bite: this leaves the constitution at three structural bounds
          indefinitely, postponing the value and not only the work.
      B = commission now, accepting that it triggers the re-derivation round
          while nothing can be issued.

CV2-2  If commissioned, whether v2 is authored as a successor to v1.
      A = yes -- v2 declares supersedes_coordinate naming v1's exact coordinate,
          the first genuine use of the ACC-LC/ACC-SU machinery. Disclosed: this
          pins v1's content_digest permanently.
      B = v2 is an independent document; supersession is left to issuance time.

CV2-3  How the ACC-AM-4 re-derivation round is sequenced.
      A = before clause content is ratified, so the projection's field set is
          settled against proposed content rather than retrofitted to ratified
          content.
      B = after, or concurrently.

CV2-4  What counts as clause content, for the purpose of the re-arm.
      A = ruled explicitly: any constitution field that is not one of the three
          structural bounds, the identity fields, or the governed-role
          references. The re-arm is mechanical once written down.
      B = left to be argued when the first clause is proposed.

CV2-5  What this round commits.
      A = scoping only. Answering commissions nothing; CV2-1=B would still
          require a further content ballot before any clause text is ratified.
      B = CV2-1=B also authorizes drafting the v2 content specification.

Record as: CV2_SURFACE=? CV2-1=? CV2-2=? CV2-3=? CV2-4=? CV2-5=?
No implementation is authorized by this ballot, and no clause content is
ratified by it.
```

---

## 4. Paste-ready independent-review prompt

```
Review, do not implement. Repository rasaha/symbolu at default head 65c90d31.
Read docs/architecture/AGENT_CONSTITUTION_CLAUSES_V2_ROUND_SCOPING_BALLOT.md and
judge:

1. Is the re-arm claim right -- does ratifying clause content beyond the three
   structural bounds trigger ACC-AM-4, and does that obligation genuinely
   require its own round? Quote the ruling.
2. CV2-1=A recommends deferring. Argue the strongest case AGAINST: is a
   constitution of three structural bounds and no clause content actually
   useful, and does deferring compound a debt rather than avoid one?
3. Does CV2-2=A's permanent pin of v1's content_digest create a hazard if v1's
   content is ever amended? Walk the failure.
4. Does anything in this ballot ratify clause content, re-arm ACC-AM-4, or move
   v1's digest -- which the surface forbids?

Report findings labelled [V]/[I]/[R]/[G] with file:line support.
```

---

## 5. Readiness verdict

`[R]` **Ready to put, and its recommendation is to wait.** `[G]` This is the one
round in the arc whose recommended answer is *not yet*: it is the only remaining
work that would commit a second round (`ACC-AM-4`'s re-derivation) on top of
capability that still cannot be exercised. `CV2-1`'s bite is stated in the row —
deferring postpones the constitution's substance, not merely its paperwork — and
§4 asks a reviewer to argue against the deferral rather than for it.
