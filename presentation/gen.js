/* Ugence + ServiceNow presentation generator — native editable shapes/connectors. */
const P = require('pptxgenjs');
const pptx = new P();
pptx.layout = 'LAYOUT_WIDE';           // 13.33 x 7.5
pptx.title = 'Ugence + ServiceNow — Detailed Architecture and Use-Case Briefing';
pptx.subject = 'Proposed independent action-level authority for governed ServiceNow agentic workflows';
pptx.author = 'Rakesh Mohan, Founder, Ugence Labs';
pptx.company = 'Ugence Labs';
pptx.revision = '2';
const DOC_TITLE = 'Ugence + ServiceNow — Detailed Architecture and Use-Case Briefing';
const OUT = 'UGENCE_SERVICENOW_ARCHITECTURE_AND_USE_CASE_BRIEFING';

const W = 13.33, H = 7.5;
const TITLE='Cambria', BODY='Calibri';

// palette
const INK='1E2340', NAVY='16143A', MUTED='6B7280', ARROW='4B5563', HAIR='D8DEE9';
const VIOLET='5145C7', VIOLET_LT='ECEAFB', VIOLET_DK='2A2170';
const TEAL='2B6CB0', TEAL_LT='E4EFF7', TEAL_DK='173A5A';
const GREEN='2E7D5B', GREEN_LT='E7F3EC', GREEN_DK='14532D';
const GREY='6B7280', GREY_LT='EEF1F4', GREY_DK='374151';
const AMBER='B7791F', AMBER_LT='FBF1DD', AMBER_DK='6B4A12';
const RED='C0392B', RED_LT='FBEBE9', RED_DK='7A2016';

const CAT = {
  SNOW:{fill:GREEN_LT,line:GREEN,font:GREEN_DK},
  UDEC:{fill:VIOLET_LT,line:VIOLET,font:VIOLET_DK},
  UEXE:{fill:TEAL_LT,line:TEAL,font:TEAL_DK},
  EXT :{fill:GREY_LT,line:GREY,font:GREY_DK},
  STOP:{fill:RED_LT,line:RED,font:RED_DK},
  HUMAN:{fill:AMBER_LT,line:AMBER,font:AMBER_DK},
};
const BADGE = {
  'IMPLEMENTED':GREEN,'PILOT PENDING':AMBER,'UNDER DEVELOPMENT':TEAL,'PROPOSED INTEGRATION':VIOLET,
  'REFERENCE-GRADE':GREY,'ANNOUNCED / FUTURE':'D97706','DESIGN-ONLY':GREY,'SHIPPED':GREEN,'PROPOSED':VIOLET,
};

function sh(){ return {type:'outer',color:'8A94A6',blur:4,offset:1.5,angle:90,opacity:0.28}; }

const DECK=[];
function slide(dark){ const s=pptx.addSlide(); s.background={color: dark?NAVY:'FFFFFF'};
  s._ops=[]; s._dark=!!dark; s._addText=s.addText.bind(s); s._addShape=s.addShape.bind(s); s._addTable=s.addTable.bind(s);
  DECK.push(s); return s; }
// recording wrappers — snapshot (deep-clone) BEFORE pptxgenjs mutates opts to EMU in place
function clone(o){ return o==null?o:JSON.parse(JSON.stringify(o)); }
function T(s,text,opts){ s._ops.push({k:'text',text:clone(text),opts:clone(opts)||{}}); return s._addText(text,opts); }
function SH(s,type,opts){ if(type!==pptx.ShapeType.line) s._ops.push({k:'shape',type,opts:clone(opts)||{}}); return s._addShape(type,opts); }
function TB(s,rows,opts){ s._ops.push({k:'table',rows:clone(rows),opts:clone(opts)||{}}); return s._addTable(rows,opts); }

function header(s,kicker,title,titleColor){
  T(s,kicker.toUpperCase(),{x:0.6,y:0.34,w:12.1,h:0.28,fontFace:BODY,fontSize:11,bold:true,color:VIOLET,charSpacing:2,align:'left'});
  T(s,title,{x:0.58,y:0.6,w:12.15,h:0.72,fontFace:TITLE,fontSize:26,bold:true,color:titleColor||INK,align:'left'});
}
function footnote(s,txt){
  T(s,txt,{x:0.6,y:7.06,w:11.55,h:0.3,fontFace:BODY,fontSize:8.5,italic:true,color:MUTED,align:'left'});
}
function badge(s,x,y,label,w){
  const c=BADGE[label]||GREY;
  const ww=w|| (0.16+label.length*0.072);
  SH(s,pptx.ShapeType.roundRect,{x,y,w:ww,h:0.26,rectRadius:0.13,fill:{color:c},line:{color:c,width:0}});
  T(s,label,{x,y,w:ww,h:0.26,fontFace:BODY,fontSize:8,bold:true,color:'FFFFFF',align:'center',valign:'middle',margin:0});
  return ww;
}
function node(s,x,y,w,h,text,cat,opts){
  opts=opts||{}; const c=CAT[cat];
  SH(s,pptx.ShapeType.roundRect,{x,y,w,h,rectRadius:0.07,fill:{color:c.fill},line:{color:c.line,width:1.5},shadow:sh()});
  T(s,text,{x:x+0.03,y,w:w-0.06,h,align:'center',valign:'middle',fontFace:BODY,fontSize:opts.fs||10.5,bold:opts.bold!==false,color:c.font,margin:1,lineSpacingMultiple:0.92});
}
function cyl(s,x,y,w,h,text,cat,opts){
  opts=opts||{}; const c=CAT[cat];
  SH(s,pptx.ShapeType.can,{x,y,w,h,fill:{color:c.fill},line:{color:c.line,width:1.5},shadow:sh()});
  T(s,text,{x:x+0.03,y:y+0.06,w:w-0.06,h:h-0.08,align:'center',valign:'middle',fontFace:BODY,fontSize:opts.fs||10,bold:true,color:c.font,margin:1,lineSpacingMultiple:0.92});
}
function seg(s,x1,y1,x2,y2,opts){
  opts=opts||{};
  s._ops.push({k:'line',x1,y1,x2,y2,color:opts.color||ARROW,width:opts.width||1.75,dash:opts.dash,arrow:opts.arrow!==false});
  const x=Math.min(x1,x2),y=Math.min(y1,y2),w=Math.max(Math.abs(x2-x1),0.001),h=Math.max(Math.abs(y2-y1),0.001);
  SH(s,pptx.ShapeType.line,{x,y,w,h,flipH:x2<x1,flipV:y2<y1,line:{color:opts.color||ARROW,width:opts.width||1.75,dashType:opts.dash||'solid',endArrowType:opts.arrow===false?'none':'triangle'}});
}
function alabel(s,x1,y1,x2,y2,label,opts){
  if(!label)return; opts=opts||{}; const mx=(x1+x2)/2,my=(y1+y2)/2,w=opts.w||1.9;
  T(s,label,{x:mx-w/2,y:my-(opts.h?opts.h/2:0.13),w,h:opts.h||0.26,fontFace:BODY,fontSize:opts.fs||8,italic:true,color:opts.color||MUTED,align:'center',valign:'middle',fill:{color:'FFFFFF'},margin:1,lineSpacingMultiple:0.9});
}
function conn(s,x1,y1,x2,y2,label,opts){ seg(s,x1,y1,x2,y2,opts); alabel(s,x1,y1,x2,y2,label,opts); }

// vertical flow in a column; nodes:[{t,cat,arrow,h,fs}]
function flow(s,cx,y0,bw,nodes,gap){
  gap=gap||0.44; let y=y0; const pos=[];
  nodes.forEach(n=>{ const h=n.h||0.5; node(s,cx-bw/2,y,bw,h,n.t,n.cat,{fs:n.fs,bold:n.bold}); pos.push({cx,x:cx-bw/2,y,w:bw,h,top:y,bot:y+h,mid:y+h/2}); y+=h+gap; });
  for(let i=0;i<pos.length-1;i++){ conn(s,cx,pos[i].bot,cx,pos[i+1].top,nodes[i].arrow,{w:nodes[i].lw||2.1}); }
  return pos;
}
function legend(s,x,y,items){ // items:[[label,cat]...]
  let cx=x;
  items.forEach(it=>{ const c=CAT[it[1]];
    SH(s,pptx.ShapeType.roundRect,{x:cx,y:y+0.02,w:0.22,h:0.16,rectRadius:0.03,fill:{color:c.fill},line:{color:c.line,width:1}});
    T(s,it[0],{x:cx+0.28,y:y-0.03,w:it[2]||1.7,h:0.26,fontFace:BODY,fontSize:8.5,color:INK,align:'left',valign:'middle',margin:0});
    cx += 0.28 + (it[2]||1.7) + 0.15;
  });
}
function card(s,x,y,w,h,o){
  SH(s,pptx.ShapeType.roundRect,{x,y,w,h,rectRadius:0.06,fill:{color:o.fill||'FFFFFF'},line:{color:o.line||HAIR,width:1},shadow:sh()});
  T(s,o.title,{x:x+0.18,y:y+0.12,w:w-0.36,h:0.34,fontFace:BODY,fontSize:o.tfs||12.5,bold:true,color:o.tcolor||VIOLET_DK,align:'left',valign:'middle',margin:0});
  if(o.badge){ badge(s,x+w-(o.badgeW||1.55)-0.16,y+0.14,o.badge,o.badgeW); }
  T(s,o.body,{x:x+0.18,y:y+0.5,w:w-0.36,h:h-0.62,fontFace:BODY,fontSize:o.bfs||9.5,color:INK,align:'left',valign:'top',margin:0,lineSpacingMultiple:1.02});
}
function divider(sectionNo,title,sub){
  const s=slide(true);
  SH(s,pptx.ShapeType.rect,{x:0,y:0,w:W,h:H,fill:{color:NAVY},line:{width:0}});
  T(s,sectionNo,{x:0.9,y:2.4,w:3,h:1,fontFace:TITLE,fontSize:64,bold:true,color:VIOLET_LT,align:'left'});
  T(s,title,{x:0.95,y:3.55,w:11.4,h:1.2,fontFace:TITLE,fontSize:34,bold:true,color:'FFFFFF',align:'left'});
  if(sub) T(s,sub,{x:0.98,y:4.75,w:10.8,h:0.8,fontFace:BODY,fontSize:15,color:'C9CFEA',align:'left'});
  T(s,'Ugence  +  ServiceNow',{x:0.98,y:6.7,w:6,h:0.3,fontFace:BODY,fontSize:11,bold:true,color:'8E97C8',align:'left',charSpacing:2});
  s.addNotes('Section '+sectionNo+' — '+title+'. Transition slide: orient the audience to this section in a sentence'+(sub?' ('+sub+')':'')+', then continue. Keep the honest posture: ServiceNow strengths acknowledged, all integrations PROPOSED, scenarios illustrative.');
  return s;
}
function notes(s,t){ s.addNotes(t); }

/* ------------------------------------------------------------------ */
/* 1. TITLE */
(()=>{ const s=slide(true);
  SH(s,pptx.ShapeType.rect,{x:0,y:0,w:W,h:H,fill:{color:NAVY},line:{width:0}});
  // subtle two-tone base
  SH(s,pptx.ShapeType.rect,{x:0,y:6.55,w:W,h:0.95,fill:{color:'1E1B4A'},line:{width:0}});
  T(s,'PARTNER ARCHITECTURE BRIEFING  ·  PROPOSED INTEGRATION',{x:0.9,y:1.15,w:11.5,h:0.3,fontFace:BODY,fontSize:12,bold:true,color:'9AA2D8',charSpacing:2});
  T(s,'Ugence + ServiceNow',{x:0.86,y:1.7,w:11.6,h:0.95,fontFace:TITLE,fontSize:46,bold:true,color:'FFFFFF'});
  T(s,'Independent Action-Level Authority for Governed Agentic Workflows',{x:0.88,y:2.68,w:11.5,h:0.95,fontFace:TITLE,fontSize:26,bold:true,color:VIOLET_LT});
  T(s,'Extending ServiceNow-governed workflows with independently verifiable authorization, operational clearance, execution reconciliation, and governed-value evidence.',
    {x:0.9,y:3.85,w:11.0,h:0.9,fontFace:BODY,fontSize:15,color:'C9CFEA',lineSpacingMultiple:1.15});
  // category legend chips
  legendDark(s,0.9,5.05);
  // presenter / company
  T(s,[{text:'Rakesh Mohan',options:{bold:true,color:'FFFFFF'}},{text:'    ·    Founder, Ugence Labs    ·    ugence.ai    ·    August 2026',options:{color:'C9CFEA'}}],
    {x:0.9,y:6.12,w:11.5,h:0.34,fontFace:BODY,fontSize:13,align:'left',valign:'middle',margin:0});
  T(s,'All ServiceNow integrations are PROPOSED — no connector ships today. All scenarios are illustrative, not customer deployments.',
    {x:0.9,y:6.68,w:11.5,h:0.4,fontFace:BODY,fontSize:11,italic:true,color:'AEB6E0'});
  notes(s,'Open by naming the single question the deck answers: when an AI agent takes a consequential action, how can the enterprise PROVE that this exact action was authorized, stayed safe at execution time, and produced only the intended effect. Emphasize the framing is complementary to ServiceNow, not competitive. State plainly up front: every integration shown is PROPOSED (no connector ships), and every scenario is illustrative, not a Ugence customer deployment. This is a technical-fit conversation aiming at one bounded pilot, not a partnership demand.');
})();
function legendDark(s,x,y){
  const items=[['ServiceNow',GREEN],['Ugence decision / authority',VIOLET],['Ugence execution / assurance',TEAL],['External target',GREY],['Human review',AMBER],['Hold / Block / Escalate',RED]];
  let cx=x, cy=y;
  items.forEach((it,i)=>{ if(i===3){cx=x;cy=y+0.42;}
    SH(s,pptx.ShapeType.roundRect,{x:cx,y:cy+0.02,w:0.24,h:0.18,rectRadius:0.03,fill:{color:it[1]},line:{width:0}});
    T(s,it[0],{x:cx+0.32,y:cy-0.04,w:3.0,h:0.28,fontFace:BODY,fontSize:10.5,color:'E7EAF7',align:'left',valign:'middle',margin:0});
    cx += 0.32+3.05;
  });
}

/* 2. HOW TO READ */
(()=>{ const s=slide();
  header(s,'How to read this deck','Two levels for two audiences — on every major scenario');
  card(s,0.6,1.42,6.0,4.05,{title:'Level 1 — Layman view',tcolor:VIOLET_DK,fill:VIOLET_LT,line:VIOLET,
    body:'For business, operations and partnership stakeholders. Each scenario first answers, in plain language:\n\n•  The enterprise problem and why it matters\n•  What could go wrong when an AI agent acts\n•  What the AI agent wants to do\n•  Where control is required\n•  What ServiceNow already provides\n•  What Ugence proposes to contribute\n•  What the enterprise receives at the end',bfs:11});
  card(s,6.75,1.42,6.0,4.05,{title:'Level 2 — Technical architecture view',tcolor:TEAL_DK,fill:TEAL_LT,line:TEAL,
    body:'For solution architects. Each scenario then shows:\n\n•  What business data enters, and where it originates\n•  What each module receives or references\n•  What it checks or decides\n•  The separate governance artifact it emits\n•  What information passes over every arrow\n•  What executes the action\n•  What operational evidence returns\n•  How the observed effect is reconciled\n•  What is recorded or referenced in ServiceNow',bfs:11});
  // How to use this briefing
  SH(s,pptx.ShapeType.roundRect,{x:0.6,y:5.62,w:12.15,h:1.28,rectRadius:0.06,fill:{color:'F1F4FA'},line:{color:VIOLET,width:1}});
  T(s,'How to use this briefing',{x:0.8,y:5.72,w:11.7,h:0.3,fontFace:BODY,fontSize:12.5,bold:true,color:VIOLET_DK,margin:0});
  T(s,'This is a detailed landscape presentation designed for screen-based discussion and technical reference. The meeting walkthrough can focus on the executive framing, UC-5 autonomous change execution, the pilot proposal, and the discovery questions; the remaining sections provide supporting architecture and use-case detail.',
    {x:0.8,y:6.04,w:11.75,h:0.8,fontFace:BODY,fontSize:11,color:INK,margin:0,lineSpacingMultiple:1.08});
  notes(s,'Set expectations: every major scenario is explained twice — a plain-language pass, then a technical architecture pass. Tell the audience they can stay at Level 1 and still follow the whole story. Architects get the data-journey detail in Level 2. Emphasize we describe guarantees, not internal mechanics — no code, schemas, algorithms, or cryptographic detail are disclosed. Read the “How to use this briefing” box aloud so the representative knows they are not expected to review every slide during the meeting.');
})();

