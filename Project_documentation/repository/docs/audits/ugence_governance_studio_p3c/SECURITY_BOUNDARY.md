# Frontend Security Boundary

- API base URL is env/build-configured and sanitized to http(s) only; no arbitrary
  URL input, no runtime host switching.
- No credentials, tokens or secrets in the bundle; no token storage; authentication
  is not implemented (P3E).
- No `dangerouslySetInnerHTML`, no `eval`, no dynamic code execution, no
  model-provider SDK, no external fetch beyond the configured API.
- Production source maps are disabled (documented).
- CSP compatibility is documented for P3E (the app is self-contained; inline styles
  come from Tailwind's compiled stylesheet).
- Architecture-boundary and terminology verifiers run in CI.
