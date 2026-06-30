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

## 2. Pin the immutable snapshot revision (not a branch)
Store the **immutable commit** the Hub currently serves for `main` — never the moving
branch name `main` itself. Resolve it via `huggingface_hub` (the same resolver the
download uses):
```bash
pip install -U "huggingface_hub[cli]"
python3 - <<'PY'
from huggingface_hub import HfApi
info = HfApi().model_info("sentence-transformers/all-MiniLM-L6-v2")
print("revision (immutable commit):", info.sha)   # -> <COMMIT_SHA> for manifest "revision"
PY
```
Download exactly that revision (the snapshot is content-addressed to the commit):
```bash
python3 - <<'PY'
from huggingface_hub import snapshot_download
path = snapshot_download("sentence-transformers/all-MiniLM-L6-v2",
                         revision="<COMMIT_SHA>", local_dir="./_tembed_snapshot")
print("snapshot at:", path, "(revision <COMMIT_SHA>)")
PY
```
The manifest's `revision` **must** be this `<COMMIT_SHA>` (an immutable identifier). If
`main` advances later, the pin still resolves to the exact files you hashed.

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
Also capture the exact library versions **and full runtime provenance** (embedding output
can drift across versions, and OS/arch/CPU are valuable provenance for re-running years
later — recorded, not gated):
```bash
python3 - <<'PY'
import json, platform as P
import sentence_transformers, transformers, torch, tokenizers
env = {
  "python": P.python_version(),
  "sentence-transformers": sentence_transformers.__version__,
  "transformers": transformers.__version__,
  "torch": torch.__version__,
  "tokenizers": tokenizers.__version__,
  "platform": P.platform(),
  "system": P.system(),
  "machine": P.machine(),
  "processor": P.processor(),
  "device": ("cuda:" + torch.cuda.get_device_name(0)) if torch.cuda.is_available() else "cpu",
}
print(json.dumps(env, indent=2))
PY
```

## 4b. Embedding reproducibility fingerprint (behaviour, not just inputs)
File hashes prove the *inputs* are identical; this proves the *runtime behaviour* is
identical — it catches pooling / normalization / tokenizer / library drift that identical
files alone do not. Use a **neutral reference string** (NOT a lexicon reading — this must
never touch the B0 estimand):
```bash
python3 - <<'PY'
import hashlib, json, numpy as np
from sentence_transformers import SentenceTransformer
REF = "The quick brown fox jumps over the lazy dog."
m = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", revision="<COMMIT_SHA>")
v = m.encode([REF], normalize_embeddings=True)[0].astype(np.float32)
fp = {
  "reference_string": REF,
  "dim": int(v.shape[0]),                                   # expect 384
  "l2_norm": round(float(np.linalg.norm(v)), 6),            # ~1.0 (normalized)
  "vector_sha256": hashlib.sha256(v.tobytes()).hexdigest(), # tight SAME-env fingerprint
  "dtype": "float32", "byte_order": "little",
  "match_tolerance_max_abs": 1e-5,                          # CROSS-env reproduction tolerance
}
print(json.dumps(fp, indent=2))
PY
```
**Honest caveat — do not overpromise bit-exactness.** Floating-point embeddings can differ
in the last bits across torch/BLAS builds and CPU-vs-GPU. So:
- `vector_sha256` is an **exact** fingerprint that should match on the **same** environment
  that produced it;
- across a **different** environment, verify instead that
  `max(abs(v_new − v_ref)) ≤ match_tolerance_max_abs` (re-derive the reference vector on the
  frozen environment, or store it alongside).

Record the whole `fp` dict in the manifest under `embedding_fingerprint`.

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
| `embedding_fingerprint` | (absent) | the `fp` dict from §4b (ref string, dim, l2_norm, vector_sha256, dtype, byte_order, tolerance) |
| `runtime_environment` | (absent) | the env dict from §4 (libs + platform/system/machine/processor/device) |

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
e["embedding_fingerprint"]=FP   # the dict printed by §4b
e["runtime_environment"]=ENV    # the dict printed by §4
p.write_text(json.dumps(m, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
print("manifest updated")
PY
```
(Paste the §4b `fp` dict as `FP` and the §4 env dict as `ENV` into the script above.)

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

# (d) embedding BEHAVIOUR reproduces (regenerate the §4b reference embedding)
python3 - <<'PY'
import json, pathlib, hashlib, numpy as np
from sentence_transformers import SentenceTransformer
m=json.loads(pathlib.Path("experiments/varna_phonetic_alignment/frozen/b0_frozen_artifacts.json").read_text())
e=m["embedding_model_T_embed"]; fp=e["embedding_fingerprint"]
mod=SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", revision=e["revision"])
v=mod.encode([fp["reference_string"]], normalize_embeddings=True)[0].astype(np.float32)
print("dim ok:", v.shape[0]==fp["dim"])
print("l2 ok:", abs(float(np.linalg.norm(v))-fp["l2_norm"])<1e-4)
print("exact sha (SAME-env only):", hashlib.sha256(v.tobytes()).hexdigest()==fp["vector_sha256"])
# cross-env: compare against a stored reference vector instead, using the tolerance:
# print("within tolerance:", float(np.max(np.abs(v - v_ref))) <= fp["match_tolerance_max_abs"])
PY
```
**Pass criteria:** `embedding_frozen True`, `ready True`, `reasons []`, all tests green,
runner still `NOT_RUN` with the "alignment not implemented" reason (not a verdict), and the
§4b fingerprint reproduces — `dim`/`l2_norm` match, and `vector_sha256` matches on the
**same** environment (cross-environment, use `match_tolerance_max_abs` instead).

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
- Implementing the alignment computation behind the now-ready gate. Until that exists,
  `run_b0.py` correctly returns `NOT_RUN` even when readiness is `True`.
- Optionally **gating** readiness on the embedding fingerprint or runtime environment (a
  `manifest.py` change) — these are recorded as provenance/reproduction checks here, not
  enforced by the gate. Promoting them to gate conditions is future hardening, not part of
  this freeze step.

> structure, not validated meaning.
