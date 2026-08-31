"""Single source of truth for the package version.

This is the first independently packaged release of the Agent Runtime. No prior
authoritative semantic version existed for a standalone distribution (the runtime
previously lived inside the ``agent_runtime_migration`` monorepo package), so the
independent distribution starts at 0.1.0. See docs/AGENT_RUNTIME_OVERVIEW.md.
"""
from __future__ import annotations

# 0.7.0 — CM-TA1 additive attempt telemetry: a neutral, opt-in seam that observes EVERY actual
# provider.execute invocation (success, expected failure, timeout, provider error, raw exception)
# with the runtime-authoritative attempt number, so retried and failed attempts are never
# collapsed into the final attempt count. Adds ProviderAttempt / ProviderAttemptStatus /
# AttemptContext / AttemptObserver / RecordingAttemptObserver and the PROVIDER_USAGE_METADATA_KEY
# under which a provider MAY attach an opaque usage mapping the runtime forwards verbatim. New
# optional config field `attempt_observer` (None = no behavior change). The runtime stays
# provider-neutral: it never imports a provider SDK and never interprets provider-specific token
# fields; a governance HOLD/BLOCK/ESCALATE or an exact-action clearance/integrity rejection never
# invokes the provider and so produces no attempt. Purely additive — no execution truth, governance
# ownership, exact-action fingerprint, proposal binding, checkpoint schema, or recovery semantics
# changes.
#
# 0.6.0 — H22-D bounded concurrent multi-workflow execution: an additive layer above H22-C that
# lets several mutually-safe workflows make progress at once. Adds a fairness-preserving batch
# selection seam on the H22-B scheduler (plan_batch: the SAME smooth-weighted-round-robin core,
# generalized to admit a batch — at max_concurrency=1 it is identical to a single step), logical
# resource claims with a fixed conflict matrix and an atomic all-or-none ResourceCoordinator, a
# shared reserve-before-execute BudgetCoordinator (limit/reserved/consumed accounting, fail-closed
# on NaN/Inf/negative, conservative settlement), bounded compensation coordination (idempotent
# registration of a separately-defined, separately-governed compensation workflow with origin
# lineage — never a direct provider call and never an exactly-once claim), and a
# ConcurrentPortfolioExecutor that plans a deterministic admission batch, runs each admitted
# indivisible H22-A quantum concurrently (synchronous or bounded thread-pool backend, proven
# equivalent), and reconciles resources/budget/failure/compensation at a stable batch boundary.
# The portfolio checkpoint gains a v2 schema carrying only the durable H22-D slice (budget limits
# + consumed, compensation registrations; reservations are transient and never persisted) — v1
# checkpoints recover unchanged. It changes no single-workflow execution truth and no governance
# ownership: H22-D decides which safe quanta may run concurrently; it never authorizes the
# consequential action inside a quantum (that stays below H22-A, with fresh governance per
# quantum), never preempts the indivisible governance→exact-action→provider chain, never runs two
# quanta for one workflow at once, and preserves the H22-C torn-state
# PORTFOLIO_RUNTIME_CHECKPOINT_DIVERGENCE fail-closed contract. In-process only: no distributed
# cluster scheduling, no distributed locking, no exactly-once external effects, no runtime
# assurance, no peer messaging, no agent/model selection.
# (0.5.0 added the H22-C durable orchestration layer; 0.4.0 added the H22-B deterministic
# coordination layer; 0.3.0 added the H22-A bounded-advancement seam; 0.2.0 added canonical
# execution state; 0.1.2 hardened the exact-action contract; 0.1.1 added fail-closed default
# governance.)
__version__ = "0.7.0"

VERSION = __version__
