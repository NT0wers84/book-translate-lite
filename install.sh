#!/bin/sh
# Installa book-translate-lite come skill per Claude Code e Codex (link simbolici).
set -e
QUI="$(cd "$(dirname "$0")" && pwd)"
for base in "$HOME/.claude/skills" "$HOME/.codex/skills"; do
  mkdir -p "$base"
  if [ -e "$base/book-translate-lite" ] && [ ! -L "$base/book-translate-lite" ]; then
    echo "SALTATO $base/book-translate-lite: esiste già e non è un link"; continue
  fi
  ln -sfn "$QUI" "$base/book-translate-lite"
  echo "ok  $base/book-translate-lite -> $QUI"
done
for c in python3 pandoc; do command -v $c >/dev/null || echo "ATTENZIONE: manca $c"; done
command -v ebook-convert >/dev/null || [ -x /Applications/calibre.app/Contents/MacOS/ebook-convert ] || echo "ATTENZIONE: manca Calibre (serve per EPUB/PDF in ingresso e per il PDF in uscita)"
command -v codex >/dev/null || command -v claude >/dev/null || [ -x /Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex ] || [ -x /Applications/Codex.app/Contents/Resources/codex ] || echo "Nota: nessuna CLI codex/claude trovata: disponibile solo la modalità in chat (passo.py)"
