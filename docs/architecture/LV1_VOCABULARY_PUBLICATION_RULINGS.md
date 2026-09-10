# `LV-1` vocabulary publication — owner rulings `PUB-1` to `PUB-5`

**The load-bearing ruling is the ordering.** Five vocabularies are published as
separate, immutable specifications **first**; only then may a record contract cite
one. That inverts how this work would naturally have been sequenced — a field is
easier to add than a specification is to write — and it is right, because a binding
to a referent that does not exist is a field that records nothing while appearing to
record provenance.

**Status: RATIFIED** on `PUB-1` to `PUB-5` by the repository owner, 2026-09-09.
**Date:** 2026-09-09.

**No implementation is authorized by this document alone.** `PUB-2` authorizes the
record contract changes, but `PUB-1` sequences them behind publication, and `PUB-3`
and `PUB-4` each require their own implementation authorization. Nothing here adds a
field, a type, a schema or a member.

---

## 0. Baseline verification

`[V]` Default branch head `d064decb`; every citation below read at that head. `[V]`
The ratified label-vocabulary ballot (`GOVERNANCE_LABEL_VOCABULARY_BALLOT.md`) and
the ratified vocabulary-binding scoping (`VOCABULARY_VERSION_FIELD_SCOPING.md`) are
both merged; these rulings close open items in each and are recorded here because
they span both.

---

## `PUB-1` — Publish five separate, immutable vocabulary specifications

Five stable vocabulary identifiers, each published at initial version `1.0.0`:

| Identifier | Governing ruling | Bound by |
|---|---|---|
| `eu-ai-act-system-classification` | `LV-B` | `SystemRegistration.classification_label` |
| `data-classification` | `LV-A` / `DE-3` | `DataUseDeclaration.classification` |
| `data-use-purpose` | `LV-E` (open shape) | `DataUseDeclaration.purpose_label` |
| `vendor-dependency-assessment-state` | `LV-C` | `VendorDependencyDeclaration.risk_posture` — renamed by `PUB-1a` below |
| `incident-severity` | `LV-D` | `IncidentRecord.severity_label` |

**Each publication is immutable**, and identified by all six of:

1. vocabulary identifier;
2. version;
3. authoritative content digest;
4. scope or tenant, where applicable;
5. governing `LV` ruling;
6. normative members — or, for an open vocabulary, its interpretation rules.

**Versioning.** `MAJOR.MINOR.PATCH`, no `v` prefix. **No mutable `latest`
reference is created.** Any change to normative membership, meaning, ordering or
interpretation requires a **new major version**. A citation or wording correction
that *provably* changes no meaning may take a **patch** version. **Minor versions
are reserved** until an additive-compatibility rule is separately established.

**Published, 2026-09-09** `[V]` — **all five**, at
`docs/vocabularies/<identifier>/1.0.0.json`:
`eu-ai-act-system-classification`, `data-classification`, `data-use-purpose`,
`incident-severity`, and `vendor-dependency-assessment-state` under the corrected name
`PUB-1a` gives it below.

Each file carries its own digest, and the digests are deliberately **not** repeated
here: a second copy in prose is a second source of truth that nothing keeps honest.
What is worth recording is that they are enforced. `[V]`
`scripts/check_vocabulary_publications.py` recomputes each digest — SHA-256 over the
specification's canonical JSON with the digest field removed — so an **edit to a
published version fails CI** rather than passing under a stale digest. The same gate
holds each closed vocabulary's members to the ballot section that ratified them,
refuses a mutable `latest` in any form, and refuses any file claiming Policy Authority
issuance. Its twin, `tests/boundaries/test_vocabulary_publications.py`, provokes each
of those failures, so the gate is known to be able to fail. Immutability is enforced
here, not asserted.

**What publication here is, and is not.** These repository specifications establish
the **canonical vocabulary content**. They do **not** constitute issuance by Policy
Authority, and nothing in the repository may describe them as an issued or signed
organizational policy. Production authority still requires an **issued Policy
Authority coordinate**. `LV-1` said the vocabularies are Policy-Authority-*owned*;
this ruling supplies the content, not the issuance.

