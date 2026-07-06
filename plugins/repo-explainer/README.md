# repo-explainer

A Claude Code plugin that turns any git repository into a self-contained local documentation website. Point it at one or more repos and it clones them, asks how you want the docs (language, business or business + technical, and the technical depth), analyzes the actual source, writes the documentation pages, and serves them locally with an embedded AI assistant that can deep-research the clone and write findings back into the docs.

## Install

```
/plugin marketplace add yustme/repo-explainer
/plugin install repo-explainer
```

During development you can also add the marketplace from a local path:

```
/plugin marketplace add /path/to/repo-explainer
/plugin install repo-explainer
```

## Usage

```
/explain-repo <git-url> [more-git-urls ...]
```

A git URL (https or ssh) or a local path works. Pass several to get one docsite with a repo switcher. If you omit the URL, the plugin asks for one.

```
/test-docsite [workspace-path]
```

Runs a UI smoke test on a generated docsite (defaults to the newest workspace): drives the served site in your Chrome, asserts navigation, TOC, assistant panel (incl. deep/fullscreen layering), select-to-Explain, podcast player and diagrams, and reports a PASS/FAIL table. Requires the claude-in-chrome extension.

You will be asked:
- **Language** — the language the documentation is written in (English by default; your locale's language is offered too).
- **Scope** — business only, or business + technical.
- **Depth** (technical only) — high-level overview, detailed technical deep-dive, or rebuild-from-scratch build guide.
- **Concepts vs. code** (technical only) — conceptual prose, verbatim code, or both.
- **Animated diagrams** — whether to render inline animated flow/architecture diagrams.
- **Podcast** — optionally produce a two-host audio episode that explains the whole topic as a story, in a language of your choice (your system language by default — independent of the docs language).

## What gets generated

Everything lands in a workspace at `~/repo-explains/<slug>/`:

- `src/<slug>/` — the cloned repository source.
- `index.html` plus per-repo `*-business.html` / `*-technical.html` — a self-contained docsite (CSS and JS inlined, no external resources).
- `config.json` — site config (repos, pages, language, models, the assistant `world` description).
- `logs/assistant.jsonl` — assistant activity log.
- *(if a podcast was requested)* `podcast/script.txt` (the two-host script), `<slug>-podcast.mp3` (the episode), and `podcast-progress.json` (synthesis progress the in-page player polls).

The docsite opens in your browser automatically when generation finishes.

## Podcast (optional)

If you opt in, the `podcast` skill composes a two-host episode that explains the whole topic as a listenable story and embeds an audio player into the docsite. The script follows an explainer composition (hook → learning promise → big-picture-first → dependency-ordered learning blocks with analogies and mini-recaps → synthesis → takeaways). Audio is synthesized locally with an open-source engine (Coqui **XTTS-v2** by default, with macOS `say` as a fallback), and foreign/technical terms are phonetically respelled for the target language so they are pronounced correctly. Synthesis runs in the background; the embedded player shows live progress and swaps in the finished episode automatically.

## The assistant

Every page carries an embedded AI assistant:

- **Explain** — select any text for a concise explanation; toggle **Deep research** to have the assistant read the real clone and answer with file-grounded detail.
- **Integrate** — turn an answer into a styled documentation block, refine it, and apply it to either the docsite or the source repo's own docs (README / `docs/`) — always with a timestamped backup.

This makes the generated site living documentation: keep researching and folding findings back in.

## Requirements

- Claude Code CLI available on PATH as `claude` (the assistant shells out to it).
- `python3` (standard library only — no third-party packages — for the docsite and server).
- `git` (and `gh` or configured credentials for private repos).
- **Podcast only (optional):** `ffmpeg` on PATH, plus a TTS engine — Coqui `coqui-tts` with `transformers>=4.57,<5`, `torch`, `torchaudio`, `torchcodec` (install into an isolated venv; the `podcast` skill documents the setup), or macOS `say` as a no-install fallback.
