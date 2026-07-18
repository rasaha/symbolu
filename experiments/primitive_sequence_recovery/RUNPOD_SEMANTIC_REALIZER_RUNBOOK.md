# RunPod Runbook — Semantic-Realizer Path (docs only)

**This is a runbook, not an execution.** No implementation, no download, no run, no scores in
producing this file. It describes how to *safely* test the semantic-realizer path on external
hardware (RunPod) **later**, under explicit approval.

**Non-negotiable guardrails (repeat at every phase):**
- **Track B (confirmatory) stays BLOCKED** unless an *independent, non-circular* concept asset is
  obtained AND passes the §5 gate. Do not claim otherwise.
- **Do not run a confirmatory experiment.** Track C (exploratory frozen-engine/text scoring) only.
- **Never overwrite `manifest.json`.** New freezes go to `manifest_v2.json`.
- **Never force READY.** READY only if `check_readiness` passes on its own.
- **Stage A untouched.** Verify with `git diff 2d42bf6 HEAD -- symbolu_neural/structural_v1`
  (must be empty) at start and end.

Design basis: `PROJECT_STATUS_AND_NEXT_PHASE.md`, `CONCEPT_RESOLVER_CIRCULARITY_AUDIT.md`,
`SEMANTIC_REALIZER_EVALUATION.md`, `OFFLINE_EMBEDDING_ASSET_AUDIT.md`,
`FROZEN_INFERENCE_ENGINE_ARCHITECTURE.md`, `REALIZER_IMPLEMENTATION_PLAN.md`.

---

## 1. Pod requirements

