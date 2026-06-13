"""Pod-only backend adapters for the warm-tier head-to-head (UNTESTED on CPU).

⚠️ These run on the GPU pod against live servers (vLLM / LMCache+CacheGen / KVPro)
and a torch build. They are NOT exercised by the CPU test suite — only the mock
backend in `cachegen_warmtier_eval.py` is. Each returns the four-callable backend
dict the harness expects: {prefill_store, reload_query, resident_query, cold_query}.

What is real vs. what is the open engineering item:
  * CacheGen / bf16 / KVPro-via-APC  — implemented over the OpenAI-compatible HTTP
    surface with TRUE streaming TTFT and measured stored bytes (disk-dir or
    Prometheus probe). These run as-is once the servers are up.
  * KVPro NVMe-snapshot              — the SERIALIZE half exists (the paged writer's
    `_maybe_dump_block` under INT4_PROTECTED_DUMP_BLOCKS); the RELOAD/reattach half
    does not. `kvpro_snapshot_backend` documents the exact contract and raises until
    that half is built. Use KVPro-via-APC for the quality/TTFT columns meanwhile.

See docs/KVPRO_VS_CACHEGEN_WARMTIER_PROTOCOL.md §Wiring.
"""
from __future__ import annotations

import os
import random
import time
from typing import Callable, Optional


# ----------------------------- bytes probes -------------------------------- #
def disk_dir_bytes(path: str) -> int:
    """Total bytes under a directory tree (LMCache local-disk / NVMe backend writes
    KV chunks as files; the before/after delta is the measured stored bytes)."""
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def disk_dir_bytes_probe(path: str) -> Callable[[], int]:
    return lambda: disk_dir_bytes(path)


def prometheus_bytes_probe(metrics_url: str,
                           gauge: str = "lmcache_local_disk_usage_bytes") -> Callable[[], Optional[float]]:
    """Best-effort: sum a gauge from a Prometheus /metrics endpoint. The exact
    LMCache gauge name is version-specific — override `gauge` to match your build
    (inspect the endpoint once). Returns None if unavailable/not found."""
    def probe() -> Optional[float]:
        try:
            import urllib.request
            txt = urllib.request.urlopen(metrics_url, timeout=5).read().decode()
        except Exception:
            return None
        tot, found = 0.0, False
        for line in txt.splitlines():
            if line.startswith(gauge) and not line.startswith("#"):
                try:
                    tot += float(line.rsplit(" ", 1)[1])
                    found = True
                except ValueError:
                    pass
        return tot if found else None
    return probe


# --------------------------- OpenAI streaming TTFT ------------------------- #
def _stream(client, model: str, prompt: str, max_tokens: int) -> tuple[str, float]:
    """Returns (full_text, time_to_first_token_s). Temp 0, greedy."""
    t0 = time.time()
    ttft: Optional[float] = None
    parts = []
    stream = client.chat.completions.create(
        model=model, messages=[{"role": "user", "content": prompt}],
        temperature=0.0, max_tokens=max_tokens, stream=True)
    for ev in stream:
        if not ev.choices:
            continue
        delta = getattr(ev.choices[0].delta, "content", None)
        if delta:
            if ttft is None:
                ttft = time.time() - t0
            parts.append(delta)
    return "".join(parts), (ttft if ttft is not None else time.time() - t0)


# ------------------- endpoint backend (cachegen / bf16 / kvpro-apc) -------- #
def openai_endpoint_backend(*, base_url: str, model: str, cold_base_url: Optional[str] = None,
                            bytes_probe: Optional[Callable[[], Optional[float]]] = None,
                            max_tokens: int = 16, api_key: str = "dummy") -> dict:
    """Warm-tier reuse over an OpenAI-compatible server. The 'store' is warming the
    prefix into the server's cache (LMCache/CacheGen offload, or APC); 'reload' is a
    follow-up request that reuses the cached prefix (cache hit) — TTFT measures the
    reload+reattach+first-token cost. 'cold' busts the cache (separate cold server,
    or a per-request nonce) for the recompute baseline.

    bytes_stored is the measured delta of `bytes_probe` across the store; for a
    fixed-codec reload, byte-faithfulness (Phase-0) is the KVPro-snapshot concern,
    not a lossy-by-design CacheGen endpoint — so resident_query here is just a hot
    cache-hit (roundtrip_clean is informative only for the snapshot backend)."""
    from openai import OpenAI
    warm = OpenAI(base_url=base_url, api_key=api_key)
    cold = OpenAI(base_url=cold_base_url, api_key=api_key) if cold_base_url else None

    def _probe() -> Optional[float]:
        try:
            return bytes_probe() if bytes_probe else None
        except Exception:
            return None

    def _delta(a: Optional[float], b: Optional[float]) -> float:
        return (b - a) if (a is not None and b is not None) else float("nan")

    def prefill_store(prefix: str):
        b0 = _probe()
        t0 = time.time()
        r = warm.chat.completions.create(
            model=model, messages=[{"role": "user", "content": prefix}],
            temperature=0.0, max_tokens=1)          # warm the prefix into the cache
        enc = time.time() - t0
        b1 = _probe()
        ntok = r.usage.prompt_tokens if getattr(r, "usage", None) else len(prefix.split())
        bs = _delta(b0, b1)
        return {"prefix": prefix}, {"n_tokens": ntok, "bytes_stored": bs,
                                    "encode_s": enc, "decode_s": 0.0, "transfer_bytes": bs}

    def reload_query(handle, q):
        out, ttft = _stream(warm, model, handle["prefix"] + "\n\n" + q["prompt"], max_tokens)
        return out, {"ttft_s": ttft}

    def resident_query(prefix, q):                  # hot cache-hit (same server)
        out, _ = _stream(warm, model, prefix + "\n\n" + q["prompt"], max_tokens)
        return out, {}

    def cold_query(prefix, q):
        client = cold or warm
        nonce = "" if cold else f"[req-{random.randint(0, 10**9)}] "   # bust prefix cache if no cold server
        out, ttft = _stream(client, model, nonce + prefix + "\n\n" + q["prompt"], max_tokens)
        return out, {"ttft_s": ttft}

    return {"prefill_store": prefill_store, "reload_query": reload_query,
            "resident_query": resident_query, "cold_query": cold_query}


