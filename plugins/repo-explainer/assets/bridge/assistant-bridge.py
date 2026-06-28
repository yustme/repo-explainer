#!/usr/bin/env python3
"""repo-explainer — local AI-assistant bridge.

Serves a generated docsite workspace and exposes POST /api/explain, /api/propose,
/api/apply, which shell out to the `claude` CLI (your Claude Code license) to power
the in-page assistant: explain a selection (concise / deep research over the cloned
source) and integrate answers back into the docs (propose -> approve -> apply).

Usage:
    python3 assistant-bridge.py <workspace-dir>

The workspace must contain config.json (written by scaffold.py). A free port is
chosen automatically and printed as:  RUNNING http://localhost:<PORT>/index.html
"""
import datetime
import http.server
import json
import os
import shutil
import socketserver
import subprocess
import sys
import threading
import time
from pathlib import Path

TIMEOUT_CONCISE = 120
TIMEOUT_DEEP = 240
TIMEOUT_APPLY = 300

LANG_NAMES = {
    "en": "English", "cs": "Czech", "sk": "Slovak", "de": "German", "fr": "French",
    "es": "Spanish", "it": "Italian", "pl": "Polish", "pt": "Portuguese", "nl": "Dutch",
}


def lang_name(code: str) -> str:
    return LANG_NAMES.get((code or "en").lower(), code or "English")


# ---- workspace / config ----
if len(sys.argv) < 2:
    print("usage: python3 assistant-bridge.py <workspace-dir>", file=sys.stderr)
    sys.exit(2)
WORKSPACE = Path(sys.argv[1]).expanduser().resolve()
CONFIG_PATH = WORKSPACE / "config.json"
if not CONFIG_PATH.is_file():
    print(f"config.json not found in {WORKSPACE}", file=sys.stderr)
    sys.exit(2)
CONFIG = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
LANG = CONFIG.get("lang", "en")
WORLD = CONFIG.get("world") or "this repository"
VISUALS = CONFIG.get("visuals", "none")
MODELS = CONFIG.get("models") or {}
MODEL_CONCISE = MODELS.get("concise", "claude-haiku-4-5-20251001")
MODEL_DEEP = MODELS.get("deep", "sonnet")
REPOS = {r["slug"]: r for r in CONFIG.get("repos", [])}
PAGES = CONFIG.get("pages", {})

LOG_DIR = WORKSPACE / "logs"
LOG_FILE = LOG_DIR / "assistant.jsonl"


