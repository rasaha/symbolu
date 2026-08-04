# Access Control (P3E)

HTTP Basic over HTTPS. No user registration, password reset, user database, roles,
groups, SSO, OAuth/OIDC/SAML, SCIM, or social login. One operator credential set via
`UGENCE_STUDIO_USERNAME` + `UGENCE_STUDIO_PASSWORD_HASH` (generated offline). No default
username or password — production fails closed when either is absent or malformed.
Failed authentication returns a generic 401 with `WWW-Authenticate`, after a fixed
delay; repeated failures per source trigger a temporary cooldown (never a permanent
lockout); success clears the counter. Credentials and Authorization headers are never
logged, and 401s never reveal whether the username exists. `/healthz` and `/readyz` are
the only unauthenticated paths.
