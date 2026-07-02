#!/usr/bin/env bash
# ============================================================================
# RunPod verification + Track C exploratory semantic-realizer run (single script)
#
# EXPLORATORY ONLY. NOT Track B. Emits only ENGINE_REALIZATION_SIGNAL / NO_SIGNAL
# / INCONCLUSIVE. Never ONTOLOGICAL_SIGNAL. Reads the repo; never modifies Stage A
# or manifest.json; commits nothing; keeps the vector asset OUTSIDE the repo.
#
# Usage:   bash run_track_c_runpod.sh
# Env overrides: REPO_URL, WORK, N_SCRAM, COV_MIN, DELTA_THRESH
# Exit codes: 0 ok · 2 tests failed · 3 asset host blocked (STOP) · 4 asset/deps · 5 guard failed
# ============================================================================
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/rasaha/symbolu.git}"
BRANCH="claude/symbolu-adversarial-eval-zevb4h"
WORK="${WORK:-/workspace}"
N_SCRAM="${N_SCRAM:-1000}"
COV_MIN="${COV_MIN:-0.50}"        # below this coverage -> INCONCLUSIVE
DELTA_THRESH="${DELTA_THRESH:-0.02}"
STAGE_A_BASELINE="2d42bf6"        # frozen Stage A baseline commit
ASSET_NAME="glove-wiki-gigaword-50"   # approved: GloVe Wiki+Gigaword, ODC-PDDL, dim 50
ASSET_URL="https://github.com/RaRe-Technologies/gensim-data/releases/download/${ASSET_NAME}/${ASSET_NAME}.gz"
ASSET_MD5_UPSTREAM="c289bc5d7f2f02c6dc9f2f9b67641813"

sec(){ echo; echo "================= $* ================="; }
reach(){ curl -fsS -o /dev/null --max-time 25 --retry 2 -r 0-0 "$1" 2>/dev/null \
         && echo "REACHABLE  $1" || echo "BLOCKED    $1"; }

# --------------------------------------------------------------------------- 1
sec "1. MACHINE IDENTITY"
echo "hostname : $(hostname)"
echo "uname    : $(uname -a)"
echo "python   : $(python3 --version 2>&1)"
if command -v nvidia-smi >/dev/null 2>&1; then nvidia-smi -L; else echo "GPU      : none (CPU-only OK for Track C)"; fi

# --------------------------------------------------------------------------- 1b
sec "1b. HOST REACHABILITY (informational)"
for h in https://huggingface.co https://github.com https://raw.githubusercontent.com \
         https://dl.fbaipublicfiles.com https://nlp.stanford.edu; do reach "$h"; done

# --------------------------------------------------------------------------- 2
sec "2. ASSET-HOST GATE (STOP if the approved asset is unreachable)"
if ! curl -fsS -o /dev/null --max-time 40 --retry 3 -r 0-0 "$ASSET_URL" 2>/dev/null; then
  echo "STOP: approved asset host unreachable:"
  echo "      $ASSET_URL"
  echo "This is NOT a usable RunPod environment for Track C. No download attempted."
  echo "LABEL: INCONCLUSIVE (asset host blocked)"
  exit 3
fi
echo "asset reachable: $ASSET_URL"

# --------------------------------------------------------------------------- 3
sec "3. CLONE + CHECKOUT"
mkdir -p "$WORK" && cd "$WORK"
[ -d symbolu/.git ] || git clone --depth 50 "$REPO_URL" symbolu
cd symbolu
git fetch origin "$BRANCH"
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH" || true
echo "HEAD: $(git rev-parse --short HEAD)"
P="experiments/primitive_sequence_recovery"

# --------------------------------------------------------------------------- 4
sec "4. TESTS"
python3 -m venv .venv && . .venv/bin/activate
pip -q install --upgrade pip >/dev/null
pip -q install numpy gensim >/dev/null   # gensim only to fetch/convert the asset
for t in test_primitive_sequence_recovery test_manifest_gate test_baseline_realizer \
         test_order_sensitive_realizer test_semantic_realizer; do
  python3 "$P/$t.py" >/dev/null && echo "PASS  $t" || { echo "FAIL  $t"; exit 2; }
done

# --------------------------------------------------------------------------- 5
sec "5. DOWNLOAD + CONVERT + HASH-PIN ASSET (kept OUTSIDE the repo)"
export ASSET_DIR="$WORK/track_c_assets"; mkdir -p "$ASSET_DIR"
export GLOVE_TXT="$ASSET_DIR/${ASSET_NAME}.txt"
python3 - <<'PY' || { echo "asset acquisition/convert failed"; exit 4; }
import os, hashlib, pathlib
import gensim.downloader as api
name = os.environ.get("ASSET_NAME", "glove-wiki-gigaword-50")
txt  = pathlib.Path(os.environ["GLOVE_TXT"])
kv = api.load(name)                       # downloads from the approved github release
kv.save_word2vec_format(str(txt))         # plain "token v1..vd" text (+ header line)
# upstream integrity cross-check on the cached .gz (if present)
cache = pathlib.Path.home()/ "gensim-data" / name / f"{name}.gz"
if cache.exists():
    md5 = hashlib.md5(cache.read_bytes()).hexdigest()
    print("cached_gz_md5:", md5, "expected:", os.environ.get("ASSET_MD5_UPSTREAM"),
          "MATCH" if md5 == os.environ.get("ASSET_MD5_UPSTREAM") else "MISMATCH")
