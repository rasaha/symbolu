# B1.1 Vidyā-Binding Review — Addendum (Ha / Kṣa)

## 1. Scope and non-claims

**Addendum only.** Corrects the B1.1 review framing for **Ha** and **Kṣa** so a *knowledge* pole (vidyā) is
not mislabeled as an automatically *liberated* endpoint. Companion to the guṇa-binding addendum (`29cb457`),
which covered Sa/Ra/Śa. Modifies **no** JSON, runs **no** model, embedding, generation, or scoring. Does
**not** modify B1, change the verdict (`RANDOM_OR_SCRAMBLED_MATCHES`), or unblock Track B (**BLOCKED**).
Reasons **within the framework's own logic** to label handling correctly; makes **no** claim of ontology
validation, Sanskrit privilege, or semantic truth. **Structure, not validated meaning.**

## 2. Vidyā is not automatically mokṣa

Ha and Kṣa are **knowledge-functions**, not liberation. In the source's own frame, **knowledge alone does
not liberate unless *realized*.** Unrealized knowledge can still **bind** — through identity, pride,
abstraction, control, command-function attachment, or intellectual possession. Both **parā-vidyā** (higher
knowledge) and **aparā-vidyā** (structured/worldly knowledge) remain **within the subtle-human / knowledge
apparatus until realization**. So, exactly as with the guṇas (golden/fiery/worldly chains), a "positive"
knowledge pole is **not** automatically a liberated endpoint.

## 3. Ha correction

- **Do not** frame Ha as *ignorance → spiritual knowledge = final liberation.*
- Treat Ha as **source-attested parā-vidyā (higher knowledge)** that **can still bind** if held as
  **identity, pride, abstraction, or command-ego.**
- **Candidate counter-direction (only if later approved):** *realized knowing beyond ownership of
  knowledge.*
- **Keep the human-review flag before freeze.**

## 4. Kṣa correction

- **Do not** frame Kṣa as *dogma → knowledge = final liberation.*
- Treat Kṣa as **source-attested aparā-vidyā / structured knowledge** that **can still bind** through
  **technical pride, dogma, analysis, control, or knowledge-identity.**
- **Candidate counter-direction (only if later approved):** *instrumental knowledge released from identity
  and possession.*
- **Keep the human-review flag before freeze.**

## 5. Updated human-review / freeze-review set

Expanded from **{Ra, Sa, Śa}** to **{Ra, Sa, Śa, Ha, Kṣa}** (five):

| varṇa | chain / apparatus | why it can still bind |
|---|---|---|
| **Ra** | rajasic activation — fiery chain | motion, desire, ambition, compulsion, projection |
| **Sa** | sattvic clarity — golden chain | attachment to purity / knowledge / harmony (sattva is still a guṇa) |
| **Śa** | rajas / artha — worldly-purpose chain | possessive worldly pursuit |
| **Ha** | parā-vidyā — higher knowledge | identity, pride, abstraction, command-ego (unless realized) |
| **Kṣa** | aparā-vidyā — structured knowledge | technical pride, dogma, analysis, control, knowledge-identity (unless realized) |

**Note (residual open, not decided here):** the earlier guṇa addendum's open flag also named **Ca (viveka)**
and **Va (dharma)**. This instruction elevates **only Ha and Kṣa**; **Ca and Va are NOT moved** and remain
`ready_draft` unless a separate decision changes them. Recorded so the loose end is explicit.

## 6. Consequences for the JSON draft

*(Documented; the JSON changes only at a separate, approved JSON-update gate.)*

- **Ha and Kṣa reclassified** from `exception_protected` / `ready_draft` → **human-review** (deferred),
  joining Ra/Sa/Śa.
- **Deferred set: {Ra, Sa, Śa} → {Ra, Sa, Śa, Ha, Kṣa}** (3 → 5). **Non-deferred: 31 → 29.**
- Ha/Kṣa `source_attested_pole` framing must be corrected at the JSON-update gate so parā-/aparā-vidyā is not
  presented as liberation; their counter-poles are authored only after the human-review decisions in §3–§4.
- The JSON draft remains **not frozen**.

## 7. Consequences for the embedding gate

The committed non-synonym embedding gate is already `BLOCKED` (dependency unavailable) and must be re-run
regardless. When it does run, **one of**:
- **A. exclude Ra / Sa / Śa / Ha / Kṣa** and run over the **remaining 29 non-deferred** entries; or
- **B. wait** until all five are finalized, then run over all 34.

Either way, the five human-review poles are **not** silently included.

## 8. Consequences for bridge-pool generation

**Bridge-pool generation remains BLOCKED** until: the five human-review poles (Ra, Sa, Śa, Ha, Kṣa) are each
resolved or explicitly pre-registered as excluded; the embedding gate passes over the finalized non-deferred
set; and human adjudication is complete. No bridge pool may include an unresolved human-review counter-pole.

## 9. Final status block

```
B1 verdict:            RANDOM_OR_SCRAMBLED_MATCHES   (unchanged)
Track B:               BLOCKED
This step:             ADDENDUM ONLY
JSON modified:         NO (Ha/Kṣa reclassification documented, applied at a later approved gate)
Embedding run:         NO
Bridge pool generated: NO
Model run:             NO
Generation run:        NO
Scoring run:           NO
Ontology validation:   NO
Sanskrit privilege:    NO
Semantic truth:        NO
```
Human-review / freeze-review set: **{Ra, Sa, Śa, Ha, Kṣa}** · non-deferred now **29**.
Preserved prior: Track G `RANDOM_POLARITY_EXPLAINS` · Track F `CORRECTNESS_DEGRADED`. Contrastivity repair
remains **necessary but not sufficient**; `R_deranged` remains the crux.

**Structure, not validated meaning.** Addendum only; the B1 verdict stands and Track B remains BLOCKED.
