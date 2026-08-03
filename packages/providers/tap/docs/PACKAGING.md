# Packaging

- **Layout:** src layout, `src/ugence_tap_provider`. Pure-Python wheel
  (`ugence_tap_provider-0.1.0-py3-none-any.whl`).
- **Version source:** `attr = "ugence_tap_provider.version.DISTRIBUTION_VERSION"`
  (read statically; the backend never imports the package).
- **Core dependency:** `ugence-governance-provider-framework>=0.1.0` only.
- **Extras:** `decision-authority` (framework `[adapters]` for the kernel-bound
  assessment integration), `dev`, `all`.
- **Ships:** the `ugence_tap_provider` package + `py.typed`. **No tests**, no
  ActionGate, no AI Hiring, no monorepo bootstrap.
- **Reproducible:** with `SOURCE_DATE_EPOCH` pinned, the wheel is **bit-for-bit
  reproducible**; the sdist is content-reproducible.

Build: `python -m build packages/providers/tap`.
Verify: `python packages/providers/tap/scripts/verify_tap_provider_distribution.py`.
