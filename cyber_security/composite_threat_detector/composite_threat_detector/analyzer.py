"""SequenceRiskAnalyzer — orchestration and finding assembly.

Pipeline per event (all deterministic, stdlib only):

    link (entity-linkage) -> governance -> ledger (multi-timescale state)
      -> match (constraints) -> ordering/clock status -> purpose (trusted evidence)
      -> recipe-version binding (dual eval) -> completion -> finding

The analyzer emits only advisory signals: ``OBSERVE`` / ``ESCALATE`` /
``UNAVAILABLE`` (never ALLOW/DENY/AUTHORIZE/BLOCK/EXECUTE). An authoritative
policy converts an ``ESCALATE`` into a binding consequence (``policy.py``); the
analyzer never does. In this phase all evaluated workflows default to **shadow
mode** — findings are advisory and no action is blocked or executed differently.

Every ingestion updates an integrity :class:`RunReport` (§11) and appends to an
append-only audit log (raw evidence + lifecycle + governance events, §5) so no
silent fallback can produce a clean-looking result.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from . import benign as benign_mod
from . import completion as completion_mod
from . import narrative, ordering, purpose as purpose_mod, signals
from .audit import AuditLog
from .canonical import digest
from .governance import ResourceGovernor, severity_rank
from .ledger import (
    ACTIVE, DECAYED, REVOKED, Assembly, CapabilityLedger, LimitExceeded,
    StateLimits, TimescalePolicy,
)
from .linkage import BY_ACTOR, BY_CASE, AssemblyKeySpec, link_event
from .matcher import match
from .model import ExtractContext, Ontology
from .providers import ProviderRegistry
from .purpose import AssemblyScope
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
    purpose: dict
    recipe_version_binding: dict
    lifecycle: str
    completion: dict
    escalation_reason: str
    recommended_consequence: str
    explanation: str
    related_correlations: list[str]
    related_event_ids: list[str]
    first_seen_position: int | None
    last_updated_position: int
    state_expiry: dict
    raw_evidence_digest: str
    shadow_mode: bool

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RunReport:
    """Anti-confounder integrity counters (§11)."""

    analyzer_enabled: bool = True
    shadow_mode: bool = True
    ontology_id: str = ""
    ontology_version: str = ""
    recipe_versions: list[str] = field(default_factory=list)
    key_specs: list[str] = field(default_factory=list)
    timescale_unit: str = ""
    providers: list[dict] = field(default_factory=list)
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
    order_ambiguous: int = 0
    order_conflicting: int = 0
    purpose_verified: int = 0
    purpose_unverified: int = 0
    recipe_version_divergences: int = 0
    governance_rejections: int = 0
    audit_records: int = 0
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
        providers: ProviderRegistry | None = None,
        shadow_mode: bool = True,
    ) -> None:
        if not specs:
            raise ValueError("at least one AssemblyKeySpec is required")
        self.ontology = ontology
        self.specs = specs
        self.timescale = timescale or TimescalePolicy()
        self.limits = limits or StateLimits()
        self.active_policy_version = active_policy_version
        self.providers = providers
        self.shadow_mode = shadow_mode
        self.ledger = CapabilityLedger(self.timescale, self.limits)
        self.audit = AuditLog()
        self.governor = ResourceGovernor(limits=self.limits)
        self._claims: dict[tuple[str, str], list] = {}
        self._order_signals: dict[tuple[str, str], dict] = {}
        self._last_signal: dict[tuple[str, str, str], str] = {}
        self._recipe_history: dict[str, dict[str, object]] = {}
        self._register_recipes(ontology)
        self._ingest_counter = 0
        self.report = RunReport(
            shadow_mode=shadow_mode,
            ontology_id=ontology.ontology_id, ontology_version=ontology.version,
            recipe_versions=sorted({r.ref for r in ontology.recipes}),
            key_specs=[s.ref for s in specs], timescale_unit=self.timescale.unit,
            providers=providers.describe() if providers else [],
        )

    def _register_recipes(self, ontology: Ontology) -> None:
        for r in ontology.recipes:
            self._recipe_history.setdefault(r.recipe_id, {})[r.version] = r

    def load_ontology(self, ontology: Ontology) -> None:
        """Swap the recipe library, preserving accumulated ledger + audit state.

        Historical reconstruction uses the recipe version bound when an assembly
        opened; new actions are also evaluated against the current version, and
        divergent outcomes are recorded (§8). Earlier findings are never rewritten.
        """
        self.ontology = ontology
        self._register_recipes(ontology)
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
        osig = ordering.extract_order_signals(event, self._ingest_counter)
        claims = benign_mod.extract_benign_context(event, at_epoch_of=parse_epoch)
        revokes = tuple(event.get("revokes", ()) or ())

        findings: list[Finding] = []
        any_linked = False

        # governance: candidate-linkage fan-out (§7)
        candidate = [al for al in link.links
                     if al.confidence != "AMBIGUOUS" and al.assembly_key]
        gd = self.governor.check_candidate_linkages(len(candidate))
        if not gd.admit:
            self.report.governance_rejections += 1
            self.audit.append("OVERLOAD", tenant_id=link.tenant_id,
                              event_id=diag["event_id"], detail={"reason": gd.reason})
            self.report.unavailable_events += 1
            diag["unavailable"] = True
            findings.append(self._governance_unavailable(link.tenant_id, cid, gd, pos))
            return IngestResult(findings, diag)

        for al in candidate:
            actor = entities.get("actor", "")
            ad = self.governor.check_actor(link.tenant_id, actor, al.assembly_key)
            if not ad.admit:
                self.report.governance_rejections += 1
                self.report.unavailable_events += 1
                diag["unavailable"] = True
                self.audit.append("OVERLOAD", tenant_id=link.tenant_id,
                                  assembly_key=al.assembly_key,
                                  event_id=diag["event_id"], detail={"reason": ad.reason})
                findings.append(self._governance_unavailable(link.tenant_id, cid, ad, pos))
                continue

            ctx = ExtractContext(
                tenant_id=link.tenant_id, correlation_id=cid,
                sequence_id=str(event.get("sequence_id", "")),
                event_id=str(event.get("event_id", "")),
                idempotency_key=str(event.get("idempotency_key", "")),
                position=pos, at_epoch=epoch, entities=entities)
            instances = self.ontology.extract(event, ctx)
            if not instances and (event.get("capability")
                                  or (event.get("tool", {}) or {}).get("capability")):
                self.report.unmapped_capabilities += 1
                diag["unmapped_capability"] = True

            key = (link.tenant_id, al.assembly_key)
            if claims:
                store = self._claims.setdefault(key, [])
                if len(store) < self.limits.max_benign_records_per_assembly:
                    store.extend(claims)
            # record ordering signals per contributing event, for later status calc
            if instances:
                self._order_signals.setdefault(key, {})[ctx.event_id] = osig

            try:
                add = self.ledger.add(
                    link.tenant_id, al.assembly_key, al.key_spec, al.link_dims,
                    instances, now, event_id=ctx.event_id,
                    idempotency_key=ctx.idempotency_key, correlation_id=cid,
                    revokes=revokes)
            except LimitExceeded as exc:
                self.report.unavailable_events += 1
                diag["unavailable"] = True
                self.audit.append("EVICTION", tenant_id=link.tenant_id,
                                  assembly_key=al.assembly_key,
                                  event_id=diag["event_id"],
                                  detail={"limit": exc.scope, "detail": exc.detail})
                findings.append(self._unavailable_finding(link.tenant_id, al, exc, pos))
                continue

            # raw evidence: append-only, survives active-risk decay (§5)
            rec = self.audit.append(
                "RAW_EVIDENCE", tenant_id=link.tenant_id, assembly_key=al.assembly_key,
                event_id=ctx.event_id,
                detail={"operation": str(event.get("operation", event.get("item", ""))),
                        "fragments": [i.fragment_id for i in instances],
                        "order_signals": osig.to_dict(), "position": pos})
            self.report.audit_records = len(self.audit)

            any_linked = True
            asm = self.ledger.get(link.tenant_id, al.assembly_key)
            if asm is not None:
                asm.actors.update(a for a in [actor] if a)
                asm.ingest_count += 1
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

            findings.extend(self._evaluate(link.tenant_id, al, now, pos,
                                           raw_digest=rec.record_digest))

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
                self.audit.append("LIFECYCLE", tenant_id=link.tenant_id,
                                  assembly_key=al.assembly_key,
                                  detail={"transition": "CLOSED"})
            else:
                # administrative reset: immutable audit event; history preserved.
                self.audit.append("ASSEMBLY_RESET", tenant_id=link.tenant_id,
                                  assembly_key=al.assembly_key,
                                  detail={"note": "active risk state cleared; "
                                                  "raw evidence + provenance retained"})
                self.ledger.reset(link.tenant_id, al.assembly_key)
                self._claims.pop((link.tenant_id, al.assembly_key), None)
                self._order_signals.pop((link.tenant_id, al.assembly_key), None)
                for k in list(self._last_signal):
                    if k[0] == link.tenant_id and k[1] == al.assembly_key:
                        del self._last_signal[k]
        self.report.audit_records = len(self.audit)
        return IngestResult([], diag)

    # -- evaluation --------------------------------------------------------
    def _evaluate(self, tenant_id, al, now, pos, *, raw_digest="") -> list[Finding]:
        asm = self.ledger.get(tenant_id, al.assembly_key)
        if asm is None:
            return []
        active = asm.active(now, self.timescale)
        risen: list[Finding] = []
        for recipe in self.ontology.recipes:
            finding, final_signal = self._evaluate_recipe(
                tenant_id, al, asm, recipe, active, now, pos, raw_digest)
            if finding is None:
                continue
            skey = (tenant_id, al.assembly_key, recipe.recipe_id)
            prev = self._last_signal.get(skey, signals.NONE)
            self._last_signal[skey] = final_signal
            if signals.rank(final_signal) <= signals.rank(prev):
                continue  # edge-triggered
            self.audit.append("FINDING", tenant_id=tenant_id,
                              assembly_key=al.assembly_key,
                              detail={"finding_id": finding.finding_id,
                                      "recipe": recipe.ref, "signal": final_signal})
            risen.append(finding)
        self.report.audit_records = len(self.audit)
        return risen

    def _evaluate_recipe(self, tenant_id, al, asm, recipe, active, now, pos, raw_digest):
        """Evaluate one recipe; return (Finding|None, final_signal)."""
        result = match(recipe, active)
        if result.signal == signals.NONE:
            return None, signals.NONE

        # bind recipe version at first sight; dual-evaluate on divergence (§8)
        bound_version = asm.bound_recipe_versions.setdefault(
            recipe.recipe_id, recipe.version)
        version_binding = {"bound_version": bound_version,
                           "current_version": recipe.version, "divergent": False}
        if bound_version != recipe.version:
            bound_recipe = self._recipe_history.get(recipe.recipe_id, {}).get(bound_version)
            if bound_recipe is not None:
                bound_result = match(bound_recipe, active)
                version_binding["bound_outcome"] = bound_result.signal
                version_binding["current_outcome"] = result.signal
                if bound_result.signal != result.signal:
                    version_binding["divergent"] = True
                    self.report.recipe_version_divergences += 1

        # ordering / clock status
        contributing_ids = [li.inst.event_id for li in result.contributing.values()]
        sig_store = self._order_signals.get((tenant_id, al.assembly_key), {})
        osigs = [sig_store[e] for e in contributing_ids if e in sig_store]
        clock_status = ordering.assembly_status(osigs)
        if clock_status == ordering.AMBIGUOUS_ORDER:
            self.report.order_ambiguous += 1
        elif clock_status == ordering.CONFLICTING_ORDER:
            self.report.order_conflicting += 1

        final_signal = result.signal
        order_block = ""
        if recipe.ordering and not ordering.satisfies_strict_ordering(
                clock_status, recipe.permit_ambiguous_ordering):
            if final_signal == signals.ESCALATE:
                final_signal = signals.OBSERVE
            order_block = (f"strict-ordering recipe under {clock_status}; "
                           f"escalation withheld (permit_ambiguous_ordering="
                           f"{recipe.permit_ambiguous_ordering})")

        # purpose: only trusted, verified, scope-matched authorization neutralizes
        scope = self._assembly_scope(asm, active)
        claims = self._claims.get((tenant_id, al.assembly_key), [])
        assessment = purpose_mod.assess(
            claims, scope, self.providers, now, self.active_policy_version, recipe)
        if claims:
            if assessment.purpose_consistency_status == purpose_mod.VERIFIED_CONSISTENT:
                self.report.purpose_verified += 1
            else:
                self.report.purpose_unverified += 1
        if final_signal == signals.ESCALATE and assessment.neutralizes:
            final_signal = signals.OBSERVE

        asm.max_severity_rank = max(asm.max_severity_rank, severity_rank(recipe.severity))
        finding = self._build_finding(
            tenant_id, al, asm, recipe, result, assessment, final_signal, pos,
            clock_status, order_block, version_binding, raw_digest)
        return finding, final_signal

    def _assembly_scope(self, asm, active) -> AssemblyScope:
        actors, ops, dests, tools = set(), set(), set(), set()
        env = ""
        for li in active:
            e = li.inst.entities
            if li.inst.actor:
                actors.add(li.inst.actor)
            if li.inst.operation:
                ops.add(li.inst.operation)
            if e.get("destination"):
                dests.add(e["destination"])
            if e.get("tool"):
                tools.add(e["tool"])
            env = env or e.get("environment", "")
        return AssemblyScope(
            tenant=asm.tenant_id, actors=tuple(sorted(actors)),
            workflow=asm.link_dims.get("workflow", ""),
            target_family=asm.link_dims.get("target_family", ""),
            operations=tuple(sorted(ops)), destinations=tuple(sorted(dests)),
            environment=env, tools=tuple(sorted(tools)))

    def _build_finding(self, tenant_id, al, asm, recipe, result, assessment,
                       signal, pos, clock_status, order_block, version_binding,
                       raw_digest) -> Finding:
        present = narrative.present_fragments(self.ontology, result)
        comp = completion_mod.analyze(result)
        related_events = sorted({s["event_id"] for s in present if s["event_id"]})
        blocking = list(result.blocking_reasons)
        if order_block:
            blocking.append(order_block)
        ordering_status = {
            "structural_ordering_ok": result.constraints["ordering_ok"],
            "clock_status": clock_status,
            "strict_ordering_satisfiable": ordering.satisfies_strict_ordering(
                clock_status, recipe.permit_ambiguous_ordering),
            "constraints": result.constraints, "blocking_reasons": blocking,
            "impossible": result.impossible, "impossible_reason": result.impossible_reason,
        }
        link_evidence = {"key_spec": al.key_spec, "confidence": al.confidence,
                         "link_dims": al.link_dims}
        benign_status = ("NEUTRALIZED" if assessment.neutralizes
                         else ("AMBIGUOUS" if assessment.declared_purpose
                               else "THREAT_DOMINATES"))
        benign_evidence = {"status": benign_status,
                           "purpose_consistency_status": assessment.purpose_consistency_status,
                           "evidence": assessment.purpose_evidence,
                           "explanation": assessment.explanation}
        lifecycle = self._lifecycle_of(asm)
        state_expiry = self._state_expiry(asm)
        escalation_reason = self._reason(result, benign_status, signal, blocking)

        body = {
            "tenant_id": tenant_id, "assembly_key": al.assembly_key,
            "key_spec": al.key_spec, "ontology": self.ontology.ontology_id,
            "ontology_version": self.ontology.version, "recipe": recipe.ref,
            "signal": signal, "present_required": result.present_required,
            "present_optional": result.present_optional, "missing": result.missing_required,
            "benign_status": benign_status, "clock_status": clock_status,
            "purpose_status": assessment.purpose_consistency_status,
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
            purpose=assessment.to_dict(), recipe_version_binding=version_binding,
            lifecycle=lifecycle, completion=asdict(comp),
            escalation_reason=escalation_reason,
            recommended_consequence=recipe.recommended_consequence,
            explanation=narrative.explanation(result, benign_status),
            related_correlations=sorted(asm.related_correlations),
            related_event_ids=related_events,
            first_seen_position=asm.first_position, last_updated_position=pos,
            state_expiry=state_expiry, raw_evidence_digest=raw_digest,
            shadow_mode=self.shadow_mode,
        )

    def _reason(self, result, benign_status, signal, blocking) -> str:
        if signal == signals.ESCALATE:
            return (f"All {len(result.recipe.required)} required fragments present, "
                    f"structural + ordering constraints satisfied; purpose "
                    f"{benign_status}.")
        if signal == signals.OBSERVE and not result.missing_required:
            return ("Recipe fragment-complete but escalation withheld: "
                    + ("; ".join(blocking) if blocking
                       else f"purpose {benign_status}"))
        return (f"{len(result.present_required)}/{len(result.recipe.required)} "
                f"required fragments present (watch).")

    def _lifecycle_of(self, asm: Assembly) -> str:
        if asm.closed:
            return "CLOSED"
        active = decayed = 0
        for li in asm.instances:
            if li.state == ACTIVE:
                active += 1
            elif li.state == DECAYED:
                decayed += 1
        if active == 0 and (decayed or asm.instances):
            return "EXPIRED"
        if decayed:
            return "DECAYING"
        return "OPEN"

    def _state_expiry(self, asm) -> dict:
        counts = {ACTIVE: 0, DECAYED: 0, REVOKED: 0}
        for li in asm.instances:
            counts[li.state] = counts.get(li.state, 0) + 1
        return {"timescale_unit": self.timescale.unit,
                "decay_half_life": self.timescale.decay_half_life,
                "decay_floor": self.timescale.decay_floor,
                "instance_states": counts, "closed": asm.closed}

    def _unavailable_finding(self, tenant_id, al, exc: LimitExceeded, pos) -> Finding:
        return self._make_unavailable(
            tenant_id, al.assembly_key, al.key_spec, al.link_dims,
            f"bounded-state exhaustion ({exc.scope}): {exc.detail}", exc.scope, pos)

    def _governance_unavailable(self, tenant_id, cid, gd, pos) -> Finding:
        return self._make_unavailable(
            tenant_id, "", "governance", {}, gd.reason, gd.limit, pos)

    def _make_unavailable(self, tenant_id, assembly_key, key_spec, link_dims,
                          reason, limit, pos) -> Finding:
        body = {"tenant_id": tenant_id, "assembly_key": assembly_key,
                "signal": signals.UNAVAILABLE, "limit": limit}
        return Finding(
            finding_id=digest(body, domain="CTD-FINDING"),
            signal=signals.UNAVAILABLE, tenant_id=tenant_id, assembly_key=assembly_key,
            key_spec=key_spec, ontology_id=self.ontology.ontology_id,
            ontology_version=self.ontology.version, recipe_id="", recipe_version="",
            severity="HIGH", completion_score=0.0, present_fragments=[],
            missing_fragments=[], ordering_status={},
            entity_link_evidence={"key_spec": key_spec, "link_dims": link_dims},
            benign_context_evidence={}, purpose={}, recipe_version_binding={},
            lifecycle="OPEN", completion={},
            escalation_reason=reason, recommended_consequence="HOLD_FOR_REVIEW",
            explanation=(f"Analyzer could not faithfully evaluate: {reason}. "
                         f"Emitting UNAVAILABLE (fail-visible), not a clean result."),
            related_correlations=[], related_event_ids=[], first_seen_position=None,
            last_updated_position=pos, state_expiry={}, raw_evidence_digest="",
            shadow_mode=self.shadow_mode)

    # -- reporting ---------------------------------------------------------
    def standing_findings(self, tenant_id: str, assembly_key: str) -> list[Finding]:
        """Level-triggered current findings for one assembly (regardless of rise)."""
        asm = self.ledger.get(tenant_id, assembly_key)
        if asm is None:
            return []
        now = float(asm.last_t if asm.last_t is not None else asm.last_position)
        active = asm.active(now, self.timescale)

        class _AL:
            key_spec = asm.key_spec
            assembly_key = asm.assembly_key
            confidence = "EXACT"
            link_dims = asm.link_dims
        out = []
        for recipe in self.ontology.recipes:
            finding, _ = self._evaluate_recipe(
                tenant_id, _AL, asm, recipe, active, now, asm.last_position, "")
            if finding is not None:
                out.append(finding)
        return out

    def reconstruct(self, tenant_id: str, assembly_key: str) -> dict:
        """Reconstruct an assembly's history from the append-only audit log (§5).

        Works even after active risk weight has fully decayed, because raw
        evidence and finding provenance are retained in the audit log.
        """
        events = [e.to_dict() for e in self.audit.for_assembly(tenant_id, assembly_key)]
        return {"tenant_id": tenant_id, "assembly_key": assembly_key,
                "audit_events": events, "chain_valid": self.audit.verify_chain()}


# ---------------------------------------------------------------------------
# Backward-compatibility facade (migration from the correlation-only prototype)
# ---------------------------------------------------------------------------
class CompositeThreatMonitor(SequenceRiskAnalyzer):
    """Deprecated alias for the original prototype's entry point.

    Preserves ``observe()`` and single-correlation grouping (``BY_CORRELATION``).
    New code should use :class:`SequenceRiskAnalyzer` with explicit key specs.
    """

    def __init__(self, ontology, *, window_actions=None, observe_at=0.5,
                 escalate_at=1.0, **kwargs):
        from .linkage import BY_CORRELATION
        ts = TimescalePolicy(
            unit="steps",
            decay_half_life=float(window_actions) if window_actions else 50.0)
        super().__init__(ontology, specs=(BY_CORRELATION,), timescale=ts, **kwargs)
