---
name: daily-log
description: "Extracts a structured evidence ledger from today's session transcripts — actions, corrections, positive signals, workflow patterns, each tagged with an evidence-strength label — and writes it to ./memory/daily/YYYY-MM-DD.md, the input the dream skill consolidates into long-term memory. Use for a daily log, an end-of-day summary, a daily wrap-up, to summarize today's conversations, or a nightly digest. Not for long-term memory consolidation itself — that's the dream skill, which reads this skill's output the next time it runs."
license: MIT
metadata:
  source: https://scalably.io/skills/daily-log
  derived_from:
    path: container/prompts/tasks/daily-log-per-user.md
    commit: d4ddad11
    date: "2026-09-07"
  triggers: [daily log, end of day summary, daily wrap-up, summarize today's conversations, nightly digest]
  not_for: ["Long-term memory consolidation itself — that's the dream skill, which reads this skill's output the next time it runs."]
---

# Daily Log — Daily Conversation Summary

## What it does

Extracts a structured evidence ledger from today's session transcripts: what was done, what was corrected, what went well, and what workflow patterns showed up — each item tagged with an evidence-strength label so nothing gets over-promoted later. Writes it to `./memory/daily/YYYY-MM-DD.md`. This file is the raw input three other things read: the `dream` skill (extracts durable facts and rules into long-term memory), session-context injection on future runs, and the `friday-feedback` skill (personalizes the weekly check-in). Write it carefully — the whole memory system is only as good as this ledger.

## Requirements

- Read access to this session's own transcript for the day. For Claude Code, that's `~/.claude/projects/<project>/*.jsonl` (`<project>` is the working-directory path with `/` replaced by `-`); other runtimes keep an equivalent per-session log — substitute its path.
- Optional: a Search Console tool, to append yesterday's click count to the Summary. Free option: none required — if you don't have one wired up, skip that line entirely.

## Inputs and outputs

| | |
|---|---|
| Input | Today's session transcript(s) for this project |
| Output | `./memory/daily/YYYY-MM-DD.md` in the fixed evidence-ledger format below — or nothing at all on a quiet day with no human activity |

## Worked example

Paste into Claude Code with this skill installed, at the end of a working day:

```text
/agent-ops:daily-log
```

Expected: the skill finds today's session transcripts under `~/.claude/projects/<project>/`, greps them for user/assistant turns, and writes `./memory/daily/2026-09-07.md` with `## Summary`, `## Actions`, `## Corrections & Feedback`, `## Positive Signals`, `## Workflow Patterns`, `## Agent/System Notes`, and `## Participants` sections. If no session ran today, it writes nothing and says so — it never invents a day's activity from yesterday's log or from memory files.

## How to schedule this

Claude Code scheduled task (interactive): run `/schedule` and describe the cadence, e.g. "every day at 23:30 run /agent-ops:dream". The task runs the skill in a fresh session.

Cron, from any machine with Claude Code installed:

```bash
30 23 * * * cd /path/to/project && claude -p "/agent-ops:dream" >> logs/dream.log 2>&1
```

Use `0 9 * * 1` for weekly Monday-morning skills and `0 16 * * 5` for the Friday check-in.

## Procedure

### Why this matters

The daily log is the primary input for three downstream consumers:

1. **The `dream` skill** — extracts corrections, preferences, and patterns into long-term memory.
2. **Context injection** — read (or otherwise surfaced) on future sessions, however your runtime handles that.
3. **The `friday-feedback` skill** — used to personalize the weekly check-in.

Write it well and the entire memory system benefits; write it sloppily and every downstream consumer inherits the noise.

### Evidence contract

The daily log is an evidence ledger, not authority to invent a preference. Tag every correction, positive signal, or workflow pattern with exactly one source tag:

- `[source:user-explicit]` — requires an exact human quote that explicitly states, corrects, approves, or makes durable the recorded behavior. Preserve whether its scope is `standing`, `project`, or `one-time`.
- `[source:user-repeated]` — requires the same behavior in at least two distinct human interactions; cite both dates. It is an observation, not a learned correction.
- `[source:observed-once]` — records one occurrence only. Never approval, preference, or promotion evidence.
- `[source:agent]`, `[source:system]`, `[source:tool]` — non-promotable. Never attribute the assistant's own suggestion, template, qualification, or tool decision to the user.
- Continuing without complaint is NOT approval. Approval requires an explicit quote such as "yes", "approved", "works", or an equally clear acceptance.
- A one-time routing/task instruction belongs in Actions or current project state — it is not a standing preference unless the human explicitly says so.
- Never persist a raw phone number. Use a stable non-phone identity when available; otherwise the verified display name.

### 1. Find today's transcripts

Session transcripts for the current project live at `~/.claude/projects/<project>/*.jsonl` (Claude Code); other runtimes keep an equivalent per-session log directory — substitute its path below.

```bash
find ~/.claude/projects/ -name "*.jsonl" -mmin -1440 -not -path "*/subagents/*" -type f 2>/dev/null
```

**Hard rule — file reads:** never use a whole-file Read on raw session `.jsonl` files; they are large and a whole-file read fails or is wasteful. Use the grep/Bash extraction in step 2 instead. For any file you do Read in full (`.md`, `.json`, `.log`), pass `offset`/`limit` — start with `limit=500` and page via `offset`; never read a whole large file in one call. If a Read errors on size, immediately retry the same file paginated rather than abandoning it.

If the find returns **zero files**, today had no activity on this project. Write nothing and stop. Do NOT retry with a different path, read yesterday's daily log to "fill in", read memory files to infer what might have happened, or fabricate activity. A missing session is a quiet day.

### 2. Extract messages

Do NOT read entire JSONL files — grep for the messages you need:

```bash
grep -h '"type":"user"\|"type":"assistant"' /path/to/session.jsonl | head -300
```

Parse the JSON lines to get: user messages (sender name/id, content) and assistant messages (text responses, tool calls made).

**Capture first, classify by evidence second.** Across the sections in step 3, capture decisions, deliverables, failures, explicit corrections, explicit approval, repeated workflows, one-time observations, and project context. Attach one `source:` tag from the evidence contract to every correction, positive signal, or workflow pattern. If the exact source or scope is unclear, downgrade it to `[source:observed-once]` or omit it — never strengthen a paraphrase.

If the session is long (grep returns >300 matches), paginate with additional `| tail -N` passes rather than silently truncating — missed end-of-session corrections are the most common dropped signal.

### Failure rule

A `[failed]` entry MUST be backed by concrete evidence from the transcript you just grepped:

1. The session JSONL contained a `tool_result` with `"is_error":true`, OR an assistant text that explicitly reports a tool/API failure.
2. Cite the exact failing tool name (e.g. `Bash`, `WebFetch`, or a Search Console tool if one is wired up) and a short direct quote from the error message.

If you cannot cite both the tool name AND a quoted error from the transcript, DO NOT write a `[failed]` item — omit it silently. Do NOT infer failures from tone or hesitation in the agent's prose, from a keyword like "auth" or "webmaster" appearing in unrelated context (a column name, a subagent name), from general knowledge of what "could have gone wrong", or by matching an unrelated service's error to the wrong tool. Accuracy beats completeness: a missed failure is recoverable next day; an invented failure poisons the memory system permanently — it gets pulled into `dream` consolidation, `friday-feedback`, and future session context.

### 3. Write the daily log

Write to `./memory/daily/YYYY-MM-DD.md` (create the directory if needed) using exactly this format:

```markdown
# Daily Log — YYYY-MM-DD

## Summary
2-3 sentences: what was worked on today, who was involved.
(optional — if a Search Console tool is available, append yesterday's click count here; otherwise skip this line)

## Actions
- [done] Completed task with specifics
- [pending] Task mentioned but not finished
- [promised] Something the agent offered and user accepted

## Corrections & Feedback
Only explicit human evidence can be a correction or preference:
- [source:user-explicit scope:standing|project|one-time] **Name** corrected: "exact quote" (category: factual|preference|tool issue)
- [source:user-explicit scope:standing|project|one-time] **Name** unsatisfied: "exact quote" (category)
- [source:agent] Agent self-corrected for **Name**: what was fixed

## Positive Signals
- [source:user-explicit] **Name** praised/approved: "exact quote" — what went well
- [source:observed-once] **Name** continued the workflow — observation only, not approval

## Workflow Patterns
- [recurring source:user-repeated dates:YYYY-MM-DD,YYYY-MM-DD] **Name**: repeated workflow
- [template source:user-explicit scope:standing|project] **Name**: explicitly confirmed format/process
- [sequence source:user-repeated dates:YYYY-MM-DD,YYYY-MM-DD] **Name**: step1 → step2 → step3
- [observed-once source:observed-once] **Name**: one occurrence; never promote

## Agent/System Notes
- [source:agent|system|tool] Non-promotable operational context, if needed

## Participants
- Name (stable non-phone ID; otherwise name only)
```

### Examples

**Active day:**

```markdown
# Daily Log — 2026-04-01

## Summary
User-A filtered 3 batches of websites by niche and extracted emails for example.com. Morning task briefing was delivered automatically.

## Actions
- [done] Filtered ~100 websites — removed news, India, casino, delivered 73 clean tech/business sites as CSV
- [done] Matched 91 websites suitable for example.com — CSV delivered
- [done] Scheduled task briefing sent at 10:30

## Corrections & Feedback
- [source:user-explicit scope:standing] **User-A** corrected: "give me categories in this form: category, category,..." (preference)
- [source:user-explicit scope:standing] **User-A** corrected: "write even those that repeat please" (preference)

## Positive Signals
- [source:observed-once] **User-A** continued sending batches — observation only, not approval

## Workflow Patterns
- [observed-once source:observed-once] **User-A**: website filtering seen in this session
- [template source:user-explicit scope:standing] **User-A**: comma-separated category output

## Agent/System Notes
No promotable agent/system notes.

## Participants
- User-A (U000000001)
```

**Quiet day:**

```markdown
# Daily Log — 2026-04-01

## Summary
Only an automated task briefing today. No human interaction.

## Actions
- [done] Daily task briefing sent — 20 tasks: 3 overdue, 5 due today

## Corrections & Feedback
No corrections detected.

## Positive Signals
No positive signals detected.

## Workflow Patterns
- [source:system] Automated daily task briefing

## Agent/System Notes
- [source:system] Automated daily task briefing ran

## Participants
No human participants today — automated task only.
```

### Delivery

This skill produces no chat output beyond a brief internal confirmation. After writing the file, tell the caller the path you wrote to (`./memory/daily/YYYY-MM-DD.md`) — do not route the content through a separate messaging or file-delivery mechanism.
