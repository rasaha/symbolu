# Content model for the portrait briefing. Blocks consumed by both HTML and DOCX renderers.
# Sources of record: catalog v1.2 (UGENCE_SERVICENOW_PRODUCT_ANCHORED_USE_CASES.md) and
# UGENCE_SERVICENOW_USE_CASE_WALKTHROUGHS.md. Landscape deck used as narrative reference only.

def B(*blocks): return list(blocks)
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
def MOD(name,maturity,rows): return {'t':'modcard','name':name,'maturity':maturity,'rows':rows}

PROP='PROPOSED'

CONTENT = []
def add(*blocks):
    for x in blocks: CONTENT.append(x)

# ============================ 1. EXECUTIVE SUMMARY ============================
add(
H1('1. Executive summary','sec1'),
QUOTE('When an AI agent takes a consequential action, how can the enterprise prove that this exact action was authorized, remained safe at execution time, and produced only the intended effect?'),
P('Enterprises are moving from AI that ',i('recommends'),' a decision to AI that ',i('makes and executes'),' it. That shift is valuable, but it changes the governance question. A general, up-front approval establishes that an action of a certain kind is permitted; it does not, by itself, prove that ',b('this exact action, on this exact target, was still safe and correct at the moment it ran'),' — or that the effect it produced matched what was authorized.'),
P('Three practical risks recur whenever an AI agent acts on the enterprise:'),
NUM(
 [b('The AI acts on the wrong target. '),'A valid-looking action is pointed at the wrong system, resource, or record.'],
 [b('Conditions change between approval and execution. '),'A change freeze begins, a dependency degrades, or a cost limit shifts in the interval between approval and action.'],
 [b('The recorded action and the actual operational effect do not match. '),'What the record says was authorized is not what actually happened in the environment.'],
),
H2('What ServiceNow already provides'),
P('ServiceNow governs the enterprise AI estate and an increasingly capable agentic runtime. AI Control Tower discovers, governs, secures and measures AI; Action Fabric exposes a governed system of action to external agents; Agent Deviation Detection flags when an agent strays from its role; AI Risk & Compliance maps controls across frameworks; Change Management and the CMDB hold approvals, windows and business context; and — with NVIDIA OpenShell — central policy is enforced at runtime on file, command and network access. AI Control Tower also measures AI adoption, business impact, realized value and ROI. This briefing treats those capabilities as real strengths and builds on them.'),
H2('What Ugence proposes to contribute'),
P('Ugence proposes a narrow, complementary layer: an ',b('independent, verifiable authority-and-evidence artifact per business action'),'. For a consequential AI action it establishes, per request: whether a properly delegated authority approved it; that the action is bound to the exact target and payload; that required evidence is trusted and current; that the live environment is safe at execution time; and — afterward — that the observed effect matched the authorization. Every ServiceNow integration described here is ',b(PROP),'; no ServiceNow connector ships today.'),
H2('Why the relationship is complementary'),
P('ServiceNow remains the system of record, the system of action and the platform that enforces execution. Ugence contributes an independent authority-decision and evidence layer that ',b('composes with'),' those capabilities. Ugence does not replace ServiceNow, does not sit above it, and does not claim unique cross-platform runtime enforcement — OpenShell already enforces at the kernel level across form factors. Where a Ugence differentiation is not established in ServiceNow documentation, this briefing states it as a ',i('discovery question'),' for ServiceNow architects, never as a claim that ServiceNow lacks a capability.'),
H2('Recommended bounded pilot'),
P('The recommended first pilot is ',b('UC-5, autonomous change execution'),' — a controlled scaling workflow the customer already runs, where exact-target authorization, an independent live-safety clearance, and execution-to-effect reconciliation land cleanly on a small, reversible footprint. A 30–60-day bounded technical pilot is proposed in Section 11.'),
NOTE('All ServiceNow integrations described in this briefing are proposed. No ServiceNow connector currently ships. The scenarios are illustrative enterprise workflows, not claimed Ugence customer deployments.', kind='warn', title='Standing disclaimer'),
PB(),
)

# ============================ 2. WHAT SERVICENOW PROVIDES ============================
add(
H1('2. What ServiceNow already provides','sec2'),
P('Positioning the proposal accurately begins with acknowledging ServiceNow’s strengths. The capabilities below are current ServiceNow functionality, cited from ServiceNow-owned sources (see the source hierarchy in the appendices).'),
TABLE('Table 1. ServiceNow capabilities acknowledged in this briefing.',
 ['ServiceNow capability','What it does'],
 [['AI Control Tower','Discovers, governs, secures, observes and measures AI across the enterprise, including real-time enforcement.'],
  ['Action Fabric','A governed system of action over MCP/A2A; every action is identity-verified, permission-scoped and auditable.'],
  ['Agent Deviation Detection','Flags at runtime when an agent strays from its authorized role.'],
  ['AI Risk & Compliance','Multi-framework control mapping (EU AI Act, NIST AI RMF and others) and enforcement.'],
  ['Change Management & CMDB','Approvals, change / blackout windows, conflict detection and business context.'],
  ['Enterprise approvals & workflow','Platform-wide approval and workflow controls.'],
  ['NVIDIA OpenShell','Central AI Control Tower policy enforced at runtime on file, command and network access.'],
  ['Adoption, impact & ROI','Measures AI adoption, business impact, realized value and ROI.']],
 widths=[0.32,0.68]),
NOTE('This briefing does not state or imply that ServiceNow lacks governance, cannot enforce, or only inventories AI; that Ugence replaces ServiceNow or sits above it; or that Ugence uniquely provides cross-platform runtime enforcement. The relationship is complementary throughout.', kind='note', title='Framing discipline'),
PB(),
)

