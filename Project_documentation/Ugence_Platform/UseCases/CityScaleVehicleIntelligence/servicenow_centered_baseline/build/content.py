# Content model — "ServiceNow-Centered City-Scale Vehicle Intelligence" (Reference Architecture v1.0).
# Ugence is intentionally absent. Responsibilities Ugence formerly provided are surfaced as neutral,
# open architectural items — never silently assigned to ServiceNow. ServiceNow facts are cited from
# official sources (research 15 August 2026). Consumed by build.py (WeasyPrint PDF + python-docx DOCX).

def H1(text,id): return {'t':'h1','text':text,'id':id}
def H2(text,id=None): return {'t':'h2','text':text,'id':id}
def H3(text): return {'t':'h3','text':text}
def P(*runs): return {'t':'p','runs':list(runs)}
def BUL(*items): return {'t':'bul','items':list(items)}
def NUM(*items): return {'t':'num','items':list(items)}
def TABLE(caption,headers,rows,widths=None): return {'t':'table','caption':caption,'headers':headers,'rows':rows,'widths':widths}
def DIAG(svg,caption): return {'t':'diagram','svg':svg,'caption':caption}
def NOTE(text,kind='note',title=None): return {'t':'callout','kind':kind,'text':text,'title':title}
def QUOTE(text): return {'t':'quote','text':text}
def PB(): return {'t':'pagebreak'}
def b(t): return {'text':t,'b':True}
def i(t): return {'text':t,'i':True}
def L(text,href=None): return {'text':text,'href':href or text}

CONTENT=[]
def add(*blocks):
    for x in blocks: CONTENT.append(x)

# ==================== 1. EXECUTIVE SUMMARY ====================
add(
H1('1. Executive summary','sec1'),
P('This document describes a ',b('ServiceNow-centered'),' reference architecture for a city-scale vehicle-intelligence scenario — traffic-signal violation detection, ANPR/ALPR, vehicle re-identification, trajectory reconstruction, bounded investigation, registry access, and citation or enforcement proposals — using ServiceNow products together with the external vehicle-intelligence platform, external consequence systems and legally accountable human authorities. It establishes a factual baseline that can later be compared with other architectures; that comparison is out of scope here.'),
QUOTE('The vehicle-intelligence platform determines what the evidence indicates. ServiceNow coordinates how the resulting event becomes a governed enterprise case — how it is reviewed, routed, approved, executed through connected systems and recorded. External consequence systems carry out the effect; human authorities make the legally accountable decisions.'),
P('“ServiceNow-centered” is used deliberately rather than “ServiceNow-only,” because ServiceNow does not replace cameras and roadside sensors, the computer-vision platform, police / registry / notification / traffic-enforcement systems, or human authorities. Within that boundary, ServiceNow serves as the enterprise ',b('case, workflow, governance-record, policy and control, approval, orchestration, exception-management and reporting'),' environment.'),
NOTE('This is a proposed reference architecture. It is not an official ServiceNow architecture, is not endorsed by ServiceNow, and is not evidence of a deployed customer solution. Availability depends on release, SKU, licensing, Store applications and customer configuration. All external integrations are proposed unless explicitly documented otherwise. Legal, privacy, surveillance, evidence, due-process and enforcement requirements must be validated by the responsible jurisdiction.', kind='warn', title='Standing scope statement'),
)

# ==================== 2. WHAT SERVICENOW CONTRIBUTES ====================
add(
H1('2. What documented ServiceNow products can contribute','sec2'),
P('At a summary level, and grounded in official ServiceNow sources (Section 19), ServiceNow can contribute the enterprise coordination layer for this scenario:'),
BUL(
 [b('The case of record. '),'Public Sector Digital Services (PSDS) provides government case management, and — where licensed and available — Investigative Case Management (ICM) holds narrative, evidence references, entities (including vehicles, locations and events via a master index), tasks and team members in a single structured record.'],
 [b('Workflow and approvals. '),'Workflow Studio / Flow Designer model the process; approval and separation-of-duties patterns route decisions to the right human authority.'],
 [b('Governance records. '),'Integrated Risk Management (IRM) and Policy & Compliance Management hold the policy, control-objective and control library; AI Control Tower holds the AI use-case and model/agent governance record; the CMDB holds asset/CI context (optionally extended by Operational Technology Management).'],
 [b('Integration and data. '),'IntegrationHub / Stream Connect / REST ingest events and orchestrate actions to external systems; Workflow Data Fabric / Zero Copy Connectors can reference external data in place for supported connectors.'],
 [b('Exceptions, reporting and security. '),'Exception and incident handling, Platform / Performance Analytics for KPI/ROI, and Security Incident Response / Security Case Management for security conditions.'],
),
P('What each of these does natively, versus what requires configuration or custom integration, is set out precisely in Section 16. What remains with the vehicle platform, the external systems and human authority is set out in Sections 5 and 9.'),
)

