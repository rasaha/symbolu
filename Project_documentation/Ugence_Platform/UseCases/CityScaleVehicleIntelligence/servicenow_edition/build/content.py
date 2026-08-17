# Content model — "Ugence + ServiceNow for City-Scale Vehicle Intelligence" (Integration Edition v1.0).
# Consumed by build.py (WeasyPrint PDF + python-docx DOCX). Ugence architecture/maturity is sourced
# from the vendor-neutral v2.0 brief; ServiceNow facts are from official-domain research (2026-08-15)
# with exact citations and explicit DISCOVERY QUESTION flags where not page-verified.

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
def MOD(name,maturity,rows): return {'t':'modcard','name':name,'maturity':maturity,'rows':rows}

CONTENT=[]
def add(*blocks):
    for x in blocks: CONTENT.append(x)

PROP='PROPOSED SERVICENOW INTEGRATION'

# ==================== 1. PURPOSE & HOW TO READ ====================
add(
H1('1. Purpose, scope and how to read this document','sec1'),
P('This is the ServiceNow-integrated edition of the Ugence city-scale vehicle-intelligence briefing. It proposes how the current Ugence governance and execution-assurance architecture could ',b('compose with ServiceNow'),' to govern a city-scale vehicle-intelligence system — traffic-signal violation detection, ANPR/ALPR, vehicle re-identification, trajectory reconstruction, bounded investigation, registry access, and citation or enforcement proposals.'),
QUOTE('The vehicle-intelligence platform determines what the evidence indicates. ServiceNow manages the enterprise records, workflows, cases, policies, assets, AI governance and operational coordination. Ugence composes with ServiceNow as an independently verifiable action-level authority and execution-assurance service — determining what may be concluded, disclosed, investigated or executed under the applicable evidence, policy, authority, purpose and scope, and verifying that the attempted action, executed action and observed effect remained within that authorization.'),
NOTE('Every Ugence–ServiceNow exchange in this document is a ' + PROP + ' — no Ugence ServiceNow connector currently ships. Nothing here implies a deployed customer integration, a certified ServiceNow Store application, a production connector, a completed joint product, or ServiceNow endorsement. The case study is illustrative and technically realistic, not a claimed customer deployment.', kind='warn', title='Integration status (applies throughout)'),
NOTE('This edition does not replace the vendor-neutral v2.0 brief, which remains the source of record for Ugence architecture, module behavior, maturity and responsibility boundaries. Where the two differ, v2.0 governs the Ugence side; this edition adds only the proposed ServiceNow composition.', kind='note', title='Relationship to the v2.0 brief'),
H2('1.1 Partnership framing (composition, not replacement)'),
P('This document is written as a partnership composition. It does ',b('not'),' state or imply that ServiceNow lacks governance, cannot enforce actions, only inventories AI, or must be replaced; and it does not describe Ugence as sitting “above” ServiceNow. ServiceNow is the enterprise platform and business system of record; Ugence contributes a narrow, independently verifiable, action-specific authority-and-assurance service that binds to the exact purpose, payload, target and case.'),
H2('1.2 ServiceNow research method, date and confidence'),
P('ServiceNow capabilities were researched on ',b('15 August 2026'),' against official ServiceNow-owned sources only, in the priority order: current product documentation (docs.servicenow.com / servicenow.com/docs), current release notes, ServiceNow Newsroom, ServiceNow Community, and product pages only where documentation did not cover a capability. Third-party summaries were not used for product behavior.'),
NOTE('Every ServiceNow capability described here is attributed to a specific official ServiceNow source in Section 21 (with the complete URL, source title, target release where applicable, and access date). Any capability, SKU, table, API, licensing or availability specific that is release-, instance- or contract-dependent is labelled “DISCOVERY QUESTION — CONFIRM WITH SERVICENOW” and consolidated in Section 20; each cited page should be re-opened and pinned to the customer’s target release before customer use. No assumption is made that any product is licensed or installed in a prospective customer’s instance.', kind='warn', title='Verification and discovery'),
H2('1.3 Maturity labels'),
P('Ugence capabilities carry the same conservative maturity labels as the v2.0 brief: ',b('IMPLEMENTED + CI'),' (merged to the default branch with its own tests in CI), ',b('IMPLEMENTED'),' (merged, tested, but no dedicated CI or not production-validated), ',b('REFERENCE'),', ',b('DESIGN-ONLY'),' and ',b('FUTURE'),'. These describe engineering status only — never production deployment, legal sufficiency, or formal proof. ServiceNow product availability is described only as ServiceNow’s official sources state it, with licensing left to discovery.'),
)

# ==================== 2. EXECUTIVE SUMMARY ====================
add(
H1('2. Executive summary','sec2'),
P('A city-scale vehicle-intelligence system can detect violations, read plates, correlate cameras and reconstruct a vehicle’s journey. Turning those technical findings into lawful, controlled, auditable government action requires three things working together: a platform that sees, an enterprise system that manages the case and the policy, and an independent authority that decides — per exact action — what may proceed and proves the effect stayed within that authorization.'),
BUL(
 [b('The vehicle platform '),'determines what the evidence indicates (perception, re-identification, trajectory). Raw video and high-volume sensor data stay in that authorized platform.'],
 [b('ServiceNow '),'is the business system of record and coordination layer: the investigative case (Public Sector Digital Services / Investigative Case Management), purpose and scope, human approvals, the policy and control library (Integrated Risk Management), the AI-governance record (AI Control Tower), asset context (CMDB / optional OT Management), workflow orchestration (Flow Designer / AI Action Fabric / IntegrationHub), and analytics.'],
 [b('Ugence '),'composes as an independently verifiable action-level authority and execution-assurance service: it admits trusted evidence, binds a governed decision, confirms model eligibility, mints one signed authorization, authorizes the exact action, checks live safety, and reconciles the observed effect — writing every artifact back to the ServiceNow case.'],
),
P('The result is a clean separation of duties in which no system both proposes and authorizes a consequential action, ServiceNow remains the system of record, and Ugence provides an independent, action-specific proof that binds authority to the exact purpose, payload, target and case.'),
DIAG('layman','Figure 1. Responsibility at a glance across the five actors — vehicle/city (cyan), ServiceNow (green), Ugence (violet), external consequence systems (grey) and human authority. Every integration is PROPOSED.'),
NOTE('Recommended posture for the partnership discussion: ServiceNow-led orchestration (Pattern A), in which a ServiceNow Playbook, AI Action Fabric flow owns the business workflow and submits each consequential action to Ugence before dispatch. A Ugence Agent Runtime coordination pattern (Pattern B) is available for bounded agentic investigation. The two are never blurred (Section 11).', kind='note', title='Recommended posture'),
)

