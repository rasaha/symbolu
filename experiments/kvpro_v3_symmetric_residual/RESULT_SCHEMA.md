# KVPro V3 Gate-1 — result schema

All results are JSON; the gate also emits a CSV. Every top-level result carries a `label`
(`MEASURED` | `NOT_A_VERDICT_SYNTHETIC`) or, for missing inputs, is simply absent (treated as NOT RUN).

## `reconstruction_metrics.json`
```jsonc
{
  "source": "capture:/path.pt" | "synthetic-fixture",
  "label":  "MEASURED" | "NOT_A_VERDICT_SYNTHETIC",
  "summary": { "<cand>": { "K_cos_min", "V_cos_min", "K_unprot_cos_min",
                           "K_mse_max", "V_mse_max" } },   // cand in affine,S1,S2,S3,S4
  "per_layer": [ { "layer": <int>, "<cand>": { "K_mse","K_cos","K_maxabs","K_head_cos_min",
                   "K_prot_mse","K_unprot_mse","K_unprot_cos","V_mse","V_cos", ... } } ]
}
```

## `attention_error_metrics.json`  (the decisive offline signal)
```jsonc
{
  "source", "label",
  "summary": { "<cand>": { "attn_out_cos_min", "attn_out_mse_max",
                           "attn_out_mse_vs_affine_max",     // ratio vs the accepted affine baseline
                           "softmax_kl_mean_max", "softmax_kl_max_max" } },
  "per_layer": [ { "layer", "<cand>": { "logit_mse","logit_maxabs","softmax_kl_mean","softmax_kl_max",
                   "softmax_js_mean","attn_out_mse","attn_out_cos","attn_out_maxabs",
                   "attn_out_mse_vs_affine", ... } } ]
}
```

## `e2e_quality.json`  (pod fake-quant; keys present only if that metric ran)
```jsonc
{
  "<cell>": { "ppl": <float>, "token_agree": <pct vs fp>,      // cell in fp,affine,S1,S2,S3,S4
              "hard_needle"?: <0..1>, "mmlu"?: <pct> },
  "_meta": { "model", "label": "MEASURED", "note" }
}
```

## `verdict.json`
```jsonc
{
  "verdict": "GO_KERNEL_PROTOTYPE" | "GO_WITH_MODIFICATION" | "NO_GO_QUALITY"
           | "NO_GO_SYSTEMS_VALUE" | "INCONCLUSIVE",
  "per_candidate": { "<cand>": {
      "quality_offline": true|false|null,   // null = NOT RUN / synthetic
      "quality_offline_reasons": [ ... ],
      "quality_e2e": true|false|null,
      "quality_e2e_reasons": [ ... ],
      "systems_pass": true|false,
      "systems_reason": "…% read-bw reduction …",
      "pct_reduction": <float> } },
  "thresholds": { "TH_ATTN_OUT_COS_MIN": 0.999, "TH_ATTN_OUT_MSE_VS_AFFINE_MAX": 1.25,
                  "TH_SOFTMAX_KL_MAX": 0.02, "TH_SYSTEMS_PCT": 5.0, ... },
  "inputs_present": { "recon", "attn", "e2e", "attn_is_synthetic" }
}
```

## `verdict_summary.csv`
```
candidate,quality_offline,quality_e2e,systems_pass,pct_reduction
S1,true,true,true,9.3
...
# VERDICT,GO_KERNEL_PROTOTYPE,,,
```

## Verdict semantics
- **GO_KERNEL_PROTOTYPE** — S1 or S2 passes quality (offline proxy **and** end-to-end) **and** clears the ≥5% systems floor.
- **GO_WITH_MODIFICATION** — only K (S4) or only V (S3) passes quality → pursue an **asymmetric** format, not one universal representation. (Note the systems value of a single-xmin drop is ~4.65%, below the floor — the CSV shows it.)
- **NO_GO_QUALITY** — every candidate fails the quality gate (report plainly).
- **NO_GO_SYSTEMS_VALUE** — quality is fine but the read-bandwidth reduction is <5% → keep affine INT4, spend effort on in-kernel gather / store-as-consumed instead.
- **INCONCLUSIVE** — required signals not yet run (e.g., synthetic-only, or end-to-end NOT RUN on a pod).
