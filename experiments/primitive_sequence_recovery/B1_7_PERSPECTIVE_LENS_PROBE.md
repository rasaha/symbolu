# B1.7 — Perspective-Lens Controllability Probe (gated; blinded; mock-tested)

**Status:** design + operator runbook. **A NEW, SEPARATE hypothesis.** It does **not** revive the Symbol‑U
meaning claim: **B1.4b′ remains `NULL_RETURN_BOTTOM`**, original B1.4b blocked, Track B blocked. This probe
tests a *repurposing* question surfaced by B1.6's divergence finding — whether the four‑plane "sphere" scaffold
is a **controllable reframing dial**, and whether the varṇa content adds anything over a plain plane‑instruction.
**No GENUTILITY/terminal verdict is ever emitted here. Structure, not validated meaning.**

Readiness label: **`B1_7_PERSPECTIVE_LENS_PROBE_READY_MOCK_TESTED`** (fake adapters only; 18 tests pass).

---

## 1. Why this exists (and what it is *not*)

B1.6 showed the Symbol‑U scaffold reliably pushes a model ~60% off its default reading — but a **scrambled**
scaffold did the same, so the divergence is a property of the *format*, not the varṇa meanings. This probe asks
the practical follow‑on: **can that divergence be *steered* — read "chair" from the MENTAL plane, "grief" from
the PHYSICAL plane — reliably enough to be a useful reframing tool?** And the adversarial core: **does the
varṇa‑sphere content beat simply telling the model "emphasize the <plane> aspects"?**

A positive result here would be a *creativity/reframing utility* claim ("the four‑plane taxonomy is a usable
control surface"), **not** a claim that the phoneme→meaning mapping is real. The `RANDOMIZED_VARNA_SPHERE` and
`PLAIN_SPHERE_INSTRUCTION` arms exist precisely to keep those two claims separate.

## 2. Four planes (lenses)

`physical`, `mental`, `intellectual`, `spiritual` — from the frozen `track_e_varna_sphere_lexicon.json`
(`unvalidated_candidate_representation`; each of 34 varṇas carries a gloss per plane).

## 3. Arms (per word × per target lens)

| arm | prompt | isolates |
|---|---|---|
| `VARNA_SPHERE_LENS` | names the plane **+** the word's varṇa‑sphere glosses as facets | full scaffold |
| `PLAIN_SPHERE_INSTRUCTION` | names the plane **only** (no varṇa content) | **the honest control** |
| `RANDOMIZED_VARNA_SPHERE` | names the plane **+ shuffled** varṇa glosses (seeded derangement) | specificity control |
| `NO_LENS_BASELINE` | no target plane ("Interpret the word …") | reference (not scored for controllability) |

All three lens arms **name the target plane**, so the *only* manipulated variable is whether varṇa glosses
(real vs shuffled vs none) are added. Grid: 12 words × (3 lens arms × 4 lenses + 1 no‑lens) = **156 records**.

## 4. Measures + the decisive contrasts

1. **Controllability** — a **blind** plane‑guesser reads each output (word + text only) and picks the plane it
   most emphasizes. Accuracy vs the true target plane (chance = 0.25). *Does the dial actually steer?*
2. **Quality** — the existing 1–7 rubric via the B1.6 judge panel (the blind package is field‑compatible).
3. **Cross‑plane divergence** — MiniLM cosine distance of a cross‑plane reading vs the word's native‑plane
   reading (reuse the B1.6 divergence script).

**Decisive contrasts (decide these reads *before* looking):**
- `VARNA_SPHERE_LENS` vs `PLAIN_SPHERE_INSTRUCTION` on **controllability** and **quality** — if ≈ equal, the
  varṇa glosses add nothing; the useful artifact is the **plane taxonomy**, and the phonemes are dead weight.
- `VARNA_SPHERE_LENS` vs `RANDOMIZED_VARNA_SPHERE` — if ≈ equal, the *specific* glosses don't matter (the
  B1.6 pattern, and the honest expectation).
