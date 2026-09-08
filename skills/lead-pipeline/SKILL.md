---
name: lead-pipeline
description: "Runs a B2B lead-generation pipeline end to end: discovers candidate companies for a niche and region, scores each against a qualification rubric, finds a contact for the ones that qualify, drafts a personalized outreach email per contact, and writes a ready-to-send CSV. Tracks every company, contact, and campaign membership in a local SQLite store so a later run only processes what changed, and supports resuming a failed run from its last completed stage. Triggers: run lead pipeline, lead pipeline, generate leads, find prospects, build a lead list, lead gen pipeline, prospect pipeline, outreach pipeline, lead pipeline status, lead pipeline resume."
license: MIT
metadata:
  source: https://scalably.io/skills/lead-pipeline
  derived_from:
    path: overrides/skills/lead-pipeline/SKILL.md
    commit: f0f1753
    date: "2026-09-08"
  triggers: [run lead pipeline, lead pipeline, generate leads, find prospects, build a lead list, lead gen pipeline, prospect pipeline, outreach pipeline, lead pipeline status, lead pipeline resume]
  not_for:
    - "Running one stage standalone for debugging — this skill is the whole orchestrated pipeline; use the individual Procedure steps directly if you only need one"
    - "You already have a domain list and just need contact emails — use batch-contact-email directly, skip discovery and scoring"
    - "Filtering an existing domain list by niche without generating a new one — use classify"
---

# Lead Pipeline

## What it does

Orchestrates a full outbound lead-generation run in one session: discover candidate companies matching a niche and region, score each against a qualification rubric, find a contact for the ones that qualify, draft a short personalized outreach email per contact, and write the result to a CSV. State (companies, contacts, scores, campaign memberships, replies) lives in a local SQLite database, so re-running the pipeline only processes what changed, and a failed run can resume from its last completed stage instead of restarting. Supports `run` (full pipeline), `test` (reduced volume, no send-ready output), `status`, and `resume`.

## Requirements

- Web search and fetch tools for company discovery. Free option: Claude Code's built-in WebSearch/WebFetch.
- Subagents for parallelizing discovery or scoring across a large target count (optional). Free option: Claude Code's Agent tool; without it, run every stage sequentially inline.
- `sqlite3` CLI (ships with macOS and most Linux distros) or Python's built-in `sqlite3` module, for the local state database.
- Prospect enrichment: Snov.io or Hunter.io API. Free option: skip enrichment, keep discovery and scoring. Contact discovery for each qualified company is delegated to the [batch-contact-email](../batch-contact-email/SKILL.md) skill (same plugin) — it already implements this scrape-first, API-fallback logic, so this pipeline reuses it rather than duplicating it. Neither vendor has a free tier that includes API access: Hunter.io's free plan gives 50 credits/month for Email Finder, Email Verifier, and Domain Search — verified 2026-09-08 from Hunter's pricing page ("50 credits per month", "Used for Email Finder, Email Verifier, and Domain Search"); Snov.io's free Trial explicitly excludes it — verified 2026-09-08 from Snov.io's pricing page ("Premium features like ... API & webhooks access and export are not available in Trial").
- Outreach delivery (optional): any ESP with an API (Snov.io campaigns, Instantly, Lemlist) to push contacts directly, or none at all — the CSV output is a complete, importable deliverable on its own.

## Inputs and outputs

