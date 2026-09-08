#!/usr/bin/env bash
# check-memory.sh — mechanical validation of the memory-system contract
# (file layout, format, caps) defined in ../SKILL.md.
#
# Expects on PATH: bash 4+, and standard POSIX text tools (grep, sed, find, wc).
# Env vars read:
#   MEMORY_ROOT       - project root containing memory/ and rules/ (default: current directory)
#   MEMORY_CHECK_SCOPE - "full" (default) or "memory" — see the SCOPE comment below.
# Example invocation:
#   MEMORY_ROOT=. MEMORY_CHECK_SCOPE=full bash scripts/check-memory.sh
#
# Run from the project root; operates on MEMORY_ROOT (default: current directory).
# Prints "OK" when clean, "VIOLATION: ..." lines otherwise. Exit 1 on violations.
set -u

ROOT="${MEMORY_ROOT:-.}"
MEM="$ROOT/memory"
LC="$ROOT/rules/learned-corrections.md"
V=0

# Scope: which surfaces this run validates.
#   full   (default) — memory/ + rules/ + the workspace surfaces (projects/INDEX.md,
#                      root clutter). What the Sunday routine and a full fleet use.
#   memory           — memory/ + rules/ ONLY. For projects where projects/ is owned by
#                      a pipeline, not by the memory routines (e.g. a site-generator
#                      pipeline that owns its own article folders, so INDEX.md coverage
#                      is never the dream routine's job). Without this the nightly run
#                      drowns in out-of-scope violations and learns to classify every
#                      violation as "skip".
SCOPE="${MEMORY_CHECK_SCOPE:-full}"
case "$SCOPE" in
  full|memory) ;;
  *) echo "check-memory.sh: MEMORY_CHECK_SCOPE must be 'full' or 'memory' (got '$SCOPE')" >&2; exit 2 ;;
esac

viol() { echo "VIOLATION: $*"; V=1; }
warn() { echo "WARN: $*"; }

# ── Caps on the injected files ──────────────────────────────────────────────
cap_lines() { # file, cap, label
  local f="$1" cap="$2" label="$3"
  [ -f "$f" ] || return 0
  local n
  n=$(grep -cve '^[[:space:]]*$' "$f")
  [ "$n" -gt "$cap" ] && viol "$label has $n non-empty lines (cap $cap)"
}
cap_lines "$MEM/profile.md" 80 "profile.md"
cap_lines "$MEM/index.md" 50 "index.md"
cap_lines "$MEM/weekly-summary.md" 80 "weekly-summary.md"

# ── The injected files must EXIST ───────────────────────────────────────────
# Every check above is guarded by `[ -f ]`, so a project with no memory/ at all
# used to print OK and exit 0 — "this dream has no input" read as green (found
# in production: a project with no memory/ directory had silently been a
# nightly no-op for months before this check existed). Absence is a
# violation, not a pass. learned-corrections.md is deliberately NOT required:
# a project with no rules yet legitimately has no file.
for f in profile.md index.md weekly-summary.md; do
  [ -f "$MEM/$f" ] || viol "$f is missing — the dream has nothing to consolidate into"
done

# The daily logs are the nightly routine's INPUT. Projects fed by a daily-log
# task must have them; a project with no daily-log task at all (sourced from
# a content pipeline instead) runs SCOPE=memory and is not asked this question.
if [ "$SCOPE" = full ]; then
  if [ ! -d "$MEM/daily" ]; then
    viol "memory/daily/ is missing — the nightly routine has no input"
  elif [ -z "$(ls -A "$MEM/daily" 2>/dev/null)" ]; then
    viol "memory/daily/ is empty — no daily-log task is feeding this project"
  fi
fi

# ── weekly-summary: exactly one week header, one Open-items section ─────────
if [ -f "$MEM/weekly-summary.md" ]; then
  wk=$(grep -c '^# Week of ' "$MEM/weekly-summary.md")
  [ "$wk" -eq 0 ] && viol "weekly-summary.md has no '# Week of YYYY-MM-DD' header"
  [ "$wk" -gt 1 ] && viol "weekly-summary.md has $wk week headers (must be 1 — archive finished weeks)"
  oi=$(grep -ci '^#\+ *open items' "$MEM/weekly-summary.md")
  [ "$oi" -gt 1 ] && viol "weekly-summary.md has $oi 'Open items' sections (must be ≤1, replaced not stacked)"
fi

