/* repo-explainer — deterministic UI assertions for the test-docsite skill.
   Injected into a served docsite page via the browser's JS console/tool.
   Every check returns {id, pass, detail}; async checks return a Promise.
   Checks restore any UI state they change (panel, deep mode, scroll). */
(function () {
  var R = {};

  // Transitions and rAF are paused in hidden tabs and mid-flight transitions make
  // geometry sampling racy, so freeze all chrome motion for the duration of the tests.
  if (!document.getElementById("__reTestStyle")) {
    var st = document.createElement("style");
    st.id = "__reTestStyle";
    st.textContent = "#aiPanel, #toc, #tocToggle, #aiToggle, #explainBtn { transition: none !important; animation: none !important; }";
    document.head.appendChild(st);
  }

  function res(id, pass, detail) { return { id: id, pass: !!pass, detail: detail || "" }; }
  function rect(el) { var r = el.getBoundingClientRect(); return { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) }; }
  function visible(el) { if (!el) return false; var s = getComputedStyle(el), r = el.getBoundingClientRect(); return s.display !== "none" && s.visibility !== "hidden" && r.width > 0 && r.height > 0; }
  function z(el) { return parseInt(getComputedStyle(el).zIndex, 10) || 0; }
  function wait(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  function describe(el) {
    if (!el) return "(none)";
    return el.tagName.toLowerCase() + (el.id ? "#" + el.id : "") + (el.className && typeof el.className === "string" ? "." + el.className.split(/\s+/).join(".") : "");
  }
  function fetchStatus(url, method) {
    return fetch(url, { method: method || "GET", cache: "no-store" }).then(function (r) { return r.status; }, function () { return 0; });
  }

  /* H1 — hub cards match config pages and all hrefs resolve. */
  R.hubCards = function (expectedPages) {
    var cards = [].slice.call(document.querySelectorAll(".cards a.card"));
    if (cards.length !== expectedPages.length) {
      return Promise.resolve(res("H1", false, "expected " + expectedPages.length + " cards, found " + cards.length));
    }
    return Promise.all(cards.map(function (a) {
      return fetchStatus(a.getAttribute("href")).then(function (st) { return { href: a.getAttribute("href"), st: st }; });
    })).then(function (rs) {
      var bad = rs.filter(function (r) { return r.st !== 200; });
      return res("H1", bad.length === 0, bad.map(function (b) { return b.href + " -> HTTP " + b.st; }).join("; "));
    });
  };

  /* H2 — podcast block: progress json reachable; when done, audio wired up. */
  R.podcast = function () {
    var sec = document.getElementById("podcast");
    if (!sec) return Promise.resolve(res("H2", true, "no podcast section (skipped)"));
    return fetch("podcast-progress.json?_=" + Math.random(), { cache: "no-store" }).then(function (r) {
      if (!r.ok) return res("H2", false, "podcast-progress.json -> HTTP " + r.status);
      return r.json().then(function (p) {
        if (p.status !== "done") return res("H2", true, "podcast status=" + p.status + " (audio not asserted)");
        var audio = document.getElementById("pcAudio");
        // player polls every 1.5-3s; give it one cycle to pick up "done"
        return wait(3500).then(function () {
          if (!audio || !audio.getAttribute("src")) return res("H2", false, "status done but #pcAudio has no src");
          var dl = document.querySelector("#podcast a[download], #pcDownload");
          var target = dl ? dl.getAttribute("href") : audio.getAttribute("src").split("?")[0];
          return fetchStatus(target, "HEAD").then(function (st) {
            return res("H2", st === 200, st === 200 ? "" : target + " -> HTTP " + st);
          });
        });
      });
    }, function (e) { return res("H2", false, "fetch failed: " + e); });
  };

  /* N1 — view switch: exactly one active link, sibling views resolve. */
  R.viewSwitch = function () {
    var links = [].slice.call(document.querySelectorAll(".viewswitch a"));
    if (!links.length) return Promise.resolve(res("N1", false, "no .viewswitch links"));
    var active = links.filter(function (a) { return a.classList.contains("active"); });
    if (active.length !== 1) return Promise.resolve(res("N1", false, active.length + " active view links, expected 1"));
    var others = links.filter(function (a) { return !a.classList.contains("active"); });
    return Promise.all(others.map(function (a) {
      return fetchStatus(a.getAttribute("href")).then(function (st) { return { href: a.getAttribute("href"), st: st }; });
    })).then(function (rs) {
      var bad = rs.filter(function (r) { return r.st !== 200; });
      return res("N1", bad.length === 0, bad.map(function (b) { return b.href + " -> HTTP " + b.st; }).join("; "));
    });
  };

  /* T1 — TOC: docked rail on wide viewports, toggle hidden, links target real ids. */
  R.tocRail = function () {
    var toc = document.getElementById("toc"), toggle = document.getElementById("tocToggle");
    var wide = window.innerWidth >= 1024;
    if (!toc) {
      var sections = document.querySelectorAll("main > section").length;
      return res("T1", sections < 3, sections + " sections but no #toc built");
    }
    var problems = [];
    if (!document.body.classList.contains("has-toc")) problems.push("body.has-toc missing");
    if (wide) {
      if (!visible(toc)) problems.push("docked rail not visible at " + window.innerWidth + "px");
      if (toggle && visible(toggle)) problems.push("#tocToggle visible in docked-rail mode");
    }
    [].forEach.call(toc.querySelectorAll("a.toc-link"), function (a) {
      var id = (a.getAttribute("href") || "").slice(1);
      if (!id || !document.getElementById(id)) problems.push("dead toc link: " + a.getAttribute("href"));
    });
    return res("T1", problems.length === 0, problems.join("; "));
  };

  /* T2 — scroll-spy: scrolling to a mid section marks its link active. */
  R.scrollSpy = function () {
    var toc = document.getElementById("toc");
    if (!toc) return Promise.resolve(res("T2", true, "no #toc (skipped)"));
    var links = [].slice.call(toc.querySelectorAll("a.toc-link"));
    if (links.length < 3) return Promise.resolve(res("T2", true, "fewer than 3 toc links (skipped)"));
    var mid = links[Math.floor(links.length / 2)];
    var id = mid.getAttribute("href").slice(1);
    var target = document.getElementById(id);
    var prevY = window.scrollY;
    // rAF never fires in hidden tabs, which would stall the page's scroll-spy;
    // shim it to a plain timeout for the duration of this check.
    var realRaf = window.requestAnimationFrame;
    window.requestAnimationFrame = function (cb) { return setTimeout(function () { cb(performance.now()); }, 0); };
    function nudge() { document.dispatchEvent(new Event("scroll")); }
    // the page uses scroll-behavior:smooth, whose animation pauses in hidden tabs — jump instantly
    function jump(y) { window.scrollTo({ top: y, left: 0, behavior: "instant" }); }
    jump(window.scrollY + target.getBoundingClientRect().top - 60);
    nudge();
    return wait(250).then(function () {
      var ok = mid.classList.contains("active");
      var detail = ok ? "" : "scrolled to #" + id + " but active link is " +
        describe(toc.querySelector("a.toc-link.active"));
      jump(prevY);
      nudge();
      return wait(150).then(function () {
        window.requestAnimationFrame = realRaf;
        return res("T2", ok, detail);
      });
    });
  };

  /* A1 — assistant panel opens and closes via its buttons. */
  R.assistantToggle = function () {
    var toggle = document.getElementById("aiToggle"), panel = document.getElementById("aiPanel"),
        close = document.getElementById("aiClose");
    if (!toggle || !panel || !close) return Promise.resolve(res("A1", false, "missing #aiToggle/#aiPanel/#aiClose"));
    panel.classList.remove("open");
    toggle.click();
    var opened = panel.classList.contains("open") && visible(panel);
    close.click();
    var closed = !panel.classList.contains("open");
    return Promise.resolve(res("A1", opened && closed,
      (opened ? "" : "panel did not open; ") + (closed ? "" : "panel did not close")));
  };

  /* A2 — deep/fullscreen mode: panel covers the viewport and nothing paints above it.
     Samples a grid of points; every hit must belong to the panel (or #explainBtn). */
  R.deepOverlap = function () {
    var panel = document.getElementById("aiPanel"), deep = document.getElementById("aiDeep");
    if (!panel || !deep) return Promise.resolve(res("A2", false, "missing #aiPanel/#aiDeep"));
    if (!deep.checked) { deep.checked = true; deep.dispatchEvent(new Event("change", { bubbles: true })); }
    return wait(150).then(function () {
      var problems = [];
      if (!panel.classList.contains("deep") || !panel.classList.contains("fs"))
        problems.push("panel classes are '" + panel.className + "', expected deep+fs+open");
      var r = rect(panel);
      if (r.w < window.innerWidth * 0.95 || r.h < window.innerHeight * 0.95)
        problems.push("fullscreen rect only " + r.w + "x" + r.h + " in " + window.innerWidth + "x" + window.innerHeight);
      if (Math.abs(r.x) > 2 || Math.abs(r.y) > 2)
        problems.push("fullscreen panel offset at (" + r.x + "," + r.y + "), expected (0,0)");
      var cols = 4, rows = 3, occluders = [];
      for (var i = 0; i < cols; i++) {
        for (var j = 0; j < rows; j++) {
          var x = Math.round(window.innerWidth * (i + 0.5) / cols);
          var y = Math.round(window.innerHeight * (j + 0.5) / rows);
          var el = document.elementFromPoint(x, y);
          if (el && !panel.contains(el) && el !== panel && el.id !== "explainBtn")
            occluders.push(describe(el) + " at (" + x + "," + y + ")");
        }
      }
      if (occluders.length) problems.push("occluded by: " + occluders.join(", "));
      // restore
      deep.checked = false; deep.dispatchEvent(new Event("change", { bubbles: true }));
      panel.classList.remove("open");
      return res("A2", problems.length === 0, problems.join("; "));
    });
  };

  /* A3 — select-to-Explain: button appears above an outside selection,
     never for selections inside the panel, and hides on scroll. */
  R.explainButton = function () {
    var btn = document.getElementById("explainBtn"), panel = document.getElementById("aiPanel");
    if (!btn || !panel) return Promise.resolve(res("A3", false, "missing #explainBtn/#aiPanel"));
    var para = document.querySelector("main section p");
    if (!para) return Promise.resolve(res("A3", false, "no content paragraph to select"));
    function select(node) {
      var range = document.createRange(); range.selectNodeContents(node);
      var sel = getSelection(); sel.removeAllRanges(); sel.addRange(range);
      document.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }));
    }
    var problems = [];
    select(para);
    return wait(80).then(function () {
      if (getComputedStyle(btn).display === "none") problems.push("button did not appear for content selection");
      else {
        var selTop = window.scrollY + para.getBoundingClientRect().top;
        var btnTop = parseFloat(btn.style.top);
        if (!(btnTop < selTop) || selTop - btnTop > 80) problems.push("button not just above selection (btn " + Math.round(btnTop) + ", sel " + Math.round(selTop) + ")");
      }
      document.dispatchEvent(new Event("scroll"));
      if (getComputedStyle(btn).display !== "none") problems.push("button not hidden on scroll");
      panel.classList.add("open");
      var inPanel = panel.querySelector(".empty, .at") || panel;
      select(inPanel);
      return wait(80);
    }).then(function () {
      if (getComputedStyle(btn).display !== "none") problems.push("button shown for selection inside panel");
      getSelection().removeAllRanges();
      panel.classList.remove("open");
      return res("A3", problems.length === 0, problems.join("; "));
    });
  };

  /* A4 — static layering invariants across the fixed chrome. */
  R.layering = function () {
    var get = function (id) { return document.getElementById(id); };
    var panel = get("aiPanel"), btn = get("explainBtn"), toc = get("toc"),
        aiT = get("aiToggle"), tocT = get("tocToggle"), topbar = document.querySelector(".topbar");
    if (!panel || !btn) return res("A4", false, "missing #aiPanel/#explainBtn");
    var problems = [];
    if (!(z(btn) > z(panel))) problems.push("#explainBtn z " + z(btn) + " not above #aiPanel z " + z(panel));
    if (aiT && !(z(panel) > z(aiT))) problems.push("#aiPanel z " + z(panel) + " not above #aiToggle z " + z(aiT));
    if (toc && tocT && !(z(toc) > z(tocT))) problems.push("#toc z " + z(toc) + " not above #tocToggle z " + z(tocT));
    if (topbar && aiT && !(z(aiT) > z(topbar))) problems.push("#aiToggle z " + z(aiT) + " not above .topbar z " + z(topbar));
    return res("A4", problems.length === 0, problems.join("; "));
  };

  /* R1 — narrow-viewport TOC: rail undocks, toggle shows and works.
     Run AFTER the harness resized the window below 1024px. */
  R.tocNarrow = function () {
    var toc = document.getElementById("toc"), toggle = document.getElementById("tocToggle");
    if (!toc) return Promise.resolve(res("R1", true, "no #toc (skipped)"));
    if (window.innerWidth >= 1024) return Promise.resolve(res("R1", false, "viewport is " + window.innerWidth + "px; resize below 1024 first"));
    var problems = [];
    if (!visible(toggle)) problems.push("#tocToggle not visible on narrow viewport");
    if (toc.classList.contains("open")) toc.classList.remove("open");
    if (visible(toc)) problems.push("rail still visible while closed on narrow viewport");
    toggle.click();
    return wait(350).then(function () {
      if (!toc.classList.contains("open") || !visible(toc)) problems.push("toggle did not open the panel");
      toggle.click();
      return wait(350);
    }).then(function () {
      if (toc.classList.contains("open")) problems.push("toggle did not close the panel");
      return res("R1", problems.length === 0, problems.join("; "));
    });
  };

  /* D1 — animated diagrams have real geometry. */
  R.diagrams = function () {
    var problems = [];
    [].forEach.call(document.querySelectorAll(".diagram"), function (d, i) {
      var r = rect(d);
      if (r.w === 0 || r.h === 0) problems.push(".diagram[" + i + "] has zero size");
      [].forEach.call(d.querySelectorAll(".fnode"), function (n) {
        var nr = rect(n);
        if (nr.w === 0 || nr.h === 0) problems.push("zero-size .fnode '" + n.textContent.trim().slice(0, 24) + "'");
        else if (nr.x < r.x - 2 || nr.x + nr.w > r.x + r.w + 2) problems.push(".fnode '" + n.textContent.trim().slice(0, 24) + "' overflows its diagram");
      });
    });
    return res("D1", problems.length === 0, problems.join("; "));
  };

  /* B1 — bridge API reachable (CORS preflight only; no claude invocation). */
  R.apiPreflight = function () {
    return fetchStatus("/api/explain", "OPTIONS").then(function (st) {
      return res("B1", st === 204, st === 204 ? "" : "OPTIONS /api/explain -> HTTP " + st);
    });
  };

  /* Run a named subset (or a sensible default set) sequentially; returns results array. */
  R.run = function (ids, opts) {
    opts = opts || {};
    var seq = Promise.resolve(), out = [];
    if (document.visibilityState !== "visible") {
      // Checks are hidden-tab tolerant (transitions frozen, rAF shimmed), but
      // timers are throttled — flag it so slow waits aren't mistaken for hangs.
      out.push(res("ENV", true, "tab is hidden; timers throttled, visual pass screenshots may not reflect animations"));
    }
    (ids || []).forEach(function (id) {
      seq = seq.then(function () {
        var fn = R[id];
        if (!fn) { out.push(res(id, false, "unknown check")); return; }
        var arg = id === "hubCards" ? opts.pages : undefined;
        return Promise.resolve().then(function () { return fn(arg); }).then(
          function (r) { out.push(r); },
          function (e) { out.push(res(id, false, "check threw: " + (e && e.message || e))); }
        );
      });
    });
    return seq.then(function () { return out; });
  };

  window.__reTest = R;
})();