# ============================ 3. RESPONSIBILITY BOUNDARY ============================
add(
H1('3. Proposed ServiceNow–Ugence responsibility boundary','sec3'),
P('The division of responsibility is consistent across every scenario in this briefing and is the core of the partnership story. ServiceNow is the system of record, workflow and action platform; Ugence contributes an independent, signed authority-and-evidence layer that composes with it.'),
TABLE('Table 2. Proposed responsibility boundary. The integration is PROPOSED; no ServiceNow connector currently ships.',
 ['ServiceNow remains responsible for','Ugence proposes to contribute'],
 [['Enterprise system of record','Binding decision artifacts'],
  ['Workflow and case management','Trusted-evidence linkage'],
  ['CMDB and business context','Exact-action and target authorization'],
  ['Platform approvals and governance','Time- and scope-bounded authority'],
  ['Action Fabric','Independent operational clearance'],
  ['ServiceNow execution pathways','Governed execution coordination'],
  ['AI Control Tower monitoring and controls','Execution receipts'],
  ['Business-value and ROI reporting','Observed-effect reconciliation'],
  ['','Authority lifecycle and reassessment'],
  ['','Cross-stage evidence lineage'],
  ['','Developing governed-value attribution']],
 widths=[0.5,0.5]),
P('Neither side replaces the other. Ugence composes with ServiceNow’s workflow, system of action and platform enforcement. The integration is marked ',b(PROP),' throughout.'),
PB(),
)

# ============================ 4. DATA JOURNEY ============================
add(
H1('4. Understanding the data journey','sec4'),
P('The single most important idea in this briefing is that ',b('not every Ugence module modifies the original ServiceNow business record'),'. Most modules read or reference business context and emit a separate governance artifact alongside it. Four kinds of data stay distinct:'),
TABLE('Table 3. Four kinds of data, kept distinct throughout.',
 ['Kind of data','Examples','Owner'],
 [['1 · Original business data','Change, incident, CI, employee, entitlement, control evidence, amount, target system, requested action','ServiceNow (system of record)'],
  ['2 · Derived governance artifacts','Decision record; model / action / risk authorization; clearance verdict; execution receipt; assurance result; revocation / reassessment signal','Ugence (each a separate artifact)'],
  ['3 · Observed operational data','Infrastructure state, service health, blackout window, dependency condition, account status, execution result, post-action effect','ServiceNow + operational telemetry'],
  ['4 · ServiceNow system-of-record entries','The change / incident / request record and its statuses; receives references, statuses and summarized outcomes','ServiceNow (via the proposed integration)']],
 widths=[0.24,0.5,0.26]),
QUOTE('Each Ugence module reads or references the necessary business context and emits a separate governance artifact. It does not silently rewrite the originating ServiceNow record.'),
H2('Layman workflow'),
P('The same journey, in plain language. Under each stage is one short example of the information added.'),
DIAG('layman_canonical','Figure 1. The end-to-end data journey in plain language (illustrative).'),
H2('Technical canonical workflow'),
P('The canonical technical spine. Each layer speaks a distinct decision verb, and authority never leaks across layers. Only the modules a given scenario actually uses are shown in that scenario’s diagram; the full set is introduced in Section 5.'),
DIAG('tech_canonical','Figure 2. The canonical technical workflow, with the fail-closed stop path (illustrative).'),
PB(),
)

