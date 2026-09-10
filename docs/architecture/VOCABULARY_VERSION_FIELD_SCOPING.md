# Vocabulary-version field — scoping

**The load-bearing question:** is adding "which vocabulary version was this written
against" one change across four records? **No — it is two changes with opposite risk
profiles, and the split is not the one the ballot's framing suggests.** Two of the
four records bind their label into a derived, self-verifying id; two do not. And the
neutral label types in `governance-contracts` canonicalize with
`dataclasses.asdict`, so putting the version **on the label** silently rewrites the
id of every record already stored in the two id-bearing packages, while putting it
**on the record** does not, because records canonicalize from an explicit key list.
That single mechanical fact decides the placement question, and it decides it
against the placement `DE-5` and `VR-5` would otherwise suggest.

**Status: RATIFIED on `VV-A` to `VV-E`** by the repository owner, 2026-09-09, who
ruled each explicitly rather than accepting the recommendations. **Three rulings
overrule this document's recommendation** (`VV-B`, `VV-D`, `VV-E`) and one
(`VV-C`) rejects the binary framing the document used. §5 records what was ruled
and why; the superseded recommendations are left visible beside them rather than
edited out, because a scoping document that hides what it got wrong is worth less
next time.

**Implementation is now authorized elsewhere, and sequenced behind publication.**
This document still adds no field, no type, no canonical projection and no schema.
The per-package contract change it recorded as unauthorized in §5A was authorized by
`PUB-2`, and `PUB-1` requires the vocabulary a binding cites to be published first —
both in `LV1_VOCABULARY_PUBLICATION_RULINGS.md`, ratified 2026-09-09. §5A and §7
below are updated accordingly; nothing in `VV-A` to `VV-E` changed. **Date:** scoped
and ratified 2026-09-09; §5A and §7 reconciled with `PUB-1`/`PUB-2` the same day.

**Why this exists.** `LV-1` ratified the vocabularies as Policy-Authority-owned
documentation. §2 of the ballot lists four conditions that must hold before any
package may interpret rather than record a label, and condition 4 —
*"the record carries which vocabulary version it was written against, or an old
record silently re-reads under a new taxonomy"* — is the one **nothing satisfies
today** `[G]`. It is the only condition that needs a code change rather than a
ruling, which is why it is scoped separately.

---

## 0. Baseline verification

`[V]` Default branch head `8d8d8fa0`, working tree clean at drafting time; every
citation below read at that head. `[V]` `ugence-governance-contracts` `0.8.0` with
`CONTRACT_VERSION = "1.0.0"` (`__init__.py:28`); `ai-system-registry` `0.2.0`,
`data-use-admission` `0.2.0`, `vendor-dependency` `0.2.0`, `incident-response`
`0.1.0`.

`[V]` **Four records, not five.** The ballot covers five vocabularies but
`data-use-admission` carries two of them on **one** record, so the field question is
asked of four record types.

---

## 1. What the code actually does

The whole scoping turns on two columns of this table, both verified rather than
assumed:

| Record | Label field | In the derived id? | Id self-verified at construction? |
|---|---|---|---|
| `SystemRegistration` | `classification_label` (`registration.py:177`) | **No** — id is binding digest + `owner_ref` + validity (`registration.py:147-162`) | Yes (`registration.py:203`) |
| `DataUseDeclaration` | `classification`, `purpose_label` (`declaration.py:133,135`) | **Yes, both** — the label's `canonical_digest()` and the purpose text are inputs (`declaration.py:91-118`) | Yes (`declaration.py:173`) |
| `VendorDependencyDeclaration` | `risk_posture` (`declaration.py:130`) | **Yes** — the label's `canonical_digest()` is an input (`declaration.py:89-105`) | Yes |
| `IncidentRecord` | `severity_label` (`records.py:80`) | **No** — id is tenant + subject + evidence digests + `opened_at` (`records.py:55-70`) | Yes |

**The two-two split is the finding.** For `ai-system-registry` and
`incident-response` the label is descriptive: it rides on the record and nothing
derives identity from it. For `data-use-admission` and `vendor-dependency` the label
is **identity-bearing** — change the label and you have a different declaration by
construction, which is deliberate and which `DE-3`/`VR-3` do not disturb, since
identity is exact-text equality rather than interpretation.

