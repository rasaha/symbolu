# ADR: Ugence S2-B Round 2 — owner ratification of the strategy vocabulary and names

**Status:** **Accepted (ratified owner declaration) — documentation only.**
This ADR records the owner's answers to the eight questions put by the S2-B Round 2
vocabulary-and-naming proposal. **No implementation is performed by this ADR, and none
exists.** It does, however, **close the last open item of the S2-B §8 implementation
gate** — see §5.

**Date:** 2026-08-29.

**Decision owner:** the repository owner, who is the sole ratifying authority for S2-B
(`ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md:23`), ratifying personally.

**Baseline:** default branch `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF`,
head `90696d16ed8e9b9942252fe297c44bc3d16393a1`.

**What was ratified, exactly.** The eight-item ballot in §7 (Part F) of
[`S2B_ROUND2_VOCABULARY_AND_NAMING_PROPOSAL.md`](S2B_ROUND2_VOCABULARY_AND_NAMING_PROPOSAL.md)
**as that file stood at commit `646dc116a68da2780ce1d5f13380eeba5dd34de7`** — document
SHA-256 `bd8cb7af88a3a8dad6e247305afb1ec5c7875b698a1d7a69188b13a16a589053`, 596 lines,
ballot-block SHA-256
`fdc8c6ee6c6d2cfa9e6560c06d4f4acd2e9185e1754ff068c0682cc4e112148d`. `[V]` The owner quoted
all four values in the ratification, and all four were verified against that commit before
this ADR was written. The file has since gained a forward-pointer to this ADR in its header
and therefore carries a different hash; the ratified text is the version at that commit.

**Recorded exactly as ruled:**
`R2-Q1=A R2-Q2=A R2-Q3=A R2-Q4=A R2-Q5=A R2-Q6=A R2-Q7=A R2-Q8=A` — the recommended path in
full.

**Numbering.** `[R]` This ADR assigns **no new OD number and no new `S2B-D` number.** These
rulings are recorded as the dated owner declaration **`S2B-R2-Q1` – `S2B-R2-Q8`**, scoped to
this ADR.

**Evidence labels.** `[V]` verified against this repository at the cited `file:line`;
`[I]` architectural inference; `[R]` an owner ruling; `[G]` an unresolved gap.

---

## 1. The eight rulings

### `S2B-R2-Q1` — Vocabulary members `[R]`

**Ruled: A.** Exactly three members, defined over **two observable axes and nothing else** —
candidate count, and parent binding:

| Member | Definition |
|---|---|
| `SINGLE_CANDIDATE_UNREVISED` | exactly one candidate, binds no parent |
| `MULTI_CANDIDATE_UNREVISED` | two or more candidates, binds no parent |
| `REVISED_ADVISORY` | binds a parent, at any candidate count |

`[R]` **No member carries a condition on the selector.** `[V]` Under OD-8 selection-policy v1
more than one qualifying candidate produces no selection
(`.../S1_CONTRACT_AND_EQUATION_SPECIFICATION.md:2653-2654`), so a lawful multi-candidate
advisory may carry a null selector; a selector condition would leave it matching no member.

`[R]` Each is named for **artifact shape, never for processing**. Together they are
**disjoint and exhaustive**, so `S2B-D3=A`'s one-strategy-per-invocation rule always has
exactly one lawful answer.

### `S2B-R2-Q2` — Recorded rejections `[R]`

**Ruled: A.** Four candidates are **rejected and inadmissible without a new ruling**:
`STAGED_DECOMPOSITION` (no observable stages exist); `SELF_CRITIQUE` / `REFLECTION`
(private model behaviour); `TOOL_AUGMENTED` (evidence collection, an OD-5 exclusion by
name); `EXTENDED_REASONING` (a model capability tier barred by `S2B-D2=A`, and a compute
claim).

### `S2B-R2-Q3` — Field names `[R]`

**Ruled: A.** `strategy_policy_ref` on `CognitiveRoleContract`; `strategy_policy_id` and
`strategy_policy_version` on `ProposerAdvisory`; and `declared_strategy` on
`ProposerAdvisory` — **the same name the process record already uses**, which is what makes
rider R1's equality legible at every call site.