# ==================== 3. HOW TO READ ====================
add(
H1('3. How to read this document','sec3'),
H2('3.1 Framing discipline'),
P('This document does not use competitive language. It never states that ServiceNow “lacks” or “cannot” do something. Where the scenario requires a capability for which no verified native ServiceNow mechanism has been established here, the responsibility is named neutrally using one of the labels below, rather than being assumed to exist or assigned silently to a product.'),
TABLE('Table 1. Neutral responsibility labels used throughout.',
 ['Label','Meaning'],
 [['CUSTOMER CONTROL','A control the customer owns and operates (policy, process or governance decision).'],
  ['EXTERNAL-SYSTEM CONTROL','A control owned by an external system (e.g. the enforcement system, registry).'],
  ['CONFIGURATION REQUIRED','Achievable by configuring documented ServiceNow capabilities; not out-of-the-box behavior.'],
  ['PROPOSED CUSTOM INTEGRATION','Requires a custom application, table, API, spoke or connector to be built.'],
  ['DISCOVERY QUESTION','A product fact (name, SKU, table, API, availability) to confirm with ServiceNow.'],
  ['ARCHITECTURAL RESPONSIBILITY TO ASSIGN','A responsibility the scenario requires that must be explicitly assigned — to configuration, an external system, a human process or an independent control — as an architecture decision.']],
 widths=[0.34,0.66]),
H2('3.2 Capability confidence labels'),
P('The native/configured/proposed table (Section 16) classifies each capability’s confidence as: ',b('VERIFIED NATIVE CAPABILITY'),'; ',b('VERIFIED BUT RELEASE/SKU DEPENDENT'),'; ',b('CONFIGURATION PATTERN'),'; ',b('PROPOSED CUSTOM INTEGRATION'),'; or ',b('DISCOVERY QUESTION'),'.'),
H2('3.3 Colour bands in diagrams'),
P('Every diagram uses four actor colours — ',b('vehicle/city platform'),' (cyan), ',b('ServiceNow'),' (green), ',b('external consequence systems'),' (grey) and ',b('human authority'),' (amber) — plus red for reject/hold branches and a ',b('dashed tan'),' box for a “responsibility to assign / discovery” item that is not a native control.'),
NOTE('Research method: ServiceNow capabilities were researched (15 August 2026) primarily via docs.servicenow.com, then official release notes, product pages and Newsroom; third-party material only for corroboration. Every load-bearing claim carries a complete, clickable source URL with title, release where applicable and access date (Section 19). Release-specific claims should be pinned to the customer’s target release (a Zurich family and a 2026 “Australia” release both exist); where documentation differs by release, confirm rather than combine.', kind='note', title='Sources and release-pinning'),
)

# ==================== 4. SCENARIO & CONTEXT ====================
add(
H1('4. Scenario and operating context','sec4'),
P('The base capability is a city-scale vehicle-intelligence system that detects a traffic-signal violation, identifies vehicles, correlates camera observations and reconstructs a trajectory. The consequential outputs escalate from detection to inference to a proposed enforcement action; the architecture must keep those distinct and route each proposed consequence through case management, review and approval before any external effect.'),
BUL(
 [b('Illustrative event: '),'a possible red-light violation at Junction 44, with camera evidence and a signal-controller state.'],
 [b('External evidence platform: '),'holds the raw video and high-volume sensor data, performs computer-vision inference and produces confidence and provenance.'],
 [b('Consequential actions: '),'a citation, a registry lookup, a disclosure, a notification, or a bounded investigation — each carrying legal and privacy weight.'],
),
P('The scenario is illustrative and technically realistic. It is not a claim of a deployed solution and does not substitute for jurisdiction-specific legal, privacy and due-process validation.'),
)

# ==================== 5. ACTOR & SYSTEM BOUNDARIES ====================
add(
H1('5. Actor and system boundaries','sec5'),
P('Four actors participate. ServiceNow is the enterprise coordination environment; it does not perform computer-vision inference and does not make legally accountable human judgments.'),
DIAG('actors','Figure 1. Actor and system boundaries: vehicle-intelligence / city platform (cyan), ServiceNow (green), external consequence systems (grey) and human authority (amber).'),
H2('5.1 Vehicle-intelligence / city platform (external)'),
BUL('Camera and sensor ingestion; computer-vision inference; ANPR / vehicle classification.',
 'Confidence and uncertainty; trajectory reconstruction; evidence provenance.',
 'Raw video and high-volume sensor storage; secure evidence retrieval.'),
H2('5.2 External consequence systems'),
BUL('Traffic-enforcement system; police / public-safety systems; vehicle registry.',
 'Citizen-notification service; payment / penalty system (if applicable); external appeals / judicial systems.'),
H2('5.3 Human authority'),
BUL('Investigative judgment; approval where required; uncertainty resolution.',
 'Corrected identity; legal and policy interpretation; appeal determination; exceptional or high-impact decisions.'),
)

