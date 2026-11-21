---
name: book-translate-lite
description: Translates a whole book (EPUB/PDF/DOCX/MD) into any language from start to finish, with a final review and a ready EPUB/DOCX/PDF, using very few tokens. Use when the user wants to translate a book, check a translation's progress, stop/resume it, rerun the review, rebuild the book or edit its glossary.
version: 2.3.0
user-invocable: true
argument-hint: "[translate <book> <lang> · status · stop · resume · review · build · terms · config · doctor]"
license: MIT
---

# book-translate-lite

Everything goes through one command:

```
BTL="python3 <folder of this SKILL.md>/scripts/btl.py"
```

Run it from anywhere. A job is found from a book path, its `<book>_temp` folder or part of its title; without one, the most recent job is used. The output of `btl` is short and written for the user: relay it in one or two sentences, in the user's language.

## What the user asks → what you run

| user says (or `/book-translate-lite …`) | run |
|---|---|
| "translate book.epub into French", `translate <book> <lang>` | `$BTL start "<book>" --to <code>`, adding `--title "…"` if they gave a translated title |
| "how is it going?", `status` | `$BTL status` |
| "stop", "pause" | `$BTL stop` |
| "continue", "resume" | `$BTL resume` |
| "review it again", "use Claude for the review" | `$BTL review --again [--engine claude]` |
| "rebuild the book", "make a PDF" | `$BTL build [--formats pdf]` |
| "translate the next volume / book 7 of the series" | `$BTL start "<book>" --to <code> --series "<previous volume's job>"` |
| "use the glossary of the previous book" (job already started) | `$BTL series [JOB] --from "<previous job>" --retro` |
| "translate X as Y", "always call him …" | `$BTL terms add "X" "Y"` (add `--proposed` if the user is unsure) |
| "change X to Y everywhere", "X was wrong in the parts already done" | `$BTL terms add "X" "Y" --retro` |
| "show the glossary" | `$BTL terms list [text]` |
| "set the title / engine / review…" | `$BTL config title="…"` · `engine=claude` · `review=flagged` |
| "what's needed?", installation problems | `$BTL doctor` |
| an old translate-book folder | `$BTL import "<folder>"` |

Rules for `start`:

- The **target language is required**. If the user did not give it, ask; never guess.
- Use the language code, for example `it`, `fr`, `de`, `es`, `pt` or `ja`.
- Add `--from <code>` only if the book is not in English.
- **Series:** if the book is a later volume of a series already translated with btl (check `$BTL jobs`), always pass `--series "<previous volume's job>"`: it carries the glossary, rules and style over and puts the new job next to the old one. If `start` prints "Other jobs by …", ask the user whether it is the same series before running `btl resume`.
- If the run stops with "the engine cannot continue" (credits, usage limit, login), tell the user and offer the alternative it prints (other engine, or `$BTL next`).

## Automatic vs in-chat

- `start` and `resume` run the job **in the background** with the `codex` or `claude` CLI. The job continues on its own until the book and its report are ready, and you do not need to stay in the conversation. Tell the user they can ask for `status` at any time.
- If `btl` says that no CLI engine is available, or the user asks to do it here (`start … --chat`), use the in-chat mode. Repeat these steps until `$BTL next` prints `FINISHED`:
  1. Run `$BTL next`.
  2. If it prints "LAUNCH NOW", start **all** the listed sub-agents **in one call**, each with its exact prompt and nothing else, and wait for them **in one wait**.
  3. Go back to 1. If it prints "BLOCKED", tell the user and keep going.

In both modes:

- **Never read** translations, tasks or `terms.json`; only `btl` output and the sub-agents' short replies.
- **Never edit translated parts by hand.**
- A cheap model with low reasoning is enough for this orchestration.

## When it is finished

`btl status` shows where the book (`book/…epub|docx|pdf`) and the report (`review/FINAL_REPORT.md`) are. Summarise the report for the user. If they want a last manual pass, read only the parts the report lists, fix them with `scripts/patch.py` (format in its header), then run `$BTL build`.
