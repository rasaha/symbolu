#!/usr/bin/env python3
"""B1.10 — per-word blind context-author runner, with pre-registered escalation ladder.

OPERATIONAL IMPROVEMENT ONLY. This runner does NOT change the B1.10 scientific design:
same six words, same Condition A/B, same author packet (sha256 7e07e16b…, asserted below and
never edited), same surface rules (imported unchanged from b1_10_surface_validator), same
judge panel, same statistics, same experiment number.

What changes vs the six-word runner: authoring is decomposed into SIX INDEPENDENT per-word
blind generations. Each job:
  - receives ONLY the unchanged master author packet (all six words, hash 7e07e16b…) plus a
    small per-word scoping directive naming which one of the six words to author THIS run;
    it receives NO Tier-1/Tier-2/Tier-3 packet, no varṇa mapping, no audit, no prior context
    set, no result — the master packet is the sole scientific/blindness content;
  - produces exactly one Condition-A + one Condition-B sentence for that word, plus the four
    self-check fields;
  - is surface-validated in isolation (per-word-pair scope, no relaxation);
  - is ACCEPTED ON FIRST PASS: the first surface-passing pair for a word is kept, never
    regenerated, never compared against other passing versions;
  - on surface FAILURE the whole pair is discarded (never edited/patched/truncated) and only
    that word is regenerated with a FRESH SEED; the retry budget per model rung is an
    OPERATIONAL safeguard only (not experimental, evidentiary, hypothesis-testing, or
    judging), and its sole trigger is a packet-blind SURFACE failure;
  - if a rung exhausts its budget without a pass, authoring for that word ESCALATES along the
    pre-registered ladder:  Qwen2.5-14B-Instruct → Qwen2.5-32B-Instruct → packet-naive human.

Per-pair provenance records: model id, resolved revision, seed, attempt number, ladder rung,
master-packet hash, delivered-prompt hash, raw-output hash, timestamp, blindness attestation,
and reason_for_escalation = SURFACE_VALIDATION_FAILURE_ONLY.

Only after ALL SIX word-pairs pass are they concatenated into ONE development context file
(ordinary Git file, no intermediate freeze). The packet-aware audit then runs on that live
file; a single final evidence freeze happens only after the completed experiment.

Guardrails: resonance / phonetic-fidelity refinement only. No GENUTILITY_*; no
ONTOLOGICAL_SIGNAL; no semantic-truth / ontology / Sanskrit-privilege claim. B1.4b' remains
NULL_RETURN_BOTTOM; original B1.4b blocked; Track B blocked. Structure, not validated meaning.

Runs on a CUDA GPU host (e.g. RunPod). transformers backend, one fresh isolated process.
"""

import argparse
import datetime
import hashlib
import json
import pathlib
import re

from b1_10_surface_validator import validate_word_pair, OFFICIAL_WORDS

# ---- master author packet (NEVER edited; hash asserted before any generation) ----
EXPECT_PACKET_SHA = "7e07e16bb160481c647b5f6e11ff166f63f2fa42e442ba16bfa6fcffe9c30628"

# ---- pre-registered escalation ladder (frozen; see B1_10_PERWORD_BLIND_AUTHORING_WORKFLOW.md) ----
# rung -> (model_id, requested_revision). The final rung is a packet-naive HUMAN and is not a
# model; it is handled out-of-band (the runner stops and emits an ESCALATE_TO_HUMAN record).
ESCALATION_LADDER = [
    {"rung": 0, "model_id": "Qwen/Qwen2.5-14B-Instruct", "revision": None},
    {"rung": 1, "model_id": "Qwen/Qwen2.5-32B-Instruct", "revision": None},
    {"rung": 2, "model_id": "PACKET_NAIVE_HUMAN", "revision": None},
]

# ---- pre-declared per-word seeds (one base seed per word; attempt k uses base_seed + k) ----
# Fixed BEFORE generation. Fresh seed per attempt = base + attempt_index (0-based).
BASE_SEEDS = {
    "pride":    20260720,
    "freedom":  20260721,
    "patience": 20260722,
    "courage":  20260723,
    "control":  20260724,
    "doubt":    20260725,
}

# ---- generation settings (fixed BEFORE generation; identical to the six-word runner) ----
TEMPERATURE, TOP_P, TOP_K, REP_PEN, MAX_NEW = 0.7, 0.9, 0, 1.0, 400

# ---- per-rung operational retry budget (safeguard only; NOT an experimental knob) ----
ATTEMPTS_PER_RUNG = 6