# ==================== 6. PRODUCT MAP ====================
add(
H1('6. ServiceNow product map','sec6'),
P('Products are included only where they perform a defensible role in this scenario, grouped by role. Availability, SKU, table and licensing are discovery items (Section 17); product behavior is cited in Section 19.'),
DIAG('snowmap','Figure 2. ServiceNow product map by role. “ServiceNow AI Action Fabric” and “Agentic Playbooks” are placed as discovery-dependent because their applicability and governance for this scenario require confirmation for the target release.'),
TABLE('Table 2. ServiceNow product map by role.',
 ['Role','Products','Contribution in this scenario'],
 [['CORE','PSDS case management / Investigative Case Management (where licensed & available); Workflow Studio / Flow Designer; IntegrationHub / Stream Connect / REST; Workflow Data Fabric / Zero Copy Connectors','The case of record, workflow, integration and (where supported) in-place data reference.'],
  ['SUPPORTING GOVERNANCE','AI Control Tower; Integrated Risk Management; Policy & Compliance Management; CMDB; Platform / Performance Analytics','Systems of record for AI governance, policy/controls, assets and measurement.'],
  ['EXCEPTION OR ESCALATION','Security Incident Response; Security Case Management','Security conditions (tampering, unauthorized access).'],
  ['OPTIONAL OPERATIONAL EXTENSION','Operational Technology Management; Field Service Management; Government Service Portal','Asset health & field remediation; constituent self-service — engaged only when relevant.'],
  ['DISCOVERY-DEPENDENT','ServiceNow AI Action Fabric; Agentic Playbooks; Customer Service Management foundation','Roles depend on confirmed naming, availability and governance for the target release.']],
 widths=[0.22,0.42,0.36]),
NOTE('Terminology is used as the cited source states it. ServiceNow’s AI-agent system of action appears in materials as “ServiceNow AI Action Fabric” (sometimes shortened to “Action Fabric”); its exact name and governance for the target release is a discovery question. This document does not depend on that product for the baseline workflow.', kind='note', title='Product naming'),
)

# ==================== 7. DATA-MINIMIZING ARCHITECTURE ====================
add(
H1('7. Data-minimizing architecture','sec7'),
P('The default architecture keeps raw video and high-volume sensor data in the authorized city or vehicle-intelligence platform. ServiceNow ordinarily receives references and metadata — not raw imagery.'),
DIAG('datamin','Figure 3. Data-minimizing architecture: raw data stays in the city platform; ServiceNow holds references and coordinates the case; only an approved action reaches the external system.'),
TABLE('Table 3. What ServiceNow ordinarily receives.',
 ['Received by ServiceNow','Retained outside ServiceNow'],
 [['Case-relevant metadata; secure evidence references; provenance identifiers; content digests where supplied; timestamps; confidence; evidence classification; retrieval authorization; observed-outcome / execution-receipt references','Raw video and high-volume sensor data (in the authorized city / vehicle-intelligence platform)']],
 widths=[0.6,0.4]),
NOTE('Two mechanisms are distinct and should not be conflated: Workflow Data Fabric / Zero Copy Connectors provide real-time access to external data in place, without copying, for supported connectors; IntegrationHub / Stream Connect / REST / custom APIs handle event ingestion and action orchestration. Not every IntegrationHub exchange is zero-copy. Any pattern that stages evidence inside ServiceNow is a CONFIGURATION decision requiring privacy, retention and jurisdiction review.', kind='warn', title='Reference vs. ingest'),
)

# ==================== 8. CANONICAL WORKFLOW ====================
add(
H1('8. ServiceNow-centered canonical workflow','sec8'),
P('The canonical baseline threads the vehicle event through ServiceNow case management, context, review and approval, to a governed dispatch and back. Each arrow names what data or record crosses the boundary.'),
DIAG('canonical','Figure 4. The ServiceNow-centered canonical workflow. The dashed box names responsibilities the scenario requires that are not a single native “authorization” step and must be assigned.'),
H2('8.1 Decision types are distinct'),
P('The architecture deliberately does not insert a generic “authorization” box. The following are different things and are not automatically equivalent; each must be identified and sourced where used:'),
TABLE('Table 4. Distinct decision types.',
 ['Decision type','What it means here'],
 [['Workflow condition','A rule in Flow Designer / Workflow Studio that gates a transition (CONFIGURATION).'],
  ['Policy or control status','An IRM / Policy & Compliance control state referenced as context — a status, not an execution authority.'],
  ['Approval','A human (or delegated) approval routed by the workflow.'],
  ['Access permission','A ServiceNow ACL / role permitting a user or service to act on a record or API.'],
  ['AI-governance status','An AI Control Tower record of a model / AI use-case’s approval state.'],
  ['Dispatch eligibility','A workflow condition determining whether an approved action may be sent to an external system.'],
  ['Legal authority','The jurisdiction’s lawful basis for the action — a CUSTOMER CONTROL / human-authority matter, not a product output.']],
 widths=[0.26,0.74]),
NOTE('Binding an approval to an exact target and parameters, re-checking at commit time, and independently reconciling the executed effect are not asserted as a single native ServiceNow step. They are named as an ARCHITECTURAL RESPONSIBILITY TO ASSIGN (Sections 13 and 15) — to configuration, an external system, a human process or an independent control.', kind='warn', title='No generic “authorization” box'),
)

