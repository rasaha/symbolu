# B1.3 v3-Authoritative — Portable Multi-Family Judge Execution Plan

**Docs only.** No EVIDENCE_FREEZE · no run · no scoring · no model call · no v3-stimulus / threshold / scorer /
lexicon edit · v2 not overwritten. Freeze status unchanged:
`FREEZE_REVIEW_V3_AUTHORITATIVE_READY_AWAITING_OPERATOR_CONFIRMATION`. **Structure, not validated meaning.**

## 1. Current blocker

The B1.3 v3-authoritative study is **artifact-ready but judge-instrument-blocked.** All inputs are done and
hash-bound: authoritative-sourced bridge pool, 371 v3 stimuli (53 objects × 7 comparisons), source/provenance
audit PASS, mechanical audits PASS, frozen scorer + tests, thresholds, judge prompt. What is missing is a
**stable, credentialed, format-compliant judge instrument.** The capability probe returned
`NOT_READY_NO_STABLE_JUDGE`: no scriptable provider API key in this runtime; Anthropic reachable only via
harness OAuth (not scriptable); the single invokable path (a generator-adjacent Claude subagent) refused the
synthetic forced-choice format; OpenAI/Mistral unreachable; Google 403. So the run must be performed in an
**external environment with proper judge access.** This plan makes that portable.

## 2. Minimum judge requirements

