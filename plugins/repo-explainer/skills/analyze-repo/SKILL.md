---
name: analyze-repo
description: >
  Methodology for analyzing a cloned repository to produce business and technical documentation at a
  chosen depth. Used by explain-repo. Use when you need to understand a codebase enough to document it
  accurately, grounded only in the actual source.
metadata:
  tools: "Read, Glob, Grep, Bash"
  model: sonnet
---

# Analyze a Repository

Produce the structured notes that the `docsite` skill turns into documentation pages. Work **only** from the cloned source at `<workspace>/src/<slug>`. The output is two tracks of notes: a business track (always) and a technical track (when the scope includes technical), at the requested depth.

## Hard rule: never invent

Every nontrivial claim must be grounded in an actual file in the clone, and cite the file path (relative to the repo root). If something cannot be determined from the source, write "unknown" or "not determined from source" — do **not** guess at architecture, ownership, intent, numbers, or behavior. Inferred claims must be labeled as inferences and tied to the evidence that supports them.

## Step 1: First-pass map (always)

Build a quick mental model before reading deeply:

- **README** and any top-level docs (`README*`, `docs/`, `CONTRIBUTING*`, `ARCHITECTURE*`).
- **Package manifests** to identify language, stack, and dependencies: `package.json`, `pyproject.toml` / `requirements.txt` / `setup.py`, `go.mod`, `Cargo.toml`, `pom.xml` / `build.gradle`, `composer.json`, `Gemfile`, etc.
- **Entry points** — `main`, CLI entrypoints, `index.*`, server bootstrap, `cmd/`, `bin/`, framework conventions.
- **Directory structure** — `Glob`/`ls` the tree to see how the project is organized.
- **Build / run config** — `Dockerfile`, `docker-compose*`, `Makefile`, CI workflows (`.github/workflows`), scripts in manifests, `.env.example`.

Note the language(s), the framework(s), how to build it, and how to run it.

## Step 2: Business track (always)

Write plain-language notes a non-engineer can follow:

- **Purpose** — what problem this solves.
- **What it does** — its capabilities, described in outcomes not internals.
- **Who it is for** — the intended users / audience.
- **Value** — why it exists, what it replaces or enables.
- **Key capabilities** — the main features, as a short list.
- **How to run it** — the simplest path to trying it (from README / run config).

Avoid jargon. Where a business claim rests on the source (e.g. a feature), cite the file that establishes it.

## Step 3: Technical track (if scope includes technical)

The depth mode controls both the content shape and how much you read.

### high-level overview
A short technical overview:
- architecture at a glance,
- the main components and what each is responsible for,
- the tech stack,
- data flow in broad strokes.

**Reading:** README, directory structure, manifests, and the entry points. Do not read the whole codebase.

### detailed technical
A full deep-dive:
- architecture and how the pieces fit,
- key modules and their responsibilities,
- important interfaces / APIs (signatures, routes, public surfaces),
- data flow and control flow,
- notable patterns and conventions,
- with **real file references** for each section.

**Reading:** a representative sample across the codebase — entry points, each major module, the core domain logic, the public interfaces, and config. Enough to describe the system accurately, not necessarily every file.

### rebuild-from-scratch
A sequential, block-by-block build guide: "to build this yourself, start with X, then add Y, then wire Z…". Each block:
- names what to build and why it comes at that point in the sequence,
- is grounded in how the real repo does it (cite the file(s)),
- carries enough technical detail to be actionable.

**Reading:** substantial parts of the codebase — you must understand construction order and the dependencies between blocks well enough to sequence them.

## Step 4: Output

Return structured notes, organized so the `docsite` skill can drop them into pages:

- one business-track section set per repo,
- one technical-track section set per repo (matching the depth mode's shape above),
- file-path citations attached to claims,
- an explicit list of anything that was "unknown" / not determinable from source.

Also propose a single one-line `world` description of the repo (used to refine `config.json` for the assistant prompts).