### How each thing canonicalizes, and why it matters

`[V]` **Labels use `dataclasses.asdict`.** `_canonical_bytes` in
`contracts/data_classification.py` (and its twins in `vendor_risk.py`,
`assurance_finding.py`) serializes *whatever fields the dataclass has*. Adding a
field to a label type therefore changes `canonical_bytes()`, changes
`canonical_digest()`, and — for the two id-bearing records — changes
`declaration_id`. No test or reviewer has to miss anything; it is automatic.

`[V]` **Records use an explicit key list.** `to_dict()` in each record names its
keys one by one (`registration.py:247-257`, `declaration.py:235-252`), and
`record_digest()` is `domain_digest(...)` over that dict. A new field on a record
changes the record digest **only if it is added to `to_dict`**, and changes the id
**only if it is added to the id derivation**. Both are deliberate, reviewable acts.

---

## 2. The two placements

### 2A. On the neutral label type — `DataClassificationLabel(label, version)`

Superficially right: it follows `DE-5` and `VR-5`, which put the label types in
`governance-contracts` precisely so every engine carries the same type. It is also
the placement that does the most damage.

- **It rewrites identity.** Every stored `DataUseDeclaration` and
  `VendorDependencyDeclaration` id was derived from a one-field label digest. Add
  the field and the same declaration derives a different id — and because both
  records **verify their own id at construction**, every stored record becomes
  unconstructible rather than merely stale. This is a silent break with a loud
  symptom.
- **It is not additive for `governance-contracts`.** The three label modules each
  state that the provider dataclasses are unchanged "so `CONTRACT_VERSION` stays
  `1.0.0`". Changing the shape of a label whose digest is an identity input is a
  `CONTRACT_VERSION` move, not a minor version bump `[R]`.
- **It pre-empts `LP-5`.** `LP-5` already weighs whether a fourth one-field label is
  the point to rule on a *shared uninterpreted-label base*. Adding a second field to
  three label types independently makes that base strictly harder to adopt later,
  and settles by accident a question wave 5 reserved.
- **`VR-5` does not forbid it but does not license it either.** "No second neutral
  type without another ruling" governs adding types; modifying one is unruled `[G]`.

### 2B. On the record — `SystemRegistration(..., classification_vocabulary_version)`

- **Identity is untouched unless you choose otherwise.** The field lands beside the
  label; `to_dict` and the id derivation are explicit, so existing ids stay valid.
- **It is additive for `governance-contracts`** — because it does not touch it at
  all. Each package versions independently.
- **It does not pre-empt `LP-5` or `LV-F`.** The label types keep their one field.
- **The cost:** four packages each grow a field rather than one type growing one,
  and `data-use-admission` needs *two* (classification and purpose are separately
  ratified vocabularies, on different schedules — the purpose vocabulary is an open
  shape under `LV-E` and may not have "versions" in the same sense at all `[R]`).

**Ratified by `VV-A`: 2B, with a refinement this document did not propose.** The
placement that looks consistent with `DE-5`/`VR-5` is the one that breaks stored
identity; the placement that looks inconsistent leaves identity alone.

The refinement: what a record carries is a **vocabulary binding**, not a version
string. A context-free `"v2"` identifies nothing — any organization-selectable
vocabulary must also identify its **authoritative vocabulary reference**. And each
record carries **one binding per vocabulary it uses**, so `DataUseDeclaration`
carries two independent bindings rather than one shared field. The field name may
establish the domain; it may not stand in for the source. See §4A for what that
requires and does not yet have.

---

## 3. What it does to ids, digests and stores

Under `VV-A` (record placement), `VV-B` (binding **in** `record_digest`) and `VV-C`
(binding in a derived id **exactly where the label digest already participates**):