# ── Tree files: frontmatter completeness, size, index coverage ──────────────
TREE_DIRS="people projects clients reference pipeline"
tree_files=""
for d in $TREE_DIRS; do
  [ -d "$MEM/$d" ] || continue
  for f in "$MEM/$d"/*.md; do
    [ -f "$f" ] || continue
    tree_files="$tree_files $f"
    rel="${f#"$MEM/"}"
    head -1 "$f" | grep -q '^---$' || viol "$rel missing frontmatter"
    for field in title: type: summary: updated:; do
      sed -n '2,8p' "$f" | grep -q "^$field" || viol "$rel frontmatter missing '$field'"
    done
    s=$(sed -n '2,8p' "$f" | grep '^summary:' | head -1 | cut -c9-)
    [ -n "$s" ] && [ "${#s}" -gt 160 ] && viol "$rel summary is ${#s} chars (cap 160)"
    n=$(grep -cve '^[[:space:]]*$' "$f")
    [ "$n" -gt 150 ] && viol "$rel has $n lines (cap 150 — split it)"
    if [ -f "$MEM/index.md" ]; then
      grep -qF "$rel" "$MEM/index.md" || viol "$rel not listed in index.md"
    fi
  done
done

# index lines must point at existing files
if [ -f "$MEM/index.md" ]; then
  grep -oE '(people|projects|clients|reference|pipeline)/[A-Za-z0-9._-]+\.md' "$MEM/index.md" | sort -u | \
  while read -r rel; do
    [ -f "$MEM/$rel" ] || echo "VIOLATION: index.md lists missing file $rel"
  done | tee /tmp/.idx-viol.$$
  [ -s /tmp/.idx-viol.$$ ] && V=1
  rm -f /tmp/.idx-viol.$$
fi

# ── learned-corrections format ──────────────────────────────────────────────
if [ -f "$LC" ]; then
  grep -q '^## Pending' "$LC" || viol "learned-corrections.md missing '## Pending' section"
  grep -q '^## Rules' "$LC" || viol "learned-corrections.md missing '## Rules' section"
  nrules=$(sed -n '/^## Rules/,/^## /p' "$LC" | grep -c '^- ')
  [ "$nrules" -gt 60 ] && viol "learned-corrections.md has $nrules rules (cap 60 — consolidate)"
  # scaffolding blocks belong in the corrections log, not here
  for marker in '\*\*Source' '\*\*Promoted' '\*\*Occurrences'; do
    c=$(grep -cE "^$marker" "$LC")
    [ "$c" -gt 0 ] && viol "learned-corrections.md has $c '$(echo "$marker" | tr -d '\\')' blocks — provenance belongs in reference/corrections-log.md"
  done
  # verbatim duplicate rule lines
  dups=$(grep '^- ' "$LC" | sed 's/<!--.*-->//' | sed 's/[[:space:]]*$//' | sort | uniq -d | head -3)
  [ -n "$dups" ] && viol "learned-corrections.md has verbatim duplicate rules: $(echo "$dups" | head -1 | cut -c1-80)..."
  # rules without an lc: id
  noid=$(sed -n '/^## Rules/,/^## /p' "$LC" | grep '^- ' | grep -cv '<!-- *lc:')
  [ "$noid" -gt 0 ] && viol "learned-corrections.md: $noid rule(s) missing an <!-- lc:slug --> id"
  # New rules carry explicit evidence metadata. Legacy rules are warned for
  # manual provenance audit; they are never auto-upgraded by the dream.
  legacy=$(sed -n '/^## Rules/,/^## /p' "$LC" | grep '^- ' | grep '<!-- *lc:' | grep -cv 'evidence:' || true)
  [ "${legacy:-0}" -gt 0 ] && warn "learned-corrections.md: $legacy legacy rule(s) lack evidence metadata — audit; do not auto-upgrade"
  bad_evidence=$(sed -n '/^## Rules/,/^## /p' "$LC" | grep '^- ' | grep 'evidence:' | grep -cv 'evidence:user-explicit' || true)
  [ "${bad_evidence:-0}" -gt 0 ] && viol "learned-corrections.md: $bad_evidence rule(s) use non-explicit evidence metadata"
  # approval-by-silence phrases; add your team's own languages here
  if grep -Eqi 'continued (using|the workflow).*without complaint|accepted without objection|approved.*bez (zamerke|prigovora)|bez (zamerke|prigovora).*approved|approved.*no objections?|no objections?.*approved' "$LC"; then
    viol "learned-corrections.md contains approval-by-silence language"
  fi
  # size sanity
  b=$(wc -c < "$LC")
  [ "$b" -gt 12000 ] && viol "learned-corrections.md is ${b} bytes (target ≤ 12000 — compress or consolidate)"
fi

# ── Evidence hygiene on injected/current surfaces ──────────────────────────
# Phone-like IDs already exist in legacy memory, so report rather than break
# the nightly run. New prompts prohibit adding them; operators can clean the
# warnings with source review instead of a destructive fleet rewrite.
for f in "$MEM/profile.md" "$MEM/weekly-summary.md" "$LC"; do
  [ -f "$f" ] || continue
  if grep -Eqi '(whatsapp|phone|telefon|tel\.?)[^[:cntrl:]]*[1-9][0-9]{8,14}|[1-9][0-9]{8,14}@s\.whatsapp\.net' "$f"; then
    warn "${f#"$ROOT/"} contains a raw phone-like identifier — remove after provenance review"
  fi
  # approval-by-silence phrases; add your team's own languages here
  if grep -Eqi 'continued (using|the workflow).*without complaint|accepted without objection|approved.*bez (zamerke|prigovora)|bez (zamerke|prigovora).*approved|approved.*no objections?|no objections?.*approved' "$f"; then
    viol "${f#"$ROOT/"} contains approval-by-silence language"
  fi
done

CORR_LOG="$MEM/reference/corrections-log.md"
if [ -f "$CORR_LOG" ]; then
  evidence_count=$(grep -c '^\*\*Evidence:\*\* *user-explicit' "$CORR_LOG" 2>/dev/null || true)
  quote_count=$(grep -c '^\*\*Source quote:\*\*' "$CORR_LOG" 2>/dev/null || true)
  if [ "${evidence_count:-0}" -gt "${quote_count:-0}" ]; then
    viol "reference/corrections-log.md has explicit evidence without a matching source quote"
  fi
fi

# corrections-log must exist when LC has rules
# NB: `grep -c` prints "0" AND exits 1 on no match, so `|| echo 0` would
# produce "0\n0" and break the -gt comparison (hit on empty-rules projects).
# `|| true` keeps the printed count and swallows the exit code.
if [ -f "$LC" ] && [ ! -f "$MEM/reference/corrections-log.md" ]; then
  nrules=$(grep -c '^- ' "$LC" 2>/dev/null || true)
  [ "${nrules:-0}" -gt 0 ] && viol "reference/corrections-log.md missing while learned-corrections has rules"
fi

# ── Projects index (workspace surface — full scope only) ────────────────────
PJ="$ROOT/projects"
if [ "$SCOPE" = full ] && [ -d "$PJ" ]; then
  ndirs=$(find "$PJ" -maxdepth 1 -mindepth 1 -type d ! -name archive | wc -l)
  if [ "$ndirs" -ge 3 ] && [ ! -f "$PJ/INDEX.md" ]; then
    viol "projects/ has $ndirs project dirs but no INDEX.md — create the index"
  fi
  if [ -f "$PJ/INDEX.md" ]; then
    for d in "$PJ"/*/; do
      [ -d "$d" ] || continue
      b=$(basename "$d"); [ "$b" = "archive" ] && continue
      grep -q "$b" "$PJ/INDEX.md" || viol "projects/$b not listed in projects/INDEX.md"
    done
  fi
fi

# ── Workspace root clutter ──────────────────────────────────────────────────
# Exclusions = the live-state surface: pipeline state files and their
# .bak twins, sync logs/watermarks, lockfiles, dotfiles. Verified against a
# live cron-driven pipeline — these are written daily and must stay at root;
# counting them made the tidy threshold unreachable.
if [ "$SCOPE" = full ]; then
loose=$(find "$ROOT" -maxdepth 1 -type f \
  ! -name 'CLAUDE.md' ! -name '*.config.json' ! -name 'CLAUDE.md.local' \
  ! -name '*state*.json' ! -name '*state*.json.*' ! -name '*.state.*' \
  ! -name '*sync-log*' ! -name '*sync-watermark*' \
  ! -name '*.lock' ! -name '.*' \
  2>/dev/null | wc -l)
[ "$loose" -gt 12 ] && viol "workspace root has $loose loose files (threshold 12 — run the workspace tidy)"
fi

[ "$V" -eq 0 ] && echo "OK" && exit 0
exit 1
