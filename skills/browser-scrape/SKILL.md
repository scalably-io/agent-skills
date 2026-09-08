---
name: browser-scrape
description: "Retrieve and extract public web-page content with Scrapling, escalating from a plain HTTP fetch to a real browser to an anti-bot stealth browser only as needed. Use for scraping, reading sites, homepage or contact harvesting, domain enrichment, repeated URLs, JS-rendered pages, and public pages that block a plain fetch. Not for login, forms, clicks, visual UI work, downloads, or authenticated interaction; use an interactive browser-automation skill for those; use a dedicated API when one exists."
license: MIT
metadata:
  source: https://scalably.io/skills/browser-scrape
  derived_from:
    path: container/skills/browser-scrape/SKILL.md
    commit: ef174fc3
    date: "2026-09-07"
  triggers: [scrape, scraping, extract page content, read this site, homepage harvest, contact harvest, JS-rendered page, page blocks fetch, Scrapling]
  not_for:
    - "Login, forms, clicks, visual UI work, downloads, or any authenticated/interactive browser task: use an interactive browser-automation skill instead"
---

# Browser Scrape

## What it does

Fetches and extracts content from public web pages using [Scrapling](https://github.com/D4Vinci/Scrapling), an open-source Python scraping library. Scrapling exposes three tiers of increasing cost: a plain HTTP fetch, a real rendered browser for JS-heavy pages, and a stealth browser for pages that actively block scraping (Cloudflare and similar). Use the cheapest tier that gets you the content, and escalate only when it doesn't.

## Requirements

- Scrapling: `pip install "scrapling[fetchers]"`. The bare `pip install scrapling` installs only the HTML parser; the `[fetchers]` extra is required for `Fetcher`/`DynamicFetcher`/`StealthyFetcher` and the CLI's `fetch`/`stealthy-fetch` subcommands. Scrapling is open source (MIT-licensed): https://github.com/D4Vinci/Scrapling.
- The browser-based tiers (`DynamicFetcher`, `StealthyFetcher`) additionally need their Playwright/Camoufox browser binaries installed; Scrapling's own install docs cover this per-platform; the plain `Fetcher` tier needs nothing beyond the pip install.

## Inputs and outputs

| | |
|---|---|
| Input | One URL or a list of URLs, plus an optional CSS/XPath selector to narrow the extraction |
| Output | CLI: a file (`.md`, `.txt`, or `.html`, chosen by the extension you name) containing the extracted content. Python API: a `Page`/`Selector` object with `.status`, `.css()`, `.xpath()`, `.find_all()` you use directly in your script |

## Worked example

Fetch `https://example.com` and pull just the H1:

```bash
pip install "scrapling[fetchers]"
scrapling extract get 'https://example.com' page.md --css-selector 'h1'
cat page.md
```

Expected: `page.md` contains the page's H1 text (`Example Domain` for that URL).

Same thing from Python, when you want the value in your own script rather than a file:

```python
from scrapling.fetchers import Fetcher

page = Fetcher.get('https://example.com')
print(page.status, page.css('h1::text').get())
```

Expected output: `200 Example Domain`.

## Procedure

### Choose the tier

1. **`Fetcher` (plain HTTP)**: fastest, lowest overhead, no browser. Default choice for ordinary pages. CLI: `scrapling extract get`.
2. **`DynamicFetcher` (real rendered browser)**: for JS-rendered pages where the plain fetch comes back empty or missing content you can see in a real browser. CLI: `scrapling extract fetch`.
3. **`StealthyFetcher` (anti-bot stealth browser)**: for pages that block both of the above (Cloudflare challenges, bot walls). Slower and heavier; use only when the page genuinely needs it. CLI: `scrapling extract stealthy-fetch`.

Escalate one tier at a time. Don't reach for the stealth tier by default: most public pages don't need it, and it costs meaningfully more time per URL.

### Single URL: CLI

The output format is decided by the file extension you give it: `.md` converts to Markdown, `.txt` strips to plain text, `.html` keeps the raw HTML.

```bash
# Plain fetch, whole page
scrapling extract get 'https://example.com' out.md

# Plain fetch, narrowed to one element, with a browser-like user agent
scrapling extract get 'https://example.com' out.md --css-selector 'article' --impersonate chrome

# Escalate to a real rendered browser
scrapling extract fetch 'https://example.com' out.md --css-selector 'article'

# Escalate to the anti-bot stealth tier
scrapling extract stealthy-fetch 'https://example.com' out.md --css-selector 'article' --solve-cloudflare
```

### Single URL or a batch: Python API

For anything beyond a one-off fetch (batches, conditional escalation, or using the extracted value inline), the Python API is more direct than shelling out to the CLI per URL:

```python
from scrapling.fetchers import Fetcher, StealthyFetcher

urls = ["https://example.com", "https://example.org"]
for url in urls:
    page = Fetcher.get(url)
    if page.status != 200:
        print(url, "failed:", page.status, page.reason)
        continue
    title = page.css('h1::text').get()
    print(url, title)
```

Escalate only the URLs that actually need it:

```python
page = Fetcher.get(url)
if page.status != 200 or not page.css('article').get():
    page = StealthyFetcher.fetch(url, solve_cloudflare=True)
```

If you'll re-scrape the same page shape after the site's markup changes, turn on adaptive mode: it relocates elements by similarity instead of breaking when a selector stops matching:

```python
StealthyFetcher.adaptive = True
page = StealthyFetcher.fetch(url)
items = page.css('.product', auto_save=True)   # first scrape: remembers the element shape
# ... later, after a redesign:
items = page.css('.product', adaptive=True)     # relocates by similarity instead of failing
```

### Interpret the result

- `page.status` (int): the HTTP status code. Treat only a 200-class response as retrieved content; don't assume success just because the call didn't raise.
- `page.css(selector)` / `page.xpath(selector)` / `page.find_all(...)`: selection methods; `.get()` returns the first match, `.getall()` returns all of them.
- A CLI run that fails prints an error and exits non-zero: check the output file exists and is non-empty before treating it as retrieved content, don't assume a zero-byte or missing file is a fluke.
- Escalate once (`Fetcher` → `DynamicFetcher`/`StealthyFetcher`), not repeatedly. If the tier that should handle the page still comes back empty or blocked after that one escalation, stop and treat it as a real failure rather than retrying the same call.

### Proxy and rate limits

Pass a proxy per request rather than storing it or its credentials in the prompt, output, or logs:

```python
page = StealthyFetcher.fetch(url, proxy='http://username:password@host:port')
```
```bash
scrapling extract get 'https://example.com' out.md --proxy 'http://username:password@host:port'
```

Keep concurrency modest for batch jobs and respect the target site's terms and robots rules; Scrapling makes evasion easy, which is exactly why it's worth self-limiting deliberately.

### Recovery

Escalate once, plain → stealth. If the tier that should work for a given page still fails for the same reason on the second attempt, stop: report the URL, the status code or exception, and which tier(s) you tried, rather than retrying the same call in a loop. If the task is actually interactive (you need to log in, fill a form, click through a flow), this skill is the wrong tool; use a full browser-automation skill instead; Scrapling is for content retrieval, not interaction.
