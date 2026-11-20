# Changelog

## 2.1.0 — 2026-11-20

- **`btl`**: one user-facing command (`start`, `status`, `stop`, `resume`, `review`, `build`, `terms`, `config`, `log`, `jobs`, `doctor`, `next`, `import`) with short, human-readable output and a job registry.
- The skill is a command router: talk to the agent or type `/book-translate-lite translate <book> <lang>`.
- Installable as a plugin: Claude Code (`.claude-plugin/`) and Codex (`.codex-plugin/`, `.agents/plugins/`) marketplaces.
- Repository layout: the skill lives in `skills/book-translate-lite/` (scripts and templates inside it). `install.sh` also puts `btl` on the PATH.

## 2.0.0 — 2026-11-20

- Everything in English: scripts, messages, prompts, docs.
- The target language is chosen by the user (`init.py --to <code>`, `--from` for the source language).
- Language profiles: `templates/languages.json` and `templates/rules/<code>.md` (it, fr, es, de, en; typography for pt, nl, pl, ja, zh, ko); generic rules for any other language.
- English file and key names: `project.json`, `terms.json` (type fixed/proposed), `state.json`, `rules.md`, `candidates.json`, `review/`, `_tasks/`, `book/`.
- Renamed scripts: `step.py` (was passo.py), `review.py` (revisione.py), `migrate.py` (migra.py); `auto.py` flags in English (`--background`, `--status`, `--engine`, `--review-engine`, `--until`).
- `migrate.py` converts v1 projects (Italian names) to v2; markers `@@PARTE/@@VECCHIO/@@NUOVO/@@FINE` are still accepted.

## 1.0.0 — 2026-11-20

- Automatic mode `auto.py` (script orchestrator, `codex exec` / `claude -p` / any command), in-chat mode, final review with targeted fixes, pandoc/Calibre build, translate-book migration, end-to-end tests.
