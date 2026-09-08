---
name: memory-system
description: "The memory-system maintenance contract — file layout, format spec, size caps, and the nightly / weekly / migration routines for a project's file-based memory (see the `memory` skill for day-to-day recall/save/forget behavior). Triggers: dream, memory consolidation, nightly memory, weekly memory cleanup, memory migration, learned corrections. Not for: answering what's already remembered — that's ordinary reading of the memory files, handled by the `memory` skill."
license: MIT
metadata:
  source: https://scalably.io/skills/memory-system
  derived_from:
    path: container/skills/memory-system/SKILL.md
    commit: d4ddad11
    date: "2026-09-07"
  triggers: [dream, memory consolidation, nightly memory, weekly memory cleanup, memory migration, learned corrections]
  not_for: [Answering user questions about what is remembered — that is ordinary reading of memory files, handled by the memory skill.]
---

# Memory System — Maintenance Contract

## What it does

Defines how a project's file-based memory is structured and kept clean: the directory layout, the frontmatter every tree file must carry, size caps on the files read every turn, and a mechanical validator (`scripts/check-memory.sh`) that turns "is memory in good shape" into `OK` or a list of `VIOLATION:`/`WARN:` lines. Three routines build on this contract — a nightly consolidation pass, a weekly cleanup pass, and a one-time migration pass for adopting the contract on an existing, unstructured memory folder — all described below. Read the `memory` skill for how memory gets used turn-to-turn; read this one before running any maintenance routine against a memory tree.

## Requirements

- bash 4+.
- Scripts read `MEMORY_ROOT` (default `.`) and `MEMORY_CHECK_SCOPE` (`full` or `memory`).
- No external packages — only standard POSIX text tools (`grep`, `sed`, `find`, `wc`, `date`).

## Inputs and outputs

| | |
|---|---|
| Input | A project's `./memory/` and `./rules/` tree — or, before the migration routine runs, whatever unstructured memory files already exist |
| Output | `scripts/check-memory.sh` prints `OK` or one `VIOLATION:`/`WARN:` line per problem found, exit 0 (clean) or 1 (violations). `scripts/archive-week.sh` moves the current week into `./memory/weekly-archive/<year>-W<nn>.md` and resets `weekly-summary.md` with a fresh header |

## Worked example

Paste into a shell from a project root, with this skill's `scripts/` copied alongside (or referenced by path), to see the validator pass on a minimal compliant tree:

```bash
mkdir -p ./memory/daily ./rules
cat > ./memory/profile.md <<'EOF'
# Profile
Solo user, freelance consultant.
EOF
cat > ./memory/index.md <<'EOF'
# Memory Index
(nothing filed yet)
EOF
cat > ./memory/weekly-summary.md <<'EOF'
# Week of 2026-09-08

## Open items
(none yet)
EOF
touch ./memory/daily/2026-09-08.md
bash scripts/check-memory.sh
```

Expected output: `OK` (exit code 0). Delete `./memory/index.md` and rerun to see the failure mode instead: `VIOLATION: index.md is missing — the dream has nothing to consolidate into`, exit code 1.

## Procedure

This skill is the single source of truth for how a project's file-based memory is structured and maintained. Three routines below load it:

| Routine | Runs | Section |
|---|---|---|
| dream (nightly) | every night | Nightly routine |
| weekly cleanup | Sunday | Sunday routine (includes nightly) |
| migration | once per project | Migration routine |

"Project" below means whatever unit owns this memory tree — a repo, a team workspace, a persistent agent session; `MEMORY_ROOT` (default `.`) points at its root, containing `memory/` and `rules/`.

Design principles, in priority order:

1. **Injected files are small and current.** Only 4 files are meant to be loaded into every conversation: `profile.md`, `index.md`, `weekly-summary.md`, and `rules/learned-corrections.md` (plus the last 3 daily logs). Everything else is read on demand. A fact that is stale or bloated in an injected file does damage on every single turn.
2. **One home per fact.** A fact lives in exactly one file. Other files may link to it, never restate it.
3. **Supersede by editing, never by appending.** When a fact or rule changes, rewrite the existing line in place. Two generations of the same fact in one file means the agent reads contradictions as truth.
4. **History is archived, not deleted.** Dated material moves to `daily/` (automatic) and `weekly-archive/` — never lost, never injected.
5. **Discipline is mechanical.** Every routine ends by running `check-memory.sh` and fixing what it reports. Caps are numbers, not vibes.

### The tree

