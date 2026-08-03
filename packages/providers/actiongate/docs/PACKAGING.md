# Packaging

- **Build backend:** setuptools (`pyproject.toml`, src layout).
- **Distribution:** `ugence-actiongate-provider` (pure Python, `py3-none-any`).
- **Namespace:** `ugence_actiongate_provider` (typed; ships `py.typed`).
- **Version:** read statically from `ugence_actiongate_provider.version.DISTRIBUTION_VERSION`.
- **Core dependency:** `ugence-governance-provider-framework>=0.1.0` only.
- **Extras:** `decision-authority`, `dev`, `all` (only extras backed by real code).
- **Console script:** `ugence-actiongate-provider` → `ugence_actiongate_provider.cli:main`.

## Build & verify

```bash
python -m build packages/providers/actiongate          # wheel + sdist
python -m build packaging/dgm-actiongate-provider      # legacy compat wheel
python packages/providers/actiongate/scripts/verify_actiongate_provider_distribution.py
```

## Guarantees (audited)
- pure Python; correct metadata, namespace, dependencies;
- **no tests** in the wheel; **no TAP**, **no AI Hiring**, **no enterprise executor**,
  **no monorepo bootstrap**, **no symlink** inside the artifact;
- canonical wheel builds **bit-for-bit reproducibly** under a pinned
  `SOURCE_DATE_EPOCH`.

## Reproducibility
Set `SOURCE_DATE_EPOCH` and pin Python/setuptools/build; two isolated builds produce
identical wheel SHA-256, member order, and metadata. See
`../../../docs/audits/actiongate_packaging/`.