# ============================ 5. MODULE RESPONSIBILITIES ============================
add(
H1('5. Ugence module responsibilities','sec5'),
P('Each module is described at the interface level — what it receives, what it decides, the separate artifact it emits, and what it explicitly does not do. This briefing describes the guarantee each module provides, not the proprietary mechanism that produces it: no source code, complete schemas, algorithms, policy-compilation internals, canonicalization procedures, key handling or cryptographic implementation details are disclosed.'),
NOTE('Verified responsibilities held throughout: the context-envelope record (CER) belongs to Decision Authority; Agent Runtime owns canonical execution state and coordinates governed execution (it is never labelled “Agent Runtime (CER)”); Agent Runtime invokes domain executors / providers; Cloud Scaling Operations is a domain executor, not an authorization gate; RA-8 compares authorized intent, execution evidence and observed effect, and never retroactively authorizes an action.', kind='note', title='Architecture invariants'),
NOTE('Each module card carries a package-maturity label defined in Appendix A. These labels describe the engineering status of the Ugence package only. REFERENCE-GRADE means a reference implementation exists and is offline-verifiable but is not production-validated; IMPLEMENTED means code exists and is verified at interface level. Neither implies production deployment validation, and neither implies a shipping ServiceNow integration — every ServiceNow integration in this briefing is separately marked PROPOSED, and no connector currently ships. Package availability, production validation and ServiceNow integration are three distinct dimensions and are never conflated.', kind='warn', title='How to read the maturity labels'),
H2('5.1 Policy, evidence and decision'),
MOD('Policy Workflow Compiler','REFERENCE-GRADE',[
 ('Question it answers','How is approved policy turned into deterministic, checkable constraints?'),
 ('Receives / references','An approved, structured policy pack (compile-time, offline).'),
 ('Checks / decides','Compiles policy into deterministic constraints.'),
 ('Emits','A digest-addressed governed-workflow artifact.'),
 ('Does not do','Make a binding decision; authorize, clear or run anything.')]),
MOD('RA-5 Trusted Evidence Admission','REFERENCE-GRADE',[
 ('Question it answers','Is each required control satisfied by trusted, re-checked evidence?'),
 ('Receives / references','Control-evidence references.'),
 ('Checks / decides','Whether evidence is trusted and current — a caller-asserted “pass” is inert.'),
 ('Emits','An evidence-derived, re-checked control result.'),
 ('Does not do','Add a second authority signature.')]),
MOD('Decision Authority','REFERENCE-GRADE',[
 ('Question it answers','Did a properly delegated authority — not the AI — approve this class of decision?'),
 ('Receives / references','Proposed action, delegated authority, constraints; owns the context-envelope record (CER).'),
 ('Checks / decides','Whether a binding decision exists within permitted scope, by a non-AI principal.'),
 ('Emits','A separate, immutable decision record; owns execution and reconciliation records.'),
 ('Does not do','Execute; inspect live conditions; let the AI self-authorize.')]),
MOD('Risk Authority','REFERENCE-GRADE',[
 ('Question it answers','How is an approved risk decision turned into a verifiable, bounded permission?'),
 ('Receives / references','An allow-family risk decision.'),
 ('Checks / decides','Whether to mint authority; scope never exceeds the decision.'),
 ('Emits','A signed, scoped, time-limited authorization (tamper-evident).'),
 ('Does not do','Execute the action.')]),
H2('5.2 Model, exact action, sequence and clearance'),
MOD('Model Authority','REFERENCE-GRADE',[
 ('Question it answers','Which model may handle this specific request, right now?'),
 ('Receives / references','Request context and approved model policy.'),
 ('Checks / decides','Per-request eligibility.'),
 ('Emits','ALLOW / DENY / HOLD / ESCALATE, with governed fallback and expiry.'),
 ('Does not do','Execute the request; replace platform provider approval.')]),
MOD('ActionGate','REFERENCE-GRADE',[
 ('Question it answers','Is this the exact authorized action on the exact target, and is it still valid?'),
 ('Receives / references','Decision record, target identity, proposed action.'),
 ('Checks / decides','Whether the action presented matches the authorized action; uncertainty maps to INDETERMINATE.'),
 ('Emits','AUTHORIZED / DENIED / INDETERMINATE, bound to the exact payload/target.'),
 ('Does not do','Judge operational safety; own execution.')]),
MOD('StoryGraph','REFERENCE-GRADE',[
 ('Question it answers','Do individually-harmless steps add up to a harmful capability?'),
 ('Receives / references','A multi-step plan across steps.'),
 ('Checks / decides','Whether benign steps assemble a harmful capability.'),
 ('Emits','OBSERVE / ESCALATE (advisory).'),
 ('Does not do','Authorize or execute.')]),
MOD('Action Clearance (ACP)','REFERENCE-GRADE',[
 ('Question it answers','Is it operationally safe to execute right now?'),
 ('Receives / references','An already-authorized action plus current live conditions.'),
 ('Checks / decides','Blackout, conflict, unhealthy dependency, operational hold.'),
 ('Emits','CLEAR / HOLD / BLOCK / ESCALATE (subtractive).'),
 ('Does not do','Create or broaden authority; dispatch execution.')]),
H2('5.3 Coordination, actuation, lifecycle and assurance'),
MOD('Agent Runtime','REFERENCE-GRADE',[
 ('Question it answers','How is the governed execution coordinated safely?'),
 ('Receives / references','A governed request; invokes providers / domain executors.'),
 ('Checks / decides','Execution lifecycle (retry / timeout / recovery).'),
 ('Emits','An execution receipt; owns canonical execution state.'),
 ('Does not do','Create authority; author policy; authorize; mint clearance.')]),
MOD('Cloud Scaling Operations','Core IMPLEMENTED · validation PILOT PENDING · additional capabilities UNDER DEVELOPMENT · integration PROPOSED',[
 ('Question it answers','How is a bounded infrastructure change carried out under strict controls?'),
 ('Receives / references','A scaling instruction plus an externally minted execution authorization.'),
 ('Checks / decides','Readiness; bounded execution (dry-run by default).'),
 ('Emits','An execution outcome + audit, returned to Agent Runtime.'),
 ('Does not do','Mint its own authority; act as a preceding authorization gate.')]),
MOD('RA-6 Authority Lifecycle','REFERENCE-GRADE',[
 ('Question it answers','How is authority kept current when conditions change?'),
 ('Receives / references','A reassessment signal when conditions change.'),
 ('Checks / decides','Whether to revoke / supersede / expire authority.'),
 ('Emits','A lifecycle mutation; revocation bites at the next pre-effect recheck.'),
 ('Does not do','Execute or authorize.')]),
MOD('RA-7 Trajectory Assurance','REFERENCE-GRADE',[
 ('Question it answers','Is an in-flight execution drifting from expected behavior?'),
 ('Receives / references','The in-flight execution (neutral observation).'),
 ('Checks / decides','Whether the trajectory is drifting.'),
 ('Emits','NORMAL / ESCALATED / UNKNOWN, a neutral reassessment signal.'),
 ('Does not do','Mint authority.')]),
MOD('RA-8 Execution Assurance','REFERENCE-GRADE',[
 ('Question it answers','Did reality match what was authorized?'),
 ('Receives / references','Authorized action, execution receipt, observed post-action state.'),
 ('Checks / decides','Whether only the intended target changed, within scope.'),
 ('Emits','matched / mismatch / partial / unknown.'),
 ('Does not do','Retroactively legitimize an unauthorized action.')]),
PB(),
)

