# Content model for the City-Scale Vehicle Intelligence client brief v2.0.
# Consumed by both the PDF (WeasyPrint) and DOCX (python-docx) renderers in build.py.
# Repository source of record: default branch tip 78e8e19 (packages/** identical on the
# working branch). Maturity is stated conservatively; see the evidence report.

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

CONTENT=[]
def add(*blocks):
    for x in blocks: CONTENT.append(x)

# ============================ 1. PURPOSE & SCOPE ============================
add(
H1('1. Document purpose and scope','sec1'),
P('This briefing shows how the current Ugence Labs governance and execution-control architecture can govern a ',b('city-scale vehicle-intelligence system'),' — traffic-signal violation detection, automatic number-plate recognition (ANPR / ALPR), vehicle re-identification, trajectory reconstruction, traffic-controller evidence, bounded investigation, registry access, and citation or enforcement proposals — including autonomous or agentic investigation, runtime authorization, controlled execution, and effect verification.'),
QUOTE('The vehicle-intelligence platform determines what the available evidence indicates. Ugence determines what may be concluded, disclosed, investigated or executed — under which policy, evidence, authority, purpose and scope — and verifies whether the resulting action remained within that authorization.'),
NOTE('This is a conceptual reference architecture grounded in the current Ugence repository. It is not legal advice, not a representation of any existing government, police or municipal deployment, and not a substitute for jurisdiction-specific policy review. Every capability is labelled with its current engineering maturity; a design or a passing unit test is never presented as a production deployment. All ServiceNow or enterprise-platform integration described here is a neutral pattern, not a shipped connector.', kind='warn', title='Scope and standing disclaimer'),
P('Acronyms are defined on first use and collected in the glossary (Appendix, Section 24). Detailed schemas, API payloads and the normative requirement catalogue are kept in the appendices so they do not interrupt the client narrative.'),
NOTE('Maturity labels used throughout (defined in full in Section 21 and the glossary): '
     'IMPLEMENTED + CI = code merged to the default branch with its own tests run in continuous integration; '
     'IMPLEMENTED = code merged with tests, but no dedicated CI workflow, or not yet production-validated; '
     'REFERENCE = a reference/illustrative implementation, not integrated into the running control plane; '
     'DESIGN-ONLY = a ratified or drafted design with no running implementation; '
     'FUTURE = proposed, not yet designed or built. These describe engineering status only — never a claim of production deployment, legal sufficiency, or formal proof.', kind='note', title='How to read the maturity labels'),
)

# ============================ 2. EXECUTIVE SUMMARY ============================
add(
H1('2. Executive summary','sec2'),
P('A city-scale vehicle-intelligence system can detect traffic violations, read plates, correlate camera observations, and reconstruct a vehicle’s journey across a road network. The genuinely hard part is not red-light detection alone; it is maintaining vehicle identity across heterogeneous cameras and imperfect observations while keeping ',b('what was directly observed'),' distinct from ',b('what was inferred'),' — and then turning a technical finding into a lawful, controlled, auditable action.'),
P('Ugence adds a separate governance and execution-control layer. It does not replace ANPR/ALPR, computer vision, vehicle re-identification, traffic-controller integration, or trajectory estimation. It governs how those outputs may become consequential decisions and actions, and it verifies that the action that executed matched the action that was authorized.'),
BUL(
 [b('Trusted evidence. '),'Preserve the distinction between observed, recorded, model-derived, calculated, inferred and asserted facts, and admit only evidence whose provenance, integrity, freshness and schema are verified.'],
 [b('Governed decisions. '),'Bind evidence, policy, model versions, purpose, scope and authority into an immutable, versioned decision case — a container that keeps purpose, evidence, authority and execution from drifting apart.'],
 [b('Model authority. '),'Ensure only approved model versions participate in specific decision classes; a technically capable model does not thereby acquire enforcement authority.'],
 [b('A single, signed authority artifact. '),'Convert an approved risk decision into one signed, scoped, time-limited authorization — the sole machine authority. No score, policy result, model output or receipt independently grants execution.'],
 [b('Exact-action enforcement and live clearance. '),'Authorize the exact action on the exact target, then re-check operational safety immediately before execution.'],
 [b('Execution and effect assurance. '),'Distinguish what was authorized, what command was attempted, what actually executed, and what effect occurred — and reconcile them.'],
 [b('Agent governance. '),'Keep autonomous investigation agents inside the authority granted to the case: a wider time window, a new zone, or identity resolution each becomes a new governed proposal.'],
),
P('Every element above maps to a ',b('specific, inspectable module in the current Ugence repository'),', at a stated maturity. Section 6 sets out that mapping; Section 21 separates what is implemented today from what is design-stage or future.'),
NOTE('Plain-English takeaway: the tracking platform remains the expert at seeing and reconstructing the vehicle journey. Ugence adds the checks that turn a technical finding into a permitted, controlled and auditable action — and the proof that the action stayed within its authorization.', kind='note', title='Takeaway'),
)

# ============================ 3. THE PROBLEM ============================
add(
H1('3. The city-scale vehicle-intelligence problem','sec3'),
P('The base solution answers a perception-and-state-estimation question: which vehicle is this, where was it before and after a traffic event, what signal states were present, and with what confidence can the system reconstruct the trajectory? The vehicle need not be visible on every camera; the system estimates a latent state from intermittent observations and road constraints, so it is a probabilistic state-estimation system, not merely a collection of cameras.'),
H2('Why ordinary vehicle intelligence is insufficient for consequential action'),
P('The base system produces increasingly consequential outputs as it moves from detection to inference to enforcement. A red-light image may be direct evidence; a reconstructed route is an inference; a claim of repeated dangerous behaviour is a higher-order conclusion; a citation, police alert, registry lookup or extended-surveillance request is an action. If these collapse into one undifferentiated pipeline, sensor error hides, model confidence is mistaken for fact, probabilistic hypotheses become factual assertions, and a capable model becomes self-authorizing.'),
TABLE('Table 1. The escalation from observation to action, and the risk if the stages are treated as equivalent.',
 ['Stage','Question answered','Risk if treated as equivalent'],
 [['Observation','What did a sensor directly capture?','Sensor error becomes hidden.'],
  ['Model derivation','What did ANPR / re-ID / classification produce?','Model confidence is mistaken for fact.'],
  ['Inference','What route or identity is most probable?','Probabilistic hypotheses become factual assertions.'],
  ['Decision','What should be concluded under policy?','Policy is bypassed or inconsistently applied.'],
  ['Authority','Who or what may approve this decision?','Capability becomes self-authorizing.'],
  ['Action','What external consequence may execute?','Incorrect decisions produce irreversible harm.']],
 widths=[0.2,0.4,0.4]),
H2('Critical uncertainty sources'),
BUL(
 'Plate occlusion, glare, motion blur, duplicate or similar plates.',
 'Cross-camera appearance changes from angle, lighting, weather, compression and partial visibility.',
 'Clock-synchronization errors between cameras, signal controllers and central systems.',
 'Ambiguous road routes between sightings, and sparse camera coverage with missing observations.',
 'Re-identification model drift or model-version changes.',
 'Incorrect mapping between controller state and camera / intersection identity.',
),
NOTE('Ugence is valuable precisely at the transition from “the AI believes X” to “the government system is permitted to do Y”.', kind='note'),
)