| Effect | Consequence |
|---|---|
| Derived ids | **Changed in `DataUseDeclaration` and `VendorDependencyDeclaration`**, whose ids already consume a label digest; **unchanged in `SystemRegistration` and `IncidentRecord`**, whose labels are descriptive. Both of the first two verify their own id at construction, so under the new record version their stored records do not merely go stale — they become unconstructible, and are read as `UNVERSIONED_LEGACY` under their historical schema version instead. |
| `record_digest()` | **Changed in all four**, by ruling. `to_dict` is explicit, so this is a deliberate projection change rather than an automatic one. Historical digests stay valid **under their historical record version** and are never recomputed under the new projection. |
| Sqlite stores | `ai-system-registry`, `data-use-admission` and `vendor-dependency` each pin a schema string (`durable.py:51`, `:57`, `:59`) and refuse a file written at another version rather than migrating it. Adding a persisted column is a `v1` → `v2` move, and every existing file becomes unreadable by the new code by design. `incident-response` ships no store, so it has no migration at all. |
| Append-only guarantee | Unaffected: nothing is rewritten, and a re-declared record under a new vocabulary version is a *new* record that `supersedes` its predecessor — the mechanism these packages already use. |

**The digest question was the sharp one, and it is ruled against this document.**
`VV-B` includes the binding, on the ground that a digest excluding the taxonomy
under which a label was interpreted is incomplete: *the system can otherwise prove
the bytes of a label while failing to prove what that label meant.* Two otherwise
identical records written against different vocabulary versions must not share a
digest. The compatibility cost is accepted rather than engineered around — the
ruling explicitly refuses to preserve an additive *appearance* by leaving
authoritative semantics outside the digest.

---

## 4. Additive, or a `CONTRACT_VERSION` move?

`[V]` `CONTRACT_VERSION` is `1.0.0` and belongs to `governance-contracts`
(`__init__.py:28`). Under **2B it does not move**, because `governance-contracts` is
not touched. Under **2A it must move**, because a label's serialized shape is an
input to two packages' identities.

Package versions move either way: a new field on a public record is a minor bump for
each package that gains one, plus a schema-version bump for each of the three that
persist.

---

## 5. Ratified decisions

Ruled by the repository owner, 2026-09-09. Where a ruling overrules this document,
the recommendation is shown beside it rather than deleted.

| # | Decision | Ruling and ground | This document had recommended |
|---|---|---|---|
| `VV-A` | Placement | **On the record (2B), beside each label-bearing field.** `governance-contracts`' neutral label types are not modified and `LP-5` is not pre-empted. **Refinement:** each record carries one binding *per vocabulary*, so `DataUseDeclaration` carries independent classification and purpose bindings. A binding must identify its **authoritative vocabulary reference**, not merely a context-free version string; the field name may establish the domain but may not stand in for the source. | 2B — **upheld**, without the per-vocabulary and authoritative-reference requirements, which the ruling adds. |
| `VV-B` | Digest | **Include the binding in `record_digest()`.** A digest that excludes the taxonomy under which the label was interpreted is incomplete: the system would otherwise prove the bytes of a label while failing to prove what that label meant. Two otherwise identical records written against different vocabulary versions must have different digests. The compatibility consequence is accepted; an additive *appearance* must not be preserved by leaving authoritative semantics outside the digest. Historical digests remain valid under their historical record version and are never recomputed under the new projection. | Exclude it, to stay additive — **overruled.** |
| `VV-C` | Derived id | **Follow each record's existing identity semantics; not a blanket yes or no.** Include the binding in a derived id **exactly where the corresponding label digest already participates** — `DataUseDeclaration` and `VendorDependencyDeclaration`. Do **not** add it to the ids of records whose labels are descriptive and non-identity-participating — `SystemRegistration` and `IncidentRecord` — whose content digest covers the binding while their stable identity semantics are unchanged. | "No, in all four" — **the framing is rejected.** The question was binary and the answer is not: binding follows the label. |
| `VV-D` | `purpose_label` | **Yes — an independent binding.** "Open shape" means the platform imposes no closed enum; it does not mean purpose terminology is timeless or anonymously sourced. The purpose binding identifies the authoritative organization- or policy-supplied vocabulary and its version **independently of data classification**. Where no authoritative purpose-vocabulary mechanism exists, that is recorded as an **implementation blocker** — never silently omitted, and never borrowed from the classification binding. This neither closes nor reinterprets `LV-E`. | "Not yet — an open shape has no version to cite" — **overruled.** |
| `VV-E` | Required or optional | **Required for new record versions; explicitly absent only for historical ones.** Every governed label on a new record version requires a non-empty binding. `""`, `None`, `"current"` and `"latest"` semantics are refused. Existing persisted records stay readable **as their historical schema version** and are treated as `UNVERSIONED_LEGACY` at the interpretation boundary; that designation must **never** resolve automatically to the latest vocabulary, and any migration needs its own ruled process. | "Optional, defaulting to empty" — **overruled.** |