| | |
|---|---|
| Input | A niche, a region, a target prospect count, and a pitch angle (what you're offering and why it matters to that niche) — plus an optional subcommand: `run` (default), `test`, `status [--run-id R]`, or `resume --run-id R` |
| Output | `./store/leadgen.db` (SQLite state — every company, contact, score, and campaign membership) and `./output/leads-<YYYYMMDD>.csv` (one row per qualified, enriched, personalized prospect) |

## Worked example

Paste into Claude Code with this skill installed:

```text
/seo-ops:lead-pipeline niche: boutique fitness studios, region: Berlin, target 50 prospects
```

Expected: `./store/leadgen.db` is created (or updated) with a new `pipeline_runs` row, a run summary lands in chat (discovered / qualified / enriched / personalized counts), and `./output/leads-20260908.csv` has up to 50 rows: `company, website, contact_name, contact_email, score, subject_line, personalized_intro, cta`.

## Procedure

<schema>
The pipeline's state lives in `./store/leadgen.db`. Initialize it once per project — this is idempotent, safe to re-run:

```bash
mkdir -p ./store ./output
sqlite3 ./store/leadgen.db <<'SQL'
CREATE TABLE IF NOT EXISTS companies (
  id INTEGER PRIMARY KEY,
  company_name TEXT,
  canonical_domain TEXT NOT NULL UNIQUE,
  website_url TEXT,
  linkedin_url TEXT,
  niche TEXT,
  qualification_state TEXT NOT NULL DEFAULT 'pending'
    CHECK (qualification_state IN ('pending','qualified','rejected','needs_review')),
  qualification_score INTEGER,
  qualification_reason TEXT,
  contact_state TEXT NOT NULL DEFAULT 'pending'
    CHECK (contact_state IN ('pending','enriched','no_contacts','failed','needs_review')),
  source_first_seen_at TEXT,
  source_last_seen_at TEXT,
  last_qualified_at TEXT,
  last_enriched_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS discovery_signals (
  id INTEGER PRIMARY KEY,
  run_id TEXT NOT NULL,
  company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  source TEXT NOT NULL CHECK (source IN ('web_search','job_listing','upwork')),
  source_key TEXT NOT NULL UNIQUE,
  source_url TEXT,
  title TEXT,
  description TEXT,
  discovered_at TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS qualification_snapshots (
  id INTEGER PRIMARY KEY,
  company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  run_id TEXT,
  score INTEGER NOT NULL CHECK (score BETWEEN 0 AND 100),
  decision TEXT NOT NULL CHECK (decision IN ('qualified','rejected','needs_review')),
  product_fit_json TEXT,
  reason TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS contacts (
  id INTEGER PRIMARY KEY,
  company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  name TEXT,
  title TEXT,
  email TEXT,
  email_normalized TEXT,
  email_source TEXT,
  verification_status TEXT NOT NULL DEFAULT 'pending'
    CHECK (verification_status IN ('pending','valid','invalid','unverifiable')),
  is_primary INTEGER NOT NULL DEFAULT 0 CHECK (is_primary IN (0,1)),
  enriched_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(company_id, email_normalized)
);

CREATE TABLE IF NOT EXISTS campaign_memberships (
  id INTEGER PRIMARY KEY,
  company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
  contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE RESTRICT,
  campaign_key TEXT NOT NULL,
  pitch_angle TEXT NOT NULL,
  external_campaign_id TEXT,
  personalization_state TEXT NOT NULL DEFAULT 'pending'
    CHECK (personalization_state IN ('pending','generated','failed','skipped')),
  subject_line TEXT,
  personalized_intro TEXT,
  value_prop TEXT,
  cta TEXT,
  sync_state TEXT NOT NULL DEFAULT 'pending'
    CHECK (sync_state IN ('pending','synced','failed','skipped')),
  sync_error TEXT,
  synced_at TEXT,
  engagement_state TEXT NOT NULL DEFAULT 'pending'
    CHECK (engagement_state IN ('pending','active','replied','converted','unsubscribed','bounced','closed')),
  last_reply_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(company_id, campaign_key)
);

CREATE TABLE IF NOT EXISTS replies (
  id INTEGER PRIMARY KEY,
  membership_id INTEGER NOT NULL REFERENCES campaign_memberships(id) ON DELETE CASCADE,
  provider TEXT NOT NULL DEFAULT 'email',
  provider_reply_id TEXT NOT NULL,
  reply_text TEXT NOT NULL,
  classification TEXT CHECK (classification IN ('interested','not_interested','objection','ooo','bounce','unsubscribe')),
  sentiment TEXT CHECK (sentiment IN ('positive','neutral','negative')),
  follow_up_action TEXT CHECK (follow_up_action IN ('schedule_demo','send_info','follow_up','close','none')),
  replied_at TEXT NOT NULL,
  classified_at TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(provider, provider_reply_id)
);

CREATE TABLE IF NOT EXISTS pipeline_runs (
  id TEXT PRIMARY KEY,
  trigger_type TEXT NOT NULL CHECK (trigger_type IN ('scheduled','manual','resume','test')),
  status TEXT NOT NULL DEFAULT 'running'
    CHECK (status IN ('running','partial','failed','completed','aborted')),
  last_error TEXT,
  checkpoint_json TEXT NOT NULL DEFAULT '{}',
  started_at TEXT NOT NULL DEFAULT (datetime('now')),
  finished_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_discovery_signals_run ON discovery_signals(run_id);
CREATE INDEX IF NOT EXISTS idx_companies_qualification_queue ON companies(qualification_state, source_last_seen_at DESC);
CREATE INDEX IF NOT EXISTS idx_companies_contact_queue ON companies(contact_state, qualification_state, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_campaign_memberships_sync_queue ON campaign_memberships(campaign_key, sync_state, created_at);
CREATE INDEX IF NOT EXISTS idx_replies_membership_time ON replies(membership_id, replied_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status ON pipeline_runs(status, started_at DESC);
SQL
```

State model: `companies` -> `discovery_signals` (why it was found) -> `qualification_snapshots` (score history, append-only) -> `contacts` (enriched) -> `campaign_memberships` (per-campaign outreach state) -> `replies`. State columns to watch: `companies.qualification_state`, `companies.contact_state`, `campaign_memberships.{personalization_state,sync_state,engagement_state}`. Every write goes through `sqlite3`/the pipeline steps below — never hand-edit a row outside a documented step, or later stages will disagree with what actually happened.
</schema>

### 1. Setup

Parse the request: niche, region, target prospect count, pitch angle, and subcommand (`run` if none given). Generate a run id: `leadgen_<YYYYMMDD_HHmm>`. `resume` reuses the original run id instead.

```bash
sqlite3 ./store/leadgen.db "INSERT INTO pipeline_runs (id, trigger_type, status, checkpoint_json)
  VALUES ('$RUN_ID', 'manual', 'running', json_object('niche', '$NICHE', 'region', '$REGION', 'target', $TARGET, 'pitch_angle', '$PITCH_ANGLE'));"
```

### 2. Preflight

Before spending any tokens or API credits, confirm the tools you actually need are available: web search/fetch, and — only if you plan to use them — `SNOV_API_KEY`/`SNOV_CLIENT_SECRET` or `HUNTER_API_KEY` for enrichment. Missing enrichment credentials are not a blocker (see Requirements — enrichment degrades to the free scrape-first path), but tell the user up front which capabilities are active for this run rather than discovering it mid-pipeline.

### 3. Discover

Default source — **niche + region search**: run several web searches varying the phrasing (`"<niche>" <region>`, `<niche> near <region>`, local directory/listing sites for that niche) until you have at least `target * 2` distinct candidate domains — the extra headroom absorbs the qualify/enrich drop-off in later stages. For each result, extract `company_name`, `canonical_domain` (strip to registrable domain), and `website_url`.

Alternate source — **hiring/gig signal search** (use when the niche is defined by a need rather than an industry, e.g. "companies that need overflow bookkeeping help"): search job boards and freelance marketplaces (Upwork, LinkedIn Jobs) for postings that signal the pain point your pitch angle solves. This finds companies with active, timely intent, at the cost of a narrower pool.

Insert each candidate, relying on the `UNIQUE(canonical_domain)` constraint to silently skip repeats across runs:

```bash
sqlite3 ./store/leadgen.db "INSERT OR IGNORE INTO companies (company_name, canonical_domain, website_url, niche, source_first_seen_at, source_last_seen_at)
  VALUES ('$NAME', '$DOMAIN', '$URL', '$NICHE', datetime('now'), datetime('now'));
  INSERT INTO discovery_signals (run_id, company_id, source, source_key, source_url, title, discovered_at)
  SELECT '$RUN_ID', id, '$SOURCE', '$SOURCE'||':'||'$DOMAIN', '$URL', '$TITLE', datetime('now')
  FROM companies WHERE canonical_domain = '$DOMAIN'
  ON CONFLICT(source_key) DO NOTHING;"
```

If the target count is large (50+), dispatch the search across several parallel subagents (one per search variant or sub-region) rather than working through queries one at a time — one message launching all of them, matching the pattern in [research](../research/SKILL.md#3-retrieve). Each subagent writes its findings to a scratch file; merge before inserting.

Gate: if discovery found zero candidates after trying every source above, tell the user and stop — do not proceed to qualify an empty set.

### 4. Qualify

Score every `pending` company 0-100 against this rubric, using the actual site content (fetch the homepage, not just the search snippet):

- **Niche/ICP fit (0-40)** — does the business genuinely match the target niche and region, and look like a plausible buyer for the pitch angle?
- **Signal strength (0-25)** — a hiring/gig posting that directly names the pain point scores highest; a generic directory listing with no explicit signal scores lowest, but is not disqualifying on its own.
- **Reachability (0-15)** — a live site plus a plausible path to a named contact (team page, LinkedIn, visible email).
- **Business viability (0-20)** — active site (not parked/dead), a size that plausibly matches who you can sell to (not a solo freelancer if you're pitching a team tool, not an enterprise if you're pitching an SMB price point).

Decision: `qualified` at `score >= min_score` (default 40), `needs_review` for `score >= min_score - 15`, `rejected` below that. Record every score — this table is append-only, so re-scoring a company adds a new row rather than overwriting:

```bash
sqlite3 ./store/leadgen.db "INSERT INTO qualification_snapshots (company_id, run_id, score, decision, product_fit_json, reason)
  VALUES ($COMPANY_ID, '$RUN_ID', $SCORE, '$DECISION', '$PRODUCT_FIT_JSON', '$REASON');
  UPDATE companies SET qualification_state = '$DECISION', qualification_score = $SCORE,
    qualification_reason = '$REASON', last_qualified_at = datetime('now') WHERE id = $COMPANY_ID;"
```

Gate: if zero companies reach `qualified`, tell the user and stop — do not enrich or personalize an empty set. `needs_review` companies are reported to the user but not carried forward automatically.

### 5. Enrich

For every `qualified` company with `contact_state = 'pending'`, find a contact using the [batch-contact-email](../batch-contact-email/SKILL.md) skill against that company's domain — it already runs the scrape-first, API-fallback waterfall (see its Requirements for the Hunter.io/Snov.io details). Take its highest-confidence result per domain.

```bash
sqlite3 ./store/leadgen.db "INSERT INTO contacts (company_id, email, email_normalized, email_source, verification_status, is_primary, enriched_at)
  VALUES ($COMPANY_ID, '$EMAIL', lower('$EMAIL'), '$SOURCE', 'valid', 1, datetime('now'));
  UPDATE companies SET contact_state = 'enriched', last_enriched_at = datetime('now') WHERE id = $COMPANY_ID;"
```

A company with no email found gets `contact_state = 'no_contacts'` and drops out of this run — never invent a plausible-looking email.

Gate: if zero companies come out enriched, tell the user and stop.

### 6. Personalize

For every enriched contact, write one short, specific outreach email: a one-line intro that references the actual discovery signal or something concrete on the company's site (not a generic template), a value proposition tied to the pitch angle, and a clear single call to action. Pick a `campaign_key` for the run (e.g. `<niche-slug>_<YYYYMMDD>`) if the caller didn't supply one.

```bash
sqlite3 ./store/leadgen.db "INSERT INTO campaign_memberships (company_id, contact_id, campaign_key, pitch_angle, subject_line, personalized_intro, value_prop, cta, personalization_state)
  VALUES ($COMPANY_ID, $CONTACT_ID, '$CAMPAIGN_KEY', '$PITCH_ANGLE', '$SUBJECT', '$INTRO', '$VALUE_PROP', '$CTA', 'generated');"
```

Gate: if zero personalizations succeed, tell the user and stop — do not write an empty output file.

### 7. Deliver

Write the CSV — this is the deliverable even if no ESP is configured:

```bash
sqlite3 -header -csv ./store/leadgen.db "SELECT c.company_name AS company, c.website_url AS website,
  ct.name AS contact_name, ct.email AS contact_email, c.qualification_score AS score,
  cm.subject_line, cm.personalized_intro, cm.cta
  FROM campaign_memberships cm
  JOIN companies c ON c.id = cm.company_id
  JOIN contacts ct ON ct.id = cm.contact_id
  WHERE cm.campaign_key = '$CAMPAIGN_KEY' AND cm.personalization_state = 'generated';" \
  > ./output/leads-$(date +%Y%m%d).csv
```

Optional — push directly into an ESP: if the caller has Snov.io (or another ESP) API credentials configured, sync each row into a campaign there instead of, or in addition to, the CSV. Mark `sync_state = 'synced'` per membership; if a sync fails, mark `sync_state = 'failed'` and keep the row in the CSV so nothing is silently dropped. Stop the sync and report a partial result if the failure ratio across the batch exceeds 5%.

Mark the run complete:

```bash
sqlite3 ./store/leadgen.db "UPDATE pipeline_runs SET status = 'completed', finished_at = datetime('now') WHERE id = '$RUN_ID';"
```

Report to the user in chat: run id, counts at each stage (discovered / qualified / enriched / personalized), and the output file path.

### 8. Replies (optional, separate invocation)

Run this on its own — typically on a schedule, separate from a fresh discovery run — for an existing `campaign_key`. If your outreach channel delivers replies to an inbox you can read (IMAP, an ESP's reply-export endpoint, or forwarded/pasted text), read new messages since the last check, classify each with Claude (`interested` / `not_interested` / `objection` / `ooo` / `bounce` / `unsubscribe`, plus a one-line follow-up action), insert into `replies`, and update `campaign_memberships.engagement_state` to `replied` for anything classified `interested`. Zero new replies is a normal, successful outcome, not an error.

```bash
sqlite3 ./store/leadgen.db "INSERT INTO replies (membership_id, provider, provider_reply_id, reply_text, classification, sentiment, follow_up_action, replied_at, classified_at)
  VALUES ($MEMBERSHIP_ID, '$PROVIDER', '$REPLY_ID', '$REPLY_TEXT', '$CLASSIFICATION', '$SENTIMENT', '$FOLLOW_UP', '$REPLIED_AT', datetime('now'));
  UPDATE campaign_memberships SET engagement_state = 'replied', last_reply_at = datetime('now') WHERE id = $MEMBERSHIP_ID;"
```

For every reply classified `interested`, reply to the user in chat immediately with the company, contact, campaign, a short snippet of the reply, and the suggested follow-up action — don't wait for a batch summary.

<resume_and_status>
**Status** (no side effects):
```bash
sqlite3 -header -column ./store/leadgen.db "SELECT id, status, started_at, finished_at FROM pipeline_runs ORDER BY started_at DESC LIMIT 10;"
sqlite3 -header -column ./store/leadgen.db "SELECT qualification_state, COUNT(*) FROM companies GROUP BY 1;"
```

**Resume** — a `resume --run-id R` request: read `checkpoint_json` and `status` from `pipeline_runs`, find the stage that has the fewest completed rows relative to the ones before it (e.g. companies `qualified` but none `enriched`), and continue from there rather than re-running earlier stages. A run already `completed` should not be resumed — tell the operator it's done. A run `aborted` should only be resumed on an explicit request.
</resume_and_status>

Run this daily via cron for ongoing discovery, and separately every few hours for reply handling — for example:
```
0 7 * * * cd /path/to/project && claude -p "/seo-ops:lead-pipeline" >> logs/lead-pipeline.log 2>&1
```
