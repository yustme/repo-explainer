---
name: test-docsite
description: >
  UI smoke test for a generated repo-explainer docsite. Drives the served site in the
  user's Chrome (claude-in-chrome), runs deterministic JS assertions from
  assets/test/checks.js (navigation, TOC, assistant panel, deep/fullscreen overlap,
  select-to-Explain, podcast player, diagrams), and reports a PASS/FAIL table in chat.
  Use after generating or changing a docsite, or when the user asks to test/verify it.
allowed-tools: Bash, Read, Glob, AskUserQuestion, mcp__claude-in-chrome__tabs_context_mcp, mcp__claude-in-chrome__tabs_create_mcp, mcp__claude-in-chrome__navigate, mcp__claude-in-chrome__javascript_tool, mcp__claude-in-chrome__read_console_messages, mcp__claude-in-chrome__resize_window, mcp__claude-in-chrome__computer
---

# Test the Docsite UI

Smoke-test an already-generated workspace. This skill does not generate anything — if there is no workspace, run `explain-repo` first.

## Step 1: Resolve the workspace

- Use the path the user gave. Otherwise pick the most recently modified directory under `~/repo-explains/` and tell the user which one you picked.
- The workspace must contain `config.json`. Parse it for:
  - `pages` — a map of content-page filename → `{repo, view}`; test `Object.keys(pages)` plus the hub `index.html` (which is not listed in `pages`),
  - `visuals` — run the diagram check only when `"animated"`,
  - language/slug for the report header.

## Step 2: Start the bridge

```bash
python3 "$PLUGIN_PATH/assets/bridge/assistant-bridge.py" <workspace>
```

Run it **in the background** and capture the first stdout line — exactly `RUNNING http://localhost:<PORT>/index.html` — to get the base URL. If a bridge for this workspace is already running (user session), reuse its URL instead of starting a second one.

Teardown is mandatory: at the end of the run (pass or fail), stop the background task. The server has no shutdown endpoint; killing the process is the supported way.

## Step 3: Open in Chrome and load the assertion bundle

1. `tabs_context_mcp` → `tabs_create_mcp` → `navigate` to the base URL.
2. Read `$PLUGIN_PATH/assets/test/checks.js` and inject its full text with `javascript_tool`. **Re-inject after every navigation** — it defines `window.__reTest`, which does not survive page loads.
3. Confirm injection: `typeof window.__reTest === "object"`.
4. **Hidden-tab caveat.** Chrome pauses CSS transitions and `requestAnimationFrame` in hidden tabs. The bundle compensates (it force-disables chrome transitions and shims rAF inside the scroll-spy check), so checks stay correct even when the user has another window in front — but timers are throttled (waits stretch to ~1 s) and a `pass: true` `ENV` entry flags the condition in the results. Because transitions are disabled during the run, passing checks do not prove animations look right — that is what the visual pass is for; prefer a foreground tab for it.

## Step 4: Run the check matrix

All hard assertions live in `checks.js`; each returns `{id, pass, detail}`. Run them via:

```js
await __reTest.run(["viewSwitch","tocRail","scrollSpy","assistantToggle","deepOverlap","explainButton","layering","diagrams","apiPreflight","podcast"], {})
```

Per page:

| Page | Checks |
|---|---|
| `index.html` (hub) | `hubCards` (pass `{pages: [...]}` from config, hub has no assistant), `podcast`, console errors |
| each content page | `viewSwitch` (N1), `tocRail` (T1), `scrollSpy` (T2), `assistantToggle` (A1), `deepOverlap` (A2), `explainButton` (A3), `layering` (A4), `diagrams` (D1, only if visuals animated), `apiPreflight` (B1), `podcast` (H2, if the page has a `#podcast` section), console errors |
| each content page, narrow | resize the window below 1024 px with `resize_window`, re-inject checks if you navigated, run `tocNarrow` (R1), then restore the original size. If `window.innerWidth` does not change after the resize (minimized window reports `outerWidth: 0`), report R1 as BLOCKED and ask the user to un-minimize Chrome — do not mark it PASS |

Console errors (C1/H3): after each page's checks, `read_console_messages` with `onlyErrors: true` — zero errors expected. Clear messages between pages to avoid bleed-over.

What the key checks assert (so you can interpret failures):

- **A2 `deepOverlap`** — enabling the Deep-research toggle must put `#aiPanel` into `open deep fs`, cover the viewport, and *nothing may paint above it* except `#explainBtn`. The check samples a 4×3 grid with `elementFromPoint` and names any occluding element with coordinates. A failure naming `#toc`/`.toc-link` is the docked-TOC-over-fullscreen-panel layering bug.
- **A3 `explainButton`** — a real text selection in the content must summon `#explainBtn` just above the selection; selections inside the panel must not; scrolling hides it.
- **A4 `layering`** — static z-index ordering: `#explainBtn` > `#aiPanel` > `#aiToggle`/`#tocToggle` > `.topbar`.

Checks restore the state they touch. Do **not** submit the assistant form or click Explain's network path — the UI test stops at the point of submission; `apiPreflight` (a 204 OPTIONS) is the only bridge-API assertion.

## Step 5: Visual pass

Take screenshots of four states per content page and eyeball them for anything geometry can't express (clipped text, misaligned chrome, broken fonts):

1. page as loaded (docked TOC),
2. assistant panel open,
3. deep/fullscreen mode,
4. narrow viewport with TOC panel open.

Save screenshots of **failing** states to disk (`save_to_disk: true`) so they can be attached to the report.

## Step 6: Report and teardown

Report in chat as markdown:

- Header: workspace path, base URL, pages tested, viewport sizes used.
- One table: check id | page | PASS/FAIL | detail (verbatim `detail` from the check — it names occluders, coordinates, HTTP codes).
- Failing-state screenshots.
- Anything the visual pass flagged that no check covers (candidate for a new check in `checks.js`).

Then stop the background bridge task and confirm teardown in the report (no orphan `assistant-bridge.py` process).

## Anti-patterns

- Never test against `file://` — the assistant, podcast polling, and API checks need the bridge's HTTP origin.
- Never leave deep mode, an open panel, or a scrolled position behind between checks; if a check crashed mid-way, reload the page and re-inject before continuing.
- Never mark the run green if a check was skipped due to an injection or navigation error — report it as FAIL with the error.