# ============================ 4. RESPONSIBILITY BOUNDARY ============================
add(
H1('4. What the platform owns and what Ugence owns','sec4'),
P('The governing invariant is that the operational intelligence system proposes facts, hypotheses, decisions or actions; it does not self-assign the authority to execute them. Ugence evaluates admissibility, scope, model eligibility, policy, decision authority, final action clearance, and — after execution — whether the observed effect matched the authorization.'),
DIAG('boundary','Figure 1. Responsibility at a glance: vehicle intelligence determines what the evidence indicates; Ugence governs what may be done with it, and verifies the effect.'),
TABLE('Table 2. Layered responsibility boundary.',
 ['Layer','Vehicle platform owns','Ugence owns'],
 [['Perception','Detection, OCR, classification, embeddings','Evidence declaration and provenance requirements'],
  ['Tracking','Cross-camera matching, route hypotheses','Rules for using inferred tracking in each decision class'],
  ['Traffic correlation','Signal-state association','Admissibility requirements and source integrity'],
  ['Case analytics','Violation proposal / risk score','Decision-case lifecycle and policy binding'],
  ['Models','Training and inference operation','Eligibility / authorization for governed decisions'],
  ['Enforcement','Action proposal','Runtime authorization, final clearance and effect verification'],
  ['Audit','Operational logs','Governed decision / action trace and authority provenance']],
 widths=[0.18,0.4,0.42]),
NOTE('Plain-English takeaway: the vehicle AI can propose a conclusion or action, but it cannot give itself permission to execute it. Ugence checks evidence, case scope, model eligibility, authority, and final clearance before the city system acts — and reconciles the effect afterward.', kind='note', title='Takeaway'),
)

# ============================ 5. REFERENCE ARCHITECTURE ============================
add(
H1('5. Current Ugence reference architecture','sec5'),
P('The architecture separates three concerns: the city and vehicle-intelligence systems that determine what the evidence indicates; the Ugence governance and execution-control plane that determines what may be concluded, disclosed, investigated or executed; and the external consequence systems that carry out the effect. The intelligence system may propose a finding or action but cannot authorize itself.'),
DIAG('refarch','Figure 2. Reference architecture in three bands. Every consequential action crosses the Ugence control plane, and the observed effect is verified back against the authorization.'),
P('The Ugence control plane is not a monolith. It is a federated set of function-specific capabilities — separate packages with explicit, machine-checked authority boundaries — coordinated so that no single component both proposes and authorizes an action. Section 6 introduces each participating module; Section 8 shows the canonical evidence-to-decision-to-action spine that threads them together.'),
NOTE('Naming note. Ugence’s implemented modules use precise internal names. This briefing uses those exact names: RA-5 trusted evidence admission, Decision Authority (owner of the DecisionCase and the Context Envelope Record), Model Authority, Risk Authority (which mints the signed authorization envelope), ActionGate, Action Clearance, Agent Runtime, and the RA-6 / RA-7 / RA-8 authority-lifecycle and assurance family.', kind='note', title='On names'),
)

