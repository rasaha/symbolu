# Portrait top-down workflow diagrams (SVG, vector). Newly laid out for portrait reading.
FS = 13.0
def _cw(fs): return 0.53*fs  # approx char width

CAT = {
 'CITY': ('#E1F0F7','#1C7FA8','#0E4C63'),   # cyan — vehicle-intelligence / city platform
 'SNOW': ('#E4F3EA','#2E8B57','#14532D'),   # sea-green — ServiceNow platform
 'EXT' : ('#EEF1F4','#6B7280','#374151'),   # grey — external consequence systems
 'HUMAN':('#FBF1DD','#B7791F','#6B4A12'),   # amber — human authority
 'STOP': ('#FBEBE9','#C0392B','#7A2016'),   # red — reject / hold / escalate branches
 'OPEN': ('#FFF6EC','#B26A00','#7A4A00'),   # tan (dashed) — responsibility to assign / discovery
}
ARROW='#4B5563'; MUTED='#6B7280'; INK='#1E2340'

def esc(t): return str(t).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')

def wrap(text, maxchars):
    out=[]
    for para in str(text).split('\n'):
        words=para.split(' '); line=''
        for w in words:
            if line and len(line)+1+len(w)>maxchars:
                out.append(line); line=w
            else:
                line=(line+' '+w).strip()
        out.append(line)
    return out

def _tspans(lines, cx, y0, dy, fill, fs, weight='400', anchor='middle'):
    s=''
    for i,ln in enumerate(lines):
        s+=f'<tspan x="{cx}" y="{y0+i*dy}">{esc(ln)}</tspan>'
    return f'<text text-anchor="{anchor}" font-family="Helvetica,Arial,sans-serif" font-size="{fs}" font-weight="{weight}" fill="{fill}">{s}</text>'

class SVG:
    def __init__(self,w):
        self.w=w; self.parts=[]; self.maxy=0
    def _grow(self,y): self.maxy=max(self.maxy,y)
    def box(self,x,y,w,h,text,cat,num=None,sub=None,fs=FS,dashed=False):
        fill,stroke,tx=CAT[cat]
        dash=' stroke-dasharray="6,4"' if dashed else ''
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{fill}" stroke="{stroke}" stroke-width="1.6"{dash}/>')
        inner=w-24
        maxc=max(6,int(inner/_cw(fs)))
        lines=wrap(text,maxc)
        sublines=wrap(sub,int((w-24)/_cw(fs-1.5))) if sub else []
        total=len(lines)*(fs+3)+ (len(sublines)*(fs-1) if sublines else 0)
        cy=y+h/2-total/2+fs
        self.parts.append(_tspans(lines,x+w/2,cy,fs+3,tx,fs,'700'))
        if sublines:
            sy=cy+len(lines)*(fs+3)+2
            self.parts.append(_tspans(sublines,x+w/2,sy,fs-1,MUTED,fs-2.0,'400'))
        if num is not None:
            self.parts.append(f'<circle cx="{x+16}" cy="{y+16}" r="12" fill="{stroke}"/>')
            self.parts.append(f'<text x="{x+16}" y="{y+20}" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" font-size="12" font-weight="700" fill="#fff">{num}</text>')
        self._grow(y+h)
    def cyl(self,x,y,w,h,text,cat,fs=FS-1):
        fill,stroke,tx=CAT[cat]
        rx=w/2; ry=10
        self.parts.append(f'<path d="M{x},{y+ry} a{rx},{ry} 0 0 1 {w},0 v{h-2*ry} a{rx},{ry} 0 0 1 -{w},0 z" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')
        self.parts.append(f'<ellipse cx="{x+rx}" cy="{y+ry}" rx="{rx}" ry="{ry}" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')
        lines=wrap(text,int((w-16)/_cw(fs)))
        cy=y+h/2-len(lines)*(fs+2)/2+fs
        self.parts.append(_tspans(lines,x+rx,cy,fs+2,tx,fs,'700'))
        self._grow(y+h)
    def arrow(self,x1,y1,x2,y2,label=None,color=ARROW,dashed=False,lw=1.8,lside='right'):
        dash=' stroke-dasharray="6,4"' if dashed else ''
        self.parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{lw}"{dash} marker-end="url(#ah)"/>')
        if label:
            mx=(x1+x2)/2; my=(y1+y2)/2
            lines=wrap(label,26)
            wpx=max(len(l) for l in lines)*_cw(10.5)+10
            if abs(x2-x1)<2:  # vertical arrow: label beside midpoint, flip inward near right edge
                by=my-(len(lines)*12)/2
                bx = mx-wpx-10 if mx>0.68*self.w else mx+10
            else:  # horizontal arrow: centre the label on the arrow midpoint (sits in the gap)
                by=my-(len(lines)*12)/2-2
                bx=mx-wpx/2
            self.parts.append(f'<rect x="{bx}" y="{by-11}" width="{wpx}" height="{len(lines)*13+4}" fill="#ffffff" opacity="0.92"/>')
            self.parts.append(_tspans(lines,bx+wpx/2,by,12,MUTED,10.5,'400'))
        self._grow(max(y1,y2))
    def label(self,x,y,text,fill=MUTED,fs=10.5,weight='400',anchor='start'):
        lines=wrap(text,60)
        self.parts.append(_tspans(lines,x,y,fs+3,fill,fs,weight,anchor))
        self._grow(y+len(lines)*(fs+3))
    def render(self,pad=14):
        h=self.maxy+pad
        defs='<defs><marker id="ah" markerWidth="9" markerHeight="9" refX="7.5" refY="3" orient="auto"><path d="M0,0 L7.5,3 L0,6 z" fill="'+ARROW+'"/></marker></defs>'
        body=''.join(self.parts)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {self.w} {h:.0f}" width="{self.w}" height="{h:.0f}">'
                f'{defs}<rect x="0" y="0" width="{self.w}" height="{h:.0f}" fill="#ffffff"/>{body}</svg>'), self.w, int(h)

