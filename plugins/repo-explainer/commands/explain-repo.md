---
description: Generate a local documentation website that explains one or more git repositories, with an embedded AI assistant
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, AskUserQuestion, Task
argument-hint: "[git-url ...]"
---

Explain one or more git repositories by generating a local documentation website.

Invoke the `explain-repo` skill and pass it `$ARGUMENTS` as the repo URL(s). If `$ARGUMENTS` is empty, ask the user for at least one git URL (or a local path) before continuing.

## What happens

The `explain-repo` skill orchestrates the whole flow:

1. Clone the repo(s) into a workspace under `~/repo-explains/<slug>/`.
2. Ask you a few questions — documentation language, scope (business, or business + technical), and (for technical) the depth: high-level overview, detailed technical, or rebuild-from-scratch guide.
3. Scaffold a self-contained docsite (one page per repo and view, plus a hub page).
4. Analyze the cloned source and write the documentation content into the pages.
5. Run a mandatory editorial review (an independent editor agent) that checks readability, coherence, and that the text and diagrams make sense — fixing clear issues and flagging the rest.
6. Start a local server and open the docsite in your browser.

The heavy lifting lives in the skills: `explain-repo` (orchestration), `analyze-repo` (how to read and understand the source), `docsite` (how to fill the pages and run the server), and `review-docs` (the mandatory editorial pass). Start by invoking `explain-repo`.
