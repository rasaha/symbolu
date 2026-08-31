# Versioning Policy (Pre-1.0)

## Two version numbers

| Number | Where | Meaning |
|---|---|---|
| Product version — `0.6.0` | `ai_hiring.product.PRODUCT_VERSION` | Maturity of the AI Hiring product; tracks build phases H0–H6 |
| Distribution version — `0.1.0` | `pyproject.toml` (`symbolu`) | The repository distribution the product ships inside |

These are intentionally distinct. Cite the **product version** when describing AI
Hiring capabilities or stability.

## Pre-1.0 semantics

The product is on the `0.x` line. Per semantic versioning §4, **anything MAY change**
while the major version is `0`. Concretely, for this product:

- **`0.MINOR.0`** — MINOR is bumped for a new build phase or a potentially
  **breaking** change to the public API (`ai_hiring.product`).
- **`0.MINOR.PATCH`** — PATCH is bumped for a backwards-compatible fix or additive,
  non-breaking change.

The leading `0.` is a standing notice: **not** certified for production hiring
decisions, integrations, or fairness/compliance claims
(`version_info().production_certified` is always `False`).

## What "stable enough to pilot" means

The public surface in [`API_REFERENCE.md`](API_REFERENCE.md) is stable enough to build
a demo or controlled pilot against, and is covered by tests. It is **not** frozen: we
reserve the right to change it before a 1.0 release. Names outside that surface are
internal and may change at any time.

## Path to 1.0 (not in scope of H0–H6)

A 1.0 release would require, at minimum: production execution adapters, durable
persistence, enterprise identity integration, independent fairness/compliance review,
and scale/performance validation — all explicitly out of scope here (see
[`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md)). Until then the product stays pre-1.0.

## Compatibility & rollback

There is no persistent state, so rollback is simply reinstalling a prior version.
Applications embedding the product should pin the distribution version and their own
`pydantic`/`numpy` versions. See [`PACKAGING.md`](PACKAGING.md) and
[`CHANGELOG.md`](CHANGELOG.md).