# ============================ 6. UC-5 LEAD SCENARIO ============================
add(
H1('6. Detailed lead scenario: UC-5 autonomous change execution','sec6'),
NOTE('This is an illustrative enterprise scenario showing how the proposed integration could work. It is not a claimed customer deployment.', kind='warn', title='Illustrative scenario'),
P('Scenario at a glance:'),
BUL(
 [b('ServiceNow change record: '),'CHG0048217'],
 [b('Business service: '),'online checkout'],
 [b('Target: '),'a production Kubernetes cluster'],
 [b('Proposed action: '),'scale the checkout service from 12 to 18 instances'],
 [b('Reason: '),'sustained demand and latency pressure'],
 [b('Constraints: '),'an approved cost ceiling, a permitted change window, healthy dependencies and rollback capability'],
),
H2('6.1 The problem in plain language'),
P('Checkout latency is rising under sustained demand, and an AI operations agent recommends adding capacity. Scaling may prevent an outage — but the online-checkout service is revenue-critical, and so is any service that shares the cluster. Scaling the wrong cluster or service, or acting on stale information, could disrupt another service or exceed the approved cost. A valid approval may no longer be safe if a freeze has begun, a dependency has become unhealthy, or projected cost now exceeds the ceiling. And after the change, the record must reflect what actually happened — that only the intended instances changed, and nothing else. The enterprise wants the speed of autonomy together with proof that the exact approved change ran, at a safe moment, with a verifiable, reconciled result.'),
H2('6.2 Data entering the workflow'),
TABLE('Table 4. Business data entering the UC-5 workflow (business-readable fields, not internal schemas).',
 ['Data category','Example','Authoritative source'],
 [['Business record','Change request CHG0048217 and its approval state','ServiceNow Change Management'],
  ['Target context','Cluster, checkout service and requested capacity (12 → 18)','CMDB, ITOM and cloud platform'],
  ['Live conditions','Freeze window, dependency health and service health','ServiceNow and operational telemetry'],
  ['Governance context','Delegated scaling authority, cost / risk limits and expiry','Approved enterprise policy'],
  ['Intended outcome','Lower latency within cost and risk constraints','Business objective']],
 widths=[0.24,0.46,0.30]),
H2('6.3 Layman workflow'),
DIAG('uc5_layman','Figure 3. UC-5 in plain language: the business journey (illustrative).'),
PB(),
H2('6.4 Technical module workflow'),
P('The workflow is presented in two phases for portrait reading: first authorization and clearance, then execution and assurance. The verified execution relationship is that Agent Runtime ',b('invokes'),' Cloud Scaling Operations (a domain executor, not a preceding gate); the executor returns its result to Agent Runtime, which supplies the execution receipt to RA-8.'),
H3('Phase 1 — Authorization and clearance'),
DIAG('uc5_auth','Figure 4. UC-5 Phase 1: binding decision, exact-action authorization and independent clearance, with the fail-closed stop path (illustrative).'),
H3('Phase 2 — Execution and assurance'),
DIAG('uc5_exec','Figure 5. UC-5 Phase 2: Agent Runtime invokes Cloud Scaling Operations, receives its result, and supplies the execution receipt to RA-8 for effect reconciliation (illustrative).'),
PB(),
H2('6.5 Module-by-module walkthrough'),
TABLE('Table 5. UC-5 authorization half — what each module receives, checks, adds and passes forward.',
 ['Module','Receives','Question it answers','Adds','Sends next','If information is missing'],
 [['Decision Authority','Proposed change, delegated authority, constraints','Is there a binding decision within delegated scope, by a non-AI principal?','A binding decision record','To ActionGate','No delegated authority → no binding decision; stop'],
  ['ActionGate','Decision record, cluster identity, proposed action','Is this the exact authorized action, still valid?','An exact-target action authorization','To Action Clearance','Mismatch or uncertainty → INDETERMINATE; stop'],
  ['Action Clearance','The authorization + current live conditions','Is it operationally safe right now?','A CLEAR / HOLD / BLOCK / ESCALATE verdict','To Agent Runtime (on CLEAR)','Unsafe or unknown live state → HOLD / BLOCK']],
 widths=[0.15,0.19,0.2,0.14,0.13,0.19]),
TABLE('Table 6. UC-5 execution half — coordination, actuation and assurance.',
 ['Module','Receives','Question it answers','Adds','Sends next','If information is missing'],
 [['Agent Runtime','The governed request (on CLEAR)','How is execution coordinated safely?','An execution receipt; owns canonical execution state','Invokes Cloud Scaling Operations; carries the receipt to RA-8','No governance wired → fails closed; blocks'],
  ['Cloud Scaling Operations','A scaling instruction + external execution authorization','Is it ready, and bounded to the authorization?','An execution outcome + audit','Returns the result to Agent Runtime','No execution authorization → dry-run only; no live change'],
  ['RA-8 Execution Assurance','Authorized action, receipt, observed cluster state','Did only the authorized instances change, within scope?','matched / mismatch / partial / unknown','Status + receipt references to ServiceNow','Cannot verify → uncertain / manual review; never auto-authorize']],
 widths=[0.15,0.19,0.19,0.15,0.15,0.17]),
H2('6.6 Human-control boundary'),
BUL(
 [b('May be autonomous: '),'evaluating the approval, binding the exact action, checking live safety, and performing the bounded scaling inside the approved window and cost ceiling.'],
 [b('Forces HOLD / ESCALATE: '),'an active freeze, a conflicting change, an unhealthy dependency, projected cost over the ceiling, or an expired / superseded authorization.'],
 [b('Remains human-binding: '),'the delegation of scaling authority itself, and any change outside the approved class or scope.'],
 [b('Limits: '),'cost ceiling, capacity-delta bounds, blast radius (one named cluster / service) and reversibility (rollback requirement).'],
 [b('Fail-closed: '),'if a mandatory approval, evidence item, live-safety check or execution confirmation is missing, the workflow does not treat uncertainty as permission.'],
),
H2('6.7 Business outcome and pilot measurements'),
P('Possible pilot measures include: exact-target authorization rate; authorization mismatches blocked; unsafe live conditions detected; execution-to-effect match rate; change success rate; rollback rate; latency improvement; service availability; time saved; and infrastructure cost.'),
NOTE('Cloud Scaling maturity — four separate dimensions (do not conflate): Core Cloud Scaling Controller: IMPLEMENTED. Production validation: PILOT PENDING. Additional agentic-AI capabilities: UNDER ACTIVE DEVELOPMENT. ServiceNow integration: PROPOSED — no connector currently ships. The core controller is implemented and awaiting pilot validation; it is not downgraded because additional capabilities or pilot validation remain pending.', kind='note', title='Cloud Scaling maturity'),
PB(),
)

