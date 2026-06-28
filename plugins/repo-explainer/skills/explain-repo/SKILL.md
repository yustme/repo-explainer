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

4. **Concepts vs. code** — only if scope includes technical. This is orthogonal to depth: depth sets *how much* is covered, this sets *how it is explained*. Three options:
   - **concepts** — stay at the level of logic and ideas: what each part does, how the pieces fit, the flow and the "why". Explain concepts and mechanisms in prose; minimal raw code (only the rare snippet that's unavoidable). For readers who want to understand the system without reading code.
   - **code** — go into the actual code: real signatures, key snippets shown verbatim (`.code` / `.prompt` blocks), file-by-file specifics, concrete identifiers and routes. For readers who will work in the codebase.
   - **both** — explain the concept first, then drop into the code that implements it. The fullest treatment.

   Carry this choice into the analysis (Step 6) and writing (Step 7) — it governs how much verbatim source vs. conceptual prose the technical track contains. It does not apply to the business track (always conceptual).

5. **Animated diagrams** — a simple yes/no. Ask regardless of scope.
   - **Yes** — generate animated flow diagrams that show how the project works: data/control flows, request lifecycles, build/run sequences, architecture interactions. They are inline, self-contained, JS-free CSS/SVG (see the `docsite` skill's diagram components) and also enabled in the in-page assistant.
   - **No** — text-and-cards documentation only.
   - Store the result as `animated` or `none` for `--visuals`. The analysis decides *which* flows merit a diagram; this toggle only turns the capability on or off.

6. **Anything specific to dig into?** — finally, ask the user one open, free-text question (not fixed choices): *"Is there anything specific you'd like explained in more depth that we haven't already covered?"* Phrase it in the chosen documentation language. This catches a concrete interest the earlier questions didn't surface (a particular subsystem, concept, integration, or "how does X actually work").
   - If the user names something, treat it as a **must-cover focus**: carry it into topic discovery (Step 5) as a pre-selected topic and into the analysis (Step 6) as a required deep-dive, even if it wasn't among the auto-discovered topics.
   - If the user says "no" / leaves it empty, proceed normally.

## Step 4: Scaffold

Run the scaffold script. It clones (or copies a local path), inlines the template CSS/JS into self-contained pages, generates the page skeletons with a `<!-- REPO_EXPLAINER:CONTENT -->` placeholder inside `<main>`, and writes `config.json`.

```bash
python3 "$PLUGIN_PATH/scripts/scaffold.py" \
  --workspace ~/repo-explains/<slug> \
  --title "<Human title, e.g. Acme — repo docs>" \
  --lang <code> \
  --scope <business|business+technical> \
  --visuals <none|animated> \
  --repo <slug>=<git-url-or-local-path> \
  [--repo <slug2>=<url2> ...]
```

Pass `--visuals animated` only if the user said yes to animated diagrams in Step 3; otherwise `--visuals none` (the default). The value is stored in `config.json` and read by both the writing step and the in-page assistant.

The script prints a single JSON line to stdout:
`{"workspace": "...", "pages": ["...html", ...], "config": "config.json"}`.
Parse it to learn the workspace path and the exact page filenames you must fill.

If `git clone` fails (private repo, missing auth, bad URL), tell the user to check their git / `gh` authentication for that host and retry. Do not fabricate content for a repo that did not clone.

## Step 5: Discover topics and let the user pick which to deep-dive

Before the full analysis, do a quick discovery pass over the clone and surface **the topics the repo deals with**, so the user can interactively choose which ones to elaborate in depth (e.g. for a Keboola repo, "what is a semantic layer" is a topic the user may want explained thoroughly). See the `analyze-repo` skill's **Topic discovery** section for how to extract them.

- Extract both **domain/conceptual** topics (e.g. "semantic layer", "Keboola Metastore", "AI-assisted classification") and **technical** topics (e.g. "Express proxy auth with the master token", "relationship graph layout"). Each topic = a short label + a one-line description, grounded in the repo.
- Present them for selection with **multiSelect `AskUserQuestion`**. Because each question allows at most 4 options, group the topics into 1–4 thematic groups (≤4 per group, ≤16 total) — e.g. headers "Domain", "Technical", "Integration". Prioritize the most central topics; if there are more than ~16, keep the most important and tell the user the rest can still be asked later via the in-page assistant (do not hide the cap).
- The user's selected topics become **dedicated, deeper sections** in the docs (Step 7). Unselected topics still get brief coverage in the normal flow. If the user selects nothing, proceed with standard depth and no dedicated topic sections.
- If the user named a specific interest in Step 3's open question (question 6), **pre-select it** here (add it as an already-checked topic, creating one for it if discovery missed it) so it is guaranteed a dedicated deep-dive.

Keep the chosen topic list (label + which page it belongs to) for the next steps.

## Step 6: Analyze the clone

Delegate the source analysis to the **`analyze-repo`** skill. Point it at `<workspace>/src/<slug>` and pass the chosen scope, depth, the **concepts-vs-code** choice (`concepts` / `code` / `both`), **the selected topics**, the **visuals** choice (`animated` / `none`), and the user's **Step 3 open-question focus** (question 6) if any. It reads the source (reading scales with depth; selected topics and the named focus get extra, focused reading) and returns structured notes for the business track and, if requested, the technical track, plus a grounded deep-dive for each selected topic. When visuals are `animated`, it also returns **flow specs** — the key flows worth visualizing, captured structurally and grounded in files (see `analyze-repo`'s "Flow capture" section). The hard rule it enforces: never invent — every nontrivial claim is grounded in actual files, with file paths cited.

For multiple repos, analyze each clone separately.

## Step 7: Write the docsite + refine config

Delegate content writing to the **`docsite`** skill. It replaces each page's `<!-- REPO_EXPLAINER:CONTENT -->` placeholder (via Edit) with documentation written in the chosen language, using the design components in the inlined styles. The technical track follows the **concepts-vs-code** choice: `concepts` = conceptual prose with minimal raw code, `code` = lots of verbatim `.code` / `.prompt` source blocks and concrete identifiers, `both` = concept first then the implementing code. Each **selected topic** is rendered as its own dedicated deep-dive section (with an anchor), on the page it best fits, and surfaced as a card/link near the top of that page (and on the hub). When `config.json` `visuals` is `animated`, it renders the analysis's flow specs as **animated diagrams** (the `.flow` / `.diagram` components) at the points in the docs where each flow is explained — see the `docsite` skill's "Animated diagrams" section.

After analysis, refine `config.json` `world` to a single accurate one-line description of the repo (it is used in the assistant's prompts). The scaffold writes only a stub.

## Step 8: Editorial review (mandatory)

Before serving, run a mandatory editorial pass with the **`review-docs`** skill. Delegate it to a **separate agent that uses a different model than the one(s) that wrote the pages** (independence avoids self-preference bias — e.g. if writing ran on the larger model, review on `sonnet`). Pass it the generated page files, the workspace `config.json`, and the clone path.

It reads each page, works out what it is about, scores it against the editorial rubric (accuracy/grounding, coherence, clarity, structure, completeness, diagram fidelity, terminology, audience fit, readability), **fixes clear, source-grounded issues in place** (only within the content markers), and **reports** anything needing a human (suspected inaccuracies, missing content, judgment calls). It never invents claims and never touches chrome/`<script>`/`<style>`. The pass is bounded to a couple of iterations per page.

Relay the editor's report to the user as part of the hand-off: what it fixed and anything it flagged. For multiple repos, review every generated page.

## Step 9: Start the server and open it

Start the bridge in the background — it serves the workspace, picks a free port, and exposes the assistant API:

```bash
python3 "$PLUGIN_PATH/assets/bridge/assistant-bridge.py" <workspace>
```

It prints exactly one line: `RUNNING http://localhost:<PORT>/index.html`. Capture that URL from the background process output, then open it:

```bash
open "http://localhost:<PORT>/index.html"   # macOS; use xdg-open on Linux
```

Run the bridge in the background so it keeps serving while the session continues. To stop it later, kill the background process / task.

## Step 10: Hand off to the user

Tell the user:
- the URL the docsite is running on,
- a short summary of the editorial review (Step 8): what was fixed and anything flagged for their attention,
- which topics got a dedicated deep-dive section (and that any other topic can still be explored via the assistant),
- if visuals are `animated`, that the docs include animated flow diagrams and the assistant can produce more on demand,
- that they can select any text and click **Explain** for a concise answer, or toggle **Deep research** to have the assistant read the actual clone (`Read`/`Grep`/`Glob` over `<workspace>/src/<slug>`),
- that under any answer they can **Integrate** the finding — proposing a styled block they can refine and approve, written into either this docsite or the source repo's own docs (README / docs/), always with a timestamped backup.

## Multi-repo

Pass multiple `--repo <slug>=<url>` flags to a single scaffold run. The result is one docsite with a repo switcher in the topbar and Business / Technical view switches per repo. Analyze and write each repo's pages independently, but keep one shared `config.json`.

## Failure handling

- **Clone fails** — check git/`gh` auth for the host, confirm the URL, retry. Skip a repo only with the user's agreement.
- **Scaffold prints no JSON / errors** — surface stderr to the user; do not proceed to analysis.
- **Bridge does not print `RUNNING ...`** — check stderr; ensure the `claude` CLI is on PATH (the assistant shells out to it) and that python3 is available.
