# B1.1 Binding / Liberating Pole-Language — Addendum

## 1. Scope and non-claims

**Addendum only.** Corrects the B1.1 pole language so poles are framed as **binding vs liberating
expression of the same tendency**, never as good/bad, positive/negative, vice/virtue, or "automatically
liberated." Modifies **no** JSON, runs **no** model, embedding, generation, or scoring. Does **not** modify
B1, change the verdict (`RANDOM_OR_SCRAMBLED_MATCHES`), or unblock Track B (**BLOCKED**). No ontology
validation, Sanskrit privilege, or semantic-truth claim. **Structure, not validated meaning.**

## 2. Why good/bad framing is wrong

Moral framing (good/bad, virtue/vice, positive/negative) **imports external labels about the referent** —
exactly what the source lexicon forbids. Its own `_legend` states: *"These are states of expression, NOT
moral judgements. Poles are never selected from external labels about the referent."* The framework's single
question is **does an expression BIND consciousness (contractive, attachment-forming) or RELEASE it
(expansive, unbinding)?**

A source-attested term may *look* sattvic, knowledgeable, dharmic, energetic, or orderly and **still bind**
if it is owned by ego, attachment, compulsion, identity, purity-pride, knowledge-pride, role-identity, or
possession. **This addendum corrects a drift in earlier B1.1 docs** (which used "positive/negative pole",
"liberated" endpoints) back to the lexicon's own binding/liberating-expression ontology.

**Updated principle:** *the task is NOT to find a morally opposite word; it is to find the **liberating
expression of the same source tendency**.*

## 3. Binding vs liberating pole language

| replace | with |
|---|---|
| good / bad | binding / liberating |
| positive / negative | binding expression / liberating expression |
| vice / virtue | source-attested pole / experimental counter-expression |
| automatically liberated | non-binding use / binding use |
| (a fixed "liberated" endpoint) | identified mode / freeing mode |

The counter-pole is renamed in intent to an **experimental counter-expression**: the *liberating expression*
of the **same** source tendency, contrasted with its **binding expression** — not a different, opposite
concept.

## 4. Updated handling of Sa / Ra / Śa / Ha / Kṣa (human-review set)

Each is the *same tendency* in a binding vs a liberating expression (verbatim from the operator):

- **Sa** — binding expression: *sattvic clarity/order when owned as purity, superiority, or attachment to
  harmony*; liberating expression: *clarity without attachment to clarity*.
- **Ra** — binding expression: *rajasic activation when driven by compulsion, desire, or projection*;
  liberating expression: *directed energy without bondage*.
- **Śa** — binding expression: *worldly purpose possessed as acquisition, status, or control*; liberating
  expression: *purposeful action without possessive bondage*.
- **Ha** — binding expression: *higher knowledge owned as spiritual identity or subtle pride*; liberating
  expression: *realized knowing without ownership*.
- **Kṣa** — binding expression: *structured knowledge owned as control, dogma, or intellectual identity*;
  liberating expression: *instrumental knowledge released from possession*.

These five remain in the **human-review / freeze-review set** {Ra, Sa, Śa, Ha, Kṣa}; the binding/liberating
formulations above are the **candidate** expressions to be finalized at review (not frozen here).

## 5. Updated handling of Ca / Va (ready_draft)

- **Va** — binding expression: *accepting-as-true without sufficient discernment*; liberating expression:
  *truth-assent purified by discernment, installing only what is non-bindingly recognized*.
- **Ca** — binding **risk**: *discernment becoming judgment / separation-pride*; liberating expression:
  *falsehood-discerning Viveka without egoic superiority*.

Va stays `ready_draft` (freeze-review item, not deferred, per the prior decision); Ca stays `ready_draft`.
Their functional distinction (Ca removes the false; Va installs the accepted-as-true) is unchanged — this
addendum only reframes their *pole language* to binding/liberating and records Ca's binding risk.

## 6. Consequences for the JSON draft

*(Documented; JSON changes only at a separate, approved JSON-update gate.)*

1. **Language pass across all entries:** drop "positive/negative/liberated" endpoint language; each entry's
   counter-pole is authored as the **liberating expression of the same source tendency**, with an explicit
   **binding expression** for contrast. Field intent: `experimental_counter_pole` → *experimental
   counter-expression (liberating mode)*.
2. **`polarity_role` vocabulary** should shift from `binding|liberated|neutral|counter_to_source` toward
   **`binding_expression | liberating_expression`** (plus `source_complex` for Ra), removing the implied
   moral endpoint. (Exact enum finalized at the JSON-update gate.)
3. **Re-express, don't re-oppose:** the counter-expression must be the *freeing mode of the same tendency*
   (e.g. Sa: clarity **without attachment to clarity**), not a different virtue. Existing ordinary-consonant
   counter-poles are re-checked against this test.
4. The five human-review poles carry the §4 candidate binding/liberating pairs; Ca/Va carry §5.
5. JSON remains **not frozen**.

## 7. Consequences for the embedding gate

The committed non-synonym gate is already `BLOCKED`. Because the language pass will **change the exact
strings**, the embedding gate must run over the **re-expressed** counter-expressions after the JSON-update
gate — over the finalized non-deferred set (currently **29**, pending the five human-review resolutions).
No scores are affected now (none exist); the frozen model + τ are unchanged.

## 8. Consequences for bridge-pool generation

Bridge phrases must use **binding/liberating-expression** language, never good/bad. Bridge-pool generation
remains **BLOCKED** until: the five human-review poles are resolved with binding/liberating formulations, the
language pass is applied, the embedding gate passes, and adjudication is complete.

## 9. Final status block

```
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES   (unchanged)
Track B:               BLOCKED
This step:             ADDENDUM ONLY
JSON modified:         NO (language pass documented, applied at a later approved gate)
Embedding run:         NO
Bridge pool generated: NO
Model run:             NO
Generation run:        NO
Scoring run:           NO
Ontology validation:   NO
Sanskrit privilege:    NO
Semantic truth:        NO
```
Human-review set: **{Ra, Sa, Śa, Ha, Kṣa}** · Ca/Va ready_draft · non-deferred **29**.
Preserved prior: Track G `RANDOM_POLARITY_EXPLAINS` · Track F `CORRECTNESS_DEGRADED`. Contrastivity repair
remains **necessary but not sufficient**; `R_deranged` remains the crux.

**Structure, not validated meaning.** Addendum only; the B1 verdict stands and Track B remains BLOCKED.
