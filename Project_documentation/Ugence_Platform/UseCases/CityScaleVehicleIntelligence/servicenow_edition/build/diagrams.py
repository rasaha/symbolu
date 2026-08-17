# Portrait top-down workflow diagrams (SVG, vector). Newly laid out for portrait reading.
FS = 13.0
def _cw(fs): return 0.53*fs  # approx char width

CAT = {
 'CITY': ('#E1F0F7','#1C7FA8','#0E4C63'),   # cyan — city & vehicle-intelligence systems
 'SNOW': ('#E4F3EA','#2E8B57','#14532D'),   # sea-green — ServiceNow platform
 'UDEC': ('#ECEAFB','#5145C7','#2A2170'),   # violet — Ugence decision / authority
 'UEXE': ('#E4EFF7','#2B6CB0','#173A5A'),   # blue — Ugence runtime / execution
 'AUTH': ('#DFF2F1','#0E7C86','#0A4A50'),   # teal — the signed authority envelope
 'EXT' : ('#EEF1F4','#6B7280','#374151'),   # grey — external consequence systems
 'STOP': ('#FBEBE9','#C0392B','#7A2016'),   # red — deny / hold / block / escalate
 'HUMAN':('#FBF1DD','#B7791F','#6B4A12'),   # amber — human authority / reassessment signal
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
    def box(self,x,y,w,h,text,cat,num=None,sub=None,fs=FS):
        fill,stroke,tx=CAT[cat]
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')
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


# ============ ServiceNow-integrated edition diagrams (5-band model) ============
# Bands: CITY (cyan) vehicle/city · SNOW (green) ServiceNow · UDEC/UEXE/AUTH Ugence ·
# EXT (grey) external consequence · HUMAN (amber) human authority.

def _col(s, cx, nw, y, seq, gap, H, fs=11):
    """Centered vertical flow. seq = [(text, cat, arrow_label_or_None, sub_or_None)]. Returns pos list."""
    pos=[]
    for i,item in enumerate(seq):
        t,cat=item[0],item[1]; lab=item[2] if len(item)>2 else None; sub=item[3] if len(item)>3 else None
        s.box(cx-nw/2,y,nw,H,t,cat,fs=fs,sub=sub); pos.append((y,y+H))
        if i<len(seq)-1: s.arrow(cx,y+H,cx,y+H+gap,lab)
        y=y+H+gap
    return pos

def d_legend_note():
    # tiny standalone band legend (used inline as a figure once)
    s=SVG(W); x=14; y=16; w=(W-28)
    bands=[('CITY','Vehicle & city systems'),('SNOW','ServiceNow platform'),('UDEC','Ugence governance'),('EXT','External consequence systems'),('HUMAN','Human authority')]
    cw=(w-4*10)/5
    for i,(cat,lab) in enumerate(bands):
        s.box(x+i*(cw+10),y,cw,40,lab,cat,fs=9.5)
    return s.render()

def d_layman():
    s=SVG(W); cx=W/2; nw=540
    seq=[('City & vehicle intelligence','CITY','evidence metadata + references',
            'cameras · signal controllers · ANPR/ALPR · re-identification · trajectory — determines what the evidence indicates'),
         ('ServiceNow','SNOW','PROPOSED Ugence governance request',
            'investigative case · purpose & scope · policy & control references · AI-governance status · human approvals'),
         ('Ugence','UDEC','AUTHORIZED + CLEAR — or DENY / HOLD / ESCALATE',
            'may this exact action proceed? — evidence, policy, authority, purpose, scope, live clearance, effect'),
         ('ServiceNow dispatches only an authorized, cleared action','SNOW','authorized action',
            'Flow Designer / AI Action Fabric / IntegrationHub'),
         ('External traffic · registry · police · notification system','EXT','receipt + observed effect ↑',None),
         ('Ugence verifies attempt, execution and effect, and writes the assurance result back to the ServiceNow case','UDEC',None,None)]
    pos=_col(s,cx,nw,16,seq,34,58,fs=12)
    s.label(14,pos[-1][1]+24,'PROPOSED SERVICENOW INTEGRATION — no Ugence ServiceNow connector currently ships. Illustrative, technically realistic composition; not a claimed deployment.',fill=INK,fs=10.5)
    return s.render()

def _band(s, x, bw, y, title, items, per_row, ch=32, fs=9.5):
    s.parts.append(f'<rect x="{x}" y="{y}" width="{bw}" height="24" rx="6" fill="{CAT["SNOW"][2]}"/>')
    s.parts.append(f'<text x="{x+10}" y="{y+16}" font-family="Helvetica,Arial,sans-serif" font-size="11" font-weight="700" fill="#fff">{esc(title)}</text>')
    s._grow(y+24)
    return _chiprow(s,items,x+8,y+32,bw-16,'SNOW',per_row=per_row,fs=fs,ch=ch,gap=8)

def d_snowmap():
    s=SVG(W); x=14; bw=W-28; y=14
    y=_band(s,x,bw,y,'Core pipeline products',
        ['Workflow Data Fabric / Zero Copy Connectors','IntegrationHub · Stream Connect · REST','PSDS case mgmt / ICM (where licensed)','Workflow Studio / Flow Designer','ServiceNow AI Action Fabric (MCP / A2A)'],3)+16
    y=_band(s,x,bw,y,'Supporting governance products',
        ['AI Control Tower','Integrated Risk Management (IRM)','Policy & Compliance Management','CMDB','Platform / Performance Analytics'],3)+16
    y=_band(s,x,bw,y,'Exception & escalation products',
        ['Security Incident Response','Security Case Management'],2)+16
    y=_band(s,x,bw,y,'Optional operational extensions',
        ['Operational Technology Management','Field Service Management','Government Service Portal'],3)+16
    s.label(14,y+22,'Products are mapped only where genuinely relevant. Availability, SKU, table and licensing specifics are DISCOVERY QUESTIONS to confirm with ServiceNow. Named “ServiceNow AI Action Fabric” (some official materials shorten it to “Action Fabric”). Data access and action orchestration are distinct: Workflow Data Fabric / Zero Copy Connectors reference external data without copying where supported; IntegrationHub / Stream Connect / REST handle ingestion and orchestration.',fill=INK,fs=10.5)
    return s.render()

def d_seq_auth():
    s=SVG(W); cx=308; nw=300
    seq=[('Vehicle-intelligence platform — event + evidence (raw retained)','CITY','evidence refs + metadata'),
         ('Workflow Data Fabric (zero-copy) reference · IntegrationHub / Stream Connect ingest','SNOW','case-relevant references'),
         ('PSDS case mgmt / ICM (where licensed) — purpose, scope, jurisdiction, approvals','SNOW','context assembly'),
         ('Context — IRM policy · AI Control Tower model status · CMDB / OT asset','SNOW','PROPOSED governance request'),
         ('RA-5 · Trusted Evidence Admission','UEXE','admitted, trusted evidence'),
         ('Decision Authority · DecisionCase + CER','UDEC','binding decision (non-AI)'),
         ('Model Authority · consumes AI Control Tower model fact','UDEC','model authorization'),
         ('Risk Authority · signed authorization envelope','AUTH','the sole machine authority'),
         ('ActionGate · exact-action authorization','UDEC',None),
         ('Action Clearance · live operational check → CLEAR (Phase 2)','UDEC',None)]
    pos=_col(s,cx,nw,16,seq,20,44,fs=10.5)
    sx=530; sw=W-sx-14; st=pos[4][0]; sb=pos[9][1]
    s.box(sx,st,sw,sb-st,'Fail-closed → auditable reason returned to the ServiceNow case: DENIED / INDETERMINATE / EXPIRED (ActionGate) · HOLD / BLOCK / ESCALATE (Clearance) · DENY / HOLD (Model Authority)','STOP',fs=9.5)
    for i in (6,8,9):
        s.arrow(cx+nw/2,(pos[i][0]+pos[i][1])/2,sx,(pos[i][0]+pos[i][1])/2,None,color=CAT['STOP'][1])
    s.label(14,pos[-1][1]+22,'Phase 1: ServiceNow assembles the case and context; Ugence independently admits evidence, binds a decision, confirms model eligibility, mints the one signed authority, authorizes the exact action and checks live safety. PROPOSED integration.',fill=INK,fs=10.5)
    return s.render()

def d_seq_exec():
    # Two ALTERNATIVE branches — never sequential co-owners of the same execution attempt.
    s=SVG(W)
    s.box(170,16,380,44,'Authorized + cleared action (from Phase 1)','UDEC',fs=11)
    s.label(190,82,'alternative branch — one per action',fill=MUTED,fs=9,anchor='middle')
    s.label(530,82,'alternative branch — one per action',fill=MUTED,fs=9,anchor='middle')
    # split arrows
    s.arrow(310,60,200,90,None); s.arrow(410,60,520,90,None)
    # Pattern A (left)
    s.box(40,92,300,56,'PATTERN A · ServiceNow dispatch — Flow Designer / AI Action Fabric / IntegrationHub','SNOW',fs=10.5)
    s.arrow(190,148,190,172)
    s.box(40,172,300,44,'External executor → execution receipt','EXT',fs=10.5)
    # Pattern B (right)
    s.box(380,92,300,56,'PATTERN B · Ugence Agent Runtime → external executor','UEXE',fs=10.5)
    s.arrow(530,148,530,172)
    s.box(380,172,300,44,'Result returns to Agent Runtime → execution receipt','UEXE',fs=10.5)
    # converge
    s.arrow(190,216,320,262,None); s.arrow(530,216,400,262,None)
    s.box(170,262,380,48,'RA-8 effect reconciliation · RA-7 in-flight assurance · RA-6 authority lifecycle','UEXE',fs=11)
    s.arrow(360,310,360,334,'assurance verdict')
    s.box(170,334,380,52,'ServiceNow write-back — PSDS case · IRM issue / exception · AI Control Tower audit · Platform Analytics','SNOW',fs=10.5)
    s.label(14,410,'Phase 2 has two alternative execution branches; exactly one is in force per action, and ServiceNow dispatch and Agent Runtime are never sequential co-owners of one execution attempt. Pattern A: ServiceNow dispatches, the external system returns a receipt, RA-8 assures, ServiceNow writes back. Pattern B: Ugence Agent Runtime invokes the external executor, the result returns to Agent Runtime which emits the receipt to RA-8, then ServiceNow writes back. PROPOSED integration.',fill=INK,fs=10.5)
    return s.render()

def d_ownership():
    s=SVG(W); x=14; bw=W-28; y=14
    def band(y,cat,title,items,per_row):
        s.parts.append(f'<rect x="{x}" y="{y}" width="{bw}" height="24" rx="6" fill="{CAT[cat][2]}"/>')
        s.parts.append(f'<text x="{x+10}" y="{y+16}" font-family="Helvetica,Arial,sans-serif" font-size="11" font-weight="700" fill="#fff">{esc(title)}</text>')
        s._grow(y+24)
        return _chiprow(s,items,x+8,y+32,bw-16,cat,per_row=per_row,fs=9,ch=30,gap=8)
    y=band(y,'CITY','Vehicle-intelligence / city platform',
        ['Source evidence','Evidence storage','Evidence provenance','CV inference','Trajectory estimation'],3)+14
    y=band(y,'SNOW','ServiceNow — business system of record',
        ['Case (PSDS / ICM)','Purpose & scope','Policy & control SoR (IRM)','AI-governance SoR (AI Control Tower)','Workflow orchestration','KPI / ROI reporting'],3)+14
    y=band(y,'UDEC','Ugence — independent action-level authority & assurance',
        ['Evidence admission (RA-5)','Model eligibility decision','DecisionCase / CER','Signed machine authority','Exact-action authorization','Live clearance','Execution record','Effect verification'],4)+14
    y=band(y,'EXT','External consequence systems',['External-system execution','Execution receipt'],2)+14
    y=band(y,'HUMAN','Human authority',['Human approval','Human review','Appeals'],3)+14
    s.label(14,y+22,'No single binding responsibility is assigned to two systems. Policy & control records are ServiceNow’s system of record (IRM); the signed per-action authority is Ugence’s. Shared items cross a PROPOSED interface only.',fill=INK,fs=10.5)
    return s.render()

def d_citation():
    s=SVG(W); cx=306; nw=306
    seq=[('Junction 44 — camera image + controller RED (raw retained)','CITY','evidence refs'),
         ('WDF zero-copy reference · IntegrationHub ingest; PSDS creates the case','SNOW','purpose · scope · jurisdiction'),
         ('Context — IRM policy · AI Control Tower ANPR status · CMDB asset','SNOW','PROPOSED governance request'),
         ('RA-5 admits evidence (integrity · freshness · schema)','UEXE','admitted evidence'),
         ('Decision Authority · DecisionCase + CER','UDEC','binding decision'),
         ('Model Authority — ANPR eligible for enforcement','UDEC','model authorized'),
         ('Risk Authority · signed authorization envelope','AUTH','scoped authority'),
         ('ActionGate · ISSUE_TRAFFIC_CITATION → AUTHORIZED','UDEC',None),
         ('Action Clearance → CLEAR','UDEC','authorized + cleared'),
         ('ServiceNow dispatch (Flow Designer / AI Action Fabric)','SNOW','authorized action'),
         ('Traffic-enforcement system executes → receipt','EXT','execution receipt'),
         ('RA-8 reconciles the effect','UEXE','effect matched'),
         ('PSDS case updated — full evidence → authority → action → effect lineage','SNOW',None)]
    pos=_col(s,cx,nw,14,seq,15,42,fs=10)
    s.label(14,pos[-1][1]+20,'Successful path (Pattern A, ServiceNow-led dispatch). Only an authorized, cleared exact action reaches the external system; the effect is verified and the lineage lands on the ServiceNow case. Illustrative example; PROPOSED integration.',fill=INK,fs=10.5)
    return s.render()

def d_failure():
    s=SVG(W); cx=300; nw=290
    seq=[('PSDS investigative case + assembled context','SNOW','PROPOSED governance request'),
         ('RA-5 evidence admission','UEXE','admitted?'),
         ('Model Authority','UDEC','eligible?'),
         ('ActionGate · exact-action authorization','UDEC','authorized?'),
         ('Action Clearance · live check','UDEC','clear?'),
         ('Ugence returns a non-authorizing disposition + reason codes','UDEC',None)]
    pos=_col(s,cx,nw,16,seq,24,46,fs=10.5)
    sx=520; sw=W-sx-14; st=pos[1][0]; sb=pos[4][1]
    s.box(sx,st,sw,sb-st,'DENIED · INDETERMINATE · HOLD · BLOCK · ESCALATE — e.g. plate below threshold (uncertain identity), stale controller record, model not eligible, authority expired, parameters drifted','STOP',fs=9.5)
    for i in (1,2,3,4):
        s.arrow(cx+nw/2,(pos[i][0]+pos[i][1])/2,sx,(pos[i][0]+pos[i][1])/2,None,color=CAT['STOP'][1])
    s.arrow(sx+sw/2,sb,sx+sw/2,(pos[5][0]+pos[5][1])/2,'reason codes')
    s.arrow(sx+sw/2,(pos[5][0]+pos[5][1])/2,cx+nw/2,(pos[5][0]+pos[5][1])/2,None)
    s.box(cx-nw/2,pos[5][1]+26,nw,44,'ServiceNow PSDS case — human-review activity or request for further admissible evidence; no citation, disclosure or identity assertion occurs','SNOW',fs=10)
    s.arrow(cx,pos[5][1],cx,pos[5][1]+26)
    s.label(14,pos[5][1]+80,'Uncertain identity is preserved, never converted to fact. The auditable reason is written back to the ServiceNow case, which routes human review. Illustrative example.',fill=INK,fs=10.5)
    return s.render()

def d_investigation():
    s=SVG(W); cx=300; nw=300
    seq=[('PSDS case mgmt / ICM (where licensed) — bounded purpose, ± time window, route-connected geography','SNOW','coordinates investigation'),
         ('Agentic Playbook / AI Action Fabric — proposes an investigation step','SNOW','each proposed action'),
         ('Ugence — RA-5 admission + DecisionCase scope check','UDEC','within purpose & scope?'),
         ('ActionGate + Action Clearance','UDEC','AUTHORIZED + CLEAR'),
         ('Governed tool / API — camera search · registry · disclosure','EXT',None)]
    pos=_col(s,cx,nw,16,seq,24,46,fs=10.5)
    sx=524; sw=W-sx-14; st=pos[1][0]; sb=pos[3][1]
    s.box(sx,st,sw,sb-st,'DENY / ESCALATE — a wider time window, a new geographic zone, identity resolution or a new data class each become a NEW governed decision, returned to the investigative case','STOP',fs=9.5)
    for i in (2,3):
        s.arrow(cx+nw/2,(pos[i][0]+pos[i][1])/2,sx,(pos[i][0]+pos[i][1])/2,None,color=CAT['STOP'][1])
    s.label(14,pos[-1][1]+22,'Scenario — Pattern A (ServiceNow-coordinated): a ServiceNow Agentic Playbook / AI Action Fabric flow coordinates the investigation and the PSDS case is the system of record; Ugence independently authorizes each consequential expansion; results and escalation reasons return to the case. Agent Runtime is not the execution owner here. Technical ability to query is never authority to query. Illustrative.',fill=INK,fs=10.5)
    return s.render()

def d_assurance():
    s=SVG(W); cx=300; nw=316
    seq=[('Risk Authority · signed authorization envelope','AUTH','WHAT WAS AUTHORIZED'),
         ('Dispatch — ServiceNow (Pattern A) or Agent Runtime attempt (Pattern B)','UEXE','WHAT WAS ATTEMPTED'),
         ('External system · execution receipt','EXT','WHAT ACTUALLY EXECUTED'),
         ('RA-8 · effect assurance (MATCHED / MISMATCH / PARTIAL)','UEXE','WHAT EFFECT OCCURRED'),
         ('ServiceNow write-back — PSDS case · IRM issue / exception · AI Control Tower audit','SNOW',None)]
    pos=_col(s,cx,nw,16,seq,26,46,fs=11)
    rx=W-172; rw=158
    s.box(rx,pos[1][0]-2,rw,44,'RA-7 · in-flight trajectory assurance','UEXE',fs=9.5)
    s.box(rx,pos[3][0]-2,rw,44,'RA-6 · authority lifecycle: revoke / epoch / expire','UDEC',fs=9.5)
    s.arrow(cx+nw/2,(pos[1][0]+pos[1][1])/2,rx,pos[1][0]+20,None,color=CAT['HUMAN'][1],dashed=True)
    s.arrow(cx+nw/2,(pos[3][0]+pos[3][1])/2,rx,pos[3][0]+20,None,color=CAT['HUMAN'][1],dashed=True)
    s.arrow(rx+rw/2,pos[1][0]+44,rx+rw/2,pos[3][0]-2,'reassessment signal',color=CAT['HUMAN'][1],dashed=True)
    s.label(14,pos[-1][1]+22,'Authorization, attempt, execution and effect are distinct records. RA-8 never retroactively authorizes; RA-7/RA-8 emit neutral reassessment signals to RA-6, which may only restrict authority. Every verdict is written back to the ServiceNow case. Verification strength is bounded by the effect source.',fill=INK,fs=10.5)
    return s.render()

def d_optional():
    s=SVG(W)
    # two side-by-side optional branches
    lx=14; lw=(W-28-20)/2; rx2=lx+lw+20
    # left: FSM
    s.box(lx,16,lw,40,'Camera / signal-controller malfunction','CITY',fs=10.5)
    s.arrow(lx+lw/2,56,lx+lw/2,80)
    s.box(lx,80,lw,40,'CMDB / OT Management — asset health','SNOW',fs=10.5)
    s.arrow(lx+lw/2,120,lx+lw/2,144,'work order')
    s.box(lx,144,lw,40,'Field Service Management — dispatch technician','SNOW',fs=10.5)
    s.arrow(lx+lw/2,184,lx+lw/2,208)
    s.box(lx,208,lw,44,'Technician remediation → asset-health result returned to the case','EXT',fs=10)
    # right: Security
    s.box(rx2,16,lw,40,'Suspected credential abuse / tampering / unauthorized access','CITY',fs=10.5)
    s.arrow(rx2+lw/2,56,rx2+lw/2,80)
    s.box(rx2,80,lw,40,'Security Incident Response / Security Case Management','SNOW',fs=10.5)
    s.arrow(rx2+lw/2,120,rx2+lw/2,144,'investigation')
    s.box(rx2,144,lw,40,'Security investigation','SNOW',fs=10.5)
    s.arrow(rx2+lw/2,184,rx2+lw/2,208,'revoke / hold')
    s.box(rx2,208,lw,44,'Ugence RA-6 authority revocation / hold signal, where appropriate','UDEC',fs=10)
    s.label(14,272,'Optional operational extensions — outside the ordinary citation pipeline. An ordinary traffic citation is neither a field-service work order nor a security incident; these branches engage only on genuine asset-failure or security conditions. PROPOSED integration; illustrative.',fill=INK,fs=10.5)
    return s.render()

def d_roadmap():
    s=SVG(W); cx=W*0.5; nw=580; x=cx-nw/2; y=16; gap=15; H=52
    phases=[('Phase 0 · Discovery','Confirm ServiceNow products, editions, data model, tables and licensing with ServiceNow; map actions, evidence sources, approvals and audit needs (resolve the discovery questions).'),
            ('Phase 1 · Shadow governance','PSDS cases assemble context; Ugence classifies evidence and evaluates policy / model eligibility without blocking production.'),
            ('Phase 2 · Low-risk runtime gates','Gate selected searches, registry calls and disclosures before dispatch through IntegrationHub / Action Fabric.'),
            ('Phase 3 · Enforcement gate','Place ActionGate + Action Clearance before citation or other binding dispatch (Pattern A).'),
            ('Phase 4 · Agentic governance','Route Agentic Playbook / AI Action Fabric tool calls and Agent Runtime attempts (Pattern B) through Ugence.'),
            ('Phase 5 · Assurance & value','RA-8 write-back to PSDS / IRM; AI Control Tower audit; Platform Analytics KPIs; evidence-backed governed-value attribution.')]
    for i,(t,sub) in enumerate(phases):
        cat='CITY' if i==0 else ('SNOW' if i in (1,2) else ('UDEC' if i in (3,4) else 'AUTH'))
        s.box(x,y,nw,H,t,cat,num=i,sub=sub,fs=12)
        if i<len(phases)-1: s.arrow(cx,y+H,cx,y+H+gap)
        y=y+H+gap
    s.label(cx,y+10,'Autonomy is earned step by step; live controlled dispatch is not enabled until dry-run, exception-path and receipt checks pass. Every integration remains PROPOSED until built and confirmed with ServiceNow.',fill=INK,fs=10.5,anchor='middle')
    return s.render()

ALL = {
 'layman': d_layman,
 'snowmap': d_snowmap,
 'seq_auth': d_seq_auth,
 'seq_exec': d_seq_exec,
 'ownership': d_ownership,
 'citation': d_citation,
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
