# DilChat — Score-Family Separation Audit

**Product:** DilChat (consumer) · **Company:** Ugence Labs · **Site:** dilchat.com
**Document type:** Independent verification audit (DESIGN-phase; no production code exists to audit — this audits the design corpus).
**Auditor role:** Independent verification auditor. This document only *verifies*; it changes no design decision. Where design and the decision log disagree, the decision log wins (that would itself be a finding).
**Scope:** Verify that the **three score families** of DEC-019 are never merged or conflated in any schema, API response, or spec.
**Canonical reference under audit:** `DILCHAT_DECISION_LOG.md` (DEC-019 authoritative).

---

## 0. The three families under audit

| # | Family | Immutable? | Version identifier(s) |
|---|--------|-----------|-----------------------|
| 1 | **Classical Guna Milan** (Ashtakoota, 0–36) | Yes, per version tuple | `rule_pack_id = ashtakoota_lahiri_classical_v1` |
| 2 | **Daily Moon Emotional / Interest Climate** | Recomputed daily (new rows) | `transit_model_version = dilchat_transit_v1`, `interest_model_version = dilchat_interest_v1` |
| 3 | **Living Compatibility** (behavioral) | Evolves from consented data | `living_compat_model_version = dilchat_living_v1` |

**Governing decision (verbatim, `DILCHAT_DECISION_LOG.md:361`):** *"Three score families are stored and versioned **separately** and never merged"* — enumerating (1) Classical Compatibility "Immutable once computed for a given version tuple. AI may explain, never alter." (2) Daily climate "Labeled DilChat models, not classical predictions." (3) Living Compatibility "Never feeds back into (1)." Line 371: *"Behavioral personalization can adjust presentation of (2) within clamped bounds but can never rewrite (1) or astrology history."*

---

## 1. VERDICT (stated up front)

> ## SCORE_SEPARATION_ENFORCED (with two minor labeling-consistency findings)

Separation is enforced **structurally and redundantly**: separate owning modules and tables (F), per-version-tuple immutability backed by triggers + RLS + unique constraints (B), divergent provenance blocks where family 1 carries `rule_pack_id` and never a model-version and family 2 carries model-versions and never a `rule_pack_id` (E/F), an AI layer that is architecturally a *translator* forbidden to compute (C), and a one-directional behavioral→classical barrier proven by property test PB-11 (D). **No DB column, no schema, and no API response returns a blended/overall/final cross-family number.** The two findings (§5) concern user-facing *machine-readable labeling granularity* on family-2/family-3 deterministic responses, not any actual merge — hence "with findings," not "violated."

---

## 2. Three-families comparison table (verified)

| Attribute | **Family 1 — Classical Guna Milan** | **Family 2 — Daily Climate** | **Family 3 — Living Compatibility** |
|---|---|---|---|
| Source inputs | Two natal Moons (rashi/nakshatra/pada) + rule pack | Sidereal transit Moon vs natal Moon, per user, per day | Consented behavioral data (feedback, agreements) |
| Owning module (`DATA_MODEL.md:45–61`) | `guna_milan` | `moon_transits` | `feedback` |
| Storage table | `guna_report` (`:243`) | `transit_daily_personal` (`:286`), `transit_couple_climate` (`:311`), `transit_daily_global` (`:267`) | `fb_living_compat_score` (`:541`) |
| Version identifier | `rule_pack_id` (+ `ephemeris_version`, `ayanamsa`) | `transit_model_version`, `interest_model_version` | `model_version = dilchat_living_v1` |
| Value column(s) | `total_score INT [0..36]`, `components JSONB` | `interest_scores JSONB`, `emotional_comfort`… (6+ NUMERIC(4,3)); couple: `tension_risk`, `synchronization` | `aggregate NUMERIC(5,3)`, `subscores JSONB` |
| Mutability | **Immutable** after insert (trigger + RLS + unique tuple) | New row per (user, date, version tuple) | New row per (couple, model_version, computed_at) |
| Who/what may change it | **Nothing** — version bump inserts a *new* row (`:913–922`) | Recompute sweep inserts new rows; behavioral personalization touches **presentation only** (`ASTROLOGY:920–926`) | Feedback pipeline recomputes aggregate; never writes into (1) or (2) |
| Provenance field carried | `rule_pack_id` present; **no** `transit/interest/living` model version | `transit_model_version` + `interest_model_version` present; **no** `rule_pack_id` | `living_compat_model_version`; aggregate only |
| Classification label | `[Traditional Vedic rule]` — classical | `[DilChat proprietary interpretation]` (`ASTROLOGY:802`) | `[DilChat proprietary interpretation]` |
| AI role (`AI_SPEC:79–94`) | **EXPLAIN only — never re-summed** | consume as input; may rank/label | consume jointly-visible aggregate only |

