---
name: workspace-reorg
description: "One-time deep cleanup of a project root that has accumulated loose files: classifies every loose file as protected, recently active, or archivable, backs up before moving anything, archives by month into projects/archive/YYYY-MM/, builds projects/INDEX.md, and reports a full manifest. Moves only, except a regenerable root node_modules/. Use for a workspace reorg, to clean up the workspace, reorganize the project root, or a one-time root cleanup. Not for routine/recurring tidying — that's the lighter workspace phase inside weekly-memory-cleanup's Sunday routine."
license: MIT
metadata:
  source: https://scalably.io/skills/workspace-reorg
  derived_from:
    path: container/prompts/tasks/workspace-reorg.md
    commit: 13ebd977
    date: "2026-09-07"
  triggers: [workspace reorg, clean up the workspace, reorganize the project root, one-time root cleanup, tidy accumulated files]
  not_for: ["Routine/recurring tidying — that's the lighter workspace phase inside weekly-memory-cleanup's Sunday routine; this skill is the one-time deep version."]
---

# Workspace Reorg — One-Time Root Cleanup

## What it does

Performs a one-time reorganization of a project's workspace root: long-accumulated loose files move into an organized structure. Classifies every loose root file as protected, recently active, or archivable; backs up everything before moving it; archives by mtime month into `projects/archive/YYYY-MM/`; maintains `projects/INDEX.md`; and reports a full manifest. Preservation beats tidiness — when unsure, protect. Moves only; the one allowed deletion is a regenerable root-level `node_modules/`.

## Requirements

- The `memory-system` skill (same plugin) — defines the full Workspace Reorganization routine and its protected-file rules that this skill runs.
- Shell access to move files and create directories (`mkdir`, `mv`, `cp`).

## Inputs and outputs

| | |
|---|---|
| Input | The project root's loose files, plus any additional protected paths the user supplies |
| Output | `./.reorg-backup/` (backup of every moved file), `./projects/archive/YYYY-MM/<name>` for archived files, `./projects/INDEX.md`, and a manifest report (moves made, protected list with reasons, ambiguous files left in place) |

## Worked example

Paste into Claude Code with this skill (and `memory-system`) installed, in a project root that has years of loose files sitting at the top level:

```text
/agent-ops:workspace-reorg
```

Expected: `./.reorg-backup/` is populated with a copy of every file about to move, `./projects/archive/2026-05/` (etc.) receives the archivable files grouped by month, `./projects/INDEX.md` lists every project directory plus the archive, and the final message is a manifest: what moved, what stayed protected and why, what was left in place as ambiguous, and before/after root file counts. Nothing referenced by `CLAUDE.md`, `rules/`, or a skill ever moves.

## Procedure

### 1. Load the contract

Read the `memory-system` skill's Workspace Reorganization section in full before touching anything — it is the single source of truth for the routine and the protected-file rules. Preservation beats tidiness: when unsure, protect.

### 2. Gather the protected list

In addition to every protected pattern `memory-system` already defines (`CLAUDE.md`, any project config file, anything matching `*state*.json` / `*.state.*` / `*.lock`, the standard dirs, and anything named in `CLAUDE.md`, `rules/`, or a skill), ask the user for any additional paths this project's own automation depends on that you would not otherwise discover — for example a path referenced only inside an external scheduler config or an automation you cannot read from here. Treat the combined list as absolute: never move, rename, or delete anything on it.

### 3. Run the routine

Follow the Workspace Reorganization routine exactly:

1. **Backup first.** `mkdir -p ./.reorg-backup && cp <every file you will move> ./.reorg-backup/` — verify the copy exists before moving anything.
2. **Classify every loose root file**: protected / active-recent / archivable. When unsure, protected wins.
3. **Archive** — archivable files move to `projects/archive/YYYY-MM/` by the file's mtime month. Related clusters (e.g. a batch of images and a PDF from one job) go into a named subdirectory (`projects/archive/2026-05/image-batch/`).
4. **Node litter** — a root-level `package.json`/`package-lock.json` gets archived like any other file; a root-level `node_modules/` may be DELETED (regenerable, never unique work) — the one deletion this routine allows.
5. **Create/refresh `projects/INDEX.md`** covering every project directory plus the archive.
6. **Report** — full manifest of moves, protected list with reasons, anything ambiguous left in place.

### 4. Report

Your final output is the manifest: every move made, the protected list with reasons, any ambiguous files left in place on purpose, and before/after root file counts. Do not send any other user-facing message.

### Hard rules

- Backup verified BEFORE any move. Moves only — the single allowed deletion is a root-level `node_modules/` directory.
- A file referenced ANYWHERE (`CLAUDE.md`, `rules/`, a skill, the protected list you gathered) does not move, period.
- Do not send any other user-facing message — the manifest report is the deliverable.
