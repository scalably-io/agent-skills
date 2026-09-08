---
name: link-insertion-finder
description: "Find the best article on a target site for inserting a backlink, given anchor text and a destination URL. Crawls the site, ranks editorial articles by topical fit and insertion naturalness, and suggests exact insertion points — with an optional check for whether the site already links to a competitor. Triggers: find placement, find article placement, link insertion opportunity, where to insert link, best article for backlink, suitable article for anchor, placement on site, find link-insertion, where can we put this link."
license: MIT
metadata:
  source: https://scalably.io/skills/link-insertion-finder
  derived_from:
    path: overrides/skills/link-insertion-finder/SKILL.md
    commit: f0f1753
    date: "2026-09-08"
  triggers: [find placement, find article placement, link insertion opportunity, where to insert link, best article for backlink, suitable article for anchor, placement on site, find link-insertion, where can we put this link]
  not_for:
    - "Drafting the actual insertion sentence into the live article — that's a lighter follow-up once a placement is chosen"
    - "Filtering domain lists or extracting emails — use classify / batch-contact-email"
    - "Writing a guest post for a publisher — use guest-post-writer"
---

# Link Insertion Finder

## What it does

Given a target site, anchor text, and a destination URL, finds the 3 best existing articles on that site for inserting a backlink — editorial body-prose insertion only, never a listicle slot or a CTA box. Crawls the site (sitemap first, then a blog index, then site search, then a `site:` web search as a last resort), filters to recent editorial articles, scores the survivors on topical fit and insertion naturalness, and returns the exact paragraph and rewritten sentence for each of the top 3. Optionally checks whether the site already links to a known competitor.

## Requirements