sha = hashlib.sha256(txt.read_bytes()).hexdigest()
print("asset_path:", txt)
print("asset_sha256:", sha)
pathlib.Path(os.environ["ASSET_DIR"], "asset.sha256").write_text(sha)
PY
export ASSET_SHA256="$(cat "$ASSET_DIR/asset.sha256")"

# --------------------------------------------------------------------------- 6
sec "6. TRACK C EXPLORATORY RUN (en_gloss; offline scoring)"
python3 - <<'PY' || { echo "track C run failed"; exit 4; }
import os, sys, json, pathlib
P = pathlib.Path("experiments/primitive_sequence_recovery"); sys.path.insert(0, str(P))
import semantic_realizer as SR
from baseline_realizer import tokenize_ordered

txt = os.environ["GLOVE_TXT"]; sha = os.environ["ASSET_SHA256"]
cov_min = float(os.environ.get("COV_MIN", "0.5"))
n_scram = int(os.environ.get("N_SCRAM", "1000"))
delta_thresh = float(os.environ.get("DELTA_THRESH", "0.02"))

vecs = SR.load_vectors(txt, expected_sha256=sha)   # hash-pinned load (raises on mismatch)
ac, wa, refs, dz, active = SR.load_frozen_corpus(P/"frozen", "en_gloss")

need = set()
for g in ac.values():   need |= set(tokenize_ordered(g))
for w in active:        need |= set(tokenize_ordered(refs[w]))
coverage = sum(t in vecs for t in need) / len(need)

m = SR.compute_exploratory_metrics(ac, wa, refs, dz, vecs, words=active,
                                   n_scram=n_scram, seed=0, delta_threshold=delta_thresh)
label = m["label"]
if coverage < cov_min:
    label = "INCONCLUSIVE"          # too many OOV tokens to trust the result
assert label in ("ENGINE_REALIZATION_SIGNAL", "NO_SIGNAL", "INCONCLUSIVE"), label
assert label != "ONTOLOGICAL_SIGNAL"

out = {"track": "C_exploratory", "channel": "en_gloss",
       "asset_path": txt, "asset_sha256": sha,
       "vocab_dim": len(next(iter(vecs.values()))), "asset_vocab": len(vecs),
       "coverage_en_gloss": round(coverage, 4), "tokens_needed": len(need),
       "n_words": m["n_words"], "MRR": round(m["mrr_real"], 4),
       "Top1": round(m["top1_real"], 4), "MRR_scramble_mean": round(m["mrr_scram_mean"], 4),
       "scramble_delta": round(m["delta"], 4), "scramble_pct": round(m["scramble_pct"], 4),
       "n_scram": m["n_scram"], "LABEL": label}
print(json.dumps(out, indent=2))
pathlib.Path(os.environ["ASSET_DIR"], "track_c_result.json").write_text(json.dumps(out, indent=2))
PY

# --------------------------------------------------------------------------- 7
sec "7. GUARDRAIL CONFIRMATIONS"
grep -q "ONTOLOGICAL_SIGNAL" "$ASSET_DIR/track_c_result.json" \
  && { echo "GUARD FAIL: ONTOLOGICAL_SIGNAL present"; exit 5; } \
  || echo "OK: no ONTOLOGICAL_SIGNAL in result"
python3 - <<'PY'
import sys, pathlib; P=pathlib.Path("experiments/primitive_sequence_recovery"); sys.path.insert(0,str(P))
import manifest as MF, run_primitive_recovery as RUN
print("manifest readiness:", MF.check_readiness(P/"frozen")["status"])   # expect NOT_READY
print("runner            :", RUN.run()["status"])                        # expect NOT_RUN
PY
echo "Track B: BLOCKED (no non-circular concept resolver; concept_id/sa_term skipped)"
if git diff --quiet "$STAGE_A_BASELINE" HEAD -- symbolu_neural/structural_v1; then
  echo "Stage A: UNTOUCHED (diff vs $STAGE_A_BASELINE empty)"
else
  echo "Stage A: MODIFIED — ABORT"; exit 5
fi
git status --porcelain frozen/manifest.json | grep -q . \
  && { echo "GUARD FAIL: manifest.json modified"; exit 5; } \
  || echo "OK: manifest.json unmodified"

sec "DONE — exploratory Track C complete (see $ASSET_DIR/track_c_result.json)"
