# Canonical Anchor Placement Rules

Single source of truth for anchor placement. All agents and skills reference this file — do NOT duplicate these rules inline.

## Read Article Type FIRST — two anchor models, mutually exclusive

Before applying any rule, read the **Article Type** field (from the brief, order row, or however the caller supplies it).

- **Standard / PR Piece** → follow **Standard rules S1-S9** below.
- **Listicle** → follow **Listicle rules L1-L9** below. Do NOT apply the Standard model.

The two models contradict each other on purpose. A listicle puts BOTH client anchors together in the client's own list item; the Standard "space anchors ≥2 sections apart, intro is the only link-free zone, Anchor 1 is the first link in the first H2" rules do NOT apply to a listicle and will produce a wrong article if forced. Never mix them.

---

## Standard / PR articles — rules S1-S9

1. Introduction section (before first H2) is completely link-free — no external hyperlinks.
2. Anchor 1 (client primary) is the FIRST external hyperlink in the article.
3. Anchor 1 goes in the first H2 section. Never in intro. Never in first 100 words.
4. Exact anchor text — case-sensitive match.
5. Anchor text flows naturally — not forced, not keyword-stuffed.
6. Never place anchors in the conclusion or last paragraph.
7. If Anchor 2 exists (Standard only): at least 2 full paragraphs after Anchor 1.
8. Do not bold, italicize, or emphasize anchor text.
9. No unauthorized external links. Authorized: high-authority informational sources + publisher internal links from the research brief.

---

## Listicle articles — rules L1-L9

A listicle is a RANKED LIST OF COMPANIES (or tools/services). The client's business is
one of the entries and MUST be first. This is what "Listicle" means here — a review
or a generic themed article is NOT a listicle even if it is labeled that way; if the client and
competitors are not listed as ranked entries, it has failed.

**Structure (mandatory):**
- Title: `Top N [category] companies/tools/services in [year]` (e.g. "7 Top Telecom Audit Companies to Know in 2026").
- Intro (link-free).
- One short H2 on selection criteria — "What to look for when choosing [category]".
- Then an H2 or H3 per entry. **Entry #1 is the CLIENT.** Remaining entries are other companies.

**Anchor placement:**

L1. The **client is entry #1** on the list. Always first.
L2. **Branded anchor (Anchor 1) goes in the client's entry heading (H2/H3).** The brand name in the heading IS the hyperlink. Example heading: `## 1. [ClientBrand](https://example.com)` or `## 1. Vendor-Neutral Advisors (like [ClientBrand](https://example.com))`.
L3. **If a second anchor exists** (a large share of listicles carry 2 anchors to the SAME client): the **keyword anchor (Anchor 2) goes in the body text directly under the client's entry heading**, using the keyword phrase. Both anchors point to the client. They are CO-LOCATED in the client's item — do NOT space them apart.
L4. If only ONE anchor exists: it is the branded anchor in the client's entry heading (L2). No body keyword link.
L5. Exact anchor text — case-sensitive match. Do not bold/italicize the anchor beyond the natural heading formatting.
L6. **NEVER HYPERLINK a competitor** — no `[text](competitor-url)` anywhere: not in a heading, not in body, not as a citation/source credit. Other companies are named in plain PLAIN TEXT only. (A screenshot IMAGE of a competitor is allowed per L7 — the ban is on clickable links/credits, not on showing their site.)
L7. **Images: screenshot EVERY listed company, including competitors** (an established team decision) using a website screenshot tool — each entry gets a real screenshot of that company's site so the listicle reads like a genuine comparison. **The competitor screenshot must be an UNLINKED image with NO source-credit link** (`![Company](images/shot.png)` — never `[![...](shot.png)](competitor-url)` and never an `*Source: [Company](url)*` caption for a competitor). Only the CLIENT's screenshot/caption may link to the client URL. This satisfies both: competitor visuals are shown, but no competitor link/credit exists (the no-competitor-link rule, L6).
L8. Other (non-client) external links must be high-authority informational sources only — `.gov`, `.org`, research, white papers, reports. Never a competitor.
L9. Include 2-3 internal links to the publisher's own articles (non-competitive anchor text).

---

## For researchers (planning phase)

**Standard / PR:**
- Plan Anchor 1 in first H2 section outline.
- Plan Anchor 2 at least 2 H2 sections later (structural breathing room, not just 2 paragraphs).
- For multi-client articles: choose a general topical angle that naturally accommodates both anchors.

**Listicle:**
- Plan a `Top N [category] …` title and a ranked list of real companies in that category, with the CLIENT as entry #1.
- Plan the branded anchor in the client's entry heading and (if a 2nd anchor exists) the keyword anchor in the client's entry body.
- Plan a screenshot target for EVERY listed company (client + competitors) — real site screenshots so it reads as a genuine comparison. Competitors get an UNLINKED screenshot (no source-credit link); only the client's may link to the client URL. Competitors are still NEVER hyperlinked in heading/body/citation.
- The ONLY screenshot target that may carry a link is the client's.

## For QA (validation phase)

**Standard / PR:**
- `anchorPass = false` if ANY rule S1-S9 is violated.
- Check word count to first anchor (must be >100 words from article start).
- Count paragraphs between anchors (must be >=2 full paragraphs).
- Verify no external links appear before Anchor 1.

**Listicle:**
- `anchorPass = false` if ANY rule L1-L9 is violated.
- Verify the client is entry #1.
- Verify the branded anchor is in the client's entry heading (exact text + URL).
- If a second anchor exists, verify the keyword anchor is in the body under the client's entry (exact text + URL). Do NOT check for ≥2-paragraph spacing — co-location is correct here.
- Verify NO competitor is HYPERLINKED anywhere (no `[text](competitor-url)` in heading/body/caption/citation). Competitor SCREENSHOTS are allowed and expected (one per listed company) — but each must be an UNLINKED image with no source-credit link. Fail only if a competitor image is wrapped in a link or has a linked `*Source:*` credit.
- Verify non-client external links are high-authority only, plus 2-3 internal links.