# ==================== 3. THE FIVE-ACTOR COMPOSITION ====================
add(
H1('3. The five-actor composition','sec3'),
P('The architecture separates five actors. The colour bands used in every diagram in this document are: ',b('vehicle/city'),' systems (cyan), ',b('ServiceNow'),' (green), ',b('Ugence'),' (violet/blue/teal), ',b('external consequence'),' systems (grey), and ',b('human authority'),' (amber).'),
TABLE('Table 1. The five actors and their role.',
 ['Actor','Role in the composition'],
 [['Vehicle-intelligence / city platform','Determines what the evidence indicates; retains raw video and sensor data; emits provenanced evidence references.'],
  ['ServiceNow','Business system of record and coordination: case, purpose/scope, approvals, policy & control library, AI-governance record, asset context, workflow orchestration, analytics.'],
  ['Ugence','Independent action-level authority and execution assurance: evidence admission, governed decision, model eligibility, signed authority, exact-action authorization, live clearance, effect verification.'],
  ['External consequence systems','Carry out the authorized effect (traffic enforcement, registry, police, notification, citation).'],
  ['Human authority','Approves, reviews and hears appeals; never bypassed where policy requires it.']],
 widths=[0.28,0.72]),
P('The governing invariant is unchanged from the vendor-neutral brief: the operational intelligence system proposes; it does not self-assign the authority to execute. ServiceNow coordinates the business process and holds the records; Ugence independently authorizes the exact action and verifies the effect.'),
)

# ==================== 4. SERVICENOW PRODUCT MAP ====================
add(
H1('4. ServiceNow product map','sec4'),
P('The products below are mapped only where they are genuinely relevant to this use case, and grouped by role. Not every product belongs in the primary pipeline. Availability and licensing are matters for discovery (Section 20); product behavior is cited from official ServiceNow sources (Section 21).'),
DIAG('snowmap','Figure 2. ServiceNow product architecture, grouped by role. The AI-agent system of action is “ServiceNow AI Action Fabric” (some official materials shorten it to “Action Fabric”); Workflow Data Fabric / Zero Copy Connectors and IntegrationHub / Stream Connect / REST are distinct mechanisms.'),
TABLE('Table 2. ServiceNow product map by role.',
 ['Group','Products','Role in this use case'],
 [['Core pipeline','Workflow Data Fabric / Zero Copy Connectors (reference); IntegrationHub / Stream Connect / REST (ingest & orchestrate); PSDS case management / Investigative Case Management where licensed and available; Workflow Studio / Flow Designer; ServiceNow AI Action Fabric','Reference or ingest evidence, assemble the case and context, dispatch authorized actions.'],
  ['Supporting governance','AI Control Tower; Integrated Risk Management; Policy & Compliance Management; CMDB; Platform / Performance Analytics','Systems of record for AI governance, policy/controls, assets and measurement.'],
  ['Exception & escalation','Security Incident Response; Security Case Management','Handle credential-abuse / tampering / unauthorized-access conditions.'],
  ['Optional operational','Operational Technology Management; Field Service Management; Government Service Portal','Asset health & field remediation; constituent self-service — engaged only when relevant.'],
  ['Discovery','(see Section 20)','SKU, table, API, licensing and availability confirmations required before customer use.']],
 widths=[0.2,0.42,0.38]),
NOTE('Naming: this document uses “ServiceNow AI Action Fabric,” the name used in current official ServiceNow documentation; some official materials shorten it to “Action Fabric.” It exposes ServiceNow’s governed system of action to AI agents through the generally available MCP Server, managed via the MCP Server Console, with actions governed by AI Control Tower. Confirm the exact current name and spelling on docs.servicenow.com for the target release.', kind='note', title='On ServiceNow AI Action Fabric'),
)

# ==================== 5. PRIMARY INTEGRATED PIPELINE ====================
add(
H1('5. The primary ServiceNow-integrated pipeline','sec5'),
P('The primary pipeline threads city intelligence, ServiceNow context assembly, Ugence governance and external execution, with assurance written back to the ServiceNow case. It is presented in two phases for portrait reading: authorization and clearance (Phase 1), then dispatch, execution and assurance (Phase 2).'),
H2('5.1 Phase 1 — evidence, context and authorization'),
DIAG('seq_auth','Figure 3a. Phase 1: ServiceNow assembles the case and context; Ugence independently admits evidence, binds a decision, confirms model eligibility, mints the one signed authority, authorizes the exact action and checks live safety. Fail-closed dispositions return an auditable reason to the ServiceNow case.'),
H2('5.2 Phase 2 — dispatch, execution and assurance'),
DIAG('seq_exec','Figure 3b. Phase 2: only an authorized, cleared action is dispatched; the external effect returns for assurance (RA-8) and the complete lineage is written back to the ServiceNow case.'),
P('At each governance step, a DENY, INDETERMINATE, HOLD, BLOCK or ESCALATE outcome returns a machine-readable reason to the originating ServiceNow case rather than proceeding. Only the signed Risk Authority envelope is machine authority; no ServiceNow record, policy result, model status or receipt independently grants execution.'),
)

# ==================== 6. DATA-MINIMIZING ARCHITECTURE ====================
add(
H1('6. Data-minimizing architecture','sec6'),
P('The default design keeps raw surveillance data out of ServiceNow. Raw video and high-volume sensor data remain in the authorized city or vehicle-intelligence evidence platform. ServiceNow receives case-relevant metadata, secure references, provenance identifiers, digests, timestamps, confidence, evidence class and retrieval authorization — not the raw imagery. Two ServiceNow mechanisms are distinct and should not be conflated: ',b('Workflow Data Fabric / Zero Copy Connectors'),' can, where supported, provide real-time access to external data without copying it into the platform; while ',b('IntegrationHub, Stream Connect, REST or custom APIs'),' handle event ingestion and action orchestration. Not every IntegrationHub exchange is zero-copy: whether a given exchange references data in place or ingests a copy depends on the connector and pattern chosen.'),
TABLE('Table 3. What crosses each boundary by default.',
 ['Boundary','Crosses by default','Stays put'],
 [['City platform → ServiceNow','Case-relevant metadata, secure references, provenance IDs, content digests, timestamps, confidence, evidence class, retrieval authorization','Raw video and high-volume sensor data (retained in the city evidence platform)'],
  ['ServiceNow → Ugence','The assembled case context and evidence references (a PROPOSED governance request)','ServiceNow record ownership; Ugence emits separate governance artifacts and does not rewrite the case'],
  ['Ugence → external system','Only an authorized, cleared exact action','Any unauthorized or uncleared action']],
 widths=[0.24,0.44,0.32]),
NOTE('ServiceNow Workflow Data Fabric’s Zero Copy Connectors are documented to access external data in place and in real time “without ever having to move the data,” retrieving exactly what is needed. This supports a reference/virtualize model for supported connectors rather than bulk-copying raw evidence into ServiceNow. It is connector-specific: whether a given source is truly zero-copy (left at rest in the external system), and the exact credit / entitlement model, are discovery questions (Section 20). IntegrationHub / Stream Connect / REST exchanges are a separate mechanism for ingestion and orchestration and are not, in general, zero-copy. Source: ServiceNow Workflow Data Fabric documentation (Section 21).', kind='note', title='Zero-copy is connector-specific'),
BUL(
 [b('ServiceNow does not become the computer-vision inference engine. '),'Perception and re-identification remain in the city platform.'],
 [b('Ugence does not become the long-term case-management system. '),'The case of record remains in ServiceNow; Ugence reads or references evidence and emits separate governance artifacts.'],
 [b('Ugence does not silently rewrite the original evidence. '),'It preserves provenance and epistemic status and adds governance records alongside.'],
),
P(b('Alternative pattern (requires review). '),'If a deployment must stage evidence references or derived metadata inside ServiceNow (for example, to support offline case work), that is a distinct storage pattern requiring the customer’s architecture, privacy and retention review, and is not the default proposed here.'),
)

