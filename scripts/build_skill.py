#!/usr/bin/env python3
"""Build a standalone Agnes-compatible skill bundle from the Claude Code plugin.

The plugin under ``plugins/repo-explainer/`` is the single source of truth. This
script flattens its multi-skill layout into ONE self-contained skill:

    repo-explainer/
    ├── SKILL.md          # orchestration (from the explain-repo skill) + reference index
    ├── references/       # the other skills, as reference playbooks
    ├── scripts/          # scaffold.py, podcast_tts.py
    └── assets/           # bridge/, template/, test/

It rewrites the plugin-only conventions so the result runs standalone:
  * ``$PLUGIN_PATH/...`` → relative paths (``scripts/...``, ``assets/...``)
  * ``the `docsite` skill`` and friends → ``references/docsite.md`` etc.
  * a single-line ``description:`` in the frontmatter (Agnes' frontmatter parser
    is line-based and reads a folded ``>`` block as the literal ">" — see
    MAINTAINING.md "Publishing to Agnes").

Then it validates the result and zips it to ``dist/repo-explainer.skill``.
With ``--upload`` it publishes to the Agnes Flea Market via the ``agnes`` CLI.

Usage:
    python scripts/build_skill.py               # build + validate + package
    python scripts/build_skill.py --upload       # also push to agnes
    python scripts/build_skill.py --format zip    # emit .zip instead of .skill

Standard library only (no third-party deps), so it runs the same locally and in CI.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

# --- Layout -----------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_DIR = REPO_ROOT / "plugins" / "repo-explainer"
SKILLS_DIR = PLUGIN_DIR / "skills"
BUILD_ROOT = REPO_ROOT / "build"
DIST_DIR = REPO_ROOT / "dist"

SKILL_NAME = "repo-explainer"
ORCHESTRATOR = "explain-repo"                       # its SKILL.md becomes the root SKILL.md
REFERENCE_SKILLS = ["analyze-repo", "docsite", "review-docs", "podcast", "test-docsite"]

# Agnes marketplace tile metadata (used by --upload).
AGNES_CATEGORY = "Documentation"

# Single-line description. MUST stay one line and contain no ": " (colon+space):
# Agnes parses frontmatter line-by-line and real YAML rejects a plain scalar with
# an embedded colon. Keep it >= 60 chars and >= 5 distinct words.
SKILL_DESCRIPTION = (
    "Generate a self-contained local documentation website that explains one or more "
    "git repositories in business and technical terms, with an embedded AI assistant, "
    "animated diagrams, and an optional two-host audio podcast. Use when someone wants "
    "to understand, explain, document, or onboard to a repo or set of repos, or passes "
    "one or more git URLs or local repo paths. Everything is grounded in the actual "
    "source and never invented."
)

# --- Templates --------------------------------------------------------------

HEAD_BODY = """
# Explain a Repository

This is the orchestration playbook. It clones repo(s), asks the user how they want the docs, scaffolds a self-contained docsite, drives analysis and writing, runs a mandatory editorial review, then serves the result with an embedded AI assistant (and, optionally, a podcast).

This skill bundles everything it needs alongside `SKILL.md`: helper playbooks under `references/`, executable helpers under `scripts/`, and the docsite files under `assets/`. Reference them by their relative path from this skill's directory (`scripts/...`, `assets/...`, `references/...`).

## Reference playbooks (read the relevant one when its step is reached)

- `references/analyze-repo.md` — how to read and understand the cloned source (depth modes, topic discovery, flow capture). Used in Steps 5-6.
- `references/docsite.md` — page-content conventions, design components, animated diagrams, `config.json`, and running the local server. Used in Steps 7 and 10.
- `references/review-docs.md` — the editorial rubric and edit-vs-report policy for the mandatory review. Used in Step 8.
- `references/podcast.md` — composing a two-host episode, TTS synthesis, embedding the player. Used in Step 9 (only if the user opts in).
- `references/test-docsite.md` — optional UI smoke test of the served docsite (needs local Chrome via claude-in-chrome). See "Optional: smoke-test the UI" at the end.

When a step says "delegate to `references/X.md`", read that playbook and follow it — for heavy or independent work (analysis, writing, the editorial review) prefer spawning a subagent with the Task tool and handing it the playbook, so the main context stays lean. The editorial review **must** run on a different model than the writer (see Step 8).

"""

TAIL_BODY = """
## Optional: smoke-test the UI

