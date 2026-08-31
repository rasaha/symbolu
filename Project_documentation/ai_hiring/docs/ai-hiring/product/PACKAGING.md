# Packaging & Artifacts

## Distribution vs. product

The AI Hiring product ships **inside** the repository's `symbolu` distribution
(`pyproject.toml`, name `symbolu`, distribution version `0.1.0`). The **product**
has its own semantic version — `ai_hiring.product.PRODUCT_VERSION == 0.6.0` — which
tracks build phases H0–H6 and is independent of the distribution version.

The **installable product surface** is a subset of the distribution:

| Package | Role |
|---|---|
| `decision_governance` | Frozen kernel (Platform v1.0) |
| `governance_providers` | Provider framework + deterministic validation providers |
| `tap_provider` | Assertion-governance provider |
| `actiongate_provider` | Action-governance provider |
| `ai_hiring` | Hiring domain + `ai_hiring.product` packaging layer |
| `domains.hiring`, `applications.ai_hiring` | Hiring domain surface + composition root |

The distribution also contains unrelated experimental `symbolu.*` modules that the
product does **not** import and does **not** require.

## Build

```bash
python -m build            # produces sdist + wheel in ./dist
```

Verified artifacts (this phase):

| Artifact | Notes |
|---|---|
| `symbolu-0.1.0-py3-none-any.whl` | pure-Python wheel; contains `ai_hiring/product/*` |
| `symbolu-0.1.0.tar.gz` | sdist |

> The wheel is large (~12 MB) because it packages the entire `symbolu` monorepo, not
> only the product. A future dedicated product distribution could scope the wheel to
> the installable surface above; that repackaging is **not** part of H6.

## Runtime dependencies

Only two third-party runtime dependencies are pulled: `numpy` and `pydantic>=2`
(see [`DEPENDENCY_REVIEW.md`](DEPENDENCY_REVIEW.md)). No vendor AI SDKs, database
drivers, or web frameworks are required to install, demo, or verify the product.
The AI/web extras in `pyproject.toml` (`openai`, `anthropic`, `mistral`, `all`) are
**optional** and unused by the product.

## Install verification (performed, not just documented)

Both paths were verified in **clean virtual environments**, importing from a
non-repository working directory to prove the install (not the source tree) is
exercised:

1. Editable install — `pip install -e .` → `python -m ai_hiring.product verify` →
   `RESULT: PASS`.
2. Wheel install — `pip install symbolu-0.1.0-py3-none-any.whl` → `verify` →
   `RESULT: PASS`.

See [`INSTALL.md`](INSTALL.md) to reproduce.

## Versioning & changelog

- Product versioning policy: [`VERSIONING.md`](VERSIONING.md).
- Version history: [`CHANGELOG.md`](CHANGELOG.md).
