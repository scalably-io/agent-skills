---
name: report
description: "Use when the user requests a report, analysis, summary, dashboard, breakdown, deep dive, or any data deliverable that should render as branded HTML. Triggers: build a report, give me a summary, dashboard, analysis, present the findings, show the breakdown. For visuals only (chart, flowchart, diagram) use a dedicated diagram/chart skill instead. To publish the result publicly, deploy it after with Netlify, Surge, or GitHub Pages."
license: MIT
metadata:
  source: https://scalably.io/skills/report
  derived_from:
    path: container/skills/report/SKILL.md
    commit: ef174fc3
    date: "2026-09-07"
    template_path: templates/html/report.html
    template_commit: 7b68ba3
    template_note: "structure derived from production; palette and typography are Scalably's own"
  triggers: [report, analysis, summary, overview, dashboard, breakdown, data presentation, deep dive]
  not_for: [Web research: use a research skill instead., File formats such as .xlsx/.pdf/.pptx: use a dedicated skill for those., Charts or diagrams only, with no report around them.]
---

# Report Design: Branded HTML Reports

## What it does

Turns data (a CSV, a set of numbers, research findings) into a polished, single-file HTML report by copying a pre-built template and filling in its modular sections (hero, key metrics, tables, callouts, closing) rather than writing report HTML from scratch. A built-in QA pass catches mobile overflow, leftover placeholder text, and broken tables before delivery.

## Requirements

- HTML rendering: none beyond a browser.
- Publishing (optional): Netlify CLI, Surge, or GitHub Pages.

## Inputs and outputs

| | |
|---|---|
| Input | A data source (CSV, numbers, or prior research/analysis) plus an audience and a short topic description |
| Output | `./projects/<slug>/output.html`, a single self-contained HTML file, ready to open in a browser or publish |

## Worked example

Paste into Claude Code with this skill installed:

```text
/agent-ops:report quarterly SEO performance report from ./data/q3.csv, audience: client executive, deliver as HTML
```

Expected: the template is copied, filled with the Q3 data, QA-checked, and saved to `./projects/q3-report/output.html`.

## Procedure

### CRITICAL RULES: read first

1. **Never write report HTML from scratch.** Always copy the template first, then edit. Freeform HTML loses the layout system, breaks the mobile stack, and produces cramped tables every time.
2. **Run the QA checklist below before delivering the file.** It catches placeholder leaks, mobile overflow, broken assets, and empty sections.
3. **Fix every issue the checklist finds** before delivery; don't ship a report with a broken layout.
4. **Use `class="table-stack"` plus `data-label` on every dense table** (4+ columns or numeric content). Without it, mobile users get a cramped horizontal-scroll table instead of stacked cards.

### 1. Copy the template

```bash
mkdir -p ./projects/<slug> && cp <skill dir>/templates/report.html ./projects/<slug>/output.html
```

