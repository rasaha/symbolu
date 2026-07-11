# G2P Aspiration Rule — SCOPING PROPOSAL (not implemented)

**Status: SCOPING ONLY. No code changed, nothing applied.** Unlike the retroflex rule, my recommendation here is
**do NOT apply as-is** (see §7) — it is phonetically motivated but lower-fidelity and higher-cost, and it
*compounds* an existing mis-mapping. Resonance / phonetic-fidelity refinement only — no ontology/semantic-truth/
Sanskrit-privilege claim, no `GENUTILITY_*`, no `ONTOLOGICAL_SIGNAL`. **B1.4b′ remains `NULL_RETURN_BOTTOM`.**

---

## 1. Motivation (the phonetics are valid)

English voiceless stops `/p, t, k/` are **aspirated** `[pʰ, tʰ, kʰ]` word-initially and at stressed-syllable
onset (*top, take, cake, pot*), and **unaspirated** after `/s/` (*stop, skip, spin*) and often when unstressed.
Sanskrit distinguishes unaspirated **pa/ta/ka** (प/त/क) from aspirated **pha/tha/kha** (फ/थ/ख). So phonetically
English initial `/tʰ/` ≈ **tha**, `/kʰ/` ≈ **kha**, `/pʰ/` ≈ **pha**. The current bridge maps **all** `/p,t,k/` →
unaspirated pa/ta/ka, ignoring aspiration entirely — the "aspiration collapse" already noted in the v3 caveats.

## 2. The candidate rule

> **Word-initial `/p, t, k/` → pha / tha / kha; elsewhere unaspirated (pa/ta/ka).** The `/s/`-cluster case is
> handled for free (in *stop/skip*, the first phoneme is `/s/`, so the stop is not word-initial and stays
> unaspirated). Route B style (context-aware bridge, G2P untouched).

## 3. Three serious problems (why this is not a clean win)

**(a) The `tha` collision — it compounds an existing MIS-mapping.** `tha` (थ) is *already* wrongly fed by the
English dental fricatives `/θ, ð/` (*the, this, that, think, path*) — the single worst fidelity bug in the whole
bridge (the/this/that are the most frequent English words, all → `tha`/melancholy). Routing word-initial `/tʰ/`
(*top, take, time*) **also** to `tha` puts **two unrelated English sources on one target**, making the melancholy
over-trigger dramatically worse. Measured: `think → tha,...` and `top → tha,pa` would both land on `tha`.

**(b) Aspiration is allophonic and stress-conditioned — the G2P can't see it.** English aspiration depends on
stress and syllable position, and the G2P encodes neither aspiration nor stress. Only **word-initial** aspiration
is reliably detectable; stressed-medial aspiration (a·*tone*, re·*peat*) is invisible, and aspiration is
dialect-variable. So any rule is **partial and imprecise** — unlike the retroflex trigger (`t/d`+`r`), which is a
clean, fully-detectable context.

**(c) Blast radius + semantic effect are large.** Measured on the frozen pole-DiD set: **7 of 24** words change
(vs **1** for the retroflex rule) — `clarity→kha`, `compassion→kha`, `cage→kha`, `craving→kha`, `peace→pha`,
`panic→pha`, `terror→tha`. And it newly populates the currently-empty aspirate targets with common word-initials:
`kha` = **cintā/worry** (so *cake, clarity, cage* → "worry"), `pha` = **bhaya/fear** (so *pot, peace, panic* →
"fear"), `tha` = **viṣāda/melancholy**. In general English this injects worry/fear/melancholy across a very large
fraction of the vocabulary.

## 4. Options

- **Option 0 (recommended): do NOT apply.** Costs (compounding the `tha` mis-map, allophonic imprecision, large
  semantic shift) outweigh the fidelity gain. Leave it flagged-and-documented, as now.
- **Option A: full word-initial `/p,t,k/` → pha/tha/kha.** Phonetically consistent but worst on all three problems
  above (esp. the `tha` collision).
- **Option B: `kha`/`pha` ONLY (leave `/t/` alone).** Aspirate only word-initial `/k/→kha`, `/p/→pha`; keep
  `/t/→ta` untouched so as not to worsen the `tha` mis-map. Avoids (a) but is inconsistent (why aspirate k,p but
  not t) and still injects worry/fear widely (problem c).
- **Option C: gate behind fixing the `tha` mis-map first.** The principled path: (1) re-route `/θ, ð/` OFF `tha`
  (to a dedicated non-Sanskrit / dropped bucket — English has these sounds, Sanskrit doesn't), THEN (2) apply the
  aspiration rule so `tha` cleanly means aspirated `/tʰ/`. This is a *larger* change (a separate `/θ,ð/`-handling
  decision) but the only way aspiration becomes a genuine fidelity improvement rather than a compounding one.

## 5. Impact (measured)

- **Frozen items: 7/24 pole-DiD words change** (clarity, compassion, cage, craving, peace, panic, terror) — a much
  bigger disturbance than the retroflex rule's 1/24 (`dread`).
- **General English: pervasive** — most `p/t/k`-initial words shift to aspirate targets.
- **Targets populated:** `tha` (already contested), `kha` (worry — was reference-only), `pha` (fear — was
  reference-only). It does NOT reach the retroflex aspirates `ṭha/ḍha` (no trigger) or the voiced aspirates.

## 6. To go live (if ever approved)

Same discipline as the retroflex rule: new bridge version + hashes → re-derive the 7 affected frozen items →
re-freeze declarations → fresh prereg before any test (anti-circularity). But note the 7-item impact means it
materially changes the pole-DiD / pole-sanity item packets.

## 7. Recommendation

**Do NOT apply the aspiration rule as-is (Option 0).** It is phonetically motivated, but three things make it a net
negative right now: it **compounds the `/θ,ð/→tha` mis-mapping**, it is **allophonic/stress-invisible** (only
word-initial is detectable), and it has a **large, semantically-heavy blast radius** (worry/fear/melancholy across
much of the vocabulary; 7/24 frozen items). If the aspiration distinction is wanted, pursue **Option C** — first
fix the `/θ,ð/→tha` mis-map, then aspirate cleanly. Absent that, the retroflex rule stands as the one worthwhile
G2P refinement; aspiration stays **documented but not applied**.

## 8. Guardrails

Proposal only; no code, no re-derivation, no re-run, nothing applied. Resonance / phonetic-fidelity refinement —
it would change *which* resonance a word receives, not whether the mapping carries validated meaning; it does not
touch the content-level nulls. No `GENUTILITY_*`, no `ONTOLOGICAL_SIGNAL`. **B1.4b′ remains `NULL_RETURN_BOTTOM`.**
Structure, not validated meaning.