# ============================ 6. PORTFOLIO ACTIVATION ============================
add(
H1('6. How this use case activates the Ugence Labs portfolio','sec6'),
P('Each module below is described at the interface level: the governance question it answers, what it receives, what it produces, whether its result grants execution authority, its role in the city-scale workflow, and its current repository maturity. Only modules that materially contribute to this use case are included. This briefing describes the guarantee each module provides, not the proprietary mechanism that produces it.'),
NOTE('A single architectural invariant holds across every module: intelligence proposes; evidence is admitted; policy requirements are evaluated; authority decides; ActionGate enforces the exact action; the runtime executes; assurance verifies the attempt, execution and effect. Only the signed Risk Authority envelope is machine authority — no evidence result, model score, policy evaluation, clearance receipt or execution receipt independently grants it.', kind='warn', title='Authority invariant'),

H2('6.1 Trusted evidence and admission'),
MOD('RA-5 — Trusted Evidence Admission  ·  ugence-risk-authority-evidence-runtime 0.1.0','IMPLEMENTED + CI',[
 ('Governance question','May this evidence enter the assurance process, and does admitted evidence satisfy the required control?'),
 ('Receives','Raw evidence with claimed provenance, a control-to-evidence map, the compiled workflow, a verification key and a clock.'),
 ('Produces','AdmittedEvidence (provenance ∧ integrity/digest ∧ freshness ∧ schema), then a trusted, bound ControlResult.'),
 ('Grants execution authority?','No — strictly upstream of authority. In production a caller-supplied “PASS” is inert; only re-checked, trusted evidence satisfies a control.'),
 ('Role in the city-scale workflow','Admits camera, controller, ANPR and registry evidence and turns control claims into trusted results; this is the linchpin that stops stale or self-asserted evidence.'),
 ('Maturity','Library IMPLEMENTED and CI-verified; end-to-end production admission wiring is PARTIAL.'),
]),
MOD('TAP — Trusted Assertion / Control-Support Provider  ·  ugence-tap-provider 0.1.0','IMPLEMENTED + CI',[
 ('Governance question','Is this material assertion supported, unsupported, constrained or indeterminate by the supplied evidence?'),
 ('Receives','An assertion plus evidence references (an AssertionGovernanceRequest).'),
 ('Produces','A component-level coverage outcome: SUPPORTED / UNSUPPORTED / CONSTRAINED / INDETERMINATE.'),
 ('Grants execution authority?','No — owns no authorization and no execution authority; an independent peer of ActionGate.'),
 ('Role in the city-scale workflow','The assertion-/control-support evaluator RA-5 wraps to test whether, e.g., “the signal was RED at the observed time” is supported by admitted evidence.'),
 ('Maturity','IMPLEMENTED and CI-verified (not production-certified).'),
]),

H2('6.2 Decision, model and authority'),
MOD('Decision Authority  ·  ugence-decision-authority 1.0.0','IMPLEMENTED + CI',[
 ('Governance question','When may an AI recommendation become a binding decision — and by whose authority?'),
 ('Receives','Subjects, policies, assessments, a recommendation, an AuthorityContext and a Context Envelope Record (CER).'),
 ('Produces','A DecisionCase (immutable, versioned) and a binding DecisionRecord; the AI is structurally barred as an authorizing principal.'),
 ('Grants execution authority?','No — it issues a binding decision, not execution; “a granted authorization never means the action happened.”'),
 ('Role in the city-scale workflow','Creates the governed DecisionCase (purpose = TRAFFIC_VIOLATION_ENFORCEMENT, bounded scope) that binds evidence, models, policy, authority and disposition.'),
 ('Maturity','IMPLEMENTED and CI-verified.'),
]),
MOD('Model Authority  ·  ugence-model-selection 0.1.0','IMPLEMENTED',[
 ('Governance question','Which model, if any, is authorized to execute this request under policy, for this decision class?'),
 ('Receives','The request, candidate executable models, and policy signals / evidence.'),
 ('Produces','A binding ModelAuthorizationDecision (ALLOW / DENY / HOLD / ESCALATE) with reason codes and governed fallback.'),
 ('Grants execution authority?','It issues a binding model-authorization decision, but owns no invocation, routing or execution.'),
 ('Role in the city-scale workflow','Confirms that ANPR / re-identification model versions are eligible for the specific decision class — investigative search is not enforcement.'),
 ('Maturity','IMPLEMENTED (renamed from Model Selection; no dedicated CI workflow yet).'),
]),
MOD('Risk Authority  ·  ugence-risk-authority 0.2.0','IMPLEMENTED + CI',[
 ('Governance question','Given trusted results for the required controls, what machine authority may be issued?'),
 ('Receives','A RiskDecisionCase built from trusted, non-compensatory ControlResults, plus an authority grant and signing key.'),
 ('Produces','A RiskDecision and, in reference mode, a signed Ed25519 RiskAuthorizationEnvelope — the sole machine authority (scope never exceeds the decision).'),
 ('Grants execution authority?','Yes, conditionally — the signed envelope is the only machine authority. In production mode it fails closed at envelope issuance today (issuance is unimplemented) and stops at a non-executable RiskDecision.'),
 ('Role in the city-scale workflow','Mints the single, scoped, time-limited authorization ActionGate matches an exact action against; controls are non-compensatory (a PASS never compensates a FAIL / STALE).'),
 ('Maturity','Spine IMPLEMENTED and CI-verified; production envelope issuance PARTIAL.'),
]),

H2('6.3 Exact-action enforcement and live clearance'),
MOD('ActionGate  ·  ugence-actiongate-provider 0.1.0','IMPLEMENTED + CI',[
 ('Governance question','Is this exact proposed action authorized under the supplied authority, policy, risk, evidence and decision context?'),
 ('Receives','An ActionGovernanceRequest (action type, actor, authority / policy / risk / evidence / decision references, idempotency key).'),
 ('Produces','An ActionGovernanceResult: AUTHORIZED / AUTHORIZED_WITH_CONSTRAINTS / DENIED / INDETERMINATE / EXPIRED, with constraints, obligations and expiry.'),
 ('Grants execution authority?','No — “authorization is never execution.” Uncertainty or infrastructure failure maps to INDETERMINATE, never to AUTHORIZED; it owns no dispatch.'),
 ('Role in the city-scale workflow','The pre-execution enforcement point: it binds the specific action (e.g. ISSUE_TRAFFIC_CITATION) to the exact target and the signed authority envelope.'),
 ('Maturity','IMPLEMENTED and CI-verified (outcome-safety enforced by a release-gating test).'),
]),
MOD('Action Clearance  ·  ugence-action-clearance 0.1.0','IMPLEMENTED',[
 ('Governance question','Given an already-authorized exact action, does it remain operationally safe immediately before execution?'),
 ('Receives','A clearance request with the authorized-action identity, a bundle of trusted current-state signals, a clearance policy and an evaluation time.'),
 ('Produces','A ClearanceResult / receipt body with status CLEAR / HOLD / BLOCK / ESCALATE (precedence BLOCK > ESCALATE > HOLD > CLEAR).'),
 ('Grants execution authority?','No — it may only preserve, narrow, hold, escalate or block an existing authorization; it may never create or broaden authority, replace ActionGate, or dispatch.'),
 ('Role in the city-scale workflow','The final invariant check at the edge of execution: authorization can go stale between decision time and execution time — clearance binds the payload, digest, target, time-to-live and parameters that were authorized.'),
 ('Maturity','IMPLEMENTED with a full local test suite; no dedicated CI workflow yet.'),
]),

H2('6.4 Runtime, execution and assurance'),
MOD('Agent Runtime  ·  ugence-agent-runtime 0.7.0','IMPLEMENTED + CI',[
 ('Governance question','How is governed execution coordinated safely, while obeying an external governance boundary?'),
 ('Receives','A workflow / task definition, a provider registry, and a governance hook.'),
 ('Produces','A workflow instance, a canonical execution state, runtime events, provider attempts and hash-chained checkpoints.'),
 ('Grants execution authority?','No — it coordinates only. With no governance adapter it fails closed (BLOCK); it re-checks an exact-action fingerprint and fails closed on drift; it never mints clearance.'),
 ('Role in the city-scale workflow','Coordinates bounded, durable, recoverable investigation and enforcement workflows; records each execution attempt as evidence.'),
 ('Maturity','IMPLEMENTED and CI-verified (durable state, checkpoints, retries/recovery, bounded advancement, scheduling, tool invocation and attempt telemetry; event sourcing is partial; concurrency is in-process).'),
]),
MOD('RA-8 — Execution & Effect Assurance  ·  ugence-risk-authority-execution-assurance 0.1.0','IMPLEMENTED + CI',[
 ('Governance question','After an authorized action executed, did the actual effect match what was authorized?'),
 ('Receives','The governed authority context, Agent Runtime attempt evidence, and effect observations.'),
 ('Produces','An EffectAssuranceAssessment (MATCHED / MISMATCH / PARTIAL / UNKNOWN / …) and a neutral authority-reassessment signal.'),
 ('Grants execution authority?','No — it emits evidence and a neutral signal only; it introduces no second authority artifact and never retroactively authorizes an action.'),
 ('Role in the city-scale workflow','Closes the loop between the authorized citation / action and the observed external effect; verification strength is bounded by the effect source.'),
 ('Maturity','IMPLEMENTED and CI-verified (reference-grade).'),
]),
MOD('RA-7 — Runtime Trajectory Assurance  ·  ugence-risk-authority-runtime-assurance 0.1.0','IMPLEMENTED + CI',[
 ('Governance question','Is the in-flight execution trajectory deviating materially enough to reassess authority?'),
 ('Receives','Runtime events / telemetry from the execution in progress.'),
 ('Produces','A TrajectoryAssessment (NORMAL / ESCALATED / UNKNOWN) and a neutral reassessment signal.'),
 ('Grants execution authority?','No — “observes and assesses; mints nothing, mutates no lifecycle state.”'),
 ('Role in the city-scale workflow','Watches long-running investigations and multi-stage actions for drift that should trigger reassessment.'),
 ('Maturity','IMPLEMENTED and CI-verified (reference-grade).'),
]),
MOD('RA-6 — Authority Lifecycle  ·  ugence-risk-authority-status-runtime 0.1.0','IMPLEMENTED + CI',[
 ('Governance question','Post-issuance, is authority still valid — should it be revoked, epoch-advanced or expired on a reassessment signal?'),
 ('Receives','An authority-reassessment signal from RA-7 or RA-8.'),
 ('Produces','A lifecycle mutation (revoke / advance epoch / expire) via the sole authenticated writer, plus a read-only status cache.'),
 ('Grants execution authority?','No new authority — the worst case is restriction; it is the only authenticated writer of authority lifecycle state.'),
 ('Role in the city-scale workflow','Lets a worsening risk picture revoke authority mid-investigation; revocation bites at the next pre-effect re-check.'),
 ('Maturity','IMPLEMENTED and CI-verified (reference in-memory persistence; mechanism present but operationally inert — no non-test write call sites).'),
]),
P(b('Supporting and cross-cutting modules. '),'The following also participate at the maturity shown, and are described here rather than as full cards to keep the primary chain in focus.'),
TABLE('Table 3. Supporting Ugence modules used in this use case.',
 ['Module (repository name)','Role in this use case','Grants authority?','Maturity'],
 [['Governed Execution Composition — ugence-risk-authority-runtime','Composes the Risk Authority envelope with Decision Authority and ActionGate into a GovernedExecutionDecision (GRANT/DENY/HOLD); the envelope is the sole issuer, the others can only subtract.','No','IMPLEMENTED + CI'],
  ['StoryGraph — ugence-storygraph 2.0.0','Advisory sequence-risk: do individually-cleared searches or actions assemble a prohibited capability? Emits OBSERVE / ESCALATE findings only.','No (advisory)','IMPLEMENTED (reference; synthetic-only)'],
  ['Policy Workflow Compiler — ugence-policy-workflow-compiler 0.2.0','Compiles a reviewed, structured policy pack into a deterministic governed-workflow definition plus an assurance manifest; rejects self-approval. Tooling, not authority.','No','IMPLEMENTED + CI (offline)'],
  ['Governance Contracts / Provider Framework','The neutral request/result vocabulary and the registry that lets capabilities interoperate without depending on one another.','No','IMPLEMENTED + CI'],
  ['Context Minimization + token accounting — ugence-context-minimization 0.2.0','Governs exactly what context an agent may carry across the data boundary, with per-attempt token accounting; fail-closed, equivalence-preserving.','No','IMPLEMENTED + CI'],
  ['Agent Workforce Composer — ugence-agent-workforce-composer 0.2.1','Offline planning of which investigation agents / teams may staff a workflow, with least-privilege permission proposals; grants nothing, schedules nothing.','No','IMPLEMENTED + CI (offline)'],
  ['Governed Value — ugence-governed-value 0.2.0','Reports net governed value and ROI of a governed workflow; all outputs are REPORTED / UNVERIFIED with no authority binding.','No','IMPLEMENTED (experimental; reported-only)'],
  ['Credential brokering (ActionGate legacy tree)','Reference mechanism that mints a per-action, scoped, single-use credential the agent never holds — least-privilege tool access.','No','IMPLEMENTED (reference; not a packaged module)']],
 widths=[0.28,0.44,0.11,0.17]),
)