/* AGENDA / NAVIGATION */
(()=>{ const s=slide();
  header(s,'Agenda','How this briefing is organized — navigate by slide number');
  const secs=[['I','Executive framing'],['II','Data journey'],['III','Module responsibilities'],['IV','Lead UC-5 walkthrough'],['V','Additional scenarios'],['VI','Full use-case portfolio'],['VII','Honest overlap & differentiation'],['VIII','Enterprise Governed Value'],['IX','Pilot proposal'],['X','Discovery & next step']];
  secs.forEach((r,i)=>{ const col=i<5?0:1, row=i%5; const x=0.7+col*6.2, y=1.7+row*1.02;
    SH(s,pptx.ShapeType.roundRect,{x,y,w:5.85,h:0.84,rectRadius:0.06,fill:{color: i<5?VIOLET_LT:TEAL_LT},line:{color:i<5?VIOLET:TEAL,width:1},shadow:sh()});
    SH(s,pptx.ShapeType.ellipse,{x:x+0.18,y:y+0.17,w:0.5,h:0.5,fill:{color:i<5?VIOLET:TEAL},line:{width:0}});
    T(s,r[0],{x:x+0.18,y:y+0.17,w:0.5,h:0.5,fontFace:TITLE,fontSize:15,bold:true,color:'FFFFFF',align:'center',valign:'middle',margin:0});
    T(s,r[1],{x:x+0.84,y:y,w:4.85,h:0.84,fontFace:BODY,fontSize:13.5,bold:true,color:INK,valign:'middle',margin:0});
  });
  footnote(s,'Meeting spine: sections I, IV, IX and X. Sections II, III and V–VIII are supporting architecture and use-case reference. Every content slide is numbered for direct navigation.');
  notes(s,'Optional navigation slide. Set the meeting path: executive framing (I), the UC-5 lead walkthrough (IV), the pilot proposal (IX), and discovery / next step (X) are the spine; II, III and V–VIII are supporting reference the representative can read after the meeting. Note that every content slide is numbered so anyone can say “let us go to slide N”.');
})();

/* SECTION I */
notes(divider('I','Executive framing','The problem, the discovery questions, what ServiceNow provides, and the partnership boundary'),
  'Section I establishes the problem and the honest partnership posture before any Ugence module appears.');

/* 4. THE ENTERPRISE PROBLEM */
(()=>{ const s=slide();
  header(s,'The enterprise problem','When an AI agent acts, can you prove it stayed in bounds?');
  SH(s,pptx.ShapeType.roundRect,{x:0.6,y:1.45,w:12.1,h:1.15,rectRadius:0.08,fill:{color:VIOLET_LT},line:{color:VIOLET,width:1.25}});
  T(s,'“When an AI agent takes a consequential action, how can the enterprise prove that this exact action was authorized, remained safe at execution time, and produced only the intended effect?”',
    {x:0.9,y:1.5,w:11.5,h:1.05,fontFace:TITLE,fontSize:16.5,italic:true,bold:true,color:VIOLET_DK,valign:'middle',lineSpacingMultiple:1.05});
  const risks=[['Wrong target','The agent acts on the wrong system, resource, or record — a valid-looking action pointed at the wrong place.'],
    ['Conditions change','Time passes between approval and execution; a freeze begins, a dependency degrades, cost limits shift.'],
    ['Effect ≠ record','What actually happened in the environment does not match what the record says was authorized.']];
  risks.forEach((r,i)=>{ const x=0.6+i*4.07;
    card(s,x,2.95,3.8,2.05,{title:(i+1)+'.  '+r[0],tcolor:RED_DK,fill:'FFFFFF',line:HAIR,body:r[1],bfs:11});
  });
  SH(s,pptx.ShapeType.roundRect,{x:0.6,y:5.35,w:12.1,h:1.4,rectRadius:0.08,fill:{color:GREY_LT},line:{color:HAIR,width:1}});
  T(s,[{text:'A simple business example.  ',options:{bold:true,color:INK}},
    {text:'An AI operations agent believes the online-checkout service needs more capacity. Scaling may prevent an outage — but scaling the wrong cluster, on stale information, during a change freeze, or past the approved cost ceiling could raise cost or disrupt another service. The enterprise wants the speed of autonomy AND proof that the change that ran is the one that was approved, for the target approved, at a moment that was safe.',options:{color:INK}}],
    {x:0.9,y:5.45,w:11.5,h:1.2,fontFace:BODY,fontSize:12,valign:'middle',lineSpacingMultiple:1.08});
  notes(s,'Lead with the question verbatim — it frames the entire deck. Walk the three risks in plain language before any module name appears. Use the checkout example (return to it in UC-5 and again in Governed Value) so the audience carries one concrete thread through the deck. Do not mention Ugence packages yet.');
})();

/* 5. WHY APPROVAL MAY NOT BE ENOUGH */
(()=>{ const s=slide();
  header(s,'Executive framing','Why an ordinary approval may not be enough — as questions, not claims');
  const qs=['Was the approval for this exact target and payload — or for a class of action?',
    'Is the approval still valid at the moment of execution?',
    'Did the proposed action or payload change after approval?',
    'Are live operational conditions still safe right now?',
    'Did execution affect only the intended resource?',
    'Can the enterprise prove the complete chain afterward?'];
  qs.forEach((q,i)=>{ const col=i%2, row=Math.floor(i/2); const x=0.6+col*6.15, y=1.55+row*1.62;
    SH(s,pptx.ShapeType.roundRect,{x,y,w:5.95,h:1.4,rectRadius:0.06,fill:{color:i%2?TEAL_LT:VIOLET_LT},line:{color:i%2?TEAL:VIOLET,width:1},shadow:sh()});
    SH(s,pptx.ShapeType.ellipse,{x:x+0.2,y:y+0.2,w:0.5,h:0.5,fill:{color:i%2?TEAL:VIOLET},line:{width:0}});
    T(s,'?',{x:x+0.2,y:y+0.2,w:0.5,h:0.5,fontFace:TITLE,fontSize:18,bold:true,color:'FFFFFF',align:'center',valign:'middle',margin:0});
    T(s,q,{x:x+0.85,y:y+0.12,w:4.95,h:1.16,fontFace:BODY,fontSize:12.5,color:INK,valign:'middle',lineSpacingMultiple:1.05,margin:0});
  });
  footnote(s,'These are enterprise discovery questions to explore with ServiceNow architects — not assertions that ServiceNow lacks controls.');
  notes(s,'Frame every one of these as a constructive discovery question. Say explicitly: "these are questions we would work through with your architects, not claims about gaps." This slide sets up the honest posture that recurs throughout — unverified differentiation is always a hypothesis to confirm.');
})();

/* 6. WHAT SERVICENOW PROVIDES */
(()=>{ const s=slide();
  header(s,'Executive framing','What ServiceNow already provides — the proposal is complementary');
  const caps=[['AI Control Tower','Discovers, governs, secures and measures AI across the enterprise; real-time enforcement.'],
    ['Action Fabric','A governed system of action (MCP / A2A) — every action identity-verified, permission-scoped, auditable.'],
    ['Agent Deviation Detection','Flags when an agent strays from its authorized role at runtime.'],
    ['AI Risk & Compliance','Multi-framework control mapping (EU AI Act, NIST AI RMF and others).'],
    ['Change Management + CMDB','Approvals, change/blackout windows, conflict detection, business context.'],
    ['NVIDIA OpenShell','Central AICT policy enforced at runtime on file, command and network access.'],
    ['Adoption, impact & ROI','AI adoption, business impact, realized value and ROI measurement.'],
    ['Approvals & workflow','Enterprise approval and workflow mechanisms across the platform.']];
  caps.forEach((c,i)=>{ const col=i%2,row=Math.floor(i/2); const x=0.6+col*6.15,y=1.5+row*1.28;
    SH(s,pptx.ShapeType.roundRect,{x,y,w:5.95,h:1.12,rectRadius:0.06,fill:{color:GREEN_LT},line:{color:GREEN,width:1}});
    T(s,c[0],{x:x+0.2,y:y+0.1,w:5.55,h:0.3,fontFace:BODY,fontSize:12,bold:true,color:GREEN_DK,margin:0});
    T(s,c[1],{x:x+0.2,y:y+0.42,w:5.55,h:0.62,fontFace:BODY,fontSize:10,color:INK,margin:0,lineSpacingMultiple:1.0});
  });
  footnote(s,'Sources: ServiceNow Docs / Newsroom / Community; NVIDIA OpenShell docs. We do not say “ServiceNow lacks / cannot / only inventories,” nor claim unique cross-platform runtime enforcement.');
  notes(s,'Spend real time here. Acknowledging ServiceNow’s strength accurately is what earns credibility for the narrow proposal that follows. Read the capabilities as facts. Explicitly avoid the banned phrases (lacks / cannot / above / replacement / only inventories) and do not claim Ugence uniquely enforces across runtimes — OpenShell already enforces at the kernel level. Position everything as complementary.');
})();

/* 7. PARTNERSHIP BOUNDARY */
(()=>{ const s=slide();
  header(s,'Executive framing','The partnership boundary — who contributes what');
  SH(s,pptx.ShapeType.roundRect,{x:0.6,y:1.5,w:6.0,h:5.25,rectRadius:0.08,fill:{color:GREEN_LT},line:{color:GREEN,width:1.25}});
  T(s,'ServiceNow remains responsible for',{x:0.8,y:1.62,w:5.6,h:0.4,fontFace:BODY,fontSize:14,bold:true,color:GREEN_DK});
  T(s,[['Enterprise system of record'],['Workflow and case management'],['CMDB and business context'],['Enterprise approvals'],['Platform governance'],['Action Fabric'],['Platform execution pathways'],['AI Control Tower monitoring & controls'],['Value and ROI reporting']].map((t,i)=>({text:t[0],options:{bullet:{code:'2022',indent:14},breakLine:true,paraSpaceAfter:5}})),
    {x:0.85,y:2.1,w:5.5,h:4.5,fontFace:BODY,fontSize:12.5,color:INK});
  SH(s,pptx.ShapeType.roundRect,{x:6.75,y:1.5,w:6.0,h:5.25,rectRadius:0.08,fill:{color:VIOLET_LT},line:{color:VIOLET,width:1.25}});
  T(s,'Ugence proposes to contribute',{x:6.95,y:1.62,w:5.6,h:0.4,fontFace:BODY,fontSize:14,bold:true,color:VIOLET_DK});
  badge(s,11.0,1.64,'PROPOSED',1.5);
  T(s,[['Binding decision artifacts'],['Trusted-evidence linkage'],['Exact-action and target authorization'],['Time- and scope-bounded authority'],['Independent operational clearance'],['Governed execution coordination'],['Execution receipts'],['Observed-effect reconciliation'],['Authority lifecycle & reassessment'],['Cross-stage evidence lineage'],['Developing governed-value attribution']].map(t=>({text:t[0],options:{bullet:{code:'2022',indent:14},breakLine:true,paraSpaceAfter:3}})),
    {x:7.0,y:2.1,w:5.55,h:4.55,fontFace:BODY,fontSize:12,color:INK});
  footnote(s,'Neither side replaces the other. Ugence composes WITH ServiceNow’s workflow, system of action and platform enforcement. Every integration is PROPOSED.');
  notes(s,'This is the single most important slide for the representative. Say it out loud: ServiceNow remains the system of record, system of action and platform enforcement; Ugence contributes an independent, verifiable authority-and-evidence layer that composes WITH it. Avoid any hierarchy language. Mark the Ugence column PROPOSED.');
})();

/* SECTION II */
divider('II','Understanding the data journey','Four kinds of data, and the same journey told first in plain language, then technically');

/* 9. FOUR KINDS OF DATA */
(()=>{ const s=slide();
  header(s,'The data journey','Four kinds of data — kept distinct throughout');
  const rows=[[ '1 · Original business data','Change, incident, CI, employee, entitlement, control evidence, amount, target system, requested action','ServiceNow (system of record)',GREEN_LT,GREEN_DK],
    ['2 · Derived governance artifacts','Decision record, model / action / risk authorization, clearance verdict, execution receipt, assurance result, revocation / reassessment signal','Ugence — each a SEPARATE artifact',VIOLET_LT,VIOLET_DK],
    ['3 · Observed operational data','Infrastructure state, service health, blackout window, dependency condition, account status, execution result, post-action effect','ServiceNow + operational telemetry',TEAL_LT,TEAL_DK],
    ['4 · ServiceNow records','Remain the system-of-record context; receive statuses, receipt references and summarized outcomes','ServiceNow (via PROPOSED integration)',GREY_LT,GREY_DK]];
  let y=1.5;
  rows.forEach(r=>{ SH(s,pptx.ShapeType.roundRect,{x:0.6,y,w:12.1,h:1.02,rectRadius:0.05,fill:{color:r[3]},line:{color:HAIR,width:1}});
    T(s,r[0],{x:0.8,y:y+0.08,w:3.0,h:0.86,fontFace:BODY,fontSize:12,bold:true,color:r[4],valign:'middle',margin:0});
    T(s,r[1],{x:3.9,y:y+0.08,w:5.7,h:0.86,fontFace:BODY,fontSize:10.5,color:INK,valign:'middle',margin:0,lineSpacingMultiple:1.0});
    T(s,r[2],{x:9.7,y:y+0.08,w:2.9,h:0.86,fontFace:BODY,fontSize:10,italic:true,color:r[4],valign:'middle',margin:0});
    y+=1.14;
  });
  SH(s,pptx.ShapeType.roundRect,{x:0.6,y:6.15,w:12.1,h:0.62,rectRadius:0.06,fill:{color:INK},line:{width:0}});
  T(s,'“Each Ugence module reads or references the necessary business context and emits a separate governance artifact. It does not silently rewrite the originating ServiceNow record.”',
    {x:0.85,y:6.17,w:11.6,h:0.58,fontFace:BODY,fontSize:11.5,italic:true,bold:true,color:'FFFFFF',valign:'middle',margin:0});
  notes(s,'This is the conceptual backbone. Stress the principle in the dark bar: modules emit NEW, separate artifacts alongside the business record — they do not quietly edit the business truth. When the record is updated, it receives a reference, status or receipt via the proposed integration. Architects should leave able to repeat the four categories.');
})();

/* 10. LAYMAN END-TO-END */
(()=>{ const s=slide();
  header(s,'The data journey','End-to-end, in plain language');
  const cx=2.15, bw=3.0;
  const ns=[{t:'Business event',cat:'SNOW',arrow:'a need or request arises'},
    {t:'AI proposes an action',cat:'UDEC',arrow:'“do X to target Y”'},
    {t:'Authorized decision',cat:'UDEC',arrow:'approved by delegated authority'},
    {t:'Permission for the exact action',cat:'UDEC',arrow:'bound to target Y and payload'},
    {t:'“Is it safe right now?” check',cat:'UEXE',arrow:'live conditions verified'},
    {t:'Controlled execution',cat:'UEXE',arrow:'action carried out'},
    {t:'Confirm the actual effect',cat:'UEXE',arrow:'only intended effect occurred'},
    {t:'Auditable result to ServiceNow',cat:'SNOW',arrow:null}];
  // two columns of the flow to fit
  const colA=ns.slice(0,4), colB=ns.slice(4);
  const pa=flow(s,cx,1.55,bw,colA,0.5);
  const pb=flow(s,cx+5.6,1.55,bw,colB,0.5);
  // connect end of A to start of B
  conn(s,pa[3].x+bw,pa[3].mid,pb[0].x, pb[0].mid,'then',{w:1.2});
  // example callouts column on right
  SH(s,pptx.ShapeType.roundRect,{x:9.9,y:1.5,w:2.9,h:5.2,rectRadius:0.06,fill:{color:GREY_LT},line:{color:HAIR,width:1}});
  T(s,'Example information added',{x:10.05,y:1.6,w:2.6,h:0.3,fontFace:BODY,fontSize:11,bold:true,color:INK});
  T(s,[['Proposed: “scale checkout 12→18”'],['Decision: approved under delegated scaling authority'],['Permission: this cluster, service, window'],['Clearance: no freeze, deps healthy, cost within limit'],['Receipt: request accepted, completed'],['Effect: 18 active, nothing else changed'],['Result: execution matched authorization']].map(t=>({text:t[0],options:{bullet:{code:'2022',indent:12},breakLine:true,paraSpaceAfter:6}})),
    {x:10.1,y:2.0,w:2.6,h:4.6,fontFace:BODY,fontSize:9.5,color:INK,lineSpacingMultiple:1.0});
  footnote(s,'No package names appear in the layman view. Illustrative example.');
  notes(s,'Walk left to right, top to bottom. Keep it business-plain: an event, a proposal, an approval, an exact permission, a safety check, execution, a confirmation of the real effect, and an auditable result back in ServiceNow. Point at the right-hand column to show the kind of information added at each step. Say the example is illustrative.');
})();

