#!/usr/bin/env python3
# extract.py — deterministic page extractor for the internal-linking skill,
# defined in ../SKILL.md.
#
# Expects on PATH: python3 3.9+, with `lxml` and `scrapling` installed
# (`pip install lxml cssselect "scrapling[fetchers]"` — `scrapling install`
# once to fetch its bundled browser). `--html-file`/`--md-file` runs need
# only lxml and cssselect.
# Env vars read: none.
# Example invocation:
#   python3 extract.py https://example.com/blog/post --stealth
#   python3 extract.py https://example.com/blog/post --html-file page.html
"""internal-linking pre-parse extractor — site-agnostic.

Fetch a page (httpx fast tier; stealth+CF fallback) and emit structured JSON the
matcher reasons over: headings, existing BODY links (anchor+href,
internal/external), already-used internal body anchors, and candidate body text.

Boilerplate removal is STRUCTURAL, not site-specific:
  1. hard chrome tags (nav/footer/header/aside/form/script/...) + ARIA landmark
     roles (navigation/banner/contentinfo/complementary/search)
  2. class/id TOKEN match against a chrome vocabulary (token match, not
     substring — 'vintage' must not match 'tag')
  3. main-content scoping: prefer <article>/<main>/[role=main]/[itemprop=
     articleBody] when one clearly holds the page's text
  4. link-density filter: any block whose text is >=65% link text with 2+ links
     is navigation/cards/tag-clouds, whatever its class says (readability-style)

Linked text STAYS in body_text so sentences read whole — already-linked
protection is enforced downstream by verify.py (exact reuse + overlap gates).

Usage:
  python3 extract.py URL [--stealth] [--html-file F]
"""
import sys, json, argparse, re
from urllib.parse import urljoin, urlparse


def norm_host(u):
    h = (urlparse(u).netloc or "").lower()
    return h[4:] if h.startswith("www.") else h


CHROME_TAGS = ("nav", "footer", "header", "aside", "script", "style",
               "noscript", "form", "iframe", "svg", "button", "select")
CHROME_ROLES = {"navigation", "banner", "contentinfo", "complementary", "search"}
# class/id tokens that mark non-prose chrome. Matched as whole tokens
# (split on space/_/-/:), so 'vintage' or 'strategy' never match 'tag'.
CHROME_TOKENS = {
    "related", "teaser", "tag", "tags", "taglist", "share", "sharing",
    "breadcrumb", "breadcrumbs", "comment", "comments", "sidebar", "widget",
    "promo", "newsletter", "subscribe", "cta", "social", "pagination",
    "pager", "menu", "navbar", "toc", "popup", "modal", "cookie", "banner",
    "recent", "trending", "popular", "card", "cards", "carousel", "footer",
    "header", "nav", "author", "byline", "meta", "advert", "ad", "ads",
}
_TOKEN_SPLIT = re.compile(r"[\s_\-:/]+")


def _class_tokens(el):
    raw = (el.get("class") or "") + " " + (el.get("id") or "")
    return {t.lower() for t in _TOKEN_SPLIT.split(raw) if t}


def _text(el):
    return re.sub(r"\s+", " ", el.text_content() or "").strip()


# jusText-style stopword density: real prose is ~30-60% stopwords by token;
# cookie banners, legal blurbs, spec lists, button soups sit far below.
_STOPWORDS = frozenset(
    "a about above after again all also an and any are as at be because been "
    "before being below between both but by can could did do does doing down "
    "during each few for from further had has have having he her here hers him "
    "his how i if in into is it its itself just me more most my no nor not of "
    "off on once only or other our out over own s same she should so some such "
    "t than that the their them then there these they this those through to too "
    "under until up very was we were what when where which while who whom why "
    "will with you your yours".split())
_WORD = re.compile(r"[a-z']+")


def _stopword_ratio(text):
    words = _WORD.findall(text.lower())
    if not words:
        return 0.0, 0
    return sum(1 for w in words if w in _STOPWORDS) / len(words), len(words)


def _jsonld_articlebody(doc):
    """Longest articleBody found in JSON-LD blocks — used as a verification
    oracle for the quality verdict, never as the extraction source (often
    truncated/absent, and it carries no link markup)."""
    best = ""
    for s in doc.iter("script"):
        if (s.get("type") or "").lower() != "application/ld+json":
            continue
        try:
            data = json.loads(s.text or "")
        except Exception:
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
            elif isinstance(node, dict):
                ab = node.get("articleBody")
                if isinstance(ab, str) and len(ab) > len(best):
                    best = ab
                stack.extend(node.values())
    return re.sub(r"\s+", " ", best).strip()


