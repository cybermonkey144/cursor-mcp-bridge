---
name: check-docs
description: Report whether tech-summary docs in docs/ are still in sync with the code they describe, using git to detect drift since each doc was verified. Use when the user asks "are the docs stale", "which docs need updating", "check doc freshness", or types /check-docs. Pair with /tech-summary, which writes the freshness frontmatter this relies on.
---

# Check Docs — staleness report for tech-summary docs

A summary doc is a snapshot; the code it describes keeps changing. Docs produced by
`/tech-summary` carry frontmatter (`verified_at_commit` + `sources`). This skill diffs
those sourced files against the verified commit to tell which docs have drifted.

## Run it

The freshness script is bundled with this plugin and always operates on the current
project's `docs/` folder (it resolves the repo root from `git rev-parse --show-toplevel`
at invocation time, not from where the script physically lives):

```bash
${CLAUDE_SKILL_DIR}/check_doc_freshness.sh          # all docs/*.md
${CLAUDE_SKILL_DIR}/check_doc_freshness.sh -v       # also list the commits that caused drift
${CLAUDE_SKILL_DIR}/check_doc_freshness.sh -b       # advance FRESH docs' markers to HEAD (see below)
${CLAUDE_SKILL_DIR}/check_doc_freshness.sh docs/auto-apply-pipeline.md   # one doc
```

### Why `--bump`
A doc's `verified_at_commit` would otherwise stay pinned far behind HEAD even when only
*unrelated* files changed — so the doc reads "verified long ago" despite still being accurate.
`--bump` rolls a **FRESH** doc's `verified_at_commit` to HEAD and `last_verified` to today.
This is safe by definition: FRESH means no sourced file changed since the last verification,
so the verification still holds at HEAD. STALE docs are never bumped — they need a real
re-verification via `/tech-summary`.

Statuses:
- **FRESH** — no sourced file changed since `verified_at_commit`.
- **STALE** — sourced files changed; the named commits are what the doc hasn't caught up to.
- **UNTRACKED** — no freshness frontmatter (not produced by `/tech-summary`).

The script exits non-zero if any doc is STALE, so it also works in a pipeline.

## After running

- Summarize the report for the user: how many fresh / stale / untracked, and which are stale.
- For each STALE doc, the changed-files list is the work list — offer to refresh it by
  re-running `/tech-summary <topic>`, which re-verifies and bumps the commit/date.
- If many docs are UNTRACKED, mention they predate the freshness system and could be
  re-generated with `/tech-summary` to opt them in.