/* 11. TECHNICAL CANONICAL WORKFLOW */
(()=>{ const s=slide();
  header(s,'The data journey','The technical canonical workflow — modules that may participate');
  legend(s,0.6,1.28,[['ServiceNow','SNOW',1.2],['Ugence decision/authority','UDEC',2.5],['Ugence execution/assurance','UEXE',2.5],['External','EXT',0.8],['Stop paths','STOP',1.2]]);
  const cx=3.4, bw=3.1;
  const ns=[{t:'ServiceNow record',cat:'SNOW',arrow:'business record + approval context'},
    {t:'Decision Authority',cat:'UDEC',arrow:'binding decision record'},
    {t:'ActionGate  ·  exact action',cat:'UDEC',arrow:'exact-target authorization'},
    {t:'Action Clearance (ACP)',cat:'UDEC',arrow:'CLEAR'},
    {t:'Agent Runtime  ·  coordinates',cat:'UEXE',arrow:'execution receipt'},
    {t:'RA-8 Execution Assurance',cat:'UEXE',arrow:'effect matched'},
    {t:'ServiceNow record (status + receipts)',cat:'SNOW',arrow:null}];
  const pos=flow(s,cx,1.65,bw,ns,0.28);
  // upstream evidence (offset) note left
  // stop column
  const sx=8.3, sy=pos[2].top, sh2=pos[3].bot-pos[2].top;
  SH(s,pptx.ShapeType.roundRect,{x:sx,y:sy,w:2.4,h:sh2,rectRadius:0.06,fill:{color:RED_LT},line:{color:RED,width:1.25}});
  T(s,'STOP  /  HOLD  /  BLOCK  /  ESCALATE\n\nuncertainty is never promoted to permission (fail-closed)',{x:sx+0.1,y:sy,w:2.2,h:sh2,fontFace:BODY,fontSize:10,bold:true,color:RED_DK,align:'center',valign:'middle',margin:2,lineSpacingMultiple:1.0});
  conn(s,pos[2].x+bw,pos[2].mid,sx,pos[2].mid,'DENIED / INDET.',{w:1.7,fs:8,color:RED});
  conn(s,pos[3].x+bw,pos[3].mid,sx,pos[3].mid,'HOLD / BLOCK',{w:1.6,fs:8,color:RED});
  conn(s,sx+1.2,sy+sh2,sx+1.2,pos[6].mid,'reason + evidence',{w:1.7,fs:8});
  seg(s,sx+1.2,pos[6].mid, pos[6].x+bw, pos[6].mid,{color:ARROW});
  // side note: evidence + risk authority + model authority optionally
  SH(s,pptx.ShapeType.roundRect,{x:8.3,y:5.15,w:4.4,h:1.5,rectRadius:0.06,fill:{color:GREY_LT},line:{color:HAIR,width:1}});
  T(s,[{text:'Where a scenario needs them:  ',options:{bold:true}},{text:'Policy Workflow Compiler and RA-5 trusted evidence sit upstream of the decision; Risk Authority mints a signed, scoped, time-limited authorization; Model Authority authorizes the model; StoryGraph flags sequence risk; RA-6 revokes authority; RA-7 assesses in-flight trajectory. Only participating modules are shown per scenario.',options:{}}],
    {x:8.45,y:5.22,w:4.15,h:1.4,fontFace:BODY,fontSize:9,color:INK,valign:'top',margin:0,lineSpacingMultiple:1.0});
  footnote(s,'Each layer speaks a distinct decision verb; authority never leaks across layers. Not every module appears in every scenario.');
  notes(s,'This is the canonical spine. Emphasize: distinct verbs per layer, fail-closed at every boundary (uncertainty never becomes permission), and that we only draw the modules a given scenario actually uses. Point out the STOP column and the return path to ServiceNow — both recur in every scenario diagram.');
})();

/* SECTION III */
divider('III','Module responsibilities','A business-readable glossary, and the repository-verified architecture facts');

/* 13. ARCHITECTURE INVARIANTS */
(()=>{ const s=slide();
  header(s,'Module responsibilities','Architecture facts we hold to (verified against the source of record)');
  const facts=[['Decision Authority owns the binding decision','It also owns execution and reconciliation records, and the context-envelope records (CER). AI is barred as an authorizing principal.'],
    ['Agent Runtime coordinates governed execution','It owns canonical execution state and invokes domain executors / providers / tools. It is not the “CER,” and it creates no authority.'],
    ['Cloud Scaling Operations is a domain executor','It is invoked by Agent Runtime and returns its result to Agent Runtime — it is not a preceding authorization gate.'],
    ['RA-8 compares intent, evidence and effect','It checks authorized intent against the execution receipt and observed effect. It never retroactively authorizes an action.'],
    ['Authority stays scoped and revocable','RA-6 is the sole writer of authority lifecycle (revoke / supersede / expire). Enforcement stays read-only.'],
    ['Fail-closed at every boundary','Missing approval, evidence, clearance or execution confirmation is never treated as permission.']];
  facts.forEach((f,i)=>{ const col=i%2,row=Math.floor(i/2); const x=0.6+col*6.15,y=1.5+row*1.72;
    SH(s,pptx.ShapeType.roundRect,{x,y,w:5.95,h:1.55,rectRadius:0.06,fill:{color:'FFFFFF'},line:{color:VIOLET,width:1},shadow:sh()});
    SH(s,pptx.ShapeType.ellipse,{x:x+0.2,y:y+0.24,w:0.42,h:0.42,fill:{color:VIOLET},line:{width:0}});
    T(s,'✓',{x:x+0.2,y:y+0.24,w:0.42,h:0.42,fontFace:BODY,fontSize:14,bold:true,color:'FFFFFF',align:'center',valign:'middle',margin:0});
    T(s,f[0],{x:x+0.78,y:y+0.14,w:5.0,h:0.5,fontFace:BODY,fontSize:11.5,bold:true,color:VIOLET_DK,margin:0,valign:'middle'});
    T(s,f[1],{x:x+0.78,y:y+0.6,w:5.0,h:0.85,fontFace:BODY,fontSize:9.8,color:INK,margin:0,lineSpacingMultiple:1.0});
  });
  footnote(s,'These invariants are held consistently across every scenario diagram in this deck.');
  notes(s,'These are the corrected, verified facts (catalog v1.2). Two matter most for the diagrams: Agent Runtime INVOKES Cloud Scaling Operations and receives its result — Cloud Scaling Operations is not a preceding gate; and CER belongs to Decision Authority, so we never write “Agent Runtime (CER).” Also stress RA-8 never retro-authorizes, and everything fails closed.');
})();

/* 14-16 MODULE GLOSSARY tables */
function glossary(subtitle, rows){
  const s=slide();
  header(s,'Module responsibilities',subtitle);
  const head=['Module','Layman responsibility','Receives / references','Checks / decides','Emits','Does not do'];
  const colW=[1.5,2.35,2.15,2.35,1.9,1.85];
  const table=[head.map(h=>({text:h,options:{fill:{color:INK},color:'FFFFFF',bold:true,fontSize:10.5,align:'left',valign:'middle'}}))];
  rows.forEach((r,ri)=>{ table.push(r.map((c,ci)=>({text:c,options:{fill:{color: ri%2?'F4F6FA':'FFFFFF'},color: ci===0?VIOLET_DK:INK,bold:ci===0,fontSize:9.6,align:'left',valign:'top'}}))); });
  TB(s,table,{x:0.5,y:1.5,w:12.35,colW,border:{type:'solid',color:HAIR,pt:0.75},rowH:0.32,fontFace:BODY,valign:'top',autoPage:false});
  footnote(s,'We describe the guarantee each module provides, not the internal mechanism. All ServiceNow integration is PROPOSED.');
  return s;
}
notes(glossary('Module glossary (1 of 3) — policy, evidence, decision, signed authority',[
  ['Policy Workflow Compiler','Turns approved policy into deterministic, checkable constraints','Approved, structured policy pack (compile-time, offline)','Compiles policy to constraints','Digest-addressed governed-workflow artifact','No binding decision; authorizes / clears / runs nothing'],
  ['RA-5 Trusted Evidence Admission','Ensures a control is met by trusted, re-checked evidence','Control evidence references','Is each control satisfied by trusted evidence? (a caller “pass” is inert)','Evidence-derived, re-checked control result','Add a second authority signature'],
  ['Decision Authority','Confirms a delegated authority — not the AI — approved this class of decision','Proposed action, delegated authority, constraints; owns CER','Is there a binding decision within scope?','A separate, immutable decision record','Execute; inspect live conditions; let AI self-authorize'],
  ['Risk Authority','Converts an approved risk decision into signed, time-limited, scoped permission','An allow-family risk decision','Whether to mint authority; scope ≤ decision scope','A signed, scoped, time-limited authorization (tamper-evident)','Execute the action'],
]),'Read down the “Does not do” column — that is where the guarantees live. PWC is compile-time only and decides nothing. RA-5 makes a stale or self-asserted “pass” inert. Decision Authority owns the binding decision and the CER, and structurally bars AI as principal. Risk Authority is the sole issuer of the signed, scoped, time-limited authorization.');

notes(glossary('Module glossary (2 of 3) — model, exact action, sequence, clearance',[
  ['Model Authority','Decides which model may handle this specific request, now','Request context, approved model policy','Per-request eligibility','ALLOW / DENY / HOLD / ESCALATE, with governed fallback and expiry','Execute the request; replace platform provider approval'],
  ['ActionGate','Converts an approval into permission for one exact action on one exact target','Decision record, target identity, proposed action','Same authorized action? still valid?','AUTHORIZED / DENIED / INDETERMINATE (uncertainty → INDETERMINATE)','Judge operational safety; own execution'],
  ['StoryGraph','Flags when individually-harmless steps add up to a harmful capability','A multi-step plan across steps','Do benign steps assemble a harmful capability?','OBSERVE / ESCALATE (advisory)','Authorize or execute'],
  ['Action Clearance (ACP)','The final “is it safe right now?” check','Already-authorized action + current conditions','Blackout, conflict, unhealthy dependency, operational hold','CLEAR / HOLD / BLOCK / ESCALATE (subtractive)','Create or broaden authority; dispatch execution'],
]),'Model Authority is a per-REQUEST binding decision with fallback and expiry, not a static allowlist. ActionGate binds to the exact action/target and never promotes uncertainty to AUTHORIZED. StoryGraph is advisory across a sequence. Action Clearance is the independent, subtractive live-safety veto — it can only preserve, narrow, hold or block, never widen.');

notes(glossary('Module glossary (3 of 3) — coordination, actuation, lifecycle, assurance',[
  ['Agent Runtime','Coordinates the governed execution and carries its state','A governed request; invokes providers / domain executors','Execution lifecycle (retry / timeout / recovery)','Execution receipt; owns canonical execution state','Create authority; author policy; authorize; mint clearance'],
  ['Cloud Scaling Operations','Carries out a bounded infrastructure change under strict controls','A scaling instruction + externally minted execution authorization','Readiness; bounded execution (dry-run by default)','Execution outcome + audit, returned to Agent Runtime','Mint its own authority; act as a preceding gate'],
  ['RA-6 Authority Lifecycle','Keeps authority current — revokes, supersedes, expires','A reassessment signal when conditions change','Whether to revoke / supersede / expire','A lifecycle mutation (bites at the next pre-effect recheck)','Execute or authorize'],
  ['RA-7 Trajectory Assurance','Watches an in-flight execution for drift','The in-flight execution (neutral observation)','Is the trajectory drifting?','NORMAL / ESCALATED / UNKNOWN → reassessment signal','Mint authority'],
  ['RA-8 Execution Assurance','Checks whether reality matched what was authorized','Authorized action, execution receipt, observed state','Did only the intended target change, within scope?','matched / mismatch / partial / unknown','Retroactively legitimize an unauthorized action'],
]),'Close the glossary on the execution and assurance modules. Agent Runtime coordinates and invokes; Cloud Scaling Operations is the domain executor it invokes (dry-run by default, needs external execution authorization) and returns its result to the runtime. RA-6 keeps authority current; RA-7 watches in-flight; RA-8 reconciles after the fact and never retro-authorizes.');

/* SECTION IV — UC-5 */
divider('IV','Lead scenario — autonomous change execution','UC-5: the full two-level walkthrough, end to end');

/* 18. UC-5 problem */
(()=>{ const s=slide();
  header(s,'UC-5 · Autonomous change execution','The problem, in plain terms');
  SH(s,pptx.ShapeType.roundRect,{x:0.6,y:1.45,w:12.1,h:0.85,rectRadius:0.06,fill:{color:GREY_LT},line:{color:HAIR,width:1}});
  T(s,[{text:'Illustrative scenario.  ',options:{bold:true,color:INK}},{text:'Change CHG0048217 · online checkout · production Kubernetes cluster · scale the checkout service from 12 to 18 instances · sustained demand and latency pressure · constraints: approved cost ceiling, permitted change window, healthy dependencies, rollback capability.  This shows how the proposed integration could operate — it is not a claimed Ugence customer deployment.',options:{color:INK,italic:true}}],
    {x:0.85,y:1.5,w:11.6,h:0.76,fontFace:BODY,fontSize:10.5,valign:'middle',margin:0,lineSpacingMultiple:1.0});
  const pts=[['Why the AI proposes scaling','Checkout latency is rising under sustained demand; more capacity may prevent an outage.'],
    ['What is at risk','Online checkout — a revenue-critical business service — and any service that shares the cluster.'],
    ['What could go wrong','Scaling the wrong cluster or service, or acting on stale information, could disrupt another service or exceed cost.'],
    ['Why a valid approval may still be unsafe','A freeze may have begun, a dependency may be unhealthy, or projected cost may now exceed the ceiling.'],
    ['Why the effect must be checked','The record must reflect what actually happened — only the intended instances changed, nothing else.'],
    ['What the enterprise wants','Autonomy with proof: the exact approved change, at a safe moment, with a verifiable, reconciled result.']];
  pts.forEach((p,i)=>{ const col=i%2,row=Math.floor(i/2); const x=0.6+col*6.15,y=2.5+row*1.42;
    SH(s,pptx.ShapeType.roundRect,{x,y,w:5.95,h:1.28,rectRadius:0.06,fill:{color:'FFFFFF'},line:{color:HAIR,width:1},shadow:sh()});
    T(s,p[0],{x:x+0.2,y:y+0.12,w:5.55,h:0.34,fontFace:BODY,fontSize:11.5,bold:true,color:VIOLET_DK,margin:0});
    T(s,p[1],{x:x+0.2,y:y+0.46,w:5.55,h:0.76,fontFace:BODY,fontSize:10,color:INK,margin:0,lineSpacingMultiple:1.02});
  });
  footnote(s,'Illustrative example — not a customer deployment.');
  notes(s,'Introduce UC-5 as the lead scenario and the pilot candidate. Read the illustrative banner verbatim — this is not a customer deployment. Keep this slide entirely in business language; the modules come next. The key tension to land: a valid approval is necessary but not sufficient, because targets and live conditions can change, and the real effect must be verified.');
})();

/* 19. UC-5 input data */
(()=>{ const s=slide();
  header(s,'UC-5 · Autonomous change execution','What business data enters the workflow');
  const head=['Data category','Example','Authoritative source'];
  const rows=[['Business record','Change request CHG0048217 and its approval state','ServiceNow Change Management'],
    ['Target context','Cluster, checkout service, requested capacity 12 → 18','CMDB / ITOM / cloud platform'],
    ['Live conditions','Freeze window, dependency health, service health','ServiceNow + operational telemetry'],
    ['Governance context','Delegated scaling authority, cost / risk limits, expiry','Approved enterprise policy'],
    ['Intended outcome','Lower latency without exceeding cost or risk limits','Business objective']];
  const table=[head.map(h=>({text:h,options:{fill:{color:INK},color:'FFFFFF',bold:true,fontSize:12,align:'left',valign:'middle'}}))];
  rows.forEach((r,ri)=>table.push(r.map((c,ci)=>({text:c,options:{fill:{color:ri%2?'F4F6FA':'FFFFFF'},color:ci===0?VIOLET_DK:INK,bold:ci===0,fontSize:11.5,align:'left',valign:'middle'}}))));
  TB(s,table,{x:0.6,y:1.7,w:12.1,colW:[3.0,5.6,3.5],border:{type:'solid',color:HAIR,pt:0.75},rowH:0.7,fontFace:BODY,valign:'middle',autoPage:false});
  T(s,'Business-readable fields only — not internal schemas. Original business data (rows 1–2) is distinct from live conditions (row 3) and from any governance artifact Ugence later emits.',
    {x:0.6,y:6.2,w:12.1,h:0.6,fontFace:BODY,fontSize:11,italic:true,color:MUTED});
  notes(s,'Use this to reinforce the four-kinds-of-data distinction with concrete rows. Rows 1–2 are original business data owned by ServiceNow; row 3 is observed operational data; row 4 is approved policy. Nothing here is a Ugence artifact yet — those are produced by the modules on the next slides and kept separate from the record.');
})();

