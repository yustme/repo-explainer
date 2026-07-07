# Maintaining & distributing the `repo-explainer` plugin

This repo is a **Claude Code plugin marketplace** that ships one plugin (`repo-explainer`), which
provides the skills. Below: how users install it, how to release updates, and how to work on each
part.

## Repo layout

```
.
├── .claude-plugin/
│   └── marketplace.json                    # marketplace catalog (repo root)
├── plugins/
│   └── repo-explainer/                      # the plugin
│       ├── .claude-plugin/
│       │   └── plugin.json                  # plugin manifest (bump version to release)
│       ├── README.md                        # plugin-level docs
│       ├── commands/
│       │   ├── explain-repo.md              # /explain-repo — generate the docsite
│       │   └── test-docsite.md              # /test-docsite — UI smoke test
│       ├── skills/
│       │   ├── explain-repo/SKILL.md        # orchestration playbook
│       │   ├── analyze-repo/SKILL.md        # how to read and understand the source
│       │   ├── docsite/SKILL.md             # how to fill pages + run the server
│       │   ├── review-docs/SKILL.md         # mandatory editorial pass
│       │   ├── podcast/SKILL.md             # optional two-host audio episode
│       │   └── test-docsite/SKILL.md        # UI smoke-test procedure
│       ├── scripts/
│       │   ├── scaffold.py                  # builds the self-contained docsite
│       │   ├── podcast_tts.py               # optional podcast synthesis pipeline
│       │   └── test_podcast_tts.py
│       └── assets/
│           ├── bridge/assistant-bridge.py   # local server + embedded assistant API
│           ├── template/                    # inlined HTML/CSS/JS for the docsite
│           └── test/checks.js               # deterministic UI assertions
├── scripts/
│   └── build_skill.py                       # plugin -> standalone Agnes skill bundle
├── .github/workflows/build-skill.yml        # CI: build + validate + attach to releases
├── Makefile                                 # `make skill` / `make upload`
├── requirements.txt                         # deps for scripts/ + optional podcast
└── MAINTAINING.md
```

Skills reference their bundled scripts/assets through `$PLUGIN_PATH` (set by Claude Code at runtime),
never through absolute paths — see the constraints below.

## Installing (for users)

```bash
/plugin marketplace add yustme/repo-explainer
/plugin install repo-explainer@repo-explainer-kit
```

The commands `/explain-repo` and `/test-docsite` then become available. `/plugin list` shows what is
installed.

## Releasing an update

The marketplace serves the plugin straight from this repo — there is nothing to package. To publish
a change:

1. Edit the skill / manifests, commit, and push to `main`.
2. **Bump `version`** in `plugins/repo-explainer/.claude-plugin/plugin.json` (semver). Clients key
   updates off this — if you don't bump it, installs won't see the change.
3. Users update with `/plugin marketplace update repo-explainer-kit` (or reinstall).

## Building the standalone skill bundle

The plugin (multi-skill, uses `$PLUGIN_PATH`, sibling-skill delegation) is not directly uploadable
as a single skill. `scripts/build_skill.py` flattens it into **one self-contained skill**:

- the `explain-repo` skill becomes the root `SKILL.md` (orchestration);
- the other skills become `references/*.md`;
- `scripts/` and `assets/` are copied in;
- plugin-only conventions are rewritten: `$PLUGIN_PATH/...` → relative paths, and
  ``the `docsite` skill`` → `references/docsite.md`, etc.;
- the frontmatter `description` is emitted as a **single line** (required — see below).

It then validates (no leftover `$PLUGIN_PATH`, no stray `` `<skill>` skill `` refs, description
length/shape, bundled files present) and packages `dist/repo-explainer.skill`.

```bash
make skill          # build + validate + package -> dist/repo-explainer.skill
make upload         # build, then publish to Agnes (needs `agnes` on PATH + `agnes auth login`)
make clean          # remove build/ and dist/
```

CI (`.github/workflows/build-skill.yml`) runs the same build on every push/PR and attaches the
`.skill` to a GitHub Release when a `v*` tag is pushed. `build/` and `dist/` are gitignored — the
bundle is always generated, never committed.

The **source of truth is the plugin**. Never hand-edit `build/` or the uploaded bundle; change the
plugin skills and rebuild. If you add or rename a skill, update `REFERENCE_SKILLS` and the reference
index in `build_skill.py`'s `HEAD_BODY` (the build warns if they drift).

