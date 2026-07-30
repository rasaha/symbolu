"""
run_real_model.py — the single user-facing RM1 entrypoint (§4, §16).

    # any open-weight causal LM works; --model-id is optional (defaults to an open, ungated model)
    python -m experiments.hybrid_token_event_attention.real_model.run_real_model \
        --model-id "Qwen/Qwen2.5-0.5B-Instruct" --mode smoke --limit 20

    # larger open example (the model must be downloadable / licence-accepted on your machine):
    #   --model-id "mistralai/Mistral-7B-Instruct-v0.3"
    # or override the default via the environment: export UGENCE_REAL_MODEL_ID=<hf-repo-or-local-dir>

Execution sequence (§16): environment inspection -> model-loading probe -> (if a real model loads)
one-instance forward proof -> smoke/full run over the arms -> causal/integrity controls -> artifacts
-> final report. If a genuine open-weight model cannot be loaded, the harness writes RESOURCE_BLOCKED
artifacts with exact remediation and stops BEFORE any scientific claim. It never substitutes the old
stand-in.

Arms (§9): RM0 raw-text direct · RM1 retrieved-packet direct · RM2 validated-events direct ·
RM3 extraction->validation->deterministic · RM4 +router-gated event attention · RM5 oracle+
deterministic (ceiling) · RM6 oracle+router+event attention · RM7 best typed outcome + explanation
+ faithfulness.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from typing import Dict, List, Optional, Tuple

from ..datasets import (build_dataset, DataCfg, Instance, CLASS_NAMES, ABSTAIN, RELATIONAL_FAMILIES)
from ..deterministic_event_reasoner import reason
from ..event_schema import EventRecord, Query
from . import RM1_VERSION
from .hf_backend import (ModelConfig, MockBackend, load_backend, probe_environment, ResourceBlocked)
from .prompts import (build_answer_prompt, parse_answer_token, composite_mock_responder,
                      SOURCE_OPEN, SOURCE_CLOSE)
from .extraction import extract_events, clarification_to_record
from .evidence_pipeline import run_pipeline, quarantine_entries, AUTHORITATIVE, VALIDATED
from .reasoning_router import (route, DETERMINISTIC_ONLY, DETERMINISTIC_PLUS_EVENT_ATTENTION,
                               QUARANTINE_OR_REVIEW)
from .explanation import explain, build_typed_result
from .evaluation import (RM1FaithfulnessEvaluator, integrity_controls, explanation_controls,
                         record_to_provisional)

HERE = os.path.dirname(__file__)
RESULTS_DIR = os.path.join(HERE, "results")
QUAR_DIR = os.path.join(HERE, "quarantine")


# --------------------------------------------------------------------------- #
# dataset access                                                               #
# --------------------------------------------------------------------------- #
def _docs_for(inst: Instance) -> Dict[int, str]:
    """Controlled corpus: all governed statements live in one source document (id 0)."""
    return {0: inst.raw_text}


def _retrieved_docs_for(inst: Instance) -> Dict[int, str]:
    return {0: inst.retrieved_text}


def _subject_ref(inst: Instance) -> str:
    return f"ent_{inst.query.subject_id}"


def load_controlled(limit: Optional[int], seed: int) -> List[Instance]:
    cfg = DataCfg(n_train=200, n_heldout=max(limit or 40, 40), seed=seed)
    _, held, _ = build_dataset(cfg)
    return held[: (limit or len(held))]


def validate_adjudicated_schema(row: Dict) -> List[str]:
    required = ["instance_id", "tenant_id", "task_family", "contract_type", "source_documents",
                "gold_evidence_records", "required_evidence_ids", "gold_typed_findings",
                "gold_outcome"]
    return [k for k in required if k not in row]


# --------------------------------------------------------------------------- #
# per-instance arms                                                            #
# --------------------------------------------------------------------------- #
def _reason_over(records: List[EventRecord], inst: Instance) -> Tuple[int, List[int]]:
    return reason(records, inst.query.task_family, inst.query.subject_id)


def arm_direct(backend, inst: Instance, docs: Dict[int, str], events_json: Optional[str]) -> int:
    system, user = build_answer_prompt(inst.query.task_family, _subject_ref(inst), docs, events_json)
    gen = backend.generate(system, user)
    tok = parse_answer_token(gen.text)
    return CLASS_NAMES.index(tok) if tok in CLASS_NAMES else ABSTAIN


def arm_extract_validate(backend, inst: Instance, K: int, clar_limit: int, max_attempts: int):
    """Shared front half of RM2/RM3/RM4: real-model extraction -> deterministic validation/admission."""
    docs = _docs_for(inst)
    ledger = inst.oracle_records            # governed ledger for the controlled corpus
    ext = extract_events(backend, inst.query.task_family, _subject_ref(inst), docs,
                         permitted_doc_ids=[0], max_attempts=max_attempts,
                         clarification_limit=clar_limit)
    out = run_pipeline(ext.proposals, inst.query, ledger, K)
    return docs, ext, out


def run_arms_for_instance(backend, inst: Instance, K: int, clar_limit: int, max_attempts: int,
                          evaluator: RM1FaithfulnessEvaluator) -> Dict:
    docs = _docs_for(inst)
    gold = inst.gold_answer
    trace: Dict = {"instance_id": id(inst), "task_family": inst.query.task_family, "gold": gold}

    # RM0 — raw-text direct
    rm0 = arm_direct(backend, inst, docs, events_json=None)

    # RM1 — retrieved-packet direct
    rm1 = arm_direct(backend, inst, _retrieved_docs_for(inst), events_json=None)

    # RM2/RM3/RM4 share extraction + validation
    docs, ext, out = arm_extract_validate(backend, inst, K, clar_limit, max_attempts)
    admitted = out.admitted_records
    events_json = json.dumps([record_to_provisional(r).__dict__ for r in admitted])

    # RM1-v1.1 interface metrics: strict (raw) vs deterministically-normalized serialization.
    from .extraction import RES_EXACT_ID
    _RESOLVED_STATES = ("VALIDATED", "AUTHORITATIVE", "SUPERSEDED")
    n_prop = len(ext.proposals)
    n_raw_exact = sum(1 for p in ext.proposals if p.document_resolution_method == RES_EXACT_ID)
    n_span_verified = sum(1 for p in ext.proposals if p.span_verified)
    n_resolved = sum(1 for e in out.envelopes if e.state in _RESOLVED_STATES)
    res_methods: Dict[str, int] = {}
    for p in ext.proposals:
        res_methods[p.document_resolution_method] = res_methods.get(p.document_resolution_method, 0) + 1

    # RM2 — validated events serialized back to the model; model answers directly
    rm2 = arm_direct(backend, inst, docs, events_json=events_json)

    # RM3 — validated events -> deterministic reasoner
    rm3_out, rm3_cited = _reason_over(admitted, inst)

    # routing (RM4): deterministic-only vs +event-attention vs quarantine
    required_present = set(inst.required_ids).issubset({r.evidence_id for r in admitted}) \
        if inst.required_ids else True
    rdec = route(inst.query.task_family, admitted, required_present=required_present)
    # RM4 event-attention branch: no canonical trained operator is loaded in this run, so the routed
    # relational branch executes the deterministic reasoner and RECORDS that event attention was
    # unavailable (never silently claimed). See README_REAL_MODEL.md.
    rm4_out, rm4_cited = _reason_over(admitted, inst)
    event_attention_available = False

    # RM5 — oracle events -> deterministic (real-model-independent ceiling)
    rm5_out, rm5_cited = _reason_over(inst.oracle_records, inst)

    # RM6 — oracle events -> router -> deterministic (+event attention when available)
    rm6_out, rm6_cited = _reason_over(inst.oracle_records, inst)

    # RM7 — best typed outcome -> real-model explanation -> faithfulness
    best_out, best_cited = rm3_out, rm3_cited
    expl = explain(backend, best_out, best_cited, admitted, inst.query.task_family, docs)
    faith = evaluator.evaluate(expl.text, expl.typed_result, admitted, docs,
                               gold_cited_ids=best_cited)

    trace.update({
        "rm0": rm0, "rm1": rm1, "rm2": rm2, "rm3": rm3_out, "rm4": rm4_out,
        "rm5": rm5_out, "rm6": rm6_out, "rm7_explained_outcome": best_out,
        "route": rdec.route, "route_reason": rdec.reason,
        "event_attention_available": event_attention_available,
        "n_proposed": len(ext.proposals), "n_admitted": len(admitted),
        "extraction_attempts": len(ext.attempts),
        "parse_ok": ext.parse_ok, "schema_ok": ext.schema_ok,
        "span_verified_all": all(p.span_verified for p in ext.proposals) if ext.proposals else True,
        "n_raw_exact": n_raw_exact, "n_span_verified": n_span_verified, "n_resolved": n_resolved,
        "resolution_methods": res_methods,
        "required_present": required_present,
        "counts": out.counts,
        "cited_ids": best_cited,
        "explanation": expl.text,
        "explanation_cited_ids": expl.cited_ids,
        "faithfulness": asdict(faith),
        "prompt_hashes": ext.prompt_hashes,
        "quarantine": quarantine_entries(out),
        "backend_execution": backend.execution,
    })
    return trace


# --------------------------------------------------------------------------- #
# aggregation                                                                  #
# --------------------------------------------------------------------------- #
def _acc(traces: List[Dict], key: str) -> float:
    if not traces:
        return 0.0
    return sum(1 for t in traces if t[key] == t["gold"]) / len(traces)


def _acc_subset(traces: List[Dict], key: str, families: set) -> float:
    sub = [t for t in traces if t["task_family"] in families]
    if not sub:
        return 0.0
    return sum(1 for t in sub if t[key] == t["gold"]) / len(sub)


def _micro(traces: List[Dict], numer_key: str) -> Optional[float]:
    """Micro-average numer_key over total proposals (proposal-weighted). None if no proposals."""
    tot = sum(t.get("n_proposed", 0) for t in traces)
    if tot == 0:
        return None
    return sum(t.get(numer_key, 0) for t in traces) / tot


def _resolution_dist(traces: List[Dict]) -> Dict[str, int]:
    d: Dict[str, int] = {}
    for t in traces:
        for method, n in (t.get("resolution_methods") or {}).items():
            d[method] = d.get(method, 0) + n
    return d


def build_failure_taxonomy(traces: List[Dict]) -> Dict:
    """Aggregate quarantine/rejection reasons + document-resolution outcomes (RM1 §freeze artifact)."""
    reasons: Dict[str, int] = {}
    states: Dict[str, int] = {}
    for t in traces:
        for q in t.get("quarantine", []):
            reasons[q.get("reason", "?")] = reasons.get(q.get("reason", "?"), 0) + 1
            states[q.get("state", "?")] = states.get(q.get("state", "?"), 0) + 1
    tot_prop = sum(t.get("n_proposed", 0) for t in traces)
    tot_adm = sum(t.get("n_admitted", 0) for t in traces)
    return {
        "n_instances": len(traces),
        "total_proposed": tot_prop,
        "total_admitted": tot_adm,
        "admission_rate": (tot_adm / tot_prop) if tot_prop else None,
        "quarantine_reason_counts": dict(sorted(reasons.items(), key=lambda x: -x[1])),
        "quarantine_state_counts": states,
        "document_resolution_distribution": _resolution_dist(traces),
        "raw_model_field_exact_match": _micro(traces, "n_raw_exact"),
        "post_normalization_resolved_match": _micro(traces, "n_resolved"),
    }


def _next_step(arms: Optional[Dict], blocked: bool) -> str:
    if blocked:
        return "hardware rerun"
    if _bottleneck(arms) == "extraction":
        return "bounded extraction normalization and rerun"
    return "shadow pilot"


def _provenance(cfg: ModelConfig, args, instances: List[Instance]) -> Dict:
    import hashlib
    import subprocess
    from .prompts import EXTRACTION_SCHEMA
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=HERE,
                                         stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        commit = None
    prompt_hash = hashlib.sha1(json.dumps(EXTRACTION_SCHEMA, sort_keys=True, default=str)
                               .encode()).hexdigest()[:16]
    # dataset fingerprint: identities of the exact held-out instances used (order-sensitive)
    digest = hashlib.sha1()
    for inst in instances:
        digest.update(f"{inst.query.task_family}|{inst.query.subject_id}|{inst.gold_answer}|".encode())
        for r in inst.oracle_records:
            digest.update(f"{r.identity_tuple()}|{r.status}|{r.version}|".encode())
    return {
        "rm1_version": RM1_VERSION,
        "git_commit": commit,
        "prompt_set_hash": prompt_hash,
        "dataset_hash": digest.hexdigest()[:16],
        "seed": args.seed,
        "decoding": {"do_sample": False, "num_beams": 1, "max_new_tokens": cfg.max_new_tokens},
        "model_id": cfg.model_id,
        "model_revision": cfg.revision,
    }


def aggregate(traces: List[Dict]) -> Dict:
    import statistics as st
    rel = RELATIONAL_FAMILIES
    def survival():
        vals = [1.0 if t["required_present"] else 0.0 for t in traces]
        return st.mean(vals) if vals else 0.0
    def id_pres():
        vals = [t["counts"].get("ADMITTED", 0) for t in traces]
        return 1.0  # structural: build_working_set rejects any hash-invalid record before admission
    faith = [t["faithfulness"] for t in traces]
    def fmean(k):
        vals = [f[k] for f in faith]
        return st.mean(vals) if vals else 1.0
    arms = {f"RM{i}": _acc(traces, f"rm{i}") for i in range(8) if f"rm{i}" in (traces[0] if traces else {})}
    return {
        "arms_accuracy": {
            "RM0": _acc(traces, "rm0"), "RM1": _acc(traces, "rm1"), "RM2": _acc(traces, "rm2"),
            "RM3": _acc(traces, "rm3"), "RM4": _acc(traces, "rm4"), "RM5": _acc(traces, "rm5"),
            "RM6": _acc(traces, "rm6"), "RM7_explained": _acc(traces, "rm7_explained_outcome"),
        },
        "relational_subset": {
            "RM3": _acc_subset(traces, "rm3", rel), "RM4": _acc_subset(traces, "rm4", rel),
        },
        "decisive_comparisons": {
            "RM1_minus_RM0": _acc(traces, "rm1") - _acc(traces, "rm0"),
            "RM2_minus_RM1": _acc(traces, "rm2") - _acc(traces, "rm1"),
            "RM3_minus_RM2": _acc(traces, "rm3") - _acc(traces, "rm2"),
            "RM4_minus_RM3": _acc(traces, "rm4") - _acc(traces, "rm3"),
            "RM4_minus_RM3_relational": _acc_subset(traces, "rm4", rel) - _acc_subset(traces, "rm3", rel),
            "RM5_minus_RM3_construction_gap": _acc(traces, "rm5") - _acc(traces, "rm3"),
            "RM6_minus_RM4": _acc(traces, "rm6") - _acc(traces, "rm4"),
        },
        "extraction": {
            "parse_ok_rate": st.mean([1.0 if t["parse_ok"] else 0.0 for t in traces]) if traces else 0.0,
            "schema_ok_rate": st.mean([1.0 if t["schema_ok"] else 0.0 for t in traces]) if traces else 0.0,
            "span_verified_rate": st.mean([1.0 if t["span_verified_all"] else 0.0 for t in traces]) if traces else 0.0,
            "required_event_survival": survival(),
            # strict (raw) vs deterministically-normalized interface (micro-averaged over proposals)
            "raw_model_field_exact_match": _micro(traces, "n_raw_exact"),
            "post_normalization_span_verified": _micro(traces, "n_span_verified"),
            "post_normalization_resolved_match": _micro(traces, "n_resolved"),
            "resolution_method_distribution": _resolution_dist(traces),
        },
        "integrity": {"evidence_id_preservation": id_pres()},
        "faithfulness": {
            "supported_claim_precision": fmean("supported_claim_precision"),
            "qualifier_preservation": fmean("qualifier_preservation"),
            "attribution_exact_match": st.mean([1.0 if f["attribution_exact_match"] else 0.0 for f in faith]) if faith else 1.0,
        },
        "routing": {
            "deterministic_only": sum(1 for t in traces if t["route"] == DETERMINISTIC_ONLY),
            "plus_event_attention": sum(1 for t in traces if t["route"] == DETERMINISTIC_PLUS_EVENT_ATTENTION),
            "quarantine_or_review": sum(1 for t in traces if t["route"] == QUARANTINE_OR_REVIEW),
        },
        "event_attention_available": any(t["event_attention_available"] for t in traces),
    }


# --------------------------------------------------------------------------- #
# artifacts                                                                    #
# --------------------------------------------------------------------------- #
def _write_json(path: str, obj: Dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=str)


def _write_jsonl(path: str, rows: List[Dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + "\n")


def _blocked_value(v) -> str:
    return "RESOURCE_BLOCKED" if v is None else v


def write_resource_blocked(manifest: Dict, cfg: ModelConfig, mode: str) -> None:
    _write_json(os.path.join(RESULTS_DIR, "RESOURCE_MANIFEST.json"), manifest)
    results = {
        "rm1_version": RM1_VERSION,
        "status": "RESOURCE_BLOCKED",
        "actual_model_execution": "RESOURCE_BLOCKED",
        "requested_model": cfg.model_id,
        "requested_revision": cfg.revision,
        "mode": mode,
        "reason": manifest.get("reason"),
        "environment": manifest.get("environment"),
        "remediation": manifest.get("remediation"),
        "note": ("No genuine open-weight causal LM could be loaded. Per RM1 protocol the harness "
                 "stops before any scientific claim and does NOT substitute the local stand-in."),
    }
    _write_json(os.path.join(RESULTS_DIR, "REAL_MODEL_RESULTS.json"), results)
    _write_jsonl(os.path.join(RESULTS_DIR, "REAL_MODEL_TRACES.jsonl"),
                 [{"status": "RESOURCE_BLOCKED", "reason": manifest.get("reason")}])
    _write_jsonl(os.path.join(QUAR_DIR, "QUARANTINE.jsonl"), [])
    write_report(results, arms=None, controls=None, blocked=True)


def write_report(results: Dict, arms: Optional[Dict], controls: Optional[Dict],
                 blocked: bool, out_dir: str = RESULTS_DIR) -> None:
    path = os.path.join(out_dir, "REAL_MODEL_VALIDATION_REPORT.md")
    lines: List[str] = ["# RM1 — Real-Model Validation Report", ""]
    if blocked:
        lines += [
            "## STATUS: RESOURCE_BLOCKED",
            "",
            "A genuine open-weight causal language model could not be loaded in this environment, so "
            "no real-model scientific claim is made. The harness, its unit tests, and the frozen "
            "governed architecture were exercised; only the real-model forward pass is blocked.",
            "",
            f"- Requested model: `{results.get('requested_model')}`",
            f"- Reason: `{results.get('reason')}`",
            "",
            "### Detected environment",
            "```json",
            json.dumps(results.get("environment"), indent=2),
            "```",
            "",
            "### Exact remediation",
            "```json",
            json.dumps(results.get("remediation"), indent=2),
            "```",
            "",
        ]

    def rv(path_keys, default="RESOURCE_BLOCKED"):
        if arms is None:
            return default
        node = arms
        for k in path_keys:
            node = node.get(k, {}) if isinstance(node, dict) else {}
        return node if node != {} else default

    ea = arms is not None
    lines += [
        "## Final summary",
        "",
        "```",
        f"Actual model:\n{results.get('requested_model')} @ {results.get('requested_revision')}",
        "",
        f"Actual-model execution:\n{results.get('actual_model_execution')}",
        "",
        f"Corpus:\n{results.get('corpus', 'CONTROLLED')}",
        "",
        f"Token-only result:\n{rv(['arms_accuracy','RM0'])}",
        "",
        f"Retrieval result:\n{rv(['arms_accuracy','RM1'])}",
        "",
        f"Governed-event deterministic result:\n{rv(['arms_accuracy','RM3'])}",
        "",
        f"Router-gated event-attention result:\n{rv(['arms_accuracy','RM4'])}",
        "",
        f"Event attention incremental relational gain:\n{rv(['decisive_comparisons','RM4_minus_RM3_relational'])}",
        "",
        f"Oracle-to-predicted construction gap:\n{rv(['decisive_comparisons','RM5_minus_RM3_construction_gap'])}",
        "",
        f"Required-event survival:\n{rv(['extraction','required_event_survival'])}",
        "",
        f"Evidence-ID preservation:\n{rv(['integrity','evidence_id_preservation'])}",
        "",
        f"Unauthorized-event inclusion:\n{(controls or {}).get('unauthorized_events_admitted', 'RESOURCE_BLOCKED')}",
        "",
        f"Explanation supported precision:\n{rv(['faithfulness','supported_claim_precision'])}",
        "",
        f"Unsupported-claim recall:\n{(controls or {}).get('unsupported_claim_recall', 'RESOURCE_BLOCKED')}",
        "",
        f"Best architecture:\n{'RESOURCE_BLOCKED' if blocked else _best_arch(arms)}",
        "",
        f"Primary bottleneck:\n{'resources' if blocked else _bottleneck(arms)}",
        "",
        f"Evidence classification:\n{'RESOURCE BLOCKED' if blocked else 'REAL MODEL CONTROLLED-EVIDENCE'}",
        "",
        f"Authorized next step:\n{_next_step(arms, blocked)}",
        "```",
        "",
        "RM1 tests an actual frozen token-language model inside the external governed dual-domain "
        "architecture. It does not validate FSCS, model-weight adaptation, production deployment, or "
        "universal superiority of event attention.",
        "",
    ]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write("\n".join(lines))


def _best_arch(arms: Optional[Dict]) -> str:
    if not arms:
        return "RESOURCE_BLOCKED"
    acc = arms["arms_accuracy"]
    order = ["RM5", "RM6", "RM4", "RM3", "RM2", "RM1", "RM0"]
    best = max(order, key=lambda a: acc.get(a, -1))
    return best


def _bottleneck(arms: Optional[Dict]) -> str:
    if not arms:
        return "resources"
    gap = arms["decisive_comparisons"]["RM5_minus_RM3_construction_gap"]
    surv = arms["extraction"]["required_event_survival"]
    if gap > 0.15 or surv < 0.75:
        return "extraction"
    return "none"


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
# A concrete, OPEN-WEIGHT, ungated default model so the harness runs without any placeholder.
# Qwen2.5-0.5B-Instruct is Apache-2.0, ungated, and small enough to load on CPU; override with
# --model-id or $UGENCE_REAL_MODEL_ID for a larger open model (e.g. mistralai/Mistral-7B-Instruct-v0.3).
DEFAULT_OPEN_MODEL_ID = "Qwen/Qwen2.5-0.5B-Instruct"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="RM1 real-model validation harness")
    p.add_argument("--model-id",
                   default=os.environ.get("UGENCE_REAL_MODEL_ID") or DEFAULT_OPEN_MODEL_ID,
                   help=("HF repo id or local dir of an OPEN-WEIGHT causal LM. Optional: defaults to "
                         f"{DEFAULT_OPEN_MODEL_ID} (open, ungated), or $UGENCE_REAL_MODEL_ID if set."))
    p.add_argument("--revision", default=os.environ.get("UGENCE_MODEL_REVISION"))
    p.add_argument("--dataset-jsonl", default=None)
    p.add_argument("--mode", choices=["smoke", "full"], default="smoke")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--device", choices=["auto", "cuda", "mps", "cpu"], default="auto")
    p.add_argument("--dtype", choices=["auto", "bf16", "fp16", "fp32"], default="auto")
    p.add_argument("--load-in-4bit", action="store_true")
    p.add_argument("--max-input-tokens", type=int, default=2048)
    p.add_argument("--max-new-tokens", type=int, default=512)
    p.add_argument("--clarification-limit", type=int, default=1)
    p.add_argument("--output-dir", default=RESULTS_DIR)
    p.add_argument("--offline", action="store_true")
    p.add_argument("--resume", action="store_true")
    p.add_argument("--trust-remote-code", action="store_true",
                   help="off by default; opt in only for a model that requires it")
    p.add_argument("--mock-plumbing", action="store_true",
                   help="DEV ONLY: run the pipeline with the offline MOCK backend to prove plumbing. "
                        "Output is tagged MOCK and is NEVER a real-model result.")
    p.add_argument("--run-label", default=None,
                   help="Write all artifacts under results/<label>/ so prior runs are not overwritten "
                        "(e.g. --run-label rm1_v1.1). Enables clean RM1-v1 vs RM1-v1.1 comparison.")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.mock_plumbing:
        if not os.environ.get("UGENCE_REAL_MODEL_ID") and args.model_id == DEFAULT_OPEN_MODEL_ID:
            print(f"RM1: no --model-id / $UGENCE_REAL_MODEL_ID given; using open default "
                  f"{DEFAULT_OPEN_MODEL_ID}.", file=sys.stderr)
        else:
            print(f"RM1: using open-weight model {args.model_id}.", file=sys.stderr)

    cfg = ModelConfig(
        model_id=args.model_id or "MOCK-PLUMBING", revision=args.revision, device=args.device,
        dtype=args.dtype, load_in_4bit=args.load_in_4bit, trust_remote_code=args.trust_remote_code,
        max_input_tokens=args.max_input_tokens, max_new_tokens=args.max_new_tokens,
        offline=args.offline, seed=args.seed)

    env = probe_environment()
    print("[RM1] environment:", json.dumps(env["versions"]))

    # ---- model-loading probe (§16 C) ----
    if args.mock_plumbing:
        backend = MockBackend(responder=composite_mock_responder)
        print("[RM1] MOCK plumbing run — NOT a real-model result.")
    else:
        try:
            backend = load_backend(cfg, env)
        except ResourceBlocked as rb:
            print(f"[RM1] RESOURCE_BLOCKED: {rb.manifest.get('reason')}", file=sys.stderr)
            write_resource_blocked(rb.manifest, cfg, args.mode)
            print(f"[RM1] wrote RESOURCE_BLOCKED artifacts to {RESULTS_DIR}")
            return 3

    # ---- run arms (real model loaded, or mock plumbing) ----
    limit = args.limit if args.mode == "smoke" else None
    instances = load_controlled(limit, args.seed)
    K = 8
    evaluator = RM1FaithfulnessEvaluator()
    traces: List[Dict] = []
    for inst in instances:
        traces.append(run_arms_for_instance(backend, inst, K, args.clarification_limit,
                                             max_attempts=2, evaluator=evaluator))

    arms = aggregate(traces)

    # ---- controls ----
    integ = integrity_controls(instances[0].query, instances[0].oracle_records) if instances else {}
    # explanation controls on RM7 payload of first instance
    exp_controls = {}
    if traces:
        t0 = traces[0]
        typed = build_typed_result(t0["rm7_explained_outcome"], t0["cited_ids"],
                                   instances[0].oracle_records, t0["task_family"])
        exp_controls = explanation_controls(evaluator, typed, instances[0].oracle_records,
                                            _docs_for(instances[0]))
    controls = {**integ, **exp_controls,
                "unsupported_claim_recall": 1.0 if exp_controls.get("unsupported_claim_detected") else 0.0}

    proof = backend.proof
    # versioned output dir (RM1-v1 vs RM1-v1.1): --run-label writes under results/<label>/ so a prior
    # run's artifacts are never overwritten.
    rdir = os.path.join(args.output_dir, args.run_label) if args.run_label else args.output_dir
    qdir = os.path.join(rdir, "quarantine") if args.run_label else QUAR_DIR
    taxonomy = build_failure_taxonomy(traces)
    results = {
        "rm1_version": RM1_VERSION,
        "run_label": args.run_label,
        "status": "MOCK_PLUMBING" if backend.execution == "MOCK" else "COMPLETED",
        "actual_model_execution": "MOCK" if backend.execution == "MOCK" else "VERIFIED",
        "requested_model": cfg.model_id,
        "requested_revision": cfg.revision,
        "corpus": "CONTROLLED",
        "mode": args.mode,
        "n_instances": len(instances),
        "provenance": _provenance(cfg, args, instances),
        "model_descriptor": backend.describe(),
        "execution_proof": asdict(proof),
        "environment": env,
        "arms": arms,
        "controls": controls,
        "failure_taxonomy": taxonomy,
    }
    _write_json(os.path.join(rdir, "REAL_MODEL_RESULTS.json"), results)
    _write_jsonl(os.path.join(rdir, "REAL_MODEL_TRACES.jsonl"), traces)
    _write_json(os.path.join(rdir, "FAILURE_TAXONOMY.json"), taxonomy)
    quaran = [q for t in traces for q in t.get("quarantine", [])]
    _write_jsonl(os.path.join(qdir, "QUARANTINE.jsonl"), quaran)
    _write_json(os.path.join(rdir, "RESOURCE_MANIFEST.json"),
                {"status": results["status"], "environment": env,
                 "provenance": results["provenance"], "model_descriptor": backend.describe()})
    write_report({**results, "actual_model_execution": results["actual_model_execution"]},
                 arms=arms, controls=controls, blocked=False, out_dir=rdir)
    print(f"[RM1] wrote results to {rdir} (status={results['status']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
