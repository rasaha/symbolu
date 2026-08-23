# BR-2C — D-38 independent review brief

**Status: NOT YET PERFORMED.** No review under ADR §35.2 D-38 has been
commissioned, begun or obtained, and nothing in this document records one. This
is the brief a distinct independent authority would be handed *before* any
capability-bearing BR-2C release. Until such a review is obtained and recorded,
`0.3.0` is blocked, and no artifact of this distribution describes any verifier
as audited, independently reviewed or production-ready.

**Authored at `6b805691`, rung `BR-2C-0`, `package_version` `0.2.3`.**

## Two limitations, stated first because they bear on how this brief is used

**No `0.3.0` head exists** [V]. D-38 binds the reviewer to *the exact release
head*, and BR-2C verifier engineering has not begun — D-32(3) leaves the
engineering half of §35.1's blocker standing in full. Everything below is
derived from `BR-2C-0`, the contract-only rung. The reviewer re-derives it
against the head they are actually given; where this brief and that head
disagree, the head wins.

**This brief shares an author with the row it serves** [G]. D-38 exists because
the same authorship was wrong twice on this boundary: D-37's ground was
falsified by the fourth audit, and §35.2's citation-exception paragraph
described a discipline that was not kept. A reviewer who accepts this checklist
as the scope of their review inherits whatever blind spot produced those two.
**The reviewer is expected to scope their own review and to record what they
asked for that this brief did not.** This document is a starting inventory, not
a definition of sufficiency.

## What D-38 requires, as ratified

D-38 requires a **distinct independent authority** — explicitly not the owner,
and not this or any prior audit of a contract-only rung — to review and
adversarially audit the exact release head, confirming both:

- **(i)** that **only ratified** parsing, verification and trust-resolution
  capabilities ship; and
- **(ii)** that **changing the prohibition list cannot self-authorize** a new
  capability.

D-38 is **not** D-32(4). D-32(4) is an external cryptographic audit of the
verifier and a precondition to **production use**. D-38 is a distinct
independent reviewer of the release head and a precondition to **shipping at
all**. Satisfying either leaves the other outstanding. D-38 amends D-32(1) and
(2), whose distinct-reviewer waiver survives only for `BR-2C-0`; D-32(3), (5)
and (6) are unamended.

## D-38(i) — only ratified capabilities ship

"Ratified" is not open to the implementer's judgement: it is the set fixed by
§35.1's BR-2C row and the §35.2 rows that rule the seam. The reviewer confirms
that what ships is a subset of this, and that nothing ships which is not.

**Ratified to ship at BR-2C** [V], from §35.1's BR-2C row and D-24, D-25, D-26,
D-28, D-34 and D-35:

| Capability | Ratified shape | Ruling row |
|---|---|---|
| Verification seams | Three **distinct exact verified-result types** for the publisher, approval and revocation seams; each binds artifact or envelope digest, signer role, signer identity, key identifier, signature profile, anchor-record digest, evaluation time, outcome and refusal reason. A `bool` return is ratified **out**. | D-24 |
| Trust resolution | An **immutable role-scoped anchor record**, not a predicate. The **anchor revision is that record's canonical digest**; no parallel revision counter. | D-25 |
| Role separation | Publisher, approver and revoker occupy **logically separate role-scoped anchor namespaces**; one physical directory may serve all three, but an anchor authorized for one role **never** authorizes another. | D-26 |
| Resolution outcome | `BenchmarkTrustAnchorResolution` carries **exactly one** of an anchor record or a typed refusal, enforced in `__post_init__`; the seam performs **no lifecycle evaluation** and takes no trusted instant, and may carry only `TRUST_ANCHOR_NOT_FOUND` and `TRUST_DIRECTORY_UNAVAILABLE`. | D-34 |
| Refusal vocabulary | A `REFUSED` verified result carries one of the **twelve** admissible reasons — the `TRUST_AND_AUTHENTICITY` fault class plus `INDETERMINATE` — and nothing else. | D-35 |
| Anchor lifecycle | The `TRUST_ANCHOR_*` states are the **verification** seam's to decide, on D-28's published evaluation order. | D-28 |

**Ratified NOT to ship at BR-2C** [V]: §35.1's BR-2C row forbids "any storage,
and any registry state whatsoever". D-01 keeps BR-2D the first phase permitted
to assert that a transition *occurred*. D-24 confines a verified result to
establishing **cryptographic verification only — never admission, never
registration, never trusted resolution**. D-04 keeps trust-anchor ownership with
the composition root and forbids a second hidden trust store inside the
registry. D-11 keeps the authoritative clock at BR-2D.