```
./memory/
  profile.md            INJECTED  WHO the user/team is + how to serve them
  index.md               INJECTED  MAP of the tree — one line per file
  weekly-summary.md      INJECTED  CURRENT week only
  channel-context.md            INJECTED (leave as-is, optional)
  reference/automation-opportunities.md   NOT injected (retired from the
                                injection set by migration — see below)
  daily/                        raw daily logs (written elsewhere; never edit)
  feedback/                     raw weekly feedback replies + opt-out flag (written by
                                friday-feedback; never by the dream)
  weekly-archive/               finished weeks: YYYY-Www.md
  people/               tree    one file per person (multi-user projects)
  projects/              tree    one file per active project or engagement
  clients/               tree    client portfolio + per-client state (only if the project has clients)
  reference/             tree    workflow specs, guides, corrections-log.md
  pipeline/              tree    standing pipeline/architecture docs (only if the project runs one)
./rules/
  learned-corrections.md  INJECTED as MANDATORY directives — one-line rules
```

**Folders are semi-dynamic.** `people/ projects/ clients/ reference/ pipeline/` is the full allowed set. Create a folder only when you have content for it — a single-user project usually needs only `reference/` and maybe `projects/`. Never invent a new top-level folder; if something truly fits nothing, put it in `reference/`.

### File format (tree files)

Every file under `people/ projects/ clients/ reference/ pipeline/` starts with frontmatter:

```markdown
---
title: Jordan K. — workflows & preferences
type: person            # person | project | client | reference | pipeline
summary: 3PL-client prospector; sheet-driven domain research; strict CSV outputs; first-names-only rule.
updated: 2026-08-20
---

## Now
Current state — what is true today. Replace, never append.

## Standing rules
The person's/project's hard preferences. One line each.

## Detail
Workflows, specs, background. Subsections as needed.
```

- `summary` ≤ 160 chars. It becomes this file's line in `index.md`, so write it as the retrieval hook: what would make a future agent open this file.
- `updated` — stamp with today's date on EVERY write to the file.
- Body: current state first, detail last. `## Now` is replaced wholesale each time it changes.
- One topic per file. A file over 150 lines gets split (e.g. `reference/orders-pipeline.md` + `reference/orders-sheets.md`) and both halves indexed.

### The injected four

**profile.md — WHO.** Identity, role, communication style, frustration triggers, top preferences. In multi-user projects: one short block per person (name, id, role, ≤3 hard preferences) — full per-person detail lives in `people/<name>.md`. NO workflow specs, NO activity history, NO client tables, NO "Previously..." chains. Cap: **80 lines.**

**index.md — MAP.** The tree's table of contents plus standing pointers:

```markdown
# Memory Index

Read the matching file BEFORE acting on a request about that person,
project, or workflow. This index is the map; the files are the truth.

## People
- people/jordan-k.md — 3PL-client prospector; sheet-driven domain research; strict CSV outputs.
- people/sam.md — bulk email extraction; filter-then-email pattern; no empty monitoring pings.

## Projects
- projects/example-client.md — cybersecurity client; backlink gap targeting.

## Reference
- reference/pipeline.md — 8-step linkbuilding pipeline; SQLite checkpoints; resume-never-restart.
- reference/corrections-log.md — full provenance for every learned-corrections rule.
```

Each line = `- <path> — <that file's frontmatter summary>`. The index must list every tree file. An optional `## Legacy` section may point at loose legacy files that workflows still reference in their old locations (e.g. email templates) — list them, don't move them. Cap: **50 lines.**

**weekly-summary.md — CURRENT WEEK.** One `# Week of YYYY-MM-DD` header (Monday), updated through the week. Contains this week's project facts, decisions, open items. Exactly ONE "Open items" section, replaced — never a second snapshot. Cap: **80 lines.** Finished weeks are moved to `weekly-archive/YYYY-Www.md` by the Sunday routine — never accumulate a second week header in this file.

**rules/learned-corrections.md — MANDATORY RULES.** Injected with mandatory-directive framing; highest authority. Format:

```markdown
# Learned Corrections — <Project>

Every rule below is mandatory. Full provenance (source quotes, wrong/right
examples, history): memory/reference/corrections-log.md — search by the
fact id in the comment.

## Rules
- Prefer named marketing/PR/editor email over generic; one email per domain; empty if none found. <!-- lc:contact-priority evidence:user-explicit -->
- Never place an anchor inside intro, conclusion, or a bulleted list item. <!-- lc:anchor-placement evidence:user-explicit -->

## Pending
(appended by live agents — ALREADY BINDING, follow immediately;
the nightly routine merges them into ## Rules)
```