# ==================== 7. RESPONSIBILITY MATRIX ====================
add(
H1('7. Ugence–ServiceNow responsibility matrix','sec7'),
P('The matrix below assigns each responsibility to exactly one accountable owner. Where a responsibility is genuinely shared, it crosses a PROPOSED interface and the boundary is stated. No single binding responsibility is assigned to two systems.'),
DIAG('ownership','Figure 4. Ownership bands: vehicle/city, ServiceNow (business system of record), Ugence (independent action-level authority & assurance), external consequence systems and human authority.'),
TABLE('Table 4. Responsibility matrix. Owner = the single accountable system for that item.',
 ['Responsibility','Owner','Boundary note'],
 [['Source evidence','Vehicle/city platform','Perception, ANPR, re-ID, trajectory.'],
  ['Evidence storage','Vehicle/city platform','Raw data retained; not moved to ServiceNow by default.'],
  ['Evidence provenance','Vehicle/city platform','Provenance references travel with the evidence.'],
  ['AI model inventory','ServiceNow (AI Control Tower)','AI asset inventory / registration is ServiceNow’s system of record.'],
  ['Model eligibility for a particular action','Ugence (Model Authority)','Consumes a trusted, versioned AI-governance fact from AI Control Tower; the per-action eligibility decision is Ugence’s.'],
  ['Policy authorship','Human authority / government','Neither ServiceNow nor Ugence authors the underlying policy.'],
  ['Policy & control system of record','ServiceNow (IRM / Policy & Compliance)','Authority documents, policies, controls, exceptions, remediation.'],
  ['DecisionCase and CER','Ugence','Governed decision & authority context; not a replacement for the ServiceNow case.'],
  ['Signed machine authority','Ugence (Risk Authority)','The single signed, scoped authorization envelope.'],
  ['Exact-action authorization','Ugence (ActionGate)','AUTHORIZED / DENIED / INDETERMINATE / EXPIRED.'],
  ['Live clearance','Ugence (Action Clearance)','CLEAR / HOLD / BLOCK / ESCALATE at the edge of execution.'],
  ['Workflow orchestration','ServiceNow (Flow Designer / AI Action Fabric / IntegrationHub)','Owns the business workflow and dispatch (Pattern A).'],
  ['External-system execution','External consequence system','Carries out the authorized effect.'],
  ['Execution receipt','External system → Ugence','Receipt returned for assurance.'],
  ['Effect verification','Ugence (RA-8)','Reconciles observed effect vs authorization; never re-authorizes.'],
  ['Case lifecycle','ServiceNow (PSDS / ICM)','The investigative/enforcement case of record.'],
  ['Human review','Human authority (via ServiceNow)','ServiceNow routes review activities; humans decide.'],
  ['Appeals','Human authority (via ServiceNow)','Contested evidence / corrected identity represented in the case.'],
  ['Security incidents','ServiceNow (SIR / Security Case Mgmt)','Credential abuse / tampering handled as security work.'],
  ['Field-maintenance work','ServiceNow (FSM, + CMDB/OT)','Asset failure handled as a work order.'],
  ['KPI and ROI reporting','ServiceNow (Platform/Performance Analytics, AI Control Tower)','Operational measurement & value are ServiceNow’s; Ugence contributes evidence-backed attribution (Section 16).']],
 widths=[0.3,0.28,0.42]),
)

# ==================== 8. SERVICENOW AS SYSTEM OF RECORD ====================
add(
H1('8. ServiceNow as the business system of record','sec8'),
P('Where supported by official documentation, Public Sector Digital Services (PSDS) and its Investigative Case Management (ICM) capability — where licensed and available — serve as the primary case layer. PSDS is ServiceNow’s purpose-built platform for digital government, built on the Customer Service Management case foundation, with a government data model that supports case types and agency services. ICM is a mission-built, AI-native solution for organizing, tracking and resolving government investigations, in which the narrative, evidence, entities, tasks and team members live in a single structured record, with entities (persons, organizations, property, vehicles, locations, events, firearms) managed through a master index.'),
TABLE('Table 5. What the ServiceNow case holds or references.',
 ['Case element','Held or referenced in ServiceNow (PSDS / ICM)'],
 [['Event & evidence references','Event entity + evidence records (references, provenance IDs, digests) — raw data stays in the city platform'],
  ['Purpose & bounded scope','Case purpose, ± time window, geography, data-class scope'],
  ['Jurisdiction','Jurisdiction / tenant on the case (confirm native vs configured — discovery)'],
  ['Requested action','The proposed external action and parameters'],
  ['Human approvals','Approval activities and approver identity'],
  ['Ugence decision reference','Reference to the Ugence DecisionCase'],
  ['Signed-authorization reference','Reference to the Risk Authority envelope'],
  ['ActionGate disposition','AUTHORIZED / DENIED / INDETERMINATE / EXPIRED + reason codes'],
  ['Action Clearance result','CLEAR / HOLD / BLOCK / ESCALATE'],
  ['Execution-receipt reference','Reference to the external execution receipt'],
  ['RA-8 effect result','MATCHED / MISMATCH / PARTIAL'],
  ['Exception, appeal & escalation status','Linked IRM issue/exception, appeal and escalation state']],
 widths=[0.3,0.7]),
NOTE('The Ugence DecisionCase and Context Envelope Record (CER) remain the governed decision and authority context; they are not a replacement for, and do not duplicate, the ServiceNow case of record. The ServiceNow case references the Ugence decision; the Ugence decision references the ServiceNow case. Sources: docs.servicenow.com PSDS (Explore Public Sector Digital Services; PSDS data model); ICM (psds-explore-inv-case-management); CSM case management (accessed 2026-08-15). ICM availability ("Q1 2026, all PSDS customers") and exact entity/field schemas are discovery questions.', kind='note', title='DecisionCase vs the ServiceNow case'),
)

