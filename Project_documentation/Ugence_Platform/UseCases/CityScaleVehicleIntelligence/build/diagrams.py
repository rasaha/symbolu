# Portrait top-down workflow diagrams (SVG, vector). Newly laid out for portrait reading.
FS = 13.0
def _cw(fs): return 0.53*fs  # approx char width

CAT = {
 'CITY': ('#E1F0F7','#1C7FA8','#0E4C63'),   # cyan/teal — city & vehicle-intelligence systems
 'UDEC': ('#ECEAFB','#5145C7','#2A2170'),   # violet — Ugence decision / authority
 'UEXE': ('#E4EFF7','#2B6CB0','#173A5A'),   # blue — Ugence runtime / execution
 'AUTH': ('#E9F7EF','#2E7D5B','#14532D'),   # green — the signed authority envelope
 'EXT' : ('#EEF1F4','#6B7280','#374151'),   # grey — external consequence systems
 'STOP': ('#FBEBE9','#C0392B','#7A2016'),   # red — deny / hold / block / escalate
 'HUMAN':('#FBF1DD','#B7791F','#6B4A12'),   # amber — human authority / reassessment signal
 'SNOW': ('#E7F3EC','#2E7D5B','#14532D'),
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

def d_boundary():
    s=SVG(W); cx=W/2; nw=470; x=cx-nw/2
    y=16
    s.box(x,y,nw,84,'Vehicle-Intelligence Platform','CITY',sub='detection · ANPR/ALPR · vehicle re-identification · road-graph & trajectory · signal-controller correlation — determines what the evidence indicates',fs=14)
    y+=84
    s.arrow(cx,y,cx,y+32,'evidence package + proposed finding or action'); y+=32
    s.box(x,y,nw,92,'Ugence Governance & Execution Control','UDEC',sub='trusted evidence · policy requirements · risk & authority · exact-action authorization · live clearance · controlled execution · effect verification · audit',fs=14)
    y+=92
    s.arrow(cx,y,cx,y+32,'authorized, cleared action only'); y+=32
    s.box(x,y,nw,62,'City · Police · Traffic · Registry · Notification systems','EXT',sub='the consequential external effect is carried out here',fs=13)
    y+=62
    s.label(cx,y+26,'Intelligence proposes. It cannot authorize itself. Ugence decides what may be concluded, disclosed, investigated or executed — and verifies the effect stayed within that authorization.',fill=INK,fs=11,anchor='middle')
    return s.render()

def d_refarch():
    s=SVG(W); m=16; bw=W-2*m; x=m; y=14
    # Band A
    s.box(x,y,bw,20,'',' CITY'.strip() if False else 'CITY') if False else None
    def band(y,title,items,cat,per_row,hgt_note=0):
        # title strip
        s.parts.append(f'<rect x="{x}" y="{y}" width="{bw}" height="26" rx="7" fill="{CAT[cat][2]}"/>')
        s.parts.append(f'<text x="{x+12}" y="{y+18}" font-family="Helvetica,Arial,sans-serif" font-size="12" font-weight="700" fill="#fff">{esc(title)}</text>')
        s._grow(y+26)
        yy=_chiprow(s,items,x+8,y+34,bw-16,cat,per_row=per_row,fs=9.5,ch=32,gap=8)
        return yy
    yA=band(y,'1 · City & vehicle-intelligence systems',
            ['Cameras / edge','ANPR / ALPR','Vehicle detect & re-ID','Road-graph & trajectory','Signal controllers','Registry / operations'],'CITY',3)
    s.arrow(W/2,yA+2,W/2,yA+26,'evidence package + proposed finding or action');
    yB0=yA+28
    yB=band(yB0,'2 · Ugence governance & execution control (the control plane)',
            ['RA-5 · trusted evidence admission','Decision Authority · DecisionCase / CER','Model Authority','Risk Authority · signed authorization envelope','ActionGate · exact-action authorization','Action Clearance · live safety','Agent Runtime · governed execution','RA-7 / RA-8 assurance · RA-6 lifecycle · audit'],'UDEC',4)
    s.arrow(W/2-70,yB+2,W/2-70,yB+26,'authorized + cleared action')
    s.arrow(W/2+90,yB+26,W/2+90,yB+2,None,color=CAT['UEXE'][1]); s.label(W/2+100,yB+16,'receipt + observed effect',fill=MUTED,fs=9)
    yC0=yB+28
    yC=band(yC0,'3 · External consequence systems',
            ['Traffic enforcement','Police / investigative','Registry','Notification','Case management','ServiceNow / GRC (proposed)'],'EXT',3)
    s.label(x,yC+22,'The intelligence system may propose a finding or action; it cannot authorize itself. Every consequential action crosses the Ugence control plane first, and the observed effect is verified back against the authorization.',fill=INK,fs=10.5)
    return s.render()

def d_lifecycle():
    s=SVG(W); cx=318; nw=300; x=cx-nw/2; y=16; gap=22; H=42
    seq=[('City evidence package (observed / derived / inferred)','CITY','provenanced evidence'),
         ('RA-5 · Trusted Evidence Admission','UEXE','admitted, trusted evidence'),
         ('Decision Authority · DecisionCase + CER','UDEC','binding decision (non-AI)'),
         ('Model Authority · eligible model version','UDEC','model authorization'),
         ('Risk Authority · signed authorization envelope','AUTH','the sole machine authority'),
         ('ActionGate · exact-action authorization','UDEC','AUTHORIZED'),
         ('Action Clearance · live-safety before execution','UDEC','CLEAR'),
         ('Agent Runtime · governed execution','UEXE','execution receipt'),
         ('RA-8 · execution & effect assurance','UEXE','effect matched'),
         ('City record + tamper-evident audit chain','CITY',None)]
    pos=[]
    for i,(t,cat,lab) in enumerate(seq):
        s.box(x,y,nw,H,t,cat,fs=11); pos.append((y,y+H))
        if i<len(seq)-1: s.arrow(cx,y+H,cx,y+H+gap,lab)
        y=y+H+gap
    sx=530; sw=W-sx-14; st=pos[2][0]; sb=pos[6][1]
    s.box(sx,st,sw,sb-st,'Fail-closed dispositions — uncertainty is never promoted to authority: DENIED / INDETERMINATE / EXPIRED (ActionGate) · HOLD / BLOCK / ESCALATE (Action Clearance) · DENY / HOLD (Model Authority)','STOP',fs=9.5)
    for i in (3,5,6):
        s.arrow(x+nw,(pos[i][0]+pos[i][1])/2,sx,(pos[i][0]+pos[i][1])/2,None,color=CAT['STOP'][1])
    s.arrow(sx+sw/2,sb,sx+sw/2,(pos[9][0]+pos[9][1])/2,'reason codes + evidence')
    s.arrow(sx+sw/2,(pos[9][0]+pos[9][1])/2,x+nw,(pos[9][0]+pos[9][1])/2,None)
    s.label(14,pos[9][1]+26,'Intelligence proposes. Evidence is admitted. Authority decides. ActionGate enforces the exact action. Clearance checks live safety. The runtime executes. Assurance verifies attempt, execution and effect. No score, policy result or receipt independently grants authority — only the signed Risk Authority envelope does.',fill=INK,fs=10.5)
    return s.render()

def d_redlight():
    s=SVG(W); cx=314; nw=290; x=cx-nw/2; y=16; gap=22; H=44
    seq=[('Junction 44: camera image + signal-controller RED state','CITY','direct + recorded evidence'),
         ('RA-5 · admit evidence (integrity · freshness · schema)','UEXE','admitted evidence'),
         ('DecisionCase · purpose = TRAFFIC_VIOLATION_ENFORCEMENT','UDEC','bounded decision'),
         ('Model Authority · ANPR v3.7 eligible for enforcement','UDEC','model authorized'),
         ('Risk Authority · signed authorization envelope','AUTH','scoped authority'),
         ('ActionGate · ISSUE_TRAFFIC_CITATION','UDEC','AUTHORIZED'),
         ('Action Clearance · bind payload + digest + expiry','UDEC','CLEAR'),
         ('Traffic enforcement system executes the notice','EXT','execution receipt'),
         ('RA-8 · verify effect · advance / close the case','UEXE',None)]
    pos=[]
    for i,(t,cat,lab) in enumerate(seq):
        s.box(x,y,nw,H,t,cat,fs=11); pos.append((y,y+H))
        if i<len(seq)-1: s.arrow(cx,y+H,cx,y+H+gap,lab)
        y=y+H+gap
    sx=528; sw=W-sx-14; st=pos[1][0]; sb=pos[6][1]
    s.box(sx,st,sw,sb-st,'HOLD / DENY / INDETERMINATE (fail-closed): plate below binding threshold · missing controller record · clock skew beyond tolerance · model not eligible · authority expired · parameters drifted','STOP',fs=9.5)
    for i in (1,3,5,6):
        s.arrow(x+nw,(pos[i][0]+pos[i][1])/2,sx,(pos[i][0]+pos[i][1])/2,None,color=CAT['STOP'][1])
    s.arrow(sx+sw/2,sb,sx+sw/2,(pos[8][0]+pos[8][1])/2,'reason codes')
    s.arrow(sx+sw/2,(pos[8][0]+pos[8][1])/2,x+nw,(pos[8][0]+pos[8][1])/2,None)
    s.label(14,pos[8][1]+26,'The same incident supports a Junction 44 citation on direct evidence, yet an inferred earlier match at Junction 39 (identity 71%) is insufficient to assert a separate violation — each proposed use of the evidence is evaluated independently. Illustrative example.',fill=INK,fs=10.5)
    return s.render()

def d_agentic():
    s=SVG(W); cx=326; nw=300; x=cx-nw/2; y=16; gap=18; H=40
    # left agent cluster
    lx=14; lw=150
    agents=['Violation agent','Trajectory agent','Identity agent','Risk agent','Enforcement agent']
    ay=16
    for a in agents:
        s.box(lx,ay,lw,28,a,'CITY',fs=9.5); ay+=33
    s.label(lx+lw/2,ay+2,'agents propose',fill=MUTED,fs=9,anchor='middle')
    seq=[('Agent Runtime · governed coordination (fails closed without governance)','UEXE','each proposed tool call'),
         ('RA-5 admission + DecisionCase scope check','UDEC','within purpose & scope?'),
         ('ActionGate · exact-action authorization','UDEC','AUTHORIZED'),
         ('Action Clearance · live safety','UDEC','CLEAR'),
         ('Tool / API: camera search · registry · citation · disclosure','EXT',None)]
    pos=[]
    for i,(t,cat,lab) in enumerate(seq):
        s.box(x,y,nw,H,t,cat,fs=11); pos.append((y,y+H))
        if i<len(seq)-1: s.arrow(cx,y+H,cx,y+H+gap,lab)
        y=y+H+gap
    # connect agent cluster to Agent Runtime (row 0)
    ar=pos[0]; armid=(ar[0]+ar[1])/2
    s.arrow(lx+lw, (16+ay-36)/2, x, armid, None,color=CAT['CITY'][1])
    sx=528; sw=W-sx-14; st=pos[1][0]; sb=pos[3][1]
    s.box(sx,st,sw,sb-st,'DENY / ESCALATE — scope expansion: a wider time window, a new geographic zone, identity resolution or a new data class each require a NEW governed decision','STOP',fs=9.5)
    for i in (1,2,3):
        s.arrow(x+nw,(pos[i][0]+pos[i][1])/2,sx,(pos[i][0]+pos[i][1])/2,None,color=CAT['STOP'][1])
    s.label(14,pos[4][1]+26,'"Search every camera in the city for the last seven days" can be technically feasible and still return DENY, because the DecisionCase authorizes only a bounded, route-connected search (for example ±30 minutes). Technical ability is not authority.',fill=INK,fs=10.5)
    return s.render()

def d_assurance():
    s=SVG(W); cx=300; nw=316; x=cx-nw/2; y=16; gap=20; H=42
    seq=[('Risk Authority · signed authorization envelope','AUTH','WHAT WAS AUTHORIZED'),
         ('Agent Runtime · provider attempt','UEXE','WHAT COMMAND WAS ATTEMPTED'),
         ('External system · execution receipt','EXT','WHAT ACTUALLY EXECUTED'),
         ('RA-8 · effect assurance (MATCHED / MISMATCH / PARTIAL)','UEXE','WHAT EFFECT OCCURRED'),
         ('City record + audit chain','CITY',None)]
    pos=[]
    for i,(t,cat,lab) in enumerate(seq):
        s.box(x,y,nw,H,t,cat,fs=11); pos.append((y,y+H))
        if i<len(seq)-1: s.arrow(cx,y+H,cx,y+H+gap,lab)
        y=y+H+gap
    # RA-7 in-flight + RA-6 lifecycle on the right
    rx=W-176; rw=162
    s.box(rx,pos[1][0]-2,rw,44,'RA-7 · in-flight trajectory assurance','UEXE',fs=9.5)
    s.box(rx,pos[3][0]-2,rw,44,'RA-6 · authority lifecycle: revoke / epoch / expire','UDEC',fs=9.5)
    s.arrow(x+nw,(pos[1][0]+pos[1][1])/2,rx,pos[1][0]+20,None,color=CAT['HUMAN'][1],dashed=True)
    s.arrow(x+nw,(pos[3][0]+pos[3][1])/2,rx,pos[3][0]+20,None,color=CAT['HUMAN'][1],dashed=True)
    s.arrow(rx+rw/2,pos[1][0]+44,rx+rw/2,pos[3][0]-2,'reassessment signal',color=CAT['HUMAN'][1],dashed=True)
    s.label(14,pos[4][1]+26,'Authorization, attempt, execution and effect are distinct records. RA-7 (in-flight) and RA-8 (post-effect) emit neutral reassessment signals to RA-6, which may revoke, advance the authority epoch, or expire authority. Reassessment restricts authority; it never grants it, and RA-8 never retroactively authorizes an action.',fill=INK,fs=10.5)
    return s.render()

def d_deploy():
    s=SVG(W); cx=300; nw=320; x=cx-nw/2; y=16; gap=28; H=48
    s.box(x,y,nw,H,'Vehicle-intelligence services','CITY',fs=12); p0=(y,y+H); y+=H
    s.arrow(cx,y,cx,y+gap,'evidence + action proposal'); y+=gap
    s.box(x,y,nw,74,'Ugence governance services','UDEC',sub='RA-5 · DecisionCase · Model Authority · Risk Authority · ActionGate · Action Clearance · RA-7/8/6 assurance · audit',fs=12); p1=(y,y+74); y+=74
    s.arrow(cx,y,cx,y+gap,'authorized + cleared action token'); y+=gap
    s.box(x,y,nw,H,'City operational systems','EXT',fs=12); y+=H
    # integration patterns box on the right of governance services
    rx=W-186; rw=172
    s.box(rx,p1[0]-4,rw,90,'Integration patterns','UEXE',sub='synchronous API gate (preferred for consequential actions) · sidecar / proxy · event-driven · shadow · batch assurance',fs=10.5)
    s.arrow(rx, p1[0]+40, x+nw, p1[0]+40, None, color=CAT['UEXE'][1])
    # ServiceNow system of record on the left
    sxb=14; swb=150
    s.box(sxb,p1[0]-4,swb,90,'ServiceNow / GRC','SNOW',sub='system of record: policies · controls · cases · exceptions · dashboards. Integration PROPOSED — no connector ships.',fs=10.5)
    s.arrow(sxb+swb, p1[0]+40, x, p1[0]+40, None, color=CAT['SNOW'][1],dashed=True)
    s.label(14,y+22,'Ugence adds evidence-bound decision-time and execution-time controls for consequential agent actions; ServiceNow (or another enterprise workflow / GRC platform) can remain the system of record. The integration is a neutral pattern, not a shipped connector.',fill=INK,fs=10.5)
    return s.render()

def d_roadmap():
    s=SVG(W); cx=W*0.5; nw=560; x=cx-nw/2; y=16; gap=16; H=52
    phases=[('Phase 0 · Discovery','Map the vehicle platform, actions, evidence sources, models, policies, authority roles, APIs and audit needs.'),
            ('Phase 1 · Shadow governance','Create DecisionCases, classify evidence, evaluate policy and model eligibility without blocking production.'),
            ('Phase 2 · Low-risk runtime gates','Gate selected searches, registry calls, disclosures or non-binding actions.'),
            ('Phase 3 · Enforcement gate','Place ActionGate + Action Clearance before citation or other binding effects.'),
            ('Phase 4 · Agent governance','Route autonomous investigation tool calls through Agent Runtime governance.'),
            ('Phase 5 · Assurance & optimization','Dashboards, appeal support, policy analytics, model-change governance, resilience hardening.')]
    for i,(t,sub) in enumerate(phases):
        cat='CITY' if i==0 else ('UDEC' if i in (1,2,3) else ('UEXE' if i==4 else 'AUTH'))
        s.box(x,y,nw,H,t,cat,num=i,sub=sub,fs=12)
        if i<len(phases)-1: s.arrow(cx,y+H,cx,y+H+gap)
        y=y+H+gap
    s.label(cx,y+10,'Autonomy is earned step by step; live controlled execution is not enabled until dry-run, exception-path and receipt checks pass.',fill=INK,fs=10.5,anchor='middle')
    return s.render()

ALL = {
 'boundary': d_boundary,
 'refarch': d_refarch,
 'lifecycle': d_lifecycle,
 'redlight': d_redlight,
 'agentic': d_agentic,
 'assurance': d_assurance,
 'deploy': d_deploy,
 'roadmap': d_roadmap,
}

if __name__=='__main__':
    import os
    os.makedirs('svg',exist_ok=True)
    for k,fn in ALL.items():
        svg,w,h=fn()
        open(f'svg/{k}.svg','w').write(svg)
        print(k,w,h)
