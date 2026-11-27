# Changelog

## 2.3.1 — 2026-11-27

- **EPUB emphasis kept:** bold and italics that an EPUB sets only through CSS classes or `style=""` (system messages, chats, thoughts, titles of works…) used to vanish, because pandoc ignores CSS. The conversion now first writes a copy of the EPUB where those elements get real `<strong>`/`<em>` (headings untouched, container styles passed down to their paragraphs, no nested emphasis). On a real 317-part novel: 0 → 3,041 paragraphs with emphasis, matching a manual reconstruction.
- Test `test_css_emphasis`.

## 2.3.0 — 2026-11-21

Lessons from a long series translation; everything is generic and applies to any kind of book.

- **Genres:** `rules.md` is now the language rules (genre-neutral: no more assumptions about past-tense narration, spells or swearing) plus a genre section from `templates/genres/`: `fiction` (default), `nonfiction`, `technical`, `children`, `poetry`, `gamelit`, `general`. Choose with `btl start … --genre` or `btl genre GENRE`; it is carried over by `--series`.
- **Series:** `btl start … --series PREV_JOB` carries the previous volume's glossary, `rules.md` and house-style settings into the new job and creates it next to the previous one. Without `--series`, `btl start` warns when another job by the same author exists and does not start on its own.
- **`btl series JOB --from PREV [--retro]`** for a job already under way: merges glossary, rules and style; `--retro` rewrites the renderings that differed in the parts already translated (paragraph by paragraph, only where the source paragraph has the term).
- **`btl terms add … --retro`** rewrites a changed rendering in the parts already translated.
- **`--workdir DIR`** (`btl start`, `init.py`): choose where `<book>_temp` is created; jobs are also found by their source book when they live elsewhere.
- **Engine blocked:** out of credits, usage limits and login errors stop the run at once (no retries, no half-finished review followed by a build) with a hint: other engine or in-chat mode.
- **Fewer false flags:** parts or paragraphs with only links/images or only the author's name are no longer "not translated"; a term inside a proper name kept as in the source (“Moon” in “Blue Moon Tavern”, “Prejudice” in “Pride and Prejudice”) is not "left untranslated"; renderings are matched with inflection (Maestro/Maestra); single lowercase common words are not checked for consistency. On a real 313-part book: parts with problems 72 → 4, final report flags 113 → 58, inconsistent terms 31 → 9.
- `btl config` accepts the job as its first argument (`btl config JOB key=value`).
- A review that stops (engine blocked, no progress) no longer goes on to build and mark the job FINISHED.
- Tests `test_series`, `test_genres`, `test_checks_and_blocked_engine`.

## 2.2.0 — 2026-11-20

- **Title page:** new `subtitle` and `rights` settings in `project.json` (`btl config subtitle="…" rights="…"`); `btl config` also shows `toc_title`.
- **Cover:** if there is no `images/cover.*`, the build extracts the cover from the original EPUB (also for imported projects).
- **Scene breaks:** an ornament image followed by its text fallback (`* * *`) is shown once — the image in EPUB/PDF, the text in DOCX, where SVG ornaments would be lost.
- Test `test_build_extras`.

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