**Versioning consequence, ruled with the above.** Record projections and persisted
schemas change, so implementation is a **new record version and a new store version**
wherever a store exists. **`governance-contracts.CONTRACT_VERSION` does not move**,
because the neutral label contracts are untouched — which is `VV-A` working as
intended.

---

## 5A. Implementation blockers, recorded rather than deferred

`VV-A` requires every binding to identify an authoritative vocabulary reference, and
`VV-D` requires that a missing mechanism be recorded as a blocker rather than worked
around. Checking the four records against that requirement turns up a gap **wider
than `VV-D` anticipated** `[V]`:

| Package | Field able to carry an authoritative reference today |
|---|---|
| `vendor-dependency` | **`policy_ref`** — an opaque Policy Authority reference, recorded and compared as text and never resolved (`VR-4`). The only one of the four with a field of the right shape. |
| `ai-system-registry` | **None.** No policy or vocabulary reference on `SystemRegistration`. |
| `data-use-admission` | **None**, for either vocabulary. The record carries `data_ref`, `residency_label` and `correlation_id`, and no policy reference at all. |
| `incident-response` | **None.** |

So the blocker is not confined to purpose: **three of the four packages have nowhere
to put an authoritative reference**, and `data-use-admission` needs two. `VR-4`'s
`policy_ref` is the shape to copy — an opaque string that identifies without
resolving, which keeps these packages from importing Policy Authority.

**Both blockers above are now ruled**, in
`LV1_VOCABULARY_PUBLICATION_RULINGS.md` (`PUB-1` to `PUB-5`, ratified 2026-09-09).
They are recorded here as answered rather than deleted, because the shape of the
answer matters more than the fact of it:

- **The per-package contract change is authorized** (`PUB-2`), with no new neutral
  type in `governance-contracts` — which is `VV-A` holding. Every binding must carry
  or resolve to the vocabulary's identity, exact version **and content digest**; a
  bare version string is insufficient.
- **`vendor-dependency` does not reuse `policy_ref`.** `PUB-2` authorized the reuse
  only if `policy_ref` normatively identifies the exact permission-vocabulary policy,
  and determined `[V]` that it does not: `VR-4` rules it an **opaque** string the
  package "must not resolve, verify, interpret or fetch"
  (`ADR_UGENCE_VENDOR_RISK_SCOPING.md:61`), and a string forbidden to be interpreted
  cannot normatively identify anything. So all four packages gain a distinct
  reference; `policy_ref` remains the shape, not the carrier.
- **The referent is being published, and publication comes first** (`PUB-1`): five
  vocabularies as separate immutable specifications at `1.0.0`, no mutable `latest`,
  major version for any normative change. **No record reference is implemented before
  the vocabulary it cites is published.**

One qualification survives the rulings, and one has since been resolved. `PUB-1` is
explicit that repository publication establishes the **canonical vocabulary content
only** — it is **not** issuance by Policy Authority, and nothing here may describe it
as an issued or signed organizational policy. And the vocabulary once called
`vendor-dependency-permission`, held from publication because it named permission
semantics its own `LV-C` members refuse, is renamed
**`vendor-dependency-assessment-state`** by `PUB-1a` and published under that name.

`[V]` **All five vocabularies are published** at
`docs/vocabularies/<identifier>/1.0.0.json`, each immutable under a content digest that
`scripts/check_vocabulary_publications.py` recomputes in CI. Every binding this
document scopes now has a referent that exists, which is what `PUB-1` required before
any of them is written.

---

## 6. Not blocked on this

