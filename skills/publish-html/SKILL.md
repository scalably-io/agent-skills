---
name: publish-html
description: "Use when the user wants a public URL for an HTML deliverable (report, dashboard, presentation) so they can share it by link. Triggers: publish, share by link, public URL, send the link, make it shareable, deploy this. For creating the HTML content first, load the report skill."
license: MIT
metadata:
  source: https://scalably.io/skills/publish-html
  derived_from:
    path: container/skills/publish-html/SKILL.md
    commit: ef174fc3
    date: "2026-09-07"
  triggers: [publish, share HTML, public link, deploy, make it shareable, send the link]
  not_for: [Creating HTML content: use the report skill., Research: use a research skill.]
---

# Publish HTML

## What it does

Publishes a finished HTML file to a public URL, after running a mandatory QA
gate that catches the failure modes that actually ship broken pages:
leftover template placeholders, mobile horizontal overflow, broken images,
empty sections, copy-pasted stats. Supports three free publish targets
(Netlify, Surge, and GitHub Pages) so there's always an option that needs
no paid account. For interpreting a publish result, read
`references/outcomes.md`; on an ambiguous or failed publish, read
`references/recovery.md` before any retry.

## Requirements

- Playwright, for the mandatory QA gate: `pip install playwright && playwright install chromium`. Free and open source.
- One of, for the actual publish step (all free-tier, no paid account required):
  - Netlify CLI: `npm install -g netlify-cli`, then `netlify login` once.
  - Surge: `npm install -g surge`, then `surge` prompts for a free account on first publish.
  - `git` + a GitHub repository with Pages enabled (Settings → Pages); no extra CLI beyond `git` itself; `gh` (GitHub's CLI) is convenient but optional.

## Inputs and outputs

| | |
|---|---|
| Input | A finished, self-contained HTML file (e.g. `./projects/<slug>/report.html`) |
| Output | A public URL on the chosen host, plus the QA gate's JSON result and 3 screenshots (`.qa-<stem>-<viewport>.png`) written next to the HTML file |

## Worked example

QA-check a report, then publish it:

```bash
python3 <skill dir>/scripts/qa_html.py ./projects/brief/brief.html --strict
```

Expected on a clean file: JSON with `"status": "PASS"`, `"hard_fails": []`,
three `.qa-brief-<viewport>.png` screenshots written next to the file, and
exit code 0.

Once it passes, publish it:

```bash
netlify deploy --prod --dir ./projects/brief
```

Expected: the CLI's own build/upload steps run, then it prints the live
production URL to stdout. Only report that URL to the user once you've
seen this output; see `references/outcomes.md` for what each of the
three publish options prints on real success.

## Procedure

### 1. Write the file into a project folder

Keep every deliverable's output inside its own project folder rather than
scattering files at the repo root:

```
./projects/<short-slug>/<name>.html
```

e.g. `./projects/q3-report/report.html`. This keeps the QA sidecar files
(screenshots, JSON) grouped with the HTML they describe, and keeps the
project root uncluttered when there are several deliverables in flight.

### 2. Run the QA gate (mandatory before every publish)

```bash
python3 <skill dir>/scripts/qa_html.py ./projects/<slug>/<name>.html
```

(`<skill dir>` is wherever this skill's files live in your setup. After a
plugin install, find it with `find ~/.claude/plugins -path
'*/publish-html/SKILL.md'` and use its parent directory; from inside the
skill's own folder, just `python3 scripts/qa_html.py ...`.)

A bad publish is effectively permanent the moment someone opens the link:
none of the three hosts below give you a true "undo the last few minutes"
button, only a way to push a corrected version. Running the gate before
every publish, not just the first one, is what catches a regression
introduced by a "quick edit."

The gate renders the file at 360 / 768 / 1280 px in headless Chromium and
catches:

- **Unfilled placeholders** ("Report Title", "First Pillar", "Row item one", etc.)
- **Horizontal overflow on mobile** (cramped numeric tables are the classic case)
- **Broken assets** (failed image hotlinks, font loads, JS errors)
- **Empty sections** (skeleton not filled in)
- **Copy-pasted stat values**

Output: JSON to stdout + 3 screenshots saved as `.qa-<stem>-<viewport>.png`
next to the HTML. Read the screenshots before publishing; the gate is
mechanical and misses taste-level issues (ugly typography, bad color, weak
copy) that only a look will catch. If you used the `report` skill's
template, its own QA checklist covers the same ground in more detail;
see `../report/SKILL.md#3-qa-checklist-before-delivery`.

- **`status: "PASS"`** → safe to publish
- **`status: "FAIL"`** → fix every entry in `hard_fails[]`, rerun, do not publish

### 3. Name the URL

Before publishing, suggest a clean slug/subdomain to the user and ask if
they want it or something different, e.g.:

> "I'll publish this as **q3-brief**. Want a different name?"

Derive it from the filename or content; keep it short and free of internal
project jargon, since it becomes part of a public URL.

### 4. Publish

Pick one of three free options and deploy the project folder:

```bash
# Netlify: prints the live production URL when it finishes
netlify deploy --prod --dir ./projects/<slug>

# Surge: prints "Success! - Published to <domain>" once every edge node confirms
surge ./projects/<slug>   # run from the project folder and follow its prompt for a domain,
                          # or pass one explicitly: surge ./projects/<slug> <your-domain>

# GitHub Pages: push the folder to the branch/path your repo's Pages source uses
git subtree push --prefix ./projects/<slug> origin gh-pages
```

Return the resulting URL to the user. Read `references/outcomes.md` for
exactly what each option prints on real success and how to read it;
don't infer "it's live" from the command merely exiting 0.

### 5. Never claim it's live before you've seen the proof

1. **Don't tell the user a URL is live until you've seen that option's own
   success signal** (the exact `Success!` line for Surge, the printed
   production URL for Netlify, a confirmed Pages build for GitHub Pages;
   see `references/outcomes.md`), or fetched the URL yourself and
   confirmed it. A URL that "looks right" from memory is not proof.
2. **Don't auto-retry an ambiguous or interrupted publish.** If the
   command was interrupted, hung, or errored partway through, treat the
   state as unknown and follow `references/recovery.md` rather than
   re-running blind; a Surge publish interrupted mid-propagation can
   leave some edge nodes on the old revision and some on the new one.
3. **Read `references/recovery.md` before any retry** on a failure:
   auth errors, build errors, and propagation delays each need a
   different fix, not the same command run again.

### Republishing

Publishing to the same slug again overwrites what's there. None of the
three options gives you a true undo of the last N minutes, but two of
them keep real history you can use instead of trying to reconstruct an
old version from memory:

- **Surge** keeps a revision history per domain: `surge list <domain>` to
  see it, `surge rollback <domain>` to revert one step, `surge rollfore
  <domain>` to move forward again.
- **Netlify** keeps full deploy history per site in its dashboard; you
  can restore a specific prior deploy from there rather than guessing.
- **GitHub Pages** is just git: `git revert` the offending commit on the
  Pages branch and push again.

Always tell the user before republishing over an existing live URL and
wait for confirmation; never silently overwrite a page someone may
already be sharing.

### Editing an existing published page

When a user gives you a link to something this skill already published
and asks for changes (fix text, tweak colors, add a section):

1. **Fetch** the live HTML with a web-fetch tool and **save** it as your
   working copy under `./projects/<slug>/`; don't start from a blank file.
2. **Read** the saved copy to understand its structure before touching it.
3. **Make targeted edits** to just the lines that need to change, rather
   than regenerating the whole file from scratch; the user chose that
   design, and a full rewrite tends to silently drift fonts, spacing, and
   layout even when you're trying to reproduce it exactly.
4. **Show the user what changed** and get confirmation before republishing:
   "**{slug}** is live, ready to update it?"
5. Republish to the same slug/domain once confirmed (step 4 above).

### Fetching source content that blocks a plain fetch

If a page you need to pull content from returns a 403 or otherwise blocks
an ordinary fetch (common on some social platforms and forums), don't keep
retrying the same plain fetch; escalate instead:

1. The `browser-scrape` skill: bounded public-page extraction, with an
   anti-bot tier for pages that specifically block scraping. See
   `../browser-scrape/SKILL.md`.
2. An interactive browser-automation skill, if the page needs a login or a
   click-through flow rather than just rendering.
3. Ask the user if they can supply the content another way.

## When to use

- The user says "publish this", "share this online", "make this a link", "deploy this"
- Right after generating an HTML report or presentation and the user wants it shareable
- The user gives you a link to something already published here and asks for edits; follow "Editing an existing published page" above
