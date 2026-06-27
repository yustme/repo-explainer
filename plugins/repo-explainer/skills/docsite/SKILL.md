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
- **Technical pages** — shape follows the depth mode: high-level = a short overview; detailed = sectioned deep-dive with `.prompt`/`.code` file references; rebuild-from-scratch = an ordered sequence of build blocks, each its own `.section`.

Cite real file paths from the analysis. Never introduce facts the analysis did not establish.

## config.json

The workspace root holds `config.json`:

```json
{
  "title": "Acme — repo docs",
  "lang": "en",
  "world": "the Acme project (a short one-line description used in assistant prompts)",
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
