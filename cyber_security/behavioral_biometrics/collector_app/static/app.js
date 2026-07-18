// Local browser collector controller. Captures in-app keyboard/pointer/context
// telemetry ONLY (page-scoped listeners; no global OS monitoring). Raw typed
// characters are never read, stored, or transmitted — only key CLASS + timing.
(function () {
  "use strict";
  var qs = function (s) { return document.querySelector(s); };
  var params = new URLSearchParams(location.search);
  // origin defaults to DEMO_ONLY; a real pilot launches with ?origin=real.
  var ORIGIN = params.get("origin") === "real" ? "REAL_PARTICIPANT" : "DEMO_ONLY";
  var SALT = "session-" + (crypto.randomUUID ? crypto.randomUUID() : Date.now());

  var state = { consent: null, participant: "", role: "verification", taskId: null,
    events: [], recording: false, region: "", sessionId: null, startWall: null };

  qs("#origin-badge").textContent = "origin: " + ORIGIN;

  function deviceId() {
    var k = "bbio_device_instance";
    var v = localStorage.getItem(k);
    if (!v) { v = "devinst_" + (crypto.randomUUID ? crypto.randomUUID().slice(0, 12) : String(Date.now())); localStorage.setItem(k, v); }
    return v;
  }
  function deviceClass() {
    var w = Math.max(screen.width, screen.height);
    if ("ontouchstart" in window && w < 900) return "phone";
    if ("ontouchstart" in window) return "tablet";
    return w > 1600 ? "desktop" : "laptop";
  }
  function browserFamily() {
    var ua = navigator.userAgent;
    if (/Firefox/.test(ua)) return "firefox";
    if (/Edg/.test(ua)) return "edge";
    if (/Chrome/.test(ua)) return "chrome";
    if (/Safari/.test(ua)) return "safari";
    return "other";
  }

  // ---------- consent ----------
  fetch("/api/consent-summary").then(function (r) { return r.json(); }).then(function (d) {
    qs("#consent-summary").innerHTML = d.html;
  }).catch(function () { qs("#consent-summary").textContent = "Consent summary unavailable."; });

  qs("#consent-checkbox").addEventListener("change", function (e) {
    qs("#btn-consent").disabled = !e.target.checked;
  });
  qs("#btn-decline").addEventListener("click", function () {
    document.body.innerHTML = "<main><h1>Thank you</h1><p>No data was collected.</p></main>";
  });
  qs("#btn-consent").addEventListener("click", function () {
    state.consent = { granted: true, purpose: "instrumentation_pilot", revoked: false,
      collected_at: new Date().toISOString(), origin: ORIGIN };
    show("setup");
    var taskSel = qs("#task");
    TASKS.forEach(function (t) { var o = document.createElement("option"); o.value = t.id; o.textContent = t.title; taskSel.appendChild(o); });
    qs("#device-meta").textContent = "device-instance: " + deviceId() + " · class: " + deviceClass() + " · browser: " + browserFamily();
    if (params.get("participant")) qs("#participant").value = params.get("participant");
  });

  // ---------- calibration ----------
  qs("#btn-calibrate").addEventListener("click", function () {
    state.participant = qs("#participant").value.trim() || ("p_" + deviceId().slice(-4));
    state.role = qs("#role").value;
    state.taskId = qs("#task").value;
    var buf = [], t0 = performance.now();
    function onk(e) { buf.push("k"); }
    function onp(e) { buf.push("p"); }
    document.addEventListener("keydown", onk);
    document.addEventListener("pointermove", onp);
    qs("#calibration-result").textContent = "Move the mouse and press a few keys… (3s)";
    setTimeout(function () {
      document.removeEventListener("keydown", onk);
      document.removeEventListener("pointermove", onp);
      var ptr = buf.filter(function (x) { return x === "p"; }).length;
      var key = buf.filter(function (x) { return x === "k"; }).length;
      var ok = ptr >= 20;
      qs("#calibration-result").innerHTML = ok ?
        ("<b>Calibration OK</b> — pointer samples: " + ptr + ", key events: " + key + ". Starting task…") :
        ("<b>Calibration weak</b> — only " + ptr + " pointer samples. Try again.");
      if (ok) setTimeout(startTask, 600);
    }, 3000);
  });

  // ---------- telemetry ----------
  function push(ev) { if (state.recording) state.events.push(ev); }
  function now() { return performance.now(); }
  function norm(clientX, clientY, rect) {
    return { x: Math.min(1, Math.max(0, (clientX - rect.left) / Math.max(1, rect.width))),
             y: Math.min(1, Math.max(0, (clientY - rect.top) / Math.max(1, rect.height))) };
  }
  function isSensitive(target) {
    return target && (target.type === "password" || target.getAttribute("data-sensitive") === "true");
  }
  function regionOf(target) {
    return (target && target.getAttribute && target.getAttribute("data-region")) || state.region || "";
  }

  var area = qs("#task-area"), lastPtr = null;
  function onKeyDown(e) { keyEvent(e, "keydown"); }
  function onKeyUp(e) { keyEvent(e, "keyup"); }
  function keyEvent(e, kind) {
    if (isSensitive(e.target)) {  // never record class/id in sensitive fields
      push({ kind: kind, ts_source: e.timeStamp, ts_recv: now(), key_class: "other",
             region: "SUPPRESSED", task_stage: state.region, active_region: "SUPPRESSED" });
      return;
    }
    var kc = KeyClass.keyToClass(e.key);
    push({ kind: kind, ts_source: e.timeStamp, ts_recv: now(), key_class: kc,
           key_id: KeyClass.safeKeyId(e.key, SALT), repeat: !!e.repeat,
           modifiers: [e.ctrlKey && "ctrl", e.altKey && "alt", e.shiftKey && "shift", e.metaKey && "meta"].filter(Boolean),
           region: regionOf(e.target), task_stage: state.region, active_region: regionOf(e.target) });
    // e.key is used ONLY for the class/id above; it is never stored or sent.
  }
  function onPointerMove(e) {
    var rect = area.getBoundingClientRect();
    var evs = (e.getCoalescedEvents ? e.getCoalescedEvents() : null) || [e];
    for (var i = 0; i < evs.length; i++) {
      var ce = evs[i], p = norm(ce.clientX, ce.clientY, rect);
      var dt = lastPtr ? (ce.timeStamp - lastPtr) : null;
      push({ kind: "pointermove", ts_source: ce.timeStamp, ts_recv: now(), x: p.x, y: p.y,
             sampling_interval: dt != null ? dt / 1000 : null, task_stage: state.region });
      lastPtr = ce.timeStamp;
    }
  }
  function onPointerDown(e) { var rect = area.getBoundingClientRect(), p = norm(e.clientX, e.clientY, rect);
    push({ kind: "pointerdown", ts_source: e.timeStamp, ts_recv: now(), x: p.x, y: p.y,
           button: String(e.button), target: (e.target && e.target.getAttribute("data-target")) || "", task_stage: state.region }); }
  function onPointerUp(e) { var rect = area.getBoundingClientRect(), p = norm(e.clientX, e.clientY, rect);
    push({ kind: "pointerup", ts_source: e.timeStamp, ts_recv: now(), x: p.x, y: p.y,
           button: String(e.button), task_stage: state.region }); }
  function onScroll(e) { push({ kind: "scroll", ts_source: e.timeStamp || now(), ts_recv: now(),
           scroll_dy: (e.target && e.target.scrollTop) || 0, task_stage: state.region }); }
  function onVisibility() { push({ kind: "visibility", ts_source: now(), ts_recv: now(),
           context_transition: true, detail: document.visibilityState, task_stage: state.region }); }
  function onBlur() { push({ kind: "blur", ts_source: now(), ts_recv: now(), context_transition: true, task_stage: state.region }); }
  function onFocus() { push({ kind: "focus", ts_source: now(), ts_recv: now(), context_transition: true, task_stage: state.region }); }
  function onResize() { push({ kind: "resize", ts_source: now(), ts_recv: now(), context_transition: true, task_stage: state.region }); }

  function attachListeners() {
    document.addEventListener("keydown", onKeyDown, true);
    document.addEventListener("keyup", onKeyUp, true);
    area.addEventListener("pointermove", onPointerMove, true);
    area.addEventListener("pointerdown", onPointerDown, true);
    area.addEventListener("pointerup", onPointerUp, true);
    area.addEventListener("scroll", onScroll, true);
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("blur", onBlur);
    window.addEventListener("focus", onFocus);
    window.addEventListener("resize", onResize);
  }
  function detachListeners() {
    document.removeEventListener("keydown", onKeyDown, true);
    document.removeEventListener("keyup", onKeyUp, true);
    area.removeEventListener("pointermove", onPointerMove, true);
    area.removeEventListener("pointerdown", onPointerDown, true);
    area.removeEventListener("pointerup", onPointerUp, true);
    area.removeEventListener("scroll", onScroll, true);
    document.removeEventListener("visibilitychange", onVisibility);
    window.removeEventListener("blur", onBlur);
    window.removeEventListener("focus", onFocus);
    window.removeEventListener("resize", onResize);
  }

  // ---------- task orchestration ----------
  var ctx = {
    stage: function (name, extra) { state.region = name;
      var ev = { kind: "stage", ts_source: now(), ts_recv: now(), task_stage: name };
      if (extra) for (var k in extra) ev[k] = extra[k];
      push(ev); qs("#stage-label").textContent = "stage: " + name; },
    finish: function (success) { finishTask(success); }
  };

  function startTask() {
    var task = TASKS.filter(function (t) { return t.id === state.taskId; })[0];
    qs("#task-title").textContent = task.title;
    area.innerHTML = "";
    state.events = []; state.recording = true; lastPtr = null;
    state.sessionId = state.participant + "_" + state.taskId + "_" + (crypto.randomUUID ? crypto.randomUUID().slice(0, 8) : Date.now());
    state.startWall = new Date().toISOString();
    qs("#rec-indicator").classList.remove("hidden");
    attachListeners();
    show("task");
    task.build(area, ctx);
  }

  qs("#btn-finish").addEventListener("click", function () { finishTask(false); });

  function finishTask(success) {
    if (!state.recording) return;
    state.recording = false;
    detachListeners();
    qs("#rec-indicator").classList.add("hidden");
    var payload = {
      session_meta: {
        participant_pseudonym: state.participant, session_id: state.sessionId,
        task_id: state.taskId, trial_id: state.sessionId, device_id: deviceId(),
        device_class: deviceClass(), os: navigator.platform || "unknown",
        role: state.role, condition: "genuine", data_origin: ORIGIN,
        session_start: state.startWall, session_end: new Date().toISOString(),
        consent: state.consent, timing_api: "PointerEvent+getCoalescedEvents;performance.now",
        browser: browserFamily(), notes: (ORIGIN === "DEMO_ONLY" ? "DEMO_ONLY" : "")
      },
      events: state.events, dropped: 0
    };
    qs("#status").textContent = "submitting…";
    fetch("/api/session", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload) })
      .then(function (r) { return r.json(); })
      .then(showDone)
      .catch(function (err) { qs("#status").textContent = "submit failed: " + err; });
  }

  function showDone(res) {
    show("done");
    qs("#status").textContent = "";
    qs("#done-message").textContent = res.completion_message || "Session complete. Thank you.";
    qs("#quality-summary").textContent = JSON.stringify({
      instrumentation_verdict: res.instrumentation_verdict, n_events: res.n_events,
      quarantined: res.quarantined, quality_reasons: res.quality_reasons,
      raw_content_leaks: res.raw_content_leaks
    }, null, 2);
    state.lastResult = res;
  }

  qs("#btn-delete").addEventListener("click", function () {
    var res = state.lastResult; if (!res) return;
    fetch("/api/delete", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ participant: res.participant, session_id: res.session_id }) })
      .then(function (r) { return r.json(); })
      .then(function (d) { qs("#done-message").textContent = d.deleted ? "This session's data has been deleted." : "Delete failed."; });
  });
  qs("#btn-again").addEventListener("click", function () { show("setup"); });

  // ---------- screen switching ----------
  function show(name) {
    ["consent", "setup", "task", "done"].forEach(function (s) {
      qs("#screen-" + s).classList.toggle("hidden", s !== name);
    });
  }

  // Content-free debug hook (counts + booleans only; NO raw content) for automated
  // browser E2E and manual acceptance checks. Never exposes key content.
  window.__bbio = {
    count: function () { return state.events.length; },
    recording: function () { return state.recording; },
    hasRawContent: function () {
      return state.events.some(function (e) {
        return ("char" in e) || ("text" in e) || ("key" in e) || ("value" in e);
      });
    },
    modalities: function () {
      var m = {}; state.events.forEach(function (e) { m[e.kind] = (m[e.kind] || 0) + 1; }); return m;
    },
    lastResult: function () { return state.lastResult || null; }
  };
})();