**The reviewer's question is the negative one.** A release that ships the six
rows above and *also* a store, a cache, a clock read, an append path, an
authority-issued result, or a resolution that a caller could mistake for a
trusted one, fails (i) — however well the ratified part is built.

## D-38(ii) — the prohibition list cannot self-authorize

This is the harder half, and the repository settles why. The guard is
**self-attested**: `FORBIDDEN_CAPABILITY_UNLOCK` and
`BR2A_FROZEN_CAPABILITY_TOKENS` are two literals in one module
(`tests/packaging/test_milestone_boundary.py`), and
`EXPORTED_IMPLEMENTATION_UNLOCK` and `BR2A_FROZEN_EXPORT_TOKENS` are the same
pattern one directory away (`tests/contract/test_confusable_and_ports.py`). A
symmetric edit moves both sides of every comparison together. **D-38 rules out
adding a shape scan** — a classifier recognising a capability by its form would
be another gameable one — so detection cannot come from inside the tree.

**It comes from an external fixed point: D-33 pre-registers, by name, exactly
which tokens `0.3.0` unlocks** [V]. Recomputed at `6b805691`, the unlock delta
between the `BR-2C-0` rung and `BR-2C` across both maps is **twelve** tokens,
and they are precisely the twelve D-33's row names:

- from `FORBIDDEN_CAPABILITY_UNLOCK` (eight): `signature_verifier`,
  `key_parser`, `trust_anchor_store`, `approval_verifier` and their unseparated
  spellings;
- from `EXPORTED_IMPLEMENTATION_UNLOCK` (four): `denyall`, `deny_all`,
  `verifier`, `trust_store`.

D-33's row sits under §35.2 change control, in a **different document** from the
literals. That asymmetry is the whole of the available leverage.

### The three classes of edit, and what each does

Measured at `6b805691` [V]:

1. **Adding** a token to both literals strengthens the ban. Not an attack.
2. **Removing** a token from both — the fourth audit's case. Suite stays green
   at 2113 with `"keyparser"` and `"key_parser"` gone, and a working parser then
   ships (worked example below). **Detected by** membership: the removed name is
   absent from both maps and from `BR2A_FROZEN_CAPABILITY_TOKENS`, so a
   reviewer diffing membership against D-33's twelve and against the frozen sets
   as the ADR records them will see the gap.
3. **Changing a token's unlock phase**, leaving membership intact. **This is the
   one that passes every existing check and lies dormant** [V]. Editing
   `"storage"` from `"BR-2D"` to `"BR-2C"` in `FORBIDDEN_CAPABILITY_UNLOCK`
   leaves the suite **green at 2113** at this rung, because `storage` is banned
   at `BR-2C-0` either way. `BR2A_FROZEN_CAPABILITY_TOKENS` does not catch it:
   that set pins **membership, not unlock phase**, and the equality assertion
   compares keys. At `0.3.0` the map would unlock **nine** tokens instead of
   eight — a thirteenth overall — and §35.1 forbids BR-2C to ship any storage at
   all. Neither `test_the_effective_ban_set_is_exactly_what_br2a_froze`,
   `test_no_capability_is_scheduled_to_unlock_at_or_before_this_version` nor
   `test_a_token_is_banned_below_its_unlock_rung_and_not_at_it` fails on it.

### The comparison baseline, and why it cannot be read from the release head

**D-33 inside the release head cannot authorize itself** [R]. A row that
authorizes an unlock and travels in the same commit stream as the code it
authorizes is not an independent baseline: an edit to the row and an edit to the
map move together, in the same commit, reviewed by the same eyes. That is the
one-file two-literal failure mode one directory up, and reading D-33 from the
head reproduces it at document scale. The row's authority as a fixed point comes
entirely from its being **older than, and separate from, the thing it is used to
check**.

**The baseline is the commit that ratified it:**

```
4920c87893328a94fa9cea407af3e9e8dd15dd8f
ADR §35.2: ratify D-33, D-34 and D-35 — the three items BR-2C's
contract slice left open        (2026-08-21)
```

The reviewer reads D-33's row **from that commit object**, pinned by its full
hash — `git show 4920c878…:docs/architecture/ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md`
— and never from the release head's working tree or from the head's copy of the
ADR. The comparison is then *historical baseline* against *exact `0.3.0` release
head*, in that direction.

