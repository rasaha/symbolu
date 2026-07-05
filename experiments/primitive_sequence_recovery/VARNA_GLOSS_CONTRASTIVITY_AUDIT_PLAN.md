# Varṇa-Gloss Contrastivity Audit — Plan & Gate Spec (companion to B1.1)

**Status:** `FUTURE_DESIGN_ONLY` — drafted 2026-07-04. **No model run · no generation · no scoring ·
nothing committed until reviewed.** Does **not** modify B1, does **not** change the B1 verdict
(`RANDOM_OR_SCRAMBLED_MATCHES`), does **not** rescue Track B, and makes **no** claim of ontology
validation, Sanskrit privilege, semantic truth, or H2 validation. **Structure, not validated meaning.**

This is the procedure that produces the **revised, contrastive A pool** B1.1 requires (design memo §3–§4)
and the **pass/fail gate** that pool must clear *before* any B1.1 generation. It is the operationalization
of one hypothesis only — *"R matched A because the meaning pool is too semantically overlapping"* — and it
is **necessary but not sufficient**: a contrastive pool with an arbitrary word→mapping link still yields
A ≈ R (that is what R_deranged tests, not this audit).

---

## 1. Inputs (read-only)

- `varna_lens/lexicon_authoritative.json` — per-consonant `binding_state` (blocked) / `liberating_state`
  (liberated), each `{english, sanskrit}`.
- `varna_lens/layer2_bridge_vocab.json` — the 64 BRIDGE meaning-phrases actually used to condition
  generation.
- (Cross-check) `B1_LEXICON_CONTRASTIVENESS_DIAGNOSTIC.md` (4ee85ab) — the prior read-only inspection whose
  hand findings this scripted audit supersedes.

The audit **reads** these; it never edits them in place. The revised pool is written to a **new** file
(`lexicon_authoritative_varna.json` already exists as an untested CANDIDATE, 1ae4d4b; B1.1 may supersede
it) and, if adopted, is placed **inside the B1.1 freeze set**.

---

## 2. Collision taxonomy (what to detect)

For every pair of entries, classify:

| type | definition | detection |
|---|---|---|
| **exact duplicate** | identical gloss string (normalized) | string equality after lemmatization |
| **near-dup liberated pole** | liberated glosses share ≥1 content lemma **or** cosine ≥ τ_near | lemma overlap + embedding |
| **near-dup blocked pole** | blocked glosses share ≥1 content lemma **or** cosine ≥ τ_near | lemma overlap + embedding |
| **broad-valence cluster** | ≥ k entries within cosine τ_broad of a centroid (same affect basin) | agglomerative clustering |

Severity ladder: **exact** > **near** > **broad-valence**. Report counts at each level.

## 3. Metrics & the contrastivity gate

Compute over the pool used to condition A:
1. **Pairwise gloss-distance matrix** (embedding cosine) for blocked poles, liberated poles, and BRIDGE
   phrases separately.
2. **Distance histogram** + summary: median, 10th percentile, and count of pairs below τ_near.
3. **Cluster sizes** at τ_broad; largest cluster k_max.
4. **Duplicate/near-duplicate counts** per §2.

**Pre-registered gate (thresholds fixed BEFORE running):**
- `exact_duplicates == 0`
- `pairs_below_τ_near ≤ P_max` (P_max pre-registered)
- `k_max ≤ K_max` (no affect basin larger than K_max entries)
- `median_pairwise_distance ≥ τ_min`

τ_near, τ_broad, τ_min, P_max, K_max, and the embedding model are **all pre-registered constants** (frozen,
hash-bound). A pool that fails the gate **cannot be used for B1.1 A**; it must be rewritten and re-audited
until it passes, and the passing pool is frozen.

> **Anti-gaming note.** The gate is on *pool separability only*. Passing it does **not** predict A will
> beat R — it only removes the "pool too mushy" confound so that R_deranged/R_domain become interpretable.
> The gate must not be tuned after seeing B1.1 outcomes.

## 4. Rewrite procedure (produces the four-field entries)

For each varṇa, author the four fields from the B1.1 design memo §4:
`blocked impulse · liberated impulse · functional operation · contrast boundary`.

Rules:
- **No synonym swaps.** A rewrite that only substitutes a near-synonym for a colliding gloss fails review.
- **The contrast-boundary field must name the specific neighbors** it separates from (e.g. "not Ya's
  relational trust"), and those named separations must be **verified by the embedding gate** (the two
  entries must sit ≥ τ_min apart after rewrite).
- **Sanskrit terms and phoneme→varṇa assignments are NOT changed** by this audit — only English glosses and
  the added operation/boundary fields. (Changing assignments would be a different, larger intervention and
  must be its own pre-registered study.)
- Each rewritten entry records a `rationale` and the `collisions_resolved` it targets, for review.

## 5. Seed collisions to resolve (from the prior inspection — verify with the script)

Preliminary basins the scripted audit must confirm and split (illustrative, not final):

- **detachment / renunciation / non-attachment:** Ka (hope→detachment), Gha (attachment→non-attachment),
  Dha (craving→cessation) — split by *what is released* (outcome vs object vs craving).
- **fearlessness:** Ḍa (shame→), Pha (fear→) — split by *what fear dissolves* (social shame vs threat).
- **awakening/clarity/knowledge:** Ta (dullness→), Bha (stupor→), Ca/Na (discernment) — split onset vs
  collapse vs analytic discrimination.
- **compassion/softening:** Ḍha (malice→compassion), La (cruelty→compassion) — **strongest collision**;
  split by *object* (slandered vs physically weak).
- **trust/openness:** Kha (anxiety→open-under-uncertainty), Ya (distrust→relational trust) — split spatial
  vs relational.
- **humility/ego:** Ṅa (pretense→), Ja (ego→) — split pretense-dropping vs ego-deflation.
- **forgiveness/patience:** Ṭha (remorse→self-acceptance), Da (anger→forbearance) — split self- vs
  other-directed.

## 6. Outputs

- `varna_contrastivity_report.json` — machine-readable: per-pair distances, collision list by severity,
  cluster sizes, gate pass/fail.
- Revised four-field pool file (new file; not an in-place edit) — **only if** the gate passes.
- A short human-readable summary appended for review.

**None of these are model runs.** The audit is CPU-only text/embedding analysis. The embedding model and
all thresholds are pre-registered and hash-bound so the audit is reproducible and non-gameable.

## 7. Integrity

- Read-only over the current lexicon; revised pool written to a **new** file, never in place.
- Thresholds and embedding model **pre-registered before running**; no post-hoc tuning.
- Passing the gate is a **precondition** for B1.1 A, **not** evidence for H2.
- If adopted, the revised pool + report are placed **inside the B1.1 freeze set** (closing the B1 gap
  where the lexicon JSONs were outside the frozen 11).

**Structure, not validated meaning.** Design only; the B1 verdict stands and Track B remains BLOCKED.