/* 20. UC-5 layman workflow */
(()=>{ const s=slide();
  header(s,'UC-5 · Autonomous change execution','The business journey (plain language)');
  const cx=2.2,bw=3.0;
  const A=[{t:'Checkout slowing down',cat:'SNOW',arrow:'demand + latency'},
    {t:'AI recommends adding capacity',cat:'UDEC',arrow:'“scale 12 → 18”'},
    {t:'Approval confirmed for this exact change',cat:'UDEC',arrow:'delegated authority'},
    {t:'Permission bound to this cluster & capacity',cat:'UDEC',arrow:null}];
  const B=[{t:'“Is it safe right now?”',cat:'UEXE',arrow:'freeze / deps / cost'},
    {t:'Capacity change carried out',cat:'UEXE',arrow:'within window & ceiling'},
    {t:'Confirm what actually changed',cat:'UEXE',arrow:'only intended instances'},
    {t:'Auditable result to the change record',cat:'SNOW',arrow:null}];
  const pa=flow(s,cx,1.6,bw,A,0.44);
  const pb=flow(s,cx+4.9,1.6,bw,B,0.44);
  conn(s,pa[3].x+bw,pa[3].mid,pb[0].x,pb[0].mid,'if permitted',{w:1.4});
  // safe-branch stop
  const sx=9.6;
  SH(s,pptx.ShapeType.roundRect,{x:sx,y:pb[0].top-0.05,w:3.1,h:1.0,rectRadius:0.06,fill:{color:RED_LT},line:{color:RED,width:1.25}});
  T(s,'Held, escalated or blocked\n(freeze · conflict · cost)',{x:sx+0.1,y:pb[0].top-0.05,w:2.9,h:1.0,fontFace:BODY,fontSize:10.5,bold:true,color:RED_DK,align:'center',valign:'middle',margin:2});
  conn(s,pb[0].x+bw,pb[0].mid,sx,pb[0].mid,'if not safe',{w:1.3,color:RED,fs:8});
  conn(s,sx+1.55,pb[0].top+1.0,sx+1.55,pb[3].mid,null);
  seg(s,sx+1.55,pb[3].mid,pb[3].x+bw,pb[3].mid);
  footnote(s,'No package names in the layman view. Illustrative example.');
  notes(s,'Tell the checkout story as a sequence anyone can follow. The one decision point is “is it safe right now?” — if not, the change is held, escalated or blocked, and even that outcome returns an auditable result to the change record. Keep module names out of this slide entirely.');
})();

/* 21. UC-5 technical workflow */
(()=>{ const s=slide();
  header(s,'UC-5 · Autonomous change execution','Technical module workflow — Agent Runtime invokes the executor');
  legend(s,0.6,1.26,[['ServiceNow','SNOW',1.2],['Ugence decision','UDEC',1.7],['Ugence execution','UEXE',1.8],['External','EXT',0.8],['Stop','STOP',0.7]]);
  const cx=5.2,bw=3.0;
  const ns=[{t:'ServiceNow Change Mgmt · CHG0048217',cat:'SNOW',arrow:'change record + approval context',fs:10},
    {t:'Decision Authority',cat:'UDEC',arrow:'binding decision record'},
    {t:'ActionGate',cat:'UDEC',arrow:'exact-target action authorization'},
    {t:'Action Clearance (ACP)',cat:'UDEC',arrow:'CLEAR'},
    {t:'Agent Runtime · coordinates',cat:'UEXE',arrow:'execution receipt'},
    {t:'RA-8 Execution Assurance',cat:'UEXE',arrow:'effect matched'},
    {t:'ServiceNow Change Record\nstatus + receipt refs + outcome',cat:'SNOW',arrow:null,fs:9.5,h:0.6}];
  const p=flow(s,cx,1.58,bw,ns,0.26);
  // invoke/return pair: Cloud Scaling Operations to the left of Agent Runtime
  const ar=p[4]; const csX=0.5, csW=2.55, csY=ar.mid-0.31, arL=ar.x, csR=csX+csW;
  node(s,csX,csY,csW,0.62,'Cloud Scaling Operations\n(controlled · dry-run)','UEXE',{fs:9});
  seg(s,arL,ar.mid-0.13,csR,ar.mid-0.13,{color:TEAL});
  alabel(s,arL,ar.mid-0.13,csR,ar.mid-0.13,'invokes',{w:0.8,fs:7,color:TEAL,h:0.2});
  seg(s,csR,ar.mid+0.13,arL,ar.mid+0.13,{color:TEAL});
  alabel(s,csR,ar.mid+0.13,arL,ar.mid+0.13,'result',{w:0.75,fs:7,color:TEAL,h:0.2});
  // CS to target
  const tgtY=csY+0.94; cyl(s,csX+0.32,tgtY,1.9,0.64,'Production\nKubernetes cluster','EXT',{fs:9});
  conn(s, csX+csW/2-0.3, csY+0.62, csX+1.27-0.3, tgtY,'scaling request',{w:1.25,fs:7});
  conn(s, csX+1.27+0.35, tgtY, csX+csW/2+0.35, csY+0.63,'outcome + audit',{w:1.25,fs:7});
  // stop column
  const sx=8.85, sTop=p[2].top, sBot=p[3].bot;
  SH(s,pptx.ShapeType.roundRect,{x:sx,y:sTop,w:2.5,h:sBot-sTop,rectRadius:0.06,fill:{color:RED_LT},line:{color:RED,width:1.25}});
  T(s,'HOLD / BLOCK / ESCALATE\nno execution',{x:sx+0.1,y:sTop,w:2.3,h:sBot-sTop,fontFace:BODY,fontSize:10,bold:true,color:RED_DK,align:'center',valign:'middle',margin:2});
  conn(s,p[2].x+bw,p[2].mid,sx,p[2].mid,'DENIED / INDET.',{w:1.6,fs:7.5,color:RED});
  conn(s,p[3].x+bw,p[3].mid,sx,p[3].mid,'HOLD / BLOCK',{w:1.5,fs:7.5,color:RED});
  conn(s,sx+1.25,sBot,sx+1.25,p[6].mid,'reason + evidence',{w:1.6,fs:7.5});
  seg(s,sx+1.25,p[6].mid,p[6].x+bw,p[6].mid);
  // mismatch note
  SH(s,pptx.ShapeType.roundRect,{x:8.85,y:5.2,w:2.5,h:1.35,rectRadius:0.06,fill:{color:GREY_LT},line:{color:HAIR,width:1}});
  T(s,'RA-8 mismatch / uncertain → escalate (still returns an auditable result to the record)',{x:8.97,y:5.28,w:2.28,h:1.2,fontFace:BODY,fontSize:9,color:INK,valign:'middle',margin:0,lineSpacingMultiple:1.0});
  footnote(s,'Agent Runtime INVOKES Cloud Scaling Operations and receives its result; the runtime carries the receipt to RA-8. Cloud Scaling Operations is a domain executor, not a preceding gate. Illustrative.');
  notes(s,'The architecturally critical slide. Trace it: Decision Authority → ActionGate → Action Clearance → Agent Runtime. Agent Runtime then INVOKES Cloud Scaling Operations (the two arrows show invocation and result-return — not a linear stage), Cloud Scaling Operations actuates the cluster, its result returns to Agent Runtime, and the runtime carries the execution receipt to RA-8. RA-8 reconciles and returns to the change record. Point out the STOP column and that even mismatch/uncertain returns an auditable result. Cloud Scaling Operations is dry-run by default and needs an external execution authorization.');
})();

/* 22. UC-5 exception paths */
(()=>{ const s=slide();
  header(s,'UC-5 · Autonomous change execution','What stops the action — and what happens then');
  const ex=[['Missing evidence / approval','The workflow does not proceed; uncertainty is not treated as permission.','STOP'],
    ['Changed target or payload','ActionGate returns DENIED / INDETERMINATE — the authorization no longer matches.','STOP'],
    ['Unsafe live conditions','Action Clearance returns HOLD / BLOCK / ESCALATE on freeze, conflict or cost.','STOP'],
    ['Authority revoked / expired','RA-6 revocation bites at the next pre-effect recheck; further action is blocked.','STOP'],
    ['Execution mismatch','RA-8 flags mismatch / partial / uncertain — the effect did not match the authorization.','STOP'],
    ['Governance not wired','Agent Runtime fails closed — consequential transitions are blocked by default.','STOP']];
  ex.forEach((e,i)=>{ const col=i%2,row=Math.floor(i/2); const x=0.6+col*6.15,y=1.55+row*1.62;
    SH(s,pptx.ShapeType.roundRect,{x,y,w:5.95,h:1.42,rectRadius:0.06,fill:{color:RED_LT},line:{color:RED,width:1}});
    T(s,e[0],{x:x+0.22,y:y+0.14,w:5.5,h:0.36,fontFace:BODY,fontSize:12,bold:true,color:RED_DK,margin:0});
    T(s,e[1],{x:x+0.22,y:y+0.52,w:5.5,h:0.8,fontFace:BODY,fontSize:10.5,color:INK,margin:0,lineSpacingMultiple:1.02});
  });
  SH(s,pptx.ShapeType.roundRect,{x:0.6,y:6.5,w:12.1,h:0.42,rectRadius:0.06,fill:{color:INK},line:{width:0}});
  T(s,'Fail-closed: if a mandatory approval, evidence item, live-safety check or execution confirmation is missing, the workflow does not treat uncertainty as permission.',
    {x:0.8,y:6.51,w:11.7,h:0.4,fontFace:BODY,fontSize:10.5,italic:true,bold:true,color:'FFFFFF',valign:'middle',margin:0});
  notes(s,'Make the fail-closed principle vivid. Each of these is a distinct guard, and in every case the workflow stops and returns an auditable reason to the change record rather than proceeding on uncertainty. This is the heart of the safety story: the system prefers a safe stop over an unsafe action.');
})();

/* 23-24 UC-5 module-by-module */
function moduleWalk(title, rows){
  const s=slide();
  header(s,'UC-5 · Autonomous change execution',title);
  const head=['Module','Receives','Question it answers','Adds','Sends next','If information is missing'];
  const colW=[1.55,2.15,2.5,1.9,1.75,2.5];
  const table=[head.map(h=>({text:h,options:{fill:{color:INK},color:'FFFFFF',bold:true,fontSize:10.5,valign:'middle'}}))];
  rows.forEach((r,ri)=>table.push(r.map((c,ci)=>({text:c,options:{fill:{color:ri%2?'F4F6FA':'FFFFFF'},color:ci===0?VIOLET_DK:INK,bold:ci===0,fontSize:9.6,valign:'top'}}))));
  TB(s,table,{x:0.5,y:1.55,w:12.35,colW,border:{type:'solid',color:HAIR,pt:0.75},rowH:0.4,fontFace:BODY,valign:'top',autoPage:false});
  footnote(s,'Each module reads or references business context and emits a SEPARATE governance artifact — it does not rewrite CHG0048217.');
  return s;
}
notes(moduleWalk('Module-by-module walkthrough (1 of 2)',[
  ['Decision Authority','Proposed change, delegated authority, constraints','Is there a binding decision within delegated scope, by a non-AI principal?','A binding decision record','To ActionGate','No delegated authority → no binding decision; stop'],
  ['ActionGate','Decision record, cluster identity, proposed action','Is this the exact authorized action, still valid?','An exact-target action authorization','To Action Clearance','Mismatch or uncertainty → INDETERMINATE; stop'],
  ['Action Clearance','The authorization + current live conditions','Is it operationally safe right now?','A CLEAR / HOLD / BLOCK / ESCALATE verdict','To Agent Runtime (on CLEAR)','Unsafe or unknown live state → HOLD / BLOCK'],
]),'Walk the authorization half. Decision Authority proves delegation (and bars AI as principal). ActionGate binds to the exact cluster/action and refuses to promote uncertainty. Action Clearance is the independent live-safety veto. In every row, missing information produces a safe stop, not a guess.');

notes(moduleWalk('Module-by-module walkthrough (2 of 2)',[
  ['Agent Runtime','The governed request (on CLEAR)','How is execution coordinated safely?','An execution receipt; owns canonical execution state','Invokes Cloud Scaling Operations; carries receipt to RA-8','No governance wired → fails closed; blocks'],
  ['Cloud Scaling Operations','A scaling instruction + external execution authorization','Is it ready, and bounded to the authorization?','Execution outcome + audit','Returns result to Agent Runtime','No execution authorization → dry-run only; no live change'],
  ['RA-8 Execution Assurance','Authorized action, receipt, observed cluster state','Did only the authorized instances change, within scope?','matched / mismatch / partial / unknown','Status + receipt refs to ServiceNow','Cannot verify → uncertain / manual review; never auto-authorize'],
]),'Walk the execution half and reinforce the corrected architecture: Agent Runtime coordinates and INVOKES Cloud Scaling Operations, which returns its result to the runtime; the runtime carries the receipt to RA-8. Cloud Scaling Operations is dry-run by default and needs an external execution authorization. RA-8 reconciles intent, evidence and effect — and never retro-authorizes.');

/* 25. UC-5 outcome + maturity */
(()=>{ const s=slide();
  header(s,'UC-5 · Autonomous change execution','Business outcome, and the Cloud Scaling maturity picture');
  card(s,0.6,1.5,6.0,3.05,{title:'Business & pilot outcome',tcolor:VIOLET_DK,fill:'FFFFFF',line:VIOLET,
    body:'•  Benefit: latency relief without waiting on a human\n•  Risk prevented: wrong cluster, freeze-time change, cost overrun\n•  Evidence produced: decision · authorization · clearance · receipt · effect-match — one lineage per change\n•  ServiceNow retains: change record, CMDB, windows, execution pathway\n•  Ugence contributes: exact-action authority, independent clearance, effect reconciliation\n•  Pilot metrics: change success rate; rollback frequency; unauthorized-target attempts blocked; effect-match rate',bfs:10.5});
  card(s,6.75,1.5,6.0,3.05,{title:'Possible governed-value measures',tcolor:TEAL_DK,fill:'FFFFFF',line:TEAL,badge:'UNDER DEVELOPMENT',badgeW:1.8,
    body:'A developing, cross-cutting capability (not an authorization gate):\n\n•  Infrastructure cost held within the ceiling\n•  Service availability preserved\n•  Latency improvement attributed to the governed action\n•  No change-window, risk or availability violation\n\nServiceNow AI Control Tower already measures adoption, business impact, realized value and ROI.',bfs:10.5});
  // maturity 4 dims
  SH(s,pptx.ShapeType.roundRect,{x:0.6,y:4.75,w:12.1,h:1.95,rectRadius:0.07,fill:{color:GREY_LT},line:{color:HAIR,width:1}});
  T(s,'Cloud Scaling maturity — four separate dimensions (do not conflate)',{x:0.8,y:4.85,w:11.6,h:0.34,fontFace:BODY,fontSize:12.5,bold:true,color:INK});
  const dims=[['Core Cloud Scaling Controller','IMPLEMENTED'],['Production validation','PILOT PENDING'],['Additional agentic-AI capabilities','UNDER DEVELOPMENT'],['ServiceNow integration','PROPOSED INTEGRATION']];
  dims.forEach((d,i)=>{ const x=0.8+i*3.0;
    SH(s,pptx.ShapeType.roundRect,{x,y:5.28,w:2.82,h:1.28,rectRadius:0.06,fill:{color:'FFFFFF'},line:{color:HAIR,width:1}});
    T(s,d[0],{x:x+0.14,y:5.4,w:2.55,h:0.62,fontFace:BODY,fontSize:10.5,bold:true,color:INK,valign:'top',margin:0,lineSpacingMultiple:1.0});
    badge(s,x+0.14,6.06,d[1],2.5);
  });
  footnote(s,'The core controller is IMPLEMENTED and awaiting pilot validation — it is not downgraded because additional capabilities or pilot validation remain pending.');
  notes(s,'Close UC-5 on value and honesty. Make the maturity distinction explicit: the CORE controller is IMPLEMENTED; production validation is PILOT PENDING; additional agentic-AI capabilities are UNDER DEVELOPMENT; the ServiceNow integration is PROPOSED. Do NOT let the four collapse into one label. Governed value is developing and cross-cutting, and AICT already measures ROI — our proposed addition is attribution, not a new gate.');
})();

/* SECTION V */
divider('V','Additional enterprise scenarios','UC-11 · UC-6 · UC-3 · UC-4 — each at both levels');

/* helper: compact technical vertical diagram */
function techDiagram(s, cx, bw, y0, ns, stopFrom, stopLabels, gap){
  const p=flow(s,cx,y0,bw,ns,gap||0.2);
  return p;
}

/* 27. UC-11 problem+input */
(()=>{ const s=slide();
  header(s,'UC-11 · Vulnerability remediation & emergency patching','The problem and the data entering the workflow');
  T(s,'An AI agent proposes to deploy an emergency patch to production servers. Speed matters — but patching the wrong set of servers, patching a business-critical system at the wrong moment, or continuing after the risk picture worsens mid-rollout can cause the very outage the patch was meant to prevent.',
    {x:0.6,y:1.45,w:6.0,h:1.5,fontFace:BODY,fontSize:12,color:INK,lineSpacingMultiple:1.1});
  T(s,[{text:'Illustrative:  ',options:{bold:true}},{text:'VUL0007731 → remediation task → change record · critical RCE on a web tier · 40 CIs in “payments-web” · emergency patch · staged rollout · ability to stop mid-flight.',options:{italic:true}}],
    {x:0.6,y:3.0,w:6.0,h:1.1,fontFace:BODY,fontSize:10.5,color:INK,lineSpacingMultiple:1.05});
  T(s,'Why staged rollout matters',{x:0.6,y:4.15,w:6.0,h:0.3,fontFace:BODY,fontSize:12,bold:true,color:VIOLET_DK});
  T(s,[['Each stage is cleared for live conditions and business-criticality before it runs'],['If the risk posture worsens, authority can be revoked before the next server is touched'],['Only the authorized configuration items are ever changed']].map(t=>({text:t[0],options:{bullet:{code:'2022',indent:12},breakLine:true,paraSpaceAfter:5}})),
    {x:0.65,y:4.5,w:5.9,h:1.6,fontFace:BODY,fontSize:10.5,color:INK});
  const head=['Data category','Example','Source'];
  const rows=[['Business record','Remediation task + change record, approval state','ServiceNow Vulnerability Response + Change'],
    ['Target context','40 CIs in payments-web, the patch','CMDB / Security Operations'],
    ['Live conditions','Business-criticality, maintenance window, risk posture','ServiceNow + telemetry'],
    ['Governance context','Delegated emergency-patch authority, expiry, revocability','Approved enterprise policy']];
  const table=[head.map(h=>({text:h,options:{fill:{color:INK},color:'FFFFFF',bold:true,fontSize:9.5,valign:'middle'}}))];
  rows.forEach((r,ri)=>table.push(r.map((c,ci)=>({text:c,options:{fill:{color:ri%2?'F4F6FA':'FFFFFF'},color:ci===0?VIOLET_DK:INK,bold:ci===0,fontSize:9,valign:'top'}}))));
  TB(s,table,{x:6.75,y:1.45,w:5.95,colW:[1.75,2.5,1.7],border:{type:'solid',color:HAIR,pt:0.75},fontFace:BODY,valign:'top',autoPage:false});
  footnote(s,'ServiceNow Vulnerability Response creates remediation tasks and links them to change for approval and emergency workflows. Illustrative example.');
  notes(s,'Set up UC-11 as a security scenario where blast radius and timing are everything. Emphasize the two distinctive controls the next slide shows: per-stage live clearance, and mid-rollout revocation. Acknowledge ServiceNow Vulnerability Response already creates and links remediation tasks — Ugence adds exact-CI binding, independent clearance, revocation and reconciliation.');
})();