def extract(html_str, base_url, selector=None, relaxed=False):
    """relaxed=True is the deterministic FALLBACK pass: only explicit
    semantics are dropped (chrome tags, ARIA roles, rel=tag); all class-token,
    link-density and stopword heuristics are skipped. Different failure mode
    from the strict pass — heuristics misfiring can't hurt it (trafilatura's
    cascade insight: independent algorithms rarely all fail on one page)."""
    from lxml import html as LH
    doc = LH.fromstring(html_str)
    root = doc.find("body")
    if root is None:
        root = doc
    if selector:
        # agent-escalation scope: when the structural heuristics misread a
        # page, the orchestrator inspects the raw HTML and re-runs extraction
        # scoped to the article container it identified. The agent picks the
        # WHERE; text/offsets stay deterministic.
        from lxml.cssselect import CSSSelector
        try:
            hits = CSSSelector(selector)(doc)
        except Exception:
            hits = doc.xpath(selector)
        if not hits:
            raise ValueError("selector %r matched nothing" % selector)
        root = max(hits, key=lambda e: len(_text(e)))
    base_host = norm_host(base_url)
    total_links = len(root.findall(".//a[@href]"))
    page_len = len(_text(root)) or 1

    # 1+2. drop hard chrome: tags, landmark roles, chrome class/id tokens.
    # Class-token drops carry a SIZE GUARD: CMSes wrap real content in
    # generically-named containers (HubSpot puts the whole post body inside
    # `hs_cos_wrapper_meta_field` — token 'meta'); a class heuristic may never
    # remove more than 35% of the page's text. Semantic tags (nav/footer/...)
    # and ARIA landmark roles stay unguarded — they are explicit declarations.
    # <header> is exempt INSIDE article/main: there it is the post's own
    # title block, not site chrome.
    def _in_article(el):
        p = el.getparent()
        while p is not None:
            if isinstance(p.tag, str) and p.tag in ("article", "main"):
                return True
            p = p.getparent()
        return False

    def _prose_len(el):
        # <p>/<blockquote> only: <li> double-counts nested structures and
        # mega-menus are <li>-heavy, which inflated nav "prose" past articles'
        return sum(len(_text(p)) for p in el.iter("p", "blockquote"))

    page_prose = _prose_len(root) or 0

    def _safe_to_token_drop(el):
        # The element must not hold the page's prose. Chrome (navs, footers,
        # tag clouds, bylines) has almost no <p>/<li> prose; article wrappers
        # hold most of it — even when a CMS gives them chrome-looking class
        # names (HubSpot `..._meta_field` wraps the whole post body).
        if page_prose:
            return _prose_len(el) <= 0.3 * page_prose
        return len(_text(el)) <= 0.35 * page_len

    to_drop = []
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        if el.tag in CHROME_TAGS:
            if el.tag == "header" and _in_article(el):
                continue
            to_drop.append(el)
        elif (el.get("role") or "").lower() in CHROME_ROLES:
            to_drop.append(el)
        elif el.tag == "a" and (el.get("rel") or "").lower() == "tag":
            to_drop.append(el)
        elif not relaxed and _class_tokens(el) & CHROME_TOKENS:
            if _safe_to_token_drop(el):
                to_drop.append(el)
    for el in to_drop:
        if el.getparent() is not None:
            el.drop_tree()

    # 3. main-content scoping: take the candidate container that clearly holds
    # the page's text; otherwise keep the whole (chrome-stripped) body.
    body_len = len(_text(root)) or 1
    candidates = (root.findall(".//article") + root.findall(".//main")
                  + root.findall(".//*[@role='main']")
                  + root.findall(".//*[@itemprop='articleBody']"))
    best = None
    for c in candidates:
        t = len(_text(c))
        if t >= 400 and t >= 0.4 * body_len and (best is None or t > len(_text(best))):
            best = c
    if best is not None:
        root = best

    # 4. link-density + stopword-density boilerplate (skipped in relaxed
    # mode). Link-dense blocks are navigation/cards/tag-clouds whatever their
    # class names; low-stopword blocks (cookie banners, legal blurbs, spec
    # soups) are not prose — both guarded so they never eat the article.
    dense = []
    lowsw = []
    root_len = len(_text(root)) or 1
    if not relaxed:
        for el in root.iter("div", "section", "ul", "ol", "table", "article"):
            t = _text(el)
            if len(t) < 40 or len(t) > 0.7 * root_len:
                continue
            anchors = el.findall(".//a[@href]")
            if len(anchors) >= 2:
                atext = " ".join(_text(a) for a in anchors)
                if len(atext) >= 0.65 * len(t):
                    dense.append(el)
                    continue
            ratio, words = _stopword_ratio(t)
            if words >= 15 and ratio < 0.12 and _safe_to_token_drop(el):
                lowsw.append(el)
        for el in dense + lowsw:
            if el.getparent() is not None:
                el.drop_tree()

    # links from the cleaned editorial region
    links, seen = [], set()
    for a in root.findall(".//a[@href]"):
        href = a.get("href")
        anchor = _text(a)
        absu = urljoin(base_url, href)
        if not absu.startswith("http"):
            continue
        internal = norm_host(absu) == base_host
        key = (anchor.lower(), absu)
        if key in seen:
            continue
        seen.add(key)
        links.append({"anchor": anchor, "href": absu, "internal": internal})

    # headings from the cleaned region only (chrome headings polluted matcher
    # context when collected document-wide), then body text without headings
    headings = []
    for h in root.iter("h1", "h2", "h3", "h4", "h5", "h6"):
        t = _text(h)
        if t:
            headings.append(t)
    for h in list(root.iter("h1", "h2", "h3", "h4", "h5", "h6")):
        if h.getparent() is not None:
            h.drop_tree()

    # body text with LINKED-SPAN positions: walk text nodes, remembering which
    # pieces live inside an <a>. verify.py uses the spans to allow an anchor
    # whose string is linked in one place but free elsewhere (positional
    # already-linked check — flat string comparison can't express that).
    pieces = []  # (text, is_link)

    def _walk(el, in_link):
        link_now = in_link or (isinstance(el.tag, str) and el.tag == "a")
        if el.text:
            pieces.append((el.text, link_now))
        for c in el:
            if isinstance(c.tag, str):
                _walk(c, link_now)
            if c.tail:
                pieces.append((c.tail, link_now))

    _walk(root, False)
    body_parts, linked_spans, pos = [], [], 0
    for txt, is_link in pieces:
        t = re.sub(r"\s+", " ", txt).strip()
        if not t:
            continue
        if body_parts:
            pos += 1  # the joining space
        if is_link:
            linked_spans.append([pos, pos + len(t)])
        body_parts.append(t)
        pos += len(t)
    body = " ".join(body_parts)

    return {
        "headings": headings,
        "existing_links": links,
        "existing_internal_anchors": sorted({l["anchor"].lower() for l in links if l["internal"] and l["anchor"]}),
        "body_text": body,
        "linked_spans": linked_spans,
        "stats": {
            "headings": len(headings),
            "links": len(links),
            "internal_links": sum(1 for l in links if l["internal"]),
            "chrome_links_excluded": max(0, total_links - len(links)),
            "dense_blocks_dropped": len(dense),
            "low_stopword_blocks_dropped": len(lowsw),
            "content_root": getattr(root, "tag", "body"),
            "mode": "relaxed" if relaxed else "strict",
            "body_chars": len(body),
        },
    }


