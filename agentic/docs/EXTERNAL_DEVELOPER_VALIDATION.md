# External Developer Validation Guide

You have been asked to try the Agentic Framework from scratch and
report what works and what does not. Your feedback directly shapes
the next iteration.

---

## Who this is for

Technically strong Python developers who have NOT used this framework
before. You should be comfortable with:
- Python 3.10+
- Installing packages in a virtual environment
- Reading library source code when docs fall short
- Working with LLM APIs (OpenAI, Anthropic) — helpful but not required

No internal project context is assumed.

---

## What you are validating

1. **Cold-start install** — can you go from zero to running code?
2. **Docs-only adoption** — can you build something from the docs alone?
3. **Governance model clarity** — does the safety/approval/budget system make sense?
4. **API ergonomics** — are the naming, composition, and patterns intuitive?
5. **Mock → real transition** — is the adapter swap path clear?

You are NOT validating production readiness, multi-agent orchestration,
or deployment infrastructure. Those are out of scope for this framework
version.

---

## Sequence to follow

Budget approximately **2–3 hours** for the full sequence. You can
stop at any point — partial feedback is still valuable.

### Phase 1: Install and orient (15–20 min)

1. Clone the repo and create a fresh virtual environment
2. Run `pip install -e .` from the repo root
3. Read the root [README.md](../../README.md) — follow its pointers
4. Read the [Quickstart](QUICKSTART.md) through the "Mental model" section
5. Record: did anything fail? Was anything confusing?

### Phase 2: Run the minimal example (10–15 min)

1. Run `python examples/minimal_governed_agent.py`
2. Read the output — can you tell what happened?
3. Read the source — does the code match what you expected from the docs?
4. Record: what was clear, what was not

### Phase 3: Run one advanced example (15–20 min)

Pick ONE:
- `python examples/governed_agent_with_approval_and_budget.py` —
  shows approval gates + budget enforcement + structured output
- `python examples/pilot_internal_copilot.py` —
  shows per-action-type approval with approve and deny paths

Read the output and source. Record friction.

### Phase 4: Read the mock → real path (15–20 min)

1. Read [Mock → Real LLM](MOCK_TO_REAL_LLM.md)
2. If you have an OpenAI or Anthropic API key:
   - Install the SDK: `pip install -e ".[openai]"` or `pip install -e ".[anthropic]"`
   - Modify the minimal example to use the real adapter
   - Run it and compare the trace output
3. If you do NOT have an API key:
   - Read the tutorial and note: is the swap path clear from reading alone?
   - Would you know what to change and what to expect?
4. Record friction

### Phase 5: Build one tiny custom governed agent (30–45 min)

**This is the most important phase.** See [Task Sheet](EXTERNAL_DEVELOPER_TASKS.md)
for the specific task (Task 3).

Build a small governed agent with:
- 2–3 custom tools at different risk levels
- At least one approval-gated action
- Tracing output

Use only the docs and examples as reference. Record every time you
had to look at framework source code.

### Phase 6: Report feedback (15–20 min)

Fill out the [Feedback Template](EXTERNAL_DEVELOPER_FEEDBACK_TEMPLATE.md).
Be blunt — criticism is more useful than praise.

---

## What to record as you go

At each phase, note:
- **What worked** — things that were immediately clear
- **What required source-code reading** — things the docs didn't cover
- **Confusing names or concepts** — anything that made you stop and think
- **Errors or unexpected behavior** — exact error messages if possible
- **Time spent** — rough per-phase timing helps us calibrate docs

---

## What counts as success

| Outcome | Rating |
|---------|--------|
| Completed all 6 phases from docs alone | Strong pass |
| Completed phases 1–4, phase 5 needed some source reading | Pass — docs need targeted fixes |
| Got stuck at phase 2 or 3 | Fail — install or basic-path friction |
| Could not install or import | Blocker — packaging issue |

Any outcome is useful. "I got stuck at X" is exactly the kind of
signal we need.

---

## Reference docs

| Doc | Purpose |
|-----|---------|
| [Quickstart](QUICKSTART.md) | Install, first agent, API orientation |
| [First Governed Agent](FIRST_GOVERNED_AGENT.md) | Feature-by-feature build guide |
| [Mock → Real LLM](MOCK_TO_REAL_LLM.md) | Adapter swap tutorial |
| [Goal Decomposition & Action Mapping](GOAL_DECOMPOSITION_AND_ACTION_MAPPING.md) | How prompts become governed actions |
| [Examples Overview](EXAMPLES_OVERVIEW.md) | All runnable examples |
| [Framework Status](FRAMEWORK_STATUS.md) | What is proved, what is deferred |
| [Task Sheet](EXTERNAL_DEVELOPER_TASKS.md) | Concrete tasks for phase 5 |
| [Feedback Template](EXTERNAL_DEVELOPER_FEEDBACK_TEMPLATE.md) | Structured feedback form |