**Two things about this baseline the reviewer must be told rather than discover.**

**It has not moved, measured** [V]. Between `4920c878` and `c3fe8708` — this
brief's own head — D-33's twelve-token clause is **byte-identical**, and the
`FORBIDDEN_CAPABILITY_UNLOCK` and `EXPORTED_IMPLEMENTATION_UNLOCK` literals are
**byte-identical** across the same span: no token added, none removed, and no
unlock phase changed. The rest of D-33's row *did* move — refreshed line
citations and an added *Five further sites* enumeration — which is why the
comparison must be scoped to the twelve-token clause and the maps, not to the
row's full text. This is the reconciliation performed once as a worked
demonstration. It says nothing about a `0.3.0` head, which does not exist; the
reviewer repeats it against the head they are given.

**The baseline must be branch-anchored before the review is commissioned** [R].
A baseline reachable only from the same line of work it is used to check is
weaker than one on the default branch: both are immutable by hash, but only the
latter is independent of the branch under review, and only the latter survives
that branch being deleted, rewritten or abandoned. **The requirement is therefore
that `4920c878` be an ancestor of the repository's default branch at the moment
the reviewer is engaged, and that the reviewer verify this rather than assume
it** — `git merge-base --is-ancestor 4920c878 <default-branch>` answers it in one
command, against whatever the default branch is on the day they are handed the
work.

**Merging the BR-2C-0 line establishes it.** That line — `4920c878` and the
commits stacked on it, up to and including this brief — reaches the default
branch through pull request **#1466**, whose merge is what promotes the baseline
from hash-pinned to branch-anchored. Until some such merge has occurred the
requirement above is unmet, and a reviewer who finds it unmet should say so in
their findings rather than let the distinction pass silently: the fallback is to
pin by full commit hash and record that the baseline was not branch-anchored,
never to substitute the release head's own copy of D-33.

**So the reviewer's procedure for (ii) is a reconciliation, not an inspection**
[R]:

1. At the release head, recompute the unlock delta across **both** maps between
   the rung below and the release's own rung, using `banned_capability_tokens`
   from `tests/_milestones.py`.
2. Reconcile that delta, **by name**, against the twelve D-33 pre-registers —
   read from the baseline commit above, never from the release head's copy.
3. Treat **any** token in the delta that D-33 does not name as a self-authorized
   capability, whether it arrived by removal, by a changed unlock phase, or by a
   ladder edit — and whether or not the suite is green.
4. Separately reconcile the **membership** of both frozen sets against the
   baseline commit's copies of both unlock maps, since a token deleted from all
   four literals leaves no delta to compute and the head's own literals cannot
   witness their own deletion.
5. Confirm that the gates which currently carry the boundary and **must** be
   relaxed for a verifier to ship at all — among them
   `test_nothing_in_the_package_performs_cryptography`,
   `test_no_verifier_or_resolver_ships_and_no_crypto_is_imported`,
   `test_no_concrete_class_in_the_package_satisfies_any_port`,
   `test_no_cryptographic_dependency_is_declared` and
   `test_no_module_outside_canonical_computes_a_digest` — were relaxed **exactly
   as far as** a ratified row requires and no further. At `0.3.0` these edits are
   unavoidable, which makes the release head the one moment where the boundary is
   defined entirely by which edits were made [G].

## What the reviewer is given, and what they must derive independently

**Given** — committed at the head, and all of it authored by the party under
review: the ADR, this distribution's `CHANGELOG.md` and `README.md`; the five
generated manifests (`public_api.json`, `public_contract_inventory.json`,
`canonical_domain_inventory.json`, `pinned_canonical_vectors.json`,
`gate_inventory.json`); the suite; `adversarial_probes.py`;
`gate_mutation_sweep.py`; `verify_benchmark_registry_authority_distribution.py`;
and `verify_br1_freeze_matrix.py`.

**Must be derived independently**, because in each case the given artifact
cannot witness the thing it describes:

- **The unlock delta and its reconciliation against D-33's twelve.** No
  committed artifact carries it; §35.2 D-37 records that no generated artifact
  in this tree carries a prohibition at all, since every manifest is derived from
  what **does** exist and a ban set so derived would pass by construction.