### `S2B-R2-Q4` — Public names `[R]`

**Ruled: A.** `ReasoningStrategy`, `StrategyPolicyResolver`, `StrategyPolicyRequest`,
`StrategyPolicyResponse`, `verify_strategy_permission` — the five names of the ratified
46 → 51 public-surface movement.

### `S2B-R2-Q5` — Representation `[R]`

**Ruled: A.** **Both** `declared_strategy` fields are typed as the `ReasoningStrategy` enum,
**fail-closed at construction**. `[V]` The options were not equivalent: a stored space-free
value passes a C5b `Token` and fails the enum, so A invalidates strictly more stored records;
the ruling accepts that in exchange for catching a non-member at construction rather than at
replay.

### `S2B-R2-Q6` — Gate `[R]`

**Ruled: A.** With `Q1` – `Q5` ratified, §8's sixth item — the vocabulary — is satisfied **in
full**, and the **implementation gate opens**. `[G]` Subject to the standing fact that no
strategy-permission policy family is registered with Policy Authority, which blocks
**execution** regardless (`ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md:343-344`).

### `S2B-R2-Q7` — Character of the vocabulary `[R]`

**Ruled: A.** The vocabulary is accepted on stated terms. `[R]` Every member is defined by
observable artifact shape, so a declaration is **derivable** from the advisory. On the five
ratified checks **alone**, a policy governs **which token a role may declare** and nothing
more. `[R]` **With `S2B-R2-Q8=A` that changes** — see §2.

### `S2B-R2-Q8` — Shape-correspondence check, and the amendment `[R]`

**Ruled: A.** `S2B-S1-Q11=A` is **amended** to add a **sixth** replay check: the declared
token equals the token the advisory's own shape yields, replay returning `False` on mismatch.

`[R]` **The owner expressly approved this as an amendment to `S2B-S1-Q11=A`**, acknowledging
its stated limits and its future vocabulary-expansion cost, and declared that **no other
prior ruling is amended.**

---

## 2. What the amendment establishes, and what it does not

`[R]` **The composition.** Under `S2B-R2-Q7=A` with `S2B-R2-Q8=A`:

* `S2B-S1-Q11=A` check four establishes **declared token ∈ permitted set**
  (`ADR_UGENCE_S2B_FIRST_SLICE_RATIFICATION.md:146-150`);
* the new sixth check establishes **declared token = shape-derived token**;
* therefore, jointly, **shape-derived token ∈ permitted set**.

`[R]` What a policy governs is therefore the **replay-verifiable shape of the advisory**, not
merely what its producer may declare. Neither check delivers this alone. The declared token
remains **informationally redundant** — a verifier could compute it — but it is a
**digest-bound commitment**, and the conjunction is what is enforceable. It is established at
**replay**, never by construction.

`[R]` **The limits are not widened, and must never be described as widened.** This
establishes **nothing** about private reasoning; it does **not** prove that a declared
procedure was *executed*; and it establishes **no** observable-stage conformance beyond what
the advisory's own shape shows
(`ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md:303-311`).

---

## 3. The amendment perimeter

`[R]` **`S2B-S1-Q11=A` is the whole of it.** Three rulings are expressly **not** amended:

* `[R]` **`S2B-D8=B` is not reopened.** The sixth check reads no stage records and stays
  within `S2B-D8=B`'s four inputs. `[R]` It **does** discharge early, **for these three
  members only**, part of what `S2B-D8=B` named a later stage
  (`.../ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md:216-218`). Disclosed, not
  glossed. Observable-procedure conformance replay in general remains deferred.
* `[R]` **`S2B-S1-Q10=A` is not amended.** That rider governs rider R1's field equality,
  which still proves nothing about private reasoning
  (`ADR_UGENCE_S2B_FIRST_SLICE_RATIFICATION.md:140-142`). The sixth check is a different
  check over two observable facts.
