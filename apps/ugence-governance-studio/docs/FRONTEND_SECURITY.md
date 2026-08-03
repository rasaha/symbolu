# Frontend Security

Env/build-configured API base URL (http(s) only, sanitized); no arbitrary URL
input; no credentials/tokens/secrets in the bundle; no token storage; no
`dangerouslySetInnerHTML`, `eval` or dynamic code execution; no model-provider
SDK; no external fetch beyond the configured API. Production source maps are OFF.
CSP for P3E: the app is self-contained (compiled Tailwind stylesheet, no inline
scripts); a strict `default-src 'self'` policy with `style-src 'self'` is the
intended P3E baseline. Authentication is not implemented in P3C.
