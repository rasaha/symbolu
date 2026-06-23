# Kosha Selector K1.1 — Additive Scoring + Secondary Level — PRE-REGISTRATION

> **Status: DESIGN, locked before implementation. Scope: selector logic ONLY (K1.1). NOT a quality eval
> (that is K2, separate).** Kosha stays **disabled by default**; C×R×S is **unchanged**; behavior stays
> **deterministic**; no training; no Guna/Vritti/Bhava; no runtime wiring; no consciousness claim.
> **This is still NOT a validation that Kosha improves answer quality.**

## 1. Motivation
The K1 selector is *precedence-first*: cue match → candidate level, conflicts resolved by a fixed
precedence (`VIJNANAMAYA > PRANAMAYA > MANOMAYA > ANANDAMAYA > ANNAMAYA`). This is brittle for **mixed-cue**
queries — e.g. *"I feel overwhelmed and nervous about this diagnosis"* has three MANOMAYA cues but one
VIJNANAMAYA cue (`diagnos`), and precedence makes the single reasoning cue win. The intended Kosha behavior
is "anxious user asking about a diagnosis → address the concern first, then reason carefully."

## 2. Change (K1.1): score-first, precedence-second, + secondary level
- **Additive scoring:** `score[level] = Σ cue_weight(matched cues) + hint_bonus + high_stakes_bonus`.
- **Pre-registered cue weights (frozen; not iterated against the eval set):** each matched cue = **0.30**,
  except a small declared **STRONG** set = **0.45**; `high_stakes` adds **+0.10 to VIJNANAMAYA** (caution
  bias); `user_level_hint` sets its level to **1.0** (dominates); `task_type_hint` adds **+0.50**.
- **Winner = argmax(score); precedence is the TIE-BREAKER only** (exact ties).
- **Secondary level:** the second-highest level becomes `secondary_level` iff its score **≥ 0.35**.
- **Blended modifier:** emitted when primary **≥ 0.60** and secondary **≥ 0.35**, *or* the top−second
  margin **< 0.30** with second **≥ 0.35** — addresses the primary aspect first, then brings in the
  secondary.
- **Preserved from K1:** explicit "simple / 5th grade / brief" **forces ANNAMAYA** unless high-stakes;
  high-stakes appends the cautious modifier; no-cue → ANNAMAYA default (confidence 0.4).

## 3. Output schema (stable; ONE primary level, no sixth Kosha)
```json
{ "level": "manomaya", "secondary_level": "vijnanamaya", "confidence": 0.74,
  "reason": "Emotional concern cues outweighed the diagnosis reasoning cue; reasoning support added because diagnosis is high-stakes.",
  "prompt_modifier": "Answer at a context/intent level: address the user's concern ... Then also explain the reasoning and tradeoffs carefully. Be cautious, ...",
  "features": { "scores": {...}, "matched_cues": {...}, "high_stakes": true, "source": "additive_cue" } }
```
`secondary_level` is `null` when there is no qualifying secondary. `KoshaSelection` gains
`secondary_level: Optional[KoshaLevel] = None` (last field, default-None → backward compatible).

## 4. Determinism & boundaries (unchanged)
Pure function of (query + optional hints); no randomness, no model, no hidden state. Disabled-by-default
prompt integration is **byte-for-byte unchanged** when `kosha=None`. C×R×S frame selection is untouched.

## 5. Honest status / non-claims
- **Selector-set accuracy is a SANITY CHECK, not validation.** The 10–14 item labelled set reflects the
  author's intuition about depth routing; matching it better ≠ better answers. Weights are **pre-registered
  by tier**, not tuned to maximize that set; we report whatever accuracy results and accept defensible
  misses.
- **K1.1 does NOT claim Kosha improves answer quality.** Whether frame+Kosha beats frame-only on a
  generation eval (clarity/usefulness) **without** regressing C×R×S frame correctness, rejected-domain
  avoidance, or factuality is **K2**, under its own pre-registration, run on the K1.1 selector.

## 6. Tests (added/updated)
Mixed-cue blending (emotional+diagnosis → MANOMAYA primary / VIJNANAMAYA secondary, blended modifier);
secondary populated only when ≥ threshold; single-cue routing unchanged; simple-force preserved;
high-stakes caution preserved; disabled-unchanged invariant preserved; no Guna/Vritti/Bhava; trace carries
`secondary_level`.

## 7. After K1.1
K2 = generation quality eval (four-arm: frame-only vs frame+Kosha, same validated rubric + Phase 3 audit,
hard guardrail that C×R×S metrics must not regress). Separate pre-registration; uses the K1.1 selector.
