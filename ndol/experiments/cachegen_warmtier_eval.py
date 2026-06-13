"""Warm-tier KV-reuse head-to-head: KVPro vs CacheGen (and a bf16 cold baseline).

Implements `docs/KVPRO_VS_CACHEGEN_WARMTIER_PROTOCOL.md`. The production motion is:

    prefill a long shared prefix ONCE -> compress (KVPro | CacheGen) -> store
    (CPU DRAM | NVMe) -> evict from HBM -> later: reload + reattach -> answer queries

This module measures, per arm, the SYSTEMS axis (bytes/token stored, reload time,
TTFT-with-reuse vs cold recompute, transfer volume, p95/p99) with quality as a
SANITY check (hard-needle/needle after store->reload->reuse). It applies the
pre-registered iso-bytes decision rule (RELIABILITY-EDGE / DOMINATED / PARITY).

Design (mirrors openai_kv_eval): workload-gen + metrics + verdict + the Phase-0
roundtrip checker are pure-stdlib and CPU-testable via a MOCK backend. The two
real backends run on the pod and are wired behind `build_backend` — they are
deliberate integration points, NOT faked here:

  * KVPro       — snapshot packed-KV + 5 sidecars to disk (extend the TIER5A
                  byte-clean CPU swap to NVMe), reload, continue. Phase-0 gates it.
  * CacheGen    — LMCache connector with CacheGen enabled; sweep its quality level
                  to match KVPro's bytes (iso-bytes) AND report its default.

A "backend" is just a dict of four callables so the harness is transport-agnostic:
  prefill_store(prefix_text)        -> (handle, meta{n_tokens,bytes_stored,encode_s,decode_s,transfer_bytes})
  reload_query(handle, query_dict)  -> (output_text, {ttft_s, ...})        # store->reload path
  resident_query(prefix, query_dict)-> (output_text, {...})                # SAME codec, no eviction (Phase-0 ref)
  cold_query(prefix, query_dict)    -> (output_text, {ttft_s})             # recompute, no reuse (TTFT baseline)
"""
from __future__ import annotations

import argparse
import json
import random
import re
import statistics
import sys
from typing import Callable, Optional

from ndol.experiments.openai_kv_eval import _filler, _hit

_TAG_Q = re.compile(r"what is the (\w+) code")
_CODE_IN_PREFIX = re.compile(r"The (\w+) code is (\d+)\.")
_TAGS = ["RED", "BLUE", "GREEN", "AMBER", "SILVER"]


