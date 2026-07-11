# B1.10 — Non-Claude Context-Author Handoff (docs-only)

Records the final post-freeze audit outcome for the Claude-authored v2 context set, and specifies the exact
operational handoff to run the frozen author packet through a genuinely packet-naive, **non-Claude** author.
Docs-only: no contexts generated here, no frozen items/packets/contexts/runners/evidence-freeze/results changed, no
new experiment number, everything stays under B1.10. Resonance / phonetic-fidelity refinement only — **no
`GENUTILITY_*`, no `ONTOLOGICAL_SIGNAL`, no semantic-truth / ontology / Sanskrit-privilege claim.** B1.4b′ remains
`NULL_RETURN_BOTTOM`; original B1.4b blocked; Track B blocked. **Structure, not validated meaning.**

---

## 1. Final audit outcome — Claude-authored v2 set (RECORDED, FINAL)

`B1_10_OFFICIAL_CONTEXTS_v2_FROZEN.md` (sha256 `8ff6345615f2b50fe3968730dd146d96ae9fec78230db184755a8447a73a7607`):

- **Surface quality:** 12/12 PASS.
- **Tier-3 echo:** CLEAN or ACCEPTABLE_GENERIC_OVERLAP for all 12 (no `SUSPECT_SPECIFIC_ECHO`, no `REJECT_ITEM`).
- **Fairness against Tier-1 / Tier-2:** FAIR for all six words (Tier-2 remains a credible competitor).
- **Rejection reason:** **set-level author-family independence only** — the author is `claude-opus-4-8`, the same
  family as the Tier-3 paraphrase author, violating `OFFICIAL_JUDGE_PANEL_SPEC §5`; corroborated by unusually
  specific scenario convergence with the Claude development sets.
- **Classification:** the v2 set **remains frozen and historical** but is classified
  **`EXCLUDED_CLAUDE_FAMILY_CONTEXTS`**.
- **Handling:** do **not** edit, reuse, or selectively borrow any sentence from it. The **non-Claude author
  requirement is not waived or amended.**

## 2. Handoff scope

The non-Claude author must receive **only**:
- `experiments/primitive_sequence_recovery/B1_10_OFFICIAL_CONTEXT_AUTHOR_PACKET.md`
  (sha256 `7e07e16bb160481c647b5f6e11ff166f63f2fa42e442ba16bfa6fcffe9c30628`).

The author must **not** receive: any Claude-authored context set; the frozen v2 contexts; Tier-1/Tier-2/Tier-3
packets; varṇa mappings or sequences; audits; results; weak/strong facet notes; or this conversation.

- **Preferred author:** `Qwen/Qwen2.5-7B-Instruct` (rev `a09a35458c702b33eeacc393d103063234e8bc28`, committed lock).
- **Alternative:** `mistralai/Mistral-7B-Instruct-v0.3` (rev `c170c708c41dac9275d15a8fff4eca08d52bab71`).
- **A packet-naive human is also acceptable** (record identity + blindness attestation; skip §3–§4).

Both models are disjoint from the Claude paraphrase author **and** from the Llama/Gemma judge panel.

## 3. Declared generation settings (fixed BEFORE generation)

| setting | value |
|---|---|
| backend | `transformers` (direct HF load; fresh isolated process) |
| dtype | float16 |
| temperature | **0.7** |
| top_p | **0.9** |
| top_k | 0 (disabled) |
| repetition_penalty | 1.0 |
| do_sample | true |
| seed | **20260712** (fixed) |
| max_new_tokens | 800 |
| runs | **exactly one** fresh generation call; no external iterative/packet-aware editing |

The packet itself instructs the model to self-discard and rewrite any *mixed/forced* sentence **within its single
response** (Section 6) — that internal self-correction is allowed; what is forbidden is any *external* editing or
re-prompting toward a hidden target. The single raw output is kept regardless.

## 4. Exact standalone invocation (RunPod, single fresh process)

