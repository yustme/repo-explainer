---
name: docsite
description: >
  Conventions for filling the generated docsite pages and operating the local server/bridge.
  Used by explain-repo. Use when writing documentation content into scaffolded pages, choosing
  design components, refining config.json, or starting/stopping the local docsite server.
metadata:
  tools: "Read, Write, Edit, Bash"
  model: sonnet
---

# Fill and Operate the Docsite

The scaffold has already built the page chrome. Your job is to write the documentation content into each page and run the local server. Locate bundled assets with `$PLUGIN_PATH`.

## The page model

`scaffold.py` generates, in the workspace root:

- `index.html` — the hub page (entry point, lists the repo(s) and views).
- per repo: `<slug>-business.html`, and `<slug>-technical.html` when scope includes technical.

Each content page is already complete except for the body: it ships with the full design chrome (topbar with the repo switcher when there is more than one repo, the Business / Technical view switch), the embedded AI assistant, and a content region inside `<main>` delimited by a marker pair, with a placeholder stub between them:

```html
<!-- REPO_EXPLAINER:CONTENT -->
<section class="hero">…stub…</section>
<!-- /REPO_EXPLAINER:CONTENT -->
```

**Your task:** with `Edit`, replace **everything between** `<!-- REPO_EXPLAINER:CONTENT -->` and `<!-- /REPO_EXPLAINER:CONTENT -->` (including the stub) with the written documentation for that page. Keep the two marker comments in place. Do not touch the chrome, the inlined CSS/JS, or the `<body data-...>` identity attributes — only the content between the markers.

The hub `index.html` is auto-generated and usable as-is; you may optionally refine its hero text and card descriptions (same marker pair) into the chosen language.

Write the content in the language from `config.json` `lang`.

**Automatic "On this page" menu.** Each content page builds its own section menu at runtime (`toc.js`) from your `<section>` headings — a toggle button bottom-left opens a slide-in list with scroll-spy. You do not author it. To make it good: structure the body as a flat sequence of `<section class="section">` blocks each led by a meaningful `<h2>` (the menu label), keep `<section class="hero">` with the `<h1>` at the top, and give dedicated deep-dive sections a stable `id` (used as the anchor). Sections without an `id` get one slugified from their heading.

## Design components

The inlined `styles.css` defines a self-contained design system on a dark ink ground (`#14181E`) with a brass accent (`#C99A3F`) and parchment text (`#E9E3D6`), using a serif display face, a system sans for body, and mono for code. Stay within these components — do not add external stylesheets, fonts, scripts, or images (the pages are self-contained and CSP-safe).

Use each component for its intended purpose:

- `.section` — wraps one documentation section. The basic building block of a page.
- `.eyebrow` — a small label above a heading (e.g. "OVERVIEW", "ARCHITECTURE").
- `.lead` — the intro paragraph of a section or page; sets context before the detail.
- `.cards` / `.card` — a grid of cards. Use for feature lists, component inventories, capability summaries — anything that reads as a set of peers.
- `.prompt` with `.src` and `.body` — a quoted / annotated block. `.src` carries the source (e.g. a file path or label), `.body` the content. Ideal for code-derived call-outs: "from `src/server.ts` — the request lifecycle is…".
- `.code` — a code or snippet block for verbatim source excerpts.
- `.callout` — a note or warning set apart from the flow (caveats, "unknown from source", gotchas).

Match content to the analysis output:
- **Business pages** — lead paragraph + sections for purpose, what it does, who it's for, value, key capabilities (`.cards`), and how to run it.
- **Technical pages** — shape follows the depth mode: high-level = a short overview; detailed = sectioned deep-dive with `.prompt`/`.code` file references; rebuild-from-scratch = an ordered sequence of build blocks, each its own `.section`. The **concepts-vs-code** choice sets the density of verbatim source: `concepts` leans on prose with the occasional snippet, `code` makes `.code` / `.prompt` source blocks the backbone of each section, `both` pairs a conceptual explanation with the implementing code.

Cite real file paths from the analysis. Never introduce facts the analysis did not establish.

## Animated diagrams (only when `config.json` `visuals` is `animated`)

When visuals are enabled, render the analysis's **flow specs** as animated diagrams placed *next to the prose that explains each flow* — not in a gallery at the end. They are styled by the inlined `styles.css` (no extra CSS needed) and are JS-free (CSS + SVG SMIL), so they work everywhere the page does. Motion is automatically frozen under `prefers-reduced-motion`, so every diagram must read correctly as a still image too. If visuals are `none`, skip this entirely.

Two components are available:

**`.flow` — animated pipeline (the default).** Use for linear or branching `A → B → C` flows: data pipelines, request lifecycles, build sequences. A row of `.fnode` boxes joined by `.link` connectors; each `.link` carries a `.dot` that travels along it. Wrap it in `.diagram` for the framed figure + caption. Highlight the key node with `.fnode.accent`.