### `PUB-1a` — the fifth vocabulary is renamed `vendor-dependency-assessment-state`

**Resolved under owner delegation, 2026-09-09.** The owner named three options and
directed the choice; option **(a), rename**, is taken, and the ground is recorded here
because the delegation does not make the reasoning less inspectable.

The conflict `PUB-1` flagged was real. `[V]` `LV-C` ratified an **assessment-state**
set — `NOT_ASSESSED`, `ASSESSED_NO_FINDINGS`, `ASSESSED_WITH_FINDINGS`,
`ASSESSMENT_LAPSED`, `ASSESSMENT_REFUSED` — and refused a permission ladder on the
explicit ground that it "would read as the implied eligibility `VR-3` forbids,
whatever the type says". `VR-3` itself rules the label carries "no grade, enum,
taxonomy, ordering, severity, score, dominance **or implied eligibility**"
(`ADR_UGENCE_VENDOR_RISK_SCOPING.md:60`). A vocabulary called `…-permission` whose
members are assessment states would reinstate by filename the conflation `LV-C` was
decided to prevent.

**Why (a) and not the other two.** The name is what a reader sees first, and that is
the whole reason `LV-C` rejected `APPROVED`, `CONDITIONAL` and `BLOCKED` — not because
the *type* would confer eligibility, which it never could, but because the *words*
would be read as conferring it. Option (b) keeps the misleading word and appends a
disclaimer, which is the shape of the defect rather than its repair: a reader who
stops at the identifier is exactly the reader the disclaimer does not reach. Option
(c) is factually wrong about this repository — `risk_posture` has a ratified vocabulary
today, and declaring it unbound would misdescribe a field that `VendorRiskLabel`
already constrains (`vendor-dependency/src/ugence_vendor_dependency/declaration.py:130`)
`[V]`.

Naming the vocabulary after its members costs nothing and removes the conflation at
its source. **The vocabulary that a future permission ladder would need does not exist,
has no ratified members, and is not reserved by this ruling** — should the owner ever
want one, it is a new vocabulary requiring its own ballot, and `VR-3` would have to
move first.

**Published under the corrected name** `[V]`, at
`docs/vocabularies/vendor-dependency-assessment-state/1.0.0.json`. The specification
carries an `eligibility` field fixed at `null` beside the `ordering` field the other
closed vocabularies carry: the two things `VR-3` forbids this label to imply are
recorded as absent rather than left to be inferred from a silence. Its five members are
held to ballot §3.4 by the same gate that holds the other four, so the rename changed
the identifier and provably nothing else.

---

## `PUB-2` — Record-local authoritative references, authorized

The contract changes the scoping document listed as unauthorized are **authorized**,
with **no additional neutral type added to `governance-contracts`**:

| Record | Bindings |
|---|---|
| `SystemRegistration` | one system-classification vocabulary binding |
| `IncidentRecord` | one severity vocabulary binding |
| `DataUseDeclaration` | **two independent** bindings — classification and purpose |
| `VendorDependencyDeclaration` | `policy_ref` reused **only if** it normatively identifies the exact permission-vocabulary policy; otherwise a distinct permission-vocabulary reference |

`[V]` **Determination on the `VendorDependencyDeclaration` condition: it does not,
so a distinct reference is required.** `VR-4` rules `policy_ref` "one non-empty
**opaque** `policy_ref` string… The package must not resolve, verify, interpret or
fetch it" (`ADR_UGENCE_VENDOR_RISK_SCOPING.md:61`). An opaque string that the
package is forbidden to interpret cannot *normatively identify* anything; it
references some policy, with no guarantee which. The condition fails on the ruling's
own terms, and `vendor-dependency` gains a distinct permission-vocabulary reference
rather than overloading `policy_ref`.

