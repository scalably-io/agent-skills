---
name: classify
description: "Batch-classify a list of website domains by niche (primary + secondary + confidence): scrapes each homepage and about page, then tags each domain against a niche rubric. Does not filter, score quality, or find contact emails, only tags. Triggers: classify domains, classify niches, niche classification, categorize websites, tag domains, bulk classify, classify sites."
license: MIT
metadata:
  source: https://scalably.io/skills/classify
  derived_from:
    path: overrides/skills/classify/SKILL.md
    commit: f0f1753
    date: "2026-09-08"
  triggers: [classify domains, classify niches, niche classification, categorize websites, tag domains, bulk classify, classify sites]
  not_for:
    - "Filtering a list by quality/region, extracting contact emails, or delivering a survivors list: pair this with a separate filter/email pass"
    - "Deep single-site analysis or competitor research: use a research skill"
    - "Single-domain qualitative judgment calls: answer directly, no batch pipeline needed"
---

# Classify

## What it does

Labels a batch of website domains with a primary niche, secondary niche, and confidence, from a fixed niche list (default or caller-supplied). For each domain: scrapes the homepage plus an about page, then tags the pair against a niche rubric: one clear definition per niche plus a few worked examples, since bare niche names alone cause keyword-adjacency mis-tags (a hedge fund site mentioning "AI" is Finance, not AI, because it doesn't sell AI as the product). Emits one row per input domain; never drops a domain, marks unresolvable ones `Unclassified` instead.

## Requirements

- Node.js 18+ (both companion scripts use the global `fetch` and standard library only).
- Domain classification via an LLM: either `ANTHROPIC_API_KEY` (direct Anthropic API, cheapest) or the Claude Code CLI (`claude -p --model haiku`) on PATH. `ANTHROPIC_BASE_URL` (optional, defaults to `https://api.anthropic.com`); set it to point the direct-API path at a compatible proxy or gateway. Free option: run classification through Claude Code itself: dispatch parallel subagents with the rubric below instead of the standalone script (see Procedure step 3, both paths documented).
- Optional bulk crawling substitute: [Scrapling](https://github.com/D4Vinci/Scrapling) (`pip install "scrapling[fetchers]"`) if you prefer a browser-capable crawler over the included plain-HTTP `scraper.mjs` for JS-heavy or Cloudflare-protected sites; verified 2026-09-08 from the project README (`scrapling extract get/fetch/stealthy-fetch <url> <output>`).
- xlsx/csv input or output (optional): Python + `openpyxl`/`pandas`, or any spreadsheet tool.

## Inputs and outputs

| | |
|---|---|
| Input | A domain list (raw text, one per line; or a CSV/XLSX with a domain column) and an optional niche list (defaults to a 16-niche generalist set: SaaS, Finance, Marketing, iGaming, Crypto, E-commerce, Business, Technology, AI, Health, Education, Travel, Lifestyle, Home & Decor, Productivity, Personal Development) |
| Output | `./output/classified-<YYYYMMDD>.csv` with columns `Domain, Primary Niche, Secondary Niche, Confidence` (or the input file updated in place if it was a CSV/XLSX) |

## Worked example

Paste into Claude Code with this skill installed:

```text
/seo-ops:classify classify these domains by niche:
example.com
example.org
example.net
```

Expected: a table (or `./output/classified-20260908.csv` for larger batches) with one row per domain (`example.com, Technology, SaaS, high`); every input domain present, none dropped, low-confidence rows flagged for a second look.

## Procedure

1. **Parse input.** Extract the domain list: a CSV/XLSX (auto-detect the domain column: "Domain", "URL", "Website", or the first column), or raw text (one domain per line). Normalize (lowercase, strip scheme/whitespace, dedupe) while keeping a mapping back to the original rows if writing results back to the source file.

2. **Confirm the niche list.** Use the caller's niches if given, else the 16-niche default above.

3. **Scrape.** Write the normalized domains one per line to a temp file, then run the bounded scraper:
   ```bash
   node <skill dir>/references/scraper.mjs domains.json scraped.json
   ```
   (`<skill dir>` is wherever this skill's files live in your setup. After
   a plugin install, find it with `find ~/.claude/plugins -path
   '*/classify/SKILL.md'` and use its parent directory; from inside the
   skill's own folder, just `node references/scraper.mjs ...`. `domains.json`
   is a JSON array of bare domains.) It fetches the homepage (falling back `https://` → `http://`) plus a discovered `/about` page, extracts title/meta/headings/body text, and writes `scraped.json`: one `{domain,title,meta,headings,body,aboutBody,status}` record per domain, `status:"error"` on DNS/HTTP failure. Adaptive concurrency (starts at 30, halves on a >50% error-rate batch) and periodic checkpointing mean an interrupted run resumes from `scraped.json` on retry. If a batch is dominated by JS-rendered or Cloudflare-protected sites, swap in Scrapling (see Requirements) for the fetch step instead; the schema classification consumes is the same shape.

4. **Build the rubric.** Before classifying, write a one-line **definition** per niche (the core business that IS this niche, not a keyword it merely mentions) plus these principles, verbatim: they are what keeps a small/fast model accurate:
   - **Evidence first**: state the site's primary business before tagging.
   - **Primary, not keyword**: tag the primary business, not an incidental feature.
   - **Is, not uses**: a site that USES a technology isn't necessarily IN that niche (a quant fund using ML internally is Finance, not AI).
   - **No forcing**: if nothing fits well, pick the closest and mark confidence low; don't invent a fit.

   Add 2-3 few-shot examples, including one near-miss, e.g. `example.org → Finance, not AI (a fund that uses ML internally, doesn't sell it)`.

5. **Classify.** Two equivalent paths, pick whichever tooling is available:
   - **Script path** (no subagent runtime needed): `node <skill dir>/references/classifier.mjs scraped.json niches.json classified.json --parallel 3` (from inside the skill's own folder, just `node references/classifier.mjs ...`). Reads `scraped.json`, batches domains (50/batch via the CLI path, 30/batch via the direct-API path), classifies each batch with Haiku, retries a failed batch twice before marking it `Unclassified`, and resumes from `classified.json` if interrupted.
   - **Subagent path** (Claude Code with the Agent tool): split `scraped.json` into chunks of 50 domains and dispatch every chunk in a single message (parallel, not sequential) to subagents carrying the rubric from step 4 and that chunk's signals; no web access needed, they judge only the passed-in signals. If already running as a subagent (nested dispatch is unavailable), skip the fan-out and classify every chunk sequentially inline using the same rubric.
   - Either way: a domain that comes back malformed or missing gets one re-classification attempt; still bad, mark `Unclassified`. Invariant: classified count == input count, always.

6. **Quality pass.** Pull the low-confidence results (scrape failed, classified from the domain name alone) and any "Unclassified" or implausible-niche rows. Fetch 5-10 of the most ambiguous ones directly (WebFetch or equivalent) and reclassify from the fetched content.

7. **Write results.** CSV (default): `./output/classified-<YYYYMMDD>.csv`, columns `Domain, Primary Niche, Secondary Niche, Confidence`. If the input was a CSV/XLSX, add/update those columns in place instead (normalize domains when matching rows back). Otherwise, display the top results as a table and offer to write the CSV.

8. **Report.** Tell the caller: total domains, classified count, unclassified count, high/low-confidence counts, and the top 5 niches by count.

<verification>
Before delivering:
1. Classified-row count equals input domain count; no domain silently dropped.
2. Every "Unclassified" row was genuinely unresolvable (scrape failed AND classification failed twice), not a shortcut.
3. A spot-check of 3-5 classified rows against their scraped signals confirms the primary niche matches the site's actual stated business, not an incidental keyword.
</verification>
