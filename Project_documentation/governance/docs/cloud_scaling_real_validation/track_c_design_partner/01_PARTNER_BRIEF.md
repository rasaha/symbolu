# Autoscaling Safety Interlock — Design-Partner Brief

*Read-only. Zero write permissions. Nothing in here changes your cluster.*

## What it is
Your autoscaler (HPA / KEDA / Karpenter) decides **when** to add replicas. Nothing in
the stack checks the next question: **did that scale-out actually help?** We run a
small, read-only engine in **shadow** next to your autoscaler that emits a **causal
verdict for each scale-out** — **HELPING / NEUTRAL / NOT_HELPING** — and flags the
**futile-runaway** pattern: an autoscaler that keeps adding replicas while the
metrics that matter do not improve. That pattern shows up when more replicas *can't*
fix the problem — a saturated downstream dependency, lock contention, a collapsed
queue, or a cascading failure.

## What we read — and nothing else
Through **your Prometheus HTTP API, read-only**, on a short cadence (~15s):
- **service signals** — CPU, memory, p99 latency, error rate, queue depth;
- **autoscaler state** — HPA current vs desired replicas, pod restarts.

That is the entire footprint. No logs, no traces, no source code, no customer data,
no PII.

## What we never do
- **No writes — ever.** We do not change HPA, deployments, nodes, or any cluster
  object. A scoped **read-only** token / RBAC role is all the engine can use.
- **We do not actuate.** When the engine judges a scale-out futile, that is a line in
  a report — **not** an action. It cannot block, cap, or alter anything you run.
- **Nothing in your data path.** No admission webhooks, no sidecars, no mutating
  agents. It can be turned on and off at will.

## What you get
- A per-scale-out **verdict stream** and a short report: where scaling **helped**,
  where it was **not helping**, and any **futile-runaway** windows — cross-referenced
  to your own incident timeline.
- A second read on autoscaling decisions that observability, cost, and autoscaling
  tools are not built to give: not *what happened* and not *what it cost*, but
  **whether the action worked.**

## What we ask of you
1. **Read-only shadow access** to one representative cluster's Prometheus (~2 weeks).
2. **Historical Prometheus / HPA exports** (6–12 months) so we can replay your past
   scaling **offline** — the fastest way to see how often this pattern occurs *for you*.
3. **~30 min/week of an SRE's time** to tell us, per flag, **true or false** — the
   only way a verdict earns trust.

Full list and data-handling terms: `03_DATA_REQUEST_NDA_CHECKLIST.md`.

## Where this stands (so you can judge it fairly)
This is early and we will say so plainly. The engine has been exercised in
**simulation** and in **offline replay of public production traces**, and in that
work it has not produced a harmful false positive. It has **not yet run on a cluster
we don't operate** — which is exactly what this partnership is for. We make **no
savings promise** and **no claim that this is proven in production**; it is a
**reliability/safety** read, not a cost-optimization tool.

## Why it's safe to say yes
Read-only means **no change-management process and no production risk.** It runs in
shadow, it cannot harm the cluster by construction, and it switches off instantly. If
the verdict tells you nothing you didn't already know, you've lost nothing —
and that result is useful to us too.

---
*Contact: `<name / email>`. NDA and data-handling terms available on request.*