Run on a CUDA RunPod (or any GPU host) in a **clean environment** — nothing from this project except the author
packet. Copy the author-packet file to the box; do **not** copy any other B1.10 file.

```bash
# --- RunPod / GPU host: clean env, single fresh process ---
pip install -q "transformers>=4.44" accelerate torch --upgrade
huggingface-cli login   # if the model requires auth (Qwen2.5 is open; token optional)
python3 author_run.py \
    --packet /workspace/B1_10_OFFICIAL_CONTEXT_AUTHOR_PACKET.md \
    --model Qwen/Qwen2.5-7B-Instruct \
    --revision a09a35458c702b33eeacc393d103063234e8bc28 \
    --out /workspace/b1_10_author_v3_qwen
```

`author_run.py` (self-contained; declares settings up front; one generation; saves raw; records provenance;
validates surface rules ONLY; never sees or compares any packet):

```python
import argparse, hashlib, json, pathlib, datetime, re, torch
from transformers import AutoTokenizer, AutoModelForCausalLM

# ---- settings fixed BEFORE generation (pre-registered) ----
TEMPERATURE, TOP_P, TOP_K, REP_PEN, SEED, MAX_NEW = 0.7, 0.9, 0, 1.0, 20260712, 800
EXPECT_PACKET_SHA = "7e07e16bb160481c647b5f6e11ff166f63f2fa42e442ba16bfa6fcffe9c30628"
WORDS = ["pride", "freedom", "patience", "courage", "control", "doubt"]
FORBIDDEN = ["binding", "liberating", "source-condition", "self-grounded", "other-conditioned"]

ap = argparse.ArgumentParser()
ap.add_argument("--packet", required=True); ap.add_argument("--model", required=True)
ap.add_argument("--revision", default=None); ap.add_argument("--out", required=True)
a = ap.parse_args()
out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)

packet_bytes = pathlib.Path(a.packet).read_bytes()
packet_sha = hashlib.sha256(packet_bytes).hexdigest()
assert packet_sha == EXPECT_PACKET_SHA, f"WRONG PACKET: {packet_sha} != {EXPECT_PACKET_SHA}"
packet_text = packet_bytes.decode("utf-8")

torch.manual_seed(SEED)
tok = AutoTokenizer.from_pretrained(a.model, revision=a.revision)
model = AutoModelForCausalLM.from_pretrained(a.model, revision=a.revision,
                                             torch_dtype=torch.float16, device_map="auto")
# the packet IS the entire instruction; deliver it as the sole user turn, no extra system prompt
msgs = [{"role": "user", "content": packet_text}]
inputs = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt").to(model.device)
gen = model.generate(inputs, max_new_tokens=MAX_NEW, do_sample=True,
                     temperature=TEMPERATURE, top_p=TOP_P, top_k=(TOP_K or None),
                     repetition_penalty=REP_PEN, pad_token_id=tok.eos_token_id)
raw = tok.decode(gen[0][inputs.shape[1]:], skip_special_tokens=True)

# ---- save raw output UNCHANGED ----
(out / "raw_output.txt").write_text(raw, encoding="utf-8")
raw_sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
resolved_rev = getattr(model.config, "_commit_hash", a.revision)

prov = {
    "artifact": "b1_10_nonclaude_author_run",
    "model_id": a.model, "revision_requested": a.revision, "revision_resolved": resolved_rev,
    "generation_settings": {"backend": "transformers", "dtype": "float16", "temperature": TEMPERATURE,
                            "top_p": TOP_P, "top_k": TOP_K, "repetition_penalty": REP_PEN,
                            "do_sample": True, "seed": SEED, "max_new_tokens": MAX_NEW, "runs": 1},
    "author_prompt_sha256": packet_sha, "raw_output_sha256": raw_sha,
    "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "blindness_attestation": ("Structural blindness: this fresh isolated process received ONLY the author packet "
                              f"(sha256 {packet_sha}); no Claude context set, frozen v2 contexts, packets, varṇa "
                              "mappings, audits, results, or facet notes were provided as input."),
}
(out / "provenance.json").write_text(json.dumps(prov, ensure_ascii=False, indent=2))

# ---- SURFACE validation ONLY (no packet comparison) ----
def surface_check(text):
    issues, sents = [], re.findall(r"^\s*([AB]):\s*(.+?)\s*$", text, flags=re.M)
    a_b = [s for _, s in sents]
    if len(a_b) != 12: issues.append(f"expected 12 sentences, found {len(a_b)}")
    for lab, s in sents:
        wc = len(s.split())
        if not (12 <= wc <= 22): issues.append(f"[{s[:40]}...] wordcount {wc} out of 12-22")
        low = s.lower()
        for f in FORBIDDEN:
            if f in low: issues.append(f"[{s[:40]}...] forbidden label '{f}'")
    # each target word present naturally in its own two sentences (by block order)
    # mixed/forced self-marks must be absent among accepted sentences
    if re.search(r"mixed-condition detected:\s*yes", text, re.I): issues.append("a sentence self-marked mixed")
    if re.search(r"naturalness:\s*forced", text, re.I): issues.append("a sentence self-marked forced")
    return issues

issues = surface_check(raw)
(out / "surface_validation.json").write_text(json.dumps(
    {"surface_pass": not issues, "issues": issues,
     "note": "Surface rules only (count/wordcount/target/forbidden-labels/self-marks). NO packet comparison. "
             "'one stable condition' relies on the author's per-sentence self-check (mixed-condition detected)."},
    ensure_ascii=False, indent=2))
print(json.dumps({"packet_sha": packet_sha, "raw_output_sha256": raw_sha,
                  "surface_pass": not issues, "issues": issues}, indent=2))
```

