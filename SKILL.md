---
name: book-translate-lite
description: Translates a whole book (EPUB/PDF/DOCX/MD) into any language from start to finish, with a final review pass and a ready EPUB/DOCX/PDF, using very few tokens - script orchestrator, groups of parts per call, automatic checks and fixes. Use to translate a book or resume a translation (a <book>_temp folder with project.json).
---

# book-translate-lite

`S=<this skill's folder>/scripts`. Run every command **inside `<book>_temp/`**. The job runs **to the end of the book**: translation → review → EPUB/DOCX/PDF + `review/FINAL_REPORT.md`.

## 1. Setup (once)

- **Ask the user for the target language** if they did not say it. Use its code, for example `it`, `fr`, `de`, `es` or `ja`. Ask for the source language too if the book is not in English.
- New book: `python3 $S/init.py book.epub --to <code> [--from <code>]`, then `cd <book>_temp`.
- Existing translate-book or v1 project: `python3 $S/migrate.py <book>_temp`. Finished parts are never touched.
- Set the translated `title` in `project.json`.
- If the user has style wishes, add them to `rules.md`.
- If the user wants key names fixed, add them to `terms.json` with `"type": "fixed"`. Candidates are listed in `candidates.json`.

## 2A. Automatic mode (recommended: zero orchestration tokens)

This needs the `codex` or `claude` CLI on the machine.

```
python3 $S/auto.py --background [--engine codex|claude] [--review-engine claude]
python3 $S/auto.py --status        # when the user asks how it is going
```

- The script translates in parallel groups, retries rejected parts, runs the review and builds the book.
- If it stops, run it again: it resumes where it stopped.
- If it is stuck, read the last lines of `auto.log`.

## 2B. In-chat mode (this app's sub-agents)

Repeat until "FINISHED", without stopping:

1. Run `python3 $S/step.py`.
2. If it prints "LAUNCH NOW": start **all** the listed sub-agents **in one call**, each with its exact prompt and nothing else. Wait for them **in one wait**, then go back to 1.
3. If it prints "BLOCKED": report it to the user and carry on.
4. If it prints "FINISHED": give the user the summary in `review/FINAL_REPORT.md`.

`step.py` closes tasks, runs checks, updates the glossary, requeues rejected parts, and moves on to the review and the build by itself.

Rules:

- **Never read translations, tasks or the glossary.** Read only the output of `step.py` and the sub-agents' short replies.
- Do not fix by hand. Never retranslate finished parts.
- Keep every intermediate message to one line at most.
- A cheap model with low reasoning is enough for the orchestrator.

## 3. Last pass (optional)

If asked, review only the parts listed in `review/FINAL_REPORT.md`:

- apply fixes with `patch.py`, using the `@@PART NNNN@@ @@OLD@@ … @@NEW@@ …` format;
- then run `python3 $S/build.py`.

## Useful

`check.py --all --short` · `finish.py` (status) · `review.py analyze` · `build.py [--partial]`