# ==================== 9. IRM & POLICY ====================
add(
H1('9. Integrated Risk Management and Policy & Compliance','sec9'),
P('ServiceNow Integrated Risk Management (IRM) and Policy and Compliance Management are positioned as the system of record for authority documents, policies, regulations, control objectives, controls, exceptions, compliance issues, remediation workflows and dashboards. IRM provides a unified GRC data model as a single source of truth for risk and compliance data across Risk Management, Policy and Compliance, Vendor Risk and Operational Risk.'),
P('Through a PROPOSED interface, Ugence receives ',b('approved, versioned policy and control references'),' from IRM. The Ugence Policy Workflow Compiler may compile an approved policy pack into deterministic runtime constraints — but it does not author or approve the underlying government policy, and it is tooling, not authority.'),
NOTE('Boundary: an IRM compliance status is relevant evidence — it is not automatically a signed per-action authorization. Only the Ugence Risk Authority envelope is machine authority. IRM remains the system of record for the compliance library and its lifecycle; Ugence adds an independent, action-specific authorization bound to the exact case, payload and target. Whether ServiceNow uses the exact phrase “system of record” for IRM, and the precise current module/table list, are discovery questions. Sources: servicenow.com IRM & Policy and Compliance Management product/docs pages; ds-Integrated-risk-management.pdf (accessed 2026-08-15).', kind='warn', title='Compliance status ≠ per-action authority'),
)

# ==================== 10. AI CONTROL TOWER ====================
add(
H1('10. AI Control Tower integration','sec10'),
P('ServiceNow AI Control Tower already governs and provides visibility into enterprise AI — it is documented to discover, observe, govern, secure and measure AI assets, models, agents and use cases across ServiceNow and third-party systems, including AI use-case registration, a unified AI asset inventory (agents, models, copilots, MCP servers, datasets) tied to CMDB, lifecycle status, approved-provider/model status with enforcement at the model-configuration level, embedded governance and risk context, and AI adoption / realized-value / ROI reporting.'),
P('Ugence does ',b('not'),' fill an absent ServiceNow AI-governance capability. Through a PROPOSED interface, Ugence Model Authority ',b('consumes a trusted, versioned AI-governance fact'),' from AI Control Tower — for example, whether a specific ANPR or re-identification model version is approved — and issues its own narrower, action-specific decision: whether that model may act in this exact decision class, for this exact purpose, payload, target and case.'),
NOTE('Ugence’s proposed contribution is action-specific, independently verifiable authority and execution evidence bound to the exact action — complementary to, and dependent upon, AI Control Tower’s enterprise AI-governance system of record. Whether “AI Use Case registration” is a first-class documented object (and its exact table), and current licensing (bundled vs standalone), are discovery questions. Sources: servicenow.com/products/ai-control-tower.html; docs.servicenow.com ai-control-tower ai-inventory / ai-assets; newsroom 2025 & 2026 AI Control Tower releases (accessed 2026-08-15).', kind='note', title='Complementary, not a gap-filler'),
)

# ==================== 11. EXECUTION PATTERNS ====================
add(
H1('11. Two execution patterns (kept separate)','sec11'),
P('Two execution patterns are presented and never blurred. In any scenario, exactly one pattern is in force, and ServiceNow and Ugence are never simultaneous owners of the same execution state.'),
MOD('Pattern A — ServiceNow-led orchestration (recommended)','RECOMMENDED',[
 ('Owner of the business workflow','ServiceNow Playbook, Flow Designer or AI Action Fabric.'),
 ('Governance step','Each consequential action is submitted to Ugence before dispatch.'),
 ('Ugence returns','AUTHORIZED / DENIED / INDETERMINATE (ActionGate) and CLEAR / HOLD / BLOCK / ESCALATE (Action Clearance), with artifact references.'),
 ('Dispatch','ServiceNow dispatches only an authorized and cleared action through IntegrationHub or an approved external integration.'),
 ('Assurance','The result returns to Ugence for assurance, then to the ServiceNow case.'),
]),
MOD('Pattern B — Ugence Agent Runtime coordination','FOR BOUNDED AGENTIC WORK',[
 ('Owner of coordination','Ugence Agent Runtime coordinates a bounded agentic investigation or provider attempt.'),
 ('Execution adapter','It invokes a PROPOSED ServiceNow execution adapter only after authorization and clearance.'),
 ('Receipt','The execution result returns to Agent Runtime, which emits the execution receipt to RA-8.'),
 ('Assurance','The final assurance verdict is written back to the ServiceNow case.'),
]),
P('For every scenario in this document, the pattern in force is stated. The red-light citation (Section 12) uses Pattern A. The bounded trajectory investigation (Section 13) uses Pattern A (ServiceNow-coordinated), with the PSDS case as system of record.'),
)

# ==================== 12. RED-LIGHT CITATION WALKTHROUGH ====================
add(
H1('12. Red-light citation walkthrough (Pattern A)','sec12'),
P('This rewrites the v2.0 red-light citation using the ServiceNow-integrated pipeline, in Pattern A (ServiceNow-led dispatch).'),
DIAG('citation','Figure 5. The successful red-light citation path: city evidence → ServiceNow case + context → Ugence governance → ServiceNow dispatch → external execution → RA-8 assurance → PSDS case updated with full lineage.'),
NUM(
 'The vehicle platform detects the Junction 44 red-light event; raw imagery is retained in the city platform.',
 'Workflow Data Fabric / Zero Copy Connectors reference the evidence in place where supported (or IntegrationHub / Stream Connect / REST ingest it); PSDS case management / Investigative Case Management creates or updates the case (purpose = enforcement, bounded scope, jurisdiction), where licensed and available.',
 'ServiceNow assembles context: IRM policy and control references, AI Control Tower ANPR-model governance status, CMDB (or optional OT Management) camera and signal-controller context.',
 'A PROPOSED governance request goes to Ugence: RA-5 admits the evidence (integrity, freshness, schema); Decision Authority binds a DecisionCase + CER.',
 'Model Authority confirms the ANPR model version is eligible for enforcement (consuming the AI Control Tower fact); Risk Authority mints the signed authorization envelope.',
 'ActionGate authorizes the exact ISSUE_TRAFFIC_CITATION action (AUTHORIZED); Action Clearance returns CLEAR.',
 'ServiceNow dispatches the authorized action to the external traffic-enforcement system (Flow Designer / AI Action Fabric / IntegrationHub).',
 'The external system returns an execution receipt; RA-8 reconciles the observed effect.',
 'PSDS updates the case and preserves the complete evidence → decision → authority → action → effect lineage.',
),
H2('12.1 HOLD / DENY / INDETERMINATE path'),
DIAG('failure','Figure 6. The failure / uncertainty path: any governance step can return a non-authorizing disposition with reason codes; the auditable reason is written back to the PSDS case, which routes human review. Uncertain identity is preserved, never converted to fact.'),
P('For example, with plate confidence below the binding threshold, ActionGate returns a non-authorizing disposition; no citation, disclosure or identity assertion occurs. The PSDS case records the reason codes and opens a human-review activity or a request for further admissible evidence.'),
)

