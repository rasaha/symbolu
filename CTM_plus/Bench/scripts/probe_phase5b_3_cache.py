#!/usr/bin/env python3
"""probe_phase5b_3_cache.py — Phase 5B.3 prep: introspect vLLM 0.7.3
CacheConfig validation + CacheEngine byte-cost + get_attn_backend.

Phase 5B.3 is the memory-savings step. It needs to:
  (a) Patch CacheConfig validation to accept "int4_protected".
  (b) Patch get_attn_backend so vLLM picks our backend class when
      kv_cache_dtype="int4_protected".
  (c) Override per-block byte-cost calculation (likely in CacheEngine
      or AttentionBackend) so the reserve shrinks from ~24 GiB to
      ~17 GiB.

This probe extracts the exact surfaces — method names, signatures,
source lines — so I can write the patches with confidence.

Sections:
  1. CacheConfig.__init__ + validation method names + source snippet.
  2. vllm.worker.cache_engine: CacheEngine class signature.
  3. CacheEngine.get_cache_block_size signature (or alternative).
  4. AttentionBackend.get_kv_cache_shape — current FA impl source.
  5. vllm.attention.selector.get_attn_backend full source.
  6. Live model_runner.kv_caches structure (find the K/V tensors).
  7. CacheConfig._verify_cache_dtype if present (or whichever method
     contains the "fp8_e5m2" check at L86).

Read-only. ~5 sec without model load; add --load for full live probe.
"""
from __future__ import annotations
import argparse
import inspect
import sys


def _hdr(t: str) -> None:
    print()
    print("=" * 70)
    print(t)
    print("=" * 70)


def _dump_method_source(cls, method_name: str, context: int = 30) -> None:
    """Print the source of a method including a few lines of context."""
    try:
        method = getattr(cls, method_name)
        src = inspect.getsource(method)
        print(f"  Source of {cls.__name__}.{method_name}:")
        for i, line in enumerate(src.splitlines(), 1):
            print(f"    L{i:>3}  {line.rstrip()}")
    except Exception as e:
        print(f"  Can't get source of {cls.__name__}.{method_name}: {e}")


def _find_methods_referencing(cls, needle: str) -> list:
    """Find methods on cls whose source contains the needle string."""
    found = []
    for name in dir(cls):
        if name.startswith("__") and name not in ("__init__", "__post_init__"):
            continue
        try:
            attr = getattr(cls, name)
            if not callable(attr):
                continue
            src = inspect.getsource(attr)
            if needle in src:
                found.append(name)
        except Exception:
            pass
    return found


def probe_cache_config() -> None:
    _hdr("Section 1 — CacheConfig validation surface")
    try:
        from vllm.config import CacheConfig
    except ImportError as e:
        print(f"  Can't import CacheConfig: {e}")
        return

    # Find methods that reference "fp8" — those are the validation
    # methods we need to patch.
    methods_with_fp8 = _find_methods_referencing(CacheConfig, "fp8_e5m2")
    print(f"  Methods referencing 'fp8_e5m2': {methods_with_fp8}")

    methods_with_kvdtype = _find_methods_referencing(CacheConfig, "kv_cache_dtype")
    print(f"  Methods referencing 'kv_cache_dtype': {methods_with_kvdtype}")
    methods_with_unknown = _find_methods_referencing(CacheConfig, "Unknown kv cache dtype")
    print(f"  Methods raising 'Unknown kv cache dtype': {methods_with_unknown}")

    # Dump the source of the most likely validation method.
    candidates = (methods_with_unknown or methods_with_fp8
                  or ["_verify_cache_dtype", "__post_init__", "_verify_args"])
    for m in candidates[:2]:
        if hasattr(CacheConfig, m):
            print()
            _dump_method_source(CacheConfig, m)

    # __init__ signature
    print()
    print(f"  CacheConfig.__init__ signature:")
    try:
        sig = inspect.signature(CacheConfig.__init__)
        print(f"    {sig}")
    except (ValueError, TypeError) as e:
        print(f"    ?: {e}")


def probe_cache_engine() -> None:
    _hdr("Section 2 — CacheEngine class")
    try:
        from vllm.worker import cache_engine as ce_mod
    except ImportError as e:
        print(f"  Can't import vllm.worker.cache_engine: {e}")
        return
    print(f"  module: {ce_mod.__file__}")

    # Look for CacheEngine class.
    if not hasattr(ce_mod, "CacheEngine"):
        print(f"  No CacheEngine class in module. Public names: "
              f"{[n for n in dir(ce_mod) if not n.startswith('_')]}")
        return

    cls = ce_mod.CacheEngine
    print(f"  class: {cls.__module__}.{cls.__name__}")

    # All public methods.
    methods = [n for n in dir(cls)
               if not n.startswith("_") and callable(getattr(cls, n, None))]
    print(f"  public methods: {methods}")

    # Specifically look for byte-cost methods.
    for fname in ("get_cache_block_size", "get_cache_size",
                  "_get_cache_block_size", "cache_block_size",
                  "compute_cache_block_size"):
        if hasattr(cls, fname):
            f = getattr(cls, fname)
            try:
                sig = inspect.signature(f)
                print(f"  has {fname}{sig}")
            except (ValueError, TypeError):
                print(f"  has {fname}(?)")

    # Dump source of get_cache_block_size if it exists.
    for fname in ("get_cache_block_size",):
        if hasattr(cls, fname):
            print()
            _dump_method_source(cls, fname)
            break


