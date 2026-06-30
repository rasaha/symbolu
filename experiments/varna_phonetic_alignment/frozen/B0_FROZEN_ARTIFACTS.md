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

## 4. Embedding model (T_embed) — METADATA PINNED, weights UNVERIFIED (`PINNED_UNVERIFIED`)
Pre-reg §12 makes **T_embed the PRIMARY, verdict-setting encoding**. The model is now
**selected and its metadata pinned** in `b0_frozen_artifacts.json`:

| field | value |
|---|---|
| `model_id` | `sentence-transformers/all-MiniLM-L6-v2` |
| `source` | `huggingface.co` |
| `expected_dim` | 384 |
| `model_config` | mean pooling, normalize-embeddings, max_seq_length 256 |
| `library_recommended_pins` | sentence-transformers / transformers / torch / tokenizers (lock at verified freeze) |
| `weights_sha256` (gate field) | **null** |
| `file_integrity.weights` | `model.safetensors` — sha256 **null**, `UNVERIFIED` |
| `file_integrity.tokenizer` / `config` | sha256 **null**, `UNVERIFIED` |
| `revision` | **null** (pin the immutable HF commit at first download) |

**Why the hashes are null (stated plainly, no fabrication).** `huggingface.co` is
**blocked by this environment's network policy** (`CONNECT 403`; only PyPI is
allowlisted). The weights/tokenizer/config sha256 and the immutable revision **cannot be
computed or resolved here**, and **no hash is fabricated** to make the gate pass. The
entry is therefore `PINNED_UNVERIFIED` with `weights_sha256: null`.

**Gate behaviour.** `manifest.embedding_frozen()` requires `status: enabled` **and** a
non-empty `weights_sha256`. With the gate field `null`, this `PINNED_UNVERIFIED` entry
keeps the readiness gate **NOT ready** and the runner at `NOT_RUN`. (`file_integrity`
records per-file provenance for the verified freeze; the `weights` entry mirrors the gate
field.)

**To finish the freeze (in an HF-enabled environment):** download the pinned model,
compute the sha256 of `model.safetensors` / `tokenizer.json` / `config.json`, record them
(set `file_integrity.*.verification: VERIFIED`), copy the weights hash into the gate field
`weights_sha256`, set the immutable `revision`, lock the library versions, and set
`status: enabled`. Readiness then flips **solely** because T_embed is frozen (tested in
`test_manifest_loader.py::test_readiness_flips_only_because_of_tembed`).

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
1. **Verify** the **T_embed** model in an HF-enabled environment (compute + pin the
   weights/tokenizer/config sha256 with `verification: VERIFIED`, pin the revision, lock
   library versions, set `status: enabled`). Metadata is pinned; verification is blocked
   here by the network policy. *(The manifest loader + readiness gate are already wired.)*
2. Implement the alignment computation behind the now-ready gate (a **code** change; the
   runner returns `NOT_RUN` even when the gate reports ready).
3. Explicit approval to execute (the runner stays `NOT_RUN` until then).

> structure, not validated meaning.
