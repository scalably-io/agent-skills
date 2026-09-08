#!/usr/bin/env python3
# loop_controller.py: deterministic re-match loop driver for the
# internal-linking skill, defined in ../SKILL.md. Optional deep-mode step;
# most runs never call this (see SKILL.md Procedure step 8).
#
# Expects on PATH: python3 3.9+, stdlib only.
# Env vars read: none.
# Example invocation:
#   python3 loop_controller.py --run-dir . --target-per-source 3 --max-rounds 2
"""Deterministic QA-feedback loop driver for internal-linking.

The model is BAD at managing a stateful multi-round loop in its head; this script
owns the loop bookkeeping so the model only does the part it's good at (matching).

Reads, for the current run dir:
  verify/<src>.json  -> {accepted:[...], rejected:[{...,reason}]}
  qa/<src>.json      -> {"results":[{source,anchor,target,verdict,reason}], ...}
  targets.json       -> [{url,...}] or [url,...]
  proposals/<src>.json (to know what was tried)
  .loop-state.json   -> {rounds:{src:N}}  (this script maintains it)

Emits (stdout JSON) a WORKLIST telling the orchestrator exactly what to re-match:
  { "rematch": [ {source, slug, current_pass_count, need, exclude_anchors:[...],
                  open_targets:[...], qa_fail_reasons:[...] } ],
    "settled": [slug,...],            # sources done (3 links, or maxed out, or no gain)
    "round_summary": "...human line..." }

Flags:
  --run-dir .            run directory (has verify/ qa/ proposals/ targets.json)
  --target-per-source 3  desired links/source
  --max-rounds 2         stop a source after this many re-match rounds
  --mark-progress        after reading, bump each non-settled source's round counter
                         (call with this once per round, AFTER the model has re-matched)
Exit 0 always; orchestrator decides from the JSON. If "rematch" is empty -> loop done.
"""
import argparse, json, os, glob, sys
from pathlib import Path

def load(p, default=None):
    try:
        return json.load(open(p))
    except Exception:
        return default

def slug_of(path):
    return os.path.basename(path)[:-5]

def target_slugs(targets):
    out = []
    for t in (targets or []):
        u = t["url"] if isinstance(t, dict) else t
        out.append(u.rstrip("/").split("/")[-1])
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", default=".")
    ap.add_argument("--target-per-source", type=int, default=3)
    ap.add_argument("--max-rounds", type=int, default=2)
    ap.add_argument("--mark-progress", action="store_true")
    a = ap.parse_args()
    R = a.run_dir.rstrip("/") + "/"

    targets = load(R + "targets.json", [])
    all_target_slugs = target_slugs(targets)
    state = load(R + ".loop-state.json", {"rounds": {}})
    rounds = state.get("rounds", {})

    rematch, settled = [], []
    # iterate over every source that has a proposals file (the worklist universe)
    for pf in sorted(glob.glob(R + "proposals/*.json")):
        slug = slug_of(pf)
        vr = load(R + "verify/" + slug + ".json", {})
        qa = load(R + "qa/" + slug + ".json", {})
        accepted = vr.get("accepted", []) if isinstance(vr, dict) else []
        rejected = vr.get("rejected", []) if isinstance(vr, dict) else []
        qa_rows = (qa.get("verdicts") or qa.get("results") or []) if isinstance(qa, dict) else (qa if isinstance(qa, list) else [])

        qa_pass = [r for r in qa_rows if str(r.get("verdict", "")).lower() == "pass"]
        qa_fail = [r for r in qa_rows if str(r.get("verdict", "")).lower() == "fail"]
        # a "good" link = verify-accepted AND qa-pass (the final-merge criterion)
        pass_keys = {(r.get("anchor"), r.get("target")) for r in qa_pass}
        good = [x for x in accepted if (x.get("anchor"), x.get("target")) in pass_keys] if qa_rows else accepted
        good_n = len(good)

        rnd = rounds.get(slug, 0)
        need = a.target_per_source - good_n

        # SETTLED if: enough links, OR rounds exhausted, OR no open targets left to try
        used_targets = {x.get("target", "").rstrip("/").split("/")[-1] for x in good}
        open_targets = [s for s in all_target_slugs if s not in used_targets]
        if need <= 0 or rnd >= a.max_rounds or not open_targets:
            settled.append(slug)
            continue

        # anchors already used for this source (don't repropose): good + everything tried
        exclude = sorted({x.get("anchor") for x in good if x.get("anchor")}
                         | {p.get("anchor") for p in (load(pf, []) or []) if isinstance(p, dict) and p.get("anchor")})
        fail_reasons = [f"'{r.get('anchor')}'→{(r.get('target') or '').split('/')[-1]}: {r.get('reason','')}"
                        for r in qa_fail]
        # Pre-build the EXACT Task prompt the orchestrator copies verbatim; model does zero composition.
        tp = (
            f"Re-match internal links for source `{slug}` (round {rnd+1}/{a.max_rounds}). "
            f"This source currently has {good_n} good link(s); find {need} MORE.\n"
            f"Read its extract at extract/{slug}.json and profiles.json. Do the mandatory per-target TALLY, "
            f"but FOCUS on these still-open targets (the source has no good link to them yet): {', '.join(open_targets)}.\n"
            f"Do NOT repropose these already-used anchors: {', '.join(exclude) if exclude else '(none)'}.\n"
            + (f"Last round these failed QA: learn from the reasons, pick BETTER anchors: {' | '.join(fail_reasons)}.\n" if fail_reasons else "")
            + f"APPEND your new proposals to the existing array in proposals/{slug}.json (keep prior entries). "
              f"Only verbatim anchors whose sentence is genuinely about the target; quality over hitting the number."
        )
        rematch.append({
            "source": slug, "slug": slug,
            "current_good_links": good_n, "need": need,
            "round": rnd + 1, "max_rounds": a.max_rounds,
            "open_targets": open_targets,
            "exclude_anchors": exclude,
            "qa_fail_reasons": fail_reasons,
            "task_prompt": tp,
        })

    if a.mark_progress:
        for w in rematch:
            rounds[w["slug"]] = rounds.get(w["slug"], 0) + 1
        state["rounds"] = rounds
        Path(R + ".loop-state.json").parent.mkdir(parents=True, exist_ok=True)
        json.dump(state, open(R + ".loop-state.json", "w"))

    n_re = len(rematch)
    summary = (f"Loop: {len(settled)} sources settled, {n_re} need re-match"
               + (f" (rounds left vary, max {a.max_rounds})" if n_re else ". LOOP DONE, proceed to merge"))
    print(json.dumps({"rematch": rematch, "settled": settled, "round_summary": summary}, indent=1))

if __name__ == "__main__":
    main()
