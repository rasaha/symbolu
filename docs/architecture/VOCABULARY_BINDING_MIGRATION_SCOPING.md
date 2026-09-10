# Migrating `UNVERSIONED_LEGACY` records — scoping

**The load-bearing question:** what process turns a persisted record written before the
vocabulary binding into one that names a published vocabulary? **The answer is that no
such process can be written against the current write surface — every shape it could
take is refused by the stores themselves, and two of them are refused by rulings rather
than by omission.** So this is not a gap where the design exists and the code is
missing. It is a gap where the design is blocked, and the block is `[R]` to clear.

**No implementation is authorized by this document, and nothing here is ruled.** Five
decisions are marked `[R]` and none is taken.

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

`[R]` **Decision `MIG-5` — is migration in scope at all?** Leaving v1 files permanently
readable and unmigrated is a real option with a real cost (two files, forever, per
tenant), and it is the only option that needs no ruling. Every other decision below is
moot if this one is "no".

---

## 5. Who may assert a historical record's vocabulary, and on what evidence

`[R]` **Decision `MIG-1`.** A migration asserts a fact nobody recorded: which vocabulary
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

`[R]` The ruling needed is whether an administrator's assertion is an acceptable basis
at all, and if so whether a migrated binding must be **distinguishable** from one
recorded at the time — a third `VocabularyBindingState`, say, rather than plain `BOUND`.

---

## 6. Supersession or rewrite, and which write surface moves

`[R]` **Decision `MIG-2`.** Rewriting in place is refused by every store by
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

`[R]` **Decision `MIG-3` — is a migrated record a new record or the same one restated?**
In `data-use-admission` and `vendor-dependency` the derived id changes, so the answer is
forced to "new" whatever the intent; anything keyed by the old id must be re-pointed. In
`ai-system-registry` the id cannot change, so the answer is forced the other way, and
§3's `D-3` refusal blocks it. **The two halves cannot be given one answer**, which is
`VV-C`'s split reappearing — and this time it is not obviously right.

`[R]` **Decision `MIG-4` — may a record whose taxonomy is genuinely unknown be migrated
at all?** Given §5, this is not an edge case: it is the ordinary case. If the answer is
no, `MIG-1` to `MIG-3` apply only to records whose vocabulary somebody can actually
attest, which may be none of them.

---

## 7. Sequencing, and what this document does not settle

`[G]` Nothing here is blocked on `LP-1` to `LP-5`: those concern stage and promotion, and
migration touches neither. `[G]` It *is* entangled with the missing interpreting layer,
as §4 says — a migration whose only beneficiary is an unbuilt layer is hard to justify
and hard to specify, because nobody can say what the layer will need.

| Decision | Question | Blocked on |
|---|---|---|
| `MIG-5` | Is migration in scope at all, or do v1 files stay readable forever? | nothing — rule first |
| `MIG-1` | Who may assert a historical vocabulary, and is an unverifiable assertion acceptable? | `MIG-5` |
| `MIG-2` | Which write surface moves: a second write, cross-file resolution, or an external tool? | `MIG-5` |
| `MIG-3` | New record or same record restated — and may the two halves differ? | `MIG-2`; `D-3` for `ai-system-registry` |
| `MIG-4` | May a record of genuinely unknown taxonomy be migrated? | `MIG-1` |

**`ai-system-registry` additionally needs `D-3` revisited or an explicit exemption**, and
that is an amendment to a ratified ADR rather than a decision this row can carry.

**Next step.** Rule `MIG-5` before anything else. If it is "no", this document closes and
the two-file state is recorded as intended rather than pending; every other decision here
is moot. If it is "yes", `MIG-1` is next, because §5 may make the rest unnecessary.
