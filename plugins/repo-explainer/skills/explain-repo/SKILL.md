---
name: explain-repo
description: >
  Generate a local documentation website explaining one or more git repositories, with an embedded
  AI assistant. Use when the user wants to understand or explain a repo or set of repos — "explain
  this repo", "document this codebase", "help me onboard to X", or passes one or more git URLs.
metadata:
  tools: "Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, Task"
  model: sonnet
---

# Explain a Repository

This is the orchestration playbook. It clones repo(s), asks the user how they want the docs, scaffolds a self-contained docsite, drives analysis and writing, then serves the result with an embedded AI assistant.

Bundled scripts and assets are located with `$PLUGIN_PATH` (set by Claude Code when running inside the plugin). Always reference them as `$PLUGIN_PATH/scripts/...` and `$PLUGIN_PATH/assets/...`.

## Step 1: Collect the repo URL(s)

The URL(s) arrive as `$ARGUMENTS` from the `/explain-repo` command. Each argument is a git URL (https or ssh) or a local path.

- If none were provided, ask the user for at least one git URL or local path.
- Accept multiple — they become one docsite with a repo switcher (see Step 7).

## Step 2: Derive the workspace

For each repo, derive a `slug` from the URL: take the last path segment, strip a trailing `.git`, lowercase it, and replace any non-alphanumeric run with a single hyphen. Example: `https://github.com/acme/widget-svc.git` -> `widget-svc`.

The default workspace directory is `~/repo-explains/<slug>/` (use the first repo's slug for multi-repo sites). Do not create it yourself — `scaffold.py` creates it and clones into `<workspace>/src/<slug>`.

## Step 3: Ask the user (AskUserQuestion)

Ask these, in order. Skip the depth question entirely if scope is business-only.

1. **Language** — the language the documentation content is written in.
   - Default option: **English** (`en`).
   - Also offer the user's home language detected from the environment locale (`$LANG` / `$LC_ALL`, e.g. `cs_CZ` -> Czech `cs`). The user here is Czech, so offer Czech as a second option.
   - Offer **Other** so the user can name a different language.
   - Store the resulting code (e.g. `en`, `cs`) for `--lang`.

2. **Scope** — what to document.
   - `business` — plain-language docs for non-engineers.
   - `business+technical` — business docs plus a technical track.

3. **Depth** — only if scope includes technical. Exactly three modes:
   - **high-level** — a short technical overview (architecture at a glance, main components, stack, data flow in broad strokes).
   - **detailed** — a full technical deep-dive (modules, interfaces, data/control flow, patterns, with real file references).
   - **rebuild-from-scratch** — a sequential, block-by-block guide to building the project yourself, grounded in how the real repo does it.

   Carry the chosen depth into the analysis step (it controls how much source gets read).

## Step 4: Scaffold

Run the scaffold script. It clones (or copies a local path), inlines the template CSS/JS into self-contained pages, generates the page skeletons with a `<!-- REPO_EXPLAINER:CONTENT -->` placeholder inside `<main>`, and writes `config.json`.

```bash
python3 "$PLUGIN_PATH/scripts/scaffold.py" \
  --workspace ~/repo-explains/<slug> \
  --title "<Human title, e.g. Acme — repo docs>" \
  --lang <code> \
  --scope <business|business+technical> \
  --repo <slug>=<git-url-or-local-path> \
  [--repo <slug2>=<url2> ...]
```

The script prints a single JSON line to stdout:
`{"workspace": "...", "pages": ["...html", ...], "config": "config.json"}`.
Parse it to learn the workspace path and the exact page filenames you must fill.

If `git clone` fails (private repo, missing auth, bad URL), tell the user to check their git / `gh` authentication for that host and retry. Do not fabricate content for a repo that did not clone.

## Step 5: Analyze the clone

Delegate the source analysis to the **`analyze-repo`** skill. Point it at `<workspace>/src/<slug>` and pass the chosen scope and depth. It reads the source (reading scales with depth) and returns structured notes for the business track and, if requested, the technical track. The hard rule it enforces: never invent — every nontrivial claim is grounded in actual files, with file paths cited.

For multiple repos, analyze each clone separately.

## Step 6: Write the docsite + refine config

Delegate content writing to the **`docsite`** skill. It replaces each page's `<!-- REPO_EXPLAINER:CONTENT -->` placeholder (via Edit) with documentation written in the chosen language, using the design components in the inlined styles.

After analysis, refine `config.json` `world` to a single accurate one-line description of the repo (it is used in the assistant's prompts). The scaffold writes only a stub.

## Step 7: Start the server and open it

Start the bridge in the background — it serves the workspace, picks a free port, and exposes the assistant API:

```bash
python3 "$PLUGIN_PATH/assets/bridge/assistant-bridge.py" <workspace>
```

It prints exactly one line: `RUNNING http://localhost:<PORT>/index.html`. Capture that URL from the background process output, then open it:

```bash
open "http://localhost:<PORT>/index.html"   # macOS; use xdg-open on Linux
```

Run the bridge in the background so it keeps serving while the session continues. To stop it later, kill the background process / task.

## Step 8: Hand off to the user

Tell the user:
- the URL the docsite is running on,
- that they can select any text and click **Explain** for a concise answer, or toggle **Deep research** to have the assistant read the actual clone (`Read`/`Grep`/`Glob` over `<workspace>/src/<slug>`),
- that under any answer they can **Integrate** the finding — proposing a styled block they can refine and approve, written into either this docsite or the source repo's own docs (README / docs/), always with a timestamped backup.

## Multi-repo

Pass multiple `--repo <slug>=<url>` flags to a single scaffold run. The result is one docsite with a repo switcher in the topbar and Business / Technical view switches per repo. Analyze and write each repo's pages independently, but keep one shared `config.json`.

## Failure handling

- **Clone fails** — check git/`gh` auth for the host, confirm the URL, retry. Skip a repo only with the user's agreement.
- **Scaffold prints no JSON / errors** — surface stderr to the user; do not proceed to analysis.
- **Bridge does not print `RUNNING ...`** — check stderr; ensure the `claude` CLI is on PATH (the assistant shells out to it) and that python3 is available.