# ==================== 9. RESPONSIBILITY MATRIX ====================
add(
H1('9. Responsibility matrix','sec9'),
P('Every responsibility in the scenario is assigned to one owner. Removing any additional governance layer does not make a responsibility disappear; where no single owner is native, it is marked shared/configured or an unresolved discovery item, to be assigned as an architecture decision.'),
TABLE('Table 5. Responsibility matrix. Owner ∈ {Vehicle platform, ServiceNow, External system, Human authority, Shared/configured, Unresolved discovery}.',
 ['Responsibility','Owner','Note'],
 [['Source evidence','Vehicle platform','Perception, ANPR, re-ID, trajectory.'],
  ['Raw evidence storage','Vehicle platform','Retained outside ServiceNow by default.'],
  ['Evidence reference','ServiceNow','References/metadata on the case; raw data by exception (CONFIGURATION).'],
  ['Case management','ServiceNow (PSDS / ICM where licensed)','The case of record.'],
  ['Purpose & scope','ServiceNow','Recorded on the case.'],
  ['Jurisdiction','ServiceNow (native vs configured — discovery)','On the case; native modelling is a discovery question.'],
  ['AI inventory & governance','ServiceNow (AI Control Tower)','AI use-case / model governance record.'],
  ['Policy & controls','ServiceNow (IRM / Policy & Compliance)','System of record for the control library.'],
  ['Model eligibility for an action','Shared/configured','AI Control Tower status referenced; per-action gating is CONFIGURATION.'],
  ['Workflow conditions','ServiceNow (Flow Designer)','CONFIGURATION.'],
  ['Human approval','Human authority (routed by ServiceNow)','Approval / separation-of-duties.'],
  ['Action dispatch','ServiceNow (IntegrationHub / Flow)','Dispatch of an approved action.'],
  ['Execution','External system','The enforcement / registry / notification system.'],
  ['Execution receipt','External system → ServiceNow','Receipt reference recorded on the case; receipt trustworthiness is EXTERNAL-SYSTEM CONTROL.'],
  ['Observed effect','External system / Shared','What actually happened; matching it to the approval is an open responsibility.'],
  ['Mismatch handling','Unresolved discovery / Human','Who resolves a mismatch is an ARCHITECTURAL RESPONSIBILITY TO ASSIGN.'],
  ['Authority / permission revocation','ServiceNow (access control) / configured','ACL / role / workflow revocation is CONFIGURATION.'],
  ['Security incident','ServiceNow (SIR / Security Case Mgmt)','Tampering / unauthorized access.'],
  ['Field-service response','ServiceNow (FSM + CMDB / OT)','Asset failure work order.'],
  ['Case write-back','ServiceNow','Result, audit history and analytics.'],
  ['Appeals','Human authority (recorded in ServiceNow)','Determination is human; the record is on the case.'],
  ['Operational analytics','ServiceNow (Platform / Performance Analytics)','KPI / dashboards.'],
  ['ROI & value reporting','ServiceNow (Analytics / AI Control Tower)','Reporting; attribution rules are CONFIGURATION.'],
  ['Independent effect/authorization reconciliation','ARCHITECTURAL RESPONSIBILITY TO ASSIGN','No single native mechanism established here; assign to configuration, external system, human process or an independent control.']],
 widths=[0.28,0.3,0.42]),
)

# ==================== 10. SUCCESSFUL WALKTHROUGH ====================
add(
H1('10. Successful red-light walkthrough','sec10'),
DIAG('redlight','Figure 5. The successful red-light path: vehicle event → reference/ingest → PSDS case + context → review → human approval → workflow dispatch → external execution → case & analytics updated.'),
NUM(
 'The vehicle platform detects a possible violation at Junction 44; raw evidence remains in the evidence platform.',
 'ServiceNow references or ingests the evidence; a PSDS case is created or updated with evidence references and confidence.',
 'Jurisdiction, purpose and classification are established on the case.',
 'Relevant IRM policy / control context is referenced; AI Control Tower model / AI-use-case status is considered where applicable; CMDB (or OT) camera / signal-controller context is attached.',
 'Workflow conditions are evaluated (thresholds, completeness) in Flow Designer.',
 'Required human approval is obtained (separation of duties).',
 'ServiceNow dispatches the approved action through an appropriate integration mechanism (Flow Designer / IntegrationHub).',
 'The external traffic-enforcement system executes or rejects it and returns a result / receipt reference.',
 'The case, audit history and analytics are updated.',
),
NOTE('Documented native capabilities (case, workflow, approvals, integration, analytics) are distinguished from CONFIGURATION and PROPOSED CUSTOM INTEGRATION in Section 16. Whether the observed effect independently matches the approved purpose and parameters is an ARCHITECTURAL RESPONSIBILITY TO ASSIGN (Section 15). Illustrative example.', kind='note', title='What is native vs. to be built'),
)

# ==================== 11. FAILURE / UNCERTAINTY ====================
add(
H1('11. Hold, reject and uncertainty paths','sec11'),
P('The architecture treats uncertainty as a reason to route to review or hold, not to proceed. The routing itself is CONFIGURATION; no ServiceNow-native control is invented to complete a path, and uncertain identity is preserved for human review rather than converted to fact.'),
DIAG('failure','Figure 6. Uncertainty and exception routing to defined outcomes.'),
TABLE('Table 6. Triggers and routed outcomes (routing = CONFIGURATION).',
 ['Trigger','Typical routed outcome'],
 [['Insufficient confidence','HOLD / REQUEST MORE EVIDENCE / HUMAN REVIEW'],
  ['Conflicting evidence','HUMAN REVIEW'],
  ['Stale or unavailable evidence','HOLD / REQUEST MORE EVIDENCE'],
  ['Identity uncertainty','HUMAN REVIEW (identity preserved, not asserted)'],
  ['Jurisdiction mismatch','REJECT / ESCALATE'],
  ['Missing approval','HOLD / ESCALATE'],
  ['Policy or control conflict','HOLD / OPEN EXCEPTION'],
  ['Unapproved AI asset or model','HOLD / HUMAN REVIEW (AI Control Tower status referenced)'],
  ['Unauthorized access attempt','OPEN SECURITY INCIDENT'],
  ['External-system rejection','RECORD result / HUMAN REVIEW'],
  ['Incomplete or ambiguous receipt','HUMAN REVIEW / OPEN EXCEPTION'],
  ['Post-execution dispute','RECORD FOR APPEAL'],
  ['Corrected identity','Update case / RECORD FOR APPEAL'],
  ['Appeal','RECORD FOR APPEAL'],
  ['Camera or controller malfunction','CREATE FIELD-SERVICE WORK ORDER'],
  ['Suspected tampering','OPEN SECURITY INCIDENT']],
 widths=[0.42,0.58]),
)