- Web fetch tools for crawling (sitemap, blog index, article bodies) and `site:` search as a fallback discovery path. Free option: Claude Code's built-in WebFetch/WebSearch, or [Scrapling](https://github.com/D4Vinci/Scrapling) (`pip install "scrapling[fetchers]"`) for JS-rendered or Cloudflare-protected sites — verified 2026-09-08 from the project README: `scrapling extract get '<url>' out.md` for plain pages, `scrapling extract stealthy-fetch '<url>' out.md --solve-cloudflare` when a page is bot-protected.
- Backlink data (optional, for the competition check): the [Ahrefs MCP server](https://ahrefs.com/blog/mcp-use-cases/) (remote endpoint `https://api.ahrefs.com/mcp/mcp`, OAuth) — verified 2026-09-08: it is Ahrefs's current official server, available on Lite/Standard/Advanced/Enterprise plans (no free tier; Ahrefs's older local npm server is archived). Free option: skip the backlink filter and rank candidates by on-page relevance only.

## Inputs and outputs

| | |
|---|---|
| Input | Target site (the publisher/blog where the link would go), anchor text, destination URL, and optionally "check competition" |
| Output | Delivered inline in chat: up to 3 ranked placements, each with article URL, section heading, exact insertion sentence (anchor in `[brackets]`), a 0-10 score, and a one-line rationale; plus the competition-check result if requested. Each accepted proposal is also appended to the per-site ledger at `./projects/link-insertion/<site-slug>/proposed.jsonl` |

## Worked example

Paste into Claude Code with this skill installed:

```text
/seo-ops:link-insertion-finder find a placement on example.com for anchor
"cloud backup service" -> https://example.org/backup, check competition
```

Expected output:
```text
Top 3 placements on example.com for anchor "cloud backup service" -> https://example.org/backup:

1. How small teams protect their data (2026-03-11)
   https://example.com/blog/small-team-data-protection
   Section: "Backup strategy"
   Suggested insertion (after: "...most teams start too late."):
   "A good starting point is a [cloud backup service] that runs automatically."
   Score: 8.5/10 — direct topical match, minor sentence rewrite

2. ...
3. ...

Competition check: no competitor links found on this site.
```

## Procedure

1. **Parse the request.** Target site, anchor text, destination URL, and (optional) multiple anchor variants or a "check competition" flag. If the request gives several anchor variants for the same site, treat it as one crawl — rank the same candidate pool per anchor and present ranked sets side by side.

2. **Check the placement ledger.** Before ranking anything, read `./projects/link-insertion/<site-slug>/proposed.jsonl` for this target site (slugify the site's hostname), if it exists — one JSON object per line, each shaped `{"date", "target_url", "anchor", "client_url"}`. Exclude any candidate whose URL already appears as a `target_url` proposed for the same `anchor` — that site+anchor placement was already suggested and must not be repeated. Keep the excluded set in mind through discovery and scoring below.

3. **Discover candidates (1-2 fetches).** In priority order:
   1. `<site>/sitemap.xml` — most editorial sites group post URLs under a `<loc>` list, often with `<lastmod>`; sort by `<lastmod>` desc and take the top 30.
   2. If the sitemap is an index, follow the `<sitemap>` child most likely to hold posts (named `post-sitemap.xml` / `blog-sitemap.xml`).
   3. No sitemap: fetch the blog index (`/blog`, `/articles`, `/news`) and extract article links; paginate once if needed.
   4. Site's own internal search, if it has one, queried with the anchor's root keyword.
   5. Last resort: a `site:<site> "<keyword>"` web search (returns roughly 10 candidates).
   Cap the candidate pool at 30 — a larger pool doesn't improve the final ranking, since scoring the top 3 is the bottleneck, not pool size.

4. **Quick filter pass — one batched fetch of all candidates.** Fetch all ~30 candidates in one bounded, parallel call rather than one at a time (`scrape.py --urls-file` equivalent, or Scrapling's `extract get`/`stealthy-fetch` per URL if the site needs JS rendering). For each: extract title, publish date (prefer the sitemap's `<lastmod>`, else a visible date, else mark unknown — don't drop for unknown date alone if `<lastmod>` gave recency), H2 headings, and an approximate word count. Drop: pre-2024 articles (unless the caller explicitly approves older), ≥50% numbered H2s (a listicle — body-prose insertion is impossible there), under 500 words (too thin for a natural insertion), and anything that 404s or stays blocked after a retry. Typical drop rate is around 50%, leaving roughly 15 survivors.

5. **Full-body scoring — one batched fetch of the survivors.** Fetch all survivors in one batched call. For each, read the article body (ignore residual nav/footer text if present) and score 0-10:
   - **Topical fit (0-4)** — does the article's actual subject sit adjacent to the anchor's domain? Direct match = 4, adjacent = 2-3, tangential = 0-1.
   - **Insertion naturalness (0-3)** — is there a paragraph where the anchor phrase fits with a small rewrite? Direct fit = 3, one-sentence reshape = 2, paragraph restructure = 1, no fit = 0.
   - **Recency (0-1.5)** — scale by publish year (older = lower).
   - **Authority signals (0-1.5)** — named author, real bio, dated comments, internal link density.
   Pick the top 3 by total score; tie-break on recency.

6. **Verify and draft the insertion — no re-fetch.** From the same content already fetched in step 5, for each of the top 3: quote 1-2 context sentences ending at the insertion point, name the section heading (the `##`/`###` above that paragraph) and write the insertion sentence with the anchor wrapped in `[brackets]` for the caller to convert into a real link. If an explicit reachability re-check is wanted, run one more batched fetch of just the top 3 and confirm each is reachable.

7. **Optional competition check.** If asked to "check competition": query the destination URL's known competitors via the Ahrefs MCP server (or an equivalent backlink API) for existing links from the target site, or fall back to a site-scoped search for competitor URLs. Report as `Site already links to: <competitor URLs>` or `No competitor links found on this site.` A competitor link found is a warning attached to the result, never a reason to withhold the placements — the caller decides whether to use a flagged placement.

8. **Deliver.** Reply to the user in chat, formatted as in the worked example: up to 3 ranked placements (article URL, section, insertion sentence with `[anchor]`, score, one-line rationale), plus the competition-check line if it was requested. Never end with a bare decline — a weak niche match or an off-topic site is a caveat you attach to the best candidates found, not a reason to return nothing. The only case where a technical block is an acceptable final answer is when the site cannot be crawled at all (fully blocked even after a retry); say so plainly rather than returning weak guesses. After delivery, append one JSON line per delivered placement to `./projects/link-insertion/<site-slug>/proposed.jsonl` (`{"date", "target_url", "anchor", "client_url"}`, creating the file and its parent directory if needed) so a later run for the same site+anchor excludes it in step 2.

<verification>
Before sending:
1. All 3 article URLs are reachable (a final spot-check fetch).
2. Each suggested insertion sentence contains the anchor text exactly as given (case-sensitive).
3. Each cited section heading matches a real H2/H3 in that article.
4. The 3 articles are distinct — no duplicates or near-duplicates from URL parameters.
5. If a competition check was requested, it is answered explicitly (yes/no with URLs), not skipped.
</verification>
