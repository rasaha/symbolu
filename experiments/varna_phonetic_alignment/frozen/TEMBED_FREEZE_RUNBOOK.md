# Runbook — Verified T_embed Freeze (HF-enabled environment)

**Purpose:** complete the `PINNED_UNVERIFIED` → verified freeze of the §12 primary
encoding (`sentence-transformers/all-MiniLM-L6-v2`), so the readiness gate flips
**solely** because T_embed is now frozen.

**Scope:** freeze only. Do **not** implement alignment, run B0, compute any result, or
touch Stage A. Run every step in an environment where `huggingface.co` is reachable.

> Why this runbook exists: in the current sandbox `huggingface.co` is blocked by the
> network policy (`CONNECT 403`; only PyPI is allowlisted), so the model weights cannot
> be downloaded or hashed here. The blocker is environmental, not scientific — the fix is
> to verify the model in an HF-enabled environment, not to weaken the estimand.

## 0. Preconditions
- `huggingface.co` reachable; `pip` available.
- Clean checkout of branch `claude/symbolu-adversarial-eval-zevb4h`.
- Confirm the five pinned artifacts already verify before you start:
  ```bash
  python3 -c "import sys; sys.path.insert(0,'experiments/varna_phonetic_alignment'); \
  import manifest as MF; print(MF.verify_hashes(MF.load_manifest())['ok'])"   # expect: True
  ```

## 1. Exact model identity
- `model_id`: **`sentence-transformers/all-MiniLM-L6-v2`** (do not substitute).
- `expected_dim`: **384**; `model_config`: mean pooling, normalize-embeddings,
  `max_seq_length` 256.

## 2. Pin the immutable revision
Resolve the current `main` commit and pin it (never leave `revision: null` or `"main"`):
```bash
git ls-remote https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2 refs/heads/main
# -> <COMMIT_SHA>   (this is the value for manifest "revision")
```
Download exactly that revision into a local dir:
```bash
pip install -U "huggingface_hub[cli]"
huggingface-cli download sentence-transformers/all-MiniLM-L6-v2 \
  --revision <COMMIT_SHA> --local-dir ./_tembed_snapshot
```