The three families live in three different modules with three different table prefixes and three different version identifiers. There is **no fourth "combined" module, table, or column.**

---

## 3. Claim-by-claim verification

### Claim A — No DB table/column co-mingles a classical Guna total with a climate or living score. **CONFIRMED.**

A full-corpus search for combining vocabulary (`blended|combined score|overall score|merged|blend|composite`) returns **only negations and structural separations**, never a field:

- `DATA_MODEL.md:26` (design canon): *"Classical / Daily-derived / Living scored & versioned separately, **never merged**"*.
- `DECISION_LOG.md:361`: *"stored and versioned **separately** and **never merged**"*.
- `ASTROLOGY_ENGINE_SPEC.md:44`: *"the three **separately versioned, never-merged** score families of DEC-019"*; `:1163` *"proprietary, **never merged** with classical."*
- `TEST_PLAN.md:23` (INV-6): *"Ashtakoota scores are **never merged** with `dilchat_transit_v1` / `dilchat_interest_v1` / `dilchat_living_v1` scores."*
- The single literal `blended` in the corpus is `AI_SPEC:278`: *"Never blended with the partner's private profile"* — a **scope** negation (family-2 own-vs-partner), reinforcing separation, not a score field.

Schema-level confirmation: `guna_report` (`DATA_MODEL.md:966–981`) has columns `total_score`, `components`, `applied_exception_ids`, `input_confidence`, `calc_trace` — **no** `overall`, `blended`, `final`, `combined`, or any climate/living column. `transit_daily_personal` (`:286–309`) carries `interest_scores`/climate scalars with **no** `guna`/`total_score` column. `fb_living_compat_score` (`:541–552`) carries `aggregate`/`subscores` scoped to family 3 only, with a note (`:547`) *"aggregate only; no per-partner raw inputs."* No table imports another family's score as a stored column. **Reproduced and confirmed.**

### Claim B — Classical Guna Milan and NatalChart are IMMUTABLE per version tuple. **CONFIRMED.**

- **Design canon** `DATA_MODEL.md:27`: *"Immutability | Classical Guna Milan & NatalChart immutable per version tuple | DEC-019"*.
- **NatalChart** `DATA_MODEL.md:218` header *"NatalChart (IMMUTABLE; DEC-007, DEC-008, DEC-019)"*; `:238` *"Immutable after insert (no UPDATE; enforced by trigger + RLS, §6/§10)."*; unique `:239` `(birth_profile_id, ephemeris_version, ayanamsa)` = "one chart per version tuple."
- **GunaMilanReport** `DATA_MODEL.md:243` header *"GunaMilanReport (IMMUTABLE; DEC-009, DEC-019)"*; `:260–261` *"Immutable after insert. Unique: (seeker_chart_id, partner_chart_id, rule_pack_id, ephemeris_version, ayanamsa) — the **version-tuple uniqueness** guaranteeing 'compute once per tuple.'"*
- **Enforcement is triple-layered.** DDL `:983` `CREATE TRIGGER guna_immutable BEFORE UPDATE OR DELETE ON guna_report … EXECUTE FUNCTION raise_immutable();`; `:1071–1073` *"`raise_immutable()` … raises an exception on any UPDATE/DELETE, backstopping the immutability of NatalChart, GunaMilanReport, ConsentEvent, and AuditEvent even against a mistaken app write."* RLS `:775–776`: *"Immutability … is enforced by omitting any UPDATE/DELETE policy and additionally by BEFORE UPDATE/DELETE triggers that raise."*
- **Version change appends, never mutates** `:913–922`: *"NatalChart, GunaMilanReport, AuditEvent are never migrated in-place with recomputed values … a version bump enqueues an arq sweep that **inserts new rows** … Old rows remain."* Engine echo `ASTROLOGY:938`: *"a new version surface producing **new rows**, never an in-place edit (INV-D5, DEC-019)."*

