# Installation & Verification

**Version:** `0.6.0` · **Python:** ≥ 3.10 · **Runtime dependencies:** `pydantic>=2.0`
(and `numpy` transitively via the repository distribution). No vendor AI SDKs, no
database, no network services are required to install, demo, or verify.

## 1. Install

The AI Hiring product ships as part of the `symbolu` repository distribution. The
**installable product surface** is the frozen platform plus the hiring packages —
see [`PACKAGING.md`](PACKAGING.md) for the exact manifest.

From a checkout:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .          # installs symbolu incl. the platform + ai_hiring packages
```

> The broader `symbolu` repository also contains unrelated experimental modules that
> are **not** part of this product and are **not** required by it. The product
> imports only `ai_hiring`, `decision_governance`, `governance_providers`,
> `tap_provider`, and `actiongate_provider`.

## 2. Verify the install (clean-env import + safety check)

The fastest end-to-end confirmation that the product imported cleanly and its
safety invariants hold:

```bash
python -m ai_hiring.product verify
```

Expected output:

```
  [PASS] execution_mode_is_deterministic
  [PASS] production_not_certified
  [PASS] demo_ran
RESULT: PASS
```

Import-surface only (no execution):

```bash
python -c "import ai_hiring.product as P; print(P.version_info().to_dict())"
```

## 3. Run the test suite (optional)

```bash
python -m pytest ai_hiring -q                 # hiring app incl. H6 product tests
python -m pytest decision_governance governance_providers \
                 tap_provider actiongate_provider ai_hiring -q   # platform + app
python -m platform_freeze.verify              # frozen-platform integrity
```

## 4. Uninstall

```bash
pip uninstall symbolu
```

## Troubleshooting

- **`ModuleNotFoundError` for an experimental `symbolu.*` module** — unrelated to this
  product; the product does not import those modules. See
  [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) (whole-repo baseline is not clean).
- **TLS/proxy errors during `pip install`** — the product has no install-time network
  dependency beyond fetching `pydantic`/`numpy`; use your environment's configured
  index/proxy.
