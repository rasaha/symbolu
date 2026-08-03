# TAP consumer map

Machine-readable: `tap_consumer_map.json`.

**Policy:** the first migration preserves **all** consumers through the
`tap_provider` compatibility facade (object identity preserved). **No consumer was
mass-edited.** New code should prefer `ugence_tap_provider`.

14 consumer sites across the repository continue to `import tap_provider` /
`from tap_provider …` unchanged. Classifications: `KEEP_LEGACY_IMPORT` (verifiers,
AI Hiring legacy adapter — AI Hiring not modified, code-governance adapter),
`MONOREPO_COMPOSITION` (enterprise validation pilot, console API, comparative
benchmark, heterogeneity validation, platform-freeze invariants),
`COMPATIBILITY_TEST` / `MONOREPO_INTEGRATION` (freeze tests, pilot conformance
consumers, `tap_provider/tests`).

All continue to resolve to the identical canonical objects; no `EXTERNAL_CONSUMER_UNKNOWN`
or `DEAD_CODE` required action in this phase.