def per_word_directive(word: str, index_1based: int) -> str:
    """Small scoping wrapper delivered ALONGSIDE the unchanged master packet.

    It does NOT alter, restate, or reinterpret Conditions A/B or any rule — those come solely
    from the master packet. It only narrows the OUTPUT SCOPE of this run to a single word and
    the matching output layout. The scientific content the author sees is identical to the
    six-word packet; only the number of words authored per run differs (the operational change).
    """
    return (
        "\n\n---\n"
        "PER-RUN SCOPE (operational; the rules, Conditions A and B, and everything above are unchanged):\n"
        f"For THIS run, author ONLY word #{index_1based} of the six: \"{word}\".\n"
        "Apply every rule in Section 5 and the self-check in Section 6 exactly as written.\n"
        "Return EXACTLY two sentences for this one word, in this layout, and nothing else:\n\n"
        f"{word}\n"
        "A: <your Condition A sentence>\n"
        "   intended class: A | confidence: <high/medium/low> | mixed-condition detected: <yes/no> | naturalness: <natural/slightly forced/forced>\n"
        "B: <your Condition B sentence>\n"
        "   intended class: B | confidence: <high/medium/low> | mixed-condition detected: <yes/no> | naturalness: <natural/slightly forced/forced>\n"
    )


def load_model(model_id, revision):
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM

    tok = AutoTokenizer.from_pretrained(model_id, revision=revision)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, revision=revision, torch_dtype=torch.float16, device_map="auto"
    )
    return tok, model


