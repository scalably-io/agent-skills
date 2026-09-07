---
name: dream
description: "Runs the nightly memory-consolidation routine defined by the memory-system skill: reads the last 48 hours of daily logs, files each fact into the right memory-tree location by an evidence contract and rubric, integrates pending learned-corrections, updates the current week's summary, and verifies the tree with a check script. Use to dream, run nightly memory consolidation, consolidate memory, or do a nightly memory pass. Not for answering what's already remembered (ordinary reading of memory files) or for the deeper weekly pass — that's weekly-memory-cleanup, which runs this routine first."
license: MIT
metadata:
  source: https://scalably.io/skills/dream
  derived_from:
    path: container/prompts/tasks/dream-per-user.md
    commit: d4ddad11
    date: "2026-09-07"
  triggers: [dream, nightly memory consolidation, run dream, consolidate memory, nightly memory pass]
  not_for: ["Answering what's already remembered — that's ordinary reading of the memory files (see the memory skill).", "The deeper weekly pass — that's the weekly-memory-cleanup skill, which runs this routine first and then goes further."]
---

# Dream — Nightly Memory Consolidation

## What it does

Dispatches into the `memory-system` skill's Nightly routine: reads the last 48 hours of daily logs, files each fact into the right memory-tree location using an evidence contract and a rubric, integrates evidence-valid pending corrections into `rules/learned-corrections.md`, updates the current week's summary and index, then verifies the tree with a mechanical check script and logs one line. Run it every night so the memory tree stays accurate without ever growing unbounded — this is the "how we keep agent memory true over months" mechanism, not a one-off cleanup.

This is the **per-user** variant: the project serves a single user (a DM/1:1, not a multi-person channel). Facts about the user need no attribution prefix — "the user prefers X" is enough, and there is usually no `people/` folder.

## Requirements

- The `memory-system` skill (same plugin) — defines the tree layout, format, caps, and the exact Nightly routine this skill runs, including `scripts/check-memory.sh`.
- `./memory/daily/*.md` populated by the `daily-log` skill (or an equivalent daily evidence ledger with the same source tags).

## Inputs and outputs

| | |
|---|---|
| Input | `./memory/daily/*.md` for the last 48 hours |
| Output | Updated `./memory/profile.md`, tree files, `./memory/weekly-summary.md`, `./memory/index.md`, `./rules/learned-corrections.md`; one line appended to `./memory/consolidation.log` |

## Worked example

Paste into Claude Code with this skill (and `memory-system`) installed, in a project with a populated `./memory/daily/` from the last two nights:

```text
/agent-ops:dream
```

Expected: no chat-facing output beyond a brief confirmation. The memory tree is updated in place (rewritten, not appended to), `./rules/learned-corrections.md` gains any newly-promoted rules under `## Rules`, and `./memory/consolidation.log` gets one new line such as: `2026-09-07 dream: 4 facts filed (2 people, 1 project), 1 rule integrated, check OK`.

## How to schedule this

Claude Code scheduled task (interactive): run `/schedule` and describe the cadence, e.g. "every day at 23:30 run /agent-ops:dream". The task runs the skill in a fresh session.

Cron, from any machine with Claude Code installed:

```bash
30 23 * * * cd /path/to/project && claude -p "/agent-ops:dream" >> logs/dream.log 2>&1
```

Use `0 9 * * 1` for weekly Monday-morning skills and `0 16 * * 5` for the Friday check-in.

## Procedure

### 1. Load the contract

Read the `memory-system` skill's Nightly routine section in full before doing anything else. It is the single source of truth for file layout, caps, and the step-by-step routine (orient → read last 48h of daily logs → extract candidates by the evidence contract → file each fact by the rubric → integrate learned-corrections → update `weekly-summary.md` → refresh `index.md` → verify with `check-memory.sh` → log one line to `consolidation.log`). This skill only dispatches into it — follow that routine phase by phase, exactly as written there.

### 2. Per-user scope

Because this is a single-user project: facts about the user need no attribution prefix — "the user prefers X" is enough. There is usually no `people/` folder; the user's own preferences live in `profile.md` and the tree, not in a per-person file.

### 3. Evidence discipline

Treat daily-log labels as candidates, not proof. Promote a preference or correction into `rules/learned-corrections.md` only from `[source:user-explicit]` plus an exact human quote and explicit `scope:standing`. Project-scoped evidence stays in its project file; one-time evidence stays in the daily/weekly record — never promoted into a mandatory rule.

### Hard rules

- Pass `offset`/`limit` on EVERY file Read (start `limit=500`, page onward). On a size error, retry the same file with paging — never skip it.
- Never read raw session `.jsonl` transcripts — daily logs only.
- Never promote `[source:observed-once]`, `[source:user-repeated]`, `[source:agent]`, `[source:system]`, or `[source:tool]` into a mandatory correction. Silence, continued use, and lack of complaint are not approval.
- Preserve system/service defaults as defaults — never relabel them as the user's confirmed preference.
- Never invent Wrong/Right examples, quantities, thresholds, dates, or other details. If the human supplied no example, omit the example fields.
- Never place a raw phone number in `profile.md`, a tree file, or `learned-corrections.md`.
- Supersede by rewriting lines in place. Never append a second generation of a fact or rule that already exists.
- End by running `scripts/check-memory.sh` and fixing every violation it prints, then append the one-line summary to `memory/consolidation.log`. Produce no other user-facing output.