| resource | requirement |
|---|---|
| **CPU** | **Sufficient for all of Track C with static embeddings + WordNet.** A CPU-only pod (4–8 vCPU, 16–32 GB RAM) is the *minimum and the default*. |
| **GPU** | **Optional; only if running a local LLM** for exploratory Track C. Not needed for static embeddings / WordNet / lexical baselines. If used: a single mid-range GPU (≥16 GB VRAM) for a small local model. |
| **Disk** | 20–40 GB. The repo is small; budget for one or two embedding matrices (GloVe 6B.300d ~1 GB; fastText per-lang ~few GB) **before slicing**. After slicing to the corpus vocab, the vendored asset is KB–MB. |
| **Internet** | **Required for the asset-acquisition phase only** (Phase A), from *approved* sources. All scoring runs must work **offline** afterward. RunPod is *not* the firewalled Claude sandbox, so PyPI + general hosts are reachable there — but acquisition is still **approval-gated** and every asset must be hash-pinned. |
| **Python** | 3.11+ (match the repo's `pyproject.toml`). `numpy` is the only hard dependency of the current code. |
| **CUDA** | **Not required** unless running a local LLM. Static-embedding / WordNet / lexical paths are pure-CPU. |

---

## 2. Setup commands

```bash
# clone + checkout
git clone <rasaha/symbolu remote> symbolu && cd symbolu
git checkout claude/symbolu-adversarial-eval-zevb4h

# minimal deps (current code needs only numpy; add nothing else in setup)
python3 -m venv .venv && . .venv/bin/activate
pip install numpy

# run existing tests (all must pass; no network, no assets)
python3 experiments/primitive_sequence_recovery/test_primitive_sequence_recovery.py
python3 experiments/primitive_sequence_recovery/test_manifest_gate.py
python3 experiments/primitive_sequence_recovery/test_baseline_realizer.py
python3 experiments/primitive_sequence_recovery/test_order_sensitive_realizer.py

# verify the gate is still NOT_READY and the runner still NOT_RUN (baseline sanity)
python3 - <<'PY'
import sys, pathlib, json
p = pathlib.Path("experiments/primitive_sequence_recovery"); sys.path.insert(0, str(p))
import manifest as MF, run_primitive_recovery as RUN
print("readiness:", MF.check_readiness(p/"frozen")["status"])   # expect NOT_READY
print("runner   :", RUN.run()["status"])                        # expect NOT_RUN
PY

# Stage A untouched
git diff 2d42bf6 HEAD -- symbolu_neural/structural_v1 | head   # expect empty
```

**Stop condition:** if any test fails, or readiness ≠ NOT_READY, or runner ≠ NOT_RUN, or the
Stage A diff is non-empty → **halt** and investigate before doing anything else.

---

## 3. Asset-acquisition phase (rules)

- Download **only** from **approved** locations (recorded in the approval); prefer immutable
  snapshot/version URLs, never "latest"/`main`.
- **Compute `sha256` for every asset** immediately after download and record it, with: source
  URL/snapshot, version, dimension, date, and **license**. **Do not fabricate hashes** — a hash
  exists only once its bytes exist.
- **Do not commit large assets** to the repo unless explicitly approved. Prefer a
  **vocabulary-restricted slice** (only tokens the corpus needs) → KB–MB → vendorable + pinnable.
- Keep raw multi-GB downloads on the pod's ephemeral disk; commit only the sliced, hashed asset
  (if approved) or keep it pod-local and record its hash.
- License must be **compatible with vendoring** if committed (prefer permissive: GloVe ODC-PDDL,
  WordNet/OEWN; note copyleft: fastText/ConceptNet CC BY-SA; avoid murky: word2vec GoogleNews).

---

## 4. Candidate asset paths

| asset | role | channel | notes |
|---|---|---|---|
| **English static embeddings** (GloVe/fastText) | `en_gloss` text realizer | approved download → slice → hash | permissive (GloVe); CPU-only |
| **Sanskrit/IAST-capable embeddings** (fastText `cc.sa`, subword) | `sa_term` text realizer | approved download → slice → hash | large, CC BY-SA; subword handles IAST; **without this, `sa_term` stays blocked** |
| **WordNet / OEWN** | concept resolver / robustness | approved download + `wn`/`nltk` data | English-centric → circularity caveat (§5) |
| **IndoWordNet / Sanskrit WordNet** | **Sanskrit-grounded** concept resolver (preferred for §5) | approved download; verify license | sparse coverage of abstractions; best non-circular candidate |
| **ConceptNet / Numberbatch** | robustness concept resolver | approved download | large; English-heavy |
| **Local LLM** | **Track C exploratory only** | GPU pod | **NOT Track B**; see §5/§7; contamination + nondeterminism risks |

---

## 5. Concept-resolver gate (defines what counts as non-circular)

A concept resolver may support **Track B only if it passes all three** (from
`CONCEPT_RESOLVER_CIRCULARITY_AUDIT.md`):

- **C1 — similarity provenance:** `sim(node_a, node_b)` depends only on *(frozen ontology, node
  ids)*; it never reads the `en_gloss` strings nor invokes an English text embedder at scoring
  time.
- **C2 — mapping provenance:** `svc/wmc → node` mappings are frozen, human-auditable, and built
  **not** by "nearest English synset via English embedding"; **Sanskrit-term-grounded** mapping
  preferred; any English use disclosed.
- **C3 — decorrelation (run-time):** on the frozen corpus, `ρ(M_concept, M_en_gloss) < ρ*`
  (pre-registered, e.g. 0.5) **and** the concept channel keeps its own real > scramble power. If
  `ρ ≈ 1` → redundant → **fail**.

**Gloss-permutation invariance audit (operationalizes C1):** freeze the resolver; draw random
permutations π of the gloss→atom association; recompute `en_gloss` rankings (must vary) and
`concept_id` rankings using the unchanged resolver (must be **identical** for all π). PASS ⇒ C1.
**Necessary but not sufficient** — it does not catch C2/C3.

**If C1, C2, or C3 fails → label Track B still BLOCKED.** The resolver may only be reported as an
exploratory/robustness channel, never confirmatory.

---

## 6. Implementation phases (gated, in order)

- **Phase A — assets only.** Download → slice → `sha256` → record license/provenance. No code
  wired to scoring. Commit only approved, hashed, sliced assets.
- **Phase B — semantic text realizer.** Implement `StaticEmbeddingRealizer` behind the existing
  `Realizer` interface (`baseline_realizer.py` pattern) + a fixed, pre-registered order-aware
  composition + hash+probe verification. Unit tests: determinism, offline, hash-verify,
  order-sensitivity, `sa` "—" zero-vector handling. **No run.**
- **Phase C — concept resolver (only if a non-circular asset exists).** Build the resolver;
  run the §5 gate (C1 gloss-permutation now; C2 provenance review; C3 deferred to run time).
  **If it fails, stop here and keep Track B BLOCKED.**
- **Phase D — `manifest_v2.json` (only after the validator passes).** Re-hash changed artifacts
  (`realizer.json`, `run_params.json`, new assets); author **`manifest_v2.json`** (never
  overwrite `manifest.json`); `check_readiness` decides its status.
- **Phase E — exploratory Track C run FIRST.** With a deterministic engine (static embeddings;
  or, clearly-labeled exploratory, a local LLM), run the text-realization scoring with
  real-vs-scramble + order-scramble nulls. **Report with `ENGINE/REALIZATION_ARTIFACT`
  ceiling**; do not present as confirmatory.
- **Phase F — Track B (only if Phase C passed C1–C3).** Run the cross-realization confirmatory
  protocol with the pre-registered decision labels. If C3 or contamination controls fail at run
  time → abort and report Track B BLOCKED.

---

## 7. Safety rules

- **Never overwrite `manifest.json`;** all new freezes → `manifest_v2.json`.
- **No READY** unless `check_readiness` returns READY on its own with all gates satisfied.
- **No result claims without the pre-registered labels** (`ONTOLOGICAL_SIGNAL` /
  `REALIZATION_ARTIFACT` / `NO_SIGNAL` / `REALIZER_DEPENDENT` / `INCONCLUSIVE`).
- **No LLM as a confirmatory result** — LLM engines are Track C exploratory only (contamination,
  nondeterminism, prompt/version dependence).
- **Stage A untouched** — re-verify the `2d42bf6` diff is empty before committing anything.
- **Track B stays BLOCKED** in all reporting unless §5 passed with an independent asset.

---

## 8. Expected outcomes (and what each means)

| outcome | interpretation / next step |
|---|---|
| **Asset acquired** (en / sa / concept) | proceed to the corresponding phase; record hash+license |
| **Asset unavailable** (esp. Sanskrit / Sanskrit-grounded concept) | that channel stays BLOCKED; do not substitute; report honestly |
| **Exploratory text signal** (Track C real > scramble) | report as `REALIZATION/ENGINE_ARTIFACT` ceiling — *not* confirmatory; check contamination + English-leakage controls |
| **No signal** (real ≈ scramble) | `NO_SIGNAL` — a valid negative result; report it |
| **Concept-resolver circularity failure** (C1/C2/C3 fail) | Track B stays BLOCKED; concept channel demoted to exploratory/robustness |
| **Track B remains blocked** | the expected default; publish Track A + honest blocked-Track-B status (Version 1) |

---

## 9. Exact diagnostic commands

```bash
cd symbolu && . .venv/bin/activate
P=experiments/primitive_sequence_recovery

# hardware / environment
python3 -c "import platform,os;print('py',platform.python_version());print('cpus',os.cpu_count())"
python3 -c "import numpy;print('numpy',numpy.__version__)"
nvidia-smi 2>/dev/null || echo "no GPU (expected for CPU-only Track C)"
free -h 2>/dev/null; df -h . 2>/dev/null | tail -1

# test suite (all four must pass)
python3 $P/test_primitive_sequence_recovery.py
python3 $P/test_manifest_gate.py
python3 $P/test_baseline_realizer.py
python3 $P/test_order_sensitive_realizer.py

# readiness + runner (expect NOT_READY / NOT_RUN until a valid manifest_v2 exists)
python3 - <<'PY'
import sys,pathlib; p=pathlib.Path("experiments/primitive_sequence_recovery"); sys.path.insert(0,str(p))
import manifest as MF, run_primitive_recovery as RUN
r=MF.check_readiness(p/"frozen")
print("readiness:",r["status"],"| reasons:",r["reasons"])
print("runner:",RUN.run()["status"])
PY

# asset hashing (run per downloaded asset; record output, do NOT invent)
sha256sum <asset-file>            # linux
# python fallback:
python3 -c "import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest())" <asset-file>

# Stage A untouched (must print nothing)
git diff 2d42bf6 HEAD -- symbolu_neural/structural_v1
```

---

## Closing

This runbook enables a **safe, gated, offline-after-acquisition** test of the semantic-realizer
path on RunPod. Its default and most likely outcome is: **Track C exploratory only**, with **Track
B remaining BLOCKED** unless an independent, non-circular, Sanskrit-grounded concept asset is
obtained and passes §5. No implementation, download, or run was performed in writing it;
`manifest.json` remains NOT_READY, the runner remains NOT_RUN, and Stage A is untouched.

> structure, not validated meaning.
