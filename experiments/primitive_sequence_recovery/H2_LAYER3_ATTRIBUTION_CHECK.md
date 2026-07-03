# Design Memo — Layer 3: Synonym-Attribute Attribution Check

**Proposal only. Docs — no code, no implementation, no `--attribute-check` mode, no model, no experiment, no scoring, no result.** Track G negative preserved (`1fe5562`, `RANDOM_POLARITY_EXPLAINS`, `A_vs_R -0.1917`, `A_vs_X -0.075`); Track B **BLOCKED**; prior PSE negatives remain valid; no ontology, no Sanskrit privilege, no semantic-truth claim.

## Corrected conceptual model (Layer 1 / 2 / 3)
- **Layer 1** — phoneme/G2P → varṇa → **frozen pole/process emission** (opaque glosses per unit). *Built.*
- **Layer 2** — frozen poles → **controlled latent-process synthesis** (fixed templates + frozen bridge vocabulary; a paraphrase of the poles, adding nothing). **Not a dictionary-meaning renderer.** *Built (optional `--synthesize`, off by default).*
- **Layer 3** — **Synonym-Attribute Attribution Check** (this memo): does the Layer 2 process **support** the word's frozen synonym-derived attributes, traceably, and **better than controls**? *Not built; DOCS_ONLY.*

Layer 2's job is to emit a *process*, not a *label*. So a word like *compassion* whose Layer 2 does not literally say "compassion" is **expected**, not a failure — whether that process supports compassion-cluster attributes is the **separate Layer 3 question**, and it is only meaningful under controls.

## What Layer 3 is and is not
- **Is:** a mechanical **attribute-support checker** — "is attribute *A* traceable to a frozen gloss this word emits, via a pre-frozen bridge rule?"
- **Is not:** semantic proof; **never** "therefore the word means *A*." `SUPPORTED` means only "this attribute has a frozen bridge rule whose required gloss was emitted."

## Layer 3 input
- Layer 1 emitted glosses.
- Layer 2 controlled synthesis.
- A **frozen synonym/attribute inventory** for the target word/cluster (from an independent thesaurus, authored blind to the varṇa glosses, committed before checking).
- A **frozen attribute→gloss bridge-rule table** (authored from gloss meanings, blind to which words emit which glosses, committed before checking).

## Layer 3 output
Per attribute, one of:
- **SUPPORTED** — a bridge rule exists **and** its required gloss is in the evidence set. Emits the evidence path: `attribute ← bridge_rule[gloss] ← varṇa.role`.
- **UNSUPPORTED** — a bridge rule exists but its required gloss was **not** emitted.
- **UNRESOLVED** — no bridge rule, or the relevant varṇa was `[unresolved]` / `INTERNAL_UNRESOLVED`.

## Worked example — `love` (emitted: Krūratā, Karuṇā/Sneha, Adharma, Dharma)
| attribute (frozen synonym set) | verdict | evidence path |
|---|---|---|
| care | **SUPPORTED** | care ← bridge[Karuṇā/Sneha] ← La.counter |
| tenderness | **SUPPORTED** | tenderness ← bridge[Karuṇā/Sneha] ← La.counter |
| affection | **SUPPORTED** | affection ← bridge[Karuṇā/Sneha] ← La.counter |
| stable relation / right-relation | **SUPPORTED** | ← bridge[Dharma/Jalatattva] ← Va.transformer |
| trust | **UNSUPPORTED** | bridge[Viśvāsa] present; **Viśvāsa not emitted** (love has no kha) |
| loyalty / devotion | **UNSUPPORTED / UNRESOLVED** | no rule, or required gloss not emitted |
| attachment | **UNRESOLVED** | no frozen bridge rule |

Tell: care/tenderness/affection all "support" via the **same** gloss (Karuṇā/Sneha), which attaches to the letter **L** — so *any* L-word supports them. That is why support-count is not evidence.

## Layer 3 must not
- Use **runtime dictionary lookup**.
- Add attributes **not traceable** to Layer 1/Layer 2.
- **Modify Layer 2** after seeing target attributes.
- Use **target-fitted** bridge words.
- Add `trust/bonding/devotion/preference` **unless emitted glosses support them**.
- Say "therefore the word means X."
- Rescue Track G, unblock Track B, or claim ontology / Sanskrit privilege / semantic truth.
- `[unresolved]` must be **preserved**, never smoothed.

## Display label + warning
```
LAYER3_ATTRIBUTION_CHECK — not scored, not evidence
supported:   care, tenderness, affection, stable-relation   (with evidence paths)
unsupported: trust        (bridge[Viśvāsa] present; not emitted)
unresolved:  devotion, attachment   (no frozen bridge rule)
WARNING: attribution is set-membership over frozen tables, not semantic proof. A scrambled/random
lexicon can support a DIFFERENT attribute set equally; prior controlled tests returned NO_SIGNAL.
```