## Publishing to Agnes (the Flea Market contract)

Agnes hosts skills in its "Flea Market", uploaded with the local CLI:

```bash
agnes auth login
agnes store upload skill dist/repo-explainer.skill \
  --name repo-explainer \
  --description "<>= 60 chars, single line, no ': '>" \
  --category Documentation
# in-place edit later (keeps the entity id):
agnes store update <entity-id> --zip dist/repo-explainer.skill
```

Hard-won requirements (each one blocked an upload during bring-up):

- **`type skill` bundle must NOT contain `.claude-plugin/plugin.json`** — a manifest at the root
  makes the server reject it as `zip_looks_like_plugin`. (Upload the *plugin* repo as `type plugin`
  if you ever want that; the skill bundle is manifest-free.)
- **The `SKILL.md` `description` must be a single line.** Agnes' frontmatter parser is line-based:
  a folded `description: >` block is read as the literal `">"` and rejected as `too_short`. Also keep
  it free of `": "` (colon+space) so it stays valid YAML for other tools. `build_skill.py` enforces
  and emits this.
- **Descriptions have a mechanical floor:** ≥ 60 characters and ≥ 5 distinct words, no placeholder
  text (`TODO`, `TBD`, `lorem ipsum`, unfilled `{{var}}`). Applies to the `--description` tile *and*
  the `SKILL.md` frontmatter.
- **`--category` must be from the fixed taxonomy:** `Code & Engineering`, `Data & Analytics`,
  `Documentation`, `Productivity`, `Communication`, `DevOps & Infra`, `Security`, `Research`, `Other`.
- After upload the entity goes through an **async LLM review**; `agnes store update` returns
  `409 prior_version_pending` until that verdict lands. Wait, then retry.

## Non-negotiable constraints (don't break these)

- **Standalone.** The plugin must run in any environment where it is installed, using only its own
  bundled files (`$PLUGIN_PATH/...`) plus the user's local git/tooling. No hardcoded absolute paths,
  no single-machine sources at runtime.
- **No personal info baked in.** Keep the skills and examples generic — no real customer, company, or
  user names. Author metadata in the manifests is the only intended identifier.
- **Grounded, never invented.** Every skill enforces the same rule: no factual/technical claim that
  the analyzed source does not support. Editorial review (`review-docs`) is a separate, mandatory
  pass — keep it independent (a different model from the writer).
- **Self-contained output.** Generated pages inline all CSS/JS and add no external stylesheets, fonts,
  scripts, or images (CSP-safe). The core generator uses the Python standard library only.

## Updating each part of the skill

- **Overall flow / the interview questions / step order** → `skills/explain-repo/SKILL.md`.
- **How the source is read and understood** (depth modes, topic discovery, flow capture) →
  `skills/analyze-repo/SKILL.md`.
- **Page content conventions, design components, animated diagrams, config.json, running the server**
  → `skills/docsite/SKILL.md`.
- **The editorial rubric and edit-vs-report policy** → `skills/review-docs/SKILL.md`.
- **Podcast composition, TTS engines, embedding the player** → `skills/podcast/SKILL.md`.
- **UI test matrix and assertions** → `skills/test-docsite/SKILL.md` (assertions live in
  `assets/test/checks.js`).
- **Docsite look & behavior** → `assets/template/` (HTML/CSS/JS) and `assets/bridge/assistant-bridge.py`.

Frontmatter rules for every `SKILL.md`: keep `name:` equal to the skill folder name; use top-level
`allowed-tools:` and `model:` (a nested `metadata:` block is silently ignored by Claude Code); avoid a
bare `": "` (colon+space) inside a folded `description:` value, as it breaks YAML.

## Maintainer scripts

`scripts/` and `assets/` are shipped with the plugin, but the tests and the podcast synthesis stack
are build/optional-time only. Run the tests:

```bash
pip install -r requirements.txt
cd plugins/repo-explainer && python -m pytest -q
```

The podcast TTS dependencies are heavy (~2 GB) and only needed to work on `podcast_tts.py`; install
them into an isolated venv as documented in the `podcast` skill.

Quick self-check before shipping — make sure no personal or vendor-specific identifiers slipped in:

```bash
git grep -niE "/Users/|<your-username>|<customer>|<company>" -- plugins && echo "FOUND — remove it" || echo "clean"
```
