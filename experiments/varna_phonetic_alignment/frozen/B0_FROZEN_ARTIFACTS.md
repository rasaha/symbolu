# B0 §17 Frozen Artifacts

This directory freezes the §17 artifacts for **B0 (Varṇa–Phonetic-Feature
Alignment)**, pre-registered in `varna_lens/PREREG_VARNA_PHONETIC_ALIGNMENT.md`.

**Freeze scope:** artifacts/config/docs only. **No B0 run, no T-vs-P alignment, no
scramble/permutation/bootstrap on real matrices, no verdict.** The runner stays
`NOT_RUN`. Stage A is untouched. None of the pre-registration caveats are weakened.

## Manifest

`b0_frozen_artifacts.json` is the authoritative §17 record (sha256 of each artifact).

| artifact | id | sha256 | role |
|---|---|---|---|
| `varna_lens/lexicon_wordformation.json` | — | `0c34f443…73027` | frozen curated varṇa table (the `word_formation_reading` field) |
| `iast_ipa_map.json` | `iast_ipa_v1` | `16dc8b18…0972` | IAST→IPA segment map, 34 consonants |
| `ipa_feature_table.json` | `approved_frozen_ipa_v1` | `c1464d0b…7ef5` | **primary** phonetic-feature source P |
| `decision_rule.json` | `b0_decision_rule_v1` | (see manifest) | frozen §12 labels + gates |
| `run_manifest_schema.json` | `b0_run_manifest_schema_v1` | (see manifest) | schema a completed-run record must satisfy |
| `PREREG_VARNA_PHONETIC_ALIGNMENT.md` | — | `8309b991…d0b07` | the design this freeze pins |

(Truncated hashes above are for reading; the full values live in `b0_frozen_artifacts.json`.)

## 1. Lexicon hash
`varna_lens/lexicon_wordformation.json` is pinned by sha256. Any edit to the table
invalidates the freeze and requires a re-freeze.

## 2. IAST→IPA map (`iast_ipa_v1`)
The 34 consonant varṇas → IPA segments, under a frozen Sanskrit-phonology scheme
(retroflex ṭ-varga apical; dental t-varga laminal; palatal c-varga as palato-alveolar
affricates; śa=ʃ, ṣa=ʂ, sa=s, ha=ɦ). Two frozen rules:
- **Conjunct kṣa** = the cluster /k͡ʂ/; its feature vector is the elementwise **mean**
  of the `k` and `ʂ` vectors.
- **Inherent /a/** is **not** in the feature vector — features describe the consonant
  segment only (the constant /a/ is handled by the pre-reg §11 carrier-vowel invariance
  check), so the /a/ cannot inflate P.

## 3. Feature library — approved frozen table (not PanPhon)
Pre-reg §5 names **PanPhon** as the primary feature library. **PanPhon is uninstallable
in this environment** (`pip install panphon` fails building the `unicodecsv` wheel), so
the explicitly-permitted alternative — an **approved frozen feature table** — is used as
the **primary** P source:
- `approved_frozen_ipa_v1`: 16 standard articulatory distinctive features
  (`voi, sg, nas, cont, son, cons, appr, lat, trill, strid, delrel, lab, cor, ant,
  distr, dor`), values in {+1,−1}; kṣa = mean(k, ʂ) → {+1,0,−1}.
- All 34 feature vectors are **distinct** (no collisions); P (hamming) is symmetric,
  zero-diagonal, NaN-free (validated at freeze, no alignment computed).
- **Primary distance** = hamming (mean |Δ| per feature); **sensitivity** = cosine.

**This is a recorded source choice, not a redesign.** It does **not** change the §12
verdict logic and does **not** weaken any caveat. **PanPhon remains reserved for the
§16 independent-replication re-freeze** (IPA tables vs PanPhon), exactly as the
pre-registration anticipates.

## 4. Embedding model (T_embed) — DEFERRED, not enabled
Pre-reg §12 makes **T_embed the PRIMARY, verdict-setting encoding**. It is **not enabled
in this freeze**: the recommended model (`sentence-transformers/all-MiniLM-L6-v2`,
dim 384) is **not installable/verifiable in the current sandbox**, so its weights cannot
be sha-pinned.

**Consequence (stated plainly):** because the primary encoding is unfrozen, **B0 cannot
run to a verdict yet.** A follow-up freeze must pin the embedding model's weight sha256
and library version before any run. Until then the runner correctly returns `NOT_RUN`.
The categorical encoding (`T_cat`) remains the sensitivity arm only — it can **not**
stand in as primary (that would change §12), so it does not unblock a verdict.

## 5. Run manifest schema (`b0_run_manifest_schema_v1`)
`run_manifest_schema.json` defines what a **completed** B0 run record must contain:
design-doc hash, the loaded artifacts' hashes, feature source, `primary_T_status`
(a verdict run **requires** `enabled`), the encodings/P-distances actually run (a verdict
requires **both** of each), seeds, Ns (scramble ≥1000, permutation ≥10⁴, bootstrap
≥2000), environment, an externally-supplied UTC timestamp, and a `results` block. **It is
the schema only — no run has been performed and no values are present.**

## What is still required before B0 can run (gated on approval)
1. Freeze the **T_embed** model (weights sha256 + library version) — the primary encoding.
2. Wire the runner to load this manifest and enforce the schema (a **code** change, out
   of scope for this artifacts-only freeze).
3. Explicit approval to execute (the runner stays `NOT_RUN` until then).

> structure, not validated meaning.
