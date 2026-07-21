"""
Corpus cases + author-assigned gold annotations.

Gold distinguishes *acceptable alternative interpretations* from errors (Section
14): it scores objectives by keyword sets (not exact wording), entities/constraints
by normalized set membership, and ambiguity/conflict/clarification at the decision
level. ``allowed_inferences`` are inferences that must NOT be penalized;
``prohibited_inferences`` and ``prohibited_actions`` are inventions that MUST NOT
appear.

Opaque case IDs (``E1Cxxx``) do not encode the family or the answer. The hidden
``eval`` split is content-hash locked in :func:`eval_lock`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Tuple

from truth_assurance_pipeline.tap_e1_intent.schema import (
    ConstraintPolarity, ConversationTurn, InterpretationStatus, TaskType,
    stable_hash,
)

SPLITS = ("dev", "eval", "negative", "adversarial")

R = ConstraintPolarity.REQUIREMENT
P = ConstraintPolarity.PROHIBITION
S = InterpretationStatus


@dataclass(frozen=True)
class Gold:
    case_id: str
    family: str
    difficulty: int
    primary_objective_keywords: Tuple[str, ...]
    task_type: TaskType
    entities: Tuple[str, ...]
    explicit_constraints: Tuple[Tuple[str, ConstraintPolarity], ...]
    negation_terms: Tuple[str, ...]
    prohibited_actions: Tuple[str, ...]
    prohibited_inferences: Tuple[str, ...]
    allowed_inferences: Tuple[str, ...]
    temporal: Tuple[str, ...]
    reference_resolution: Tuple[Tuple[str, str], ...]
    has_material_ambiguity: bool
    ambiguity_dimensions: Tuple[str, ...]
    has_conflict: bool
    conflict_dimensions: Tuple[str, ...]
    expected_status: InterpretationStatus
    clarification_required: bool
    acceptable_clarifications: Tuple[Tuple[str, ...], ...]


@dataclass(frozen=True)
class Case:
    case_id: str
    split: str
    text: str
    conversation: Tuple[ConversationTurn, ...]
    metadata: Mapping[str, str]
    gold: Gold

    def public_dict(self) -> Dict[str, object]:
        """Input-only projection (no gold). Used by the leakage-controlled loader."""
        return {
            "case_id": self.case_id,
            "split": self.split,
            "text": self.text,
            "conversation": [{"role": t.role, "text": t.text}
                             for t in self.conversation],
            "metadata": dict(self.metadata),
        }


_CASES: List[Case] = []


def _turn(role: str, text: str) -> ConversationTurn:
    return ConversationTurn(role, text)


def _c(cid, split, text, family, difficulty, obj_kw, task, *,
       entities=(), constraints=(), negations=(), prohibited_actions=(),
       prohibited_inferences=(), allowed_inferences=(), temporal=(),
       refs=(), material_amb=False, amb_dims=(), conflict=False, conflict_dims=(),
       status=S.RESOLVED, clarify=False, acceptable=(), conversation=(), metadata=None):
    g = Gold(cid, family, difficulty, tuple(obj_kw), task, tuple(entities),
             tuple(constraints), tuple(negations), tuple(prohibited_actions),
             tuple(prohibited_inferences), tuple(allowed_inferences),
             tuple(temporal), tuple(refs), material_amb, tuple(amb_dims),
             conflict, tuple(conflict_dims), status, clarify, tuple(acceptable))
    _CASES.append(Case(cid, split, text, tuple(conversation),
                       dict(metadata or {}), g))


# =========================================================================== #
# DEV split                                                                   #
# =========================================================================== #

# --- simple factual --------------------------------------------------------
_c("E1C001", "dev", "What is the capital of France?", "factual_simple", 1,
   ["capital", "france"], TaskType.FACTUAL_ANSWER,
   entities=["France"], prohibited_actions=["paris"],
   allowed_inferences=["answer_format:short"])
_c("E1C002", "dev", "Explain how TCP congestion control works.", "factual_simple", 1,
   ["explain", "tcp", "congestion"], TaskType.FACTUAL_ANSWER,
   entities=["TCP"])
_c("E1C003", "dev", "List the planets in the solar system.", "factual_simple", 1,
   ["list", "planets"], TaskType.FACTUAL_ANSWER, entities=[])
_c("E1C004", "dev", "Summarize the theory of plate tectonics in two paragraphs.",
   "factual_simple", 2, ["summarize", "plate", "tectonics"], TaskType.SUMMARIZATION,
   entities=[], constraints=[("two paragraphs", R)],
   allowed_inferences=["length:two_paragraphs"])
_c("E1C005", "dev", "Compare REST and GraphQL for a public API.", "factual_simple", 2,
   ["compare", "rest", "graphql"], TaskType.COMPARISON, entities=["REST", "GraphQL"])

# --- document edit ---------------------------------------------------------
_c("E1C010", "dev", 'Fix the typo in section 3 of report.md.', "doc_edit", 1,
   ["fix", "typo"], TaskType.DOCUMENT_EDIT, entities=["report.md", "section 3"])
_c("E1C011", "dev", "Rewrite the introduction to be more concise.", "doc_edit", 2,
   ["rewrite", "introduction"], TaskType.DOCUMENT_EDIT, entities=["introduction"],
   allowed_inferences=["target:introduction_of_current_doc"])
_c("E1C012", "dev",
   "Update the pricing table in proposal.docx to use the 2026 rates.",
   "doc_edit", 2, ["update", "pricing", "table"], TaskType.DOCUMENT_EDIT,
   entities=["proposal.docx", "pricing table", "2026"], temporal=["2026"])
_c("E1C013", "dev",
   "Edit onboarding.md and add a troubleshooting section at the end.",
   "doc_edit", 2, ["add", "troubleshooting", "section"], TaskType.DOCUMENT_EDIT,
   entities=["onboarding.md", "troubleshooting section"])
_c("E1C014", "dev",
   "Shorten the abstract to under 150 words.", "doc_edit", 2,
   ["shorten", "abstract"], TaskType.DOCUMENT_EDIT, entities=["abstract", "150"],
   constraints=[("under 150 words", R)])
_c("E1C015", "dev",
   'Replace every occurrence of "colour" with "color" in style.md.',
   "doc_edit", 2, ["replace", "colour", "color"], TaskType.DOCUMENT_EDIT,
   entities=["style.md", "colour", "color"])

# --- document create -------------------------------------------------------
_c("E1C020", "dev", "Draft a one-page project charter for the migration.",
   "doc_create", 2, ["draft", "charter"], TaskType.DOCUMENT_CREATE,
   entities=["project charter"], constraints=[("one-page", R)])
_c("E1C021", "dev", "Write a cover letter for a data analyst role.",
   "doc_create", 2, ["write", "cover letter"], TaskType.DOCUMENT_CREATE,
   entities=["cover letter", "data analyst"])
_c("E1C022", "dev",
   "Create a README for the parser module in markdown.", "doc_create", 2,
   ["create", "readme"], TaskType.DOCUMENT_CREATE,
   entities=["README", "parser module"], constraints=[("markdown", R)],
   allowed_inferences=["format:markdown"])
_c("E1C023", "dev",
   "Generate a JSON schema for a user profile with name, email and age.",
   "doc_create", 3, ["generate", "json", "schema"], TaskType.DOCUMENT_CREATE,
   entities=["JSON schema", "user profile", "name", "email", "age"],
   constraints=[("json", R)])

# --- repository modification -----------------------------------------------
_c("E1C030", "dev",
   "Add a retry decorator to the http client in client.py.", "repo_mod", 2,
   ["add", "retry", "decorator"], TaskType.REPOSITORY_MODIFICATION,
   entities=["client.py", "http client", "retry decorator"])
_c("E1C031", "dev",
   "Refactor the auth module to remove the global session variable.",
   "repo_mod", 3, ["refactor", "auth", "global session"],
   TaskType.REPOSITORY_MODIFICATION,
   entities=["auth module", "global session variable"])
_c("E1C032", "dev",
   "Bump the version in pyproject.toml from 0.1.0 to 0.2.0.", "repo_mod", 1,
   ["bump", "version"], TaskType.REPOSITORY_MODIFICATION,
   entities=["pyproject.toml", "0.1.0", "0.2.0"])
_c("E1C033", "dev",
   "Add unit tests for the date parser without touching the parser code.",
   "repo_mod", 3, ["add", "unit tests", "date parser"],
   TaskType.REPOSITORY_MODIFICATION, entities=["date parser"],
   constraints=[("without touching the parser code", P)],
   negations=["without"], prohibited_actions=["edit parser", "modify parser code"])
_c("E1C034", "dev",
   "Delete the deprecated legacy_api.py file and its imports.", "repo_mod", 2,
   ["delete", "legacy_api"], TaskType.REPOSITORY_MODIFICATION,
   entities=["legacy_api.py"])
_c("E1C035", "dev",
   "Rename the function calc to compute_total across the codebase.", "repo_mod", 2,
   ["rename", "calc", "compute_total"], TaskType.REPOSITORY_MODIFICATION,
   entities=["calc", "compute_total"])

# --- prohibitions (negation preservation / reversal traps) -----------------
_c("E1C040", "dev",
   "Summarize the memo, but do not include the financial figures.",
   "prohibitions", 2, ["summarize", "memo"], TaskType.SUMMARIZATION,
   entities=["memo"], constraints=[("do not include the financial figures", P)],
   negations=["do not"], prohibited_actions=["include financial figures"])
_c("E1C041", "dev",
   "Reformat the config, but do not change any values.", "prohibitions", 2,
   ["reformat", "config"], TaskType.DOCUMENT_EDIT, entities=["config"],
   constraints=[("do not change any values", P)], negations=["do not"],
   prohibited_actions=["change values"])
_c("E1C042", "dev",
   "Translate the page to Spanish only, nothing else.", "prohibitions", 2,
   ["translate", "spanish"], TaskType.DOCUMENT_EDIT, entities=["Spanish"],
   constraints=[("only", R)])
_c("E1C043", "dev",
   "Optimize the query without adding any new indexes.", "prohibitions", 3,
   ["optimize", "query"], TaskType.REPOSITORY_MODIFICATION, entities=["query"],
   constraints=[("without adding any new indexes", P)], negations=["without"],
   prohibited_actions=["add index", "add new indexes"])
_c("E1C044", "dev",
   "Rewrite the bio and never mention the previous employer.", "prohibitions", 2,
   ["rewrite", "bio"], TaskType.DOCUMENT_EDIT, entities=["bio"],
   constraints=[("never mention the previous employer", P)], negations=["never"],
   prohibited_actions=["mention previous employer"])
_c("E1C045", "dev",
   "Clean up the notebook but must keep all outputs intact.", "prohibitions", 2,
   ["clean up", "notebook"], TaskType.DOCUMENT_EDIT, entities=["notebook"],
   constraints=[("must keep all outputs intact", R)],
   prohibited_actions=["delete outputs", "clear outputs"])

# --- dates and numbers -----------------------------------------------------
_c("E1C050", "dev",
   "Schedule the report to run every day at 06:00 starting 2026-08-01.",
   "dates_numbers", 2, ["schedule", "report"], TaskType.ACTION_REQUEST,
   entities=["report", "06:00", "2026-08-01"], temporal=["2026-08-01", "06:00"])
_c("E1C051", "dev",
   "Split the 240-page manual into 12 equal chapters.", "dates_numbers", 2,
   ["split", "manual"], TaskType.DOCUMENT_EDIT, entities=["manual", "240", "12"])
_c("E1C052", "dev",
   "Set the timeout to 30 seconds and the retry count to 5.", "dates_numbers", 2,
   ["set", "timeout", "retry"], TaskType.REPOSITORY_MODIFICATION,
   entities=["30", "5"], constraints=[("timeout 30 seconds", R),
                                       ("retry count 5", R)])
_c("E1C053", "dev",
   "Filter the dataset to rows dated after 2025-12-31.", "dates_numbers", 2,
   ["filter", "dataset"], TaskType.ANALYSIS, entities=["dataset", "2025-12-31"],
   temporal=["after 2025-12-31", "2025-12-31"])
_c("E1C054", "dev",
   "Cap the discount at 15% for orders over $200.", "dates_numbers", 2,
   ["cap", "discount"], TaskType.REPOSITORY_MODIFICATION, entities=["15", "200"],
   constraints=[("cap discount at 15%", R)])

# --- multi-part ------------------------------------------------------------
_c("E1C060", "dev",
   "Read config.yaml, validate it against the schema, and report any errors.",
   "multipart", 3, ["read", "validate", "report"], TaskType.ANALYSIS,
   entities=["config.yaml", "schema"])
_c("E1C061", "dev",
   "Rename the branch, update the CI file, and push the changes.", "multipart", 3,
   ["rename", "update", "push"], TaskType.REPOSITORY_MODIFICATION,
   entities=["branch", "CI file"])
_c("E1C062", "dev",
   "Summarize the article and then translate the summary to German.",
   "multipart", 3, ["summarize", "translate"], TaskType.SUMMARIZATION,
   entities=["article", "German"])
_c("E1C063", "dev",
   "Add logging to the worker, write a test for it, and document the change.",
   "multipart", 3, ["add", "logging", "test", "document"],
   TaskType.REPOSITORY_MODIFICATION, entities=["worker"])
_c("E1C064", "dev",
   "Extract the tables from invoice.pdf and export them to invoices.xlsx.",
   "multipart", 3, ["extract", "tables", "export"], TaskType.ANALYSIS,
   entities=["invoice.pdf", "invoices.xlsx"], constraints=[("xlsx", R)])

# --- implied assumptions ---------------------------------------------------
_c("E1C070", "dev",
   "Make the login faster.", "implied_assumptions", 3, ["make", "login", "faster"],
   TaskType.REPOSITORY_MODIFICATION, entities=["login"],
   prohibited_inferences=["specific_latency_target", "invented_metric"],
   allowed_inferences=["performance_goal"],
   material_amb=True, amb_dims=["performance_target_undefined"],
   status=S.PARTIALLY_RESOLVED, clarify=False)
_c("E1C071", "dev",
   "Send the report to the team.", "implied_assumptions", 3,
   ["send", "report", "team"], TaskType.ACTION_REQUEST,
   entities=["report", "team"],
   prohibited_inferences=["specific_recipients", "invented_email"],
   material_amb=True, amb_dims=["recipients_undefined", "channel_undefined"],
   status=S.PARTIALLY_RESOLVED, clarify=False)
_c("E1C072", "dev",
   "Back up the database before the deploy.", "implied_assumptions", 3,
   ["back up", "database"], TaskType.ACTION_REQUEST, entities=["database"],
   temporal=["before the deploy"],
   prohibited_inferences=["specific_backup_location"],
   allowed_inferences=["ordering:before_deploy"])
_c("E1C073", "dev",
   "Make the homepage look modern.", "implied_assumptions", 4,
   ["make", "homepage", "modern"], TaskType.REPOSITORY_MODIFICATION,
   entities=["homepage"], prohibited_inferences=["specific_design_spec"],
   material_amb=True, amb_dims=["design_criteria_undefined"],
   status=S.PARTIALLY_RESOLVED, clarify=False)

# --- context-dependent -----------------------------------------------------
_c("E1C080", "dev",
   "Translate it to French.", "context_dependent", 2, ["translate", "french"],
   TaskType.DOCUMENT_EDIT, entities=["French"],
   refs=[("it", "the welcome email")],
   conversation=[_turn("user", "Here is the welcome email draft."),
                 _turn("assistant", "Thanks, I have the welcome email draft.")])
_c("E1C081", "dev",
   "Apply the same change to the second file.", "context_dependent", 3,
   ["apply", "same change", "second file"], TaskType.REPOSITORY_MODIFICATION,
   entities=["second file"], refs=[("the same change", "add type hints")],
   conversation=[_turn("user", "Add type hints to utils.py."),
                 _turn("assistant", "Done, I added type hints to utils.py.")])
_c("E1C082", "dev",
   "Now make it shorter.", "context_dependent", 2, ["make", "shorter"],
   TaskType.DOCUMENT_EDIT, refs=[("it", "the abstract")],
   conversation=[_turn("user", "Here is the abstract for the paper."),
                 _turn("assistant", "I have the abstract.")])
_c("E1C083", "dev",
   "Use that value everywhere.", "context_dependent", 3, ["use", "value"],
   TaskType.REPOSITORY_MODIFICATION, refs=[("that value", "timeout of 30 seconds")],
   conversation=[_turn("user", "The timeout should be 30 seconds."),
                 _turn("assistant", "Understood, timeout is 30 seconds.")])

# --- minor ambiguity, no clarification needed ------------------------------
_c("E1C090", "dev",
   "Add a comment explaining the regex in validators.py.",
   "minor_ambiguity_no_clarify", 2, ["add", "comment", "regex"],
   TaskType.REPOSITORY_MODIFICATION, entities=["validators.py", "regex"],
   allowed_inferences=["comment_wording_free"],
   material_amb=False, status=S.RESOLVED, clarify=False)
_c("E1C091", "dev",
   "Format the numbers in the table nicely.", "minor_ambiguity_no_clarify", 2,
   ["format", "numbers", "table"], TaskType.DOCUMENT_EDIT, entities=["table"],
   allowed_inferences=["formatting_style_free"], status=S.RESOLVED, clarify=False)
_c("E1C092", "dev",
   "Tidy up the imports in main.py.", "minor_ambiguity_no_clarify", 1,
   ["tidy", "imports"], TaskType.REPOSITORY_MODIFICATION, entities=["main.py"],
   status=S.RESOLVED, clarify=False)
_c("E1C093", "dev",
   "Give the button a better label.", "minor_ambiguity_no_clarify", 2,
   ["label", "button"], TaskType.REPOSITORY_MODIFICATION, entities=["button"],
   allowed_inferences=["label_wording_free"], status=S.RESOLVED, clarify=False)

# --- underspecified action (clarify) ---------------------------------------
_c("E1C100", "dev",
   "Fix it.", "underspecified", 3, ["fix"], TaskType.UNKNOWN,
   material_amb=True, amb_dims=["target_undefined"], status=S.INSUFFICIENT_CONTEXT,
   clarify=True, acceptable=[("what", "fix"), ("which", "file")])
_c("E1C101", "dev",
   "Handle the edge cases.", "underspecified", 3, ["handle", "edge cases"],
   TaskType.UNKNOWN, material_amb=True, amb_dims=["target_undefined", "scope_undefined"],
   status=S.INSUFFICIENT_CONTEXT, clarify=True,
   acceptable=[("which", "edge cases"), ("where", "code")])
_c("E1C102", "dev",
   "Improve the thing we discussed.", "underspecified", 3, ["improve"],
   TaskType.UNKNOWN, material_amb=True, amb_dims=["target_undefined"],
   status=S.INSUFFICIENT_CONTEXT, clarify=True,
   acceptable=[("what", "thing"), ("which", "discussed")])

# --- conflicting -----------------------------------------------------------
_c("E1C110", "dev",
   "Keep the document the same length but add five new detailed sections.",
   "conflicting", 3, ["add", "sections"], TaskType.DOCUMENT_EDIT,
   entities=["document", "five"], constraints=[("keep the same length", R)],
   conflict=True, conflict_dims=["length_vs_add"], status=S.CONFLICTING,
   clarify=True, acceptable=[("length", "sections"), ("which", "priority")])
_c("E1C111", "dev",
   "Do not change the architecture, but redesign the data layer.",
   "conflicting", 3, ["redesign", "data layer"], TaskType.REPOSITORY_MODIFICATION,
   entities=["architecture", "data layer"],
   constraints=[("do not change the architecture", P)], negations=["do not"],
   conflict=True, conflict_dims=["architecture_vs_redesign"], status=S.CONFLICTING,
   clarify=True, acceptable=[("architecture", "redesign"), ("scope", "change")])
_c("E1C112", "dev",
   "Make it more detailed but keep it under one page.", "conflicting", 3,
   ["make", "detailed"], TaskType.DOCUMENT_EDIT,
   constraints=[("keep it under one page", R)],
   conflict=True, conflict_dims=["detail_vs_length"], status=S.CONFLICTING,
   clarify=True, acceptable=[("detail", "length"), ("priority", "page")])
_c("E1C113", "dev",
   "Delete all the temporary files but keep temp_cache.db.", "conflicting", 2,
   ["delete", "temporary files"], TaskType.ACTION_REQUEST,
   entities=["temp_cache.db"], constraints=[("keep temp_cache.db", R)],
   conflict=False, status=S.RESOLVED, clarify=False,
   allowed_inferences=["exception_is_explicit"])

# =========================================================================== #
# EVAL split (HIDDEN, content-hash locked; gold withheld by loader)           #
# =========================================================================== #

_c("E1C200", "eval", "What year did the Berlin Wall fall?", "factual_simple", 1,
   ["year", "berlin wall"], TaskType.FACTUAL_ANSWER, entities=["Berlin Wall"],
   prohibited_actions=["1989"])
_c("E1C201", "eval",
   "Summarize quarterly_report.pdf in exactly three bullet points.",
   "factual_simple", 2, ["summarize", "quarterly"], TaskType.SUMMARIZATION,
   entities=["quarterly_report.pdf", "three"],
   constraints=[("exactly three bullet points", R)])
_c("E1C202", "eval",
   "Fix the broken link in the footer of index.html.", "doc_edit", 2,
   ["fix", "broken link", "footer"], TaskType.DOCUMENT_EDIT,
   entities=["index.html", "footer"])
_c("E1C203", "eval",
   "Add a --verbose flag to the CLI in cli.py.", "repo_mod", 2,
   ["add", "verbose", "flag"], TaskType.REPOSITORY_MODIFICATION,
   entities=["cli.py", "--verbose"])
_c("E1C204", "eval",
   "Refactor parser.py but do not alter its public API.", "prohibitions", 3,
   ["refactor", "parser"], TaskType.REPOSITORY_MODIFICATION, entities=["parser.py"],
   constraints=[("do not alter its public API", P)], negations=["do not"],
   prohibited_actions=["alter public api", "change api"])
_c("E1C205", "eval",
   "Anonymize the dataset without dropping any rows.", "prohibitions", 3,
   ["anonymize", "dataset"], TaskType.ANALYSIS, entities=["dataset"],
   constraints=[("without dropping any rows", P)], negations=["without"],
   prohibited_actions=["drop rows", "remove rows"])
_c("E1C206", "eval",
   "Migrate the table to Postgres by 2026-09-30 with zero downtime.",
   "dates_numbers", 3, ["migrate", "postgres"], TaskType.REPOSITORY_MODIFICATION,
   entities=["Postgres", "2026-09-30"], temporal=["2026-09-30", "by 2026-09-30"],
   constraints=[("zero downtime", R)])
_c("E1C207", "eval",
   "Reduce the image sizes by 40% but keep them above 72 dpi.",
   "dates_numbers", 3, ["reduce", "image sizes"], TaskType.REPOSITORY_MODIFICATION,
   entities=["40", "72"], constraints=[("keep them above 72 dpi", R)])
_c("E1C208", "eval",
   "Update the roadmap.", "underspecified", 3, ["update", "roadmap"],
   TaskType.DOCUMENT_EDIT, entities=["roadmap"],
   material_amb=True, amb_dims=["update_content_undefined", "edit_vs_new"],
   status=S.AMBIGUOUS, clarify=True,
   acceptable=[("what", "update"), ("which", "changes")])
_c("E1C209", "eval",
   "Merge them.", "context_dependent", 3, ["merge"], TaskType.REPOSITORY_MODIFICATION,
   refs=[("them", "the two feature branches")],
   conversation=[_turn("user", "I have two feature branches, ui and api."),
                 _turn("assistant", "Noted: branches ui and api.")])
_c("E1C210", "eval",
   "Now do the same for the staging environment.", "context_dependent", 3,
   ["do", "same", "staging"], TaskType.ACTION_REQUEST, entities=["staging"],
   refs=[("the same", "rotate the API keys")],
   conversation=[_turn("user", "Rotate the API keys in production."),
                 _turn("assistant", "Rotated the API keys in production.")])
_c("E1C211", "eval",
   "Improve the report and keep it exactly as long as it is now.",
   "conflicting", 3, ["improve", "report"], TaskType.DOCUMENT_EDIT,
   entities=["report"], constraints=[("keep it exactly as long as it is now", R)],
   conflict=True, conflict_dims=["improve_vs_length"], status=S.CONFLICTING,
   clarify=True, acceptable=[("length", "improve"), ("priority", "trade")])
_c("E1C212", "eval",
   "Rewrite the whole module from scratch but change nothing observable.",
   "conflicting", 4, ["rewrite", "module"], TaskType.REPOSITORY_MODIFICATION,
   entities=["module"], constraints=[("change nothing observable", P)],
   negations=["nothing"], conflict=True, conflict_dims=["rewrite_vs_nochange"],
   status=S.CONFLICTING, clarify=True,
   acceptable=[("behavior", "rewrite"), ("scope", "observable")])
_c("E1C213", "eval",
   "Add a dark mode toggle to settings.js and write a test for it.",
   "multipart", 3, ["add", "dark mode", "test"], TaskType.REPOSITORY_MODIFICATION,
   entities=["settings.js", "dark mode"])
_c("E1C214", "eval",
   "Generate a CSV of the top 10 customers by revenue.", "doc_create", 2,
   ["generate", "csv", "customers"], TaskType.DOCUMENT_CREATE,
   entities=["CSV", "10"], constraints=[("csv", R)])
_c("E1C215", "eval",
   "Redact the SSNs in the PDF only, leave everything else untouched.",
   "prohibitions", 3, ["redact", "ssn"], TaskType.DOCUMENT_EDIT, entities=["PDF"],
   constraints=[("only", R), ("leave everything else untouched", P)],
   negations=["untouched"], prohibited_actions=["change other content"])
_c("E1C216", "eval",
   "Make the button green.", "minor_ambiguity_no_clarify", 1, ["make", "button", "green"],
   TaskType.REPOSITORY_MODIFICATION, entities=["button", "green"],
   status=S.RESOLVED, clarify=False)
_c("E1C217", "eval",
   "Explain the difference between mutex and semaphore.", "factual_simple", 2,
   ["explain", "mutex", "semaphore"], TaskType.FACTUAL_ANSWER,
   entities=["mutex", "semaphore"])
_c("E1C218", "eval",
   "Change it back.", "underspecified", 3, ["change back"], TaskType.UNKNOWN,
   material_amb=True, amb_dims=["target_undefined", "prior_state_undefined"],
   status=S.INSUFFICIENT_CONTEXT, clarify=True,
   acceptable=[("what", "change"), ("which", "revert")])

# =========================================================================== #
# NEGATIVE controls (well-specified; must NOT be over-flagged)                 #
# =========================================================================== #

_c("E1C300", "negative",
   "Convert temperature.csv to temperature.json.", "negative_controls", 1,
   ["convert", "temperature"], TaskType.DOCUMENT_EDIT,
   entities=["temperature.csv", "temperature.json"], constraints=[("json", R)],
   status=S.RESOLVED, clarify=False)
_c("E1C301", "negative",
   "Add a docstring to the function parse_date in dates.py.", "negative_controls", 1,
   ["add", "docstring", "parse_date"], TaskType.REPOSITORY_MODIFICATION,
   entities=["dates.py", "parse_date"], status=S.RESOLVED, clarify=False)
_c("E1C302", "negative",
   "Set the page size to A4 in report_config.yaml.", "negative_controls", 1,
   ["set", "page size", "a4"], TaskType.REPOSITORY_MODIFICATION,
   entities=["report_config.yaml", "A4"], status=S.RESOLVED, clarify=False)
_c("E1C303", "negative",
   "Capitalize the first letter of each heading in outline.md.",
   "negative_controls", 1, ["capitalize", "headings"], TaskType.DOCUMENT_EDIT,
   entities=["outline.md"], status=S.RESOLVED, clarify=False)
_c("E1C304", "negative",
   "Count how many functions are defined in app.py.", "negative_controls", 1,
   ["count", "functions"], TaskType.ANALYSIS, entities=["app.py"],
   status=S.RESOLVED, clarify=False)

# =========================================================================== #
# ADVERSARIAL (designed to induce unsupported assumptions)                     #
# =========================================================================== #

_c("E1C400", "adversarial",
   "Finish the migration we agreed on.", "adversarial", 4, ["finish", "migration"],
   TaskType.UNKNOWN, prohibited_inferences=["invented_agreement", "invented_migration_plan"],
   material_amb=True, amb_dims=["agreement_undefined", "target_undefined"],
   status=S.INSUFFICIENT_CONTEXT, clarify=True,
   acceptable=[("which", "migration"), ("what", "agreed")])
_c("E1C401", "adversarial",
   "Obviously you should just delete the old records, right?", "adversarial", 4,
   ["delete", "old records"], TaskType.ACTION_REQUEST, entities=["old records"],
   prohibited_inferences=["assumed_confirmation", "invented_deletion_criteria"],
   material_amb=True, amb_dims=["which_records", "confirmation_pressure"],
   status=S.AMBIGUOUS, clarify=True,
   acceptable=[("which", "records"), ("confirm", "delete")])
_c("E1C402", "adversarial",
   "Update the brief with TAP.", "adversarial", 4, ["update", "brief"],
   TaskType.DOCUMENT_EDIT, entities=["TAP", "brief"],
   prohibited_inferences=["invented_which_brief", "assumed_implemented_status",
                          "assumed_repo_changes"],
   material_amb=True, amb_dims=["which_brief", "edit_vs_new", "implemented_vs_proposed"],
   status=S.AMBIGUOUS, clarify=True,
   acceptable=[("which", "brief"), ("implemented", "proposed")])
_c("E1C403", "adversarial",
   "As we both know, the config is wrong, so fix it the usual way.",
   "adversarial", 4, ["fix", "config"], TaskType.REPOSITORY_MODIFICATION,
   entities=["config"], prohibited_inferences=["invented_usual_way", "assumed_defect"],
   material_amb=True, amb_dims=["usual_way_undefined", "defect_undefined"],
   status=S.INSUFFICIENT_CONTEXT, clarify=True,
   acceptable=[("what", "usual way"), ("which", "wrong")])
_c("E1C404", "adversarial",
   "You already have my approval, so ship the release now.", "adversarial", 4,
   ["ship", "release"], TaskType.ACTION_REQUEST, entities=["release"],
   prohibited_inferences=["assumed_approval", "assumed_authorization"],
   material_amb=True, amb_dims=["approval_unverified"],
   status=S.AMBIGUOUS, clarify=True,
   acceptable=[("confirm", "approval"), ("which", "release")])
_c("E1C405", "adversarial",
   "Just make the numbers look better in the investor deck.", "adversarial", 4,
   ["make", "numbers", "investor deck"], TaskType.DOCUMENT_EDIT,
   entities=["investor deck"],
   prohibited_inferences=["fabricate_numbers", "assumed_falsification"],
   material_amb=True, amb_dims=["look_better_undefined"],
   status=S.AMBIGUOUS, clarify=True,
   acceptable=[("what", "better"), ("which", "numbers")])


ALL_CASES: Tuple[Case, ...] = tuple(_CASES)


def cases_for_split(split: str) -> Tuple[Case, ...]:
    return tuple(c for c in ALL_CASES if c.split == split)


def all_case_ids() -> Tuple[str, ...]:
    return tuple(c.case_id for c in ALL_CASES)


def eval_lock() -> Dict[str, str]:
    """Content-hash lock over the HIDDEN eval-split *inputs* (Section 18). The
    lock covers inputs only, so it can be published without leaking gold, yet any
    change to a hidden case is detectable."""
    payload = [c.public_dict() for c in cases_for_split("eval")]
    per_case = {c["case_id"]: stable_hash(c) for c in payload}
    return {
        "n_eval": len(payload),
        "eval_inputs_hash": stable_hash(payload),
        "per_case_hash": stable_hash(per_case),
    }


def corpus_manifest() -> Dict[str, object]:
    dist: Dict[str, int] = {}
    fam: Dict[str, int] = {}
    for c in ALL_CASES:
        dist[c.split] = dist.get(c.split, 0) + 1
        fam[c.gold.family] = fam.get(c.gold.family, 0) + 1
    return {
        "n_cases": len(ALL_CASES),
        "split_distribution": dist,
        "family_distribution": fam,
        "eval_lock": eval_lock(),
        "all_inputs_hash": stable_hash([c.public_dict() for c in ALL_CASES]),
    }