# ============================ 7. EVIDENCE CLASSES ============================
add(
H1('7. Evidence classes and provenance','sec7'),
P('The single most important epistemic control is that evidence never collapses into one undifferentiated Boolean claim. Each claim carries its class and provenance so that a downstream decision receives the epistemic status it needs to decide admissibility for the requested action.'),
TABLE('Table 4. Mandatory evidence classes.',
 ['Class','Definition','Example','Permitted use is explicit'],
 [['OBSERVED','Direct sensor capture','Vehicle image at Junction 44','May support direct presence if sensor requirements pass'],
  ['RECORDED','State from an authoritative operational system','Signal controller = RED at 14:08:23','May support signal condition when integrity / time binding passes'],
  ['MODEL_DERIVED','Output of a learned model','Plate = DXB-12345, confidence 99.1%','Subject to model authority and threshold'],
  ['CALCULATED','Deterministic computation from inputs','Travel time = 163 s','Subject to input provenance and algorithm version'],
  ['INFERRED','Probabilistic conclusion across evidence','Same vehicle likely at Junction 39 and 44','Must preserve confidence and inference method'],
  ['HUMAN_ASSERTED','Human-entered finding or annotation','Officer marks plate unreadable','Requires identity / role provenance'],
  ['EXTERNAL_ATTESTED','Claim supplied by another trusted authority','Registry ownership response','Requires source trust and purpose authorization']],
 widths=[0.16,0.26,0.3,0.28]),
H2('7.1 Evidence envelope'),
P('Every governed evidence item is carried in an envelope that preserves provenance and epistemic status rather than a flattened statement such as “vehicle violated signal.” In the current architecture, RA-5 is the component that admits an item into the trusted set — verifying provenance, integrity (content hash), freshness and schema — before any control may treat it as satisfied.'),
TABLE('Table 5. Evidence envelope fields (business-readable; not an internal schema).',
 ['Field group','Contents'],
 [['Identity','evidence_id, case_id, source_system, source_id'],
  ['Time','observed_at, ingested_at, clock-quality flags'],
  ['Integrity','content_hash, signature, source identity'],
  ['Model / algorithm','model_id, model_version, algorithm_version, confidence (where applicable)'],
  ['Epistemics','evidence_class, direct_or_inferred, parent_evidence_ids'],
  ['Governance','retention_class, purpose_binding, tenant / jurisdiction, quality_flags']],
 widths=[0.24,0.76]),
H2('7.2 Preserving direct versus inferred history'),
P('Because evidence class is preserved, policy can authorize a citation at Junction 44 on direct camera and controller evidence while explicitly denying a claim that a violation occurred at Junction 39 — or denying use of the inferred route for an unrelated investigation. A client should be able to see exactly why one evidence package permits a Junction 44 citation yet remains insufficient to assert a separate violation at Junction 39.'),
TABLE('Table 6. One incident, three evidence strengths.',
 ['Item','Evidence','Class / confidence'],
 [['Junction 44','Camera image + controller RED state; plate 99.1%','OBSERVED + RECORDED + MODEL_DERIVED'],
  ['Junction 39','Partial camera match','MODEL_DERIVED + INFERRED, identity 71%'],
  ['Route 39 → 44','Most probable route from road graph + timing','INFERRED, route 87%']],
 widths=[0.22,0.48,0.3]),
)

# ============================ 8. POLICY / RISK / DECISION / AUTHORITY ============================
add(
H1('8. Policy, risk, decision and authority — kept separate','sec8'),
P('The canonical spine threads the participating modules so that no component both proposes and authorizes. Intelligence proposes; RA-5 admits evidence; Decision Authority binds a decision; Model Authority confirms model eligibility; Risk Authority mints the single signed authorization; ActionGate enforces the exact action; Action Clearance checks live safety; Agent Runtime executes; and the RA assurance family verifies attempt, execution and effect.'),
DIAG('lifecycle','Figure 3. The canonical evidence-to-decision-to-action-to-effect spine, with the fail-closed disposition column. Only the signed Risk Authority envelope is machine authority.'),
H2('8.1 Authority must be separate from capability'),
P('The presence of data, or a technical ability to query it, must never constitute authorization. A system capable of reconstructing seven days of travel may still be authorized for only ±30 minutes around a specific traffic event. In the repository this is enforced structurally: Decision Authority bars the AI as an authorizing principal; the only machine authority is a signed, scoped, time-limited Risk Authority envelope; and ActionGate promotes uncertainty to INDETERMINATE, never to AUTHORIZED.'),
H2('8.2 Where policy actually lives today'),
P('It is important to be precise about policy. The repository implements a ',b('Policy Workflow Compiler'),' — tooling that compiles a reviewed, structured policy pack into a deterministic governed-workflow definition and an assurance manifest, and that rejects self-approval. There is ',b('no'),' “Policy Center”, “Policy Authority” or “Policy & Compliance Center” component in the codebase today; those appear only in an internal strategy design note. Binding evaluation of controls into machine authority is Risk Authority’s non-compensatory gate, not a policy engine.'),
NOTE('The Policy Workflow Compiler describes and compiles policy; a human-approval record ratifies release; Risk Authority evaluates trusted control results into the one signed authority. The Policy Center must never manufacture evidence, attest its own evidence, authorize execution, issue credentials, or bypass Decision Authority or ActionGate. The broader “Policy & Compliance Center” evolution (design-time / deployment-time / runtime / post-execution compliance evaluation) is DESIGN-ONLY today — see Section 21.', kind='warn', title='Policy: implemented tooling vs. design-only evolution'),
)

# ============================ 9. MODEL & WORKFLOW ELIGIBILITY ============================
add(
H1('9. Model and workflow eligibility','sec9'),
P('Vehicle intelligence depends on many learned models. A newly deployed or retrained model must not automatically acquire enforcement authority merely because it performs well technically. In the current architecture this is owned by ',b('Model Authority'),', which returns a binding ModelAuthorizationDecision (ALLOW / DENY / HOLD / ESCALATE) for a specific decision class.'),
TABLE('Table 7. Model-authority requirements.',
 ['Requirement','Example rule'],
 [['Model identity','Every governed output names an immutable model_id and model_version.'],
  ['Task eligibility','An ANPR model may be eligible for plate extraction and a re-ID model for candidate matching; neither implies authority to issue a fine.'],
  ['Decision-class approval','A model may be approved for investigative search but not automated enforcement.'],
  ['Jurisdiction / tenant approval','Approval may differ across municipalities, agencies or deployments.'],
  ['Confidence floor','Decision-specific thresholds apply; low-confidence results route to HOLD or human review.'],
  ['Validation status','Experimental, shadow, deprecated or revoked models cannot silently produce binding decisions.'],
  ['Change control','A material model / version change requires re-authorization before governed use.']],
 widths=[0.28,0.72]),
NOTE('Worked example: a Vehicle Re-ID v5.0 model is approved for INVESTIGATIVE_SEARCH only. A system request to issue a citation using it yields no eligible model for AUTOMATED_ENFORCEMENT, so Model Authority returns HOLD / ESCALATE and the citation does not execute. Deployment is not decision authority.', kind='note', title='Model eligibility in action'),
)

