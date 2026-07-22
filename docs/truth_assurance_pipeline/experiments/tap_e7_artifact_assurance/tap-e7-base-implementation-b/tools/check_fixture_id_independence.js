'use strict';
// Anti-cheating: scan runtime src for any corpus fixture-ID string or expected-outcome constant.
const fs=require('fs'), path=require('path');
const SRC=path.join(__dirname,'..','src');
const ids=/\b(LX|CR|JS|UC|EM|PV|SV|MD|DT|PR|SEC|ZR|INF)\d{2}[a-z]?\b/g;
const hits=[];
for(const fn of fs.readdirSync(SRC)){ const t=fs.readFileSync(path.join(SRC,fn),'utf8');
  const m=t.match(ids); if(m) hits.push({file:fn,matches:[...new Set(m)]}); }
const out={runtime_source_scanned:fs.readdirSync(SRC),fixture_id_strings_in_runtime_src:hits,
  permitted:0,pass:hits.length===0};
fs.writeFileSync(path.join(__dirname,'..','results','fixture-id-independence.json'),JSON.stringify(out,null,1));
console.log('fixture-id independence:',hits.length===0?'PASS (0 in runtime src)':'FAIL',JSON.stringify(hits));
process.exit(hits.length===0?0:1);
