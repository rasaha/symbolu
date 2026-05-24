#!/usr/bin/env python3
"""probe_phase5b_4_forward.py — Phase 5B.4 prep: dump FlashAttentionImpl.forward.

Phase 5B.4 needs to replace FlashAttentionImpl.forward (the FA impl's
attention call) with our own logic that:
  1. Writes new K/V via PartialGroupQuantizer (not reshape_and_cache_flash).
  2. Reads packed K via the Phase 2.4.1b kernel (not the FA flash_attn
     call against bf16 paged cache).

To write that replacement correctly, I need to see exactly what
FlashAttentionImpl.forward currently does — its full source, the args
it receives, and the helper functions it calls (reshape_and_cache_flash,
flash_attn_varlen_func, flash_attn_with_kvcache, etc.).

Read-only probe. Dumps source of relevant FA functions + AttentionMetadata
structure. No model load needed — pure module introspection (~3 sec).

Sections:
  1. FlashAttentionImpl.forward full source.
  2. FlashAttentionImpl.__init__ signature + stored attributes.
  3. Helper functions / kernels FlashAttentionImpl.forward calls
     (reshape_and_cache_flash, flash_attn_varlen_func, etc.).
  4. FlashAttentionMetadata attribute list (the metadata that gets
     passed into forward).
  5. AttentionLayer protocol (the `self` arg to forward).
"""
from __future__ import annotations
import inspect
import sys


def _hdr(t: str) -> None:
    print()
    print("=" * 70)
    print(t)
    print("=" * 70)


def _dump_source(obj, name_for_label: str, context: int = 0) -> None:
    try:
        src = inspect.getsource(obj)
        print(f"  Source of {name_for_label}:")
        for i, line in enumerate(src.splitlines(), 1):
            print(f"    L{i:>4}  {line.rstrip()}")
    except Exception as e:
        print(f"  Can't get source of {name_for_label}: {e}")


def probe_fa_impl_forward() -> None:
    _hdr("Section 1 — FlashAttentionImpl.forward FULL source")
    try:
        from vllm.attention.backends.flash_attn import FlashAttentionImpl
    except ImportError as e:
        print(f"  Can't import: {e}")
        return
    _dump_source(FlashAttentionImpl.forward, "FlashAttentionImpl.forward")


def probe_fa_impl_init() -> None:
    _hdr("Section 2 — FlashAttentionImpl.__init__ signature + init body")
    try:
        from vllm.attention.backends.flash_attn import FlashAttentionImpl
    except ImportError as e:
        print(f"  Can't import: {e}")
        return
    try:
        sig = inspect.signature(FlashAttentionImpl.__init__)
        print(f"  Signature: {sig}")
    except (ValueError, TypeError):
        print("  Signature: ?")
    _dump_source(FlashAttentionImpl.__init__, "FlashAttentionImpl.__init__")


def probe_fa_metadata() -> None:
    _hdr("Section 3 — FlashAttentionMetadata class structure")
    try:
        from vllm.attention.backends.flash_attn import FlashAttentionMetadata
    except ImportError as e:
        print(f"  Can't import: {e}")
        return
    print(f"  class: {FlashAttentionMetadata.__module__}.{FlashAttentionMetadata.__name__}")
    # Print the dataclass fields if it is one.
    print(f"  MRO: {[c.__name__ for c in FlashAttentionMetadata.__mro__]}")
    # Try to get the dataclass fields.
    try:
        import dataclasses
        if dataclasses.is_dataclass(FlashAttentionMetadata):
            fields = dataclasses.fields(FlashAttentionMetadata)
            print(f"  dataclass fields ({len(fields)}):")
            for f in fields:
                print(f"    {f.name:35s}  {f.type}")
        else:
            print("  not a dataclass; public attrs:")
            attrs = [a for a in dir(FlashAttentionMetadata) if not a.startswith("_")]
            print(f"    {attrs}")
    except Exception as e:
        print(f"  inspection error: {e}")


def probe_attention_layer_protocol() -> None:
    _hdr("Section 4 — AttentionLayer protocol (the 'layer' arg)")
    try:
        from vllm.attention.backends.flash_attn import AttentionLayer
    except ImportError as e:
        print(f"  Can't import: {e}")
        return
    print(f"  class: {AttentionLayer.__module__}.{AttentionLayer.__name__}")
    print(f"  MRO: {[c.__name__ for c in AttentionLayer.__mro__]}")
    _dump_source(AttentionLayer, "AttentionLayer (full class)")


def probe_reshape_and_cache_flash() -> None:
    _hdr("Section 5 — reshape_and_cache_flash op signature")
    try:
        import torch
        # The op lives at torch.ops._C_cache_ops.reshape_and_cache_flash —
        # it's a C++ op; we can introspect its schema via the registry.
        for op_name in ("_C_cache_ops", "_C"):
            ns = getattr(torch.ops, op_name, None)
            if ns is None:
                continue
            for f_name in dir(ns):
                if "reshape_and_cache" in f_name:
                    f = getattr(ns, f_name)
                    print(f"  found op: torch.ops.{op_name}.{f_name}")
                    try:
                        # OpOverloadPacket has overloads.
                        overloads = f.overloads()
                        for ov in overloads:
                            print(f"    overload '{ov}': {f.__getattr__(ov)._schema}")
                    except Exception as e:
                        print(f"    schema introspection error: {e}")
    except ImportError as e:
        print(f"  Can't import torch: {e}")


def probe_flash_attn_funcs() -> None:
    _hdr("Section 6 — flash_attn_with_kvcache / flash_attn_varlen_func location")
    try:
        from vllm.attention.backends import flash_attn as fa
    except ImportError as e:
        print(f"  Can't import: {e}")
        return
    # Look for top-level functions in the FA backend module.
    for name in dir(fa):
        if "flash_attn" in name.lower():
            obj = getattr(fa, name)
            if callable(obj):
                try:
                    sig = inspect.signature(obj)
                    src_file = inspect.getfile(obj) if hasattr(obj, "__code__") else "?"
                    print(f"  {name}{sig}")
                    print(f"    from: {src_file}")
                except (ValueError, TypeError, OSError):
                    print(f"  {name}: <can't get signature>")


def main() -> int:
    print("Phase 5B.4 prep — FlashAttentionImpl.forward source dump")

    probe_fa_impl_forward()
    probe_fa_impl_init()
    probe_fa_metadata()
    probe_attention_layer_protocol()
    probe_reshape_and_cache_flash()
    probe_flash_attn_funcs()

    print()
    print("=" * 70)
    print("Probe complete. Paste back so I can write 5B.4 against real code.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
