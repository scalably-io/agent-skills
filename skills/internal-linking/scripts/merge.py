#!/usr/bin/env python3
# merge.py — deterministic final-merge for the internal-linking skill,
# defined in ../SKILL.md.
#
# Expects on PATH: python3 3.9+, stdlib only.
# Env vars read: none.
# Example invocation:
#   python3 merge.py --verify-dir verify/ --qa-dir qa/ --out final-links.json
"""Deterministic final-merge for internal-linking campaigns (stdlib only).

Joins validity-gate survivors with QA verdicts on the FULL (source, anchor,
target) key and emits the final link list + a per-link audit trail. This step
replaces any ad-hoc merging by the orchestrator — two real production bugs
motivated it: a `[a-z]*` glob that silently dropped digit-prefixed source
slugs, and verdict matching on (anchor, target) without source that let one
batch's FAIL poison identical pairs from other sources.

Usage:
  python3 merge.py --verify-dir verify/ --qa-dir qa/ --out final-links.json

Inputs:
  verify/*.json — verify.py stdout saved per source: {"accepted":[...], "rejected":[...]}
                  (accepted rows carry source/anchor/anchor_exact/target/sentence)
  qa/*.json     — any layout; every file containing {"results":[...]} is read.
                  Verdict rows MUST carry source+anchor+target (quality-gate contract).

Rules:
  - a link is FINAL iff it is verify-accepted AND has a QA verdict 'pass'
  - verify-accepted with NO matching verdict -> counted 'unjudged' and EXCLUDED,
    listed loudly (the orchestrator must re-run QA for them — never silently drop)
  - verdicts that match nothing are listed as 'orphan verdicts' (key mismatch bug)
Exit code 1 if any unjudged links or orphan verdicts exist, so the pipeline
notices instead of shipping a silently-shrunk campaign.
"""
import sys, json, glob, os, argparse, re
from pathlib import Path
from urllib.parse import urlparse


def norm_url(u):
    u = (u or "").strip().rstrip("/").lower()
    p = urlparse(u)
    host = p.netloc[4:] if p.netloc.startswith("www.") else p.netloc
    return host + p.path


def norm_a(s):
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def key(row):
    return (norm_url(row.get("source")), norm_a(row.get("anchor")), norm_url(row.get("target")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-dir", required=True)
    ap.add_argument("--qa-dir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    accepted = {}
    for f in sorted(glob.glob(os.path.join(a.verify_dir, "*.json"))):
        d = json.load(open(f))
        for row in d.get("accepted", []):
            if not row.get("source"):
                # verify.py output is per-source; derive from filename slug if absent
                row["source"] = os.path.basename(f)[:-5]
            accepted[key(row)] = row

    verdicts = {}
    orphans = []
    for f in sorted(glob.glob(os.path.join(a.qa_dir, "*.json"))):
        try:
            d = json.load(open(f))
        except Exception:
            continue
        rows = d.get("results") if isinstance(d, dict) else None
        if not rows:
            continue
        for r in rows:
            k = key(r)
            if not all(k):
                orphans.append({"file": os.path.basename(f), "row": r,
                                "why": "missing source/anchor/target"})
                continue
            if k not in accepted:
                orphans.append({"file": os.path.basename(f), "row": r,
                                "why": "no matching verify-accepted link"})
                continue
            verdicts[k] = r

    final, qa_failed, unjudged = [], [], []
    for k, row in accepted.items():
        v = verdicts.get(k)
        if v is None:
            unjudged.append(row)
        elif str(v.get("verdict", "")).lower() == "pass":
            # Normalize the "why this link" field — the matching subagent emits it under
            # different names across runs (target_topic / reason / rationale).
            # Coalesce into a single stable `why` so the sheet column always fills.
            row["why"] = (row.get("target_topic") or row.get("reason")
                          or row.get("rationale") or "")
            final.append(row)
        else:
            qa_failed.append({**row, "qa_reason": v.get("reason", "")})

    # Anchor-portfolio flag: the same anchor TEXT reused many times
    # over-optimizes the anchor profile. We FLAG, never drop — the human decides
    # at insertion time. Count each anchor text across the final links and stamp
    # every link with how many times its anchor appears campaign-wide.
    anchor_freq = {}
    for r in final:
        anchor_freq[norm_a(r.get("anchor"))] = anchor_freq.get(norm_a(r.get("anchor")), 0) + 1
    for r in final:
        r["anchor_reuse_count"] = anchor_freq[norm_a(r.get("anchor"))]
    reused = sorted(({"anchor": r.get("anchor"), "count": r["anchor_reuse_count"]}
                     for r in final if r["anchor_reuse_count"] > 1),
                    key=lambda x: -x["count"])
    # de-dupe the reused list (one entry per anchor text)
    seen_a, reused_unique = set(), []
    for x in reused:
        if norm_a(x["anchor"]) not in seen_a:
            seen_a.add(norm_a(x["anchor"])); reused_unique.append(x)

    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(final, open(a.out, "w"), indent=1, ensure_ascii=False)
    audit = {
        "verify_accepted": len(accepted),
        "qa_pass": len(final),
        "qa_fail": len(qa_failed),
        "reused_anchors": reused_unique,  # anchor texts used >1x (over-optimization flag)
        "unjudged": [ {"source": r.get("source"), "anchor": r.get("anchor"),
                       "target": r.get("target")} for r in unjudged ],
        "orphan_verdicts": orphans,
        "qa_failed": [ {"source": r.get("source"), "anchor": r.get("anchor"),
                        "target": r.get("target"), "reason": r.get("qa_reason")}
                       for r in qa_failed ],
    }
    json.dump(audit, open(a.out + ".audit.json", "w"), indent=1, ensure_ascii=False)
    print(json.dumps({"final": len(final), "qa_fail": len(qa_failed),
                      "unjudged": len(unjudged), "orphan_verdicts": len(orphans),
                      "reused_anchors": len(reused_unique)}))
    if unjudged or orphans:
        sys.stderr.write(
            f"MERGE INCOMPLETE: {len(unjudged)} unjudged links, "
            f"{len(orphans)} orphan verdicts — see {a.out}.audit.json. "
            "Re-run QA for unjudged links; do NOT deliver without resolving.\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