**`LV-F`** — whether general-purpose AI models belong in the system-classification
set — was independent, and has since been ruled by `PUB-3`: a separate
`GeneralPurposeAIModelRegistration` record, no member added here. The reasoning holds
either way, which is why it was independent: the field records *which version* was
used, not *which members exist*. The new record, when scoped, carries its own binding
under the same `VV-A` to `VV-E` rules.

`[R]` **`LP-5`** — the shared uninterpreted-label base — is only entangled under
2A. If `VV-A` is ruled 2B, this scoping adds nothing wave 5 must work around, which
is a further argument for 2B.

`[G]` **The interpreting layer still does not exist.** Even with the field shipped,
§2's conditions 2 and 3 remain unmet: no owner has ruled what each member *entails*,
and no package that may decide has been given the vocabulary. This field removes one
of four blockers and enables nothing on its own.

---

## 7. Recommended next step

`VV-A` to `VV-E` are ruled, and the shape of the work is now known and larger than
this document first estimated: four packages gaining one binding per governed
vocabulary (six bindings in total), each required and each in the record digest;
derived ids changing in two of the four; new record versions throughout and new
store versions in three; a version-discriminated read path so historical records
stay readable as `UNVERSIONED_LEGACY`; and `governance-contracts` untouched.

**It is authorized, and it starts with publication, not code.** `PUB-2` grants the
per-package contract change §5A recorded as unauthorized, and `PUB-1` sequences it:
the five vocabulary specifications are published as immutable documents first, and a
record binding is implemented only after the vocabulary it cites exists to be cited.
A binding to a referent that does not exist is a field that records nothing while
appearing to record provenance.

`[V]` **That publication has happened**, for all five, at `docs/vocabularies/`. The
prior condition is discharged: nothing this document scopes is now waiting on a
missing referent.

`[V]` **And the bindings are implemented**, in all four packages —
`data-use-admission` 0.3.0, `ai-system-registry` 0.3.0, `incident-response` 0.2.0 and
`vendor-dependency` 0.3.0. Each carries the vocabulary's identity, exact version and
content digest as a package-local `VocabularyBinding`; each is required (`VV-E`),
covered by `record_digest()` (`VV-B`), and in the derived id only where the label
already participated in identity (`VV-C`). `governance-contracts` gained no type and
did not move its `CONTRACT_VERSION` in any of the four, which is `VV-A` working as
intended.

**Two things the scoping did not anticipate, recorded because they cost something.**

`[V]` The `VV-C` split is visible in the code now, and it decided more than the id: the
two records where the answer is *no* keep every id they ever wrote, so the change is
invisible to anything keyed by their ids, while the two where it is *yes* renumber every
new record. The binary framing `VV-C` rejected would have got one of those two halves
wrong whichever way it was answered.

`[V]` The four copies of `VocabularyBinding` are the price `VV-A` chose, and one of them
found a defect for all four: `incident-response` is the only one of the four running a
refusal mutation sweep, and it reported seven guards in the shared file that no test
observed. Each is now covered in every copy, and one branch was deleted rather than
tested — `ContractViolation` subclasses `ValueError`, so an `except (TypeError,
ValueError)` beside a bare re-raise could only catch what the re-raise had already
handled, while blunting the precise refusal message on any path that reached it. A
shared type would have had one test suite; four copies had one sweep, and the sweep is
what found it.

## 8. What is still not done

`[G]` **The interpreting layer.** §2's conditions 2 and 3 remain unmet: no owner has
ruled what each member *entails*, and no package permitted to decide has been given the
vocabulary. Every record can now say which taxonomy it was written under; nothing can
say what that taxonomy means.

`[R]` **Two contract changes are ruled and unscoped** — the
`GeneralPurposeAIModelRegistration` record (`PUB-3`) and the regulatory-status field
(`PUB-4`). Each needs its own scoping and its own implementation authorization.

`[G]` **Migration of historical records.** Every package reads its v1 records and
refuses to write beside them; `VV-E` rules that turning a `UNVERSIONED_LEGACY` record
into a bound one needs its own ruled process, and no such process exists. Until one
does, a deployment with v1 files keeps two files rather than one.
