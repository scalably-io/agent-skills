---
name: guest-post-writer
description: "Write a complete guest-post article from a brief (target site, topic, target keyword, anchor and URL) — runs research, drafting, an anti-AI writing-quality pass, anchor and webmaster policy checks, optional image generation, and a DOCX export. Triggers: write guest post, guest post, write article, content article, link building article, write post for site, draft guest post, write blog post for link."
license: MIT
metadata:
  source: https://scalably.io/skills/guest-post-writer
  derived_from:
    path: overrides/skills/guest-post-writer/SKILL.md
    commit: f0f1753
    date: "2026-09-07"
    rules_path: admin-rules/04-writing-quality.md
    rules_commit: 97f1383
  triggers: [write guest post, guest post, write article, content article, link building article, write post for site, draft guest post, write blog post for link]
  not_for:
    - "Processing a whole queue of briefs unattended — run this skill once per brief"
    - "General blog writing unrelated to link-building outreach"
---

# Guest Post Writer

## What it does

Writes a complete guest-post article from a brief — target site, topic, target keyword, anchor text and URL — through a deterministic pipeline: research the topic and target site, draft the article with real links and image markers, run an anti-AI writing-quality pass, validate against [anchor-policy](../anchor-policy/SKILL.md) and [webmaster-policy](../webmaster-policy/SKILL.md), generate or mark images, and export a DOCX. Supports both anchor models — Standard/PR and Listicle — per [anchor-policy/references/canonical-rules.md](../anchor-policy/references/canonical-rules.md).

## Requirements

