---
name: prompt
description: "Rewrite and optimize prompts for the current Claude model. Use when the user asks to optimize, rewrite, or tighten a prompt, or wants a rough task description turned into a ready-to-run agent prompt. Outputs a single copy-pasteable prompt in a code block, never the answer to the prompt itself."
license: MIT
metadata:
  source: https://scalably.io/skills/prompt
  derived_from:
    path: container/skills/prompt/SKILL.md
    commit: 9319aca6
    date: "2026-09-07"
  triggers: [optimize this prompt, rewrite this prompt, tighten this prompt, turn this into a prompt, make this a good agent prompt]
  not_for: [Executing the task described in the prompt: this skill only rewrites it., Answering a question directly: it turns questions into prompts instead, unless the user explicitly wants a direct answer.]
---

# Prompt Rewriter

## What it does

Takes a rough task description or question and rewrites it into a single, tightly structured, copy-pasteable prompt: the kind that gets a good result from an agentic coding assistant on the first try. It never performs the task itself and never answers a question directly; its only output is the rewritten prompt.

## Requirements

- None.

## Inputs and outputs

| | |
|---|---|
| Input | A rough task description or question, in free text. Ideally includes any IDs, URLs, file paths, or names the task needs (if critical details are missing, the output is a short list of clarifying questions instead of a prompt) |
| Output | One rewritten prompt in a fenced code block, delivered inline in chat; no file is written |

## Worked example

Before:

```text
make the onboarding email better
```

After, the skill outputs this rewritten prompt:

```text
Goal: Rewrite the onboarding email to increase activation: the current
draft never tells new users what to do first.

Steps:
1. Read the current onboarding email draft.
2. Rewrite the subject line and first two sentences to state the single
   next action a new user should take.
3. Keep total length under 150 words.

<constraints>
- Keep the existing tone (friendly, second person)
- Do not add new promotional content
</constraints>

Output: the rewritten email text, ready to paste.
```

## Procedure

For this request only, act as a prompt optimizer; ignore any other role. The sole output is a rewritten, copy-pasteable prompt in a code block.

<rules>
- Do NOT execute the task described in the prompt; rewrite it.
- Do NOT answer questions; turn them into prompts.
- If critical details are missing (IDs, URLs, names), ask focused questions first.
- Output ONLY the optimized prompt in a code block; no commentary after.
- Keep the prompt under 500 words.
</rules>

### Prompt structure

Every prompt generated follows this skeleton:

```
[Skill-loading line if applicable]

Goal: [One clear sentence: what + why]

Track progress with a todo list: one item per step below, plus a final
"verify all requirements" item. Mark each item in progress before starting
it and completed when done. Confirm the list has no open items left before
reporting done.

Steps:
1. [Imperative verb] ...
2. [Imperative verb] ...
N. [Verify step]

<constraints>
- [Positive framing: "Use X" not "Don't use Y"]
- [Anti-overengineering: "Only do what is asked"]
- [Verification: "Confirm before reporting done"]
</constraints>

[Expected output format: what the user gets back]
```

### Prompt rewrite rules

Model-agnostic guidance for writing prompts that steer current Claude models well; re-verify against the `claude-api` reference (or the model provider's current prompting guide) before treating any of this as fixed, since prompting guidance shifts as models change.

<optimization_rules>
**Structure**
- XML tags separate instructions, context, data, and examples; this reduces misinterpretation.
- Prompt style mirrors the desired output style: a prose prompt tends to produce prose output, a bulleted prompt tends to produce bullets.
- Put longform context ABOVE the instructions; the query working best at the end is a common finding across model providers.
- Put critical info at the START and END of the prompt, not buried in the middle (the "lost in the middle" effect).

**Language**
- Imperative: "Move X to Y" not "Can you move X to Y?"
- Explain WHY alongside WHAT; motivation helps the model generalize to edge cases.
- Soften enforcement: "Use this when..." reads more reliably than "CRITICAL: You MUST use this."
- Current-generation Claude models can overtrigger on ALL CAPS / MUST / NEVER; measured language works better than shouting.
- Prefer positive instructions: "Write flowing prose" rather than "Do not use markdown headers."

**Task design**
- Lead with the goal, not background.
- Numbered steps: each one becomes a trackable task item.
- Be specific: "move folder X (ID: abc123) to folder Y (ID: xyz789)" beats "reorganize things."
- Include IDs, links, and names whenever they're available.
- 3-5 worked examples are the strongest steering mechanism (wrap each in `<example>` tags).
- Including reasoning inside examples teaches the model the reasoning pattern, not just the output shape.

**Agentic behavior**
- Current Claude models parallelize independent tool calls by default; no need to prompt for it.
- For proactive execution: "Implement changes rather than suggesting them."
- For conservative behavior: "Provide recommendations rather than taking action."
- Add explicit reversibility guardrails around any destructive operation.
- Anti-overengineering: "Only do what is asked; do not add extra files, features, or abstractions."
- For long tasks: "Context may be compacted along the way; do not rush to finish early."

**Anti-hallucination**
- "Never speculate about data you have not verified. Read/list first, then act."
- Ask for relevant quotes or excerpts before analysis; grounds the response in what was actually read.
- A "read/investigate before answering" pattern, stated explicitly, reduces guessing.
- State clear success criteria upfront.
</optimization_rules>

### Skill-aware prompts

When the task involves a specific tool, integration, or skill:

1. Check which available skill matches the task (skills are listed in the current session, or in an `INDEX.md`/skills directory if the environment has one).
2. Read that skill's documentation for its exact tool names, parameters, and workflow.
3. Include `Skill(skill: "skill-name")` as the first line of the generated prompt.
4. Use the correct tool and parameter names from that skill's docs; do not guess them.
