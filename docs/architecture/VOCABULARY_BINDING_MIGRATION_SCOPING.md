# Migrating `UNVERSIONED_LEGACY` records — scoping

**The load-bearing question:** what process turns a persisted record written before the
vocabulary binding into one that names a published vocabulary? **The answer is that no
such process can be written against the current write surface — every shape it could
take is refused by the stores themselves, and two of them are refused by rulings rather
than by omission.** So this is not a gap where the design exists and the code is
missing. It is a gap where the design is blocked, and the block is `[R]` to clear.

**Status: `MIG-5` RULED `NOT_IN_SCOPE`**, 2026-09-10, under owner direction — the owner
named the two options and their costs and directed the ruling, as they did for `PUB-1a`.
`MIG-1` to `MIG-4` are **closed as moot** by it. §8 records the ruling and its ground;
the analysis below is left as written, because the ground for the ruling is in it and a
document that edits out its own reasoning is worth less next time.

**No implementation is authorized, and none is needed.** The ruling's whole content is
that a thing does not get built.

---

## 0. Baseline verification

`[V]` Default branch state at `124aa2f6`, with the four bindings implemented:
`data-use-admission` 0.3.0, `ai-system-registry` 0.3.0, `incident-response` 0.2.0,
`vendor-dependency` 0.3.0. Every claim below was executed against that tree, not read
off it.

---

## 1. Three stores, and only two of them have the problem

`[V]` **`incident-response` has no store at all** (D-4): "an incident's durability is its
`AuditReference` into a store that already exists". Nothing in that package persists an
incident, so it has no historical records to migrate. Whoever persisted one holds the
problem, and it is not this package's to solve. **It is out of scope here**, and any
document that lists all four packages as needing migration is wrong about this one.

That leaves `data-use-admission`, `ai-system-registry` and `vendor-dependency`, each with
one tenant-bound, append-only sqlite file whose only write is a single append.

---

## 2. What the stores actually refuse — executed, not inferred

`[V]` A v1 file is readable and takes no writes; the refusal names `VV-E` and says
migration needs its own process. That is the deliberate part. What follows is not.

`[V]` **A legacy record cannot be copied into a v2 file.** `declare`/`register` refuses
any record whose `record_version` is not current:

    declare takes a data_use_admission.v2 declaration; 'data_use_admission.v1' is a
    historical shape that can be read and not written

`[V]` **So a migrated record has no predecessor to supersede.** The predecessor is
resolved from *the same file* (`existing.get(declaration.supersedes)`), and the v1
record cannot be in a v2 file. Appending a correctly-formed migrated record to a fresh
v2 file gives:

    DeclarationSupersessionError: the superseded declaration does not exist

`[V]` **The pure rules would have allowed it.** Called directly on the two records,
`supersession_refusals(migrated, legacy)` returns `()` in both `data-use-admission` and
`vendor-dependency`: the tenant matches, the data or vendor reference matches, and
`declared_terms()` differs because the binding is part of the terms. **The contract
permits the migration; the store cannot express it.** That is a narrower and more
fixable problem than "migration is undesigned", and it is the finding this document
exists to record.

---

## 3. `VV-C` inverts here, and the easy half is the hard one

`VV-C` put the vocabulary into the derived id where the label already participated in
identity, and left it out where the label was descriptive. For migration that split
reverses which packages are tractable.

| Package | Vocabulary in the id (`VV-C`) | Migrated record's id | Consequence |
|---|---|---|---|
| `data-use-admission` | yes | **new** | A distinct record; supersession is the natural shape |
| `vendor-dependency` | yes | **new** | Same |
| `ai-system-registry` | **no** | **identical** | Collides with the record it migrates |

`[V]` In `ai-system-registry` the migrated registration derives
`reg_4548967efa55f21bf292d1565c397094` — byte-identical to the legacy one, because the
id is the binding, owner and window and none of those changed. Appending it is refused:

    DuplicateRegistrationError: registration reg_... is already recorded; records are
    never edited

`[V]` And supersession is refused independently, by a **ruling** rather than a
mechanism. `D-3` requires a superseding registration to bind a *different* system
identity:

    a superseding registration must bind a different system identity; an unchanged
    system has nothing to supersede

A migration changes nothing about the system — that is the whole point of it — so `D-3`
forbids expressing it as a supersession. **`ai-system-registry` is therefore blocked on
a ratified ruling, not on code**, and no write surface change alone unblocks it.

---

## 4. What migration is actually for, and how much it is worth

`[V]` **Reads already work across both files.** The pure selectors take a caller-held
collection, and a v1 store reads its records normally, so a composition root holding two
stores can read both and answer over the union today. Nothing is unreadable, nothing is
lost, and no query is unanswerable — the cost of not migrating is **two files instead of
one**, plus records that honestly report `UNVERSIONED_LEGACY`.