# ============================ 7. ADDITIONAL SCENARIOS ============================
add(H1('7. Additional detailed enterprise scenarios','sec7'))

# UC-11
add(
H2('7.1 UC-11 — Vulnerability remediation and emergency patching','sec7_11'),
P('A critical vulnerability is found on production servers, and an AI agent proposes to deploy an emergency patch. Speed matters — but patching the wrong set of servers, patching a business-critical system at the wrong moment, or continuing after the risk picture worsens mid-rollout can cause the very outage the patch was meant to prevent.'),
NOTE('Illustrative: VUL0007731 → remediation task → change record; a critical remote-code-execution vulnerability on a web tier; 40 configuration items in “payments-web”; an emergency patch; a staged rollout with the ability to stop mid-flight. Not a customer deployment.', kind='warn'),
P('ServiceNow Vulnerability Response already creates remediation tasks, links them to change for approval and tracking, and can initiate emergency response workflows. The proposed Ugence value is exact-CI binding, per-stage clearance, mid-rollout revocation and effect reconciliation.'),
TABLE('Table 7. Business data entering the UC-11 workflow.',
 ['Data category','Example','Source'],
 [['Business record','Remediation task and change record, approval state','ServiceNow Vulnerability Response + Change'],
  ['Target context','40 CIs in payments-web, the patch','CMDB / Security Operations'],
  ['Live conditions','Business-criticality, maintenance window, risk posture','ServiceNow + telemetry'],
  ['Governance context','Delegated emergency-patch authority, expiry, revocability','Approved enterprise policy']],
 widths=[0.24,0.46,0.30]),
P(b('Layman workflow. '),'Critical vulnerability found → AI proposes an emergency patch → approval confirmed for this exact server set and patch → permission bound to those servers → per-stage “is it safe right now?” → patch this stage (or stop remaining stages if unsafe or the risk changed) → confirm only authorized servers changed → auditable result returned to the remediation record.'),
DIAG('uc11','Figure 6. UC-11 technical workflow, with RA-6 mid-rollout revocation and the per-stage stop path (illustrative).'),
P(b('Human-control boundary. '),'Per-stage clearance and patching are autonomous inside the authorized CI set and window; a peak-trading or criticality hold, a closed window, expired authority or a revocation signal forces HOLD / ESCALATE; the emergency-patch authority delegation and any CI outside the authorized set remain human-binding. Because RA-6 is the sole authority-lifecycle writer, a worsening risk posture can revoke authority mid-rollout; revocation is bounded-latency, stopping the ',i('next'),' stage at the pre-effect recheck, not one already in progress.'),
P(b('Metrics and evidence. '),'Mean-time-to-remediation; unauthorized-target attempts blocked; percentage of stages correctly stopped on revocation; effect-match rate. Evidence returned to ServiceNow: per-stage authorization, clearance, receipts, revocation record and effect-match.'),
PB(),
)

# UC-6
add(
H2('7.2 UC-6 — Access provisioning with segregation of duties','sec7_6'),
P('An employee asks a self-service assistant for elevated access — for example, the ability to both create and approve payments. An AI agent could fulfil it in seconds, but granting an entitlement that breaks segregation of duties, or that the requester’s current risk posture should block, can create fraud exposure that is hard to unwind.'),
NOTE('Illustrative: RITM0102934; a finance analyst who already holds “create payment” requests “approve payment” in the ERP; a segregation-of-duties rule prohibits one person holding both. Not a customer deployment.', kind='warn'),
P('ServiceNow provides Service Catalog request fulfilment, entitlement management, and — with the Veza-based identity capabilities — least-privilege and AI Agent access controls. The proposed Ugence value is exact-entitlement authorization and an independent segregation-of-duties clearance.'),
P(b('Layman workflow. '),'Employee requests elevated access → approval confirmed for this exact entitlement → permission bound to this user and entitlement → “any conflict? safe now?” → access granted, or blocked for human review on a segregation-of-duties conflict → confirm only that access was granted → auditable result returned to the request.'),
DIAG('uc6','Figure 7. UC-6 technical workflow; the decisive control is the segregation-of-duties conflict at clearance time (illustrative).'),
P(b('Human-control boundary. '),'Fulfilling entitlements with no segregation-of-duties conflict and a clear risk posture may be autonomous; any conflict, elevated risk posture, disabled account or expired authority forces HOLD / ESCALATE / BLOCK; the access-grant authority delegation and any entitlement outside scope remain human-binding. A perfectly valid authorization is still blocked when Action Clearance detects a conflict — authorization and clearance are independent.'),
P(b('Metrics and evidence. '),'Access-policy violations prevented; percentage of grants with matched effect; time saved per request; unauthorized-entitlement attempts blocked. Evidence: decision, exact-entitlement authorization, SoD clearance and effect-match (or a clean “no change” on block).'),
PB(),
)

