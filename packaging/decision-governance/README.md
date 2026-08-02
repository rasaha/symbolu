# decision-governance (compatibility distribution)

Legacy wheel name for the Decision Authority capability. The implementation now
lives in the canonical package **`ugence-decision-authority`**
(`packages/capabilities/decision-authority`). This distribution ships only the
logic-free `decision_governance` compatibility shim and depends on the canonical
wheel — there is no duplicated source. Prefer `ugence-decision-authority` in new
dependency declarations.