def probe_attention_backend_shape() -> None:
    _hdr("Section 3 — FlashAttentionBackend.get_kv_cache_shape source")
    try:
        from vllm.attention.backends.flash_attn import FlashAttentionBackend
    except ImportError as e:
        print(f"  Can't import FlashAttentionBackend: {e}")
        return
    _dump_method_source(FlashAttentionBackend, "get_kv_cache_shape")


def probe_selector() -> None:
    _hdr("Section 4 — get_attn_backend selector source")
    try:
        from vllm.attention import selector as sel
    except ImportError as e:
        print(f"  Can't import vllm.attention.selector: {e}")
        return
    if hasattr(sel, "get_attn_backend"):
        try:
            src = inspect.getsource(sel.get_attn_backend)
            print(f"  Source of get_attn_backend:")
            for i, line in enumerate(src.splitlines(), 1):
                print(f"    L{i:>3}  {line.rstrip()}")
        except Exception as e:
            print(f"  Can't get source: {e}")
    # Also check helper functions referenced.
    for fname in ("backend_name_to_enum", "_cached_get_attn_backend"):
        if hasattr(sel, fname):
            f = getattr(sel, fname)
            try:
                src = inspect.getsource(f)
                print()
                print(f"  Source of {fname}:")
                for i, line in enumerate(src.splitlines(), 1):
                    print(f"    L{i:>3}  {line.rstrip()}")
            except Exception as e:
                print(f"  Can't get source of {fname}: {e}")


def probe_live_cache_engine(llm) -> None:
    _hdr("Section 5 — live CacheEngine + kv_caches")
    try:
        worker = llm.llm_engine.model_executor.driver_worker
    except AttributeError as e:
        print(f"  No driver_worker: {e}")
        return
    print(f"  worker class: {type(worker).__module__}.{type(worker).__name__}")

    # cache_engine (singular)
    ce = getattr(worker, "cache_engine", None)
    print(f"  worker.cache_engine: type={type(ce).__name__ if ce is not None else 'None'}")
    if isinstance(ce, list):
        print(f"    is list of length {len(ce)}")
        if ce:
            first = ce[0]
            print(f"    cache_engine[0]: type={type(first).__module__}.{type(first).__name__}")
            attrs = [a for a in dir(first)
                     if not a.startswith("_") and not callable(getattr(first, a, None))]
            print(f"    cache_engine[0] non-callable public attrs: {attrs[:20]}")
            # Look for gpu_cache.
            if hasattr(first, "gpu_cache"):
                gc = first.gpu_cache
                if isinstance(gc, list):
                    print(f"    cache_engine[0].gpu_cache: list of {len(gc)}")
                    if gc and hasattr(gc[0], "shape"):
                        t = gc[0]
                        b = t.numel() * t.element_size()
                        print(f"      first tensor: shape={tuple(t.shape)}, "
                              f"dtype={t.dtype}, bytes={b:,} ({b/1024/1024:.2f} MB)")
                        total = sum(g.numel() * g.element_size() for g in gc
                                    if hasattr(g, "numel"))
                        print(f"      total across {len(gc)} layers: "
                              f"{total/1024/1024/1024:.3f} GB")
                else:
                    print(f"    cache_engine[0].gpu_cache: {type(gc).__name__}")

    # ALSO try the model_runner path.
    print()
    mr = getattr(worker, "model_runner", None)
    if mr is not None:
        kvc = getattr(mr, "kv_caches", None)
        print(f"  worker.model_runner.kv_caches: type={type(kvc).__name__ if kvc is not None else 'None'}")
        if isinstance(kvc, list):
            print(f"    list of {len(kvc)}")
            if kvc:
                t = kvc[0]
                if hasattr(t, "shape"):
                    b = t.numel() * t.element_size()
                    print(f"    first tensor: shape={tuple(t.shape)}, "
                          f"dtype={t.dtype}, bytes={b:,} ({b/1024/1024:.2f} MB)")
                    total = sum(g.numel() * g.element_size() for g in kvc
                                if hasattr(g, "numel"))
                    print(f"    total across {len(kvc)} layers: "
                          f"{total/1024/1024/1024:.3f} GB")


def main(argv) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--load", action="store_true",
                        help="Load Qwen2.5-7B to probe live CacheEngine + kv_caches.")
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--max-model-len", type=int, default=2048)
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.3)
    args = parser.parse_args(argv)

    print("Phase 5B.3 prep — CacheEngine + selector + validation probe")
    print(f"  --load: {args.load}")

    probe_cache_config()
    probe_cache_engine()
    probe_attention_backend_shape()
    probe_selector()

    if args.load:
        from vllm import LLM
        print()
        print("Loading model...")
        llm = LLM(
            model=args.model, max_model_len=args.max_model_len,
            gpu_memory_utilization=args.gpu_memory_utilization,
            enforce_eager=True,
        )
        probe_live_cache_engine(llm)

    print()
    print("=" * 70)
    print("Probe complete. Paste back so I can write the 5B.3 patches.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
