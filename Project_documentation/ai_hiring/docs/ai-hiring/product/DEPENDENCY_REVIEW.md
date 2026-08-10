# Dependency & Supply-Chain Review

Scope: the AI Hiring product (`ai_hiring.product`) and the packages it imports
(`ai_hiring`, `decision_governance`, `governance_providers`, `tap_provider`,
`actiongate_provider`). Reviewed at product `0.6.0`.

## Third-party runtime dependencies

| Dependency | Constraint | Used for | Notes |
|---|---|---|---|
| `pydantic` | `>=2.0` | typed models / validation across the platform | widely used, actively maintained |
| `numpy` | `>=1.24` | pulled transitively by the `symbolu` distribution | **not** used by the product's code paths |

That is the entire third-party runtime footprint. The product code itself imports
**only** the Python standard library (`argparse`, `dataclasses`, `enum`, `hashlib`,
`json`, `sys`, `typing`) plus first-party packages.

## No vendor / integration SDKs

The product imports **no** AI-vendor SDK (`openai`, `anthropic`, `mistralai`), **no**
cloud SDK (`boto3`, `googleapiclient`), **no** communication SDK (`smtplib`,
`sendgrid`, `twilio`), **no** ATS/HRIS SDK (`workday`, `greenhouse`, `lever`), **no**
HTTP client (`requests`, `httpx`), and **no** database driver (`sqlalchemy`,
`psycopg2`). This is enforced by a packaging boundary test
(`test_h6_boundary.py::test_product_imports_no_vendor_sdks`).

The optional extras declared in `pyproject.toml` (`openai`, `anthropic`, `mistral`,
`all`) are **not** dependencies of this product and are never imported by it.

## Supply-chain posture

- **Minimal attack surface:** two well-known runtime dependencies; no network clients
  compiled into the product paths.
- **No install-time code execution** beyond standard setuptools packaging.
- **No secrets** are read, embedded, or required. The typed config carries no
  credentials.
- **Deterministic, offline:** the product performs no outbound network I/O at import,
  demo, or verify time. It can run fully air-gapped.
- **Pinning:** applications embedding the product should pin `pydantic`/`numpy` to
  known-good versions in their own lockfile; the product declares floors, not exact
  pins, to remain embeddable.

## Enforcement

Boundary tests fail the build if a vendor SDK, production transport, or kernel
internal is imported by the product layer. See `ai_hiring/tests/test_h6_boundary.py`
and `ai_hiring/tests/test_h5_boundary.py`.
