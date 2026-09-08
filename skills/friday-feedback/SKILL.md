---
name: friday-feedback
description: "Runs a natural weekly check-in: reads the week's daily logs for corrections, frustrations, wins, repeated tasks and manual patterns worth automating, then sends ONE short first-person reflective message — never a numbered survey — asking what to improve and what to automate, and saves any reply to a dated feedback file. Supports an explicit opt-out. Use for Friday feedback, a weekly check-in, asking for feedback, or a weekly reflection. Not for a structured survey or NPS-style questionnaire."
license: MIT
metadata:
  source: https://scalably.io/skills/friday-feedback
  derived_from:
    path: container/prompts/tasks/friday-feedback.md
    commit: e7194cc7
    date: "2026-09-07"
  triggers: [friday feedback, weekly check-in, ask for feedback, weekly reflection]
  not_for: ["A structured survey or NPS-style questionnaire — this skill is deliberately a short, natural, first-person message, never a form."]
---

# Friday Feedback — Weekly Check-In

## What it does

Runs a weekly check-in that is you reflecting on your own performance and asking for guidance — not a survey. Reads the week's daily logs, pulls out corrections, frustrations, wins, repeated requests, and manual patterns worth automating, then sends ONE short, natural, first-person message asking what to improve and whether anything should be automated. If the user replies, saves the response to a dated feedback file. If the user asks to stop, writes an opt-out flag and this skill should no longer be scheduled.

## Requirements

- `./memory/daily/*.md` for the week (written by the `daily-log` skill, or an equivalent daily evidence ledger).
- A way to message the user in the same channel this agent normally talks to them in, and to see a reply in the same session — for Claude Code this is a normal chat turn.

## Inputs and outputs

| | |
|---|---|
| Input | This week's `./memory/daily/*.md`, plus `./memory/profile.md` for the user's name |
| Output | One chat message; if the user replies, `./memory/feedback/{YYYY}-W{NN}.md`; if the user opts out, `./memory/feedback/.opt-out` |

## Worked example

Paste into Claude Code with this skill installed, on a Friday, in a project with at least 3 days of dailies this week:

```text
/agent-ops:friday-feedback
```

Expected: a short chat message like "This week I handled about 40 website lists and 3 email extractions. I know I messed up the category format on Tuesday — that should be fixed now. Anything else I should improve? Also, I noticed you extract emails from lists almost daily — want me to set that up as an automatic pipeline?" — then the skill waits. If the user replies, the reply is saved to `./memory/feedback/2026-W36.md`; if fewer than 3 days of activity happened this week, or `./memory/feedback/.opt-out` exists, the skill does nothing and exits silently.

## How to schedule this

Claude Code scheduled task (interactive): run `/schedule` and describe the cadence, e.g. "every Friday at 16:00 run /agent-ops:friday-feedback". The task runs the skill in a fresh session.

Cron, from any machine with Claude Code installed:

```bash
0 16 * * 5 cd /path/to/project && claude -p "/agent-ops:friday-feedback" >> logs/friday-feedback.log 2>&1
```

## Procedure

### 1. Pre-checks

Opt-out check — if this exists, do nothing else this run:

```bash
[ -f ./memory/feedback/.opt-out ] && echo "OPT_OUT"
```

If `OPT_OUT`, stop immediately.

Activity threshold — count this week's daily logs (Monday through Friday):

```bash
ls ./memory/daily/$(date -d "last monday" +%Y-%m-%d 2>/dev/null || date +%Y-%m-*)*.md 2>/dev/null | wc -l
```

Read this week's daily logs. If fewer than 3 days of activity, skip — not enough to ask about. Stop.

### 2. Analyze the week

Read all daily logs from this week. Identify:

- **Corrections** — times the user said "no", "wrong", corrected you
- **Frustrations** — times the user was unsatisfied, had to repeat themselves
- **Wins** — things that went well, user said "great", "perfect", "thanks"
- **Repeated tasks** — things the user asked you to do 3+ times this week
- **Manual patterns** — tasks the user did themselves that you could automate

### 3. Write ONE natural message

Combine into a single short message (3-5 sentences max):

1. **Brief week summary** — what you worked on together (1 sentence)
2. **Self-reflection** — acknowledge a specific mistake or frustration if any (1 sentence, skip if none)
3. **Improvement ask** — open question about what to get better at (1 sentence)
4. **Automation/feature suggestion** — if you spotted a repeated pattern, suggest automating it. Or ask: "Anything you keep doing manually that I should handle?" (1 sentence)

**Tone rules:**

- First person, casual, direct
- Reference SPECIFIC events from daily logs (dates, tools, tasks)
- Never say "survey", "feedback", "rate", "scale of 1-10"
- Never use emojis
- Never number the questions — it's a conversation, not a form
- If the week was smooth with zero corrections, keep it shorter — just the summary + automation ask

**Examples:**

Active week with corrections:

> "This week I handled about 40 website lists and 3 email extractions. I know I messed up the category format on Tuesday — that should be fixed now. Anything else I should improve? Also, I noticed you extract emails from lists almost daily — want me to set that up as an automatic pipeline?"

Smooth week:

> "Good week — we published 2 dashboard updates and the market research. Anything you'd change about how I work? Or anything you keep doing manually that I could take over?"

Week with new workflow:

> "We set up the link-building pipeline this week — cross-referencing your sheet and finding emails for 151 domains. How's it working so far? Anything to adjust, or any other workflows you want automated?"

### 4. Send and wait

Reply to the user in chat with the message. Then wait. Do NOT follow up. Do NOT send a second message.

### 5. Handle the response

If the user replies in this session:

1. Thank them briefly (one sentence).
2. Save their response:

```bash
mkdir -p ./memory/feedback
```

Write to `./memory/feedback/{YYYY}-W{NN}.md`:

```markdown
# Feedback — Week {N}, {Year}

**Date:** {Friday date}
**User:** {name from profile.md}

## Response
{User's full reply, including transcription if voice message}

## Extracted Items
- **Improvement:** {what they want fixed}
- **Feature request:** {new capability they asked for}
- **Automation request:** {workflow they want automated}
- **Positive:** {what they liked}

## Agent Notes
- {Any context from daily logs that explains the feedback}
```

3. If the user explicitly asks you to stop these check-ins ("don't ask me this", "stop asking", "no more feedback", "opt out"):
   - Create the opt-out flag: `mkdir -p ./memory/feedback && touch ./memory/feedback/.opt-out`
   - If the user opts out, stop scheduling this skill — cancel or disable the recurring task that runs it (for a Claude Code `/schedule` task, that means deleting or turning off that scheduled task).
   - Respond: "Got it, I won't ask again. You can always tell me to restart these anytime."

If no reply comes, do nothing. Never follow up. Never nag.