### Claim C — AI may EXPLAIN but never RECALCULATE or ALTER a deterministic result. **CONFIRMED.**

- **Invariant AI-1** `AI_SPEC:64–68`: *"The AI layer MUST NOT calculate, re-derive, adjust, round, re-weight, or 'correct' any planetary position, nakshatra, pada, rashi, Koota value, Guna Milan total, transit score, interest score, or living-compatibility score. Every such number reaching the AI is an **input it may cite but never mutate**."*
- **Invariant AI-2** `AI_SPEC:70–76`: *"The AI **may EXPLAIN a Guna Milan score** … but it **must never recalculate or alter it** … The number in the explanation is copied verbatim from the deterministic input and cited by field name."*
- **Value→producer table** `AI_SPEC:83–85`: Individual Koota scores and the "Ashtakoota total (0–36)" are produced by `guna_milan`, AI role *"EXPLAIN only — never re-summed"*.
- **Grounding (Invariant AI-4)** `AI_SPEC:1289–1292` + post-filter `:196` output schema: `cited_score` *"MUST equal input.raw_score exactly. Post-filter rejects mismatch."* Engine echo INV-D2 `ASTROLOGY:54`: *"No language model participates in any astronomical or scoring computation … LLMs only *explain* already-computed, schema-validated values."*
- **Requirement + Test.** PRD `FR-1305` (`:339`): *"AI never alters classical scores | P0 | AI can explain a Koota; cannot change its value (DEC-019)."* The proving test is **PB-11** (`TEST_PLAN.md:374`): *"**Separation:** no code path lets a `dilchat_living_v1` value alter a stored Guna Milan component (mutation attempt is rejected/no-op; classical row unchanged)."* → **INV-7** (`:24`): *"Behavioral personalization can NEVER rewrite astrology … it never mutates concept (1) or astrology history."* Companion **INV-6** (`:23`) guards non-merge; test **AI-05** (`:559`) asserts a malicious adapter emitting fabricated Koota/longitude values is rejected and *"the served scorecard/profile numbers equal the deterministic engine's, not the AI's."*

*Auditor note on invariant numbering:* the task brief referenced "INV-6, INV-7" for this claim. In `TEST_PLAN.md` those IDs are the correct score-separation invariants (INV-6 = classical ≠ derived; INV-7 = personalization never rewrites astrology), and PB-11 maps to **INV-7**. (The `PRIVACY` doc reuses the labels INV-6/INV-7 for consent-projection invariants — a namespace collision worth noting but not a separation defect.)

### Claim D — Living Compatibility never feeds back into the classical score or astrology history. **CONFIRMED.**

- PRD `FR-1403` (`:347`): *"No feedback into classical score | P0 | Living Compatibility never mutates Guna Milan or astrology history (DEC-019)."*
- Roadmap `:406`: Living Compatibility *"**never feeds back into the classical score or astrology history** (FR-1403, DEC-019)"*; `:412` test *"aggregate never mutates Guna Milan/astrology (FR-1403) — invariant test"*; `:415` security check *"behavioral data never rewrites classical score (DEC-019)."*
- DEC-019 `:369`: family 3 *"Never feeds back into (1)."*
- API `:567`: *"Living Compatibility never feeds back into classical Guna Milan (DEC-019)."*
- **The barrier is one-directional and structurally read-only.** Family 2's couple equations *read* the classical Bhakoot result as a feature without touching it — `ASTROLOGY:891–893`: *"`bhakoot_flag_AB` reuses the **classical** Bhakoot dosha result (§5.8) as a *feature* — the classical score is **read, never modified** (DEC-019)"*; pseudocode `:1137` comment *"reads CLASSICAL result, unmodified."* Behavioral calibration is confined to presentation `ASTROLOGY:920–926`: *"a **presentation-layer** calibration may re-rank or re-emphasize … within clamped bounds … It **cannot** alter any classical Guna Milan value, any stored transit feature, or the raw score equations — only the ordering/emphasis of what is shown (DEC-019)."* The consent gate for family-3 inputs is a preference flag: `users_preferences.behavioral_personalization_enabled` *"gates Living Compat inputs (DEC-019)"* (`DATA_MODEL.md:186`).

