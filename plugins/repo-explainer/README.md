# repo-explainer

A Claude Code plugin that turns any git repository into a self-contained local documentation website. Point it at one or more repos and it clones them, asks how you want the docs (language, business or business + technical, and the technical depth), analyzes the actual source, writes the documentation pages, and serves them locally with an embedded AI assistant that can deep-research the clone and write findings back into the docs.

## Install

```
/plugin marketplace add yustme/repo-explainer
/plugin install repo-explainer
```

During development you can also add the marketplace from a local path:

```
/plugin marketplace add /Users/vojtatuma/repos/repo-explainer
/plugin install repo-explainer
```

## Usage

```
/explain-repo <git-url> [more-git-urls ...]
```

A git URL (https or ssh) or a local path works. Pass several to get one docsite with a repo switcher. If you omit the URL, the plugin asks for one.

You will be asked:
- **Language** — the language the documentation is written in (English by default; your locale's language is offered too).
- **Scope** — business only, or business + technical.
- **Depth** (technical only) — high-level overview, detailed technical deep-dive, or rebuild-from-scratch build guide.

## What gets generated

Everything lands in a workspace at `~/repo-explains/<slug>/`:

- `src/<slug>/` — the cloned repository source.
- `index.html` plus per-repo `*-business.html` / `*-technical.html` — a self-contained docsite (CSS and JS inlined, no external resources).
- `config.json` — site config (repos, pages, language, models, the assistant `world` description).
- `logs/assistant.jsonl` — assistant activity log.

The docsite opens in your browser automatically when generation finishes.

## The assistant

Every page carries an embedded AI assistant:

- **Explain** — select any text for a concise explanation; toggle **Deep research** to have the assistant read the real clone and answer with file-grounded detail.
- **Integrate** — turn an answer into a styled documentation block, refine it, and apply it to either the docsite or the source repo's own docs (README / `docs/`) — always with a timestamped backup.

This makes the generated site living documentation: keep researching and folding findings back in.

## Requirements

- Claude Code CLI available on PATH as `claude` (the assistant shells out to it).
- `python3` (standard library only — no third-party packages).
- `git` (and `gh` or configured credentials for private repos).
