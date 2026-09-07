---
name: memory
description: "Use when the user says remember, forget, recall, or asks what do you know about something, or wants to save a correction, preference, or durable fact for a future session. Triggers: remember, forget, recall, memory, save this, store this, what do you know about, what did we discuss. Not for: session-scoped notes that don't need to persist — keep those in context; not for storing files — write files to the project directory instead. Memory here is plain files under `./memory/` and `./rules/`, read and edited directly — there is no memory API and no separate memory tool to call."
license: MIT
metadata:
  source: https://scalably.io/skills/memory
  derived_from:
    path: container/skills/memory/SKILL.md
    commit: ef174fc3
    date: "2026-09-07"
  triggers: [remember, forget, recall, memory, save this, store this, what do you know about, what did we discuss]
  not_for: [Session-scoped notes that don't need to persist — keep those in context., Storing files — write files to the project directory instead.]
---

# Memory (File-Based)

## What it does

Gives an agent durable memory across sessions using nothing but plain files under `./memory/` and `./rules/` — no database, no vector store, no memory API. On "remember X" it files the fact in the right place (a mandatory rule, a topic file, or the current week's notes); on "what do you know about X" it reads the tree in a fixed order instead of grepping everything; on "forget X" it removes or retires the fact cleanly, never leaving a second contradicting copy behind. The `memory-system` skill defines the tree layout, file formats, and size caps this skill files things into — install both together.

## Requirements

- The `memory-system` skill (same plugin) — defines the file layout, format, and caps this skill reads and writes against.
- A memory directory as defined by the memory-system skill (default `./memory`).
- Optional: a way to search prior session transcripts or chat logs by keyword, for facts the tree doesn't already have. Free option: `grep` over your runtime's saved session logs, if it keeps any; otherwise skip this step and rely on the tree alone.

## Inputs and outputs

| | |
|---|---|
| Input | A chat message containing a remember/forget/recall cue, or a fact, preference, or correction stated in passing |
| Output | Remember/forget: an edit to `./rules/learned-corrections.md` or a file under `./memory/` (in place — never a second, contradicting copy). Recall: an answer delivered in chat, sourced from the tree — never invented |

## Worked example

Paste into Claude Code with this skill (and `memory-system`) installed, in a project that already has a `./memory/` tree set up per the memory-system skill:

```text
remember that the staging DB is reset every Monday
```

Expected: no existing file already covers this, so the fact is filed as a new line under `## Pending` in `./rules/learned-corrections.md`:

```
- The staging DB is reset every Monday. <!-- lc:staging-db-reset -->
```

No confirmation is shown beyond normal conversation — filing happens silently, and a later "what do you know about the staging DB" recalls it from that file.

## Procedure

### Where memory lives

| Layer | Where | You |
|---|---|---|
| Essentials, every turn | `./memory/profile.md`, `./memory/index.md`, `./memory/weekly-summary.md`, `./rules/learned-corrections.md` | some runtimes inject these automatically into context — if yours doesn't, read them yourself before answering a recall question or filing a new fact; never name the plumbing to the user |
| Mandatory rules | `./rules/learned-corrections.md` | follow ALL of it — `## Pending` included (binding immediately); append new rules to `## Pending` |
| Deep detail | `./memory/` tree — `people/ projects/ clients/ reference/` | read on demand via `./memory/index.md` |
| Raw history | `./memory/daily/*.md` + prior session transcripts (keyword search) | search when the answer isn't in the tree |

### Recall — "what do you know about X?"

1. Check context first — if your runtime injects the essentials automatically, it usually already has the answer.
2. Read `./memory/index.md` → open the matching tree file (the index line's summary tells you which). One read, not a scan.
3. Still nothing → grep `./memory/daily/` for the term, or search prior session transcripts by keyword if your runtime keeps any.
4. Genuinely absent → say you don't have it recorded. Never invent.

Answer naturally. Never mention files, injection, or memory structure to the user — "I'll remember that" / "here's what I know", not the mechanics.

### Remember — saving something

Decide silently; never tell the user whether or where you are saving.

- **Correction or standing instruction** ("always X", "never Y", output format, hard boundary) → append ONE line to `./rules/learned-corrections.md` under `## Pending`: `- <the rule, ≤160 chars> <!-- lc:<short-slug> -->`. The memory-system skill's periodic maintenance routine integrates it into the mandatory rules.
- **Durable fact** (person, project state, client detail, workflow deviation) → update the matching file under `./memory/` IN PLACE (find it via `index.md`; restamp its `updated:` line). If a fact changed, rewrite the old line — never append a contradicting second version.
- **New topic with no matching file** → create it under the right folder (`people/ projects/ clients/ reference/`) with the standard frontmatter (`title`, `type`, `summary` ≤160 chars, `updated`) and add its line to `./memory/index.md`.
- **Unsure where it goes** → the `## Pending` drop-box under `./rules/learned-corrections.md` is always safe; the periodic maintenance routine files it correctly.

Do NOT store: greetings, one-time events (the daily log already has them), anything an external tracker (a spreadsheet, a task board) already tracks, or workflow mechanics a skill already defines — store only the user's deviations and preferences.

### Forget — removing something

On an explicit "forget X": find it (index → file), delete the line or mark the rule retired, and confirm plainly. For `learned-corrections.md` rules, move the rule to the corrections log's `## Retired` section instead of silently deleting — see the memory-system skill for that file's location and format.

### Hard rules

- Supersede by editing, never by appending a second generation.
- A periodic maintenance pass (see the `memory-system` skill) enforces caps and structure; your job in the moment is only correct filing.
