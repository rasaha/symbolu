'use strict';
// Blind harness: wraps fs.readFileSync to log every package read and THROW on any
// expected/ or derivations/ read while blind is active. Projects each fixture to the
// true input envelope only.
const fs=require('fs'), path=require('path');
const V=require('../src/verifier.js');
const CF=require('./recompute_config_fingerprint.js');
const PKG=process.argv[2];
const OUT=path.join(__dirname,'..','results');
const realRead=fs.readFileSync;
const OPENED=[]; let BLIND=false;
fs.readFileSync=function(f,...a){ const p=String(f);
  if(p.includes('tap-e7-base-companion-1.1.1')) OPENED.push(p);
  if(BLIND && (p.includes('/expected/')||p.includes('/derivations/')||p.includes('-audit/')||p.includes('implementation-a')))
    throw new Error('BLIND VIOLATION: '+p);
  return realRead.call(fs,f,...a); };

const [got,want]=CF.recompute(PKG);
if(got!==want){ console.error('FINGERPRINT MISMATCH — stop'); process.exit(2); }
const res=V.loadResources(PKG);
const cm=JSON.parse(realRead(path.join(PKG,'manifest/corpus-manifest.json')));
const authoritative={}; for(const e of cm.fixtures){ authoritative[path.basename(e.path).slice(0,-5)]=e.authoritative; }
const INPUT=['modality','validation_record','artifact','profile_ref','release_ref'];
fs.mkdirSync(path.join(OUT,'blind'),{recursive:true});
const corpusDir=path.join(PKG,'corpus'); const produced={}; const timings={};
for(const fn of fs.readdirSync(corpusDir).sort()){
  const fid=fn.slice(0,-5);
  const obj=JSON.parse(realRead(path.join(corpusDir,fn)));
  const sub={}; for(const k of INPUT) if(k in obj) sub[k]=obj[k];
  BLIND=true; const t0=process.hrtime.bigint();
  const rec=V.evaluate(res,sub);
  const tr=V.trace(sub,rec,false), trr=V.trace(sub,rec,true);
  const dt=Number(process.hrtime.bigint()-t0)/1e6; BLIND=false;
  timings[fid]=dt;
  const out={fixture_id:fid,authoritative:authoritative[fid],assurance_record:rec,trace:tr,redacted_trace:trr};
  fs.writeFileSync(path.join(OUT,'blind',fid+'.json'),JSON.stringify(out,null,1));
  produced[fid]=out;
}
const expReads=OPENED.filter(p=>p.includes('/expected/')||p.includes('/derivations/'));
const proof={fixtures_evaluated:Object.keys(produced).length,expected_or_derivation_reads_during_blind:expReads,
  blind_boundary_intact:expReads.length===0,config_fingerprint_recomputed:got,config_fingerprint_match:got===want};
fs.writeFileSync(path.join(__dirname,'..','clean_room_evidence','blind-boundary-proof.json'),JSON.stringify(proof,null,1));
// access log: unique package paths read
const uniq=[...new Set(OPENED)].map(p=>p.split('tap-e7-base-companion-1.1.1/')[1]||p).sort();
fs.writeFileSync(path.join(__dirname,'..','clean_room_evidence','file-access-log.json'),
  JSON.stringify({package_paths_read:uniq,any_forbidden:uniq.some(p=>p.startsWith('expected/')||p.startsWith('derivations/'))},null,1));
const crypto=require('crypto'); const h=crypto.createHash('sha256');
for(const fn of fs.readdirSync(path.join(OUT,'blind')).sort()) h.update(realRead(path.join(OUT,'blind',fn)));
fs.writeFileSync(path.join(__dirname,'..','clean_room_evidence','blind-output-root.json'),
  JSON.stringify({blind_output_sha256:'sha-256:'+h.digest('hex'),fixtures:Object.keys(produced).length},null,1));
fs.writeFileSync(path.join(OUT,'timings.json'),JSON.stringify(timings,null,1));
console.log('blind: evaluated',Object.keys(produced).length,'| boundary intact:',proof.blind_boundary_intact,'| fingerprint:',got===want);