# UC-3
add(
H2('7.3 UC-3 — High-risk AI action enforcement','sec7_3'),
NOTE('Illustrative (privileged production access): an AI use case classified high-risk is about to grant privileged production access automatically. The policy is approved and controls are on file — but at the moment of action, is every required control currently satisfied by trusted, re-checked evidence, or is the system relying on a stale, self-asserted “pass”? Not a customer deployment.', kind='warn'),
P('Acting on out-of-date compliance evidence is exactly what audits punish. AI Control Tower and AI Risk & Compliance remain the governance systems of record — classification, multi-framework control mapping and enforcement. Ugence proposes an independently verifiable, action-level authority artifact linked to ',b('current'),' evidence, so a stale or self-asserted control cannot wave an action through.'),
DIAG('uc3','Figure 8. UC-3 technical workflow: trusted-evidence admission, a signed and scoped authority, exact-action enforcement and effect reconciliation (illustrative).'),
P(b('Positioning (honest). '),'Whether ServiceNow already emits an equivalent independently verifiable, evidence-fresh per-action artifact is a discovery hypothesis to confirm with the customer’s architects — not an assumed gap. The policy approval and the authority delegation remain human-binding, and stale or self-asserted evidence is never treated as a satisfied control.'),
P(b('Metrics and evidence. '),'Percentage of high-risk actions with fresh-evidence backing; stale-evidence blocks; effect-match rate. Evidence: a re-checked control result, a signed authorization, an exact-action authorization and an effect-match — an audit-ready chain.'),
PB(),
)

# UC-4
add(
H2('7.4 UC-4 — External agents through Action Fabric, A2A and MCP','sec7_4'),
P('Enterprises now let external AI agents (for example Claude or Copilot) take real actions on enterprise systems. ServiceNow Action Fabric opens its system of action to these agents and routes every action through AI Control Tower; with NVIDIA OpenShell, policy is enforced at runtime on file, command and network access. The remaining question is narrow: for each business action an external agent takes, is there an independent, verifiable record that this exact action was authorized — and does anything notice when individually-allowed steps add up to something that should not be allowed?'),
NOTE('Ownership (unchanged): Action Fabric owns the governed ServiceNow action pathway; NVIDIA OpenShell owns its runtime / sandbox enforcement. Ugence proposes authority, exact-action binding, evidence lineage, clearance where applicable, sequence-risk and assurance artifacts. Ugence does not own or replace Action Fabric or OpenShell.', kind='note', title='Ownership'),
DIAG('uc4','Figure 9. UC-4 technical workflow: dispatch and kernel-level enforcement are ServiceNow (Action Fabric) and NVIDIA (OpenShell); Ugence adds authority, exact-payload binding, sequence-risk and assurance only (illustrative).'),
P('This is the strongest overlap zone and a partnership-native one — Anthropic is ServiceNow’s Action Fabric design partner. Ugence claims neither a governance gap nor unique cross-runtime enforcement; the differentiation is confined to the properties of the independent authority-and-evidence artifact (Section 9). Metrics: unauthorized-payload attempts blocked; sequence escalations caught; percentage of actions with an independent authorization record.'),
PB(),
)

# ============================ 8. PORTFOLIO ============================
def uc(idn,name,problem,anchor,ugence,autonomy,maturity,discovery):
    return {'id':idn,'name':name,'problem':problem,'anchor':anchor,'ugence':ugence,'autonomy':autonomy,'maturity':maturity,'discovery':discovery}

add(
H1('8. Full use-case portfolio','sec8'),
P('The collection below comprises ',b('enterprise workflow scenarios grounded in actual ServiceNow products, with proposed Ugence governance extensions'),'. They are not proven Ugence customer deployments. Every ServiceNow integration is ',b(PROP),'.'),
H2('8.1 Pilot-ready operational scenarios'),
{'t':'uccards','cards':[
 uc('UC-5','Autonomous change execution','Scale / restart / config changes made autonomously','Change Management + ITOM','Exact-CI authority, independent clearance, effect reconciliation','Autonomous within window and cost; freeze / conflict force stop','PROPOSED INTEGRATION','Which change and CMDB events are authoritative?'),
 uc('UC-6','Access provisioning with SoD','Elevated access fulfilled by an assistant','Service Catalog / Employee Center (+ Veza)','Exact-entitlement authority + independent SoD clearance','Autonomous when no SoD conflict; conflict → block','PROPOSED INTEGRATION','Which entitlement class suits a bounded pilot?'),
 uc('UC-11','Vulnerability remediation','Emergency patch to production CIs','Security Operations — Vulnerability Response','Exact-CI binding, per-stage clearance, mid-rollout revocation','Per-stage autonomy; revocation stops the next stage','PROPOSED INTEGRATION','Which critical-vulnerability workflow for a pilot?'),
]},
H2('8.2 Practical scenarios requiring bounded autonomy'),
{'t':'uccards','cards':[
 uc('UC-7','Refunds and credits','AI issues a refund or credit','Customer Service Management (Now Assist)','Amount + account binding; reconcile executed = authorized','Within a delegated dollar threshold','PROPOSED INTEGRATION','Which refund band is safe to pilot?'),
 uc('UC-8','Procurement and PO execution','AI places a purchase order','Sourcing & Procurement Operations','Compiled policy, supplier-evidence check, exact PO binding','Threshold-bound; above → human authority','PROPOSED INTEGRATION','Which spend threshold and category?'),
 uc('UC-10','Agentic hiring (human-binding)','AI assists screening and scheduling','HR Service Delivery / Recruitment','Keep hire / reject human; immutable decision record','Assistive only; decision stays human-binding','PROPOSED INTEGRATION','Which step may be automated vs human-bound?'),
]},
H2('8.3 Strategic governance scenarios'),
{'t':'uccards','cards':[
 uc('UC-2','Per-request model authorization','Regulated data about to reach a model','AI Control Tower model / provider governance','Per-request ALLOW / DENY / HOLD / ESCALATE + fallback / expiry','Per-request binding, not a static allowlist','PROPOSED INTEGRATION','Which data classes trigger per-request control?'),
 uc('UC-3','High-risk action enforcement','High-risk AI action on stale evidence','AI Control Tower — AI Risk & Compliance','Signed, scoped, evidence-fresh action authority','Only while trusted evidence is current','PROPOSED INTEGRATION','Which high-risk use case for a pilot?'),
 uc('UC-4','External-agent governance','External agents act on the system of action','Action Fabric + AI Agent Fabric + OpenShell','Independent exact-payload authority, sequence-risk, assurance','Composes with platform enforcement','PROPOSED INTEGRATION','Which external-agent workflow to pilot?'),
 uc('UC-12','Data-boundary governance','Agents pull enterprise data into context','Workflow Data Fabric + AICT privacy','Minimum-necessary context; token accounting; fail-closed','Governs exactly what crosses the model boundary','PROPOSED INTEGRATION','Which data domains need boundary control?'),
]},
H2('8.4 Emerging or future scenarios'),
{'t':'uccards','cards':[
 uc('UC-1','Autonomous security containment','Autonomous host isolation / account disable / IP block','Security Incident Response — Tier 2 SOC AI Specialist','Exact-target authority, live-safety clearance, effect reconciliation','Forward-looking; not shipped','ANNOUNCED / FUTURE — Tier 2 SOC AI Specialist expected December 2026','When the specialist ships, where does authority bind?'),
 uc('UC-9','Governed multi-agent workforce','A team of agents runs an end-to-end process','AI Agent Orchestrator / Autonomous Workforce','Least-privilege team plan granting nothing; per-action authorization + sequence-risk','Composition grants no authority','PROPOSED INTEGRATION','Which multi-agent process to bound first?'),
]},
PB(),
)

