---
description: UI smoke test for a generated docsite — clicks through the served site in Chrome and reports PASS/FAIL
allowed-tools: Bash, Read, Glob, AskUserQuestion
argument-hint: "[workspace-path]"
---

Run a UI smoke test against a generated repo-explainer docsite.

Invoke the `test-docsite` skill and pass it `$ARGUMENTS` as the workspace path. If `$ARGUMENTS` is empty, the skill picks the most recently modified workspace under `~/repo-explains/` and says which one it chose.

## What happens

1. Start the local bridge server for the workspace (background) and open the site in your Chrome.
2. Inject `assets/test/checks.js` and run deterministic assertions on every page: hub cards, view switch, TOC rail + scroll-spy, assistant open/close, deep/fullscreen overlap, select-to-Explain, z-index layering, podcast player, animated diagrams, console errors, plus a narrow-viewport pass.
3. Take screenshots of the key UI states for a visual sanity pass.
4. Report a PASS/FAIL table in chat with failure details and screenshots, then stop the server.

No content is modified and no assistant/`claude` API calls are made — the test stops at the point of submission.