- Any lens arm vs chance (0.25) — if ≫ chance, the plane instruction is a genuine, usable reframing dial.

**Prior (honest):** controllability well above chance for all lens arms; `PLAIN` ≈ `VARNA` ≈ `RANDOMIZED`
→ a real, shippable *reframing tool* whose engine is the **taxonomy/instruction, not the varṇa mapping**.
This would leave B1.4b′ exactly where it is.

## 5. Blinding + gating (the features that matter)

- **Blind package** (`panel_judge_visible_outputs.jsonl`): `item_id, target_text, neutral_context,
  blinded_output_id, generation_text, output_format` — **no arm, no target plane, no varṇa**. Enforced by
  `make_judge_visible` (drops any output leaking method/varṇa/Sanskrit terms via the shared whole‑word matcher;
  a leak drops that one output, never the run). Plane *words* in the text are allowed — they are the signal the
  guesser must detect.
- **Evidence‑freeze gate** — real generation refuses without an operator declaration whose mode +
  `targets_sha256` + `sphere_lexicon_sha256` + attestation match (`verify_freeze_gate`).
- **Ratings‑freeze before unblinding** — quality reuses the B1.6 `RATINGS_FROZEN` gate; controllability
  unblinds **only** inside `aggregate_controllability`.
- **No same‑model judging** — guesser/judge models (Llama/Gemma) differ from generators (Mistral/Qwen).
- **Labels are plumbing only** — `B1_7_PROBE_*`; **never** a `GENUTILITY_*`/terminal verdict.

## 6. Frozen inputs

