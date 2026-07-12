// Real-browser end-to-end driver via the Chrome DevTools Protocol (no npm deps;
// uses node's global WebSocket + fetch). Launches headless Chromium, drives the
// actual collector page with REAL keyboard/pointer events, and verifies that
// privacy-safe telemetry is captured (with NO raw content) and a session is stored.
//
// Usage: node browser_e2e.js <baseUrl> <chromePath>
// Emits a single JSON line to stdout and exits 0 on success, non-zero on failure.

const { spawn } = require("child_process");
const os = require("os");
const fs = require("fs");
const path = require("path");

const BASE = process.argv[2] || "http://127.0.0.1:8794";
const CHROME = process.argv[3] || process.env.BBIO_CHROME;

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function main() {
  const userDir = fs.mkdtempSync(path.join(os.tmpdir(), "bbio-cr-"));
  const proc = spawn(CHROME, ["--headless=new", "--no-sandbox", "--disable-gpu",
    "--remote-debugging-port=0", "--user-data-dir=" + userDir, "about:blank"],
    { stdio: ["ignore", "ignore", "pipe"] });

  const wsUrl = await new Promise((resolve, reject) => {
    let buf = "";
    const to = setTimeout(() => reject(new Error("no devtools ws")), 15000);
    proc.stderr.on("data", d => {
      buf += d.toString();
      const m = buf.match(/DevTools listening on (ws:\/\/\S+)/);
      if (m) { clearTimeout(to); resolve(m[1]); }
    });
  });

  const cdp = await connect(wsUrl);
  let sessionId;
  try {
    const { targetId } = await cdp.send("Target.createTarget", { url: "about:blank" });
    const att = await cdp.send("Target.attachToTarget", { targetId, flatten: true });
    sessionId = att.sessionId;
    await cdp.send("Page.enable", {}, sessionId);
    await cdp.send("Runtime.enable", {}, sessionId);
    await cdp.send("Input.enable", {}, sessionId).catch(() => {});
    await cdp.send("Page.navigate", { url: BASE + "/?origin=demo&participant=e2e_p" }, sessionId);
    await sleep(800);

    // consent
    await evalIn(cdp, sessionId,
      "document.querySelector('#consent-checkbox').checked=true;" +
      "document.querySelector('#btn-consent').disabled=false;" +
      "document.querySelector('#btn-consent').click(); 'ok'");
    await sleep(200);
    // setup: participant + task, then calibrate
    await evalIn(cdp, sessionId,
      "document.querySelector('#participant').value='e2e_p';" +
      "document.querySelector('#task').value='mixed_workflow';" +
      "document.querySelector('#btn-calibrate').click(); 'ok'");

    // feed real pointer moves during the 3s calibration window
    for (let i = 0; i < 40; i++) {
      await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved",
        x: 200 + (i % 20) * 8, y: 250 + (i % 10) * 6 }, sessionId);
      await sleep(70);
    }
    await sleep(1200); // calibration completes (3s) + auto-start (600ms)

    // task is running: dispatch REAL key + pointer events
    const recording = await evalIn(cdp, sessionId, "window.__bbio && window.__bbio.recording()");
    for (let i = 0; i < 30; i++) {
      const ch = "abcdefghij"[i % 10];
      await cdp.send("Input.dispatchKeyEvent", { type: "keyDown", key: ch, text: ch }, sessionId);
      await sleep(15);
      await cdp.send("Input.dispatchKeyEvent", { type: "keyUp", key: ch }, sessionId);
      await cdp.send("Input.dispatchMouseEvent", { type: "mouseMoved",
        x: 150 + i * 5, y: 200 + (i % 7) * 9 }, sessionId);
      await sleep(20);
    }

    const count = await evalIn(cdp, sessionId, "window.__bbio.count()");
    const hasRaw = await evalIn(cdp, sessionId, "window.__bbio.hasRawContent()");
    const modalities = await evalIn(cdp, sessionId, "JSON.stringify(window.__bbio.modalities())");

    // finish -> POST -> stored
    await evalIn(cdp, sessionId, "document.querySelector('#btn-finish').click(); 'ok'");
    await sleep(1200);
    const result = await evalIn(cdp, sessionId,
      "JSON.stringify(window.__bbio.lastResult()||{})");

    const parsed = JSON.parse(result || "{}");
    const ok = count > 20 && hasRaw === false && parsed && parsed.ok === true
      && (parsed.raw_content_leaks || []).length === 0;
    console.log(JSON.stringify({ ok, recording, captured_events: count,
      has_raw_content: hasRaw, modalities: JSON.parse(modalities || "{}"),
      server_result: { ok: parsed.ok, verdict: parsed.instrumentation_verdict,
        session_id: parsed.session_id, leaks: parsed.raw_content_leaks } }));
    proc.kill(); process.exit(ok ? 0 : 2);
  } catch (e) {
    console.log(JSON.stringify({ ok: false, error: String(e) }));
    proc.kill(); process.exit(3);
  }
}

async function evalIn(cdp, sessionId, expr) {
  const r = await cdp.send("Runtime.evaluate",
    { expression: expr, returnByValue: true, awaitPromise: true }, sessionId);
  return r && r.result ? r.result.value : undefined;
}

function connect(wsUrl) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    let id = 0;
    const pending = new Map();
    ws.addEventListener("open", () => resolve({
      send(method, params, sessionId) {
        return new Promise((res, rej) => {
          const mid = ++id;
          pending.set(mid, { res, rej });
          const msg = { id: mid, method, params: params || {} };
          if (sessionId) msg.sessionId = sessionId;
          ws.send(JSON.stringify(msg));
          setTimeout(() => { if (pending.has(mid)) { pending.delete(mid); rej(new Error("timeout " + method)); } }, 10000);
        });
      }
    }));
    ws.addEventListener("message", ev => {
      const m = JSON.parse(ev.data);
      if (m.id && pending.has(m.id)) {
        const p = pending.get(m.id); pending.delete(m.id);
        if (m.error) p.rej(new Error(m.error.message)); else p.res(m.result);
      }
    });
    ws.addEventListener("error", e => reject(new Error("ws error")));
  });
}

main();