/* 28. UC-11 technical */
(()=>{ const s=slide();
  header(s,'UC-11 · Vulnerability remediation','Technical module workflow — with mid-rollout revocation');
  legend(s,0.6,1.26,[['ServiceNow','SNOW',1.2],['Ugence decision','UDEC',1.7],['Ugence execution','UEXE',1.8],['External','EXT',0.8],['Stop','STOP',0.7]]);
  const cx=5.2,bw=3.0;
  const ns=[{t:'ServiceNow Vuln. Response + Change',cat:'SNOW',arrow:'remediation task + approval',fs:10},
    {t:'Decision Authority',cat:'UDEC',arrow:'binding decision record'},
    {t:'ActionGate',cat:'UDEC',arrow:'exact CI-set + patch authorization'},
    {t:'Action Clearance (ACP)',cat:'UDEC',arrow:'CLEAR per stage'},
    {t:'Agent Runtime · staged rollout',cat:'UEXE',arrow:'execution receipts'},
    {t:'RA-8 Execution Assurance',cat:'UEXE',arrow:'matched / partial'},
    {t:'ServiceNow Remediation + Change record',cat:'SNOW',arrow:null,fs:9.5,h:0.6}];
  const p=flow(s,cx,1.58,bw,ns,0.26);
  // target cylinder left of agent runtime
  const ar=p[4]; cyl(s,0.75,ar.mid-0.33,1.9,0.62,'40 CIs\npayments-web','EXT',{fs:9});
  conn(s,ar.x,ar.mid-0.1,2.65,ar.mid-0.1,'staged patch',{w:1.25,fs:7});
  conn(s,2.65,ar.mid+0.16,ar.x,ar.mid+0.16,'per-stage outcome',{w:1.5,fs:7});
  // RA-6 revoke into ACP
  node(s,0.6,p[3].mid-0.33,2.3,0.66,'RA-6 Authority lifecycle\nrevoke / supersede / expire','UDEC',{fs:8.5});
  conn(s,2.9,p[3].mid,p[3].x,p[3].mid,'risk changed → revoke',{w:1.55,fs:7,color:AMBER,dash:'dash'});
  // stop column
  const sx=8.85,sTop=p[2].top,sBot=p[3].bot;
  SH(s,pptx.ShapeType.roundRect,{x:sx,y:sTop,w:2.5,h:sBot-sTop,rectRadius:0.06,fill:{color:RED_LT},line:{color:RED,width:1.25}});
  T(s,'HOLD / BLOCK / ESCALATE\nremaining stages stopped',{x:sx+0.1,y:sTop,w:2.3,h:sBot-sTop,fontFace:BODY,fontSize:10,bold:true,color:RED_DK,align:'center',valign:'middle',margin:2});
  conn(s,p[2].x+bw,p[2].mid,sx,p[2].mid,'DENIED / INDET.',{w:1.6,fs:7.5,color:RED});
  conn(s,p[3].x+bw,p[3].mid,sx,p[3].mid,'HOLD / BLOCK',{w:1.5,fs:7.5,color:RED});
  conn(s,sx+1.25,sBot,sx+1.25,p[6].mid,'reason + evidence',{w:1.6,fs:7.5});
  seg(s,sx+1.25,p[6].mid,p[6].x+bw,p[6].mid);
  footnote(s,'Revocation is bounded-latency: it stops the next stage at the pre-effect recheck, not one already in progress. Illustrative example.');
  notes(s,'Same spine as UC-5 but note two differences: the rollout is staged (per-stage CLEAR), and RA-6 can revoke authority mid-rollout — the dashed amber arrow into Action Clearance. Revocation is bounded-latency: it stops the NEXT stage, not one already running. Agent Runtime coordinates the staged rollout and carries receipts to RA-8.');
})();

/* 29. UC-11 module + metrics */
(()=>{ const s=slide();
  header(s,'UC-11 · Vulnerability remediation','Human-control boundary, and business & pilot metrics');
  card(s,0.6,1.5,6.0,5.1,{title:'Human-control boundary',tcolor:VIOLET_DK,fill:VIOLET_LT,line:VIOLET,
    body:'•  Autonomous: per-stage clearance and patching INSIDE the authorized CI set and window\n\n•  Forces HOLD / ESCALATE: peak-trading or criticality hold, window closed, expired authority, a revocation signal\n\n•  Human-binding: the emergency-patch authority delegation; any CI outside the authorized set\n\n•  Limits: named CI set, staged rollout, reversibility, revocability mid-flight\n\n•  Fail-closed: missing approval, evidence, clearance or execution confirmation is never permission',bfs:11});
  card(s,6.75,1.5,6.0,5.1,{title:'Business outcome & pilot metrics',tcolor:TEAL_DK,fill:'FFFFFF',line:TEAL,
    body:'Benefit:  faster mean-time-to-remediation for critical vulnerabilities.\nRisk prevented:  out-of-scope or business-critical systems patched at the wrong moment; runaway rollout after risk worsens.\nEvidence:  per-stage authorization, clearance, receipts, revocation record, effect-match.\n\nPossible pilot metrics:\n•  Mean-time-to-remediation\n•  Unauthorized-target attempts blocked\n•  % of stages correctly stopped on revocation\n•  Effect-match rate\n\nGoverned-value (developing):  exposure-window reduction attributed to governed remediation, with preserved availability.',bfs:10.5});
  footnote(s,'Governed-value attribution is a developing, cross-cutting capability — not an authorization gate.');
  notes(s,'Close UC-11 on control and measurement. The boundary slide is where a security leader confirms nothing consequential happens without delegated authority, and that revocation gives a hard stop mid-rollout. Pilot metrics are concrete and security-relevant. Keep governed value labelled developing.');
})();

/* 30. UC-6 problem + layman */
(()=>{ const s=slide();
  header(s,'UC-6 · Access provisioning with segregation of duties','The problem, and the business journey');
  T(s,'An employee asks a self-service assistant for elevated access — for example, the ability to both create and approve payments. An AI agent could fulfil it in seconds. But granting an entitlement that breaks segregation of duties, or that the requester’s current risk posture should block, can create fraud exposure that is hard to unwind.',
    {x:0.6,y:1.45,w:6.0,h:1.7,fontFace:BODY,fontSize:12,color:INK,lineSpacingMultiple:1.12});
  T(s,[{text:'Illustrative:  ',options:{bold:true}},{text:'RITM0102934 · a finance analyst who already holds “create payment” requests “approve payment” in the ERP · an SoD rule prohibits one person holding both.',options:{italic:true}}],
    {x:0.6,y:3.25,w:6.0,h:1.0,fontFace:BODY,fontSize:10.5,color:INK,lineSpacingMultiple:1.05});
  T(s,'ServiceNow already provides Service Catalog request fulfilment, entitlement management, and Veza-based identity and least-privilege controls. Ugence proposes exact-entitlement authorization and an independent SoD clearance.',
    {x:0.6,y:4.35,w:6.0,h:1.1,fontFace:BODY,fontSize:10.5,italic:true,color:MUTED,lineSpacingMultiple:1.08});
  // layman flow on right
  const cx=9.7,bw=2.7;
  const ns=[{t:'Employee requests elevated access',cat:'SNOW',arrow:'self-service'},
    {t:'Approval confirmed for this exact entitlement',cat:'UDEC',arrow:'delegated'},
    {t:'Any conflict? safe now?',cat:'UEXE',arrow:'SoD + risk posture'},
    {t:'Granted, or blocked for review',cat:'UEXE',arrow:'auditable either way'},
    {t:'Result returned to the request',cat:'SNOW',arrow:null}];
  flow(s,cx,1.5,bw,ns,0.3);
  footnote(s,'Illustrative example — not a customer deployment.');
  notes(s,'UC-6 is a fraud-prevention story. The decisive control is the SoD conflict check at clearance time. Keep the left side plain-language, the right side a simple journey. Acknowledge ServiceNow + Veza identity controls; Ugence adds exact-entitlement binding and an independent SoD veto.');
})();

/* 31. UC-6 technical */
(()=>{ const s=slide();
  header(s,'UC-6 · Access provisioning','Technical module workflow — segregation-of-duties veto');
  legend(s,0.6,1.26,[['ServiceNow','SNOW',1.2],['Ugence decision','UDEC',1.7],['Ugence execution','UEXE',1.8],['External','EXT',0.8],['Stop','STOP',0.7]]);
  const cx=5.2,bw=3.0;
  const ns=[{t:'ServiceNow Service Catalog · RITM0102934',cat:'SNOW',arrow:'access request + approval',fs:9.5},
    {t:'Decision Authority',cat:'UDEC',arrow:'binding decision record'},
    {t:'ActionGate',cat:'UDEC',arrow:'exact-entitlement authorization'},
    {t:'Action Clearance · SoD + risk veto',cat:'UDEC',arrow:'CLEAR',fs:10},
    {t:'Agent Runtime · provisioning',cat:'UEXE',arrow:'execution receipt'},
    {t:'RA-8 Execution Assurance',cat:'UEXE',arrow:'only authorized entitlement granted'},
    {t:'ServiceNow Request record',cat:'SNOW',arrow:null,fs:10}];
  const p=flow(s,cx,1.58,bw,ns,0.26);
  const ar=p[4]; cyl(s,0.85,ar.mid-0.3,1.9,0.6,'ERP entitlement\nsystem','EXT',{fs:9});
  conn(s,ar.x,ar.mid-0.08,2.75,ar.mid-0.08,'provision',{w:1.05,fs:7});
  conn(s,2.75,ar.mid+0.16,ar.x,ar.mid+0.16,'outcome',{w:1.05,fs:7});
  const sx=8.85,sTop=p[2].top,sBot=p[3].bot;
  SH(s,pptx.ShapeType.roundRect,{x:sx,y:sTop,w:2.5,h:sBot-sTop,rectRadius:0.06,fill:{color:RED_LT},line:{color:RED,width:1.25}});
  T(s,'BLOCK / ESCALATE\nno grant · human review',{x:sx+0.1,y:sTop,w:2.3,h:sBot-sTop,fontFace:BODY,fontSize:10,bold:true,color:RED_DK,align:'center',valign:'middle',margin:2});
  conn(s,p[2].x+bw,p[2].mid,sx,p[2].mid,'DENIED / INDET.',{w:1.6,fs:7.5,color:RED});
  conn(s,p[3].x+bw,p[3].mid,sx,p[3].mid,'SoD conflict → BLOCK',{w:1.8,fs:7.5,color:RED});
  conn(s,sx+1.25,sBot,sx+1.25,p[6].mid,'SoD reason + evidence',{w:1.9,fs:7.5});
  seg(s,sx+1.25,p[6].mid,p[6].x+bw,p[6].mid);
  footnote(s,'The decisive control is the SoD conflict at clearance time — the action can be perfectly authorized and still be blocked. Illustrative.');
  notes(s,'The teaching point: even a perfectly valid authorization is blocked when Action Clearance detects an SoD conflict — authorization and clearance are independent. On a clean request, Agent Runtime provisions in the ERP, the result returns, and RA-8 confirms ONLY the authorized entitlement was granted.');
})();

/* 32. UC-6 human control + metrics */
(()=>{ const s=slide();
  header(s,'UC-6 · Access provisioning','Human-control boundary, and business & pilot metrics');
  card(s,0.6,1.5,6.0,5.1,{title:'Human-control boundary',tcolor:VIOLET_DK,fill:VIOLET_LT,line:VIOLET,
    body:'•  Autonomous: fulfilling entitlements with NO SoD conflict and a clear risk posture\n\n•  Forces HOLD / ESCALATE / BLOCK: any SoD conflict, elevated risk posture, disabled account, expired authority\n\n•  Human-binding: the access-grant authority delegation; any entitlement outside scope\n\n•  Limits: exactly one entitlement per authorization; reversibility; SoD rule as a hard veto\n\n•  Fail-closed: if SoD state or approval cannot be established, the request is not treated as permitted',bfs:11});
  card(s,6.75,1.5,6.0,5.1,{title:'Business outcome & pilot metrics',tcolor:TEAL_DK,fill:'FFFFFF',line:TEAL,
    body:'Benefit:  fast self-service access without a queue.\nRisk prevented:  SoD violations and fraud exposure; silent AI self-grant.\nEvidence:  decision, exact-entitlement authorization, SoD clearance, effect-match (or a clean “no change” on block).\n\nPossible pilot metrics:\n•  Access-policy violations prevented\n•  % of grants with matched effect\n•  Time saved per request\n•  Unauthorized-entitlement attempts blocked\n\nGoverned-value (developing):  fraud-exposure reduction attributed to blocked SoD conflicts, with preserved compliance.',bfs:10.5});
  footnote(s,'Governed-value attribution is a developing, cross-cutting capability — not an authorization gate.');
  notes(s,'Close UC-6 for a risk/compliance owner: nothing is granted that breaks SoD, the AI never self-grants, and a blocked request produces a clean “no change” with an SoD reason. Metrics are audit-relevant. Governed value stays developing.');
})();

/* 33. UC-3 problem */
(()=>{ const s=slide();
  header(s,'UC-3 · High-risk AI action enforcement','A concrete, regulated illustrative example');
  SH(s,pptx.ShapeType.roundRect,{x:0.6,y:1.45,w:12.1,h:1.0,rectRadius:0.06,fill:{color:VIOLET_LT},line:{color:VIOLET,width:1}});
  T(s,[{text:'Illustrative (privileged system access).  ',options:{bold:true,color:VIOLET_DK}},{text:'An AI use case classified high-risk is about to grant privileged production access automatically. The policy is approved and controls are on file — but at the moment of action, is every required control currently satisfied by trusted, re-checked evidence, or is the system relying on a stale, self-asserted “pass”?  Acting on out-of-date compliance evidence is exactly what audits punish.',options:{color:INK}}],
    {x:0.85,y:1.5,w:11.6,h:0.92,fontFace:BODY,fontSize:11,valign:'middle',margin:0,lineSpacingMultiple:1.05});
  T(s,'Discovery questions (not claims about ServiceNow)',{x:0.6,y:2.65,w:6.0,h:0.32,fontFace:BODY,fontSize:12.5,bold:true,color:VIOLET_DK});
  T(s,[['Is each control satisfied by trusted, re-checked evidence — not a caller-asserted pass?'],['Is the resulting permission a signed, scoped, time-limited artifact a downstream gate can verify?'],['Did the action that ran stay within the authorized scope?']].map(t=>({text:t[0],options:{bullet:{code:'2022',indent:12},breakLine:true,paraSpaceAfter:8}})),
    {x:0.65,y:3.05,w:5.95,h:2.0,fontFace:BODY,fontSize:11,color:INK,lineSpacingMultiple:1.05});
  card(s,6.75,2.65,6.0,3.9,{title:'System-of-record stays with ServiceNow',tcolor:GREEN_DK,fill:GREEN_LT,line:GREEN,
    body:'AI Control Tower and AI Risk & Compliance remain the governance systems of record — classification, multi-framework control mapping (EU AI Act, NIST AI RMF and others), and enforcement.\n\nUgence proposes an independently verifiable, action-level authority artifact linked to CURRENT evidence — so a stale or self-asserted control cannot wave an action through.\n\nAnything not established in ServiceNow documentation is treated as a discovery hypothesis, not a claim.',bfs:11});
  footnote(s,'Illustrative example — not a customer deployment. AICT / AI Risk & Compliance remain the governance systems of record.');
  notes(s,'Do not leave “high-risk” abstract — anchor it to privileged production access. The point is evidence freshness: an approved policy is not enough if the control evidence is stale. ServiceNow AICT/AIRC remain the systems of record; Ugence proposes a signed, evidence-linked, action-level authority. Frame anything unverified as a discovery hypothesis.');
})();

