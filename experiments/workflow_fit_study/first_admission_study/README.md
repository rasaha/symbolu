# First admission study (RM-4) — run environment

**Status:** preregistered, not executed. See `preregistration_rm4.json` and
`docs/REASONING_METHOD_FIRST_ADMISSION_STUDY_PLAN.md` §7.

## Where the credential goes

Nowhere in this repository. Two supported places:

1. **Claude Code on the web:** the environment's variable settings, described at
   https://code.claude.com/docs/en/claude-code-on-the-web. The variable is present in the
   session's process environment and nothing in the repository reads it except the
   provider factory inside the boundary process.
2. **A local run:** a `.env` file outside the repository, or copied from `.env.example`
   and kept untracked (`.env` is git-ignored at the root).

The prepared bundle's credential scan refuses any bundle that carries a credential-shaped
value, and the provider configuration accepts only a dotted factory path, never a key.
A key pasted into chat, a manifest or a commit is compromised and must be regenerated.

## Variables

| Variable | Meaning |
| --- | --- |
| `MISTRAL_API_KEY` or `OPENAI_API_KEY` | The one credential matching the preregistered model client identity |
| `WORKFLOW_FIT_BENCHMARK_PATH` | The BBH file outside the repository; digests only are committed |

## What still blocks execution

Recorded in `preregistration_rm4.json`: the D5 verdict-custody decision, an authorised
baseline calibration run, and the credential above. Every output of this study is
RESEARCH EVIDENCE / CRYPTOGRAPHICALLY VERIFIABLE SELF-ATTESTATION (SR-5).