# ---------------- diagram builders ----------------
W=720

# ================= City-scale vehicle-intelligence diagrams =================

def _chiprow(s, items, x0, y, total_w, cat, per_row=None, fs=9.5, ch=30, gap=8):
    """Draw a row (or grid) of small chips inside a band. Returns bottom y."""
    n=len(items)
    per_row=per_row or n
    rows=[items[i:i+per_row] for i in range(0,n,per_row)]
    cw=(total_w-(per_row-1)*gap)/per_row
    yy=y
    for row in rows:
        # centre a short final row
        rw=len(row); off=(total_w-(rw*cw+(rw-1)*gap))/2 if rw<per_row else 0
        for j,it in enumerate(row):
            cx=x0+off+j*(cw+gap)
            s.box(cx,yy,cw,ch,it,cat,fs=fs)
        yy+=ch+gap
    return yy-gap

# ============ ServiceNow-centered baseline diagrams (no Ugence) ============
# Actor bands: CITY (cyan) vehicle platform · SNOW (green) ServiceNow ·
# EXT (grey) external consequence systems · HUMAN (amber) human authority.
# OPEN (tan, dashed) = a responsibility to assign / discovery item — not a native control.

def _col(s, cx, nw, y, seq, gap, H, fs=11):
    pos=[]
    for i,item in enumerate(seq):
        t,cat=item[0],item[1]; lab=item[2] if len(item)>2 else None; sub=item[3] if len(item)>3 else None
        dashed = (cat=='OPEN')
        s.box(cx-nw/2,y,nw,H,t,cat,fs=fs,sub=sub,dashed=dashed); pos.append((y,y+H))
        if i<len(seq)-1: s.arrow(cx,y+H,cx,y+H+gap,lab)
        y=y+H+gap
    return pos

def _band(s, x, bw, y, title, items, per_row, cat='SNOW', ch=32, fs=9.5):
    s.parts.append(f'<rect x="{x}" y="{y}" width="{bw}" height="24" rx="6" fill="{CAT[cat][2]}"/>')
    s.parts.append(f'<text x="{x+10}" y="{y+16}" font-family="Helvetica,Arial,sans-serif" font-size="11" font-weight="700" fill="#fff">{esc(title)}</text>')
    s._grow(y+24)
    return _chiprow(s,items,x+8,y+32,bw-16,cat,per_row=per_row,fs=fs,ch=ch,gap=8)