### Claim E — Daily interest/tension/comfort/receptivity scores are LABELED DilChat-derived, not classical Vedic formulas; provenance carries the transit/interest model_version, not a rule_pack_id. **CONFIRMED.**

- **Section-level label** `ASTROLOGY:802–808` (§8 header): *"**Everything in §8 is a DilChat product model, NOT a classical formula (DEC-019).** These equations map already-computed transit features onto DilChat's 12-interest ontology and 8 daily dimensions. They are versioned as `dilchat_interest_v1` / `dilchat_interp_v1`."* The 8 daily-climate dimensions (`emotional comfort, sensitivity, expression tendency, conversation receptivity, need for space, decision steadiness, couple tension risk, couple synchronization`) are declared `[DilChat proprietary interpretation]` at `:869`. Even the phase display quantity is tagged proprietary (`:770`).
- **Provenance separation (the decisive structural evidence).** The two deterministic API responses carry *disjoint* provenance blocks:
  - Guna Milan scorecard `API_SPEC:726–732` provenance contains `rule_pack_id: "ashtakoota_lahiri_classical_v1"` and **no** `transit_model_version` / `interest_model_version`. Narration `:735–736`: *"`total.score` is the classical Ashtakoota total (DEC-019 family 1) — immutable for this version tuple, and AI may explain but never alter it."*
  - Daily interest profile `API_SPEC:768–775` provenance contains `transit_model_version: "dilchat_transit_v1"` and `interest_model_version: "dilchat_interest_v1"` and **no** `rule_pack_id`; plus disclaimer `:767` and `AI_SPEC:399` *"This is DilChat's daily-climate model (dilchat_transit_v1), **not a classical prediction** and not a forecast of events."*
- **AI output kind is a `const`.** Every family-2 AI output object sets `"kind": { "const": "dilchat_interpretation" }` (e.g., `AI_SPEC:187, 331, 446`), and the daily-summary disclaimer is mandatory. The invariant provenance schema (`AI_SPEC:1574`) pins `prompt_pack_version` — an AI-layer version, never a rule pack. Language rule PRD `:27`: *"Concept (2) is *interpretation*, never *classical prediction*."* Test `U-MT-06` (`:199`) enforces it.

### Claim F — Each family carries its OWN provenance/version identifier, stored in separate tables. **CONFIRMED.**

The canonical provenance tuple (`DATA_MODEL.md:30–39`, `DECISION_LOG.md:36–49`) enumerates *distinct* fields per family: `rule_pack_id` (1), `transit_model_version` + `interest_model_version` (2), `living_compat_model_version` (3). Storage is in three separate module-owned tables:

- `guna_report.rule_pack_id` (`:250`) — family 1, module `guna_milan`.
- `transit_daily_personal.transit_model_version` + `.interest_model_version` (`:305–306`) — family 2, module `moon_transits`; couple aggregate `transit_couple_climate.model_version` (`:321`).
- `fb_living_compat_score.model_version = dilchat_living_v1` (`:546`) — family 3, module `feedback`.

Each table has its **own** version-tuple unique constraint (`:608, 611, 612, 552`), so a value can only ever exist keyed by its own family's version identifier. Cross-module reads must go through service ports, never raw SQL against another module's tables (DEC-002, `:43`), so no query joins family 1 and family 3 into one row.

---

## 4. Conflation-attempt test list (where conflation *could* occur, and why it does not)