/* 34. UC-3 technical */
(()=>{ const s=slide();
  header(s,'UC-3 · High-risk AI action enforcement','Technical module workflow — evidence-linked signed authority');
  legend(s,0.6,1.26,[['ServiceNow','SNOW',1.2],['Ugence decision','UDEC',1.7],['Ugence execution','UEXE',1.8],['External','EXT',0.8],['Stop','STOP',0.7]]);
  const cx=3.3,bw=3.2;
  const ns=[{t:'ServiceNow AI Control Tower / IRM',cat:'SNOW',arrow:'policy pack + control evidence refs',fs:10},
    {t:'Policy Workflow Compiler + RA-5 trusted evidence',cat:'UDEC',arrow:'re-checked control result',fs:9.5,h:0.7},
    {t:'Decision Authority',cat:'UDEC',arrow:'binding decision record'},
    {t:'Risk Authority · signed, scoped, time-limited',cat:'UDEC',arrow:'signed authorization artifact',fs:9.5},
    {t:'ActionGate',cat:'UDEC',arrow:'exact-action authorization'},
    {t:'Agent Runtime → execution → RA-8 assurance',cat:'UEXE',arrow:'effect matched',fs:9.5},
    {t:'ServiceNow AI case record (authorization + effect refs)',cat:'SNOW',arrow:null,fs:9,h:0.6}];
  const p=flow(s,cx,1.55,bw,ns,0.22);
  const sx=8.0,sTop=p[1].top,sBot=p[4].bot;
  SH(s,pptx.ShapeType.roundRect,{x:sx,y:sTop,w:2.6,h:sBot-sTop,rectRadius:0.06,fill:{color:RED_LT},line:{color:RED,width:1.25}});
  T(s,'NOT PERMITTED\n\nstale / untrusted evidence\nno allow-family decision\nDENIED / INDETERMINATE',{x:sx+0.1,y:sTop,w:2.4,h:sBot-sTop,fontFace:BODY,fontSize:9.5,bold:true,color:RED_DK,align:'center',valign:'middle',margin:2,lineSpacingMultiple:1.05});
  conn(s,p[1].x+bw,p[1].mid,sx,p[1].mid,'evidence stale',{w:1.4,fs:7.5,color:RED});
  conn(s,p[3].x+bw,p[3].mid,sx,p[3].mid,'no allow-family',{w:1.5,fs:7.5,color:RED});
  conn(s,p[4].x+bw,p[4].mid,sx,p[4].mid,'DENIED / INDET.',{w:1.6,fs:7.5,color:RED});
  conn(s,sx+1.3,sBot,sx+1.3,p[6].mid,'reason + evidence',{w:1.6,fs:7.5});
  seg(s,sx+1.3,p[6].mid,p[6].x+bw,p[6].mid);
  footnote(s,'A caller-asserted “pass” is inert: only trusted, re-checked evidence satisfies a control. The authorization is signed, scoped and time-limited. Illustrative.');
  notes(s,'Trace the evidence-first path: compiled policy + RA-5 trusted evidence → a re-checked control result (a stale “pass” is inert) → Decision Authority → Risk Authority mints a signed, scoped, time-limited authorization → ActionGate enforces the exact action → execution → RA-8. Three stop conditions all route to NOT PERMITTED. Position Risk Authority as the sole issuer of the signed artifact.');
})();

/* 35. UC-3 positioning + metrics */
(()=>{ const s=slide();
  header(s,'UC-3 · High-risk AI action enforcement','Positioning, control boundary and metrics');
  card(s,0.6,1.5,6.0,5.1,{title:'Positioning (honest)',tcolor:VIOLET_DK,fill:VIOLET_LT,line:VIOLET,
    body:'•  ServiceNow AI Control Tower & AI Risk and Compliance remain the governance systems of record — this is a real, shipped strength.\n\n•  Ugence proposes a signed, scoped, time-limited, action-level authority whose validity depends on trusted, currently-satisfied evidence.\n\n•  Whether ServiceNow already emits an equivalent independently verifiable, evidence-fresh per-action artifact is a discovery hypothesis to confirm with architects — not an assumed gap.\n\n•  Human-binding: the policy approval and the authority delegation. Fail-closed: stale or self-asserted evidence is never a satisfied control.',bfs:10.8});
  card(s,6.75,1.5,6.0,5.1,{title:'Outcome & pilot metrics',tcolor:TEAL_DK,fill:'FFFFFF',line:TEAL,
    body:'Benefit:  high-risk automation that stays inside an evidence-backed, approved boundary.\nRisk prevented:  acting on stale compliance evidence; unbounded high-risk actions.\nEvidence:  re-checked control result, signed authorization, exact-action authorization, effect-match — an audit-ready chain.\n\nPossible pilot metrics:\n•  % of high-risk actions with fresh-evidence backing\n•  Stale-evidence blocks\n•  Effect-match rate\n\nGoverned-value (developing):  audit-finding reduction attributed to evidence-fresh enforcement, with preserved compliance constraints.',bfs:10.5});
  footnote(s,'Unverified differentiation is stated as a discovery hypothesis, never as a ServiceNow gap.');
  notes(s,'This is the slide where discipline matters most. Credit AICT/AIRC generously. State the Ugence proposal narrowly — a signed, evidence-fresh, action-level artifact — and immediately flag that whether ServiceNow already does this is a question for their architects. Metrics are audit-centric.');
})();

/* 36. UC-4 problem+layman */
(()=>{ const s=slide();
  header(s,'UC-4 · External agents via Action Fabric & A2A / MCP','The problem, and the business journey');
  T(s,'Enterprises now let external AI agents (for example Claude or Copilot) take real actions on enterprise systems. ServiceNow Action Fabric opens its system of action to these agents and routes every action through AI Control Tower; with NVIDIA OpenShell, policy is enforced at runtime on file, command and network access.',
    {x:0.6,y:1.45,w:6.0,h:1.7,fontFace:BODY,fontSize:11.5,color:INK,lineSpacingMultiple:1.12});
  T(s,'The remaining question is narrow: for each business action an external agent takes, is there an independent, verifiable record that THIS exact action was authorized — and does anything notice when individually-allowed steps add up to something that should not be allowed?',
    {x:0.6,y:3.2,w:6.0,h:1.4,fontFace:BODY,fontSize:11.5,color:INK,lineSpacingMultiple:1.12});
  SH(s,pptx.ShapeType.roundRect,{x:0.6,y:4.7,w:6.0,h:1.75,rectRadius:0.06,fill:{color:GREEN_LT},line:{color:GREEN,width:1}});
  T(s,[{text:'Ownership (unchanged).  ',options:{bold:true,color:GREEN_DK}},{text:'Action Fabric owns the governed ServiceNow action pathway; NVIDIA OpenShell owns its runtime / sandbox enforcement. Ugence contributes authority, exact-action binding, evidence lineage, clearance, sequence-risk and assurance artifacts — composition, not replacement.',options:{color:INK}}],
    {x:0.8,y:4.8,w:5.65,h:1.55,fontFace:BODY,fontSize:10.5,valign:'middle',margin:0,lineSpacingMultiple:1.08});
  const cx=9.7,bw=2.7;
  const ns=[{t:'External AI agent proposes a step',cat:'EXT',arrow:'via Action Fabric'},
    {t:'Allowed model & exact action?',cat:'UDEC',arrow:'bound to payload'},
    {t:'Do the steps together look harmful?',cat:'UDEC',arrow:'sequence risk'},
    {t:'Enforced by the platform',cat:'SNOW',arrow:'Action Fabric + OpenShell'},
    {t:'Independent record to ServiceNow',cat:'SNOW',arrow:null}];
  flow(s,cx,1.5,bw,ns,0.28);
  footnote(s,'Ugence does not own or replace Action Fabric or OpenShell execution. Illustrative example.');
  notes(s,'This is the strongest overlap zone and a partnership-native one (Anthropic is ServiceNow’s design partner). Be explicit: ServiceNow already governs and enforces these actions, including at the kernel level via OpenShell. Ugence claims neither a gap nor unique cross-runtime enforcement — only the artifact properties. Read the green ownership box aloud.');
})();

/* 37. UC-4 technical */
(()=>{ const s=slide();
  header(s,'UC-4 · External agents','Technical module workflow — composition, not ownership');
  legend(s,0.6,1.24,[['ServiceNow','SNOW',1.2],['Ugence decision','UDEC',1.7],['Ugence execution','UEXE',1.8],['External','EXT',0.8],['Stop','STOP',0.7]]);
  const cx=4.55,bw=3.5;
  const ns=[{t:'External AI agent · Claude / Copilot / custom',cat:'EXT',arrow:'governed step request',fs:9.5},
    {t:'ServiceNow Action Fabric · via AI Control Tower',cat:'SNOW',arrow:'business action context',fs:9.5},
    {t:'Agent Runtime · governance-decision seam',cat:'UEXE',arrow:'per-step request',fs:9.5},
    {t:'Model Authority → ActionGate · exact payload',cat:'UDEC',arrow:'exact-payload authorization',fs:9.5},
    {t:'StoryGraph → Action Clearance (ACP)',cat:'UDEC',arrow:'CLEAR',fs:9.5},
    {t:'ServiceNow Action Fabric → dispatch',cat:'SNOW',arrow:'dispatch'},
    {t:'OpenShell runtime enforcement · ServiceNow–NVIDIA',cat:'EXT',arrow:'enforced execution result',fs:9.5},
    {t:'RA-7 Trajectory Assurance',cat:'UEXE',arrow:'assurance evidence'},
    {t:'ServiceNow case + AI Control Tower audit',cat:'SNOW',arrow:null,fs:9.5}];
  ns.forEach(n=>n.h=0.48);
  const p=flow(s,cx,1.48,bw,ns,0.1);
  // stop column right, spanning nodes 4-5 (the Ugence decision layer)
  const sx=8.85, sTop=p[3].top, sBot=p[4].bot;
  SH(s,pptx.ShapeType.roundRect,{x:sx,y:sTop,w:2.5,h:sBot-sTop,rectRadius:0.06,fill:{color:RED_LT},line:{color:RED,width:1.25}});
  T(s,'HOLD / BLOCK / ESCALATE\nvalue movement paused',{x:sx+0.1,y:sTop,w:2.3,h:sBot-sTop,fontFace:BODY,fontSize:9.5,bold:true,color:RED_DK,align:'center',valign:'middle',margin:2});
  conn(s,p[3].x+bw,p[3].mid,sx,p[3].mid,'DENY / DENIED',{w:1.4,fs:7.5,color:RED});
  conn(s,p[4].x+bw,p[4].mid,sx,p[4].mid,'ESCALATE seq-risk / HOLD',{w:1.9,fs:7.5,color:RED});
  conn(s,sx+1.25,sBot,sx+1.25,p[8].mid,'reason + evidence',{w:1.6,fs:7.5});
  seg(s,sx+1.25,p[8].mid,p[8].x+bw,p[8].mid);
  // ownership callout (left margin, clear of the column)
  SH(s,pptx.ShapeType.roundRect,{x:0.6,y:2.6,w:2.05,h:2.35,rectRadius:0.06,fill:{color:GREEN_LT},line:{color:GREEN,width:1}});
  T(s,'Ownership',{x:0.72,y:2.68,w:1.8,h:0.28,fontFace:BODY,fontSize:10,bold:true,color:GREEN_DK,margin:0});
  T(s,'Dispatch + runtime enforcement = ServiceNow (Action Fabric) + NVIDIA (OpenShell).\n\nUgence adds authority, exact-payload binding, sequence-risk and assurance only — composition, not replacement.',
    {x:0.72,y:3.0,w:1.82,h:1.9,fontFace:BODY,fontSize:8.6,color:INK,valign:'top',margin:0,lineSpacingMultiple:1.02});
  footnote(s,'Ugence does not own or replace Action Fabric or OpenShell execution. Illustrative example.');
  notes(s,'Trace it carefully to preserve ownership: the external agent goes through Action Fabric; Ugence’s Agent Runtime is an independent decision seam; Model Authority and ActionGate bind the exact payload; StoryGraph flags sequence risk; Action Clearance clears; then Action Fabric DISPATCHES and OpenShell ENFORCES at runtime; RA-7 observes the trajectory and returns assurance evidence to the ServiceNow audit context. The dispatch and enforcement boxes are ServiceNow / NVIDIA (green / grey); the Ugence boxes are authority, advisory and assurance only. Anthropic is ServiceNow’s Action Fabric design partner — partnership-native.');
})();

/* 38. UC-4 positioning + metrics */
(()=>{ const s=slide();
  header(s,'UC-4 · External agents','Positioning, ownership and metrics');
  card(s,0.6,1.5,6.0,5.1,{title:'Ownership & positioning',tcolor:VIOLET_DK,fill:VIOLET_LT,line:VIOLET,
    body:'•  Action Fabric owns the governed ServiceNow action pathway; every action is identity-verified, permission-scoped and auditable.\n\n•  NVIDIA OpenShell owns runtime / sandbox enforcement on file, command and network access.\n\n•  Ugence contributes: an independent, signed, exact-payload authorization; sequence-risk advisory across the plan; trajectory assurance — composition and partnership, not replacement.\n\n•  Ugence does NOT claim to own Action Fabric or OpenShell execution, nor unique cross-runtime enforcement.',bfs:10.8});
  card(s,6.75,1.5,6.0,5.1,{title:'Outcome & pilot metrics',tcolor:TEAL_DK,fill:'FFFFFF',line:TEAL,
    body:'Benefit:  external agents get real work done under a verifiable, independent authorization trail.\nRisk prevented:  an unauthorized payload, or a harmful combination of individually-allowed steps, moving value unnoticed.\nEvidence:  model authorization, exact-payload authorization, sequence-risk signal, trajectory assurance.\n\nPossible pilot metrics:\n•  Unauthorized-payload attempts blocked\n•  Sequence escalations caught\n•  % of actions with an independent authorization record\n\nGoverned-value (developing):  prevented-loss attributed to sequence and payload controls, with preserved service constraints.',bfs:10.3});
  footnote(s,'Anthropic is ServiceNow’s Action Fabric design partner — this is a partnership-native conversation.');
  notes(s,'Close UC-4 by reinforcing ownership and the partnership framing (Anthropic design partner). The differentiation is confined to artifact properties. Metrics center on unauthorized payloads and sequence escalations. Keep governed value developing.');
})();

/* SECTION VI PORTFOLIO */
divider('VI','The full use-case portfolio','All 12 scenarios — grounded in ServiceNow products, with proposed Ugence governance extensions');

function portfolio(subtitle, groupTitle, groupColor, cases){
  const s=slide();
  header(s,'Use-case portfolio',subtitle);
  T(s,groupTitle,{x:0.6,y:1.35,w:12.1,h:0.34,fontFace:BODY,fontSize:14,bold:true,color:groupColor});
  const n=cases.length; const perRow = n>3?2:n; const rows=Math.ceil(n/perRow);
  const cw=(12.1-(perRow-1)*0.25)/perRow; const ch = rows>1?2.45:4.9;
  cases.forEach((c,i)=>{ const col=i%perRow,row=Math.floor(i/perRow); const x=0.6+col*(cw+0.25), y=1.8+row*(ch+0.22);
    SH(s,pptx.ShapeType.roundRect,{x,y,w:cw,h:ch,rectRadius:0.06,fill:{color:'FFFFFF'},line:{color:HAIR,width:1},shadow:sh()});
    T(s,c.id+' · '+c.name,{x:x+0.16,y:y+0.12,w:cw-0.32,h:0.5,fontFace:BODY,fontSize:11.5,bold:true,color:VIOLET_DK,valign:'top',margin:0});
    badge(s,x+0.16,y+ch-0.36,c.badge,c.badgeW||1.7);
    const body=[{t:'Problem',v:c.problem},{t:'ServiceNow anchor',v:c.anchor},{t:'Ugence proposes',v:c.ugence},{t:'Autonomy',v:c.autonomy},{t:'Discovery',v:c.discovery}];
    let ty=y+0.6;
    const bh=(ch-1.05)/body.length;
    body.forEach(b=>{ T(s,[{text:b.t+':  ',options:{bold:true,color:INK}},{text:b.v,options:{color:INK}}],{x:x+0.16,y:ty,w:cw-0.32,h:bh,fontFace:BODY,fontSize:8.6,valign:'top',margin:0,lineSpacingMultiple:0.98}); ty+=bh; });
  });
  footnote(s,'Enterprise workflow scenarios grounded in actual ServiceNow products, with proposed Ugence governance extensions. Not proven deployments, production customer use cases, or existing integrations.');
  return s;
}

