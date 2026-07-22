'use strict';
const fs = require('fs'), path = require('path'), crypto = require('crypto');
function canon(o){ if(o===null||typeof o!=='object')return JSON.stringify(o);
  if(Array.isArray(o))return '['+o.map(canon).join(',')+']';
  return '{'+Object.keys(o).sort().map(k=>JSON.stringify(k)+':'+canon(o[k])).join(',')+'}'; }
const sha=(b)=>'sha-256:'+crypto.createHash('sha256').update(b).digest('hex');
function recompute(pkg){
  const rel=JSON.parse(fs.readFileSync(path.join(pkg,'manifest/release-manifest.json')));
  const rm=JSON.parse(fs.readFileSync(path.join(pkg,'manifest/resource-manifest.json')));
  const runtime=rm.resources.filter(e=>e.outcome_affecting);
  const obj={target_spec:rel.target_specification,target_profile:rel.target_profile,
    canonicalization:rel.canonicalization,thresholds:{T_accept:0.85,T_reject:0.35},
    runtime_resources:runtime.map(e=>({path:e.path,sha256:e.sha256}))};
  return [sha(Buffer.from(canon(obj)+'\n','utf8')), rel.roots.config_fingerprint, runtime];
}
module.exports={recompute,canon,sha};
if(require.main===module){ const [g,w,rt]=recompute(process.argv[2]);
  console.log('recomputed:',g); console.log('package   :',w);
  console.log('runtime_resources:',rt.length,'| corpus excluded:',!rt.some(e=>e.path.startsWith('corpus/')));
  console.log(g===w?'MATCH':'MISMATCH'); process.exit(g===w?0:2); }
