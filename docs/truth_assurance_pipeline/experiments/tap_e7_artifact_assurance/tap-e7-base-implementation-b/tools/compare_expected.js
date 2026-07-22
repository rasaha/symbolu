'use strict';
// Phase 2: reveal expected, compare against blind-produced records. No package writes.
const fs=require('fs'), path=require('path');
const PKG=process.argv[2], OUT=path.join(__dirname,'..','results');
const canon=(o)=> (o===null||typeof o!=='object')?JSON.stringify(o):
  Array.isArray(o)?'['+o.map(canon).join(',')+']':'{'+Object.keys(o).sort().map(k=>JSON.stringify(k)+':'+canon(o[k])).join(',')+'}';
const nf=(fs_)=>fs_.map(f=>[f.category,f.polarity]).sort();
const rows=[];
for(const fn of fs.readdirSync(path.join(OUT,'blind')).sort()){
  const fid=fn.slice(0,-5);
  const prod=JSON.parse(fs.readFileSync(path.join(OUT,'blind',fn)));
  const exp=JSON.parse(fs.readFileSync(path.join(PKG,'expected',fid+'.expected.json')));
  const rec=prod.assurance_record, auth=prod.authoritative, diffs=[];
  if(rec.outcome!==exp.outcome)diffs.push('outcome');
  if(canon(nf(rec.findings))!==canon(nf(exp.findings)))diffs.push('findings');
  if(canon(rec.evaluation_summary)!==canon(exp.evaluation_summary))diffs.push('evaluation_summary');
  if(canon(rec.projection_pi)!==canon(exp.projection_pi))diffs.push('projection_pi');
  if(rec.projection_pi_sha256!==exp.projection_pi_sha256)diffs.push('projection_hash');
  const ok=diffs.length===0;
  let cls; if(auth){ cls= ok?'EXACT_PASS':'IMPLEMENTATION_B_DEFECT_OR_PACKAGE_DEFECT'; }
  else cls='INFORMATIVE_NON_GATE';
  rows.push({fixture:fid,authoritative:auth,pass:ok,classification:cls,diffs,
    produced_outcome:rec.outcome,expected_outcome:exp.outcome,
    produced_findings:rec.findings.map(f=>f.category),expected_findings:exp.findings.map(f=>f.category)});
}
const mand=rows.filter(r=>r.authoritative);
const summary={mandatory_total:mand.length,mandatory_exact_pass:mand.filter(r=>r.pass).length,
  mandatory_fail:mand.filter(r=>!r.pass).length,
  informative_total:rows.length-mand.length,informative_pass:rows.filter(r=>!r.authoritative&&r.pass).length,
  informative_fail:rows.filter(r=>!r.authoritative&&!r.pass).length};
fs.writeFileSync(path.join(OUT,'mandatory-results.json'),JSON.stringify({summary,rows:mand},null,1));
fs.writeFileSync(path.join(OUT,'informative-results.json'),JSON.stringify({rows:rows.filter(r=>!r.authoritative)},null,1));
for(const r of mand) if(!r.pass) fs.writeFileSync(path.join(OUT,'defects',r.fixture+'.json'),JSON.stringify(r,null,1));
console.log('MANDATORY exact_pass:',summary.mandatory_exact_pass,'/',summary.mandatory_total,'| fail:',summary.mandatory_fail);
console.log('INFORMATIVE:',summary.informative_pass,'pass,',summary.informative_fail,'fail (non-gate)');
for(const r of mand) if(!r.pass) console.log('  FAIL',r.fixture,r.diffs,'prod',r.produced_findings,'exp',r.expected_findings);