def generate_once(tok, model, prompt_text, seed):
    import torch

    torch.manual_seed(seed)
    msgs = [{"role": "user", "content": prompt_text}]
    enc = tok.apply_chat_template(
        msgs, add_generation_prompt=True, return_tensors="pt", return_dict=True
    ).to(model.device)
    input_len = enc["input_ids"].shape[1]
    gen = model.generate(
        **enc,
        max_new_tokens=MAX_NEW,
        do_sample=True,
        temperature=TEMPERATURE,
        top_p=TOP_P,
        top_k=(TOP_K or None),
        repetition_penalty=REP_PEN,
        pad_token_id=tok.eos_token_id,
    )
    raw = tok.decode(gen[0][input_len:], skip_special_tokens=True)
    resolved_rev = getattr(model.config, "_commit_hash", None)
    return raw, resolved_rev


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def free_model(model):
    """Release a loaded model's VRAM before loading the next rung (defensive; a single
    80 GB A100 cannot hold two large models at once). No-op if torch is unavailable."""
    try:
        del model
        import gc
        import torch
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def author_one_word(word, index_1based, packet_text, packet_sha, out_dir, start_rung=0, max_rung=None):
    """Author one word-pair, climbing the escalation ladder until a surface pass or budget end.

    Returns (accepted_pair_dict_or_None, provenance_record). Accept-first-pass: the FIRST
    surface-passing generation is returned; no further attempts are made and no passing
    versions are compared.

    `max_rung` caps the highest ladder rung this INVOCATION will attempt (inclusive; default =
    last rung). Running one rung per process (`--start-rung r --max-rung r`) keeps only one
    model on disk/VRAM at a time and makes each rung a genuinely fresh, packet-only process.
    If the capped budget is exhausted without a pass AND a higher rung exists, the record's
    status is `RUNG_EXHAUSTED_ESCALATE_NEXT_PROCESS` (surface failure only) — the operator then
    runs the next rung in a fresh process. The escalation TRIGGER is unchanged: packet-blind
    surface-validation failure only.
    """
    last_idx = len(ESCALATION_LADDER) - 1
    cap = last_idx if max_rung is None else min(max_rung, last_idx)

    directive = per_word_directive(word, index_1based)
    delivered_prompt = packet_text + directive
    delivered_sha = hashlib.sha256(delivered_prompt.encode("utf-8")).hexdigest()
    base_seed = BASE_SEEDS[word]

    attempts_log = []
    tok = model = loaded_id = None

    for rung_spec in ESCALATION_LADDER[start_rung:cap + 1]:
        rung, model_id = rung_spec["rung"], rung_spec["model_id"]

        if model_id == "PACKET_NAIVE_HUMAN":
            # Terminal rung: the runner cannot generate this; it emits a handoff record.
            record = {
                "artifact": "b1_10_perword_author_run",
                "word": word, "word_index_1based": index_1based,
                "status": "ESCALATE_TO_HUMAN",
                "ladder_rung": rung, "model_id": model_id,
                "reason_for_escalation": "SURFACE_VALIDATION_FAILURE_ONLY",
                "master_packet_sha256": packet_sha,
                "delivered_prompt_sha256": delivered_sha,
                "attempts": attempts_log,
                "timestamp_utc": utc_now(),
                "note": ("Both model rungs exhausted their operational retry budget on packet-blind "
                         "SURFACE failures only. A packet-naive human author must now write this one "
                         "word-pair from the unchanged master packet + per-word directive. Record the "
                         "human's identity + blindness attestation on intake."),
            }
            return None, record

        if loaded_id != model_id:
            if model is not None:
                free_model(model)
                model = None
            tok, model = load_model(model_id, rung_spec["revision"])
            loaded_id = model_id

        for attempt in range(ATTEMPTS_PER_RUNG):
            seed = base_seed + attempt
            raw, resolved_rev = generate_once(tok, model, delivered_prompt, seed)
            raw_sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            check = validate_word_pair(raw, word)

            # persist EVERY raw attempt unchanged (auditable; failures preserved, never patched)
            attempt_dir = out_dir / f"{word}_rung{rung}_attempt{attempt}"
            attempt_dir.mkdir(parents=True, exist_ok=True)
            (attempt_dir / "raw_output.txt").write_text(raw, encoding="utf-8")
            (attempt_dir / "surface_validation.json").write_text(
                json.dumps(check, ensure_ascii=False, indent=2)
            )

            attempt_rec = {
                "ladder_rung": rung, "model_id": model_id,
                "revision_requested": rung_spec["revision"], "revision_resolved": resolved_rev,
                "attempt_index": attempt, "seed": seed,
                "raw_output_sha256": raw_sha,
                "surface_pass": check["surface_pass"], "issues": check["issues"],
                "timestamp_utc": utc_now(),
            }
            attempts_log.append(attempt_rec)

            if check["surface_pass"]:
                # ACCEPT-FIRST-PASS: keep this pair, stop immediately, never regenerate/compare.
                provenance = {
                    "artifact": "b1_10_perword_author_run",
                    "word": word, "word_index_1based": index_1based,
                    "status": "ACCEPTED",
                    "accepted": {
                        "ladder_rung": rung, "model_id": model_id,
                        "revision_requested": rung_spec["revision"], "revision_resolved": resolved_rev,
                        "attempt_index": attempt, "seed": seed,
                        "raw_output_sha256": raw_sha,
                    },
                    "generation_settings": {
                        "backend": "transformers", "dtype": "float16",
                        "temperature": TEMPERATURE, "top_p": TOP_P, "top_k": TOP_K,
                        "repetition_penalty": REP_PEN, "do_sample": True,
                        "max_new_tokens": MAX_NEW,
                    },
                    "master_packet_sha256": packet_sha,
                    "delivered_prompt_sha256": delivered_sha,
                    "per_word_directive": directive,
                    "attempts": attempts_log,
                    "reason_for_escalation": "SURFACE_VALIDATION_FAILURE_ONLY",
                    "retry_budget_role": ("operational safeguard only — NOT experimental, evidentiary, "
                                          "hypothesis-testing, or judging"),
                    "blindness_attestation": (
                        "Structural blindness: this fresh isolated process received ONLY the unchanged "
                        f"master author packet (sha256 {packet_sha}) plus a per-word output-scope "
                        "directive naming one of the six words. No Tier-1/Tier-2/Tier-3 packet, varṇa "
                        "mapping, audit, prior context set, or result was provided as input."
                    ),
                    "timestamp_utc": utc_now(),
                }
                (attempt_dir / "ACCEPTED.txt").write_text(raw, encoding="utf-8")
                return raw, provenance

    if model is not None:
        free_model(model)

    # This invocation's capped rung budget was exhausted with no surface pass. If a higher rung
    # exists beyond the cap, the operator escalates by running the NEXT rung in a fresh process
    # (one model per process — disk/VRAM safe). The escalation trigger is surface failure only.
    next_rung = cap + 1
    next_model = ESCALATION_LADDER[next_rung]["model_id"] if next_rung <= last_idx else None
    return None, {
        "artifact": "b1_10_perword_author_run", "word": word, "word_index_1based": index_1based,
        "status": "RUNG_EXHAUSTED_ESCALATE_NEXT_PROCESS",
        "exhausted_up_to_rung": cap, "next_rung": next_rung if next_model else None,
        "next_rung_model": next_model,
        "reason_for_escalation": "SURFACE_VALIDATION_FAILURE_ONLY", "attempts": attempts_log,
        "master_packet_sha256": packet_sha, "delivered_prompt_sha256": delivered_sha,
        "per_word_directive": directive, "timestamp_utc": utc_now(),
        "note": ("Run the next rung in a FRESH process to keep one model on disk/VRAM at a time: "
                 f"`--words {word} --start-rung {next_rung} --max-rung {next_rung}`" if next_model
                 else "No higher rung; capped at the human rung — see ESCALATE_TO_HUMAN handling."),
    }