# ==================== 12. BOUNDED INVESTIGATION ====================
add(
H1('12. Bounded investigation','sec12'),
P('A PSDS investigative case establishes the investigative purpose and bounds time, geography, data class and jurisdiction. Each proposed investigative step is routed through workflow rules, approvals and access controls before an external query is sent.'),
DIAG('investigation','Figure 7. Bounded investigation: widening time, geography, identity resolution or data class becomes a new governed case decision or approval event.'),
BUL(
 'A ServiceNow investigator or (discovery-dependent) an Agentic Playbook proposes another investigative step.',
 'Workflow rules, approvals and access controls (separation of duties) evaluate the step.',
 'The approved query is sent to an external camera, registry or evidence system; results return to the investigative case.',
 'A request to widen time, geography, identity resolution or data class becomes a NEW governed case decision or approval event — enforced by CONFIGURATION, not assumed.',
),
NOTE('Technical ability to run a query is never legal authority to run it. Scope monotonicity (no silent widening) is a CONFIGURATION / approval pattern to design; Agentic Playbook applicability is a DISCOVERY QUESTION for the target release.', kind='warn', title='Capability is not authority'),
)

# ==================== 13. APPEALS & CORRECTED IDENTITY ====================
add(
H1('13. Appeals and corrected identity','sec13'),
P('Appeals and corrected identity are handled as case events, with the determination made by human authority and recorded in ServiceNow.'),
BUL(
 [b('Appeal intake. '),'An appeal opens (or updates) a case activity; the originating enforcement case is linked. Whether a citizen self-service intake uses the Government Service Portal is a DISCOVERY QUESTION / CONFIGURATION.'],
 [b('Corrected identity. '),'A correction updates the case entity record; prior actions taken on the earlier identity are linked so the correction is traceable. The correctness of a re-matched identity is a Human-authority / EXTERNAL-SYSTEM CONTROL matter, not a product assertion.'],
 [b('Determination. '),'The appeal outcome is a human-authority decision recorded on the case; any downstream reversal in the external enforcement system is an EXTERNAL-SYSTEM CONTROL step dispatched and recorded like any other action.'],
),
NOTE('Matching a corrected identity or a reversed action back to the original approved purpose and parameters — end to end — is an ARCHITECTURAL RESPONSIBILITY TO ASSIGN (Section 15). It is not claimed as native reconciliation.', kind='note', title='Traceability vs. reconciliation'),
)

# ==================== 14. SECURITY & OPERATIONAL EXCEPTIONS ====================
add(
H1('14. Security and operational exceptions','sec14'),
P('Two exception families sit outside the ordinary citation workflow and engage only on genuine conditions.'),
DIAG('optional','Figure 8. Optional operational and security branches.'),
BUL(
 [b('Camera or signal-controller malfunction. '),'CMDB (or optional OT Management) records the asset condition; Field Service Management raises a work order and dispatches a technician; the asset-health result returns to the case. Whether cameras and traffic/rail signal controllers are out-of-box OT device classes is a DISCOVERY QUESTION.'],
 [b('Suspected tampering / unauthorized access. '),'Security Incident Response / Security Case Management run a security investigation and containment workflow; revoking an access or permission is a CONFIGURATION / access-control action.'],
),
)

# ==================== 15. ASSURANCE & AUDIT BASELINE ====================
add(
H1('15. Assurance and audit baseline','sec15'),
P('Using documented, configurable capabilities, the ServiceNow-centered architecture can record a substantial audit trail. It can also frame — without competitive language — the assurance questions that remain to be assigned as architecture decisions.'),
DIAG('assurance','Figure 9. What the architecture can record, and the assurance questions that remain a responsibility to assign.'),
H2('15.1 What can be recorded (documented / configurable)'),
BUL('Case history; approvals; workflow activity.',
 'Integration result; exception / incident; policy & control reference.',
 'AI-governance record; operational KPI; audit evidence.'),
H2('15.2 Assurance questions that remain a responsibility to assign'),
TABLE('Table 7. Open assurance questions and where they may be assigned.',
 ['Assurance question','Assign to'],
 [['What exact action was approved, and what exact target & parameters were dispatched?','CONFIGURATION (bind the dispatched payload to the approval) / EXTERNAL-SYSTEM CONTROL'],
  ['Did the external system execute the same request that was approved?','EXTERNAL-SYSTEM CONTROL'],
  ['Is the execution receipt independently trustworthy?','EXTERNAL / INDEPENDENT CONTROL'],
  ['Can the observed effect be matched to the approved purpose and scope?','ARCHITECTURAL RESPONSIBILITY TO ASSIGN'],
  ['Who resolves a mismatch, and what becomes the appeal record?','HUMAN PROCESS / CONFIGURATION']],
 widths=[0.56,0.44]),
NOTE('These are stated neutrally as architecture decisions. This document does not claim independent cryptographic verification of authorization, attempt, execution or effect unless such a mechanism is documented and implemented in the described architecture; none is asserted here.', kind='warn', title='No unsupported assurance claim'),
)

