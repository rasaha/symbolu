# Governance label vocabulary — ratification ballot

**The load-bearing question:** are the five label vocabularies across the wave-2/3/4
governance packages blocked on an unratified taxonomy? **No — four of the five are
already ratified, as deliberately uninterpreted.** `D-2`, `DE-3`, `VR-3` and `AE-3`
each rule the label a non-empty opaque value with no member set, and each gives the
same ground: a validated enum would make a recording package a classifier. What is
genuinely unruled is narrower and different: **nobody has written the member sets
down anywhere, not even non-normatively; three of the six label fields are bare `str`
while three are neutral contract types, an asymmetry no decision explains; and no
package owns the interpreting layer.** This ballot rules on those three things and
does not disturb `D-2`, `DE-3`, `VR-3` or `AE-3`.

**Status: RATIFIED** on `LV-A` to `LV-E`, 2026-09-09, on the repository owner's
instruction to rule all five and record each with its ground. The owner named the
options for each decision and directed the ruling; each was resolved to the
recommendation §3 and §5 already argued for, and §5 now records the ruling rather
than the recommendation. No decision was carried by anything other than the grounds
written beside it, and any of the five can be overturned by the owner before this
ballot merges.

**Documentation only.** Ratification settles *what the vocabularies are and who owns
them*. It authorizes **no implementation**: no enum, no new neutral type, no package
change, no field. §6's follow-ups each need their own authorization. **Date:**
ballot drafted 2026-09-08, ratified 2026-09-09.

**Correction this ballot records.** The package READMEs say each vocabulary "is
unratified, so the label stays uninterpreted until an owner fixes a taxonomy", and a
prior audit repeated that wording. It is imprecise: the uninterpreted-ness is a
positive ruling repeated four times, most recently in `governance-contracts` 0.8.0
(`AE-3`), not an oversight awaiting a taxonomy. The READMEs should say so; that
correction is listed under recommended follow-up, not performed here.

---

## 0. Baseline verification

`[V]` Default branch `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`,
head `5d572afb`; every citation below re-checked against that head. `[V]` Working
tree clean at drafting time. `[V]`
`ugence-governance-contracts` `0.8.0`; `ai-system-registry` `0.2.0`;
`data-use-admission` `0.2.0`; `vendor-dependency` `0.2.0`; `incident-response`
`0.1.0`.

`[V]` **Five vocabularies, four packages.** The commissioning question names four
taxonomies but five vocabularies, because `data-use-admission` carries two. This
ballot treats all five and keeps the count explicit, since two of the five are
already-landed neutral types and three are not.

---

## 1. What is already ruled, and what is not

| Ruling | Text | Where |
|---|---|---|
| `D-2` | Risk classification is **an uninterpreted label**. "A validated enum would require ratifying a risk taxonomy first, and would make the registry a classifier — a thing that judges rather than records. A refusal reason exists for a blank label, not for an unrecognized one." | `ADR_UGENCE_AI_SYSTEM_REGISTRY_SCOPING.md:43` `[V]` |
| `DE-3` | `UNINTERPRETED`, "following AI System Registry D-2. No enum, taxonomy, lattice, hierarchy, severity, ordering, dominance or implied compatibility." | `ADR_UGENCE_DATA_EGRESS_AUTHORITY_SCOPING.md:62` `[V]` |
| `DE-5` | `DataClassificationLabel` lands in `governance-contracts` first. | `…:64` `[V]` |
| `VR-3` | `SEPARATE_OPAQUE_RISK_LABEL` — distinct from `DataClassificationLabel`; "no grade, enum, taxonomy, ordering, severity, score, dominance or implied eligibility." | `ADR_UGENCE_VENDOR_RISK_SCOPING.md:60` `[V]` |
| `VR-5` | `VendorRiskLabel` lands in `governance-contracts` first; "no second neutral type without another ruling." | `…:62` `[V]` |
| `AE-3` | The assurance-finding label is uninterpreted, on the same grounds. | `contracts/assurance_finding.py:26-37` `[V]` |

**Not ruled anywhere** `[G]`:

1. The member set of any of the five vocabularies, even as non-normative reference text.
2. Why `data-use-admission.purpose_label`, `ai_system_registry.classification_label`
   and `incident_response.severity_label` are bare `str`
   (`declaration.py:135`, `registration.py:177`, `records.py:80`) while the
   classification and vendor-risk labels beside them are neutral contract types.
   No decision covers the purpose or severity fields at all.
3. Who may interpret a label — order it, compare it, gate on it — and where that
   code lives.

