"""CTM+ Tier-Aware Inference Benchmark Harness.

Mode A (synthetic): runs without a GPU. Drives the existing
:class:`kv_policy.KVCachePolicy` (and baseline policies) against
a multi-tier cache + three long-context workloads (agentic, RAG,
chat) and reports per-tier byte counters.

The headline question this harness answers:

    *When KV-cache pressure forces blocks out of HBM into a slow
    tier (DRAM, NVMe, or HBF), does CTM+ reduce the bytes read
    from the slow tier compared to LRU, by enough to matter?*

Mode B (real model via vLLM) is a follow-up — only worth running
once Mode A shows the directional result.

See ``Bench/README.md`` for scope + non-goals.
"""

from ctm_bench.tier_model import (
    TierSpec,
    TieredCache,
    TierCounters,
    AccessResult,
    BlockTier,
    HBM_HBF_NVME_2025,
    HBM_DDR_NVME_2025,
)
from ctm_bench.policies import (
    Policy,
    LRUPolicy,
    FIFOPolicy,
    CTMPlusPolicyAdapter,
    POLICIES,
    BenchConfig,
    AccessContext,
)
from ctm_bench.workload import (
    WorkloadSpec,
    AccessPattern,
    TraceEvent,
    generate_agentic,
    generate_agentic_clustered,
    generate_rag,
    generate_chat,
    AGENTIC_64K,
    AGENTIC_CLUSTERED_64K,
    RAG_128K,
    CHAT_32K,
)
from ctm_bench.metrics import (
    RunResult,
    summarize,
    markdown_table,
)
from ctm_bench.runner_sim import run_sim


__version__ = "0.1.0"

__all__ = [
    "TierSpec",
    "TieredCache",
    "TierCounters",
    "AccessResult",
    "BlockTier",
    "HBM_HBF_NVME_2025",
    "HBM_DDR_NVME_2025",
    "Policy",
    "LRUPolicy",
    "FIFOPolicy",
    "CTMPlusPolicyAdapter",
    "POLICIES",
    "BenchConfig",
    "AccessContext",
    "WorkloadSpec",
    "AccessPattern",
    "TraceEvent",
    "generate_agentic",
    "generate_agentic_clustered",
    "generate_rag",
    "generate_chat",
    "AGENTIC_64K",
    "AGENTIC_CLUSTERED_64K",
    "RAG_128K",
    "CHAT_32K",
    "RunResult",
    "summarize",
    "markdown_table",
    "run_sim",
]