def d_actors():
    s=SVG(W); x=14; bw=W-28; y=14
    y=_band(s,x,bw,y,'Vehicle-intelligence / city platform (external to ServiceNow)',
        ['Camera & sensor ingestion','Computer-vision inference','ANPR / vehicle classification','Confidence & uncertainty','Trajectory reconstruction','Evidence provenance','Raw video & sensor storage','Secure evidence retrieval'],4,'CITY')+14
    y=_band(s,x,bw,y,'ServiceNow — enterprise case, workflow, governance-record, policy, approval, orchestration, reporting',
        ['PSDS case mgmt / ICM (where licensed)','Purpose · scope · jurisdiction','IRM policy & control library','AI Control Tower AI-governance record','CMDB / OT asset context','Workflow rules & approvals','Dispatch via IntegrationHub / Flow','Exceptions · analytics · audit history'],4,'SNOW')+14
    y=_band(s,x,bw,y,'External consequence systems',
        ['Traffic-enforcement system','Police / public-safety','Vehicle registry','Citizen-notification','Payment / penalty (if any)','Appeals / judicial'],3,'EXT')+14
    y=_band(s,x,bw,y,'Human authority',
        ['Investigative judgment','Approval where required','Uncertainty resolution','Corrected identity','Legal & policy interpretation','Appeal determination'],3,'HUMAN')+14
    s.label(14,y+22,'ServiceNow coordinates how the event becomes a governed enterprise case; it does not perform computer-vision inference or legally accountable human judgment. Proposed reference architecture — not an official or endorsed ServiceNow design.',fill=INK,fs=10.5)
    return s.render()

def d_snowmap():
    s=SVG(W); x=14; bw=W-28; y=14
    y=_band(s,x,bw,y,'CORE',
        ['PSDS case mgmt / ICM (where licensed)','Workflow Studio / Flow Designer','IntegrationHub / Stream Connect / REST','Workflow Data Fabric / Zero Copy Connectors'],2)+14
    y=_band(s,x,bw,y,'SUPPORTING GOVERNANCE',
        ['AI Control Tower','Integrated Risk Management (IRM)','Policy & Compliance Management','CMDB','Platform / Performance Analytics'],3)+14
    y=_band(s,x,bw,y,'EXCEPTION OR ESCALATION',
        ['Security Incident Response','Security Case Management'],2)+14
    y=_band(s,x,bw,y,'OPTIONAL OPERATIONAL EXTENSION',
        ['Operational Technology Management','Field Service Management','Government Service Portal'],3)+14
    y=_band(s,x,bw,y,'DISCOVERY-DEPENDENT',
        ['ServiceNow AI Action Fabric','Agentic Playbooks','Customer Service Management foundation'],3)+14
    s.label(14,y+22,'Products are included only where they perform a defensible role. Availability, SKU, table and licensing are discovery items to confirm with ServiceNow. “ServiceNow AI Action Fabric” and “Agentic Playbooks” are placed as discovery-dependent because their applicability and governance for this scenario require confirmation for the target release.',fill=INK,fs=10.5)
    return s.render()

def d_datamin():
    s=SVG(W); cx=W/2; nw=560
    seq=[('Vehicle-intelligence / city platform (raw video & high-volume sensor data retained here)','CITY','evidence references + metadata (not raw imagery)',None),
         ('ServiceNow enterprise case (references, not raw imagery)','SNOW','approved, dispatched action only',None),
         ('External consequence system','EXT','execution result / receipt reference returns to the case',None)]
    pos=_col(s,cx,nw,16,seq,34,58,fs=11.5)
    s.box(14,pos[-1][1]+22,W-28,66,'Two distinct mechanisms — do not conflate','SNOW',sub='Workflow Data Fabric / Zero Copy Connectors: real-time access to external data in place, without copying, for supported connectors. IntegrationHub / Stream Connect / REST / custom APIs: event ingestion and action orchestration. Not every IntegrationHub exchange is zero-copy.',fs=11)
    s.label(14,pos[-1][1]+110,'ServiceNow does not become the computer-vision engine and does not store raw surveillance data by default. Any pattern that stages evidence inside ServiceNow is a CONFIGURATION decision requiring privacy, retention and jurisdiction review.',fill=INK,fs=10.5)
    return s.render()