# ============================ 10. ACTIONGATE & CLEARANCE ============================
add(
H1('10. ActionGate and pre-execution enforcement','sec10'),
P('ActionGate is the pre-execution enforcement point. Given an action proposal and the supplied authority, policy, risk, evidence and decision context, it returns an explicit, machine-readable disposition. Crucially — and this corrects a common shorthand — ActionGate’s vocabulary is an ',b('authorization'),' vocabulary, distinct from the live-safety vocabulary of Action Clearance.'),
TABLE('Table 8. ActionGate disposition semantics (authorization).',
 ['Disposition','Meaning'],
 [['AUTHORIZED','All authority, policy, risk, evidence and scope conditions are satisfied for this exact action.'],
  ['AUTHORIZED_WITH_CONSTRAINTS','Authorized, subject to explicit constraints and obligations carried forward.'],
  ['DENIED','The action is prohibited or its prerequisites cannot be satisfied.'],
  ['INDETERMINATE','Uncertainty or an infrastructure failure — never promoted to AUTHORIZED (fail-closed).'],
  ['EXPIRED','The supplied authority is no longer valid.']],
 widths=[0.34,0.66]),
H2('10.1 Action Clearance'),
P('Authorization can become stale between decision time and execution time. Action Clearance is the final invariant check at the edge of execution. It verifies that the actual command still matches the case, authority, policy, target system, time-to-live and parameters that were authorized, and returns CLEAR / HOLD / BLOCK / ESCALATE. It may narrow, hold, escalate or block — it can never create or broaden authority.'),
BUL(
 'The case is still open and not revoked.',
 'The policy version remains applicable, or an approved grandfathering rule exists.',
 'Model authorization has not been revoked.',
 'Action type and target system match the authorized action.',
 'Vehicle identity, time window, geography and recipient parameters have not expanded.',
 'Human approval, when required, is present and bound to the same case / action digest.',
 'The action request has not expired or been replayed.',
),
NOTE('Plain-English takeaway: a high-confidence AI result is not enough by itself. Ugence separately checks evidence strength (RA-5), model approval (Model Authority), purpose and scope (DecisionCase), the signed authority (Risk Authority), exact-action authorization (ActionGate) and final runtime clearance (Action Clearance).', kind='note', title='Takeaway'),
)

# ============================ 11. AGENTIC INVESTIGATION ============================
add(
H1('11. Agentic investigation governance','sec11'),
P('If the vehicle solution evolves into an agentic architecture, every agent should propose actions through Ugence rather than recursively invoking tools without external authority. This matters because an investigative agent naturally expands its search whenever uncertainty remains. In the current architecture, Agent Runtime coordinates these agents and fails closed without a governance adapter; each proposed tool call is governed as a discrete action.'),
DIAG('agentic','Figure 4. Bounded agentic investigation: a capable agent is kept inside the authority granted to the case. Every consequential tool call is a governed proposal; scope expansion is a new decision.'),
P('An investigation agent can request another camera search, a wider temporal window, another geographic zone, registry resolution, disclosure to another agency, citation generation, or human review. Each consequential expansion becomes a separately governed proposal. The technical ability to perform a query is never treated as authority to perform it.'),
BUL(
 [b('Scope monotonicity. '),'Agents cannot widen time, geography, identity or data class without a new authorization event.'],
 [b('Least privilege. '),'A service receives only the tool and data permissions necessary for its current authorized action; the reference credential broker mints a per-action, scoped, single-use credential the agent never holds.'],
 [b('Sequence risk. '),'StoryGraph advises when individually-cleared steps assemble a prohibited capability (OBSERVE / ESCALATE), feeding human review — it never authorizes or denies by itself.'],
),
NOTE('An agent may technically be able to search the whole city for seven days, but the case may authorize only route-connected cameras within thirty minutes of the incident. Expanding the investigation becomes a new governed decision. Illustrative example.', kind='note', title='Takeaway'),
)

# ============================ 12. END-TO-END WORKFLOWS ============================
add(
H1('12. End-to-end governed workflows','sec12'),
H2('12.1 Workflow A — standard red-light citation'),
DIAG('redlight','Figure 5. The governed red-light citation workflow, with the fail-closed disposition column and the effect-verification close-out (illustrative).'),
NUM(
 'A camera detects a candidate red-light event and creates a source event ID.',
 'ANPR extracts the plate; the traffic controller supplies signal state; timestamps and location bindings are packaged as evidence.',
 'RA-5 admits the evidence: source identity, integrity, timestamp quality, minimum completeness and schema.',
 'A DecisionCase is created with purpose = TRAFFIC_VIOLATION_ENFORCEMENT and bounded scope.',
 'Model Authority verifies the ANPR (and any other) model versions are eligible for the decision class.',
 'Trusted control results feed Risk Authority, which mints the signed, scoped authorization envelope.',
 'ActionGate evaluates the exact action (ISSUE_TRAFFIC_CITATION) and returns AUTHORIZED / DENIED / INDETERMINATE with reason codes.',
 'On AUTHORIZED, Action Clearance binds the citation payload to the authorized case / action digest and returns CLEAR.',
 'The traffic system executes the notice and returns an execution receipt; RA-8 verifies the effect and the case lifecycle advances or closes.',
),
H2('12.2 Workflow B — trajectory reconstruction for investigation'),
NUM(
 'A triggering event creates an investigation-scoped DecisionCase.',
 'Permitted time and geography are established before any broad camera search.',
 'The trajectory service requests candidate camera searches as governed actions through Agent Runtime.',
 'Each result is classified by evidence class and confidence; inferred route segments remain explicit.',
 'Any request to widen the search window, access a new data class, or resolve a person identity becomes a new authorization decision.',
 'The investigator receives a timeline that visually and structurally separates direct observations from inferred transitions.',
 'Downstream use of the timeline is governed independently: investigation support does not automatically authorize enforcement.',
),
H2('12.3 Workflow C — uncertain identity'),
P('When identity confidence is below the binding threshold, the workflow does not force a single identity. For example, with plate confidence 82% and re-identification confidence 88% against a policy threshold of “plate ≥ 97% OR approved human corroboration”, ActionGate returns a non-authorizing disposition and the next permitted action is human review or the collection of additional admissible evidence — the ambiguity is preserved rather than resolved by fiat.'),
)

# ============================ 13. RUNTIME / EXECUTION / EFFECT ASSURANCE ============================
add(
H1('13. Runtime, execution and effect assurance','sec13'),
P('Governance does not end at authorization. The current architecture distinguishes four different records and reconciles them, so the enterprise can prove not just that an action was permitted but that what executed matched what was authorized.'),
DIAG('assurance','Figure 6. Authorization versus attempt versus execution versus effect, with the RA-7 / RA-8 reassessment signals feeding the RA-6 authority lifecycle.'),
TABLE('Table 9. Four distinct records in the execution lifecycle.',
 ['Record','What it captures','Owner (repository)'],
 [['Authorization','What was authorized — the signed, scoped envelope','Risk Authority'],
  ['Attempt','What command was attempted (a provider attempt)','Agent Runtime'],
  ['Receipt','What actually executed on the external system','Domain executor / external system'],
  ['Effect verification','What effect occurred, reconciled against the authorization (MATCHED / MISMATCH / PARTIAL)','RA-8 execution & effect assurance']],
 widths=[0.2,0.5,0.3]),
P('RA-7 assesses the in-flight trajectory; RA-8 reconciles the post-execution effect. Both emit neutral authority-reassessment signals to RA-6, which may revoke, advance the authority epoch, or expire authority. These signals ',b('restrict'),' authority; they never grant it, and RA-8 never retroactively authorizes an action. Verification strength is honestly bounded by the effect source: a provider self-report is not physical ground truth.'),
NOTE('Maturity note: the RA-5 → RA-8 packages are implemented and CI-verified at the library level, but they are not yet wired into a single running end-to-end enforcement path (RA-6 has no non-test write call sites today, and Risk Authority’s production envelope issuance is unimplemented). This briefing treats the mechanism as implemented and the end-to-end operational enforcement as PARTIAL — see Section 21.', kind='warn', title='Honest maturity'),
)