# ============================ 9. OVERLAP & DIFFERENTIATION ============================
add(
H1('9. Honest overlap and precise differentiation','sec9'),
P('Several capabilities genuinely overlap with current ServiceNow functionality. They are named here as overlaps, discussed as granularity or independent-verification extensions, never as governance gaps.'),
TABLE('Table 8. Confirmed overlap zones and the narrow proposed Ugence edge.',
 ['Zone','ServiceNow capability','Ugence proposed edge (narrow)'],
 [['ActionGate ↔ Action Fabric / AICT','Governed, identity-verified, auditable action execution','Per-payload / target authorization re-checked at commit (discovery hypothesis)'],
  ['RA-7 ↔ Agent Deviation Detection','Flags when an agent strays from its role','Independently verifiable trajectory signal into an authority lifecycle'],
  ['RA-6 ↔ real-time shutdown','Can stop a misbehaving agent','Authority-lifecycle revoke / epoch; enforcement stays read-only'],
  ['Model Authority ↔ Skill-Kit approval','Restricts which models run','Per-request binding decision with governed fallback and expiry'],
  ['AICT + NVIDIA OpenShell','Central policy enforced at runtime across file / command / network','Ugence does not claim unique cross-runtime enforcement — the differentiation is the artifact']],
 widths=[0.26,0.36,0.38]),
P('The narrow, defensible differentiation is confined to the properties of an independent, action-level authority-and-evidence artifact: independently verifiable (by a party other than the executor); bound to the exact business action and target; linked to trusted evidence; scoped and time-limited; re-checked before consequential execution; separated from live operational clearance; connected to execution receipts; reconciled against observed effect; and usable in a cross-stage evidence lineage.'),
NOTE('Absence from public documentation is never treated as proof that ServiceNow lacks a capability. Where a Ugence edge is unconfirmed, it is a discovery question for ServiceNow architects.', kind='note', title='Evidence discipline'),
PB(),
)

# ============================ 10. GOVERNED VALUE ============================
add(
H1('10. Enterprise Governed Value','sec10'),
NOTE('Enterprise Governed Value is a developing, cross-cutting capability — not an authorization gate.', kind='note', title='Status: under development'),
P('ServiceNow AI Control Tower already measures AI adoption, business impact, realized value and ROI. This proposal does not duplicate or replace that. The proposed Ugence contribution is ',b('evidence-backed outcome attribution'),' connecting approved objectives, governed-execution evidence, attributable cost, observed outcomes, and preserved risk, compliance, quality and service constraints — reusing the governance evidence the pipelines already emit, adding attribution rather than a new gate.'),
TABLE('Table 9. Governed-value attribution illustrated with the UC-5 checkout-scaling example.',
 ['Element','UC-5 example'],
 [['Approved objective','Reduce checkout latency'],
  ['Baseline','Current latency, capacity and cost'],
  ['Governed action','Scale 12 → 18 instances'],
  ['Execution evidence','Authorization · clearance · receipt'],
  ['Observed outcome','Latency improved; service healthy'],
  ['Attributable cost','Additional infrastructure expense'],
  ['Preserved constraints','No change-window, risk or availability violation'],
  ['Governed-value question','Enough attributable value without unacceptable trade-offs?']],
 widths=[0.34,0.66]),
PB(),
)

# ============================ 11. PILOT ============================
add(
H1('11. Proposed bounded pilot','sec11'),
P('The recommended first pilot is UC-5, autonomous change execution, as a bounded 30–60-day technical pilot. Autonomy is earned step by step; live controlled execution is not enabled until dry-run, exception-path and receipt checks pass. No broad production autonomy is promised at pilot start.'),
NUM(
 'Joint technical discovery',
 'Data and integration mapping',
 'Historical replay',
 'Dry-run or shadow evaluation',
 'HOLD / BLOCK / ESCALATE testing',
 'Limited controlled execution',
 'Execution-receipt verification',
 'Observed-effect reconciliation',
 'Pilot evaluation',
 'Joint next-phase decision',
),
P(b('Possible pilot boundary: '),'one controlled scaling workflow; a limited set of noncritical or carefully selected CIs / clusters; restricted action types; explicit authority and cost limits; defined rollback requirements; and no broad production autonomy at pilot start. Success is measured on safety and fidelity first — exact-target binding, mismatches blocked, effect-match — then on operational benefit.'),
PB(),
)

