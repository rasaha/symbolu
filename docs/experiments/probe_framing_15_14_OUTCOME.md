# §15.14 framing-stickiness probe — v1 outcome (ANNOTATION_FAILED, deferred to v2)

## Status

§0.8-binding closure of §15.14 implementation §0.X v1 on branch
`claude/sticky-framing-spec-r6U1j`.

**Outcome:** cascade verdict UNAVAILABLE.

The implementation script `scripts/probe_framing_15_14.py` ran
end-to-end through its self-test gate, stimulus + labels SHA
validation, Pass A + Pass B extraction, Pass C judge inference, and
the `ANNOTATION_FAILURE_RATE_THRESHOLD = 0.05` gate. On both judge
configurations available to the runpod hardware (single A100-80,
~48 GB workspace quota), the JSON-parse failure-rate gate fired
before the Pass D κ-gate could even be computed. The cascade verdict
was correctly NOT computed.

This is a clean §0.8 outcome. It does not modify or supersede any
§13 / §14 / §15.x verdict-of-record. §15.14 v1 closes here; cascade
computation is deferred to a v2 §0.X with judge configuration
upgrade or prompt amendment.

## §15.x ledger entry

| Phase | Mechanism | Outcome | Domain |
|---|---|---|---|
| §13.10 | Unsupervised entropy | AUC=0.661 (saturated) | Single-turn |
| §15.10 | Supervised linear (Z) | PARTIAL_SIGNAL_IN_Z | Single-turn |
| §15.11 | Layer-wise phase coherence | NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE | Single-turn |
| §15.12 | Synthesis + closure | sealed | N/A |
| §15.13 | Continuation inertia (R_inertia) | NO_MATERIAL_SIGNAL_IN_INERTIA (AUC=0.6300) | Multi-turn |
| **§15.14 v1** | **Framing-stickiness (R_framing)** | **ANNOTATION_FAILED on tested judge configurations** | **Multi-turn** |

§15.14 v1 does NOT produce a `STRONG_SIGNAL_IN_FRAMING` /
`PARTIAL_SIGNAL_IN_FRAMING` / `NO_MATERIAL_SIGNAL_IN_FRAMING` cascade
verdict. The cascade was never computed; the implementation's
ANNOTATION_FAILED gate (exit 9) fired in protocol-compliant order
on both judge configurations empirically tested.

## Empirical evidence

### Hardware envelope (runpod)

- **GPU:** single NVIDIA A100 80GB PCIe (81920 MiB VRAM)
- **Workspace quota:** ~48 GB on `/workspace` (MooseFS-mounted on `mfs#ca-mtl-3.runpod.net`)
- **Host RAM:** 944 GiB total

### Default judge: Qwen/Qwen2.5-72B-Instruct

NOT loadable on tested hardware.

- Model weights ~140 GB at bf16.
- Single 80 GB GPU is insufficient (140 GB > 80 GB).
- Workspace quota is insufficient (140 GB > ~48 GB).
- Download crashed at ~1.8 GB / 27.4 GB on multiple attempts with
  `OSError: [Errno 122] Disk quota exceeded`.

This materialized Risk #1 from §15.14 spec Chunk 6 ("LLM-judge model
availability / drift").

### Pre-A2 fallback judge: Qwen/Qwen2.5-7B-Instruct

Loaded successfully on the A100-80. Pass C ran over 650 evaluation
rows.

| Quantity | Value |
|---|---|
| `judge_fallback_used` | `true` |
| `json_parse_failure_rate` | `0.2692` |
| `ANNOTATION_FAILURE_RATE_THRESHOLD` (inclusive) | `0.05` |
| Pass D κ-gate | not reached (Pass C gate fired first) |
| Cascade computation | not reached |
| Script exit code | 9 (ANNOTATION_FAILED) |

### Post-A2 fallback judge: meta-llama/Llama-3.1-8B-Instruct

(Effective under §15.14-A2.) Loaded successfully on the A100-80.
Pass C ran over 650 evaluation rows.

| Quantity | Value |
|---|---|
| `judge_fallback_used` | `true` |
| `json_parse_failure_rate` | `0.7077` |
| `ANNOTATION_FAILURE_RATE_THRESHOLD` (inclusive) | `0.05` |
| Pass D κ-gate | not reached (Pass C gate fired first) |
| Cascade computation | not reached |
| Script exit code | 9 (ANNOTATION_FAILED) |