def d_canonical():
    s=SVG(W); cx=300; nw=308
    seq=[('Vehicle-intelligence event (possible violation)','CITY','evidence refs + confidence'),
         ('Reference (Zero Copy) or ingest (IntegrationHub / Stream Connect / REST)','SNOW','case-relevant metadata'),
         ('PSDS case created / updated — purpose, scope, jurisdiction, classification','SNOW','case record'),
         ('Context — IRM policy/control status · AI Control Tower model status · CMDB / OT asset','SNOW','status, not authority'),
         ('Evidence & confidence review (workflow rules)','SNOW','review result'),
         ('Human approval where required (separation of duties)','HUMAN','approval decision'),
         ('Dispatch-eligibility check (workflow condition), then workflow dispatch','SNOW','approved action + parameters'),
         ('External consequence system executes or rejects','EXT','execution result / receipt'),
         ('ServiceNow case updated · exception / incident / appeal · analytics','SNOW',None)]
    pos=_col(s,cx,nw,16,seq,20,46,fs=10.5)
    # OPEN responsibilities on the right
    rx=520; rw=W-rx-14; st=pos[3][0]; sb=pos[7][1]
    s.box(rx,st,rw,sb-st,'RESPONSIBILITIES TO ASSIGN (not a single native “authorization” box): exact-action binding to target/parameters · commit-time recheck · independent effect reconciliation · receipt trustworthiness — assign to configuration, external system, human process or an independent control','OPEN',fs=9,dashed=True)
    s.label(14,pos[-1][1]+22,'Each arrow names what crosses the boundary. The decision types are distinct and not automatically equivalent: a workflow condition, a policy/control status, an approval, an access permission, an AI-governance status, a dispatch-eligibility rule and a legal authority are different things. No generic “authorization” step is asserted without an identified, sourced ServiceNow mechanism.',fill=INK,fs=10.5)
    return s.render()

def d_redlight():
    s=SVG(W); cx=300; nw=300
    seq=[('Junction 44 — possible red-light event (raw evidence retained in city platform)','CITY','evidence refs + confidence'),
         ('Reference / ingest evidence; PSDS case created / updated','SNOW','case record'),
         ('Purpose = enforcement · jurisdiction · classification; evidence class & confidence recorded','SNOW','case context'),
         ('Context — IRM policy/control status · AI Control Tower model status · CMDB camera/controller','SNOW','governance status'),
         ('Workflow conditions evaluated (thresholds, completeness)','SNOW','condition result'),
         ('Human approval where required','HUMAN','approval'),
         ('Workflow dispatch (Flow Designer / IntegrationHub)','SNOW','approved action'),
         ('Traffic-enforcement system executes or rejects','EXT','result / receipt'),
         ('PSDS case, audit history and analytics updated','SNOW',None)]
    pos=_col(s,cx,nw,16,seq,16,42,fs=10)
    s.label(14,pos[-1][1]+20,'Documented native capabilities (case, workflow, approvals, integration, analytics) are distinguished from CONFIGURATION and PROPOSED CUSTOM INTEGRATION in Section 16. Whether the effect independently matches the approved purpose and parameters is a RESPONSIBILITY TO ASSIGN. Illustrative example; proposed reference architecture.',fill=INK,fs=10.5)
    return s.render()