# ============================ 14. SECURITY / PRIVACY / ABUSE ============================
add(
H1('14. Security, privacy and abuse resistance','sec14'),
P('The controls below are governance safeguards. This document deliberately does not provide operational surveillance tactics beyond what is needed to explain those safeguards.'),
TABLE('Table 10. Security, privacy and abuse-resistance controls.',
 ['Control objective','Required behaviour'],
 [['Purpose limitation','Evidence retrieval and downstream use carry case / purpose context; secondary-use expansion requires new authority.'],
  ['Temporal & geographic bounds','Default ±N minutes and route-connected geography; extension is an exceptional, logged approval.'],
  ['Least privilege','Services receive only the tool / data permissions necessary for the current authorized action.'],
  ['Scope monotonicity','Agents cannot widen time, geography, identity or data class without a new authorization.'],
  ['Tenant / jurisdiction isolation','Cases, policies, evidence and authority grants remain scoped to the correct administrative boundary.'],
  ['Sensitive-identity separation','Vehicle identity, registered owner, driver face and passenger identity are separate, separately governed capabilities.'],
  ['Model-version control','Only eligible model versions produce binding decisions; revocation blocks new binding actions without redeployment.'],
  ['Registry-access control','Owner / registry resolution is a separately authorized capability, not a default.'],
  ['Anti-replay','Clearances are nonce / digest / expiry bound and cannot be reused for another action.'],
  ['Tamper evidence','Decision / action records use hashes / signatures; the signed authority envelope is Ed25519-bound.'],
  ['Emergency override','Overrides are explicit, time-bounded, attributable and post-reviewed.'],
  ['Revocation','Model, authority, policy or action grants can be revoked before execution (RA-6).'],
  ['Retention & deletion','Retention is set by evidence class, purpose and case status; derived data is handled explicitly.'],
  ['Appeal & correction','Contested evidence, corrected identity and revoked decisions are represented, not silently overwritten.'],
  ['Time-of-check / time-of-use','Action Clearance re-checks at the edge of execution to catch drift between decision and execution.']],
 widths=[0.3,0.7]),
)

# ============================ 15. SERVICENOW / ENTERPRISE INTEGRATION ============================
add(
H1('15. ServiceNow and enterprise integration','sec15'),
P('Ugence complements enterprise workflow and governance-risk-compliance (GRC) platforms such as ServiceNow; it does not replace them. A platform like ServiceNow can remain the system of record for policies, regulations, controls, cases, exceptions, incidents, remediation, dashboards and lifecycle workflows. Ugence provides the deeper, evidence-bound decision-time and execution-time controls for consequential agent actions.'),
NOTE('This is a neutral integration pattern, not a claim about a deployed integration. No ServiceNow (or other enterprise-platform) connector ships in the repository today; any such integration is PROPOSED.', kind='warn', title='Integration status'),
TABLE('Table 11. A neutral division of labour with an enterprise workflow / GRC platform.',
 ['The enterprise platform can own','Ugence provides'],
 [['Policies, regulations and control catalogues','Trusted evidence admission and control assurance (RA-5 / TAP)'],
  ['Cases, exceptions and incidents','The governed DecisionCase and the signed authority envelope'],
  ['Remediation and lifecycle workflows','Exact-action authorization, live clearance and controlled execution'],
  ['Dashboards and reporting','Execution / effect reconciliation and governed-value reporting'],
  ['System of record and audit store','A native evidence → decision → authority → action → effect trace']],
 widths=[0.5,0.5]),
)

# ============================ 16. DEPLOYMENT ============================
add(
H1('16. Deployment architecture and integration patterns','sec16'),
DIAG('deploy','Figure 7. Deployment pattern: Ugence governance services sit between vehicle-intelligence services and city operational systems; an enterprise GRC platform can remain the system of record.'),
TABLE('Table 12. Integration patterns and their governance characteristics.',
 ['Pattern','Use','Governance characteristic'],
 [['Synchronous API gate','Before a citation, registry lookup, camera search or disclosure','Strong runtime prevention; preferred for consequential actions.'],
  ['Sidecar / service proxy','Intercept selected agent / tool calls','Central policy with low application coupling.'],
  ['Event-driven evaluation','Evaluate evidence / cases from a message bus','Good for asynchronous case workflows and HOLD / escalation.'],
  ['Shadow mode','Observe decisions without blocking','Useful for policy calibration and pilot evidence.'],
  ['Batch assurance','Post-process historical cases','Useful for audit analytics — not a substitute for runtime gating.']],
 widths=[0.24,0.4,0.36]),
H2('16.1 Non-functional requirements'),
TABLE('Table 13. Non-functional requirements.',
 ['ID','Requirement','Target / interpretation'],
 [['NFR-01','Availability','Governance services match the criticality tier of the governed action path.'],
  ['NFR-02','Fail behaviour','Consequential actions fail closed on missing policy, invalid authority or unverifiable clearance.'],
  ['NFR-03','Latency','Runtime-gate latency fits the operational SLO and is measured separately from computer-vision inference.'],
  ['NFR-04','Determinism','Given the same signed inputs, policy version, authority state and model-eligibility state, ActionGate produces reproducible dispositions.'],
  ['NFR-05','Audit durability','Decision / action records are append-only or versioned and recoverable.'],
  ['NFR-06','Explainability','Every non-trivial disposition includes reason codes and references to the evaluated rules / evidence.'],
  ['NFR-07','Isolation','Tenant / jurisdiction boundaries are enforced at storage, policy, authority and runtime layers.'],
  ['NFR-08','Versioning','Policies, schemas, models and governance contracts are versioned with compatibility controls.'],
  ['NFR-09','Observability','Metrics for decision volume, deny / hold / escalate rates, latency, evidence quality and policy misses.'],
  ['NFR-10','Scalability','Bursty event volume is supported without bypassing governance under load.']],
 widths=[0.1,0.24,0.66]),
)

# ============================ 17. FAILURE MODES ============================
add(
H1('17. Failure modes and fail-closed behaviour','sec17'),
P('The system treats uncertainty as a reason to stop, not a reason to proceed. Each failure mode has a defined, fail-closed response.'),
TABLE('Table 14. Failure modes and required responses.',
 ['Failure mode','Required response','Rationale'],
 [['Missing controller evidence','HOLD or DENY the enforcement action','Do not substitute inferred signal state for a required direct record.'],
  ['Clock skew beyond tolerance','HOLD','Event correlation may be invalid.'],
  ['Low ANPR confidence','HOLD / human review','Identity is not sufficiently established.'],
  ['Conflicting camera identity matches','HOLD / investigate','Preserve ambiguity rather than forcing a single identity.'],
  ['Model version not authorized','DENY (no eligible model)','Deployment does not imply decision authority.'],
  ['Policy unavailable or invalid','DENY / HOLD, fail closed','No implicit default authorization.'],
  ['Authority expired or revoked','DENY','No stale approvals.'],
  ['Action parameters differ from the approved case','DENY clearance','Prevents last-mile scope drift.'],
  ['Agent requests broader surveillance scope','ESCALATE or DENY','Expansion requires separate authority.'],
  ['Audit persistence failure for a binding action','HOLD where policy requires a durable record','Do not create unauditable enforcement effects.']],
 widths=[0.3,0.3,0.4]),
)

# ============================ 18. KPIs / GOVERNED VALUE ============================
add(
H1('18. KPIs, acceptance criteria and governed value','sec18'),
TABLE('Table 15. Acceptance criteria.',
 ['Category','Metric / acceptance criterion'],
 [['Evidence integrity','100% of governed evidence has source identity, timestamp, class and immutable reference.'],
  ['Inference transparency','100% of inferred trajectory segments are distinguishable from direct observations.'],
  ['Model control','0 binding actions from models not eligible for the applicable decision class.'],
  ['Purpose / scope','0 unauthorized temporal / geographic / data-class expansions in the controlled test suite.'],
  ['Action control','100% of consequential external actions require a valid ActionGate disposition and clearance where configured.'],
  ['Reasonability','Every DENIED / HOLD / INDETERMINATE / ESCALATE carries stable reason codes.'],
  ['Anti-replay','Replayed or expired clearances are rejected.'],
  ['Auditability','A reviewer can reconstruct evidence → policy → authority → action → effect for sampled cases without relying on application logs alone.'],
  ['Human review','Configured review-required scenarios cannot bypass human authority.'],
  ['Operational overhead','Measured governance latency and availability meet deployment SLOs without weakening fail-closed behaviour.']],
 widths=[0.26,0.74]),
H2('18.1 Governed value'),
P('Ugence includes an experimental Governed Value capability that reports the net governed value and ROI of a governed workflow — for example, connecting an approved objective (reduce unsafe red-light running), governed-execution evidence, attributable cost and observed outcomes. In the current repository these outputs are explicitly ',b('reported and unverified'),', with no authority binding and no continuous integration; they support pilot analytics, not automated decisions.'),
NOTE('Governed Value is an experimental reporting kernel (REPORTED / UNVERIFIED). It does not attest outcomes, does not grant authority, and must not be read as an audited financial result.', kind='note', title='Governed Value maturity'),
)

