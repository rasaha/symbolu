# MILESTONE_A_PRIME_CANDIDATE_E_SOURCE_REGISTER

> **STATUS — A1.6 Candidate E Source Register. Docs-only. Search complete.**
> Executes **only** A1.6 of `MILESTONE_A_PRIME_PREREGISTRATION_AMENDMENT_1.md`: source discovery
> + admissibility screening. **No dataset downloaded, no rating/data values inspected, no code,
> no analysis, no freeze, no A′ execution, no Stage A / structural_v1 change, ⊥ preserved.** This
> register emits a **desk-search outcome only** — never PASS/FAIL/⊥/INCONCLUSIVE (those are A′
> run outcomes). Date: 2026-06-29. **structure, not validated meaning.**

## 1. Method and environmental constraint
- **Tooling:** identification via web search over scholarly indices; per-candidate screening
  against the A1.2 admissibility criteria.
- **Bound (A1.6):** fixed query set; **15 candidates screened** (cap = 25); search run to
  completion; every candidate recorded with an explicit include/exclude reason.
- **Environmental constraint (material to verification):** the session egress policy **blocks the
  data/landing hosts** required to verify file existence, exact machine-readable format, and
  license text. Confirmed policy denials (HTTP 403 CONNECT-rejected): `osf.io`,
  `link.springer.com`, `doi.org`, `www.nature.com`, `psycnet.apa.org`, `www.biorxiv.org`,
  `arxiv.org`, `pmc.ncbi.nlm.nih.gov`. Reachable: the search index and `raw.githubusercontent.com`.
  Per the proxy README the correct action is to **report the blocked host, not route around it.**
  Consequently A1.2 criteria **2 (machine-readable), 5 (license-clear), 6 (freezable artifact)**
  could be **identified-as-likely from citations/abstracts but NOT verified**. Criteria
  **1, 3, 4, 7, 8** were screenable from published descriptions. Verification of 2/5/6 is a
  **precondition to A1.8 freeze** and requires host access.
- **No rating value was retrieved or inspected.** Only titles, abstracts, and metadata were read.

## 2. Screened candidates (per-candidate fields)

Legend — A1.2 verdict: **ADM-S** = admissible on screenable criteria (1,3,4,7,8), criteria 2/5/6
*unverifiable here*; **EXC** = excluded.

### INCLUDED (admissible on substance; 2/5/6 pending host-blocked verification)

**C1 — McCormick, Kim, List & Nygaard — "Sound to Meaning Mappings in the Bouba-Kiki Effect"**
- Identifier/URL: escholarship.org/uc/item/3s632891 ; stimuli/data: osf.io/ekpgh (host blocked)
- Query: "McCormick 2015 … 537 pseudowords roundedness ratings data availability"
- Stimulus type: **537 CVCV pseudowords** (American-English phonotactics; homophones of real
  words excluded)
- Dimension measured: **shape (roundedness–pointedness)**
- Lexically empty: **Yes** (pseudowords; real-word homophones excluded)
- Machine-readable: **likely (OSF-hosted)** — *unverifiable (host blocked)*
- Usable without coder judgment: **Yes** — per-stimulus human ratings → deterministic P (A1.4)
- License/reuse: **unverifiable (OSF blocked)**
- Satisfies A1.2: **ADM-S** (criteria 1,3,4,7 met; 8 plausible; 2/5/6 unverified)
- Decision: **INCLUDE (candidate)**

**C2 — "Phonetic underpinnings of sound symbolism across multiple domains of meaning" (2024)**
- Identifier/URL: bioRxiv 2024.09.03.610970 ; PMC11398306 (hosts blocked)
- Query: "Phonetic underpinnings … 537 pseudowords OSF data"
- Stimulus type: **same 537 McCormick CVCV pseudowords**
- Dimension measured: **7 domains — shape, texture, weight, SIZE, brightness, arousal, valence**
- Lexically empty: **Yes**
- Machine-readable: **likely** — *unverifiable (host blocked)*
- Usable without coder judgment: **Yes** — per-stimulus human ratings → deterministic P
- License/reuse: **unverifiable**; **caveat:** preprint licenses are often CC-BY-NC-**ND**, which
  would **fail criterion 5** (no derivatives) — must be checked