def log_event(entry: dict) -> None:
    try:
        LOG_DIR.mkdir(exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def now_iso() -> str:
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def repo_src(repo_slug: str) -> Path:
    r = REPOS.get(repo_slug)
    if r and r.get("src"):
        p = (WORKSPACE / r["src"]).resolve()
        if p.is_dir():
            return p
    return WORKSPACE


def repo_docs_root(repo_slug: str) -> Path:
    r = REPOS.get(repo_slug)
    if r and r.get("docs_root"):
        p = (WORKSPACE / r["docs_root"]).resolve()
        if p.is_dir():
            return p
    return repo_src(repo_slug)


def rel_path(p: str) -> str:
    if not p:
        return "?"
    try:
        base = str(WORKSPACE) + "/"
        if p.startswith(base):
            return p[len(base):]
    except Exception:
        pass
    return p


def describe_tool(name: str, inp: dict) -> str:
    inp = inp or {}
    if name == "Read":
        return "📄 Reading " + rel_path(inp.get("file_path", "?"))
    if name == "Grep":
        pat = inp.get("pattern", "?")
        where = inp.get("path") or inp.get("glob") or ""
        return '🔍 Grep "' + str(pat)[:60] + '"' + (" in " + rel_path(where) if where else "")
    if name == "Glob":
        return "📁 Glob " + str(inp.get("pattern", "?"))
    if name == "Edit":
        return "✏️ Editing " + rel_path(inp.get("file_path", "?"))
    if name == "Write":
        return "💾 Writing " + rel_path(inp.get("file_path", "?"))
    if name == "Bash":
        return "⌨️ " + str(inp.get("command", ""))[:70]
    return "🔧 " + (name or "tool")


# ---- prompt builders ----
def build_explain_prompt(selection, context, deep=False):
    selection = (selection or "")[:2000]
    context = (context or "")[:4000]
    L = lang_name(LANG)
    if not deep:
        return (
            f"You are a concise technical explainer embedded in the documentation of {WORLD}.\n\n"
            "The reader selected a piece of text and wants to know what it means in the context "
            "of this project.\n\n"
            f'Selected text:\n"""\n{selection}\n"""\n\n'
            f'Surrounding context from the page:\n"""\n{context}\n"""\n\n'
            "Explain what the selected text means specifically in the context of this project. Be "
            f"concrete and brief (3-6 sentences). Answer in {L}. Keep technical terms in English. "
            "Plain text, no markdown headings."
        )
    return (
        f"You are an expert technical explainer embedded in the documentation of {WORLD}.\n\n"
        "The COMPLETE source code of this project is in the CURRENT DIRECTORY. Read it with the "
        "Read / Grep / Glob tools and ground your explanation in the real code, not general "
        "impressions.\n\n"
        f'The user selected this text and wants a DEEP explanation:\n"""\n{selection}\n"""\n\n'
        f'Surrounding context from the page:\n"""\n{context}\n"""\n\n'
        "Proceed:\n"
        "1) Find the relevant file(s) in the real source (grep/glob/read) and explain how it ACTUALLY "
        "works, referencing concrete files and their behavior.\n"
        "2) If it helps understanding, SHOW the most relevant file (or a substantial part) in a fenced "
        "code block, with the file path above it.\n"
        "3) Explain in depth and structured — markdown: ### headings, bullets, **bold**, `inline code`, "
        "fenced ```code``` blocks. Length is fine.\n"
        + _visual_clause()
        + f"\nAnswer in {L}. Keep technical terms in English."
    )


def _visual_clause():
    """Step 4 of the deep prompt — the infographic instruction, tuned by the visuals setting.

    The infographic renders in a sandboxed, script-less iframe with NO access to the page's CSS,
    so it must be a fully self-contained ```html block (its own inline <style>, no external
    resources, no <script>). Animation must be pure CSS keyframes or SVG SMIL."""
    base = ("4) If a visual helps, you MAY add at the very end ONE compact self-contained infographic "
            "as a single ```html block: its own inline <style>, dark background #14181E, text #E9E3D6, "
            "accent #C99A3F, no external resources, no <script>, max ~440px tall. ")
    if VISUALS == "animated":
        return (base +
                "PREFER an ANIMATED diagram that shows how the thing works — a flow/pipeline, request "
                "lifecycle, or component interaction with movement (a dot/packet traveling between "
                "stages, a flowing dashed connector, or staged reveals). Animate with CSS keyframes or "
                "SVG SMIL only (the sandbox blocks JS). Add a `@media (prefers-reduced-motion: reduce)` "
                "rule that freezes motion so it still reads as a still image. Skip it only if a visual "
                "genuinely would not help.\n")
    return base + "Skip it if it doesn't genuinely help.\n"


def build_propose_prompt(answer, selection, context, page, instruction="", prior=""):
    answer = (answer or "")[:6000]
    selection = (selection or "")[:1500]
    context = (context or "")[:2500]
    instruction = (instruction or "")[:1200]
    prior = (prior or "")[:6000]
    L = lang_name(LANG)
    extra = ""
    if prior:
        extra += ("\nYour PREVIOUS proposal was:\n\"\"\"\n" + prior + "\n\"\"\"\n"
                  "Adapt it per the user instruction below.\n")
    if instruction:
        extra += "\nAdditional user instruction for the proposal:\n\"\"\"\n" + instruction + "\n\"\"\"\n"
    return (
        f"You are a documentation editor for {WORLD}.\n\n"
        f"In the current directory is the page `{page}` — an HTML documentation page. You may read it "
        "with Read / Grep / Glob. DO NOT write; only propose.\n\n"
        "The user got this explanation from the AI assistant and considers it good. They want to fold "
        "it back into the page CONTENT to improve the docs:\n\n"
        f'EXPLANATION:\n"""\n{answer}\n"""\n\n'
        f'(It concerned the selection: "{selection}")\n'
        f'(Surrounding context on the page: "{context}")\n'
        f"{extra}\n"
        "Task — propose the integration. Read the relevant part of the page and return, IN THIS ORDER:\n"
        "1) **Where it goes** — the specific section (its heading) and location (after which existing block).\n"
        "2) **Why** — 1-2 sentences.\n"
        "3) **Proposed HTML** — a ready-to-insert block as ONE ```html fenced block. It must match the "
        "neighboring blocks of that section (same CSS classes and structure already used there — read them "
        "first). Insert CONTENT only; never `<aside id=\"aiPanel\">`, `<script>`, or `<style>`.\n\n"
        f"Be concrete and brief. Answer in {L}. Keep technical terms in English."
    )


def build_apply_prompt(proposal, target, page, repo_slug, instruction=""):
    proposal = (proposal or "")[:9000]
    instruction = (instruction or "")[:1200]
    L = lang_name(LANG)
    extra = ""
    if instruction:
        extra = "\nAdditional user instruction (takes precedence):\n\"\"\"\n" + instruction + "\n\"\"\"\n"
    if target == "repo":
        docs = REPOS.get(repo_slug, {}).get("docs_root", "src/" + repo_slug)
        return (
            f"You are a documentation editor for {WORLD}.\n\n"
            f"Integrate the following APPROVED proposal into the SOURCE REPOSITORY's documentation. "
            f"The repo is in the current directory under `{docs}`.\n\n"
            f'APPROVED PROPOSAL:\n"""\n{proposal}\n"""\n'
            f"{extra}\n"
            "Rules:\n"
            f"- Prefer editing `{docs}/README.md` (create it if missing). If a `{docs}/docs/` directory "
            "is clearly more appropriate, you may create/edit a markdown file there instead.\n"
            "- Write in MARKDOWN (this is a source repo, not the HTML docsite). Convert the proposed HTML "
            "content into clean markdown prose; do not paste raw HTML.\n"
            "- Edit ONLY files under that repo path. Use the Edit tool (or Write for a new file).\n"
            f"- Keep the existing document's language and style. Write new prose in {L} only if the "
            "document is already in that language; otherwise match the document.\n\n"
            "At the end write a short summary (1-3 sentences): what you added and to which file. "
            f"Answer in {L}."
        )
    return (
        f"You are a documentation editor for {WORLD}.\n\n"
        f"In the current directory is `{page}`. Integrate the following APPROVED proposal into the "
        "CONTENT of that page using the Edit tool.\n\n"
        f'APPROVED PROPOSAL:\n"""\n{proposal}\n"""\n'
        f"{extra}\n"
        "Rules:\n"
        f"- Edit ONLY `{page}`, and only its content sections.\n"
        "- NEVER touch `<aside id=\"aiPanel\">`, `<script>` blocks, or `<style>`.\n"
        "- Insert the HTML block exactly where the proposal targets, consistent with neighboring blocks "
        "(reuse the same CSS classes already present — read them first).\n"
        "- Keep valid HTML and `<meta charset=\"utf-8\">` and UTF-8.\n"
        "- Use the Edit tool (no other files).\n\n"
        "At the end write a short summary (1-3 sentences): what you inserted and into which section. "
        f"Answer in {L}."
    )


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WORKSPACE), **kwargs)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, obj, status=200):
        payload = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _sse(self, obj):
        try:
            self.wfile.write(("data: " + json.dumps(obj, ensure_ascii=False) + "\n\n").encode("utf-8"))
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            raise
        except Exception:
            pass

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def _read_body(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            return json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return {}

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/api/explain":
            self._handle_explain()
        elif path == "/api/propose":
            self._handle_propose()
        elif path == "/api/apply":
            self._handle_apply()
        else:
            self.send_error(404)

    # ---- concise + deep explain ----
    def _handle_explain(self):
        t_start = time.time()
        body = self._read_body()
        selection = (body.get("selection") or "").strip()
        context = (body.get("context") or "").strip()
        source = body.get("source") or "selection"
        repo = body.get("repo") or ""
        deep = (body.get("mode") or "concise") == "deep"
        if not selection:
            self._json({"text": "(nothing selected)"})
            return
        if deep:
            prompt = build_explain_prompt(selection, context, deep=True)
            self._stream_claude(
                prompt=prompt, allowed_tools=["Read", "Grep", "Glob"],
                run_cwd=str(repo_src(repo)), timeout_s=TIMEOUT_DEEP,
                busy_label="⏳ Starting deep model and opening the source…",
                init_label="🧠 Reading the source…", writing_label="✍️ Writing the explanation…",
                log_extra={"event": "explain", "mode": "deep", "source": source, "repo": repo,
                           "selection": selection, "context": context, "prompt_chars": len(prompt),
                           "model": MODEL_DEEP},
            )
            return
        prompt = build_explain_prompt(selection, context, deep=False)
        cmd = ["claude", "-p", prompt, "--model", MODEL_CONCISE, "--output-format", "json"]
        meta, error, ok, text = {}, None, False, ""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(WORKSPACE),
                                    timeout=TIMEOUT_CONCISE)
            if result.returncode != 0:
                err = (result.stderr or "").strip()
                low = err.lower()
                if "401" in err or "403" in err or "auth" in low or "login" in low:
                    text = ("Claude CLI auth error. Sign in: run `claude` interactively, or "
                            "`claude setup-token` for headless.")
                else:
                    text = "claude failed: " + (err[:400] or "unknown error")
                error = err[:600] or ("exit %d" % result.returncode)
            else:
                data = json.loads(result.stdout)
                text = (data.get("result") or "").strip() or "(empty answer)"
                ok = not data.get("is_error", False)
                usage = data.get("usage") or {}
                meta = {"cost_usd": data.get("total_cost_usd"), "duration_ms": data.get("duration_ms"),
                        "session_id": data.get("session_id"), "input_tokens": usage.get("input_tokens"),
                        "output_tokens": usage.get("output_tokens")}
        except FileNotFoundError:
            text = "`claude` CLI not found in PATH. Start the bridge where Claude Code is available."
            error = "claude not found"
        except subprocess.TimeoutExpired:
            text = f"Timed out ({TIMEOUT_CONCISE} s)."
            error = "timeout"
        except Exception as exc:  # noqa: BLE001
            text = "Server error: " + str(exc)
            error = str(exc)
        log_event({"ts": now_iso(), "event": "explain", "ok": ok, "mode": "concise", "source": source,
                   "repo": repo, "selection": selection, "context": context, "prompt_chars": len(prompt),
                   "model": MODEL_CONCISE, "response": text, "server_ms": int((time.time() - t_start) * 1000),
                   "claude": meta, "error": error, "client": self.client_address[0] if self.client_address else None})
        self._json({"text": text})

    def _handle_propose(self):
        body = self._read_body()
        answer = (body.get("answer") or "").strip()
        selection = (body.get("selection") or "").strip()
        context = (body.get("context") or "").strip()
        instruction = (body.get("instruction") or "").strip()
        prior = (body.get("prior") or "").strip()
        page = (body.get("page") or "").strip()
        repo = body.get("repo") or ""
        if not answer:
            self._json({"text": "(missing answer to integrate)"})
            return
        if page not in PAGES:
            self._json({"text": "(unknown page)"})
            return
        prompt = build_propose_prompt(answer, selection, context, page, instruction, prior)
        self._stream_claude(
            prompt=prompt, allowed_tools=["Read", "Grep", "Glob"], run_cwd=str(WORKSPACE),
            timeout_s=TIMEOUT_DEEP, busy_label="⏳ Reading the page and preparing a proposal…",
            init_label="🧠 Finding the right place on the page…", writing_label="✍️ Drafting the addition…",
            log_extra={"event": "propose", "page": page, "repo": repo, "selection": selection,
                       "context": context, "instruction": instruction, "is_refine": bool(prior),
                       "prompt_chars": len(prompt), "model": MODEL_DEEP},
        )

    def _handle_apply(self):
        body = self._read_body()
        proposal = (body.get("proposal") or "").strip()
        instruction = (body.get("instruction") or "").strip()
        target = "repo" if (body.get("target") == "repo") else "docsite"
        page = (body.get("page") or "").strip()
        repo = body.get("repo") or ""
        if not proposal:
            self._json({"text": "(missing proposal to merge)"})
            return
        if target == "docsite" and page not in PAGES:
            self._json({"text": "(unknown page)"})
            return
        # backup target
        backup = None
        if target == "docsite":
            tgt = WORKSPACE / page
        else:
            tgt = repo_docs_root(repo) / "README.md"
        if tgt.is_file():
            cand = str(tgt) + ".bak-" + time.strftime("%Y%m%d-%H%M%S")
            try:
                shutil.copy2(tgt, cand)
                backup = cand
            except Exception:
                backup = None
        prompt = build_apply_prompt(proposal, target, page, repo, instruction)
        busy = ("🗂️ Backup: " + Path(backup).name + " · merging…") if backup else "🔀 Merging the proposal…"
        self._stream_claude(
            prompt=prompt, allowed_tools=["Read", "Grep", "Glob", "Edit", "Write"], run_cwd=str(WORKSPACE),
            timeout_s=TIMEOUT_APPLY, busy_label=busy, init_label="🧠 Reading and preparing the edit…",
            writing_label="✍️ Finishing and summarizing…",
            log_extra={"event": "apply", "target": target, "page": page, "repo": repo,
                       "instruction": instruction, "proposal_chars": len(proposal),
                       "prompt_chars": len(prompt), "model": MODEL_DEEP, "backup": backup},
        )

    # ---- shared streaming engine ----
    def _stream_claude(self, prompt, allowed_tools, run_cwd, timeout_s, busy_label, log_extra,
                       init_label="🧠 Working…", writing_label="✍️ Writing…"):
        t_start = time.time()
        cmd = ["claude", "-p", prompt, "--model", MODEL_DEEP, "--output-format", "stream-json", "--verbose"]
        if allowed_tools:
            cmd += ["--allowedTools"] + list(allowed_tools)
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        text, meta, error, ok, tool_count = "", {}, None, False, 0
        timed_out = {"v": False}
        proc = None
        try:
            self._sse({"type": "status", "text": busy_label})
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, cwd=run_cwd, bufsize=1)

            def _kill():
                timed_out["v"] = True
                try:
                    proc.kill()
                except Exception:
                    pass

            timer = threading.Timer(timeout_s, _kill)
            timer.start()
            try:
                for line in proc.stdout:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    etype = ev.get("type")
                    if etype == "system" and ev.get("subtype") == "init":
                        self._sse({"type": "status", "text": init_label})
                    elif etype == "assistant":
                        emitted = False
                        for blk in (ev.get("message", {}) or {}).get("content", []) or []:
                            if blk.get("type") == "tool_use":
                                tool_count += 1
                                self._sse({"type": "status",
                                           "text": "[%d] %s" % (tool_count, describe_tool(blk.get("name"), blk.get("input")))})
                            elif blk.get("type") == "text" and blk.get("text", "").strip() and not emitted:
                                emitted = True
                                self._sse({"type": "status", "text": writing_label})
                    elif etype == "result":
                        text = (ev.get("result") or "").strip()
                        usage = ev.get("usage") or {}
                        meta = {"cost_usd": ev.get("total_cost_usd"), "duration_ms": ev.get("duration_ms"),
                                "session_id": ev.get("session_id"), "is_error": ev.get("is_error"),
                                "num_turns": ev.get("num_turns"), "input_tokens": usage.get("input_tokens"),
                                "output_tokens": usage.get("output_tokens")}
                        ok = not ev.get("is_error", False)
            finally:
                proc.wait()
                timer.cancel()

            if timed_out["v"]:
                error = "timeout"
                self._sse({"type": "error", "text": f"Timed out ({timeout_s} s)."})
            elif proc.returncode not in (0, None) and not text:
                err = (proc.stderr.read() if proc.stderr else "").strip()
                error = err[:600] or ("exit %d" % proc.returncode)
                self._sse({"type": "error", "text": "claude failed: " + (err[:400] or "unknown error")})
            else:
                if not text:
                    text = "(empty answer)"
                self._sse({"type": "done", "text": text, "tools": tool_count, "claude": meta})
        except (BrokenPipeError, ConnectionResetError):
            error = "client disconnected"
            if proc:
                try:
                    proc.kill()
                except Exception:
                    pass
        except FileNotFoundError:
            error = "claude not found"
            self._sse({"type": "error", "text": "`claude` CLI not found in PATH."})
        except Exception as exc:  # noqa: BLE001
            error = str(exc)
            self._sse({"type": "error", "text": "Server error: " + str(exc)})

        entry = {"ts": now_iso(), "ok": ok, "tools": tool_count, "response": text,
                 "server_ms": int((time.time() - t_start) * 1000), "claude": meta, "error": error,
                 "client": self.client_address[0] if self.client_address else None}
        entry.update(log_extra or {})
        log_event(entry)

    def log_message(self, *args):
        pass


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    log_event({"ts": now_iso(), "event": "server_start", "workspace": str(WORKSPACE),
               "lang": LANG, "model_concise": MODEL_CONCISE, "model_deep": MODEL_DEEP,
               "repos": list(REPOS.keys()), "pages": list(PAGES.keys())})
    with Server(("127.0.0.1", 0), Handler) as httpd:
        port = httpd.server_address[1]
        print(f"RUNNING http://localhost:{port}/index.html", flush=True)
        print(f"(serving {WORKSPACE}; POST /api/* bridges to `claude`; log {LOG_FILE}; Ctrl+C to stop)",
              flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