### Empirical conclusion (§15.14 v1)

At the 7-8B parameter scale, neither tested judge family (Qwen-2.5
nor Llama-3.1) reliably produces the pinned JSON output for the
§15.14 judge prompt at the 5% failure-rate gate threshold. The
prompt-text and small-scale-instruction-tuning interaction is the
binding constraint at this scale.

Both gates fired in the protocol-compliant order documented in §15.14
spec Chunk 5. The cascade is not computable on tested judge
configurations.

## Artifacts preserved (intact on this branch)

| Path | Size | State |
|---|---|---|
| `docs/experiments/sticky_framing_15_14_stimuli.json` | ~1.2 MB | LOCKED — SHA `e56cfe8c102f0520fd26b906bdd08377c243ac45bd9fbf80956006dddd1957c7` |
| `docs/experiments/sticky_framing_15_14_calibration_labels.json` | ~50 KB | LOCKED — SHA `e9776ff223ef913b2e404d2cf90203e9615c01640bc8fc5c42ffabf2d49b0d6c`; 50/50 human-annotated by `rasaha-2026-04-30` |
| `docs/experiments/sticky_framing_15_14_calibration_responses.json` | ~720 KB | committed; 50/50 Qwen-7B subject responses (runpod `47fe791df9a7`) |
| `docs/experiments/framing_15_14_extractions.npz` | ~18 MB | INTACT — 130 chains × 5 turns of `s_t`, `q_t`, `a_prev`, `f_1`, `r_t_response` |
| `docs/experiments/sticky_framing_15_14_annotation_review.md` | ~44 KB | preserved |
| `scripts/probe_framing_15_14.py` | ~3378 lines | end-to-end runnable; gates correctly enforced |
| `scripts/curate_framing_15_14_stimuli.py` | preserved | reproducible curation generator |
| `scripts/validate_framing_15_14_stimuli.py` | preserved | strict-mode validator |

**Key preservation:** the extraction cache `.npz` is the expensive
artifact (130 chains × K=6 multi-turn forward passes). Any future v2
§0.X that obtains a working judge configuration can run
`python3 scripts/probe_framing_15_14.py --force-annotate` and reach
the cascade in ~1–2 hours without re-running Pass A + Pass B. The
multi-turn extraction work is not lost.

## Spec amendments that landed during §15.14 v1

| Amendment | Status | Scope | Sign-off commit |
|---|---|---|---|
| §15.14-A1 | EFFECTIVE | Allow `synthetic_frame_positive_v1` source enum value, restricted to `frame_positive_chains` only | `8ba407f` |
| §15.14-A2 | EFFECTIVE | Replace `JUDGE_MODEL_ID_FALLBACK`: `Qwen/Qwen2.5-7B-Instruct` → `meta-llama/Llama-3.1-8B-Instruct` | `34912e3` |

Both amendments stand and are §0.8-binding. Both were narrowly scoped
and disclosed up front. Neither modified any sealed threshold
(severity rubric, `BINARY_LABEL_THRESHOLD`, `KAPPA_GATE_THRESHOLD`,
`DIRECTION_GATE_THRESHOLD`, `PARTIAL_AUC_THRESHOLD`,
`STRONG_AUC_THRESHOLD`, `STRONG_DELTA_AUC_THRESHOLD`,
`ANNOTATION_FAILURE_RATE_THRESHOLD`), the cascade structure, the
52-pattern Class-3 firewall, the frozen judge prompt, or any
§13 / §14 / §15.x verdict-of-record.

## v2 candidate paths (each requires a fresh §0.X commitment)

None are authorized by this document. Each below is an open research
direction for a future top-level §0.X.

| Candidate | Approach | Most likely to address |
|---|---|---|
| v2-Y | Provision a 2× 80GB-GPU runpod with ≥200 GB workspace; run with the default `Qwen/Qwen2.5-72B-Instruct` judge | Both gate failures; spec-compliant default path |
| v2-V | New §15.14-A3 amendment softening the JSON requirement (e.g., add few-shot examples; or trailing "OUTPUT EXACTLY THIS JSON FORMAT" instruction) | The JSON-parse rate at 7-8B scale |
| v2-U | New §15.14-A3 amendment changing the judge prompt to a single-digit response (0/1/2) instead of JSON | The JSON-parse rate decisively; loses the rationale field |
| v2-W | New §15.14-A3 amendment trying a different 7-8B judge family (Mistral-7B, Phi-3, etc.) | Empirical question about small-scale instruction-tuning differences |
| v2-T | New §0.X applying §15.14 to a different subject model (Llama-3-8B subject + Qwen-72B judge) | Cross-model generalization of the framing-stickiness hypothesis |

