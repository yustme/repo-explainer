/* repo-explainer — in-page AI assistant.
   Same-origin (relative) API; served by assistant-bridge.py.
   Page identity comes from <body data-repo data-page data-view data-world>. */
(function () {
  var API = "/api/explain", PROPOSE_API = "/api/propose", APPLY_API = "/api/apply";
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var B = document.body;
  var REPO = B.getAttribute("data-repo") || "";
  var PAGE = B.getAttribute("data-page") || "";
  var WORLD = B.getAttribute("data-world") || (document.title || "this repository");
  var HAS_REPO_TARGET = B.getAttribute("data-repo-docs") === "1";

  var panel = document.getElementById("aiPanel"),
      log = document.getElementById("aiLog"),
      toggle = document.getElementById("aiToggle"),
      closeBtn = document.getElementById("aiClose"),
      explainBtn = document.getElementById("explainBtn"),
      form = document.getElementById("aiForm"),
      input = document.getElementById("aiInput");
  if (!panel) return;
  var lastSel = "", lastCtx = "";
  var EMPTY_HTML = log.innerHTML;

  // Deep research toggle: fullscreen + deep mode (reads the real clone).
  var deepChk = document.getElementById("aiDeep");
  var deepLbl = document.getElementById("aiDeepLbl");
  function applyDeep() {
    var on = deepChk.checked;
    panel.classList.toggle("deep", on);
    panel.classList.toggle("fs", on);
    deepLbl.classList.toggle("on", on);
    if (on) panel.classList.add("open");
  }
  deepChk.addEventListener("change", applyDeep);
  toggle.addEventListener("click", function () { panel.classList.toggle("open"); });
  closeBtn.addEventListener("click", function () { panel.classList.remove("open"); });
  document.getElementById("aiClear").addEventListener("click", function () {
    log.innerHTML = EMPTY_HTML; lastSel = ""; lastCtx = "";
  });

  function clearBtn() { explainBtn.style.display = "none"; }
  document.addEventListener("mouseup", function () {
    setTimeout(function () {
      var sel = window.getSelection();
      var txt = sel ? sel.toString().trim() : "";
      if (!txt || txt.length < 2) { clearBtn(); return; }
      if (panel.contains(sel.anchorNode)) { clearBtn(); return; }
      var range = sel.getRangeAt(0), r = range.getBoundingClientRect();
      if (!r || (r.width === 0 && r.height === 0)) { clearBtn(); return; }
      lastSel = txt;
      lastCtx = extractContext(sel.anchorNode);
      explainBtn.style.display = "block";
      var bx = window.scrollX + r.left + r.width / 2 - explainBtn.offsetWidth / 2;
      var by = window.scrollY + r.top - explainBtn.offsetHeight - 8;
      explainBtn.style.left = Math.max(8, bx) + "px";
      explainBtn.style.top = Math.max(8, by) + "px";
    }, 10);
  });
  document.addEventListener("scroll", clearBtn, true);

  function clip(s, n) { s = (s || "").replace(/\s+/g, " ").trim(); return s.length > n ? s.slice(0, n) + "…" : s; }
  function headingAbove(block, sec) {
    if (!sec || !block) return "";
    var hs = [].slice.call(sec.querySelectorAll("h2, h3, h4")), found = "";
    hs.forEach(function (h) {
      if (h.compareDocumentPosition(block) & Node.DOCUMENT_POSITION_FOLLOWING) found = h.textContent.trim();
    });
    return found;
  }
  function extractContext(node) {
    var el = node && node.nodeType === 3 ? node.parentElement : node;
    if (!el) return "";
    var parts = ["Page: " + (document.title || WORLD) + "."];
    var sec = el.closest("section, .section");
    if (sec) {
      var h2 = sec.querySelector("h2");
      if (h2) parts.push("Section: " + h2.textContent.trim());
      var lead = sec.querySelector(".lead");
      if (lead) parts.push("Section is about: " + clip(lead.textContent, 320));
    }
    var block = el.closest("p, li, td, h2, h3, h4, .prompt .body, .prompt, .code, .callout, .lead, .card");
    var sub = headingAbove(block || el, sec);
    if (sub) parts.push("Subsection: " + sub);
    if (block) {
      var prev = block.previousElementSibling, next = block.nextElementSibling;
      if (prev && prev.textContent.trim()) parts.push("Previous block: " + clip(prev.textContent, 280));
      parts.push("Block with the selected text: " + clip(block.textContent, 700));
      if (next && next.textContent.trim()) parts.push("Next block: " + clip(next.textContent, 280));
    }
    return parts.join("\n").slice(0, 1900);
  }

  explainBtn.addEventListener("mousedown", function (e) { e.preventDefault(); });
  explainBtn.addEventListener("click", function () {
    var txt = lastSel, ctx = lastCtx; clearBtn(); ask(txt, ctx, true);
  });
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var q = input.value.trim(); if (!q) return; input.value = "";
    ask(q, lastCtx, false);
  });

  function addMsg(cls, text) {
    var d = document.createElement("div"); d.className = "msg " + cls; d.textContent = text;
    log.appendChild(d); log.scrollTop = log.scrollHeight; return d;
  }

  function ask(selection, context, isSelection) {
    panel.classList.add("open");
    var deep = panel.classList.contains("deep");
    var empty = log.querySelector(".empty"); if (empty) empty.remove();
    addMsg("user", (isSelection ? "Explain: " : "") + selection);
    var ai = addMsg("ai", "");
    var src = isSelection ? "selection" : "followup";
    if (deep) {
      var dbody = JSON.stringify({ selection: selection, context: context, source: src, mode: "deep", repo: REPO });
      runStream(ai, API, dbody, {
        label: "deep research running",
        onDone: function (text) {
          renderAnswer(ai, text || "(empty answer)", true, function () { addIntegrateUI(ai, text, selection, context); });
        }
      });
      return;
    }
    var think = document.createElement("span"); think.className = "think"; think.textContent = "thinking…";
    ai.appendChild(think);
    var cbody = JSON.stringify({ selection: selection, context: context, source: src, mode: "concise", repo: REPO });
    fetch(API, { method: "POST", headers: { "Content-Type": "application/json" }, body: cbody })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        ai.textContent = "";
        var t = d.text || "(empty answer)";
        renderAnswer(ai, t, false, function () { addIntegrateUI(ai, t, selection, context); });
      })
      .catch(bridgeDown.bind(null, ai));
  }

  function bridgeDown(ai) {
    ai.innerHTML = '<span class="think">The local bridge is not running. Start it with:</span><br>' +
      '<code style="font-family:var(--font-mono);color:var(--steel);font-size:0.8rem">python3 assistant-bridge.py &lt;workspace&gt;</code>';
  }

  // Generic SSE runner: live activity log inside `container`; opts.onDone(text).
  function runStream(container, endpoint, body, opts) {
    opts = opts || {};
    var label = opts.label || "working";
    var acts = document.createElement("div"); acts.className = "acts";
    var head = document.createElement("div"); head.className = "acts-head";
    head.innerHTML = '<span class="spin"></span><span class="acts-title"></span>';
    var listEl = document.createElement("div"); listEl.className = "acts-list";
    acts.appendChild(head); acts.appendChild(listEl); container.appendChild(acts);
    var title = head.querySelector(".acts-title"); title.textContent = label + "…";
    log.scrollTop = log.scrollHeight;
    var t0 = Date.now();
    var timer = setInterval(function () { title.textContent = label + "… " + Math.round((Date.now() - t0) / 1000) + " s"; }, 1000);
    function addAct(text) { var d = document.createElement("div"); d.className = "act"; d.textContent = text; listEl.appendChild(d); log.scrollTop = log.scrollHeight; }
    fetch(endpoint, { method: "POST", headers: { "Content-Type": "application/json" }, body: body })
      .then(function (r) {
        if (!r.body) throw new Error("no stream");
        var reader = r.body.getReader(), dec = new TextDecoder(), buf = "";
        function pump() {
          return reader.read().then(function (res) {
            if (res.done) { clearInterval(timer); return; }
            buf += dec.decode(res.value, { stream: true });
            var chunks = buf.split("\n\n"); buf = chunks.pop();
            chunks.forEach(function (c) {
              var line = c.replace(/^data: ?/, "").trim();
              if (!line) return;
              var ev; try { ev = JSON.parse(line); } catch (e) { return; }
              if (ev.type === "status") { addAct(ev.text); }
              else if (ev.type === "done") { clearInterval(timer); acts.remove(); (opts.onDone || function () {})(ev.text); }
              else if (ev.type === "error") { clearInterval(timer); title.textContent = ev.text; head.querySelector(".spin").style.display = "none"; if (opts.onError) opts.onError(ev.text); }
            });
            return pump();
          });
        }
        return pump();
      })
      .catch(function () { clearInterval(timer); acts.remove(); bridgeDown(container); });
  }

  // ---- Feedback loop: integrate an answer back into docs ----
  function addIntegrateUI(aiEl, answerText, selection, context) {
    if (!answerText || /^The local bridge/.test(answerText) || /^\(/.test(answerText)) return;
    var bar = document.createElement("div"); bar.className = "intbar";
    var btn = document.createElement("button"); btn.type = "button"; btn.className = "intbtn";
    btn.textContent = "✚ Integrate into docs";
    btn.title = "Propose folding this answer back into the documentation";
    bar.appendChild(btn); aiEl.appendChild(bar); log.scrollTop = log.scrollHeight;
    btn.addEventListener("click", function () { bar.remove(); startProposal(answerText, selection, context, "", ""); });
  }

  function startProposal(answerText, selection, context, instruction, prior) {
    var card = document.createElement("div"); card.className = "msg ai intcard";
    log.appendChild(card); log.scrollTop = log.scrollHeight;
    var body = JSON.stringify({ answer: answerText, selection: selection, context: context, instruction: instruction, prior: prior, page: PAGE, repo: REPO });
    runStream(card, PROPOSE_API, body, {
      label: "preparing integration proposal",
      onDone: function (text) { renderProposal(card, text, answerText, selection, context); }
    });
  }

  function renderProposal(card, proposalText, answerText, selection, context) {
    card.innerHTML = "";
    var h = document.createElement("div"); h.className = "intcard-h"; h.textContent = "Integration proposal"; card.appendChild(h);
    var bodyEl = document.createElement("div"); bodyEl.className = "intcard-body"; bodyEl.innerHTML = renderRich(proposalText, true); card.appendChild(bodyEl);
    var ta = document.createElement("textarea"); ta.className = "intta"; ta.placeholder = "Add an instruction to refine the proposal (optional), then Regenerate…"; card.appendChild(ta);
    var tgtWrap = document.createElement("div"); tgtWrap.className = "inttarget";
    tgtWrap.innerHTML = "Merge target:";
    var sel = document.createElement("select");
    var o1 = document.createElement("option"); o1.value = "docsite"; o1.textContent = "This documentation page"; sel.appendChild(o1);
    if (HAS_REPO_TARGET) { var o2 = document.createElement("option"); o2.value = "repo"; o2.textContent = "Source repo docs (README/docs)"; sel.appendChild(o2); }
    tgtWrap.appendChild(sel); card.appendChild(tgtWrap);
    var row = document.createElement("div"); row.className = "introw";
    var regen = document.createElement("button"); regen.type = "button"; regen.className = "intbtn ghost"; regen.textContent = "↻ Regenerate with edit";
    var approve = document.createElement("button"); approve.type = "button"; approve.className = "intbtn"; approve.textContent = "✓ Approve & merge";
    var cancel = document.createElement("button"); cancel.type = "button"; cancel.className = "intbtn ghost"; cancel.textContent = "Cancel";
    row.appendChild(regen); row.appendChild(approve); row.appendChild(cancel); card.appendChild(row); log.scrollTop = log.scrollHeight;
    regen.addEventListener("click", function () { var instr = ta.value.trim(); card.remove(); startProposal(answerText, selection, context, instr, proposalText); });
    approve.addEventListener("click", function () { applyIntegration(card, proposalText, ta.value.trim(), sel.value); });
    cancel.addEventListener("click", function () { card.remove(); });
  }

  function applyIntegration(card, proposalText, instruction, target) {
    card.innerHTML = "";
    var h = document.createElement("div"); h.className = "intcard-h"; h.textContent = "Merging into " + (target === "repo" ? "source repo docs" : "documentation page"); card.appendChild(h);
    var body = JSON.stringify({ proposal: proposalText, instruction: instruction, target: target, page: PAGE, repo: REPO });
    runStream(card, APPLY_API, body, {
      label: "merging",
      onDone: function (text) {
        card.innerHTML = "";
        var ok = document.createElement("div"); ok.className = "intok";
        ok.innerHTML = "<strong>✓ Merged</strong> — a .bak backup was created.";
        var summary = document.createElement("div"); summary.className = "intcard-body"; summary.innerHTML = renderRich(text || "", false);
        card.appendChild(ok); card.appendChild(summary);
        if (target !== "repo") {
          var rl = document.createElement("button"); rl.type = "button"; rl.className = "intbtn"; rl.textContent = "↻ Reload page";
          rl.addEventListener("click", function () { location.reload(); });
          card.appendChild(rl);
        }
        log.scrollTop = log.scrollHeight;
      }
    });
  }

  function esc(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
  function escAttr(s) { return s.replace(/&/g, "&amp;").replace(/"/g, "&quot;"); }
  function inline(s) {
    s = esc(s);
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>").replace(/__([^_]+)__/g, "<strong>$1</strong>");
    s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
    return s;
  }
  function renderBlocks(seg) {
    var lines = seg.split("\n"), out = "", li = false;
    function cl() { if (li) { out += "</ul>"; li = false; } }
    lines.forEach(function (ln) {
      var t = ln.trim();
      if (!t) { cl(); return; }
      var h = t.match(/^(#{2,4})\s+(.*)$/);
      if (h) { cl(); var lv = Math.min(4, h[1].length + 1); out += "<h" + lv + ">" + inline(h[2]) + "</h" + lv + ">"; return; }
      var m = t.match(/^[-•*]\s+(.*)$/);
      if (m) { if (!li) { out += "<ul>"; li = true; } out += "<li>" + inline(m[1]) + "</li>"; return; }
      cl(); out += "<p>" + inline(t) + "</p>";
    });
    cl(); return out;
  }
  // codeOnly=true renders ```html blocks as readable code (proposal review)
  function renderRich(text, codeOnly) {
    var parts = String(text).split("```"), html = "";
    for (var i = 0; i < parts.length; i++) {
      if (i % 2 === 1) {
        var seg = parts[i], nl = seg.indexOf("\n");
        var lang = (nl >= 0 ? seg.slice(0, nl) : "").trim().toLowerCase();
        var code = (nl >= 0 ? seg.slice(nl + 1) : seg).replace(/\n$/, "");
        if (lang === "html" && !codeOnly) { html += '<iframe class="ig" sandbox srcdoc="' + escAttr(code) + '"></iframe>'; }
        else { html += '<pre class="cb"><code>' + esc(code) + "</code></pre>"; }
      } else { html += renderBlocks(parts[i]); }
    }
    return html;
  }
  function renderAnswer(el, text, deep, onComplete) {
    function done() { if (onComplete) onComplete(); }
    if (deep || reduce) { el.innerHTML = renderRich(text); log.scrollTop = log.scrollHeight; done(); return; }
    var i = 0;
    (function step() {
      if (i < text.length) { el.textContent = text.slice(0, i); i += 2; log.scrollTop = log.scrollHeight; setTimeout(step, 12); }
      else { el.innerHTML = renderRich(text); log.scrollTop = log.scrollHeight; done(); }
    })();
  }
})();
