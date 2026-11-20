#!/bin/sh
# Manual install (alternative to the plugin marketplaces): links the skill into Claude Code and
# Codex and puts the `btl` command on your PATH (~/.local/bin).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
SKILL="$HERE/skills/book-translate-lite"
for base in "$HOME/.claude/skills" "$HOME/.codex/skills"; do
  mkdir -p "$base"
  if [ -e "$base/book-translate-lite" ] && [ ! -L "$base/book-translate-lite" ]; then
    echo "SKIPPED $base/book-translate-lite: exists and is not a symlink"; continue
  fi
  ln -sfn "$SKILL" "$base/book-translate-lite"
  echo "ok  skill   $base/book-translate-lite"
done
mkdir -p "$HOME/.local/bin"
chmod +x "$SKILL/scripts/"*.py
ln -sfn "$SKILL/scripts/btl.py" "$HOME/.local/bin/btl"
echo "ok  command $HOME/.local/bin/btl"
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) echo "Note: add ~/.local/bin to your PATH to type 'btl' directly (agents do not need it)";; esac
echo
python3 "$SKILL/scripts/btl.py" doctor
