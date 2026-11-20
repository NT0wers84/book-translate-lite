# book-translate-lite

**Translate a whole book into any language by asking your AI agent.** It runs to the end on its own and gives you the finished EPUB, DOCX and PDF plus a review report. It uses very few tokens.

Works with **Claude Code** and **Codex** (app or CLI). Input formats: EPUB, PDF, DOCX and Markdown.

```
You:    Translate ~/Books/The Clockwork Lighthouse.epub into Italian.
Agent:  Started: 41 parts, en → it. It will translate, review and build the book on its own.
        Ask me "how is it going?" whenever you like.
…
You:    How is it going?
Agent:  Il Faro a Orologeria — translating 28/41 (68%), running.
…
Agent:  Finished. book/Il Faro a Orologeria.epub (+ docx, pdf). The review applied 37 fixes;
        2 parts are worth a quick look (see review/FINAL_REPORT.md).
```

## Install

**Claude Code:**

```
/plugin marketplace add NT0wers84/book-translate-lite
/plugin install book-translate-lite@book-translate-lite
```

**Codex:**

```bash
codex plugin marketplace add NT0wers84/book-translate-lite
codex plugin add book-translate-lite@book-translate-lite
```

**Manual install** (both apps, plus a `btl` command in your terminal):

```bash
git clone https://github.com/NT0wers84/book-translate-lite.git
cd book-translate-lite && ./install.sh
```

Requirements:

- Python 3.9+, [pandoc](https://pandoc.org/installing.html) and [Calibre](https://calibre-ebook.com).
- For the hands-off background mode, also the [Codex CLI](https://github.com/openai/codex) or the [Claude Code CLI](https://docs.anthropic.com/claude-code).
- Without a CLI, the agent translates inside the chat instead.

To see what is missing, ask the agent *"check the book translator setup"* or run `btl doctor`.

## Use it

Just talk to the agent. In Claude Code you can also type `/book-translate-lite …`.

| you say | what happens |
|---|---|
| *Translate `book.epub` into French* | sets up the job and starts translating in the background |
| *Translate it into German, title "Der Leuchtturm"* | the same, with the translated title |
| *How is it going?* | progress, phase, where the book and the report are |
| *Stop* / *Continue* | stops it, and later resumes it where it was |
| *Always translate "Brass Warden" as "Custode d’Ottone"* | adds a fixed glossary term |
| *Show the glossary* | lists the terms (fixed or proposed) |
| *Use Claude for the review* / *Review it again* | reruns the final review, then rebuilds the book |
| *Make a PDF* / *Rebuild the book* | builds the formats again |
| *Check the setup* | lists what is installed and what is missing |

The agent always asks for the target language if you did not give it.

## The `btl` command

The agent uses one command, `btl`, and you can use it too:

```
btl start BOOK --to LANG [--from LANG] [--title "…"] [--engine codex|claude] [--review-engine claude]
btl status [JOB]             btl stop [JOB]            btl resume [JOB]
btl review [JOB] [--again] [--flagged] [--engine claude]
btl build [JOB] [--formats epub,docx,pdf]
btl terms list [TEXT] | add SOURCE TARGET [--proposed] | remove SOURCE
btl config [KEY=VALUE …]     btl log [JOB]             btl jobs     btl doctor
btl next [JOB]               (in-chat mode: tells the agent which sub-agents to launch)
btl import FOLDER            (projects started with translate-book or v1)
```

`JOB` can be the book file, its `<book>_temp` folder, or part of the title. Without it, `btl` uses the current folder's job or the most recent one.

## What it does

```
book.epub ─▶ parts ─▶ translation in groups ─▶ checks ─▶ review ─▶ EPUB · DOCX · PDF
                      (engine, in parallel)    (scripts)  (engine)    + FINAL_REPORT.md
```

1. **Setup.** Calibre converts the book to Markdown, split into parts of about 6,000 characters, and recurring names are collected as glossary candidates.
2. **Translation.** Groups of 3 parts are translated in parallel. Every answer is checked: paragraphs, bold and italics, images, headings, glossary terms, forbidden forms. Rejected parts are retranslated with the list of errors. New names proposed by the model go into the glossary.
3. **Review.** The whole book is scanned:
   - terms rendered differently in different parts;
   - sentences left in the source language;
   - quote and punctuation problems.

   Then the review engine (which can be a different one, for example Claude) re-reads source and translation and makes targeted fixes. Fixes that would break the structure are rejected, and the originals are kept.
4. **Book.** pandoc builds the EPUB and DOCX and Calibre the PDF, with the correct language tag, a full table of contents and styled system messages. The cover comes from the original EPUB (or `images/cover.*`); scene breaks are never doubled. Optional title-page lines: `btl config subtitle="Series, volume 6" rights="Personal use only"`.
5. **Report.** `review/FINAL_REPORT.md` lists what is still worth a look.

Everything stays in a `<book>_temp/` folder next to the book. You can stop and resume at any time.

### Why it uses few tokens

With typical setups, most of the cost is the **orchestrating conversation**, which grows with every step. Here:

- The orchestrator is a **script**. Each group of parts is a single model call with a self-contained task, so no model spends tokens coordinating.
- Each task holds only what that group needs: the rules, the glossary terms that occur in those parts, and a short continuity excerpt.
- Checks and typography fixes are done by scripts, not by the model.

Details are in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Languages

Any target language works. Some have a **profile** with typography and publishing conventions:

| profile | quotes | notes |
|---|---|---|
| Italian `it` | «» | punctuation outside quotes, *passato remoto*, `Okay`→`Ok` |
| French `fr` | « » | non-breaking spaces, *passé simple* |
| Spanish `es` | «» | dialogue with raya, ¿ ¡ |
| German `de` | „“ | Präteritum, consistent du/Sie |
| English `en` | “” | |
| `pt` `nl` `pl` `ja` `zh` `ko` | profile typography | generic rules |

Adding a language takes a few lines: see [docs/LANGUAGES.md](docs/LANGUAGES.md). Pull requests are welcome.

## Settings

Change settings by telling the agent, or with `btl config KEY=VALUE`. Everything is stored in the job's `project.json`.

| key | default | meaning |
|---|---|---|
| `title`, `author` | from the book | metadata of the translated book |
| `engine`, `model`, `reasoning` | `codex`, —, `low` | translation engine (`codex`, `claude`, or `command` with `engine_command`) |
| `review_engine`, `review_model`, `review_reasoning` | same as translation, —, `medium` | review engine |
| `review` | `full` | `full`, `flagged` (only parts with problems) or `none` |
| `group_size`, `parallel`, `retries` | 3, 3, 2 | parts per call, calls at once, retries of a rejected part |
| `replacements`, `forbidden`, `uppercase_chat` | from the language profile | automatic fixes, blocking forms, all-caps chat names |
| `formats` | `epub,docx,pdf` | output formats |

The per-book style rules live in `rules.md`, and the glossary in `terms.json`.

## Repository layout

```
skills/book-translate-lite/   the skill: SKILL.md, scripts/ (btl.py and the pipeline), templates/
.claude-plugin/ .codex-plugin/ .agents/   plugin and marketplace manifests
docs/  tests/  install.sh
```

Tests run without any model, using a fake engine and a short book written for them:

```bash
python3 tests/test_all.py
```

## Notes

- Translate only books you have the right to translate, for example for personal use or with permission.

## License

MIT. `skills/book-translate-lite/scripts/vendor/convert.py` and `manifest.py`, which handle input conversion and splitting, are copied unchanged from **translate-book** © 2025 Rainman (MIT); see `scripts/vendor/LICENSE-translate-book`. Everything else was written from scratch.