# ============================ 19. RED-LIGHT CASE ============================
add(
H1('19. Illustrative red-light violation case','sec19'),
NOTE('Illustrative only. Identifiers and values are fictional and do not represent any real vehicle, person or deployment.', kind='warn'),
H2('19.1 Input facts'),
TABLE('Table 16. Input facts and evidence classes.',
 ['Item','Value','Evidence class'],
 [['Camera J44 sighting','White SUV; plate image available','OBSERVED'],
  ['ANPR plate','DXB-12345; 99.1%','MODEL_DERIVED'],
  ['Signal controller','RED at 14:08:23.441','RECORDED'],
  ['Camera J39 candidate','Possible same SUV; partial plate; 71% identity','MODEL_DERIVED / INFERRED'],
  ['Route J39 → J44','Most probable route; 87%','INFERRED'],
  ['Re-ID model','v5.2, approved for investigative matching','Model-authority fact'],
  ['ANPR model','v3.7, approved for enforcement plate extraction','Model-authority fact']],
 widths=[0.26,0.46,0.28]),
H2('19.2 Policy'),
P('Automated citation requires direct camera evidence at the violation intersection, direct / authoritative controller-state evidence, time binding within the configured skew tolerance, plate confidence ≥ 97%, an eligible ANPR model, and no unresolved identity conflict. Trajectory inference is not required for this citation and may not be used to assert additional violations without separate evidence.'),
H2('19.3 Governed outcome'),
TABLE('Table 17. The same incident, evaluated action by action.',
 ['Proposed action','Disposition','Reason'],
 [['Issue citation for Junction 44','AUTHORIZED → CLEAR','Direct evidence + signal record + 99.1% plate + eligible model + valid authority.'],
  ['Assert vehicle violated Junction 39','DENIED','No admissible direct violation evidence; only low-confidence identity inference.'],
  ['Search prior 30 minutes on route-connected cameras','AUTHORIZED if case scope permits','Investigation is bounded to purpose / time / geography.'],
  ['Search all city cameras for the prior 7 days','ESCALATE / DENIED','Exceeds standard case scope; requires separate authority.'],
  ['Resolve registered owner for delivery','AUTHORIZED only under explicit identity-resolution authority','Registry capability is separately governed.'],
  ['Run driver-face identification','DENIED under ordinary traffic-case policy','Not necessary or authorized for the stated purpose.']],
 widths=[0.34,0.28,0.38]),
P(b('Takeaway. '),'The same evidence can legitimately support one action and not another. Direct evidence supports the Junction 44 citation, while an uncertain earlier match may aid investigation but is insufficient to assert another violation — each proposed use of the evidence is evaluated independently.'),
)

# ============================ 20. ROADMAP ============================
add(
H1('20. Phased pilot and implementation roadmap','sec20'),
P('Autonomy is earned step by step; live controlled execution is not enabled until dry-run, exception-path and receipt checks pass. No broad production autonomy is promised at pilot start.'),
DIAG('roadmap','Figure 8. A phased adoption roadmap from discovery to full assurance.'),
TABLE('Table 18. Phase exit criteria.',
 ['Phase','Exit criterion'],
 [['0 · Discovery','Governance boundary and action inventory approved.'],
  ['1 · Shadow governance','Disposition quality validated against historical / live review.'],
  ['2 · Low-risk runtime gates','No bypass paths; latency and fail behaviour accepted.'],
  ['3 · Enforcement gate','End-to-end evidence / authority / action tests pass.'],
  ['4 · Agent governance','Scope-expansion and privilege-escalation adversarial tests pass.'],
  ['5 · Assurance & optimization','Production assurance SLOs and audit KPIs sustained.']],
 widths=[0.32,0.68]),
)

# ============================ 21. CURRENT VS FUTURE ============================
add(
H1('21. Current capability versus future evolution','sec21'),
P('This section states plainly what is implemented today on the default branch and what is design-stage or future, so that no reader mistakes a design or a passing test for a deployment.'),
TABLE('Table 19. Current implemented capabilities (default-branch tip).',
 ['Capability','Repository module','Maturity'],
 [['Neutral governance contracts + provider framework','governance-contracts, governance-provider-framework','IMPLEMENTED + CI'],
  ['Trusted evidence admission + control assurance','risk-authority-evidence-runtime (RA-5), tap','IMPLEMENTED + CI (library); integration PARTIAL'],
  ['Binding decision + DecisionCase + CER','decision-authority','IMPLEMENTED + CI'],
  ['Model authority','model-selection (Model Authority)','IMPLEMENTED (no dedicated CI)'],
  ['Signed authorization envelope (sole authority)','risk_authority','IMPLEMENTED + CI (spine); production issuance PARTIAL'],
  ['Exact-action authorization','actiongate','IMPLEMENTED + CI'],
  ['Live-safety clearance','action-clearance','IMPLEMENTED (no dedicated CI)'],
  ['Governed execution runtime','agent-runtime','IMPLEMENTED + CI'],
  ['Runtime / execution / effect assurance + authority lifecycle','risk-authority-runtime-assurance (RA-7), risk-authority-execution-assurance (RA-8), risk-authority-status-runtime (RA-6), risk-authority-runtime','IMPLEMENTED + CI (library); end-to-end enforcement PARTIAL'],
  ['Sequence-risk advisory','storygraph','IMPLEMENTED (reference; synthetic-only)'],
  ['Policy compilation tooling','policy-workflow-compiler','IMPLEMENTED + CI (offline)'],
  ['Context minimization + token accounting','context-minimization (+ runtime integration)','IMPLEMENTED + CI'],
  ['Agent workforce planning','agent-workforce-composer','IMPLEMENTED + CI (offline)'],
  ['Governed-value reporting','governed-value','IMPLEMENTED (experimental; reported-only; no CI)'],
  ['Per-action credential brokering','ActionGate legacy tree (not a package)','IMPLEMENTED (reference)']],
 widths=[0.34,0.44,0.22]),
TABLE('Table 20. Design-only and future capabilities (NOT implemented — not to be read as available).',
 ['Capability','Status','Evidence'],
 [['Policy & Compliance Center / adaptive-compliance lifecycle (design/deploy/runtime/post-execution)','DESIGN-ONLY','Internal strategy note; only the Policy Workflow Compiler is implemented.'],
  ['End-to-end operational RA-5 → RA-8 enforcement path','PARTIAL','Libraries + CI exist; not wired into a running enforcement path (no non-test RA-6 writers; production envelope issuance unimplemented).'],
  ['Ugence Value Intelligence (GV-2C / GV-2E / GV-3R)','DESIGN-ONLY','Draft pull request (design only); not merged.'],
  ['Document / PDF policy ingestion, OCR, formal verification / proof','MISSING / FUTURE','Named as the largest true gaps in internal strategy.'],
  ['Credential Broker as a first-class package; agent / workload identity','DESIGN-ONLY / FUTURE','Reference broker exists only in the ActionGate legacy tree.'],
  ['Live-cluster / production validation; CI for Action Clearance, Model Authority, Governed Value','FUTURE','Not present on the default branch today.']],
 widths=[0.36,0.16,0.48]),
NOTE('A design document is not implementation; a passing unit test is not a real-world deployment; a verification receipt is not execution authority; and a compliance evaluation is not a mathematical proof unless a genuine formal method is used. This briefing holds to those distinctions throughout.', kind='warn', title='Evidence discipline'),
)