```html
<figure class="diagram">
  <span class="cap">Request lifecycle · src/server.ts</span>
  <div class="flow">
    <div class="fnode">Client<span class="fs">HTTP request</span></div>
    <div class="link"><span class="dot"></span></div>
    <div class="fnode accent">Express proxy<span class="fs">src/server.ts</span></div>
    <div class="link"><span class="dot"></span></div>
    <div class="fnode">Upstream API<span class="fs">authed call</span></div>
  </div>
</figure>
```

**SVG building blocks — for 2-D architecture / sequence diagrams** that need real layout. Author the `<svg>` inline (with a `viewBox`) and apply the classes from `styles.css`: `.node` / `.node.accent` for boxes, `.nlabel` / `.nsub` for text, `.edge` for static connectors, `.edge.live` for a flowing (animated dashed) connector, `.packet` for a dot that travels along an inline `style="offset-path:path('…')"`, `.reveal` for a staged fade-in, `.glow` to pulse a focal element.

```html
<figure class="diagram">
  <span class="cap">Data flow · src/pipeline/</span>
  <svg viewBox="0 0 320 90" role="img" aria-label="Extractor sends records to the transformer, which writes to storage">
    <rect class="node" x="6" y="30" width="78" height="30" rx="6"/>
    <text class="nlabel" x="45" y="49" text-anchor="middle">Extract</text>
    <path class="edge live" d="M84 45 H140"/>
    <rect class="node accent" x="140" y="30" width="78" height="30" rx="6"/>
    <text class="nlabel" x="179" y="49" text-anchor="middle">Transform</text>
    <path class="edge live" d="M218 45 H274"/>
    <rect class="node" x="274" y="30" width="40" height="30" rx="6"/>
    <circle class="packet" r="3" style="offset-path:path('M84 45 H274')"/>
  </svg>
</figure>
```

Keep every node, edge, and label grounded in the flow spec (and thus in real files). Put the caption (`.cap`) to work as the source citation. Prefer a few diagrams that genuinely clarify how the system works over decorating every section.

The in-page assistant produces its own animated diagrams independently: its infographics render in a **sandboxed, script-less iframe with no access to this page's CSS**, so the assistant must emit a fully self-contained block with its own inline `<style>` (it cannot reuse `.flow`/`.diagram`). That path is handled by `assistant-bridge.py`; you only author the static pages here.

## config.json

The workspace root holds `config.json`:

```json
{
  "title": "Acme — repo docs",
  "lang": "en",
  "world": "the Acme project (a short one-line description used in assistant prompts)",
  "visuals": "animated",
  "models": {"concise": "claude-haiku-4-5-20251001", "deep": "sonnet"},
  "repos": [{"slug": "acme", "name": "Acme", "src": "src/acme", "docs_root": "src/acme"}],
  "pages": {
    "acme-business.html": {"repo": "acme", "view": "business"},
    "acme-technical.html": {"repo": "acme", "view": "technical"}
  }
}
```

- `repos` — each cloned repo: `slug`, display `name`, `src` (the clone path), `docs_root` (where repo-targeted doc edits land).
- `pages` — maps each generated page file to its repo and view.
- `lang` — the documentation content language; also the answer language for deep assistant calls.
- `visuals` — `animated` or `none`. When `animated`, pages carry animated flow diagrams and the assistant is told it may produce them; when `none`, both stay text-only.
- `models` — `concise` (fast, no tools) and `deep` (tool-using research).
- `world` — a one-line description of the repo injected into assistant prompts. The scaffold writes a stub; **refine it** after analysis (Edit `config.json`) to a single accurate sentence describing what the repo is. Accurate `world` text materially improves the assistant's answers.

## Running the server

Start the bridge in the background — it reads `config.json`, serves the workspace statically on a free port (bound to `127.0.0.1`), and exposes the assistant API:

```bash
python3 "$PLUGIN_PATH/assets/bridge/assistant-bridge.py" <workspace>
```

It prints exactly one line: `RUNNING http://localhost:<PORT>/index.html`. Capture that, then open it (`open <url>` on macOS, `xdg-open <url>` on Linux). Keep the process in the background so the site stays up.

To stop the server, kill the background process / task. Logs are written to `<workspace>/logs/assistant.jsonl`.

## The assistant feedback loop

The pages are living documentation, not a static export. From any page the user can:

1. **Explain** — select text and get a concise answer (no tools), or toggle **Deep research** to have the assistant read the actual clone (`Read`/`Grep`/`Glob` over the repo `src`).
2. **Propose / Integrate** — turn an answer into a styled HTML block proposed for the page.
3. **Apply** — after the user refines and approves, write the block into either this docsite page or the source repo's own docs (`docs_root` — typically README.md or `docs/...`), always with a timestamped `.bak` backup of the target first.

Write pages knowing they will grow this way: leave clear section boundaries so integrated blocks slot in cleanly.
