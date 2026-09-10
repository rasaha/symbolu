# Ugence Workflow Converters

`ugence-workflow-converters` converts a third-party workflow export, **offline**,
into three files the Ugence tooling already understands:

1. a **DRAFT policy pack** (`policy_pack.draft.json`), the Policy Workflow Compiler's
   input, holding only what the export honestly declares;
2. a **content-addressed conversion report** (`conversion_report.json`) with a
   mapping table for every construct, the unsupported constructs, the semantic-loss
   warnings, the governance gaps, and the tool and credential requirements as
   handles only;
3. a **preview Workflow IR** (`preview_workflow_ir.v1.json`) labelled
   `PREVIEW_UNAPPROVED`, synthesized by the compiler's public synthesizer from the
   validated draft, for inspection on the Governance Studio's Bring Your Workflow
   screen.

Owner ruling CV-1 to CV-5 (`docs/architecture/ADR_UGENCE_AUTHORITY_PLANE_SCOPING.md`
§23). It is **tooling, not a governance authority**, and it makes exactly one claim:

> Constructs were translated per the mapping table and nothing more. This report
> makes no claim of semantic equivalence, governance, approval, validation or
> executability. The emitted pack is a DRAFT for human review; the preview Workflow
> IR is unapproved.

## Formats

| Format | Status | Why |
|---|---|---|
| n8n workflow JSON | **implemented** | declarative file; credentials referenced by id and name, never by value |
| BPMN 2.0 XML | **implemented** | declarative XML; a document type or entity declaration is refused before parsing |
| LangGraph, CrewAI, AutoGen | deferred | their definitions live in code or framework objects; converting them means importing or executing customer code, which the ruling forbids. Deferred until a declarative export exists |

## Use

```bash
ugence-workflow-converters version
ugence-workflow-converters formats
ugence-workflow-converters convert n8n my-workflow.n8n.json --out out/ [--no-preview]
ugence-workflow-converters convert bpmn-2.0 my-process.bpmn --out out/ [--no-preview]
```

Exit 0 on a conversion (`PARTIAL` included; the report says what did not translate),
2 on a refusal (nothing is written), 1 on a usage error.

## What the n8n converter does with each node

| n8n construct | Pack object | Report |
|---|---|---|
| `if` branch | `DecisionRule` with the predicates that translate (`$json.field` against a literal, with the comparators the compiler has) | loss codes for each condition that did not |
| `switch`, `filter` | `DecisionRule` with no predicate | `SWITCH_CASES_NOT_TRANSLATED`; gap `BRANCH_PREDICATE_NOT_TRANSLATED` |
| HTTP or app node that reads | `ConnectorMapping` + `RequiredEvidence` | credential handle, tool requirement |
| HTTP or app node that writes | `ConnectorMapping` only | gap `CONSEQUENTIAL_ACTION_WITHOUT_AUTHORITY`: no authority is declared, so no `ActionConstraint` is fabricated |
| LangChain model or agent node | nothing | gap `MODEL_STEP_WITHOUT_GOVERNANCE`, tool requirement |
| form (human step) | nothing | gap `HUMAN_STEP_WITHOUT_AUTHORITY` |
| trigger | nothing | gap `ENTRY_POINT_NOT_GOVERNED` |
| set, merge, noOp and other data shaping | nothing | `UNMAPPED`, no governance meaning |
| code, function, command, sub-workflow | nothing | `UNSUPPORTED`, never inspected beyond its type |
| unknown type | nothing | `UNSUPPORTED`; the conversion is `PARTIAL` |

Every emitted object cites the export itself, registered as the pack's
`SourceDocument` with the input digest: the one provenance the converter truly has.

## What the BPMN 2.0 converter does with each element

| BPMN construct | Pack object | Report |
|---|---|---|
| exclusive or inclusive gateway | one `DecisionRule` per conditioned outgoing flow, with the predicates that translate (`variable <op> literal`, `variable`, `!variable`, conjoined) | loss codes per clause that did not; the default flow's condition is ignored and said so |
| businessRuleTask | `DecisionRule` with no predicate | `DMN_NOT_TRANSLATED`; gap `BRANCH_PREDICATE_NOT_TRANSLATED` |
| receiveTask | `ConnectorMapping` + `RequiredEvidence` | tool requirement |
| sendTask, message or signal throw | `ConnectorMapping` only | gap `CONSEQUENTIAL_ACTION_WITHOUT_AUTHORITY` |
| serviceTask | `ConnectorMapping` only | gap `SERVICE_EFFECT_UNDECLARED`: BPMN does not say whether it reads or writes |
| userTask, manualTask | nothing | gap `HUMAN_STEP_WITHOUT_AUTHORITY`, naming the lane as performer context |
| startEvent | nothing | gap `ENTRY_POINT_NOT_GOVERNED` |
| endEvent, catch events, parallel and event-based gateways, boundary events | nothing | `UNMAPPED`, control flow and exception paths are not carried |
| abstract task | nothing | gap `TASK_EFFECT_UNDECLARED` |
| lane, participant | nothing | `UNMAPPED`, performer and pool context |
| scriptTask, callActivity, complexGateway | nothing | `UNSUPPORTED`; scripts are never inspected |
| any other element of the BPMN namespace under a process | nothing | `UNSUPPORTED`; the conversion is `PARTIAL` |

BPMN names no credentials, so the credential requirements of a BPMN conversion are always empty.

## What it refuses, whole

Not JSON or not XML (YAML, code, archives), not an object, not an export of the named
format, an XML document type or entity declaration, over 1 MiB, deeper than 32
levels, more than 200 nodes, or any secret-shaped key, attribute, name/value pair or
value anywhere in the export. A refusal writes nothing.

## What it never does

Fetch a URL, execute or inspect code, import a framework object, move a pack past
`DRAFT` (the compiler refuses `DRAFT -> COMPILED`, and a test proves the converter's
output cannot be compiled without approval), write `SEMANTICALLY_EQUIVALENT` (the
composer's reserved word), or store, copy or name a secret value.

## Develop

```bash
cd packages/tooling/workflow-converters && python -m pytest -q
```

The suite puts this package's `src`, the compiler's and, when present, the
composer's on `sys.path`; the composer is optional and one test skips without it.
