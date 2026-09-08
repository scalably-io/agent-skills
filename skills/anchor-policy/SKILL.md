---
name: anchor-policy
description: "Validate anchor text placement, URL correctness, and SEO positioning in a guest-post draft against a target anchor spec: checks that anchors land in the correct sections, the primary anchor is the first external link, the introduction is link-free, and spacing rules are met, for both the Standard/PR and Listicle anchor models. Triggers: check anchors, validate links, anchor policy, anchor compliance, verify anchor text, anchor QA, link placement check."
license: MIT
metadata:
  source: https://scalably.io/skills/anchor-policy
  derived_from:
    path: overrides/skills/anchor-policy/SKILL.md
    commit: f0f1753
    date: "2026-09-07"
  triggers: [check anchors, validate links, anchor policy, anchor compliance, verify anchor text, anchor QA, link placement check]
  not_for:
    - "Writing or editing article content: use guest-post-writer for that"
    - "Checking whether external URLs are live or reachable"
---

# Anchor Policy

## What it does

Validates anchor placement, URL correctness, and SEO positioning in a guest-post draft against the canonical anchor rules, for both anchor models a guest post can use: **Standard/PR** (rules S1-S9) and **Listicle** (rules L1-L9). The two models are mutually exclusive; the skill reads the article type first and applies only the matching rule set. Returns a pass/fail verdict with the exact rule(s) violated and actionable remediation.

## Requirements

- None; input is a draft file and a target URL (plus the anchor spec described below). No external tools or network access needed.

## Inputs and outputs

| | |
|---|---|
| Input | A draft (markdown or plain text) plus an anchor spec: article type (`Standard`/`PR` or `Listicle`), Anchor 1 text + URL, and Anchor 2 text + URL if a second anchor exists |
| Output | A pass/fail JSON verdict: `{"pass": bool, "failed_rules": [...], "notes": [...]}` |

## Worked example

Paste into Claude Code with this skill installed:

```text
/seo-ops:anchor-policy check this draft against the anchor spec below.

Spec:
- Article type: Standard
- Anchor 1: "cloud backup service" -> https://example.org/backup

Draft:
## Why Backups Matter
Losing data is costly, so many teams turn to [cloud backup](https://example.org/backup) to stay safe.
```

Expected verdict:

```json
{
  "pass": false,
  "failed_rules": ["S4"],
  "notes": ["Anchor text is \"cloud backup\" but the spec requires the exact text \"cloud backup service\" (case-sensitive). S4 fails. Fix: change the link text to match the spec exactly."]
}
```

## Procedure

### 1. Read the canonical rules

Read `references/canonical-rules.md` in this skill folder. Determine the article type from the spec (Standard/PR or Listicle) before checking anything else; the two rule sets contradict each other on purpose and must never be mixed.

### 2. Validate

Apply every rule in the matching set (S1-S9 for Standard/PR, L1-L9 for Listicle) using the "For QA (validation phase)" section of `canonical-rules.md`. A missing anchor, a URL mismatch, or an unauthorized/competitor link fails QA immediately regardless of any other rule's status.

### 3. Report

Return JSON:

```json
{
  "pass": true,
  "failed_rules": [],
  "notes": []
}
```

When failing, set `pass=false`, list every violated rule ID in `failed_rules` (e.g. `"S2"`, `"L6"`), and give one concrete, actionable remediation per failure in `notes`.

<verification>
Before returning a verdict:
1. Every rule in the matching set (S1-S9 or L1-L9) was checked explicitly; no silent omissions.
2. Each failed rule has a specific reason tied to the draft text, not a generic statement.
3. Remediation guidance says exactly what to change, not just what is wrong.
4. Never mark a rule compliant when the evidence needed to check it (draft text, anchor spec) is missing; fail safe (`pass=false`) instead, and say what evidence is missing.
</verification>
