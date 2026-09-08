#!/usr/bin/env python3
# verify.py — deterministic validity gate for the internal-linking skill,
# defined in ../SKILL.md.
#
# Expects on PATH: python3 3.9+, stdlib only.
# Env vars read: none.
# Example invocation:
#   python3 verify.py --extract extract/example-post.json \
#       --proposals proposals/example-post.json --targets targets.json \
#       --ledger ledger.json --counts counts.json > verify/example-post.json
"""Deterministic VALIDITY gate for internal-linking proposals (pure facts, no LLM).

For ONE source, check each proposed (anchor, target) against:
 - target in the provided target list
 - anchor appears VERBATIM in the source body text (outside links/headings — body_text already is)
 - anchor not already used as a link on the source
 - source does not already link to that target
 - global uniqueness: an anchor string maps to exactly ONE target across the whole campaign (ledger)
 - a source links a given target at most once; <= 3 links per source

Stdlib only — runs with any python3.

Usage:
  python3 verify.py --extract SRC.json --proposals PROP.json --targets TARG.json [--ledger LEDGER.json]
    PROP.json : [{"anchor": "...", "target": "https://...", "sentence": "...", "target_topic": "..."}]
    TARG.json : ["https://target1", "https://target2", ...]
    LEDGER.json (read + rewritten): {"anchor_lc": "target_url"}  one target per anchor, campaign-wide
Output (stdout): {"accepted":[...], "rejected":[{...,"reason":...}], "summary":{...}}
"""
import sys, json, argparse, re
from pathlib import Path


def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


_TRACKING = ("utm_", "fbclid", "gclid", "mc_cid", "mc_eid", "ref")


def norm_url(u):
    """Canonicalize for comparison: scheme/www/case/trailing-slash/fragment/
    tracking-params insensitive. Raw string equality broke 'already links this
    target' on sites mixing http(s), www, and trailing slashes."""
    from urllib.parse import urlparse, parse_qsl, urlencode
    u = (u or "").strip()
    p = urlparse(u)
    host = p.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    path = p.path.rstrip("/") or "/"
    q = [(k, v) for k, v in parse_qsl(p.query)
         if not any(k.lower().startswith(t) for t in _TRACKING)]
    return host + path + (("?" + urlencode(sorted(q))) if q else "")