(`<skill dir>` is wherever this skill's files live in your setup. After a
plugin install, find it with `find ~/.claude/plugins -path
'*/report/SKILL.md'` and use its parent directory; from inside the
skill's own folder, just `cp templates/report.html ...`.)

### 2. Edit the copy

**Delete that comment block as your first edit**: a report that still contains it has not been filled in yet.

Replace the placeholder content. Sections are modular: add, remove, reorder, or duplicate any of them:

| Section | Element | Use for |
|---------|---------|---------|
| Header | `.report-header` | Logo/name + report type + date |
| Hero | `.hero` | Title, subtitle, intro |
| Executive summary | `.callout` | The one headline finding |
| Key metrics | `.kpi-grid` | 3-5 KPI cards with labels |
| Pillars | `.feature-grid` / `.feature-card` | 3-4 key areas or framework pillars, each with a heading + description |
| Data table | `table.table-stack` in `.table-wrap` | Tabular data, see Tables below |
| Analysis | `.grid-2` | Two-column deep dive: narrative on one side, a pull-quote `.callout` on the other |
| Alerts | `.callout-success` / `.callout-warning` / `.callout-critical` | Status callouts for a positive result, something to watch, or an urgent issue |
| Recommendations | `<ol>` list with cards | Numbered action items |
| Closing | CTA button | Call to action or sign-off |
| Footer | `<footer>` | Name + report title + date |

### Tables: mobile-stack rule

Tables with 4+ columns or numeric data must use the mobile-stacking pattern:

```html
<table class="table-stack">
  <thead>
    <tr><th>Item</th><th class="num">Value</th><th>Source</th></tr>
  </thead>
  <tbody>
    <tr>
      <td data-label="Item">Organic traffic</td>
      <td class="num" data-label="Value">42,100</td>
      <td data-label="Source">GA4</td>
    </tr>
  </tbody>
</table>
```

On mobile, each row stacks as a labelled card. On desktop it renders as a normal table: same markup, two layouts. Every `<td>` needs a matching `data-label` or the table breaks on mobile.

### 3. QA checklist (before delivery)

Open the file in a browser at three widths (390px, 768px, 1440px) and verify:

- No horizontal overflow at any width
- No leftover `TEMPLATE_PLACEHOLDER` comment or placeholder copy (e.g. "One or two paragraphs of...")
- Stats and cards collapse cleanly: 3-col to 2-col to 1-col
- Every `table-stack` table has `data-label` on every `<td>`
- Footer doesn't clip, links (if any) resolve

Fix every issue found before moving on.

### 4. Deliver

Tell the user the file's path (`./projects/<slug>/output.html`) so they can open it in a browser.

**Publish (optional):** for a client-facing or publicly shared report, deploy the file with the Netlify CLI (`netlify deploy --prod --dir ./projects/<slug>`), Surge (`surge ./projects/<slug>`), or GitHub Pages, and return the URL to the user.

### Adapting sections

- Duplicate any section to repeat it; remove sections you don't need.
- Change grid columns (e.g. `repeat(4, ...)`) to fit the number of cards.
- Use `.label` for a stat card's category, `.stat-value` for the number, `.stat-label` for its description. Add `.stat-change.positive` or `.stat-change.negative` for deltas.
- Wrap tables in `.table-wrap` so they scroll horizontally as a fallback on very small screens.

### Charts (optional)

For a trend or comparison chart, load Chart.js before `</body>`:

```html
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
```

Match the chart's colors and fonts to the CSS variables already defined in the template's `:root` block (`--text`, `--text-60`, `--border`, `--brand`, `--fb`) so it doesn't clash with the rest of the report. Prefer stat cards and tables over charts when the data is simple: a chart earns its place only for a trend over time, a category comparison, or a part-of-whole breakdown.

### Data presentation

- Numbers: right-aligned, tabular figures. Currency with symbol and consistent decimal places.
- Changes: use `.stat-change.positive` (green) or `.stat-change.negative` (red).
- Always show the date range in the header and footer.

### Brand rules

The template ships with Scalably's own design tokens, not a client's: `--bg #faf9f7` (warm off-white canvas), `--text #0a0a09` (near-black), `--green #01e9ac` (the one accent, reserved for the `.cta-button`; never decorative, never a second use per view), `--green-deep #00c896` (green text/links/badges on the light background), `--text-muted #5a5a55` (secondary text, feeds `--text-60`). Typography: `--fd` Instrument Serif for h1-h3, `--fb` Figtree for body text, `--fm` JetBrains Mono for labels (`.section-label`, `.meta`, `.badge`, `.rank-chip`). Every other CSS variable (`--brand`, `--text-95/60/50/30`, `--border*`, `--surface*`) is derived from these five; see the comment above `:root` in the template for the derivation.

### Do not

- Change the CSS custom properties (`--bg`, `--green`, `--green-deep`, `--text`, `--text-muted`, etc.); they hold the template's design system together.
- Introduce a second raw `--green` usage; it belongs to the CTA button only; use `--brand`/`--green-deep` for any other accent.
- Remove the Google Fonts link or change `font-family`.
- Add drop shadows, gradients beyond what's already in the template, or a second accent color.
