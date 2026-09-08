---
name: automation
description: "Use when the user requests bulk or repetitive data work that doesn't need judgment: process all rows, cross-reference two lists, batch-update many records, run the same calculation across N items. Triggers: process all, for each row, bulk update, automate this, run a script over, do this for every."
license: MIT
metadata:
  source: https://scalably.io/skills/automation
  derived_from:
    path: container/skills/automation/SKILL.md
    commit: ef174fc3
    date: "2026-09-07"
  triggers: [automate, run script, bulk process, repetitive task, process all rows, check all, update all, batch update]
  not_for: [Tasks requiring judgment or interpretation: do those directly., Scheduling future runs: use a task scheduler for that.]
---

# Automation Scripts: Model-Orchestrated Scripting

## What it does

Handles repetitive, mechanical data work with a short script instead of processing it item-by-item as an agent: reading hundreds of rows, checking many URLs, cross-referencing two lists, running the same calculation across N items. The agent decides *what* to do and *why*; the script does the *work*; the agent verifies the output and reports the result in plain language.

## Requirements

- Bash and a Python 3 or Node 22 runtime.

## Inputs and outputs

| | |
|---|---|
| Input | A bulk/repetitive task in free text (e.g. "rename every file in X", "check status for these 200 URLs") plus the source data: files, a folder, or pasted rows |
| Output | A script under `./scripts/<task-name>.<py\|js>` and its result: files changed in place, or a JSON/text summary printed to stdout |

## Worked example

Paste into Claude Code with this skill installed:

```text
/agent-ops:automation rename every file in ./exports from "Report - <client> - <date>.pdf" to "<date>-<client>.pdf", dry run first
```

Expected: a script at `./scripts/rename-exports.py` that parses each filename, prints an old-name → new-name diff table for review (dry run, no changes made), then on confirmation renames the files in `./exports/` and reports how many were renamed and how many were skipped.

## Procedure

### Core principle

Scripts do the mechanical work; the model orchestrates:

```
User request → model decides WHAT to do → script does the WORK → model reports results
```

### When to use a script vs. doing it directly

| Task | Script | Direct |
|------|--------|--------|
| Read hundreds of rows from a file/sheet | Yes | No |
| Check many URLs for status | Yes | No |
| Calculate totals/averages | Yes | No |
| Cross-reference two lists or sheets | Yes | No |
| Copy/transform data between files | Yes | No |
| Decide which rows need action | No | Yes |
| Interpret results for the user | No | Yes |
| Handle ambiguous or edge cases | No | Yes |

### 1. Check for an existing script

Look in `./scripts/` for something that already does this. If nothing fits, tell the user: "I can build a script for this. It will run instantly next time."

### 2. Build the script

- Write it to `./scripts/<task-name>.<py|js>`.
- Pattern: read input (stdin, args, or a file path) → process → structured output (JSON to stdout, or files changed in place).
- For anything that renames, deletes, or overwrites files, support a `--dry-run` flag that prints what *would* change without changing it, and require an explicit confirmation (a second flag, or a re-run without `--dry-run`) before it acts for real.
- Test it against a small sample of the real data before running it on everything.

### 3. Verify + report (after every run)

Raw script output is not useful to the user on its own; process it first.

**Verify:**
- Sanity check: do the numbers add up (e.g. done + pending + failed = total)?
- Anomaly check: is anything unusual (e.g. a much higher failure rate than expected)?
- Error check: did any items fail, and why?

**Analyze:**
- Spot trends: "the completion rate dropped 14% from the prior run."
- Find patterns: "8 of 12 failures share the same cause."
- Flag outliers: one item behaving very differently from the rest.

**Report to the user:**
- A short, formatted summary, not raw JSON.
- Key numbers first, in bold; anomalies and recommended next steps after.

Example:

```
Processed 229 records:
- 180 succeeded (78.6%)
- 30 pending
- 12 failed >7 days (8 share the same error code)
- 7 unknown (source unreachable)

Success rate is down from 92% last run. The failures starting Feb 20
share one error code; worth checking that dependency first.
```

### Keep building

Every reusable script accumulates for next time:

1. Save it to `./scripts/`.
2. Note what it does and how to invoke it (a one-line comment at the top of the file is enough).
3. Test it against sample data before trusting it on a full run.
