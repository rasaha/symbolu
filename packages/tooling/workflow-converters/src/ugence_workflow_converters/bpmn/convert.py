"""BPMN 2.0 export → DRAFT policy pack + mapping table (CV-2, CV-3, CV-4).

A BPMN 2.0 export is XML in the OMG namespace: ``definitions`` holding one or more
``process`` elements (and optionally a ``collaboration`` of ``participant`` pools),
each process holding flow nodes (tasks, gateways, events, sub-processes), the
``sequenceFlow`` elements between them, and ``laneSet`` / ``lane`` partitions that
name a performer. This converter reads exactly that, by element name, through the
table below, and writes each construct into the compiler's own objects where one
honestly fits:

  exclusive / inclusive gateway   → one DecisionRule per conditioned outgoing flow,
                                    with the predicate when it translates
  businessRuleTask                → DecisionRule with no predicate (the rule lives
                                    in DMN, which is not carried) and a loss warning
  receiveTask                     → ConnectorMapping + RequiredEvidence (a read)
  sendTask, message throw         → ConnectorMapping, and a governance gap: the
                                    action has no authority, so no ActionConstraint
                                    is fabricated
  serviceTask                     → ConnectorMapping, and a gap: BPMN does not say
                                    whether the service reads or writes
  userTask, manualTask            → nothing in the pack; a gap: a lane names a
                                    performer, not an authority, and none is invented
  startEvent                      → nothing; a gap: entry is unadmitted
  endEvent, catch events, waits   → nothing; the compiler synthesizes its own
                                    terminal outcomes and carries no waits
  parallel / event-based gateway  → nothing; control flow is not carried
  boundary event                  → nothing; the exception path is not carried
  scriptTask                      → UNSUPPORTED, never inspected beyond its type
  callActivity, sub-processes     → UNSUPPORTED / container; children are read
  lane, participant               → UNMAPPED, recorded as performer context
  any other element of the BPMN   → UNSUPPORTED, and the conversion is PARTIAL
  namespace under a process

Every emitted object cites the export itself, registered as the pack's
``SourceDocument`` with the input digest, as its provenance. Nothing else is
invented, and the pack stays DRAFT.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Tuple

from ugence_policy_workflow_compiler.api import PolicyPack, validate_policy_pack
from ugence_policy_workflow_compiler.models.common import PolicyPackStatus
from ugence_policy_workflow_compiler.models.connectors import ConnectorMapping
from ugence_policy_workflow_compiler.models.evidence import RequiredEvidence
from ugence_policy_workflow_compiler.models.provenance import ProvenanceSourceType, SourceDocument
from ugence_policy_workflow_compiler.models.rules import Comparator, DecisionRule, Predicate
from ugence_policy_workflow_compiler.serialization import hashing

from ..intake import MAX_CONSTRUCTS, local_name, namespace_of, parse_xml_export, slug
from ..report import (
    ConversionRefused,
    ConversionReport,
    ConversionState,
    CredentialRequirement,
    GovernanceGap,
    MappingRow,
    PackSummary,
    RefusalCode,
    RowOutcome,
    SemanticLossWarning,
    SourceSummary,
    ToolRequirement,
    ValidationSummary,
    converter_identity,
)

FORMAT = "bpmn-2.0"
BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"

# -- the mapping table, by BPMN element ---------------------------------------- #

DECISION_GATEWAYS = ("exclusiveGateway", "inclusiveGateway")
FLOW_GATEWAYS = ("parallelGateway", "eventBasedGateway")
UNSUPPORTED_GATEWAYS = ("complexGateway",)
HUMAN_TASKS = ("userTask", "manualTask")
READ_TASKS = ("receiveTask",)
WRITE_TASKS = ("sendTask",)
SERVICE_TASKS = ("serviceTask",)
RULE_TASKS = ("businessRuleTask",)
EXECUTABLE_TASKS = ("scriptTask",)
ABSTRACT_TASKS = ("task",)
CALLED = ("callActivity",)
CONTAINERS = ("subProcess", "adHocSubProcess", "transaction")
START_EVENTS = ("startEvent",)
END_EVENTS = ("endEvent",)
CATCH_EVENTS = ("intermediateCatchEvent",)
THROW_EVENTS = ("intermediateThrowEvent",)
BOUNDARY_EVENTS = ("boundaryEvent",)
FLOW_NODES = (DECISION_GATEWAYS + FLOW_GATEWAYS + UNSUPPORTED_GATEWAYS + HUMAN_TASKS + READ_TASKS + WRITE_TASKS
              + SERVICE_TASKS + RULE_TASKS + EXECUTABLE_TASKS + ABSTRACT_TASKS + CALLED + CONTAINERS
              + START_EVENTS + END_EVENTS + CATCH_EVENTS + THROW_EVENTS + BOUNDARY_EVENTS)
#: BPMN elements that are structure, not constructs: read where relevant, never rows.
STRUCTURAL = ("sequenceFlow", "laneSet", "lane", "flowNodeRef", "childLaneSet", "extensionElements", "documentation",
              "incoming", "outgoing", "ioSpecification", "dataInput", "dataOutput", "inputSet", "outputSet",
              "dataInputAssociation", "dataOutputAssociation", "sourceRef", "targetRef", "property", "conditionExpression",
              "multiInstanceLoopCharacteristics", "standardLoopCharacteristics", "loopCardinality", "completionCondition",
              "dataObject", "dataObjectReference", "dataStoreReference", "dataState", "textAnnotation", "text", "association",
              "group", "category", "categoryValue", "messageFlow", "participant", "collaboration", "process", "definitions",
              "message", "signal", "error", "escalation", "itemDefinition", "interface", "operation", "inMessageRef", "outMessageRef",
              "errorRef", "resource", "potentialOwner", "performer", "humanPerformer", "resourceRef", "resourceAssignmentExpression",
              "formalExpression", "script", "rendering", "timeDate", "timeDuration", "timeCycle", "activationCondition",
              "dataOutputRefs", "dataInputRefs", "assignment", "from", "to", "transformation", "BPMNDiagram", "BPMNPlane",
              "BPMNShape", "BPMNEdge", "BPMNLabel", "Bounds", "waypoint", "relationship", "extension", "import", "auditing",
              "monitoring", "categoryValueRef", "supports", "eventDefinitionRef")
EVENT_DEFINITIONS = ("timerEventDefinition", "messageEventDefinition", "signalEventDefinition", "errorEventDefinition",
                     "escalationEventDefinition", "terminateEventDefinition", "conditionalEventDefinition", "linkEventDefinition",
                     "compensateEventDefinition", "cancelEventDefinition")

EXPRESSION_MARK = re.compile(r"\$\{|#\{|^\s*=")
_COMPARATORS = {"==": Comparator.EQ, "=": Comparator.EQ, "!=": Comparator.NE, "<>": Comparator.NE,
                ">=": Comparator.GTE, "<=": Comparator.LTE, ">": Comparator.GT, "<": Comparator.LT}
_CLAUSE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_.]*)\s*(==|!=|<>|>=|<=|=|>|<)\s*(.+?)\s*$")
_NOT = re.compile(r"^\s*(?:!|not\s+)\s*([A-Za-z_][A-Za-z0-9_.]*)\s*$")
_IDENT = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_.]*)\s*$")


class _Ctx:
    def __init__(self, source_id: str) -> None:
        self.source_id = source_id
        self.rows: List[MappingRow] = []
        self.losses: List[SemanticLossWarning] = []
        self.gaps: List[GovernanceGap] = []
        self.tools: List[ToolRequirement] = []
        self.credentials: List[CredentialRequirement] = []
        self.decision_rules: List[DecisionRule] = []
        self.connectors: List[ConnectorMapping] = []
        self.evidence: List[RequiredEvidence] = []
        self.connections: List[Tuple[str, str]] = []
        self.lane_of: Dict[str, str] = {}
        self.flows_out: Dict[str, List[Tuple[str, str, str, bool]]] = {}  # source -> [(flow_id, target, condition, is_default)]
        self.seen: set = set()

    def loss(self, cid: str, code: str, detail: str) -> str:
        self.losses.append(SemanticLossWarning(source_construct_id=cid, code=code, detail=detail))
        return code

    def gap(self, cid: str, code: str, detail: str) -> None:
        self.gaps.append(GovernanceGap(source_construct_id=cid, gap_code=code, detail=detail))


# -- expressions ---------------------------------------------------------------- #


def _strip_expression(text: str) -> str:
    t = text.strip()
    for opener in ("${", "#{"):
        if t.startswith(opener) and t.endswith("}"):
            return t[2:-1].strip()
    if t.startswith("="):
        return t[1:].strip()
    return t


def _literal(raw: str) -> Tuple[bool, Any, str]:
    r = raw.strip()
    if re.fullmatch(r"-?\d+", r):
        return True, int(r), ""
    if re.fullmatch(r"-?\d+\.\d+", r):
        value = float(r)
        return (True, int(value), "") if value.is_integer() else (False, None, "NON_INTEGER_LITERAL")
    if r.lower() in ("true", "false"):
        return True, r.lower() == "true", ""
    if len(r) >= 2 and r[0] == r[-1] and r[0] in "\"'":
        return True, r[1:-1], ""
    if r.lower() == "null":
        return True, None, ""
    return False, None, "EXPRESSION_NOT_TRANSLATED"


def _fact(name: str) -> str:
    return name.split(".")[-1] if "." in name else name


def translate_condition(text: str, cid: str, ctx: _Ctx) -> Tuple[List[Predicate], List[str]]:
    """A gateway flow's condition into compiler predicates: conjunctions of
    ``variable <op> literal``, ``variable`` and ``!variable`` translate; anything
    else is a named loss and is not carried."""
    body = _strip_expression(text)
    predicates: List[Predicate] = []
    losses: List[str] = []
    if not body:
        losses.append(ctx.loss(cid, "BRANCH_PREDICATE_NOT_TRANSLATED", "the flow declares an empty condition"))
        return predicates, losses
    if "||" in body or re.search(r"\bor\b", body):
        losses.append(ctx.loss(cid, "OR_COMBINATOR_NOT_TRANSLATED", "compiler predicates conjoin; a disjunction is not carried"))
        return predicates, losses
    for clause in re.split(r"&&|\band\b", body):
        m = _CLAUSE.match(clause)
        if m:
            fact, op, rhs = m.group(1), m.group(2), m.group(3)
            usable, literal, loss = _literal(rhs)
            if not usable:
                losses.append(ctx.loss(cid, loss, f"right-hand side {rhs!r} is not a deterministic literal"))
                continue
            if isinstance(literal, bool) and op in ("==", "="):
                predicates.append(Predicate(fact_key=_fact(fact), comparator=Comparator.IS_TRUE if literal else Comparator.IS_FALSE))
            else:
                predicates.append(Predicate(fact_key=_fact(fact), comparator=_COMPARATORS[op], value=literal))
            continue
        m = _NOT.match(clause)
        if m:
            predicates.append(Predicate(fact_key=_fact(m.group(1)), comparator=Comparator.IS_FALSE))
            continue
        m = _IDENT.match(clause)
        if m:
            predicates.append(Predicate(fact_key=_fact(m.group(1)), comparator=Comparator.IS_TRUE))
            continue
        losses.append(ctx.loss(cid, "EXPRESSION_NOT_TRANSLATED", f"clause {clause.strip()!r} has no compiler shape"))
    return predicates, sorted(set(losses))


# -- reading the tree ------------------------------------------------------------ #


def _attr(element: ET.Element, name: str) -> str:
    for key, value in element.attrib.items():
        if local_name(key) == name:
            return value
    return ""


def _extension_detail(element: ET.Element) -> Tuple[str, bool, bool]:
    """(target text from extension attributes, has_script, has_expression)."""
    parts: List[str] = []
    has_script = False
    has_expression = False
    for key, value in element.attrib.items():
        if namespace_of(key) and namespace_of(key) != BPMN_NS:
            parts.append(f"{local_name(key)}={value}")
            if EXPRESSION_MARK.search(value):
                has_expression = True
    for child in element.iter():
        if child is element:
            continue
        name = local_name(child.tag)
        if name in ("script", "taskDefinition", "connector", "connectorId", "class", "topic", "type"):
            if name == "script":
                has_script = True
            for key, value in child.attrib.items():
                parts.append(f"{name}.{local_name(key)}={value}")
        if child.text and EXPRESSION_MARK.search(child.text):
            has_expression = True
    return " ".join(parts), has_script, has_expression


def _event_definitions(element: ET.Element) -> List[str]:
    return [local_name(c.tag).replace("EventDefinition", "") for c in element if local_name(c.tag) in EVENT_DEFINITIONS]


def _index_flows(process: ET.Element, ctx: _Ctx) -> None:
    for element in process.iter():
        if local_name(element.tag) != "sequenceFlow" or namespace_of(element.tag) != BPMN_NS:
            continue
        source, target = _attr(element, "sourceRef"), _attr(element, "targetRef")
        condition = ""
        for child in element:
            if local_name(child.tag) == "conditionExpression":
                condition = (child.text or "").strip()
        if source and target:
            ctx.connections.append((source, target))
            ctx.flows_out.setdefault(source, []).append((_attr(element, "id") or f"{source}->{target}", target, condition, False))
    # default flows are named on the gateway
    for element in process.iter():
        default = _attr(element, "default")
        if default:
            src = _attr(element, "id")
            ctx.flows_out[src] = [(fid, tgt, cond, fid == default) for fid, tgt, cond, _ in ctx.flows_out.get(src, [])]


def _index_lanes(process: ET.Element, ctx: _Ctx) -> List[Tuple[str, str]]:
    lanes: List[Tuple[str, str]] = []
    for lane in process.iter():
        if local_name(lane.tag) != "lane" or namespace_of(lane.tag) != BPMN_NS:
            continue
        lane_id, lane_name = _attr(lane, "id"), _attr(lane, "name") or _attr(lane, "id")
        lanes.append((lane_id, lane_name))
        for ref in lane:
            if local_name(ref.tag) == "flowNodeRef" and ref.text:
                ctx.lane_of[ref.text.strip()] = lane_name
    return lanes


def _flow_nodes(container: ET.Element) -> List[ET.Element]:
    out: List[ET.Element] = []
    for child in container:
        name = local_name(child.tag)
        if namespace_of(child.tag) != BPMN_NS:
            continue
        if name in FLOW_NODES or (name not in STRUCTURAL and name not in EVENT_DEFINITIONS):
            out.append(child)
            if name in CONTAINERS:
                out.extend(_flow_nodes(child))
    return out


# -- the converter -------------------------------------------------------------- #


def convert_bpmn_export(data: bytes) -> Tuple[PolicyPack, ConversionReport, List[Tuple[str, str]]]:
    """Bytes of a BPMN 2.0 export in; (DRAFT pack, unsealed report, connections) out.

    Raises :class:`ConversionRefused` and writes nothing when the export is not XML,
    not BPMN 2.0, carries a document type or entity declaration, is too large or
    deep, has too many flow nodes, or carries a secret-shaped attribute or text.
    """
    root, input_digest = parse_xml_export(data)
    if local_name(root.tag) != "definitions" or namespace_of(root.tag) != BPMN_NS:
        raise ConversionRefused(RefusalCode.NOT_AN_EXPORT_OF_THIS_FORMAT, "a BPMN 2.0 export is a definitions element in the OMG BPMN namespace")
    processes = [c for c in root if local_name(c.tag) == "process" and namespace_of(c.tag) == BPMN_NS]
    if not processes:
        raise ConversionRefused(RefusalCode.NOT_AN_EXPORT_OF_THIS_FORMAT, "a BPMN 2.0 export holds at least one process")
    nodes = [(p, n) for p in processes for n in _flow_nodes(p)]
    if len(nodes) > MAX_CONSTRUCTS:
        raise ConversionRefused(RefusalCode.TOO_MANY_NODES, f"{len(nodes)} flow nodes exceed {MAX_CONSTRUCTS}")

    workflow_name = (_attr(processes[0], "name") or _attr(root, "name") or _attr(processes[0], "id") or "unnamed BPMN process")
    if len(processes) > 1:
        workflow_name = f"{workflow_name} (+{len(processes) - 1} more)"
    source_id = f"src_bpmn_{input_digest.replace('sha256:', '')[:12]}"
    ctx = _Ctx(source_id)
    lanes: List[Tuple[str, str]] = []
    for process in processes:
        _index_flows(process, ctx)
        lanes.extend(_index_lanes(process, ctx))

    participants = [c for coll in root if local_name(coll.tag) == "collaboration" for c in coll if local_name(c.tag) == "participant"]
    for participant in participants:
        pid = _attr(participant, "id") or "participant"
        ctx.rows.append(MappingRow(source_construct_id=pid, source_construct_type="participant", source_name=_attr(participant, "name"),
                                   outcome=RowOutcome.UNMAPPED, reason_code="POOL_CONTEXT", note="a pool names a party, not a governance object"))
    for lane_id, lane_name in lanes:
        ctx.rows.append(MappingRow(source_construct_id=lane_id or lane_name, source_construct_type="lane", source_name=lane_name,
                                   outcome=RowOutcome.UNMAPPED, reason_code="LANE_PERFORMER_NOT_AUTHORITY",
                                   note="a lane names a performer; an authority requirement is not invented from it"))

    for index, (process, element) in enumerate(nodes):
        kind = local_name(element.tag)
        cid = _attr(element, "id") or f"{kind}-{index}"
        if cid in ctx.seen:
            cid = f"{cid}#{index}"
        ctx.seen.add(cid)
        name = _attr(element, "name") or cid
        base = f"{slug(name)}_{hashing.digest(cid).replace('sha256:', '')[:8]}"
        lane = ctx.lane_of.get(_attr(element, "id"), "")
        lane_note = f" in lane {lane!r}" if lane else ""
        target_text, has_script, has_expression = _extension_detail(element)
        losses: List[str] = []
        if any(local_name(c.tag) in ("multiInstanceLoopCharacteristics", "standardLoopCharacteristics") for c in element):
            losses.append(ctx.loss(cid, "LOOP_NOT_CARRIED", f"{name!r} declares loop characteristics; the compiler carries no loop"))
        if has_expression:
            losses.append(ctx.loss(cid, "EXPRESSION_NOT_EVALUATED", "extension attributes carry expressions; they are recorded, never evaluated"))

        if kind in START_EVENTS:
            defs = _event_definitions(element)
            ctx.gap(cid, "ENTRY_POINT_NOT_GOVERNED", f"start event {name!r} ({', '.join(defs) or 'none'}) admits work with no admission check")
            ctx.rows.append(MappingRow(source_construct_id=cid, source_construct_type=kind, source_name=name, outcome=RowOutcome.UNMAPPED,
                                       reason_code="ENTRY_POINT", note=", ".join(defs), semantic_loss=tuple(losses)))
            continue
        if kind in END_EVENTS:
            defs = _event_definitions(element)
            ctx.rows.append(MappingRow(source_construct_id=cid, source_construct_type=kind, source_name=name, outcome=RowOutcome.UNMAPPED,
                                       reason_code="TERMINAL", note=("the compiler synthesizes its own terminal outcomes; " + ", ".join(defs)).strip("; "),
                                       semantic_loss=tuple(losses)))
            continue
        if kind in CATCH_EVENTS or kind in FLOW_GATEWAYS:
            defs = _event_definitions(element)
            reason = "EVENT_WAIT" if kind in CATCH_EVENTS or kind == "eventBasedGateway" else "PARALLEL_SPLIT"
            losses.append(ctx.loss(cid, "CONTROL_FLOW_CONSTRUCT_NOT_CARRIED", f"{kind} {name!r} is control flow; the compiler synthesizes its own order"))
            ctx.rows.append(MappingRow(source_construct_id=cid, source_construct_type=kind, source_name=name, outcome=RowOutcome.UNMAPPED,
                                       reason_code=reason, note=", ".join(defs), semantic_loss=tuple(sorted(set(losses)))))
            continue
        if kind in BOUNDARY_EVENTS:
            defs = _event_definitions(element)
            losses.append(ctx.loss(cid, "EXCEPTION_PATH_NOT_CARRIED", f"boundary event {name!r} ({', '.join(defs) or 'none'}) on {_attr(element, 'attachedToRef')!r} is an exception path; no exception rule is fabricated"))
            ctx.rows.append(MappingRow(source_construct_id=cid, source_construct_type=kind, source_name=name, outcome=RowOutcome.UNMAPPED,
                                       reason_code="EXCEPTION_PATH", note=", ".join(defs), semantic_loss=tuple(sorted(set(losses)))))
            continue
        if kind in THROW_EVENTS:
            defs = _event_definitions(element)
            if "message" in defs or "signal" in defs or "escalation" in defs:
                cm_id = f"cm_{base}"
                ctx.connectors.append(ConnectorMapping(object_id=cm_id, name=name, policy_concept=slug(name), target_system=f"bpmn:{kind}",
                                                       target_field=", ".join(defs), description=f"converted from BPMN {kind} {name!r}{lane_note}",
                                                       provenance_refs=(source_id,)))
                ctx.tools.append(ToolRequirement(source_construct_id=cid, tool=f"bpmn:{kind}", target=", ".join(defs)))
                ctx.gap(cid, "CONSEQUENTIAL_ACTION_WITHOUT_AUTHORITY", f"{name!r} throws {', '.join(defs)} outward; no authority is declared, so no action constraint is fabricated")
                ctx.rows.append(MappingRow(source_construct_id=cid, source_construct_type=kind, source_name=name, outcome=RowOutcome.MAPPED,
                                           target_object_ids=(cm_id,), target_object_types=("CONNECTOR_MAPPING",), reason_code="EXTERNAL_THROW_TO_CONNECTOR_MAPPING",
                                           note=", ".join(defs), semantic_loss=tuple(sorted(set(losses)))))
            else:
                ctx.rows.append(MappingRow(source_construct_id=cid, source_construct_type=kind, source_name=name, outcome=RowOutcome.UNMAPPED,
                                           reason_code="INTERNAL_THROW", note=", ".join(defs) or "none", semantic_loss=tuple(losses)))
            continue

        if kind in DECISION_GATEWAYS:
            flows = ctx.flows_out.get(_attr(element, "id"), [])
            conditioned = [(fid, tgt, cond) for fid, tgt, cond, is_default in flows if cond and not is_default]
            if any(cond and is_default for _fid, _tgt, cond, is_default in flows):
                losses.append(ctx.loss(cid, "DEFAULT_FLOW_CONDITION_IGNORED", f"the default flow of {name!r} declares a condition; a default flow is taken when no other applies, so its condition is not carried"))
            rule_ids: List[str] = []
            if not conditioned:
                rule_id = f"rule_{base}"
                ctx.decision_rules.append(DecisionRule(object_id=rule_id, name=name, conditions=(),
                                                       description=f"converted from BPMN {kind} {name!r}{lane_note}; no outgoing flow declares a condition",
                                                       provenance_refs=(source_id,)))
                rule_ids.append(rule_id)
                ctx.gap(cid, "BRANCH_PREDICATE_NOT_TRANSLATED", f"gateway {name!r} became a decision rule with no predicate; a reviewer must state it")
            else:
                partial = False
                for fid, tgt, cond in conditioned:
                    predicates, plosses = translate_condition(cond, cid, ctx)
                    losses.extend(plosses)
                    rule_id = f"rule_{base}_{slug(fid)[:24]}"
                    ctx.decision_rules.append(DecisionRule(object_id=rule_id, name=f"{name} → {tgt}", conditions=tuple(predicates),
                                                           description=f"converted from BPMN {kind} {name!r}{lane_note}, outgoing flow {fid!r} to {tgt!r}; predicates translated: {len(predicates)}",
                                                           provenance_refs=(source_id,)))
                    rule_ids.append(rule_id)
                    if not predicates:
                        partial = True
                if partial:
                    ctx.gap(cid, "BRANCH_PREDICATE_PARTIAL", f"gateway {name!r} has at least one outgoing condition that did not translate")
                if len(conditioned) > 1:
                    losses.append(ctx.loss(cid, "GATEWAY_BRANCHES_AS_SEPARATE_RULES", f"{len(conditioned)} conditioned flows became {len(conditioned)} rules; their exclusivity is not carried"))
            if kind == "inclusiveGateway":
                losses.append(ctx.loss(cid, "INCLUSIVE_SEMANTICS_NOT_CARRIED", "an inclusive gateway may take several flows; each is carried as its own rule"))
            ctx.rows.append(MappingRow(source_construct_id=cid, source_construct_type=kind, source_name=name, outcome=RowOutcome.MAPPED,
                                       target_object_ids=tuple(rule_ids), target_object_types=tuple("DECISION_RULE" for _ in rule_ids),
                                       reason_code="GATEWAY_TO_DECISION_RULES", semantic_loss=tuple(sorted(set(losses)))))
            continue
        if kind in UNSUPPORTED_GATEWAYS:
            ctx.rows.append(MappingRow(source_construct_id=cid, source_construct_type=kind, source_name=name, outcome=RowOutcome.UNSUPPORTED,
                                       reason_code="COMPLEX_GATEWAY_NOT_TRANSLATED", semantic_loss=tuple(losses)))
            continue

        if kind in RULE_TASKS:
            rule_id = f"rule_{base}"
            ref = _attr(element, "decisionRef") or target_text
            losses.append(ctx.loss(cid, "DMN_NOT_TRANSLATED", f"the decision logic of {name!r} lives in {ref or 'an undeclared decision'} and is not carried"))
            ctx.decision_rules.append(DecisionRule(object_id=rule_id, name=name, conditions=(),
                                                   description=f"converted from BPMN businessRuleTask {name!r}{lane_note}; decision reference: {ref or 'none'}",
                                                   provenance_refs=(source_id,)))
            ctx.gap(cid, "BRANCH_PREDICATE_NOT_TRANSLATED", f"business rule task {name!r} became a decision rule with no predicate; a reviewer must state it")
            ctx.rows.append(MappingRow(source_construct_id=cid, source_construct_type=kind, source_name=name, outcome=RowOutcome.MAPPED,
                                       target_object_ids=(rule_id,), target_object_types=("DECISION_RULE",), reason_code="BUSINESS_RULE_TO_DECISION_RULE",
                                       note=ref, semantic_loss=tuple(sorted(set(losses)))))
            continue
        if kind in EXECUTABLE_TASKS or has_script:
            ctx.rows.append(MappingRow(source_construct_id=cid, source_construct_type=kind, source_name=name, outcome=RowOutcome.UNSUPPORTED,
                                       reason_code="EXECUTABLE_NOT_TRANSLATED", note="scripts are never inspected or translated", semantic_loss=tuple(losses)))
            continue
        if kind in HUMAN_TASKS:
            ctx.gap(cid, "HUMAN_STEP_WITHOUT_AUTHORITY", f"human task {name!r}{lane_note} names a performer at most, never an authority; an authority requirement is not invented")
            ctx.rows.append(MappingRow(source_construct_id=cid, source_construct_type=kind, source_name=name, outcome=RowOutcome.UNMAPPED,
                                       reason_code="HUMAN_STEP", note=f"lane: {lane}" if lane else "", semantic_loss=tuple(losses)))
            continue
        if kind in READ_TASKS or kind in WRITE_TASKS or kind in SERVICE_TASKS:
            cm_id = f"cm_{base}"
            implementation = _attr(element, "implementation") or _attr(element, "operationRef") or _attr(element, "messageRef")
            target = " ".join(p for p in (implementation, target_text) if p) or kind
            ctx.connectors.append(ConnectorMapping(object_id=cm_id, name=name, policy_concept=slug(name), target_system=f"bpmn:{kind}",
                                                   target_field=target, description=f"converted from BPMN {kind} {name!r}{lane_note}",
                                                   provenance_refs=(source_id,)))
            ctx.tools.append(ToolRequirement(source_construct_id=cid, tool=f"bpmn:{kind}", target=target))
            targets, types = [cm_id], ["CONNECTOR_MAPPING"]
            if kind in READ_TASKS:
                ev_id = f"ev_{base}"
                ctx.evidence.append(RequiredEvidence(object_id=ev_id, name=name, fact_key=slug(name), connector_mapping_id=cm_id,
                                                     description=f"message received by BPMN {kind} {name!r}", provenance_refs=(source_id,)))
                targets.append(ev_id)
                types.append("REQUIRED_EVIDENCE")
                reason = "RECEIVE_TO_CONNECTOR_AND_EVIDENCE"
            elif kind in WRITE_TASKS:
                ctx.gap(cid, "CONSEQUENTIAL_ACTION_WITHOUT_AUTHORITY", f"{name!r} sends outward; no authority is declared, so no action constraint is fabricated")
                reason = "SEND_TO_CONNECTOR_MAPPING"
            else:
                ctx.gap(cid, "SERVICE_EFFECT_UNDECLARED", f"service task {name!r} does not say whether it reads or writes; no evidence or constraint is derived until a reviewer says")
                reason = "SERVICE_TO_CONNECTOR_MAPPING"
            ctx.rows.append(MappingRow(source_construct_id=cid, source_construct_type=kind, source_name=name, outcome=RowOutcome.MAPPED,
                                       target_object_ids=tuple(targets), target_object_types=tuple(types), reason_code=reason,
                                       semantic_loss=tuple(sorted(set(losses)))))
            continue
        if kind in ABSTRACT_TASKS:
            ctx.gap(cid, "TASK_EFFECT_UNDECLARED", f"abstract task {name!r}{lane_note} declares no type; nothing is derived from it")
            ctx.rows.append(MappingRow(source_construct_id=cid, source_construct_type=kind, source_name=name, outcome=RowOutcome.UNMAPPED,
                                       reason_code="ABSTRACT_TASK", semantic_loss=tuple(losses)))
            continue
        if kind in CALLED:
            ctx.rows.append(MappingRow(source_construct_id=cid, source_construct_type=kind, source_name=name, outcome=RowOutcome.UNSUPPORTED,
                                       reason_code="CALLED_PROCESS_NOT_TRANSLATED", note=_attr(element, "calledElement"), semantic_loss=tuple(losses)))
            continue
        if kind in CONTAINERS:
            ctx.rows.append(MappingRow(source_construct_id=cid, source_construct_type=kind, source_name=name, outcome=RowOutcome.UNMAPPED,
                                       reason_code="SUBPROCESS_CONTAINER", note="its flow nodes are read as constructs of their own", semantic_loss=tuple(losses)))
            continue
        ctx.rows.append(MappingRow(source_construct_id=cid, source_construct_type=kind, source_name=name, outcome=RowOutcome.UNSUPPORTED,
                                   reason_code="UNKNOWN_ELEMENT", semantic_loss=tuple(losses)))

    if ctx.connections:
        ctx.loss("$", "CONTROL_FLOW_ORDER_NOT_CARRIED", f"{len(ctx.connections)} sequence flows are recorded in the report; the compiler synthesizes its own order")
    data_refs = sum(1 for p in processes for e in p.iter() if local_name(e.tag) in ("dataObjectReference", "dataStoreReference"))
    if data_refs:
        ctx.loss("$", "DATA_OBJECTS_NOT_CARRIED", f"{data_refs} data object or store references are not carried; evidence is derived from receive tasks only")

    exporter = " ".join(p for p in (_attr(root, "exporter"), _attr(root, "exporterVersion")) if p)
    source_document = SourceDocument(
        object_id=source_id, name=f"BPMN export: {workflow_name}", source_type=ProvenanceSourceType.REFERENCE_IMPLEMENTATION,
        title=workflow_name, document_version=_attr(root, "id"), content_digest=input_digest,
        description="the third-party export this pack was converted from; every object cites it",
    )
    pack_id = f"bpmn_{slug(workflow_name)}_{input_digest.replace('sha256:', '')[:8]}"
    pack = PolicyPack(
        pack_id=pack_id, name=workflow_name, status=PolicyPackStatus.DRAFT, domain="converted",
        description=f"DRAFT converted from a BPMN 2.0 export by ugence-workflow-converters; {converter_identity(FORMAT)['distribution_version']}. "
                    "Structurally translated only: not equivalent, not governed, not approved.",
        source_documents=(source_document,), decision_rules=tuple(ctx.decision_rules), required_evidence=tuple(ctx.evidence),
        connector_mappings=tuple(ctx.connectors),
    )
    report_ = validate_policy_pack(pack)
    unsupported = tuple(r for r in ctx.rows if r.outcome is RowOutcome.UNSUPPORTED)
    state = ConversionState.PARTIAL if (unsupported or ctx.losses) else ConversionState.STRUCTURALLY_TRANSLATED
    counts: Dict[str, int] = {}
    for obj in pack.all_objects():
        counts[obj.object_type.value] = counts.get(obj.object_type.value, 0) + 1
    report = ConversionReport(
        converter=converter_identity(FORMAT),
        source=SourceSummary(format=FORMAT, format_detail=("BPMN 2.0 XML export" + (f"; exporter {exporter}" if exporter else "")),
                             input_digest=input_digest, input_bytes=len(data), workflow_name=workflow_name,
                             construct_count=len(nodes), connection_count=len(ctx.connections)),
        conversion_state=state,
        mapping_table=tuple(ctx.rows),
        unsupported_constructs=unsupported,
        semantic_loss_warnings=tuple(ctx.losses),
        governance_gaps=tuple(ctx.gaps),
        tool_requirements=tuple(ctx.tools),
        credential_requirements=tuple(ctx.credentials),
        pack=PackSummary(pack_id=pack_id, status=pack.status.value, pack_digest=hashing.digest(pack.model_dump(mode="json")), object_counts=counts),
        validation=ValidationSummary(ok=report_.ok, counts=report_.counts(),
                                     blocking=tuple({"code": d.code, "object_id": d.object_id, "message": d.message} for d in report_.blocking)),
    )
    return pack, report, list(ctx.connections)