# ==================== 16. NATIVE / CONFIGURED / PROPOSED ====================
add(
H1('16. Native, configured and proposed capability table','sec16'),
P('For each major workflow step: the product(s), the documented native capability, and what would require configuration, custom integration, an external system or a human — with a confidence label. Confidence ∈ {VERIFIED NATIVE, VERIFIED BUT RELEASE/SKU DEPENDENT, CONFIGURATION PATTERN, PROPOSED CUSTOM INTEGRATION, DISCOVERY QUESTION}.'),
TABLE('Table 8. Native vs. configured vs. proposed (by workflow step).',
 ['Workflow step','ServiceNow product','Native capability','Config / custom / external / human','Confidence'],
 [['Reference external data in place','Workflow Data Fabric / Zero Copy Connectors','Zero-copy access for supported connectors','Connector coverage; whether truly at-rest','VERIFIED BUT RELEASE/SKU DEPENDENT'],
  ['Ingest event','IntegrationHub / Stream Connect / REST','Spokes / flows / REST integration','Specific spokes & entitlement','VERIFIED BUT RELEASE/SKU DEPENDENT'],
  ['Create / manage the case','PSDS / ICM (where licensed)','Government case management; entity master index','Jurisdiction / approval / external-reference fields native vs configured','VERIFIED BUT RELEASE/SKU DEPENDENT'],
  ['Purpose, scope, classification','PSDS','Case fields / data model','Some fields may be configured','CONFIGURATION PATTERN'],
  ['Policy / control context','IRM / Policy & Compliance','Control library, control status','Mapping controls to this scenario','VERIFIED NATIVE / CONFIGURATION PATTERN'],
  ['AI-governance status','AI Control Tower','AI use-case & model governance record','Per-action gating logic','VERIFIED NATIVE / CONFIGURATION PATTERN'],
  ['Asset context','CMDB (+ optional OT)','CI / asset system of record','Camera / controller OT classes','DISCOVERY QUESTION'],
  ['Evidence & confidence review','Flow Designer / Workflow Studio','Workflow conditions','Thresholds & rules for this scenario','CONFIGURATION PATTERN'],
  ['Human approval','Flow Designer approvals','Approvals & separation of duties','Approval policy design','VERIFIED NATIVE / CONFIGURATION PATTERN'],
  ['Dispatch approved action','Flow Designer / IntegrationHub','Orchestrated dispatch','Binding payload to the exact approval','CONFIGURATION PATTERN / PROPOSED CUSTOM INTEGRATION'],
  ['External execution','(external system)','—','External-system responsibility','EXTERNAL-SYSTEM CONTROL'],
  ['Execution receipt handling','IntegrationHub / Flow','Capture integration result','Receipt trustworthiness','EXTERNAL-SYSTEM CONTROL'],
  ['Effect ↔ approval reconciliation','—','—','No single native mechanism established here','ARCHITECTURAL RESPONSIBILITY TO ASSIGN'],
  ['Exceptions / incidents / appeals','PSDS / SIR / Security Case Mgmt','Exception & incident handling','Routing & policy','CONFIGURATION PATTERN'],
  ['Analytics / KPI / ROI','Platform / Performance Analytics; AI Control Tower','Dashboards, KPIs, value/ROI reporting','Attribution rules','VERIFIED BUT RELEASE/SKU DEPENDENT']],
 widths=[0.19,0.16,0.2,0.24,0.21]),
)

# ==================== 17. DISCOVERY QUESTIONS ====================
add(
H1('17. Discovery questions for ServiceNow','sec17'),
P('A prioritized set for the partnership discussion (with Praneeth and ServiceNow architects). Product facts are separated from questions requiring confirmation.'),
TABLE('Table 9. Discovery questions.',
 ['#','Area','Question to confirm with ServiceNow'],
 [['Q-1','Names & release','Correct product / feature names and target release (Zurich vs the 2026 “Australia” release); pin every cited URL to the customer’s release.'],
  ['Q-2','PSDS / ICM','PSDS and ICM entitlements/SKUs; ICM availability for the target release; which Store apps are in the base entitlement.'],
  ['Q-3','Case & evidence data model','Exact case and entity tables and the event-entity schema; native modelling of jurisdiction, approvals and external-agency reference IDs vs configuration.'],
  ['Q-4','External-reference support','How external evidence references, digests and retrieval authorizations are stored and linked on the case.'],
  ['Q-5','Workflow Data Fabric / Zero Copy','Availability and connector coverage; whether zero-copy leaves data at rest for all connector types; credit/entitlement model.'],
  ['Q-6','IntegrationHub / Stream Connect','Which spokes / patterns the external-system integrations require; edition / transaction entitlement.'],
  ['Q-7','AI Action Fabric','Exact current name/spelling and governance for the target release; whether it is relevant to this scenario at all.'],
  ['Q-8','Agentic Playbooks','Applicability, single vs multi-agent coordination, and entitlement for the target release.'],
  ['Q-9','AI Control Tower','AI use-case / model records and whether any enforcement is applied; ownership fields; licensing (bundled vs standalone).'],
  ['Q-10','IRM / Policy & Compliance','Control library table names; how control status is referenced by a workflow; packaging/entitlement.'],
  ['Q-11','Approvals & SoD','Documented approval and separation-of-duties patterns for consequential public-sector actions.'],
  ['Q-12','Workflow audit & receipts','Workflow audit semantics; how an integration/execution receipt is captured and how much of the dispatched payload is retained.'],
  ['Q-13','External-system result handling','Expected result / rejection / receipt semantics from the enforcement, registry and notification systems.'],
  ['Q-14','Security & field-service escalation','SecOps SKU covering SIR; Security Case Management product boundary; FSM tier; OT device classes for cameras / signal controllers.'],
  ['Q-15','Reporting & ROI','Analytics tier (Performance Analytics Pro/Premium vs baseline) for the intended KPI/ROI dashboards.'],
  ['Q-16','Custom build','Which custom applications, tables, APIs or spokes would be required for exact-action binding, commit-time recheck and effect reconciliation.']],
 widths=[0.06,0.16,0.78]),
)