# ==================== 13. SCENARIO A — INVESTIGATION ====================
add(
H1('13. Scenario — bounded trajectory investigation','sec13'),
P('PSDS case management / Investigative Case Management (where licensed and available) owns the investigation case. A ServiceNow Agentic Playbook or AI Action Fabric flow coordinates investigation activities, while Ugence independently authorizes each consequential expansion. This scenario uses Pattern A (ServiceNow-coordinated): the PSDS case is the coordinating system of record and Agent Runtime is not the execution owner here.'),
DIAG('investigation','Figure 7. Bounded trajectory investigation: each request to widen time, geography, identity or data class becomes a separately governed action; results and escalation reasons return to the investigative case.'),
BUL(
 'The PSDS case establishes a bounded purpose, ± time window and route-connected geography before any broad camera search.',
 'Each proposed investigation step (another camera search, a wider window, a new zone, registry resolution, disclosure) is submitted to Ugence as a discrete governed action.',
 'Ugence checks it against the DecisionCase scope; a wider window, new geography, identity resolution or new data class each require a NEW governed decision (DENY / ESCALATE otherwise).',
 'Results, and any escalation reasons, return to the investigative case; the investigator sees direct observations and inferred transitions kept distinct.',
),
NOTE('Technical ability to run a query is never authority to run it. “Search every camera in the city for seven days” can be technically feasible and still return DENY because the case authorizes only a bounded, route-connected search. Illustrative example.', kind='note', title='Scope is authority, not capability'),
)

# ==================== 14. SCENARIO B — UNCERTAIN IDENTITY ====================
add(
H1('14. Scenario — uncertain identity','sec14'),
P('When the evidence remains ambiguous, Ugence does not turn confidence into identity fact.'),
BUL(
 'Plate and re-identification confidence are below the policy binding threshold (for example, plate 82% against a 97% threshold with no approved human corroboration).',
 'ActionGate returns a non-authorizing disposition (INDETERMINATE / HOLD) with reason codes.',
 'PSDS creates a human-review activity or requests further admissible evidence; the ambiguity is preserved on the case, not resolved by fiat.',
 'No citation or identity disclosure occurs without sufficient evidence and appropriate authority.',
),
P('This is the same discipline as the vendor-neutral brief, expressed through the ServiceNow case: the auditable reason lands on the PSDS case, and human authority decides the next step.'),
)

# ==================== 15. OPTIONAL OPERATIONAL BRANCHES ====================
add(
H1('15. Optional operational branches','sec15'),
P('Two optional branches sit outside the ordinary citation pipeline. They engage only on genuine asset-failure or security conditions — an ordinary traffic citation is neither a field-service work order nor a security incident.'),
DIAG('optional','Figure 8. Optional operational extensions: asset failure routes through CMDB / OT Management → Field Service Management; suspected credential abuse routes through Security Incident Response / Security Case Management, which can trigger a Ugence authority revocation or hold.'),
BUL(
 [b('Camera or signal-controller malfunction. '),'CMDB (or optional Operational Technology Management) records the asset-health condition; Field Service Management raises a work order and dispatches a technician; the asset-health result returns to the case. (Whether cameras and signal controllers are out-of-box OT device classes is a discovery question.)'],
 [b('Suspected credential abuse, tampering or unauthorized surveillance access. '),'Security Incident Response / Security Case Management runs a security investigation; where appropriate, Ugence RA-6 issues an authority revocation or hold signal, restricting authority downstream.'],
),
)

# ==================== 16. ANALYTICS & GOVERNED VALUE ====================
add(
H1('16. Analytics and governed value','sec16'),
P('ServiceNow Platform Analytics, Performance Analytics and AI Control Tower already support operational measurement, AI adoption, realized value and ROI reporting. This document does not claim ServiceNow lacks ROI measurement.'),
P('Ugence Governed Value remains labelled by its actual maturity — ',b('EXPERIMENTAL / REPORTED / UNVERIFIED'),' — with no authority binding and no continuous integration. It is not an authorization stage. The proposed future contribution is ',b('evidence-backed outcome attribution'),' that connects approved objectives, a workflow baseline, the governed decision and authorization, execution receipts, observed outcomes, model and infrastructure costs, attribution rules, and preserved risk / compliance / quality / service constraints — reusing the governance evidence the pipeline already emits, adding attribution rather than a new gate.'),
NOTE('Governed Value is an experimental reporting kernel (REPORTED / UNVERIFIED). It does not attest outcomes, does not grant authority, and must not be read as an audited financial result. Operational KPI and ROI reporting are ServiceNow’s (Platform/Performance Analytics, AI Control Tower).', kind='note', title='Governed Value maturity'),
)

# ==================== 17. INTEGRATION CATALOGUE ====================
add(
H1('17. Interface-level integration catalogue','sec17'),
P('Each proposed exchange is described at the safe-to-share interface level — no source code, proprietary algorithms, complete schemas, key handling, internal thresholds or credentials. Every row is a ' + PROP + '.'),
TABLE('Table 6. Proposed ServiceNow ↔ Ugence integration points (interface level).',
 ['#','ServiceNow trigger / record','Input referenced','Ugence module','Artifact emitted','ServiceNow record updated','On failure / uncertainty'],
 [['I-1','PSDS case created / action proposed','Evidence refs, purpose, scope, approvals','RA-5 → Decision Authority','AdmittedEvidence; DecisionCase + CER','Case: decision reference','Reason codes → case; human-review activity'],
  ['I-2','AI Control Tower model-status query','Model id/version, approval status','Model Authority','ModelAuthorizationDecision','Case: model-authorization ref','DENY/HOLD → case'],
  ['I-3','IRM policy/control reference','Approved, versioned policy pack refs','Policy Workflow Compiler → Risk Authority','Compiled constraints; signed envelope','Case: authorization ref','No authority issued → case'],
  ['I-4','Exact-action submission (Pattern A)','Action type, target, parameters, digest','ActionGate','ActionGovernanceResult','Case: disposition + reason codes','DENIED/INDETERMINATE → case'],
  ['I-5','Pre-dispatch clearance','Authorized action + live signals','Action Clearance','ClearanceResult (CLEAR/HOLD/BLOCK/ESCALATE)','Case: clearance result','HOLD/BLOCK/ESCALATE → case'],
  ['I-6','Dispatch result (receipt)','Execution receipt / external result','RA-8 (+ Agent Runtime, Pattern B)','EffectAssuranceAssessment','Case: effect result; IRM issue if mismatch','MISMATCH/PARTIAL → IRM issue + case'],
  ['I-7','Reassessment signal','RA-7/RA-8 signals','RA-6','Authority lifecycle mutation','Case: authority state; SIR link if security','Revoke/hold → case']],
 widths=[0.05,0.19,0.16,0.14,0.16,0.16,0.14]),
TABLE('Table 7. Cross-cutting expectations for every integration point.',
 ['Property','Expectation'],
 [['Success behavior','Authorized + cleared action dispatched by ServiceNow; artifacts referenced on the case.'],
  ['Failure / uncertainty behavior','Fail closed; machine-readable reason returned to the originating ServiceNow case; no default-allow.'],
  ['Idempotency / replay','Requests carry an idempotency key; clearances are digest/expiry-bound and rejected on replay or parameter drift.'],
  ['Audit reference','Every artifact is referenced from the ServiceNow case, forming an evidence → authority → action → effect chain.'],
  ['Integration status',PROP + ' — no connector ships; interface shapes are illustrative and subject to discovery.']],
 widths=[0.26,0.74]),
)