`[G]` What migration would buy is a single file and a uniform answer to "under which
taxonomy was this written". Neither is worth much while the interpreting layer does not
exist: no owner has ruled what any member *entails*, and no package permitted to decide
has been given a vocabulary. **Migrating records so that a layer nobody has built can
interpret them more conveniently is work done ahead of its own justification.**

**Decision `MIG-5` — is migration in scope at all? Ruled `NOT_IN_SCOPE`; see §8.**
Leaving v1 files permanently readable and unmigrated has a real cost — two files,
forever, per tenant — and it is the only option that needs no further ruling. Every
other decision below is moot, and §8 says why.

---

## 5. Who may assert a historical record's vocabulary, and on what evidence

**Decision `MIG-1` — closed as moot by `MIG-5`.** The analysis stands, and it is the
largest part of the ground for that ruling. A migration asserts a fact nobody recorded: which vocabulary
version a label was read under at the time it was written. Three sources are available
and none is evidence:

- **Inference from the record's date** against publication dates — but `PUB-1` published
  every vocabulary at `1.0.0` on 2026-09-09, *after* every historical record. Every
  legacy record predates every published version, so no date-based inference can
  conclude anything except "none of these".
- **Assertion by an administrator**, which is the same act as the original declaration
  and carries the same ceiling: `authenticity_status` is permanently
  `STRUCTURAL_UNVERIFIED`, so the platform proves nothing about it either way.
- **A Policy Authority coordinate**, which `PUB-1` says these specifications do not
  have: repository publication establishes canonical content and **not** issuance.

`[G]` So a migrated record would carry a binding whose truth rests on an assertion the
repository cannot check, presented in a field whose whole purpose is to make provenance
checkable. That is a worse failure than an honest `UNVERSIONED_LEGACY`: the second says
"unknown", the first says "known" and is not.

The ruling this needed — whether an administrator's assertion is an acceptable basis at
all, and whether a migrated binding must be distinguishable from one recorded at the
time — is not required, because `MIG-5` means no migrated binding is ever written. Had
migration gone ahead, a third `VocabularyBindingState` would have been the minimum.

---

## 6. Supersession or rewrite, and which write surface moves

**Decision `MIG-2` — closed as moot by `MIG-5`.** Rewriting in place is refused by every store by
construction — "a declaration is never edited or deleted" — and reopening that is a much
larger change than migration, since append-only is what makes the stored digests mean
anything. Supersession is the shape the contracts already permit (§2), and it needs
**one** of:

- **a second write** that appends a legacy record into a v2 file so it can be superseded
  — which makes "the only write is `declare`" false, in three packages that state it as
  a structural guarantee; or
- **cross-file predecessor resolution**, letting a v2 store accept a predecessor read
  from a v1 file — narrower, and it makes the v1 file an input to a v2 write, which is a
  coupling nobody has ruled on; or
- **a one-shot migration tool outside the store**, writing a new v2 file directly and
  never using `declare` — which puts record-writing code outside the class that holds
  every invariant, and is the option most likely to produce a file the package would
  have refused to write.

**Decision `MIG-3` — closed as moot by `MIG-5`.** Is a migrated record a new record or
the same one restated?
In `data-use-admission` and `vendor-dependency` the derived id changes, so the answer is
forced to "new" whatever the intent; anything keyed by the old id must be re-pointed. In
`ai-system-registry` the id cannot change, so the answer is forced the other way, and
§3's `D-3` refusal blocks it. **The two halves cannot be given one answer**, which is
`VV-C`'s split reappearing — and this time it is not obviously right.

**Decision `MIG-4` — closed as moot by `MIG-5`, and it is the reason for it.** May a
record whose taxonomy is genuinely unknown be migrated at all? Given §5 this is not an
edge case, it is the ordinary case — and §8 makes it the ordinary case by a stronger
route than §5 reached.

---

## 7. Sequencing, and what this document does not settle

`[G]` Nothing here is blocked on `LP-1` to `LP-5`: those concern stage and promotion, and
migration touches neither. `[G]` It *is* entangled with the missing interpreting layer,
as §4 says — a migration whose only beneficiary is an unbuilt layer is hard to justify
and hard to specify, because nobody can say what the layer will need.

| Decision | Question | Outcome |
|---|---|---|
| `MIG-5` | Is migration in scope at all, or do v1 files stay readable forever? | **`NOT_IN_SCOPE`** — §8 |
| `MIG-1` | Who may assert a historical vocabulary, and is an unverifiable assertion acceptable? | moot |
| `MIG-2` | Which write surface moves: a second write, cross-file resolution, or an external tool? | moot |
| `MIG-3` | New record or same record restated — and may the two halves differ? | moot |
| `MIG-4` | May a record of genuinely unknown taxonomy be migrated? | moot |

