# B1.10 — Official Judge Panel & Independence Spec (docs-only)

**Freezes the judge configuration and independence rules for the official B1.10 control-extension run.** Docs-only:
no frozen items, packets, contexts, runners, evidence-freeze declarations, results, or experiment numbering are
altered. Stays under B1.10. Resonance / phonetic-fidelity refinement only — **no `GENUTILITY_*`, no
`ONTOLOGICAL_SIGNAL`, no semantic-truth / ontology / Sanskrit-privilege claim.** B1.4b′ remains
`NULL_RETURN_BOTTOM`; original B1.4b blocked; Track B blocked. **Structure, not validated meaning.**

Basis: B1.8 (`B1_8_CONTEXT_RESOLVED_GENERATION_RUNBOOK.md`), the B1.6-v2 judge panel
(`b1_6_llm_judge_panel.py`), `B1_JUDGE_PATH_ADDENDUM.md`, `B1_JUDGE_RUN_V2_PROVENANCE.json`. B1.10 reuses the B1.8
**judge models and diversity policy**; it does **not** reuse the B1.8 *rubric* (see §3).

---

## 1. Official judge panel (FROZEN)

The official B1.10 run uses the exact B1.8 / B1.6-v2 three-judge panel:

| code | model id | family |
|---|---|---|
| J0 | `meta-llama/Llama-3.1-8B-Instruct` | Llama |
| J1 | `meta-llama/Meta-Llama-3-8B-Instruct` | Llama |
| J2 | `google/gemma-2-9b-it` | Gemma |

- **Decoding:** greedy (temperature 0), backend `transformers`, via the reused `b1_6_llm_adapter` (retry-on-
  unparseable, no output editing).
- **Cross-family:** two families (Llama, Gemma), three checkpoints — the program's established sufficiency bar.
- **Rationale for reuse (over the Claude pilot):** cross-family independence; removes the Claude-judges-Claude-
  authored-paraphrase self-preference risk (the Tier-3 plain-English renders were authored by Claude); same
  measurement instrument as B1.6/B1.8/B1.9. The B1.10 *pilot* (Claude Opus + Sonnet) is hereby re-labelled a
  **Claude-judge probe**, methodologically distinct from this official panel; its +9 margin is not directly
  comparable to any Llama/Gemma-panel result.

## 2. Judge-family independence rule (FROZEN)

- No model may judge text it authored. The Tier-3 packets are Claude-authored paraphrases; therefore **no Claude
  model may serve as a judge** in the official run.
- The judge panel must be **family-disjoint** from (a) any generator (B1.10 has none — trivially satisfied),
  (b) the **context author** (§5), and (c) the **Tier-3 paraphrase author** (Claude).
- The existing `detect_judge_generator_conflicts` guard (`b1_6_llm_judge_panel.py`) flags `judge == generator` and
  `SAME_FAMILY`; for B1.10 the analogous check is judge-vs-(context-author, paraphrase-author) family.
- **Mistral and Qwen remain non-judges** (carried from `B1_JUDGE_PATH_ADDENDUM.md`); they are eligible only as an
  independent context author (§5), never as judges.

## 3. What is reused, and what is NOT

- **Reused:** the three judge **models**, the cross-family diversity policy, the no-self-judging policy, the
  `b1_6_llm_adapter` decoding/retry stack, and the blind-package discipline (judges see only word + context
  sentence + packet text).
- **NOT reused:** the B1.8 **rubric.** B1.8 used the frozen B1.6 **1–7** generative-utility rubric (8 positive +
  2 penalty dimensions) to rate *generated interpretations*. B1.10 is a **no-generation** rating and keeps its own
  **0–6 single-question** source-condition rating (the frozen `run_b1_10_control_ext` question and scale). The
  panel is the same; the scale and question are B1.10's own and are unchanged by this spec.

## 4. Same-panel-for-all-three-tiers rule (FROZEN)

All three tiers — **Tier 1 (valence)**, **Tier 2 (generic source-condition)**, **Tier 3 (specific packet)** — and
both poles and both contexts, i.e. all 72 cells, **must be rated by the identical J0+J1+J2 panel**, each cell rated
by all three judges (≥3 ratings/cell). Rationale: the primary statistics are **within-panel** differences —
`increment_over_valence = specific_margin − valence_margin` and
`increment_over_source_condition = specific_margin − generic_source_condition_margin`. Judging tiers with different
models would confound *tier* with *judge* and invalidate both increments. No tier may be rated by a different or
partial panel.

## 5. Context-author independence rule (FROZEN)

The official contexts (per `B1_10_INDEPENDENT_CONTEXT_GENERATION_PROTOCOL.md`) must be produced by an author that is:
- **packet-naive** — sees none of the §1 never-see material in that protocol (Tier-3 packets, varṇa sequences,
  prior context sets, audits, facet notes, prior results) — **mandatory**;
- **disjoint from the judge panel** — not J0/J1/J2, and not the Llama or Gemma families;
- **disjoint from the Tier-3 paraphrase author** — not Claude / not any Anthropic model.

An LLM context author, if used, may therefore be a single fresh session of a model **outside** {Llama, Gemma,
Claude} — e.g. `mistralai/Mistral-7B-Instruct-v0.3` or `Qwen/Qwen2.5-7B-Instruct` (both non-judge, non-paraphrase
families) — or a human. The three packet-aware development context sets remain
`EXCLUDED_DEVELOPMENT_CONTEXTS_PACKET_AWARE` and are never official stimuli.

## 6. Provenance requirements for the independent author (FROZEN)

At context-generation time, record (per the generation protocol §9):
- **author identity** — human (name/role) or the exact model id + a clean-session attestation;
- **date** (UTC);
- **prompt hash** — sha256 of the exact author prompt delivered;
- **context hash** — sha256 of the frozen 12-sentence set;
- **acceptance checklist** + rejection/regeneration log;
- **blindness attestation** — explicit statement that the author saw none of the never-see material and is
  disjoint from the judge panel and the paraphrase author (§2, §5).

## 7. Seeds / evaluation settings (FROZEN for B1.10)

- B1.10 keeps its **own** fixed seeds (`20260712`, and a second replicate seed such as `20260713`), documented in
  the runner; it does **not** adopt B1.8's `reblind_seed = 20260709`.
- Judges greedy (temp 0); each of the 72 cells rated by all three judges; ≥2 replicate seeds recommended for the
  cell-order shuffle. Missing-data rules per the runner (drop/re-draw; exclude incomplete word; >15% → inconclusive).

## 8. Status

- Docs-only freeze of the judge configuration + independence rules. **No** frozen items, packets, contexts,
  runners, evidence-freeze declarations, results, or experiment numbers changed. The official run is **not**
  performed here; a B1.10 control-ext evidence-freeze declaration (naming this panel) is still required before any
  real judging, and the official contexts must first be blindly authored (§5–§6).

## 9. Guardrails
Resonance / phonetic-fidelity refinement only. No `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; no semantic-truth /
ontology / Sanskrit-privilege claim. **B1.4b′ remains `NULL_RETURN_BOTTOM`. Original B1.4b blocked. Track B blocked.
Structure, not validated meaning.**