# ==================== 18. PHASED PILOT ====================
add(
H1('18. Phased pilot','sec18'),
DIAG('roadmap','Figure 10. A phased adoption roadmap for the ServiceNow-centered baseline.'),
TABLE('Table 10. Phase exit criteria.',
 ['Phase','Exit criterion'],
 [['0 · Discovery','Discovery questions (Section 17) resolved; products, release, entitlements and data model confirmed.'],
  ['1 · Case & context','PSDS case, evidence-reference model and IRM / AI Control Tower / CMDB context stood up; no external dispatch.'],
  ['2 · Review & approval','Workflow conditions, evidence review and human approval / separation-of-duties configured and tested.'],
  ['3 · Governed dispatch','External consequence system integrated; only approved actions dispatched; receipts captured.'],
  ['4 · Exceptions & assurance','Exception / incident / appeal / field-service paths; the open assurance responsibilities explicitly assigned; analytics live.'],
  ['5 · Investigation & scale','Bounded-investigation and scope-expansion approval patterns; hardening and reporting.']],
 widths=[0.3,0.7]),
)

# ==================== 19. SOURCE REGISTER ====================
add(
H1('19. Source and citation register','sec19'),
P('Official ServiceNow sources for each capability, with complete URLs, in the documented priority order (product documentation → release notes → product pages → Newsroom). Access date: ',b('15 August 2026'),'. Where a documentation URL is release-pinned, the release is named; re-open and pin each page to the customer’s target release before customer use.'),
BUL(
 [b('Public Sector Digital Services — '),'Product page; “Exploring Public Sector Digital Services” (Zurich); PSDS data model. ',L('https://www.servicenow.com/products/public-sector-digital-services.html'),' · ',L('https://www.servicenow.com/docs/bundle/zurich-government-industry/page/product/public-sector/concept/exploring-public-sector-digital-services.html'),' · ',L('https://www.servicenow.com/docs/r/government-industry/public-sector-digital-services-data-model.html')],
 [b('Investigative Case Management — '),'“Explore Investigative Case Management”; PSDS case management. ',L('https://www.servicenow.com/docs/r/government-industry/psds-explore-inv-case-management.html'),' · ',L('https://www.servicenow.com/docs/r/government-industry/psds-explore-case-management.html')],
 [b('Customer Service Management (case) — '),'Case management for CSM (Zurich). ',L('https://www.servicenow.com/docs/bundle/zurich-customer-service-management/page/product/customer-service-management/concept/csm-case-management.html')],
 [b('Government Service Portal — '),'Using the Government Service Portal in PSDS (Vancouver). ',L('https://www.servicenow.com/docs/bundle/vancouver-government-industry/page/product/public-sector/concept/using-psds-government-service-portal-overview.html')],
 [b('Workflow Data Fabric / Zero Copy Connectors — '),'Managing connections (Zurich); product page. ',L('https://www.servicenow.com/docs/bundle/zurich-integrate-applications/page/administer/workflow-data-fabric/concept/managing-connections-wdf.html'),' · ',L('https://www.servicenow.com/platform/workflow-data-fabric.html')],
 [b('IntegrationHub — '),'Product page; IntegrationHub concept (Zurich). ',L('https://www.servicenow.com/products/integration-hub.html'),' · ',L('https://www.servicenow.com/docs/bundle/zurich-integrate-applications/page/administer/integrationhub/concept/integrationhub.html')],
 [b('Workflow Studio / Flow Designer — '),'Flow Designer product & architecture (Zurich); Workflow Studio release notes (Washington DC). ',L('https://www.servicenow.com/products/platform-flow-designer.html'),' · ',L('https://www.servicenow.com/docs/bundle/zurich-build-workflows/page/administer/flow-designer/concept/flow-designer-arch-overview.html'),' · ',L('https://www.servicenow.com/docs/bundle/washingtondc-release-notes/page/release-notes/now-platform-app-engine/workflow-studio-rn.html')],
 [b('ServiceNow AI Action Fabric — '),'Product page; Newsroom (2026). ',L('https://www.servicenow.com/platform/action-fabric.html'),' · ',L('https://newsroom.servicenow.com/press-releases/details/2026/ServiceNow-opens-its-full-system-of-action-to-every-AI-Agent-in-the-enterprise/default.aspx')],
 [b('AI Control Tower — '),'Product page; AI inventory docs; Newsroom (2026). ',L('https://www.servicenow.com/products/ai-control-tower.html'),' · ',L('https://www.servicenow.com/docs/r/intelligent-experiences/ai-control-tower/ai-inventory.html'),' · ',L('https://newsroom.servicenow.com/press-releases/details/2026/ServiceNow-expands-AI-Control-Tower-to-discover-observe-govern-secure-and-measure-AI-deployed-across-any-system-in-the-enterprise/default.aspx')],
 [b('Integrated Risk Management — '),'Product page. ',L('https://www.servicenow.com/products/integrated-risk-management.html')],
 [b('Policy & Compliance Management — '),'Product page; docs. ',L('https://www.servicenow.com/products/policy-compliance-management.html'),' · ',L('https://www.servicenow.com/docs/r/governance-risk-compliance/policy-and-compliance-management/r_PolicyComplianceMgmt.html')],
 [b('Agentic Playbooks — '),'Platform page; docs landing. ',L('https://www.servicenow.com/platform/agentic-playbooks.html'),' · ',L('https://www.servicenow.com/docs/r/build-workflows/workflow-studio/agentic-playbooks-landing.html')],
 [b('CMDB — '),'Product page; CMDB documentation. ',L('https://www.servicenow.com/products/servicenow-platform/configuration-management-database.html'),' · ',L('https://www.servicenow.com/docs/r/servicenow-platform/configuration-management-database-cmdb/c_ITILConfigurationManagement.html')],
 [b('Platform / Performance Analytics — '),'Performance Analytics “Your KPIs” (Xanadu Now Intelligence). ',L('https://www.servicenow.com/docs/bundle/xanadu-now-intelligence/page/use/performance-analytics/concept/your-kpis.html')],
 [b('Operational Technology Management — '),'Product page; OT overview docs. ',L('https://www.servicenow.com/products/operational-technology-management.html'),' · ',L('https://www.servicenow.com/docs/r/operational-technology/operational-technology-overview.html')],
 [b('Field Service Management — '),'Product page; work-order docs. ',L('https://www.servicenow.com/products/field-service-management.html'),' · ',L('https://www.servicenow.com/docs/r/field-service-management/work-order-management/t_CreateAWorkOrder.html')],
 [b('Security Incident Response — '),'Product page; SIR landing (Xanadu). ',L('https://www.servicenow.com/products/security-incident-response.html'),' · ',L('https://www.servicenow.com/docs/bundle/xanadu-security-management/page/product/security-incident-response/reference/sir-landing-page.html')],
 [b('Security Case Management — '),'Security case management documentation. ',L('https://www.servicenow.com/docs/r/security-management/case-mgmt.html')],
),
P(i('Every release-, SKU-, table-, API- or availability-specific claim is treated as a discovery question (Section 17), to be confirmed against the live page for the customer’s release before customer use. Third-party material was used only for corroboration, never as the primary basis for a product claim.')),
)

