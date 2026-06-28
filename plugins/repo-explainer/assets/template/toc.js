/* repo-explainer — in-page section menu ("On this page") with scroll-spy.
   Auto-built from the page's <section> headings; no authoring needed. Self-contained,
   no deps, mirrors the AI-assistant pattern (toggle bottom-left, slide-in panel). */
(function () {
  var main = document.querySelector("main");
  if (!main) return;

  function slug(s) {
    return (s || "").toLowerCase()
      .replace(/&[^;]+;/g, " ")
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 48) || "section";
  }

  var sections = [].slice.call(main.querySelectorAll(":scope > section"));
  var items = [], used = {};
  sections.forEach(function (sec) {
    var isHero = sec.classList.contains("hero");
    var h = sec.querySelector(isHero ? "h1" : "h2");
    if (!h) return;
    var label = h.textContent.trim();
    if (!label) return;
    if (!sec.id) {
      var base = isHero ? "top" : slug(label), id = base, n = 2;
      while (used[id] || document.getElementById(id)) { id = base + "-" + n++; }
      sec.id = id;
    }
    used[sec.id] = true;
    items.push({ id: sec.id, label: label, hero: isHero, el: sec });
  });
  if (items.length < 3) return; // too short to bother

  var toggle = document.createElement("button");
  toggle.id = "tocToggle"; toggle.type = "button";
  toggle.innerHTML = "☰ Contents";
  document.body.appendChild(toggle);

  var panel = document.createElement("nav");
  panel.id = "toc"; panel.setAttribute("aria-label", "Contents");
  var head = document.createElement("div"); head.className = "toc-h";
  head.innerHTML = '<span class="toc-t">On this page</span>';
  var close = document.createElement("button");
  close.type = "button"; close.className = "toc-x"; close.title = "Close"; close.textContent = "×";
  head.appendChild(close); panel.appendChild(head);

  var list = document.createElement("div"); list.className = "toc-list";
  var linkById = {};
  items.forEach(function (it) {
    var a = document.createElement("a");
    a.href = "#" + it.id; a.textContent = it.label;
    a.className = "toc-link" + (it.hero ? " toc-top" : "");
    list.appendChild(a); linkById[it.id] = a;
    a.addEventListener("click", function () {
      // when the menu is a docked rail (>=1024px) keep it open; otherwise close after a jump
      if (window.matchMedia("(max-width: 1023px)").matches) panel.classList.remove("open");
    });
  });
  panel.appendChild(list); document.body.appendChild(panel);
  document.body.classList.add("has-toc"); // CSS docks the menu open on wide viewports

  toggle.addEventListener("click", function () { panel.classList.toggle("open"); });
  close.addEventListener("click", function () { panel.classList.remove("open"); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") panel.classList.remove("open"); });

  // Scroll-spy: active = last section whose top crossed the line under the topbar.
  var current = null;
  function setActive(id) {
    if (id === current) return;
    if (current && linkById[current]) linkById[current].classList.remove("active");
    current = id;
    if (current && linkById[current]) {
      var a = linkById[current];
      a.classList.add("active");
      a.scrollIntoView({ block: "nearest" });
    }
  }
  function spy() {
    var line = 92, best = items[0].id;
    for (var i = 0; i < items.length; i++) {
      if (items[i].el.getBoundingClientRect().top - line <= 0) best = items[i].id;
      else break;
    }
    setActive(best);
  }
  var ticking = false;
  function onScroll() {
    if (ticking) return; ticking = true;
    requestAnimationFrame(function () { spy(); ticking = false; });
  }
  document.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onScroll, { passive: true });
  spy();
})();
