"""n8n workflow export → DRAFT policy pack + mapping table (CV-2, CV-3, CV-4).

An n8n export is a JSON object with ``nodes`` (each with ``id``, ``name``, ``type``,
``parameters`` and, for nodes that reach a system, ``credentials`` naming a stored
credential by id and name, never its value) and ``connections`` (name-keyed
adjacency). This converter reads exactly that, by type, through the table below,
and writes each construct into the compiler's own objects where one honestly fits:

  branch (if)              → DecisionRule, with the predicates that translate
  branch (switch, filter)  → DecisionRule with no predicate, and a loss warning
  system read              → ConnectorMapping + RequiredEvidence
  system write             → ConnectorMapping, and a governance gap: the action has
                             no authority, so no ActionConstraint is fabricated
  model or agent step      → nothing in the pack; a gap and a tool requirement
  human step               → nothing in the pack; a gap: authority is not invented
  trigger                  → nothing; a gap: entry is unadmitted
  data shaping             → nothing; no governance meaning
  code, command, workflow  → UNSUPPORTED, never inspected beyond its type
  unknown type             → UNSUPPORTED, and the conversion is PARTIAL

Every emitted object cites the export itself, registered as the pack's
``SourceDocument`` with the input digest, as its provenance: that is the one true
provenance the converter has. Nothing else is invented, and the pack stays DRAFT.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional, Tuple

from ugence_policy_workflow_compiler.api import PolicyPack, validate_policy_pack
from ugence_policy_workflow_compiler.models.common import PolicyPackStatus
from ugence_policy_workflow_compiler.models.connectors import ConnectorMapping
from ugence_policy_workflow_compiler.models.evidence import RequiredEvidence
from ugence_policy_workflow_compiler.models.provenance import ProvenanceSourceType, SourceDocument
from ugence_policy_workflow_compiler.models.rules import Comparator, DecisionRule, Predicate
from ugence_policy_workflow_compiler.serialization import hashing

from ..intake import MAX_CONSTRUCTS, parse_export, slug
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

FORMAT = "n8n"

# -- the mapping table, by n8n node type ------------------------------------- #

BRANCH_IF = ("n8n-nodes-base.if",)
BRANCH_OTHER = ("n8n-nodes-base.switch", "n8n-nodes-base.filter")
EXECUTABLE = ("n8n-nodes-base.code", "n8n-nodes-base.function", "n8n-nodes-base.functionItem",
              "n8n-nodes-base.executeCommand", "n8n-nodes-base.executeWorkflow",
              "n8n-nodes-base.ssh", "n8n-nodes-base.python")
DATA_SHAPING = ("n8n-nodes-base.set", "n8n-nodes-base.merge", "n8n-nodes-base.noOp",
                "n8n-nodes-base.splitInBatches", "n8n-nodes-base.itemLists", "n8n-nodes-base.aggregate",
                "n8n-nodes-base.sort", "n8n-nodes-base.limit", "n8n-nodes-base.wait",
                "n8n-nodes-base.dateTime", "n8n-nodes-base.renameKeys", "n8n-nodes-base.splitOut",
                "n8n-nodes-base.removeDuplicates", "n8n-nodes-base.summarize",
                "n8n-nodes-base.compareDatasets", "n8n-nodes-base.stopAndError", "n8n-nodes-base.editImage",
                "n8n-nodes-base.html", "n8n-nodes-base.markdown", "n8n-nodes-base.xml", "n8n-nodes-base.crypto")
HUMAN = ("n8n-nodes-base.form",)
TRIGGER_EXACT = ("n8n-nodes-base.manualTrigger", "n8n-nodes-base.webhook", "n8n-nodes-base.cron",
                 "n8n-nodes-base.scheduleTrigger", "n8n-nodes-base.formTrigger", "n8n-nodes-base.start")
MODEL_PREFIX = "@n8n/n8n-nodes-langchain."
HTTP = "n8n-nodes-base.httpRequest"

WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
WRITE_OPERATIONS = {"create", "update", "delete", "send", "post", "sendMessage", "postMessage", "insert",
                    "upsert", "execute", "write", "append", "remove", "publish", "trigger", "run",
                    "sendEmail", "reply", "move", "archive", "invite", "add", "set"}
EXPRESSION = re.compile(r"=\s*\{\{|\{\{.*\}\}")

_IF_V2_OPERATIONS = {
    "equals": Comparator.EQ, "notEquals": Comparator.NE,
    "gt": Comparator.GT, "gte": Comparator.GTE, "lt": Comparator.LT, "lte": Comparator.LTE,
    "larger": Comparator.GT, "largerEqual": Comparator.GTE, "smaller": Comparator.LT, "smallerEqual": Comparator.LTE,
    "exists": Comparator.NON_EMPTY, "notExists": Comparator.IS_EMPTY,
    "notEmpty": Comparator.NON_EMPTY, "empty": Comparator.IS_EMPTY,
    "true": Comparator.IS_TRUE, "false": Comparator.IS_FALSE,
}
_IF_V1_OPERATIONS = {
    "equal": Comparator.EQ, "notEqual": Comparator.NE, "larger": Comparator.GT, "largerEqual": Comparator.GTE,
    "smaller": Comparator.LT, "smallerEqual": Comparator.LTE, "isEmpty": Comparator.IS_EMPTY,
    "isNotEmpty": Comparator.NON_EMPTY, "true": Comparator.IS_TRUE, "false": Comparator.IS_FALSE,
}
_FACT_REF = re.compile(r"^=?\s*\{\{\s*\$json(?:\.([A-Za-z_][A-Za-z0-9_]*)|\[[\"']([^\"']+)[\"']\])\s*\}\}\s*$")

# -- helpers ----------------------------------------------------------------- #


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

    def loss(self, cid: str, code: str, detail: str) -> str:
        self.losses.append(SemanticLossWarning(source_construct_id=cid, code=code, detail=detail))
        return code

    def gap(self, cid: str, code: str, detail: str) -> None:
        self.gaps.append(GovernanceGap(source_construct_id=cid, gap_code=code, detail=detail))


def _construct_id(node: Mapping[str, Any], index: int) -> str:
    raw = str(node.get("id") or node.get("name") or f"node-{index}")
    return raw


def _fact_key(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    m = _FACT_REF.match(value)
    if not m:
        return None
    return m.group(1) or m.group(2)


def _literal(value: Any) -> Tuple[bool, Any, str]:
    """(usable, value, loss_code). Floats are integers or refused; expressions refused."""
    if isinstance(value, bool) or value is None or isinstance(value, int):
        return True, value, ""
    if isinstance(value, float):
        if value.is_integer():
            return True, int(value), ""
        return False, None, "NON_INTEGER_LITERAL"
    if isinstance(value, str):
        if EXPRESSION.search(value):
            return False, None, "EXPRESSION_NOT_TRANSLATED"
        return True, value, ""
    return False, None, "LITERAL_SHAPE_NOT_TRANSLATED"


def _has_expression(value: Any) -> bool:
    stack = [value]
    while stack:
        v = stack.pop()
        if isinstance(v, str) and EXPRESSION.search(v):
            return True
        if isinstance(v, Mapping):
            stack.extend(v.values())
        elif isinstance(v, (list, tuple)):
            stack.extend(v)
    return False


def _if_predicates(params: Mapping[str, Any], cid: str, ctx: _Ctx) -> Tuple[List[Predicate], List[str]]:
    predicates: List[Predicate] = []
    losses: List[str] = []
    conditions = params.get("conditions")
    if isinstance(conditions, Mapping) and isinstance(conditions.get("conditions"), list):
        # IF node v2: {conditions: {conditions: [{leftValue, rightValue, operator: {type, operation}}]}}
        for cond in conditions["conditions"]:
            if not isinstance(cond, Mapping):
                continue
            op = cond.get("operator", {}) if isinstance(cond.get("operator"), Mapping) else {}
            comparator = _IF_V2_OPERATIONS.get(str(op.get("operation", "")))
            fact = _fact_key(cond.get("leftValue"))
            usable, literal, loss = _literal(cond.get("rightValue"))
            if comparator is None:
                losses.append(ctx.loss(cid, "OPERATOR_NOT_TRANSLATED", f"operator {op.get('operation')!r} has no compiler comparator"))
                continue
            if fact is None:
                losses.append(ctx.loss(cid, "EXPRESSION_NOT_TRANSLATED", "left value is not a plain $json field reference"))
                continue
            if comparator in (Comparator.NON_EMPTY, Comparator.IS_EMPTY, Comparator.IS_TRUE, Comparator.IS_FALSE):
                predicates.append(Predicate(fact_key=fact, comparator=comparator))
                continue
            if not usable:
                losses.append(ctx.loss(cid, loss, "right value could not be carried as a deterministic literal"))
                continue
            predicates.append(Predicate(fact_key=fact, comparator=comparator, value=literal))
    elif isinstance(conditions, Mapping):
        # IF node v1: {conditions: {number: [{value1, operation, value2}], string: [...], boolean: [...]}}
        for group in ("number", "string", "boolean"):
            for cond in conditions.get(group, []) or []:
                if not isinstance(cond, Mapping):
                    continue
                comparator = _IF_V1_OPERATIONS.get(str(cond.get("operation", "equal")))
                fact = _fact_key(cond.get("value1"))
                usable, literal, loss = _literal(cond.get("value2"))
                if comparator is None:
                    losses.append(ctx.loss(cid, "OPERATOR_NOT_TRANSLATED", f"operation {cond.get('operation')!r} has no compiler comparator"))
                    continue
                if fact is None:
                    losses.append(ctx.loss(cid, "EXPRESSION_NOT_TRANSLATED", "value1 is not a plain $json field reference"))
                    continue
                if comparator in (Comparator.NON_EMPTY, Comparator.IS_EMPTY, Comparator.IS_TRUE, Comparator.IS_FALSE):
                    predicates.append(Predicate(fact_key=fact, comparator=comparator))
                    continue
                if not usable:
                    losses.append(ctx.loss(cid, loss, "value2 could not be carried as a deterministic literal"))
                    continue
                predicates.append(Predicate(fact_key=fact, comparator=comparator, value=literal))
    else:
        losses.append(ctx.loss(cid, "BRANCH_PREDICATE_NOT_TRANSLATED", "the branch declares no readable conditions"))
    combinator = conditions.get("combinator") if isinstance(conditions, Mapping) else None
    if combinator and str(combinator).lower() == "or" and len(predicates) > 1:
        losses.append(ctx.loss(cid, "OR_COMBINATOR_NOT_TRANSLATED", "compiler predicates conjoin; an OR branch is carried as its parts"))
    return predicates, sorted(set(losses))


def _credential_handles(node: Mapping[str, Any], cid: str, ctx: _Ctx) -> str:
    handles: List[str] = []
    creds = node.get("credentials")
    if isinstance(creds, Mapping):
        for ctype, ref in sorted(creds.items()):
            name = ref.get("name") if isinstance(ref, Mapping) else ref
            handle = f"{ctype}:{slug(str(name or ctype))}"
            handles.append(handle)
            ctx.credentials.append(CredentialRequirement(source_construct_id=cid, credential_type=str(ctype), credential_handle=handle))
    return ";".join(handles)


def _target_of(node_type: str, params: Mapping[str, Any]) -> Tuple[str, bool]:
    """(target description without a scheme, is_write)."""
    method = str(params.get("method", "GET") or "GET").upper()
    if node_type == HTTP:
        url = str(params.get("url", "") or "")
        url = re.sub(r"^[a-z][a-z0-9+.-]*://", "", url, flags=re.IGNORECASE)
        return f"{method} {url}".strip(), method in WRITE_METHODS
    resource = str(params.get("resource", "") or "")
    operation = str(params.get("operation", "") or "")
    is_write = operation in WRITE_OPERATIONS or any(w in node_type.lower() for w in ("send", "emailsend"))
    target = " ".join(p for p in (resource, operation) if p) or node_type.split(".")[-1]
    return target, is_write


def _is_trigger(node_type: str) -> bool:
    return node_type in TRIGGER_EXACT or node_type.endswith("Trigger")


def _connections(export: Mapping[str, Any]) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    conns = export.get("connections")
    if not isinstance(conns, Mapping):
        return out
    for source, outputs in conns.items():
        if not isinstance(outputs, Mapping):
            continue
        for lanes in outputs.values():
            if not isinstance(lanes, list):
                continue
            for lane in lanes:
                if not isinstance(lane, list):
                    continue
                for target in lane:
                    if isinstance(target, Mapping) and target.get("node"):
                        out.append((str(source), str(target["node"])))
    return out


# -- the converter ----------------------------------------------------------- #


def convert_n8n_export(data: bytes) -> Tuple[PolicyPack, ConversionReport, List[Tuple[str, str]]]:
    """Bytes of an n8n export in; (DRAFT pack, unsealed report, connections) out.

    Raises :class:`ConversionRefused` and writes nothing when the export is not
    JSON, not an n8n export, too large or deep, has too many nodes, or carries a
    secret-shaped key or value anywhere.
    """
    export, input_digest = parse_export(data)
    nodes = export.get("nodes")
    if not isinstance(nodes, list) or "connections" not in export:
        raise ConversionRefused(RefusalCode.NOT_AN_EXPORT_OF_THIS_FORMAT, "an n8n export has a nodes list and a connections object")
    if len(nodes) > MAX_CONSTRUCTS:
        raise ConversionRefused(RefusalCode.TOO_MANY_NODES, f"{len(nodes)} nodes exceed {MAX_CONSTRUCTS}")

    workflow_name = str(export.get("name") or "unnamed n8n workflow")
    source_id = f"src_n8n_{input_digest.replace('sha256:', '')[:12]}"
    ctx = _Ctx(source_id)
    seen_ids: set = set()

    for index, node in enumerate(nodes):
        if not isinstance(node, Mapping):
            cid = f"node-{index}"
            ctx.rows.append(MappingRow(source_construct_id=cid, source_construct_type="?", outcome=RowOutcome.UNSUPPORTED, reason_code="MALFORMED_NODE"))
            continue
        cid = _construct_id(node, index)
        if cid in seen_ids:
            cid = f"{cid}#{index}"
        seen_ids.add(cid)
        ntype = str(node.get("type") or "")
        name = str(node.get("name") or cid)
        params = node.get("parameters") if isinstance(node.get("parameters"), Mapping) else {}
        base = f"{slug(name)}_{hashing.digest(cid).replace('sha256:', '')[:8]}"
        losses: List[str] = []
        if node.get("disabled") is True:
            losses.append(ctx.loss(cid, "DISABLED_IN_SOURCE", "the node is disabled in the export; it is carried as declared"))

        if _is_trigger(ntype):
            ctx.gap(cid, "ENTRY_POINT_NOT_GOVERNED", f"trigger {name!r} admits work with no admission check; the compiler has no entry construct")
            ctx.rows.append(MappingRow(source_construct_id=cid, source_construct_type=ntype, source_name=name, outcome=RowOutcome.UNMAPPED, reason_code="ENTRY_POINT", semantic_loss=tuple(losses)))
            continue

        if ntype in BRANCH_IF or ntype in BRANCH_OTHER:
            if ntype in BRANCH_IF:
                predicates, plosses = _if_predicates(params, cid, ctx)
                losses.extend(plosses)
            else:
                predicates = []
                losses.append(ctx.loss(cid, "SWITCH_CASES_NOT_TRANSLATED", f"{ntype.split('.')[-1]} cases are not carried as predicates"))
            rule_id = f"rule_{base}"
            rule = DecisionRule(object_id=rule_id, name=name, description=f"converted from n8n {ntype} {name!r}; predicates translated: {len(predicates)}",
                                conditions=tuple(predicates), provenance_refs=(source_id,))
            ctx.decision_rules.append(rule)
            if not predicates:
                ctx.gap(cid, "BRANCH_PREDICATE_NOT_TRANSLATED", f"branch {name!r} became a decision rule with no predicate; a reviewer must state it")
            elif losses:
                ctx.gap(cid, "BRANCH_PREDICATE_PARTIAL", f"branch {name!r} lost at least one condition in translation")
            ctx.rows.append(MappingRow(source_construct_id=cid, source_construct_type=ntype, source_name=name, outcome=RowOutcome.MAPPED,
                                       target_object_ids=(rule_id,), target_object_types=("DECISION_RULE",), reason_code="BRANCH_TO_DECISION_RULE",
                                       semantic_loss=tuple(sorted(set(losses)))))
            continue

        if ntype in EXECUTABLE:
            ctx.rows.append(MappingRow(source_construct_id=cid, source_construct_type=ntype, source_name=name, outcome=RowOutcome.UNSUPPORTED,
                                       reason_code="EXECUTABLE_NOT_TRANSLATED", note="code, commands and sub-workflows are never inspected or translated",
                                       semantic_loss=tuple(losses)))
            continue

        if ntype.startswith(MODEL_PREFIX):
            _credential_handles(node, cid, ctx)
            ctx.tools.append(ToolRequirement(source_construct_id=cid, tool=ntype, target=str(params.get("model", "") or "")))
            ctx.gap(cid, "MODEL_STEP_WITHOUT_GOVERNANCE", f"model or agent step {name!r} has no model-selection, steering or clearance declaration in the export")
            ctx.rows.append(MappingRow(source_construct_id=cid, source_construct_type=ntype, source_name=name, outcome=RowOutcome.UNMAPPED,
                                       reason_code="MODEL_STEP", semantic_loss=tuple(losses)))
            continue

        if ntype in HUMAN:
            ctx.gap(cid, "HUMAN_STEP_WITHOUT_AUTHORITY", f"human step {name!r} names no authority; an authority requirement is not invented")
            ctx.rows.append(MappingRow(source_construct_id=cid, source_construct_type=ntype, source_name=name, outcome=RowOutcome.UNMAPPED,
                                       reason_code="HUMAN_STEP", semantic_loss=tuple(losses)))
            continue

        if ntype in DATA_SHAPING:
            ctx.rows.append(MappingRow(source_construct_id=cid, source_construct_type=ntype, source_name=name, outcome=RowOutcome.UNMAPPED,
                                       reason_code="DATA_SHAPING", note="no governance meaning; not carried", semantic_loss=tuple(losses)))
            continue

        reaches_a_system = ntype == HTTP or isinstance(node.get("credentials"), Mapping) or ntype.startswith("n8n-nodes-base.")
        if reaches_a_system and ntype.startswith(("n8n-nodes-base.", "@")) and ntype:
            handle = _credential_handles(node, cid, ctx)
            target, is_write = _target_of(ntype, params)
            if _has_expression(params):
                losses.append(ctx.loss(cid, "EXPRESSION_NOT_EVALUATED", "parameters carry n8n expressions; they are recorded, never evaluated"))
            cm_id = f"cm_{base}"
            ctx.connectors.append(ConnectorMapping(object_id=cm_id, name=name, policy_concept=slug(name), target_system=ntype,
                                                   target_field=target or ntype, credential_handle=handle,
                                                   description=f"converted from n8n {ntype} {name!r}", provenance_refs=(source_id,)))
            ctx.tools.append(ToolRequirement(source_construct_id=cid, tool=ntype, target=target))
            targets = [cm_id]
            types = ["CONNECTOR_MAPPING"]
            if is_write:
                ctx.gap(cid, "CONSEQUENTIAL_ACTION_WITHOUT_AUTHORITY", f"{name!r} writes to {ntype}; no authority is declared, so no action constraint is fabricated")
                reason = "SYSTEM_WRITE_TO_CONNECTOR_MAPPING"
            else:
                ev_id = f"ev_{base}"
                ctx.evidence.append(RequiredEvidence(object_id=ev_id, name=name, fact_key=slug(name), connector_mapping_id=cm_id,
                                                     description=f"data read by n8n {ntype} {name!r}", provenance_refs=(source_id,)))
                targets.append(ev_id)
                types.append("REQUIRED_EVIDENCE")
                reason = "SYSTEM_READ_TO_CONNECTOR_AND_EVIDENCE"
            ctx.rows.append(MappingRow(source_construct_id=cid, source_construct_type=ntype, source_name=name, outcome=RowOutcome.MAPPED,
                                       target_object_ids=tuple(targets), target_object_types=tuple(types), reason_code=reason,
                                       semantic_loss=tuple(sorted(set(losses)))))
            continue

        ctx.rows.append(MappingRow(source_construct_id=cid, source_construct_type=ntype or "?", source_name=name, outcome=RowOutcome.UNSUPPORTED,
                                   reason_code="UNKNOWN_NODE_TYPE", semantic_loss=tuple(losses)))

    connections = _connections(export)
    if connections:
        ctx.loss("$", "CONTROL_FLOW_ORDER_NOT_CARRIED", f"{len(connections)} connections are recorded in the report; the compiler synthesizes its own order")
    if export.get("pinData"):
        ctx.loss("$", "PINNED_DATA_IGNORED", "pinned test data in the export is not read")

    source_document = SourceDocument(
        object_id=source_id, name=f"n8n export: {workflow_name}", source_type=ProvenanceSourceType.REFERENCE_IMPLEMENTATION,
        title=workflow_name, document_version=str(export.get("versionId", "") or ""), content_digest=input_digest,
        description="the third-party export this pack was converted from; every object cites it",
    )
    pack_id = f"n8n_{slug(workflow_name)}_{input_digest.replace('sha256:', '')[:8]}"
    pack = PolicyPack(
        pack_id=pack_id, name=workflow_name, status=PolicyPackStatus.DRAFT, domain="converted",
        description=f"DRAFT converted from an n8n export by ugence-workflow-converters; {converter_identity(FORMAT)['distribution_version']}. "
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
        source=SourceSummary(format=FORMAT, format_detail="n8n workflow JSON export", input_digest=input_digest, input_bytes=len(data),
                             workflow_name=workflow_name, construct_count=len(nodes), connection_count=len(connections)),
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
    return pack, report, connections
