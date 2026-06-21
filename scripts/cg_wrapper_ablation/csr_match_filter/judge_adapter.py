"""judge_adapter.py — pluggable answer judges for the Phase 2B robustness eval.

A Judge scores one answer against the pre-registered rubric and returns structured JSON:
  {primary_frame_correct, secondary_handling_correct, rejected_domain_avoidance,
   phoneme_overreach, factuality_preserved, clarity_score, must_include_recall,
   must_not_violation_rate, reasons: [...]}

DeterministicRubricJudge applies the locked rubric (rubric.py) — judge_backend=deterministic_rubric,
production_valid=partial. StubJudge is for tests. LLMJudgeAdapter is an optional independent LLM judge
(env-configured; never required, no keys for tests) — judge_backend=real_llm_judge,
production_valid=stronger. No Phase 1/2 scoring logic is modified here.
"""

from __future__ import annotations

import json
import re
from typing import Dict, List, Optional

from . import rubric as RB


class Judge:
    judge_backend = "abstract"
    production_valid = "none"

    def score(self, query: str, answer: str, example: Dict, terms: Optional[List[str]] = None) -> Dict:
        raise NotImplementedError


def _secondary_promoted(answer: str, example: Dict) -> bool:
    """Rule 4: expected-secondary asserted while expected-primary is NOT asserted."""
    prim = RB.asserted_domains(answer, example.get("expected_primary", []))
    sec = RB.asserted_domains(answer, example.get("expected_secondary", []))
    return bool(sec) and not bool(prim)


class DeterministicRubricJudge(Judge):
    judge_backend = "deterministic_rubric"
    production_valid = "partial"

    def __init__(self, rubric_cfg: Optional[Dict] = None):
        self.rubric_cfg = rubric_cfg or {}
        self.rubric_version = (rubric_cfg or {}).get("version", "framed_answer_rubric_v1")
        self.is_v2 = "v2" in self.rubric_version

    def score(self, query, answer, example, terms=None) -> Dict:
        if self.is_v2:
            s = RB.score_answer_v2(answer, example, terms)
            promoted = bool(s["rejected_domain_promotion"])
            pfc = bool(s["primary_frame_correct"])
            alt = bool(s["alternate_true_sense_mention"])
        else:
            s = RB.score_answer(answer, example, terms)
            promoted = _secondary_promoted(answer, example)
            pfc = bool(s["primary_frame_correct"]) and not promoted
            alt = False
        reasons = []
        if not pfc:
            reasons.append("primary not asserted, rejected asserted, or non-primary promoted")
        if promoted:
            reasons.append("non-primary sense promoted to primary")
        if s["rejected_domain_avoidance"] == 0.0:
            reasons.append(f"rejected leak: {s.get('_mentioned_rejected')}")
        if s["phoneme_overreach_rate"]:
            reasons.append("phoneme-overreach assertion")
        if s["factuality_preserved"] == 0.0:
            reasons.append("factuality not preserved (false claim)")
        return {
            "primary_frame_correct": pfc,
            "secondary_handling_correct": bool(s["secondary_handling_correct"]) and not promoted,
            "rejected_domain_avoidance": bool(s["rejected_domain_avoidance"]),
            "phoneme_overreach": bool(s["phoneme_overreach_rate"]),
            "factuality_preserved": bool(s["factuality_preserved"]),
            "clarity_score": float(s["answer_clarity_proxy"]),
            "must_include_recall": s["must_include_recall"],
            "must_not_violation_rate": s["must_not_violation_rate"],
            "secondary_promoted": promoted,
            "alternate_true_sense_mention": alt,
            "rubric_version": self.rubric_version,
            "reasons": reasons,
        }


class StubJudge(Judge):
    """Deterministic fixed-shape judge for tests (always 'perfect' unless answer is empty)."""
    judge_backend = "stub_judge"
    production_valid = "none"

    def score(self, query, answer, example, terms=None) -> Dict:
        ok = bool((answer or "").strip())
        return {"primary_frame_correct": ok, "secondary_handling_correct": ok,
                "rejected_domain_avoidance": ok, "phoneme_overreach": False,
                "factuality_preserved": ok, "clarity_score": 1.0 if ok else 0.0,
                "must_include_recall": 1.0 if ok else 0.0, "must_not_violation_rate": 0.0,
                "secondary_promoted": False, "reasons": [] if ok else ["empty answer"]}


_JUDGE_KEYS = ("primary_frame_correct", "secondary_handling_correct", "rejected_domain_avoidance",
               "phoneme_overreach", "factuality_preserved", "clarity_score")


class LLMJudgeAdapter(Judge):
    """Independent LLM judge: prompts a model to grade the answer vs the rubric, parses JSON.

    Falls back to the deterministic judge for any field the model omits, so output schema is stable.
    """
    judge_backend = "real_llm_judge"
    production_valid = "stronger"

    def __init__(self, llm, rubric_cfg: Optional[Dict] = None):
        self.llm = llm
        self.backstop = DeterministicRubricJudge(rubric_cfg)

    def _prompt(self, query, answer, example) -> str:
        return (
            "You are a strict evaluator. Grade the ANSWER against the rubric and reply with ONLY a "
            "JSON object with boolean keys primary_frame_correct, secondary_handling_correct, "
            "rejected_domain_avoidance, phoneme_overreach, factuality_preserved and a float "
            "clarity_score in [0,1].\n"
            "Rules: (1) phoneme-overreach is TRUE only if the answer ASSERTS that sound/phonemes prove "
            "meaning; merely mentioning or denying it is FALSE. (2) Naming a rejected domain only to "
            "REFUTE it is NOT a leak. (3) A secondary domain promoted above the primary is a framing "
            "error. (4) Factuality is independent of frame compliance.\n"
            f"Expected primary: {example.get('expected_primary')}\n"
            f"Expected secondary: {example.get('expected_secondary')}\n"
            f"Rejected (must not be framed as the answer): {example.get('expected_rejected')}\n"
            f"Question: {query}\nANSWER: {answer}\nJSON:")

    def score(self, query, answer, example, terms=None) -> Dict:
        out = self.backstop.score(query, answer, example, terms)   # backstop for missing fields
        try:
            raw = self.llm.generate(self._prompt(query, answer, example))
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            parsed = json.loads(m.group(0)) if m else {}
            for k in _JUDGE_KEYS:
                if k in parsed:
                    out[k] = (bool(parsed[k]) if k != "clarity_score" else float(parsed[k]))
            out["reasons"] = parsed.get("reasons", out["reasons"])
            out["_judge"] = "real_llm_judge"
        except Exception as exc:
            out["_judge"] = f"llm_judge_failed_backstopped: {type(exc).__name__}"
        return out


def load_judge(backend: str = "deterministic", rubric_cfg: Optional[Dict] = None, llm=None):
    """Return (judge, info). backend in {deterministic, stub, llm}."""
    if backend == "stub":
        return StubJudge(), "stub_judge"
    if backend == "llm":
        if llm is None:
            return DeterministicRubricJudge(rubric_cfg), "llm judge requested but no LLM -> deterministic"
        return LLMJudgeAdapter(llm, rubric_cfg), "real_llm_judge"
    return DeterministicRubricJudge(rubric_cfg), "deterministic_rubric"
