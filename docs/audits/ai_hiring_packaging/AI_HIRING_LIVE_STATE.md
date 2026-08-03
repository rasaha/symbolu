# AI Hiring — Live-State Verification

Machine-readable: [`ai_hiring_live_state.json`](ai_hiring_live_state.json).
All values were verified against the live repository, not carried forward from
the prompt.

## Repository state at start
| Field | Value |
|---|---|
| Default branch | `claude/setup-symbolu-monorepo-014vhNMAoVW2Ys5RBBr3bKDF` |
| Starting commit | `b6fd6ca50721106958a732dbba88301c00e2fda3` |
| Working branch | `claude/ai-hiring-independent-package-wsh3x3` (branched from the default HEAD) |
| Working tree | clean |
| Python | 3.11.15 |
| Build backend | `setuptools.build_meta` |

## Latest merged PR & prerequisites
- Latest merged PR: **#1295** — *research: incubate and reproduce bounded binding
  slots* — merge commit `b6fd6ca5` (== default HEAD).
- Present on the default branch: **Context Minimization** (PRs #1290–#1293),
  the **Hybrid LLM vNext audit** (#1294), and the **bounded-slot incubation**
  (#1295). ✅
- No active unmerged AI Hiring packaging PR. ✅

## Product / distribution metadata
| Field | Value |
|---|---|
| Product version | `0.6.0` (`ai_hiring/product/version.py`) |
| Current distribution | bundled inside monolithic `symbolu` (name `symbolu`, version `0.1.0`) |
| `ai_hiring.__version__` | `0.1.0` |
| Release classification | `PACKAGE_READY_FOR_CONTROLLED_PILOT` |
| Production certified | **False** (hard-coded) |
| Current import paths | `ai_hiring`, `domains.hiring`, `applications.ai_hiring` |

## Baselines (recorded before any change)
| Baseline | Result |
|---|---|
| `python -m pytest ai_hiring/tests` | **778 collected, 778 passed** |
| Platform freeze (`python -m platform_freeze.verify`) | **PASS**, digest `d4ad77e1…a174a1a6` |
| Dependency versions | pydantic 2.13.4; ugence-decision-authority 1.0.0; ugence-governance-provider-framework 0.1.0; ugence-governance-contracts 0.1.0 |
| Known baseline failures | none |

Note: pydantic and pytest are not present in the base interpreter by default;
they were installed to run the suite. Governance dependencies resolve from
`packages/*/src` via the repo `conftest.py`.
