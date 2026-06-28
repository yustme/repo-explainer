#!/usr/bin/env python3
"""repo-explainer — scaffold a docsite workspace for one or more git repos.

Clones the repo(s), generates the hub + per-repo business/technical pages from the
bundled templates (design system + AI assistant inlined, self-contained), and writes
config.json for assistant-bridge.py. Content sections are left as a placeholder for
Claude to fill.

Usage:
  python3 scaffold.py --workspace <dir> --title <str> --lang <code> \
      --scope <business|business+technical> [--visuals <none|animated>] \
      --repo <slug>=<git-url-or-local-path> [--repo <slug>=<url> ...] [--world <str>] [--brand <str>]

Prints one JSON line describing the result.
"""
import argparse
import html
import json
import shutil
import subprocess
import sys
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "assets" / "template"


def slugify(s: str) -> str:
    out = "".join(c if (c.isalnum() or c in "-_") else "-" for c in s.lower()).strip("-")
    while "--" in out:
        out = out.replace("--", "-")
    return out or "repo"


def clone_repo(source: str, dest: Path) -> None:
    if dest.exists() and any(dest.iterdir()):
        return  # idempotent: already populated
    dest.parent.mkdir(parents=True, exist_ok=True)
    p = Path(source).expanduser()
    if p.exists():  # local path
        shutil.copytree(p, dest, dirs_exist_ok=True)
        return
    res = subprocess.run(["git", "clone", "--depth", "1", source, str(dest)],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"git clone failed for {source}: {(res.stderr or '').strip()[:400]}")


def sub(template: str, mapping: dict) -> str:
    out = template
    for k, v in mapping.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def nav_html(repos, current_slug, current_view, has_technical) -> str:
    parts = []
    if len(repos) > 1:
        links = []
        for r in repos:
            cls = " class=\"active\"" if r["slug"] == current_slug else ""
            links.append(f'<a{cls} href="{r["slug"]}-business.html">{html.escape(r["name"])}</a>')
        parts.append('<span class="reposwitch"><span class="lbl">Repo</span>' + "".join(links) + "</span>")
    vs = [f'<a class="{ "active" if current_view=="business" else "" }" href="{current_slug}-business.html">Business</a>']
    if has_technical:
        vs.append(f'<a class="{ "active" if current_view=="technical" else "" }" href="{current_slug}-technical.html">Technical</a>')
    parts.append('<nav class="viewswitch" aria-label="View">' + "".join(vs) + "</nav>")
    return "".join(parts)


def cards_html(repos, has_technical) -> str:
    multi = len(repos) > 1
    out = []
    for r in repos:
        label = (html.escape(r["name"]) + " · ") if multi else ""
        out.append(
            f'    <a class="card" href="{r["slug"]}-business.html">'
            f'<span class="num">{label}Business</span>'
            f'<h3>Business overview</h3>'
            f'<p>What it does and why — in plain language for decision-makers.</p>'
            f'<span class="go">Open <span class="arrow">→</span></span></a>'
        )
        if has_technical:
            out.append(
                f'    <a class="card" href="{r["slug"]}-technical.html">'
                f'<span class="num">{label}Technical</span>'
                f'<h3>Technical deep-dive</h3>'
                f'<p>How it works inside — architecture, modules, data flow.</p>'
                f'<span class="go">Open <span class="arrow">→</span></span></a>'
            )
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--title", default="Repository documentation")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--scope", default="business+technical",
                    choices=["business", "business+technical"])
    ap.add_argument("--visuals", default="none", choices=["none", "animated"],
                    help="animated: docsite + assistant generate animated flow diagrams")
    ap.add_argument("--repo", action="append", required=True,
                    help="slug=git-url-or-local-path (repeatable)")
    ap.add_argument("--world", default="")
    ap.add_argument("--brand", default="")
    args = ap.parse_args()

    has_technical = args.scope == "business+technical"
    ws = Path(args.workspace).expanduser().resolve()
    (ws / "src").mkdir(parents=True, exist_ok=True)

    repos = []
    for spec in args.repo:
        if "=" not in spec:
            print(json.dumps({"error": f"bad --repo {spec!r}, expected slug=source"}))
            sys.exit(2)
        slug, source = spec.split("=", 1)
        slug = slugify(slug)
        dest = ws / "src" / slug
        try:
            clone_repo(source, dest)
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"error": str(exc)}))
            sys.exit(1)
        name = slug.replace("-", " ").replace("_", " ").title()
        repos.append({"slug": slug, "name": name, "src": f"src/{slug}", "docs_root": f"src/{slug}"})

    brand = args.brand or (repos[0]["name"] if len(repos) == 1 else args.title)
    world = args.world or f"the {brand} project"
    styles = (TEMPLATE_DIR / "styles.css").read_text(encoding="utf-8")
    assistant_js = (TEMPLATE_DIR / "assistant.js").read_text(encoding="utf-8")
    toc_js = (TEMPLATE_DIR / "toc.js").read_text(encoding="utf-8")
    page_tpl = (TEMPLATE_DIR / "page.html").read_text(encoding="utf-8")
    index_tpl = (TEMPLATE_DIR / "index.html").read_text(encoding="utf-8")

    pages = {}
    generated = []

    def write_page(repo, view):
        fname = f"{repo['slug']}-{view}.html"
        eyebrow = "BUSINESS" if view == "business" else "TECHNICAL"
        h1 = f"{html.escape(repo['name'])} — {'business' if view=='business' else 'technical'}"
        page = sub(page_tpl, {
            "LANG": html.escape(args.lang),
            "TITLE": html.escape(f"{repo['name']} — {view}"),
            "STYLES": styles,
            "ASSISTANT_JS": assistant_js,
            "TOC_JS": toc_js,
            "BRAND": html.escape(brand),
            "REPO": html.escape(repo["slug"]),
            "PAGE": html.escape(fname),
            "VIEW": view,
            "WORLD": html.escape(world, quote=True),
            "REPO_DOCS": "1",
            "NAV": nav_html(repos, repo["slug"], view, has_technical),
            "EYEBROW": eyebrow,
            "H1": h1,
        })
        (ws / fname).write_text(page, encoding="utf-8")
        pages[fname] = {"repo": repo["slug"], "view": view}
        generated.append(fname)

    for r in repos:
        write_page(r, "business")
        if has_technical:
            write_page(r, "technical")

    # hub
    index = sub(index_tpl, {
        "LANG": html.escape(args.lang),
        "TITLE": html.escape(args.title),
        "STYLES": styles,
        "BRAND": html.escape(brand),
        "EYEBROW": "Repository documentation",
        "H1": html.escape(args.title),
        "LEAD": "Two views per repository: a business overview and a technical deep-dive. Pick one to start.",
        "CARDS": cards_html(repos, has_technical),
        "FOOT": "Generated by repo-explainer · local documentation",
    })
    (ws / "index.html").write_text(index, encoding="utf-8")
    generated.append("index.html")

    config = {
        "title": args.title,
        "lang": args.lang,
        "world": world,
        "visuals": args.visuals,
        "models": {"concise": "claude-haiku-4-5-20251001", "deep": "sonnet"},
        "repos": repos,
        "pages": pages,
    }
    (ws / "config.json").write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "workspace": str(ws),
        "config": "config.json",
        "repos": [r["slug"] for r in repos],
        "pages": generated,
        "scope": args.scope,
        "lang": args.lang,
        "visuals": args.visuals,
        "has_technical": has_technical,
    }))


if __name__ == "__main__":
    main()