_MD_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)[^)]*\)")
_MD_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_MD_HEADING = re.compile(r"^#{1,6}\s+(.*)$")


def extract_markdown(md_str, base_url):
    """Deterministic extract for a MARKDOWN source document (e.g. a draft
    article uploaded in chat, pre-publication). Same output contract as the
    HTML path — body_text, headings, existing_links, linked_spans — so
    verify.py and the matching subagent work unchanged. Strips embedded images
    (including multi-MB base64 data URIs) and code fences."""
    base_host = norm_host(base_url) if base_url.startswith("http") else ""
    headings, pieces, links, seen = [], [], [], set()
    in_fence = False
    for line in md_str.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if "data:image" in line or "data:application" in line:
            line = _MD_IMAGE.sub(" ", line)
            line = re.sub(r"\(data:[^)]*\)?", " ", line)
        line = _MD_IMAGE.sub(" ", line)
        m = _MD_HEADING.match(line)
        if m:
            t = _MD_LINK.sub(lambda g: g.group(1), m.group(1)).strip()
            if t:
                headings.append(t)
            continue
        pos = 0
        for lm in _MD_LINK.finditer(line):
            if lm.start() > pos:
                pieces.append((line[pos:lm.start()], False))
            anchor, href = lm.group(1).strip(), lm.group(2).strip()
            pieces.append((anchor, True))
            absu = href if href.startswith("http") else (urljoin(base_url, href) if base_url.startswith("http") else href)
            internal = bool(base_host) and norm_host(absu) == base_host
            key = (anchor.lower(), absu)
            if key not in seen and absu.startswith("http"):
                seen.add(key)
                links.append({"anchor": anchor, "href": absu, "internal": internal})
            pos = lm.end()
        if pos < len(line):
            pieces.append((line[pos:], False))
        pieces.append((" ", False))

    body_parts, linked_spans, pos = [], [], 0
    for txt, is_link in pieces:
        t = re.sub(r"\s+", " ", txt).strip()
        if not t:
            continue
        if body_parts:
            pos += 1
        if is_link:
            linked_spans.append([pos, pos + len(t)])
        body_parts.append(t)
        pos += len(t)
    body = " ".join(body_parts)
    return {
        "headings": headings,
        "existing_links": links,
        "existing_internal_anchors": sorted({l["anchor"].lower() for l in links if l["internal"] and l["anchor"]}),
        "body_text": body,
        "linked_spans": linked_spans,
        "stats": {
            "headings": len(headings),
            "links": len(links),
            "internal_links": sum(1 for l in links if l["internal"]),
            "chrome_links_excluded": 0,
            "dense_blocks_dropped": 0,
            "low_stopword_blocks_dropped": 0,
            "content_root": "markdown",
            "mode": "markdown",
            "body_chars": len(body),
        },
    }


