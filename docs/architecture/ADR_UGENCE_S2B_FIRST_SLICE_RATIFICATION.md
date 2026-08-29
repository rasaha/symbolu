# ADR: Ugence S2-B first slice — owner ratification of the design proposals

**Status:** **Accepted (ratified owner declaration) — documentation only.**
This ADR records the owner's answers to the thirteen questions put by the S2-B first-slice
design specification. **No implementation is authorized by this ADR, and none exists.**
The S2-B implementation gate remains **closed** — see §5.

**Date:** 2026-08-29.

**Decision owner:** the repository owner, who is the sole ratifying authority for S2-B
(`ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md:23`).

**Baseline:** default branch `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`,
head `90696d16ed8e9b9942252fe297c44bc3d16393a1`.

**What was ratified, exactly.** The thirteen-item ballot in §7 of
[`S2B_FIRST_SLICE_DESIGN_SPECIFICATION.md`](S2B_FIRST_SLICE_DESIGN_SPECIFICATION.md)
**as that file stood at commit `e6003a2a2cadf42926c34828b30c2f2de3aad967`** — SHA-256
`9a35347dfd8d97a779ddec365de73cffcc1f3c5eeaffa2c0753e5c05b15de0ae`, 805 lines. `[V]` That
commit is the immutable record of the text answered. The file has since gained a
forward-pointer to this ADR in its header and therefore carries a different hash; the
ratified text is the version at that commit, not the current working copy.

**Recorded exactly as ruled:**
`Q1=A Q2=A Q3=A Q4=A Q5=A Q6=A Q7=A Q8=A Q9=A Q10=A Q11=A Q12=A Q13=A` — the recommended
path in full, with no item answered against recommendation and no coupling invoked.

**Numbering.** `[R]` This ADR assigns **no new OD number and no new `S2B-D` number.** OD-1
through OD-10 remain the Agentic Proposer decision record; `S2B-D1` – `S2B-D8` and rider
`R1` remain the S2-B scoping record. Neither is extended, renumbered or reopened. These
rulings are recorded as the dated owner declaration **`S2B-S1-Q1` – `S2B-S1-Q13`**, scoped
to this ADR.

**Governing and unchanged:**
[`ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md`](ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md)
(`S2B-D1` – `S2B-D8`, rider `R1`, the §8 gate);
[`ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md`](ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md)
(D1–D10, O-1 – O-4, OD-1 … OD-10, A11–A13);
[`ADR_UGENCE_POLICY_AUTHORITY.md`](ADR_UGENCE_POLICY_AUTHORITY.md) (P-1 … P-11);
[`ADR_UGENCE_REASONING_COMPUTE_GOVERNANCE_RCG0_SCOPING.md`](ADR_UGENCE_REASONING_COMPUTE_GOVERNANCE_RCG0_SCOPING.md)
(RCG-D1 … RCG-D10);
[`S1_CONTRACT_AND_EQUATION_SPECIFICATION.md`](../../packages/capabilities/agentic-proposer/docs/S1_CONTRACT_AND_EQUATION_SPECIFICATION.md).

**Evidence labels.** `[V]` verified against this repository at the cited `file:line`;
`[I]` architectural inference; `[R]` an owner ruling; `[G]` an unresolved gap.

---

## 1. The thirteen rulings

Each is recorded in the words of the option the owner selected. The design specification's
§2 holds the supporting proposal, the repository evidence, the ENTAILED/CHOSEN split, the
rejected alternatives, and the guard obligation for each.

### `S2B-S1-Q1` — Vocabulary admission `[R]`

