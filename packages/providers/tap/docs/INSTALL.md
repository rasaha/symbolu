# Installing ugence-tap-provider

```bash
pip install ugence-tap-provider                       # core (in-process, network-free)
pip install "ugence-tap-provider[decision-authority]" # + kernel-bound assessment integration
pip install "ugence-tap-provider[dev]"                # + pytest/build for development
```

- **Python:** >= 3.10. Pure-Python wheel (`py3-none-any`).
- **Core dependency:** `ugence-governance-provider-framework` only.
- **No** model SDK, web framework, database driver, or cloud client is pulled in.
- Remote mode requires no extra dependency (in-process client abstraction).

Legacy installs: `pip install dgm-tap-provider` provides the `tap_provider`
namespace and pulls in the canonical wheel.
