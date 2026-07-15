---
name: tech-summary
description: Generate a technical summary document for a topic or area of the codebase. Cursor does the heavy code-reading via the cursor-agent MCP, Claude verifies the findings against the real files, then writes a consistently-formatted summary to docs/. Use when the user asks to "summarize", "document", "write up", or "explain an area of" the code, or types /tech-summary <topic>.
---

# Tech Summary — Cursor reads, Claude verifies, docs/ gets the file

Produce a durable, consistently-formatted technical summary of a topic or code area.
The division of labour is deliberate:

- **Cursor (via `cursor-agent` MCP)** does the heavy, wide reading — it has full filesystem
  access and keeps that bulk out of the main context.
- **Claude verifies** Cursor's claims against the actual files before anything is written.
  Cursor can be confidently wrong; never write a summary on its word alone.
- **Output goes to `docs/`** as a checked-in markdown file, matching the repo's existing
  human-facing docs.

This skill requires the `cursor-agent` MCP server (bundled with the `cursor-agent-tool`
plugin in this same marketplace) to be installed and connected.

## Inputs

- **Topic / area** — the argument after `/tech-summary` (e.g. `auto-apply pipeline`,
  `backend/api/human_mentor_connections.py`, `the embeddings backfill flow`).
- If no topic is given, ask the user what to summarize before proceeding. Do not guess.

## Process

### 1. Delegate the reading to Cursor
Use the `cursor-agent` MCP. For a one-shot summary use `run`; for an area you'll iterate on,
`create_session` + `send_message` so context accumulates across calls.

Ask Cursor to return **structured raw material**, not prose — that's what Claude verifies:
- The exact files involved, with paths.
- Entry points (routes, jobs, exported functions, components).
- The data/control flow between them.
- External dependencies (DB tables, MCP servers, third-party APIs, env vars).
- Any gotchas, footguns, or known-disabled paths it noticed.

Tell Cursor explicitly: cite real file paths and symbol names; do not invent.

### 2. Verify before writing — REQUIRED
This is the non-negotiable step. For every non-trivial claim Cursor makes:
- Open the file and confirm the path, symbol, and behavior exist as described.
- Spot-check flow claims by reading the actual call sites, not just the file Cursor named.
- Prefer `graphify query "<question>"` for relationship/architecture claims when
  `graphify-out/` exists — it returns a scoped subgraph instead of raw greps.
- If a claim doesn't hold up, fix it or drop it. Note corrections so the user sees what changed.

Never copy Cursor's output into the doc unverified.

### 3. Write the summary to docs/
File name: kebab-case of the topic, e.g. `docs/auto-apply-pipeline.md`.
If a file for this topic already exists, **update it in place** rather than creating a duplicate —
and bump `last_verified` + `verified_at_commit` to the current commit, since you just re-verified it.

Every summary MUST start with freshness frontmatter so the paired `/check-docs` skill
can later tell whether the code has drifted. Get the commit with `git rev-parse HEAD`
and list every file you verified in step 2 under `sources:` (these are exactly the files
the staleness check diffs against — be complete, or drift will go undetected).

Use this template exactly (drop a body section only if it genuinely doesn't apply):

```markdown
---
topic: <topic>
last_verified: <YYYY-MM-DD>
verified_at_commit: <git rev-parse HEAD>
sources:
  - path/to/file_you_verified.py
  - path/to/another.ts
---

# <Topic> — Technical Summary

> Scope: <one line on what this covers>

## Overview
2-4 sentences: what this area does and why it exists.

## Key files
| File | Responsibility |
|------|----------------|
| `path/to/file.py` | … |

## Entry points
Routes, scheduled jobs, exported functions, or components that kick this off.

## Data & control flow
How a request/event moves through the pieces. A short numbered list or a fenced
ASCII diagram. Reference files as `path:symbol`.

## External dependencies
DB tables, MCP servers, third-party APIs, env vars, other services.

## Gotchas & constraints
Footguns, disabled paths, perf limits, ordering requirements — what would bite
someone editing this.

## Open questions
Anything unverified, ambiguous, or worth a follow-up. Empty is fine.
```

### 4. Close out
- State where the file was written and list any claims you corrected during verification.
- The freshness frontmatter you wrote lets the paired `/check-docs` skill report later
  whether the sourced files have changed since this verification.
- Offer to add a pointer line in `.claude/knowledge/` if the user wants it surfaced in
  future sessions (if this project has that persistent-knowledge system).

## Rules

- Cursor reads, Claude verifies, docs/ stores. Don't skip verification because the topic
  "looks simple."
- Keep the doc to what's true today — date it, and put anything uncertain under Open questions
  rather than stating it as fact.
- One topic per file. Match the repo's existing doc tone (concise, file-path-anchored).