**Ruled: A.** A **closed** strategy vocabulary, admitting members only by three criteria —
externally evidenceable; not a contract mechanism or an outcome (OD-5's four exclusions);
provider-neutral — with at least two members, **no default member** and **no escape
member** (`OTHER` / `UNSPECIFIED` / `NONE`).

`[R]` **No member is ratified by this ruling, and none may be inferred from it.**

### `S2B-S1-Q2` — Contract shape `[R]`

**Ruled: A.** `CognitiveRoleContract` 10 → 11 fields, the added field being a **C5a policy
reference only**. `ProposerAdvisory` 27 → 30 fields, adding the governing policy identity,
the policy version and one scalar declared-strategy assertion — **all C5b, all
identity-participating, all required and non-nullable**. The private unsigned payload
26 → 29. `ProposerProcessRecord` stays 18. `AdvisoryCandidateSet` stays 12.

`[R]` **No field name is ratified.**

### `S2B-S1-Q3` — Record field class `[R]`

**Ruled: A.** `ProposerProcessRecord.declared_strategy` is **narrowed from C5c to C5b**, so
both sides of rider R1's equality carry the same class. `[V]` OD-1 states that this
narrowing, while the field stays outside `P_unsigned`, needs no new ratification
(`ADR_UGENCE_AGENTIC_PROPOSER_MVP_READINESS.md:633`); this declaration takes it.

`[R]` OD-1's rider is **not** engaged: the advisory's declared-strategy assertion is a new
field, not this one made identity-participating by reclassification.

### `S2B-S1-Q4` — Normalization `[R]`

**Ruled: A.** Membership is **exact codepoint equality** between two C5b-constrained ASCII
values. No normalizer, no casefolding, no trimming, no splitting. `set_paths` and
`nfc_paths` stay `frozenset()`.

### `S2B-S1-Q5` — Builder signatures `[R]`

**Ruled: A.** `build_proposer_advisory` and `build_advisory_revision` each gain exactly two
keyword-only parameters — the injected resolver and the producer's declared-strategy
assertion — and **no policy-identity or version parameter**.
`build_proposer_process_record` replaces `declared_strategy` and `advisory_digest` with one
`advisory` parameter and **derives both** (rider R1).

`[V]` The record-builder change sits **outside** A13's enumeration of four builders and
carries its own public-surface ratification, which `S2B-S1-Q6` supplies
(`ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md:243-251`). A13 stands intact for
its four.

### `S2B-S1-Q6` — Public surface `[R]`

**Ruled: A.** The Agentic Proposer curated surface moves **46 → 51 names**: the strategy
vocabulary, the resolver protocol, the resolver request shape, the resolver response shape,
and the replay function. **No removals, no renames.**

`[R]` **No name is ratified.** `[V]` No exported name may begin with `Proposal` or
`Recommendation` (D7).

### `S2B-S1-Q7` — Package version `[R]`

**Ruled: A.** `0.3.0`, moved in the **same change set** as the fields, vocabulary,
protocol, replay function and tests — never ahead of them, on the I8 ordering OD-7 part 8
already established.

### `S2B-S1-Q8` — Exception type `[R]`

**Ruled: A.** **No new exception type.** The `S2B-D5=A` construction refusal is discharged
by the existing H2 surface — `pydantic.ValidationError` for a value failing its own field
constraint, and `CrossContractViolationError` for a rule comparing independently
constructed instances. H2 stays at **five classes of failure**.

### `S2B-S1-Q9` — Resolver protocol `[R]`

**Ruled: A.** A package-owned `runtime_checkable` Protocol, implemented elsewhere, with one
keyword-only `resolve(*, request) -> response`. The request carries the policy reference,
tenant, case and a **caller-supplied** `as_of`. The response carries the policy identity,
the version **as a string**, the permitted set, and an **echo of the reference**. **No
`verified` boolean.** Identity and version are stamped **from the response only**
(`S2B-D7=A`).

### `S2B-S1-Q10` — Rider R1 semantics `[R]`

**Ruled: A**, including the `advisory_digest` derivation and the digest-equality check.
The record's `declared_strategy` is derived from the proposal-bound declaration at
construction; exact equality is re-established at replay.

`[R]` **That equality proves correspondence between two observable fields only.** It never
proves conformance with private reasoning, and never proves that the declared procedure was
executed (`ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md:303-306`).

### `S2B-S1-Q11` — Replay function `[R]`

> `[R]` **AMENDED 2026-08-29 by `S2B-R2-Q8=A`**
> ([`ADR_UGENCE_S2B_ROUND2_VOCABULARY_RATIFICATION.md`](ADR_UGENCE_S2B_ROUND2_VOCABULARY_RATIFICATION.md)).
> A **sixth** check is added: the declared token equals the token the advisory's own shape
> yields, replay returning `False` on mismatch. The five checks below stand unchanged and in
> order; the list is no longer closed at five. No other part of this declaration is amended.

**Ruled: A.** One **new** exported function, returning `bool`, never raising, taking exactly
`S2B-D8=B`'s four inputs, checking in order: policy identity and version match; the role's
reference resolves to the same policy; the permitted set is non-empty; the declared strategy
is a member; the record's declaration **and** `advisory_digest` match the advisory. It emits
**no disposition and no reserved authority term**.

### `S2B-S1-Q12` — Construction order `[R]`

**Ruled: A.** Resolution and the permission test occur **before** the OD-7 evaluation
sequence, so an unpermitted run **never reaches the injected domain evaluator**. `[I]` This
is externally observable, which is why it required a ruling rather than an implementer's
choice.

### `S2B-S1-Q13` — Implementation gate `[R]`

**Ruled: A.** Ratifying `Q1` – `Q12` satisfies the §8 gate **except the vocabulary
members**, which must still arrive together with the field that carries them per OD-5(iii).
**Code may not begin until they do.**

---

## 2. What is now ratified

`[R]` The architectural scope and binding semantics of S2-B were ratified on 2026-08-28
(`S2B-D1` – `S2B-D8`, rider `R1`). `[R]` The first slice's **contract shape, normalization
rule, builder signatures, public-surface delta, package version, exception treatment,
resolver protocol, derive-and-equality rule, replay function, construction order and
vocabulary admission criteria** are ratified by this declaration.

---

## 3. What remains ungranted

`[G]` **The strategy vocabulary's members.** `S2B-S1-Q1` ratifies the admission criteria and
the closure rules; it ratifies **no member**. OD-5(iii) requires the concept and the
vocabulary that gives it content to arrive together, so the members must be ratified in the
same act that declares the field.

`[R]` Also ungranted, and unchanged by this declaration: every **concrete name, spelling,
default and encoding**; strategy **composition**, ordering or subordinates (`S2B-D3=A`);
**mandate-level** narrowing and per-invocation authorization (`S2B-D4=A`); **required**
strategies; the **operational-disposition owner** for a structural permission failure
(`S2B-D5=A`); **observable-procedure conformance replay** and any producer of observable
reasoning stages (`S2B-D8`); registration of the strategy-permission **policy family** and
its Policy Authority adapter; a **strategy-policy registry**; any **binding to Reasoning
Compute Governance**; and the Agent Constitution.

`[G]` **No second Policy Authority family is registered**, so `S2B-D1=A` remains
implementation-blocked independently of this declaration
(`ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md:343-344`).

`[G]` **No component records observable reasoning stages**
(`.../ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md:346-347`).

---

## 4. Non-claims carried forward

This declaration changes nothing in the S2-B ADR's §6. Reasoning Strategy Permission still
does not claim, and must never be described as claiming, that a model's private reasoning
becomes deterministic, that a declared strategy proves the model internally followed it,
that Ugence can inspect or replay private chain-of-thought, or that permission to use a
strategy authorizes additional compute, tools, evidence access or consequential execution.
`[R]` It duplicates no part of RCG, and **S2-B still creates no binding to Reasoning Compute
Governance.**

---

## 5. Implementation gate — still closed

> `[R]` **SUPERSEDED 2026-08-29.** The vocabulary's members were ratified by `S2B-R2-Q1=A`,
> and `S2B-R2-Q6=A` records that all six §8 gate items are satisfied. **The gate is now
> open** — see
> [`ADR_UGENCE_S2B_ROUND2_VOCABULARY_RATIFICATION.md`](ADR_UGENCE_S2B_ROUND2_VOCABULARY_RATIFICATION.md)
> §5. The section below records the position as it stood on that date and is retained as
> history, not as current status.

`[R]` **No S2-B code may begin.** Per `S2B-S1-Q13=A`, five of the §8 gate's six items are
satisfied by this declaration — normalization profile, contract shape, builder signatures,
public surface, package version — and the sixth, the **vocabulary**, is satisfied only as to
its **admission criteria**. Its **members** are outstanding, and the gate is not open until
they are ratified.

`[I]` This is the A11/A12 pattern the S2-B ADR already names: "unblocked on ratification
grounds" is not "authorized to implement"
(`ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md:374-376`). Ratification of a
design is not authorization to write production code, and this ADR does not claim it is.

**The next ratification** is the strategy vocabulary's members, admitted under
`S2B-S1-Q1`'s three criteria, declared together with the field that carries them.

---

## 6. Review provenance

`[I]` The design specification these rulings answer was **independently reviewed twice**,
read-only against this repository, under an artifact-identity check binding each review to
exact content. Both returned **`SOUND_WITH_CORRECTIONS`** with **no blocker**: no accidental
ratification, no hidden contract commitment, no private-chain-of-thought confusion, no
conflict with S2-A, A13, RCG-0, Policy Authority or the merged S2-B ADR, and no duplication
of RCG. Both rounds' corrections were citation accuracy and ballot construction, and both
were applied before the ballot was put to the owner. `[I]` Those reviews are deliberative
evidence, not repository sources; **this ADR and the commit it names are the canonical
record.**

---

## 7. What this ADR changed

One new documentation file, plus a one-line forward-pointer added to the design
specification's header. **No production source, test, specification, readiness ADR, RCG
document, CHANGELOG, `public_api.json`, `version.py`, package metadata, CI workflow or
platform-freeze artifact is modified.** The Agentic Proposer stays at `0.2.0` with
forty-six authorized public names until the implementation change set that `S2B-S1-Q7`
governs is itself authorized.
