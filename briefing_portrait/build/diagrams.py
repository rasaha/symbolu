# Portrait top-down workflow diagrams (SVG, vector). Newly laid out for portrait reading.
FS = 13.0
def _cw(fs): return 0.53*fs  # approx char width

CAT = {
 'SNOW': ('#E7F3EC','#2E7D5B','#14532D'),
 'UDEC': ('#ECEAFB','#5145C7','#2A2170'),
 'UEXE': ('#E4EFF7','#2B6CB0','#173A5A'),
 'EXT' : ('#EEF1F4','#6B7280','#374151'),
 'STOP': ('#FBEBE9','#C0392B','#7A2016'),
 'HUMAN':('#FBF1DD','#B7791F','#6B4A12'),
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

def d_layman_canonical():
    s=SVG(W); cx=W*0.42; nw=300; x=cx-nw/2; y=16; gap=14; H=44
    stages=[('Business event','a need or request arises','SNOW'),
            ('AI proposes an action','“do X to target Y”','UEXE'),
            ('Authorized decision','approved by delegated authority','UDEC'),
            ('Permission for the exact action','bound to target Y and payload','UDEC'),
            ('“Is it safe right now?” check','live conditions verified','UEXE'),
            ('Controlled execution','the action is carried out','UEXE'),
            ('Confirm the actual effect','only the intended effect occurred','UEXE'),
            ('Auditable result returned to ServiceNow','status + receipt references','SNOW')]
    pos=[]
    for i,(t,sub,cat) in enumerate(stages):
        s.box(x,y,nw,H,t,cat,num=i+1,sub=sub); pos.append((y,y+H));
        if i<len(stages)-1: s.arrow(cx,y+H,cx,y+H+gap);
        y=y+H+gap
    return s.render()

def d_tech_canonical():
    s=SVG(W); cx=W*0.36; nw=290; x=cx-nw/2; y=16; gap=30; H=42
    seq=[('ServiceNow record','SNOW','business record + approval context'),
         ('Decision Authority','UDEC','binding decision record'),
         ('ActionGate  ·  exact action','UDEC','exact-target authorization'),
         ('Action Clearance (ACP)','UDEC','CLEAR'),
         ('Agent Runtime  ·  coordinates','UEXE','execution receipt'),
         ('RA-8 Execution Assurance','UEXE','effect matched'),
         ('ServiceNow record (status + receipts)','SNOW',None)]
    pos=[]
    for i,(t,cat,lab) in enumerate(seq):
        s.box(x,y,nw,H,t,cat); pos.append((y,y+H))
        if i<len(seq)-1: s.arrow(cx,y+H,cx,y+H+gap,lab)
        y=y+H+gap
    # stop column
    sx=W*0.72; sw=W-sx-14
    stop_top=pos[2][0]; stop_bot=pos[3][1]
    s.box(sx,stop_top,sw,stop_bot-stop_top,'STOP / HOLD / BLOCK / ESCALATE — uncertainty is never promoted to permission (fail-closed)','STOP',fs=11)
    s.arrow(x+nw,(pos[2][0]+pos[2][1])/2,sx,(pos[2][0]+pos[2][1])/2,'DENIED / INDET.',color=CAT['STOP'][1])
    s.arrow(x+nw,(pos[3][0]+pos[3][1])/2,sx,(pos[3][0]+pos[3][1])/2,'HOLD / BLOCK',color=CAT['STOP'][1])
    s.arrow(sx+sw/2,stop_bot,sx+sw/2,(pos[6][0]+pos[6][1])/2,'reason + evidence')
    s.arrow(sx+sw/2,(pos[6][0]+pos[6][1])/2,x+nw,(pos[6][0]+pos[6][1])/2,None)
    s.label(14,pos[6][1]+28,'Where a scenario needs them, Policy Workflow Compiler and RA-5 sit upstream of the decision; Risk Authority mints a signed, scoped, time-limited authorization; Model Authority authorizes the model; StoryGraph flags sequence risk; RA-6 revokes authority; RA-7 assesses in-flight trajectory. Only participating modules are shown per scenario.',fill=INK,fs=10.5)
    return s.render()

def d_uc5_layman():
    s=SVG(W); cx=W*0.42; nw=310; x=cx-nw/2; y=16; gap=13; H=42
    stages=[('Checkout slowing down','demand + latency pressure','SNOW'),
            ('AI recommends adding capacity','“scale 12 → 18”','UEXE'),
            ('Approval confirmed for this exact change','delegated authority','UDEC'),
            ('Permission bound to this cluster & capacity','this cluster, service, window','UDEC'),
            ('“Is it safe right now?”','freeze / dependencies / cost','UEXE'),
            ('Capacity change carried out','within window & cost ceiling','UEXE'),
            ('Confirm what actually changed','only the intended instances','UEXE'),
            ('Auditable result returned to the change record',None,'SNOW')]
    for i,(t,sub,cat) in enumerate(stages):
        s.box(x,y,nw,H,t,cat,num=i+1,sub=sub)
        if i<len(stages)-1: s.arrow(cx,y+H,cx,y+H+gap)
        y=y+H+gap
    # stop branch at safety check (index4)
    return s.render()

def d_uc5_auth():
    s=SVG(W); cx=W*0.36; nw=300; x=cx-nw/2; y=16; gap=30; H=44
    seq=[('ServiceNow Change Management · CHG0048217','SNOW','change record + approval context'),
         ('Decision Authority','UDEC','binding decision record'),
         ('ActionGate','UDEC','exact-target action authorization'),
         ('Action Clearance (ACP)','UDEC','CLEAR → proceed to execution (Phase 2)')]
    pos=[]
    for i,(t,cat,lab) in enumerate(seq):
        s.box(x,y,nw,H,t,cat); pos.append((y,y+H))
        if i<len(seq)-1: s.arrow(cx,y+H,cx,y+H+gap,lab)
        else: s.arrow(cx,y+H,cx,y+H+gap,lab)
        y=y+H+gap
    sx=W*0.72; sw=W-sx-14
    st=pos[2][0]; sb=pos[3][1]
    s.box(sx,st,sw,sb-st,'HOLD / BLOCK / ESCALATE — no execution','STOP',fs=11)
    s.arrow(x+nw,(pos[2][0]+pos[2][1])/2,sx,(pos[2][0]+pos[2][1])/2,'DENIED / INDET.',color=CAT['STOP'][1])
    s.arrow(x+nw,(pos[3][0]+pos[3][1])/2,sx,(pos[3][0]+pos[3][1])/2,'HOLD / BLOCK',color=CAT['STOP'][1])
    s.label(14,pos[3][1]+42,'Side paths (any of these stops the workflow and returns an auditable reason to CHG0048217): missing evidence or approval; changed target or requested action; unsafe live conditions; revoked or expired authority; governance not wired (Agent Runtime fails closed).',fill=INK,fs=10.5)
    s.arrow(cx,pos[3][1]+gap,cx,pos[3][1]+gap+6,None)
    return s.render()

def d_uc5_exec():
    # Three columns: RA-6 (left) · main flow (centre) · Cloud Scaling Operations (right).
    s=SVG(W); cx=332; nw=264; x=cx-nw/2; y=20
    s.box(x,y,nw,40,'Action Clearance (ACP) · CLEAR','UDEC'); y+=40
    s.arrow(cx,y,cx,y+26,'authorized + cleared'); y+=26
    s.box(x,y,nw,54,'Agent Runtime · governed execution coordination','UEXE',fs=11.5); ar=(y,y+54); armid=(ar[0]+ar[1])/2; y+=54
    # Cloud Scaling Operations on the RIGHT, invoked by Agent Runtime
    csx=510; csw=196; csy=ar[0]-6
    s.box(csx,csy,csw,58,'Cloud Scaling Operations','UEXE',sub='controlled actuation · dry-run default',fs=11)
    # invoke (main -> CSO) and return (CSO -> main); labels centred in the 46px gap
    s.arrow(x+nw,armid-9,csx,armid-9,None,color=CAT['UEXE'][1])
    s.arrow(csx,armid+11,x+nw,armid+11,None,color=CAT['UEXE'][1])
    s.label((x+nw+csx)/2,armid-13,'invokes',fill=CAT['UEXE'][1],fs=8.5,weight='700',anchor='middle')
    s.label((x+nw+csx)/2,armid+9,'returns',fill=CAT['UEXE'][1],fs=8.5,weight='700',anchor='middle')
    # cloud target below CSO
    cyy=csy+58+30
    s.cyl(csx+16,cyy,csw-32,46,'Production Kubernetes cluster','EXT')
    s.arrow(csx+csw/2-20,csy+58,csx+csw/2-20,cyy,None)
    s.arrow(csx+csw/2+24,cyy,csx+csw/2+24,csy+58,None,color=ARROW)
    s.label(csx+csw/2,cyy+62,'scaling request ↓   ↑ outcome + audit',fill=MUTED,fs=9,anchor='middle')
    # RA-6 lifecycle on the LEFT, revokes into Agent Runtime
    rx=14; rw=172
    s.box(rx,ar[0]-6,rw,58,'RA-6 lifecycle','UDEC',sub='revoke / supersede / expire',fs=11)
    s.arrow(rx+rw,armid,x,armid,None,color=CAT['HUMAN'][1],dashed=True)
    # AR -> RA-8
    s.arrow(cx,y,cx,y+26,'execution receipt'); y+=26
    s.box(x,y,nw,42,'RA-8 Execution Assurance','UEXE'); y+=42
    s.arrow(cx,y,cx,y+26,'effect matched'); y+=26
    s.box(x,y,nw,54,'ServiceNow Change Record — status, receipt references and observed outcome','SNOW',fs=11); y+=54
    s.label(14,max(y,cyy+80)+14,'Agent Runtime invokes Cloud Scaling Operations (a domain executor, not a preceding gate); the executor returns its result to Agent Runtime, which supplies the execution receipt to RA-8. RA-8 compares authorized intent, the execution receipt and the observed effect; a mismatch / partial / uncertain result is escalated and still returns an auditable outcome to the change record. RA-8 never retroactively authorizes an action.',fill=INK,fs=10.5)
    return s.render()

def _flow_with_stop(seq, stop_label, stop_range, note, cx_frac=0.36, target_left=None):
    s=SVG(W); cx=W*cx_frac; nw=300; x=cx-nw/2; y=16; gap=30; H=44
    pos=[]
    for i,(t,cat,lab) in enumerate(seq):
        s.box(x,y,nw,H if '\n' not in t else H+8,t,cat); pos.append((y,y+H));
        if i<len(seq)-1: s.arrow(cx,y+H,cx,y+H+gap,lab)
        y=y+H+gap
    sx=W*0.72; sw=W-sx-14
    a,b=stop_range
    st=pos[a][0]; sb=pos[b][1]
    s.box(sx,st,sw,sb-st,stop_label,'STOP',fs=11)
    for i,lab in stop_range_arrows(a,b):
        s.arrow(x+nw,(pos[i][0]+pos[i][1])/2,sx,(pos[i][0]+pos[i][1])/2,lab,color=CAT['STOP'][1])
    if note: s.label(14,sb+30,note,fill=INK,fs=10.5)
    return s,pos,x,nw,cx,sx,sw,sb

def stop_range_arrows(a,b):
    return []

def d_uc11():
    # Three columns: left side-cluster (RA-6 + CI target) · main flow · right STOP.
    s=SVG(W); cx=314; nw=248; x=cx-nw/2; y=16; gap=30; H=46
    seq=[('ServiceNow Vulnerability Response + Change','SNOW','remediation task + approval'),
         ('Decision Authority','UDEC','binding decision record'),
         ('ActionGate','UDEC','exact CI-set + patch authorization'),
         ('Action Clearance (ACP) · per stage','UDEC','CLEAR per stage'),
         ('Agent Runtime · staged rollout','UEXE','execution receipts'),
         ('RA-8 Execution Assurance','UEXE','matched / partial'),
         ('ServiceNow Remediation + Change record','SNOW',None)]
    pos=[]
    for i,(t,cat,lab) in enumerate(seq):
        s.box(x,y,nw,H,t,cat); pos.append((y,y+H))
        if i<len(seq)-1: s.arrow(cx,y+H,cx,y+H+gap,lab)
        y=y+H+gap
    lx=14; lw=150
    # CI target cylinder left of Agent Runtime (idx4)
    ar=pos[4]; armid=(ar[0]+ar[1])/2
    s.cyl(lx,ar[0]-1,lw,46,'40 CIs · payments-web','EXT')
    s.arrow(x,armid-8,lx+lw,armid-8,None)
    s.arrow(lx+lw,armid+12,x,armid+12,None)
    s.label(lx+lw/2,ar[0]+64,'staged patch · outcome',fill=MUTED,fs=9,anchor='middle')
    # RA-6 revoke into ACP (idx3)
    acp=pos[3]; acpmid=(acp[0]+acp[1])/2
    s.box(lx,acp[0]-4,lw,52,'RA-6 lifecycle','UDEC',sub='revoke / supersede / expire',fs=11)
    s.arrow(lx+lw,acpmid,x,acpmid,None,color=CAT['HUMAN'][1],dashed=True)
    # right STOP over ActionGate + ACP (idx2-idx3)
    sx=528; sw=W-sx-14; st=pos[2][0]; sb=pos[3][1]
    s.box(sx,st,sw,sb-st,'HOLD / BLOCK / ESCALATE — remaining stages stopped','STOP',fs=10.5)
    s.arrow(x+nw,(pos[2][0]+pos[2][1])/2,sx,(pos[2][0]+pos[2][1])/2,'DENIED / INDET.',color=CAT['STOP'][1])
    s.arrow(x+nw,acpmid,sx,acpmid,'HOLD / BLOCK',color=CAT['STOP'][1])
    s.arrow(sx+sw/2,sb,sx+sw/2,(pos[6][0]+pos[6][1])/2,'reason + evidence')
    s.arrow(sx+sw/2,(pos[6][0]+pos[6][1])/2,x+nw,(pos[6][0]+pos[6][1])/2,None)
    s.label(14,pos[6][1]+26,'Revocation is bounded-latency: it stops the next stage at the pre-effect recheck, not one already in progress. Illustrative example.',fill=INK,fs=10.5)
    return s.render()

def d_uc6():
    # Three columns: left ERP target · main flow · right STOP.
    s=SVG(W); cx=314; nw=248; x=cx-nw/2; y=16; gap=30; H=46
    seq=[('ServiceNow Service Catalog · RITM0102934','SNOW','access request + approval'),
         ('Decision Authority','UDEC','binding decision record'),
         ('ActionGate','UDEC','exact-entitlement authorization'),
         ('Action Clearance (ACP) · SoD + risk veto','UDEC','CLEAR'),
         ('Agent Runtime · provisioning','UEXE','execution receipt'),
         ('RA-8 Execution Assurance','UEXE','only authorized entitlement granted'),
         ('ServiceNow Request record','SNOW',None)]
    pos=[]
    for i,(t,cat,lab) in enumerate(seq):
        s.box(x,y,nw,H,t,cat); pos.append((y,y+H))
        if i<len(seq)-1: s.arrow(cx,y+H,cx,y+H+gap,lab)
        y=y+H+gap
    lx=14; lw=150
    ar=pos[4]; armid=(ar[0]+ar[1])/2
    s.cyl(lx,ar[0]-1,lw,46,'ERP entitlement system','EXT')
    s.arrow(x,armid-8,lx+lw,armid-8,None)
    s.arrow(lx+lw,armid+12,x,armid+12,None)
    s.label(lx+lw/2,ar[0]+64,'provision · outcome',fill=MUTED,fs=9,anchor='middle')
    sx=528; sw=W-sx-14; st=pos[2][0]; sb=pos[3][1]
    s.box(sx,st,sw,sb-st,'BLOCK / ESCALATE — no grant, routed for human review','STOP',fs=10.5)
    s.arrow(x+nw,(pos[2][0]+pos[2][1])/2,sx,(pos[2][0]+pos[2][1])/2,'DENIED / INDET.',color=CAT['STOP'][1])
    s.arrow(x+nw,(pos[3][0]+pos[3][1])/2,sx,(pos[3][0]+pos[3][1])/2,'SoD → BLOCK',color=CAT['STOP'][1])
    s.arrow(sx+sw/2,sb,sx+sw/2,(pos[6][0]+pos[6][1])/2,'SoD reason + evidence')
    s.arrow(sx+sw/2,(pos[6][0]+pos[6][1])/2,x+nw,(pos[6][0]+pos[6][1])/2,None)
    s.label(14,pos[6][1]+26,'The decisive control is the segregation-of-duties conflict at clearance time: the action can be perfectly authorized and still be blocked. Illustrative example.',fill=INK,fs=10.5)
    return s.render()

def d_uc3():
    # Main flow + right STOP with a generous gap so branch labels never clip.
    s=SVG(W); cx=W*0.36; nw=290; x=cx-nw/2; y=16; gap=28; H=46
    seq=[('ServiceNow AI Control Tower / IRM','SNOW','policy pack + control evidence references'),
         ('Policy Workflow Compiler + RA-5 trusted evidence','UDEC','re-checked control result'),
         ('Decision Authority','UDEC','binding decision record'),
         ('Risk Authority · signed, scoped, time-limited','UDEC','signed authorization artifact'),
         ('ActionGate','UDEC','exact-action authorization'),
         ('Agent Runtime → execution → RA-8 assurance','UEXE','effect matched'),
         ('ServiceNow AI case record (authorization + effect refs)','SNOW',None)]
    pos=[]
    for i,(t,cat,lab) in enumerate(seq):
        s.box(x,y,nw,H,t,cat,fs=11.5); pos.append((y,y+H))
        if i<len(seq)-1: s.arrow(cx,y+H,cx,y+H+gap,lab)
        y=y+H+gap
    sx=W*0.72; sw=W-sx-14; st=pos[1][0]; sb=pos[4][1]
    s.box(sx,st,sw,sb-st,'NOT PERMITTED — stale or untrusted evidence · no allow-family decision · DENIED / INDETERMINATE','STOP',fs=10.5)
    s.arrow(x+nw,(pos[1][0]+pos[1][1])/2,sx,(pos[1][0]+pos[1][1])/2,'evidence stale',color=CAT['STOP'][1])
    s.arrow(x+nw,(pos[3][0]+pos[3][1])/2,sx,(pos[3][0]+pos[3][1])/2,'no allow-family',color=CAT['STOP'][1])
    s.arrow(x+nw,(pos[4][0]+pos[4][1])/2,sx,(pos[4][0]+pos[4][1])/2,'DENIED / INDET.',color=CAT['STOP'][1])
    s.arrow(sx+sw/2,sb,sx+sw/2,(pos[6][0]+pos[6][1])/2,'reason + evidence')
    s.arrow(sx+sw/2,(pos[6][0]+pos[6][1])/2,x+nw,(pos[6][0]+pos[6][1])/2,None)
    s.label(14,pos[6][1]+26,'A caller-asserted “pass” is inert: only trusted, re-checked evidence satisfies a control. The authorization is signed, scoped and time-limited. AI Control Tower and AI Risk & Compliance remain the governance systems of record. Illustrative example.',fill=INK,fs=10.5)
    return s.render()

def d_uc4():
    s=SVG(W); cx=W*0.42; nw=320; x=cx-nw/2; y=16; gap=24; H=40
    seq=[('External AI agent · Claude / Copilot / custom','EXT','governed step request'),
         ('ServiceNow Action Fabric · via AI Control Tower','SNOW','business action context'),
         ('Agent Runtime · governance-decision seam','UEXE','per-step request'),
         ('Model Authority → ActionGate · exact payload','UDEC','exact-payload authorization'),
         ('StoryGraph → Action Clearance (ACP)','UDEC','CLEAR'),
         ('ServiceNow Action Fabric → dispatch','SNOW','dispatch'),
         ('OpenShell runtime enforcement · ServiceNow–NVIDIA','EXT','enforced execution result'),
         ('RA-7 Trajectory Assurance','UEXE','assurance evidence'),
         ('ServiceNow case + AI Control Tower audit','SNOW',None)]
    pos=[]
    for i,(t,cat,lab) in enumerate(seq):
        s.box(x,y,nw,H,t,cat,fs=11); pos.append((y,y+H))
        if i<len(seq)-1: s.arrow(cx,y+H,cx,y+H+gap,lab)
        y=y+H+gap
    sx=W*0.76; sw=W-sx-14; st=pos[3][0]; sb=pos[4][1]
    s.box(sx,st,sw,sb-st,'HOLD / BLOCK / ESCALATE — value movement paused','STOP',fs=10.5)
    s.arrow(x+nw,(pos[3][0]+pos[3][1])/2,sx,(pos[3][0]+pos[3][1])/2,'DENY / DENIED',color=CAT['STOP'][1])
    s.arrow(x+nw,(pos[4][0]+pos[4][1])/2,sx,(pos[4][0]+pos[4][1])/2,'ESCALATE seq-risk',color=CAT['STOP'][1])
    s.arrow(sx+sw/2,sb,sx+sw/2,(pos[8][0]+pos[8][1])/2,'reason + evidence')
    s.arrow(sx+sw/2,(pos[8][0]+pos[8][1])/2,x+nw,(pos[8][0]+pos[8][1])/2,None)
    s.label(14,pos[8][1]+18,'Dispatch and kernel-level enforcement are ServiceNow (Action Fabric) and NVIDIA (OpenShell). Ugence adds authority, exact-payload binding, sequence-risk and assurance only — composition, not replacement. Illustrative example.',fill=INK,fs=10.5)
    return s.render()

ALL = {
 'layman_canonical': d_layman_canonical,
 'tech_canonical': d_tech_canonical,
 'uc5_layman': d_uc5_layman,
 'uc5_auth': d_uc5_auth,
 'uc5_exec': d_uc5_exec,
 'uc11': d_uc11,
 'uc6': d_uc6,
 'uc3': d_uc3,
 'uc4': d_uc4,
}

if __name__=='__main__':
    import os
    os.makedirs('svg',exist_ok=True)
    for k,fn in ALL.items():
        svg,w,h=fn()
        open(f'svg/{k}.svg','w').write(svg)
        print(k,w,h)
