'use strict';
// TAP-E7-BASE Independent Implementation B (JavaScript / Node, stdlib only).
// Functional-pipeline architecture, authored from the published v1.1.1 normative resources.
// Consumes only (ValidationRecord, CandidateArtifact, descriptor envelope). Imports nothing
// from Implementation A, the corpus builder, auditors, or expected-result logic.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

// ---- generic utilities (locally implemented) ----
const canon = (o) => stableStringify(o);
function stableStringify(o) {
  if (o === null || typeof o !== 'object') return JSON.stringify(o);
  if (Array.isArray(o)) return '[' + o.map(stableStringify).join(',') + ']';
  const keys = Object.keys(o).sort();
  return '{' + keys.map(k => JSON.stringify(k) + ':' + stableStringify(o[k])).join(',') + '}';
}
const shaTag = (buf) => 'sha-256:' + crypto.createHash('sha256').update(buf).digest('hex');

// ---- frozen taxonomy (transcribed from TAP-E7 §8) ----
const POSITIVE = new Set(['FABRICATION','MEANING_DISTORTION','STATUS_UPGRADE','CERTAINTY_OVERSTATEMENT',
  'SCOPE_EXPANSION','QUALIFICATION_OMISSION','MISLEADING_CONTRADICTION_OMISSION','UNCERTAINTY_SUPPRESSION',
  'PROVENANCE_MISMATCH','CITATION_MISMATCH']);
const LIMITATION = new Set(['CORRESPONDENCE_UNRESOLVED','UNSUPPORTED_MODALITY','INPUT_INTEGRITY_FAILURE','PROCESSING_FAILURE']);
const polarity = (c) => POSITIVE.has(c) ? 'POSITIVE_VIOLATION' : (LIMITATION.has(c) ? 'EVALUATION_LIMITATION' : (() => { throw new Error('unknown ' + c); })());
function aggregateOutcome(cats) { // §8.1
  const p = new Set(cats.map(polarity));
  if (p.has('POSITIVE_VIOLATION')) return 'NOT_ASSURED';
  if (p.has('EVALUATION_LIMITATION')) return 'INDETERMINATE';
  return 'ASSURED';
}
// exact rational Jaccard via bigint-free integer pair compare
const T_ACCEPT = [85, 100], T_REJECT = [35, 100];
const geFrac = (n, d, tn, td) => n * td >= tn * d; // n/d >= tn/td

// ---- resource loader ----
function loadResources(pkg) {
  const read = (rel) => fs.readFileSync(path.join(pkg, rel), 'utf8');
  const confus = {}, invis = {}, fn = {};
  for (const l of read('resources/normalization/unicode-confusables.tsv').split('\n')) {
    if (!l.trim() || l.startsWith('#')) continue; const c = l.split('\t');
    confus[parseInt(c[0].slice(2), 16)] = { skeleton: c[3], suspicious: c[4] === '1' };
  }
  for (const l of read('resources/normalization/invisible-codepoints.tsv').split('\n')) {
    if (!l.trim() || l.startsWith('#')) continue; const c = l.split('\t');
    invis[parseInt(c[0].slice(2), 16)] = { disposition: c[3], suspicious: c[4] === '1' };
  }
  for (const l of read('resources/language/pos-cues.tsv').split('\n')) {
    if (!l.trim() || l.startsWith('#')) continue; const c = l.split('\t'); fn[c[0].trim()] = c[1].trim();
  }
  const irregular = {};
  for (const l of read('resources/normalization/lemmatization-irregular.tsv').split('\n')) {
    if (!l.trim() || l.startsWith('#')) continue; const c = l.trim().split(/\t+/);
    if (c.length >= 2) irregular[c[0].toLowerCase()] = c[1].toLowerCase();
  }
  const engCore = new Set(read('resources/language/eng-core.txt').split('\n').map(s => s.trim()).filter(s => s && !s.startsWith('#')));
  return { confus, invis, fn, irregular, engCore };
}

