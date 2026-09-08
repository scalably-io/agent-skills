# Scalably Skills Library

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Agent Skills](https://img.shields.io/badge/Agent_Skills-compatible-01e9ac)

Contains 22 skills Scalably runs in production, genericized: research, reporting, memory, publishing, and runtime discipline for any agent (`agent-ops`), plus link building and content operations for SEO work (`seo-ops`). Every skill here is a real, in-use production procedure with client names, internal tool paths, and proprietary identifiers stripped out, not a demo written for this release.

Built and maintained by [Scalably](https://scalably.io). License: MIT.

## Install in Claude Code

```
/plugin marketplace add scalably-io/agent-skills
/plugin install agent-ops@scalably-agent-skills
/plugin install seo-ops@scalably-agent-skills
```

## Try without installing

```
claude --plugin-dir ~/path/agent-skills
```

Points a single Claude Code session at this repo's plugins without touching your marketplace config. With `--plugin-dir`, skills load under the directory name rather than the marketplace plugin name; invoke them as `/agent-skills:<name>` (e.g. `/agent-skills:research`), not `/agent-ops:` or `/seo-ops:`.

## Codex

Codex doesn't read plugin marketplaces. Copy the skill folder(s) you want straight into your project:

```
cp -R skills/research .agents/skills/
```

Skills that link to sibling skills (`../<name>/SKILL.md`) expect those siblings to be alongside them; copy the whole `skills/` directory instead of a single folder to keep those links working.

## Any Agent Skills runtime

Every skill is a self-contained folder: `SKILL.md` plus, where needed, a `references/` or `scripts/` subfolder. Copy the folder into wherever your runtime looks for skills; nothing here depends on the Claude Code plugin system to function.

## Skills (22)

| Skill | Plugin | What it does |
|---|---|---|
| [research](skills/research/) | agent-ops | Runs parallel research across several angles of a topic, each in its own subagent, then triangulates the findings and writes a cited report. [→](https://scalably.io/skills/research) |
| [report](skills/report/) | agent-ops | Turns data into a polished, single-file HTML report by filling in a pre-built template's modular sections instead of writing report HTML from scratch. [→](https://scalably.io/skills/report) |
| [automation](skills/automation/) | agent-ops | Handles repetitive, mechanical data work with a short script instead of processing it item-by-item as an agent. [→](https://scalably.io/skills/automation) |
| [prompt](skills/prompt/) | agent-ops | Rewrites a rough task description or question into a single, tightly structured, copy-pasteable prompt for an agentic coding assistant. [→](https://scalably.io/skills/prompt) |
| [memory](skills/memory/) | agent-ops | Gives an agent durable memory across sessions using nothing but plain files (no database, no vector store, no memory API). [→](https://scalably.io/skills/memory) |
| [memory-system](skills/memory-system/) | agent-ops | Defines how a project's file-based memory is structured and kept clean: directory layout, frontmatter, size caps, and a mechanical validator. [→](https://scalably.io/skills/memory-system) |
| [runtime-constraints](skills/runtime-constraints/) | agent-ops | A discipline for working across unpredictable agent runtimes: probe before you assume, install to scratch, treat blocked paths as hard boundaries. [→](https://scalably.io/skills/runtime-constraints) |
| [browser-scrape](skills/browser-scrape/) | agent-ops | Fetches and extracts content from public web pages using Scrapling, escalating from a plain HTTP fetch to a stealth browser only as needed. [→](https://scalably.io/skills/browser-scrape) |
| [publish-html](skills/publish-html/) | agent-ops | Publishes a finished HTML file to a public URL after running a mandatory QA gate that catches the failure modes that actually ship broken pages. [→](https://scalably.io/skills/publish-html) |
| [daily-log](skills/daily-log/) | agent-ops | Extracts a structured evidence ledger from today's session transcripts (what was done, corrected, and what patterns showed up) for the memory system to consume. [→](https://scalably.io/skills/daily-log) |
| [dream](skills/dream/) | agent-ops | Nightly memory-consolidation pass: files daily-log facts into the memory tree, integrates corrections, and verifies the tree with a mechanical check script. [→](https://scalably.io/skills/dream) |
| [weekly-memory-cleanup](skills/weekly-memory-cleanup/) | agent-ops | Runs the nightly memory routine plus a deeper Sunday pass: archives the week, dedupes rules, and rebuilds the memory index from scratch. [→](https://scalably.io/skills/weekly-memory-cleanup) |
| [friday-feedback](skills/friday-feedback/) | agent-ops | Runs a weekly self-reflection check-in that asks the user what to improve and whether anything should be automated, based on the week's daily logs. [→](https://scalably.io/skills/friday-feedback) |
| [workspace-reorg](skills/workspace-reorg/) | agent-ops | One-time reorganization of a project's workspace root: classifies loose files, backs them up, and archives them by month into an organized structure. [→](https://scalably.io/skills/workspace-reorg) |
| [anchor-policy](skills/anchor-policy/) | seo-ops | Validates anchor placement, URL correctness, and SEO positioning in a guest-post draft against the canonical Standard/PR and Listicle anchor rules. [→](https://scalably.io/skills/anchor-policy) |
| [webmaster-policy](skills/webmaster-policy/) | seo-ops | Validates a guest-post draft against a target site's webmaster requirements (formatting, prohibited topics, word count, and image rules). [→](https://scalably.io/skills/webmaster-policy) |
| [classify](skills/classify/) | seo-ops | Labels a batch of website domains with a primary niche, secondary niche, and confidence, from a fixed niche list. [→](https://scalably.io/skills/classify) |
| [link-insertion-finder](skills/link-insertion-finder/) | seo-ops | Finds the 3 best existing articles on a target site for inserting a backlink, given anchor text and a destination URL. [→](https://scalably.io/skills/link-insertion-finder) |
| [batch-contact-email](skills/batch-contact-email/) | seo-ops | Pure email lookup for an already-vetted domain list: scrapes contact pages first, falls back to a paid API only when scraping finds nothing. [→](https://scalably.io/skills/batch-contact-email) |
| [lead-pipeline](skills/lead-pipeline/) | seo-ops | Orchestrates a full outbound lead-generation run in one session: discover, qualify, enrich, personalize, and deliver a ready-to-send CSV. [→](https://scalably.io/skills/lead-pipeline) |
| [internal-linking](skills/internal-linking/) | seo-ops | Proposes internal links from a set of source pages to target pages you want to boost, with anchor text taken verbatim from the source's own body prose. [→](https://scalably.io/skills/internal-linking) |
| [guest-post-writer](skills/guest-post-writer/) | seo-ops | Writes a complete guest-post article from a brief through a deterministic pipeline: research, draft, quality pass, policy checks, images, and DOCX export. [→](https://scalably.io/skills/guest-post-writer) |

## Requirements philosophy

Every external dependency named in a skill's Requirements has a free option: the skill is fully runnable with zero paid credentials, degrading gracefully rather than blocking. Ahrefs, DataForSEO, Hunter.io, and Snov.io appear only as optional upgrades, named explicitly wherever a skill uses one, alongside the free path it falls back to.

## Privacy

No telemetry. Nothing runs on install: installing a plugin or copying a skill folder executes no code. Scripts inside a skill (`references/`, `scripts/`) run only when that skill's own procedure explicitly calls them, driven by the agent following `SKILL.md`, never automatically. Every skill here is derived from a real production procedure with client names, internal identifiers, and proprietary tool paths removed, and checked by a private scanner before every release.

## Versioning

Plugin versions (`agent-ops`, `seo-ops`) are bumped by hand and listed in [CHANGELOG.md](CHANGELOG.md).

## License

MIT, see [LICENSE](LICENSE).