- Web search and fetch tools for research. Free option: Claude Code's built-in WebSearch/WebFetch.
- Subagents for the research/draft/audit passes. Free option: Claude Code's Agent tool; without it, run the steps sequentially in the same session.
- Image generation (optional): any image-generation tool or MCP available in the environment. No free option; the skill degrades to leaving `<!-- image: <keyword> -->` markers instead of real images.
- Website screenshots (Listicle briefs only, optional): a browser tool that can navigate to a URL and capture a screenshot. Free option: the Playwright CLI (`npx playwright screenshot <url> shot.png`; https://playwright.dev/docs/cli#take-a-screenshot).
- Pandoc, to export the final draft as DOCX: https://pandoc.org (`brew install pandoc` / `apt install pandoc`).
- The [anchor-policy](../anchor-policy/SKILL.md) and [webmaster-policy](../webmaster-policy/SKILL.md) skills for the QA passes (same plugin).

## Inputs and outputs

| | |
|---|---|
| Input | A brief: target site (the domain the article will publish to), topic, target keyword, anchor text, anchor URL, article type (`Standard`/`PR` or `Listicle`), and any webmaster requirements for the target site |
| Output | `./projects/<folder>/draft.md` (final article) and `./projects/<folder>/article.docx` (DOCX export with embedded images or image markers) |

## Worked example

Paste into Claude Code with this skill installed:

```text
/seo-ops:guest-post-writer write a guest post from this brief:
- Target site: example.com
- Topic: cloud backup best practices for small businesses
- Target keyword: cloud backup service
- Anchor: "cloud backup service" -> https://example.org/backup
- Article type: Standard
- Webmaster requirements: 800-1200 words, no pricing claims, one image per H2
```

Expected: `./projects/cloud-backup-example-20260907/draft.md` passes both `anchor-policy` and `webmaster-policy`, and `./projects/cloud-backup-example-20260907/article.docx` is produced with images embedded (or `<!-- image: cloud-backup -->` markers if no image tool is available).

## Procedure

1. **Build the brief.** Write `./projects/<folder>/context.md` from the input brief: target site, topic, target keyword, anchor text + URL (and a second anchor if the brief gives one), article type, and webmaster requirements. This file is shared state — every later step reads it. Article type selects the anchor model for the whole run: Standard/PR uses the Standard rules, Listicle uses the Listicle rules; the two are mutually exclusive. Canonical rules: [anchor-policy/references/canonical-rules.md](../anchor-policy/references/canonical-rules.md).

2. **Research.** Research the target site's tone and existing content, find 3-5 fresh statistics with named sources, 2-4 external authority links, and — if the target site publishes existing content — 2-3 internal links to its own pages (a `site:<target-site>` search finds candidates). Build an outline with anchor placement and image-marker suggestions. Output: `./projects/<folder>/research.md`. Use a subagent for this step if the Agent tool is available; otherwise do it inline in the same session.

3. **Draft.** Write the full article from `research.md` + `context.md`, as a subagent if available. Include the external links, internal links, and a marker for each intended image — `<!-- image: <keyword>: <description> -->` — directly in the draft at the point the image belongs, not as a later addition. For a Listicle brief, also add one `<!-- screenshot: <company name> -->` marker under each listed company's entry, including competitors. Output: `./projects/<folder>/draft.md`.

4. **Writing-quality pass.** Apply every rule in [references/writing-quality.md](references/writing-quality.md) before finalizing the draft. This is a two-pass process — draft, audit, rewrite — move on only after the rewrite.

5. **Anchor check.** Invoke [anchor-policy](../anchor-policy/SKILL.md) against `draft.md` and the brief's anchor spec.

6. **Webmaster check.** Invoke [webmaster-policy](../webmaster-policy/SKILL.md) against `draft.md` and the brief's webmaster requirements.

7. **Repair loop.** If either check fails, fix and re-run — up to 3 rounds. A QA failure is work to do, not a reason to stop:
   - *Mechanical* failures (an unsourced statistic, a banned word, a generic image caption, an unauthorized link): fix directly with a targeted edit to `draft.md`. For an unsourced statistic, check `research.md` first — the source is usually already there; name it inline, or delete the statistic if `research.md` truly has no source for it.
   - *Structural* failures (AI-sounding tone, a missing section, a short word count, wrong anchor placement): rewrite the affected section, quoting the checker's failed rule(s) verbatim so the fix targets exactly that rule and nothing else.
   - Re-run the failed checker after a mechanical fix; re-run BOTH checkers after any rewrite, since a rewrite can regress the other check. Stop only after 3 rounds where the same finding keeps surviving, and say so plainly in the final output rather than declaring success.

8. **Images.** For every `<!-- image: -->` marker: if an image-generation tool is available, generate a real image (prompt built from the marker's description plus surrounding article context), save it to `./projects/<folder>/images/img-<keyword>.png`, and replace the marker with a standard markdown image pointing at that real path. If no image tool is available, leave the marker as-is and say so in the final output.

   For every `<!-- screenshot: -->` marker (Listicle briefs only): capture that company's site with a browser screenshot tool — see Requirements — save it under `./projects/<folder>/images/`, and replace the marker with a standard markdown image pointing at the saved file. Per the Listicle rules, a competitor's screenshot is never wrapped in a link and never carries a linked source caption; only the client's screenshot may link to the client URL.

9. **Convert to DOCX.**
   ```bash
   echo 'function Image(el) el.attributes.width = "6in" return el end' > /tmp/pandoc-fullwidth.lua
   pandoc ./projects/<folder>/draft.md --resource-path=./projects/<folder> --lua-filter=/tmp/pandoc-fullwidth.lua -o ./projects/<folder>/article.docx
   ```

10. **Final DOCX QA.** Open the generated DOCX and verify: images are present and visible (not broken), images run full column width (not small thumbnails with text wrapped beside them), captions sit cleanly below their image rather than floating beside it, and no unresolved `<!-- image: -->` or `<!-- screenshot: -->` marker remains (unless step 8's no-tool fallback deliberately left one, in which case the final output says so). If any of these are wrong, fix `draft.md` and reconvert.

11. **Deliver.** Reply to the user in chat with the paths to `draft.md` and `article.docx`, plus a short completeness note: any missing input, any assumption made, and anything that did not converge after 3 repair rounds.

<verification>
Before delivering:
1. `draft.md` includes 2-4 external links to named authoritative sources and, if the target site has existing content, 2-3 internal links to it.
2. Anchors are placed per the anchor model for the article type (see anchor-policy).
3. Every `<!-- image: -->` and `<!-- screenshot: -->` marker is resolved to a real image, or deliberately left as-is with a note in the final output — never silently dropped.
4. Both anchor-policy and webmaster-policy pass, or the final output states plainly which check still fails and why.
5. `article.docx` opens with images visible at full width and no leftover placeholder text.
</verification>