// ---- strict JSON: independent raw-byte scanner (does not trust JSON.parse for dup keys) ----
function strictJson(buf) {
  if (buf.length >= 3 && buf[0] === 0xEF && buf[1] === 0xBB && buf[2] === 0xBF) return 'INPUT_INTEGRITY_FAILURE';
  let s;
  try { s = new TextDecoder('utf-8', { fatal: true }).decode(buf); }
  catch { return 'INPUT_INTEGRITY_FAILURE'; }
  if (maxDepth(s) > 64) return 'PROCESSING_FAILURE';
  if (/[:\[,]\s*0\d/.test(s)) return 'INPUT_INTEGRITY_FAILURE';         // leading zero
  if (/[:\[,]\s*\+/.test(s)) return 'INPUT_INTEGRITY_FAILURE';          // leading plus
  if (/\bNaN\b/.test(s) || /\bInfinity\b/.test(s)) return 'INPUT_INTEGRITY_FAILURE';
  const sr = surrogates(s); if (sr) return sr;
  const dup = duplicateKeys(s); if (dup) return 'INPUT_INTEGRITY_FAILURE';
  let obj; try { obj = JSON.parse(s); } catch { return 'INPUT_INTEGRITY_FAILURE'; }
  return limits(obj);                                                   // PROCESSING_FAILURE or null
}
function maxDepth(s) { let d = 0, mx = 0, inStr = false, esc = false;
  for (const ch of s) { if (inStr) { if (esc) esc = false; else if (ch === '\\') esc = true; else if (ch === '"') inStr = false; continue; }
    if (ch === '"') inStr = true; else if (ch === '{' || ch === '[') { d++; if (d > mx) mx = d; } else if (ch === '}' || ch === ']') d--; }
  return mx; }
function surrogates(s) { const re = /\\u([0-9a-fA-F]{4})/g; let m;
  while ((m = re.exec(s)) !== null) { const cp = parseInt(m[1], 16);
    if (cp >= 0xD800 && cp <= 0xDBFF) { const nx = s.slice(m.index + 6, m.index + 12); const mm = /^\\u([0-9a-fA-F]{4})/.exec(nx);
      if (!(mm && parseInt(mm[1], 16) >= 0xDC00 && parseInt(mm[1], 16) <= 0xDFFF)) return 'INPUT_INTEGRITY_FAILURE'; }
    else if (cp >= 0xDC00 && cp <= 0xDFFF) { const pr = s.slice(Math.max(0, m.index - 6), m.index); const mm = /\\u([0-9a-fA-F]{4})$/.exec(pr);
      if (!(mm && parseInt(mm[1], 16) >= 0xD800 && parseInt(mm[1], 16) <= 0xDBFF)) return 'INPUT_INTEGRITY_FAILURE'; } }
  return null; }
function duplicateKeys(s) { // scan object literals for repeated keys at each nesting scope
  let i = 0, inStr = false, esc = false; const stack = [];
  const cur = () => stack[stack.length - 1];
  while (i < s.length) { const ch = s[i];
    if (inStr) { if (esc) esc = false; else if (ch === '\\') esc = true; else if (ch === '"') { inStr = false;
        const sc = cur(); if (sc && sc.expectKey) { const key = readString(s, sc.keyStart, i); if (sc.keys.has(key)) return true; sc.keys.add(key); sc.expectKey = false; } }
      i++; continue; }
    if (ch === '"') { inStr = true; const sc = cur(); if (sc && sc.type === 'obj' && sc.wantKey) { sc.expectKey = true; sc.keyStart = i + 1; sc.wantKey = false; } i++; continue; }
    if (ch === '{') { stack.push({ type: 'obj', keys: new Set(), wantKey: true, expectKey: false }); i++; continue; }
    if (ch === '[') { stack.push({ type: 'arr' }); i++; continue; }
    if (ch === '}' || ch === ']') { stack.pop(); i++; continue; }
    if (ch === ',') { const sc = cur(); if (sc && sc.type === 'obj') sc.wantKey = true; i++; continue; }
    i++; }
  return false; }
function readString(s, start, end) { return s.slice(start, end); }
function limits(x) { if (x && typeof x === 'object') { if (!Array.isArray(x)) { if (Object.keys(x).length > 100000) return 'PROCESSING_FAILURE';
      for (const k of Object.keys(x)) { const r = limits(x[k]); if (r) return r; } } else { for (const v of x) { const r = limits(v); if (r) return r; } } }
  else if (typeof x === 'string') { if (x.length > 1048576) return 'PROCESSING_FAILURE'; }
  return null; }

// ---- input reconstruction (recipe support) ----
function reconstruct(part) {
  if ('text' in part) return Buffer.from(part.text, 'utf8');
  if ('raw' in part) return Buffer.from(part.raw, 'utf8');
  const inp = part.input, k = inp.kind;
  if (k === 'raw') return Buffer.from(inp.raw, 'utf8');
  if (k === 'raw_bytes_hex') return Buffer.from(inp.hex, 'hex');
  if (k === 'base64') return Buffer.from(inp.raw_input_base64, 'base64');
  if (k === 'recipe') { const r = inp.recipe;
    if (r.type === 'nested_object') return Buffer.from('{"a":'.repeat(r.depth) + '1' + '}'.repeat(r.depth));
    if (r.type === 'nested_array') return Buffer.from('['.repeat(r.depth) + '1' + ']'.repeat(r.depth));
    if (r.type === 'flat_object') { const parts = []; for (let i = 0; i < r.fields; i++) parts.push(`"f${i}":0`); return Buffer.from('{' + parts.join(',') + '}'); }
    if (r.type === 'string_value') return Buffer.from('{"s":"' + 'a'.repeat(r.length) + '"}'); }
  throw new Error('bad part');
}

// ---- tokenization / lemmatization (content-token set) ----
const FN_CONTENT_EXCLUDE = new Set(['MODAL','NEGATION','DETERMINER','AUXILIARY','PREPOSITION','CONJUNCTION']);
function contentTokens(res, text) {
  const t = text.normalize('NFC').replace(/\[[^\]]*\]/g, ' ');
  const toks = (t.toLowerCase().match(/[\p{L}\p{N}]+/gu) || []);
  const out = new Set();
  for (const tok of toks) { if (FN_CONTENT_EXCLUDE.has(res.fn[tok])) continue; out.add(lemma(res, tok)); }
  return out;
}
function lemma(res, tok) { if (res.irregular[tok]) return res.irregular[tok];
  const rules = [['ies', 'y'], ['sses', 'ss'], ['ing', ''], ['ed', ''], ['s', '']];
  for (const [suf, rep] of rules) { if (tok.endsWith(suf) && tok.length - suf.length >= 3) return tok.slice(0, tok.length - suf.length) + rep; }
  return tok; }
function entryTokens(res, e) { return contentTokens(res, [e.subject, e.predicate, e.object].map(x => String(x || '')).join(' ')); }
function jaccard(a, b) { let inter = 0; for (const x of a) if (b.has(x)) inter++; const uni = a.size + b.size - inter; return [inter, uni || 1, uni === 0]; }

// ---- unicode ----
function rejectCodepoint(res, text) { for (const ch of text) { const iv = res.invis[ch.codePointAt(0)]; if (iv && iv.disposition === 'reject') return true; } return false; }
function suspiciousUnicode(res, text) { for (const ch of text) { const cp = ch.codePointAt(0);
  const cf = res.confus[cp]; if (cf && cf.suspicious) return true;
  const iv = res.invis[cp]; if (iv && iv.disposition === 'strip-and-flag' && iv.suspicious) return true; } return false; }

// ---- BASE-MD unsupported / malformed ----
function mdUnsupported(text) {
  if (/<!--/.test(text)) return true;
  if (/<\/?[a-zA-Z][^>]*>/.test(text)) return true;
  if (/^\s*\[[^\]]*\]:\s*$/m.test(text)) return true;
  return false;
}

