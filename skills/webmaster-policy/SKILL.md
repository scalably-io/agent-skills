---
name: webmaster-policy
description: "Validate a guest-post draft against a target site's webmaster requirements — checks formatting, structure, prohibited topics, word count, section constraints, and image formatting with descriptive captions. Triggers: webmaster policy, check requirements, webmaster requirements, policy check, validate draft, content requirements, site requirements, webmaster QA."
license: MIT
metadata:
  source: https://scalably.io/skills/webmaster-policy
  derived_from:
    path: overrides/skills/webmaster-policy/SKILL.md
    commit: f0f1753
    date: "2026-09-07"
  triggers: [webmaster policy, check requirements, webmaster requirements, policy check, validate draft, content requirements, site requirements, webmaster QA]
  not_for:
    - "Anchor link validation — use anchor-policy for that"
    - "Writing the article itself — use guest-post-writer for that"
---

# Webmaster Policy

## What it does

Validates a guest-post draft against a target site's webmaster requirements: formatting and structural rules, prohibited topics or claims, word-count and section constraints, and image formatting (position and captions). Returns a pass/fail verdict with the exact requirement violated and actionable remediation. Defaults to fail-safe — an ambiguous requirement is treated as unmet, not waved through.

## Requirements

- None; input is a draft file and the target site's webmaster requirements (a short list of formatting/topic/word-count rules). No external tools or network access needed.

## Inputs and outputs

| | |
|---|---|
| Input | A draft (markdown or plain text) plus the target site's webmaster requirements: formatting/structure rules, prohibited topics or claims (if any), a word-count range, and image rules |
| Output | A pass/fail JSON verdict: `{"pass": bool, "failed_rules": [...], "notes": [...]}` |

## Worked example

Paste into Claude Code with this skill installed:

```text
/seo-ops:webmaster-policy check this draft against the site's requirements.

Requirements:
- 400-600 words
- No pricing claims
- Every image needs a specific, descriptive caption (no "Stock photo" or "AI generated" labels)

Draft:
## Getting Started With Cloud Backup
Cloud backup keeps your files safe even if a laptop is lost or a drive fails.

![Backup dashboard](https://example.com/img-1.png)
*Stock photo*

Most small teams can set up automated backups in under an hour, without needing a full IT department.
```

Expected verdict:

```json
{
  "pass": false,
  "failed_rules": ["5"],
  "notes": ["The caption \"Stock photo\" is a generic label, not a specific description of what the image shows — rule 5 fails. Fix: replace it with a caption describing the actual dashboard screenshot (e.g. \"The backup dashboard showing a completed nightly sync\")."]
}
```

## Procedure

### 1. Read the requirements

Take the target site's webmaster requirements as given in the input — do not infer requirements that were not stated.

### 2. Validate

Check the draft against each of the following, using only what the target site's own requirements specify:

1. The draft satisfies every mandatory formatting and structural requirement (headings, sections, required elements).
2. The draft avoids any prohibited topic or claim, if any were specified.
3. The draft's word count and section structure match the stated constraints.
4. Every image sits at the start of its section (right after the H2/H3), not at the end.
5. Every image has a specific, descriptive caption — never a generic label like "AI generated" or "Stock photo".

Any violation fails QA. If a requirement is ambiguous or under-specified, default to fail-safe: mark it failed and say why, rather than assuming compliance.

### 3. Report

Return JSON:

```json
{
  "pass": true,
  "failed_rules": [],
  "notes": []
}
```

When failing, set `pass=false`, list every violated requirement (by the numbering in step 2, or the target site's own rule label if it has one) in `failed_rules`, and give one concrete remediation per failure in `notes`.

<verification>
Before returning a verdict:
1. Every requirement in step 2 was checked explicitly — no silent omissions.
2. Each failed item has a specific reason tied to the draft text, not a generic statement.
3. Remediation guidance says exactly what to change, not just what is wrong.
4. Never mark a requirement compliant when the evidence needed to check it is missing — fail safe (`pass=false`) instead, and say what evidence is missing.
</verification>