## Recommended data format (frozen before any check)
```jsonc
// synonym_attribute_inventory.json  (independent thesaurus, blind to varṇa glosses)
{ "love": { "synonym_cluster": ["affection","care","fondness","devotion","romance","attachment"],
            "attributes": ["care","tenderness","affection","trust","devotion","attachment","stable-relation","loyalty"],
            "source": "thesaurus-X frozen <date>" } }

// attribute_gloss_bridge.json  (authored from GLOSS meanings, blind to target words)
{ "care": ["Karuṇā/Sneha"], "tenderness": ["Karuṇā/Sneha"], "affection": ["Karuṇā/Sneha"],
  "trust": ["Viśvāsa"], "stable-relation": ["Dharma/Jalatattva"], "right-relation": ["Dharma/Jalatattva"] }
```

## If Layer 3 is ever scored
All arms pass through **equivalent Layer 1 → Layer 2 → Layer 3 paths**: **A** real · **R** random · **S** scrambled · **F** sign/role-flipped · **C** surface/cluster-coda-only · **X** context-only · **D** dictionary/gloss-only.

**Success requires:**
- A supports the correct synonym attributes better than **R, S, F, C, X, D**, each by a predeclared CI-lower-bound > 0.
- Co-primary comparisons **frozen before scoring**.
- Scorer **blinded** to source word, arm, dictionary meaning, and answer key.
- Targets + attribute inventories frozen before scoring; null + surface-parity + relabeling-invariance checks; human-review subset before any positive claim.

**Failure / kill criteria:**
- A does not beat **random/scrambled** → NO_SIGNAL.
- **X or D beats A** → NO_INCREMENTAL_UTILITY.
- **C matches A** → structure confound.
- Unsupported terms added; Layer 2 edited to fit; dictionary meaning leaks into the synthesis; result used as evidence without controls → void.
- Any Track G rescue / Track B unblock / ontology / Sanskrit-privilege / semantic-truth claim → stop.

## Required honest caveat (structural)
- The correct attribute set is **derived from dictionary/thesaurus data**, so **D (dictionary-only) is structurally close to the answer key**.
- Therefore **A beating D is near-unbeatable** — Layer 3's incremental-utility bar is rigged against a positive.
- Because "support" is set-membership over a **frozen, high-DOF, researcher-authored** attribute→gloss table, a **scrambled** lexicon supports a different attribute set equally → `A ≈ S` is the expected outcome.
- The **Layer 3 scored form is likely to confirm NO_SIGNAL / NO_INCREMENTAL_UTILITY.**
- Layer 3 is useful mainly for **inspection and traceability** unless a **non-dictionary, independent attribute target** exists (which would change the analysis and would need its own prereg).

## What the current sample outputs do and do not show
- **Do show:** Layer 1/Layer 2 run deterministically, stay within frozen terms, mark `[unresolved]`/`INTERNAL_UNRESOLVED`, produce a latent process — discipline guards working.
- **Do NOT show:** any evidence for or against the Layer 3 hypothesis; any dictionary-meaning recovery; anything scored. `compassion` → non-"compassion" only confirms Layer 2 is not a dictionary renderer (expected), and is **not** a Layer 3 verdict.

## What must be frozen before any Layer 3 implementation
Synonym clusters + attribute inventories (independent thesaurus, blind); attribute→gloss bridge rules (blind to target words); Layer 2 fixed templates; the evidence-path validator (rejects any attribute not traceable to an emitted gloss; preserves `[unresolved]`); co-primary comparisons, target sets, seeds, decision rule. Post-hoc edits → `INVALID_POSTHOC`.

## Recommendation
**DOCS_ONLY now — no implementation yet.** If built at all, build Layer 3 first as an **inspection-only attribution display** (`LAYER3_ATTRIBUTION_CHECK — not scored, not evidence`), never scored. Scoring stays a separate, explicitly-approved, pre-registered step with a **null prior**, framed as a rigor check, never a rescue. Honest expectation for a scored Layer 3: **NO_SIGNAL / NO_INCREMENTAL_UTILITY** (D-dominance + scramble-equivalence). The reframe fixed the conceptual model; it did not change the evidential prior.

---

Guardrails: no ontology, no Sanskrit privilege, no semantic-truth claim, no Track B unblock, no rescue of Track G; Track G negative exact (`1fe5562`, `RANDOM_POLARITY_EXPLAINS`, `A_vs_R -0.1917`, `A_vs_X -0.075`).

Structure, not validated meaning.
