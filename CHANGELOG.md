# Changelog

## 1.0.1 - 2026-09-08

Punctuation pass: em and en dashes removed from all skill text, README and changelog, per Scalably's style rule. No procedural changes.

## 1.0.0 - 2026-09-08

Initial release: 22 skills across two plugins.

### agent-ops (14)

- research
- report
- automation
- prompt
- memory
- memory-system
- runtime-constraints
- browser-scrape
- publish-html
- daily-log
- dream
- weekly-memory-cleanup
- friday-feedback
- workspace-reorg

### seo-ops (8)

- anchor-policy
- webmaster-policy
- classify
- link-insertion-finder
- batch-contact-email
- lead-pipeline
- internal-linking
- guest-post-writer

### deferred

- Tier C client-shaped content skills (four) are not in 1.0.0.
- internal-linking Mode B edited-anchor sub-flow not carried over: the production skill can propose a minimal text edit (`BEFORE:`/`AFTER:`) when no verbatim anchor exists for a strong target, clearly labeled unvalidated until confirmed; this release keeps only the verbatim-anchor path.
- classify has no Google Sheets output option: batch-contact-email supports writing results to a Sheets MCP server or `gspread`, classify supports CSV/XLSX only.