# ==================== 18. ASSURANCE & WRITE-BACK ====================
add(
H1('18. Runtime, execution and effect assurance with write-back','sec18'),
P('Governance does not end at authorization. Authorization, attempt, execution and effect are distinct records, reconciled and written back to the ServiceNow case.'),
DIAG('assurance','Figure 9. Authorization vs attempt vs execution vs effect, with RA-7 (in-flight) and RA-8 (post-effect) reassessment signals feeding RA-6, and every verdict written back to the ServiceNow case.'),
TABLE('Table 8. Four distinct records, and where each lands in ServiceNow.',
 ['Record','What it captures','Owner','Write-back'],
 [['Authorization','The signed, scoped envelope','Ugence Risk Authority','Case: authorization reference'],
  ['Attempt','What command was attempted','Ugence Agent Runtime (Pattern B) / ServiceNow (Pattern A)','Case / flow record'],
  ['Receipt','What actually executed','External system','Case: receipt reference'],
  ['Effect verification','Observed effect vs authorization','Ugence RA-8','Case: effect result; IRM issue on mismatch']],
 widths=[0.18,0.34,0.26,0.22]),
P('RA-7 and RA-8 emit neutral reassessment signals to RA-6, which may only restrict authority (revoke / epoch / expire); RA-8 never retroactively authorizes an action, and verification strength is honestly bounded by the effect source. Per the v2.0 brief, the RA-5→RA-8 packages are IMPLEMENTED and CI-verified at the library level, while end-to-end operational enforcement is PARTIAL.'),
)

# ==================== 19. PRODUCT-TO-PIPELINE MAPPING (Deliverable A) ====================
add(
H1('19. ServiceNow product-to-pipeline mapping','sec19'),
P('This table maps each pipeline stage to the ServiceNow product(s) and the Ugence module(s) involved. It is Deliverable A.'),
TABLE('Table 9. Product-to-pipeline mapping.',
 ['Pipeline stage','ServiceNow product(s)','Ugence module(s)','Status'],
 [['Reference evidence (zero-copy where supported)','Workflow Data Fabric / Zero Copy Connectors','—',PROP],
  ['Ingest events / orchestrate','IntegrationHub / Stream Connect / REST','—',PROP],
  ['Create / update the case','PSDS case management / Investigative Case Management where licensed and available (on the CSM case foundation)','—',PROP],
  ['Assemble context','PSDS; IRM / Policy & Compliance; AI Control Tower; CMDB (+ optional OT)','—',PROP],
  ['Admit trusted evidence','—','RA-5 Trusted Evidence Admission','IMPLEMENTED + CI (lib)'],
  ['Bind the decision','—','Decision Authority (DecisionCase + CER)','IMPLEMENTED + CI'],
  ['Model eligibility','AI Control Tower (fact)','Model Authority','IMPLEMENTED'],
  ['Mint the signed authority','IRM (policy refs)','Risk Authority','IMPLEMENTED + CI (issuance PARTIAL)'],
  ['Authorize the exact action','—','ActionGate','IMPLEMENTED + CI'],
  ['Live clearance','—','Action Clearance','IMPLEMENTED'],
  ['Dispatch the authorized action','Flow Designer / AI Action Fabric / IntegrationHub','(Pattern A)',PROP],
  ['Coordinate agentic steps','Agentic Playbooks / AI Action Fabric','Agent Runtime (Pattern B)','IMPLEMENTED + CI'],
  ['Execute externally','(external system via ServiceNow)','—','—'],
  ['Assure & reconcile','—','RA-7 / RA-8 / RA-6','IMPLEMENTED + CI (lib)'],
  ['Write back & report','PSDS case; IRM issue; AI Control Tower audit; Platform Analytics','Governed Value (experimental)',PROP]],
 widths=[0.24,0.3,0.28,0.18]),
)

# ==================== 20. DISCOVERY QUESTIONS (Deliverable E) ====================
add(
H1('20. Discovery questions to confirm with ServiceNow','sec20'),
P('These are the items that could not be page-verified from official documentation in this preparation environment, or that depend on the customer’s release, instance and contract. Each should be confirmed with ServiceNow (for the partnership discussion, with Praneeth). This is Deliverable E.'),
TABLE('Table 10. Discovery questions.',
 ['#','Area','Question to confirm with ServiceNow'],
 [['D-1','PSDS','Exact PSDS SKU / entitlement; which Store apps are in the base entitlement vs sold separately; does the government data model natively carry jurisdiction, approvals and external-reference fields, or are these configured?'],
  ['D-2','Investigative Case Mgmt','Confirm the “Q1 2026, all PSDS customers” availability; exact entity/table names and the event-entity schema; native modelling of jurisdiction, approvals and external-agency reference IDs; whether ICM needs a SKU beyond base PSDS.'],
  ['D-3','CSM foundation','Which CSM tier underpins PSDS/ICM, and whether CSM is bundled into PSDS entitlement or separate; base case table and fields PSDS/ICM extend.'],
  ['D-4','Workflow Data Fabric','Does zero-copy leave data fully at rest for all connector types; exact “Data Fabric credits” / entitlement/tier model for projected query volume.'],
  ['D-5','IntegrationHub','Which specific spokes the external-system integrations require (OOTB vs Store vs custom); edition/transaction entitlement for projected volume.'],
  ['D-6','Workflow Studio / Flow Designer','For the target release, does Workflow Studio fully replace the standalone Flow Designer UI; any capabilities that remain one-or-the-other.'],
  ['D-7','AI Action Fabric','Confirm the exact current product name and its spelling on docs.servicenow.com for the target release (“ServiceNow AI Action Fabric,” sometimes shortened to “Action Fabric”); GA scope for the target release; whether AI Control Tower governance is mandatory/enforced for all externally-dispatched actions or configurable; whether AI Gateway is required vs recommended for sensitive-data MCP traffic.'],
  ['D-8','AI Control Tower','Is “AI Use Case registration” a first-class documented object and its table/record name; ownership fields/roles; current licensing (bundled vs standalone) and GA status of expanded capabilities as of 2026-08-15.'],
  ['D-9','IRM / Policy & Compliance','Does ServiceNow use the phrase “system of record” for IRM; precise current module and table names (authority document, citation, control objective, control, policy exception, issue); packaging/entitlement.'],
  ['D-10','Agentic Playbooks','Exact activity name and whether they coordinate multiple agents or one embedded agent per activity; release and Now Assist / AI Agents entitlement.'],
  ['D-11','CMDB','Baseline CMDB inclusion; which advanced features (Service Graph Connectors, CSDM) need additional entitlement.'],
  ['D-12','OT Management','OOTB discovery / CI classes for cameras and traffic/rail signal controllers, or custom modelling; entitlement and dependency on Discovery / Vulnerability Response.'],
  ['D-13','Analytics','Which tier (Performance Analytics Pro/Premium vs baseline; Platform Analytics baseline) is required for the intended KPI/ROI dashboards, and license-consuming roles.'],
  ['D-14','FSM','Which FSM package/tier; is AI Schedule-and-Dispatch Optimization included or an add-on.'],
  ['D-15','SIR / Security Case Mgmt','Which SecOps SKU covers SIR; is “Security Case Management” a standalone product or the workspace/case framework; is “Physical Security Case Management” the relevant offering for camera/OT security; licensing.'],
  ['D-16','Release pinning','Pin all cited docs URLs to the customer’s target release family (current: Zurich) and re-verify against the live pages before customer use.']],
 widths=[0.06,0.16,0.78]),
)

