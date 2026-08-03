# Versioning

`ugence-ai-hiring` carries **two distinct version numbers** that describe
different things. They are deliberately not the same value.

## Distribution version vs product version

| Concept | Value | Tracks |
| --- | --- | --- |
| Distribution (wheel) version — `__version__` | `0.1.0` | The packaging lifecycle of the distributable artifact. |
| Product (capability-maturity) version — `PRODUCT_VERSION` | `0.6.0` | H0–H6 capability maturity of the product. |

- **Distribution version** answers "which packaged build is this?" It follows the
  packaging lifecycle of `ugence-ai-hiring` as a wheel/sdist.
- **Product version** answers "how mature is the hiring-governance capability?"
  It tracks capability maturity independently of packaging.

Both are surfaced by:

```bash
python -m ugence_ai_hiring version
python -m ugence_ai_hiring version --json
```

and programmatically:

```python
from ugence_ai_hiring import __version__, PRODUCT_VERSION, version_info

version_info().distribution_version   # e.g. "0.1.0"
version_info().product_version        # e.g. "0.6.0"
```

## Pre-1.0 semantics

The distribution version is pre-1.0 (`0.1.0`). Pre-1.0 means the packaging and
public surface may still change between minor releases; treat the API as
stabilizing rather than frozen. The release classification is
`PACKAGE_READY_FOR_CONTROLLED_PILOT` and `production_certified` is always
`False`.

## Extraction does not reset the product version

Extracting the code into the independent `ugence-ai-hiring` distribution did not
reset the product version. The product (capability-maturity) version is carried
forward as `0.6.0`; it reflects the maturity of the capability, which the
packaging change did not alter. The distribution version starts its own lifecycle
at `0.1.0`.

## Related metadata

`version_info()` also exposes `platform_baseline`, `stability`,
`release_classification`, `production_certified`, `contract_versions`,
`dependency_versions`, `optional_integrations`, and `build_commit`. See
[API_REFERENCE.md](API_REFERENCE.md).
