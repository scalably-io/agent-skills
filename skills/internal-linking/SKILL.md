---
name: internal-linking
description: "Internal-linking campaign engine. Given a site plus (optionally) target pages to boost and source pages to link from, proposes up to 3 high-quality internal links per source — anchors verbatim from each source's own body text, semantically matched to targets, validated by a deterministic gate, and QA-checked — then delivers a CSV (or Google Sheet). Five scripts do the deterministic parts (candidate selection, extraction, validity gate, the optional re-match loop, final merge); an agent does the matching and quality judgment. Triggers: run internal linking, internal linking for, internal-linking campaign, build internal links, find internal link opportunities, internal link audit."
license: MIT
metadata:
  source: https://scalably.io/skills/internal-linking
  derived_from:
    path: overrides/skills/internal-linking/SKILL.md
    commit: f0f1753
    date: "2026-09-08"
  triggers: [run internal linking, internal linking for, internal-linking campaign, build internal links, find internal link opportunities, internal link audit]
  not_for:
    - "Writing or publishing the links onto the live site — this skill only proposes verbatim placements; a human (or a separate edit) implements them"
    - "Finding a placement on someone else's site for a backlink — that's link-insertion-finder, a different (external) linking problem"
---

# Internal Linking

## What it does

For one site, proposes internal links from a set of SOURCE pages to a set of TARGET pages you want to boost — up to 3 per source, anchor text taken verbatim from the source's own body prose (never invented), matched to the target that fits it, checked by a deterministic validity gate (anchor really is in the body, not already linked, no anchor mapped to two different targets, no target over-linked), and judged by a quality pass before it's ever reported. If you don't supply target/source lists, the skill can build a free shortlist itself from your sitemap and (optionally) Google Search Console. Works equally for a full multi-source campaign or a single already-written page.

## Requirements

