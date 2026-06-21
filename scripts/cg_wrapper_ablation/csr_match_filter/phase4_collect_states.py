#!/usr/bin/env python3
"""phase4_collect_states.py — Phase 4 Stage-A hidden-state collector (RunPod / GPU).

Captures the model's residual/hidden state at the FINAL PROMPT TOKEN, *before* any answer token is
generated, for the base and framed Phase 2B-v2 prompts, sweeping all (or a configured set of) layers.
Saves activations to .npz and an aligned metadata JSONL. Labels (audit_pass/fail, frame_violation,
primary_frame_missing, secondary_promoted, rejected_domain_leak, phoneme_overreach,
factuality_suspected) come from the POST-generation Phase 3 audit of the saved/generated answer, while
FEATURES come only from the pre-generation prompt forward pass — the two are kept strictly separate.

Boundaries: Stage-A plumbing only. No Phase 4 claim, no adversarial dataset, no generation control, no
Bhava/Guna/Vritti/JEPA. The frozen Phase 1 scorer/thresholds, the Phase 2 framed prompt (reused
verbatim via prompts.py), rubric_v2, and the Phase 3 audit rules are all imported read-only.

  python phase4_collect_states.py \
    --data .../framed_answer_eval_v2_rubricv2.jsonl --arms base,framed --layers all \
    --traces runs/csr_phase2b/robustness_eval_v2.json \
    --model mistralai/Mistral-7B-Instruct-v0.3 --out-dir runs/csr_phase4
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from csr_match_filter import answer_audit as AA               # noqa: E402
from csr_match_filter import eval_framed_answers as EF        # frozen frame + prompts  # noqa: E402
from csr_match_filter import eval_match_filter as EV          # KB  # noqa: E402
from csr_match_filter import prompts as P                     # frozen Phase 2 prompts  # noqa: E402
from csr_match_filter.eval_real_output_audit import is_meta_parrot  # noqa: E402
from csr_match_filter.match import dominant_terms             # noqa: E402

_HERE = Path(__file__).resolve().parent
_DATA = _HERE / "eval_data" / "framed_answer_eval_v2_rubricv2.jsonl"
EXTRACTION_MODE = "last_prompt_token_pre_generation"

# ---- pure helpers (CPU-testable, no torch) --------------------------------------------------------


def prompt_sha256(prompt: str) -> str:
    return hashlib.sha256((prompt or "").encode("utf-8")).hexdigest()


def build_prompts(ex, trace) -> dict:
    """The exact Phase 2 base/framed prompts for one example (reused verbatim from prompts.py)."""
    q, eid = ex["query"], ex["id"]
    return {"base": P.build_base_prompt(q, eid),
            "framed": P.build_framed_prompt(q, trace.primary_domains, trace.secondary_domains,
                                            trace.rejected_domains, eid)}


def frame_dict_from_trace(trace) -> dict:
    return {"primary_domains": list(trace.primary_domains),
            "secondary_domains": list(trace.secondary_domains),
            "rejected_domains": list(trace.rejected_domains)}


def labels_from_audit(query, answer, frame, alt=None, false_claims=None, terms=None) -> dict:
    """Post-generation labels from the frozen Phase 3 auditor. `answer` is the generated text; this is
    used ONLY for labels, never for features."""
    res = AA.audit_answer(query, answer or "", frame, terms=terms, alternate_true_senses=alt,
                          false_claims=false_claims)
    ft = set(res.finding_types)
    frame_findings = {"primary_frame_missing", "secondary_promoted_to_primary",
                      "rejected_domain_promoted", "phoneme_overreach_claim"}
    return {
        "audit_pass": bool(res.passed),
        "audit_fail": bool(not res.passed),
        "frame_violation": bool(ft & frame_findings),
        "primary_frame_missing": "primary_frame_missing" in ft,
        "secondary_promoted": "secondary_promoted_to_primary" in ft,
        "rejected_domain_leak": "rejected_domain_promoted" in ft,
        "phoneme_overreach": "phoneme_overreach_claim" in ft,
        "factuality_suspected": "factuality_suspected" in ft,
        "answer_too_generic": "answer_too_generic" in ft,
        "meta_parroting": bool(is_meta_parrot(answer or "")),
        "audit_finding_types": sorted(ft),
    }


def build_metadata_row(row_index, ex, arm, prompt, model_id, layers, labels, label_source,
                       feature_dim=None, prompt_token_count=None, final_prompt_token_id=None,
                       final_prompt_token_text=None, frame_summary=None,
                       answer_trace_source_id=None) -> dict:
    """One aligned metadata record. token_position=-1 (final prompt token); features never read
    answer tokens (enforced by construction and recorded here as `features_from_answer_tokens`)."""
    h = prompt_sha256(prompt)
    return {
        "row_index": int(row_index),
        "id": ex["id"], "arm": arm, "category": ex.get("category"), "query": ex["query"],
        "model_id": model_id,
        "prompt_sha256": h,
        "prompt_hash": h,
        "prompt_token_count": (None if prompt_token_count is None else int(prompt_token_count)),
        "token_position": -1,
        "token_position_desc": "final_prompt_token",
        "final_prompt_token_id": (None if final_prompt_token_id is None else int(final_prompt_token_id)),
        "final_prompt_token_text": final_prompt_token_text,
        "extraction_mode": EXTRACTION_MODE,
        "reads_answer_tokens": False,
        "features_from_answer_tokens": False,
        "feature_provenance": "residual_stream_hidden_state",
        "layers": list(layers),
        "feature_dim": (None if feature_dim is None else int(feature_dim)),
        "csr_frame_summary": frame_summary,
        "answer_trace_source_id": answer_trace_source_id,
        "label_source": label_source,
        "labels": labels,
    }


def frame_summary_of(trace) -> dict:
    return {"primary": list(trace.primary_domains), "secondary": list(trace.secondary_domains),
            "rejected": list(trace.rejected_domains)}


# ---- diagnostics (CPU-testable) -------------------------------------------------------------------

# Label fields whose class balance gates the Stage-B probe; <5 positives -> warn.
DIAG_LABELS = ("audit_fail", "frame_violation", "rejected_domain_leak", "secondary_promoted",
               "factuality_suspected", "meta_parroting")

MANIFEST_REQUIRED = (
    "model_id", "tokenizer_name", "n_examples", "arms", "n_layers", "d_model", "layers",
    "extraction_mode", "token_position", "token_position_desc", "features_from_answer_tokens",
    "reads_answer_tokens", "feature_provenance", "contains_phase1_csr_scores",
    "contains_phonemic_12d_profile", "contains_csr_trace_vector", "prompt_hashes_present",
    "trace_source", "label_sources", "skipped_examples", "dry_run", "activations_synthetic",
    "valid_for_phase4_signal",
)


def label_diagnostics(meta, min_pos: int = 5) -> dict:
    """Class balance per gating label + missing-label count + low-positive warnings."""
    labelled = [m for m in meta if m.get("labels")]
    missing = len(meta) - len(labelled)
    balance, warnings = {}, []
    for k in DIAG_LABELS:
        pos = sum(1 for m in labelled if m["labels"].get(k))
        neg = len(labelled) - pos
        balance[k] = {"pos": pos, "neg": neg, "n": len(labelled)}
        if pos < min_pos:
            warnings.append(f"label '{k}' has only {pos} positives (< {min_pos})")
    return {"n_rows": len(meta), "n_labelled": len(labelled), "n_missing_labels": missing,
            "min_pos_threshold": min_pos, "balance": balance, "warnings": warnings}


def validate_saved_activations(npz_path, expected_n_layers=None) -> dict:
    """Reload the .npz and verify shape/alignment, finiteness, and non-degenerate variance."""
    d = np.load(npz_path, allow_pickle=True)
    X = d["X"]
    ids, arms, layers = d["ids"], d["arms"], d["layers"]
    checks = {"X_shape": list(X.shape), "n_layers": int(len(layers)),
              "d_model": int(X.shape[-1]) if X.ndim == 3 else None}
    ok = True
    issues = []
    if X.ndim != 3:
        ok = False; issues.append(f"X.ndim={X.ndim}, expected 3 [N, n_layers, d_model]")
    else:
        N, L, D = X.shape
        for name, val in (("len(ids)==N", len(ids) == N), ("len(arms)==N", len(arms) == N),
                          ("len(layers)==n_layers", len(layers) == L)):
            if not val:
                ok = False; issues.append(name + " FAILED")
        if expected_n_layers is not None and L != expected_n_layers:
            ok = False; issues.append(f"n_layers {L} != expected {expected_n_layers}")
        if X.size:
            if not np.isfinite(X).all():
                ok = False; issues.append("X contains NaN/inf")
            var_examples = float(X.var(axis=0).max()) if N > 1 else 0.0
            var_layers = float(X.var(axis=1).max()) if L > 1 else 0.0
            checks["max_variance_across_examples"] = var_examples
            checks["max_variance_across_layers"] = var_layers
            if N > 1 and var_examples <= 0.0:
                ok = False; issues.append("zero variance across examples (identical/zeroed features)")
            if L > 1 and var_layers <= 0.0:
                ok = False; issues.append("zero variance across layers")
    checks["ok"] = ok
    checks["issues"] = issues
    return checks


def assert_no_feature_leakage(manifest, meta) -> dict:
    """Explicit, recorded guarantees that probe features are ONLY pre-generation hidden states."""
    problems = []
    if manifest.get("features_from_answer_tokens") is not False:
        problems.append("features_from_answer_tokens must be False")
    if manifest.get("reads_answer_tokens") is not False:
        problems.append("reads_answer_tokens must be False")
    if manifest.get("feature_provenance") != "residual_stream_hidden_state":
        problems.append("feature_provenance must be residual_stream_hidden_state")
    for flag in ("contains_phase1_csr_scores", "contains_phonemic_12d_profile",
                 "contains_csr_trace_vector"):
        if manifest.get(flag) is not False:
            problems.append(f"{flag} must be False (no such probe features allowed)")
    for m in meta:
        if m.get("features_from_answer_tokens") is not False or m.get("token_position") != -1:
            problems.append(f"row {m.get('id')}/{m.get('arm')} has answer-token/position leak")
            break
    return {"answer_tokens_used_as_features": False, "answer_text_used_only_for_labels": True,
            "phase1_csr_scores_in_features": False, "phonemic_12d_in_features": False,
            "csr_trace_vector_in_features": False, "problems": problems, "ok": not problems}


def validate_manifest(manifest) -> list:
    """Return the list of missing required manifest fields (empty == valid)."""
    return [k for k in MANIFEST_REQUIRED if k not in manifest]


def resolve_layers(arg, n_hidden_states):
    """`all` -> every hidden-state index [0..n], else a comma list. n_hidden_states = n_layers+1
    (index 0 is the embedding output)."""
    if arg in (None, "", "all"):
        return list(range(n_hidden_states))
    return [int(x) for x in str(arg).split(",") if x.strip() != ""]


def load_label_index(traces_path):
    """Index saved Phase 2B traces by id -> {arm: {answer, scores}} for label building (no re-gen)."""
    blob = json.loads(Path(traces_path).read_text())
    tr = blob.get("traces")
    idx = {}
    rows_iter = []
    if isinstance(tr, dict):
        for _backend, rows in tr.items():
            rows_iter = rows
            break
    elif isinstance(tr, list):
        rows_iter = tr
    for r in rows_iter:
        idx[r["id"]] = {a: {"answer": (r.get("answers") or {}).get(a),
                            "scores": (r.get("scores") or {}).get(a)} for a in (r.get("answers") or {})}
    return idx


# ---- GPU model code (guarded; only runs on the pod) ----------------------------------------------


def load_model(model_id):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    here, parent = str(_HERE), str(_HERE.parent)
    saved = list(sys.path)
    sys.path[:] = [p for p in sys.path if p not in ("", here, parent)]   # avoid HF relative-import bug
    try:
        tok = AutoTokenizer.from_pretrained(model_id)
        try:                                                   # prefer accelerate sharding if present
            model = AutoModelForCausalLM.from_pretrained(
                model_id, torch_dtype="auto", device_map="auto", output_hidden_states=True)
        except (ValueError, ImportError):                      # no `accelerate`: plain single-device load
            dtype = torch.float16 if torch.cuda.is_available() else torch.float32
            model = AutoModelForCausalLM.from_pretrained(
                model_id, torch_dtype=dtype, output_hidden_states=True)
            if torch.cuda.is_available():
                model = model.to("cuda")
        model.eval()
        device = next(model.parameters()).device
        return tok, model, device
    finally:
        sys.path[:] = saved


def _encode(tok, prompt):
    if getattr(tok, "chat_template", None):
        msgs = [{"role": "user", "content": prompt}]
        try:
            enc = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt",
                                          return_dict=True)
        except TypeError:
            enc = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt")
    else:
        enc = tok(prompt, return_tensors="pt")
    if not hasattr(enc, "keys"):
        enc = {"input_ids": enc}
    return enc


def prompt_hidden_states(tok, model, device, prompt, layers=None):
    """([n_layers, d_model] residual-stream vectors at the FINAL prompt token, layer list, token info).
    No generation: a single forward pass over the prompt only."""
    import torch
    enc = _encode(tok, prompt)
    enc = {k: v.to(device) for k, v in enc.items() if hasattr(v, "to")}
    with torch.no_grad():
        out = model(**enc, output_hidden_states=True, use_cache=False)
    hs = out.hidden_states                                  # tuple len n_layers+1, each [1, seq, d]
    ids_seq = enc["input_ids"][0]
    last = int(ids_seq.shape[0]) - 1
    last_id = int(ids_seq[last].item())
    try:
        last_text = tok.decode([last_id])
    except Exception:
        last_text = None
    lyrs = resolve_layers("all", len(hs)) if layers is None else layers
    vec = np.stack([hs[l][0, last, :].float().cpu().numpy() for l in lyrs], 0)
    info = {"token_count": int(ids_seq.shape[0]), "last_token_id": last_id,
            "last_token_text": last_text}
    return vec, lyrs, info


def generate_answer(tok, model, device, prompt, max_new=400):
    import torch
    enc = _encode(tok, prompt)
    enc = {k: v.to(device) for k, v in enc.items() if hasattr(v, "to")}
    in_len = enc["input_ids"].shape[1]
    with torch.no_grad():
        out = model.generate(**enc, max_new_tokens=max_new, do_sample=False,
                             pad_token_id=(tok.eos_token_id or tok.pad_token_id or 0))
    return tok.decode(out[0][in_len:], skip_special_tokens=True).strip()


# ---- main ----------------------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(_DATA))
    ap.add_argument("--kb", default=str(EV._KB))
    ap.add_argument("--arms", default="base,framed")
    ap.add_argument("--layers", default="all", help="'all' or comma list, e.g. 0,8,16,24,32")
    ap.add_argument("--model", default=None, help="HF id/path (default env CSR_LLM_MODEL or Mistral)")
    ap.add_argument("--semantic-backend", default="real", choices=["real", "hashing", "lexical", "demo"])
    ap.add_argument("--traces", default=None, help="saved Phase 2B robustness JSON -> labels (no re-gen)")
    ap.add_argument("--generate", action="store_true", help="generate answers for labels if no --traces")
    ap.add_argument("--max-tokens", type=int, default=400)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out-dir", default="runs/csr_phase4")
    ap.add_argument("--dry-run", action="store_true",
                    help="CPU smoke: build prompts+metadata, write ZERO activations (no model)")
    args = ap.parse_args()

    import os
    model_id = args.model or os.environ.get("CSR_LLM_MODEL", "mistralai/Mistral-7B-Instruct-v0.3")
    rows = EF.load_data(args.data)
    if args.limit:
        rows = rows[: args.limit]
    arms = [a.strip() for a in args.arms.split(",") if a.strip()]
    kb = EV.load_kb(args.kb)
    adapter, provider, sem_info = EF.build_frame_adapter(args.semantic_backend, kb)
    label_idx = load_label_index(args.traces) if args.traces else {}

    tok = model = device = None
    layers = None
    tokenizer_name = "dry_run" if args.dry_run else None
    if not args.dry_run:
        print(f"[phase4] loading model {model_id} (GPU) …")
        tok, model, device = load_model(model_id)
        tokenizer_name = getattr(tok, "name_or_path", None) or model_id

    X, meta = [], []
    ri = 0
    skipped = 0
    n_total = len(rows) * len(arms)
    for ei, ex in enumerate(rows):
        if not args.dry_run and ei % 20 == 0:
            print(f"[phase4] {ri}/{n_total} rows ({ei}/{len(rows)} examples) …", flush=True)
        trace, terms = EF.frame_for(ex, adapter, provider)
        prompts = build_prompts(ex, trace)
        frame = frame_dict_from_trace(trace)
        fsumm = frame_summary_of(trace)
        alt = ex.get("expected_secondary_true_senses", [])
        false_claims = ex.get("false_claims", [])
        subj = (dominant_terms(ex["query"])[:1] or None)
        for arm in arms:
            prompt = prompts[arm]
            # ---- features: pre-generation hidden state at the final prompt token ----
            try:
                if args.dry_run:
                    lyrs = resolve_layers(args.layers, 3)        # tiny synthetic shape for smoke
                    vec = np.random.default_rng(ri).standard_normal((len(lyrs), 8)).astype(np.float32)
                    tok_info = {"token_count": len((prompt or "").split()), "last_token_id": -1,
                                "last_token_text": "<dry_run>"}
                else:
                    vec, lyrs, tok_info = prompt_hidden_states(
                        tok, model, device, prompt,
                        None if args.layers == "all" else [int(x) for x in args.layers.split(",")])
                    vec = vec.astype(np.float32)
            except Exception as e:                                # never silently mis-collect
                print(f"[phase4] SKIP {ex['id']}/{arm}: {type(e).__name__}: {e}")
                skipped += 1
                continue
            if layers is None:
                layers = lyrs
            elif list(lyrs) != list(layers):
                print(f"[phase4] SKIP {ex['id']}/{arm}: layer set changed {lyrs} != {layers}")
                skipped += 1
                continue
            # ---- label: from saved traces, else optional generation, else none ----
            answer, label_source, trace_src_id = None, "none", None
            if ex["id"] in label_idx and arm in label_idx[ex["id"]]:
                answer = label_idx[ex["id"]][arm].get("answer")
                label_source = "phase2b_traces"
                trace_src_id = ex["id"]
            elif args.generate and not args.dry_run:
                answer = generate_answer(tok, model, device, prompt, args.max_tokens)
                label_source = "generated_for_label_only"
            labels = (labels_from_audit(ex["query"], answer, frame, alt, false_claims, subj)
                      if answer is not None else None)
            X.append(vec)
            meta.append(build_metadata_row(
                ri, ex, arm, prompt, model_id, layers, labels, label_source,
                feature_dim=vec.shape[-1], prompt_token_count=tok_info["token_count"],
                final_prompt_token_id=tok_info["last_token_id"],
                final_prompt_token_text=tok_info["last_token_text"],
                frame_summary=fsumm, answer_trace_source_id=trace_src_id))
            ri += 1

    Xarr = np.stack(X, 0) if X else np.zeros((0, 0, 0), dtype=np.float32)   # [N, n_layers, d_model]
    outd = Path(args.out_dir)
    outd.mkdir(parents=True, exist_ok=True)
    npz_path = outd / "phase4_activations.npz"
    np.savez_compressed(npz_path, X=Xarr, layers=np.array(layers or [], dtype=int),
                        ids=np.array([m["id"] for m in meta], dtype=object),
                        arms=np.array([m["arm"] for m in meta], dtype=object))
    with (outd / "phase4_metadata.jsonl").open("w") as fh:
        for m in meta:
            fh.write(json.dumps(m) + "\n")

    # ---- diagnostics ----
    diag = label_diagnostics(meta)
    shape = validate_saved_activations(npz_path, expected_n_layers=len(layers or []))
    manifest = {
        "model_id": model_id, "tokenizer_name": tokenizer_name,
        "n_examples": len(meta), "arms": arms,
        "layers": list(layers or []), "n_layers": len(layers or []),
        "d_model": int(Xarr.shape[-1]) if Xarr.size else 0,
        "feature_dim": int(Xarr.shape[-1]) if Xarr.size else 0,
        "extraction_mode": EXTRACTION_MODE, "token_position": -1,
        "token_position_desc": "final_prompt_token",
        "reads_answer_tokens": False, "features_from_answer_tokens": False,
        "feature_provenance": "residual_stream_hidden_state",
        "contains_phase1_csr_scores": False, "contains_phonemic_12d_profile": False,
        "contains_csr_trace_vector": False,
        "prompt_hashes_present": sum(1 for m in meta if m.get("prompt_hash")),
        "semantic_frame_backend": sem_info, "dataset": str(args.data),
        "trace_source": (str(args.traces) if args.traces else
                         ("generated" if args.generate else "none")),
        "label_sources": sorted({m["label_source"] for m in meta}),
        "skipped_examples": int(skipped),
        "label_diagnostics": diag, "shape_diagnostics": shape,
        "dry_run": bool(args.dry_run),
        "activations_synthetic": bool(args.dry_run),
        "valid_for_phase4_signal": (not args.dry_run) and shape.get("ok", False),
    }
    leak = assert_no_feature_leakage(manifest, meta)
    manifest["leakage_diagnostics"] = leak
    missing = validate_manifest(manifest)
    manifest["manifest_complete"] = (not missing)
    (outd / "phase4_manifest.json").write_text(json.dumps(manifest, indent=2))
    (outd / "phase4_label_diagnostics.json").write_text(json.dumps(diag, indent=2))

    # ---- console summary ----
    print("=" * 80)
    print(f"[phase4] wrote X={Xarr.shape} + {len(meta)} metadata rows to {outd}  (skipped={skipped})")
    print(f"[phase4] model={model_id}  tokenizer={tokenizer_name}  "
          f"layers={len(layers or [])}  d_model={manifest['d_model']}")
    if args.dry_run:
        print("[phase4] ⚠️  DRY-RUN: activations are ZERO/synthetic — NOT VALID for Phase 4 signal.")
    print("[phase4] LABEL BALANCE:")
    for k, v in diag["balance"].items():
        print(f"     {k:22} pos={v['pos']:>4}  neg={v['neg']:>4}  n={v['n']}")
    print(f"     missing/empty labels: {diag['n_missing_labels']}")
    for w in diag["warnings"]:
        print(f"     ⚠️  {w}")
    print(f"[phase4] SHAPE OK={shape['ok']}  {shape.get('issues') or ''}")
    print(f"[phase4] LEAKAGE OK={leak['ok']}  {leak.get('problems') or ''}")
    print(f"[phase4] MANIFEST complete={not missing}  missing={missing}")
    print(f"[phase4] VALID_FOR_PHASE4_SIGNAL={manifest['valid_for_phase4_signal']}")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