Whichever v2 path is pursued, the corresponding §0.X must:

- Re-validate the locked stimulus + labels SHAs at start.
- Pin the judge configuration in its commit metadata.
- Preserve all §13/§14/§15.x verdicts-of-record (including this
  v1 closure outcome).
- NOT modify the cascade structure, the 52-firewall, or any sealed
  §0.8 threshold inherited from §15.14 v1.

## What was learned (independent of any cascade verdict)

Two findings stand on their own from §15.14 v1 even without a cascade
verdict:

1. **Bimodal severity distribution at the human level.** The
   calibration annotation pass (50 rows, single annotator
   `rasaha-2026-04-30`) produced severity counts of:
   - `0 (IGNORED)`: 28 rows (56%)
   - `1 (MENTIONED)`: 1 row (2%)
   - `2 (STRUCTURED)`: 21 rows (42%)

   Qwen-7B-Instruct's behavior on this stimulus set is bimodal at
   the human level: it either fully ignores the framing convention
   on the post-framing question or fully embraces it, with very
   little middle ground. This observation is independent of any
   geometric prediction by R_framing.

2. **Small-scale judge JSON-format reliability is the binding
   constraint at this protocol scale.** Two different 7-8B-class
   instruction-tuned models (Qwen-2.5-7B and Llama-3.1-8B) both
   failed the 5% JSON-parse gate on the §15.14 judge prompt, with
   strikingly different rates (27% vs 71%). This is a real
   empirical finding about LLM-as-judge reliability at this scale
   and prompt complexity.

Neither finding requires the cascade verdict to be informative.

## Audit-trail integrity (§0.8-binding)

§13.9 hold preserved. §6.1 N=21 autonomy result preserved.
§15.10 PARTIAL_SIGNAL_IN_Z preserved. §15.11
NO_MATERIAL_SIGNAL_IN_PHASE_COHERENCE preserved. §15.12 closure
preserved. §15.13 NO_MATERIAL_SIGNAL_IN_INERTIA preserved.

§15.14 v1 closes with `ANNOTATION_FAILED on tested judge
configurations`. The cascade rule is mechanical; we did not compute
a verdict, and we are not asserting one. The framing-stickiness
hypothesis (whether residual-stream geometry foretells inappropriate
framing recurrence at later turns of a multi-turn chat) remains
untested at the 7-8B-judge scale on this hardware envelope.

## Branch state advance

```
PENDING_LLAMA_FALLBACK_ANNOTATION_RESULT
            ↓ (run completed; gate fired at 0.7077 > 0.05)
ANNOTATION_FAILED_ON_LLAMA_3_1_8B_FALLBACK
            ↓ (user election of Path Z; this commit)
§15_14_V1_CLOSED_AS_ANNOTATION_FAILED_ON_TESTED_JUDGES_DEFERRED_TO_V2
```

## Provenance

- §15.14 spec sealed at: `docs/design/15_14_STICKY_FRAMING_DESIGN_SPEC.md`
- §15.14-A1 (synthetic_frame_positive_v1) EFFECTIVE: commit `8ba407f`
- §15.14-A2 (Llama-3.1-8B fallback) EFFECTIVE: commit `34912e3`
- Implementation §0.X authorization: commit `de2b504`
- Implementation chunks I-1..I-5: commits `834fcf5` through `80fccff`
- `.npz` writer bugfix: commit `9842fbae`
- Calibration responses: commit `fd610995` (Qwen-7B subject; runpod `47fe791df9a7`)
- Calibration labels: commit `4ba0c27d` (annotator `rasaha-2026-04-30`)
- Pre-A2 Qwen-7B fallback run: `json_parse_failure_rate = 0.2692`, exit 9
- Post-A2 Llama-3.1-8B fallback run: `json_parse_failure_rate = 0.7077`, exit 9
- Both runs: ANNOTATION_FAILED before cascade; no JSON / MD output written.

## End of §15.14 v1