# ==================== 20. GLOSSARY & LIMITATIONS ====================
add(
H1('20. Glossary and limitations','sec20'),
TABLE('Table 11. Glossary.',
 ['Term','Definition'],
 [['ServiceNow-centered','ServiceNow as the enterprise case / workflow / governance-record / policy / approval / orchestration / reporting environment — not a replacement for cameras, the CV platform, external systems or human authorities.'],
  ['PSDS','Public Sector Digital Services — ServiceNow’s digital-government platform (case foundation from CSM).'],
  ['ICM','Investigative Case Management — government investigation case capability within PSDS (where licensed).'],
  ['IRM','Integrated Risk Management — ServiceNow’s GRC suite; system of record for policy / controls.'],
  ['AI Control Tower','ServiceNow’s command center to discover / observe / govern / secure / measure enterprise AI.'],
  ['Workflow Data Fabric / Zero Copy','Reference external data in place without copying, for supported connectors.'],
  ['IntegrationHub / Stream Connect / REST','Event ingestion and action orchestration (not, in general, zero-copy).'],
  ['ServiceNow AI Action Fabric','ServiceNow’s system of action for AI agents via the MCP Server (sometimes shortened to “Action Fabric”); applicability here is a discovery question.'],
  ['ARCHITECTURAL RESPONSIBILITY TO ASSIGN','A responsibility the scenario requires that must be explicitly assigned — to configuration, an external system, a human process or an independent control.']],
 widths=[0.26,0.74]),
H2('20.1 Limitations'),
BUL(
 'This is a proposed reference architecture, not an official or endorsed ServiceNow design, and not evidence of a deployed solution.',
 'Availability depends on release, SKU, licensing, Store applications and customer configuration; all external integrations are proposed unless explicitly documented otherwise.',
 'ServiceNow capabilities are cited from official sources and should be page-verified and release-pinned before customer use.',
 'Legal, privacy, surveillance, evidence, due-process and enforcement requirements must be validated by the responsible jurisdiction.',
 'No independent cryptographic verification of authorization, attempt, execution or effect is claimed; the open assurance responsibilities (Section 15) are architecture decisions to assign.',
),
P(i('End of document. ServiceNow-centered proposed reference architecture and illustrative technical case study, grounded in official ServiceNow sources identified on 2026-08-15 (page-verify and release-pin before customer use). Not legal advice, not a claimed deployment, and not ServiceNow-endorsed.')),
)