// ---- segmentation + assertion identification ----
const INSTRUCTION_LEADS = new Set(['ignore','disregard','mark','delete','system','note','review','click','run','execute','print','output']);
function assertiveSentences(res, text, vrEntityTokens) {
  const noCode = text.replace(/```[\s\S]*?```/g, ' ');
  const out = [];
  for (const line of noCode.split('\n')) {
    if (/^\s*#{1,6}\s+/.test(line)) continue;                 // heading fragment
    for (const sent of line.split(/(?<=[.?!])\s+/)) {
      const s = sent.trim(); if (!s) continue;
      if (s.endsWith('?')) continue;                          // interrogative
      const first = (s.toLowerCase().match(/[a-z0-9]+/g) || [])[0];
      const toks = contentTokens(res, s);
      let shares = false; for (const x of toks) if (vrEntityTokens.has(x)) { shares = true; break; }
      if (first && INSTRUCTION_LEADS.has(first) && !shares) continue; // imperative/instruction
      out.push(s);
    }
  }
  return out;
}

// ---- fidelity (structural) ----
function fidelity(entry, meta) {
  const status = entry.status || 'SUPPORTED';
  if (status === 'CONTRADICTED') return 'STATUS_UPGRADE';
  if (status === 'UNKNOWN') return 'UNCERTAINTY_SUPPRESSION';
  if ('counter_evidence' in entry) return 'MISLEADING_CONTRADICTION_OMISSION';
  if ('provenance_ids' in entry && meta.attributed_source && !entry.provenance_ids.includes(meta.attributed_source)) return 'PROVENANCE_MISMATCH';
  if ('citation_ids' in entry && meta.citation && !entry.citation_ids.includes(meta.citation)) return 'CITATION_MISMATCH';
  return null;
}

// ---- correspondence for one text proposition ----
function correspondText(res, prop, entries, meta) {
  const at = contentTokens(res, prop);
  for (const e of entries) { // exact normalized
    const et = entryTokens(res, e);
    if (at.size && setsEqual(at, et)) return { kind: 'evaluated', method: 'exact', finding: fidelity(e, meta), entry: e.entry_id };
  }
  let best = null, bi = -1, bu = 1;
  for (const e of entries) { const [i, u] = jaccard(at, entryTokens(res, e)); if (i * bu > bi * u) { bi = i; bu = u; best = e; } }
  if (best && geFrac(bi, bu, T_ACCEPT[0], T_ACCEPT[1])) return { kind: 'evaluated', method: 'lexical', finding: fidelity(best, meta), entry: best.entry_id };
  if (best && geFrac(bi, bu, T_REJECT[0], T_REJECT[1])) return { kind: 'unresolved' };
  return { kind: 'fabrication' };
}
function setsEqual(a, b) { if (a.size !== b.size) return false; for (const x of a) if (!b.has(x)) return false; return true; }

// ---- JSON assertion ----
function correspondJson(res, obj, entries, findings) {
  if (!obj || typeof obj !== 'object' || Array.isArray(obj) ||
      !(('statement' in obj) || ('subject' in obj) || ('validation_entry_id' in obj))) return [];
  const meta = { attributed_source: obj.attributed_source, citation: obj.citation };
  if ('validation_entry_id' in obj) {
    const vid = obj.validation_entry_id;
    if (Array.isArray(vid) || typeof vid !== 'string' || vid === '') { findings.push('INPUT_INTEGRITY_FAILURE'); return []; }
    const entry = entries.find(e => e.entry_id === vid);
    if (!entry) { findings.push('INPUT_INTEGRITY_FAILURE'); return []; }
    const prop = obj.statement || [obj.subject, obj.predicate, obj.object].map(x => String(x || '')).join(' ');
    const [i, u] = jaccard(contentTokens(res, prop), entryTokens(res, entry));
    if (!geFrac(i, u, T_REJECT[0], T_REJECT[1])) { findings.push('INPUT_INTEGRITY_FAILURE'); return []; }
    return [{ kind: 'evaluated', method: 'explicit', finding: fidelity(entry, meta), entry: entry.entry_id }];
  }
  if ('subject' in obj && 'predicate' in obj && 'object' in obj) {
    for (const e of entries) if (['subject','predicate','object'].every(k => String(obj[k]).toLowerCase() === String(e[k] || '').toLowerCase()))
      return [{ kind: 'evaluated', method: 'structured', finding: fidelity(e, meta), entry: e.entry_id }];
  }
  return [correspondText(res, obj.statement || '', entries, meta)];
}

// ---- assemble AssuranceRecord ----
function assemble(units, extra) {
  const findings = []; let ev = 0, un = 0, corr = 0;
  const mc = { explicit: 0, exact: 0, structured: 0, lexical: 0 }, add = { unresolved: 0, no_match: 0 };
  for (const u of units) {
    if (u.kind === 'evaluated') { ev++; corr++; mc[u.method]++; if (u.finding) findings.push({ finding_index: findings.length, category: u.finding, polarity: polarity(u.finding), validation_ref: u.entry }); }
    else if (u.kind === 'unresolved') { un++; corr++; add.unresolved++; findings.push({ finding_index: findings.length, category: 'CORRESPONDENCE_UNRESOLVED', polarity: 'EVALUATION_LIMITATION' }); }
    else if (u.kind === 'fabrication') { un++; corr++; add.no_match++; findings.push({ finding_index: findings.length, category: 'FABRICATION', polarity: 'POSITIVE_VIOLATION' }); }
  }
  for (const c of extra) findings.push({ finding_index: findings.length, category: c, polarity: polarity(c) });
  const cats = findings.map(f => f.category);
  const outcome = aggregateOutcome(cats);
  const es = { total_assertive: units.length, evaluated_assertive: ev, unevaluated_assertive: un,
    positive_violations: cats.filter(c => polarity(c) === 'POSITIVE_VIOLATION').length,
    evaluation_limitations: cats.filter(c => polarity(c) === 'EVALUATION_LIMITATION').length,
    'x-tap-e7-base-evaluation-summary': { correspondence_units_total: corr, correspondence_method_counts: mc, companion_method_counts: add } };
  const pi = { outcome, findings: findings.map(f => ({ category: f.category, polarity: f.polarity })),
    evaluation_summary: { total_assertive: es.total_assertive, evaluated_assertive: es.evaluated_assertive,
      unevaluated_assertive: es.unevaluated_assertive, positive_violations: es.positive_violations, evaluation_limitations: es.evaluation_limitations } };
  return { outcome, findings, evaluation_summary: es, projection_pi: pi, projection_pi_sha256: shaTag(Buffer.from(canon(pi) + '\n', 'utf8')) };
}

// ---- main ----
function evaluate(res, submission) {
  const vr = submission.validation_record || {}; const entries = vr.entries || [];
  const pr = submission.profile_ref || {};
  if (!pr || pr.profile_id !== 'tap-e7-base' || String(pr.profile_version || '').split('.')[0] !== '1' ||
      submission.release_ref !== 'tap-e7-base-companion/1.1.0') return assemble([], ['INPUT_INTEGRITY_FAILURE']);
  const mod = submission.modality;
  if (mod !== 'text' && mod !== 'json') return assemble([], ['UNSUPPORTED_MODALITY']);
  const parts = (submission.artifact && submission.artifact.parts) || [];
  if (mod === 'json') {
    if (!parts.length) return assemble([], []);
    const raw = reconstruct(parts[0]); const f = strictJson(raw);
    if (f) return assemble([], [f]);
    const obj = JSON.parse(raw.toString('utf8'));
    const extra = []; const units = correspondJson(res, obj, entries, extra);
    return assemble(units, extra);
  }
  const raw = reconstruct(parts[0]); const text = raw.toString('utf8');
  if (rejectCodepoint(res, text)) return assemble([], ['INPUT_INTEGRITY_FAILURE']);
  if (mdUnsupported(text)) return assemble([], ['PROCESSING_FAILURE']);
  const suspicious = suspiciousUnicode(res, text);
  const vrEnt = new Set(); for (const e of entries) for (const x of contentTokens(res, String(e.subject || ''))) vrEnt.add(x);
  const units = [];
  for (const sent of assertiveSentences(res, text, vrEnt)) {
    if (suspicious) { units.push({ kind: 'unresolved' }); }
    else { const m = /\[([^\]]+)\]/.exec(sent); const meta = m ? { citation: m[1] } : {}; units.push(correspondText(res, sent, entries, meta)); }
  }
  return assemble(units, []);
}
function trace(submission, record, redacted) {
  const parts = (submission.artifact && submission.artifact.parts) || [];
  const raw = parts.length ? reconstruct(parts[0]) : Buffer.alloc(0);
  const node = { outcome: record.outcome, findings: record.findings.map(f => f.category),
    artifact_ptr: '/artifact/parts/0', artifact_sha256: shaTag(raw) };
  if (!redacted) { try { node.artifact_text = raw.toString('utf8'); } catch { node.artifact_text = '<binary>'; } }
  return node;
}
module.exports = { loadResources, evaluate, trace, strictJson, contentTokens, jaccard, lemma, aggregateOutcome, polarity, canon, shaTag, reconstruct, geFrac };