notes(portfolio('Pilot-ready operational scenarios','Group A — pilot-ready operational','2E7D5B',[
  {id:'UC-5',name:'Autonomous change execution',problem:'Scale/restart/config changes made autonomously',anchor:'Change Management + ITOM',ugence:'Exact-CI authority, independent clearance, effect reconciliation',autonomy:'Autonomous within window & cost; freeze/conflict force stop',discovery:'Which change + CMDB events are authoritative?',badge:'PROPOSED INTEGRATION',badgeW:2.0},
  {id:'UC-6',name:'Access provisioning with SoD',problem:'Elevated access fulfilled by an assistant',anchor:'Service Catalog / Employee Center + Veza',ugence:'Exact-entitlement authority + independent SoD clearance',autonomy:'Autonomous when no SoD conflict; conflict → block',discovery:'Which entitlement class suits a bounded pilot?',badge:'PROPOSED INTEGRATION',badgeW:2.0},
  {id:'UC-11',name:'Vulnerability remediation',problem:'Emergency patch to production CIs',anchor:'Security Operations — Vulnerability Response',ugence:'Exact-CI binding, per-stage clearance, mid-rollout revocation',autonomy:'Per-stage autonomy; revocation stops next stage',discovery:'Which critical-vuln workflow for a pilot?',badge:'PROPOSED INTEGRATION',badgeW:2.0},
]),'Group A are the most pilot-ready. UC-5 is the recommended first pilot. All three are available-now ServiceNow anchors with PROPOSED Ugence integration. Emphasize the catalog framing in the footnote — grounded ServiceNow products, proposed extensions, not deployments.');

notes(portfolio('Practical scenarios requiring bounded autonomy','Group B — bounded autonomy','B7791F',[
  {id:'UC-7',name:'Refunds & credits',problem:'AI issues a refund or credit',anchor:'Customer Service Management (Now Assist)',ugence:'Amount+account binding; reconcile executed = authorized',autonomy:'Within a delegated dollar threshold',discovery:'Which refund band is safe to pilot?',badge:'PROPOSED INTEGRATION',badgeW:2.0},
  {id:'UC-8',name:'Procurement / PO issuance',problem:'AI places a purchase order',anchor:'Sourcing & Procurement Operations',ugence:'Compiled policy, supplier-evidence check, exact PO binding',autonomy:'Threshold-bound; above → human authority',discovery:'Which spend threshold and category?',badge:'PROPOSED INTEGRATION',badgeW:2.0},
  {id:'UC-10',name:'Agentic hiring (human-binding)',problem:'AI assists screening & scheduling',anchor:'HR Service Delivery / Recruitment',ugence:'Keep hire/reject human; immutable decision record',autonomy:'Assistive only; decision stays human-binding',discovery:'Which step may be automated vs human-bound?',badge:'PROPOSED INTEGRATION',badgeW:2.0},
]),'Group B are practical but need tighter autonomy limits — money movement and hiring. In UC-10 the binding decision stays human by design (AI barred as principal), which is a compliance strength. All PROPOSED.');

notes(portfolio('Strategic governance scenarios','Group C — strategic governance','5145C7',[
  {id:'UC-2',name:'Per-request model authorization',problem:'Regulated data about to reach a model',anchor:'AI Control Tower model/provider governance',ugence:'Per-request ALLOW/DENY/HOLD/ESCALATE + fallback/expiry',autonomy:'Per-request binding, not a static allowlist',discovery:'Which data classes trigger per-request control?',badge:'PROPOSED INTEGRATION',badgeW:2.0},
  {id:'UC-3',name:'High-risk action enforcement',problem:'High-risk AI action on stale evidence',anchor:'AI Control Tower — AI Risk & Compliance',ugence:'Signed, scoped, evidence-fresh action authority',autonomy:'Only while trusted evidence is current',discovery:'Which high-risk use case for a pilot?',badge:'PROPOSED INTEGRATION',badgeW:2.0},
  {id:'UC-4',name:'External-agent governance',problem:'External agents act on the system of action',anchor:'Action Fabric + AI Agent Fabric + OpenShell',ugence:'Independent exact-payload authority, sequence-risk, assurance',autonomy:'Composes with platform enforcement',discovery:'Which external-agent workflow to pilot?',badge:'PROPOSED INTEGRATION',badgeW:2.0},
  {id:'UC-12',name:'Data-boundary governance',problem:'Agents pull enterprise data into context',anchor:'Workflow Data Fabric + AICT privacy',ugence:'Minimum-necessary context; token accounting; fail-closed',autonomy:'Governs exactly what crosses the model boundary',discovery:'Which data domains need boundary control?',badge:'PROPOSED INTEGRATION',badgeW:2.0},
]),'Group C are strategic governance plays that extend AI Control Tower into per-request and per-action enforcement. Keep the honest overlap posture (next section) in mind — position as extension of an approved governance state, framed as discovery where unverified.');

notes(portfolio('Emerging or future scenarios','Group D — emerging / future','D97706',[
  {id:'UC-1',name:'Autonomous security containment',problem:'Autonomous host isolation / account disable / IP block',anchor:'Security Incident Response — Tier 2 SOC AI Specialist',ugence:'Exact-target authority, live-safety clearance, effect reconciliation',autonomy:'Forward-looking; not shipped',discovery:'When the specialist ships, where does authority bind?',badge:'ANNOUNCED / FUTURE',badgeW:2.0},
  {id:'UC-9',name:'Governed multi-agent workforce',problem:'A team of agents runs an end-to-end process',anchor:'AI Agent Orchestrator / Autonomous Workforce',ugence:'Least-privilege team plan granting nothing; per-action authorization + sequence risk',autonomy:'Composition grants no authority',discovery:'Which multi-agent process to bound first?',badge:'PROPOSED INTEGRATION',badgeW:2.0},
]),'Group D are emerging. UC-1 is explicitly ANNOUNCED/FUTURE — the Tier 2 SOC AI Specialist is expected December 2026 and has not shipped; present it as “where this goes,” never as available. UC-9 is a composition play that grants no authority.');

/* SECTION VII */
divider('VII','Honest overlap & differentiation','Name the overlaps first — then the narrow, artifact-level differentiation');

/* 45. OVERLAP ZONES */
(()=>{ const s=slide();
  header(s,'Honest overlap','Confirmed overlap zones — discussed as overlaps, not gaps');
  const head=['Zone','ServiceNow capability','Ugence proposed edge (narrow)'];
  const rows=[['ActionGate ↔ Action Fabric / AICT','Governed, identity-verified, auditable action execution','Per-payload/target authorization re-checked at commit (discovery hypothesis)'],
    ['RA-7 ↔ Agent Deviation Detection','Flags when an agent strays from its role','Independently verifiable trajectory signal into an authority lifecycle'],
    ['RA-6 ↔ real-time shutdown','Can stop a misbehaving agent','Authority-lifecycle revoke/epoch; enforcement stays read-only'],
    ['Model Authority ↔ Skill-Kit approval','Restricts which models run','Per-request binding decision with governed fallback + expiry'],
    ['AICT + NVIDIA OpenShell','Central policy enforced at runtime across file/command/network','Ugence does NOT claim unique cross-runtime enforcement — differentiation is the artifact']];
  const table=[head.map(h=>({text:h,options:{fill:{color:INK},color:'FFFFFF',bold:true,fontSize:11,valign:'middle'}}))];
  rows.forEach((r,ri)=>table.push(r.map((c,ci)=>({text:c,options:{fill:{color:ri%2?'F4F6FA':'FFFFFF'},color:ci===0?VIOLET_DK:INK,bold:ci===0,fontSize:10,valign:'middle'}}))));
  TB(s,table,{x:0.6,y:1.6,w:12.1,colW:[3.4,4.2,4.5],border:{type:'solid',color:HAIR,pt:0.75},rowH:0.9,fontFace:BODY,valign:'middle',autoPage:false});
  footnote(s,'Absence from public documentation is never treated as proof ServiceNow lacks a property — those points are questions for ServiceNow architects.');
  notes(s,'Name every overlap zone yourself, before the reviewer does — it is the fastest way to earn trust. The OpenShell row is the one to get exactly right: ServiceNow already enforces at runtime across form factors, so we explicitly do not claim unique cross-runtime enforcement. Where the Ugence edge is unconfirmed, say “discovery hypothesis.”');
})();

/* 46. DIFFERENTIATION */
(()=>{ const s=slide();
  header(s,'Differentiation','The narrow, defensible edge — properties of one authority artifact');
  T(s,'Ugence does not claim a governance gap or unique cross-runtime enforcement. The differentiation is confined to the properties of an independent, action-level authority-and-evidence artifact:',
    {x:0.6,y:1.45,w:12.1,h:0.7,fontFace:BODY,fontSize:12.5,color:INK,lineSpacingMultiple:1.08});
  const props=[['Independently verifiable','by a party other than the executor'],
    ['Bound to the exact business action & target','not a class of action'],
    ['Linked to trusted evidence','stale or self-asserted evidence is inert'],
    ['Scoped & time-limited','scope never exceeds the decision'],
    ['Re-checked before consequential execution','at commit time'],
    ['Separated from live operational clearance','independent, subtractive veto'],
    ['Connected to execution receipts','what actually ran'],
    ['Reconciled against observed effect','intent vs reality'],
    ['Usable in a cross-stage evidence lineage','one story per action']];
  props.forEach((p,i)=>{ const col=i%3,row=Math.floor(i/3); const x=0.6+col*4.07,y=2.35+row*1.42;
    SH(s,pptx.ShapeType.roundRect,{x,y,w:3.85,h:1.28,rectRadius:0.06,fill:{color:VIOLET_LT},line:{color:VIOLET,width:1}});
    SH(s,pptx.ShapeType.ellipse,{x:x+0.16,y:y+0.16,w:0.34,h:0.34,fill:{color:VIOLET},line:{width:0}});
    T(s,String(i+1),{x:x+0.16,y:y+0.16,w:0.34,h:0.34,fontFace:BODY,fontSize:11,bold:true,color:'FFFFFF',align:'center',valign:'middle',margin:0});
    T(s,p[0],{x:x+0.6,y:y+0.14,w:3.15,h:0.6,fontFace:BODY,fontSize:10.5,bold:true,color:VIOLET_DK,margin:0,valign:'middle'});
    T(s,p[1],{x:x+0.6,y:y+0.72,w:3.15,h:0.5,fontFace:BODY,fontSize:9.5,italic:true,color:INK,margin:0});
  });
  footnote(s,'These properties are the whole differentiation. Everything else in the deck is a variation on this one boundary.');
  notes(s,'This is the thesis in nine properties. Deliver it as “the differentiation is the artifact, not where enforcement runs.” If asked how each property is produced, answer at the guarantee level only — no mechanism, keys, or algorithms. Frame any property ServiceNow may already provide as a discovery question.');
})();

/* SECTION VIII GOVERNED VALUE */
divider('VIII','Enterprise Governed Value','A developing, cross-cutting capability — evidence-backed outcome attribution');

/* 48. GOVERNED VALUE */
(()=>{ const s=slide();
  header(s,'Enterprise Governed Value','Developing & cross-cutting — not an authorization gate');
  badge(s,10.9,0.66,'UNDER DEVELOPMENT',1.9);
  SH(s,pptx.ShapeType.roundRect,{x:0.6,y:1.5,w:6.0,h:2.0,rectRadius:0.06,fill:{color:GREEN_LT},line:{color:GREEN,width:1}});
  T(s,[{text:'ServiceNow already measures value.  ',options:{bold:true,color:GREEN_DK}},{text:'AI Control Tower measures AI adoption, business impact, realized value and ROI. This proposal does not duplicate or replace that.',options:{color:INK}}],
    {x:0.8,y:1.62,w:5.65,h:1.8,fontFace:BODY,fontSize:11.5,valign:'top',margin:0,lineSpacingMultiple:1.1});
  SH(s,pptx.ShapeType.roundRect,{x:6.75,y:1.5,w:6.0,h:2.0,rectRadius:0.06,fill:{color:VIOLET_LT},line:{color:VIOLET,width:1}});
  T(s,[{text:'Ugence proposes attribution.  ',options:{bold:true,color:VIOLET_DK}},{text:'Evidence-backed outcome attribution that connects approved objectives, governed-execution evidence, attributable cost, observed outcomes, and preserved risk, compliance, quality and service constraints.',options:{color:INK}}],
    {x:6.95,y:1.62,w:5.65,h:1.8,fontFace:BODY,fontSize:11.5,valign:'top',margin:0,lineSpacingMultiple:1.1});
  T(s,'Concrete example — UC-5 checkout scaling',{x:0.6,y:3.7,w:12,h:0.32,fontFace:BODY,fontSize:13,bold:true,color:INK});
  const ex=[['Approved objective','Reduce checkout latency'],['Baseline','Current latency, capacity, cost'],['Governed action','Scale 12 → 18 instances'],['Execution evidence','Authorization · clearance · receipt'],['Observed outcome','Latency improved; service healthy'],['Attributable cost','Additional infrastructure expense'],['Preserved constraints','No window / risk / availability violation'],['Governed-value question','Enough attributable value without unacceptable trade-offs?']];
  ex.forEach((e,i)=>{ const col=i%4,row=Math.floor(i/4); const x=0.6+col*3.05,y=4.1+row*1.28;
    SH(s,pptx.ShapeType.roundRect,{x,y,w:2.9,h:1.15,rectRadius:0.05,fill:{color:'FFFFFF'},line:{color:HAIR,width:1}});
    T(s,e[0],{x:x+0.14,y:y+0.1,w:2.62,h:0.34,fontFace:BODY,fontSize:9.5,bold:true,color:TEAL_DK,margin:0});
    T(s,e[1],{x:x+0.14,y:y+0.44,w:2.62,h:0.66,fontFace:BODY,fontSize:9.5,color:INK,margin:0,lineSpacingMultiple:1.0});
  });
  footnote(s,'Clearly under development. It reuses the governance evidence the pipelines already emit — it adds attribution, not a new gate.');
  notes(s,'Present governed value as developing and cross-cutting. Credit AICT for already measuring adoption/impact/value/ROI. The Ugence addition is attribution: tying a specific governed action to a specific outcome without trading away constraints — using the evidence the pipelines already emit. Walk the UC-5 example left to right. Do not present it as an authorization stage.');
})();

/* SECTION IX PILOT */
divider('IX','Pilot proposal','One bounded technical pilot around UC-5 — no broad production autonomy');

/* 50. PILOT PROGRESSION */
(()=>{ const s=slide();
  header(s,'Pilot proposal','A bounded progression — earn autonomy step by step');
  const steps=['Technical discovery','Data & integration mapping','Offline / historical replay','Dry-run / shadow evaluation','HOLD / BLOCK / ESCALATE testing','Limited controlled execution','Execution-receipt verification','Observed-effect reconciliation','Pilot evaluation','Jointly agreed next phase'];
  steps.forEach((st,i)=>{ const col=i%5,row=Math.floor(i/5); const x=0.6+col*2.42,y=1.7+row*1.9;
    SH(s,pptx.ShapeType.roundRect,{x,y,w:2.24,h:1.55,rectRadius:0.06,fill:{color:i<5?VIOLET_LT:TEAL_LT},line:{color:i<5?VIOLET:TEAL,width:1.25},shadow:sh()});
    SH(s,pptx.ShapeType.ellipse,{x:x+0.14,y:y+0.14,w:0.44,h:0.44,fill:{color:i<5?VIOLET:TEAL},line:{width:0}});
    T(s,String(i+1),{x:x+0.14,y:y+0.14,w:0.44,h:0.44,fontFace:BODY,fontSize:14,bold:true,color:'FFFFFF',align:'center',valign:'middle',margin:0});
    T(s,st,{x:x+0.12,y:y+0.66,w:2.0,h:0.82,fontFace:BODY,fontSize:10.5,bold:true,color:i<5?VIOLET_DK:TEAL_DK,valign:'top',margin:0,lineSpacingMultiple:1.0});
    if(col<4){ seg(s,x+2.24,y+0.78,x+2.42,y+0.78,{width:1.5}); }
  });
  // row connector 5->6
  seg(s,0.6+4*2.42+1.12,1.7+1.55,0.6+1.12,1.7+1.9,{width:1.25,dash:'dash'});
  footnote(s,'Live controlled execution is not enabled until dry-run, exception-path and receipt checks pass. No broad production autonomy at pilot start.');
  notes(s,'Walk the ten steps as a confidence-building ladder: nothing consequential runs live until offline replay, dry-run/shadow, exception-path testing and receipt verification all pass. This directly answers the “are you going to let AI loose in production?” objection — no, autonomy is earned in bounded steps with the customer.');
})();

/* 51. PILOT BOUNDARY + MEASUREMENTS */
(()=>{ const s=slide();
  header(s,'Pilot proposal','Boundary and measurements');
  card(s,0.6,1.5,6.0,5.1,{title:'Possible pilot boundary',tcolor:VIOLET_DK,fill:VIOLET_LT,line:VIOLET,
    body:'•  One controlled scaling workflow (UC-5)\n•  A limited set of noncritical or carefully selected CIs / clusters\n•  Restricted action types\n•  Explicit authority and cost limits\n•  Defined rollback requirements\n•  No broad production autonomy at pilot start\n\nThe pilot proves the authorization → clearance → execution → reconciliation chain on a small, reversible footprint before any scope increase.',bfs:11.5});
  card(s,6.75,1.5,6.0,5.1,{title:'Possible measurements',tcolor:TEAL_DK,fill:'FFFFFF',line:TEAL,
    body:'•  % of actions bound to the exact approved target\n•  Authorization mismatches blocked\n•  Unsafe live conditions detected\n•  HOLD / BLOCK / ESCALATE accuracy\n•  Execution-to-effect match rate\n•  Change success rate\n•  Rollback rate\n•  Service availability\n•  Time saved\n•  Infrastructure cost\n•  Attributable governed value (developing)',bfs:11.5});
  footnote(s,'Success is measured on safety and fidelity first (exact-target binding, mismatch blocks, effect-match), then on operational benefit.');
  notes(s,'Keep the boundary tight and reversible; that is what makes a pilot approvable. Lead the measurements with safety/fidelity metrics — exact-target binding, mismatch blocks, effect-match — before efficiency metrics. Attributable governed value is labelled developing.');
})();