def d_failure():
    s=SVG(W); cx=270; nw=300
    seq=[('PSDS case + assembled context','SNOW','workflow evaluation'),
         ('Workflow rules / approvals / access controls','SNOW','condition / approval result'),
         ('ServiceNow routes to the appropriate path','SNOW',None)]
    pos=_col(s,cx,nw,16,seq,26,46,fs=10.5)
    # right column of outcome chips
    rx=470; rw=W-rx-14
    outs=['HOLD — await evidence','HUMAN REVIEW','REJECT','ESCALATE','REQUEST MORE EVIDENCE','OPEN EXCEPTION','OPEN SECURITY INCIDENT','CREATE FIELD-SERVICE WORK ORDER','RECORD FOR APPEAL']
    oy=pos[0][0]
    for o in outs:
        cat='STOP' if o in ('REJECT','HOLD — await evidence') else ('HUMAN' if 'REVIEW' in o or 'APPEAL' in o else 'SNOW')
        s.box(rx,oy,rw,28,o,cat,fs=9.5); oy+=32
    s.arrow(cx+nw/2,(pos[2][0]+pos[2][1])/2,rx,pos[0][0]+ (oy-pos[0][0])/2,None)
    s.label(14,max(pos[-1][1],oy)+16,'Triggers include insufficient confidence, conflicting / stale / unavailable evidence, identity uncertainty, jurisdiction mismatch, missing approval, policy/control conflict, unapproved AI asset or model, unauthorized access attempt, external-system rejection, ambiguous receipt, dispute, corrected identity, appeal, camera/controller malfunction, suspected tampering. The routing itself is CONFIGURATION; no ServiceNow-native control is invented to complete a path. Uncertain identity is preserved for human review, not converted to fact.',fill=INK,fs=10.5)
    return s.render()

def d_investigation():
    s=SVG(W); cx=300; nw=300
    seq=[('PSDS investigative case — purpose bounded: time, geography, data class, jurisdiction','SNOW','coordinates investigation'),
         ('Investigator or ServiceNow Agentic Playbook proposes another investigative step','SNOW','proposed step'),
         ('Workflow rules · approvals · access controls (separation of duties)','SNOW','approved / denied'),
         ('Approved query sent to external camera / registry / evidence system','EXT','results'),
         ('Results return to the investigative case','SNOW',None)]
    pos=_col(s,cx,nw,16,seq,22,46,fs=10.5)
    rx=524; rw=W-rx-14; st=pos[1][0]; sb=pos[2][1]
    s.box(rx,st,rw,sb-st,'Widening time, geography, identity resolution or data class = a NEW governed case decision or approval event — enforced by CONFIGURATION, not assumed','OPEN',fs=9.5,dashed=True)
    for i in (1,2):
        s.arrow(cx+nw/2,(pos[i][0]+pos[i][1])/2,rx,(pos[i][0]+pos[i][1])/2,None,color=CAT['OPEN'][1])
    s.label(14,pos[-1][1]+22,'Technical ability to run a query is never legal authority to run it. Scope monotonicity (no silent widening) is a CONFIGURATION / approval pattern to design; Agentic Playbook applicability is a DISCOVERY QUESTION for the target release. Illustrative.',fill=INK,fs=10.5)
    return s.render()

def d_assurance():
    s=SVG(W); cx=W/2
    s.box(14,16,W-28,92,'What the ServiceNow-centered architecture can record (documented / configurable)','SNOW',sub='case history · approvals · workflow activity · integration result · exception / incident · policy & control reference · AI-governance record · operational KPI · audit evidence',fs=11.5)
    y=126
    s.label(W/2,y+2,'Assurance questions that remain a RESPONSIBILITY TO ASSIGN — to configuration, an external system, a human process or an independent control:',fill=INK,fs=10.5,anchor='middle',weight='700')
    y+=46
    qs=[('What exact action was approved, and what exact target & parameters were dispatched?','CONFIGURATION / EXTERNAL'),
        ('Did the external system execute the same request that was approved?','EXTERNAL-SYSTEM CONTROL'),
        ('Is the execution receipt independently trustworthy?','EXTERNAL / INDEPENDENT CONTROL'),
        ('Can the observed effect be matched to the approved purpose and scope?','ARCHITECTURAL RESPONSIBILITY TO ASSIGN'),
        ('Who resolves a mismatch, and what becomes the appeal record?','HUMAN PROCESS / CONFIGURATION')]
    colw=(W-28-16)/2
    for idx,(q,tag) in enumerate(qs):
        col=idx%2; row=idx//2
        bx=14+col*(colw+16); by=y+row*68
        s.box(bx,by,colw,60,q,'OPEN',sub='→ '+tag,fs=9.5,dashed=True)
    s.label(14,y+3*68+6,'These are stated neutrally as architecture decisions, without competitive language and without claiming any independent cryptographic verification unless documented and implemented in the described architecture.',fill=INK,fs=10.5)
    return s.render()

