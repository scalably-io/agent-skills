#!/usr/bin/env python3
# il_candidates.py — deterministic TARGET/SOURCE candidate selector for the
# internal-linking skill, defined in ../SKILL.md. This is the free,
# no-API-key path: it needs no Ahrefs/DataForSEO account to produce a
# usable campaign shortlist from Google Search Console + the sitemap alone.
#
# Expects on PATH: python3 3.9+, stdlib only (urllib, gzip, xml.etree) plus
# `google-auth` if you pass --sa (GSC access via a Google service account;
# `pip install google-auth`). Without --sa (or with an unreadable file) the
# script degrades automatically to sitemap-only candidate selection — no
# error, just a smaller/less-ranked pool. Without --sa, SOURCE candidates
# come back empty (source ranking needs GSC clicks/impressions, and there's
# no sitemap-only fallback for that half) — pass --sources FILE (one URL
# per line, '#' comments allowed) to supply your own source list instead.
# Env vars read: none — auth is by the --sa service-account JSON file.
# Example invocation:
#   python3 il_candidates.py --domain example.com --max-targets 15 \
#       --max-sources 30 --json profiles/candidates.json
#   # no-GSC-access path:
#   python3 il_candidates.py --domain example.com --sources my-sources.txt \
#       --json profiles/candidates.json
"""il_candidates — deterministic TARGET/SOURCE candidate selection for an
internal-linking campaign. Agent-browser pattern: the CLI does all data
gathering + ranking; the agent reads a COMPACT structured table and applies
final SEO judgment. No MCP round-trips, no raw API blobs in the agent context.

Data sources — GSC maximally, all of it FREE (no API units), read from a
Google service account you provide (via --sa); the agent never sees a key:
  - GSC page metrics (searchAnalytics, dim=[page]) — the performance universe:
    clicks, impressions, CTR, position per page. PRIMARY selection signal.
  - GSC page+query (searchAnalytics, dim=[page,query]) — the actual Google
    queries each page ranks for = FREE per-page keyword profiles, more accurate
    than a paid keyword tool's estimates for the site's own pages. Feeds the
    matcher's profiles.
  - Sitemap (robots.txt -> sitemap.xml, recursive, gzip-tolerant) — catches
    zero-traffic / brand-new pages GSC cannot see (no impressions yet).
This script does not call Ahrefs or DataForSEO — see SKILL.md's Requirements
for the optional paid keyword-value-weighting step (via an MCP server), which
runs separately and only on the shortlist this script produces.

Selection rules:
  TARGETS (pages to boost), up to 15:
    bucket A  page-2 rankers        : 11 <= position <= 20
    bucket B  high-impr / low-click : impressions >= IMPR_MIN and clicks <= CLICK_MAX
    bucket C  zero-traffic          : in sitemap, absent from GSC (need most help)
  SOURCES (link-from pages), up to 30:
    high clicks desc, then impressions desc; EXCLUDE pages used as a source in
    the last LEDGER_WINDOW_DAYS (unless the site is small < SMALL_SITE).
    With --sources FILE instead: the given URLs are the source set, filtered
    to the same domain and excluding chosen targets — no GSC ranking applied.
  A page is never both a target and a source in one run. Obvious junk URLs
  (/tag/ /category/ /wp- /cart /privacy /login ...) are pre-filtered.

Caps are "up to" — never padded. Output is compact (top ~40 targets / ~50
sources) so even a 1000-page site stays context-safe.

Usage:
  python3 il_candidates.py --domain example.com \
      [--sa /path/to/service-account.json] [--sources sources.txt] \
      [--ledger ledger.json] \
      [--days 90] [--max-targets 15] [--max-sources 30] [--json out.json]
Output (stdout): a compact human+machine table; full JSON with --json.
"""
import sys, os, json, argparse, gzip, re, time, urllib.request, urllib.parse, urllib.error
import warnings
from pathlib import Path
# Silence the harmless RequestsDependencyWarning (urllib3/chardet version mismatch
# in any python3) — it's cosmetic but prints to stderr on every run and has made
# the agent waste turns "investigating" it. Suppress so the run stays clean.
warnings.filterwarnings("ignore")
from xml.etree import ElementTree as ET

