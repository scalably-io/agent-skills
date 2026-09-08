---
name: batch-contact-email
description: "Extract a contact email for each domain in a list — no niche or quality filtering, assumes the domains are already vetted. Scrapes common contact paths first, falls back to an email-lookup API only when scraping finds nothing, and delivers a CSV (or a markdown table for small batches) with one row per input domain, never silently dropping one. Triggers: find emails, extract emails, contact emails, email list, find contacts, emails for these sites, emails from domains, email extraction, contacts CSV, contacts sheet."
license: MIT
metadata:
  source: https://scalably.io/skills/batch-contact-email
  derived_from:
    path: overrides/skills/batch-contact-email/SKILL.md
    commit: f0f1753
    date: "2026-09-08"
  triggers: [find emails, extract emails, contact emails, email list, find contacts, emails for these sites, emails from domains, email extraction, contacts CSV, contacts sheet]
  not_for:
    - "Filtering domains by niche/region/quality first — use classify, then this skill"
    - "Finding link insertion opportunities — use link-insertion-finder"
---

# Batch Contact Email

## What it does

Pure email lookup for an already-vetted domain list: no classification or filtering step, so it's faster than pairing classify with a filter. For each domain, tries a small set of contact-page paths first (free — plain scraping), and only calls a paid email-lookup API when scraping genuinely finds nothing. Every input domain appears in the output, with the found email or `/` if none was found anywhere — never a silent drop.

## Requirements