- Satisfies A1.2: **ADM-S** (incl. SIZE, construct-aligned to the Glasgow SIZE endpoint)
- Decision: **INCLUDE (candidate; construct-aligned)**

**C3 — Knoeferle, Li, Maggioni & Spence (2017), "What drives sound symbolism?" (Sci. Rep.)**
- Identifier/URL: nature.com s41598-017-05965-y (host blocked)
- Query: "Knoeferle 2017 sound size shape pseudoword data"
- Stimulus type: **100 pseudowords** (+10 shapes)
- Dimension measured: **size and shape (roundedness)**
- Lexically empty: **Yes**
- Machine-readable: **likely (Sci. Rep. OA supplementary)** — *unverifiable*
- Usable without coder judgment: **Yes** — per-stimulus ratings → P
- License/reuse: **likely CC BY (OA journal)** — *unverifiable*
- Satisfies A1.2: **ADM-S**; **criterion-8 risk** — stimuli parametrically varied on acoustic
  features ⇒ potential E/phonology collinearity (a §9.0 check, not a screening exclusion)
- Decision: **INCLUDE (candidate; collinearity to watch)**

**C4 — Preziosi & Coane (2017), "Remembering that big things sound big" (Cogn. Res. P&I)**
- Identifier/URL: PMC5318481 ; springeropen 10.1186/s41235-016-0047-y (hosts blocked)
- Query: "Preziosi Coane 2017 nonword size ratings 100 nonwords data"
- Stimulus type: **100 nonwords**
- Dimension measured: **SIZE**
- Lexically empty: **Yes**
- Machine-readable: **likely** — *unverifiable*
- Usable without coder judgment: **Yes** — per-stimulus ratings → P
- License/reuse: **likely CC BY (open-access journal)** — *unverifiable*
- Satisfies A1.2: **ADM-S** (SIZE, construct-aligned; small N)
- Decision: **INCLUDE (candidate; construct-aligned, small)**

### EXCLUDED

**C5 — LEX-ICON (arXiv 2511.10045, 2025)** — 8,052 **real** words + 2,930 pseudowords, ≤25
semantic dims. **EXCLUDE:** mixes gloss-dependent real words; pseudoword-annotation provenance
(human vs model/LLM-generated) **could not be verified** (arXiv blocked) and an LLM-probing
dataset risks model-derived (not externally-measured-human) annotations → fails criterion 2/4
intent. Re-evaluate only if annotations confirmed human-measured.

**C6 — Sharma et al. (arXiv 2512.12245, 2025)** — 810 **adjectives** × 27 languages.
**EXCLUDE:** real adjectives → gloss-dependent (fails criterion 3/4).

**C7 — Winter et al. (2021), "Size sound symbolism in the English lexicon"** — **EXCLUDE:** real
lexicon items rated/derived with meaning → not lexically empty (fails criterion 3/4).

**C8 — "Do sound symbolism effects for written words relate to phonemes or phoneme features?"
(Lang. & Cognition)** — **EXCLUDE:** real written words → gloss-dependent (fails criterion 3).

**C9 — Schmidtke, Conrad & Jacobs (2014), "Phonological iconicity" / Sublexical Affective Values**
— **EXCLUDE:** per-unit values computed by **averaging valence/arousal of real words** containing
the unit → derived from a gloss-bearing corpus (fails criterion 4; this is the path that leaks
meaning).

**C10 — Winter et al. iconicity ratings (English, ~14k words)** — **EXCLUDE as primary:**
iconicity rated **against meaning** (fails criterion 4). Retained only as the §1 secondary
confounded-ceiling `E` (unchanged), not a primary candidate.

**C11 — Sapir (1929)** — **EXCLUDE:** no machine-readable per-segment table (fails criterion 2);
this is part of the original under-specified set the amendment replaced.

