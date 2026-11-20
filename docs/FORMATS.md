# Formats

## Translation answer (`save.py`, automatic mode)

```
@@PART 0012@@
…translated text, same Markdown and same paragraphs as the source…
@@META@@
{"new_entities": [{"source": "Salt Market", "target_proposal": "Mercato del Sale", "category": "place", "evidence": "…"}],
 "conflicts":    [{"source": "Copper Gull", "current_target": "Gabbiano di Rame", "proposed_target": "Gabbiano Ramato", "reason": "…"}]}
@@PART 0013@@
…
```

- `@@META@@` is optional.
- With `save.py`, invalid META blocks the whole save. In automatic mode only the affected part is dropped, and it is then retried.

## Review answer (`patch.py`)

```
@@PART 0012@@
@@OLD@@
exact text copied from the translation (unique within the part)
@@NEW@@
corrected text
@@OLD@@
…
@@NEW@@
…
@@PART 0013@@
@@OK@@
```

A fix is applied only if `OLD` occurs exactly once in the part. It is undone if it makes a part that passed the check fail.

- The first original of every changed part is kept in `review/backup/`.
- Every applied fix is listed in `review/changes.md`.

## `terms.json`

```json
[{"source": "Brass Warden", "target": "Custode d’Ottone", "type": "fixed", "note": "automaton, male", "aliases": ["Warden"]}]
```

- **fixed** (F in tasks): the model never changes it. Proposed changes go to `state.json → fixed_conflicts`.
- **proposed** (P): a `conflicts` entry in a part's META can change it.
- A task includes only the terms whose `source`, or one of its `aliases`, occurs in the task's parts.

## `state.json`

```json
{"done": [1, 2], "meta_merged": [1, 2], "flagged": {"0002": ["…"]}, "reviewed": [1],
 "fixed_conflicts": [], "attempts": {"0002": 1}, "finished": false}
```

There are no hashes: a part is done when `output_chunkNNNN.md` exists. Editing the glossary never requeues finished parts.

## Working folder

```
<book>_temp/
  chunkNNNN.md  output_chunkNNNN.md  output_chunkNNNN.meta.json
  project.json rules.md terms.json candidates.json state.json
  _tasks/       tasks in progress (deleted when closed)
  review/       flags.json report.md changes.md backup/ FINAL_REPORT.md
  book/         <title>.epub .docx .pdf
  auto.log      automatic mode log
  input.md images/ manifest.json config.txt   (from the conversion)
```