* `[R]` **`S2B-D5=A` is not amended.** `[V]` Its final triggering condition is already "or
  replay cannot establish correspondence"
  (`.../ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md:145-147`), which absorbs a
  declaration-to-shape mismatch, and the sixth check's structural semantics — replay returns
  `False`, no disposition, no reserved authority term — are exactly `S2B-D5=A`'s ratified
  result.

`[R]` OD-1 … OD-10, A11–A13, P-1 … P-11, RCG-D1 … RCG-D10, `S2B-D1` – `S2B-D8`, rider `R1`
and `S2B-S1-Q1` – `S2B-S1-Q13` are otherwise unchanged.

---

## 4. Disclosed forward cost

`[R]` **The three members tile every lawful advisory, so no fourth can simply be added.** Any
later member — including `STAGED_DECOMPOSITION`, admissible only if observable stages ever
exist — would overlap one of the three. It contradicts the disjoint-and-exhaustive property
`S2B-R2-Q1=A` ratifies, and under `S2B-R2-Q8=A` it additionally leaves the shape-derived
comparison with no unique answer. Admitting one would require **either** a redefinition
restoring the tiling **or** the composition ruling `S2B-D3=A` deferred
(`.../ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md:123-127`) — and, on either
route, a change to the ratified sixth check.

`[R]` The owner acknowledged this cost in ratifying `S2B-R2-Q8=A`.

---

## 5. Implementation gate — now OPEN

`[R]` **All six items of the §8 gate are ratified.**

| §8 gate item | Satisfied by |
|---|---|
| the strategy **vocabulary** | `S2B-S1-Q1=A` (criteria) + `S2B-R2-Q1=A` (members) |
| the **normalization** profile | `S2B-S1-Q4=A` |
| the concrete **contract shape** | `S2B-S1-Q2=A`, `Q3=A` + `S2B-R2-Q3=A`, `Q5=A` |
| the **builder signatures** | `S2B-S1-Q5=A` |
| the **public surface** | `S2B-S1-Q6=A` + `S2B-R2-Q4=A` |
| the **later package version** | `S2B-S1-Q7=A` (`0.3.0`) |

`[R]` **S2-B implementation may begin.** This reverses the position recorded at
`ADR_UGENCE_S2B_FIRST_SLICE_RATIFICATION.md:§5`, which held the gate closed pending the
vocabulary's members; those members are ratified here.

`[G]` **Execution nevertheless remains blocked**, and this is not a gate item: **no
strategy-permission policy family is registered with Policy Authority**
(`.../ADR_UGENCE_S2B_REASONING_STRATEGY_PERMISSION_SCOPING.md:343-344`). `[I]` Implementation
against a stubbed `StrategyPolicyResolver` is nonetheless possible on the
`DomainEvaluationProvider` precedent, since the protocol is injected and this package
implements no resolver.

`[R]` **What implementation must still respect, unchanged:** the ratified construction and
replay order; `S2B-D7=A`'s package-stamping discipline; the C3 bar on numeric values; the C6
canonicalization freeze; the bar on emitting any denial or reserved authority term; and every
non-claim in the S2-B ADR's §6.

---

## 6. Review provenance

`[I]` The proposal these rulings answer was **independently reviewed five times**, read-only
against this repository, each review bound to exact content by an artifact-identity check.
Four returned `SOUND_WITH_CORRECTIONS`; the fifth, asked to judge the ballot, recommended
this path and contributed the composition argument recorded in §2. `[I]` One review finding
was rejected on the evidence as wrong about the repository. `[I]` Those reviews are
deliberative evidence, not repository sources, and no review session ratified anything —
**this ADR and the commit it names are the canonical record.**

---

## 7. What this ADR changed

One new documentation file, plus a forward-pointer added to the Round 2 proposal's header and
an amendment notice added beside `S2B-S1-Q11` in the first-slice ratification ADR. **No
production source, test, specification, CHANGELOG, `public_api.json`, `version.py`, package
metadata, CI workflow or platform-freeze artifact is modified.** The Agentic Proposer remains
at `0.2.0` with forty-six authorized public names until the implementation change set
`S2B-S1-Q7=A` governs is itself written.