---

## 2. Ruling proposed: separate vocabulary from enforcement

The four existing rulings answer *who may interpret* (never the recording package).
They do not answer *which names exist*. Those are separable, and conflating them is
why the vocabularies have stayed empty: closing a member set has felt like
overturning `D-2`, when it need not.

**`LV-1` — Vocabularies are ratified as documentation, owned by Policy Authority,
and never as enums in the recording packages or in `governance-contracts`.**

A ratified vocabulary is a table in a governance document, cited by `policy_ref`.
The recording packages continue to accept any non-blank text and to refuse only a
blank one, exactly as `D-2` describes. `governance-contracts` continues to ship
structural validation only. Nothing in the type surface changes, so no package
becomes a classifier and no `CONTRACT_VERSION` moves.

**What would have to be true for a package to interpret rather than record** —
the same four conditions for all five vocabularies:

1. The member set is ratified and versioned, so "unrecognized" is a decidable
   question rather than a guess.
2. An owner has ruled what each member *entails* — not merely what it names.
   `PROHIBITED` meaning "may not run" is a policy, not a vocabulary entry.
3. Interpretation lives in a package that is already permitted to decide: Policy
   Authority evaluates, ActionGate or Model Selection enforces. A recording
   package that interpreted its own label would cross `D-5` (`records and never
   gates`) directly.
4. The record carries which vocabulary version it was written against, or an old
   record silently re-reads under a new taxonomy. None of the five records carries
   this field today `[G]`.

Until all four hold, a label stays a label. That is the correct posture, not a
temporary one.

---

## 3. The five vocabularies

Each set below is **ratified** by §5, except where a line still carries `[R]`.
Member counts are kept small deliberately: a set nobody can apply consistently is
worse than an opaque string, because it looks decidable. Placement — which type
carries a label — is *not* settled here for three of the five; see §4.

### 3.1 System classification — `ai-system-registry`

Placement `[R]`: **stays capability-local as `str` for now** — see §4, blocked on `LP-5`.

| Member | Meaning |
|---|---|
| `PROHIBITED` | The organization has ruled this class of system may not be built or run at all. |
| `HIGH_RISK` | Consequential to health, safety, rights, livelihood or legal standing; the heaviest obligations attach. |
| `LIMITED_RISK` | Interacts with people or generates content, so disclosure and transparency obligations attach, but not the high-risk set. |
| `MINIMAL_RISK` | No obligation beyond ordinary engineering governance. |
| `UNCLASSIFIED` | Registered before classification was assessed. Not a judgment that risk is low. |

**Ratified by `LV-B` (`TRACK_THE_REGIME`).** The four risk tiers track the EU AI
Act's structure, because a tier set that maps onto no external regime creates a
second mapping to maintain. **This remains a legal and product judgment rather than
a technical one, and is the ruling most open to owner override** — a different regime, or an
organization-internal set, is equally implementable. `UNCLASSIFIED` is proposed
because without it the first registration of an unassessed system forces a false
claim, and `D-2` guarantees no refusal for an unrecognized label anyway.

### 3.2 Data classification — `data-use-admission`

Placement: **already correct.** `DataClassificationLabel` in `governance-contracts`
under `DE-5` `[V]`. No move proposed.

| Member | Meaning |
|---|---|
| `PUBLIC` | Disclosure outside the organization causes no harm. |
| `INTERNAL` | For employees and contracted parties; disclosure is unwanted but not damaging. |
| `CONFIDENTIAL` | Disclosure causes commercial, contractual or reputational harm. |
| `RESTRICTED` | Disclosure causes serious harm to a person or the organization; access is individually granted. |
| `REGULATED` | Carries a statutory handling regime (personal data, health, payment, export-controlled) that overrides the tiers above. |

`[R]` **Not covered by any `LV` letter, so it stays open.** `REGULATED` is proposed
as an orthogonal member rather than a fifth rung
because regulation is a different axis from sensitivity — regulated data can be
low-sensitivity. If the owner prefers strict rungs, `REGULATED` should instead
become a separate flag on the declaration, which is a contract change and out of
this ballot's scope.

### 3.3 Purpose — `data-use-admission`

Placement `[R]`: **stays capability-local as `str`** — and, uniquely among the five,
**this ballot recommends the set stay open.**

Purpose is not a classification of a thing; it is a description of an intent, and
intents are generative. Every closed purpose list in practice grows a member named
`OTHER`, which is the set admitting it should not have been closed. A closed set
here would also collide with the lawful-basis and purpose-limitation vocabularies a
privacy regime already imposes, which this repository does not own.