Each row is a plausible code path where two families might bleed together; the right column shows the design control that keeps them separated.

| # | Conceivable conflation path | Design control that separates it | Evidence |
|---|---|---|---|
| C1 | **AI "explains" a score and silently re-computes / re-sums it** | AI-1/AI-2 forbid computation; grounding post-filter requires `cited_score == input.raw_score`; AI reads values as **immutable inputs** cited by field name | `AI_SPEC:64–76, 196, 1289–1315`; test AI-05 `:559` |
| C2 | **A combined dashboard endpoint returns one merged compatibility number** | No such endpoint exists. Three separate endpoints — `GET /couples/{id}/guna-milan`, `GET /me/daily` + `/couples/{id}/climate`, `GET /couples/{id}/living-compatibility` — each returns its own family with its own provenance block; the dashboard **composes, never merges** | `API_SPEC:454, 464–465, 564`; §2 above |
| C3 | **Behavioral personalization rewrites a classical or transit value while "adjusting" it** | Personalization is presentation-only within clamped bounds; cannot alter Guna values, stored transit features, or raw equations | `ASTROLOGY:920–926`; DEC-019 `:371`; PB-11 `:374` |
| C4 | **Living Compatibility aggregate flows back into the Guna total** | One-directional read-only barrier; FR-1403; PB-11 asserts mutation attempt rejected / classical row unchanged | `PRD:347`; `ROADMAP:406,412,415`; `TEST_PLAN:374` |
| C5 | **Family-2 couple equations consume Bhakoot and mutate it** | Classical Bhakoot is read as a *feature*, "read, never modified"; classical row is immutable regardless (trigger) | `ASTROLOGY:891–893, 1137`; `DATA_MODEL:983` |
| C6 | **A shared "compatibility" record co-stores classical + climate + living columns** | Three separate tables in three modules; no shared row; each has its own unique version-tuple key | `DATA_MODEL:243, 286, 311, 541` |
| C7 | **Provenance ambiguity lets a climate score masquerade as classical** | Disjoint provenance: family 1 carries `rule_pack_id` and no model-version; family 2 carries model-versions and no `rule_pack_id`; AI `kind: const dilchat_interpretation` | `API_SPEC:726–732` vs `768–775`; `AI_SPEC:187` |
| C8 | **A malicious/hallucinating AI adapter injects fabricated Koota/longitude numbers** | Grounding + validation reject fabricated values; served numbers equal deterministic engine's, not AI's; unvalidated egress forbidden (AI-3) | `AI_SPEC:1266–1268, 1289–1315`; test AI-05 `:559` |
| C9 | **Version bump recomputes and overwrites the prior classical/history in place** | Append-only sweep inserts new rows keyed by new version tuple; old rows retained; INV-7 corollary "astrology history is immutable" | `DATA_MODEL:913–922`; `TEST_PLAN:270`; `ASTROLOGY:946–955` |

**On C2 specifically (the combined/dashboard concern raised in the brief):** the corpus defines *no* endpoint that returns all three families in a single merged number. Where a client shows them together it must call three distinct endpoints, each returning a **separately labeled field with its own provenance block** — the composition happens client-side over three provenance-stamped payloads, not as a server-side merge. This satisfies the "separate labeled fields with separate provenance, not a merged number" requirement.

---

## 5. Findings

Both findings are **minor / labeling-consistency**; neither is an actual merge, and neither downgrades the structural verdict. They are recorded so an implementer closes the gap between the airtight *storage/provenance* separation and the *machine-readable presentation label* on deterministic (non-AI) responses.

### Finding F-1 (Severity: LOW) — Deterministic daily/climate API responses lack an explicit machine-readable family label field.