- **≥ 2 model families / vendors** where possible (the design's no-single-family-dominance guard needs this).
- **Exact model IDs pinned** (provider + model identifier + version/date stamp) and recorded in the frozen run
  log.
- **JSON / forced-choice compliance verified** by a synthetic probe **before** freeze (refusal/malformed rate
  under the invalid cap).
- **Stable credentialed access** (keys present, endpoints reachable, rate limits known).
- **No generator-adjacent subagent judging** (same family as the session) **unless explicitly downgraded** to a
  single-family pilot with a documented weak-blinding caveat.

## 3. Recommended judge panel (configuration guidance only — not a run)

Any of these satisfy the ≥2-family goal; pick by what has stable credentials in the external environment:
- **local open-weight (Mistral / Llama / Qwen) + one hosted family (OpenAI or Gemini)** — good portability,
  cross-vendor.
- **OpenAI + Gemini** — two hosted vendors.
- **OpenAI + Gemini + Claude** — three families, if all creds exist (strongest for the dominance guard).
- **Mistral/local + OpenAI** or **Mistral/local + Gemini** — one local + one hosted.

Prefer at least one **non-Claude** family so the judge is not generator-adjacent. A single-Claude panel is
allowed **only** under the explicit single-family-pilot downgrade (§7).

## 4. Pre-freeze compliance probe (synthetic only)

Before freeze, run a small **synthetic** probe per pinned model (never real B1.3 items — use throwaway "widget"
A/B prompts in the exact judge format):
- **forced-choice JSON/letter compliance** (does it emit `A`/`B` + optional confidence?);
- **refusal rate** and **malformed rate** (must be below the invalid cap, draft 10%);
- **latency / rate-limit** behavior;
- **exact model ID** captured (as returned by the provider);
- **provider / family** captured.
A model that fails compliance is **excluded** from the panel (not coerced).

## 5. Freeze declaration prerequisites

Declare EVIDENCE_FREEZE **only after all** of:
1. **exact model IDs known** and recorded;
2. **compliance probe passed** for each panel model;
3. **provider/family panel selected** (≥2 families, or explicit single-family-pilot downgrade);
4. **artifact hash manifest confirmed unchanged** (re-hash the 16 active v3 artifacts vs
   `…freeze_review_manifest_v3_authoritative.json`; any mismatch blocks freeze).
Freeze is an **explicit operator declaration** — never automatic, never by the runner.

## 6. Portable runner requirements (specification — not implemented here)

A portable runner (external environment) must accept / provide:
- **model config file** (see `b1_3_v3_judge_runner_config_template.json`): panel of {provider, model_id,
  api_key_env, base_url?, temperature, max_tokens};
- **API keys from environment** (never hard-coded; read by `api_key_env` name);
- **local model option** (e.g. an OpenAI-compatible local server / Ollama endpoint via `base_url`);
- **retry policy** (≤2 retries on transport/empty only; **no prompt change on retry**);
- **JSON repair/reject policy** (parse `A`/`B`; if unparseable after retries → `parse_status` set,
  `invalid_flag=true`; **never hand-repair** a substantive answer);
- **refusal handling** (refusal → `parse_status=refused`, `invalid_flag=true`; counted, never coerced);
- **blinding** (build judge-facing packets from the v3 stimuli using **only** `target_word`,
  `dictionary_anchor`, `neutral_context`, `option_left`, `option_right`, `question`; **never** send
  `arm_left`/`arm_right`/`source_metadata`);
- **output artifact paths** (judge-output JSONL + score report JSON/MD).

**Judge-output JSONL schema** (what the existing frozen scorer `score_b1_3_concrete_object_llm.py` consumes):
`item_id · comparison_id · target_word · primary_or_secondary_or_diagnostic · object_family · model_id ·
arm_left · arm_right · deranged_stratum · selected_option (A|B) · confidence? · parse_status · invalid_flag`.
The runner copies `arm_left`/`arm_right` from the stimulus (for scoring) but never exposes them to the model.

## 7. Run modes

- **probe-only** — synthetic compliance probe per model; no real items; no freeze.
- **freeze-check** — re-hash the 16 active artifacts vs the manifest; confirm unchanged; report ready/blocked;
  no scoring.
- **score-frozen** — after freeze: build blinded packets, call the pinned panel over the 371 comparisons,
  write judge-output JSONL, run the frozen scorer → terminal label. **Only mode that produces the result.**
- **single-family-pilot** — explicitly downgraded: one family, run + scored, **result reported as a pilot with
  a weak-blinding / single-family caveat**; cannot earn `…SIGNAL_EARNED_STRONG` framing without the dominance
  caveat.
- **multi-family-evidence-run** — ≥2 families; the intended evidence mode.

## 8. Invalid-run conditions

The run is `LLM_OBJECT_MODULATION_INVALID_RUN` (or blocked) if any:
- **missing exact model IDs** (panel not pinned);
- **high refusal / malformed rate** (> invalid cap, draft 10%);
- **single-family dominance** when **not** explicitly downgraded to a pilot;
- **artifacts changed after freeze** (hash mismatch);
- **threshold or scorer edits after freeze**.
These are pre-declared; the scorer already enforces the invalid-rate cap and single-family-dominance guard.

## 9. Operator command templates (placeholders — DO NOT EXECUTE here)

```bash
# 0. external env: export credentials (names only; values from your secret store)
export OPENAI_API_KEY=...        # if using OpenAI
export GOOGLE_API_KEY=...        # if using Gemini
export MISTRAL_API_KEY=...       # if using Mistral
# (local model: run an OpenAI-compatible server and set base_url in the config)

# 1. probe-only (synthetic compliance; no real items, no freeze)
python3 run_b1_3_v3_judges.py --mode probe-only \
    --config b1_3_v3_judge_runner_config_template.json \
    --out ./probe_out/

# 2. freeze-check (re-hash artifacts vs manifest; no scoring)
python3 run_b1_3_v3_judges.py --mode freeze-check \
    --manifest b1_3_concrete_object_llm_freeze_review_manifest_v3_authoritative.json

# 3. (OPERATOR) declare EVIDENCE_FREEZE explicitly, pinning the probed model IDs — a human step, not a command.

# 4. score-frozen (multi-family evidence run) — ONLY after freeze
python3 run_b1_3_v3_judges.py --mode multi-family-evidence-run \
    --config <frozen_pinned_config>.json \
    --stimuli b1_3_concrete_object_final_stimuli_draft_v3_authoritative.jsonl \
    --judge-out ./run_out/judge_outputs.jsonl
python3 score_b1_3_concrete_object_llm.py \
    --stimuli b1_3_concrete_object_final_stimuli_draft_v3_authoritative.jsonl \
    --judge-outputs ./run_out/judge_outputs.jsonl \
    --style-audit b1_3_concrete_object_style_audit_report_v3_authoritative.json \
    --contract b1_3_concrete_object_llm_scoring_contract_v2.json \
    --out-json ./run_out/score_report.json --out-md ./run_out/score_report.md
```

(`run_b1_3_v3_judges.py` is the **portable runner to be implemented in the external environment** per §6; it is
**not** created or executed here. The scorer `score_b1_3_concrete_object_llm.py` already exists and is frozen.)

## 10. Boundary statement

**B1.3 v3-authoritative remains artifact-ready but judge-instrument-blocked. No evidence freeze declared.
Nothing run or scored. Track B remains blocked. Structure, not validated meaning.**
