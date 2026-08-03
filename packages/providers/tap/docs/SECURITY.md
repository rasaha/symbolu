# Security

- **No execution authority.** TAP cannot authorize, dispatch, or execute anything;
  it exposes no such surface and imports no action control-plane / external-execution
  port. A wrong or malicious assertion result cannot cause an action.
- **Fail closed.** Infrastructure failure and uncertainty map to INDETERMINATE, never
  SUPPORTED.
- **No embedded secrets.** Only secret *references* are accepted; TAP implements no
  secret-management system and logs no secrets.
- **No implicit data access.** TAP never fetches unrestricted enterprise data; it
  evaluates caller-supplied evidence references only.
- **Remote transport** must be independently secured and authenticated by the
  operator; TAP provides no transport security of its own.
- **Not production certified** — see KNOWN_LIMITATIONS.md.