UA = {"User-Agent": "Mozilla/5.0 (compatible; il-candidates/1.0)"}
IMPR_MIN = 200          # bucket B: high-impression threshold
CLICK_MAX = 2           # bucket B: low/zero-click threshold
PAGE2_LO, PAGE2_HI = 11, 20
LEDGER_WINDOW_DAYS = 90
SMALL_SITE = 40         # below this many pages, allow source reuse
JUNK = re.compile(r"/(tag|category|categories|author|page|wp-|cart|checkout|"
                  r"privacy|terms|login|signin|sign-in|register|account|search|"
                  r"feed|wp-json|cdn-cgi)(/|$|\?)", re.I)
# Index/listing/hub pages — poor SOURCES (little body prose, mostly links/nav).
# A bare section root like /blog or /blog/ is a listing; exclude from sources.
INDEXLIKE = re.compile(r"/(blog|articles?|posts?|news|resources?|category|categories"
                       r"|topics?|guides?)/?$", re.I)

# ---------- GSC (direct API, service account; token fetched once, reused) ----------
_GSC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"

def _gsc_token(sa_path):
    """OAuth access token for the mounted SA. Prefers google-auth; falls back to
    a hand-rolled RS256 JWT (cryptography) when google-auth is absent. None on
    failure / missing SA file."""
    if not (sa_path and os.path.exists(sa_path)):
        return None
    try:
        import google.auth.transport.requests
        from google.oauth2 import service_account
        creds = service_account.Credentials.from_service_account_file(
            sa_path, scopes=[_GSC_SCOPE])
        creds.refresh(google.auth.transport.requests.Request())
        return creds.token
    except Exception:
        pass
    try:
        import base64
        from cryptography.hazmat.primitives import serialization, hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        sa = json.load(open(sa_path)); now = int(time.time())
        def b(o): return base64.urlsafe_b64encode(json.dumps(o).encode()).rstrip(b"=")
        si = b({"alg": "RS256", "typ": "JWT"}) + b"." + b({
            "iss": sa["client_email"], "scope": _GSC_SCOPE,
            "aud": "https://oauth2.googleapis.com/token", "iat": now, "exp": now + 3600})
        k = serialization.load_pem_private_key(sa["private_key"].encode(), None)
        jwt = si + b"." + base64.urlsafe_b64encode(
            k.sign(si, padding.PKCS1v15(), hashes.SHA256())).rstrip(b"=")
        return json.load(urllib.request.urlopen("https://oauth2.googleapis.com/token",
            data=urllib.parse.urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": jwt.decode()}).encode()))["access_token"]
    except Exception:
        return None

def _gsc_query_rows(site, tok, days, dims, limit=25000):
    """Raw searchAnalytics rows for a property + dimensions, or None on HTTP error
    (so the caller can try the other property form)."""
    end = time.strftime("%Y-%m-%d", time.gmtime())
    start = time.strftime("%Y-%m-%d", time.gmtime(time.time() - days * 86400))
    body = json.dumps({"startDate": start, "endDate": end,
                       "dimensions": dims, "rowLimit": limit}).encode()
    url = (f"https://www.googleapis.com/webmasters/v3/sites/"
           f"{urllib.parse.quote(site, safe='')}/searchAnalytics/query")
    req = urllib.request.Request(url, data=body,
                                 headers={"Authorization": f"Bearer {tok}",
                                          "Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=60)).get("rows", [])
    except urllib.error.HTTPError:
        return None

def gsc_pages(domain, tok, days):
    """({url: {clicks, impressions, ctr, position}}, working_site_url) from GSC
    (dim=[page]). Returns ({}, None) if no property is accessible."""
    if not tok:
        return {}, None
    for site in (f"sc-domain:{domain}", f"https://{domain}/"):
        rows = _gsc_query_rows(site, tok, days, dims=["page"])
        if rows is not None:
            return ({_canon(r["keys"][0]): {
                "clicks": r.get("clicks", 0), "impressions": r.get("impressions", 0),
                "ctr": round(r.get("ctr", 0), 4), "position": round(r.get("position", 0), 1)}
                for r in rows}, site)
    return {}, None

# ---------- Sitemap (robots.txt -> recursive, gzip-tolerant) ----------
def sitemap_urls(domain):
    seen, pages = set(), set()
    starts = _robots_sitemaps(domain) or [f"https://{domain}/sitemap.xml",
                                           f"https://{domain}/sitemap_index.xml"]
    stack = list(starts)
    while stack:
        sm = stack.pop()
        if sm in seen or len(seen) > 200:
            continue
        seen.add(sm)
        data = _fetch(sm)
        if not data:
            continue
        try:
            root = ET.fromstring(data)
        except ET.ParseError:
            continue
        ns = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
        children = [l.text.strip() for s in root.iter(f"{ns}sitemap")
                    for l in [s.find(f"{ns}loc")] if l is not None and l.text]
        stack.extend(children)
        for u in root.iter(f"{ns}url"):
            l = u.find(f"{ns}loc")
            if l is not None and l.text:
                pages.add(_canon(l.text.strip()))
    return pages

def _robots_sitemaps(domain):
    data = _fetch(f"https://{domain}/robots.txt")
    if not data:
        return []
    return re.findall(r"(?im)^\s*sitemap:\s*(\S+)", data.decode("utf-8", "ignore"))

def _fetch(url):
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25)
        data = r.read()
        if url.endswith(".gz") or data[:2] == b"\x1f\x8b":
            data = gzip.decompress(data)
        return data
    except Exception:
        return None

# ---------- GSC page+query profiles (FREE keyword profiles per page) ----------
def _toggle_www(u):
    """Return the same URL with www. added if absent / removed if present, or None
    if the host can't be toggled. Used to recover from a www-canonical mismatch."""
    p = urllib.parse.urlparse(u or "")
    host = p.netloc
    if not host:
        return None
    new = host[4:] if host.lower().startswith("www.") else "www." + host
    return urllib.parse.urlunparse(p._replace(netloc=new))


def _inspect_one(url, site, tok, base):
    """One URL Inspection call. Returns the indexStatusResult dict, or None on error."""
    body = json.dumps({"inspectionUrl": url, "siteUrl": site,
                       "languageCode": "en-US"}).encode()
    req = urllib.request.Request(base, data=body,
          headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=30)) \
               .get("inspectionResult", {}).get("indexStatusResult", {})
    except Exception:
        return None


def gsc_inspect(urls, site, tok, budget=45):
    """URL Inspection (searchconsole.googleapis.com) on a BOUNDED set of candidate
    URLs — returns {url: {coverage, verdict, referring_urls_count, indexed}}.
    coverageState like 'Crawled - currently not indexed' / 'Discovered - currently
    not indexed' marks the highest-value internal-linking targets (links can push
    them into the index). referring_urls_count = how many internal links Google
    already sees -> low count = under-linked. Rate-limited (~2000/day, slow per
    URL), so capped at `budget`. Best-effort; never blocks selection.

    WWW-CANONICAL RECOVERY: GSC may report page URLs in one host form (e.g. non-www,
    after _canon strips www) while Google indexed the OTHER form (www). Inspecting the
    wrong form returns the false-negative coverage 'URL is unknown to Google'. When we
    see that, retry the www-toggled form and keep whichever Google actually knows — so
    an indexed page is never mislabelled 'not-indexed' (which would wrongly float it to
    the top of the target ranking and print a false status into the output)."""
    if not (tok and urls):
        return {}
    out = {}
    base = "https://searchconsole.googleapis.com/v1/urlInspection/index:inspect"
    for u in list(urls)[:budget]:
        ir = _inspect_one(u, site, tok, base)
        if ir is None:
            continue
        cov = ir.get("coverageState", "")
        # False-negative recovery: the inspected host form is unknown to Google but
        # the page may be indexed under the www-toggled form. Try it once.
        if "unknown to google" in cov.lower():
            alt = _toggle_www(u)
            if alt:
                alt_ir = _inspect_one(alt, site, tok, base)
                if alt_ir and "unknown to google" not in (alt_ir.get("coverageState", "")).lower():
                    ir, cov = alt_ir, alt_ir.get("coverageState", "")
        out[u] = {"coverage": cov, "verdict": ir.get("verdict"),
                  "referring_urls_count": len(ir.get("referringUrls", []) or []),
                  "indexed": ir.get("verdict") == "PASS" and "not indexed" not in cov.lower()}
    return out

def gsc_profiles(domain, tok, days, top_n=12):
    """{url: [{q, clicks, impressions, position}]} — the top Google queries each
    page ranks for, straight from GSC (FREE, no API units, the site's real data).
    One searchAnalytics call with dim=[page,query]. Returns {} on no access."""
    if not tok:
        return {}
    for site in (f"sc-domain:{domain}", f"https://{domain}/"):
        rows = _gsc_query_rows(site, tok, days, dims=["page", "query"], limit=25000)
        if rows is None:
            continue
        prof = {}
        for r in rows:
            u = _canon(r["keys"][0])
            prof.setdefault(u, []).append({
                "q": r["keys"][1], "clicks": r.get("clicks", 0),
                "impressions": r.get("impressions", 0),
                "position": round(r.get("position", 0), 1)})
        for u in prof:  # keep top_n queries per page by impressions
            prof[u] = sorted(prof[u], key=lambda x: -x["impressions"])[:top_n]
        return prof
    return {}

# ---------- helpers ----------
def _canon(u):
    p = urllib.parse.urlparse((u or "").strip())
    host = p.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = p.path.rstrip("/") or "/"
    return f"https://{host}{path}"

def _recent_ledger_sources(ledger_path, window_days):
    if not (ledger_path and os.path.exists(ledger_path)):
        return set()
    cutoff = time.strftime("%Y-%m-%d", time.gmtime(time.time() - window_days * 86400))
    used = set()
    for line in open(ledger_path, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except Exception:
            continue
        if (e.get("date") or "9999") >= cutoff and e.get("source"):
            used.add(_canon(e["source"]))
    return used

def _load_sources_file(path, domain):
    """--sources FILE: one URL per line, '#' starts a comment (inline or
    whole-line), blank lines ignored. Returns canonicalized, deduped URLs
    restricted to the given domain (www-insensitive) — the caller still
    excludes chosen targets on top of this."""
    dom = domain.lower()
    if dom.startswith("www."):
        dom = dom[4:]
    urls, seen = [], set()
    for line in open(path, encoding="utf-8"):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        u = _canon(line)
        host = urllib.parse.urlparse(u).netloc.lower()
        if host != dom or u in seen:
            continue
        seen.add(u)
        urls.append(u)
    return urls

# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", required=True)
    ap.add_argument("--sa", help="path to a Google service account JSON key with Search Console read access; omit to skip GSC and use sitemap-only selection")
    ap.add_argument("--sources", help="path to a plain-text file of source URLs (one per line, "
                     "'#' starts a comment) to use as the SOURCE set instead of GSC-ranked "
                     "sources; still filtered to the same domain and to exclude chosen "
                     "targets. Use this for the no-Search-Console-access path — without --sa, "
                     "source ranking needs GSC clicks/impressions and returns empty otherwise.")
    ap.add_argument("--ledger")
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--max-targets", type=int, default=15)
    ap.add_argument("--max-sources", type=int, default=30)
    ap.add_argument("--inspect", action="store_true",
                    help="enrich target shortlist with URL Inspection index-status "
                         "(unindexed/under-linked detection); slower, rate-limited")
    ap.add_argument("--json")
    a = ap.parse_args()
    domain = a.domain.replace("https://", "").replace("http://", "").strip("/")

    tok = _gsc_token(a.sa)                          # one token, reused
    gsc, site_url = gsc_pages(domain, tok, a.days)  # dim=[page] — metrics + resolved property
    profiles = gsc_profiles(domain, tok, a.days)    # dim=[page,query] — FREE keyword profiles
    smap = sitemap_urls(domain)
    universe = set(gsc) | smap
    universe = {u for u in universe if not JUNK.search(u)}
    homepage = _canon(f"https://{domain}/")  # never a TARGET (it's a hub/source)

    recent_src = _recent_ledger_sources(a.ledger, LEDGER_WINDOW_DAYS)
    small = len(universe) < SMALL_SITE

    # ---- target candidates ----
    page2, highimp, zero = [], [], []
    for u in universe:
        if u == homepage:        # homepage is a source/hub, not a boost target
            continue
        g = gsc.get(u)
        if not g:
            zero.append({"url": u, **{k: None for k in ("clicks", "impressions", "ctr", "position")},
                         "bucket": "zero-traffic"})
            continue
        if PAGE2_LO <= g["position"] <= PAGE2_HI:
            page2.append({"url": u, **g, "bucket": "page-2"})
        elif g["impressions"] >= IMPR_MIN and g["clicks"] <= CLICK_MAX:
            highimp.append({"url": u, **g, "bucket": "high-impr-low-click"})
    page2.sort(key=lambda x: -(x["impressions"] or 0))
    highimp.sort(key=lambda x: -(x["impressions"] or 0))
    target_pool = page2 + highimp + zero  # priority order

    # attach the FREE GSC keyword profile (top queries) to each target candidate —
    # this IS the matcher's profile data; no per-target ahrefs call needed
    for t in target_pool:
        qs = profiles.get(t["url"], [])
        t["top_queries"] = [x["q"] for x in qs[:8]]

    targets = target_pool[: max(a.max_targets * 2, 40)]  # compact pool for the agent

    # OPTIONAL: URL Inspection enrichment on the shortlist (rate-limited, slow).
    # Flags unindexed / under-linked pages — the highest-value IL targets — and
    # re-ranks them to the front (a 'not indexed' page that internal links can
    # push into the index beats a merely-page-2 page).
    if a.inspect and site_url:
        insp = gsc_inspect([t["url"] for t in targets], site_url, tok)
        for t in targets:
            i = insp.get(t["url"])
            if i:
                t["coverage"] = i["coverage"]
                t["referring_urls_count"] = i["referring_urls_count"]
                t["indexed"] = i["indexed"]
        def _prio(t):
            cov = (t.get("coverage") or "").lower()
            not_indexed = "not indexed" in cov            # highest priority
            ref = t.get("referring_urls_count")
            under_linked = ref is not None and ref <= 3   # next priority
            return (0 if not_indexed else (1 if under_linked else 2),
                    -(t["impressions"] or 0))
        targets.sort(key=_prio)

    chosen_target_urls = {t["url"] for t in targets[: a.max_targets]}

    # ---- source candidates ----
    if a.sources:
        # No-GSC-access path: the caller supplies the source set directly.
        # Still apply the script's own filters — same domain, not a chosen
        # target — but skip the GSC ranking/exclusion logic below (there's
        # no click/impression data to rank by).
        src = [{"url": u, **{k: None for k in ("clicks", "impressions", "ctr", "position")}}
               for u in _load_sources_file(a.sources, domain) if u not in chosen_target_urls]
    else:
        # A source must be a real content page with body prose to host links — NOT
        # the homepage or a section/index listing (those are hubs: little prose, mostly
        # nav, yield 0-1 body links and waste a slot). Exclude them from sources too.
        src = []
        for u in universe:
            if u in chosen_target_urls:
                continue
            if u == homepage or INDEXLIKE.search(u):  # homepage + listing/index pages
                continue
            g = gsc.get(u)
            if not g:
                continue
            if not small and u in recent_src:
                continue
            src.append({"url": u, **g})
        src.sort(key=lambda x: (-(x["clicks"] or 0), -(x["impressions"] or 0)))
    sources = src[: max(a.max_sources * 2, 50)]

    result = {
        "domain": domain,
        "stats": {"gsc_pages": len(gsc), "sitemap_pages": len(smap),
                  "universe": len(universe), "small_site": small,
                  "recent_excluded_sources": len(recent_src),
                  "gsc_access": bool(gsc), "profiles": len(profiles)},
        "targets": {"max": a.max_targets, "candidates": targets},
        "sources": {"max": a.max_sources, "candidates": sources},
        # full per-page query profiles (matcher reads these instead of ahrefs)
        "profiles": {u: profiles[u] for u in
                     ({t["url"] for t in targets} | {x["url"] for x in sources})
                     if u in profiles},
    }
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        json.dump(result, open(a.json, "w"), ensure_ascii=False, indent=1)

    # compact stdout
    s = result["stats"]
    print(f"# il-candidates {domain}")
    print(f"# universe={s['universe']} (gsc={s['gsc_pages']} sitemap={s['sitemap_pages']}) "
          f"gsc_access={s['gsc_access']} profiles={s['profiles']} "
          f"small_site={s['small_site']} excluded_recent_sources={s['recent_excluded_sources']}")
    cov_hdr = " | coverage | reflinks" if a.inspect else ""
    print(f"\n## TARGET candidates (pick up to {a.max_targets}) — url | bucket | pos | impr | clk{cov_hdr} | top_queries")
    for t in targets:
        tq = ", ".join(t.get("top_queries", [])[:4])
        cov = (f"\t{t.get('coverage','?')}\t{t.get('referring_urls_count','?')}"
               if a.inspect else "")
        print(f"{t['url']}\t{t['bucket']}\t{t['position']}\t{t['impressions']}\t{t['clicks']}{cov}\t{tq}")
    print(f"\n## SOURCE candidates (pick up to {a.max_sources}) — url | clk | impr | pos")
    for x in sources:
        print(f"{x['url']}\t{x['clicks']}\t{x['impressions']}\t{x['position']}")


if __name__ == "__main__":
    main()