def _load_proposals(path):
    """Accept either a flat array of proposals or a nested wrapper.

    The matching subagent writes a flat array `[{anchor,target,...}]`, but the
    orchestrator sometimes batches several sources into one object before calling this gate.
    Tolerate both so the agent never has to hand-flatten:
      - [ {...}, {...} ]                                  -> as-is
      - {"proposals":[...]} / {"links":[...]}            -> inner list
      - {"src-slug": [ {...} ], "other-slug": [ {...} ]} -> concat all values
    """
    data = json.load(open(path))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for k in ("proposals", "links", "accepted"):
            v = data.get(k)
            if isinstance(v, list):
                return v
        # source-keyed dict of lists -> flatten
        flat = []
        for v in data.values():
            if isinstance(v, list):
                flat.extend(x for x in v if isinstance(x, dict))
            elif isinstance(v, dict) and ("anchor" in v or "target" in v):
                flat.append(v)
        if flat:
            return flat
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extract", required=True)
    ap.add_argument("--proposals", required=True)
    ap.add_argument("--targets", required=True)
    ap.add_argument("--ledger")
    ap.add_argument("--max-anchor-reuse", type=int, default=2,
                    help="max times one anchor TEXT may be used campaign-wide (anchor-portfolio health; 0=unlimited)")
    ap.add_argument("--max-per-target", type=int, default=8,
                    help="max links any single TARGET may receive campaign-wide (distribution balance; 0=unlimited)")
    ap.add_argument("--counts",
                    help="campaign-wide tally file {anchors:{a:n}, targets:{t:n}} — read+rewritten across sources to enforce the two caps above")
    a = ap.parse_args()

    ex = json.load(open(a.extract))
    props = _load_proposals(a.proposals)
    _t = json.load(open(a.targets))
    # Harden: targets.json may be bare strings, dicts with a "url" key (the
    # selector writes {url,bucket,vol,kd,...}), or a {"targets":[...]} wrapper.
    # Normalize to a flat list of URL strings so every downstream use is safe.
    if isinstance(_t, dict):
        _t = _t.get("targets", list(_t.values()))
    targets = []
    for x in (_t or []):
        if isinstance(x, str):
            targets.append(x)
        elif isinstance(x, dict):
            u = x.get("url") or x.get("target") or x.get("href")
            if u:
                targets.append(u)
    ledger = {}
    if a.ledger:
        try:
            ledger = json.load(open(a.ledger))
        except Exception:
            ledger = {}
    # campaign-wide tallies for the two caps (separate file, backward-compatible)
    counts = {"anchors": {}, "targets": {}}
    if a.counts:
        try:
            loaded = json.load(open(a.counts))
            counts["anchors"] = loaded.get("anchors", {})
            counts["targets"] = loaded.get("targets", {})
        except Exception:
            pass
    anchor_ct, target_ct = counts["anchors"], counts["targets"]

    body = ex.get("body_text", "") or ""
    body_lc = norm(body)
    used_anchors = {norm(x) for x in ex.get("existing_internal_anchors", [])}
    existing_targets = {norm_url(l.get("href")) for l in ex.get("existing_links", []) if l.get("internal")}
    target_norm2raw = {norm_url(t): t for t in targets}

    source_url = ex.get("url", "")
    # every existing BODY link's anchor text (internal AND external) — a new
    # anchor may not overlap one, or the human implementer would have to nest
    # or split <a> tags
    existing_anchor_texts = {norm(l.get("anchor")) for l in ex.get("existing_links", [])
                             if l.get("anchor") and len(norm(l["anchor"])) > 3}
    # positional linked spans (newer extracts): exact [start,end) of linked
    # text inside body_text — enables occurrence-level already-linked checks
    linked_spans = ex.get("linked_spans")

    def _free_occurrence(a_lc):
        """First index where a_lc occurs in body OUTSIDE every linked span;
        -1 if all occurrences are inside links, -2 if no occurrence at all."""
        found = False
        start = 0
        while True:
            i = body_lc.find(a_lc, start)
            if i < 0:
                return -1 if found else -2
            found = True
            j = i + len(a_lc)
            if not any(s < j and i < e for s, e in linked_spans):
                return i
            start = i + 1

    accepted, rejected, this_source_targets = [], [], set()
    for p in props:
        anchor = (p.get("anchor") or "").strip()
        target = (p.get("target") or "").strip()
        a_lc = norm(anchor)

        def rej(reason):
            rejected.append({**p, "source": p.get("source") or source_url, "reason": reason})

        if not anchor or not target:
            rej("missing anchor or target"); continue
        t_norm = norm_url(target)
        if t_norm not in target_norm2raw:
            rej("target not in provided target list"); continue
        target = target_norm2raw[t_norm]  # canonical form from the target list
        p = {**p, "target": target}
        if a_lc not in body_lc:
            rej("anchor not verbatim in source body text"); continue
        anchor_idx = None
        if isinstance(linked_spans, list):
            # positional check: the anchor must occur somewhere OUTSIDE all
            # existing links — a string linked in one sentence may still be
            # placed at its free occurrence in another.
            i = _free_occurrence(a_lc)
            if i < 0:
                rej("every occurrence of anchor is inside an existing link"); continue
            anchor_idx = i
        else:
            # legacy extracts without spans: conservative string checks
            if a_lc in used_anchors:
                rej("anchor already used as a link on the source"); continue
            overlap = next((t for t in existing_anchor_texts
                            if t and (t in a_lc or a_lc in t)), None)
            if overlap:
                rej("anchor overlaps existing link text (%r)" % overlap); continue
        if t_norm in existing_targets:
            rej("source already links to this target"); continue
        if a_lc in ledger and norm_url(ledger[a_lc]) != t_norm:
            rej("anchor already mapped to a different target campaign-wide (%s)" % ledger[a_lc]); continue
        if t_norm in this_source_targets:
            rej("source already links this target in this batch"); continue
        if len(accepted) >= 3:
            rej("source already has 3 accepted links"); continue
        # campaign-wide anchor-portfolio cap: don't over-use one anchor TEXT
        if a.max_anchor_reuse and anchor_ct.get(a_lc, 0) >= a.max_anchor_reuse:
            rej("anchor used %d× campaign-wide (cap %d) — diversify the anchor"
                % (anchor_ct.get(a_lc, 0), a.max_anchor_reuse)); continue
        # campaign-wide distribution cap: don't let one target hog the links
        if a.max_per_target and target_ct.get(t_norm, 0) >= a.max_per_target:
            rej("target already has %d links campaign-wide (cap %d) — spread to other targets"
                % (target_ct.get(t_norm, 0), a.max_per_target)); continue

        idx = anchor_idx if anchor_idx is not None else body_lc.find(a_lc)
        exact = body[idx:idx + len(anchor)] if idx >= 0 else anchor
        accepted.append({**p, "source": p.get("source") or source_url, "anchor_exact": exact})
        ledger[a_lc] = target
        anchor_ct[a_lc] = anchor_ct.get(a_lc, 0) + 1
        target_ct[t_norm] = target_ct.get(t_norm, 0) + 1
        this_source_targets.add(t_norm)
        used_anchors.add(a_lc)

    if a.ledger:
        Path(a.ledger).parent.mkdir(parents=True, exist_ok=True)
        json.dump(ledger, open(a.ledger, "w"))
    if a.counts:
        Path(a.counts).parent.mkdir(parents=True, exist_ok=True)
        json.dump({"anchors": anchor_ct, "targets": target_ct}, open(a.counts, "w"))
    print(json.dumps({
        "accepted": accepted,
        "rejected": rejected,
        "summary": {"accepted": len(accepted), "rejected": len(rejected)},
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
