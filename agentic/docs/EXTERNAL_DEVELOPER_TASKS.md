# External Developer Trial Tasks

Three concrete tasks for external validation. Complete them in order.
Use only the docs and examples as reference — do not read framework
internals unless you are stuck.

**Record every friction point.** That is the primary goal.

---

## Task 1: Run the minimal example

**Goal:** Confirm the install path works and you can read a trace.

**Steps:**
1. Create a fresh virtual environment
2. `pip install -e .` from the repo root
3. `python examples/minimal_governed_agent.py`
4. Read the trace output

**Success criteria:**
- The script runs without errors
- You can explain what `trace.status`, `trace.actions_executed`,
  and `trace.total_tokens` mean from reading the output

**Record:**
- Did the install work? Any missing dependencies?
- Was the trace output readable?
- Did you understand what the agent did?

---

## Task 2: Read (or try) the mock-to-real adapter path

**Goal:** Understand what changes when you switch from mock to real LLM.

**If you have an API key (OpenAI or Anthropic):**
1. Install the adapter SDK: `pip install -e ".[openai]"` or
   `pip install -e ".[anthropic]"`
2. Copy `examples/minimal_governed_agent.py` to a new file
3. Replace `MockLLMAdapter(...)` with `OpenAIAdapter(model="gpt-4")`
   or `AnthropicAdapter(model="claude-sonnet-4-20250514")`
4. Set your API key as an environment variable
5. Run it and compare the trace

**If you do NOT have an API key:**
1. Read [Mock → Real LLM](MOCK_TO_REAL_LLM.md)
2. Answer these questions from the doc alone:
   - What import do you change?
   - What constructor argument do you change?
   - What stays the same in the rest of your code?
   - What does `trace.accounting_mode` change to?
   - What new failure modes should you expect?

**Success criteria:**
- With key: real adapter runs, trace shows `accounting_mode: "exact"`
- Without key: you can answer all five questions from the doc

**Record:**
- Was the swap path clear from the tutorial?
- What was confusing about `action_type_to_tool` mapping?
- Any errors during the swap?

---

## Task 3: Build a custom governed agent

**Goal:** Build a small governed agent from scratch, using only docs.

**Specification:**

Build a **governed task manager** with these three tools:

| Tool name | What it does | Risk level |
|-----------|-------------|------------|
| `list_tasks` | Returns a hardcoded list of 3 tasks | `READ_ONLY` |
| `complete_task` | Marks a task as done (just print/return) | `WRITE` |
| `delete_task` | Deletes a task (just print/return) | `DESTRUCTIVE` |

Requirements:
- Use `build_agent()` with `MockLLMAdapter`
- Use `ToolSpec` for all three tools
- Add an `ApprovalPolicy` that requires approval for `complete_task`
  and `delete_task` but not `list_tasks`
- Add an `ApprovalController` with an auto-approve callback
- Use `run_with_trace()` and print `format_trace()`
- Run it with a prompt like "Show my tasks and complete the first one"

**Stretch (optional):**
- Add a `BudgetPolicy` with `max_total_tokens=5000`
- Run a second query with an auto-deny callback and verify the
  action is blocked in the trace
- Use `describe_approval_coverage()` to preview which actions are gated

**Success criteria:**
- Script runs without errors
- Trace shows the approval gate fired for the write/destructive actions
- You can explain the output

**Record:**
- How long did it take?
- What did you have to look up in docs?
- What did you have to look up in source code?
- What would have made it faster?

---

## After completing the tasks

Fill out the [Feedback Template](EXTERNAL_DEVELOPER_FEEDBACK_TEMPLATE.md)
and return it with your task scripts.