# ============================ 12. DISCOVERY & NEXT STEP ============================
add(
H1('12. Discovery questions and next step','sec12'),
P('Constructive questions to work through together — the answers shape the pilot:'),
BUL(
 'Which ServiceNow records are authoritative for each scenario?',
 'What events expose the approval, target and execution context?',
 'Where could an independent action-level authorization be evaluated?',
 'Where could a live operational clearance verdict be consumed?',
 'How should execution receipts and effect results be associated with the originating record?',
 'Which controls already provide equivalent granularity?',
 'What should remain human-binding?',
 'What data may leave the ServiceNow boundary?',
 'What evidence would be required for production acceptance?',
),
QUOTE('The proposed next step is a joint technical discovery session to select and define one bounded pilot.'),
P('This is a request for technical fit, not a broad partnership commitment. ServiceNow remains the system of record, the system of action and the platform that enforces execution; Ugence contributes an independent, signed authority-and-evidence artifact that composes with it.'),
PB(),
)

# ============================ 13. APPENDICES ============================
add(
H1('13. Appendices','sec13'),
H2('Appendix A — Maturity and availability legend'),
TABLE('Table 10. Maturity and availability labels used in this briefing.',
 ['Label','Meaning'],
 [['IMPLEMENTED','Package code exists and is verified at interface level. Does not imply production-deployment validation or a shipping ServiceNow integration.'],
  ['REFERENCE-GRADE','A reference implementation exists and is offline-verifiable, but is not production-validated. Does not imply a shipping ServiceNow integration.'],
  ['PILOT PENDING','Implemented, but awaiting production / pilot validation.'],
  ['ADDITIONAL CAPABILITIES UNDER DEVELOPMENT','Further capabilities beyond the implemented core are actively being built.'],
  ['DESIGN-ONLY','Architecture / design intent; not yet a package.'],
  ['PROPOSED INTEGRATION','A ServiceNow integration adapter is design intent only; no ServiceNow connector currently ships. (Also written “integration PROPOSED”.)'],
  ['ANNOUNCED / FUTURE','A named future capability publicly announced but not yet shipped (e.g., the Tier 2 SOC AI Specialist expected December 2026).']],
 widths=[0.42,0.58]),
H2('Appendix B — Module-to-scenario matrix'),
TABLE('Table 11. Which modules participate in each detailed scenario (● = participates).',
 ['Module','UC-5','UC-11','UC-6','UC-3','UC-4'],
 [['Policy Workflow Compiler','','','','●',''],
  ['RA-5 Trusted Evidence Admission','','','','●',''],
  ['Decision Authority','●','●','●','●',''],
  ['Risk Authority','','','','●',''],
  ['Model Authority','','','','','●'],
  ['ActionGate','●','●','●','●','●'],
  ['StoryGraph','','','','','●'],
  ['Action Clearance (ACP)','●','●','●','','●'],
  ['Cloud Scaling Operations','●','','','',''],
  ['Agent Runtime','●','●','●','●','●'],
  ['RA-6 Authority Lifecycle','','●','','',''],
  ['RA-7 Trajectory Assurance','','','','','●'],
  ['RA-8 Execution Assurance','●','●','●','●','']],
 widths=[0.4,0.12,0.12,0.12,0.12,0.12]),
P(i('UC-4 ends in RA-7 (in-flight trajectory assurance) rather than RA-8, because execution and enforcement are performed by ServiceNow Action Fabric and NVIDIA OpenShell. UC-11 uniquely exercises RA-6 for mid-rollout revocation. UC-5 uniquely exercises Cloud Scaling Operations as the domain executor.')),
H2('Appendix C — Source hierarchy and citations'),
P('Product behavior is grounded first in ServiceNow product documentation, then release notes, Newsroom and Community; NVIDIA documentation for OpenShell; third-party press only for corroboration. Ugence module behavior is grounded in the source-of-record documents (catalog v1.2 and the use-case walkthrough companion) at the guarantee level; no internal repository detail is disclosed.'),
BUL(
 [b('ServiceNow Docs: '),'existing product behavior and workflow mechanics (docs.servicenow.com).'],
 [b('ServiceNow release notes: '),'versions and availability.'],
 [b('ServiceNow Newsroom: '),'announcements, partnerships and future availability (e.g., the December 2026 Tier 2 SOC AI Specialist).'],
 [b('ServiceNow Community: '),'supporting and explanatory material.'],
 [b('NVIDIA documentation: '),'OpenShell technical behavior (enforcement via seccomp, Landlock LSM and network namespaces — not eBPF).'],
 [b('Third-party press: '),'corroboration of announcement facts only.'],
),
P(i('Direct page fetches to some ServiceNow properties were egress-restricted during preparation; product names, availability framing and protocol support were corroborated across multiple ServiceNow-owned sources and should be spot-checked on the live documentation before customer use. No internal repository paths are cited in this external document.')),
H2('Appendix D — Standing qualifications and disclaimers'),
BUL(
 'All ServiceNow integrations described are PROPOSED; no ServiceNow connector currently ships.',
 'All scenarios are illustrative enterprise workflows, not claimed Ugence customer deployments.',
 'Maturity dimensions are not conflated: a multi-module workflow carries per-module maturity.',
 'Unverified differentiation is a discovery hypothesis, never a claim that ServiceNow lacks a capability.',
 'This briefing describes what each module guarantees, not the proprietary mechanism that produces it.',
),
)