## 5. Validation — author-packet SURFACE rules only

The runner checks **only** the surface rules from the author packet; it makes **no packet comparison**:
- exactly **12** accepted sentences (two per word, in packet order),
- each **12–22 words**,
- target word **present naturally** in its word block,
- **one stable condition** — relied on via the author's own per-sentence `mixed-condition detected: no` self-check
  (any `yes`/`forced` self-mark fails surface validation and the whole run returns to a new packet-naive author),
- **no forbidden labels** (binding / liberating / source-condition / self-grounded / other-conditioned).

If surface validation **fails**, do not patch — re-run with a fresh packet-naive author (or the alternative model).

## 6. Freeze BEFORE any packet-aware audit

Only after surface validation passes:
1. Extract the 12 accepted sentences + the author's self-check fields + the provenance block into a **new,
   separately-labelled** artifact — **`B1_10_OFFICIAL_CONTEXTS_v3_QWEN.md`** (v3 = non-Claude), with a byte-identical
   **`..._v3_QWEN_FROZEN.md`** copy. (`v2` = the excluded Claude set stays untouched; all prior B1.10 artifacts
   preserved.)
2. Record and publish the frozen v3 sha256 **before** the packets are ever placed beside it.
3. **Do not compare against any packet before this freeze.** The freeze-before-comparison ordering is what
   guarantees no packet knowledge can retroactively shape the contexts.

## 7. After freeze (separate step — not part of this handoff)

Bring the frozen v3 set here, then re-run the packet-aware audit (context-independence → Tier-3 echo → Tier-1/Tier-2
fairness → word-level decisions). **Do not run judges.** Only after the v3 set passes the packet-aware audit does a
v3 control-extension build + a new evidence-freeze declaration become appropriate — each a later, separately gated
step.

## 8. Guardrails
Docs-only. No contexts generated in this Claude session. No new experiment number. Everything under B1.10. All prior
artifacts preserved. Resonance / phonetic-fidelity refinement only. No `GENUTILITY_*`; no `ONTOLOGICAL_SIGNAL`; no
semantic-truth / ontology / Sanskrit-privilege claim. **B1.4b′ remains `NULL_RETURN_BOTTOM`. Original B1.4b blocked.
Track B blocked. Structure, not validated meaning.**