## 3. Files to hash
Determinism-relevant set (matches the manifest's `file_integrity` slots):
- `model.safetensors`  ← **the gate field** (`weights_sha256`)
- `tokenizer.json`
- `config.json`
- `sentence_bert_config.json`

(Optional, for full provenance: `tokenizer_config.json`, `vocab.txt`,
`special_tokens_map.json`, `modules.json`, `1_Pooling/config.json`.)

## 4. Commands to compute sha256
```bash
cd _tembed_snapshot
sha256sum model.safetensors tokenizer.json config.json sentence_bert_config.json
# portable fallback:
python3 - <<'PY'
import hashlib, pathlib
for f in ["model.safetensors","tokenizer.json","config.json","sentence_bert_config.json"]:
    p = pathlib.Path(f)
    print(f, hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else "MISSING")
PY
```
Also capture the exact library versions (embedding output can drift across versions):
```bash
python3 -c "import sentence_transformers,transformers,torch,tokenizers,platform as p; \
print('python',p.python_version()); \
print('sentence-transformers',sentence_transformers.__version__); \
print('transformers',transformers.__version__); \
print('torch',torch.__version__); print('tokenizers',tokenizers.__version__)"
```

## 5. Fields to fill in `b0_frozen_artifacts.json` → `embedding_model_T_embed`
| field | from `PINNED_UNVERIFIED` | to verified |
|---|---|---|
| `status` | `"PINNED_UNVERIFIED"` | `"enabled"` |
| `enabled` | `false` | `true` |
| `weights_sha256` (gate field) | `null` | `<sha256 of model.safetensors>` |
| `revision` | `null` | `<COMMIT_SHA>` |
| `file_integrity.weights.sha256` / `.verification` | `null` / `UNVERIFIED` | `<hash>` / `VERIFIED` |
| `file_integrity.tokenizer.*` | `null` / `UNVERIFIED` | `<hash>` / `VERIFIED` |
| `file_integrity.config.*` | `null` / `UNVERIFIED` | `<hash>` / `VERIFIED` |
| `file_integrity.sentence_bert_config.*` | `null` / `UNVERIFIED` | `<hash>` / `VERIFIED` |
| `library_recommended_pins` | ranges | replace with **exact** locked versions (add `python`) |

Leave `model_id`, `source`, `expected_dim`, `model_config`, `selection_rationale` as-is
(confirm `model_config` matches the downloaded `config.json` / `1_Pooling/config.json`).

## 6. How to update the manifest
Edit only the `embedding_model_T_embed` block (a small script is cleaner than hand-editing):
```bash
python3 - <<'PY'
import json, pathlib
p = pathlib.Path("experiments/varna_phonetic_alignment/frozen/b0_frozen_artifacts.json")
m = json.loads(p.read_text(encoding="utf-8"))
e = m["embedding_model_T_embed"]
W="<weights_sha256>"; TOK="<tokenizer_sha256>"; CFG="<config_sha256>"; SBC="<sbert_cfg_sha256>"
e["status"]="enabled"; e["enabled"]=True; e["weights_sha256"]=W; e["revision"]="<COMMIT_SHA>"
e["file_integrity"]["weights"].update(sha256=W, verification="VERIFIED")
e["file_integrity"]["tokenizer"].update(sha256=TOK, verification="VERIFIED")
e["file_integrity"]["config"].update(sha256=CFG, verification="VERIFIED")
e["file_integrity"]["sentence_bert_config"].update(sha256=SBC, verification="VERIFIED")
e["library_recommended_pins"]={"note":"LOCKED at verified freeze",
  "python":"<x.y.z>","sentence-transformers":"<v>","transformers":"<v>",
  "torch":"<v>","tokenizers":"<v>"}
p.write_text(json.dumps(m, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print("manifest updated")
PY
```

## 7. How to verify readiness flips (the acceptance check)
```bash
# (a) the five pinned artifacts STILL verify (you changed none of them)
python3 -c "import sys; sys.path.insert(0,'experiments/varna_phonetic_alignment'); \
import manifest as MF; m=MF.load_manifest(); \
print('hashes_ok', MF.verify_hashes(m)['ok']); \
print('embedding_frozen', MF.embedding_frozen(m)); \
print('ready', MF.check_readiness(m)['ready']); \
print('reasons', MF.check_readiness(m)['reasons'])"
# expect: hashes_ok True | embedding_frozen True | ready True | reasons []

# (b) tests still pass
python3 experiments/varna_phonetic_alignment/test_manifest_loader.py
python3 experiments/varna_phonetic_alignment/test_varna_phonetic_alignment.py

# (c) runner: gate now READY but STILL NOT_RUN (alignment not implemented — expected)
python3 experiments/varna_phonetic_alignment/run_b0.py
# expect status NOT_RUN, reason: "...alignment computation not implemented..."
```
**Pass criteria:** `embedding_frozen True`, `ready True`, `reasons []`, all tests green,
runner still `NOT_RUN` with the "alignment not implemented" reason (not a verdict).

## 8. What must remain unchanged
- **The five pinned artifacts and their hashes:** `lexicon_wordformation.json`,
  `iast_ipa_map.json`, `ipa_feature_table.json`, `decision_rule.json`,
  `run_manifest_schema.json` — and the design-doc hash
  (`PREREG_VARNA_PHONETIC_ALIGNMENT.md`). If any of these changes, you have done more
  than a T_embed freeze.
- **`manifest.py`** gate logic (no code change in this step).
- **T_cat stays sensitivity-only**; `primary_encoding` stays `"embedding"`.
- **§12 verdict logic and all caveats** — unchanged.
- **No alignment run, no verdict, no Mantel/partial-Mantel/permutation/scramble/bootstrap
  on real matrices.**
- **Stage A** (`symbolu_neural/structural_v1`) — untouched
  (`git diff 2d42bf6 HEAD -- symbolu_neural/structural_v1` must stay empty).

## 9. Out of scope (separate, still gated on approval)
Implementing the alignment computation behind the now-ready gate. Until that exists,
`run_b0.py` correctly returns `NOT_RUN` even when readiness is `True`.

> structure, not validated meaning.