**Every binding must carry or resolve to the authoritative vocabulary identity, its
exact version, and its content digest. A bare version string is insufficient.**

Implement as **new record and schema versions**. Include the bindings in record
digests, and in derived ids **wherever the associated label already participates in
identity** — `DataUseDeclaration` and `VendorDependencyDeclaration`, per the
ratified `VV-B` and `VV-C`. **An absent reference is never defaulted to the current
vocabulary.**

**Sequenced behind `PUB-1`:** no record reference is implemented before the
vocabulary it cites is published.

---

## `PUB-3` — `LV-F`: general-purpose AI models get a separate record

**GPAI values are not added to the AI-system classification vocabulary.** A
general-purpose AI model and an AI system are **different regulated objects** under
the Act, and flattening them into one ladder would misdescribe both.

A separate `GeneralPurposeAIModelRegistration` record is to be scoped, distinguishing:

- the object's status as a general-purpose AI model; and
- whether it is classified or designated as presenting **systemic risk**.

These are two facts, not one rung. **Until that record is implemented, the explicit
disclosure that GPAI models are uncovered is retained** in `ai-system-registry` and
in the ballot — the gap stays visible rather than being closed on paper.

Scoping and implementation each need their own authorization.

---

## `PUB-4` — `REGULATED` is orthogonal, not a fifth classification rung

`REGULATED` is **removed from the data-classification ladder**, which becomes
`PUBLIC`, `INTERNAL`, `CONFIDENTIAL`, `RESTRICTED`. Regulatory applicability
**coexists with** any sensitivity classification rather than displacing one: regulated
data can be low-sensitivity, which is exactly why a rung was the wrong shape.

It is to be scoped as a **separate status**, and preferably not a Boolean —
`REGULATED`, `NOT_REGULATED`, `UNDETERMINED`, carrying the applicable legal or
policy references. A Boolean cannot express "nobody has assessed this", which is the
state most records will be in.

This contract change requires separate implementation authorization.

---

## `PUB-5` — Official Journal citations, adopted

| Member or object | Citation |
|---|---|
| `PROHIBITED` | Article 5, "Prohibited AI practices" |
| `HIGH_RISK` | Article 6, with Annexes I and III |
| `TRANSPARENCY_OBLIGATIONS` | Article 50 |
| GPAI model classified as presenting systemic risk | Article 51 |
| General GPAI-provider obligations | Article 53 |
| Additional obligations, GPAI with systemic risk | Article 55 |

**No article is invented for `MINIMAL_RISK` or `UNCLASSIFIED`.** "Minimal or no
risk" is the Commission's explanatory description of systems the Act subjects to no
specific rules — it is not established by a classification article. `UNCLASSIFIED`
is an internal registry state with no statutory counterpart at all. Both stay
uncited, and that is the accurate record rather than a gap.

GPAI is governed separately in Chapter V, which is the statutory basis for `PUB-3`
treating it as a different object rather than another rung.

---

## Sequencing, and what each ruling still needs

| Step | Authorized by | Blocked on |
|---|---|---|
| ~~Publish all five vocabularies at `1.0.0`~~ | `PUB-1`, `PUB-1a` | **done** — `docs/vocabularies/` |
| ~~Implement record bindings~~ | `PUB-2` | **done** — all four packages, `[V]` |
| Scope `GeneralPurposeAIModelRegistration` | — | its own authorization (`PUB-3`) |
| Scope the regulatory-status field | — | its own authorization (`PUB-4`) |

`[G]` **The interpreting layer still does not exist.** `PUB-1` and `PUB-2` together
satisfy the ballot's §2 conditions 1 and 4. Conditions 2 and 3 remain unmet: no
owner has ruled what each member *entails*, and no package permitted to decide has
been given the vocabulary. Publishing and binding make interpretation *possible*
later; they do not make any package an interpreter now.

**The mirror coordinates are not in scope here.** They are registry configuration
and credentials — an infrastructure task, not a software-design ruling.
