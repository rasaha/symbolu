# Guna/Vritti Human Labeling — PRE-REGISTRATION + Rater Protocol (doc-only)

> **Status: DESIGN ONLY, doc-only.** Defines how to collect **human** Guna/Vritti labels that can survive
> the anti-circularity guardrail — the only path to a real `LEARNS_SIGNAL`. No training; no GPU; no runtime
> change; **no Sanskrit/jargon shown to raters**; Bhava NOT labelled; **Kosha NOT labelled here**
> (deferred — depth is already deterministically operationalized and surface-confounded). Builds on
> `docs/CG_GUNA_VRITTI_LABEL_SOURCE_PREREG.md` (the usability gates) and reuses the de-biasing discipline
> of the supervised-observation packet.

## 1. Why human labels (and why de-biased)
Weak heuristic labels are surface-derivable → a probe on them is `SURFACE_CONFOUNDED` (proven by our own
guardrail). The only labels that can show a non-trivial hidden-state finding are **human interpretive
judgments that beat the surface baseline.** To keep them honest, raters judge **observable response
qualities in plain language** and never see the Guna/Vritti constructs (so they can't "label the theory").
The analyst maps observable labels → Guna/Vritti **after the fact**.

## 2. What raters see / never see
**See:** an opaque `item_id`, the `prompt`, the `response`, and the rater instructions (§5). Nothing else.
**Never see (asserted by the exporter):** the words Guna/Vritti/Sattva/Rajas/Tamas/Pramana/Viparyaya/
Vikalpa/Nidra/Smriti/Kosha/Bhava; any weak/auto label; label source; model identity; hidden states; the
"correct" answer key; whether another rater agreed.

## 3. Observable label schema (rater-facing — NO jargon)
```json
{ "item_id": "opaque", "prompt": "...", "response": "...",
  "human_labels": {
    "response_kind": null,            // ONE of: grounded_factual | factually_wrong |
                                      //         speculative_imaginative | evasive_nonanswer | recall_of_context
    "clear_and_lucid": null,          // yes/no
    "energetic_actionable": null,     // yes/no
    "dull_confusing_lowsignal": null, // yes/no
    "clarity_1to5": null,             // 1..5
    "short_reason": null }            // optional, ≤1 sentence
}
```

## 4. Analyst-side mapping (NEVER shown to raters)
| observable label | construct |
|---|---|
| `response_kind = grounded_factual` | Vritti **pramana** |
| `response_kind = factually_wrong` | Vritti **viparyaya** |
| `response_kind = speculative_imaginative` | Vritti **vikalpa** |
| `response_kind = evasive_nonanswer` | Vritti **nidra** |
| `response_kind = recall_of_context` | Vritti **smriti** |
| `clear_and_lucid = yes` | Guna **sattva** = 1 |
| `energetic_actionable = yes` | Guna **rajas** = 1 |
| `dull_confusing_lowsignal = yes` | Guna **tamas** = 1 |
Guna dims 4–6 remain `null` (underdefined; not labelled).

## 5. Rater instructions (plain language — handed to raters)
> You will read a **question** and one **answer**. Judge **the answer**.
> 1. **What kind of answer is it?** Pick one:
>    - *grounded & factual* — gives correct, real information;
>    - *factually wrong* — states something false/incorrect (use your knowledge; if a reference is shown,
>      use it);
>    - *speculative / imaginative* — hypothetical, fictional, or made-up;
>    - *evasive / non-answer* — refuses, is empty, or dodges ("I don't know");
>    - *recall of context* — mainly repeats/quotes something from earlier in the conversation or given facts.
> 2. **Clear and lucid?** yes/no — is it well-organized and easy to follow?
> 3. **Energetic / actionable?** yes/no — does it give active steps/next-actions or drive toward doing?
> 4. **Dull / confusing / low-signal?** yes/no — is it vague, padded, heavy, or hard to use?
> 5. **Clarity 1–5** and an optional one-line reason.
> Judge what's there; don't guess the system's intent. There are no "right" categories to discover.

- **Two independent raters** where possible; do not discuss during labeling.
- For the `factually_wrong` call, raters use general knowledge or a **reference** if provided; if they
  genuinely can't tell, they pick the closest other category and note it.

## 6. Leakage / circularity controls (still binding)
1. Labels come from **prompt + response (+ optional reference) ONLY** — never hidden states.
2. **The surface-feature baseline still applies:** even human labels must let the hidden-state probe
   **beat surface features** (`surface_baseline.py`). Any human label that is itself ≥0.85 surface-AUROC is
   `SURFACE_CONFOUNDED` and cannot support a deep claim (e.g. "evasive" ≈ short/refusal words may be
   surface-confounded; "factually_wrong" is the most likely to be *non*-surface, hence most valuable).
3. Raters never see weak/auto labels, the answer key, or each other's labels.
4. Grouped train/test split by source item; balanced prevalence enforced.

## 7. Agreement & usability gates (from the label-source pre-reg §8–9)
- **Cohen/Fleiss κ** on `response_kind` and each yes/no Guna flag; **Spearman** on `clarity_1to5`.
- Usable for a `LEARNS_SIGNAL`-eligible probe only if **`LABELS_USABLE_HUMAN`**: κ ≥ 0.60 on
  `response_kind`, ≥ 0.50 per Guna flag; non-degenerate prevalence (≥ ~8 per class/flag); **and ≥1 label is
  NOT surface-confounded** (so a hidden-state win over surface is possible).
- Else → `LABELS_LOW_AGREEMENT` / `LABELS_DEGENERATE_PREVALENCE` / `LABELS_SURFACE_CONFOUNDED`, which cap
  the probe at `SYNTHETIC_ONLY`/confounded-caution. No post-hoc tuning.

## 8. Sample size & source items
- **Items:** ≥ ~120 (prefer 200+), each a real prompt+response pair (e.g. from `robustness_eval_v2.json`
  answers or the K2 generations), balanced so each `response_kind` and each Guna flag has ≥ ~8 positives.
- **Dual-rate** ≥ ~60-item overlap for κ. Adjudication rule fixed before labeling (majority / named
  tie-breaker).
- Provide a **reference / ground-truth** field for items where factuality is checkable (gates the
  `factually_wrong` call).

## 9. Packet artifacts (exporter)
`export_guna_vritti_label_packet.py` emits (mirroring the supervised-observation pattern):
- `guna_vritti_label_packet.jsonl` — rater-facing rows (de-biased; assert no forbidden fields);
- `guna_vritti_labels_template.csv` — `item_id` + label columns;
- `guna_vritti_private_keymap.json` — **analyst-only** (opaque_id → source_id, any weak label kept for
  later concordance, never given to raters).

## 10. How labels feed the probe
Filled labels → analyst mapping (§4) → `labels.guna`/`labels.vritti` with `label_meta.source = human`
(or `adjudicated`) → harness probe. A `LEARNS_SIGNAL` is reportable **only if** labels are
`LABELS_USABLE_HUMAN` **and** the probe beats the surface baseline by ≥0.05 on a non-confounded label.

## 11. Boundaries / current claim
*Human Guna/Vritti labeling is pre-registered with a de-biased, jargon-free rater packet and the same
leakage/agreement/surface-baseline gates as the rest of the track. No labels have been collected; no
training has been run; no Guna/Vritti cognitive-state claim is made. Bhava and Kosha are not labelled.*
