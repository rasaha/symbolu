"""
The exact prompt sent to the real model to produce an interpretation core.

There is ONE prompt (it asks for both a free-text intent for baseline A and the
schema core reused by baselines B-F). The deterministic layers (extraction,
provenance, ambiguity, conflict, clarification) are applied afterward IN CODE per
baseline — the model is never asked to perform them, so the ablation isolates the
value of each frozen layer on top of the model core.

The prompt deliberately instructs the model to INTERPRET, never to answer, and never
to invent unstated details — mirroring the TAP-E1 layer boundary.
"""

from __future__ import annotations

from typing import Dict

from truth_assurance_pipeline.tap_e1_intent.schema import RawUserRequest, TaskType

_TASK_TYPES = ", ".join(t.value for t in TaskType)

SYSTEM = (
    "You are the Intent Understanding Layer of a Truth Assurance Platform. Your only "
    "job is to interpret what the user appears to want and what remains unresolved. "
    "You MUST NOT answer, fulfill, or perform the request. You MUST NOT invent any "
    "entity, constraint, date, recipient, or detail the user did not provide. If the "
    "request is underspecified or ambiguous, say so rather than guessing."
)

_INSTRUCTIONS = f"""Interpret the request below and return ONLY a JSON object with keys:
  raw_intent: one plain sentence describing what the user wants (no answer).
  primary_objective: the core objective, in your words.
  task_type: one of [{_TASK_TYPES}].
  requested_output: what artifact/answer form the user wants (do not produce it).
  target_object: the main object acted on, or null.
  entities: array of concrete entities EXPLICITLY present (files, names, ids, values).
  explicit_constraints: array of {{"text": "...", "polarity": "requirement"|"prohibition"}}
      for constraints the user actually stated (e.g. "preserve headers", "no new deps").
  temporal_constraints: array of date/time constraints as written.
  stated_assumptions: array of assumptions YOU are making, each marked as your inference.
  references: array of things referring to prior conversation or external artifacts.
  interpretation_status: one of RESOLVED, PARTIALLY_RESOLVED, AMBIGUOUS, CONFLICTING,
      INSUFFICIENT_CONTEXT, ABSTAINED.
Rules: include only what is grounded in the text/context; never fabricate entities or
constraints; if key information is missing, use PARTIALLY_RESOLVED/AMBIGUOUS/
INSUFFICIENT_CONTEXT and do not commit to one reading."""


def build_prompt(request: RawUserRequest) -> Dict[str, str]:
    convo = ""
    if request.conversation:
        lines = [f"{t.role}: {t.text}" for t in request.conversation]
        convo = "Conversation so far:\n" + "\n".join(lines) + "\n\n"
    meta = ""
    if request.metadata:
        meta = "Application metadata: " + ", ".join(
            f"{k}={v}" for k, v in sorted(request.metadata.items())) + "\n\n"
    user = f"{convo}{meta}Current request:\n\"{request.text}\"\n\n{_INSTRUCTIONS}"
    return {"system": SYSTEM, "user": user}