**C12 — Newman (1933)** — **EXCLUDE:** same as C11 (no machine-readable data).

**C13 — Köhler (1929/1947)** — **EXCLUDE:** exemplar contrast only; no extractable per-segment
values (fails criterion 2/7).

**C14 — Nielsen & Rendall (2011) / D'Onofrio (2014)** — **EXCLUDE (provisional):** pseudoword
shape studies with **no confirmed machine-readable public release** (criterion 2 unverifiable and
not indicated); revisit only if an open data artifact is found.

**C15 — Neural-basis pseudoword–shape studies (e.g. PMC10529692 / PMC10327042; bioRxiv 2023)** —
**EXCLUDE:** neuroimaging with small fixed stimulus sets; not a per-stimulus ratings dataset
(fails criterion 7 as an `E` source).

## 3. Ranking of admissible candidates (A1.3 metadata-only rule)
Rule: **largest documented stimulus/segment count**, tie-break **earliest publication date**.
*(Ranking is metadata-only and dimension-blind, as specified.)*

| Rank | Candidate | Count | Year | Dimension |
|---|---|---|---|---|
| 1 | **C1 McCormick** | 537 | 2015 | shape |
| 2 | **C2 multi-domain** | 537 | 2024 | 7 incl. **SIZE** |
| 3 | **C3 Knoeferle** | 100 | 2017 | size & shape |
| 4 | **C4 Preziosi & Coane** | 100 | 2017 | size |

**Construct-alignment flag for the A1.3 selection step (not resolved here).** The metadata-only
top rank (C1) measures **shape**, but the canonical confirmatory endpoint is **Glasgow SIZE**, and
no standard semantic *shape* `Y` norm exists. Per A1.3/A1.7 the endpoint may change **only** for
construct match, never result-seeking; a shape-only `E` would strand the endpoint. The
**construct-aligned** admissible source is **C2** (same 537 count, includes SIZE *and* shape) —
its only material gap is the **license caveat** (possible NC-ND preprint license → criterion 5).
This dimension-vs-ranking interaction is a documented **input to the A1.3 selection decision**;
A1.6 does **not** make the final pick.

## 4. Decision (desk-search outcome only)

> **SINGLE-SOURCE E FOUND — QUALIFIED (host-blocked verification pending).**

Justification: the bounded search positively identified **≥1 single, published, gloss-free,
lexically-empty, human-measured pseudoword sound-symbolism source** (C1–C4) satisfying the
**screenable** admissibility criteria (1 public/citable, 3 lexically-empty, 4 gloss-independent,
7 deterministically projectable; 8 plausible). This is **not** a fallback situation (A1.5 not
triggered) and **not** an environment-blocked null: identification succeeded.

**Binding qualifier:** criteria **2 (machine-readable format), 5 (license permits
redistribution/derivatives), 6 (fixed freezable artifact)** are **unverified** because the data
hosts (OSF/bioRxiv/PMC/Springer/Nature/doi.org/arXiv) are egress-blocked this session. Therefore:
- the find is **substantive but not freeze-ready**;
- **A1.3 selection** and **A1.8 freeze** are **blocked until host access is granted** and the
  selected source's license + machine-readability are confirmed (especially the **C2 license
  caveat**);
- no A′ execution, no freeze, and no downstream B–G work follows from this register.

## 5. Next steps (each separately authorized; none taken here)
1. Obtain egress access to the data hosts (or supply the candidate files out-of-band).
2. Verify, for the construct-aligned candidate (C2; fallbacks C1/C4/C3): exact machine-readable
   format, fixed-artifact existence, and a **redistribution/derivative-permitting license**.
3. If verified → run **A1.3** selection (apply ranking + construct-alignment) and **A1.8** freeze.
4. If C2's license fails and no size-aligned admissible source verifies → escalate to the A1.3
   endpoint/construct decision or the A1.5 fallback, as pre-registered.

---
> **A1.6 desk search · sources identified, verification host-blocked · no values inspected ·
> no freeze · A′ not run · ⊥ preserved · Stage A untouched.**
> **structure, not validated meaning.**
