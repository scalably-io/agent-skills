---
name: weekly-memory-cleanup
description: "Runs the memory-system skill's Sunday deep pass: the nightly routine first, then archiving the finished week, deduping and topic-merging learned-corrections, reviewing the tree for staleness, cross-file deduping, and rebuilding the index from scratch. Use for weekly memory cleanup, a Sunday memory cleanup, a weekly deep pass, archiving the week, or a memory audit. Not for the nightly pass alone — that's the dream skill; this skill runs it first and then goes further."
license: MIT
metadata:
  source: https://scalably.io/skills/weekly-memory-cleanup
  derived_from:
    path: container/prompts/tasks/weekly-memory-cleanup.md
    commit: 7242274a
    date: "2026-09-07"
  triggers: [weekly memory cleanup, sunday memory cleanup, weekly deep pass, archive the week, memory audit]
  not_for: ["The nightly pass by itself — that's the dream skill (this skill runs it first, then goes further)."]
---

# Weekly Memory Cleanup — Sunday Deep Pass

## What it does

Runs the `memory-system` skill's Nightly routine first, then its deeper Sunday pass: archives the finished week into `weekly-archive/`, dedupes and topic-merges `rules/learned-corrections.md`, reviews the tree for staleness, cross-file dedupes, and rebuilds `index.md` from scratch. This is the enforcement layer — whatever drifted during the week (duplicate rules, contradictions, stale "Now" sections, cap overruns) gets fixed here, not deferred to the following week.

## Requirements

- The `memory-system` skill (same plugin) — defines the tree layout and the exact Sunday routine this skill runs, including `scripts/check-memory.sh` and `scripts/archive-week.sh`.
- A week of `./memory/daily/*.md` logs (from the `daily-log` skill or equivalent) and an existing `./memory/` tree, ideally maintained nightly by the `dream` skill.

## Inputs and outputs

| | |
|---|---|
| Input | The full `./memory/` and `./rules/` tree, plus this week's `./memory/daily/*.md` |
| Output | `./memory/weekly-archive/<year>-W<nn>.md` (the finished week), a reset `./memory/weekly-summary.md`, a deduped `./rules/learned-corrections.md` + `./memory/reference/corrections-log.md`, a rebuilt `./memory/index.md`; a 3-5 line report appended to `./memory/consolidation.log` |

## Worked example

Paste into Claude Code with this skill (and `memory-system`) installed, on a Sunday, in a project with a week of dailies and a tree the `dream` skill has been maintaining nightly:

```text
/agent-ops:weekly-memory-cleanup
```

Expected: no chat-facing output beyond a brief confirmation. `./memory/weekly-summary.md` is archived to `./memory/weekly-archive/2026-W36.md` and reset with a fresh Monday header (open items carried forward), `./rules/learned-corrections.md` has duplicate and superseded rules removed or merged, `./memory/index.md` is rebuilt from the tree's frontmatter, and `./memory/consolidation.log` gets a 3-5 line report such as: `2026-09-06 weekly-cleanup: archived W36, merged 2 duplicate rules, retired 1 superseded rule, compressed 3 matured rules, check OK — profile 41/80, index 22/50, weekly 18/80, LC 34/60`.

## How to schedule this

Claude Code scheduled task (interactive): run `/schedule` and describe the cadence, e.g. "every Sunday at 09:00 run /agent-ops:weekly-memory-cleanup". The task runs the skill in a fresh session.

Cron, from any machine with Claude Code installed:

```bash
0 9 * * 0 cd /path/to/project && claude -p "/agent-ops:weekly-memory-cleanup" >> logs/weekly-memory-cleanup.log 2>&1
```

## Procedure

### 1. Load the contract

Read the `memory-system` skill's Sunday routine section in full before doing anything else. It is the single source of truth for the routine, and it explicitly includes running the Nightly routine first.

### 2. Run the nightly routine, then the Sunday deep passes

Follow the Sunday routine phase by phase, exactly as defined in `memory-system`:

1. Run the Nightly routine (orient, read recent dailies, file facts, integrate corrections, update the week, refresh the index, verify).
2. **Archive the week** — run `scripts/archive-week.sh`; carry forward still-open items into the new week's "Open items".
3. **Learned-corrections deep pass** — delete verbatim duplicate rules; topic-merge rules on the same subject into one line (move ancestors to `## Retired` in the corrections log with a superseded-by note); compress matured rules (promoted ≥14 days ago, no re-violation this week) to one-liners, moving examples to the log; resolve any contradiction to the latest rule and log the resolution.
4. **The 80% rule** — any injected file above 80% of its cap gets consolidated this pass, before it can break the cap mid-week.
5. **Tree hygiene** — for every tree file: `updated` older than 60 days → verify its `## Now` against recent dailies, restamp or move stale state out; files over 150 lines → split; orphan files → index them or fold them into an existing file.
6. **Cross-file dedupe** — a fact found in two homes: keep the one the rubric assigns, replace the other with a pointer.
7. **Rebuild `index.md`** from the tree's frontmatter (every file, correct summaries, nothing extra).
8. **Verify + report** — run `scripts/check-memory.sh` until clean; append a 3-5 line report to `memory/consolidation.log`.

### 3. Enforcement stance

You are the enforcement layer for whatever drifted during the week — duplicate rules, contradictions, stale "Now" sections, cap overruns. Fix it this pass; do not defer a violation to next week.

### Hard rules

- Pass `offset`/`limit` on EVERY file Read. Never read session `.jsonl` files.
- Moves, not deletions: archived weeks go to `weekly-archive/`, retired rules go to the corrections log's `## Retired` section. The only thing you may delete outright is a verbatim duplicate line.
- End with the check script clean and a 3-5 line report appended to `memory/consolidation.log` (merged/archived/compressed counts, final sizes of the four injected files). Produce no other user-facing output.