# ============================ 22. REQUIREMENT CATALOGUE ============================
add(
H1('22. Appendix A — Requirement catalogue','sec22'),
TABLE('Table 21. Normative requirement catalogue.',
 ['ID','Normative requirement'],
 [['REQ-EV-001','The system SHALL preserve the evidence class for every claim used in a governed decision.'],
  ['REQ-EV-002','The system SHALL retain provenance linkage from derived / inferred evidence to parent evidence.'],
  ['REQ-EV-003','The system SHALL represent confidence and quality flags without converting uncertainty to a Boolean fact.'],
  ['REQ-EV-004','The system SHALL validate configured timestamp-skew bounds before time-sensitive correlation is admissible.'],
  ['REQ-DC-001','Every consequential action SHALL reference an active DecisionCase.'],
  ['REQ-DC-002','A DecisionCase SHALL define purpose and bounded scope before broad retrieval actions are authorized.'],
  ['REQ-DC-003','Scope expansion SHALL require a new or amended authorization event.'],
  ['REQ-MA-001','Every model-derived governed evidence item SHALL identify model_id and model_version.'],
  ['REQ-MA-002','A model SHALL NOT be binding for a decision class unless an active eligibility record permits it.'],
  ['REQ-MA-003','Model revocation SHALL prevent new binding actions without requiring application redeployment.'],
  ['REQ-AU-001','Decision authority SHALL be explicit and separable from the proposing service.'],
  ['REQ-AG-001','ActionGate SHALL return one of AUTHORIZED / AUTHORIZED_WITH_CONSTRAINTS / DENIED / INDETERMINATE / EXPIRED plus reason codes.'],
  ['REQ-AG-002','Missing or invalid governance prerequisites SHALL NOT default to AUTHORIZED.'],
  ['REQ-AC-001','Configured consequential actions SHALL pass Action Clearance (CLEAR) immediately before execution.'],
  ['REQ-AC-002','Clearance SHALL bind action type, subject, parameters, target, case, authority and expiry.'],
  ['REQ-AC-003','Expired, replayed or parameter-modified action requests SHALL be rejected.'],
  ['REQ-AR-001','Agent tool calls that access cameras, registry, sensitive identities, disclosures or enforcement SHALL be governable actions.'],
  ['REQ-AR-002','An agent SHALL NOT broaden temporal / geographic scope solely because additional search may improve confidence.'],
  ['REQ-AS-001','Binding decisions SHALL record policy version, evidence references, model eligibility and authority provenance.'],
  ['REQ-AS-002','Execution receipts and effect verification SHALL link actual external effects back to the authorized action.'],
  ['REQ-PR-001','Retention SHALL be determined by evidence class, purpose and case status.'],
  ['REQ-PR-002','Vehicle identity, owner identity, driver identity and passenger identity SHALL be separately governable capabilities.'],
  ['REQ-SEC-001','Cross-tenant or cross-jurisdiction evidence / action references SHALL be denied unless explicitly authorized.'],
  ['REQ-SEC-002','Emergency overrides SHALL be attributable, time-bounded and auditable.'],
  ['REQ-OPS-001','Governance bypass due to service overload SHALL be prohibited for binding actions.'],
  ['REQ-OPS-002','Governance-service health and disposition metrics SHALL be observable independently from vehicle-inference metrics.']],
 widths=[0.16,0.84]),
)

# ============================ 23. DATA MODEL / API ============================
add(
H1('23. Appendix B — Data model and illustrative contracts','sec23'),
P('The core entities below are business-readable roles, not internal schemas. Field names are illustrative and align with the current governance-contracts vocabulary where applicable.'),
TABLE('Table 22. Core entities.',
 ['Entity','Role'],
 [['Evidence','Provenanced sensor / model / derived / inferred item.'],
  ['EvidenceAssessment','RA-5 admission result, quality flags, admissibility by decision class.'],
  ['VehicleHypothesis','Candidate vehicle identity and cross-camera match confidence.'],
  ['TrajectorySegment','From / to locations, times, route basis, direct / inferred status, confidence.'],
  ['DecisionCase','Canonical, immutable / versioned purpose / scope / evidence / policy / authority container (owns the CER).'],
  ['ModelAuthorization','Model / version / task / decision-class eligibility record.'],
  ['RiskAuthorizationEnvelope','The signed, scoped, time-limited machine authority.'],
  ['ActionGovernanceResult','AUTHORIZED / AUTHORIZED_WITH_CONSTRAINTS / DENIED / INDETERMINATE / EXPIRED + reason codes.'],
  ['ClearanceResult','CLEAR / HOLD / BLOCK / ESCALATE + binding digest, expiry and anti-replay fields.'],
  ['ExecutionReceipt','Target-system result, timestamp, external ID and returned evidence.'],
  ['EffectAssuranceAssessment','MATCHED / MISMATCH / PARTIAL / UNKNOWN reconciliation of the observed effect.']],
 widths=[0.28,0.72]),
H2('23.1 Illustrative ActionGate request'),
P('A conceptual request to evaluate an exact action (field names illustrative): action_type = ISSUE_TRAFFIC_CITATION; target_system = CITY_TRAFFIC_ENFORCEMENT; subject = { vehicle_plate: DXB-12345 }; evidence_refs = [ EV-CAM-44, EV-SIGNAL-44, EV-ANPR-44 ]; decision_ref = DC-983274; action_parameters = { junction: J44, event_time: 14:08:23.441 }.'),
H2('23.2 Illustrative response'),
P('A conceptual authorization result: disposition = AUTHORIZED; reason_codes = [ DIRECT_SIGNAL_EVIDENCE_OK, ANPR_THRESHOLD_MET, MODEL_ELIGIBLE, AUTHORITY_VALID ]; policy_version = TrafficViolationPolicy-2026.4; decision_digest = sha256:…; clearance_required = true; expires_at = … . Note that AUTHORIZED is an authorization result, not an execution: Action Clearance and the runtime still stand between it and any effect.'),
)

# ============================ 24. GLOSSARY ============================
add(
H1('24. Appendix C — Glossary','sec24'),
TABLE('Table 23. Glossary of terms and acronyms.',
 ['Term','Definition'],
 [['ANPR / ALPR','Automatic Number-Plate Recognition / Automatic License-Plate Recognition.'],
  ['Re-identification (re-ID)','Matching the same vehicle across different cameras and views.'],
  ['RA-5','Trusted Evidence Admission (risk-authority-evidence-runtime): admits only provenance-, integrity-, freshness- and schema-verified evidence.'],
  ['TAP','Trusted Assertion / control-support Provider: evaluates whether an assertion is supported by evidence.'],
  ['DecisionCase','The canonical, immutable / versioned container binding purpose, scope, evidence, models, policy, authority and disposition.'],
  ['CER','Context Envelope Record: the governance context record owned by Decision Authority.'],
  ['Model Authority','The capability that authorizes which model version may act in a decision class (repository distribution: ugence-model-selection).'],
  ['Risk Authority','Mints the signed Ed25519 RiskAuthorizationEnvelope — the sole machine authority.'],
  ['ActionGate','Pre-execution enforcement: returns AUTHORIZED / AUTHORIZED_WITH_CONSTRAINTS / DENIED / INDETERMINATE / EXPIRED.'],
  ['Action Clearance','Live-safety check at the edge of execution: returns CLEAR / HOLD / BLOCK / ESCALATE.'],
  ['Agent Runtime','Coordinates governed execution; fails closed without a governance adapter.'],
  ['RA-6 / RA-7 / RA-8','Authority lifecycle (revoke / epoch / expire) / in-flight trajectory assurance / post-execution effect assurance.'],
  ['StoryGraph','Advisory sequence-risk analyzer (OBSERVE / ESCALATE).'],
  ['GRC','Governance, Risk and Compliance (e.g. an enterprise workflow platform such as ServiceNow).'],
  ['IMPLEMENTED + CI','Merged to the default branch with its own tests run in continuous integration.'],
  ['REFERENCE / DESIGN-ONLY / FUTURE','A reference implementation not wired into the control plane / a design with no running code / proposed and not yet built.']],
 widths=[0.24,0.76]),
P(i('End of document. This is a conceptual reference architecture grounded in the current Ugence repository at the default-branch tip; it is not legal advice and does not represent an existing deployment.')),
)
