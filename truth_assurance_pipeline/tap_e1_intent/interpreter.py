"""
The Intent Understanding Layer + the V0..V5 ablation ladder (Section 15).

This layer interprets a request; it never answers it, retrieves evidence, decides
policy, judges truth, or authorizes an action (Section 3).

HONESTY (Section 21): the "model interpretation" used by V0/V1 is a DETERMINISTIC
heuristic stand-in, not a real LLM. The whole layer is deterministic so the study is
reproducible and the leakage/provenance gates are meaningful. Consequently the study
measures whether the *structured + deterministic-first mechanism* reduces specific
failure modes relative to a shallow interpreter on SYNTHETIC inputs — it is not
evidence about real LLM intent understanding or production behavior.

Ablation ladder (each variant adds one capability; simpler variants may win):

  V0  raw interpretation          : single guessed reading, may answer, no schema
                                    discipline, no provenance, never clarifies.
  V1  structured schema only      : typed IntentRecord via naive heuristics; no
                                    deterministic extraction; over-claims provenance.
  V2  + deterministic extraction  : quotes/dates/numbers/negations/formats/ids with
                                    spans; prohibitions preserved (no reversal).
  V3  + provenance enforcement    : append-only ledger; correct provenance kinds;
                                    no false EXPLICIT provenance; defaults visible.
  V4  + ambiguity/conflict detect : candidate interpretations + conflict items;
                                    statuses AMBIGUOUS/CONFLICTING; no silent resolve.
  V5  + clarification policy       : proceed / assume / clarify / abstain.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from truth_assurance_pipeline.tap_e1_intent import (
    ambiguity as amb_mod, clarification as clar_mod, conflicts as conf_mod,
    extraction as ext_mod,
)
from truth_assurance_pipeline.tap_e1_intent.clarification import Decision
from truth_assurance_pipeline.tap_e1_intent.provenance import ProvenanceLedger
from truth_assurance_pipeline.tap_e1_intent.schema import (
    SCHEMA_VERSION, AmbiguityItem, CandidateInterpretation, ConfidenceVector,
    Constraint, ConstraintPolarity, ConflictItem, Entity, IntentRecord,
    InterpretationStatus, Provenance, ProvenanceKind, RawUserRequest, Span,
    TaskType, TemporalConstraint, stable_hash,
)


# --------------------------------------------------------------------------- #
# Ablation configuration                                                      #
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class AblationConfig:
    name: str
    structured: bool          # produce a typed IntentRecord (V1+)
    deterministic: bool       # run deterministic-first extraction (V2+)
    provenance: bool          # enforce append-only provenance kinds (V3+)
    ambiguity_conflict: bool  # detect ambiguity/conflict, emit candidates (V4+)
    clarification: bool       # run clarification/abstention policy (V5+)
    description: str


ABLATIONS: Tuple[AblationConfig, ...] = (
    AblationConfig("V0", False, False, False, False, False,
                   "raw model interpretation (single reading; may answer)"),
    AblationConfig("V1", True, False, False, False, False,
                   "structured schema only (naive heuristics; over-claims provenance)"),
    AblationConfig("V2", True, True, False, False, False,
                   "deterministic extraction + structured schema"),
    AblationConfig("V3", True, True, True, False, False,
                   "V2 + provenance enforcement"),
    AblationConfig("V4", True, True, True, True, False,
                   "V3 + ambiguity/conflict detection"),
    AblationConfig("V5", True, True, True, True, True,
                   "V4 + clarification/abstention policy"),
)


def config(name: str) -> AblationConfig:
    for c in ABLATIONS:
        if c.name == name:
            return c
    raise KeyError(name)


# --------------------------------------------------------------------------- #
# Shared lexical helpers                                                       #
# --------------------------------------------------------------------------- #

_VERB_TASK = {
    "summarize": TaskType.SUMMARIZATION, "summarise": TaskType.SUMMARIZATION,
    "compare": TaskType.COMPARISON,
    "explain": TaskType.FACTUAL_ANSWER, "list": TaskType.FACTUAL_ANSWER,
    "edit": TaskType.DOCUMENT_EDIT, "rewrite": TaskType.DOCUMENT_EDIT,
    "update": TaskType.DOCUMENT_EDIT, "shorten": TaskType.DOCUMENT_EDIT,
    "reformat": TaskType.DOCUMENT_EDIT, "replace": TaskType.DOCUMENT_EDIT,
    "translate": TaskType.DOCUMENT_EDIT, "redact": TaskType.DOCUMENT_EDIT,
    "format": TaskType.DOCUMENT_EDIT, "capitalize": TaskType.DOCUMENT_EDIT,
    "fix": TaskType.DOCUMENT_EDIT, "tidy": TaskType.REPOSITORY_MODIFICATION,
    "write": TaskType.DOCUMENT_CREATE, "draft": TaskType.DOCUMENT_CREATE,
    "create": TaskType.DOCUMENT_CREATE, "generate": TaskType.DOCUMENT_CREATE,
    "add": TaskType.REPOSITORY_MODIFICATION, "remove": TaskType.REPOSITORY_MODIFICATION,
    "delete": TaskType.REPOSITORY_MODIFICATION, "refactor": TaskType.REPOSITORY_MODIFICATION,
    "rename": TaskType.REPOSITORY_MODIFICATION, "bump": TaskType.REPOSITORY_MODIFICATION,
    "optimize": TaskType.REPOSITORY_MODIFICATION, "implement": TaskType.REPOSITORY_MODIFICATION,
    "set": TaskType.REPOSITORY_MODIFICATION, "cap": TaskType.REPOSITORY_MODIFICATION,
    "make": TaskType.REPOSITORY_MODIFICATION, "clean": TaskType.DOCUMENT_EDIT,
    "analyze": TaskType.ANALYSIS, "analyse": TaskType.ANALYSIS,
    "validate": TaskType.ANALYSIS, "count": TaskType.ANALYSIS,
    "filter": TaskType.ANALYSIS, "extract": TaskType.ANALYSIS, "read": TaskType.ANALYSIS,
    "schedule": TaskType.ACTION_REQUEST, "send": TaskType.ACTION_REQUEST,
    "ship": TaskType.ACTION_REQUEST, "deploy": TaskType.ACTION_REQUEST,
    "run": TaskType.ACTION_REQUEST, "merge": TaskType.REPOSITORY_MODIFICATION,
    "split": TaskType.DOCUMENT_EDIT, "migrate": TaskType.REPOSITORY_MODIFICATION,
    "reduce": TaskType.REPOSITORY_MODIFICATION, "anonymize": TaskType.ANALYSIS,
    "convert": TaskType.DOCUMENT_EDIT, "back": TaskType.ACTION_REQUEST,
    "improve": TaskType.REPOSITORY_MODIFICATION, "handle": TaskType.UNKNOWN,
    "finish": TaskType.UNKNOWN, "apply": TaskType.REPOSITORY_MODIFICATION,
    "use": TaskType.REPOSITORY_MODIFICATION, "change": TaskType.REPOSITORY_MODIFICATION,
    "keep": TaskType.DOCUMENT_EDIT, "give": TaskType.REPOSITORY_MODIFICATION,
    "label": TaskType.REPOSITORY_MODIFICATION,
}

_QUESTION_WORD = re.compile(r"^\s*(what|who|when|where|which|how|why)\b", re.I)
_QUESTION_WORDS = frozenset(("what", "who", "when", "where", "which", "how", "why"))
_PRONOUN_ONLY_TARGET = re.compile(r"^\s*(fix|change back|do the same|merge)\b", re.I)


def _first_word(text: str) -> str:
    m = re.search(r"[A-Za-z]+", text)
    return m.group(0).lower() if m else ""


def _tokens(text: str) -> List[str]:
    return re.findall(r"[A-Za-z][A-Za-z_-]+", text)


# --------------------------------------------------------------------------- #
# The layer                                                                   #
# --------------------------------------------------------------------------- #

class IntentUnderstandingLayer:
    def __init__(self, cfg: AblationConfig):
        self.cfg = cfg

    def interpret(self, request: RawUserRequest) -> IntentRecord:
        if not self.cfg.structured:
            return self._v0_raw(request)
        return self._structured(request)

    # ---- V0: raw single-reading interpretation ------------------------------
    def _v0_raw(self, request: RawUserRequest) -> IntentRecord:
        text = request.text
        low = text.lower()
        verb = self._leading_verb_naive(text)
        task = _VERB_TASK.get(verb, TaskType.UNKNOWN)
        if _QUESTION_WORD.match(text):
            task = TaskType.FACTUAL_ANSWER

        entities = self._naive_entities(text)
        # NAIVE FLAW 1: object right after "do not <verb>" is grabbed as the action,
        # reversing the prohibition.
        objective = self._naive_objective(text, verb)
        # NAIVE FLAW 2: for a factual question the raw variant *answers* it.
        requested_output = ""
        speculative_answer = ""
        if task is TaskType.FACTUAL_ANSWER:
            speculative_answer = "<the layer produced a direct answer here>"
            requested_output = speculative_answer

        return IntentRecord(
            schema_version=SCHEMA_VERSION,
            request_id=request.request_id,
            source_text_hash=request.text_hash,
            primary_objective=objective,
            task_type=task,
            requested_output=requested_output,
            target_object=(entities[0].text if entities else None),
            entities=tuple(entities),
            explicit_constraints=(),           # naive: constraints dropped entirely
            interpretation_status=InterpretationStatus.RESOLVED,  # always commits
            selected_interpretation=objective,
            clarification_required=False,
            confidence_vector=None,
            provenance=(),                     # no provenance at all
            stated_assumptions=(("__ANSWERED__",) if speculative_answer else ()),
        )

    # ---- V1..V5: structured -------------------------------------------------
    def _structured(self, request: RawUserRequest) -> IntentRecord:
        cfg = self.cfg
        text = request.text
        low = text.lower()
        ledger = ProvenanceLedger()

        det = ext_mod.run_extraction(text) if cfg.deterministic else None

        # --- task type & objective ------------------------------------------
        if cfg.deterministic and det is not None:
            verb = self._leading_verb_deterministic(text, det)
        else:
            verb = self._leading_verb_naive(text)
        task = _VERB_TASK.get(verb, TaskType.UNKNOWN)
        if _QUESTION_WORD.match(text):
            task = TaskType.FACTUAL_ANSWER

        objective = self._objective(text, verb, det, cfg)

        # --- entities --------------------------------------------------------
        entities = self._entities(text, det, cfg, ledger)

        # --- constraints -----------------------------------------------------
        constraints: Tuple[Constraint, ...] = ()
        scope_constraints: Tuple[Constraint, ...] = ()
        temporal: Tuple[TemporalConstraint, ...] = ()
        if cfg.deterministic and det is not None:
            constraints = tuple(self._restamp(c, cfg, ledger, f"constraint[{i}]")
                                for i, c in enumerate(det.constraints))
            temporal = tuple(self._restamp_temporal(t, cfg, ledger, f"temporal[{i}]")
                             for i, t in enumerate(det.temporal))
        # V1 (naive, no deterministic): constraints are NOT extracted -> dropped.

        # --- output format (default assumption is visible & removable) -------
        requested_output, ro_prov_kind = self._requested_output(text, det, task, cfg)
        if cfg.provenance:
            ledger.record("requested_output", ro_prov_kind, requested_output)
        elif cfg.structured:
            ledger.record("requested_output", ProvenanceKind.EXPLICIT_TEXT,
                          requested_output)  # V1/V2 over-claim

        # --- references / conversation dependencies -------------------------
        refs, conv_deps, references_prior = self._references(request)

        # --- ambiguity / conflict -------------------------------------------
        ambiguity_items: Tuple[AmbiguityItem, ...] = ()
        conflict_items: Tuple[ConflictItem, ...] = ()
        candidates: Tuple[CandidateInterpretation, ...] = ()
        status = InterpretationStatus.RESOLVED
        clarification_required = False
        clar_questions = ()
        missing: Tuple[str, ...] = ()
        assumptions: Tuple[str, ...] = ()

        amb_res = None
        conf_res = None
        if cfg.ambiguity_conflict:
            amb_res = amb_mod.detect(
                text, request.conversation,
                task_is_document_edit=(task in (TaskType.DOCUMENT_EDIT,)))
            conf_res = conf_mod.detect(text, constraints, request.conversation)
            ambiguity_items = amb_res.items
            conflict_items = conf_res.items
            candidates = self._candidates(text, objective, amb_res, conf_res)
            if amb_res.material or conf_res.items:
                # V4 (no clarification policy): represent, do not resolve silently.
                status = (InterpretationStatus.CONFLICTING if conf_res.items
                          else InterpretationStatus.AMBIGUOUS)
            missing = tuple(a.dimension for a in amb_res.material)

        # --- clarification / abstention policy ------------------------------
        if cfg.clarification:
            actionable = self._has_actionable_content(text, verb, task)
            outcome = clar_mod.decide(
                amb_res if amb_res is not None else amb_mod.AmbiguityResult((), ()),
                conf_res if conf_res is not None else conf_mod.ConflictResult(()),
                request.conversation,
                has_actionable_content=actionable,
                references_prior_context=references_prior)
            status = outcome.status
            clarification_required = outcome.clarification_required
            clar_questions = outcome.questions
            assumptions = assumptions + outcome.assumptions

        selected = None if (clarification_required or
                            status in (InterpretationStatus.ABSTAINED,
                                       InterpretationStatus.CONFLICTING,
                                       InterpretationStatus.AMBIGUOUS,
                                       InterpretationStatus.INSUFFICIENT_CONTEXT)) \
            else objective

        confidence = self._confidence(det, entities, constraints, task, verb,
                                      references_prior and not request.conversation,
                                      clarification_required, cfg)

        # provenance completeness for objective / task_type / entities
        if cfg.provenance:
            ledger.record("primary_objective", ProvenanceKind.MODEL_INFERENCE, objective)
            ledger.record("task_type",
                          ProvenanceKind.DETERMINISTIC_EXTRACTION if cfg.deterministic
                          else ProvenanceKind.MODEL_INFERENCE, task.value)
        elif cfg.structured:
            ledger.record("primary_objective", ProvenanceKind.EXPLICIT_TEXT, objective)
            ledger.record("task_type", ProvenanceKind.EXPLICIT_TEXT, task.value)

        return IntentRecord(
            schema_version=SCHEMA_VERSION,
            request_id=request.request_id,
            source_text_hash=request.text_hash,
            primary_objective=objective,
            task_type=task,
            requested_output=requested_output,
            target_object=self._target(entities),
            entities=entities,
            explicit_constraints=tuple(
                c for c in constraints if c.polarity is ConstraintPolarity.REQUIREMENT
                or c.polarity is ConstraintPolarity.PROHIBITION),
            temporal_constraints=temporal,
            scope_constraints=scope_constraints,
            stated_assumptions=assumptions,
            references=refs,
            conversation_dependencies=conv_deps,
            ambiguity_items=ambiguity_items,
            missing_information=missing,
            conflicting_instructions=conflict_items,
            candidate_interpretations=candidates,
            selected_interpretation=selected,
            interpretation_status=status,
            clarification_required=clarification_required,
            clarification_questions=clar_questions,
            confidence_vector=confidence,
            provenance=ledger.entries(),
        )

    # ---- naive helpers (V0/V1) ---------------------------------------------
    def _leading_verb_naive(self, text: str) -> str:
        for tok in _tokens(text):
            t = tok.lower()
            if t in _VERB_TASK:
                return t          # picks the FIRST verb, even inside "do not ..."
        return _first_word(text)

    def _naive_entities(self, text: str) -> List[Entity]:
        out: List[Entity] = []
        seen = set()
        # quoted strings
        for m in re.finditer(r"[\"“”']([^\"“”']{1,60})[\"“”']", text):
            e = m.group(1)
            if e.lower() not in seen:
                seen.add(e.lower())
                out.append(Entity(e, "reference",
                                  Provenance(ProvenanceKind.EXPLICIT_TEXT,
                                             (Span(m.start(1), m.end(1), e),))))
        # NAIVE FLAW: grab every capitalized token, including sentence-initial verb
        for m in re.finditer(r"\b[A-Z][A-Za-z0-9_]+\b", text):
            e = m.group(0)
            if e.lower() not in seen:
                seen.add(e.lower())
                out.append(Entity(e, "topic",
                                  Provenance(ProvenanceKind.EXPLICIT_TEXT,
                                             (Span(m.start(), m.end(), e),))))
        return out

    def _naive_objective(self, text: str, verb: str) -> str:
        # If "do not <verb> <obj>" appears, the naive reader still frames <verb>
        # <obj> as the objective -> prohibition reversal.
        m = re.search(r"do not\s+(\w+)\s+([\w ]{0,30})", text.lower())
        if m:
            return f"{m.group(1)} {m.group(2)}".strip()
        return text.strip().rstrip(".")

    # ---- deterministic helpers (V2+) ---------------------------------------
    def _leading_verb_deterministic(self, text: str,
                                    det: ext_mod.DeterministicExtraction) -> str:
        prohibited_spans = [c.provenance.spans[0] for c in det.constraints
                            if c.polarity is ConstraintPolarity.PROHIBITION
                            and c.provenance.spans]
        for verb, span in det.imperatives:
            # skip any imperative whose span falls inside a prohibition clause
            if any(ps.start <= span.start < ps.end for ps in prohibited_spans):
                continue
            return verb
        # fall back to first token verb not inside a prohibition
        return self._leading_verb_naive(text)

    def _objective(self, text, verb, det, cfg) -> str:
        if not cfg.deterministic or det is None:
            return self._naive_objective(text, verb)
        # deterministic: never frame a prohibited verb+object as the objective
        clean = text.strip().rstrip(".")
        prohibited_spans = [c.provenance.spans[0] for c in det.constraints
                            if c.polarity is ConstraintPolarity.PROHIBITION
                            and c.provenance.spans]
        # objective = leading imperative clause up to first prohibition/",but"
        cut = len(clean)
        for ps in prohibited_spans:
            cut = min(cut, ps.start)
        m = re.search(r",?\s*\b(but|without|and never|and do not)\b", clean.lower())
        if m:
            cut = min(cut, m.start())
        obj = clean[:cut].strip().rstrip(",").strip()
        return obj or clean

    def _entities(self, text, det, cfg, ledger) -> Tuple[Entity, ...]:
        if not cfg.deterministic or det is None:
            ents = self._naive_entities(text)
            if cfg.provenance:
                for i, e in enumerate(ents):
                    ledger.record(f"entity[{i}]", ProvenanceKind.MODEL_INFERENCE, e.text)
            elif cfg.structured:
                for i, e in enumerate(ents):
                    ledger.record(f"entity[{i}]", ProvenanceKind.EXPLICIT_TEXT, e.text)
            return tuple(ents)

        out: List[Entity] = []
        seen = set()

        def add(txt, role, span, kind):
            k = txt.lower()
            if k in seen or not txt.strip():
                return
            seen.add(k)
            prov = Provenance(kind, (span,) if span else ())
            out.append(Entity(txt, role, prov))
            if cfg.provenance:
                ledger.record(f"entity[{len(out)-1}]", kind, txt)
            else:
                ledger.record(f"entity[{len(out)-1}]", ProvenanceKind.EXPLICIT_TEXT, txt)

        for s in det.filenames:
            add(s.text, "target_object", s, ProvenanceKind.DETERMINISTIC_EXTRACTION)
        for s in det.quotes:
            add(s.text, "reference", s, ProvenanceKind.DETERMINISTIC_EXTRACTION)
        for s in det.identifiers:
            add(s.text, "reference", s, ProvenanceKind.DETERMINISTIC_EXTRACTION)
        for s in det.numbers:
            add(s.text, "value", s, ProvenanceKind.DETERMINISTIC_EXTRACTION)
        # proper-noun-ish multiword capitalized phrases. Strip a leading question
        # word or imperative verb so "What"/"Fix"/"Update" are never emitted as
        # entities (that would be an invented entity).
        _skip_lead = _QUESTION_WORDS | set(_VERB_TASK.keys()) | {
            "the", "a", "an", "please", "just", "now", "then"}
        for m in re.finditer(r"\b[A-Z][A-Za-z0-9_]+(?:\s+[A-Z][A-Za-z0-9_]+)*\b", text):
            toks = m.group(0).split()
            offset = m.start()
            while toks and toks[0].lower() in _skip_lead:
                offset += len(toks[0]) + 1
                toks = toks[1:]
            if not toks:
                continue
            phrase = " ".join(toks)
            add(phrase, "topic", Span(offset, offset + len(phrase), phrase),
                ProvenanceKind.DETERMINISTIC_EXTRACTION)
        return tuple(out)

    def _restamp(self, c: Constraint, cfg, ledger, path) -> Constraint:
        if cfg.provenance:
            ledger.record(path, c.provenance.kind, c.text)
            return c
        # V2 keeps deterministic provenance but still records; V1 never reaches here
        ledger.record(path, ProvenanceKind.EXPLICIT_TEXT, c.text)
        return c

    def _restamp_temporal(self, t: TemporalConstraint, cfg, ledger, path
                          ) -> TemporalConstraint:
        if cfg.provenance:
            ledger.record(path, t.provenance.kind, t.text)
        else:
            ledger.record(path, ProvenanceKind.EXPLICIT_TEXT, t.text)
        return t

    def _requested_output(self, text, det, task, cfg
                          ) -> Tuple[str, ProvenanceKind]:
        low = text.lower()
        if cfg.deterministic and det is not None and det.output_formats:
            fmt = det.output_formats[0][0]
            return f"output in {fmt}", ProvenanceKind.DETERMINISTIC_EXTRACTION
        for fmt in ext_mod.OUTPUT_FORMATS:
            if re.search(r"\b" + re.escape(fmt) + r"\b", low):
                return f"output in {fmt}", (ProvenanceKind.DETERMINISTIC_EXTRACTION
                                            if cfg.deterministic
                                            else ProvenanceKind.MODEL_INFERENCE)
        # default assumption (visible, removable)
        default = {
            TaskType.FACTUAL_ANSWER: "a direct textual answer (assumed)",
            TaskType.SUMMARIZATION: "a summary (assumed)",
            TaskType.DOCUMENT_EDIT: "the edited document (assumed)",
            TaskType.DOCUMENT_CREATE: "a new document (assumed)",
            TaskType.REPOSITORY_MODIFICATION: "a code change (assumed)",
            TaskType.ANALYSIS: "an analysis result (assumed)",
            TaskType.ACTION_REQUEST: "the action performed (assumed)",
        }.get(task, "unspecified (assumed)")
        return default, ProvenanceKind.DEFAULT_ASSUMPTION

    def _references(self, request: RawUserRequest):
        text = request.text
        low = text.lower()
        refs: List[str] = []
        conv_deps: List[str] = []
        references_prior = False
        for pron in ("it", "them", "that value", "the same", "the same change",
                     "change back", "the usual"):
            if re.search(r"\b" + re.escape(pron) + r"\b", low):
                references_prior = True
                # try to resolve from conversation (last user turn noun phrase)
                resolved = self._resolve_from_context(request.conversation)
                if resolved:
                    conv_deps.append(f"{pron} -> {resolved}")
                    refs.append(resolved)
                else:
                    refs.append(pron)
                break
        # definite reference words also imply potential prior dependency
        return tuple(refs), tuple(conv_deps), references_prior

    def _resolve_from_context(self, conversation) -> Optional[str]:
        if not conversation:
            return None
        phrases = []
        for turn in conversation:
            if turn.role != "user":
                continue
            for m in re.finditer(r"\b(?:the|a|an|my)\s+([a-z][a-z_]+(?:\s+[a-z][a-z_]+){0,3})",
                                 turn.text.lower()):
                phrases.append(m.group(1).strip())
        heads = {p.split()[-1] for p in phrases}
        if len(phrases) == 1 or (len(heads) == 1 and phrases):
            return phrases[0]
        return None

    def _candidates(self, text, objective, amb_res, conf_res
                    ) -> Tuple[CandidateInterpretation, ...]:
        if not amb_res.material and not conf_res.items:
            return ()
        out: List[CandidateInterpretation] = []
        # produce two readings per material ambiguity dimension (bounded)
        dim = (amb_res.material[0].dimension if amb_res.material
               else conf_res.items[0].kind.value)
        out.append(CandidateInterpretation(
            "A", objective, ("leading imperative in the request",),
            (f"unresolved: {dim}",), (dim,), 0.5,
            "acts on the wrong target / scope"))
        out.append(CandidateInterpretation(
            "B", f"alternative reading given {dim}", (f"ambiguity on {dim}",),
            ("leading imperative",), (dim,), 0.5,
            "performs a different operation than intended"))
        return tuple(out)

    def _has_actionable_content(self, text, verb, task) -> bool:
        # No recognizable operation AND no concrete object -> not actionable.
        if verb in _VERB_TASK and task is not TaskType.UNKNOWN:
            return True
        # bare "fix it" / "change back" -> has a verb but no target
        if _PRONOUN_ONLY_TARGET.match(text) and len(_tokens(text)) <= 3:
            return True   # actionable *intent* exists, just underspecified target
        return bool(_tokens(text))

    def _target(self, entities: Tuple[Entity, ...]) -> Optional[str]:
        for e in entities:
            if e.role == "target_object":
                return e.text
        return entities[0].text if entities else None

    def _confidence(self, det, entities, constraints, task, verb,
                    missing_context, clarification, cfg) -> ConfidenceVector:
        deterministic = cfg.deterministic and det is not None
        obj_c = 0.9 if verb in _VERB_TASK else 0.4
        ent_c = 0.85 if (deterministic and entities) else (0.6 if entities else 0.3)
        con_c = 0.9 if (deterministic and constraints) else (0.5 if constraints else 0.6)
        ref_c = 0.3 if missing_context else 0.9
        task_c = 0.9 if task is not TaskType.UNKNOWN else 0.3
        clar_c = 0.9 if clarification else 0.7
        return ConfidenceVector(obj_c, ent_c, con_c, ref_c, task_c, clar_c)