- One new rule = ONE line (target ≤160 chars) + `<!-- lc:<slug> evidence:user-explicit -->`. Existing rules without an evidence marker are legacy and must not be silently upgraded; audit their provenance before touching them.
- A NEW or SUBTLE rule (promoted <14 days, or re-violated since promotion) may temporarily keep a 2–4 line form with a Wrong/Right example. The Sunday routine compresses it to one line once stable.
- A rule that needs real length (a full spec, a category list) gets a one-line entry here + its own file in `reference/` linked by path.
- Cap: **60 rules.** At the cap, consolidate before adding.
- `## Pending` always exists, even when empty. Pending rules are IN FORCE from the moment they are written — "pending" refers only to nightly integration/dedup into `## Rules`, never to applicability.

**reference/corrections-log.md** — the provenance ledger:

```markdown
## lc:contact-priority
**Rule (current):** <one-liner as it stands in learned-corrections.md>
**History:** 2026-04-06 refined (no generic fallback) · 2026-04-10 promoted
**Evidence:** user-explicit · scope: standing
**Source quote:** "dont force info@ if theres a real contact" (source, 2026-04-06)
**Wrong:** info@site.com when editor@ exists · **Right:** editor@site.com

## Retired
- lc:article-age-2024 — superseded by lc:article-age (2023+, not 2024+), 2026-05-12
```

Never re-promote a rule listed under `## Retired` unless the user explicitly reinstates it.

### Evidence contract

Daily logs are a lossy evidence layer. Their labels are candidates, never authority by themselves.

- `source:user-explicit` means an exact human quote explicitly states or corrects the behavior. Only `scope:standing` can become a mandatory learned correction.
- `source:user-repeated` means the behavior was observed in at least two dated human interactions. It may support a durable tree fact, but never a mandatory correction without explicit standing language.
- `source:observed-once` is one occurrence. Keep it in the daily log or current project state; never convert it into a preference or habit.
- `source:agent`, `source:system`, and `source:tool` are non-promotable. An assistant suggestion, qualification, template, or tool choice is not a user preference.
- Silence, continued use, and lack of complaint are not approval. An explicit acceptance quote is required.
- A task-specific routing decision or correction remains project/one-time state unless the human explicitly makes it standing.
- Preserve externally supplied service defaults as defaults; never attribute them to the user without confirmation.
- Never store raw phone numbers in `profile.md`, tree files, `weekly-summary.md`, or `learned-corrections.md`. Use a stable non-phone identity or verified name.
- Wrong/Right examples are optional. Never invent an example, number, threshold, date, or quantity. If the source contains no example, omit those fields.

### The rubric — where does a fact go?

Ask in order:

1. **Is it an explicit standing correction/instruction from a human?** → learned-corrections one-liner (+ log entry). Check `## Rules` AND `## Retired` first: if a rule on the same topic exists, REWRITE that line under its existing `lc:` id. Never append a sibling. Require `[source:user-explicit scope:standing]` plus the exact quote; otherwise continue through the rubric.
2. **Is it durable — still true and useful in 90 days without edits?** (who someone is, a workflow spec, a hard preference, a tool fact) → `profile.md` if it's top-level WHO material and fits the cap; otherwise the matching tree file (update in place, restamp `updated`).
3. **Is it current-week project state?** → `weekly-summary.md`.
4. **Is it a dated event, a batch count, a session recap?** → it is ALREADY in the daily log. Do not copy it anywhere else. Ledger-shaped material never enters profile, tree files, or rules.
5. **None of the above?** → skip it. Not every fact deserves storage.