def fetch(url, stealth=False):
    from scrapling.fetchers import Fetcher, StealthyFetcher
    if not stealth:
        try:
            p = Fetcher.get(url, timeout=20)
            html_str = getattr(p, "html_content", None) or ""
            if len(html_str) > 500 and "just a moment" not in html_str[:1500].lower():
                return html_str, "get"
        except Exception as e:
            sys.stderr.write("get tier failed: %r\n" % e)
    p = StealthyFetcher.fetch(url, headless=True, solve_cloudflare=True)
    return (getattr(p, "html_content", None) or ""), "stealth"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--stealth", action="store_true")
    ap.add_argument("--html-file")
    ap.add_argument("--selector", help="CSS selector (or XPath) of the content container — agent-escalation scope when structural detection misreads a page")
    ap.add_argument("--save-html", help="also save the fetched raw HTML here (for escalation inspection)")
    ap.add_argument("--md-file", help="treat input as a MARKDOWN document (draft article) instead of fetching/parsing HTML; url arg = its future/canonical URL or a placeholder slug")
    a = ap.parse_args()
    try:
        if a.md_file:
            with open(a.md_file, "r", encoding="utf-8", errors="replace") as f:
                out = extract_markdown(f.read(), a.url)
            out["url"] = a.url
            out["status"] = "ok"
            out["tier"] = "markdown"
            s = out["stats"]
            out["quality"] = "ok" if s["body_chars"] >= 500 else "suspect"
            print(json.dumps(out, ensure_ascii=False))
            return
        if a.html_file:
            with open(a.html_file, "r", encoding="utf-8", errors="replace") as f:
                html_str, tier = f.read(), "file"
        else:
            html_str, tier = fetch(a.url, a.stealth)
        if not html_str:
            print(json.dumps({"url": a.url, "status": "error", "error": "empty html"}))
            return
        if a.save_html:
            with open(a.save_html, "w", encoding="utf-8") as f:
                f.write(html_str)

        # JSON-LD articleBody = free verification oracle (never the source)
        from lxml import html as LH
        oracle = _jsonld_articlebody(LH.fromstring(html_str))

        def quality(out):
            s = out["stats"]
            if s["body_chars"] < 500 or (s["links"] == 0 and s["headings"] == 0):
                return "suspect"
            if len(oracle) > 600:
                if s["body_chars"] < 0.5 * len(oracle):
                    return "suspect"  # under-extraction vs declared articleBody
                probe = oracle[200:280].lower()
                if probe and probe not in out["body_text"].lower():
                    return "suspect"  # body diverges from declared articleBody
            return "ok"

        # deterministic cascade: strict -> relaxed (independent failure
        # modes); agent --selector escalation only after both miss
        out = extract(html_str, a.url, selector=a.selector)
        out["quality"] = quality(out)
        if out["quality"] != "ok" and not a.selector:
            relaxed_out = extract(html_str, a.url, relaxed=True)
            relaxed_out["quality"] = quality(relaxed_out)
            if relaxed_out["quality"] == "ok":
                out = relaxed_out
        out["url"] = a.url
        out["status"] = "ok"
        out["tier"] = tier
        out["stats"]["jsonld_articlebody_chars"] = len(oracle)
        print(json.dumps(out, ensure_ascii=False))
    except Exception as e:
        import traceback
        print(json.dumps({"url": a.url, "status": "error", "error": repr(e), "tb": traceback.format_exc()[-600:]}))


if __name__ == "__main__":
    main()