After the site is served, you can verify the UI actually works (navigation, TOC, assistant panel, deep/fullscreen layering, select-to-Explain, podcast player, diagrams) by following `references/test-docsite.md`. It drives the served site in the user's Chrome via the claude-in-chrome tools and reports a PASS/FAIL table. This requires a local Chrome with the claude-in-chrome extension — skip it in environments without one.
"""

# Ordered replacements for the orchestrator body (from "## Step 1" onward).
ORCH_REPLACEMENTS = [
    ('"$PLUGIN_PATH/scripts/', '"scripts/'),
    ('"$PLUGIN_PATH/assets/', '"assets/'),
    ("$PLUGIN_PATH/scripts/", "scripts/"),
    ("$PLUGIN_PATH/assets/", "assets/"),
    ("the **`analyze-repo`** skill", "`references/analyze-repo.md`"),
    ("the **`docsite`** skill", "`references/docsite.md`"),
    ("the **`review-docs`** skill", "`references/review-docs.md`"),
    ("the **`podcast`** skill", "`references/podcast.md`"),
    ("the `analyze-repo` skill's **Topic discovery** section",
     "`references/analyze-repo.md` (see **Topic discovery**)"),
    ("`analyze-repo`'s", "`references/analyze-repo.md`'s"),
    ("the `docsite` skill's", "`references/docsite.md`'s"),
    ("embedded as a player in the docsite. See the `podcast` skill.",
     "embedded as a player in the docsite. See `references/podcast.md`."),
    ("the TTS voice/phonetic-respelling rules in the `podcast` skill.",
     "the TTS voice/phonetic-respelling rules in `references/podcast.md`."),
    ("The `podcast` skill (a) composes",
     "The podcast step (`references/podcast.md`) (a) composes"),
    ("`$ARGUMENTS` from the `/explain-repo` command", "arguments when the skill is invoked"),
]

# Ordered replacements for each reference file. Skill-suffixed forms first so the
# bare-token pass doesn't leave a stray "skill".
REF_REPLACEMENTS = [
    ("$PLUGIN_PATH/scripts/", "scripts/"),
    ("$PLUGIN_PATH/assets/", "assets/"),
    ('"$PLUGIN_PATH/', '"'),
    ("`$PLUGIN_PATH`", "this skill's directory"),
    ("`analyze-repo` skill", "`references/analyze-repo.md`"),
    ("`docsite` skill", "`references/docsite.md`"),
    ("`review-docs` skill", "`references/review-docs.md`"),
    ("`test-docsite` skill", "`references/test-docsite.md`"),
    ("`analyze-repo`", "`references/analyze-repo.md`"),
    ("`docsite`", "`references/docsite.md`"),
    ("`review-docs`", "`references/review-docs.md`"),
    ("`explain-repo`", "the orchestration (`SKILL.md`)"),
]

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


# --- Helpers ----------------------------------------------------------------

def strip_frontmatter(text: str) -> str:
    return FRONTMATTER_RE.sub("", text, count=1)


def apply(replacements, text: str) -> str:
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def die(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


# --- Build ------------------------------------------------------------------

def build() -> Path:
    if not SKILLS_DIR.is_dir():
        die(f"plugin skills dir not found: {SKILLS_DIR}")

    present = {p.name for p in SKILLS_DIR.iterdir() if p.is_dir()}
    expected = set(REFERENCE_SKILLS) | {ORCHESTRATOR}
    if present != expected:
        # Not fatal, but the reference index in HEAD_BODY is curated — warn loudly.
        print(f"WARNING: plugin skills {sorted(present)} != expected {sorted(expected)}; "
              f"update REFERENCE_SKILLS and the reference index in HEAD_BODY.", file=sys.stderr)

    out = BUILD_ROOT / SKILL_NAME
    if BUILD_ROOT.exists():
        shutil.rmtree(BUILD_ROOT)
    (out / "references").mkdir(parents=True)

    # scripts (runtime only — skip tests)
    (out / "scripts").mkdir()
    for name in ("scaffold.py", "podcast_tts.py"):
        shutil.copy2(PLUGIN_DIR / "scripts" / name, out / "scripts" / name)

    # assets (bridge + template + test), excluding caches
    for sub in ("bridge", "template", "test"):
        shutil.copytree(PLUGIN_DIR / "assets" / sub, out / "assets" / sub,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))

    # references = the non-orchestrator skills, transformed
    for name in REFERENCE_SKILLS:
        body = strip_frontmatter((SKILLS_DIR / name / "SKILL.md").read_text(encoding="utf-8"))
        (out / "references" / f"{name}.md").write_text(apply(REF_REPLACEMENTS, body), encoding="utf-8")

    # SKILL.md = frontmatter + head + transformed orchestrator (from "## Step 1") + tail
    orch = strip_frontmatter((SKILLS_DIR / ORCHESTRATOR / "SKILL.md").read_text(encoding="utf-8"))
    idx = orch.find("## Step 1")
    if idx == -1:
        die("orchestrator SKILL.md has no '## Step 1' section")
    steps = apply(ORCH_REPLACEMENTS, orch[idx:]).rstrip() + "\n"
    frontmatter = f"---\nname: {SKILL_NAME}\ndescription: {SKILL_DESCRIPTION}\n---\n"
    (out / "SKILL.md").write_text(frontmatter + HEAD_BODY + steps + TAIL_BODY, encoding="utf-8")

    return out


# --- Validate ---------------------------------------------------------------

def validate(skill_dir: Path) -> None:
    problems = []

    # Description: single line, colon-safe, long enough, enough distinct words.
    if " : " in SKILL_DESCRIPTION or ": " in SKILL_DESCRIPTION:
        problems.append("SKILL_DESCRIPTION contains ': ' — breaks YAML and the Agnes tile parser.")
    if "\n" in SKILL_DESCRIPTION:
        problems.append("SKILL_DESCRIPTION must be a single line.")
    if len(SKILL_DESCRIPTION) < 60:
        problems.append(f"SKILL_DESCRIPTION too short ({len(SKILL_DESCRIPTION)} < 60).")
    if len(set(SKILL_DESCRIPTION.split())) < 5:
        problems.append("SKILL_DESCRIPTION needs >= 5 distinct words.")

    # No plugin-only conventions may survive anywhere in the built markdown.
    stray_skill = re.compile(r"`(analyze-repo|docsite|review-docs|podcast|test-docsite|explain-repo)` skill")
    for md in skill_dir.rglob("*.md"):
        txt = md.read_text(encoding="utf-8")
        rel = md.relative_to(skill_dir)
        if "$PLUGIN_PATH" in txt:
            problems.append(f"{rel}: leftover $PLUGIN_PATH")
        if stray_skill.search(txt):
            problems.append(f"{rel}: leftover `<skill>` skill cross-reference")

    # Frontmatter must exist with name + a matching description.
    skill_md = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(skill_md)
    if not m:
        problems.append("SKILL.md has no frontmatter")
    else:
        fm = {}
        for line in m.group(1).splitlines():
            if ":" in line and line.strip() and not line.lstrip().startswith("#"):
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip()
        if fm.get("name") != SKILL_NAME:
            problems.append(f"SKILL.md frontmatter name != {SKILL_NAME}")
        if len(fm.get("description", "")) < 60:
            problems.append("SKILL.md frontmatter description parsed < 60 chars (folded scalar?)")

    # Referenced bundled files must exist.
    for rel in ("scripts/scaffold.py", "scripts/podcast_tts.py", "assets/bridge/assistant-bridge.py"):
        if not (skill_dir / rel).is_file():
            problems.append(f"missing bundled file: {rel}")

    if problems:
        die("validation failed:\n  - " + "\n  - ".join(problems))
    print("validation: OK")


# --- Package ----------------------------------------------------------------

def package(skill_dir: Path, fmt: str) -> Path:
    DIST_DIR.mkdir(exist_ok=True)
    out = DIST_DIR / f"{SKILL_NAME}.{fmt}"
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(skill_dir.rglob("*")):
            if f.is_file():
                z.write(f, arcname=f"{SKILL_NAME}/{f.relative_to(skill_dir).as_posix()}")
    print(f"packaged: {out} ({out.stat().st_size} bytes)")
    return out


def upload(bundle: Path) -> None:
    if not shutil.which("agnes"):
        die("`agnes` CLI not found on PATH — cannot upload.")
    cmd = [
        "agnes", "store", "upload", "skill", str(bundle),
        "--name", SKILL_NAME,
        "--description", SKILL_DESCRIPTION,
        "--category", AGNES_CATEGORY,
    ]
    print("uploading to Agnes:", " ".join(cmd[:5]), "...")
    subprocess.run(cmd, check=True)


# --- Main -------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Build the standalone repo-explainer skill bundle.")
    ap.add_argument("--format", choices=["skill", "zip"], default="skill",
                    help="output extension (both are ZIP archives; default: skill)")
    ap.add_argument("--upload", action="store_true", help="publish to the Agnes Flea Market after building")
    args = ap.parse_args()

    skill_dir = build()
    validate(skill_dir)
    bundle = package(skill_dir, args.format)
    if args.upload:
        upload(bundle)
    print("done.")


if __name__ == "__main__":
    main()