# ==================== 21. SOURCE REGISTER (Deliverable F) ====================
add(
H1('21. Source and citation register','sec21'),
P('Official ServiceNow sources for each capability, with complete URLs, in the documented priority order (product documentation → release notes → Newsroom → product pages). Access date: ',b('15 August 2026'),'. Where a documentation URL is release-pinned, the release is named in parentheses; re-open each page and pin it to the customer’s target release (current family: Zurich) before customer use. Ugence architecture and maturity are cited from the vendor-neutral v2.0 brief and the Ugence repository. This is Deliverable F.'),
BUL(
 [b('Public Sector Digital Services — '),'“Exploring Public Sector Digital Services” (Zurich) and the PSDS data model. ',L('https://www.servicenow.com/docs/bundle/zurich-government-industry/page/product/public-sector/concept/exploring-public-sector-digital-services.html'),' · ',L('https://www.servicenow.com/docs/r/government-industry/public-sector-digital-services-data-model.html')],
 [b('Investigative Case Management — '),'“Explore Investigative Case Management,” plus store release notes. ',L('https://www.servicenow.com/docs/r/government-industry/psds-explore-inv-case-management.html'),' · ',L('https://www.servicenow.com/docs/r/store-release-notes/store-rn-public-sector-csm-investigative-case-mgmt.html')],
 [b('Customer Service Management (case) — '),'“Case management for Customer Service Management” (Zurich). ',L('https://www.servicenow.com/docs/bundle/zurich-customer-service-management/page/product/customer-service-management/concept/csm-case-management.html')],
 [b('Government Service Portal — '),'“Using the Government Service Portal in Public Sector Digital Services” (Vancouver). ',L('https://www.servicenow.com/docs/bundle/vancouver-government-industry/page/product/public-sector/concept/using-psds-government-service-portal-overview.html')],
 [b('Workflow Data Fabric / Zero Copy Connectors — '),'Managing connections (Zurich); product page. ',L('https://www.servicenow.com/docs/bundle/zurich-integrate-applications/page/administer/workflow-data-fabric/concept/managing-connections-wdf.html'),' · ',L('https://www.servicenow.com/platform/workflow-data-fabric.html')],
 [b('IntegrationHub — '),'Product page; IntegrationHub concept (Zurich). ',L('https://www.servicenow.com/products/integration-hub.html'),' · ',L('https://www.servicenow.com/docs/bundle/zurich-integrate-applications/page/administer/integrationhub/concept/integrationhub.html')],
 [b('Workflow Studio / Flow Designer — '),'Flow Designer product & architecture (Zurich); Workflow Studio release notes (Washington DC). ',L('https://www.servicenow.com/products/platform-flow-designer.html'),' · ',L('https://www.servicenow.com/docs/bundle/zurich-build-workflows/page/administer/flow-designer/concept/flow-designer-arch-overview.html'),' · ',L('https://www.servicenow.com/docs/bundle/washingtondc-release-notes/page/release-notes/now-platform-app-engine/workflow-studio-rn.html')],
 [b('ServiceNow AI Action Fabric — '),'Product page; Newsroom (2026, “opens its full system of action to every AI agent”). ',L('https://www.servicenow.com/platform/action-fabric.html'),' · ',L('https://newsroom.servicenow.com/press-releases/details/2026/ServiceNow-opens-its-full-system-of-action-to-every-AI-Agent-in-the-enterprise/default.aspx')],
 [b('AI Control Tower — '),'Product page; AI inventory docs; Newsroom (2026 expansion). ',L('https://www.servicenow.com/products/ai-control-tower.html'),' · ',L('https://www.servicenow.com/docs/r/intelligent-experiences/ai-control-tower/ai-inventory.html'),' · ',L('https://newsroom.servicenow.com/press-releases/details/2026/ServiceNow-expands-AI-Control-Tower-to-discover-observe-govern-secure-and-measure-AI-deployed-across-any-system-in-the-enterprise/default.aspx')],
 [b('Integrated Risk Management — '),'Product page. ',L('https://www.servicenow.com/products/integrated-risk-management.html')],
 [b('Policy & Compliance Management — '),'Product page; Policy and Compliance Management docs. ',L('https://www.servicenow.com/products/policy-compliance-management.html'),' · ',L('https://www.servicenow.com/docs/r/governance-risk-compliance/policy-and-compliance-management/r_PolicyComplianceMgmt.html')],
 [b('Agentic Playbooks — '),'Platform page; Agentic Playbooks docs landing. ',L('https://www.servicenow.com/platform/agentic-playbooks.html'),' · ',L('https://www.servicenow.com/docs/r/build-workflows/workflow-studio/agentic-playbooks-landing.html')],
 [b('CMDB — '),'Product page; CMDB documentation. ',L('https://www.servicenow.com/products/servicenow-platform/configuration-management-database.html'),' · ',L('https://www.servicenow.com/docs/r/servicenow-platform/configuration-management-database-cmdb/c_ITILConfigurationManagement.html')],
 [b('Platform / Performance Analytics — '),'Performance Analytics “Your KPIs” (Xanadu Now Intelligence). ',L('https://www.servicenow.com/docs/bundle/xanadu-now-intelligence/page/use/performance-analytics/concept/your-kpis.html')],
 [b('Operational Technology Management — '),'Product page; OT Management overview docs. ',L('https://www.servicenow.com/products/operational-technology-management.html'),' · ',L('https://www.servicenow.com/docs/r/operational-technology/operational-technology-overview.html')],
 [b('Field Service Management — '),'Product page; work-order management docs. ',L('https://www.servicenow.com/products/field-service-management.html'),' · ',L('https://www.servicenow.com/docs/r/field-service-management/work-order-management/t_CreateAWorkOrder.html')],
 [b('Security Incident Response — '),'Product page; SIR landing (Xanadu). ',L('https://www.servicenow.com/products/security-incident-response.html'),' · ',L('https://www.servicenow.com/docs/bundle/xanadu-security-management/page/product/security-incident-response/reference/sir-landing-page.html')],
 [b('Security Case Management — '),'Security case management documentation. ',L('https://www.servicenow.com/docs/r/security-management/case-mgmt.html')],
),
P(i('Ugence module behavior and maturity are cited from the vendor-neutral v2.0 brief and the Ugence repository default branch. Any capability, SKU, table, API, licensing or availability specific that is release-, instance- or contract-dependent is treated as a discovery question (Section 20), to be confirmed against the live page for the customer’s release before customer use.')),
)

