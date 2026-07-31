"""SequenceRiskAnalyzer — orchestration and finding assembly.

Pipeline per event (all deterministic, stdlib only):

    link (entity-linkage) -> ledger (multi-timescale state) -> match (constraints)
      -> benign (evidence-gated qualification) -> completion (advisory lookahead)
      -> finding

The analyzer emits only advisory signals: ``OBSERVE`` / ``ESCALATE`` /
``UNAVAILABLE`` (never ALLOW/DENY/AUTHORIZE/BLOCK/EXECUTE). An authoritative
ActionGate or workflow policy converts an ``ESCALATE`` into a binding consequence
(see ``policy.py``); the analyzer never does. Removing or disabling the analyzer
cannot increase authority or turn a denied action into an allowed one.

Every event ingestion updates an integrity :class:`RunReport` (§11) so no silent
fallback can produce a clean-looking result: dedup suppressions, ambiguous links,
unmapped capabilities, decayed evidence, and bounded-state exhaustion are all
counted and surfaced.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from . import benign as benign_mod
from . import completion as completion_mod
from . import narrative, signals
from .canonical import digest
from .ledger import (
    ACTIVE, DECAYED, REVOKED, CapabilityLedger, LimitExceeded, StateLimits,
    TimescalePolicy,
)
from .linkage import BY_ACTOR, BY_CASE, AssemblyKeySpec, link_event
from .matcher import match
from .model import ExtractContext, Ontology
from .timeutil import event_epoch, parse_epoch

DEFAULT_SPECS: tuple[AssemblyKeySpec, ...] = (BY_CASE, BY_ACTOR)


@dataclass
class Finding:
    """Advisory sequence-risk finding (§9)."""

    finding_id: str
    signal: str
    tenant_id: str
    assembly_key: str
    key_spec: str
    ontology_id: str
    ontology_version: str
    recipe_id: str
    recipe_version: str
    severity: str
    completion_score: float
    present_fragments: list[dict]
    missing_fragments: list[str]
    ordering_status: dict
    entity_link_evidence: dict
    benign_context_evidence: dict
    completion: dict
    escalation_reason: str
    recommended_consequence: str
    explanation: str
    related_correlations: list[str]
    related_event_ids: list[str]
    first_seen_position: int | None
    last_updated_position: int
    state_expiry: dict

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RunReport:
    """Anti-confounder integrity counters (§11)."""

    analyzer_enabled: bool = True
    ontology_id: str = ""
    ontology_version: str = ""
    recipe_versions: list[str] = field(default_factory=list)
    key_specs: list[str] = field(default_factory=list)
    timescale_unit: str = ""
    events_ingested: int = 0
    lifecycle_events: int = 0
    fragments_extracted: int = 0
    events_linked: int = 0
    ambiguous_links: int = 0
    assemblies_touched: set[str] = field(default_factory=set)
    correlations_seen: set[str] = field(default_factory=set)
    duplicates_suppressed: int = 0
    retries_suppressed: int = 0
    capabilities_revoked: int = 0
    unmapped_capabilities: int = 0
    unavailable_events: int = 0
    findings_emitted: int = 0
    escalations_emitted: int = 0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["assemblies_touched"] = len(self.assemblies_touched)
        d["correlations_seen"] = len(self.correlations_seen)
        return d


@dataclass
class IngestResult:
    findings: list[Finding]
    diagnostics: dict


class SequenceRiskAnalyzer:
    """Deterministic, advisory composite-capability & sequence-risk analyzer."""

    def __init__(
        self,
        ontology: Ontology,
        *,
        specs: tuple[AssemblyKeySpec, ...] = DEFAULT_SPECS,
        timescale: TimescalePolicy | None = None,
        limits: StateLimits | None = None,
        active_policy_version: str | None = None,
    ) -> None:
        if not specs:
            raise ValueError("at least one AssemblyKeySpec is required")
        self.ontology = ontology
        self.specs = specs
        self.timescale = timescale or TimescalePolicy()
        self.limits = limits or StateLimits()
        self.active_policy_version = active_policy_version
        self.ledger = CapabilityLedger(self.timescale, self.limits)
        self._benign: dict[tuple[str, str], list] = {}
        self._last_signal: dict[tuple[str, str, str], str] = {}
        self._ingest_counter = 0
        self.report = RunReport(
            ontology_id=ontology.ontology_id,
            ontology_version=ontology.version,
            recipe_versions=sorted({r.ref for r in ontology.recipes}),
            key_specs=[s.ref for s in specs],
            timescale_unit=self.timescale.unit,
        )

    # -- ontology hot-swap (recipe-version change during an active case, §10.19) --
    def load_ontology(self, ontology: Ontology) -> None:
        """Swap the recipe library, preserving accumulated ledger state.

        Findings record the recipe version in force at emission time; existing
        assemblies keep their fragments and continue under the new recipes.
        """
        self.ontology = ontology
        self.report.ontology_version = ontology.version
        self.report.recipe_versions = sorted(
            set(self.report.recipe_versions) | {r.ref for r in ontology.recipes})

    # -- time / position ---------------------------------------------------
    def _order_coord(self, event: dict) -> tuple[int, float | None]:
        epoch = event_epoch(event)
        if "position" in event:
            pos = int(event["position"])
        else:
            seq = str(event.get("sequence_id", ""))
            digits = "".join(ch for ch in seq.rsplit(":", 1)[-1] if ch.isdigit())
            pos = int(digits) if digits else self._ingest_counter
        return pos, epoch

    # -- public API --------------------------------------------------------
    def observe(self, event: dict) -> list[Finding]:
        """Back-compat convenience: ingest and return risen findings only."""
        return self.ingest(event).findings

    def ingest(self, event: dict) -> IngestResult:
        self._ingest_counter += 1
        self.report.events_ingested += 1
        diag = {"event_id": str(event.get("event_id", "")), "linked": False,
                "fragments_extracted": 0, "duplicate": False, "retried": False,
                "ambiguous": False, "unavailable": False, "lifecycle": None}

        etype = event.get("type")
        if etype in ("close_case", "reset"):
            return self._lifecycle(event, etype, diag)

        link = link_event(event, self.specs)
        cid = link.correlation_id
        if cid:
            self.report.correlations_seen.add(cid)
        if link.ambiguous:
            self.report.ambiguous_links += 1
            diag["ambiguous"] = True
            diag["ambiguous_reasons"] = list(link.reasons)
            return IngestResult([], diag)

        pos, epoch = self._order_coord(event)
        now = float(epoch) if epoch is not None else float(pos)
        entities = link.entities

        # benign context (attach to every assembly this event links into)
        contexts = benign_mod.extract_benign_context(event, at_epoch_of=parse_epoch)

        findings: list[Finding] = []
        revokes = tuple(event.get("revokes", ()) or ())
        any_linked = False

        for al in link.links:
            if al.confidence == "AMBIGUOUS" or not al.assembly_key:
                continue
            ctx = ExtractContext(
                tenant_id=link.tenant_id, correlation_id=cid,
                sequence_id=str(event.get("sequence_id", "")),
                event_id=str(event.get("event_id", "")),
                idempotency_key=str(event.get("idempotency_key", "")),
                position=pos, at_epoch=epoch, entities=entities,
            )
            instances = self.ontology.extract(event, ctx)
            # capability tag present but unmapped ⇒ record a miss (no silent pass)
            if not instances and (event.get("capability")
                                  or (event.get("tool", {}) or {}).get("capability")):
                self.report.unmapped_capabilities += 1
                diag["unmapped_capability"] = True

            key = (link.tenant_id, al.assembly_key)
            if contexts:
                store = self._benign.setdefault(key, [])
                if len(store) < self.limits.max_instances_per_assembly:
                    store.extend(contexts)

            try:
                add = self.ledger.add(
                    link.tenant_id, al.assembly_key, al.key_spec, al.link_dims,
                    instances, now, event_id=ctx.event_id,
                    idempotency_key=ctx.idempotency_key, correlation_id=cid,
                    revokes=revokes)
            except LimitExceeded as exc:
                self.report.unavailable_events += 1
                diag["unavailable"] = True
                findings.append(self._unavailable_finding(link.tenant_id, al, exc, pos))
                continue

            any_linked = True
            self.report.assemblies_touched.add(al.assembly_key)
            self.report.fragments_extracted += len(instances)
            diag["fragments_extracted"] += len(instances)
            if add.duplicate:
                self.report.duplicates_suppressed += 1
                diag["duplicate"] = True
            if add.retried:
                self.report.retries_suppressed += 1
                diag["retried"] = True
            if add.revoked_ids:
                self.report.capabilities_revoked += len(add.revoked_ids)

            findings.extend(self._evaluate(link.tenant_id, al, now, pos))

        if any_linked:
            self.report.events_linked += 1
            diag["linked"] = True

        self.report.findings_emitted += len(findings)
        self.report.escalations_emitted += sum(
            1 for f in findings if f.signal == signals.ESCALATE)
        return IngestResult(findings, diag)

    # -- lifecycle ---------------------------------------------------------
    def _lifecycle(self, event, etype, diag) -> IngestResult:
        self.report.lifecycle_events += 1
        diag["lifecycle"] = etype
        link = link_event(event, self.specs)
        for al in link.links:
            if not al.assembly_key:
                continue
            if etype == "close_case":
                self.ledger.close_case(link.tenant_id, al.assembly_key)
            else:
                self.ledger.reset(link.tenant_id, al.assembly_key)
                self._benign.pop((link.tenant_id, al.assembly_key), None)
                for k in list(self._last_signal):
                    if k[0] == link.tenant_id and k[1] == al.assembly_key:
                        del self._last_signal[k]
        return IngestResult([], diag)

    # -- evaluation --------------------------------------------------------
    def _evaluate(self, tenant_id, al, now, pos) -> list[Finding]:
        asm = self.ledger.get(tenant_id, al.assembly_key)
        if asm is None:
            return []
        active = asm.active(now, self.timescale)
        contexts = self._benign.get((tenant_id, al.assembly_key), [])
        risen: list[Finding] = []
        for recipe in self.ontology.recipes:
            result = match(recipe, active)
            if result.signal == signals.NONE:
                # still update last_signal downward? keep monotone edge-trigger.
                continue
            benign_verdict = benign_mod.evaluate(
                recipe, contexts, asm.link_dims, now, self.active_policy_version)
            final_signal = result.signal
            if result.signal == signals.ESCALATE and \
                    benign_verdict.status == benign_mod.NEUTRALIZED:
                final_signal = signals.OBSERVE  # qualified by valid approval

            skey = (tenant_id, al.assembly_key, recipe.ref)
            prev = self._last_signal.get(skey, signals.NONE)
            self._last_signal[skey] = final_signal
            if signals.rank(final_signal) <= signals.rank(prev):
                continue  # edge-triggered: emit only when advisory concern rises
            risen.append(self._build_finding(
                tenant_id, al, asm, recipe, result, benign_verdict, final_signal, pos))
        return risen

    def _build_finding(self, tenant_id, al, asm, recipe, result, benign_verdict,
                       signal, pos) -> Finding:
        present = narrative.present_fragments(self.ontology, result)
        comp = completion_mod.analyze(result)
        related_events = sorted({s["event_id"] for s in present if s["event_id"]})
        ordering_status = {
            "ok": result.constraints["ordering_ok"],
            "constraints": result.constraints,
            "blocking_reasons": result.blocking_reasons,
            "impossible": result.impossible,
            "impossible_reason": result.impossible_reason,
        }
        link_evidence = {
            "key_spec": al.key_spec, "confidence": al.confidence,
            "link_dims": al.link_dims,
        }
        benign_evidence = {
            "status": benign_verdict.status,
            "applied": benign_verdict.applied,
            "rejected": benign_verdict.rejected,
            "explanation": benign_verdict.explanation,
        }
        state_expiry = self._state_expiry(asm)
        escalation_reason = self._reason(result, benign_verdict, signal)

        body = {
            "tenant_id": tenant_id, "assembly_key": al.assembly_key,
            "key_spec": al.key_spec, "ontology": self.ontology.ontology_id,
            "ontology_version": self.ontology.version, "recipe": recipe.ref,
            "signal": signal, "present_required": result.present_required,
            "present_optional": result.present_optional,
            "missing": result.missing_required,
            "benign_status": benign_verdict.status,
            "ordering_ok": result.constraints["ordering_ok"],
        }
        return Finding(
            finding_id=digest(body, domain="CTD-FINDING"),
            signal=signal, tenant_id=tenant_id, assembly_key=al.assembly_key,
            key_spec=al.key_spec, ontology_id=self.ontology.ontology_id,
            ontology_version=self.ontology.version, recipe_id=recipe.recipe_id,
            recipe_version=recipe.version, severity=recipe.severity,
            completion_score=result.completeness, present_fragments=present,
            missing_fragments=result.missing_required, ordering_status=ordering_status,
            entity_link_evidence=link_evidence, benign_context_evidence=benign_evidence,
            completion=asdict(comp), escalation_reason=escalation_reason,
            recommended_consequence=recipe.recommended_consequence,
            explanation=narrative.explanation(result, benign_verdict.status),
            related_correlations=sorted(asm.related_correlations),
            related_event_ids=related_events,
            first_seen_position=asm.first_position, last_updated_position=pos,
            state_expiry=state_expiry,
        )

    def _reason(self, result, benign_verdict, signal) -> str:
        if signal == signals.ESCALATE:
            return (f"All {len(result.recipe.required)} required fragments present "
                    f"and structural constraints satisfied; benign context "
                    f"{benign_verdict.status}.")
        if signal == signals.OBSERVE and not result.missing_required:
            return ("Recipe fragment-complete but escalation withheld: "
                    + ("; ".join(result.blocking_reasons)
                       if result.blocking_reasons
                       else f"benign context {benign_verdict.status}"))
        return (f"{len(result.present_required)}/{len(result.recipe.required)} "
                f"required fragments present (watch).")

    def _state_expiry(self, asm) -> dict:
        counts = {ACTIVE: 0, DECAYED: 0, REVOKED: 0}
        for li in asm.instances:
            counts[li.state] = counts.get(li.state, 0) + 1
        return {
            "timescale_unit": self.timescale.unit,
            "decay_half_life": self.timescale.decay_half_life,
            "decay_floor": self.timescale.decay_floor,
            "instance_states": counts,
            "closed": asm.closed,
        }

    def _unavailable_finding(self, tenant_id, al, exc: LimitExceeded, pos) -> Finding:
        body = {"tenant_id": tenant_id, "assembly_key": al.assembly_key,
                "signal": signals.UNAVAILABLE, "scope": exc.scope}
        return Finding(
            finding_id=digest(body, domain="CTD-FINDING"),
            signal=signals.UNAVAILABLE, tenant_id=tenant_id,
            assembly_key=al.assembly_key, key_spec=al.key_spec,
            ontology_id=self.ontology.ontology_id,
            ontology_version=self.ontology.version, recipe_id="", recipe_version="",
            severity="HIGH", completion_score=0.0, present_fragments=[],
            missing_fragments=[], ordering_status={},
            entity_link_evidence={"key_spec": al.key_spec, "link_dims": al.link_dims},
            benign_context_evidence={}, completion={},
            escalation_reason=f"bounded-state exhaustion ({exc.scope}): {exc.detail}",
            recommended_consequence="HOLD_FOR_REVIEW",
            explanation=(f"Analyzer could not faithfully evaluate this assembly: "
                         f"{exc}. Emitting UNAVAILABLE (fail-loud), not a clean result."),
            related_correlations=[], related_event_ids=[],
            first_seen_position=None, last_updated_position=pos,
            state_expiry={},
        )

    # -- reporting ---------------------------------------------------------
    def standing_findings(self, tenant_id: str, assembly_key: str) -> list[Finding]:
        """Level-triggered current findings for one assembly (regardless of rise)."""
        asm = self.ledger.get(tenant_id, assembly_key)
        if asm is None:
            return []
        now = float(asm.last_t if asm.last_t is not None else asm.last_position)
        active = asm.active(now, self.timescale)
        contexts = self._benign.get((tenant_id, assembly_key), [])
        out = []

        class _AL:  # minimal shim carrying the assembly's key metadata
            key_spec = asm.key_spec
            assembly_key = asm.assembly_key
            confidence = "EXACT"
            link_dims = asm.link_dims
        for recipe in self.ontology.recipes:
            result = match(recipe, active)
            if result.signal == signals.NONE:
                continue
            bv = benign_mod.evaluate(recipe, contexts, asm.link_dims, now,
                                     self.active_policy_version)
            sig = result.signal
            if sig == signals.ESCALATE and bv.status == benign_mod.NEUTRALIZED:
                sig = signals.OBSERVE
            out.append(self._build_finding(tenant_id, _AL, asm, recipe, result, bv,
                                           sig, asm.last_position))
        return out


# ---------------------------------------------------------------------------
# Backward-compatibility facade (migration from the correlation-only prototype)
# ---------------------------------------------------------------------------
class CompositeThreatMonitor(SequenceRiskAnalyzer):
    """Deprecated alias for the original prototype's entry point.

    Preserves the ``observe()`` call and the single-correlation grouping the first
    version used (``BY_CORRELATION``), so existing illustrations keep working. New
    code should use :class:`SequenceRiskAnalyzer` with an explicit key spec set.
    See MIGRATION_NOTES in the spec.
    """

    def __init__(self, ontology, *, window_actions=None, observe_at=0.5,
                 escalate_at=1.0, **kwargs):
        from .linkage import BY_CORRELATION
        # Map the legacy short-window knob onto the transient-decay half-life so
        # the *documented* behavior (persistent capability is retained) holds.
        ts = TimescalePolicy(
            unit="steps",
            decay_half_life=float(window_actions) if window_actions else 50.0,
        )
        super().__init__(ontology, specs=(BY_CORRELATION,), timescale=ts, **kwargs)