- Page fetching for `extract.py`: [Scrapling](https://github.com/D4Vinci/Scrapling) (`pip install "scrapling[fetchers]"`) — verified 2026-09-08 from the project README: `scrapling install` once to pull its bundled browser for JS/Cloudflare pages.
- Search-performance data for free candidate selection (optional): a Google service account with Search Console read access, passed to `il_candidates.py --sa <path>`. Free option: omit `--sa` — the script degrades automatically to sitemap-only selection for TARGETS (fewer signals, still usable), but **returns zero SOURCE candidates** (source ranking needs GSC clicks/impressions and there's no sitemap-only fallback for that half). Without a Search Console service account, supply your own source list with `il_candidates.py --sources <file>` (one URL per line, `#` comments allowed) instead of leaving sources empty.
- Keyword volume/difficulty to prioritize which targets are worth boosting (optional, paid): the [Ahrefs MCP server](https://ahrefs.com/blog/mcp-use-cases/) (`https://api.ahrefs.com/mcp/mcp`, OAuth, no free tier — same server verified for link-insertion-finder) or the [DataForSEO MCP server](https://github.com/dataforseo/mcp-server-typescript) (`npx dataforseo-mcp-server@latest`, needs a DataForSEO account — verified 2026-09-08 from the project README: open-source server, but the DataForSEO API itself requires paid credentials). Free option: skip this step entirely — `il_candidates.py`'s own GSC/sitemap ranking plus `extract.py`'s on-page headings and text (used for the per-target topic synthesis in Procedure step 3) already build usable target profiles with no paid API.
- Subagents for matching and quality judgment. Free option: Claude Code's Agent tool; without it, run every source sequentially inline using the same instructions.
- Sheet output (optional): any Sheets MCP server (e.g. [xing5/mcp-google-sheets](https://github.com/xing5/mcp-google-sheets)) or the [gspread](https://docs.gspread.org/) package (`pip install gspread`) — both verified 2026-09-08. Free option: the CSV output alone.

## Inputs and outputs

| | |
|---|---|
| Input | Site domain; optionally a list of TARGET urls (pages to boost) and SOURCE urls (pages to link from) — if either is missing, the skill builds a shortlist itself |
| Output | `./projects/internal-linking/<campaign>-<YYYYMMDD-HHMM>/final-links.json` (+ `.audit.json`), pivoted into `./output/internal-linking-<campaign>.csv` (two blocks: one row per source with up to 3 link/anchor pairs, one row per target with its link count); every delivered link is also appended to `./memory/internal-linking-ledger.jsonl` |

## Worked example

Paste into Claude Code with this skill installed (run from a repo/working directory you're happy to write `./projects/`, `./output/`, and `./memory/` into):

```text
/seo-ops:internal-linking run internal linking for example.com — auto-select targets and sources, up to 10 targets
```

Expected command sequence (the agent runs these; see Procedure for what each step means). Shown here is the **no-API path** — no Search Console service account — which needs a plain-text `sources.txt` (one candidate source URL per line, `#` comments allowed) since sitemap-only selection can't rank sources on its own:

```bash
mkdir -p ./projects/internal-linking/example-20260908-0930/{extract,profiles,proposals,verify,qa}

python3 scripts/il_candidates.py --domain example.com \
    --ledger ./memory/internal-linking-ledger.jsonl \
    --sources ./sources.txt \
    --max-targets 10 --max-sources 30 \
    --json ./projects/internal-linking/example-20260908-0930/profiles/candidates.json
# -> prints a TARGET table (sitemap-only, since no --sa) and a SOURCE table (from
#    ./sources.txt, filtered to the domain and to exclude chosen targets); pick from
#    them and write
#    ./projects/internal-linking/example-20260908-0930/targets.json and sources.json
#
# Fuller option, with a Search Console service account — ranks BOTH targets and
# sources from real click/impression data instead of sitemap-only + a manual list:
#   python3 scripts/il_candidates.py --domain example.com --sa /path/to/sa.json \
#       --ledger ./memory/internal-linking-ledger.jsonl \
#       --max-targets 10 --max-sources 30 --inspect \
#       --json ./projects/internal-linking/example-20260908-0930/profiles/candidates.json

python3 scripts/extract.py https://example.com/blog/backup-guide \
    > ./projects/internal-linking/example-20260908-0930/extract/backup-guide.json
python3 scripts/extract.py https://example.com/pricing \
    > ./projects/internal-linking/example-20260908-0930/extract/pricing.json
# (repeat once per chosen source and target URL)

# agent matching step (no CLI — see Procedure step 4), one subagent per source,
# writing ./projects/internal-linking/example-20260908-0930/proposals/<slug>.json

python3 scripts/verify.py \
    --extract ./projects/internal-linking/example-20260908-0930/extract/backup-guide.json \
    --proposals ./projects/internal-linking/example-20260908-0930/proposals/backup-guide.json \
    --targets ./projects/internal-linking/example-20260908-0930/targets.json \
    --ledger ./projects/internal-linking/example-20260908-0930/ledger.json \
    --counts ./projects/internal-linking/example-20260908-0930/counts.json \
    > ./projects/internal-linking/example-20260908-0930/verify/backup-guide.json

# agent quality-gate step (no CLI — see Procedure step 6), writing
# ./projects/internal-linking/example-20260908-0930/qa/<slug>.json

python3 scripts/merge.py \
    --verify-dir ./projects/internal-linking/example-20260908-0930/verify/ \
    --qa-dir ./projects/internal-linking/example-20260908-0930/qa/ \
    --out ./projects/internal-linking/example-20260908-0930/final-links.json
```

Expected output: `final-links.json` (one record per validated, QA-passed link: `source`, `anchor`, `anchor_exact`, `target`, `sentence`, `why`, `anchor_reuse_count`) plus `final-links.json.audit.json`; then `./output/internal-linking-example-20260908-0930.csv` and appended lines in `./memory/internal-linking-ledger.jsonl`.

## Procedure

0. **Set up a fresh run directory.** `mkdir -p ./projects/internal-linking/<campaign>-<YYYYMMDD-HHMM>/{extract,profiles,proposals,verify,qa}` — `<campaign>` is the site or project name, the timestamp keeps same-day runs distinct. **Never reuse an existing run directory or write into one that already has `proposals/`, `verify/`, or `qa/` files from a prior run** — stale files there will contaminate matching (the matcher anchors on old proposals) and corrupt the merge (old verdicts become orphans against new proposals). Append one line to `./projects/internal-linking/INDEX.md` once the run starts (`- <campaign>-<timestamp> — <site>, N targets / M sources`); fill in the link count once step 8 finishes.

1. **Candidate selection — only if targets and/or sources were NOT provided.** If the caller gave explicit lists, skip to step 2 and use them verbatim (write them to `targets.json` / `sources.json` in the run dir). Otherwise run:
   ```
   python3 scripts/il_candidates.py --domain <domain> \
       --ledger ./memory/internal-linking-ledger.jsonl \
       --max-targets 15 --max-sources 30 --inspect \
       --json <run-dir>/profiles/candidates.json
   ```
   `--inspect` adds a per-URL Google index-status check on the target shortlist (slower, rate-limited, but the single most valuable target signal for a real campaign — a page that is *not indexed* AND *under-linked* floats to the top). Read the printed TARGET table (bucketed `page-2` = position 11-20, `high-impr-low-click` = demand with no payoff, `zero-traffic` = in the sitemap but no search data yet) and SOURCE table (ranked by clicks then impressions). Apply your own SEO judgment on top: drop anything topically useless that slipped through (thin pages, pure listicles, legal/contact pages), prefer a mix of informational and commercial targets, and never pad the list to hit the cap — fewer good pages beats more weak ones. Write the final choice to `targets.json` and `sources.json`, and say plainly in your reply that targets/sources were auto-selected.

   **No Search Console access (no `--sa`):** you still get a real TARGET table from the sitemap alone, but the SOURCE table comes back empty — there's no click/impression signal to rank sources by, and sitemap-only has no fallback for that half. Pass `--sources <file>` (a plain-text list of candidate source URLs, one per line, `#` comments allowed) to supply the source set yourself; the script still applies its own filters (same domain, excludes chosen targets) before printing the table. Don't try to run the campaign with an empty source list.

   If you have an Ahrefs or DataForSEO MCP tool available (see Requirements), you can additionally pull search volume + keyword difficulty for each target's top query (from the candidate table's `top_queries` column) and prioritize high-volume/low-difficulty page-2 pages first — a small push (a few internal links) is far more likely to flip a low-difficulty page-2 ranker to page 1 than a high-difficulty one. This step is optional; skip it and rank by the GSC/sitemap buckets alone if no such tool is available.

   **Degrades, never fabricates:** if `--sa` was omitted or GSC access fails, the script automatically falls back to sitemap-only candidates (say so in your reply). If the sitemap is also empty, ask the caller for target/source lists instead of guessing URLs.

2. **Extract every source and every target.** For each URL: `python3 scripts/extract.py <url> [--stealth]` (add `--stealth` up front for known JS-heavy or Cloudflare-protected sites, or retry with it after a plain fetch comes back empty) `> <run-dir>/extract/<slug>.json`. For a draft that isn't published yet, use `--md-file <path-to-markdown>` with a placeholder URL instead of fetching. Each result has `{headings, existing_links, existing_internal_anchors, body_text, linked_spans, quality, stats}`.

   Escalation ladder — never feed a `quality: "suspect"` extract into matching:
   1. `status != "ok"` or a tiny/empty page → retry once with `--stealth`.
   2. Still `quality: "suspect"` (the structural boilerplate-removal misread the page) → re-fetch with `--save-html raw/<slug>.html`, read the raw HTML, identify the CSS selector of the real article container, and re-run with `--selector "<css>"`. You pick the *where*; the script keeps the extraction itself deterministic.
   3. Still suspect after a selector attempt → report that URL as extraction-failed and drop it from this run; don't fabricate its body text.

3. **Build target profiles.** For each target, write `profiles.json` = `[{"url", "topic", "keywords":[...]}]`. `keywords` comes from `candidates.json`'s `profiles` block if step 1 ran (the target's real top Google queries, free) — otherwise use the target's own extracted headings plus a one-to-two-line topic synthesis you write from its `body_text`. If a target's keyword set looks thin and you have an Ahrefs/DataForSEO MCP tool, you can widen it with a related-terms lookup — optional.

4. **Match — one subagent per source, dispatched in parallel.** For each SOURCE, launch a subagent (the Agent tool, or run inline sequentially if subagents aren't available) with: the source's `extract/<slug>.json`, `profiles.json`, and an output path `proposals/<slug>.json`. Instruct it to do a mandatory per-target tally pass first (so it doesn't stop at the first plausible match), then propose up to 3 `{"anchor", "target", "sentence", "target_topic"}` objects — `anchor` must be a verbatim substring of the source's `body_text` (never invented or paraphrased), `target` one of the URLs in `targets.json`, `sentence` the surrounding context, `target_topic` a one-line reason it fits. Write the array to the output path. **Dispatch every source's subagent in a single batch (e.g. 5 at a time)** rather than one-at-a-time — this is the single biggest speed factor on a real campaign; each subagent gets its own full context so quality doesn't suffer from parallelism.

5. **Validity gate — deterministic, one source at a time.**
   ```
   python3 scripts/verify.py --extract extract/<slug>.json --proposals proposals/<slug>.json \
       --targets targets.json --ledger ledger.json --counts counts.json \
       --max-anchor-reuse 2 --max-per-target 3 > verify/<slug>.json
   ```
   Run this **sequentially**, not in parallel — `counts.json` and `ledger.json` are shared, campaign-wide tally files that every source's call reads and rewrites (a parallel run would race them and produce wrong caps). This is a *different* file from the persistent `./memory/internal-linking-ledger.jsonl` used in steps 1 and 9 — `ledger.json` here is a per-run scratch file the script maintains itself (`{anchor_lc: target_url}`, campaign-wide anchor→target uniqueness), and does not need to be pre-created. `verify.py` enforces: anchor genuinely in the body outside any existing link, target is one of the provided targets, source doesn't already link that target, an anchor text maps to only one target for the whole campaign, at most 3 accepted links per source, an anchor text used more than `--max-anchor-reuse` times campaign-wide is rejected (anchor-portfolio diversity), and a target that already has `--max-per-target` links campaign-wide is rejected (distribution balance, so one target doesn't hog every link). A rejected proposal is reported with its reason; the source's other proposals still get their own chance.

6. **Quality gate — subagent judgment, per source (batch where useful).** For each source with ≥1 accepted link, dispatch a subagent (batching several sources per call is fine — QA judgments are independent) with the accepted proposals from `verify/<slug>.json` and `profiles.json`. It returns a pass/fail verdict per link with a reason, written to `qa/<slug>.json` as `{"results":[{"source","anchor","target","verdict","reason"}]}` — every row must carry `source`+`anchor`+`target` copied verbatim, or `merge.py` in step 8 can't join it back to the right link. After this single QA pass, go to step 8 — that's the default, fast path.

7. **Optional deep-mode re-match loop — skip by default.** Only run this when explicitly asked for "deep mode" or "max recall": each round adds real runtime (re-match + re-verify + re-QA), worthwhile only when recall matters more than speed. The reason this step exists as a *script* rather than agent judgment: tracking which of N sources still needs more links, which anchors they've already tried, and how many rounds each has had is exactly the kind of multi-item bookkeeping a model loses track of across a long loop — `loop_controller.py` owns that state so the model only does the part it's actually good at (matching), never the round-counting.
   ```
   python3 scripts/loop_controller.py --run-dir . --target-per-source 3 --max-rounds 2
   ```
   Prints `{"rematch":[...], "settled":[...], "round_summary":"..."}`. If `rematch` is empty, the loop is done — go to step 8. Otherwise, for each item in `rematch`, copy its `task_prompt` field verbatim into a new subagent call (the controller pre-builds the exact prompt: which targets are still open, which anchors to avoid repeating, what failed QA last round and why); the subagent appends new proposals to the existing `proposals/<slug>.json` array. Re-run step 5 and step 6 for just the re-matched sources, then re-run the controller with `--mark-progress` to bump each source's round counter, and repeat until `rematch` is empty.

8. **Final merge — deterministic, never hand-merged.**
   ```
   python3 scripts/merge.py --verify-dir verify/ --qa-dir qa/ --out final-links.json
   ```
   Joins validity-accepted links with QA-pass verdicts on the full `(source, anchor, target)` key. **Don't reassemble the final list with your own glob/loop logic** — a naive join has shipped real bugs before (a filename-pattern glob silently dropping some sources; verdict-matching without the source key letting one source's FAIL poison an identical anchor/target pair from a different source). If it exits non-zero, it printed which links are unjudged (verify-accepted but no matching QA verdict — re-run QA for them) or orphaned (a QA verdict matching nothing — a key mismatch to fix); resolve those and re-run merge before delivering anything.

9. **Deliver.** Read `final-links.json` fresh (never a stale copy) and pivot it into two blocks:
   - **By source** — one row per source: `Source URL, Link 1, Anchor 1, Link 2, Anchor 2, Link 3, Anchor 3`. Fewer than 3 links for a source → leave the unused pair(s) blank, never pad. Every `Anchor N` value is the record's `anchor_exact` field — the exact on-page casing `verify.py` extracted — never the matcher's proposed `anchor`, which may not match the page's own capitalization.
   - **By target** — one row per target that received ≥1 link: `Target URL, Count, Why`. `Count` = total links to that target across the run; `Why` is a short grounded reason if the target was auto-selected (bucket + position + impressions, from `candidates.json`), blank if the caller supplied the target list.
   Do the pivot in a small script (read `final-links.json`, write the rows), not by eyeballing — never invent or drop a link in the pivot. Write `./output/internal-linking-<campaign>.csv` by default and tell the caller the path. If a Google Sheet was asked for, push the same two blocks to a sheet via a Sheets MCP server or `gspread` (see Requirements) instead of, or in addition to, the CSV. If any anchor's `anchor_reuse_count` in `final-links.json` is above 1, mention it in your reply so the team can diversify at insertion — don't silently ship an over-optimized anchor profile.

10. **Ledger.** Append one JSON line per delivered link to `./memory/internal-linking-ledger.jsonl`: `{"date", "source", "target", "anchor"}`. Future runs' `il_candidates.py --ledger` call reads this file to exclude sources used as a source in roughly the last 90 days, so campaigns don't keep re-proposing from the same handful of pages.

11. **Report.** Reply to the user in chat: sources processed, total links delivered, per-target distribution, what was dropped at the validity gate vs. the QA gate (with a couple of example reasons), and the output path (CSV path and/or sheet URL). If a source got 0 links, say so and why rather than omitting it. Update the `INDEX.md` line from step 0 with the final link count.

**Single-source runs.** For one already-written page rather than a full campaign, skip step 1 unless you also want the target list auto-picked, and run steps 2, 4, 5, 6, 8, 9, 10 for just that one source — the same scripts and the same two gates apply at N=1, nothing about the pipeline changes.

<verification>
Before delivering:
1. Every link in `final-links.json` passed both `verify.py` (the deterministic gate) and a QA `pass` verdict — never report a link that skipped either.
2. `merge.py` exited 0 (no unjudged links, no orphan verdicts) before the CSV/Sheet was built.
3. The CSV's source block has at most 3 (Link, Anchor) pairs per row, with unused pairs left blank, not padded.
4. Every input source that produced 0 accepted links is still accounted for in the report (not silently omitted).
5. Every Anchor value in the delivered output is `anchor_exact` from the record, not the matcher's `anchor`.
6. Every delivered link was appended to `./memory/internal-linking-ledger.jsonl`.
</verification>