def extract_pair_block(raw, word):
    """Pull the accepted `word\nA: ...\nB: ...` block (with self-check lines) out of raw output."""
    sent_re = re.compile(r"^\s*([AB]):\s*.+$", flags=re.M)
    lines = [f"{word}"]
    for m in sent_re.finditer(raw):
        # include the sentence line and, if present, the following self-check line
        start = raw.rfind("\n", 0, m.start()) + 1
        end = raw.find("\n", m.end())
        block = raw[start:(end if end != -1 else len(raw))]
        lines.append(block.strip())
        # try to grab the self-check line that follows
        nxt_start = end + 1 if end != -1 else len(raw)
        nxt_end = raw.find("\n", nxt_start)
        sc_line = raw[nxt_start:(nxt_end if nxt_end != -1 else len(raw))]
        if "intended class:" in sc_line:
            lines.append("   " + sc_line.strip())
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="B1.10 per-word blind author runner (escalation ladder).")
    ap.add_argument("--packet", required=True, help="path to B1_10_OFFICIAL_CONTEXT_AUTHOR_PACKET.md (hash 7e07e16b…)")
    ap.add_argument("--out", required=True, help="output directory for per-word artifacts")
    ap.add_argument("--words", nargs="*", default=OFFICIAL_WORDS,
                    help="subset of words to author (default: all six, packet order)")
    ap.add_argument("--start-rung", type=int, default=0, help="ladder rung to start from (0=14B,1=32B,2=human)")
    ap.add_argument("--max-rung", type=int, default=None,
                    help="highest rung this INVOCATION attempts, inclusive (default: last). "
                         "Use `--start-rung r --max-rung r` to run ONE rung per process (disk/VRAM safe).")
    a = ap.parse_args()

    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    packet_bytes = pathlib.Path(a.packet).read_bytes()
    packet_sha = hashlib.sha256(packet_bytes).hexdigest()
    assert packet_sha == EXPECT_PACKET_SHA, f"WRONG PACKET: {packet_sha} != {EXPECT_PACKET_SHA}"
    packet_text = packet_bytes.decode("utf-8")

    all_provenance = []
    accepted_blocks = []
    all_passed = True

    for word in a.words:
        idx = OFFICIAL_WORDS.index(word) + 1
        raw, prov = author_one_word(word, idx, packet_text, packet_sha, out,
                                    start_rung=a.start_rung, max_rung=a.max_rung)
        prov_json = json.dumps(prov, ensure_ascii=False, indent=2)
        (out / f"provenance_{word}.json").write_text(prov_json)
        # rung-scoped copy so a phased (one-rung-per-process) run never overwrites an earlier
        # phase's record on disk (canonical provenance_<word>.json still holds the latest)
        cap = (len(ESCALATION_LADDER) - 1) if a.max_rung is None else a.max_rung
        (out / f"provenance_{word}.rung{a.start_rung}_to_{cap}.json").write_text(prov_json)
        all_provenance.append(prov)
        if prov["status"] == "ACCEPTED":
            accepted_blocks.append(extract_pair_block(raw, word))
        else:
            all_passed = False
            print(json.dumps({"word": word, "status": prov["status"],
                              "reason": prov.get("reason_for_escalation")}, indent=2))

    # concatenate ONLY after all six pass (no intermediate freeze)
    if all_passed and set(a.words) == set(OFFICIAL_WORDS):
        combined = "\n\n".join(accepted_blocks) + "\n"
        (out / "b1_10_contexts_v3_perword.txt").write_text(combined, encoding="utf-8")
        combined_sha = hashlib.sha256(combined.encode("utf-8")).hexdigest()
        (out / "combined_context_sha256.txt").write_text(combined_sha + "\n")
        print(f"ALL SIX PASSED. combined context sha256 = {combined_sha}")
    else:
        print("NOT ALL WORDS PASSED (or partial word set): no combined context file written.")

    (out / "run_summary.json").write_text(json.dumps(
        {"master_packet_sha256": packet_sha, "all_passed": all_passed,
         "words": a.words, "provenance": all_provenance},
        ensure_ascii=False, indent=2))
    print(json.dumps({"master_packet_sha256": packet_sha, "all_passed": all_passed,
                      "words_status": [{"word": p["word"], "status": p["status"]} for p in all_provenance]},
                     indent=2))


if __name__ == "__main__":
    main()