Never store: anything derivable from the workspace or skills (workflow mechanics a skill already defines — store only the user's DEVIATIONS and explicit preferences), one-time events, greetings, raw phone numbers, raw numbers a spreadsheet or task tracker already tracks.

### Nightly routine (dream)

Hard read rule: page long files instead of reading them whole (start with a limit around 500 lines). Never read raw session transcripts — dailies only.

1. **Orient.** List `./memory/*` and `./memory/*/*`; read `profile.md`, `index.md`, `rules/learned-corrections.md`; tail `consolidation.log` (5 lines — for what was already done, NOT as a format example; see step 9).
2. **Read the last 48h of daily logs** (`./memory/daily/`, by filename date).
3. **Extract candidates.** Apply the evidence contract before the rubric. Explicit standing corrections are promotion candidates. Repeated observations can be durable tree candidates. Observed-once, agent/system/tool notes, and approval-by-silence remain non-promotable. Legacy daily entries without a `source:` tag are unverified: they may inform dated/project state, but cannot create or strengthen a mandatory rule.
4. **File each fact by the rubric.** Update in place; supersede by rewriting; restamp `updated:`; refresh the file's `summary` if its content shifted; create a new tree file only when no existing file fits (then add its index line).
5. **Integrate learned-corrections.** Move evidence-valid `## Pending` entries into `## Rules` (exists-check first — same topic = rewrite existing line); entries without explicit human provenance remain Pending and are reported for audit, not promoted. Promote new corrections only when the daily contains `[source:user-explicit scope:standing]`, an exact quote, and directive language ("always", "never", "from now on") or an equally clear hard boundary. One-time factual/project corrections do NOT qualify. Write/refresh the corrections-log entry with `Evidence: user-explicit`, source quote, actor, and date. Add Wrong/Right examples only when the human supplied them.
6. **Update `weekly-summary.md`** — current week section only.
7. **Refresh `index.md`** lines for files you touched.
8. **Verify:** run `bash scripts/check-memory.sh`. Fix every violation it prints, rerun until clean (max 3 passes; if still failing, log the remaining violation in `consolidation.log`).
9. **Log one line** to `memory/consolidation.log`, in THIS format: `2026-08-21 dream: 4 facts filed (2 people, 1 project), 1 rule integrated, check OK`. One line, plain prose, starting with the date. Use this format even when the lines already in the file look different — legacy entries from an earlier system may use another shape. Do NOT copy their shape, and do NOT reintroduce old fields. Never rewrite the existing lines either — append yours and move on.

### Sunday routine (weekly cleanup)

Run the nightly routine first, then:

1. **Archive the week.** Run `bash scripts/archive-week.sh` — moves the finished week to `weekly-archive/` and resets `weekly-summary.md` with a fresh Monday header. Carry forward still-open items into the new week's "Open items".
2. **Learned-corrections deep pass.**
   - Delete verbatim duplicate rules (keep one).
   - Topic-merge: rules on the same subject collapse into ONE line holding the latest form; ancestors move to `## Retired` in the log with a superseded-by note.
   - Compress matured rules (promoted ≥14 days ago, no re-violation in the week's dailies) to one-liners; move their examples to the log.
   - Contradiction check: no two rules may disagree; resolve to the latest, log the resolution.
3. **The 80% rule.** Any injected file above 80% of its cap (profile 64 lines, index 40, weekly 64, LC 48 rules) gets consolidated THIS pass — merge related entries, push detail into tree files — so the cap never breaks mid-week.
4. **Tree hygiene.** For every tree file: `updated` older than 60 days → verify its `## Now` against recent dailies, either restamp or move stale state out; files >150 lines → split; orphan files → index them or fold them into an existing file.
5. **Cross-file dedupe.** A fact found in two homes: keep the one the rubric assigns, replace the other with a link.
6. **Rebuild `index.md`** from the tree's frontmatter (every file, correct summaries, nothing extra).
7. **Verify + report.** Run `check-memory.sh` until clean; append a 3-5 line report to `consolidation.log` (what was merged, archived, compressed; final sizes).

### Migration routine (one-time, per project)

Goal: transform a project's legacy memory into this contract. MOVES ONLY — nothing is deleted; everything legacy survives in the backup or an archive location.

1. **Backup first:** `cp -r ./memory ./memory/.pre-migration-backup` is WRONG (recursive). Use:
   `mkdir -p ./.migration-backup && cp -r ./memory ./rules ./.migration-backup/`
   Verify the copy exists before touching anything.
2. **Inventory.** Read `profile.md`, `weekly-summary.md`, `rules/learned-corrections.md` fully (paging long files). List every other `memory/*.md`.
3. **Split `profile.md`** by the rubric:
   - Identity / role / communication style / frustration triggers / top preferences → new lean `profile.md` (≤80 lines).
   - Per-person blocks (multi-user projects) → `people/<slug>.md`, keeping each person's workflows and preferences; profile keeps a 2-4 line block per person.
   - Workflow specs / guides / schemas → `reference/<topic>.md`.
   - Client tables / portfolio / per-client state → `clients/` (verify against recent dailies before writing a status; an old "Active" row is a CLAIM, not a fact — carry it as `status unverified since <date>` unless a recent daily confirms it).
   - Project state → `projects/<slug>.md`.
   - Dated activity chains ("Last active ... Previously ...") → keep ONE `Last active: <date>` line in the person's file; drop the chain (history already lives in `daily/`).
4. **Rebuild `weekly-summary.md`:** keep only the current week (create the Monday header if the legacy file has none). Move ALL older week sections into `weekly-archive/<year>-W<nn>.md` files, splitting by their own week headers (approximate weeks are fine — preserve content, don't polish it).
5. **Rebuild `learned-corrections.md`:**
   - Deduplicate verbatim-repeated rules (keep one).
   - Topic-merge refinement chains — keep the LATEST form of each rule.
   - Convert every surviving rule to the one-line + `<!-- lc:slug -->` format (rules promoted in the last 14 days may keep a short Wrong/Right example).
   - Write `reference/corrections-log.md`: one entry per surviving rule (current form, history, source, examples) + `## Retired` listing every merged-away ancestor.
   - Add the `## Pending` section.
6. **Retire `automation-opportunities.md` from injection:** move it to `reference/automation-opportunities.md` with frontmatter + an index line (content preserved, no longer injected). Leave `channel-context.md` untouched.
7. **Write frontmatter** on every tree file; write `index.md`.
8. **Verify:** `check-memory.sh` until clean. Then confirm the numbers: every byte of legacy content is accounted for (backup + new tree + archive). Nothing may be summarized away silently — when in doubt, move verbatim into the matching file's `## Detail`.
9. **Report** (final message of the task): before/after sizes of the four injected files, list of created tree files, count of rules before/after dedup+merge, anything you were unsure about.

### Workspace phase (Sunday routine, after the memory passes)

If your project also uses its root as a working directory for an agent, keep it organized: system files + standard dirs only. Working files live in `projects/<name>/`; one-off intermediates belong in a temp directory (they should never have been written to the project root at all).

**Protected — NEVER move, rename, or delete:**
- `CLAUDE.md`, any project config file, anything matching `*state*.json`, `*.state.*`, `*.lock`
- the standard dirs: `memory/ rules/ logs/ media/ conversations/ projects/ task-runs/ state/ audio/`
- any file whose name appears in the project's `CLAUDE.md`, `rules/`, or a skill — run `grep -rl "<filename>" CLAUDE.md rules/ 2>/dev/null` before touching ANY root file; a hit = protected
- any file listed under PROTECTED in the task prompt that invoked you

**Tidy rules (moves only, never delete):**

1. Loose root files that are stale work artifacts (images, CSVs, one-off scripts, error logs, generated docs) older than 14 days and unprotected → move to `projects/archive/YYYY-MM/`, preserving names.
2. Recent (<14d) loose files → leave, list in the report (their session may still be live).
3. Maintain `projects/INDEX.md`: one line per project dir — `- <dir> — <what it is / for whom>` — plus an `archive/` line.
4. Report: files moved, files left, protected hits.

### Workspace reorganization (one-time task, per project)

The deep version of the workspace phase, for the initial cleanup of long-accumulated root clutter. Same protected rules as above, PLUS:

1. **Backup first:** `mkdir -p ./.reorg-backup && cp <every file you will move> ./.reorg-backup/` — verify before moving anything.
2. Classify EVERY loose root file: protected / active-recent / archivable. When unsure, protected wins.
3. Archivable → `projects/archive/YYYY-MM/` by the file's mtime month. Related clusters (e.g. a batch of images+pdf from one job) go into a named subdir (`projects/archive/2026-05/image-batch/`).
4. Node litter (`package.json`, `package-lock.json`, `node_modules/` at root) → archive the json files; `node_modules/` at root may be DELETED (regenerable, never unique work) — the ONE deletion allowed.
5. Create/refresh `projects/INDEX.md` covering every project dir + archive.
6. Report: full manifest of moves, protected list with reasons, anything ambiguous.

### Scripts

- `scripts/check-memory.sh` — mechanical validation. Checks caps (profile 80 / index 50 / weekly 80 lines, LC 60 rules), exactly one week header in `weekly-summary.md`, frontmatter completeness on tree files, index↔tree consistency both directions, LC format (one-liners, ids, Pending present, no scaffolding blocks, no verbatim duplicates). Prints `OK` or `VIOLATION:` lines; exit 1 on violations. Scope via `MEMORY_CHECK_SCOPE`: `full` (default — also checks `projects/INDEX.md` coverage and workspace-root clutter) or `memory` (`memory/` + `rules/` only — use where `projects/` belongs to a pipeline rather than to the memory routines; an unknown value exits 2).
- `scripts/archive-week.sh` — moves the current weekly-summary content to `weekly-archive/<year>-W<nn>.md` and writes a fresh header. Safe to run only from the Sunday routine.
