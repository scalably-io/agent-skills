#!/usr/bin/env bash
# archive-week.sh — rotate the finished week out of weekly-summary.md, part
# of the memory-system contract defined in ../SKILL.md.
#
# Expects on PATH: bash 4+, coreutils date (GNU or BSD — both invocation
# forms are tried below).
# Env vars read:
#   MEMORY_ROOT - project root containing memory/ (default: current directory)
# Example invocation:
#   MEMORY_ROOT=. bash scripts/archive-week.sh
#
# Moves current content to ./memory/weekly-archive/<year>-W<nn>.md and writes
# a fresh header for the new week. Intended to be run by the Sunday routine
# AFTER the week's content is final. Refuses to run twice on the same week.
set -eu

ROOT="${MEMORY_ROOT:-.}"
WS="$ROOT/memory/weekly-summary.md"
ARCH="$ROOT/memory/weekly-archive"

[ -f "$WS" ] || { echo "no weekly-summary.md — nothing to archive"; exit 0; }
mkdir -p "$ARCH"

# ISO year/week of the week being archived (the week containing yesterday,
# so a Sunday-night or Monday-early run archives the week that just ended).
Y=$(date -d yesterday +%G 2>/dev/null || date -v-1d +%G)
W=$(date -d yesterday +%V 2>/dev/null || date -v-1d +%V)
DEST="$ARCH/$Y-W$W.md"

if [ -f "$DEST" ]; then
  echo "refusing: $DEST already exists (week already archived)"
  exit 1
fi

cp "$WS" "$DEST"

# Fresh file for the new week, headed by this week's Monday.
MON=$(date -d 'monday this week' +%F 2>/dev/null || date -v-mon +%F)
cat > "$WS" <<EOF
# Week of $MON

## Open items
(carry forward from $Y-W$W if still open)
EOF

echo "archived -> $DEST; weekly-summary.md reset for week of $MON"
