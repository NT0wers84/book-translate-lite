#!/bin/sh
# Install book-translate-lite as a skill for Claude Code and Codex (symlinks).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
for base in "$HOME/.claude/skills" "$HOME/.codex/skills"; do
  mkdir -p "$base"
  if [ -e "$base/book-translate-lite" ] && [ ! -L "$base/book-translate-lite" ]; then
    echo "SKIPPED $base/book-translate-lite: exists and is not a symlink"; continue
  fi
  ln -sfn "$HERE" "$base/book-translate-lite"
  echo "ok  $base/book-translate-lite -> $HERE"
done
for c in python3 pandoc; do command -v $c >/dev/null || echo "WARNING: $c is missing"; done
command -v ebook-convert >/dev/null || [ -x /Applications/calibre.app/Contents/MacOS/ebook-convert ] || echo "WARNING: Calibre is missing (needed for EPUB/PDF input and PDF output)"
command -v codex >/dev/null || command -v claude >/dev/null || [ -x /Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex ] || [ -x /Applications/Codex.app/Contents/Resources/codex ] || echo "Note: no codex/claude CLI found: only the in-chat mode (step.py) is available"
