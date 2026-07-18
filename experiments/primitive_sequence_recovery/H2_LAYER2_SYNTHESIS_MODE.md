# Design Memo — Optional Layer 2 Synthesis Mode (sample-text harness)

**Proposal only. Docs — no code, no harness change, no `--synthesize` implementation, no model, no experiment, no scoring, no result.** Layer 2 is **controlled paraphrase only** — optional, exploratory, **not evidence, not semantic proof**; it does **not** rescue Track G and does **not** unblock Track B. Track G negative preserved (`1fe5562`, `RANDOM_POLARITY_EXPLAINS`, `A_vs_R -0.1917`, `A_vs_X -0.075`); Track B **BLOCKED**; no ontology, no Sanskrit privilege, no semantic-truth claim.

**Governing warning:** Layer 2 is the single highest-contamination surface in this line of work. A synthesis that sounds apt is exactly what Barnum/storytelling produces, and the committed `varna_lens` results show a **scrambled** lexicon run through the same templates reads equally apt (that is what NO_SIGNAL means). So Layer 2 can be built safely *only* as a mechanical, gloss-backed paraphrase that adds zero information — and it must never be cited as evidence.

## 0. Governing principle
Layer 2 is a **controlled paraphrase of Layer 1's emitted frozen poles** — a deterministic substitution through a **frozen bridge-vocabulary table**, composed by **fixed templates**. It introduces **no new content**, no dictionary lookup, no target-fitting. It is a pure function of the varṇa sequence, so it is **identical across any two words with the same emitted poles** (e.g. every `La+a+Va` word yields the same synthesis, regardless of meaning). That invariance is the only thing that keeps it from being storytelling.

## 1. Layer 1 unchanged
Layer 1 stays exactly as committed (`a8bf5f1`): only frozen lexicon terms, no bridge, no "therefore means," no evidence claim. Layer 2 is a **separate, opt-in add-on** that consumes Layer 1's output and never alters it.

## 2. Label
Every Layer 2 block carries: **`INTERPRETIVE_SYNTHESIS_ONLY — not scored, not evidence`** plus the closing warning in §7.

## 3. Composition rule (fixed templates, gloss-backed only)
Layer 2 renders each *scored* varṇa as a fixed clause, using the **bridge phrase** for its emitted gloss, then joins clauses with a fixed connective:
- **SEED clause:** `"{seed.binding_bridge} moves toward {seed.counter_bridge}"`
- **TRANSFORMER clause:** `"{transformer.pole_bridge} is the resolving principle"` (or `"resolved through {transformer.pole_bridge}"`)
- **FIELD clause (optional, off by default):** `"in a field of {field.bridge}"`
- **Connective:** `", and "`. **INTERNAL_UNRESOLVED / MISSING → literal `[unresolved]`**, never paraphrased away.

The synthesis for `love` (La+a+Va) is therefore, mechanically:
> "separative harshness moves toward compassion/gentleness, and order/dharmic relation is the resolving principle."

## 4. Fixed templates only
- No per-word handcrafted prose. Templates are a small closed set, authored and frozen before use.
- No dictionary-meaning lookup of the input word.
- No target-fitted terms.
- **No token that isn't traceable to an emitted gloss via the bridge table** (enforced by the §8 validator).

## 5. `love` — allowed vs forbidden
- **Allowed:** "separative harshness transformed into compassionate, dharmic relation." — every content word is backed: *separative harshness*=Krūratā, *compassionate*=Karuṇā/Sneha, *dharmic relation*=Dharma. ✅
- **Forbidden:** "love means compassion with **trust**." ❌ — because (a) "means" bridges to the dictionary, and (b) **"trust" (Viśvāsa) is not emitted by love's varṇas** (trust comes from `kha`, which love does not contain). Adding it is fabrication.

## 6. Allowed bridge vocabulary (frozen table — one phrase per lexicon gloss, authored blind)
Each bridge phrase is a **paraphrase of the lexicon gloss**, fixed, identical everywhere it occurs:
| Lexicon gloss (emitted) | Bridge phrase |
|---|---|
| Krūratā (Cruelty) | separative harshness |
| Karuṇā/Sneha (Compassion/Gentleness) | compassion/gentleness |
| Adharma (deviation) | disorder/deviation |
| Dharma (sustaining order) | order / dharmic relation |
| Escapism | withdrawal/escape |
| Mokṣa/Sattvaguṇa (liberation/clarity) | liberation/clarity |
| Cintā (Worry) | worry |
| Viśvāsa (Trust) | trust |
| Āśā (Hope) | hope |
| Nirāśā (Detachment) | detachment/letting-go |
| Mūrcchā (Deluded obsession) | deluded obsession/entrancement |
| Jāgaraṇa (Awareness/awakening) | awareness/awakening |
| (ya) Lack of confidence → Confidence | (lack of) confidence |
| a — Birth of cognition | emergence/beginning |
| ai — Welfare, materialization | welfare/making-real |
| u — Zoom, contraction | contraction/focus |
Rule: the table is authored **once, blind to target words**, committed, and never edited per item. A gloss with no table entry → the varṇa renders as `[unresolved]`, not a guess.