**Ratified by `LV-E` (`OPEN_SHAPE`):** a *shape* rather than a set — a purpose label
must name an activity and its beneficiary, and a governance document lists
worked examples without closing the set. If the owner wants a closed set anyway,
that is a decision this ballot flags rather than pre-empts.

### 3.4 Vendor posture — `vendor-dependency`

Placement: **already correct.** `VendorRiskLabel` in `governance-contracts` under
`VR-5` `[V]`. No move proposed.

| Member | Meaning |
|---|---|
| `NOT_ASSESSED` | No due-diligence exercise has been performed. |
| `ASSESSED_NO_FINDINGS` | An exercise completed and raised nothing. |
| `ASSESSED_WITH_FINDINGS` | An exercise completed and raised findings; the findings, not this label, say what they are. |
| `ASSESSMENT_LAPSED` | An exercise completed once, and the interval the organization set has since passed. |
| `ASSESSMENT_REFUSED` | The vendor declined to be assessed, or the exercise could not complete. |

**Ratified by `LV-C` (`ASSESSMENT_STATE_SET`). These names deliberately avoid
`APPROVED`, `CONDITIONAL` and `BLOCKED`, and that restraint is the point.** The obvious posture
vocabulary is a permission ladder, and `VR-3` forbids exactly that: "no implied
eligibility". A label reading `APPROVED` would be read as a permission by every
human who saw it, whatever the type says, and `vendor-dependency` "confers no
approval and no onboarding status" (`README.md`, maturity ceiling). The set above
records what was *done*, leaving what it *permits* to Policy Authority. It is
harder to read and it is the honest option; the owner may prefer the ladder and
accept the conflation.

### 3.5 Incident severity — `incident-response`

Placement `[R]`: **stays capability-local as `str` for now** — see §4, blocked on `LP-5`.

| Member | Meaning |
|---|---|
| `SEV1` | Ongoing harm to people, data or money; containment takes precedence over service. |
| `SEV2` | Governed behaviour is materially wrong and a customer or regulator would be entitled to know. |
| `SEV3` | Contained or bounded; correctness or control is degraded without ongoing harm. |
| `SEV4` | Noted for the record; no containment expected. |

**Ratified by `LV-D`: (a) now, (b) when an operational surface needs the query,
(c) refused. Severity is the one vocabulary whose natural form conflicts with the
existing rulings.** Every other label is a name;
severity is a *rank* — `SEV1` is worse than `SEV2`, and that is the point of having
it. `DE-3` and `VR-3` forbid ordering, and `incident-response` follows the same
posture by its README. Three options:

- **(a) Keep it opaque and unordered.** `SEV1`–`SEV4` are four names; any ordering
  lives in the responder's runbook, never in code. Consistent with every existing
  ruling; makes "all incidents at or above SEV2" unanswerable in this repository.
- **(b) Rule severity a distinct ordered kind**, and say plainly that it is not one
  of the uninterpreted labels. This is the first ordered vocabulary in the platform
  and needs its own ruling, not an extension of `DE-3`.
- **(c) Record an explicit rank field alongside the opaque label**, so ordering is
  data a caller supplied rather than meaning the package inferred.

**Recommendation: (a) now, (b) when an operational surface needs the query.**
Option (c) looks like the compromise and is the worst of the three: it makes the
package carry an ordering it must not interpret, and gives two sources of truth
about the same incident.

---

## 4. What is blocked on wave-5 `LP`, and what is not

`LP-1` ruled `DEFER_TO_WAVE_5` and deferred `LP-2` to `LP-5` with it
(`ADR_UGENCE_LIFECYCLE_PROMOTION_SCOPING.md:63-67`) `[V]`.

**Blocked — placement, for three of the five.** `LP-5` asks whether a neutral
`StageLabel` lands in `governance-contracts` "following `DE-5`, `VR-5` and `AE-5`",
and records that "a fourth one-field label may be the point at which a shared
uninterpreted-label base is worth ruling on instead" `[V]`. Three of the five
vocabularies here — system classification, purpose, incident severity — are exactly
that fourth, fifth and sixth one-field label. Landing three new neutral types now
would settle `LP-5` by accident, in the direction that makes the shared base
hardest to adopt later. **So the placement question for those three is deferred to
wave 5 and ruled with `LP-5`, not here.** Their fields stay `str`.