- `frozen/b1_7_perspective_lens_targets_v1.json` — 12 words, 3 per native plane: physical
  (river/mirror/**chair**), mental (grief/wonder/**dread**), intellectual (balance/freedom/**justice**),
  spiritual (lotus/dawn/**sacred**). The first 8 reuse frozen B1.6 varṇa sequences; the 4 added words
  (chair/dread/justice/sacred) are decomposed via `stage_a_prime_coverage.normalize` (A_PRIME_EN) + the frozen
  phoneme→varṇa bridge (not tuned to any output). `randomization_seed = 20260709`; source hashes pinned.
- `track_e_varna_sphere_lexicon.json` — the four‑plane gloss table (hash‑pinned by the gate).

## 7. RunPod runbook (transformers backend; no vLLM)

Reuses the hardened `b1_6_llm_adapter` (transformers direct‑load) and the B1.6 judge panel/scorer. Models are
already cached. Run one generator/guesser at a time (sequential single‑GPU).

```bash
cd /workspace/symbolu && git pull origin claude/symbolu-adversarial-eval-zevb4h
cd experiments/primitive_sequence_recovery
export HF_HOME=/workspace/.cache/huggingface
export PROBE=run_out/b1_7_perspective_lens
mkdir -p "$PROBE"

# (0) evidence-freeze declaration (OPERATOR — authorizes the probe)
python3 - <<'PY'
import hashlib, json, os, pathlib
import perspective_lens_probe as PL
def sha(p): return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
decl = {"artifact": "b1_7_perspective_lens_EVIDENCE_FREEZE_DECLARED", "evidence_freeze_declared": True,
        "mode": PL.MODE, "targets_sha256": sha(PL.TARGETS_FILE),
        "sphere_lexicon_sha256": sha(PL.SPHERE_LEXICON_FILE), "declared_by": os.environ.get("USER","operator"),
        "declared_at_utc": "2026-07-09T00:00:00Z", "attestation": PL.ATTESTATION}
pathlib.Path(os.environ["PROBE"]+"/b1_7_EVIDENCE_FREEZE_DECLARED.json").write_text(json.dumps(decl, indent=2))
print("declared")
PY

# (1) generate — one generator via transformers (repeat per generator, changing model_id + gen_code)
python3 - <<'PY'
import os, pathlib
import perspective_lens_probe as PL, b1_6_llm_adapter as A
ad = A.build_adapter(A.GenerationSettings(model_id="mistralai/Mistral-7B-Instruct-v0.3",
                                          backend="transformers", max_tokens=600, temperature=0.7))
res = PL.run(mock=False, adapter=ad, settings=ad.s,
             decl_path=pathlib.Path(os.environ["PROBE"]+"/b1_7_EVIDENCE_FREEZE_DECLARED.json"),
             gen_code="M1", out_dir=pathlib.Path(os.environ["PROBE"]+"/generation_M1"), write=True)
print("n_success", res["manifest"]["n_success"], "n_failures", res["manifest"]["n_failures"])
PY

# (2) controllability — a BLIND guesser (use a NON-generator model, e.g. Gemma)
python3 - <<'PY'
import os, pathlib
import perspective_lens_probe as PL, b1_6_llm_adapter as A
ad = A.build_adapter(A.GenerationSettings(model_id="google/gemma-2-9b-it", backend="transformers",
                                          max_tokens=16, temperature=0.0, max_attempts=5))
jv = pathlib.Path(os.environ["PROBE"]+"/generation_M1/panel_judge_visible_outputs.jsonl")
part = PL.run_guesser(jv, adapter=ad, out_dir=pathlib.Path(os.environ["PROBE"]+"/controllability_M1"), write=True)
print("guesses", part["n_guesses"], "errors", part["n_errors"])
PY

# (3) unblind controllability (only here)
python3 - <<'PY'
import os, pathlib, json
import perspective_lens_probe as PL
G = pathlib.Path(os.environ["PROBE"]+"/generation_M1")
guesses = json.loads((pathlib.Path(os.environ["PROBE"]+"/controllability_M1/controllability_part.json")).read_text())["guesses"]
hidden  = json.loads((G/"panel_hidden_lens_metadata.json").read_text())
res = PL.aggregate_controllability(guesses, hidden)
for a, v in res["controllability_by_arm"].items():
    print(f"  {a:26} n={v['n']:3} accuracy={v['accuracy']} (chance {v['chance']})")
PY
```

Quality (optional, same as B1.6): point `run_b1_6_v2_llm_judge_panel.py judge` at
`$PROBE/generation_M1/panel_judge_visible_outputs.jsonl`, then a `RATINGS_FROZEN` declaration, then
`judge_b1_6_pilot_outputs.aggregate(...)` with `hidden_meta = panel_hidden_lens_metadata.json` → per‑arm quality
composite. Divergence: reuse the B1.6 MiniLM script, pairing each word's cross‑plane reading vs its native‑plane
reading, per arm.

## 8. How to read the result (honesty rails)

- **Controllability ≫ 0.25 for all lens arms** → the plane instruction is a genuine reframing dial. Good news,
  and *independent of the meaning hypothesis*.
- **`VARNA` ≈ `PLAIN` ≈ `RANDOMIZED`** → the varṇa glosses add nothing; ship the **taxonomy**, drop the
  phonemes. (Expected.)
- **`VARNA` clearly > `PLAIN` on controllability *and* quality, *and* `VARNA` > `RANDOMIZED`** → the *specific*
  glosses help. This would be the first non‑null signal anywhere; treat it as **hypothesis‑generating only**
  (8 words, exploratory, multiple planes = multiple comparisons) → pre‑register a powered confirmatory run with
  `VARNA vs PLAIN` controllability as the single primary endpoint before claiming anything.
- Whatever happens, **B1.4b′ stays `NULL_RETURN_BOTTOM`**; a reframing‑utility result is not a meaning result.

## 9. Guardrails

Mock‑tested only in‑repo; real generation is an operator action on a model host. No external API. No
unblinding before the aggregation/freeze steps. No `GENUTILITY_*` label. `run_out/` and declarations are
gitignored (never committed). Original B1.4b blocked; Track B blocked. **Structure, not validated meaning.**
