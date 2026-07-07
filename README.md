# repo-explainer

A [Claude Code](https://claude.com/claude-code) plugin marketplace shipping one plugin:
**`repo-explainer`** — generate a self-contained local documentation website that explains any
git repository (or a set of them) in business and technical terms, with an embedded AI assistant
that can deep-research the cloned source and write findings back.

Point it at a repo and it clones the source, interviews you about what you want (language, scope,
depth, animated diagrams, optional audio podcast), analyzes the actual code, writes the docs,
runs a mandatory editorial review, and serves the result — a living docsite you can keep asking
questions of.

## Install

```
/plugin marketplace add yustme/repo-explainer
/plugin install repo-explainer@repo-explainer-kit
```

Then run `/explain-repo <git-url>` (or just `/explain-repo` and it will ask for one).

## Update

```
/plugin marketplace update repo-explainer-kit
```

## What it does

1. Clones the repo(s) into a workspace under `~/repo-explains/<slug>/`.
2. Asks you a few questions — documentation language, scope (business / business + technical),
   depth, animated diagrams, and an optional two-host audio podcast.
3. Scaffolds a self-contained docsite (CSS/JS inlined, no external resources).
4. Analyzes the cloned source and writes the documentation, grounded only in the real code.
5. Runs a mandatory editorial review (an independent editor agent) before serving.
6. Optionally produces a two-host audio podcast that explains the whole topic as a story.
7. Starts a local server and opens the docsite, with an embedded assistant for follow-up research.

It never invents facts — every nontrivial claim is grounded in an actual file, with the path cited.

## Commands

- `/explain-repo [git-url ...]` — generate the docsite.
- `/test-docsite [workspace-path]` — UI smoke test of a generated docsite (requires the
  claude-in-chrome extension).

## Maintaining

See [MAINTAINING.md](MAINTAINING.md) — repo layout, release process, and how to update each skill.

## License

[MIT](LICENSE)
