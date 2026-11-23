#!/usr/bin/env sh
# Copy the reel2rules Claude Code skills into ~/.claude/skills (or <project>/.claude/skills if a path is given).
set -e
src="$(cd "$(dirname "$0")/../skills" && pwd)"
dst="${1:+$1/.claude/skills}"; dst="${dst:-$HOME/.claude/skills}"
mkdir -p "$dst"
for s in strategy-extract strategy-test; do
  if [ -e "$dst/$s" ]; then echo "skip $s (already exists in $dst - remove it first to update)"; continue; fi
  cp -R "$src/$s" "$dst/$s" && echo "installed $s -> $dst"
done
