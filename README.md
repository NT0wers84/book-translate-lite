# book-translate-lite

An agent skill for **Claude Code** and **Codex** that translates a whole book (EPUB, PDF, DOCX or Markdown) **into any language, from start to finish**. It runs a **final review pass** and produces a ready EPUB, DOCX and PDF. It is designed to use as few tokens as possible.

```
book.epub ─ init ─▶ parts ─▶ translation in groups ─▶ checks ─▶ review ─▶ EPUB · DOCX · PDF
                             (engine, in parallel)    (scripts)  (engine)    + FINAL_REPORT.md
```

## Why

With typical translation skills, most of the cost comes from the **orchestrator**: a long conversation that resends hundreds of thousands of tokens on every call. This skill avoids that in three ways:

1. **The orchestrator is a script** (`auto.py`). Each group of 3 parts is *one* non-interactive model call (`codex exec` or `claude -p`) with a self-contained task. The model needs no tools: it answers with the translated blocks, and the script saves and checks them.
2. **Minimal tasks.** Each task contains only:
   - the rules;
   - the glossary terms that occur in those parts;
   - recurring names that have no translation yet;
   - the end of the previous part, for continuity.
3. **Scripts, not the model, do the checks and mechanical fixes.**
   - Checks: paragraphs, Markdown, terms and forbidden forms.
   - Fixes: apostrophes, quote punctuation, `...` → `…` and per-project replacements.

Without a CLI, the **in-chat mode** (`step.py`) uses the app's sub-agents. The orchestrator only runs one command that tells it what to do next.

## Install

```bash
git clone https://github.com/NT0wers84/book-translate-lite.git
cd book-translate-lite && ./install.sh
```

`install.sh` symlinks the skill into `~/.claude/skills/` and `~/.codex/skills/`.

Requirements:

- Python 3.9+, [pandoc](https://pandoc.org) 3.x and [Calibre](https://calibre-ebook.com) (conversion and PDF);
- for the automatic mode, the [Codex](https://github.com/openai/codex) or [Claude Code](https://docs.anthropic.com/claude-code) CLI.

## Quick start

```bash
S=~/.claude/skills/book-translate-lite/scripts
python3 $S/init.py "My Book.epub" --to fr          # target language: any code (it, fr, de, es, ja, …)
cd "My Book_temp"
# optional: translated title in project.json, fixed names in terms.json, style notes in rules.md
python3 $S/auto.py --background                     # runs on its own until the book is done
python3 $S/auto.py --status                         # progress
```

The result goes to `book/<title>.epub|docx|pdf`, and the summary to `review/FINAL_REPORT.md`.

### Prompt for an agent (Codex or Claude)

> Use the book-translate-lite skill to translate `<path>/book.epub` into French. Set up the project with `init.py`, set the translated title, then start the automatic mode in the background and tell me how to follow it. If no CLI is available, use the in-chat mode and keep going until "FINISHED".

To resume a job:

> Use the book-translate-lite skill in `<path>/<book>_temp` and take the translation to the end.

## Languages

`--to` accepts any language code: the model translates into it.

Some languages have a **profile**:

- typography in `templates/languages.json`;
- publishing conventions in `templates/rules/<code>.md`.

| profile | language | quotes | extra |
|---|---|---|---|
| `it` | Italian | «» | full stop and comma outside quotes, `Okay`→`Ok`, `...`→`…`, *passato remoto* |
| `fr` | French | «» | non-breaking spaces, *passé simple*, `...`→`…` |
| `es` | Spanish | «» | dialogue with raya, ¿ ¡, `...`→`…` |
| `de` | German | „“ | Präteritum, consistent du/Sie, `...`→`…` |
| `en` | English | “” | US spelling unless told otherwise |
| `pt` `nl` `pl` `ja` `zh` `ko` | — | profile typography | generic rules |

Any other code uses the generic rules. To add or improve a language, see [docs/LANGUAGES.md](docs/LANGUAGES.md). Pull requests are welcome.

## Phases

| phase | what happens | files |
|---|---|---|
| setup | Calibre conversion to Markdown split into parts of about 6,000 characters; recurring names collected | `chunkNNNN.md`, `project.json`, `rules.md`, `terms.json`, `candidates.json` |
| translation | groups of `group_size` parts, `parallel` at a time. Each answer is checked; rejected parts are retranslated with the list of errors up to `retries` times, then accepted and flagged | `output_chunkNNNN.md`, `.meta.json`, `state.json`, `auto.log` |
| glossary | after each group, new terms proposed by the model are added as **proposed**. A conflict on a proposed term changes it; a conflict on a **fixed** term is only recorded | `terms.json`, `state.json → fixed_conflicts` |
| analysis | whole-book scan: structure errors, terms rendered differently across parts, sentences left in the source language, quotes, doubled words | `review/flags.json`, `review/report.md` |
| review | the review engine (which can differ, for example Claude) re-reads source and translation and answers with targeted `@@OLD@@/@@NEW@@` fixes. A fix that is not found or breaks the check is rejected | `review/changes.md`, `review/backup/` |
| book | EPUB and DOCX with pandoc, PDF with Calibre: correct `lang`, full table of contents, box for system messages | `book/` |
| report | what is left to check by hand, and the proposed changes to fixed terms | `review/FINAL_REPORT.md` |

`review` in `project.json` controls how much is reviewed: `full` (default), `flagged` (only parts with problems) or `none`.

## Configuration: `project.json`

| key | default | meaning |
|---|---|---|
| `target_lang`, `target_lang_name`, `source_lang` | from `init.py` | languages |
| `title`, `author` | from the book | metadata of the final book |
| `group_size`, `parallel` | 3, 3 | parts per call, calls in parallel |
| `retries` | 2 | retranslations of a rejected part |
| `engine`, `model`, `reasoning` | `codex`, —, `low` | translation engine |
| `review_engine`, `review_model`, `review_reasoning` | same as translation, —, `medium` | review engine |
| `engine_command` | — | with `engine: "command"`: any command that reads the task on stdin and prints the answer |
| `review`, `review_group_size` | `full`, 3 | review scope |
| `quotes`, `typographic_apostrophe`, `punct_outside_quotes` | from the language profile | automatic typography |
| `replacements` | from the profile | `[{"re", "with"}]` applied on every save |
| `forbidden` | — | `[{"re", "msg"}]` forms that block a part |
| `uppercase_chat` | — | names whose `Name: …` lines must be ALL CAPS |
| `ratio_min`, `ratio_max` | 0.6 / 1.9 | paragraph length bounds (translation/source) |
| `formats`, `timeout_minutes` | `epub,docx,pdf`, 20 | |

## Commands

| script | use |
|---|---|
| `init.py book --to <code> [--from <code>] [--chunk-size 6000]` | creates `<book>_temp/` next to the book |
| `auto.py [--background] [--status] [--engine …] [--until N] [--review …]` | automatic mode, resumable |
| `step.py` | in-chat mode: prints the next action until "FINISHED" |
| `prep.py [A B] [--review]` · `save.py` · `patch.py` · `finish.py [A B]` | single steps, by hand |
| `check.py A [B] \| --all [--short] [--fix]` | checks, read-only unless `--fix` |
| `review.py analyze \| todo \| final` | whole-book analysis, parts to review, closing with build and report |
| `build.py [--title] [--formats] [--partial] [--out]` | builds the book |
| `migrate.py <folder>_temp` | imports a [translate-book](https://github.com/deusyu/translate-book) or v1 project without touching finished parts |

Block and file formats are in [docs/FORMATS.md](docs/FORMATS.md); design notes are in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Tests

```bash
python3 tests/test_all.py
```

The tests use a short book written for them (`tests/test_book.md`) and a fake engine, so no model is called. They cover:

- the automatic mode, with one error to retry, the review and EPUB/DOCX/PDF output;
- the in-chat mode with simulated sub-agents;
- a second target language;
- rejection of incomplete parts;
- both migrations.

## Notes

- Translate only books you have the right to translate, for example for personal use or with permission.
- Each book lives in its own `<book>_temp/` folder; the skill never writes outside it.

## License

MIT. `scripts/vendor/convert.py` and `scripts/vendor/manifest.py` (input conversion and splitting) are copied unchanged from **translate-book** © 2025 Rainman, MIT licence; see [scripts/vendor/LICENSE-translate-book](scripts/vendor/LICENSE-translate-book). Everything else was written from scratch.
