#!/usr/bin/env python3
"""probe_phase5b_2_backend.py — Phase 5B.2 prep: introspect vLLM 0.7.3
attention backend internals.

Loads Qwen2.5-7B in vLLM (stock, no install) and walks the object tree
to extract everything we need before subclassing the backend:

  1. The model_runner.attn_backend class (top-level backend selector
     class), with its module path and public method names.
  2. Per-attention-layer impl class (the actual implementation that
     calls FlashAttention), with module path + public methods.
  3. CacheConfig's kv_cache_dtype validation behavior:
     - what values does it accept by default?
     - what happens when we try to pass "int4_protected"?
  4. The backend selection function (likely
     `vllm.attention.selector.get_attn_backend`) — find it and dump
     its signature.
  5. Per-block KV cache shape (the calculation we'll need to override
     in Phase 5B.3 to land memory savings).

Output is structured stdout sections — copy-paste back so I can write
the subclass against real evidence rather than guessed APIs.

Does NOT modify anything. Read-only probe. ~30 seconds runtime.
"""
from __future__ import annotations
import argparse
import inspect
import sys
from pathlib import Path


def _hdr(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def _safe_repr(x) -> str:
    try:
        return repr(x)
    except Exception as e:
        return f"<repr error: {e}>"


def _public_attrs(obj, skip_callable: bool = False) -> list:
    out = []
    for name in dir(obj):
        if name.startswith("_"):
            continue
        try:
            val = getattr(obj, name)
        except Exception:
            continue
        if skip_callable and callable(val):
            continue
        out.append((name, val))
    return out


def _public_methods(cls) -> list:
    methods = []
    for name in dir(cls):
        if name.startswith("_"):
            continue
        try:
            attr = getattr(cls, name)
        except Exception:
            continue
        if callable(attr):
            methods.append(name)
    return methods


def probe_vllm_modules() -> None:
    """Check which vLLM attention-related modules are importable
    and report their __file__ paths."""
    _hdr("Section 1 — vLLM module discovery")
    modules_of_interest = [
        "vllm",
        "vllm.attention",
        "vllm.attention.layer",
        "vllm.attention.selector",
        "vllm.attention.backends",
        "vllm.attention.backends.abstract",
        "vllm.attention.backends.flash_attn",
        "vllm.config",
    ]
    for mod_name in modules_of_interest:
        try:
            mod = __import__(mod_name, fromlist=["__file__"])
            path = getattr(mod, "__file__", "<no __file__>")
            print(f"  [OK]  {mod_name:45s} {path}")
        except ImportError as e:
            print(f"  [MISS] {mod_name:45s} {e}")


def probe_cache_config() -> None:
    """Look at vLLM's CacheConfig to see what kv_cache_dtype values
    are accepted by default + where the validation lives."""
    _hdr("Section 2 — CacheConfig.kv_cache_dtype validation")
    try:
        from vllm.config import CacheConfig
    except ImportError as e:
        print(f"  Can't import CacheConfig: {e}")
        return

    # Inspect the class itself.
    print(f"  CacheConfig class: {CacheConfig.__module__}.{CacheConfig.__name__}")
    print(f"  Source file: {inspect.getfile(CacheConfig)}")

    # Try to find the validation logic.
    src = inspect.getsource(CacheConfig)
    # Find lines that mention kv_cache_dtype.
    print(f"  Source lines mentioning 'kv_cache_dtype' or 'fp8':")
    for i, line in enumerate(src.splitlines(), 1):
        lower = line.lower()
        if "kv_cache_dtype" in lower or "'fp8" in lower or '"fp8' in lower:
            print(f"    L{i:>4}  {line.rstrip()}")

    # Try construction with the default + check accepted values.
    print()
    print("  Trying CacheConfig(kv_cache_dtype='auto') ...")
    try:
        cfg = CacheConfig(
            block_size=16, gpu_memory_utilization=0.5,
            swap_space=0, cache_dtype="auto",
        )
        print(f"    OK: {cfg}")
    except TypeError as e:
        # Probably different constructor signature — list __init__ params.
        sig = inspect.signature(CacheConfig.__init__)
        print(f"    TypeError. __init__ signature: {sig}")
        return
    except Exception as e:
        print(f"    Error: {e}")

    print()
    print("  Trying CacheConfig(kv_cache_dtype='int4_protected') ...")
    try:
        cfg = CacheConfig(
            block_size=16, gpu_memory_utilization=0.5,
            swap_space=0, cache_dtype="int4_protected",
        )
        print(f"    OK (would accept): {cfg}")
    except Exception as e:
        print(f"    REJECTED with: {type(e).__name__}: {e}")


def probe_attention_backends() -> None:
    """Look at the abstract AttentionBackend base + FlashAttention impl."""
    _hdr("Section 3 — AttentionBackend abstract + FlashAttentionBackend")
    try:
        from vllm.attention.backends import abstract as abs_mod
    except ImportError as e:
        print(f"  Can't import abstract: {e}")
        return

    base_cls = None
    for name in ("AttentionBackend", "Backend"):
        if hasattr(abs_mod, name):
            base_cls = getattr(abs_mod, name)
            break
    if base_cls is None:
        print("  Couldn't find AttentionBackend base class in abstract module.")
        return

    print(f"  Base class: {base_cls.__module__}.{base_cls.__name__}")
    print(f"  Public methods: {_public_methods(base_cls)}")
    # Show all abstract/static method names with their signatures.
    print(f"  Method signatures (first 15):")
    for name in _public_methods(base_cls)[:15]:
        try:
            m = getattr(base_cls, name)
            sig = inspect.signature(m)
            print(f"    {name}{sig}")
        except (ValueError, TypeError):
            print(f"    {name}(?)")

    # FlashAttention backend
    print()
    try:
        from vllm.attention.backends import flash_attn as fa_mod
    except ImportError as e:
        print(f"  Can't import flash_attn backend: {e}")
        return

    # Look for known classes.
    print(f"  flash_attn module classes:")
    for name in dir(fa_mod):
        if name.startswith("_"):
            continue
        attr = getattr(fa_mod, name)
        if inspect.isclass(attr):
            print(f"    {name}  (mro tail: ... {attr.__mro__[-3:-1]})")


def probe_get_attn_backend() -> None:
    """Find the function that vLLM uses to select an attention backend."""
    _hdr("Section 4 — get_attn_backend selector")
    try:
        from vllm.attention import selector as sel_mod
    except ImportError as e:
        print(f"  Can't import vllm.attention.selector: {e}")
        return

    print(f"  selector module: {sel_mod.__file__}")
    print(f"  Public names: {[n for n in dir(sel_mod) if not n.startswith('_')]}")

    for fname in ("get_attn_backend", "_which_attn_backend",
                  "which_attn_backend", "select_attn_backend"):
        if hasattr(sel_mod, fname):
            f = getattr(sel_mod, fname)
            try:
                sig = inspect.signature(f)
                print(f"  {fname}{sig}")
            except (ValueError, TypeError):
                print(f"  {fname}(?)")


def probe_model_runner(llm) -> None:
    """Inspect the live model_runner's attn_backend."""
    _hdr("Section 5 — live model_runner.attn_backend")
    candidates = [
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner,
        lambda x: x.model_executor.driver_worker.model_runner,
    ]
    mr = None
    for fn in candidates:
        try:
            cand = fn(llm)
            if cand is not None:
                mr = cand
                break
        except (AttributeError, IndexError):
            pass
    if mr is None:
        print("  Could not locate model_runner.")
        return
    print(f"  model_runner class: {type(mr).__module__}.{type(mr).__name__}")

    # attn_backend can be a class or instance — check both.
    if hasattr(mr, "attn_backend"):
        ab = mr.attn_backend
        print(f"  model_runner.attn_backend = {ab!r}")
        if inspect.isclass(ab):
            print(f"    (is class) name = {ab.__name__}, module = {ab.__module__}")
            print(f"    public methods: {_public_methods(ab)[:20]}")
            # Try get_kv_cache_shape
            if hasattr(ab, "get_kv_cache_shape"):
                try:
                    sig = inspect.signature(ab.get_kv_cache_shape)
                    print(f"    get_kv_cache_shape{sig}")
                except (ValueError, TypeError):
                    pass
        else:
            print(f"    (is instance) class = {type(ab).__module__}.{type(ab).__name__}")
    else:
        print("  model_runner has NO attn_backend attribute.")
        print(f"  All model_runner public attrs: "
              f"{[n for n in dir(mr) if not n.startswith('_')][:30]}")


def probe_attention_layers(llm) -> None:
    """Walk the model for Attention layers; report their impl class."""
    _hdr("Section 6 — Attention layer .impl objects")
    candidates = [
        lambda x: x.llm_engine.model_executor.driver_worker.model_runner.model,
        lambda x: x.model_executor.driver_worker.model_runner.model,
    ]
    model = None
    for fn in candidates:
        try:
            cand = fn(llm)
            if cand is not None:
                model = cand
                break
        except (AttributeError, IndexError):
            pass
    if model is None:
        print("  Could not locate model.")
        return

    n_attention = 0
    impl_classes_seen = {}
    for name, sub in model.named_modules():
        cls = type(sub).__name__
        if not cls.endswith("Attention"):
            continue
        # Leaf only.
        has_inner = any(
            type(s).__name__.endswith("Attention") for s in sub.modules() if s is not sub
        )
        if has_inner:
            continue
        n_attention += 1
        # Look at common attribute names that hold the impl.
        for attr_name in ("impl", "attn_impl", "attention_impl", "_impl"):
            if hasattr(sub, attr_name):
                imp = getattr(sub, attr_name)
                key = (attr_name, type(imp).__module__, type(imp).__name__)
                impl_classes_seen.setdefault(key, 0)
                impl_classes_seen[key] += 1
                break
        else:
            print(f"  Attention layer '{name}' has no recognizable impl attr.")
            print(f"    public attrs: {[n for n, _ in _public_attrs(sub, skip_callable=True)][:20]}")
            break

    print(f"  Total leaf attention layers found: {n_attention}")
    print(f"  Impl classes seen (attr, module, class) -> count:")
    for k, v in impl_classes_seen.items():
        print(f"    {k}  x{v}")

    # Detail one impl instance.
    if impl_classes_seen and n_attention > 0:
        first = next(iter(model.named_modules()))
        for name, sub in model.named_modules():
            if not type(sub).__name__.endswith("Attention"):
                continue
            if any(type(s).__name__.endswith("Attention") for s in sub.modules() if s is not sub):
                continue
            for attr_name in ("impl", "attn_impl", "attention_impl", "_impl"):
                if hasattr(sub, attr_name):
                    imp = getattr(sub, attr_name)
                    print()
                    print(f"  Sample impl from layer '{name}':")
                    print(f"    type: {type(imp).__module__}.{type(imp).__name__}")
                    print(f"    mro: {[c.__name__ for c in type(imp).__mro__]}")
                    print(f"    public attrs (non-callable): "
                          f"{[n for n, _ in _public_attrs(imp, skip_callable=True)][:15]}")
                    print(f"    public methods: {_public_methods(type(imp))[:20]}")
                    # Specifically try get_kv_cache_shape on the class.
                    cls = type(imp)
                    if hasattr(cls, "get_kv_cache_shape"):
                        print(f"    has get_kv_cache_shape: True")
                    break
            break


def probe_cache_engine(llm) -> None:
    """Inspect CacheEngine — where per-block byte cost lives."""
    _hdr("Section 7 — CacheEngine + paged cache structure")
    try:
        # vLLM 0.7.x typically: worker.cache_engine
        worker = llm.llm_engine.model_executor.driver_worker
    except AttributeError as e:
        print(f"  No driver_worker: {e}")
        return
    print(f"  worker class: {type(worker).__module__}.{type(worker).__name__}")
    ce = getattr(worker, "cache_engine", None)
    if ce is None:
        # Maybe cache_engines (list).
        ces = getattr(worker, "cache_engines", None)
        if ces is None:
            print(f"  No cache_engine / cache_engines attr.")
            print(f"  worker public attrs: "
                  f"{[n for n, _ in _public_attrs(worker, skip_callable=True)][:20]}")
            return
        print(f"  worker.cache_engines = list of {len(ces)} engines")
        ce = ces[0]
    print(f"  cache_engine class: {type(ce).__module__}.{type(ce).__name__}")
    print(f"  public attrs (non-callable): "
          f"{[n for n, _ in _public_attrs(ce, skip_callable=True)][:25]}")
    print(f"  public methods: {_public_methods(type(ce))[:25]}")

    # Look for gpu_cache / kv_cache.
    for attr in ("gpu_cache", "kv_cache", "cpu_cache"):
        if hasattr(ce, attr):
            val = getattr(ce, attr)
            if isinstance(val, list):
                if val and hasattr(val[0], "shape"):
                    print(f"  {attr}: list of {len(val)} tensors, "
                          f"first shape {tuple(val[0].shape)} dtype {val[0].dtype}")
                    if hasattr(val[0], "is_cuda"):
                        b = val[0].numel() * val[0].element_size()
                        print(f"    first tensor bytes: {b:,} ({b/1024/1024:.2f} MB)")
                        total = sum(t.numel() * t.element_size() for t in val)
                        print(f"    total bytes across list: {total:,} "
                              f"({total/1024/1024/1024:.3f} GB)")
                else:
                    print(f"  {attr}: list of {len(val)} {type(val[0]).__name__ if val else '?'}")
            else:
                print(f"  {attr}: {type(val).__name__}")

    # Look for get_cache_block_size.
    cls = type(ce)
    for fname in ("get_cache_block_size", "_get_cache_block_size",
                  "cache_block_size"):
        if hasattr(cls, fname):
            f = getattr(cls, fname)
            print(f"  has {fname}: {f!r}")


def main(argv) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen2.5-7B-Instruct")
    parser.add_argument("--max-model-len", type=int, default=2048,
                        help="Keep small; we only need engine init.")
    parser.add_argument("--gpu-memory-utilization", type=float, default=0.3)
    parser.add_argument("--skip-load", action="store_true",
                        help="Skip the model load — only probe importable modules + CacheConfig.")
    args = parser.parse_args(argv)

    print("Phase 5B.2 prep — vLLM 0.7.3 attention backend probe")
    print(f"  model:           {args.model}")
    print(f"  max_model_len:   {args.max_model_len}")
    print(f"  skip_load:       {args.skip_load}")

    # Module-level probes (no model load needed).
    probe_vllm_modules()
    probe_cache_config()
    probe_attention_backends()
    probe_get_attn_backend()

    if args.skip_load:
        print()
        print("Skipping model-load probes (--skip-load).")
        return 0

    # Instance-level probes (need a live LLM).
    try:
        from vllm import LLM
    except ImportError as e:
        print(f"\nCan't import vllm.LLM: {e}")
        return 1

    print()
    print("Loading model (this is the only slow step) ...")
    try:
        llm = LLM(
            model=args.model, max_model_len=args.max_model_len,
            gpu_memory_utilization=args.gpu_memory_utilization,
            enforce_eager=True,
        )
    except Exception as e:
        print(f"\nModel load failed: {e}")
        return 1

    probe_model_runner(llm)
    probe_attention_layers(llm)
    probe_cache_engine(llm)

    print()
    print("=" * 70)
    print("Probe complete. Paste this entire output back so I can write")
    print("Int4ProtectedAttentionBackend against real evidence.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
