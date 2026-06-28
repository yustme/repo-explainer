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

## Topic discovery (for the interactive topic picker)

`explain-repo` calls this before the full analysis to offer the user a menu of topics to deep-dive. From the first-pass map (README, directory/module names, domain vocabulary in code and docs, key dependencies), extract the **topics this repo deals with**. Produce a flat list where each topic has:

- a short **label** (e.g. "Semantic layer", "Express proxy auth", "Relationship graph layout"),
- a **one-line description** grounded in the repo,
- a **track** hint: `domain` (conceptual / business — belongs on the business page) or `technical` (belongs on the technical page),
- the **evidence** (a file or two that establishes it).

Cover two kinds:
- **Domain / conceptual topics** — the business concepts the project is about (its problem domain, key entities, external systems it integrates with). These are what a newcomer would want explained ("what even is a semantic layer?").
- **Technical topics** — notable mechanisms, patterns, or subsystems in the code (auth flow, a proxy, a streaming pipeline, a layout algorithm, an AI integration).

Aim for the ~8–16 most central topics. Do not invent topics the source does not support. Return this list to `explain-repo`; the user selects a subset to elaborate.

## Flow capture (only when visuals = animated)

When `explain-repo` passes visuals = `animated`, also identify the **flows worth visualizing** — the sequences and structures that are easier to grasp as a moving picture than as prose. The animation is there to explain *how the thing works*, so favor flows where something moves through stages.

Good candidates (only those the source actually supports):
- **Pipelines / data flow** — input → transform → output stages (ETL, request → handler → response, parse → build → emit).
- **Request / control lifecycle** — what happens from an entry point to a result, in order.
- **Build / run sequence** — the ordered steps to go from source to a running system (pairs naturally with rebuild-from-scratch depth).
- **Architecture interactions** — the main components and what calls/sends what to whom.
- **State machines** — a small number of states and the transitions between them.

For each flow, capture a **flow spec** the `docsite` skill can render directly:
- a short **title** and a one-line description of what it shows,
- a **kind**: `pipeline` (linear/branching A→B→C), `sequence`, `architecture`, or `state`,
- the **nodes/steps** in order — each a short label (+ optional sub-label), grounded in the file(s) that establish it,
- the **edges** — what connects to what and, where it matters, *what moves along the edge* (a request, a record, an event),
- the **evidence** — the file path(s) the flow is derived from.
- a **track** hint (`domain` for a business "how it works" overview, `technical` for an internal mechanism) and which page it belongs on.

Same hard rule: every node, edge, and ordering must be grounded in the actual source — do not invent stages or connections to make a prettier diagram. If a flow is only partially determinable, capture what is known and mark the rest "unknown". Aim for the few flows that genuinely aid understanding (typically 2–6), not a diagram for every paragraph.

## Required focus (Step 3 question 5)

If `explain-repo` passes a user-named focus from the final interview question, treat it as a **mandatory deep-dive**: read the relevant source thoroughly and produce a grounded, in-depth section for it even if it was not among the auto-discovered topics. If the source genuinely does not cover it, say so explicitly rather than padding.

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

The depth mode controls both the content shape and how much you read. The **concepts-vs-code** choice (orthogonal to depth) controls how findings are *expressed*:

- **concepts** — describe logic, responsibilities, flow, and the "why" in prose. Reference files by path, but quote code only when a sentence genuinely cannot stand without it. The reader should understand the system without reading the source.
- **code** — show the real code: actual signatures, key snippets quoted verbatim with their file path, concrete routes/identifiers/types, file-by-file specifics. Still explain, but anchor every point in shown source.
- **both** — lead with the concept, then show the code that implements it.

This shapes presentation, not what you read — you still read enough source for the depth mode. Apply it to the technical track and to technical topic deep-dives; the business track stays conceptual regardless.

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
- the **flow specs** from "Flow capture" when visuals = `animated`,
- a grounded deep-dive for the user's named focus (Step 3 question 5) when one was given,
- file-path citations attached to claims,
- an explicit list of anything that was "unknown" / not determinable from source.

Also propose a single one-line `world` description of the repo (used to refine `config.json` for the assistant prompts).