def d_optional():
    s=SVG(W)
    lx=14; lw=(W-28-20)/2; rx2=lx+lw+20
    s.box(lx,16,lw,40,'Camera / signal-controller malfunction','CITY',fs=10.5)
    s.arrow(lx+lw/2,56,lx+lw/2,80)
    s.box(lx,80,lw,40,'CMDB / OT Management — asset condition','SNOW',fs=10.5)
    s.arrow(lx+lw/2,120,lx+lw/2,144,'work order')
    s.box(lx,144,lw,40,'Field Service Management — dispatch technician','SNOW',fs=10.5)
    s.arrow(lx+lw/2,184,lx+lw/2,208)
    s.box(lx,208,lw,44,'Technician remediation → asset-health result returned to the case','EXT',fs=10)
    s.box(rx2,16,lw,40,'Suspected tampering / unauthorized access','CITY',fs=10.5)
    s.arrow(rx2+lw/2,56,rx2+lw/2,80)
    s.box(rx2,80,lw,40,'Security Incident Response / Security Case Management','SNOW',fs=10.5)
    s.arrow(rx2+lw/2,120,rx2+lw/2,144,'investigation')
    s.box(rx2,144,lw,40,'Security investigation & containment workflow','SNOW',fs=10.5)
    s.arrow(rx2+lw/2,184,rx2+lw/2,208)
    s.box(rx2,208,lw,44,'Access / permission revocation is a CONFIGURATION / access-control action','OPEN',fs=10,dashed=True)
    s.label(14,272,'Optional operational extensions — outside the ordinary citation workflow. Availability/entitlement (e.g. out-of-box OT classes for cameras and signal controllers) are discovery items. Proposed reference architecture; illustrative.',fill=INK,fs=10.5)
    return s.render()

def d_roadmap():
    s=SVG(W); cx=W*0.5; nw=580; x=cx-nw/2; y=16; gap=15; H=52
    phases=[('Phase 0 · Discovery','Confirm product names, target release, PSDS / ICM entitlements, data model, external-reference support, integration mechanisms and audit/receipt semantics with ServiceNow.'),
            ('Phase 1 · Case & context','Stand up the PSDS case, evidence-reference model, IRM/AI Control Tower/CMDB context; no external dispatch yet.'),
            ('Phase 2 · Review & approval','Configure workflow conditions, evidence review and human approval / separation-of-duties patterns.'),
            ('Phase 3 · Governed dispatch','Integrate the external consequence system (IntegrationHub / Flow); dispatch only approved actions; capture receipts.'),
            ('Phase 4 · Exceptions & assurance','Exception, incident, appeal and field-service paths; assign the open assurance responsibilities; analytics & KPIs.'),
            ('Phase 5 · Investigation & scale','Bounded investigation patterns; scope-expansion approvals; hardening and reporting.')]
    for i,(t,sub) in enumerate(phases):
        cat='CITY' if i==0 else ('SNOW' if i in (1,2,3) else ('HUMAN' if i==4 else 'EXT'))
        s.box(x,y,nw,H,t,cat,num=i,sub=sub,fs=12)
        if i<len(phases)-1: s.arrow(cx,y+H,cx,y+H+gap)
        y=y+H+gap
    s.label(cx,y+10,'Every external integration is proposed unless explicitly documented otherwise; availability depends on release, SKU, licensing, Store apps and customer configuration.',fill=INK,fs=10.5,anchor='middle')
    return s.render()

ALL = {
 'actors': d_actors,
 'snowmap': d_snowmap,
 'datamin': d_datamin,
 'canonical': d_canonical,
 'redlight': d_redlight,
 'failure': d_failure,
 'investigation': d_investigation,
 'assurance': d_assurance,
 'optional': d_optional,
 'roadmap': d_roadmap,
}

if __name__=='__main__':
    import os
    os.makedirs('svg',exist_ok=True)
    for k,fn in ALL.items():
        svg,w,h=fn(); open(f'svg/{k}.svg','w').write(svg); print(k,w,h)
