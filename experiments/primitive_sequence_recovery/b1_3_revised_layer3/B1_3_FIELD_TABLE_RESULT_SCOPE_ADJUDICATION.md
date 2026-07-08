# B1.3 Field-Table Result Scope Adjudication

## 1. Scope

Adjudicates **what the varṇa→field table pre-check actually ruled out** — separating the two distinct findings
(register-dimension undefensibility vs order-invariance) and deciding what remains adjudicable. Scope
adjudication only: no implementation, no judges, no rerun, no scoring, **no EVIDENCE_FREEZE**. No prior
verdict is changed; no positive label is earned. Track B BLOCKED; no ontology / Sanskrit / semantic-truth
claim. **Structure, not validated meaning.**

## 2. What the pre-check validly ruled out

The pre-check had **two** findings; the first is dimension-specific:

- **The social/register-field version is CLOSED.** The frozen glosses barely touch the register/affective
  dimensions (formality 4/68, distance 4/68, intimacy 5/68, domestic 5/68). Forcing varṇa onto these would be
  inventing a bridge the ontology does not contain. → the **father/papa/mother/mama social-register test** and
  the **LLM field-discrimination plan *as specified* (register dimensions)** are **ruled out**.
- These are register/**usage-convention** properties anyway (largely explained by frequency/babbling/etymology,
  §B1.3 confound spec), so a varṇa system failing to produce them is unsurprising and not a loss of anything
  varṇa-specific.

## 3. What the pre-check did NOT fully rule out

The **defensibility** failure was specific to *register* dimensions. The glosses **do** map — and map well —
to their **native vṛtti dimensions**: potency 31/68, activity 24/68, dependency 14/68, hardness 12/68. So on
the **defensibility axis**, the following remain **adjudicable** (not closed by this pre-check):

- a **vṛtti-native propensity test** on dimensions the glossary actually encodes: attachment/release,
  striving/surrender, ego/humility, agitation/steadiness, binding/liberation, grasping/openness;
- (weakly) a **Gita/śloka modulation** test on those same mental/spiritual dimensions — noted only for
  completeness; it carries maximal interpretive subjectivity (flagged repeatedly as least testable).

**Two hard prerequisites gate this remaining path (both likely fatal):**

1. **Order-sensitivity** (§4) — generalizes across *every* field version, vṛtti included.
2. **External, non-circular ground truth for vṛtti-dimension word ratings.** For register you had real
   linguistic properties LLMs rate reliably (formality/intimacy). For vṛtti ("how much *grasping* does the
   word *father* carry?") there is likely **no external, inter-subjective ground truth** — it is exactly the
   doctrinal/first-person judgment that cannot be measured non-circularly. This must be established before any
   vṛtti test could run, and it may not exist.

## 4. Critical issue — order sensitivity

**scrambled ≈ real (cosine 0.967)** is a serious blocker that is **dimension-independent** and therefore
**generalizes** — a vṛtti-native test would face it too. It reconfirms B1.1's scrambled-tie: the varṇa
**sequence/order carries essentially no information** under any composition that wasn't tuned to force it.

**Rule:** any future vṛtti test must first show **real order/role composition differs from scrambled**
*without post-hoc tuning*. Given the arc's repeated scrambled-ties, this is a **high bar and the likely
outcome is still null**. **If order cannot be made operative without tuning, `STOP_NOW` returns for the vṛtti
path as well.**

## 5. Register-field vs vṛtti-field distinction

- **Register-field** = formal / intimate / domestic / institutional **social usage** — a property of a word's
  learned convention. **Closed** for varṇa (§2), and largely a convention confound anyway.
- **Vṛtti-field** = mental/spiritual **tendency** — grasping, release, agitation, surrender, binding,
  liberation. This is what the frozen glossary **actually encodes**, so it is the **faithful** ("on its own
  terms") test of the ontology — but it inherits the order blocker (§4) and lacks an obvious external ground
  truth (§3).

The pre-check's real lesson: **varṇa glosses are a vṛtti-field, not a register-field.** Testing them as
register was a category mismatch; testing them as vṛtti is faithful but runs into order-invariance and the
ground-truth problem.

## 6. Decision

```
DECISION: SOCIAL_REGISTER_FIELD_CLOSED_BUT_VRITTI_FIELD_REMAINS_ADJUDICABLE
```

Honest and precise: the pre-check **specifically** ruled out the register-field version (defensibility
4–5/68), but its defensibility failure does **not** generalize to the glossary's **native vṛtti dimensions**,
which are well-grounded (potency/activity/dependency). So `FIELD_TABLE_FAILURE_GENERALIZES_STOP_NOW`
**overstates** (the defensibility failure was register-specific). `INCONCLUSIVE_NEEDS_VRITTI_DIMENSION_REVIEW`
understates the clarity we have (register is genuinely closed; vṛtti is the identified remaining space). Hence
**register closed, vṛtti remains adjudicable** — *conditional on* clearing the two hard prerequisites (§3, §4),
which the accumulated evidence suggests it likely will not.

## 7 / 8. Next gate

```
next gate: B1_4_VRITTI_PROPENSITY_DIMENSION_SPEC
```

The vṛtti dimension spec must, before anything else: (a) define the vṛtti dimensions from the frozen glossary,
(b) establish whether an **external, non-circular ground truth** for word-level vṛtti ratings exists at all
(if not → `VARNA_LINE_CLOSURE_MEMO`), and (c) show **order-operative** composition without tuning (if not →
`VARNA_LINE_CLOSURE_MEMO`). This is a genuinely narrow gate with two likely-fatal prerequisites, not an open
runway.

## 9. Final status block

```
document:                    B1.3 field-table result SCOPE adjudication (scope only; nothing run)
decision:                    SOCIAL_REGISTER_FIELD_CLOSED_BUT_VRITTI_FIELD_REMAINS_ADJUDICABLE
ruled out:                   social/register field test (father/papa); register-dim LLM field plan as specified
remains adjudicable:         vṛtti-native propensity dims (glossary's own space) — CONDITIONAL on order-sensitivity
                             + external vṛtti ground truth (both likely fatal)
order sensitivity:           scrambled ≈ real (0.967) — dimension-independent blocker; generalizes; must be cleared non-circularly
ran judges / scoring:        NO
EVIDENCE_FREEZE:             NONE
B1.1 verdict:                UNCHANGED — RANDOM_OR_SCRAMBLED_MATCHES
B1.2 / B1.3 prior:           UNCHANGED (not rescued)
LLM_PROPENSITY_FIELD_DISCRIMINATION / PROPENSITY_MODULATION_SIGNAL: NOT earned
LIMITED_GENERATION_UTILITY / MAPPING_FIDELITY_SIGNAL: NOT earned
Track B:                     BLOCKED
Track G / Track F:           RANDOM_POLARITY_EXPLAINS (1fe5562) / CORRECTNESS_DEGRADED — preserved
ontology / Sanskrit / truth: NONE
next gate:                   B1_4_VRITTI_PROPENSITY_DIMENSION_SPEC (else VARNA_LINE_CLOSURE_MEMO)
```

**Structure, not validated meaning.** The pre-check closed the register-field version (varṇa glosses are
vṛtti, not register) but did not rule out the glossary's native vṛtti dimensions; that remaining path is
conditional on two hard, likely-fatal prerequisites — order-sensitivity and an external vṛtti ground truth.
Nothing was run or scored, no prior result changed, and Track B remains BLOCKED.
