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

**Status:** scoping document — no implementation, and none authorized. This
document adds no field, no type and no test. **Date:** 2026-09-09.

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

**Recommendation `[R]`: 2B.** The placement that looks consistent with `DE-5`/`VR-5`
is the one that breaks stored identity; the placement that looks inconsistent leaves
identity alone. Consistency of *where types live* is worth less than not rewriting
the id of every record already written.

---

## 3. What it does to ids, digests and stores

Assuming 2B, and assuming the field is **excluded** from both the id derivation and
`to_dict` unless a ruling says otherwise:

| Effect | Consequence |
|---|---|
| Derived ids | Unchanged in all four records. Stored records stay constructible. |
| `record_digest()` | Unchanged, because `to_dict` is explicit. **But a digest that omits the version no longer covers the whole record** `[R]` — see the decision below. |
| Sqlite stores | `ai-system-registry`, `data-use-admission` and `vendor-dependency` each pin a schema string (`durable.py:51`, `:57`, `:59`) and refuse a file written at another version rather than migrating it. Adding a persisted column is a `v1` → `v2` move, and every existing file becomes unreadable by the new code by design. `incident-response` ships no store, so it has no migration at all. |
| Append-only guarantee | Unaffected: nothing is rewritten, and a re-declared record under a new vocabulary version is a *new* record that `supersedes` its predecessor — the mechanism these packages already use. |

**The digest question is the sharp one.** Excluding the version from
`record_digest()` keeps the change additive but means two records that differ only
in which taxonomy they were written against share a digest. Including it makes the
digest honest and changes every stored record digest. There is no third option, and
it is an owner decision rather than a technical one.

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

## 5. Owner decisions

| # | Decision | Recommendation |
|---|---|---|
| `VV-A` | Placement: on the record (2B) or on the neutral label type (2A)? | **2B.** 2A rewrites the id of every stored declaration in two packages and forces a `CONTRACT_VERSION` move; 2B touches `governance-contracts` not at all. |
| `VV-B` | Does the version enter `record_digest()`? | **No**, initially. It keeps the change additive and stored digests valid. Accept openly that the digest then does not cover the version, and revisit if a consumer needs digest-level distinction. |
| `VV-C` | Does the version enter the derived id? | **No**, in all four. Yes would make re-publishing a vocabulary version fork the identity of unchanged records — the opposite of what the field is for. |
| `VV-D` | Does `purpose_label` get one? | **Not yet.** `LV-E` ratified purpose as an *open shape*, not a closed set; an open shape has no version to cite, so the field would be decorative. Decide with `LV-E`'s first revision, not now. |
| `VV-E` | Required or optional on the record? | **Optional, defaulting to empty.** A required field makes every existing composition root fail to construct a record it constructed yesterday; an empty default reads honestly as "written before versions were recorded". |

---

## 6. Not blocked on this

`[R]` **`LV-F`** — whether general-purpose AI models belong in the
system-classification set — is independent. The field records *which version* was
used, not *which members exist*, so `LV-F` can be ruled before or after.

`[R]` **`LP-5`** — the shared uninterpreted-label base — is only entangled under
2A. If `VV-A` is ruled 2B, this scoping adds nothing wave 5 must work around, which
is a further argument for 2B.

`[G]` **The interpreting layer still does not exist.** Even with the field shipped,
§2's conditions 2 and 3 remain unmet: no owner has ruled what each member *entails*,
and no package that may decide has been given the vocabulary. This field removes one
of four blockers and enables nothing on its own.

---

## 7. Recommended next step

None until `VV-A` to `VV-E` are ruled. If they are ruled as recommended, the
implementation is four packages each gaining one optional field excluded from id and
digest, three schema-version bumps, and no change to `governance-contracts` — small
enough for one change set, and worth nothing until the ballot's other three
conditions have owners.