- **That the ratified capability set is not exceeded.** `public_api.json` and
  `public_contract_inventory.json` enumerate what shipped; neither can say what
  was ratified. Only the §35.2 rows can, and they are prose.
- **That the suite's own gates were not weakened in the same diff.** A green
  suite at the head is consistent with both a sound boundary and a relaxed one.
  `gate_mutation_sweep.py` reports on the gates that **exist**, so a deleted
  gate leaves no survivor to classify.
- **Whether the shipped verifier is correct.** It is outside D-38 and belongs to
  D-32(4)'s external cryptographic audit. D-38 asks what ships, not whether it is
  cryptographically sound; a release can pass D-38 and remain barred from
  production use.
- **Reachability of anything the tests reach by convention.** The suite resolves
  the sibling BR-1 layer through `conftest.py`'s path insertion. In an isolated
  checkout without that sibling, collection fails outright; with it, **two**
  monorepo-scope properties skip, so a clean detached run reads **2111 passed, 2
  skipped = 2113 collected** rather than 2113 passed [V].

**In-row line citations are not evidence.** §35.2 freezes them at ratification
for all thirty-eight rows: resolve the **symbol** a row names, never the line
number it gives. Fifteen such citations do not resolve at this head. This brief
cites symbols and test names only, for the same reason.

## Worked example — the four `KeyParser` variants, reproduced at `6b805691`

Reproduced against a scratch copy of the package (`git archive`, the working
tree untouched), with `"keyparser"` and `"key_parser"` deleted from both
`FORBIDDEN_CAPABILITY_UNLOCK` and `BR2A_FROZEN_CAPABILITY_TOKENS`, then a
`class KeyParser` shipped under `src/` [V]:

| Variant | What it does, and where | Result |
|---|---|---|
| **A** | digests its input, in `contracts/keys.py` | **1 failed** — `test_no_module_outside_canonical_computes_a_digest` |
| **B** | calls `base64.b64decode`, same module | **2 failed** — `test_the_only_non_stdlib_import_anywhere_is_the_frozen_br1_layer` and `test_the_only_non_stdlib_import_is_the_frozen_br1_layer` |
| **C** | a working `parse()` validating `"<key-id>:<base64>"` with `re`, decoding base64 in pure Python — a bit accumulator, no import beyond `re` | **GREEN at 2113** |
| **D** | variant A's digesting parser, written into `contracts/canonical.py` instead | **GREEN at 2113** |

Variant **C** is not a placeholder: it round-trips `base64.b64encode` at every
payload length 1 through 39, and raises `ValueError` on all eight malformed
inputs exercised. Variant **D** shows that variant A fails because of **where
the module sits**, not because it digests — the digest gate is scoped to
location. Restore the two tokens and re-run C: **exactly one** gate catches it,
`test_no_class_or_function_anywhere_carries_a_forbidden_capability_name`.

**What the reviewer takes from this**: at `BR-2C-0` the naming-token guard is
the **sole** control preventing a working key parser from entering the package.
The list-free gates do not carry the load — variant C trips none of them. At
`0.3.0` the eight capability tokens naming exactly this class of code unlock by
ratified design, so the control demonstrated here is **gone at the release head
by construction**, and D-38(i)'s enumeration is what replaces it. The reviewer
should expect to re-run these four variants, and to construct better ones.

## Negative findings, and unavailability

**A negative finding on (i) or (ii) blocks the release.** It does not attach a
condition, a follow-up item or a documented exception. A capability shipped
outside the ratified set, or a prohibition edit not traceable to a ratified row,
means `0.3.0` does not ship until either the code is withdrawn or the ADR is
amended by a fresh §35.2 ruling — and an amendment written to accommodate a
finding is itself an owner decision, taken on the record, never a reviewer
concession.

**A negative finding is not discharged by a green suite.** Class-3 edits above
are green by construction; D-38 was ratified precisely because the suite cannot
witness its own weakening.

**If the review is unavailable, `0.3.0` REMAINS BLOCKED.** Unavailability is not
a lapse condition and carries no default-permit. There is no substitute route:
not the owner's own review, which D-32(1) and (2) waived only for `BR-2C-0` and
which D-38 withdraws for any capability-bearing release; not a further audit of
a contract-only rung, which D-38 excludes by name; and not D-32(4)'s external
cryptographic audit, which is a different gate answering a different question.

**This brief records no review, no reviewer and no finding.** Those are recorded
when a review has actually been obtained, by an amendment to §35.2 — not here.
