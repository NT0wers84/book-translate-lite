---
name: book-translate-lite
description: Translates a whole book (EPUB/PDF/DOCX/MD) into any language from start to finish, with a final review and a ready EPUB/DOCX/PDF, using very few tokens. Use when the user wants to translate a book, check a translation's progress, stop/resume it, rerun the review, rebuild the book or edit its glossary.
version: 2.3.2
user-invocable: true
argument-hint: "[translate <book> <lang> · status · stop · resume · review · build · terms · config · doctor]"
license: MIT
---

# book-translate-lite

Everything goes through one command:

```
BTL="python3 <folder of this SKILL.md>/scripts/btl.py"
```

There is no `btl` on the PATH: always call it with the full `python3 …/btl.py` path above. Run it from anywhere. A job is found from a book path, its `<book>_temp` folder or part of its title; without one, the most recent job is used. The output of `btl` is short and written for the user: relay it in one or two sentences, in the user's language.

**Sandboxed agents (Codex):**

- `start`, `resume`, `review` and `stop` launch or stop the engine in the background, so they must run **outside the sandbox**. Run them with escalated permissions (`sandbox_permissions: "require_escalated"`) and propose the prefix rule `["python3", "<…>/scripts/btl.py"]` so the user approves btl once.
- If `btl` exits with code 3, it is telling you exactly this.
- `status`, `wait`, `log`, `jobs`, `terms` and `config` work inside the sandbox.

## What the user asks → what you run

| user says (or `/book-translate-lite …`) | run |
|---|---|
| "translate book.epub into French", `translate <book> <lang>` | `$BTL start "<book>" --to <code>`, adding `--title "…"` if they gave a translated title |
| "how is it going?", `status` | `$BTL status` |
| "stop", "pause" | `$BTL stop` |
| "continue", "resume" | `$BTL resume` |
| "review it again", "use Claude for the review" | `$BTL review --again [--engine claude]` |
| "rebuild the book", "make a PDF" | `$BTL build [--formats pdf]` |
| "it's a manual / an essay / a children's book / poems / a LitRPG" | `$BTL genre <technical|nonfiction|children|poetry|gamelit>` (or `--genre` on `start`) |
| "translate the next volume of the series" | `$BTL start "<book>" --to <code> --series "<previous volume's job>"` |
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
- **Genre:** pass `--genre` with the kind of book — `fiction` (default: novels), `nonfiction` (essays, history, biography, popular science), `technical` (manuals, programming, textbooks), `children`, `poetry`, `gamelit` (LitRPG/stat-based stories), `general`. Infer it from the title, the user's words or the first pages; if unsure, ask in one line.
- Anything that belongs to one book or series (names, house terms, forbidden forms) goes in that job (`btl terms add`, its `rules.md`, `btl config`), never in the skill's templates.
- **Series:** if the book is a later volume of a series already translated with btl (check `$BTL jobs`), always pass `--series "<previous volume's job>"`: it carries the glossary, rules and style over and puts the new job next to the old one. If `start` prints "Other jobs by …", ask the user whether it is the same series before running `btl resume`.
- If the run stops with "the engine cannot continue" (credits, usage limit, login), tell the user and offer the alternative it prints (other engine, or `$BTL next`).

## Automatic vs in-chat

- `start` and `resume` run the job **in the background** with the `codex` or `claude` CLI. The job continues on its own until the book and its report are ready, and you do not need to stay in the conversation. Tell the user they can ask for `status` at any time, and end your turn.
- **Do not poll** `status` in a loop and do not run `resume` while `status` says "running": every check costs tokens, and the job does not need you.
- If the user wants you to stay until the end (for example a goal like "translate it to the end"), run `$BTL wait --minutes 120`. It is one quiet call that returns when the book is finished or the run stopped. If it is still running, call it again. If it stopped, run `$BTL resume` once and report what `status` says.
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