/* SECTION X */
divider('X','Discovery & next step','Constructive questions, and a request for one joint technical session');

/* 53. DISCOVERY QUESTIONS */
(()=>{ const s=slide();
  header(s,'Discovery questions for ServiceNow','Constructive questions to work through together');
  const qs=['Which ServiceNow records are authoritative for each scenario?',
    'What events expose the approval, target and execution context?',
    'Where could an independent action-level authorization be evaluated?',
    'Where could a live operational clearance verdict be consumed?',
    'How should execution receipts and effect results be associated with the originating record?',
    'Which controls already provide equivalent granularity?',
    'Which use case is most suitable for a bounded pilot?',
    'What should remain human-binding?',
    'What data may leave the ServiceNow boundary?',
    'What evidence would be required for production acceptance?'];
  qs.forEach((q,i)=>{ const col=i%2,row=Math.floor(i/2); const x=0.6+col*6.15,y=1.5+row*1.02;
    SH(s,pptx.ShapeType.roundRect,{x,y,w:5.95,h:0.9,rectRadius:0.05,fill:{color:i%2?TEAL_LT:VIOLET_LT},line:{color:i%2?TEAL:VIOLET,width:1}});
    T(s,String(i+1),{x:x+0.14,y:y+0.14,w:0.5,h:0.62,fontFace:TITLE,fontSize:18,bold:true,color:i%2?TEAL:VIOLET,align:'center',valign:'middle',margin:0});
    T(s,q,{x:x+0.72,y:y+0.06,w:5.1,h:0.78,fontFace:BODY,fontSize:10.5,color:INK,valign:'middle',margin:0,lineSpacingMultiple:1.0});
  });
  footnote(s,'Every question is designed to establish technical fit before any commitment — the answers shape the pilot.');
  notes(s,'These are the questions we want to leave with the representative. They establish authoritative inputs, integration points, and what stays human-binding — the raw material for scoping a pilot. Ask which they can answer now and which need an architect.');
})();

/* 54. NEXT STEP close */
(()=>{ const s=slide(true);
  SH(s,pptx.ShapeType.rect,{x:0,y:0,w:W,h:H,fill:{color:NAVY},line:{width:0}});
  T(s,'THE NEXT STEP',{x:0.95,y:1.5,w:11,h:0.4,fontFace:BODY,fontSize:13,bold:true,color:'9AA2D8',charSpacing:2});
  T(s,'One joint technical discovery session',{x:0.9,y:2.0,w:11.5,h:0.9,fontFace:TITLE,fontSize:34,bold:true,color:'FFFFFF'});
  T(s,'to select and define one bounded pilot — most likely UC-5, autonomous change execution.',{x:0.95,y:3.0,w:11,h:0.7,fontFace:BODY,fontSize:16,color:'C9CFEA'});
  const asks=[['We are not asking for','a broad partnership commitment before technical fit is established.'],['We are asking for','a working session with your architects to map records, events and integration points, and to agree a small, reversible pilot.']];
  asks.forEach((a,i)=>{ const x=0.95+i*6.0;
    SH(s,pptx.ShapeType.roundRect,{x,y:4.0,w:5.65,h:2.0,rectRadius:0.08,fill:{color:i?'241F55':'201B4C'},line:{color:'3A3475',width:1}});
    T(s,a[0],{x:x+0.25,y:4.2,w:5.2,h:0.4,fontFace:BODY,fontSize:13,bold:true,color:i?'8FE3C2':'F4B8B0'});
    T(s,a[1],{x:x+0.25,y:4.65,w:5.2,h:1.2,fontFace:BODY,fontSize:13,color:'E7EAF7',lineSpacingMultiple:1.12});
  });
  T(s,'All ServiceNow integrations PROPOSED · all scenarios illustrative · composition, not replacement.',{x:0.95,y:6.42,w:11.4,h:0.35,fontFace:BODY,fontSize:11,italic:true,color:'AEB6E0'});
  T(s,'Rakesh Mohan  ·  Founder, Ugence Labs  ·  ugence.ai',{x:0.95,y:6.88,w:11.4,h:0.35,fontFace:BODY,fontSize:12.5,bold:true,color:'8FE3C2',align:'left',valign:'middle',margin:0});
  notes(s,'Close on a modest, concrete ask: one joint technical discovery session to scope a bounded pilot — not a partnership demand. Restate the guardrails one last time: everything is proposed, everything illustrative, and Ugence composes with ServiceNow. Invite the discovery-question answers as the starting agenda. Presenter: Rakesh Mohan, Founder, Ugence Labs.');
})();

/* APPENDIX */
/* 55. maturity legend + disclaimers */
(()=>{ const s=slide();
  header(s,'Appendix','Maturity & availability legend, and standing disclaimers');
  const labels=['IMPLEMENTED','REFERENCE-GRADE','PILOT PENDING','UNDER DEVELOPMENT','PROPOSED INTEGRATION','ANNOUNCED / FUTURE','DESIGN-ONLY'];
  const desc={'IMPLEMENTED':'Code exists and is verified at interface level.','REFERENCE-GRADE':'Ships reference implementations; not production-validated.','PILOT PENDING':'Awaiting production / pilot validation.','UNDER DEVELOPMENT':'Additional capabilities actively being built.','PROPOSED INTEGRATION':'A ServiceNow integration adapter is design intent; no connector ships.','ANNOUNCED / FUTURE':'A named future capability; not yet shipped.','DESIGN-ONLY':'Architecture / design; not a package.'};
  labels.forEach((l,i)=>{ const y=1.55+i*0.62;
    badge(s,0.6,y,l,2.2);
    T(s,desc[l],{x:3.0,y:y-0.04,w:9.6,h:0.34,fontFace:BODY,fontSize:11,color:INK,valign:'middle',margin:0});
  });
  SH(s,pptx.ShapeType.roundRect,{x:0.6,y:6.05,w:12.1,h:0.85,rectRadius:0.06,fill:{color:INK},line:{width:0}});
  T(s,[{text:'Standing disclaimers.  ',options:{bold:true,color:'FFFFFF'}},{text:'All ServiceNow integrations are PROPOSED — no connector ships. All scenarios are illustrative, not customer deployments. Maturity dimensions are not conflated: a multi-module workflow carries per-module maturity. Unverified differentiation is a discovery hypothesis, never a claim that ServiceNow lacks a capability.',options:{color:'E7EAF7'}}],
    {x:0.8,y:6.1,w:11.7,h:0.75,fontFace:BODY,fontSize:10,valign:'middle',margin:0,lineSpacingMultiple:1.03});
  notes(s,'Use this as the reference for every badge in the deck. The key discipline: do not apply one maturity label to a whole workflow — individual modules differ (e.g., Cloud Scaling core IMPLEMENTED, integration PROPOSED). Re-read the standing disclaimers.');
})();

/* 56. sources */
(()=>{ const s=slide();
  header(s,'Appendix','Source hierarchy & citations');
  const src=[['1 · ServiceNow Docs','Existing product behavior and workflow mechanics (docs.servicenow.com)'],
    ['2 · ServiceNow release notes','Versions and availability (what ships when)'],
    ['3 · ServiceNow Newsroom','Announcements, partnerships and future availability'],
    ['4 · ServiceNow Community','Supporting or explanatory material'],
    ['5 · NVIDIA documentation','OpenShell technical behavior (seccomp + Landlock LSM + network namespaces; not eBPF)'],
    ['6 · Third-party press','Corroboration of announcement facts only (e.g. Dec-2026 SOC availability)']];
  src.forEach((r,i)=>{ const y=1.55+i*0.66;
    SH(s,pptx.ShapeType.roundRect,{x:0.6,y,w:12.1,h:0.56,rectRadius:0.05,fill:{color:i%2?'F4F6FA':'FFFFFF'},line:{color:HAIR,width:1}});
    T(s,r[0],{x:0.8,y:y+0.02,w:3.3,h:0.52,fontFace:BODY,fontSize:11.5,bold:true,color:VIOLET_DK,valign:'middle',margin:0});
    T(s,r[1],{x:4.2,y:y+0.02,w:8.3,h:0.52,fontFace:BODY,fontSize:10.5,color:INK,valign:'middle',margin:0});
  });
  T(s,'Key anchors: AI Control Tower · Action Fabric · AI Agent Fabric · AI Risk & Compliance · Change Management · Security Incident Response · Vulnerability Response · Service Catalog · HRSD · Sourcing & Procurement · NVIDIA OpenShell.',
    {x:0.6,y:5.7,w:12.1,h:0.7,fontFace:BODY,fontSize:10.5,italic:true,color:MUTED,lineSpacingMultiple:1.1});
  T(s,'Ugence module behavior is grounded in the source-of-record documents (catalog v1.2 and the walkthrough companion) at the guarantee level; no internal repository detail is exposed here.',
    {x:0.6,y:6.45,w:12.1,h:0.5,fontFace:BODY,fontSize:10,italic:true,color:MUTED});
  notes(s,'State the source hierarchy plainly: ServiceNow Docs first, then release notes, Newsroom, Community; NVIDIA docs for OpenShell; third-party press only to corroborate. Note the OpenShell technical correction (seccomp + Landlock + network namespaces, not eBPF). No internal repository paths are shown in this external deck.');
})();

/* ---------- HTML mirror emitter (same coordinates, for Chromium render) ---------- */
const fs=require('fs');
const PX=96; // px per inch
function esc(t){ return String(t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function escBR(t){ return esc(t).replace(/\n/g,'<br>'); }
function fam(f){ return f==='Cambria'?"Cambria, Georgia, 'Times New Roman', serif":"Calibri, Arial, Helvetica, sans-serif"; }
function col(c){ return c?('#'+String(c).replace('#','')):'transparent'; }
function runsHTML(text,baseOpts){
  const arr=Array.isArray(text)?text:[{text:text,options:{}}];
  return arr.map(r=>{ const o=r.options||{}; const st=[];
    if(o.bold||baseOpts.bold) st.push('font-weight:700');
    if(o.italic||baseOpts.italic) st.push('font-style:italic');
    if(o.color) st.push('color:'+col(o.color));
    const pre=(o.bullet)?'•  ':'';
    const br=(o.breakLine)?'<br>':'';
    return '<span style="'+st.join(';')+'">'+pre+escBR(r.text)+'</span>'+br;
  }).join('');
}
function textDIV(op){
  const o=op.opts||{}; const x=o.x*PX,y=o.y*PX,w=o.w*PX,h=o.h*PX;
  const align=o.align||'left';
  const valign=o.valign==='middle'?'center':(o.valign==='bottom'?'flex-end':'flex-start');
  const st=['position:absolute','left:'+x+'px','top:'+y+'px','width:'+w+'px','height:'+h+'px',
    'display:flex','flex-direction:column','justify-content:'+valign,
    'font-family:'+fam(o.fontFace),'font-size:'+((o.fontSize||14)*PX/72)+'px',
    'color:'+col(o.color||'1E2340'),'text-align:'+align,
    'line-height:'+(o.lineSpacingMultiple||1.05),'overflow:hidden','box-sizing:border-box'];
  const pad=(o.margin!=null?(typeof o.margin==='number'?o.margin:2):2); st.push('padding:'+(pad*PX/72)+'px');
  if(o.bold) st.push('font-weight:700'); if(o.italic) st.push('font-style:italic');
  if(o.charSpacing) st.push('letter-spacing:'+(o.charSpacing*0.7)+'px');
  if(o.fill&&o.fill.color) st.push('background:'+col(o.fill.color));
  const inner='<div style="width:100%;text-align:'+align+'">'+runsHTML(op.text,o)+'</div>';
  return '<div style="'+st.join(';')+'">'+inner+'</div>';
}
function shapeDIV(op){
  const o=op.opts||{}; const x=o.x*PX,y=o.y*PX,w=o.w*PX,h=o.h*PX; const st=['position:absolute','left:'+x+'px','top:'+y+'px','width:'+w+'px','height:'+h+'px','box-sizing:border-box'];
  if(o.fill&&o.fill.color) st.push('background:'+col(o.fill.color));
  if(o.line&&o.line.width>0) st.push('border:'+(o.line.width)+'px solid '+col(o.line.color));
  if(op.type===pptx.ShapeType.ellipse) st.push('border-radius:50%');
  else if(op.type===pptx.ShapeType.can) st.push('border-radius:'+(w/2)+'px / 14px');
  else if(op.type===pptx.ShapeType.roundRect) st.push('border-radius:'+((o.rectRadius||0.06)*PX)+'px');
  if(o.shadow) st.push('box-shadow:2px 3px 7px rgba(120,130,150,0.30)');
  return '<div style="'+st.join(';')+'"></div>';
}
function tableHTML(op){
  const o=op.opts||{}; const x=o.x*PX,y=o.y*PX,w=o.w*PX; const colW=(o.colW||[]).map(c=>c*PX);
  let html='<table style="position:absolute;left:'+x+'px;top:'+y+'px;width:'+w+'px;border-collapse:collapse;table-layout:fixed;font-family:'+fam(o.fontFace)+'">';
  op.rows.forEach(row=>{ html+='<tr>'; row.forEach((cell,ci)=>{ const co=cell.options||{}; const st=['border:0.75px solid #D8DEE9','box-sizing:border-box','vertical-align:'+(co.valign==='middle'?'middle':'top'),
      'padding:4px 6px','font-size:'+((co.fontSize||10)*PX/72)+'px','color:'+col(co.color||'1E2340'),'text-align:'+(co.align||'left'),'overflow:hidden'];
    if(co.fill&&co.fill.color) st.push('background:'+col(co.fill.color));
    if(co.bold) st.push('font-weight:700');
    if(colW[ci]) st.push('width:'+colW[ci]+'px');
    html+='<td style="'+st.join(';')+'">'+escBR(cell.text)+'</td>'; }); html+='</tr>'; });
  return html+'</table>';
}
function slideHTML(s){
  const bg = s._dark? '#16143A':'#FFFFFF';
  let lines=''; const others=[];
  s._ops.forEach(op=>{ if(op.k==='line') return; });
  // svg overlay for lines
  let svg='<svg width="'+(W*PX)+'" height="'+(H*PX)+'" style="position:absolute;left:0;top:0;pointer-events:none" xmlns="http://www.w3.org/2000/svg"><defs>'
    +'<marker id="ah" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L7,3 L0,6 Z" fill="#4B5563"/></marker>'
    +'<marker id="ahr" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L7,3 L0,6 Z" fill="#C0392B"/></marker>'
    +'<marker id="aht" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L7,3 L0,6 Z" fill="#2B6CB0"/></marker>'
    +'<marker id="aha" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto"><path d="M0,0 L7,3 L0,6 Z" fill="#B7791F"/></marker></defs>';
  s._ops.filter(op=>op.k==='line').forEach(op=>{
    const mk = op.color==='C0392B'?'ahr':(op.color==='2B6CB0'?'aht':(op.color==='B7791F'?'aha':'ah'));
    svg+='<line x1="'+(op.x1*PX)+'" y1="'+(op.y1*PX)+'" x2="'+(op.x2*PX)+'" y2="'+(op.y2*PX)+'" stroke="'+col(op.color)+'" stroke-width="'+op.width+'" '+(op.dash?'stroke-dasharray="5,3" ':'')+(op.arrow?'marker-end="url(#'+mk+')" ':'')+'/>';
  });
  svg+='</svg>';
  let body='';
  s._ops.forEach(op=>{ if(op.k==='shape') body+=shapeDIV(op); else if(op.k==='text') body+=textDIV(op); else if(op.k==='table') body+=tableHTML(op); });
  return '<div class="page" style="position:relative;width:'+(W*PX)+'px;height:'+(H*PX)+'px;background:'+bg+';overflow:hidden">'+svg+body+'</div>';
}
function addPageNumbers(){
  DECK.forEach((s,i)=>{
    if(i===0) return;              // title slide: not numbered
    if(s._divider || s._dark) return; // dividers / dark slides: not numbered
    T(s,String(i+1),{x:12.35,y:7.06,w:0.5,h:0.3,fontFace:BODY,fontSize:9.5,color:MUTED,align:'right',valign:'middle',margin:0});
  });
}
function buildMirror(){
  let html='<!doctype html><html><head><meta charset="utf-8"><title>'+DOC_TITLE+'</title><style>@page{size:'+W+'in '+H+'in;margin:0}html,body{margin:0;padding:0}.page{page-break-after:always}</style></head><body>';
  DECK.forEach(s=>{ html+=slideHTML(s); });
  html+='</body></html>';
  fs.writeFileSync(OUT+'.render.html',html);
  console.log('MIRROR', DECK.length,'slides');
}

addPageNumbers();
pptx.writeFile({fileName:OUT+'.pptx'}).then(f=>{console.log('WROTE',f); buildMirror();}).catch(e=>{console.error('ERR',e);process.exit(1);});