**Observation.** AI-produced family-2 outputs carry `"kind": "dilchat_interpretation"` as a schema `const` (`AI_SPEC:187, 331`). But the **deterministic** daily response example (`API_SPEC:744–776`) conveys "this is family 2, not classical" only via (a) the prose `disclaimer` string (`:767`) and (b) the `transit_model_version`/`interest_model_version` in provenance. There is no top-level enum field (e.g., `family: "daily_climate"` / `kind: "interpretation"`) analogous to the AI `kind`. Test `U-MT-06` (`TEST_PLAN.md:199`) *requires* the concept-2 output be *"labeled `interpretation`, never `classical_prediction`"* — so the test presumes a label the API example does not show.
**Risk.** A client could render a family-2 number without the disclaimer and, absent an explicit label, present it with classical weight. Low risk because provenance already disambiguates by version string.
**Recommendation.** Add an explicit, schema-`const` family/label field (e.g., `"kind": "interpretation"`) to the deterministic `GET /me/daily` and `GET /couples/{id}/climate` response schemas, mirroring the AI `kind` const, so the U-MT-06 label is machine-checkable on deterministic responses too.

### Finding F-2 (Severity: LOW) — Family-2 couple-climate and family-3 living-compat tables use a generic `model_version` column instead of family-explicit version columns.

**Observation.** `transit_daily_personal` names its provenance columns explicitly (`transit_model_version`, `interest_model_version`, `:305–306`). But `transit_couple_climate.model_version` (`:321`) and `fb_living_compat_score.model_version` (`:546`) both use a generically named `model_version` column. The values differ correctly (`dilchat_transit_v1`-family vs `dilchat_living_v1`), but the shared column *name* across two different families slightly weakens self-description and could invite a future join/utility that treats them as the same axis.
**Risk.** Very low; the values and owning tables/modules remain distinct, and no cross-family read is permitted (DEC-002).
**Recommendation.** Rename to family-explicit columns (`climate_model_version`, `living_compat_model_version`) for symmetry with `transit_daily_personal`, so provenance intent is unambiguous at the column level and no generic `model_version` name is reused across families.

*No HIGH or MEDIUM findings.* No column, schema, or response was found that stores or returns a blended cross-family number; no path was found by which family 2 or 3 can mutate family 1.

---

## 6. Traceability

| Audit claim | Governing decision / requirement | Primary structural control | Proving test |
|---|---|---|---|
| A — no co-mingled field | DEC-019; canon `DATA_MODEL:26` | Separate columns; only-negation search result | INV-6 / PB-5-adjacent |
| B — immutability | DEC-019; `DATA_MODEL:27, 218, 243, 260` | `raise_immutable()` trigger + RLS + unique tuple | PB-3/PB-4; IT-RECALC-01 (`:262`) |
| C — AI explain, never alter | DEC-014, DEC-019; FR-1305 | AI-1/AI-2/AI-4; grounding post-filter | PB-11 (INV-7); AI-05 |
| D — no feedback into classical | DEC-019; FR-1403 | one-directional read-only barrier; presentation-only calibration | PB-11; ROADMAP:412 |
| E — family-2 labeled proprietary | DEC-019; PRD language rule `:27` | disjoint provenance; `[DilChat proprietary interpretation]`; AI `kind` const | U-MT-06 |
| F — own provenance, separate tables | DEC-019 §0 tuple; DEC-002 | three modules / three tables / three version ids | INV-16; INV-5 |

---

## 7. Conclusion

The DilChat design corpus enforces score-family separation along **five independent axes at once** — module ownership, physical table separation, per-version-tuple immutability (trigger + RLS + unique constraint), disjoint provenance identifiers, and an AI layer architecturally barred from computation — with a dedicated property test (PB-11) pinning the one-directional behavioral→classical barrier and a merge-guarding invariant (INV-6). No schema, column, or API response returns a blended, overall, or final cross-family score; a client that shows all three shows three separately labeled, separately provenance-stamped fields. The only gaps are two low-severity labeling-consistency items on deterministic family-2/family-3 surfaces (§5), neither of which is a merge.

> ## FINAL VERDICT: SCORE_SEPARATION_ENFORCED_WITH_FINDINGS
> (Separation is strongly and redundantly enforced. The two findings are LOW-severity labeling-consistency items on user-facing family-2/family-3 responses — close them and the corpus is at unqualified SCORE_SEPARATION_ENFORCED.)

*End of DILCHAT_SCORE_SEPARATION_AUDIT.md*
