"""The composite-threat monitor: stateful accumulator + recipe matcher.

This is the engine. It ingests a stream of events (each an *individually*
admissible action, in the digital case), groups them by ``correlation_id``,
accumulates the capability fragments each contributes, and — after every event —
re-matches the accumulated fragments against the ontology's recipes. When a
correlation crosses an advisory threshold for a recipe, it emits a
:class:`Finding` reconstructing the assembled "story".

Design properties
-----------------
* **Deterministic.** No wall-clock, no randomness. Fragment arrival order within
  a correlation is a monotone counter; ties in matching are broken by sorted ids.
  The same event stream always yields the same findings and finding digests.
* **Escalate-only.** A finding's ``signal`` is always ``OBSERVE`` or
  ``ESCALATE`` — never ALLOW/DENY. The monitor produces *advisory evidence*; the
  Action Gate remains the sole decider (spec §3/§12).
* **Windowed.** Structuring attacks spread steps out to slip under per-action
  thresholds; ``window_actions`` bounds how many recent steps per correlation
  are retained, so "assembly" means "within a bounded span", not "ever".
* **Edge-triggered.** ``observe`` returns only findings whose signal *rose* on
  this event, so a caller is not spammed with an unchanged standing finding.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import signals
from .canonical import digest
from .model import FragmentInstance, Ontology
from .narrative import build_story

_TRAILING_INT = re.compile(r"(\d+)\s*$")


@dataclass(frozen=True)
class Finding:
    """One advisory finding: a reconstructed composite-threat story."""

    finding_id: str            # deterministic digest of the finding's content
    ontology_id: str
    ontology_version: str
    correlation_id: str
    recipe_id: str
    signal: str                # OBSERVE | ESCALATE  (never ALLOW/DENY)
    completeness: float        # |present ∩ required| / |required|
    story: dict
    at_position: int           # arrival position of the event that triggered it
    at_sequence_id: str

    def to_dict(self) -> dict:
        return {
            "finding_id": self.finding_id,
            "ontology_id": self.ontology_id,
            "ontology_version": self.ontology_version,
            "correlation_id": self.correlation_id,
            "recipe_id": self.recipe_id,
            "signal": self.signal,
            "completeness": self.completeness,
            "at_position": self.at_position,
            "at_sequence_id": self.at_sequence_id,
            "story": self.story,
        }


@dataclass
class _CorrelationState:
    instances: list[FragmentInstance] = field(default_factory=list)
    count: int = 0  # monotone arrival counter (defines position)
    # last advisory signal emitted per recipe, to make emission edge-triggered
    last_signal: dict[str, str] = field(default_factory=dict)


class CompositeThreatMonitor:
    """Accumulate fragments per correlation and emit advisory findings."""

    def __init__(
        self,
        ontology: Ontology,
        *,
        window_actions: int | None = None,
        observe_at: float = 0.5,
        escalate_at: float = 1.0,
    ) -> None:
        if window_actions is not None and window_actions < 1:
            raise ValueError("window_actions must be >= 1 or None")
        if not 0.0 < observe_at <= escalate_at <= 1.0:
            raise ValueError("thresholds must satisfy 0 < observe_at <= escalate_at <= 1")
        self.ontology = ontology
        self.window_actions = window_actions
        self.observe_at = observe_at
        self.escalate_at = escalate_at
        self._state: dict[str, _CorrelationState] = {}

    # -- ingestion ---------------------------------------------------------
    def observe(self, event: dict) -> list[Finding]:
        """Ingest one event; return findings whose signal ROSE on this event.

        ``event`` must carry ``correlation_id`` and ``sequence_id``; the rest is
        interpreted by the ontology's extractor.
        """
        cid = str(event["correlation_id"])
        st = self._state.setdefault(cid, _CorrelationState())
        position = self._position(event, st)
        st.count = max(st.count, position + 1)

        for inst in self.ontology.extract(event, cid, position):
            st.instances.append(inst)

        if self.window_actions is not None:
            floor = st.count - self.window_actions
            if floor > 0:
                st.instances = [i for i in st.instances if i.position >= floor]

        return self._match(cid, st, position, str(event.get("sequence_id", "")))

    def _position(self, event: dict, st: _CorrelationState) -> int:
        """Deterministic arrival position within the correlation.

        Prefer a trailing integer in ``sequence_id`` (the spec's monotonic
        ``correlation_id:NNNN`` convention); fall back to the arrival counter.
        """
        m = _TRAILING_INT.search(str(event.get("sequence_id", "")))
        if m:
            return int(m.group(1))
        return st.count

    # -- matching ----------------------------------------------------------
    def _match(self, cid, st, position, sequence_id) -> list[Finding]:
        present = {i.fragment_id for i in st.instances}
        risen: list[Finding] = []
        for recipe in self.ontology.recipes:
            hit = recipe.required & present
            completeness = len(hit) / len(recipe.required)
            signal = signals.signal_for(
                completeness, observe_at=self.observe_at, escalate_at=self.escalate_at)
            prev = st.last_signal.get(recipe.recipe_id, signals.NONE)
            if signal == signals.NONE:
                continue
            assert signals.is_advisory(signal)  # invariant: escalate-only
            st.last_signal[recipe.recipe_id] = signal
            if signals.rank(signal) <= signals.rank(prev):
                continue  # edge-triggered: only surface when concern rises
            story = build_story(self.ontology, recipe, st.instances)
            risen.append(self._finding(cid, recipe, signal, completeness,
                                       story, position, sequence_id))
        return risen

    def _finding(self, cid, recipe, signal, completeness, story,
                 position, sequence_id) -> Finding:
        body = {
            "ontology_id": self.ontology.ontology_id,
            "ontology_version": self.ontology.version,
            "correlation_id": cid,
            "recipe_id": recipe.recipe_id,
            "signal": signal,
            "completeness": completeness,
            "story": story,
        }
        return Finding(
            finding_id=digest(body, domain="CTD-FINDING"),
            ontology_id=self.ontology.ontology_id,
            ontology_version=self.ontology.version,
            correlation_id=cid,
            recipe_id=recipe.recipe_id,
            signal=signal,
            completeness=completeness,
            story=story,
            at_position=position,
            at_sequence_id=sequence_id,
        )

    # -- reporting ---------------------------------------------------------
    def standing_findings(self, correlation_id: str) -> list[Finding]:
        """All currently-active (signal != NONE) findings for a correlation.

        Unlike :meth:`observe`, this is level-triggered — it reports the current
        standing state regardless of whether it rose on the last event.
        """
        st = self._state.get(correlation_id)
        if st is None:
            return []
        present = {i.fragment_id for i in st.instances}
        out: list[Finding] = []
        last_pos = max((i.position for i in st.instances), default=0)
        for recipe in self.ontology.recipes:
            completeness = len(recipe.required & present) / len(recipe.required)
            signal = signals.signal_for(
                completeness, observe_at=self.observe_at, escalate_at=self.escalate_at)
            if signal == signals.NONE:
                continue
            story = build_story(self.ontology, recipe, st.instances)
            out.append(self._finding(correlation_id, recipe, signal, completeness,
                                     story, last_pos, ""))
        return out