def cachegen_backend(*, base_url: str, model: str, disk_dir: Optional[str] = None,
                     metrics_url: Optional[str] = None, cold_base_url: Optional[str] = None,
                     max_tokens: int = 16) -> dict:
    """vLLM + LMCache with CacheGen enabled. Measure stored bytes from the local-disk
    backend dir (preferred, exact) or a Prometheus gauge. Sweep CacheGen's quality
    level across separate runs (one server config per level) to hit iso-bytes."""
    probe = (disk_dir_bytes_probe(disk_dir) if disk_dir
             else (prometheus_bytes_probe(metrics_url) if metrics_url else None))
    return openai_endpoint_backend(base_url=base_url, model=model, cold_base_url=cold_base_url,
                                   bytes_probe=probe, max_tokens=max_tokens)


def bf16_cold_backend(*, base_url: str, model: str, max_tokens: int = 16) -> dict:
    """Plain vLLM bf16 — used mainly as the cold-recompute TTFT denominator and the
    quality ceiling. No reuse cache assumed."""
    return openai_endpoint_backend(base_url=base_url, model=model, max_tokens=max_tokens)


def kvpro_apc_backend(*, base_url: str, model: str, disk_dir: Optional[str] = None,
                      cold_base_url: Optional[str] = None, max_tokens: int = 16) -> dict:
    """KVPro served via vLLM with APC (eager-only, Phase 6K.16) for HOT prefix reuse.
    ⚠️ APC keeps reused KV in GPU HBM — this measures reuse QUALITY + TTFT, NOT the
    NVMe warm tier. The NVMe bytes/transfer columns require `kvpro_snapshot_backend`."""
    probe = disk_dir_bytes_probe(disk_dir) if disk_dir else None
    return openai_endpoint_backend(base_url=base_url, model=model, cold_base_url=cold_base_url,
                                   bytes_probe=probe, max_tokens=max_tokens)


def kvpro_snapshot_backend(*, snapshot_dir: Optional[str] = None, **kw) -> dict:
    """KVPro NVMe-snapshot warm tier.

    The serialize/restore PRIMITIVE now exists:
    `kv_policy.tier5b_snapshot` provides `save_prefix_snapshot` / `load_prefix_snapshot`
    / `restore_prefix` (the missing reload half — re-injects packed K/V + 5 sidecars into
    a fresh paged allocation, re-encoding protect via the writer's _protect_store) and a
    built-in `verify_roundtrip` byte-gate. RUN `verify_roundtrip` ON THE POD FIRST — it is
    the protocol's Phase-0 gate (snapshot → zero → restore → byte-compare); the primitive
    is HARDWARE-UNTESTED until it passes.

    The REMAINING gap is only the live-engine wiring this backend needs:
      - prefill_store: get the prefix's writer + kv_cache + its block_ids from the running
        vLLM engine, call save_prefix_snapshot(writer, kv_cache, block_ids, {snapshot_dir}/{id}),
        evict; record dir-size delta as bytes_stored (disk_dir_bytes).
      - reload_query: allocate fresh blocks for the prefix, load_prefix_snapshot + restore_prefix
        into them, then serve the query attending over the restored KV.
    Both need handles into the engine's block manager / writer registry, which is the
    integration this raises on. Until wired, use kvpro_apc_backend for the quality + TTFT
    columns (HOT reuse); this snapshot path adds the true NVMe bytes/transfer columns.
    """
    raise NotImplementedError(kvpro_snapshot_backend.__doc__)