# ==================== 22. PHASED PILOT ====================
add(
H1('22. Phased pilot','sec22'),
P('Autonomy is earned step by step; live controlled dispatch is not enabled until dry-run, exception-path and receipt checks pass. Every integration remains PROPOSED until built and confirmed with ServiceNow.'),
DIAG('roadmap','Figure 10. A phased adoption roadmap from discovery to assurance-and-value, integrated with ServiceNow.'),
TABLE('Table 12. Phase exit criteria.',
 ['Phase','Exit criterion'],
 [['0 · Discovery','Discovery questions (Section 20) resolved with ServiceNow; products, editions, data model and licensing confirmed; action inventory approved.'],
  ['1 · Shadow governance','Disposition quality validated against historical / live review, with no blocking.'],
  ['2 · Low-risk runtime gates','Selected searches / registry calls / disclosures gated before dispatch; no bypass paths; latency and fail behavior accepted.'],
  ['3 · Enforcement gate','ActionGate + Action Clearance before citation dispatch; end-to-end evidence / authority / action tests pass.'],
  ['4 · Agentic governance','Agentic Playbook / AI Action Fabric and Agent Runtime routes governed; scope-expansion and escalation adversarial tests pass.'],
  ['5 · Assurance & value','RA-8 write-back to PSDS / IRM; AI Control Tower audit; Platform Analytics KPIs; production assurance SLOs and audit KPIs sustained.']],
 widths=[0.3,0.7]),
)

# ==================== 23. APPENDIX — UGENCE MODULES & GLOSSARY ====================
add(
H1('23. Appendix — Ugence module reference and glossary','sec23'),
P('The Ugence modules referenced above are unchanged from the vendor-neutral v2.0 brief. Maturity is repository-backed (default branch).'),
TABLE('Table 13. Ugence module reference (maturity from v2.0).',
 ['Module (repository name)','Role','Maturity'],
 [['RA-5 — risk-authority-evidence-runtime','Trusted evidence admission + control assurance','IMPLEMENTED + CI (lib); integration PARTIAL'],
  ['TAP — ugence-tap-provider','Assertion / control-support evaluator RA-5 wraps','IMPLEMENTED + CI'],
  ['Decision Authority — ugence-decision-authority','DecisionCase (immutable/versioned) + CER; binding decision','IMPLEMENTED + CI'],
  ['Model Authority — ugence-model-selection','Per-action model-authorization decision','IMPLEMENTED (no dedicated CI)'],
  ['Risk Authority — ugence-risk-authority','Signed Ed25519 authorization envelope (sole machine authority)','IMPLEMENTED + CI; production issuance PARTIAL'],
  ['ActionGate — ugence-actiongate-provider','Exact-action authorization (AUTHORIZED / DENIED / INDETERMINATE / EXPIRED)','IMPLEMENTED + CI'],
  ['Action Clearance — ugence-action-clearance','Live-safety clearance (CLEAR / HOLD / BLOCK / ESCALATE)','IMPLEMENTED (no dedicated CI)'],
  ['Agent Runtime — ugence-agent-runtime','Governed execution coordination (fails closed)','IMPLEMENTED + CI'],
  ['RA-7 / RA-8 / RA-6','In-flight assurance / effect reconciliation / authority lifecycle','IMPLEMENTED + CI (lib); end-to-end PARTIAL'],
  ['Policy Workflow Compiler — ugence-policy-workflow-compiler','Compiles an approved policy pack into runtime constraints (tooling, not authority)','IMPLEMENTED + CI (offline)'],
  ['Governed Value — ugence-governed-value','Reported net governed value / ROI (experimental)','IMPLEMENTED (experimental; reported-only)']],
 widths=[0.34,0.42,0.24]),
H2('23.1 Glossary'),
TABLE('Table 14. Glossary.',
 ['Term','Definition'],
 [['PSDS','Public Sector Digital Services — ServiceNow’s digital-government platform (case foundation from CSM).'],
  ['ICM','Investigative Case Management — AI-native government investigation case capability within PSDS.'],
  ['IRM','Integrated Risk Management — ServiceNow’s GRC suite; system of record for policy/controls.'],
  ['AI Control Tower','ServiceNow’s command center to discover/observe/govern/secure/measure enterprise AI.'],
  ['ServiceNow AI Action Fabric','ServiceNow’s system of action exposed to AI agents via the MCP Server, governed by AI Control Tower. Some official materials shorten it to “Action Fabric”.'],
  ['IntegrationHub','ServiceNow integration framework; spokes (grouped actions/subflows) to external systems.'],
  ['Workflow Data Fabric','ServiceNow unified data foundation; Zero Copy Connectors reference external data without moving it.'],
  ['CER','Context Envelope Record — the Ugence governance context record owned by Decision Authority.'],
  ['DecisionCase','The Ugence governed decision & authority container (not the ServiceNow case of record).'],
  ['Pattern A / B','ServiceNow-led dispatch / Ugence Agent Runtime coordination — never simultaneous owners of execution.'],
  ['PROPOSED SERVICENOW INTEGRATION','No Ugence ServiceNow connector ships; the integration is illustrative and subject to discovery.']],
 widths=[0.24,0.76]),
P(i('End of document. This is a conceptual, PROPOSED integration architecture and illustrative case study, grounded in the current Ugence repository and official ServiceNow sources identified on 2026-08-15 (page-verify before customer use). It is not legal advice, not a claimed deployment, and not ServiceNow-endorsed.')),
)