# ------------------------------- workload ---------------------------------- #
def make_reuse_workload(n_prefixes: int = 4, queries_per_prefix: int = 5,
                        ctx_sentences: int = 120, n_hard: int = 2, seed: int = 0) -> list[dict]:
    """Each prefix is a long shared context with several planted coded facts; each
    query reuses that prefix and asks for one code by attribute. The first `n_hard`
    queries are labelled hard_needle (targets planted early, more distractors between
    fact and query — where cheap/lossy codec noise bites); the rest are needle."""
    rng = random.Random(seed)
    work = []
    for i in range(n_prefixes):
        tags = list(_TAGS)
        rng.shuffle(tags)
        codes = {t: rng.randint(10000, 99999) for t in tags}
        chunks = []
        for t in tags:
            chunks.append(_filler(rng, max(1, ctx_sentences // len(tags))))
            chunks.append(f"The {t} code is {codes[t]}.")
        prefix = " ".join(chunks)
        # hard queries target the EARLIEST-planted tags (longest fact->query distance)
        order = tags
        queries = []
        for j in range(queries_per_prefix):
            kind = "hard_needle" if j < n_hard else "needle"
            t = order[j % len(order)] if kind == "hard_needle" else rng.choice(tags)
            queries.append({"id": f"p{i}_q{j}", "kind": kind, "answer": str(codes[t]),
                            "prompt": f"Question: what is the {t} code? Reply with only the number."})
        work.append({"id": f"prefix_{i}", "prefix": prefix, "queries": queries})
    return work


# ---------------------------- orchestration -------------------------------- #
def run_warmtier_arm(workload: list[dict], *, arm: str, backend: dict, with_cold: bool = True) -> dict:
    """Drive the reuse motion through one backend; collect store + query records."""
    prefill_store = backend["prefill_store"]
    reload_query = backend["reload_query"]
    cold_query = backend.get("cold_query") if with_cold else None
    store_recs, query_recs = [], []
    for pf in workload:
        handle, meta = prefill_store(pf["prefix"])
        store_recs.append({"arm": arm, "prefix_id": pf["id"],
                           "n_tokens": meta["n_tokens"], "bytes_stored": meta["bytes_stored"],
                           "encode_s": meta.get("encode_s", 0.0), "decode_s": meta.get("decode_s", 0.0),
                           "transfer_bytes": meta.get("transfer_bytes", meta["bytes_stored"])})
        for q in pf["queries"]:
            out, qm = reload_query(handle, q)
            rec = {"arm": arm, "prefix_id": pf["id"], "query_id": q["id"], "kind": q["kind"],
                   "answer": q["answer"], "output": out, "ttft_warm_s": qm["ttft_s"]}
            if cold_query is not None:
                _, cm = cold_query(pf["prefix"], q)
                rec["ttft_cold_s"] = cm["ttft_s"]
            query_recs.append(rec)
    return {"store": store_recs, "query": query_recs}


def roundtrip_clean(workload: list[dict], *, backend: dict) -> dict:
    """Phase-0 feasibility gate: is the store->evict->reload path byte-faithful?
    Compares the store->reload answer against the SAME codec with KV kept resident
    (no eviction). For a correctly-serializing codec (KVPro target, per TIER5A) these
    are identical; a divergence flags storage-path corruption -> INTEGRATION-BLOCKED."""
    prefill_store, reload_query = backend["prefill_store"], backend["reload_query"]
    resident_query = backend["resident_query"]
    rows = []
    for pf in workload:
        handle, _ = prefill_store(pf["prefix"])
        for q in pf["queries"]:
            warm, _ = reload_query(handle, q)
            ref, _ = resident_query(pf["prefix"], q)
            rows.append({"prefix_id": pf["id"], "query_id": q["id"], "identical": warm == ref})
    n_id = sum(r["identical"] for r in rows)
    return {"clean": n_id == len(rows), "n": len(rows), "n_identical": n_id, "rows": rows}


# ------------------------------- metrics ----------------------------------- #
def _pct(xs: list[float], p: float) -> float:
    if not xs:
        return float("nan")
    s = sorted(xs)
    k = (len(s) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def summarize_arm(arm_out: dict, label: Optional[str] = None) -> dict:
    store, query = arm_out["store"], arm_out["query"]
    tot_tok = sum(s["n_tokens"] for s in store) or 1
    warm = [q["ttft_warm_s"] for q in query]
    out = {
        "label": label or (store[0]["arm"] if store else "?"),
        "n_prefixes": len(store), "n_queries": len(query),
        "bytes_per_token": sum(s["bytes_stored"] for s in store) / tot_tok,
        "transfer_bytes_per_token": sum(s["transfer_bytes"] for s in store) / tot_tok,
        "reload_s_per_1k": 1000.0 * sum(s["decode_s"] for s in store) / tot_tok,
        "ttft_warm_p50": _pct(warm, 50), "ttft_warm_p95": _pct(warm, 95), "ttft_warm_p99": _pct(warm, 99),
    }
    cold = [q["ttft_cold_s"] for q in query if "ttft_cold_s" in q]
    if cold and warm and statistics.mean(warm) > 0:
        out["ttft_speedup_vs_cold"] = statistics.mean(cold) / statistics.mean(warm)
    for k in ("needle", "hard_needle"):
        sub = [q for q in query if q["kind"] == k]
        out[k] = (sum(_hit(q) for q in sub) / len(sub)) if sub else float("nan")
    return out


# ----------------------------- comparison ---------------------------------- #
def _kvpro_key(arms: dict) -> Optional[str]:
    return next((k for k in arms if "kvpro" in k.lower() or "int4_prot" in k.lower()), None)


def _iso_cachegen_key(arms: dict, kvpro_key: str) -> Optional[str]:
    target = arms[kvpro_key]["bytes_per_token"]
    cands = {k: v for k, v in arms.items() if "cachegen" in k.lower() or "cgen" in k.lower()}
    if not cands:
        return None
    return min(cands, key=lambda k: abs(cands[k]["bytes_per_token"] - target))


def verdict(arms: dict, roundtrip: Optional[dict] = None) -> str:
    """Pre-registered iso-bytes decision rule (QUALITY tail + bytes + reload)."""
    if roundtrip is not None and not roundtrip.get("clean", True):
        return ("INTEGRATION-BLOCKED: KVPro store->reload is not byte-faithful "
                f"({roundtrip['n_identical']}/{roundtrip['n']} identical) → warm-tier pillar is "
                "blocked on engineering, not measured down. Fix serialization before comparing.")
    kv = _kvpro_key(arms)
    if not kv:
        return "need a KVPro arm to decide"
    iso = _iso_cachegen_key(arms, kv)
    if not iso:
        return "need a CacheGen arm to decide"
    d = arms[kv]["hard_needle"] - arms[iso]["hard_needle"]
    kvb, cgb = arms[kv]["bytes_per_token"], arms[iso]["bytes_per_token"]
    kvr, cgr = arms[kv]["reload_s_per_1k"], arms[iso]["reload_s_per_1k"]
    if d >= 0.05:
        return (f"RELIABILITY-EDGE: KVPro hard-needle +{d:.2f} over CacheGen@iso-bytes ({iso}) — "
                "tail-safe warm-tier reuse is the claim; state the byte/reload trade honestly.")
    if d <= -0.05:
        return (f"CacheGen ahead on hard-needle (+{-d:.2f}) at iso-bytes → with its transport "
                "advantage this leans DOMINATED; KVPro is not the warm-tier codec.")
    # quality parity at iso-bytes → decide on bytes + reload
    if cgb <= kvb and cgr <= kvr:
        return ("DOMINATED: CacheGen matches hard-tail quality at ≤ bytes and ≤ reload → KVPro has "
                "no warm-tier role; cut the reliability-layer pillar (record as a durable negative).")
    return ("PARITY/MIXED: comparable hard-tail quality; differentiate on integration (vLLM-native) "
            "+ the hot-tier QUALITY-EDGE, not warm-tier codec superiority.")


# ------------------------------- backends ---------------------------------- #
def _parse_codes(prefix: str) -> dict:
    return {m.group(1): m.group(2) for m in _CODE_IN_PREFIX.finditer(prefix)}


def _queried_tag(prompt: str) -> Optional[str]:
    m = _TAG_Q.search(prompt)
    return m.group(1) if m else None


def make_mock_backend(*, bytes_per_token: float = 8.9, hard_quality: float = 1.0,
                      ttft_warm_s: float = 0.05, ttft_cold_s: float = 0.5,
                      reload_s: float = 0.01, encode_s: float = 0.02,
                      corrupt_reload: bool = False, seed: int = 0) -> dict:
    """In-process backend for CPU tests / smoke. `hard_quality` simulates a lossy
    codec dropping the hard tail (CacheGen-like); `corrupt_reload` simulates a broken
    serialization path to exercise the INTEGRATION-BLOCKED branch of Phase-0."""
    rng = random.Random(seed)

    def _answer(codes: dict, q: dict, degrade: bool) -> str:
        true = codes.get(_queried_tag(q["prompt"]), "")
        if degrade and q["kind"] == "hard_needle" and rng.random() > hard_quality:
            return "00000"          # lossy-codec tail miss
        return true

    def prefill_store(prefix: str):
        ntok = max(1, len(prefix.split()))
        handle = {"codes": _parse_codes(prefix)}
        meta = {"n_tokens": ntok, "bytes_stored": bytes_per_token * ntok,
                "encode_s": encode_s, "decode_s": reload_s, "transfer_bytes": bytes_per_token * ntok}
        return handle, meta

    def reload_query(handle, q):
        if corrupt_reload:
            return "99999", {"ttft_s": ttft_warm_s}      # storage-path corruption
        return _answer(handle["codes"], q, degrade=True), {"ttft_s": ttft_warm_s}

    def resident_query(prefix, q):                        # same codec, no eviction (Phase-0 ref)
        return _answer(_parse_codes(prefix), q, degrade=True), {}

    def cold_query(prefix, q):                            # recompute, no reuse
        return _parse_codes(prefix).get(_queried_tag(q["prompt"]), ""), {"ttft_s": ttft_cold_s}

    return {"prefill_store": prefill_store, "reload_query": reload_query,
            "resident_query": resident_query, "cold_query": cold_query}


def build_backend(name: str, **opts) -> dict:
    """Factory. `mock` is in-process (CPU). `cachegen` / `bf16` / `kvpro` delegate to
    the pod adapters in `warmtier_backends` (need a live server; see the protocol
    §Wiring). `kvpro` defaults to the NVMe-snapshot path (the Phase-0 item, not yet
    built → raises); pass `mode=apc` for HOT prefix-reuse quality/TTFT today."""
    if name == "mock":
        return make_mock_backend(**opts)
    if name in ("cachegen", "bf16", "kvpro"):
        from ndol.experiments import warmtier_backends as wb
        if name == "cachegen":
            return wb.cachegen_backend(**opts)
        if name == "bf16":
            return wb.bf16_cold_backend(**opts)
        mode = opts.pop("mode", "snapshot")
        return wb.kvpro_apc_backend(**opts) if mode == "apc" else wb.kvpro_snapshot_backend(**opts)
    raise ValueError(f"unknown backend: {name}")


# ----------------------------------- CLI ----------------------------------- #
def _add_workload_args(p):
    p.add_argument("--n-prefixes", type=int, default=4)
    p.add_argument("--queries-per-prefix", type=int, default=5)
    p.add_argument("--ctx-sentences", type=int, default=120)
    p.add_argument("--n-hard", type=int, default=2)
    p.add_argument("--seed", type=int, default=0)


def _coerce(v: str):
    for cast in (int, float):
        try:
            return cast(v)
        except ValueError:
            pass
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    return v


def _backend_opts(args) -> dict:
    """Mock-tuning flags + generic --opt KEY=VAL passthrough (for the pod backends:
    base_url=..., model=..., disk_dir=..., cold_base_url=..., mode=apc, ...)."""
    opts = {k: v for k, v in (("bytes_per_token", getattr(args, "bytes_per_token", None)),
                              ("hard_quality", getattr(args, "hard_quality", None)),
                              ("corrupt_reload", getattr(args, "corrupt_reload", None))) if v is not None}
    for kv in getattr(args, "opt", None) or []:
        if "=" not in kv:
            raise SystemExit(f"--opt expects KEY=VAL, got {kv!r}")
        k, v = kv.split("=", 1)
        opts[k] = _coerce(v)
    return opts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="KVPro vs CacheGen warm-tier KV-reuse head-to-head")
    sub = ap.add_subparsers(dest="cmd", required=True)

    rt = sub.add_parser("roundtrip", help="Phase-0 feasibility gate: is store->reload byte-faithful?")
    rt.add_argument("--backend", default="mock")
    rt.add_argument("--bytes-per-token", type=float)
    rt.add_argument("--corrupt-reload", action="store_true")
    rt.add_argument("--opt", action="append", help="backend KEY=VAL (e.g. base_url=..., model=...)")
    _add_workload_args(rt)

    r = sub.add_parser("run", help="run the reuse workload through one backend; write its summary")
    r.add_argument("--backend", required=True, help="mock | kvpro | cachegen | bf16")
    r.add_argument("--arm", required=True, help="arm label, e.g. kvpro / cachegen_iso / cachegen_default / bf16")
    r.add_argument("--out", required=True)
    r.add_argument("--bytes-per-token", type=float)
    r.add_argument("--hard-quality", type=float)
    r.add_argument("--no-cold", action="store_true")
    r.add_argument("--opt", action="append", help="backend KEY=VAL (e.g. base_url=..., model=..., mode=apc)")
    _add_workload_args(r)

    c = sub.add_parser("compare", help="compare arm summaries; print table + iso-bytes verdict")
    c.add_argument("--arms", required=True, help="comma list of summary json files")
    c.add_argument("--roundtrip", help="optional roundtrip json (gates INTEGRATION-BLOCKED)")

    args = ap.parse_args(argv)
    wl = lambda: make_reuse_workload(args.n_prefixes, args.queries_per_prefix,
                                     args.ctx_sentences, args.n_hard, args.seed)

    if args.cmd == "roundtrip":
        be = build_backend(args.backend, **_backend_opts(args))
        res = roundtrip_clean(wl(), backend=be)
        print(f"[roundtrip:{args.backend}] clean={res['clean']} "
              f"({res['n_identical']}/{res['n']} identical)")
        return 0 if res["clean"] else 1

    if args.cmd == "run":
        be = build_backend(args.backend, **_backend_opts(args))
        arm_out = run_warmtier_arm(wl(), arm=args.arm, backend=be, with_cold=not args.no_cold)
        s = summarize_arm(arm_out, label=args.arm)
        with open(args.out, "w") as fh:
            json.dump(s, fh, indent=2)
        sp = s.get("ttft_speedup_vs_cold", float("nan"))
        print(f"[{args.arm}] bytes/tok={s['bytes_per_token']:.2f} needle={s['needle']:.3f} "
              f"hard={s['hard_needle']:.3f} ttft_p99={s['ttft_warm_p99']:.3f}s "
              f"speedup_vs_cold={sp:.2f}× → {args.out}")
        return 0

    arms = {}
    for path in args.arms.split(","):
        with open(path.strip()) as fh:
            s = json.load(fh)
        arms[s["label"]] = s
    rt_data = None
    if args.roundtrip:
        with open(args.roundtrip) as fh:
            rt_data = json.load(fh)
    hdr = ("label", "bytes/tok", "needle", "hard", "reload/1k", "ttft_p99", "spdup")
    print(f"{hdr[0]:<18}{hdr[1]:>10}{hdr[2]:>8}{hdr[3]:>8}{hdr[4]:>11}{hdr[5]:>10}{hdr[6]:>8}")
    for label, m in arms.items():
        print(f"{label:<18}{m['bytes_per_token']:>10.2f}{m['needle']:>8.3f}{m['hard_needle']:>8.3f}"
              f"{m['reload_s_per_1k']:>11.2f}{m['ttft_warm_p99']:>10.3f}"
              f"{m.get('ttft_speedup_vs_cold', float('nan')):>8.2f}")
    print(f"\n  VERDICT (iso-bytes): {verdict(arms, rt_data)}")
    print("  (Systems axis — bytes/transfer/TTFT/p99 — and quality-after-reuse per "
          "docs/KVPRO_VS_CACHEGEN_WARMTIER_PROTOCOL.md)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