- Web fetch tools to scrape contact pages. Free option: Claude Code's built-in WebFetch, or [Scrapling](https://github.com/D4Vinci/Scrapling) (`pip install "scrapling[fetchers]"`) for JS-rendered or Cloudflare-protected sites — verified 2026-09-08 from the project README.
- Subagents for parallelizing large batches (optional). Free option: Claude Code's Agent tool; without it, run every domain sequentially inline in the same session.
- Email discovery fallback (optional, used only when scraping fails): the [Hunter.io API](https://hunter.io/api-documentation/v2#discover) (`https://api.hunter.io/v2/domain-search`). Free option: Hunter's free tier — 50 credits/month, 1 credit per Domain Search call returning a result — verified 2026-09-08 from Hunter's pricing page; or skip Hunter entirely and rely on scraped `mailto:` links and contact pages only.
- Google Sheets output (optional): any Sheets MCP server (e.g. [xing5/mcp-google-sheets](https://github.com/xing5/mcp-google-sheets)), or the [gspread](https://docs.gspread.org/) Python package (`pip install gspread`) — verified 2026-09-08, current PyPI release 6.2.1.

## Inputs and outputs

| | |
|---|---|
| Input | A domain list (one per line, with or without scheme) and an output preference — CSV (default), a markdown table (batches under 30), or Google Sheets |
| Output | `./output/contact-emails-<YYYYMMDD-HHMM>.csv` with columns `Domain, Email` (`/` where nothing was found), or the same rows inline as a markdown table for small batches |

## Worked example

Paste into Claude Code with this skill installed:

```text
/seo-ops:batch-contact-email find contact emails for these domains:
example.com
example.org
example.net
```

Expected: `./output/contact-emails-20260908-1400.csv` with one row per domain (`example.com, hello@example.com`) plus a summary line — `3 domains -> 2 emails found (67% hit rate).`

## Procedure

1. **Parse input.** Accept the domain list, one per line, with or without a scheme. Strip schemes, normalize, deduplicate. Decide output format: CSV by default, a Google Sheet if the caller asks for one or supplies a sheet URL, or an inline markdown table for small batches (under 30 domains).

2. **Per-domain email-finding method.** For each domain, follow this waterfall, returning on the first hit:
   1. **Fetch common contact paths**, in this order, stopping at the first 200-OK page with at least one email match: `/contact`, `/contact-us`, `/about`, `/about-us`, then the homepage (last resort — emails often sit in the footer).
   2. **Regex the page text** for `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}`, plus obfuscated forms (`name [at] domain [dot] com`, `name (at) domain (dot) com`) and `mailto:` links.
   3. **Reject decoys**: `example@`, `your.email@`, `name@example.com`, addresses embedded in an image `src="..."`, and local-parts ending in more than 5 digits (usually a CDN cache filename, not a real address).
   4. **Pick the best match** when several emails are found: prefer a same-domain address over a free-mail one, prefer editorial roles (`editor@`, `editorial@`, `tips@`, `pitch@`) for media sites, prefer `info@`/`contact@`/`hello@` for SaaS or services, and avoid `noreply@`/`no-reply@`/`support+billing@`.
   5. **Fall back to Hunter** (see Requirements) only when scraping genuinely fails — every contact path blocked or 404, regex finds nothing, or every match was rejected as a decoy. Take the most generic email returned, in priority order `info@`, `contact@`, `hello@`, `editor@`. On a Hunter rate-limit or auth error, skip it — that domain yields `/`.
   6. Emit `{"domain","email"}` for the domain (`email` = the address found, or `/`). Never omit a domain.

3. **Parallelize larger batches.** For anything beyond a handful of domains, dispatch chunks of domains to subagents in parallel rather than working through the list sequentially in the main session — one message dispatching every chunk at once, not a few at a time. A useful pattern for a worker subagent here: give it a restricted tool set (fetch/search tools plus the ability to write its results to a file, nothing else — specifically no ability to spawn further subagents or message other agents) so a worker can't nest-dispatch or drift outside its one job. Pick a `run_id` for the batch (e.g. `bce-<YYYYMMDD-HHMM>`) and have each worker write its rows to `./runs/<run_id>/chunk-<i>.jsonl` — one `{"domain","email"}` object per line — rather than returning them as prose, since prose responses fragment across many parallel workers and are unreliable to reassemble. Chunk size: roughly 12 domains per worker, capped at around 8 workers running concurrently (grow the chunk size before growing the worker count past that — a much higher concurrent-worker count has been observed to exhaust local browser-launch limits and produce hard failures on some fetch backends; if you hit that, lower the worker count and grow chunks instead). If you are already running as a subagent, nested dispatch is usually unavailable — skip the fan-out and process every chunk sequentially inline using the same waterfall.

4. **Merge the chunk files.** Read every `./runs/<run_id>/chunk-*.jsonl`, one JSON object per line, and merge by domain (last write wins on a duplicate):
   ```bash
   python3 - <<'PY'
   import json, glob
   rows = {}
   for f in sorted(glob.glob("./runs/<run_id>/chunk-*.jsonl")):
       for line in open(f, encoding="utf-8", errors="replace"):
           line = line.strip()
           if not line:
               continue
           try:
               o = json.loads(line)
           except Exception:
               continue
           rows[o["domain"]] = o.get("email", "/")
   print(f"merged {len(rows)} domains")
   PY
   ```
   If the merged row count doesn't match the input domain count, diff input vs. merged, re-dispatch only the missing domains to one more worker (or run them inline), and re-merge. Every input domain must appear before building the output.

5. **Build the output.**
   - **CSV** (default): write `./output/contact-emails-<YYYYMMDD-HHMM>.csv`, columns `Domain, Email`, and tell the user the file path.
   - **Google Sheet**: write the CSV locally first, then push it to a sheet via a Sheets MCP server or `gspread` (see Requirements) — create a new sheet, or write into a caller-supplied sheet URL if given.
   - **Markdown table** (batches under 30): reply inline in chat instead of writing a file.

6. **Summary.** Reply to the user in chat: `<N_in> domains -> <N_with_email> emails found (<hit_rate>% hit rate).` A hit rate under 60% usually means anti-bot protection is blocking most contact pages, or the email-lookup fallback is out of quota — note that in the summary when the batch consistently scores low.

<verification>
Before delivering:
1. Output row count equals input domain count — a domain that couldn't be reached still appears, with `/`.
2. Hit rate in the summary matches a recount of the output rows.
3. Every non-`/` email is well-formed (passes the regex again on the output, not just on the scraped input).
4. No decoy address (`example@`, `your.email@`, `name@example.com`) made it into the output.
</verification>