`[V]` **`D-3` does not need revisiting after all.** §3 recorded that
`ai-system-registry` would need that ratified ADR amended or an explicit exemption before
a migration could be expressed. Under `MIG-5` no migration is expressed, so `D-3` stands
untouched — which is the ruling paying for itself immediately: the cheapest way to avoid
amending a ratified ruling turned out to be not needing to.

---

## 8. `MIG-5` — ruled `NOT_IN_SCOPE`

**Ruled 2026-09-10 under owner direction**, who named the two options and their costs and
directed the ruling. Recorded here with its ground, because a delegated ruling is not a
less inspectable one.

**Historical records stay in their v1 files, readable and unmigrated, permanently. No
migration process is designed, authorized or forthcoming.** A deployment holding v1
records keeps two files per tenant per package in `data-use-admission`,
`ai-system-registry` and `vendor-dependency`. That is the intended end state, not a
pending one.

### The ground, in the order that decides it

`[V]` **1. A migrated binding would be false, not merely unverifiable.** §5 argued that
no evidence can establish which vocabulary a historical record was written under. The
dates make the stronger claim available: every vocabulary was published at
`2026-09-09T23:59Z`, and every record in a v1 file was written by code that shipped
before the bindings landed on `2026-09-10T01:40Z` or later. A record written before
publication was **not** written under `1.0.0` of anything, because `1.0.0` did not exist.
Migrating it would not be recording an uncertain fact; it would be recording a fact known
to be untrue, in the one field on the record whose entire purpose is to make provenance
checkable. `UNVERSIONED_LEGACY` is not a degraded answer here. It is the correct one.

A window is arithmetically available — the two hours on 2026-09-10 between publication
and the bindings landing — in which a published vocabulary existed while v1 code was
still current. `[V]` **It is empty, and by a firmer fact than timing.** Neither the
publication nor the bindings has reached the default branch:
`docs/vocabularies/` does not exist there at all, and none of the five commits carrying
this work is an ancestor of it. So no release of any package has ever coexisted with a
published vocabulary, and every record a v1 file can hold was written by code that had
nothing to cite. If that ever ceases to be true — after this branch merges and before
every deployment upgrades — it is a reason to revisit this ruling, and it is listed below
as one.

`[V]` **2. Nothing is lost by not migrating.** Reads work across both files today — the
pure selectors take a caller-held collection and a v1 store reads normally — so no record
is unreadable, no query unanswerable and no history broken. The cost is one extra file,
paid by composition roots that already hold every other decision.

`[G]` **3. The only beneficiary does not exist.** Migration's payoff is a uniform answer
to "under which taxonomy was this written", which nothing can use: the ballot's §2
conditions 2 and 3 are still unmet, no owner has ruled what any member *entails*, and no
package permitted to decide has been given a vocabulary. Specifying work for an unbuilt
consumer means guessing what it will need, and guessing wrong is how a migration gets run
twice.

`[V]` **4. The price of "yes" was two ratified guarantees.** Every route in §6 requires
either a second write in three packages that state "the only write is `declare`" as a
structural guarantee, or record-writing code outside the class holding the invariants.
`ai-system-registry` additionally required `D-3` amended or exempted. Spending ratified
guarantees on point 3's payoff is a bad trade at any price.

### What this ruling does not say

It does not say the two-file state is elegant, and it does not say migration is
impossible — §2 showed the *contracts* already permit the supersession and only the store
cannot express it. It says the case for spending anything on it has not been made.

`[R]` **What would reopen it.** Any of: an interpreting layer is authorized and needs
uniform bindings; a deployment is found holding v1 records written **after this work
merges**, which is the first moment a record could be written while a citable vocabulary
exists — ground 1 holds today because publication has not reached the default branch, and
it stops being self-maintaining the moment it does; or the two-file cost turns out to
bite something concrete rather than being an inconvenience. Reopening means ruling
`MIG-5` again, not treating `MIG-1` to `MIG-4` as merely paused.

---

## 9. The one thing left to correct

`[G]` Three packages refuse a write to a v1 file with a message ending "Migrating it
needs its own ruled process (VV-E), not an append". That sentence is still **true** — and
it now reads as a promise that such a process is coming, when the ruling is that none is.
The messages and the CHANGELOG entries that echo them should say the v1 file is closed
permanently. **That is a code change, outside this document's authorization**, and it is
the only follow-up this ruling generates.
