# Static CSR = Context × Semantic × Resonance — RESULT (filled)

> Closeout of the static CSR probe (`docs/STL_CSR_REFACTOR_PLAN.md`). Numbers from
> `runs/bhava_probe/20260621T020740Z_csr/`. Representation/probe track; generation path already parked.

## Setup (confirmed available)
Active-CG checkpoint contained the trained token-scorer Context (`conscious_gen.token_cache._csr_scorer.context_proj`) + `R_tok`. Sanskrit Varna pipeline loaded (46 varṇas, affinity table for 32,768 tokens, 80.6 % Sanskrit-mapped, CMUdict + g2p_en). All CSR components extracted (none faked).

## correctness (n=170; pos=49, neg=121)

| Feature | AUROC | CI | decodable |
|---------|------:|----|:---------:|
| **resonance_combined** | **0.832** | [0.755, 0.903] | yes (single best) |
| state_32d | 0.828 | [0.745, 0.902] | yes |
| state_bhava | 0.818 | [0.736, 0.892] | yes |
| phoneme_bhava / vritti_consonant† | 0.813 | [0.734, 0.886] | yes |
| semantic (input emb.) | 0.783 | [0.701, 0.856] | yes |
| **hidden_only** | 0.777 | [0.690, 0.861] | yes |
| context_r_ctx | 0.738 | [0.641, 0.822] | yes |
| **csr_static (C+S+R)** | 0.778 | [0.697, 0.853] | yes (≤ resonance alone) |
| hidden_plus_csr | 0.736 | [0.650, 0.815] | yes (< hidden) |
| hidden_plus_state_bhava_plus_csr | 0.790 | [0.716, 0.859] | yes (≈ hidden, ns) |

† phoneme_bhava and vritti_consonant came out **identical** — likely a degenerate vowel/consonant
split in extraction. `resonance_combined` (independent varna affinity) is the authoritative Resonance
feature; the split rows are not over-read.

CSR decision answers: state_bhava decodable ✔, resonance ✔, context ✔, semantic ✔;
**CSR beats its parts: �’No’**, CSR adds to state_bhava: No, hidden+state_bhava+CSR beats hidden: No.

## DECISION: `CSR_REDUNDANT` → **PARK_CSR**

Every part decodes correctness, but the **combination adds nothing** over the best part, and **CSR
adds nothing over hidden** (`hidden+csr` 0.736 < hidden 0.777; full 0.790 ≈ hidden, ns). No
complementary signal → park.

### Honest interpretation
- **Resonance decodes correctness (0.832, even best)** — but it is **text-derived**, so this is the
  Sanskrit-phoneme statistics tracking **problem difficulty** (a surface confound), not the phoneme
  structure carrying meaning. The decisive test (adds over hidden) **fails**: the hidden state already
  captures the difficulty signal. This is exactly the redundancy the probe was built to detect.
- The C × S × R decomposition is **redundant**: parts are individually decodable (all correlate with
  difficulty) but carry no joint signal beyond hidden.

## CG / STL / CSR track — combined verdict: **PARK** (all questions negative)

| Question | Result |
|----------|--------|
| Wrapper improves generation? | `ACTIVE_NO_EFFECT` (B≈C, ΔBhava=0) — parked |
| state-Bhava unique signal? | `BHAVA_WEAK_SIGNAL` — decodable but redundant with hidden |
| CSR = Context×Semantic×Resonance complementary? | `CSR_REDUNDANT` — parts decode, combination redundant with hidden |

## Known limitations / what could still be explored (separate, pre-registered)
- Resonance's apparent signal is a text-difficulty confound; a cleaner test would control for prompt
  length/surface statistics, but the redundancy-with-hidden result already settles "no complementary
  signal."
- The phoneme/vritti split was degenerate — fix only matters if the vowel-vs-consonant breakdown is of
  independent interest; it does not affect the verdict.
- STL (Signal→Transformation→Laya, temporal) remains deferred and untested.
- Probe = correlation; generation path parked, so nothing here revives the wrapper.