## 7. Output format
```
EXPLORATORY_SAMPLE_ONLY — not scored, not evidence
[Layer 1 frozen rendering — unchanged]
INTERPRETIVE_SYNTHESIS_ONLY — not scored, not evidence
[Layer 2 controlled synthesis — fixed template over bridge vocabulary]
WARNING: This is interpretive synthesis, not evidence and not semantic proof. The same templates
applied to a scrambled/random lexicon read equally well; prior controlled tests returned NO_SIGNAL.
```

## 8. Kill / invalid cases
- Synthesis requires the input word's **dictionary meaning** → invalid.
- Synthesis contains a term **not traceable to an emitted gloss** (validator: every content token must appear in the bridge phrases of *this word's* emitted glosses) → invalid. (This is what blocks "trust/bonding/devotion" when not emitted.)
- Synthesis **changes with the target word** for the same varṇa sequence → invalid (target-fitting).
- Synthesis used as **evidence**, or to **rescue Track G**, or to claim ontology/Sanskrit-privilege/semantic-truth → stop.
- Layer 1 had `MISSING`/`INTERNAL_UNRESOLVED` and Layer 2 silently smooths it over → invalid (must render `[unresolved]`).

## 9. Samples (from actual emitted poles)
- **love** (`La a Va`, g2p): L1 seed Krūratā→Karuṇā/Sneha · transformer Dharma. **L2:** "separative harshness moves toward compassion/gentleness, and order/dharmic relation is the resolving principle." *(forbidden: any "trust/bonding" — not emitted.)*
- **sukha** (`sa u kha a` — **IAST mode; not in cmudict, g2p would abort**): L1 seed Escapism→Mokṣa/clarity · field contraction · transformer Viśvāsa(Trust). **L2:** "withdrawal/escape moves toward liberation/clarity, and trust is the resolving principle."
- **like** (`La ai Ka`, g2p): L1 seed Krūratā→Karuṇā/Sneha · field welfare · transformer Nirāśā(Detachment). **L2:** "separative harshness moves toward compassion/gentleness, and detachment/letting-go is the resolving principle." *(note: differs from love only at the transformer — Detachment vs Dharma; forbidden: Detachment→"preference".)*
- **bhaya** (`bha a ya a` — **IAST mode; g2p would abort**): L1 seed Mūrcchā(deluded obsession)→Jāgaraṇa · transformer Confidence. **L2:** "deluded obsession/entrancement moves toward awareness/awakening, and confidence is the resolving principle." *(forbidden: "bhaya means fear" or "→ fearlessness" — dictionary/unsupported.)*

Note the honest tells across these: `sukha`/`bhaya` require IAST (g2p aborts), and `like` vs `love` differ *only* at the transformer — the synthesis faithfully reflects that, and does **not** make either land on the target word's dictionary sense. That faithfulness is the point; the aptness is not evidence.

## 10. Recommendation
**DOCS_ONLY first.** Layer 2 is the highest storytelling-risk surface in the whole program, so it should be specified and reviewed as a doc **before** any code. Implement as an optional `--synthesize` mode **later, only if** you accept all of:
- a **frozen, committed bridge-vocabulary table** authored blind;
- **fixed templates** + the §8 **"no unsupported term" validator** (rejects any token not traceable to an emitted gloss);
- the `INTERPRETIVE_SYNTHESIS_ONLY` label **and** the §7 warning on every block;
- **off by default**, exploratory only, never scored, never cited, never used to rescue Track G;
- `[unresolved]` preserved from Layer 1, never smoothed.

Persist this as a docs-only spec first; only after that, on explicit approval, wire `--synthesize` with the validator. Doc first.

---

Guardrails: no ontology, no Sanskrit privilege, no semantic-truth claim, no Track B unblock, no Track G rescue; Track G negative exact (`1fe5562`, `RANDOM_POLARITY_EXPLAINS`, `A_vs_R -0.1917`, `A_vs_X -0.075`).

Structure, not validated meaning.