**Blocked — interpretation, for system classification specifically.** Gating on a
classification requires knowing which registration is in force for a running system
in an environment. `ai-system-registry` records no stage (`LP-3`) and never compares
`deployment_environment_ref` (`LP-4`), and `system_identity.py:63` records that
nobody has ratified interpreting an environment reference `[V]`. Until `LP-3` and
`LP-4` are ruled, §2's condition 3 cannot be met for this vocabulary however well
the member set is written.

**Not blocked.** The member sets themselves; the placement of data classification
(`DE-5`, landed) and vendor posture (`VR-5`, landed); and every `LV-1` question in
§2. Wave 5 does not gate writing a vocabulary down.

---

## 5. Ratified decisions

| # | Decision | Ruling | Ground |
|---|---|---|---|
| `LV-A` | Adopt `LV-1` — vocabularies ratified as Policy-Authority-owned documentation, never as enums in the recording packages or `governance-contracts`? | **`ADOPT_LV_1`.** | It closes the real gap — no member set written down anywhere — without disturbing `D-2`, `DE-3`, `VR-3` or `AE-3`. No type surface moves and no `CONTRACT_VERSION` moves, so no recording package becomes a classifier, which is the single ground all four existing rulings gave. The alternative — enums in the packages — would overturn four rulings to solve a documentation problem. |
| `LV-B` | Do the system-classification tiers track the EU AI Act, or an organization-internal set? | **`TRACK_THE_REGIME`.** The four tiers of §3.1 plus `UNCLASSIFIED`. | An internal set creates a mapping to an external regime that must be maintained forever and re-argued at every audit; tracking the regime makes the mapping the identity. `UNCLASSIFIED` is ratified with them because `D-2` guarantees no refusal for an unrecognized label, so without it the first registration of an unassessed system would force a false claim. **This is the ruling most open to owner override**: it is a legal and product judgment, not a technical one, and a different regime is equally implementable. |
| `LV-C` | Vendor posture: the assessment-state set proposed in §3.4, or a permission ladder (`APPROVED` / `CONDITIONAL` / `BLOCKED`)? | **`ASSESSMENT_STATE_SET`.** `NOT_ASSESSED`, `ASSESSED_NO_FINDINGS`, `ASSESSED_WITH_FINDINGS`, `ASSESSMENT_LAPSED`, `ASSESSMENT_REFUSED`. | `VR-3` rules the label carries "no implied eligibility". A member reading `APPROVED` would be read as a permission by every human who saw it, whatever the type says, and `vendor-dependency` "confers no approval and no onboarding status". The assessment-state set records what was *done* and leaves what it *permits* to Policy Authority. It is harder to read; that is the cost of not conflating a record with a permission. |
| `LV-D` | Incident severity: (a) opaque and unordered, (b) a distinct ordered kind, or (c) an explicit rank field? | **`(a)_OPAQUE_AND_UNORDERED` now; `(b)` when an operational surface needs the query. `(c)` is refused.** | (a) is consistent with every existing ruling and costs only that "all incidents at or above SEV2" is unanswerable in this repository — a query nothing today asks. (b) stays available because severity genuinely *is* ranked, and when a surface needs that it deserves its own ruling rather than an extension of `DE-3`. (c) is refused as the false compromise: it makes the package carry an ordering it must not interpret, and creates two sources of truth about one incident. |
| `LV-E` | Purpose: open shape as recommended, or closed set? | **`OPEN_SHAPE`.** A purpose label names an activity and its beneficiary; a governance document lists worked examples without closing the set. | Purpose describes an intent, and intents are generative. Every closed purpose set in practice grows a member named `OTHER`, which is the set admitting it should not have been closed. A closed set here would also collide with the lawful-basis and purpose-limitation vocabularies a privacy regime already imposes, which this repository does not own. |

**What ratification did not decide.** Placement for system classification, purpose
and severity stays deferred to wave 5 with `LP-5` (§4) — these five rulings fix
*which names exist and who owns them*, never *what type carries them*. The three
fields stay bare `str`, and nothing in §6 is authorized.

---

## 6. Recommended follow-up, if this ballot is ratified

Not authorized by it, and each is a separate change:

1. Correct the five READMEs' gap bullets — "unratified, until an owner fixes a
   taxonomy" is not what `D-2`, `DE-3`, `VR-3` and `AE-3` say.
2. Add the vocabulary-version field named in §2 condition 4 to whichever records
   the owner wants interpretable, as a contract change with its own ruling.
3. Carry `LP-5` the finding in §4: three further one-field labels now exist, which
   strengthens the shared-base option it flagged.
