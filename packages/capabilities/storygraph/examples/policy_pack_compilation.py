#!/usr/bin/env python3
"""Policy Pack compilation — compile the reference StoryPolicyPack (policy-as-code).

Compiles the frozen reference account-takeover Policy Pack and shows that the
compiled graph reproduces the frozen graph's freeze digest — i.e. the pack
declares the frozen slice as customer-configurable policy without changing any
StoryGraph semantics. Deterministic; public policypack API.

    python examples/policy_pack_compilation.py
"""

from __future__ import annotations

from ugence_storygraph.policypack import compiler, reference


def main() -> int:
    bundle = compiler.compile_pack(reference.ACCOUNT_TAKEOVER_PACK)
    graph_digest = compiler.graph_freeze_digest(bundle)

    print("compiled graph ref:", bundle.graph.ref)
    print("graph freeze digest:", graph_digest)
    print("bundle digest:      ", bundle.bundle_digest)
    print("compiler version:   ", compiler.COMPILER_VERSION)

    # The compiled reference graph reproduces the frozen account-takeover graph.
    assert bundle.graph.ref == "ACCOUNT_TAKEOVER_TRANSFER@1.0.0"
    assert graph_digest == \
        "sha-256:6a77b8997263c40f2b6d791c9391ae562dfb51ba6e7ae04ce5da5f775cc081a8"
    print("OK — pack compiles and reproduces the frozen graph (no semantic change).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
