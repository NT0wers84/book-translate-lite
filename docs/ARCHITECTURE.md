# Architecture and design choices

## Where the tokens go

On a real 291-part book, translated with an LLM orchestrator and sub-agents, the logs showed three costs:

- **Sub-agents.** Every tool call costs about 25–30k tokens of fixed context (system prompt, tools, history), while a translated part produces about 2.5k. The cost follows the **number of calls**, not the length of the text.
- **Orchestrator.** A conversation kept open for days reached about 400k tokens per call. It accounted for about **90%** of the total spend.
- **Skill file.** The original skill had a `SKILL.md` of about 7k tokens, loaded into every context.

## User interface

Users talk to their agent. The skill (`SKILL.md`, about 700 tokens) maps requests to **one command**, `btl`, whose output is short and written for humans:

- `btl start`, `status`, `stop`, `resume`, `review`, `build`, `terms`, `config` and `doctor`;
- `btl next` drives the in-chat mode.

A small registry (`~/.book-translate-lite/jobs.json`) lets the user refer to a job by part of its title.

## Answers

| problem | solution |
|---|---|
| expensive LLM orchestrator | `auto.py`: the orchestrator is a script. In chat, `step.py` reduces every step to one command with a few lines of output |
| too many calls per part | **one group of 3 parts = 1 call** in automatic mode, with no tools; 2 calls (`cat` the task + `save.py`) in chat |
| needless context | each task contains only the terms that occur, the rules and 600 characters of continuity |
| the model checks and fixes | `check.py` and `fix()`: checks and typography are deterministic |
| "to be retranslated" after every glossary change | state without hashes |
| EPUB tagged with the wrong language, single-entry table of contents | `build.py` uses pandoc with `lang` from `project.json` and `--split-level=1`: one chapter per `#` |
| jobs that stop halfway | rejected parts are retried with the list of errors, then accepted and flagged; rounds with no progress stop with a clear message; everything is resumable |

## Review

The review is separate from the translation, for three reasons:

1. **Flags** are computed on the whole book with the final glossary. For example: "this term is rendered differently in 12 parts". A single sub-agent cannot see this.
2. The **review engine** can be stronger: for example Claude for the review and Codex at low reasoning for the translation.
3. The reviewer returns only **targeted fixes**, so the output is cheap. Fixes that are not found, or that break the structure, are rejected.

## Languages

All instructions to the model are in English. The target language is a parameter, and each **language profile** adds two things:

- `templates/languages.json`: quotes, apostrophes, automatic replacements, table of contents title;
- `templates/rules/<code>.md`: publishing conventions (dialogue punctuation, narrative tense, number format).

Without a profile, `templates/rules/generic.md` asks the model to follow the target language's own publishing conventions.

## Reuse

From translate-book (MIT), `convert.py` and `manifest.py` are reused unchanged. They handle the Calibre → HTML → Markdown conversion, notes, images and splitting. The part format (`chunkNNNN.md` / `output_chunkNNNN.md` / `.meta.json`) is compatible, so `migrate.py` can import projects started with translate-book.
