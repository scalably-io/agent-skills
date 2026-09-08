#!/usr/bin/env python3
# qa_html.py — pre-publish QA gate for HTML deliverables, part of the
# publish-html skill defined in ../SKILL.md.
#
# Expects on PATH: python3 3.10+, with the `playwright` package installed
# and its bundled Chromium available (`pip install playwright && playwright
# install chromium`). Without Chromium, pass --allow-static-only to run the
# text-only checks and skip the browser-rendered ones.
# Env vars read:
#   QA_ALLOWED_PATH_PREFIXES        - colon-separated path allowlist for the
#                                      HTML file argument (default: the
#                                      current working directory, plus /tmp
#                                      and /private/tmp for scratch files)
#   PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH - override Chromium's binary path
#                                      (default: Playwright's own bundled
#                                      build, which is version-matched to
#                                      the installed Playwright release)
# Example invocation:
#   python3 scripts/qa_html.py ./projects/brief/brief.html --strict
"""
qa_html.py — Pre-publish QA gate for HTML deliverables.

Catches the failure modes that have shipped broken HTML to real audiences:
  - unfilled template placeholders
  - horizontal overflow on mobile
  - broken images / fonts / scripts
  - empty sections (skeleton not filled)
  - copy-pasted stat values

Renders the file at 360 / 768 / 1280 px in headless Chromium and returns
JSON to stdout. Exit 0 on PASS, 1 on FAIL. Always writes 3 screenshots
next to the HTML as `.qa-<stem>-<viewport>.png` so you (or a reviewer)
can eyeball them.

Usage
-----
    python3 qa_html.py ./projects/<slug>/report.html
    python3 qa_html.py ./projects/<slug>/report.html --strict   # warnings also fail

Output
------
    {
      "status": "PASS" | "FAIL",
      "file": "...",
      "hard_fails": [...],
      "warnings":   [...],
      "screenshots": [...],
      "metrics": { ... }
    }
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Bumped whenever the sidecar shape or check semantics change, so a
# consumer of the JSON output can detect a stale expectation.
SCRIPT_VERSION = "1.0.0"


def _default_allowed_prefixes() -> list[str]:
    """No fixed project layout in the public build — the default allowlist
    is the current working directory (wherever you invoke this from) plus
    /tmp for legitimate scratch files. Set QA_ALLOWED_PATH_PREFIXES to
    override entirely for a different layout (e.g. a monorepo where the
    HTML lives outside cwd)."""
    return [str(Path.cwd()), "/tmp", "/private/tmp"]  # macOS resolves /tmp -> /private/tmp


def _resolve_safe(
    path: str | Path, *, must_exist: bool, required_suffix: str | None
) -> Path:
    """Resolve a path and require its real target to live under the allowlist.

    `resolve()` follows symlinks, so a symlink that points outside the
    allowlist gets rejected at the allowlist check (its resolved target
    won't match). System symlinks like `/tmp -> /private/tmp` are fine
    because `/private/tmp` is also allowlisted.

    Raises ValueError on rejection.
    """
    raw = Path(path)
    try:
        resolved = raw.resolve(strict=must_exist)
    except FileNotFoundError as e:
        raise ValueError(f"path does not exist: {raw}") from e

    raw_allow = os.environ.get("QA_ALLOWED_PATH_PREFIXES", "")
    prefixes = [p.strip() for p in raw_allow.split(":") if p.strip()] or _default_allowed_prefixes()

    s = str(resolved)
    if not any(
        s == p.rstrip("/") or s.startswith(p.rstrip("/") + "/") for p in prefixes
    ):
        raise ValueError(
            f"path outside allowlist: {resolved}. "
            f"Allowed prefixes: {prefixes}. "
            "Override via QA_ALLOWED_PATH_PREFIXES env var."
        )

    if required_suffix is not None and resolved.suffix.lower() != required_suffix.lower():
        raise ValueError(
            f"wrong extension {resolved.suffix!r} (expected {required_suffix!r})"
        )
    return resolved

# Hard placeholder markers. These are HTML comments embedded in a template
# next to every default value. Whoever fills the template MUST remove the
# marker when filling. Presence in a finished file is unambiguous -> hard
# fail. Regex (not substring matching) to avoid false positives on
# plausible real values like "+28%" or "TBD" that happen to share a word.
PLACEHOLDER_MARKER_RE = re.compile(
    # Match the TEMPLATE_PLACEHOLDER token inside any HTML comment block
    # (single- or multi-line), capturing the optional :name suffix.
    r"<!--[\s\S]*?TEMPLATE_PLACEHOLDER(?::([\w-]+))?[\s\S]*?-->",
    re.IGNORECASE,
)

# Long, distinctive prose that nobody types in real content. Hard fail if
# any of these appear verbatim in the rendered HTML.
HIGH_CONFIDENCE_PLACEHOLDERS: list[str] = [
    "One-line summary of what this report covers.",
    "Brief introduction to the pillars, framework, or focus areas.",
    "Description of the first concept or area of focus.",
    "Description of the second concept or area of focus.",
    "Description of the third concept or area of focus.",
    "Write 2-4 paragraphs.",
    "A pull quote or key insight that deserves emphasis",
    "Positive finding or result that should be highlighted.",
    "Something that needs attention but is not critical.",
    "Urgent issue requiring immediate action.",
    "Replace this with",
    "Lorem ipsum",
    "{{",
    "}}",
    "<%=",
]

# Strings that USUALLY indicate template defaults but COULD be real content
# in a legitimate deliverable ("+28%" is a real KPI; "First Pillar" might
# be a real product name). Warn but do not block.
SOFT_PLACEHOLDERS: list[str] = [
    "Company Name",
    "Report Title",
    "Report Type",
    "Key headline finding or insight",
    "Primary Metric",
    "Secondary Metric",
    "Tertiary Metric",
    "Fourth Metric",
    "First Pillar",
    "Second Pillar",
    "Third Pillar",
    "Success headline",
    "Warning headline",
    "Critical headline",
    "Row item one",
    "Row item two",
    "Row item three",
    "Row item four",
    "First key finding",
    "Second key finding",
    "Third key finding",
    "First recommendation",
    "Second recommendation",
    "Third recommendation",
    "Fourth recommendation",
    "+12.4%",
    "1.29M",
    "TODO:",
    "TBD",
    "PLACEHOLDER",
]

# Strings that are LEGITIMATE in a finished report and must never trigger
# a placeholder warning.
PLACEHOLDER_WHITELIST: set[str] = {
    "Confidential",
}

VIEWPORTS = [
    {"name": "mobile", "width": 360, "height": 800, "dpr": 2},
    {"name": "tablet", "width": 768, "height": 1024, "dpr": 2},
    {"name": "desktop", "width": 1280, "height": 900, "dpr": 1},
]

# Brand fingerprints. When a brand is requested via --brand, the file MUST
# contain at least one fingerprint from each axis (font + color token) or
# the gate fails. This catches "the agent freelanced HTML instead of using
# the brand's template" — a real failure mode where a required design
# system gets silently ignored and the output looks like a different
# product. `example-brand` below is a placeholder showing the pattern;
# replace it with your own brand's actual fonts/tokens (see the `report`
# skill's template for one worked example of a brand to fingerprint).
BRANDS: dict[str, dict[str, list[str]]] = {
    "example-brand": {
        "fonts": ["Instrument Serif", "Figtree"],
        "color_tokens": [
            "--bg:",
            "--text-muted:",
        ],
    },
}


@dataclass
class QAResult:
    status: str = "PASS"
    file: str = ""
    file_sha256: str = ""
    qa_run_at: str = ""
    script_version: str = SCRIPT_VERSION
    hard_fails: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    screenshots: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(self.__dict__, indent=2, default=str)


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _scan_static_html(html: str, result: QAResult, brand: str | None = None) -> None:
    """Cheap regex/string checks that don't need a browser."""
    # Hard placeholder markers — whoever copied the template and didn't
    # remove these is shipping skeleton text.
    marker_hits = PLACEHOLDER_MARKER_RE.findall(html)
    if marker_hits:
        named = sorted({m for m in marker_hits if m})
        anonymous = sum(1 for m in marker_hits if not m)
        bits: list[str] = []
        if named:
            bits.append(f"named: {named[:8]}{'…' if len(named) > 8 else ''}")
        if anonymous:
            bits.append(f"unnamed: {anonymous}")
        result.hard_fails.append(
            "TEMPLATE_PLACEHOLDER markers leaked — the template was copied but the "
            "markers weren't removed after filling it in. " + "; ".join(bits)
        )

    high_leaked = [
        s
        for s in HIGH_CONFIDENCE_PLACEHOLDERS
        if s in html and s not in PLACEHOLDER_WHITELIST
    ]
    if high_leaked:
        result.hard_fails.append(
            "unfilled placeholders (high-confidence) leaked into final HTML: "
            + ", ".join(repr(s) for s in high_leaked[:8])
            + ("…" if len(high_leaked) > 8 else "")
        )

    soft_leaked = [
        s
        for s in SOFT_PLACEHOLDERS
        if s in html and s not in PLACEHOLDER_WHITELIST
    ]
    if soft_leaked:
        result.warnings.append(
            "possible unfilled placeholders (could be real content): "
            + ", ".join(repr(s) for s in soft_leaked[:8])
            + ("…" if len(soft_leaked) > 8 else "")
            + " — verify each value is intentional"
        )

    if brand:
        spec = BRANDS.get(brand)
        if not spec:
            result.warnings.append(
                f"unknown brand '{brand}' — known brands: {list(BRANDS)}"
            )
        else:
            font_hits = [f for f in spec["fonts"] if f in html]
            color_hits = [c for c in spec["color_tokens"] if c in html]
            if not font_hits or not color_hits:
                result.hard_fails.append(
                    f"brand '{brand}' fingerprint missing — file does not look like a "
                    f"{brand} deliverable. Found fonts: {font_hits or 'NONE'}, "
                    f"color tokens: {color_hits or 'NONE'}. "
                    f"Required: at least one font from {spec['fonts']} AND at least one "
                    f"color token from {spec['color_tokens']}. "
                    "Most likely cause: the file was written from scratch instead of "
                    "copying the brand's template (see the `report` skill's "
                    "templates/report.html for one worked example)."
                )

    # File too short
    visible = re.sub(r"<[^>]+>", " ", html)
    visible = re.sub(r"\s+", " ", visible).strip()
    result.metrics["visible_chars"] = len(visible)
    if len(visible) < 200:
        result.hard_fails.append(
            f"visible text too short ({len(visible)} chars) — page is empty or skeleton-only"
        )

    # Sanity — file has no <body> contents
    body_match = re.search(r"<body[^>]*>(.*?)</body>", html, re.DOTALL | re.IGNORECASE)
    if not body_match or len(body_match.group(1).strip()) < 50:
        result.hard_fails.append("<body> is empty or missing — file likely incomplete")


def _check_overflow(page: Any, vp: dict[str, Any], result: QAResult) -> None:
    overflow = page.evaluate(
        """
        () => {
          const docW = document.documentElement.scrollWidth;
          const viewW = window.innerWidth;
          const offending = [...document.querySelectorAll('body *')]
            .filter(el => {
              if (!el.offsetParent && el.tagName !== 'BODY') return false;
              const r = el.getBoundingClientRect();
              return r.right > viewW + 1 && r.width > 0 && r.height > 0;
            })
            .slice(0, 5)
            .map(el => ({
              tag: el.tagName.toLowerCase(),
              cls: (el.className || '').toString().slice(0, 80),
              w: Math.round(el.getBoundingClientRect().width),
              right: Math.round(el.getBoundingClientRect().right),
            }));
          return { docW, viewW, offending };
        }
        """
    )
    if overflow["docW"] > overflow["viewW"] + 1:
        result.hard_fails.append(
            f"[{vp['name']} {vp['width']}px] horizontal overflow: "
            f"document is {overflow['docW']}px wide, viewport {overflow['viewW']}px. "
            f"Offending elements: {overflow['offending']}"
        )


def _check_broken_assets(page: Any, vp: dict[str, Any], result: QAResult) -> None:
    broken = page.evaluate(
        """
        () => ({
          imgs: [...document.images]
            .filter(i => i.complete && i.naturalWidth === 0)
            .map(i => i.currentSrc || i.src)
            .slice(0, 5),
          videos: [...document.querySelectorAll('video')]
            .filter(v => v.error)
            .map(v => v.currentSrc || v.querySelector('source')?.src || '')
            .slice(0, 5),
        })
        """
    )
    if broken["imgs"]:
        result.hard_fails.append(f"[{vp['name']}] broken images: {broken['imgs']}")
    if broken["videos"]:
        result.hard_fails.append(f"[{vp['name']}] broken videos: {broken['videos']}")

    fonts_ready = page.evaluate(
        "() => document.fonts && document.fonts.status === 'loaded'"
    )
    if fonts_ready is False:
        result.warnings.append(f"[{vp['name']}] fonts did not finish loading")


def _check_empty_sections(page: Any, vp: dict[str, Any], result: QAResult) -> None:
    if vp["name"] != "desktop":
        return
    empties = page.evaluate(
        """
        () => [...document.querySelectorAll('section')]
          .map((s, i) => ({
            i,
            id: s.id || s.className || s.tagName.toLowerCase(),
            text: (s.innerText || '').replace(/\\s+/g, ' ').trim(),
          }))
          .filter(s => s.text.length < 30)
          .slice(0, 5)
        """
    )
    if empties:
        for s in empties:
            result.hard_fails.append(
                f"empty section #{s['i']} ({s['id']}): only {len(s['text'])} chars — "
                f"skeleton not filled. Content: {s['text']!r}"
            )


def _check_stat_dupes(page: Any, vp: dict[str, Any], result: QAResult) -> None:
    if vp["name"] != "desktop":
        return
    stats = page.evaluate(
        """
        () => [...document.querySelectorAll('.stat-value')]
          .map(el => el.innerText.trim())
          .filter(t => t.length > 0)
        """
    )
    if len(stats) >= 2:
        unique = set(stats)
        if len(unique) == 1:
            result.warnings.append(
                f"all {len(stats)} .stat-value elements show the same value {stats[0]!r} "
                "— likely copy-paste, fill each stat individually"
            )


def _check_table_overflow(page: Any, vp: dict[str, Any], result: QAResult) -> None:
    if vp["name"] != "mobile":
        return
    info = page.evaluate(
        """
        () => [...document.querySelectorAll('table')]
          .map((t, i) => {
            const r = t.getBoundingClientRect();
            return {
              i,
              cls: (t.className || '').toString(),
              cols: t.querySelector('thead tr')?.children.length || 0,
              w: Math.round(r.width),
              docW: t.scrollWidth,
              viewW: window.innerWidth,
            };
          })
        """
    )
    for t in info:
        is_stack = "table-stack" in t["cls"]
        if t["cols"] >= 4 and not is_stack:
            result.warnings.append(
                f"table #{t['i']} has {t['cols']} columns and no .table-stack class — "
                "dense tables get cramped on mobile. Add class=\"table-stack\" "
                "and data-label attrs on each <td>."
            )


def _check_table_stack_labels(page: Any, vp: dict[str, Any], result: QAResult) -> None:
    """`.table-stack` requires non-empty data-label on every body cell, otherwise
    the mobile label/value layout silently breaks."""
    if vp["name"] != "desktop":
        return
    bad = page.evaluate(
        """
        () => [...document.querySelectorAll('table.table-stack')]
          .map((t, i) => {
            const cells = [...t.querySelectorAll('tbody td')];
            const missing = cells
              .map((c, ci) => ({
                ci,
                text: (c.innerText || '').trim().slice(0, 40),
                label: (c.getAttribute('data-label') || '').trim(),
              }))
              .filter(c => !c.label);
            return { i, missing: missing.slice(0, 5), totalMissing: missing.length };
          })
          .filter(t => t.totalMissing > 0)
        """
    )
    for t in bad:
        result.hard_fails.append(
            f"table.table-stack #{t['i']} has {t['totalMissing']} body cell(s) "
            f"without data-label — mobile layout will break (no label shown). "
            f"Sample: {t['missing']}"
        )


def _capture_console(page: Any, errors: list[str]) -> None:
    page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
    page.on(
        "console",
        lambda msg: errors.append(f"{msg.type}: {msg.text}") if msg.type == "error" else None,
    )


def _install_file_url_guard(context: Any, allowed_url: str) -> None:
    """Block any file:// request OTHER than the initial navigation.
    Defense against HTML that smuggles `<img src="file:///etc/...">` into
    the rendered output / screenshot."""
    def handler(route: Any) -> None:
        try:
            url = route.request.url
            if url == allowed_url:
                return route.continue_()
            if url.startswith("file://"):
                return route.abort()
            return route.continue_()
        except Exception:
            try:
                return route.abort()
            except Exception:
                pass
    try:
        context.route("**/*", handler)
    except Exception:
        pass


def qa_html(
    html_path: Path,
    strict: bool = False,
    brand: str | None = None,
    allow_static_only: bool = False,
) -> QAResult:
    result = QAResult(file=str(html_path))

    # Path confinement — an untrusted path argument is rejected up front:
    # symlink escapes, paths outside the allowlist, and the wrong extension
    # are all caught before the file is ever opened.
    try:
        safe = _resolve_safe(html_path, must_exist=True, required_suffix=".html")
    except ValueError as e:
        result.status = "FAIL"
        result.hard_fails.append(f"path rejected: {e}")
        return result
    html_path = safe
    result.file = str(html_path)
    result.qa_run_at = _dt.datetime.now(_dt.timezone.utc).isoformat()

    try:
        result.file_sha256 = _sha256_of(html_path)
    except Exception as e:
        result.status = "FAIL"
        result.hard_fails.append(f"could not hash file: {e}")
        return result

    try:
        html = html_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        result.status = "FAIL"
        result.hard_fails.append(f"could not read file: {e}")
        return result

    _scan_static_html(html, result, brand=brand)

    # Render in headless Chromium at every viewport.
    # Default = browser REQUIRED. If unavailable, hard fail. Override only
    # via --allow-static-only for explicit debug runs.
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        msg = f"playwright not installed — browser-rendered checks unavailable: {e}"
        if allow_static_only:
            result.warnings.append(msg + " (static-only mode)")
            if result.hard_fails:
                result.status = "FAIL"
            return result
        result.hard_fails.append(
            msg + ". Install playwright (`pip install playwright && playwright install "
            "chromium`) or pass --allow-static-only for debug."
        )
        result.status = "FAIL"
        return result

    # Use Playwright's OWN bundled Chromium (version-locked to the installed
    # Playwright release) — executable_path=None makes Playwright resolve
    # its bundled build. A manually pinned system Chromium can drift out of
    # version lockstep with Playwright's CDP handshake and fail to launch,
    # so this only honors PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH when it
    # deliberately points somewhere that actually exists.
    chromium_path = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH")
    if not chromium_path or not Path(chromium_path).exists():
        chromium_path = None
    file_url = "file://" + str(html_path)

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(
                executable_path=chromium_path,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
        except Exception as e:
            msg = f"could not launch chromium: {e}"
            if allow_static_only:
                result.warnings.append(msg + " — static-only mode")
                if result.hard_fails:
                    result.status = "FAIL"
                return result
            result.hard_fails.append(
                msg + ". Pass --allow-static-only for explicit debug runs."
            )
            result.status = "FAIL"
            return result

        for vp in VIEWPORTS:
            ctx = browser.new_context(
                viewport={"width": vp["width"], "height": vp["height"]},
                device_scale_factor=vp["dpr"],
            )
            _install_file_url_guard(ctx, file_url)
            page = ctx.new_page()
            console_errors: list[str] = []
            _capture_console(page, console_errors)
            try:
                page.goto(file_url, wait_until="domcontentloaded", timeout=15000)
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception as e:
                result.warnings.append(f"[{vp['name']}] page load issue: {e}")
            try:
                _check_overflow(page, vp, result)
                _check_broken_assets(page, vp, result)
                _check_empty_sections(page, vp, result)
                _check_stat_dupes(page, vp, result)
                _check_table_overflow(page, vp, result)
                _check_table_stack_labels(page, vp, result)
            except Exception as e:
                result.warnings.append(f"[{vp['name']}] check error: {e}")

            shot_path = html_path.parent / f".qa-{html_path.stem}-{vp['name']}.png"
            try:
                page.screenshot(path=str(shot_path), full_page=True)
                result.screenshots.append(str(shot_path))
            except Exception as e:
                result.warnings.append(f"[{vp['name']}] screenshot failed: {e}")

            if console_errors:
                result.warnings.append(
                    f"[{vp['name']}] {len(console_errors)} console error(s): "
                    + " | ".join(console_errors[:3])
                )

            ctx.close()
        browser.close()

    if result.hard_fails or (strict and result.warnings):
        result.status = "FAIL"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="HTML pre-publish QA gate")
    parser.add_argument("html_path", help="Path to the HTML file to QA")
    parser.add_argument(
        "--strict", action="store_true", help="Treat warnings as failures"
    )
    parser.add_argument(
        "--brand",
        default=None,
        choices=sorted(BRANDS.keys()),
        help="Require brand fingerprint (fonts + color tokens). "
        "Catches HTML written freeform instead of from the required brand template.",
    )
    parser.add_argument(
        "--allow-static-only",
        action="store_true",
        help="If set, missing Chromium/Playwright produces warnings instead of "
        "hard fails. Default OFF — a real QA run needs a browser.",
    )
    args = parser.parse_args()

    result = qa_html(
        Path(args.html_path),
        strict=args.strict,
        brand=args.brand,
        allow_static_only=args.allow_static_only,
    )
    print(result.to_json())

    # Persist JSON next to the file so a later step (or a human) can detect
    # "QA was run" without re-running it.
    log_path = Path(args.html_path).parent / f".qa-{Path(args.html_path).stem}.json"
    try:
        log_path.write_text(result.to_json(), encoding="utf-8")
    except Exception:
        pass

    return 0 if result.status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
