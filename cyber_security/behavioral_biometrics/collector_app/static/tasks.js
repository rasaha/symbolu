// Controlled tasks (interactive). Each task renders neutral content into #task-area
// and emits stage/context markers via ctx. Telemetry (keyboard/pointer) is captured
// globally by app.js on the task area; tasks NEVER read typed text — only structure.
(function (root) {
  var NEUTRAL_COPY = "the quick brown fox jumps over the lazy dog while five wizards vex";
  var NEUTRAL_PROMPT = "In two or three neutral sentences, describe a walk in a park. " +
    "Do not include names, passwords, or anything private.";

  function el(tag, cls, txt) { var e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }

  function textTask(area, ctx, prompt, stages) {
    ctx.stage(stages[0], { active_region: "prompt" });
    area.appendChild(el("p", "prompt", prompt));
    var ta = el("textarea", "entry"); ta.setAttribute("data-region", "entry");
    ta.setAttribute("aria-label", "neutral entry"); ta.rows = 4; area.appendChild(ta);
    ta.addEventListener("focus", function () { ctx.stage(stages[1], { active_region: "entry", expected_interaction: "keyboard" }); });
    var done = el("button", "", "Submit"); area.appendChild(done);
    done.addEventListener("click", function () { ctx.stage(stages[2], { active_region: "submit" }); ctx.finish(true); });
    setTimeout(function () { ta.focus(); }, 30);
  }

  function targetTask(area, ctx, nTargets, drag) {
    ctx.stage("ready", { active_region: "arena" });
    var arena = el("div", "arena"); area.appendChild(arena);
    var i = 0;
    function place() {
      arena.innerHTML = "";
      if (i >= nTargets) { ctx.stage("confirm"); ctx.finish(true); return; }
      ctx.stage(drag ? "drag" : "acquire", { active_region: "target_" + i, expected_interaction: "pointer" });
      var t = el("div", "target", drag ? "drag me" : "click");
      t.style.left = (10 + Math.floor(Math.random() * 70)) + "%";
      t.style.top = (10 + Math.floor(Math.random() * 60)) + "%";
      t.setAttribute("data-target", "target_" + i);
      if (drag) {
        var slot = el("div", "slot", "drop here"); slot.style.right = "8%"; slot.style.bottom = "12%";
        arena.appendChild(slot); t.draggable = true;
        t.addEventListener("dragend", function () { ctx.stage("drop", { active_region: "slot_" + i }); i++; place(); });
      } else {
        t.addEventListener("click", function () { i++; place(); });
      }
      arena.appendChild(t);
    }
    place();
  }

  function scrollTask(area, ctx) {
    ctx.stage("ready", { active_region: "list" });
    var box = el("div", "scrollbox"); area.appendChild(box);
    var target = 24;
    for (var k = 0; k < 40; k++) {
      var row = el("div", "row-item", "item " + k + (k === target ? "  ← select this" : ""));
      row.setAttribute("data-target", "item_" + k);
      if (k === target) { row.classList.add("goal"); row.addEventListener("click", function () { ctx.stage("select"); ctx.finish(true); }); }
      box.appendChild(row);
    }
    box.addEventListener("scroll", function () { ctx.stage("scroll", { active_region: "list" }); });
  }

  function mixedTask(area, ctx, rounds) {
    ctx.stage("warmup", { active_region: "form" });
    var round = 0;
    function step() {
      area.innerHTML = "";
      if (round >= rounds) { ctx.stage("review"); ctx.finish(true); return; }
      ctx.stage("type", { active_region: "field_" + round, expected_interaction: "keyboard" });
      area.appendChild(el("p", "prompt", "Field " + (round + 1) + " of " + rounds + ": type a few neutral words, then click Next."));
      var ta = el("input", "entry"); ta.setAttribute("data-region", "field_" + round); area.appendChild(ta);
      var next = el("button", "", "Next"); area.appendChild(next);
      next.addEventListener("click", function () { ctx.stage("point", { active_region: "next_" + round, expected_interaction: "pointer" }); round++; step(); });
      setTimeout(function () { ta.focus(); }, 20);
    }
    step();
  }

  var TASKS = [
    { id: "fixed_copy", title: "Fixed-copy typing", build: function (a, c) { a.appendChild(el("p", "copy", NEUTRAL_COPY)); textTask(a, c, "Type the sentence above, then Submit.", ["warmup", "type", "review"]); } },
    { id: "free_response", title: "Free-response typing", build: function (a, c) { textTask(a, c, NEUTRAL_PROMPT, ["prompt", "type", "submit"]); } },
    { id: "point_click", title: "Point-and-click", build: function (a, c) { targetTask(a, c, 6, false); } },
    { id: "drag_drop", title: "Drag-and-drop", build: function (a, c) { targetTask(a, c, 4, true); } },
    { id: "scroll_select", title: "Scroll-and-select", build: function (a, c) { scrollTask(a, c); } },
    { id: "mixed_workflow", title: "Mixed keyboard + pointer", build: function (a, c) { mixedTask(a, c, 4); } },
    { id: "repeat_workflow", title: "Repeated identical workflow", build: function (a, c) { mixedTask(a, c, 4); } }
  ];

  root.TASKS = TASKS;
  if (typeof module !== "undefined" && module.exports) module.exports = { TASKS: TASKS };
})(typeof window !== "undefined" ? window : globalThis);
